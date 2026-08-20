"""`R4-05` -- one-time authenticated redemption into exactly one membership.

Scope: `redeem` and the store method it writes through. The uniform-failure matrix is `R4-07`, which
also owns §7.1's two-connection blocking race and the "replacement account cannot redeem" case.

**Route B, per §6.2's recommendation.** At-most-once rests on a conditional `UPDATE` affecting
exactly one row rather than on a `SELECT ... FOR UPDATE` of the invitation. §6.2's 2026-08-18
correction notes that §6.1's account-row lock is unavoidable either way, so the two routes are
closer than the original text implied and Route A is defensible -- but Route B still avoids a
*second* predicate-by-predicate compilation test, and leaves the at-most-once claim resting on
`rowcount` rather than on a lock whose absence a green SQLite suite would hide.

**What is asserted here and what cannot be.** Four of §6.1's five steps are observable from one
process: the signature admits no caller-named account, the addressee check, the post-lock expiry
re-read, and at-most-once. The **account-liveness re-read** is a different case,
recorded rather than faked -- see `TestTheAccountLivenessReRead`.

**The refusal is one refusal.** §5 and `FR-025`: a wrong secret, an expired invitation, a revoked
one, an addressee mismatch, a tombstone actor, and an already-redeemed token all produce the same
`InvitationOperationFailed(INVITATION_FAILURE)`. Tests assert the message equality, not merely that
something raised -- a test asserting only "redemption fails" passes on an implementation that
discloses which check failed.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import Account, AccountService
from khepri.rca.actor_resolution import ActorResolver, ResolvedActor
from khepri.rca.errors import INVITATION_FAILURE, InvitationOperationFailed
from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.invitation_service import InvitationService
from khepri.rca.invitations import InvitationOffer, parse_token
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import (
    MEMBER_ROLE,
    OWNER_ROLE,
    Membership,
    MembershipEvent,
    OrganizationService,
)
from khepri.rca.persistence import (
    InvitationRow,
    MembershipEventRow,
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    factory_fixture,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=7)
LIFETIME = timedelta(hours=12)
CREDENTIAL = "correct horse battery staple"

_COUNTER = itertools.count()


def _account(factory: sessionmaker, label: str) -> tuple[str, str]:
    """A registered account. Returns `(account_id, canonical_email)`."""
    email = f"r405-{label}{next(_COUNTER)}@example.com"
    account = AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL)
    return account.account_id, email


def _organization(factory: sessionmaker) -> tuple[str, str]:
    owner_id, _ = _account(factory, "owner")
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        f"Acme {next(_COUNTER)}", owner_id, now=NOW
    )
    return organization.organization_id, owner_id


def _service(factory: sessionmaker) -> InvitationService:
    return InvitationService(SqlInvitationStore(factory))


def _actor(factory: sessionmaker, account_id: str) -> ResolvedActor:
    """A resolved actor, through the real resolver.

    Through `ActorResolver` rather than by construction, so the fixture cannot represent a state
    the production path refuses to produce -- `assert_account_active` is part of what makes a
    `ResolvedActor` mean what §6.1 says it means.
    """
    sessions = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
    token = sessions.create(account_id, now=NOW)
    resolver = ActorResolver(
        sessions, LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory))
    )
    return resolver.resolve_actor(token, now=NOW)


def _invite(
    factory: sessionmaker,
    offer: InvitationOffer,
    *,
    expires_at: datetime = LATER,
) -> str:
    """An open invitation. Returns its token.

    Takes the `InvitationOffer` rather than its fields, matching `InvitationService.issue`. The flat
    form had six parameters, which CodeScene scores as Excess Number of Function Arguments -- the
    third occurrence of that shape in this program, so the grouping is now the default rather than a
    fix applied after a gate failure.
    """
    return _service(factory).issue(offer, expires_at=expires_at, now=NOW)


def _offer(
    organization_id: str,
    issued_by: str,
    target: str,
    role: str = MEMBER_ROLE,
) -> InvitationOffer:
    """The grouped inputs `issue` takes."""
    return InvitationOffer(
        organization_id=organization_id,
        intended_role=role,
        target_identity=target,
        issued_by=issued_by,
    )


def _role_of(factory: sessionmaker, organization_id: str, account_id: str) -> str | None:
    """The live role, read from the store rather than from any returned object."""
    membership = SqlOrganizationStore(factory).get_membership(organization_id, account_id)
    return None if membership is None else membership.role


def _memberships(factory: sessionmaker, organization_id: str) -> int:
    with factory() as database:
        return len(
            database.query(MembershipRow)
            .filter(MembershipRow.organization_id == organization_id)
            .all()
        )


class TestTheSignatureAdmitsNoCallerNamedAccount:
    """§6's correction: `redeem(token, actor, *, now)`, never an `account_id` parameter.

    A caller-supplied `account_id` lets any holder of a stolen token name **someone else's**
    account -- or an account they hold no session for -- and the membership is created for them.
    `FR-019` requires an *authenticated* account, and a parameter is not authentication. Asserted
    against the signature because that is the only place the property lives: no runtime test can
    prove the absence of a parameter.
    """

    def test_redeem_takes_an_actor_and_no_account_identifier(self) -> None:
        import inspect

        parameters = inspect.signature(InvitationService.redeem).parameters

        assert "actor" in parameters, "the account must come from a resolved actor"
        assert "account_id" not in parameters, (
            "a caller-supplied account identifier is the defect §6's correction removed: it lets a "
            "token holder name any account, which `FR-019` forbids"
        )
        assert parameters["actor"].annotation in (
            "ResolvedActor",
            ResolvedActor,
        ), "the actor is a `ResolvedActor`, carrying a session that was checked live"


class TestTheHappyPath:
    """`FR-018` -- exactly one membership, at the invitation's `intended_role`."""

    def test_redemption_creates_the_membership(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "invitee")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))

        _service(factory).redeem(token, _actor(factory, invitee_id), now=NOW)

        assert _role_of(factory, organization_id, invitee_id) == MEMBER_ROLE

    def test_the_intended_role_is_honoured(self, factory: sessionmaker) -> None:
        """An invitation naming `owner` creates an owner, not a member."""
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "coowner")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email, OWNER_ROLE))

        _service(factory).redeem(token, _actor(factory, invitee_id), now=NOW)

        assert _role_of(factory, organization_id, invitee_id) == OWNER_ROLE

    def test_the_invitation_is_marked_redeemed(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "marked")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))
        invitation_id, _ = parse_token(token)

        _service(factory).redeem(token, _actor(factory, invitee_id), now=NOW)

        stored = SqlInvitationStore(factory).get_invitation(invitation_id, now=NOW)
        assert stored is not None
        assert stored.redeemed_at is not None
        assert stored.verifier is None, "the verifier is destroyed at the trigger (§3)"

    def test_an_fr014_event_records_the_creation(self, factory: sessionmaker) -> None:
        """§6.2: no new `MembershipEvent` kind -- `prior_role IS NULL`, `next_role = intended`.

        The nullability design carries the kind, and this is its first real test outside
        organization creation. The actor differs from the subject only here, which is what
        distinguishes a redemption from a founding.
        """
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "evented")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))

        _service(factory).redeem(token, _actor(factory, invitee_id), now=NOW)

        with factory() as database:
            events = (
                database.query(MembershipEventRow)
                .filter(
                    MembershipEventRow.organization_id == organization_id,
                    MembershipEventRow.account_id == invitee_id,
                )
                .all()
            )
        assert len(events) == 1
        assert events[0].prior_role is None, "a creation has no prior role"
        assert events[0].next_role == MEMBER_ROLE
        assert events[0].actor_account_id == invitee_id, (
            "the redeemer is the actor: they accepted, and `FR-014` attributes a change "
            "to whoever made it"
        )


class TestAtMostOnce:
    """`FR-017` -- and `FR-018`'s cardinality, which the composite key alone does not protect."""

    def test_a_second_redemption_by_the_same_account_is_refused(
        self, factory: sessionmaker
    ) -> None:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "twice")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))
        service = _service(factory)

        service.redeem(token, _actor(factory, invitee_id), now=NOW)

        with pytest.raises(InvitationOperationFailed) as refusal:
            service.redeem(token, _actor(factory, invitee_id), now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _memberships(factory, organization_id) == 2, "the owner and the one invitee"

    def test_a_second_account_cannot_redeem_the_same_token(
        self, factory: sessionmaker
    ) -> None:
        """§6.2's race, in its sequential form.

        Two *different* accounts produce two distinct primary keys, so
        `(organization_id, account_id)` refuses neither -- which is why the conditional
        update exists. The addressee check (§6.1.1) also refuses this, so the test asserts
        the membership count rather than the refusal alone: it must hold whichever guard
        fires first.
        """
        organization_id, owner_id = _organization(factory)
        first_id, first_email = _account(factory, "first")
        second_id, _ = _account(factory, "second")
        token = _invite(factory, _offer(organization_id, owner_id, first_email))
        service = _service(factory)

        service.redeem(token, _actor(factory, first_id), now=NOW)

        with pytest.raises(InvitationOperationFailed):
            service.redeem(token, _actor(factory, second_id), now=NOW)

        assert _role_of(factory, organization_id, second_id) is None
        assert _memberships(factory, organization_id) == 2

    def test_an_existing_member_is_refused_without_consuming_the_token(
        self, factory: sessionmaker
    ) -> None:
        """§6.2: refuse uniformly, and do not create a second membership.

        The composite key makes a duplicate unexpressible, so the point of the refusal is that the
        token is not silently consumed -- an owner re-inviting a member should not have the
        invitation vanish into an `IntegrityError`.
        """
        organization_id, owner_id = _organization(factory)
        member_id, member_email = _account(factory, "already")
        with factory.begin() as database:
            database.add(
                MembershipRow(
                    organization_id=organization_id,
                    account_id=member_id,
                    role=MEMBER_ROLE,
                )
            )
        token = _invite(factory, _offer(organization_id, owner_id, member_email))

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(token, _actor(factory, member_id), now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, member_id) == MEMBER_ROLE
        assert _memberships(factory, organization_id) == 2


class TestTheAddresseeMustBeTheActor:
    """§6.1.1 -- the two cases it names, neither of which is a happy path."""

    def test_a_forwarded_token_is_refused(self, factory: sessionmaker) -> None:
        """Account `B` presenting a **valid** token addressed to `A`.

        This is what makes a forwarded token useless, and forwarding is the realistic threat:
        invitations travel by email. Without it the invitation is a bearer credential whose
        addressee is decorative, and §3's claim that the retained target identity attributes the
        resulting membership becomes false.
        """
        organization_id, owner_id = _organization(factory)
        _, addressed_email = _account(factory, "addressed")
        bearer_id, _ = _account(factory, "bearer")
        token = _invite(factory, _offer(organization_id, owner_id, addressed_email))

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(token, _actor(factory, bearer_id), now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE, (
            "indistinguishable from a wrong secret; a caller must not learn that the token was "
            "valid but addressed elsewhere"
        )
        assert _role_of(factory, organization_id, bearer_id) is None

    def test_the_comparison_is_canonical(self, factory: sessionmaker) -> None:
        """A case difference must not refuse the addressee.

        The mirror of `R4-06`'s cascade test: folding on only one side silently spares an
        invitation there and silently refuses one here.
        """
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "mixed")
        token = _invite(
            factory, _offer(organization_id, owner_id, f"  {invitee_email.upper()} ")
        )

        _service(factory).redeem(token, _actor(factory, invitee_id), now=NOW)

        assert _role_of(factory, organization_id, invitee_id) == MEMBER_ROLE

    def test_a_tombstone_actor_is_refused(self, factory: sessionmaker) -> None:
        """`actor.account.email is None` fails **closed** (§6.1.1).

        A purged account cannot be shown to be the addressee, and nothing here reconstructs an
        identity from a tombstone. The actor is built directly because `assert_account_active`
        refuses a purged account, so the real resolver cannot produce this state -- which is the
        point: the guard must hold even if a future caller path does.
        """
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "tombstone")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))

        live = _actor(factory, invitee_id)
        purged = ResolvedActor(session=live.session, account=_purged(live.account))

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(token, purged, now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, invitee_id) is None


def _purged(account: Account) -> Account:
    """The tombstone form of an account, via the domain's own door."""
    return account.disabled(now=NOW).purged()


class TestTheSecretIsVerified:
    """`FR-016`/§5 -- the token's secret, on the uniform path."""

    def test_a_wrong_secret_is_refused(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "wrongsecret")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))
        invitation_id, _ = parse_token(token)
        forged = f"kci1.{invitation_id}.not-the-secret"

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(forged, _actor(factory, invitee_id), now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, invitee_id) is None

    def test_a_malformed_token_is_refused(self, factory: sessionmaker) -> None:
        organization_id, _ = _organization(factory)
        invitee_id, _ = _account(factory, "malformed")

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem("not-a-token", _actor(factory, invitee_id), now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _memberships(factory, organization_id) == 1

    def test_an_unknown_invitation_is_refused(self, factory: sessionmaker) -> None:
        organization_id, _ = _organization(factory)
        invitee_id, _ = _account(factory, "unknown")

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(
                "kci1.inv_absent.secret", _actor(factory, invitee_id), now=NOW
            )

        assert str(refusal.value) == INVITATION_FAILURE
        assert _memberships(factory, organization_id) == 1


class TestNonOpenInvitations:
    """§5's derived terminal states, each taking the same refusal."""

    def test_an_expired_invitation_is_refused(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "expired")
        token = _invite(
            factory,
            _offer(organization_id, owner_id, invitee_email),
            expires_at=NOW + timedelta(hours=1),
        )

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(
                token, _actor(factory, invitee_id), now=NOW + timedelta(hours=2)
            )

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, invitee_id) is None

    def test_a_revoked_invitation_is_refused(self, factory: sessionmaker) -> None:
        """Revocation deletes the row (§4.1), so this is the unknown-identifier path."""
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "revoked")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))
        invitation_id, _ = parse_token(token)
        service = _service(factory)
        service.revoke(organization_id, invitation_id, actor_account_id=owner_id, now=NOW)

        with pytest.raises(InvitationOperationFailed) as refusal:
            service.redeem(token, _actor(factory, invitee_id), now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, invitee_id) is None

    def test_expiry_between_verification_and_the_write_is_refused(
        self, factory: sessionmaker
    ) -> None:
        """§6.2: `:now` is re-read at transition time, not reused from verification.

        §5 verifies the secret before any lock is taken, and the transaction may then wait. An
        invitation open at verification can be expired by the time the conditional update runs, and
        a predicate checking only the two timestamp columns would let it win -- the row is still
        `NULL, NULL`, because expiry has no column.

        The wait is not simulated here; what is asserted is that the *statement* carries the
        expiry clause, by presenting a `now` past the horizon and seeing the write refuse. The
        clause's presence is what the mutation run proves.
        """
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "boundary")
        token = _invite(
            factory,
            _offer(organization_id, owner_id, invitee_email),
            expires_at=NOW + timedelta(hours=1),
        )

        with pytest.raises(InvitationOperationFailed):
            _service(factory).redeem(
                token, _actor(factory, invitee_id), now=NOW + timedelta(hours=1)
            )

        assert _role_of(factory, organization_id, invitee_id) is None, (
            "`expires_at > :now` is strict, so the horizon instant itself is not open"
        )


class TestTheAccountLivenessReRead:
    """§6.1 step 1 -- and the limits of what this slice can prove about it.

    **The requirement.** `ResolvedActor` carries an `Account` *snapshot*, read before the
    transaction opened. §6.1's correction of 2026-08-18: the transaction then takes a lock and may
    wait on a competing writer, so an account disabled inside that window would otherwise yield "a
    durable membership created for an account that is no longer an authenticated actor". The write
    is therefore conditioned on `can_act` re-evaluated on the account row read **under the lock**.

    **Why one process cannot reproduce the race.** Closing the window requires the two operations to
    contend on the same row, and demonstrating that requires a second connection holding a
    transaction open -- which §7.1 assigns to `R4-07` for its own race and which this slice's
    obligations do not include. What is reachable here is the *stale snapshot*, which is the half
    that the re-read exists to catch: an actor resolved while live, whose account is disabled before
    `redeem` is called.

    That case is genuinely load-bearing rather than a proxy: without the re-read, `redeem` trusts
    the snapshot and creates the membership. Verified by removing the re-read and watching this
    class fail.
    """

    def test_a_stale_actor_snapshot_does_not_authorize_a_membership(
        self, factory: sessionmaker
    ) -> None:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "stale")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))

        actor = _actor(factory, invitee_id)

        accounts = SqlAccountStore(factory)
        live = accounts.get_account(invitee_id)
        assert live is not None
        assert accounts.save_account(live.disabled(now=NOW))

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(token, actor, now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, invitee_id) is None, (
            "the actor's account snapshot was live when resolved and is disabled at the write; "
            "`FR-019`'s 'at the moment of acceptance' is a claim about the commit"
        )

    def test_the_invitation_is_not_consumed_by_a_refused_redemption(
        self, factory: sessionmaker
    ) -> None:
        """A refusal must leave the invitation open, or the account holder loses their offer.

        §6.1 notes the consumed-and-refused state "is not even recoverable by retry", which is why
        the refusal path must not mark the row.
        """
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "unconsumed")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))
        invitation_id, _ = parse_token(token)

        actor = _actor(factory, invitee_id)
        accounts = SqlAccountStore(factory)
        live = accounts.get_account(invitee_id)
        assert live is not None
        assert accounts.save_account(live.disabled(now=NOW))

        with pytest.raises(InvitationOperationFailed):
            _service(factory).redeem(token, actor, now=NOW)

        assert accounts.save_account(live.enabled())
        stored = SqlInvitationStore(factory).get_invitation(invitation_id, now=NOW)
        assert stored is not None
        assert stored.is_open_at(NOW), "a refused redemption leaves the invitation open"


class TestTheSessionMustBeLiveAtTheWrite:
    """§6.1 -- `Session.is_live_at(now)`, not `is_revoked`, evaluated as late as possible.

    Revoking a session does not touch `rca_accounts`, so `can_act` still passes: the account fix
    does not cover this. And expiry is the clock rather than a write, so no lock reaches it --
    §6.1's residual, which §8.5 records the owner accepting with `FR-019` read as the last check.
    """

    def test_a_revoked_session_does_not_authorize_a_membership(
        self, factory: sessionmaker
    ) -> None:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "revokedsession")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))

        sessions = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
        session_token = sessions.create(invitee_id, now=NOW)
        resolver = ActorResolver(
            sessions, LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory))
        )
        actor = resolver.resolve_actor(session_token, now=NOW)
        sessions.revoke(session_token, now=NOW)

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(token, actor, now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, invitee_id) is None

    def test_an_expired_session_does_not_authorize_a_membership(
        self, factory: sessionmaker
    ) -> None:
        """`is_live_at`, not `is_revoked`: expiry has no write to serialize against.

        Reaching past the combined predicate to the revocation half alone is the drift
        `accounts.py:68` warns about for `can_act`, and this is the test that catches it.
        """
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "expiredsession")
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))

        actor = _actor(factory, invitee_id)
        after_expiry = NOW + LIFETIME + timedelta(seconds=1)

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(token, actor, now=after_expiry)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, invitee_id) is None


class TestTheConditionalStatementIsTheAtMostOnceGuard:
    """Route B's statement, tested at the store because the service shadows it.

    **Why these bypass `redeem`.** The service pre-checks `invitation.is_open_at(now)` before
    calling the store, so every sequential path is refused before the conditional `UPDATE` runs.
    That pre-check is the cheap read; the statement is what makes the transition atomic, and its
    clauses exist precisely for the case the pre-check cannot catch -- two transactions both reading
    the invitation as open, which is §6.2's race. A test routed through the service can therefore
    never fail on them: verified by dropping `expires_at > :now`, `redeemed_at IS NULL`, and the
    `rowcount` check in turn and watching all 21 service-level tests stay green.

    So these call `redeem_into_membership` directly, with the row already in the state a losing
    concurrent transaction would find. That is as close as one process gets; the two-connection form
    is `R4-07`'s per §7.1.
    """

    def _prepare(self, factory, label):
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, label)
        token = _invite(factory, _offer(organization_id, owner_id, invitee_email))
        invitation_id, _ = parse_token(token)
        return organization_id, invitee_id, invitation_id

    def _attempt(self, factory, organization_id, account_id, invitation_id, *, now=NOW):
        return SqlInvitationStore(factory).redeem_into_membership(
            invitation_id,
            account_id=account_id,
            organization_id=organization_id,
            role=MEMBER_ROLE,
            now=now,
            membership=Membership.create(organization_id, account_id, MEMBER_ROLE),
            event=MembershipEvent.created(
                organization_id,
                account_id,
                MEMBER_ROLE,
                actor_account_id=account_id,
                now=NOW,
            ),
            session_id_hash=_actor(factory, account_id).session.session_id_hash,
        )

    def test_a_second_account_loses_on_an_already_redeemed_row(self, factory) -> None:
        """`redeemed_at IS NULL` -- the clause the loser of §6.2's race hits.

        Two *different* accounts produce two distinct primary keys, so the composite key refuses
        neither and the existing-member guard does not fire. Only the statement refuses.
        """
        organization_id, first_id, invitation_id = self._prepare(factory, "stmtfirst")
        assert self._attempt(factory, organization_id, first_id, invitation_id) is True

        second_id, _ = _account(factory, "stmtsecond")
        assert (
            self._attempt(factory, organization_id, second_id, invitation_id) is False
        ), (
            "without `redeemed_at IS NULL` both accounts win and `FR-018` is violated twice, with "
            "two memberships where the requirement permits one"
        )
        assert _role_of(factory, organization_id, second_id) is None
        assert _memberships(factory, organization_id) == 2

    def test_an_expired_row_is_refused_by_the_statement(self, factory) -> None:
        """`expires_at > :now`, with `now` re-read at transition time.

        §6.2: §5 verifies before the lock and the transaction may then wait, so an invitation open
        at verification can be expired when the statement runs -- and the two timestamp columns are
        still `NULL, NULL`, because expiry has no column.

        **Isolating this clause took two attempts, both recorded because each failed differently.**
        Advancing `now` past the default horizon also expires the session the helper
        resolves, so the session re-read refuses first and the clause is never reached --
        that version passed with the clause removed. Editing `expires_at` backwards instead
        violates `ck_rca_invitation_expiry_after_issuance`, which the schema refuses
        outright. What works is a short horizon at issuance and a `now` between issuance and
        expiry plus one second: the invitation is past its horizon, the session is still
        live, and only this clause can refuse.
        """
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "stmtexpired")
        short = NOW + timedelta(minutes=5)
        token = _invite(
            factory,
            _offer(organization_id, owner_id, invitee_email),
            expires_at=short,
        )
        invitation_id, _ = parse_token(token)
        just_expired = short + timedelta(seconds=1)

        assert (
            self._attempt(
                factory, organization_id, invitee_id, invitation_id, now=just_expired
            )
            is False
        ), (
            "the statement must refuse a row past its horizon; both timestamp columns are still "
            "NULL, so only `expires_at > :now` can refuse it"
        )
        assert _role_of(factory, organization_id, invitee_id) is None

    def test_a_revoked_row_is_refused_by_the_statement(self, factory) -> None:
        """`revoked_at IS NULL`, in the marked form only redeemed-then-revoked produces."""
        organization_id, invitee_id, invitation_id = self._prepare(factory, "stmtrevoked")
        with factory.begin() as database:
            row = database.get(InvitationRow, invitation_id)
            assert row is not None
            row.revoked_at = NOW

        assert self._attempt(factory, organization_id, invitee_id, invitation_id) is False
        assert _role_of(factory, organization_id, invitee_id) is None

    def test_no_membership_or_event_is_written_when_the_statement_refuses(
        self, factory
    ) -> None:
        """The `rowcount` check is what stops the two inserts.

        Without it the statement's refusal is ignored and all three writes proceed, so a membership
        commits for an invitation that was not open -- `FR-018`'s cardinality broken from the other
        side. This is the assertion that fails when `rowcount` is not consulted.
        """
        organization_id, invitee_id, invitation_id = self._prepare(factory, "stmtrowcount")
        with factory.begin() as database:
            row = database.get(InvitationRow, invitation_id)
            assert row is not None
            row.redeemed_at = NOW

        assert self._attempt(factory, organization_id, invitee_id, invitation_id) is False
        assert _role_of(factory, organization_id, invitee_id) is None
        with factory() as database:
            events = (
                database.query(MembershipEventRow)
                .filter(MembershipEventRow.account_id == invitee_id)
                .all()
            )
        assert events == [], "nor an `FR-014` event"
