"""`R4-07` -- the invitation uniform-failure matrix, and §7.1's motivating assertion.

Scope: the causes that can be exercised in one process. The race cases need two genuine
PostgreSQL connections and live in `test_rca001_concurrent_invitations.py`.

## What this file adds, and what was already delivered

`R4-07`'s obligations accumulated across §3, §4.1, §6.1.1, §7 and §9, and the reordering that put
`R4-06` before `R4-05` meant several landed early. Recorded here rather than re-asserted, because
two tests asserting one property drift apart -- the divergence class
`test_every_fake_implements_its_whole_protocol` exists to catch.

| Obligation | Where it lives |
|---|---|
| Cross-organization revoke, `B` still open | `..._invitation_service.py`,
  `TestRevocationIsScopedToTheOrganization` |
| Addressee mismatch (a forwarded token) | `..._invitation_redemption.py`,
  `TestTheAddresseeMustBeTheActor` |
| `actor.account.email is None` (a tombstone) | same class |
| Demotion leaves invitations open | `..._invitation_cascades.py`,
  `TestDemotionLeavesInvitationsOpen` |
| Canonical matching at issuance and signup | both files, one test each |

What remains, and is here: **a correct secret presented against a non-open invitation** (§3 owes
this and it is not the wrong-secret case), **the replacement-account transfer** §7.1 exists to
prevent, and the refusal-cause table that makes the uniformity claim one assertion rather than
several.

## The uniformity claim, and why it is asserted as message equality

`FR-025` and §5 require every refusal to be indistinguishable. A test asserting only that
redemption *raised* passes on an implementation that discloses which check failed -- so every case
below asserts `str(refusal.value) == INVITATION_FAILURE`, and the parametrized table asserts the
whole set collapses to one message rather than checking each in isolation.
"""

from __future__ import annotations

import itertools
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.actor_resolution import ActorResolver, ResolvedActor
from khepri.rca.errors import INVITATION_FAILURE, InvitationOperationFailed
from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.invitation_service import InvitationService
from khepri.rca.invitations import InvitationOffer, parse_token
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import MEMBER_ROLE, OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    factory_fixture,
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=7)
LIFETIME = timedelta(hours=12)
CREDENTIAL = "correct horse battery staple"
PURGE_HORIZON = NOW + timedelta(days=800)

_COUNTER = itertools.count()


def _account(factory: sessionmaker, label: str) -> tuple[str, str]:
    email = f"r407-{label}{next(_COUNTER)}@example.com"
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


def _offer(organization_id: str, issued_by: str, target: str) -> InvitationOffer:
    return InvitationOffer(
        organization_id=organization_id,
        intended_role=MEMBER_ROLE,
        target_identity=target,
        issued_by=issued_by,
    )


def _actor(factory: sessionmaker, account_id: str) -> ResolvedActor:
    sessions = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
    token = sessions.create(account_id, now=NOW)
    resolver = ActorResolver(
        sessions, LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory))
    )
    return resolver.resolve_actor(token, now=NOW)


def _role_of(factory: sessionmaker, organization_id: str, account_id: str) -> str | None:
    membership = SqlOrganizationStore(factory).get_membership(organization_id, account_id)
    return None if membership is None else membership.role


def _disable_and_purge(factory: sessionmaker, account_id: str) -> None:
    """Take an account through disablement to tombstone, as `KHEPRI-DEC-015` §2b does."""
    accounts = SqlAccountStore(factory)
    live = accounts.get_account(account_id)
    assert live is not None
    assert accounts.save_account(live.disabled(now=NOW))
    assert accounts.purge_if_still_eligible(account_id, PURGE_HORIZON)


class _Context(NamedTuple):
    """What every cause-builder below needs to construct its token."""

    organization_id: str
    owner_id: str
    invitee_email: str


#: §5's refusal causes, each with a builder method named `_<cause>` on the class below.
#:
#: A list rather than six branches: a cause added here without a builder fails with an
#: `AttributeError` naming the missing method, which is louder than an `elif` nobody wrote.
_CAUSES = (
    "unknown_invitation",
    "malformed_token",
    "wrong_secret",
    "expired",
    "revoked",
    "foreign_addressee",
)


class TestACorrectSecretAgainstANonOpenInvitation:
    """§3 -- the right secret against a row that is no longer open.

    **Which check refuses depends on the cause, and that is worth stating precisely** because the
    obvious reading of this obligation is wrong. For an *expired* invitation the secret verification
    is what refuses, not the state check: `find_for_redemption` destroys the verifier of an expired
    row in the transaction that reads it (§3's destroy-on-touch), so by the time `redeem` compares,
    there is no verifier left and `verify_secret` fails. Verified by disclosing a distinct message
    from the openness branch and watching nothing fail -- the expired path never reaches it.

    That is the design working, not a gap: §5 requires an expired invitation to be indistinguishable
    from an unknown one, and destroying the verifier makes them the *same* refusal by construction
    rather than by two branches agreeing on a message. For a revoked invitation the row is gone
    entirely (§4.1 deletes), and for a replayed one the verifier was destroyed at the first
    redemption. So all three converge on the verification branch, and
    `TestEveryCauseCollapsesToOneRefusal` is what proves that branch discloses nothing.

    What these tests are therefore worth: they assert the **outcome** for a caller holding genuine
    material -- refused, and no membership -- which is the requirement. They do not assert which
    internal check fired, because pinning that would break the moment the destroy-on-touch
    rule moved, and the rule is more load-bearing than its ordering.
    """

    def test_expired(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "expired")
        token = _service(factory).issue(
            _offer(organization_id, owner_id, invitee_email),
            expires_at=NOW + timedelta(hours=1),
            now=NOW,
        )

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(
                token, _actor(factory, invitee_id), now=NOW + timedelta(hours=2)
            )

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, invitee_id) is None

    def test_revoked(self, factory: sessionmaker) -> None:
        """Revocation deletes the row (§4.1), so a correct secret meets an absent invitation."""
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "revoked")
        service = _service(factory)
        token = service.issue(
            _offer(organization_id, owner_id, invitee_email), expires_at=LATER, now=NOW
        )
        invitation_id, _ = parse_token(token)
        service.revoke(organization_id, invitation_id, actor_account_id=owner_id, now=NOW)

        with pytest.raises(InvitationOperationFailed) as refusal:
            service.redeem(token, _actor(factory, invitee_id), now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, invitee_id) is None

    def test_already_redeemed(self, factory: sessionmaker) -> None:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "replayed")
        service = _service(factory)
        token = service.issue(
            _offer(organization_id, owner_id, invitee_email), expires_at=LATER, now=NOW
        )
        service.redeem(token, _actor(factory, invitee_id), now=NOW)

        with pytest.raises(InvitationOperationFailed) as refusal:
            service.redeem(token, _actor(factory, invitee_id), now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE

    def test_the_verifier_is_gone_by_the_time_expiry_refuses(
        self, factory: sessionmaker
    ) -> None:
        """§3's destroy-on-touch, observed through the verb that triggers it.

        `KHEPRI-DEC-015` §5 measures the harm of a surviving verifier in days, and expiry fires no
        event -- so nothing happens at the horizon unless a read makes it happen. The read that
        refuses is the one that destroys, which is what makes an actively-presented expired
        invitation the case that matters most.
        """
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, "destroyed")
        token = _service(factory).issue(
            _offer(organization_id, owner_id, invitee_email),
            expires_at=NOW + timedelta(hours=1),
            now=NOW,
        )
        invitation_id, _ = parse_token(token)

        with pytest.raises(InvitationOperationFailed):
            _service(factory).redeem(
                token, _actor(factory, invitee_id), now=NOW + timedelta(hours=2)
            )

        stored = SqlInvitationStore(factory).get_invitation(
            invitation_id, now=NOW + timedelta(hours=2)
        )
        assert stored is not None
        assert stored.verifier is None, (
            "the refusing read must destroy the expired verifier; without it the bytes survive "
            "until an unscheduled sweeper runs, and `R4-03` records that no scheduler exists"
        )


class TestTheReplacementAccountCannotRedeem:
    """§7.1's motivating assertion, deferred to `R4-07` because it needs a verb `R4-05` added.

    **The transfer this prevents.** An address is released when its account is purged, so a
    *different* person can register it. By §6.1.1's own addressee rule that new account is then the
    legitimate addressee of an invitation issued to someone else entirely -- so without the purge
    cascade it redeems into an organization it was never invited to. §7.1: "The failure is not
    'revocation missed a row'; it is that a purge plus a stale invitation transfers an offer of
    membership from one person to another."

    `R4-06` asserted the **state** -- that the purge closes the invitation. This asserts the
    **consequence**, which is what the requirement is actually about, and it needed `redeem` to
    exist. §7.1 split them for exactly that reason.
    """

    def test_a_new_account_at_a_released_address_is_refused(
        self, factory: sessionmaker
    ) -> None:
        organization_id, owner_id = _organization(factory)
        original_id, address = _account(factory, "released")
        token = _service(factory).issue(
            _offer(organization_id, owner_id, address), expires_at=LATER, now=NOW
        )

        _disable_and_purge(factory, original_id)

        # A different person registers the released address. `create_account` succeeds because the
        # tombstone holds no email, which is what makes the address reusable in the first place.
        replacement = AccountService(SqlAccountStore(factory)).create_account(
            address, CREDENTIAL
        )
        assert replacement.account_id != original_id

        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(token, _actor(factory, replacement.account_id), now=NOW)

        assert str(refusal.value) == INVITATION_FAILURE
        assert _role_of(factory, organization_id, replacement.account_id) is None, (
            "a replacement account at a released address must not inherit an invitation addressed "
            "to the person who held it; that is the identity transfer §7.1 exists to prevent"
        )

    def test_the_invitation_is_gone_rather_than_merely_unredeemable(
        self, factory: sessionmaker
    ) -> None:
        """The purge cascade deletes, so there is nothing left to redeem.

        Asserted separately because the refusal above would also hold if the invitation survived
        and some later check refused it -- and a surviving row means a retained `target_identity`
        whose two authorized purposes have both lapsed, which §3 forbids independently of whether
        anyone can redeem it.
        """
        organization_id, owner_id = _organization(factory)
        original_id, address = _account(factory, "gone")
        token = _service(factory).issue(
            _offer(organization_id, owner_id, address), expires_at=LATER, now=NOW
        )
        invitation_id, _ = parse_token(token)

        _disable_and_purge(factory, original_id)

        assert (
            SqlInvitationStore(factory).get_invitation(invitation_id, now=NOW) is None
        ), "the purge cascade deletes the row rather than marking it"


class TestEveryCauseCollapsesToOneRefusal:
    """`FR-025` as one assertion over the whole cause set, not several in isolation.

    Each case is refused for a different reason and the test collects the messages, so uniformity is
    asserted as a property of the *set*. Checking each case's message where it is raised proves the
    message is right; checking them together proves nothing distinguishes them, which is the
    requirement. Verified: two distinct messages on the verification branch fail nine tests.

    **A dispatch table rather than an if/elif chain.** The chain was six branches in one method,
    which CodeScene scores as Complex Method -- and the table reads closer to §5's own state list,
    where a missing cause is a missing row rather than a branch nobody counts.
    """

    def _unknown_invitation(self, factory: sessionmaker, ctx: _Context) -> tuple[str, datetime]:
        return "kci1.inv_absent.secret", NOW

    def _malformed_token(self, factory: sessionmaker, ctx: _Context) -> tuple[str, datetime]:
        return "not-a-token", NOW

    def _wrong_secret(self, factory: sessionmaker, ctx: _Context) -> tuple[str, datetime]:
        issued = _service(factory).issue(
            _offer(ctx.organization_id, ctx.owner_id, ctx.invitee_email),
            expires_at=LATER,
            now=NOW,
        )
        return f"kci1.{parse_token(issued)[0]}.wrong-secret", NOW

    def _expired(self, factory: sessionmaker, ctx: _Context) -> tuple[str, datetime]:
        token = _service(factory).issue(
            _offer(ctx.organization_id, ctx.owner_id, ctx.invitee_email),
            expires_at=NOW + timedelta(hours=1),
            now=NOW,
        )
        return token, NOW + timedelta(hours=2)

    def _revoked(self, factory: sessionmaker, ctx: _Context) -> tuple[str, datetime]:
        service = _service(factory)
        token = service.issue(
            _offer(ctx.organization_id, ctx.owner_id, ctx.invitee_email),
            expires_at=LATER,
            now=NOW,
        )
        service.revoke(
            ctx.organization_id, parse_token(token)[0], actor_account_id=ctx.owner_id, now=NOW
        )
        return token, NOW

    def _foreign_addressee(self, factory: sessionmaker, ctx: _Context) -> tuple[str, datetime]:
        _, other_email = _account(factory, "other")
        token = _service(factory).issue(
            _offer(ctx.organization_id, ctx.owner_id, other_email), expires_at=LATER, now=NOW
        )
        return token, NOW

    def _refusal_for(self, factory: sessionmaker, cause: str) -> str:
        organization_id, owner_id = _organization(factory)
        invitee_id, invitee_email = _account(factory, f"m{cause}")
        ctx = _Context(organization_id, owner_id, invitee_email)

        token, moment = getattr(self, f"_{cause}")(factory, ctx)
        with pytest.raises(InvitationOperationFailed) as refusal:
            _service(factory).redeem(token, _actor(factory, invitee_id), now=moment)
        return str(refusal.value)

    @pytest.mark.parametrize("cause", _CAUSES)
    def test_the_message_is_the_uniform_one(self, factory: sessionmaker, cause: str) -> None:
        assert self._refusal_for(factory, cause) == INVITATION_FAILURE

    def test_no_cause_is_distinguishable_from_another(self, factory: sessionmaker) -> None:
        """The set assertion: six causes, one message.

        This is the test that fails if a later slice adds a helpful message to any one branch --
        the realistic regression, since each branch looks harmless on its own.
        """
        messages = {self._refusal_for(factory, cause) for cause in _CAUSES}

        assert messages == {INVITATION_FAILURE}, (
            f"six distinct causes produced {len(messages)} distinct messages: "
            f"{sorted(messages)}; `FR-025` requires a denial for an unreachable object to be "
            "indistinguishable from one for an object that does not exist"
        )
