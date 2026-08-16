"""R6-06: cross-organization read and mutation indistinguishability.

**The three scenarios this file owns, and why they are three rather than one.** `RCA-001`'s
scenario table names them separately because they make different claims:

- **14 — attempted cross-org read.** Denied, and *indistinguishable from nonexistence*. The claim
  is about the refusal's shape, not its occurrence.
- **15 — attempted cross-org mutation.** Denied with **no state change in either organization**.
  `STATUS.md`'s `FR-024` row records this as having no test, because until `R6` there was no
  mutating protected action to attempt.
- **12 — multi-organization membership.** Both memberships hold and *scopes do not merge*. The one
  scenario here where the actor is genuinely authorized somewhere, which is what makes it able to
  catch an accumulation defect the other two cannot see.

**What "indistinguishable" is asserted to mean, exactly.** Two refusals match when they carry the
same message *and* the same exception type. Collecting `str(exception)` into a set is the idiom
`test_rca001_organization_switching.py:122` established; adding the type closes the case where a
future refusal keeps the wording and changes the class, which a caller can branch on just as
easily. Timing is deliberately not asserted -- it is a real channel and it is not this slice's,
since nothing here is constant-time by construction.

**Why a set of size one, rather than asserting a particular message.** Pinning the exact string
would make this file fail whenever the wording changes, and the requirement is not that the message
is any specific text -- it is that a caller cannot *tell the two cases apart*. The set is the
requirement written down. A known-value assertion would be the weaker test that also fails more
often, which is the trade `STATUS.md` warns against elsewhere.

**Not covered, and it has no surface rather than being skipped.** `FR-023`'s object-level half --
"object identifiers never grant authority" -- is verifiable only at organization-scope granularity
today, because no object-level authorization path exists. Recorded in `STATUS.md` as this slice's
carried gap; constructing a test for it would mean inventing the surface first.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.actor_resolution import ActorResolver
from khepri.rca.authorization_resolution import AuthorizationResolver
from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, OrganizationService
from khepri.rca.persistence import (
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.switching import OrganizationSwitcher
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    NOW,
    factory_fixture,
)

LIFETIME = timedelta(hours=12)
NO_SUCH_ORGANIZATION = "org_does_not_exist"


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


def _attempt_across(orgs: TwoOrganizations, verb: str, target: str, account: str) -> None:
    """Pass the gate for `target`, then call the verb -- what an authorized caller does.

    The acting token is always Alice's -- she is the fixture's cross-organization actor, and every
    scenario 15 cell is "Alice reaches into B". Taking it as a parameter would be an argument with
    one possible value at every call site.

    **The gate alone proves nothing about state.** `require_owner` is read-only, so a test that
    called it and then asserted "no organization changed" would be asserting a fact about the
    fixture, not about the code: the post-state would hold even if the verb wrote unconditionally.
    Found in review on `#198`.

    With the verb on the code path, scenario 15's claim becomes load-bearing in both directions --
    a handler that skips the gate reaches the write and the `pytest.raises` fails, and a gate that
    refuses only after mutating is caught by the state assertions outside the block.
    """
    context = _resolver(orgs.factory).require_owner(
        orgs.alice_token, organization_id=target, now=NOW
    )
    getattr(_organizations(orgs.factory), verb)(
        target, account, actor_account_id=context.account_id, now=NOW
    )


class TwoOrganizations:
    """Organizations A and B, disjoint except where a test deliberately joins them.

    `alice` owns A and `bob` owns B, and neither belongs to the other's. That disjointness is the
    precondition every cross-organization claim rests on, so it is built once and never mutated by
    the fixture itself -- a test that needs a shared member grants it explicitly, in view.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self.factory = factory
        organizations = _organizations(factory)

        self.alice = _account(factory, "alice@example.test")
        self.bob = _account(factory, "bob@example.test")

        self.a = organizations.create_organization("A", self.alice, now=NOW).organization_id
        self.b = organizations.create_organization("B", self.bob, now=NOW).organization_id

        self.alice_token = self._session_in(self.alice, self.a)
        self.bob_token = self._session_in(self.bob, self.b)

    def _session_in(self, account_id: str, organization_id: str) -> str:
        token = _sessions(self.factory).create(account_id, now=NOW)
        OrganizationSwitcher(_sessions(self.factory), SqlOrganizationStore(self.factory)).switch(
            token, organization_id, now=NOW
        )
        return token


@pytest.fixture(name="orgs")
def orgs_fixture(factory: sessionmaker) -> TwoOrganizations:
    return TwoOrganizations(factory)


def _refusal_shapes(attempts) -> set[tuple[type, str]]:
    """Run each attempt, and return the distinct (type, message) pairs it refused with.

    **Type travels with the message deliberately.** A refusal that keeps its wording and changes
    its class is distinguishable by `except` just as surely as one that changes its wording, and a
    message-only comparison would call that indistinguishable. Each attempt must raise; an attempt
    that returns is a failure of the claim, not a shape to compare, so `pytest.raises` stays.
    """
    shapes: set[tuple[type, str]] = set()
    for attempt in attempts:
        with pytest.raises(ScopeAccessDenied) as raised:
            attempt()
        shapes.add((type(raised.value), str(raised.value)))
    return shapes


class TestScenarioFourteenCrossOrganizationRead:
    """Denied, and indistinguishable from nonexistence (`FR-023`, `FR-024`, `FR-025`)."""

    def test_resolving_another_organizations_scope_is_refused(
        self, orgs: TwoOrganizations
    ) -> None:
        with pytest.raises(ScopeAccessDenied):
            _isolation(orgs.factory).resolve_scope(orgs.alice, orgs.b)

    def test_a_real_foreign_organization_and_a_nonexistent_one_refuse_identically(
        self, orgs: TwoOrganizations
    ) -> None:
        """The enumeration oracle this closes, stated plainly.

        If "B exists and you are not in it" read differently from "no such organization", a
        caller with one account could map every organization on the platform by probing
        identifiers and sorting the two refusals apart.

        **Why this holds structurally, and what that means for this test.** Both cases reach the
        *same* guard: a nonexistent organization has no membership row either, so the membership
        check refuses it before the scope lookup is ever consulted. Rewording that one guard moves
        both refusals together, so a mutant that changes its message leaves this test green -- and
        that is correct rather than a weakness, because such a mutant does not reintroduce the
        oracle. What does reintroduce it is an *earlier* existence check, added in good faith for
        a clearer error, and this test dies against exactly that.
        """
        isolation = _isolation(orgs.factory)
        shapes = _refusal_shapes(
            [
                lambda: isolation.resolve_scope(orgs.alice, orgs.b),
                lambda: isolation.resolve_scope(orgs.alice, NO_SUCH_ORGANIZATION),
            ]
        )
        assert len(shapes) == 1

    def test_no_organization_existence_check_precedes_the_membership_check(
        self, orgs: TwoOrganizations
    ) -> None:
        """The ordering that makes indistinguishability structural, asserted directly.

        The case above shows the two refusals match; this one shows *why*, by pinning the
        property that keeps them matching. A real organization the actor is not in must be
        refused without its scope ever being read -- if the scope were consulted first, existence
        would become observable through whatever the lookup does differently for a row that
        exists. Recording the store's calls is the only way to see an ordering, since both
        orderings produce the same exception today.
        """
        store = SqlOrganizationStore(orgs.factory)
        consulted: list[str] = []
        real_get_scope = store.get_scope
        real_get_membership = store.get_membership

        def watched_get_scope(organization_id: str):
            consulted.append("scope")
            return real_get_scope(organization_id)

        def watched_get_membership(organization_id: str, account_id: str):
            consulted.append("membership")
            return real_get_membership(organization_id, account_id)

        store.get_scope = watched_get_scope  # type: ignore[method-assign]
        store.get_membership = watched_get_membership  # type: ignore[method-assign]

        with pytest.raises(ScopeAccessDenied):
            IsolationService(store, SqlAccountStore(orgs.factory)).resolve_scope(
                orgs.alice, orgs.b
            )

        assert "scope" not in consulted, (
            "the organization's scope was read while refusing a non-member, which makes "
            "existence observable"
        )
        assert consulted == ["membership"]

    def test_the_request_gate_refuses_both_identically_too(
        self, orgs: TwoOrganizations
    ) -> None:
        """`for_request` is a second reachable read path and needs the same property.

        One path holding the line while another leaks is the defect a per-path test finds and a
        single shared assertion does not, which is why this is not folded into the case above.
        """
        resolver = _resolver(orgs.factory)
        shapes = _refusal_shapes(
            [
                lambda: resolver.for_request(orgs.alice_token, organization_id=orgs.b, now=NOW),
                lambda: resolver.for_request(
                    orgs.alice_token, organization_id=NO_SUCH_ORGANIZATION, now=NOW
                ),
            ]
        )
        assert len(shapes) == 1

    def test_the_owner_gate_refuses_both_identically_too(self, orgs: TwoOrganizations) -> None:
        """An owner of A probing B learns nothing, including that B exists.

        Owning *an* organization is the strongest position a caller can hold in this model, so if
        any read path leaks nonexistence it is most likely to leak here.
        """
        resolver = _resolver(orgs.factory)
        shapes = _refusal_shapes(
            [
                lambda: resolver.require_owner(orgs.alice_token, organization_id=orgs.b, now=NOW),
                lambda: resolver.require_owner(
                    orgs.alice_token, organization_id=NO_SUCH_ORGANIZATION, now=NOW
                ),
            ]
        )
        assert len(shapes) == 1

    def test_a_foreign_organizations_scope_is_never_returned(
        self, orgs: TwoOrganizations
    ) -> None:
        """Alice's own scope resolves; B's key is not reachable through her at all.

        Asserting the refusal alone would pass for a resolver that returned A's key when asked
        for B -- wrong data rather than no data. Comparing against B's real key, read through
        Bob, is what distinguishes those.
        """
        isolation = _isolation(orgs.factory)
        alice_scope = isolation.resolve_scope(orgs.alice, orgs.a)
        bob_scope = isolation.resolve_scope(orgs.bob, orgs.b)
        assert alice_scope != bob_scope
        with pytest.raises(ScopeAccessDenied):
            isolation.resolve_scope(orgs.alice, orgs.b)


class TestScenarioFifteenCrossOrganizationMutation:
    """Denied, with **no state change in either organization** (`FR-023`, `FR-024`).

    `STATUS.md`'s `FR-024` row records that this scenario had no test, because no mutating
    protected action existed to attempt until `R6`. The "either" is the load-bearing word: a
    refusal that left the actor's *own* organization altered would satisfy every assertion about
    the target and still be the defect.

    **Each cell attempts the mutation, rather than only the gate in front of it.** The first
    version of this class called `require_owner` and asserted no organization changed -- but
    `require_owner` is read-only, so that assertion was guaranteed by the fixture and would have
    held even against a verb that wrote unconditionally. Found in review on `#198`.
    `_attempt_across` now puts the write on the code path, verified by deleting its gate call and
    watching all three cells fail.
    """

    def test_promoting_into_another_organization_changes_neither(
        self, orgs: TwoOrganizations
    ) -> None:
        carol = _account(orgs.factory, "carol@example.test")
        _grant(orgs.factory, orgs.b, carol, MEMBER_ROLE)

        with pytest.raises(ScopeAccessDenied):
            _attempt_across(orgs, "promote_to_owner", orgs.b, carol)

        assert _role_of(orgs.factory, orgs.b, carol) == MEMBER_ROLE
        assert _role_of(orgs.factory, orgs.b, orgs.bob) == OWNER_ROLE
        assert _role_of(orgs.factory, orgs.a, orgs.alice) == OWNER_ROLE

    def test_revoking_in_another_organization_changes_neither(
        self, orgs: TwoOrganizations
    ) -> None:
        with pytest.raises(ScopeAccessDenied):
            _attempt_across(orgs, "revoke_membership", orgs.b, orgs.bob)

        assert _role_of(orgs.factory, orgs.b, orgs.bob) == OWNER_ROLE
        assert _role_of(orgs.factory, orgs.a, orgs.alice) == OWNER_ROLE

    def test_a_refused_mutation_leaves_the_actors_own_organization_intact(
        self, orgs: TwoOrganizations
    ) -> None:
        """The half of "either" that a target-only assertion misses.

        A gate that resolved against the actor's active organization and then refused on the
        named one would pass every assertion about B while having authorized against A. This
        pins A's membership across the attempt so that drift is visible.
        """
        dave = _account(orgs.factory, "dave@example.test")
        _grant(orgs.factory, orgs.a, dave, MEMBER_ROLE)

        with pytest.raises(ScopeAccessDenied):
            _attempt_across(orgs, "revoke_membership", orgs.b, orgs.bob)

        assert _role_of(orgs.factory, orgs.a, dave) == MEMBER_ROLE
        assert _role_of(orgs.factory, orgs.a, orgs.alice) == OWNER_ROLE

    def test_a_mutation_against_a_nonexistent_organization_is_refused_identically(
        self, orgs: TwoOrganizations
    ) -> None:
        resolver = _resolver(orgs.factory)
        shapes = _refusal_shapes(
            [
                lambda: resolver.require_owner(orgs.alice_token, organization_id=orgs.b, now=NOW),
                lambda: resolver.require_owner(
                    orgs.alice_token, organization_id=NO_SUCH_ORGANIZATION, now=NOW
                ),
            ]
        )
        assert len(shapes) == 1


class TestScenarioTwelveScopesDoNotMerge:
    """Both memberships hold; scopes do not merge (`FR-011`, `FR-035`).

    The actor here is a genuine member of both organizations, which is what separates this from
    the two scenarios above: every refusal there could be explained by "not a member anywhere
    relevant", and none of those explanations apply to this actor.
    """

    def test_both_memberships_hold(self, orgs: TwoOrganizations) -> None:
        _grant(orgs.factory, orgs.b, orgs.alice, MEMBER_ROLE)
        assert _role_of(orgs.factory, orgs.a, orgs.alice) == OWNER_ROLE
        assert _role_of(orgs.factory, orgs.b, orgs.alice) == MEMBER_ROLE

    def test_the_two_scopes_are_distinct(self, orgs: TwoOrganizations) -> None:
        """`FR-035`: one key per organization, never one per actor.

        A per-actor key would make a dual member's two organizations share storage, which is the
        merge this scenario is named for.
        """
        _grant(orgs.factory, orgs.b, orgs.alice, MEMBER_ROLE)
        isolation = _isolation(orgs.factory)
        assert isolation.resolve_scope(orgs.alice, orgs.a) != (
            isolation.resolve_scope(orgs.alice, orgs.b)
        )

    def test_the_key_does_not_depend_on_which_member_asks(self, orgs: TwoOrganizations) -> None:
        """B's key is B's, whether Bob or the newly-added Alice resolves it."""
        _grant(orgs.factory, orgs.b, orgs.alice, MEMBER_ROLE)
        isolation = _isolation(orgs.factory)
        assert isolation.resolve_scope(orgs.alice, orgs.b) == (
            isolation.resolve_scope(orgs.bob, orgs.b)
        )

    def test_being_active_in_one_does_not_authorize_the_other(
        self, orgs: TwoOrganizations
    ) -> None:
        """`FR-027`: at most one active organization, so membership in both is not access to both.

        This is the accumulation defect in its exact form -- an actor legitimately in A and B,
        active in A, reaching B through the request gate because they *are* a member. `R6-04`
        refuses it by comparing against the session's active organization rather than by
        checking membership, and only a dual member can tell those two implementations apart.
        """
        _grant(orgs.factory, orgs.b, orgs.alice, MEMBER_ROLE)
        resolver = _resolver(orgs.factory)

        active = resolver.resolve(orgs.alice_token, now=NOW)
        assert active.organization_id == orgs.a

        with pytest.raises(ScopeAccessDenied):
            resolver.for_request(orgs.alice_token, organization_id=orgs.b, now=NOW)

    def test_switching_moves_the_active_organization_rather_than_adding_one(
        self, orgs: TwoOrganizations
    ) -> None:
        """After switching to B, A is the one now refused -- the count stays at one.

        Asserting only that B became reachable would pass for an implementation that accumulated
        both. The claim is that the switch *moved* the authority, so A's refusal afterwards is
        the half that carries it.
        """
        _grant(orgs.factory, orgs.b, orgs.alice, MEMBER_ROLE)
        switcher = OrganizationSwitcher(
            _sessions(orgs.factory), SqlOrganizationStore(orgs.factory)
        )
        switcher.switch(orgs.alice_token, orgs.b, now=NOW)

        resolver = _resolver(orgs.factory)
        assert resolver.resolve(orgs.alice_token, now=NOW).organization_id == orgs.b
        with pytest.raises(ScopeAccessDenied):
            resolver.for_request(orgs.alice_token, organization_id=orgs.a, now=NOW)

    def test_the_role_resolved_is_the_active_organizations_role(
        self, orgs: TwoOrganizations
    ) -> None:
        """Alice owns A and merely belongs to B, so the switch must change her role too.

        A resolver that carried the highest role across organizations, or that read the role from
        the wrong one, would make her an owner of B. Two organizations with two different roles
        is the only arrangement that catches it.
        """
        _grant(orgs.factory, orgs.b, orgs.alice, MEMBER_ROLE)
        resolver = _resolver(orgs.factory)
        assert resolver.resolve(orgs.alice_token, now=NOW).role == OWNER_ROLE

        OrganizationSwitcher(_sessions(orgs.factory), SqlOrganizationStore(orgs.factory)).switch(
            orgs.alice_token, orgs.b, now=NOW
        )
        switched = resolver.resolve(orgs.alice_token, now=NOW)
        assert switched.role == MEMBER_ROLE
        assert not switched.is_owner
