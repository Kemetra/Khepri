"""R6-05: the exhaustive `{owner, member, non-member, unauthenticated}` action matrix.

**What this file is, and why it is not a second copy of `R6-04`'s tests.** `RCA-001`'s
Verification section requires one test per cell of `R6-01` §3's matrix, and `STATUS.md` records
that no such test existed. `test_rca001_authorization_resolution.py` proves the resolver's
*mechanism* -- that roles are read live, that the owner gate refuses a member. This file asks a
different question of the same code: for each actor kind and each protected action, does the
specified outcome occur? Organizing by cell is what makes an absent row visible as a hole in a
table rather than as a test nobody noticed was missing.

**Every cell drives the real action, not just the gate in front of it.** A `pytest.raises` on
`require_owner` restates `TestTheOwnerGate` and cannot fail in any new way -- and asserting the
post-state after a *read-only* gate is worse than useless, because the assertion is then guaranteed
by fixture setup and would hold even if the verb wrote unconditionally. That defect was in the
first version of this file and was found in review on `#197`/`#198`.

So every cell goes through `_attempt`, which passes the gate and *then* calls the verb, exactly as
an authorized caller must. Two distinct defects now die here: a handler that skips the gate reaches
the verb and the `pytest.raises` fails, and a gate that raises *after* mutating is caught by the
state assertion outside the block. Verified by deleting the gate call from `_attempt` and watching
all nine `DENY` cells fail.

**The three owner-only rows are one parametrized table, not three near-identical classes.** They
share one shape -- an owner-only mutation of one membership -- so `OWNER_ONLY_ROWS` ×
`DENIED_COLUMNS` expresses the nine cells as data. That is what `CodeScene` flagged as duplication
on `#197`, and deduplicating it also made the file read like the specification's own table, where a
missing row is a missing line rather than an absent method nobody counts. The `PERMIT` cells stay
separate, because "the action proceeded" means a different end state for each of the three.

**The gated path is what is under test, and that is a deliberate boundary.** The three owner-only
verbs take `actor_account_id` for attribution and check no authority of their own, so calling
`promote_to_owner` directly succeeds regardless of the caller's role. That is not a defect this
file can close and not one it should hide: `R6-04` placed the check in the gate, and proving that
*nothing reaches the verbs except through the gate* is `R6-08`'s whole subject. Here, each cell
drives the action the way an authorized caller must -- resolve, then act -- and `R6-08` makes that
the only available route. `STATUS.md` carries the finding so it is inherited rather than
rediscovered.

**One cell of §3.1 is uncovered, and it is named rather than papered over.** Scope resolution's
`unauthenticated` column cannot be tested at this surface: `IsolationService.resolve_scope` takes
an `account_id` and no token, so it distinguishes no authenticated owner from an arbitrary caller
presenting that owner's identifier. `TestResolveAnIsolationScope` records it and asserts the
signature that makes it true, so the gap fails loudly when an authenticated boundary arrives
(`R7`). A matrix that quietly counted an unknown-identifier refusal as the unauthenticated cell
would be exactly the "test that cannot fail" this file exists to avoid.

**So this file covers 19 of §3.1's 20 cells, and the matrix is not complete.** `RCA-001`'s
Verification requirement is not satisfied until that cell is expressible. Scenario 18 is fully
tested here; **scenario 19 is partial**, because it requires denial for *every* protected action
and `TestScenarioNineteen` reaches only the resolver methods -- §3.2's six account-scoped actions
are out of scope below, and the isolation cell is the one named above. Stated here as well as in
`STATUS.md` because a reader reaching for "is the matrix done?" opens this file first.

**Scope: `R6-01` §3.1 only.** The six §3.2 account-scoped actions turn on self-versus-another
account, and `AuthorizationContext` carries the acting `account_id` with no target, so those cells
cannot be expressed without the context change `authorization_resolution.py` defers to `R6-02`.
Covering them here would mean inventing a target parameter mid-slice. Recorded as a carried gap in
`STATUS.md`; §3.1's five actions appear below, one cell short.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import NamedTuple

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


MATRIX_DESIGN = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-08-15-r6-01-authorization-matrix-design.md"
)

#: Every §3.1 action, keyed to the class in this file that covers it.
#:
#: The values are what makes this more than a second hand-maintained list: the *keys* are checked
#: against the design note's own §3.1 table, so an action added there without a test class here
#: fails. `tasks.md:191` requires the matrix to be "exhaustive by construction -- adding an action
#: without a row fails", and a tuple nobody diffs against anything satisfies that only by
#: convention. Found in review on `#197`.
#:
#: `R4` and `R5` extend §3.1 by design (`R6-01` §7), so this is the assertion that makes those
#: slices notice they owe the matrix a row.
ACTION_COVERAGE = {
    "Promote to owner": "TestTheOwnerOnlyRows",
    "Demote to member": "TestTheOwnerOnlyRows",
    "Revoke a membership": "TestTheOwnerOnlyRows",
    "Resolve an isolation scope": "TestResolveAnIsolationScope",
    "Switch active organization": "TestSwitchActiveOrganization",
}


def _actions_in_the_design() -> list[str]:
    """The §3.1 action column, read from the governed design note rather than restated.

    Parsing the table is deliberate: a copied list is a second source of truth for one fact, which
    is what `STATUS.md` and the `RRA-009` divergence both warn about. If the note is reformatted
    this test fails loudly rather than silently comparing against nothing -- the row-count floor
    below is what makes that failure visible.
    """
    text = MATRIX_DESIGN.read_text(encoding="utf-8")
    section = text.split("### 3.1 Organization-scoped actions")[1].split("### 3.2")[0]
    return [
        line.split("|")[1].strip()
        for line in section.splitlines()
        if line.startswith("| ") and "PERMIT" in line or line.startswith("| ") and "DENY" in line
    ]


def test_every_protected_action_in_the_design_has_a_matrix_class() -> None:
    """Exhaustiveness by construction (`tasks.md:191`).

    Adding a row to `R6-01` §3.1 without adding a test class here fails this, which is the
    property the task requires and which a hand-maintained tuple cannot provide on its own.
    """
    actions = _actions_in_the_design()
    assert len(actions) >= 5, (
        f"parsed {len(actions)} actions from the design note's §3.1 table; the parser is broken "
        "or the note was reformatted, and either way this test is comparing against nothing"
    )

    covered = set(ACTION_COVERAGE)
    assert set(actions) == covered, (
        f"§3.1 actions without a matrix class: {sorted(set(actions) - covered)}; "
        f"classes naming an action the design no longer lists: {sorted(covered - set(actions))}"
    )

    defined = {name for name in globals() if name.startswith("Test")}
    assert set(ACTION_COVERAGE.values()) <= defined, (
        f"ACTION_COVERAGE names classes that do not exist: "
        f"{sorted(set(ACTION_COVERAGE.values()) - defined)}"
    )


@pytest.fixture(name="stack")
def stack_fixture(factory: sessionmaker) -> Stack:
    return Stack(factory)


def _attempt(stack: Stack, verb: str, token: str, account: str) -> None:
    """Do what an authorized caller does: pass the gate, then call the verb.

    **Why every cell goes through this instead of calling the gate alone.** A `DENY` cell claims
    the *action did not happen*, and that claim is only load-bearing if the action was on the code
    path. A test that calls `require_owner` and then asserts the membership is unchanged asserts
    nothing about the code: `require_owner` is read-only, so the post-state was guaranteed by
    fixture setup and would hold even if the verb wrote unconditionally.

    Putting both calls inside one helper makes the refusal the thing that *prevents* the write.
    Found in review on `#197`/`#198`; verified by deleting the gate call below and watching the
    post-state assertions fail rather than the `pytest.raises`.

    The organization comes from the fixture rather than from a parameter: every cell in this file
    acts on the one organization `Stack` builds, so a target argument would have one possible value
    at each call site. Cross-organization targeting is `R6-06`'s subject, not this file's.
    """
    context = _resolver(stack.factory).require_owner(
        token, organization_id=stack.organization_id, now=NOW
    )
    getattr(stack.organizations, verb)(
        stack.organization_id, account, actor_account_id=context.account_id, now=NOW
    )


class Cell(NamedTuple):
    """One denied cell of the matrix: an action, a target, an actor kind, and the refusal.

    A named tuple rather than a tuple of five positional values, so the parametrized test takes
    *one* argument and each field is read by name at the point it is used.
    """

    verb: str
    subject: str
    expected: str
    column: str
    refusal: type[Exception]


#: The nine denied cells of `R6-01` §3.1 rows 1-3, as one table.
#:
#: One row per cell rather than two axes crossed, because a `pytest` fixture-argument per axis is
#: how this method grew six parameters -- and because the specification's own table is a list of
#: cells, not a product. Each entry is: the verb, whose membership the cell targets and what it
#: must still read afterwards, the acting column, and the refusal that column must raise.
#:
#: **The demotion rows target `member`, not `owner`.** The setup promotes `stack.member` to be the
#: second owner `FR-013` requires, and that promoted account is the one the attempted demotion aims
#: at -- so it is the one whose role must be unchanged. Asserting `stack.owner` instead would be
#: satisfied by a demotion path that hit the wrong target and then raised. Found in review on
#: `#197`.
#:
#: `unauthenticated` raises `AuthenticationFailed` rather than `ScopeAccessDenied`, and the
#: difference is the point: no actor is established, so no row is reached at all (`R6-01` §3.3,
#: scenario 19). One shared exception type would erase that distinction.
DENIED_CELLS = tuple(
    Cell(verb=verb, subject=subject, expected=expected, column=column, refusal=refusal)
    for verb, subject, expected in (
        ("promote_to_owner", "member", MEMBER_ROLE),
        ("demote_to_member", "member", OWNER_ROLE),
        ("revoke_membership", "member", MEMBER_ROLE),
    )
    for column, refusal in (
        ("member", ScopeAccessDenied),
        ("non_member", ScopeAccessDenied),
        ("unauthenticated", AuthenticationFailed),
    )
)


def _token_for(stack: Stack, column: str) -> str:
    return {
        "member": stack.member_token,
        "non_member": stack.outsider_token,
        "unauthenticated": INVALID_TOKEN,
    }[column]


class TestTheOwnerOnlyRows:
    """`R6-01` §3.1 rows 1-3: owner PERMIT, member/non-member/unauthenticated DENY.

    Promotion, demotion, and revocation share one shape -- an owner-only mutation of one
    membership -- so they are one parametrized table rather than three classes differing only in a
    verb name. The `PERMIT` cells stay separate below, because each proves a different end state.

    **The member column of revocation is not "a member leaving".** Matrix note 1: no operation
    expresses self-revocation, so that is a distinct action with its own row if it is ever added,
    not a widening of this cell.
    """

    @pytest.mark.parametrize("cell", DENIED_CELLS, ids=lambda c: f"{c.verb}-{c.column}")
    def test_the_action_is_refused_and_no_role_changes(self, stack: Stack, cell: Cell) -> None:
        """Nine cells: three owner-only actions against three denied actor kinds.

        The assertion after the block is the load-bearing one. `_attempt` puts the verb on the
        code path, so a handler that skipped the gate would reach the write and fail the
        `pytest.raises`; a gate that refused only *after* mutating is caught here instead.
        """
        target_account = getattr(stack, cell.subject)
        token = _token_for(stack, cell.column)
        if cell.verb == "demote_to_member":
            # Demotion needs a second owner (`FR-013` protects the final one), and promoting the
            # fixture's member to provide it would hand the `member` column an owner's token --
            # the cell would then fail for the wrong reason. A fresh plain member keeps it honest.
            _promote(stack, stack.member)
            if cell.column == "member":
                token = _plain_member_token(stack)

        with pytest.raises(cell.refusal):
            _attempt(stack, cell.verb, token, target_account)

        assert _role_of(stack.factory, stack.organization_id, target_account) == cell.expected


class TestTheOwnerPermitCells:
    """`R6-01` §3.1 rows 1-3, owner column: each proves a different end state.

    Kept as three tests rather than folded into the table above, because "the action proceeded"
    means something different for each -- a raised role, a lowered one, and an absent membership.
    A parametrized expected-value would hide that behind a lookup.
    """

    def test_an_owner_promotes_a_member(self, stack: Stack) -> None:
        _attempt(stack, "promote_to_owner", stack.owner_token, stack.member)
        assert _role_of(stack.factory, stack.organization_id, stack.member) == OWNER_ROLE

    def test_an_owner_demotes_another_owner(self, stack: Stack) -> None:
        """A second owner first: `FR-013` refuses to demote the final one regardless of authority.

        Without it this cell would fail on an invariant that is not authorization, and the matrix
        would be asserting the wrong thing.
        """
        _promote(stack, stack.member)
        _attempt(stack, "demote_to_member", stack.owner_token, stack.member)
        assert _role_of(stack.factory, stack.organization_id, stack.member) == MEMBER_ROLE

    def test_an_owner_revokes_a_member(self, stack: Stack) -> None:
        _attempt(stack, "revoke_membership", stack.owner_token, stack.member)
        assert _role_of(stack.factory, stack.organization_id, stack.member) is None


class TestResolveAnIsolationScope:
    """`R6-01` §3.1 row 4: owner **and member** PERMIT, non-member and unauthenticated DENY.

    This is one of the two rows where the member column is a PERMIT, and keeping it distinct from
    the owner-only rows is the point of testing it separately -- a matrix that treated every §3.1
    action as owner-only would pass three rows and be wrong about two.

    `R6-01` §6 settles that `isolation.py`'s own membership refusal *is* the enforcement here, so
    these cells drive `IsolationService` directly rather than adding a second gate in front of it.

    **The unauthenticated cell of this row is not covered, and the reason is recorded rather than
    hidden.** `resolve_scope` takes an `account_id` and no token, so it authenticates nobody: a
    caller who knows a member's identifier gets that member's scope. Passing an unknown identifier
    tests the nonexistent-account branch, not the unauthenticated one, and naming such a test
    "unauthenticated" would be the matrix claiming a cell it never reached.
    `test_the_unauthenticated_cell_is_unreachable_at_this_surface` states the gap and fails when
    the surface changes.
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

    def test_an_unknown_account_identifier_is_refused(self, stack: Stack) -> None:
        """The nonexistent-account branch, which is **not** the unauthenticated column.

        Named for what it actually covers. An earlier version of this test called itself
        `test_an_unauthenticated_caller_is_refused`, and the name was the defect: it implied a
        matrix cell that the assertion does not reach. See the class docstring.
        """
        with pytest.raises(ScopeAccessDenied):
            _isolation(stack).resolve_scope("no-such-account", stack.organization_id)

    def test_the_unauthenticated_cell_is_unreachable_at_this_surface(self, stack: Stack) -> None:
        """**A recorded gap, not an endorsement** -- `resolve_scope` authenticates nobody.

        It takes an `account_id` and no token, so a caller who merely *knows* a member's
        identifier resolves that member's scope. The identifier is doing the work of a
        credential, which is precisely what `R6-01` §5's critical rule forbids: "object
        identifiers never grant authority".

        This is not a defect this slice can close, and pretending otherwise is worse than
        recording it. `IsolationService` has no production caller (`STATUS.md`, `FR-031`), so the
        exposure is latent -- the authenticated boundary in front of it is `R7`'s. What must not
        happen is a matrix that *looks* complete while its unauthenticated cell is untested, so
        the gap is asserted here in the idiom `test_rca001_guard_evidence.py` established: the
        test fails the moment `resolve_scope` grows an authentication parameter, which is the
        moment this note needs rewriting.
        """
        import inspect

        parameters = inspect.signature(IsolationService.resolve_scope).parameters
        assert "token" not in parameters
        assert set(parameters) == {"self", "account_id", "organization_id"}

        owner_scope = _isolation(stack).resolve_scope(stack.owner, stack.organization_id)
        assert owner_scope, (
            "resolve_scope returns a scope to any caller presenting a member's account_id; "
            "the unauthenticated cell of R6-01 §3.1 row 4 cannot be tested at this surface"
        )


class TestSwitchActiveOrganization:
    """`R6-01` §3.1 row 5: owner and member PERMIT, non-member and unauthenticated DENY."""

    def test_an_owner_switches(self, stack: Stack) -> None:
        """Starts from a *cleared* session, so the asserted value was not already true.

        `Stack` switches each token in during setup, so a cell that switched again and asserted
        the organization would pass even against a `switch` that kept its membership check and
        stopped persisting anything. Clearing first makes the assertion observe the write.
        Found in review on `#197`.
        """
        _switcher(stack).clear(stack.owner_token, now=NOW)
        assert _active_organization(stack, stack.owner_token) is None

        _switcher(stack).switch(stack.owner_token, stack.organization_id, now=NOW)
        assert _active_organization(stack, stack.owner_token) == stack.organization_id

    def test_a_member_switches(self, stack: Stack) -> None:
        _switcher(stack).clear(stack.member_token, now=NOW)
        assert _active_organization(stack, stack.member_token) is None

        _switcher(stack).switch(stack.member_token, stack.organization_id, now=NOW)
        assert _active_organization(stack, stack.member_token) == stack.organization_id

    def test_a_non_member_is_refused_and_the_session_stays_unswitched(self, stack: Stack) -> None:
        """Reads the **stored session**, not the resolved context.

        `_context_for` normalizes an active organization with no live membership to `None`, so a
        `switch` that persisted the organization and *then* raised would still resolve to
        `organization_id=None` and satisfy a context-level assertion. Only the raw session shows
        whether anything was written. Found in review on `#197`.
        """
        with pytest.raises(ScopeAccessDenied):
            _switcher(stack).switch(stack.outsider_token, stack.organization_id, now=NOW)

        assert _active_organization(stack, stack.outsider_token) is None

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


def _active_organization(stack: Stack, token: str) -> str | None:
    """The organization stored on the session itself, bypassing the resolver's normalization."""
    return stack.sessions.resolve(token, now=NOW).active_organization_id


def _plain_member_token(stack: Stack) -> str:
    """A token for an account that is a plain member of the organization.

    Used only by the demotion row, whose setup promotes `stack.member` to supply the second owner
    `FR-013` requires. That promotion would otherwise hand the `member` column an owner's token,
    and the cell would pass the gate and fail for a reason that is not the one under test.
    """
    accounts = AccountService(SqlAccountStore(stack.factory))
    account_id = accounts.create_account("plain@example.test", CREDENTIAL).account_id
    _grant_membership(stack.factory, stack.organization_id, account_id, MEMBER_ROLE)
    token = stack.sessions.create(account_id, now=NOW)
    _switcher(stack).switch(token, stack.organization_id, now=NOW)
    return token
