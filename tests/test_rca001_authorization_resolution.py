"""R6-04: live membership and role resolution at every protected action.

**What these tests are for, stated narrowly.** They prove the resolver's own behavior: that every
lookup is live, that the organization comes from the session rather than the caller, and that the
owner gate refuses everyone else identically. The exhaustive
`{owner, member, non-member, unauthenticated}` matrix is `R6-05`, cross-organization
indistinguishability is `R6-06`, and stale-session revocation and demotion are `R6-07`. Each of
those is a distinct body of evidence, and folding them in here would make this file the matrix
without anyone deciding it should be.

**The defect every "live lookup" test must be able to see.** A resolver that reads the role once
and reuses it satisfies every assertion made against a single returned context. So the tests that
matter here mutate state *between* two resolutions of the same token and assert the second
observes the change -- `TestTheRoleIsReadLive` and `TestMembershipIsReadLive` exist for exactly
that, and a memoizing resolver dies against them while passing everything else.

**The organization is never the caller's to name.** `resolve_scope` accepts a bare
`organization_id`, so a handler holding a route parameter could reach a scope without this
resolver running. `TestTheRequestNeverNamesItsOwnScope` asserts the comparison that closes it,
including the case that looks harmless: an organization the actor genuinely belongs to, which is
still refused when it is not the session's active one.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.actor_resolution import ActorResolver
from khepri.rca.authorization_resolution import AuthorizationResolver
from khepri.rca.errors import AuthenticationFailed, ScopeAccessDenied
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.switching import OrganizationSwitcher
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
    grant_membership,
    two_owner_organization,
)

LIFETIME = timedelta(hours=12)


def _sessions(factory: sessionmaker) -> SessionService:
    return SessionService(SqlSessionStore(factory), lifetime=LIFETIME)


def _resolver(factory: sessionmaker) -> AuthorizationResolver:
    """Built fresh from stores each time, so nothing survives between calls by construction.

    A resolver held across two calls would still read live, but building it per call means a
    test cannot accidentally prove liveness that only holds because the object was new.
    """
    actors = ActorResolver(
        _sessions(factory),
        LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory)),
    )
    return AuthorizationResolver(actors, SqlOrganizationStore(factory))


def _switcher(factory: sessionmaker) -> OrganizationSwitcher:
    return OrganizationSwitcher(_sessions(factory), SqlOrganizationStore(factory))


def _organizations(factory: sessionmaker) -> OrganizationService:
    return OrganizationService(SqlOrganizationStore(factory))


def _account(factory: sessionmaker, email: str) -> str:
    return AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL).account_id


def _active_session(factory: sessionmaker, account_id: str, organization_id: str) -> str:
    """A live token already pointed at one organization -- the normal precondition for §3.1."""
    token = _sessions(factory).create(account_id, now=NOW)
    _switcher(factory).switch(token, organization_id, now=NOW)
    return token


class TestResolvingAnActiveMembership:
    def test_an_owner_resolves_with_their_live_role(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        token = _active_session(factory, stack.first.account_id, stack.organization.organization_id)

        context = _resolver(factory).resolve(token, now=NOW)

        assert context.account_id == stack.first.account_id
        assert context.organization_id == stack.organization.organization_id
        assert context.role == OWNER_ROLE
        assert context.is_owner

    def test_a_member_resolves_as_a_member(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        token = _active_session(factory, member, stack.organization.organization_id)

        context = _resolver(factory).resolve(token, now=NOW)

        assert context.role == MEMBER_ROLE
        assert not context.is_owner


class TestAnActorInNoOrganization:
    """`FR-028` and scenario 18: authenticates, and every organization-scoped cell is `DENY`."""

    def test_a_session_with_no_active_organization_resolves_rather_than_refusing(
        self, factory: sessionmaker
    ) -> None:
        """Refusing here would deny the authentication rather than the action.

        `FR-028` requires an account with no membership to authenticate successfully. A resolver
        that raises for a member-less actor makes scenario 18 unreachable, and the account-scoped
        actions of `R6-01` §3.2 -- which that actor may legitimately perform -- unreachable too.
        """
        account = _account(factory, "nobody@example.test")
        token = _sessions(factory).create(account, now=NOW)

        context = _resolver(factory).resolve(token, now=NOW)

        assert context.account_id == account
        assert context.organization_id is None
        assert context.role is None
        assert not context.is_owner

    def test_an_actor_in_no_organization_is_refused_the_owner_gate(
        self, factory: sessionmaker
    ) -> None:
        account = _account(factory, "nobody@example.test")
        token = _sessions(factory).create(account, now=NOW)

        with pytest.raises(ScopeAccessDenied):
            _resolver(factory).require_owner(token, now=NOW)


class TestMembershipIsReadLive:
    """`FR-030` and scenario 20: a revocation takes effect without the session ending."""

    def test_a_revoked_membership_stops_authorizing_on_the_next_resolution(
        self, factory: sessionmaker
    ) -> None:
        """The session is untouched; the store is changed; the second resolution must observe it.

        A resolver caching the first result returns `owner` here and passes any test that
        inspects one context. This one re-resolves the *same token* after the revocation.
        """
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        token = _active_session(factory, member, stack.organization.organization_id)
        assert _resolver(factory).resolve(token, now=NOW).role == MEMBER_ROLE

        _organizations(factory).revoke_membership(
            stack.organization.organization_id,
            member,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )

        context = _resolver(factory).resolve(token, now=NOW)
        assert context.organization_id is None
        assert context.role is None

    def test_the_session_remains_valid_after_the_membership_ends(
        self, factory: sessionmaker
    ) -> None:
        """`FR-030`'s exact wording: it must cease to authorize *in that organization*, not end.

        A resolver implementing revocation by refusing the session conflates two states and
        breaks `FR-028` for the same actor a moment later.
        """
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        token = _active_session(factory, member, stack.organization.organization_id)

        _organizations(factory).revoke_membership(
            stack.organization.organization_id,
            member,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )

        context = _resolver(factory).resolve(token, now=NOW)
        assert context.account_id == member

    def test_the_role_is_not_read_from_the_session(self, factory: sessionmaker) -> None:
        """The session still names the organization after revocation; the store no longer does.

        This is the circularity `R6-03` refused at switch time. A resolver trusting
        `session.active_organization_id` as evidence of membership reports the actor still in the
        organization, because that field is exactly what was not changed.
        """
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        token = _active_session(factory, member, stack.organization.organization_id)

        _organizations(factory).revoke_membership(
            stack.organization.organization_id,
            member,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )

        still_named = _sessions(factory).resolve(token, now=NOW)
        assert still_named.active_organization_id == stack.organization.organization_id
        assert _resolver(factory).resolve(token, now=NOW).organization_id is None


class TestOneResolverHeldAcrossAChange:
    """The same resolver instance, reused -- which is how a request handler will hold one.

    **These tests exist because the rest of this file could not see a cache.** Every other helper
    builds a fresh `AuthorizationResolver` per call, so a resolver memoizing contexts on itself
    passed all of them: the second resolution was always a different object with an empty cache.
    A long-lived resolver is the realistic deployment, and it is the one a cache breaks.

    Nothing in the module holds state between calls today. These assert that it stays true, which
    is a different claim from asserting it is true once.
    """

    def test_a_reused_resolver_observes_a_revocation(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        token = _active_session(factory, member, stack.organization.organization_id)
        resolver = _resolver(factory)
        assert resolver.resolve(token, now=NOW).role == MEMBER_ROLE

        _organizations(factory).revoke_membership(
            stack.organization.organization_id,
            member,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )

        assert resolver.resolve(token, now=NOW).organization_id is None

    def test_a_reused_resolver_observes_a_demotion(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        token = _active_session(
            factory, stack.second.account_id, stack.organization.organization_id
        )
        resolver = _resolver(factory)
        assert resolver.resolve(token, now=NOW).is_owner

        _organizations(factory).demote_to_member(
            stack.organization.organization_id,
            stack.second.account_id,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )

        assert not resolver.resolve(token, now=NOW).is_owner

    def test_a_reused_resolver_observes_a_promotion(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        token = _active_session(factory, member, stack.organization.organization_id)
        resolver = _resolver(factory)
        with pytest.raises(ScopeAccessDenied):
            resolver.require_owner(token, now=NOW)

        _organizations(factory).promote_to_owner(
            stack.organization.organization_id,
            member,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )

        assert resolver.require_owner(token, now=NOW).is_owner

    def test_a_reused_resolver_observes_a_disablement(self, factory: sessionmaker) -> None:
        """`FR-008` at step 3, through a held resolver: a cache above the chokepoint hides it."""
        stack = two_owner_organization(factory)
        token = _active_session(
            factory, stack.second.account_id, stack.organization.organization_id
        )
        resolver = _resolver(factory)
        assert resolver.resolve(token, now=NOW).is_owner

        LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory)).disable_account(
            stack.second.account_id, now=NOW
        )

        with pytest.raises(AuthenticationFailed):
            resolver.resolve(token, now=NOW)

    def test_a_reused_resolver_observes_a_switch(self, factory: sessionmaker) -> None:
        """`FR-029`'s second clause through a held resolver: a switch binds later decisions."""
        stack = two_owner_organization(factory)
        second = _organizations(factory).create_organization(
            "Beta", stack.first.account_id, now=NOW
        )
        token = _active_session(factory, stack.first.account_id, stack.organization.organization_id)
        resolver = _resolver(factory)
        assert (
            resolver.resolve(token, now=NOW).organization_id == stack.organization.organization_id
        )

        _switcher(factory).switch(token, second.organization_id, now=NOW)

        assert resolver.resolve(token, now=NOW).organization_id == second.organization_id

    def test_a_reused_resolver_does_not_leak_one_actor_into_another(
        self, factory: sessionmaker
    ) -> None:
        """A cache keyed on anything but the token would answer the wrong actor's question.

        Two live tokens with different roles, resolved through one resolver, interleaved.
        """
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        owner_token = _active_session(
            factory, stack.first.account_id, stack.organization.organization_id
        )
        member_token = _active_session(factory, member, stack.organization.organization_id)
        resolver = _resolver(factory)

        assert resolver.resolve(owner_token, now=NOW).is_owner
        assert not resolver.resolve(member_token, now=NOW).is_owner
        assert resolver.resolve(owner_token, now=NOW).is_owner


class TestTheRoleIsReadLive:
    """Scenario 10: a role change takes effect for decisions made after it."""

    def test_a_demoted_owner_resolves_as_a_member(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        token = _active_session(
            factory, stack.second.account_id, stack.organization.organization_id
        )
        assert _resolver(factory).resolve(token, now=NOW).is_owner

        _organizations(factory).demote_to_member(
            stack.organization.organization_id,
            stack.second.account_id,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )

        context = _resolver(factory).resolve(token, now=NOW)
        assert context.role == MEMBER_ROLE
        assert not context.is_owner

    def test_a_demoted_owner_loses_the_owner_gate(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        token = _active_session(
            factory, stack.second.account_id, stack.organization.organization_id
        )
        _resolver(factory).require_owner(token, now=NOW)

        _organizations(factory).demote_to_member(
            stack.organization.organization_id,
            stack.second.account_id,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )

        with pytest.raises(ScopeAccessDenied):
            _resolver(factory).require_owner(token, now=NOW)

    def test_a_promoted_member_gains_the_owner_gate(self, factory: sessionmaker) -> None:
        """The permitting direction, which a resolver that always denies would pass without."""
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        token = _active_session(factory, member, stack.organization.organization_id)
        with pytest.raises(ScopeAccessDenied):
            _resolver(factory).require_owner(token, now=NOW)

        _organizations(factory).promote_to_owner(
            stack.organization.organization_id,
            member,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )

        assert _resolver(factory).require_owner(token, now=NOW).is_owner


class TestTheOwnerGate:
    """`R6-01` §3.1's owner-only column: promote, demote, and revoke a membership."""

    def test_a_member_is_refused(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        token = _active_session(factory, member, stack.organization.organization_id)

        with pytest.raises(ScopeAccessDenied):
            _resolver(factory).require_owner(token, now=NOW)

    def test_a_member_and_a_non_member_are_refused_identically(self, factory: sessionmaker) -> None:
        """`R6-01` §3.1 gives both `DENY`, and a distinguishable refusal discloses membership.

        A caller who could tell the two apart would learn which organizations they are a member
        of by reading a denial, which is state they were never granted.
        """
        stack = two_owner_organization(factory)
        member = _account(factory, "member@example.test")
        grant_membership(stack, member, MEMBER_ROLE, factory=factory)
        member_token = _active_session(factory, member, stack.organization.organization_id)
        outsider = _account(factory, "outsider@example.test")
        outsider_token = _sessions(factory).create(outsider, now=NOW)

        with pytest.raises(ScopeAccessDenied) as as_member:
            _resolver(factory).require_owner(member_token, now=NOW)
        with pytest.raises(ScopeAccessDenied) as as_outsider:
            _resolver(factory).require_owner(outsider_token, now=NOW)

        assert str(as_member.value) == str(as_outsider.value)

    def test_it_returns_the_context_rather_than_a_boolean(self, factory: sessionmaker) -> None:
        """A boolean invites a caller who forgets to check it; the failure mode is silence.

        Returning the context means the only way past this call is to have been permitted.
        """
        stack = two_owner_organization(factory)
        token = _active_session(factory, stack.first.account_id, stack.organization.organization_id)

        context = _resolver(factory).require_owner(token, now=NOW)

        assert context.organization_id == stack.organization.organization_id
        assert context.is_owner


class TestTheRequestNeverNamesItsOwnScope:
    """`R6-01` §5's critical rule: identifiers never grant authority."""

    def test_the_active_organization_is_accepted(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        token = _active_session(factory, stack.first.account_id, stack.organization.organization_id)

        context = _resolver(factory).for_request(
            token, organization_id=stack.organization.organization_id, now=NOW
        )

        assert context.organization_id == stack.organization.organization_id

    def test_another_organization_the_actor_belongs_to_is_still_refused(
        self, factory: sessionmaker
    ) -> None:
        """The case that looks harmless, and is the one the rule is about.

        The actor is a genuine owner of both organizations, so a membership check alone permits
        this. `FR-027` allows at most one active organization; honoring a request-named one makes
        the session's active organization advisory and both reachable at once.
        """
        stack = two_owner_organization(factory)
        second = _organizations(factory).create_organization(
            "Beta", stack.first.account_id, now=NOW
        )
        token = _active_session(factory, stack.first.account_id, stack.organization.organization_id)

        with pytest.raises(ScopeAccessDenied):
            _resolver(factory).for_request(token, organization_id=second.organization_id, now=NOW)

    def test_an_unknown_organization_and_a_non_active_one_refuse_identically(
        self, factory: sessionmaker
    ) -> None:
        """`R6-03` closed this enumeration oracle on the switch path; it stays closed here."""
        stack = two_owner_organization(factory)
        second = _organizations(factory).create_organization(
            "Beta", stack.first.account_id, now=NOW
        )
        token = _active_session(factory, stack.first.account_id, stack.organization.organization_id)
        resolver = _resolver(factory)

        with pytest.raises(ScopeAccessDenied) as unknown:
            resolver.for_request(token, organization_id="no-such-organization", now=NOW)
        with pytest.raises(ScopeAccessDenied) as not_active:
            resolver.for_request(token, organization_id=second.organization_id, now=NOW)

        assert str(unknown.value) == str(not_active.value)

    def test_naming_no_organization_uses_the_session(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        token = _active_session(factory, stack.first.account_id, stack.organization.organization_id)

        context = _resolver(factory).for_request(token, now=NOW)

        assert context.organization_id == stack.organization.organization_id


class TestStepsTwoAndThreeStillRun:
    """Step 4 is reachable only through steps 2 and 3 (`R3-01` §4, `R6-01` §5)."""

    def test_an_invalid_token_is_refused(self, factory: sessionmaker) -> None:
        with pytest.raises(AuthenticationFailed):
            _resolver(factory).resolve("not-a-token", now=NOW)

    def test_a_disabled_account_is_refused_before_any_role_lookup(
        self, factory: sessionmaker
    ) -> None:
        """Scenario 16, satisfied at step 3 rather than here (`R6-01` §4).

        The refusal is `AuthenticationFailed` rather than `ScopeAccessDenied`, which is what
        proves it happened at `R3-05`'s chokepoint and not in this module's membership logic.
        """
        stack = two_owner_organization(factory)
        token = _active_session(
            factory, stack.second.account_id, stack.organization.organization_id
        )
        LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory)).disable_account(
            stack.second.account_id, now=NOW
        )

        with pytest.raises(AuthenticationFailed):
            _resolver(factory).resolve(token, now=NOW)

    def test_an_expired_session_is_refused(self, factory: sessionmaker) -> None:
        stack = two_owner_organization(factory)
        token = _active_session(factory, stack.first.account_id, stack.organization.organization_id)

        with pytest.raises(AuthenticationFailed):
            _resolver(factory).resolve(token, now=NOW + LIFETIME + timedelta(seconds=1))


class TestTheFinalOwnerInvariantIsNotDuplicated:
    """`R6-01` §4: authorization permits; the invariant refuses. Two different answers."""

    def test_a_final_owner_demoting_themselves_is_authorized_and_still_fails(
        self, factory: sessionmaker
    ) -> None:
        """Scenario 17, and the sequence that proves the guard was not moved into the resolver.

        A resolver that pre-checks the final-owner rule raises `ScopeAccessDenied` at
        `require_owner` and this test fails at the first line. The correct behavior is that
        authorization *succeeds* -- the actor really is an owner -- and the write refuses with
        `FINAL_OWNER_FAILURE`, which names its cause because `FR-013` requires it to.
        """
        stack = two_owner_organization(factory)
        organizations = _organizations(factory)
        organizations.demote_to_member(
            stack.organization.organization_id,
            stack.second.account_id,
            actor_account_id=stack.first.account_id,
            now=NOW,
        )
        token = _active_session(factory, stack.first.account_id, stack.organization.organization_id)

        context = _resolver(factory).require_owner(token, now=NOW)
        assert context.is_owner

        with pytest.raises(Exception) as refusal:
            organizations.demote_to_member(
                stack.organization.organization_id,
                stack.first.account_id,
                actor_account_id=stack.first.account_id,
                now=NOW,
            )
        assert not isinstance(refusal.value, ScopeAccessDenied)
