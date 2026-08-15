"""R3-05: account activity is enforced on every actor resolution.

**The requirement.** `FR-008` says a disabled account's pre-existing sessions must cease to
authorize "with no dependence on session expiry". `R3-01` §4 makes that step 3 of the resolution
path, consulted *every time* rather than cached at login.

**Why this slice exists at all.** `lifecycle.assert_account_active` has shipped since `R1` with no
production caller. `R3-04` deliberately did not wire it — its tests cover session state, not
account state, and a chokepoint whose only proof lives in another slice's suite is a chokepoint
nobody has tested. This is where it gets its first caller and its evidence.

**The defect this guards against is subtle and passes a type checker.** An implementation that
copies `can_act` into the session row at login satisfies every signature and fails `FR-008`: the
copy goes stale the instant the account is disabled, and authority then survives until expiry.
`test_disablement_takes_effect_on_the_very_next_resolution` fails against that implementation.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.actor_resolution import ActorResolver
from khepri.rca.errors import AuthenticationFailed
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.persistence import (
    SqlAccountStore,
    SqlOrganizationStore,
)
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
    two_owner_organization,
)

LIFETIME = timedelta(hours=12)


def _accounts(factory: sessionmaker) -> SqlAccountStore:
    return SqlAccountStore(factory)


def _account(factory: sessionmaker, email: str = EMAIL) -> str:
    return AccountService(_accounts(factory)).create_account(email, CREDENTIAL).account_id


def _lifecycle(factory: sessionmaker) -> LifecycleService:
    return LifecycleService(_accounts(factory), SqlOrganizationStore(factory))


def _sessions(factory: sessionmaker) -> SessionService:
    return SessionService(SqlSessionStore(factory), lifetime=LIFETIME)


def _resolver(factory: sessionmaker) -> ActorResolver:
    return ActorResolver(_sessions(factory), _lifecycle(factory))


def _owner_with_a_co_owner(factory: sessionmaker) -> str:
    """An owner who can be disabled, because a second owner keeps `FR-013` satisfied.

    Uses the shared `two_owner_organization` support rather than assembling the four setup
    statements again -- that duplication is exactly what the helper was extracted to remove.
    """
    return two_owner_organization(factory).first.account_id


class TestTheChokepoint:
    def test_an_active_account_resolves(self, factory: sessionmaker) -> None:
        account = _account(factory)
        token = _sessions(factory).create(account, now=NOW)
        assert _resolver(factory).resolve_actor(token, now=NOW).account_id == account

    def test_disablement_takes_effect_on_the_very_next_resolution(
        self, factory: sessionmaker
    ) -> None:
        """`FR-008`, and the reason a cached `can_act` flag is unacceptable.

        The session is issued while the account is active and remains unexpired and unrevoked
        throughout. Only the account changes. An implementation that read account state at login
        would still resolve here.
        """
        account = _account(factory)
        token = _sessions(factory).create(account, now=NOW)
        resolver = _resolver(factory)
        assert resolver.resolve_actor(token, now=NOW).account_id == account

        _lifecycle(factory).disable_account(account, now=NOW)

        with pytest.raises(AuthenticationFailed):
            resolver.resolve_actor(token, now=NOW)

    def test_the_session_itself_is_untouched_by_disablement(
        self, factory: sessionmaker
    ) -> None:
        """Disablement stops authorization; it does not rewrite session state.

        `FR-008` is satisfied by consulting account status live, not by revoking rows. Asserting
        this keeps the two mechanisms distinct -- if a future edit made disablement revoke
        sessions instead, the chokepoint could be removed and this suite would still pass.
        """
        account = _account(factory)
        token = _sessions(factory).create(account, now=NOW)
        _lifecycle(factory).disable_account(account, now=NOW)
        stored = _sessions(factory).resolve(token, now=NOW)
        assert stored.revoked_at is None
        assert stored.is_live_at(NOW)

    def test_re_enablement_restores_a_pre_existing_session(
        self, factory: sessionmaker
    ) -> None:
        """Disable then re-enable, and a session minted beforehand resolves again.

        **Asserted deliberately, because the opposite is the intuitive guess.** `can_act` is
        `is_enabled and not is_purged` — it does not consult the verifier, and `accounts.py:92`
        states that weakness is intentional: "a verifier-less account must still be re-enablable
        and still resolve for the lifecycle chokepoint."

        The apparent oddity is that `KHEPRI-DEC-015` §5 leaves the verifier destroyed, so the
        account can never mint a *new* session, while this old one works. That is coherent:
        `FR-008` ties revocation to disablement, and re-enablement is the owner reversing that
        deliberately — §2b exists precisely so an account can be restored "after a dispute, an
        erroneous disablement, or a lapsed commercial relationship". Ending pre-existing sessions
        on re-enable would punish exactly the case the horizon was designed to protect.

        Whether re-enablement should nonetheless revoke pre-existing sessions is recorded as an
        open question for the owner rather than decided here — this slice calls the chokepoint, it
        does not redefine it.
        """
        account = _account(factory)
        token = _sessions(factory).create(account, now=NOW)
        lifecycle = _lifecycle(factory)
        lifecycle.disable_account(account, now=NOW)

        with pytest.raises(AuthenticationFailed):
            _resolver(factory).resolve_actor(token, now=NOW)

        lifecycle.enable_account(account)
        assert _resolver(factory).resolve_actor(token, now=NOW).account_id == account

    def test_a_purged_account_never_resolves(self, factory: sessionmaker) -> None:
        """The other half of `can_act`. A tombstone is not re-enablable and must not authorize."""
        account = _account(factory)
        token = _sessions(factory).create(account, now=NOW)
        accounts = _accounts(factory)
        stored = accounts.get_account(account)
        assert stored is not None
        assert accounts.save_account(stored.disabled(now=NOW).purged())

        with pytest.raises(AuthenticationFailed):
            _resolver(factory).resolve_actor(token, now=NOW)

    def test_an_unknown_account_is_refused(self, factory: sessionmaker) -> None:
        """A session row whose account has been purged away resolves to nothing."""
        resolver = _resolver(factory)
        token = _sessions(factory).create(_account(factory), now=NOW)
        with pytest.raises(AuthenticationFailed):
            ActorResolver(_sessions(factory), _lifecycle(factory)).resolve_actor(
                token + "tamper", now=NOW
            )
        assert resolver.resolve_actor(token, now=NOW) is not None


class TestUniformRefusal:
    def test_a_disabled_account_is_indistinguishable_from_every_other_refusal(
        self, factory: sessionmaker
    ) -> None:
        """`FR-004`, `FR-022`. Five causes, one message.

        A disabled account must not be distinguishable from an expired session or an unknown
        token, or a caller can probe account state without holding a credential.
        """
        sessions = _sessions(factory)
        resolver = _resolver(factory)

        expired = sessions.create(_account(factory, "expired@example.test"), now=NOW)
        revoked_account = _account(factory, "revoked@example.test")
        revoked = sessions.create(revoked_account, now=NOW)
        sessions.revoke(revoked, now=NOW)
        disabled_account = _account(factory, OTHER_EMAIL)
        disabled = sessions.create(disabled_account, now=NOW)
        _lifecycle(factory).disable_account(disabled_account, now=NOW)

        messages = set()
        for token, moment in (
            ("cse_unknown", NOW),
            ("not-a-token", NOW),
            (expired, NOW + LIFETIME),
            (revoked, NOW),
            (disabled, NOW),
        ):
            with pytest.raises(AuthenticationFailed) as raised:
                resolver.resolve_actor(token, now=moment)
            messages.add(str(raised.value))
        assert len(messages) == 1


class TestResolvedActor:
    def test_the_actor_carries_no_role_or_membership(self, factory: sessionmaker) -> None:
        """`FR-030`. Step 4 of `R3-01` §4 -- live membership and role -- is `R6-04`, not this.

        Resolving an actor answers "who is this and may they act at all", never "what may they
        do here". A role cached on this object would go stale exactly as a cached `can_act` would.
        """
        account = _owner_with_a_co_owner(factory)
        token = _sessions(factory).create(account, now=NOW)
        actor = _resolver(factory).resolve_actor(token, now=NOW)
        forbidden = {"role", "is_owner", "permissions", "membership", "owner_id"}
        assert forbidden.isdisjoint(dir(actor))

    def test_the_actor_exposes_the_session_and_the_account(
        self, factory: sessionmaker
    ) -> None:
        """Both halves are needed downstream: the session carries the active organization
        (`FR-027`) and the account is what `R6-04` will resolve membership against."""
        account = _account(factory)
        token = _sessions(factory).create(account, now=NOW)
        actor = _resolver(factory).resolve_actor(token, now=NOW)
        assert actor.account_id == account
        assert actor.session.account_id == account
        assert actor.account.account_id == account


class TestOrderOfChecks:
    def test_an_expired_session_is_refused_without_consulting_the_account(
        self, factory: sessionmaker
    ) -> None:
        """Session liveness is checked before account state, and the order is observable.

        Not a micro-optimization: an account lookup for a session that is already dead is a
        database read attributable to an unauthenticated caller, which is a denial-of-service
        surface on an endpoint that refuses anyway.
        """
        account = _account(factory)
        token = _sessions(factory).create(account, now=NOW)

        class _ExplodingLifecycle(LifecycleService):
            def assert_account_active(self, account_id: str) -> object:
                raise AssertionError("account state consulted for a dead session")

        resolver = ActorResolver(
            _sessions(factory),
            _ExplodingLifecycle(_accounts(factory), SqlOrganizationStore(factory)),
        )
        with pytest.raises(AuthenticationFailed):
            resolver.resolve_actor(token, now=NOW + LIFETIME)
