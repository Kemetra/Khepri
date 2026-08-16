"""R6-07: revocation, demotion, and disablement take effect without the session ending.

**The claim, taken from `FR-030` and `FR-008` verbatim.** `FR-030`: a change to membership or role
must take effect for decisions made after it, *"without requiring the affected session to end"*.
`FR-008`: a disabled account's pre-existing sessions must cease to authorize *"with no dependence
on session expiry to take effect"*. Both name the same failure mode -- authority that outlives the
change until something else clears it -- and both are about what happens **while the session is
still there**.

**Demotion is the load-bearing case, and why.** It is the only one of the three changes where the
actor keeps some authority, so it is the only one where "the right amount of authority was removed"
is a testable claim at all. Revocation and disablement are total: any assertion that the actor lost
*something* is also an assertion that they lost everything, and the two cannot be told apart.

After a demotion the session is live, the organization is still active, `require_owner` refuses --
**and `for_request` still succeeds, and `resolve_scope` still returns the same key**, because
`R6-01` §3.1 gives a member `PERMIT` for both. A test asserting only the refusal accepts a demotion
that quietly revoked.

`R6-04` is not blind to this, and the distinction is narrower than it first appears.
`TestTheRoleIsReadLive::test_a_demoted_owner_resolves_as_a_member` asserts `role == MEMBER_ROLE`,
which is positive rather than a denial, and a demotion implemented as a revocation dies against it.
Verified by mutating `demote_to_member` to call `revoke_membership`: `R6-04` catches it with that
one test, and this file with three. What is added here is the *consequence* -- that the demoted
actor's member-permitted actions still work and resolve the same isolation key -- which is the
claim `R6-04` has no test for and which is what "the right amount" means in practice.

**"Immediate" is asserted rather than assumed.** Every test resolves at `NOW`, applies the change
at `NOW`, and resolves again at `NOW`, with no time advanced anywhere. A change that took effect
only after a refresh or an expiry would still satisfy a test that let the clock move between the
two resolutions, and `R6-07`'s named output is exactly this property.

**The session must still be live afterwards, and that is asserted separately.** "The action stops"
and "the session ended" are different outcomes with the same surface at the refused call. If
revoking a membership also destroyed the session, `FR-030`'s "without requiring the affected
session to end" would be violated by an implementation that looks correct from the refusal alone.
So each revocation and demotion case asserts the token still resolves.

Scenario 20 is the named case: a membership revoked while a session exists. Scenario 16 is
disablement, whose account-level half `test_rca001_disablement.py` already covers; what is added
here is its effect *through a live session and the resolver*, which did not exist when those tests
were written.
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
from khepri.rca.persistence import MembershipRow, SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.switching import OrganizationSwitcher
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    NOW,
    factory_fixture,
)

LIFETIME = timedelta(hours=12)


def _sessions(factory: sessionmaker) -> SessionService:
    return SessionService(SqlSessionStore(factory), lifetime=LIFETIME)


def _resolver(factory: sessionmaker) -> AuthorizationResolver:
    actors = ActorResolver(
        _sessions(factory),
        LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory)),
    )
    return AuthorizationResolver(actors, SqlOrganizationStore(factory))


def _isolation(factory: sessionmaker) -> IsolationService:
    return IsolationService(SqlOrganizationStore(factory), SqlAccountStore(factory))


def _organizations(factory: sessionmaker) -> OrganizationService:
    return OrganizationService(SqlOrganizationStore(factory))


def _account(factory: sessionmaker, email: str) -> str:
    return AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL).account_id


def _grant(factory: sessionmaker, organization_id: str, account_id: str, role: str) -> None:
    with factory.begin() as database:
        database.add(
            MembershipRow(organization_id=organization_id, account_id=account_id, role=role)
        )


def _role_of(factory: sessionmaker, organization_id: str, account_id: str) -> str | None:
    membership = SqlOrganizationStore(factory).get_membership(organization_id, account_id)
    return None if membership is None else membership.role


class Live:
    """An organization with two owners and one member, each holding a live session.

    Two owners because `FR-013` refuses to demote or revoke the final one: with a single owner the
    demotion cases would fail on an invariant that is not authorization, and the test would be
    reporting the wrong thing.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self.factory = factory
        self.first = _account(factory, "first@example.test")
        self.second = _account(factory, "second@example.test")
        self.member = _account(factory, "member@example.test")

        organization = _organizations(factory).create_organization("Acme", self.first, now=NOW)
        self.organization_id = organization.organization_id
        _grant(factory, self.organization_id, self.second, OWNER_ROLE)
        _grant(factory, self.organization_id, self.member, MEMBER_ROLE)

        self.first_token = self._session(self.first)
        self.second_token = self._session(self.second)
        self.member_token = self._session(self.member)

    def _session(self, account_id: str) -> str:
        token = _sessions(self.factory).create(account_id, now=NOW)
        OrganizationSwitcher(_sessions(self.factory), SqlOrganizationStore(self.factory)).switch(
            token, self.organization_id, now=NOW
        )
        return token


@pytest.fixture(name="live")
def live_fixture(factory: sessionmaker) -> Live:
    return Live(factory)


class TestScenarioTwentyRevocationWhileASessionExists:
    """`FR-030` second clause: the session stops authorizing *in that organization*.

    `STATUS.md` recorded `FR-030` as not implemented with "scenario 20 becomes testable once a
    session exists". It does now.
    """

    def test_the_session_stops_authorizing_immediately(self, live: Live) -> None:
        """No clock movement anywhere: resolve, revoke, resolve, all at `NOW`.

        A change that only took effect at the next refresh or expiry would pass a test that
        advanced time between the two resolutions, which is why none is advanced.
        """
        resolver = _resolver(live.factory)
        assert resolver.resolve(live.member_token, now=NOW).organization_id == live.organization_id

        _organizations(live.factory).revoke_membership(
            live.organization_id, live.member, actor_account_id=live.first, now=NOW
        )

        assert resolver.resolve(live.member_token, now=NOW).organization_id is None

    def test_the_session_itself_is_still_live(self, live: Live) -> None:
        """`FR-030`: "without requiring the affected session to end".

        The distinction this makes is invisible at the refused call. An implementation that
        destroyed the session on revocation would refuse the action correctly and violate the
        requirement, and only asking the session directly separates the two.
        """
        _organizations(live.factory).revoke_membership(
            live.organization_id, live.member, actor_account_id=live.first, now=NOW
        )

        session = _sessions(live.factory).resolve(live.member_token, now=NOW)
        assert session.account_id == live.member

    def test_the_actor_still_authenticates(self, live: Live) -> None:
        """A revoked member is not a failed authentication -- `FR-028`'s state, reached by removal.

        Resolution must succeed and return a context with no organization, exactly as for an
        account that never joined one. A refusal here would be denying the authentication rather
        than the action.
        """
        _organizations(live.factory).revoke_membership(
            live.organization_id, live.member, actor_account_id=live.first, now=NOW
        )

        context = _resolver(live.factory).resolve(live.member_token, now=NOW)
        assert context.account_id == live.member
        assert context.organization_id is None
        assert context.role is None

    def test_the_organization_scoped_actions_all_stop(self, live: Live) -> None:
        _organizations(live.factory).revoke_membership(
            live.organization_id, live.member, actor_account_id=live.first, now=NOW
        )
        resolver = _resolver(live.factory)

        with pytest.raises(ScopeAccessDenied):
            resolver.for_request(
                live.member_token, organization_id=live.organization_id, now=NOW
            )
        with pytest.raises(ScopeAccessDenied):
            resolver.require_owner(
                live.member_token, organization_id=live.organization_id, now=NOW
            )
        with pytest.raises(ScopeAccessDenied):
            _isolation(live.factory).resolve_scope(live.member, live.organization_id)

    def test_other_members_are_unaffected(self, live: Live) -> None:
        """`FR-012`: one membership ends and the others do not.

        A revocation that cleared the organization's memberships would satisfy every assertion
        above, since each only asks about the revoked actor.
        """
        _organizations(live.factory).revoke_membership(
            live.organization_id, live.member, actor_account_id=live.first, now=NOW
        )
        resolver = _resolver(live.factory)

        assert resolver.resolve(live.first_token, now=NOW).is_owner
        assert resolver.resolve(live.second_token, now=NOW).is_owner
        assert _role_of(live.factory, live.organization_id, live.first) == OWNER_ROLE


class TestDemotionRemovesExactlyOwnerAuthority:
    """The load-bearing case: authority is *narrowed*, not withdrawn.

    Every assertion `R6-04` makes about a demotion is a denial, so a demotion implemented as a
    revocation passes all of them. The tests here are the other half -- what must **still work**
    afterwards -- and they are the reason this class exists rather than being folded into the
    revocation cases above.
    """

    def test_the_owner_gate_closes_immediately(self, live: Live) -> None:
        resolver = _resolver(live.factory)
        assert resolver.require_owner(
            live.second_token, organization_id=live.organization_id, now=NOW
        ).is_owner

        _organizations(live.factory).demote_to_member(
            live.organization_id, live.second, actor_account_id=live.first, now=NOW
        )

        with pytest.raises(ScopeAccessDenied):
            resolver.require_owner(
                live.second_token, organization_id=live.organization_id, now=NOW
            )

    def test_the_membership_survives_the_demotion(self, live: Live) -> None:
        """The assertion a denial-only test cannot make: they are still a member.

        This is what separates demotion from revocation, and a demotion that removed the row
        would pass every refusal assertion in this file.
        """
        _organizations(live.factory).demote_to_member(
            live.organization_id, live.second, actor_account_id=live.first, now=NOW
        )

        context = _resolver(live.factory).resolve(live.second_token, now=NOW)
        assert context.organization_id == live.organization_id
        assert context.role == MEMBER_ROLE
        assert not context.is_owner

    def test_the_member_permitted_actions_still_work(self, live: Live) -> None:
        """`R6-01` §3.1 gives a member `PERMIT` for scope resolution and for the request gate.

        Both must still succeed after the demotion. A demotion that over-refused would fail
        here while satisfying every "the owner gate closed" assertion.
        """
        before = _isolation(live.factory).resolve_scope(live.second, live.organization_id)

        _organizations(live.factory).demote_to_member(
            live.organization_id, live.second, actor_account_id=live.first, now=NOW
        )

        after = _isolation(live.factory).resolve_scope(live.second, live.organization_id)
        assert after == before

        context = _resolver(live.factory).for_request(
            live.second_token, organization_id=live.organization_id, now=NOW
        )
        assert context.organization_id == live.organization_id

    def test_the_session_is_still_live(self, live: Live) -> None:
        _organizations(live.factory).demote_to_member(
            live.organization_id, live.second, actor_account_id=live.first, now=NOW
        )
        assert _sessions(live.factory).resolve(live.second_token, now=NOW).account_id == (
            live.second
        )

    def test_a_refused_owner_action_changes_no_state(self, live: Live) -> None:
        """The refusal leaves the membership table exactly as the demotion left it."""
        _organizations(live.factory).demote_to_member(
            live.organization_id, live.second, actor_account_id=live.first, now=NOW
        )

        with pytest.raises(ScopeAccessDenied):
            _resolver(live.factory).require_owner(
                live.second_token, organization_id=live.organization_id, now=NOW
            )

        assert _role_of(live.factory, live.organization_id, live.second) == MEMBER_ROLE
        assert _role_of(live.factory, live.organization_id, live.first) == OWNER_ROLE
        assert _role_of(live.factory, live.organization_id, live.member) == MEMBER_ROLE

    def test_a_promotion_takes_effect_just_as_immediately(self, live: Live) -> None:
        """The symmetric direction, which no `FR` states and every implementation should hold.

        `FR-030` says "a change", not "a reduction". A resolver that read live only when
        withdrawing authority would be a strange implementation, but it is one this file would
        otherwise not distinguish from a correct one.
        """
        resolver = _resolver(live.factory)
        with pytest.raises(ScopeAccessDenied):
            resolver.require_owner(
                live.member_token, organization_id=live.organization_id, now=NOW
            )

        _organizations(live.factory).promote_to_owner(
            live.organization_id, live.member, actor_account_id=live.first, now=NOW
        )

        assert resolver.require_owner(
            live.member_token, organization_id=live.organization_id, now=NOW
        ).is_owner


class TestScenarioSixteenDisablementThroughALiveSession:
    """`FR-008`: pre-existing sessions cease to authorize, with no dependence on expiry.

    `test_rca001_disablement.py` covers disablement at the account and scope level. What is new
    here is the path through a *live session and the resolver*, which did not exist when those
    tests were written -- `STATUS.md`'s `FR-008` row records `assert_account_active` as having no
    production caller, and `ActorResolver` is now one.
    """

    def test_every_protected_action_stops_immediately(self, live: Live) -> None:
        resolver = _resolver(live.factory)
        assert resolver.resolve(live.second_token, now=NOW).is_owner

        LifecycleService(
            SqlAccountStore(live.factory), SqlOrganizationStore(live.factory)
        ).disable_account(live.second, now=NOW)

        with pytest.raises(AuthenticationFailed):
            resolver.resolve(live.second_token, now=NOW)
        with pytest.raises(AuthenticationFailed):
            resolver.for_request(
                live.second_token, organization_id=live.organization_id, now=NOW
            )
        with pytest.raises(AuthenticationFailed):
            resolver.require_owner(
                live.second_token, organization_id=live.organization_id, now=NOW
            )
        with pytest.raises(ScopeAccessDenied):
            _isolation(live.factory).resolve_scope(live.second, live.organization_id)

    def test_it_does_not_wait_for_the_session_to_expire(self, live: Live) -> None:
        """`FR-008`'s "no dependence on session expiry", asserted where it can fail.

        The session's own lifetime has hours left at `NOW`; the refusal must not be the expiry
        arriving early. Resolving the session directly confirms it would still be valid, so the
        refusal above is attributable to disablement alone.
        """
        LifecycleService(
            SqlAccountStore(live.factory), SqlOrganizationStore(live.factory)
        ).disable_account(live.second, now=NOW)

        session = _sessions(live.factory).resolve(live.second_token, now=NOW)
        assert session.account_id == live.second

        with pytest.raises(AuthenticationFailed):
            _resolver(live.factory).resolve(live.second_token, now=NOW)

    def test_the_refusal_is_authentication_not_authorization(self, live: Live) -> None:
        """A disabled account fails at step 3, before any role is read.

        The distinction matters: `ScopeAccessDenied` would say "you are not authorized here",
        which is a different and weaker claim than "you are not an actor at all", and would leave
        a disabled account resolving contexts for organizations it still has rows in.
        """
        LifecycleService(
            SqlAccountStore(live.factory), SqlOrganizationStore(live.factory)
        ).disable_account(live.second, now=NOW)

        with pytest.raises(AuthenticationFailed):
            _resolver(live.factory).resolve(live.second_token, now=NOW)

    def test_the_membership_row_is_untouched_by_disablement(self, live: Live) -> None:
        """Disablement is an account fact, not a membership one (`FR-008` vs `FR-012`).

        `count_effective_authority` depends on this: disablement never writes to
        `rca_memberships`, so the row survives and the account simply stops being able to act.
        A disablement that revoked memberships would make re-enablement lossy.
        """
        LifecycleService(
            SqlAccountStore(live.factory), SqlOrganizationStore(live.factory)
        ).disable_account(live.second, now=NOW)

        assert _role_of(live.factory, live.organization_id, live.second) == OWNER_ROLE

    def test_other_accounts_sessions_keep_working(self, live: Live) -> None:
        LifecycleService(
            SqlAccountStore(live.factory), SqlOrganizationStore(live.factory)
        ).disable_account(live.second, now=NOW)
        resolver = _resolver(live.factory)

        assert resolver.resolve(live.first_token, now=NOW).is_owner
        assert resolver.resolve(live.member_token, now=NOW).role == MEMBER_ROLE
