"""R6-05: the exhaustive `{owner, member, non-member, unauthenticated}` action matrix.

**What this file is, and why it is not a second copy of `R6-04`'s tests.** `RCA-001`'s
Verification section requires one test per cell of `R6-01` §3's matrix, and `STATUS.md` records
that no such test existed. `test_rca001_authorization_resolution.py` proves the resolver's
*mechanism* -- that roles are read live, that the owner gate refuses a member. This file asks a
different question of the same code: for each actor kind and each protected action, does the
specified outcome occur? Organizing by cell is what makes an absent row visible as a hole in a
table rather than as a test nobody noticed was missing.

**Every cell asserts the observable effect, never only the exception.** A `pytest.raises` on
`require_owner` restates `TestTheOwnerGate` and cannot fail in any new way. What a `DENY` cell
actually claims is that *the action did not happen*, so each denial asserts the membership is
unchanged afterwards. That is the assertion with content: a gate that raised after mutating, or a
verb reached by some other path, dies here while a `pytest.raises`-only test passes.

**The gated path is what is under test, and that is a deliberate boundary.** The three owner-only
verbs take `actor_account_id` for attribution and check no authority of their own, so calling
`promote_to_owner` directly succeeds regardless of the caller's role. That is not a defect this
file can close and not one it should hide: `R6-04` placed the check in the gate, and proving that
*nothing reaches the verbs except through the gate* is `R6-08`'s whole subject. Here, each cell
drives the action the way an authorized caller must -- resolve, then act -- and `R6-08` makes that
the only available route. `STATUS.md` carries the finding so it is inherited rather than
rediscovered.

**Scope: `R6-01` §3.1 only.** The six §3.2 account-scoped actions turn on self-versus-another
account, and `AuthorizationContext` carries the acting `account_id` with no target, so those cells
cannot be expressed without the context change `authorization_resolution.py` defers to `R6-02`.
Covering them here would mean inventing a target parameter mid-slice. Recorded as a carried gap in
`STATUS.md`; §3.1's five actions are complete below.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.actor_resolution import ActorResolver
from khepri.rca.authorization_resolution import AuthorizationResolver
from khepri.rca.errors import AuthenticationFailed, ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.switching import OrganizationSwitcher
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    NOW,
    factory_fixture,
)

LIFETIME = timedelta(hours=12)
INVALID_TOKEN = "not-a-session-token"


def _resolver(factory: sessionmaker) -> AuthorizationResolver:
    actors = ActorResolver(
        SessionService(SqlSessionStore(factory), lifetime=LIFETIME),
        LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory)),
    )
    return AuthorizationResolver(actors, SqlOrganizationStore(factory))


def _role_of(factory: sessionmaker, organization_id: str, account_id: str) -> str | None:
    """The live role, read straight from the store rather than from any returned object.

    Every `DENY` cell asserts against this. Reading through the store is the point: a value taken
    from the service's own return would be the service agreeing with itself, and the claim being
    made is about what was *written*.
    """
    membership = SqlOrganizationStore(factory).get_membership(organization_id, account_id)
    return None if membership is None else membership.role


class Stack:
    """One organization, one owner, one member, one outsider, and live tokens for each.

    Built per test rather than shared. These tests mutate roles and memberships, and a fixture
    reused across cells would let one cell's promotion satisfy another cell's assertion -- the
    matrix would then pass for reasons unrelated to the code under test.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self.factory = factory
        accounts = AccountService(SqlAccountStore(factory))
        self.sessions = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
        self.organizations = OrganizationService(SqlOrganizationStore(factory))

        self.owner = accounts.create_account("owner@example.test", CREDENTIAL).account_id
        self.member = accounts.create_account("member@example.test", CREDENTIAL).account_id
        self.outsider = accounts.create_account("outsider@example.test", CREDENTIAL).account_id

        organization = self.organizations.create_organization("Acme", self.owner, now=NOW)
        self.organization_id = organization.organization_id
        _grant_membership(factory, self.organization_id, self.member, MEMBER_ROLE)

        self.owner_token = self._session(self.owner)
        self.member_token = self._session(self.member)
        self.outsider_token = self._session(self.outsider)

    def _session(self, account_id: str) -> str:
        """A session already switched into the organization where the actor has one.

        The outsider's session is deliberately left with no active organization, because that is
        what a non-member's session *is* -- `R6-02` fixed `organization_id=None` as the single
        spelling of "not a member here", and giving the outsider an active organization would be
        modelling a state the switch path refuses to create.
        """
        token = self.sessions.create(account_id, now=NOW)
        if account_id != self.outsider:
            switcher = OrganizationSwitcher(self.sessions, SqlOrganizationStore(self.factory))
            switcher.switch(token, self.organization_id, now=NOW)
        return token


def _grant_membership(
    factory: sessionmaker, organization_id: str, account_id: str, role: str
) -> None:
    from khepri.rca.persistence import MembershipRow

    with factory.begin() as database:
        database.add(
            MembershipRow(organization_id=organization_id, account_id=account_id, role=role)
        )


@pytest.fixture(name="stack")
def stack_fixture(factory: sessionmaker) -> Stack:
    return Stack(factory)


class TestPromoteToOwner:
    """`R6-01` §3.1 row 1: owner PERMIT, everyone else DENY."""

    def test_an_owner_promotes_a_member(self, stack: Stack) -> None:
        context = _resolver(stack.factory).require_owner(
            stack.owner_token, organization_id=stack.organization_id, now=NOW
        )
        stack.organizations.promote_to_owner(
            stack.organization_id,
            stack.member,
            actor_account_id=context.account_id,
            now=NOW,
        )
        assert _role_of(stack.factory, stack.organization_id, stack.member) == OWNER_ROLE

    def test_a_member_is_refused_and_no_role_changes(self, stack: Stack) -> None:
        with pytest.raises(ScopeAccessDenied):
            _resolver(stack.factory).require_owner(
                stack.member_token, organization_id=stack.organization_id, now=NOW
            )
        assert _role_of(stack.factory, stack.organization_id, stack.member) == MEMBER_ROLE

    def test_a_non_member_is_refused_and_no_role_changes(self, stack: Stack) -> None:
        with pytest.raises(ScopeAccessDenied):
            _resolver(stack.factory).require_owner(
                stack.outsider_token, organization_id=stack.organization_id, now=NOW
            )
        assert _role_of(stack.factory, stack.organization_id, stack.member) == MEMBER_ROLE

    def test_an_unauthenticated_caller_is_refused_and_no_role_changes(self, stack: Stack) -> None:
        with pytest.raises(AuthenticationFailed):
            _resolver(stack.factory).require_owner(
                INVALID_TOKEN, organization_id=stack.organization_id, now=NOW
            )
        assert _role_of(stack.factory, stack.organization_id, stack.member) == MEMBER_ROLE


class TestDemoteToMember:
    """`R6-01` §3.1 row 2: owner PERMIT, everyone else DENY.

    The organization is given a second owner first, because `FR-013` refuses to demote the final
    owner regardless of authority. Without it the owner cell would fail for a reason that is not
    authorization at all, and the matrix would be asserting the wrong invariant.
    """

    def test_an_owner_demotes_another_owner(self, stack: Stack) -> None:
        _promote(stack, stack.member)
        context = _resolver(stack.factory).require_owner(
            stack.owner_token, organization_id=stack.organization_id, now=NOW
        )
        stack.organizations.demote_to_member(
            stack.organization_id,
            stack.member,
            actor_account_id=context.account_id,
            now=NOW,
        )
        assert _role_of(stack.factory, stack.organization_id, stack.member) == MEMBER_ROLE

    def test_a_member_is_refused_and_no_role_changes(self, stack: Stack) -> None:
        _promote(stack, stack.member)
        other = _member_token_after_demotion_attempt(stack)
        with pytest.raises(ScopeAccessDenied):
            _resolver(stack.factory).require_owner(
                other, organization_id=stack.organization_id, now=NOW
            )
        assert _role_of(stack.factory, stack.organization_id, stack.owner) == OWNER_ROLE

    def test_a_non_member_is_refused_and_no_role_changes(self, stack: Stack) -> None:
        with pytest.raises(ScopeAccessDenied):
            _resolver(stack.factory).require_owner(
                stack.outsider_token, organization_id=stack.organization_id, now=NOW
            )
        assert _role_of(stack.factory, stack.organization_id, stack.owner) == OWNER_ROLE

    def test_an_unauthenticated_caller_is_refused_and_no_role_changes(self, stack: Stack) -> None:
        with pytest.raises(AuthenticationFailed):
            _resolver(stack.factory).require_owner(
                INVALID_TOKEN, organization_id=stack.organization_id, now=NOW
            )
        assert _role_of(stack.factory, stack.organization_id, stack.owner) == OWNER_ROLE


class TestRevokeMembership:
    """`R6-01` §3.1 row 3: owner PERMIT, everyone else DENY.

    Note 1 of the matrix is load-bearing here: a member revoking *their own* membership is not
    this cell. No operation expresses leaving an organization, so the member column stays DENY and
    a test for self-revocation would be testing an action that does not exist.
    """

    def test_an_owner_revokes_a_member(self, stack: Stack) -> None:
        context = _resolver(stack.factory).require_owner(
            stack.owner_token, organization_id=stack.organization_id, now=NOW
        )
        stack.organizations.revoke_membership(
            stack.organization_id,
            stack.member,
            actor_account_id=context.account_id,
            now=NOW,
        )
        assert _role_of(stack.factory, stack.organization_id, stack.member) is None

    def test_a_member_is_refused_and_the_membership_survives(self, stack: Stack) -> None:
        with pytest.raises(ScopeAccessDenied):
            _resolver(stack.factory).require_owner(
                stack.member_token, organization_id=stack.organization_id, now=NOW
            )
        assert _role_of(stack.factory, stack.organization_id, stack.member) == MEMBER_ROLE

    def test_a_non_member_is_refused_and_the_membership_survives(self, stack: Stack) -> None:
        with pytest.raises(ScopeAccessDenied):
            _resolver(stack.factory).require_owner(
                stack.outsider_token, organization_id=stack.organization_id, now=NOW
            )
        assert _role_of(stack.factory, stack.organization_id, stack.member) == MEMBER_ROLE

    def test_an_unauthenticated_caller_is_refused_and_the_membership_survives(
        self, stack: Stack
    ) -> None:
        with pytest.raises(AuthenticationFailed):
            _resolver(stack.factory).require_owner(
                INVALID_TOKEN, organization_id=stack.organization_id, now=NOW
            )
        assert _role_of(stack.factory, stack.organization_id, stack.member) == MEMBER_ROLE


class TestResolveAnIsolationScope:
    """`R6-01` §3.1 row 4: owner **and member** PERMIT, non-member and unauthenticated DENY.

    This is one of the two rows where the member column is a PERMIT, and keeping it distinct from
    the owner-only rows is the point of testing it separately -- a matrix that treated every §3.1
    action as owner-only would pass three rows and be wrong about two.

    `R6-01` §6 settles that `isolation.py`'s own membership refusal *is* the enforcement here, so
    these cells drive `IsolationService` directly rather than adding a second gate in front of it.
    """

    def test_an_owner_resolves_the_scope(self, stack: Stack) -> None:
        assert _isolation(stack).resolve_scope(stack.owner, stack.organization_id)

    def test_a_member_resolves_the_scope(self, stack: Stack) -> None:
        assert _isolation(stack).resolve_scope(stack.member, stack.organization_id)

    def test_an_owner_and_a_member_reach_the_same_scope(self, stack: Stack) -> None:
        """The PERMIT is to one organization's key, not to a per-actor one.

        `FR-035` requires the key to be stable across membership differences, so two members of
        one organization resolving different keys would be a defect no per-actor assertion sees.
        """
        isolation = _isolation(stack)
        assert isolation.resolve_scope(stack.owner, stack.organization_id) == (
            isolation.resolve_scope(stack.member, stack.organization_id)
        )

    def test_a_non_member_is_refused(self, stack: Stack) -> None:
        with pytest.raises(ScopeAccessDenied):
            _isolation(stack).resolve_scope(stack.outsider, stack.organization_id)

    def test_an_unauthenticated_caller_is_refused(self, stack: Stack) -> None:
        """No account at all, which is what `unauthenticated` means for an account-keyed call.

        `resolve_scope` takes an `account_id` rather than a token, so the unauthenticated column
        is expressed as an identifier no account holds -- the state a caller who never
        authenticated is in.
        """
        with pytest.raises(ScopeAccessDenied):
            _isolation(stack).resolve_scope("no-such-account", stack.organization_id)


class TestSwitchActiveOrganization:
    """`R6-01` §3.1 row 5: owner and member PERMIT, non-member and unauthenticated DENY."""

    def test_an_owner_switches(self, stack: Stack) -> None:
        session = _switcher(stack).switch(stack.owner_token, stack.organization_id, now=NOW)
        assert session.active_organization_id == stack.organization_id

    def test_a_member_switches(self, stack: Stack) -> None:
        session = _switcher(stack).switch(stack.member_token, stack.organization_id, now=NOW)
        assert session.active_organization_id == stack.organization_id

    def test_a_non_member_is_refused_and_the_session_stays_unswitched(self, stack: Stack) -> None:
        with pytest.raises(ScopeAccessDenied):
            _switcher(stack).switch(stack.outsider_token, stack.organization_id, now=NOW)
        context = _resolver(stack.factory).resolve(stack.outsider_token, now=NOW)
        assert context.organization_id is None

    def test_a_non_member_naming_the_organization_on_a_request_is_refused(
        self, stack: Stack
    ) -> None:
        """The same DENY reached through `for_request` rather than through the switch path.

        Its own cell rather than a line inside the scenario-18 aggregate: removing
        `for_request`'s comparison leaves every other assertion in this file green, so without
        this test that guard's entire matrix-level coverage would rest on one composite test
        that is about something else. A guard held by a single incidental assertion is one
        edit away from being held by none.
        """
        with pytest.raises(ScopeAccessDenied):
            _resolver(stack.factory).for_request(
                stack.outsider_token, organization_id=stack.organization_id, now=NOW
            )

    def test_an_unauthenticated_caller_is_refused(self, stack: Stack) -> None:
        with pytest.raises(AuthenticationFailed):
            _switcher(stack).switch(INVALID_TOKEN, stack.organization_id, now=NOW)


class TestScenarioEighteen:
    """Scenario 18: authenticated with no organization -- every §3.1 cell DENY, §3.2 permitted.

    `R6-01` §3.3 names this scenario directly and `STATUS.md` lists 18 among the scenarios with no
    test. The actor here is not a failed authentication: `FR-028` requires them to authenticate
    *successfully*, which is why the first assertion is that resolution returns a context at all.
    """

    def test_the_actor_authenticates_successfully(self, stack: Stack) -> None:
        context = _resolver(stack.factory).resolve(stack.outsider_token, now=NOW)
        assert context.account_id == stack.outsider
        assert context.organization_id is None
        assert context.role is None

    def test_every_organization_scoped_action_is_denied(self, stack: Stack) -> None:
        resolver = _resolver(stack.factory)
        with pytest.raises(ScopeAccessDenied):
            resolver.require_owner(
                stack.outsider_token, organization_id=stack.organization_id, now=NOW
            )
        with pytest.raises(ScopeAccessDenied):
            resolver.for_request(
                stack.outsider_token, organization_id=stack.organization_id, now=NOW
            )
        with pytest.raises(ScopeAccessDenied):
            _isolation(stack).resolve_scope(stack.outsider, stack.organization_id)
        with pytest.raises(ScopeAccessDenied):
            _switcher(stack).switch(stack.outsider_token, stack.organization_id, now=NOW)


class TestScenarioNineteen:
    """Scenario 19: a stale or invalid session is the `unauthenticated` column of both tables.

    The actor is never established, so no row is reached -- which is why every assertion here is
    `AuthenticationFailed` rather than the `ScopeAccessDenied` a resolved-but-unauthorized actor
    receives. `R6-07` covers sessions that were valid and became stale; this is the invalid case.
    """

    def test_no_row_is_reached(self, stack: Stack) -> None:
        resolver = _resolver(stack.factory)
        with pytest.raises(AuthenticationFailed):
            resolver.resolve(INVALID_TOKEN, now=NOW)
        with pytest.raises(AuthenticationFailed):
            resolver.for_request(INVALID_TOKEN, organization_id=stack.organization_id, now=NOW)
        with pytest.raises(AuthenticationFailed):
            resolver.require_owner(INVALID_TOKEN, organization_id=stack.organization_id, now=NOW)

    def test_an_expired_session_reaches_no_row_either(self, stack: Stack) -> None:
        later = NOW + LIFETIME + timedelta(seconds=1)
        with pytest.raises(AuthenticationFailed):
            _resolver(stack.factory).require_owner(
                stack.owner_token, organization_id=stack.organization_id, now=later
            )
        assert _role_of(stack.factory, stack.organization_id, stack.member) == MEMBER_ROLE


def _isolation(stack: Stack) -> IsolationService:
    return IsolationService(SqlOrganizationStore(stack.factory), SqlAccountStore(stack.factory))


def _switcher(stack: Stack) -> OrganizationSwitcher:
    return OrganizationSwitcher(stack.sessions, SqlOrganizationStore(stack.factory))


def _promote(stack: Stack, account_id: str) -> None:
    stack.organizations.promote_to_owner(
        stack.organization_id, account_id, actor_account_id=stack.owner, now=NOW
    )


def _member_token_after_demotion_attempt(stack: Stack) -> str:
    """A token for an account that is a plain member of the organization.

    The member was promoted by the demotion fixture, so this adds a fresh member rather than
    reusing `stack.member_token` -- whose holder is now an owner and would pass the gate.
    """
    accounts = AccountService(SqlAccountStore(stack.factory))
    account_id = accounts.create_account("plain@example.test", CREDENTIAL).account_id
    _grant_membership(stack.factory, stack.organization_id, account_id, MEMBER_ROLE)
    token = stack.sessions.create(account_id, now=NOW)
    _switcher(stack).switch(token, stack.organization_id, now=NOW)
    return token
