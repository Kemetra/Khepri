"""R6-03: selecting and switching the active organization.

**`FR-029` has two clauses and the second is the one implementations miss.** A switch must succeed
only into an organization where the actor holds a *current* membership, **and** must "take effect
for every subsequent authorization decision in that session". The second clause is what makes this
a persistence operation rather than a pure function: a service that returns an updated record
without writing it satisfies the first clause and fails the second, and every test that inspects
only the return value passes against it.

`test_a_switch_survives_a_fresh_read` exists for exactly that defect -- it re-resolves the session
through a new store rather than trusting the returned object.

**Membership is read live, never from the session.** The session already carries an
`active_organization_id`, and using it to decide whether a switch is permitted would be circular:
it would let an actor stay in an organization they had been revoked from. `FR-030` requires a
revocation to take effect for decisions made after it without the session ending.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import AuthenticationFailed, ScopeAccessDenied
from khepri.rca.organizations import MEMBER_ROLE, OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.switching import OrganizationSwitcher
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
    grant_membership,
    two_owner_organization,
)

LIFETIME = timedelta(hours=12)


def _sessions(factory: sessionmaker) -> SessionService:
    return SessionService(SqlSessionStore(factory), lifetime=LIFETIME)


def _switcher(factory: sessionmaker) -> OrganizationSwitcher:
    return OrganizationSwitcher(_sessions(factory), SqlOrganizationStore(factory))


def _account(factory: sessionmaker, email: str) -> str:
    return AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL).account_id


def _organization(factory: sessionmaker, name: str, owner: str) -> str:
    service = OrganizationService(SqlOrganizationStore(factory))
    return service.create_organization(name, owner, now=NOW).organization_id


class TestSwitchingIn:
    def test_a_member_switches_into_their_organization(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        token = _sessions(factory).create(stack.first.account_id, now=NOW)
        switched = _switcher(factory).switch(token, stack.organization.organization_id, now=NOW)
        assert switched.active_organization_id == stack.organization.organization_id

    def test_a_switch_survives_a_fresh_read(self, factory: sessionmaker) -> None:
        """`FR-029`'s second clause: it must take effect for *subsequent* decisions.

        Re-resolved through a new store, so a service that computed the new record and never
        called `save_session` fails here while passing every assertion on the return value.
        """
        stack = two_owner_organization(factory)
        token = _sessions(factory).create(stack.first.account_id, now=NOW)
        _switcher(factory).switch(token, stack.organization.organization_id, now=NOW)

        reread = SessionService(SqlSessionStore(factory), lifetime=LIFETIME).resolve(
            token, now=NOW
        )
        assert reread.active_organization_id == stack.organization.organization_id

    def test_switching_between_two_organizations_replaces_rather_than_accumulates(
        self, factory: sessionmaker
    ) -> None:
        """`FR-027`: at most one active organization. One nullable column cannot hold two, so
        this asserts the service does not work around the schema."""
        stack = two_owner_organization(factory)
        second = _organization(factory, "Beta", stack.first.account_id)
        switcher = _switcher(factory)
        token = _sessions(factory).create(stack.first.account_id, now=NOW)

        switcher.switch(token, stack.organization.organization_id, now=NOW)
        switched = switcher.switch(token, second, now=NOW)
        assert switched.active_organization_id == second

    def test_a_member_role_may_switch(self, factory: sessionmaker) -> None:
        """`R6-01` §3.1: switching is permitted for owner *and* member. Only membership is
        required, not ownership."""
        stack = two_owner_organization(factory)
        joiner = _account(factory, "joiner@example.test")
        grant_membership(stack, joiner, MEMBER_ROLE, factory=factory)
        token = _sessions(factory).create(joiner, now=NOW)
        switched = _switcher(factory).switch(token, stack.organization.organization_id, now=NOW)
        assert switched.active_organization_id == stack.organization.organization_id


class TestSwitchingIsRefused:
    def test_a_non_member_cannot_switch_in(self, factory: sessionmaker) -> None:
        """`FR-029` first clause, and `R6-01` §3.1's non-member column."""
        stack = two_owner_organization(factory)
        outsider = _account(factory, "outsider@example.test")
        token = _sessions(factory).create(outsider, now=NOW)
        with pytest.raises(ScopeAccessDenied):
            _switcher(factory).switch(token, stack.organization.organization_id, now=NOW)

    def test_a_nonexistent_organization_is_refused_identically(
        self, factory: sessionmaker
    ) -> None:
        """`FR-004`, `FR-022`: indistinguishable from a real organization the actor is not in.

        Otherwise a caller enumerates which organizations exist by probing switches.
        """
        stack = two_owner_organization(factory)
        outsider = _account(factory, "outsider@example.test")
        token = _sessions(factory).create(outsider, now=NOW)
        switcher = _switcher(factory)

        refusals = set()
        for target in (stack.organization.organization_id, "org_does_not_exist"):
            with pytest.raises(ScopeAccessDenied) as raised:
                switcher.switch(token, target, now=NOW)
            refusals.add(str(raised.value))
        assert len(refusals) == 1

    def test_a_revoked_membership_cannot_be_switched_into(
        self, factory: sessionmaker
    ) -> None:
        """`FR-029` reads membership **live**. A cached membership would admit this."""
        stack = two_owner_organization(factory)
        joiner = _account(factory, "joiner@example.test")
        grant_membership(stack, joiner, MEMBER_ROLE, factory=factory)
        token = _sessions(factory).create(joiner, now=NOW)

        OrganizationService(SqlOrganizationStore(factory)).revoke_membership(
            stack.organization.organization_id,
            joiner,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )
        with pytest.raises(ScopeAccessDenied):
            _switcher(factory).switch(token, stack.organization.organization_id, now=NOW)

    def test_an_expired_session_cannot_switch(self, factory: sessionmaker) -> None:
        """Session liveness is checked first, so the refusal is the session's, not the scope's.

        Ordering matters: `Session.switched_to` raises `ValueError` on a revoked session, and a
        `ValueError` escaping where `AuthenticationFailed` is expected would break the uniform
        refusal `R3-04` and `R3-05` both hold.
        """
        stack = two_owner_organization(factory)
        token = _sessions(factory).create(stack.first.account_id, now=NOW)
        with pytest.raises(AuthenticationFailed):
            _switcher(factory).switch(
                token, stack.organization.organization_id, now=NOW + LIFETIME
            )

    def test_a_revoked_session_cannot_switch(self, factory: sessionmaker) -> None:
        """The `ValueError` path in `switched_to` must be unreachable through this service."""
        stack = two_owner_organization(factory)
        sessions = _sessions(factory)
        token = sessions.create(stack.first.account_id, now=NOW)
        sessions.revoke(token, now=NOW)
        with pytest.raises(AuthenticationFailed):
            _switcher(factory).switch(token, stack.organization.organization_id, now=NOW)

    def test_an_unknown_session_cannot_switch(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        with pytest.raises(AuthenticationFailed):
            _switcher(factory).switch(
                "cse_unknown", stack.organization.organization_id, now=NOW
            )


class TestClearing:
    def test_clearing_succeeds_without_a_membership_check(
        self, factory: sessionmaker
    ) -> None:
        """`FR-030`: a session whose active-organization membership was revoked must cease to
        authorize *there* while remaining a valid session. Clearing is how that is expressed
        without ending the session, and there is no organization to be a member of.
        """
        stack = two_owner_organization(factory)
        switcher = _switcher(factory)
        token = _sessions(factory).create(stack.first.account_id, now=NOW)
        switcher.switch(token, stack.organization.organization_id, now=NOW)

        cleared = switcher.clear(token, now=NOW)
        assert cleared.active_organization_id is None

    def test_clearing_persists(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        switcher = _switcher(factory)
        token = _sessions(factory).create(stack.first.account_id, now=NOW)
        switcher.switch(token, stack.organization.organization_id, now=NOW)
        switcher.clear(token, now=NOW)

        reread = SessionService(SqlSessionStore(factory), lifetime=LIFETIME).resolve(
            token, now=NOW
        )
        assert reread.active_organization_id is None

    def test_clearing_an_already_clear_session_is_not_an_error(
        self, factory: sessionmaker
    ) -> None:
        """`FR-028`, scenario 18: an account in no organization is a normal authenticated state."""
        account = _account(factory, OTHER_EMAIL)
        token = _sessions(factory).create(account, now=NOW)
        assert _switcher(factory).clear(token, now=NOW).active_organization_id is None


class TestTheSwitcherCachesNothing:
    def test_it_does_not_read_the_sessions_own_active_organization(
        self, factory: sessionmaker
    ) -> None:
        """The circularity this service must not have.

        Deciding a switch from the session's existing `active_organization_id` would let an actor
        remain in an organization they had been revoked from -- the session would authorize its
        own continued authority. Membership comes from the store, every time.
        """
        import inspect as inspect_module

        source = inspect_module.getsource(OrganizationSwitcher)
        assert "active_organization_id" not in source
