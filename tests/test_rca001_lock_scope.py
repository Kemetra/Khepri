"""Only owner-reducing writes take a row lock (`R1-05`).

`R1-04` put the `FR-013` guard and its write in one transaction under
`SELECT ... FOR UPDATE`. `R1-05` is the complementary claim, and the roadmap states it as "prove
non-owner-reducing operations do not acquire unnecessary locks".

**Why the negative claim needs its own evidence.** A lock that is too *narrow* fails loudly --
`test_rca001_concurrent_final_owner.py` measured `#155` recurring at 4 failures in 12 attempts
against PostgreSQL. A lock that is too *wide* fails silently: every test stays green, correctness is
untouched, and the only symptom is contention between operations that never needed to serialize.
Nothing in the suite would notice `promote_membership` starting to lock every owner row in the
organization.

The roadmap's design requirements name this directly -- "leave unrelated organizations independent"
-- and its stop conditions forbid "two independent final-owner guards". A lock appearing on a path
with no guard to protect is how that second guard arrives: `promote_membership`'s docstring already
warns that taking the lock anyway "would imply a guard exists here and invite a later reader to add
one".

**How these tests work, and why not with a database.** SQLite emits no `FOR UPDATE` and SQLAlchemy
silently omits it for that dialect, so a lock cannot be observed by running the suite -- the same
reason `test_rca001_final_owner.py:247-263` compiles against the PostgreSQL dialect instead. The
positive direction is already covered there and in `test_rca001_revocation.py`; this file covers the
negative direction two ways:

1. **Statically**, across **every module in `src/khepri/rca`**: only methods named in `_MAY_LOCK`
   may reach a lock. A new method fails the test rather than passing unnoticed. The
   scan follows delegation, so "reach" includes calling a helper that locks -- in any module.
2. **By compilation**, asserting each locking statement's predicates clause by clause -- not merely
   that a predicate appears somewhere in the SQL.

The static half is what makes this durable. A test that only compiled today's statements would say
nothing about a lock added tomorrow to a method this file never thought to name.

**Nine gaps closed over three review rounds on `#208`**, each confirmed by watching the mutant
escape the version before the fix, and die after it:

- **Delegation to an allowlisted helper.** The scan was non-transitive *by design*, and that design
  turned out to be an escape hatch.
- **`with_for_update=` as a keyword argument.** It is neither a `Name` nor an `Attribute`, so an AST
  walk over those two node types missed it.
- **The outer `role` predicate dropped.** `assert "role =" in sql` is a disjunction over two
  predicates, so it passed on whichever survived.
- **The subquery `role` predicate dropped.** The same disjunction, from the other side.
- **A caller in another module.** Fixing the first gap created this one: the scan became transitive
  but still read only `persistence.py`, so making `LifecycleService.enable_account` delegate to
  `apply_owner_reducing_change` acquired the lock with all eight tests green. Now the whole package
  is scanned, which surfaced `disable_account` and `demote_to_member` as legitimate service-layer
  reachers.
- **An aliased import.** `import owner_memberships_for_update as lock_owners` then
  `lock_owners(...)` is an ordinary spelling a name-exact match misses. `R6-08` resolves aliases for
  the same reason.
- **An `async def` body.** `ast.AsyncFunctionDef` is not an `ast.FunctionDef`, so async functions
  were dropped from the scan entirely.
- **A local variable alias.** `lock = self._organizations.apply_owner_reducing_change` then
  `lock(...)` records only `lock`. The module-level import-alias fix did not cover a local binding.
- **A disjunction instead of a conjunction.** Counting predicates cannot tell `a AND b` from
  `a OR b`, and the `OR` form locks every owner row in *every* organization. The predicates' shape
  is now asserted, not just their presence.

Three lessons worth carrying, all about this file's own history:

**Self-selected mutants measure imagination, not coverage.** The first version's mutation testing
killed three mutants chosen by its author, all of which the design already anticipated. Nine more
escaped, found by an outside reviewer over three rounds.

**Widening a static analysis changes what shadows what.** The first attempt at package-wide scanning
concatenated every module and parsed once, which *silently weakened* the scan -- see `_rca_modules`.
It was caught by this file's own scanner self-test, which is the argument for having one.

**Each fix opened the next gap.** Transitivity made cross-module reach matter; package-wide scanning
made import aliasing and async matter; resolving import aliases made *local* aliases matter. A
static boundary is only as wide as the spellings it knows, so
`test_the_scanner_sees_the_locks_that_are_there` plants every known route -- that list is the real
statement of what this file can and cannot catch, and it is not a closed set.

**Presence is not shape.** Three separate findings came from assertions that checked a predicate
*existed* without checking where it sat or how it was joined: two `role =` predicates a substring
match could not tell apart, and a conjunction a count could not tell from a disjunction. When
asserting against compiled SQL, pin the clause.
"""

from __future__ import annotations

import ast
import pathlib

from sqlalchemy.dialects import postgresql

from khepri.rca.persistence import (
    organization_owners_for_update,
    owner_memberships_for_update,
)

#: Both function node types. `async def` is `AsyncFunctionDef`, not a subclass of `FunctionDef`.
_AnyFunction = ast.FunctionDef | ast.AsyncFunctionDef

_RCA_PACKAGE = pathlib.Path("src/khepri/rca")
_PERSISTENCE = _RCA_PACKAGE / "persistence.py"


def _rca_modules() -> list[str]:
    """Every RCA module's source, so the scan spans the package rather than one file.

    **Why not just `persistence.py`.** The scan follows delegation, but an earlier version fed it
    only that one file, so a caller in a *different* module was invisible: making
    `LifecycleService.enable_account` (`lifecycle.py`) delegate to `apply_owner_reducing_change`
    acquired the allowlisted lock and left all eight tests green. `lifecycle.py:120` already calls
    that method legitimately, so cross-module reach is the normal shape here, not a hypothetical.
    Found in review on `#208`, after the transitive fix in the same PR made this gap reachable.

    **A list rather than one concatenated string, and that distinction is load-bearing.** The first
    attempt joined every module into one source and parsed it once. That *silently weakened* the
    scan: `_methods_reaching_a_lock` keys on function name, `stores.py` sorts after
    `persistence.py`, and `stores.py`'s `OrganizationStore` Protocol declares
    `def apply_owner_reducing_change(...) -> str: ...` with an empty body. The stub overwrote the
    real implementation, so the scanner reported the package's principal locking method as
    lock-free -- caught only because this file's own self-test asserts that method is found.
    Collecting per-module and taking the union keeps a Protocol stub from masking an implementation.
    """
    return [path.read_text(encoding="utf-8") for path in sorted(_RCA_PACKAGE.rglob("*.py"))]


#: The two module-level statements that carry `FOR UPDATE`, plus the raw SQLAlchemy call, so a
#: method reaching for the lock by any of the three routes is caught.
#: The named locking statements, listed here rather than in `_MAY_LOCK` because this frozenset has
#: a second job: `_lock_aliases` seeds itself from it, so a statement named here is still detected
#: when a caller imports it under an alias. `W1-02`'s two lock a single workspace row by primary
#: key -- the narrowest scope a lock can have -- and
#: `test_w102_workspace_persistence.py` compiles each against the PostgreSQL dialect to assert the
#: `FOR UPDATE` clause and its table, which is the `W1-02` counterpart of the paired-predicate
#: tests below. `W1-03`'s `live_runs_for_update` locks a *set* -- every live run of one version in
#: one scope -- so the cascade projects each run's tombstone from the row a concurrent completion
#: left rather than the one it is about to replace; `test_w103_tombstone_projection.py` compiles it.
_LOCK_ROUTES = frozenset(
    {
        "owner_memberships_for_update",
        "organization_owners_for_update",
        "run_for_update",
        "version_for_update",
        "live_runs_for_update",
    }
)

#: `with_for_update` reaches SQLAlchemy two ways and both must be scanned: as a method
#: (`select(...).with_for_update()`) and as a **keyword argument**
#: (`database.get(Row, id, with_for_update=True)`, also `Session.refresh`). The keyword form issues
#: the same locking query and appears as neither a `Name` nor an `Attribute` in the AST, so a scan
#: that walked only those two node types missed it entirely. Found in review on `#208`.
#:
#: One boundary worth stating, because it looks like a gap and is not. Adding
#: `with_for_update=True` to a `get` *inside* `apply_owner_reducing_change` changes nothing these
#: tests should catch: that method already holds the lock over those rows, so the keyword is
#: redundant rather than newly contending. The scan reports methods, so a lock added to an
#: already-allowlisted method is invisible by design -- and the paired-predicate tests below are
#: what bound how wide *its* lock may be. The keyword form is caught where it matters, in a
#: lock-free method; verified by planting one in `get_membership` and watching two tests fail.
_LOCK_CALL = "with_for_update"

#: The only methods permitted to reach a lock, each with the guard that justifies it.
#:
#: `apply_owner_reducing_change` counts effective owners and then writes, so a concurrent write can
#: invalidate the count between the two. `_apply_membership_change` is the shared boundary, and
#: `revoke_membership` and `demote_membership` reach the lock *through* it -- both can remove an
#: organization's final owner, so both need it. Every other write either raises the owner count or
#: cannot change it.
#:
#: Callers are listed explicitly rather than exempted as "only delegating". The scan is transitive
#: precisely because delegation is a real way to acquire a lock, so a method that reaches one must
#: say so here. Every name below is a claim that this method needs the lock, and the
#: paired-predicate tests below are what check the lock it takes is no wider than its guard.
#:
#: **Two layers, because the scan spans the package.** The store methods hold the lock;
#: `disable_account` (`lifecycle.py`) and `demote_to_member` (`organizations.py`) are the service
#: verbs that reach them, and both are genuinely owner-reducing -- `disable_account` *is* the
#: `FR-013` guard path, and `demote_to_member` can remove an organization's last owner. They
#: appeared only once the scan widened past `persistence.py`, which is the widening working.
#:
#: Removing an external identity can now remove an external-only account's final authentication
#: capability. `owner_reduction_outcome` is the shared final-owner decision, and the three unlink
#: methods are its store/service call chain. They are listed explicitly for the same reason as the
#: membership call chain: delegation is still a locking path, and this operation can reduce the
#: effective-owner count even though it does not change the membership role.
#:
#: Adding a name here is the review conversation this allowlist exists to force, in the same spirit
#: as `R6-08`'s `VERB_CALLER_ALLOWLIST`. It is not a list to extend for convenience.
_MAY_LOCK = frozenset(
    {
        # store-level: the methods that construct the lock
        "apply_owner_reducing_change",
        # `R4-05`: redemption locks the **account row**, not owner memberships.
        # `owner_memberships_for_update` selects rows in organizations the account already owns,
        # and `FR-019`'s invitee owns none -- `FOR UPDATE` over an empty result set acquires no
        # lock, so a concurrent `disable_account` would block on nothing. The account row is the
        # one row both operations certainly touch.
        "account_for_update",
        "redeem_into_membership",
        "_apply_membership_change",
        "revoke_membership",
        "demote_membership",
        # service-level: the owner-reducing verbs that reach it
        "disable_account",
        "demote_to_member",
        # provider-neutral external-capability removal and its shared guard
        "owner_reduction_outcome",
        "unlink_external_identity_outcome",
        "unlink_external_identity",
        "unlink_identity",
        # `R4-05`'s service verb, listed because the scan follows delegation: `redeem` reaches
        # `redeem_into_membership`, which constructs the lock.
        "redeem",
        # `W1-02` workspace transitions. Each reads a column and then decides on it, and the
        # decision is what the lock protects. `complete_analysis_run` and `seal_dataset_version`
        # report **whether this call** performed the transition: without the lock two callers can
        # both read the pre-state, both write, and both be told `True`, and completion
        # additionally discards the first writer's package digest and version provenance, which
        # `FR-111` binds to the run.
        #
        # `set_retention_state` is here after being removed and put back on the same PR, which is
        # worth the sentence. I argued it needed no lock because concurrent tombstones agree on
        # the state they want. They do not agree on `retention_changed_at`: both read `active`,
        # both find the no-op check false, and the second overwrites the first deletion instant --
        # moving the horizon `KHEPRI-DEC-033` §5 anchors to it. Two reviewers found it
        # independently. `tombstone_dataset_version` reaches it by delegation.
        "complete_analysis_run",
        "seal_dataset_version",
        "set_retention_state",
        "tombstone_dataset_version",
        # Adding a derivative locks its *parent*: `add_analysis_run` takes `version_for_update`
        # and `add_artifact_binding` takes `run_for_update`, each requiring the parent still live
        # in the same transaction. The guard is the liveness check; the lock is what stops a
        # concurrent tombstone landing between the check and the insert, which would leave a live
        # derivative of a deleted input that no cascade reaches. Review on `#370` found the window.
        "add_analysis_run",
        "add_artifact_binding",
        # `W1-03`: the deletion's cascade locks the live runs it is about to project and tombstone
        # (`live_runs_for_update`), because a plain read there races `complete_analysis_run`'s
        # `run_for_update`: the cascade would project an immutable tombstone from the
        # pre-completion row and then commit over the completion. Both helpers run inside
        # `set_retention_state`'s transaction, under the version lock it already holds.
        "_tombstone_version",
        "_cascade_tombstone_to_runs",
        # `W1-04`: completion, its seven bindings and the version's seal are one transaction
        # (`FR-111` -- a completed run naming no artifacts must never be readable), under the run
        # lock and then the version lock, in `add_analysis_run`'s order.
        "record_completion",
    }
)


def _lock_aliases(tree: ast.Module) -> frozenset[str]:
    """Local names bound to a locking statement, including aliased imports.

    `from khepri.rca.persistence import owner_memberships_for_update as lock_owners` then
    `lock_owners(...)` reaches the same statement under a name `_LOCK_ROUTES` does not contain, so a
    name-exact match misses it -- verified by planting exactly that and watching all eight tests
    stay green (`#208` review). Module aliases are covered too: `import persistence as p` then
    `p.owner_memberships_for_update(...)` arrives as an `Attribute` whose `attr` is the real name,
    which `_called_names` already records.

    `R6-08`'s `_context_aliases` resolves aliases for the same reason and was added in the same kind
    of review (`#200` P2). Ordinary spellings evade a name-exact scan without anyone intending to.
    """
    aliases = set(_LOCK_ROUTES)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        aliases.update(
            alias.asname for alias in node.names if alias.name in _LOCK_ROUTES and alias.asname
        )
    return frozenset(aliases)


def _is_lock_construction(node: ast.AST, routes: frozenset[str]) -> bool:
    """Whether this single node is one of the three ways to construct a lock.

    Split out from the walk so each route is one flat check: a named locking statement (under any
    local name in `routes`), a `.with_for_update()` call, or a `with_for_update=` keyword.
    """
    if isinstance(node, ast.Name):
        return node.id in routes
    if isinstance(node, ast.Attribute):
        return node.attr == _LOCK_CALL
    if isinstance(node, ast.Call):
        return any(keyword.arg == _LOCK_CALL for keyword in node.keywords)
    return False


def _locks_directly(node: _AnyFunction, routes: frozenset[str]) -> bool:
    """Whether this function body constructs a lock itself, by any of the three routes."""
    return any(_is_lock_construction(inner, routes) for inner in ast.walk(node))


def _local_function_aliases(node: _AnyFunction) -> set[str]:
    """Names a bound method or function was assigned to inside this body.

    `lock = self._organizations.apply_owner_reducing_change` then `lock(...)` calls the locking
    method while `_called_names` records only `lock` -- so the delegation is invisible. This returns
    the *right-hand* names of such assignments, which the caller adds to its call set.

    Verified by planting exactly that in `enable_account` and watching all eight tests stay green
    (`#208` review, second round). The import-alias fix in the first round did not cover it: that
    one resolves module-level `import ... as`; this one is a local binding.
    """
    aliased: set[str] = set()
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Assign):
            continue
        # Only bare references, never calls: `x = f()` binds a *result*, `x = f` binds the callable.
        if isinstance(inner.value, ast.Attribute):
            aliased.add(inner.value.attr)
        elif isinstance(inner.value, ast.Name):
            aliased.add(inner.value.id)
    return aliased


def _called_names(node: _AnyFunction) -> set[str]:
    """Every name this function calls, whether bare (`helper()`) or via an attribute
    (`self._helper()`), plus any callable it bound to a local name.

    The local-binding half matters because a call through a variable records only the variable, so
    delegation through an assignment would otherwise evade the scan -- see
    `_local_function_aliases`.
    """
    called: set[str] = set()
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        target = inner.func
        if isinstance(target, ast.Name):
            called.add(target.id)
        elif isinstance(target, ast.Attribute):
            called.add(target.attr)
    return called | _local_function_aliases(node)


def _methods_reaching_a_lock(*sources: str) -> set[str]:
    """Every function in `sources` that can reach a lock, **including through delegation**.

    Accepts one or many modules. Facts are unioned by function name across modules rather than
    merged by overwriting, so a Protocol stub in one module cannot mask a locking implementation of
    the same name in another -- see `_rca_modules` for the failure that motivated this.

    A direct lock is a reference to a named locking statement, a `.with_for_update()` call, or a
    `with_for_update=` keyword. Transitive reach is then computed to a fixed point: a function
    calling one that locks reaches the lock too.

    **The transitive closure is the correction that matters.** An earlier version scanned only
    direct construction and its docstring defended that as deliberate -- `revoke_membership` and
    `demote_membership` lock only by calling `_apply_membership_change`, which is allowlisted in its
    own right, so they were reported lock-free. That rationale is also an escape hatch: *any*
    method can acquire the lock by delegating to the allowlisted helper, and the scan would not
    notice. Verified by making `promote_membership` delegate to `_apply_membership_change` and
    watching all seven tests stay green. Found in review on `#208`.

    The consequence is that `revoke_membership` and `demote_membership` now appear in the result and
    must be allowlisted explicitly -- which is the honest position, because they *do* take the lock
    and they *do* need it.
    """
    reaching, calls = _collect_lock_facts(sources)
    return _close_over_callers(reaching, calls)


def _functions_in(tree: ast.Module) -> list[_AnyFunction]:
    """Every function definition in one module, **sync and async alike**.

    `async def` parses to `ast.AsyncFunctionDef`, which is *not* an `ast.FunctionDef`, so a scan
    testing only the latter drops async functions entirely -- an async path could then lock with
    every assertion green. Verified by making one RCA method `async def` and watching all eight
    tests pass (`#208` review). No RCA module defines one today; this keeps the claim true when one
    does.
    """
    return [
        node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def _collect_lock_facts(sources: tuple[str, ...]) -> tuple[set[str], dict[str, set[str]]]:
    """Direct lockers, and every name each function calls, keyed by function name.

    Facts are **unioned, never overwritten**: a stub definition cannot retract what a real one
    established, which is what keeps `stores.py`'s Protocol from masking `persistence.py`.
    """
    reaching: set[str] = set()
    calls: dict[str, set[str]] = {}
    for source in sources:
        tree = ast.parse(source)
        routes = _lock_aliases(tree)
        for node in _functions_in(tree):
            calls.setdefault(node.name, set()).update(_called_names(node))
            if _locks_directly(node, routes):
                reaching.add(node.name)
    return reaching, calls


def _close_over_callers(reaching: set[str], calls: dict[str, set[str]]) -> set[str]:
    """Grow `reaching` to a fixed point: whoever calls a lock-reacher reaches the lock.

    Iteration is bounded by the function count, so a mutually-recursive pair cannot loop forever.
    """
    closed = set(reaching)
    for _ in range(len(calls) + 1):
        grown = {name for name, called in calls.items() if called & closed}
        if grown <= closed:
            break
        closed |= grown
    return closed


def test_only_governed_owner_reducing_writes_reach_a_lock() -> None:
    """The load-bearing assertion. A new locking path fails here before it can add contention.

    Mutation-checked: adding `owner_memberships_for_update` to `promote_membership` fails this
    test, and removing `_apply_membership_change` from `_MAY_LOCK` fails it too -- so the
    allowlist cannot be quietly widened without the diff showing it.
    """
    reaching = _methods_reaching_a_lock(*_rca_modules())

    unexpected = reaching - _MAY_LOCK - _LOCK_ROUTES
    assert unexpected == set(), (
        f"these methods acquire a row lock without a guard justifying it: {sorted(unexpected)}. "
        "A lock with no guard to protect is how a second final-owner guard arrives -- see the "
        "roadmap's R1 stop conditions."
    )


def test_the_scanner_sees_the_locks_that_are_there() -> None:
    """Self-test. Without it, a scanner broken into returning an empty set passes the test above.

    Follows `test_rca001_boundary.py::test_rca_import_checker_flags_and_clears_expected_cases`.
    """
    reaching = _methods_reaching_a_lock(*_rca_modules())

    assert "apply_owner_reducing_change" in reaching, "the scanner found no lock at all"
    assert "_apply_membership_change" in reaching

    planted = _methods_reaching_a_lock(
        "from khepri.rca.persistence import owner_memberships_for_update as lock_owners\n"
        "def innocent():\n"
        "    return 1\n"
        "def by_named_statement():\n"
        "    return owner_memberships_for_update('acc_x')\n"
        "def by_method_call():\n"
        "    return select(Row).with_for_update()\n"
        "def by_keyword():\n"
        "    return database.get(Row, 'id', with_for_update=True)\n"
        "def by_alias():\n"
        "    return lock_owners('acc_x')\n"
        "async def by_async():\n"
        "    return owner_memberships_for_update('acc_x')\n"
        "def by_delegation():\n"
        "    return self.by_keyword()\n"
        "def by_two_hops():\n"
        "    return self.by_delegation()\n"
    )
    assert planted == {
        "by_named_statement",
        "by_method_call",
        "by_keyword",
        "by_alias",
        "by_async",
        "by_delegation",
        "by_two_hops",
    }, (
        "the scanner must catch every construction route -- bare name, method call, keyword, "
        "aliased import, and async body -- and follow delegation transitively. Each of these "
        "escaped some earlier version of this file"
    )
    assert "innocent" not in planted, "the scanner must not flag a function that cannot lock"


def test_the_two_locking_statements_still_lock() -> None:
    """The allowlist is only meaningful if the names on it correspond to real locks.

    Without this, deleting `.with_for_update()` from both statements would leave every assertion
    here green: the scanner matches the *name*, and a statement that no longer locks keeps it.
    """
    for statement in (
        owner_memberships_for_update("acc_example"),
        organization_owners_for_update("org_example"),
    ):
        sql = str(statement.compile(dialect=postgresql.dialect()))
        assert "FOR UPDATE" in sql


def test_the_owner_lock_is_scoped_to_one_organization() -> None:
    """ "Leave unrelated organizations independent" (`R1` design requirements).

    `organization_owners_for_update` locks by organization, so two organizations' owner-reducing
    operations do not contend. A statement that dropped the predicate would serialize every
    organization in the table against every other -- correct, and unusably slow.

    This statement is a single flat `WHERE` with one of each predicate, so a substring assertion is
    unambiguous here. `owner_memberships_for_update` is not, and is handled separately below.

    **The predicates must be joined by `AND`, and counting them does not establish that.** Rewriting
    the `where` as `or_(organization_id == ..., role == ...)` keeps both counts at one while
    PostgreSQL locks every owner row in *every* organization plus every membership in the named
    one -- the exact opposite of the independence this test claims. Verified: that mutant passed
    all eight tests before this assertion existed. Found in review on `#208`.
    """
    sql = str(organization_owners_for_update("org_example").compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in sql
    assert sql.count("rca_memberships.organization_id =") == 1, (
        "the lock must be scoped to one organization, by exactly one predicate"
    )
    assert sql.count("rca_memberships.role =") == 1, (
        "only owner rows are locked, not every membership"
    )
    assert _where_clause(sql) == (
        "rca_memberships.organization_id = %(organization_id_1)s "
        "AND rca_memberships.role = %(role_1)s"
    ), (
        "the two predicates must be conjunctive. A disjunction satisfies both counts above and "
        "locks vastly more rows"
    )
    assert " OR " not in _where_clause(sql), "a disjunction here defeats organization independence"


def _where_clause(sql: str) -> str:
    """The `WHERE` body of compiled SQL, normalized to one line and stripped of trailing clauses.

    Exists so a test can assert the predicates' **shape** rather than only their presence. Counting
    operands cannot distinguish `a AND b` from `a OR b`, and the difference is how many rows the
    lock covers.
    """
    body = sql[sql.index("WHERE") + len("WHERE") :]
    for terminator in (" ORDER BY ", " FOR UPDATE", " GROUP BY ", " LIMIT "):
        if terminator in body:
            body = body[: body.index(terminator)]
    return " ".join(body.split())


def _split_on_subquery(sql: str) -> tuple[str, str]:
    """Split compiled SQL into (subquery text, everything outside it).

    Depth-counted rather than sliced on the first `)`. A naive `sql.index(")")` lands inside the
    bound-parameter placeholder `%(account_id_1)s` and truncates the subquery, which made the first
    version of this helper fail against the real statement -- an argument for driving these
    assertions off compiled output rather than a hand-written string.
    """
    start = sql.index("(SELECT")
    end = _matching_paren(sql, start)
    return sql[start : end + 1], sql[:start] + sql[end + 1 :]


def _matching_paren(text: str, start: int) -> int:
    """Index of the `)` closing the `(` at `start`, counting depth."""
    depth = 0
    for offset, character in enumerate(text[start:], start=start):
        depth += {"(": 1, ")": -1}.get(character, 0)
        if depth == 0 and character == ")":
            return offset
    raise AssertionError("the subquery is unbalanced; the statement shape changed")


def test_the_account_lock_is_scoped_to_one_account() -> None:
    """The sibling scope claim. The disable path locks by *account*, because one disablement can
    reduce owners in every organization that account owns -- so its scope is that account's owner
    rows, not one organization's."""
    sql = str(owner_memberships_for_update("acc_example").compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in sql
    assert "rca_memberships.account_id =" in sql, "the lock must be scoped to one account"


def test_the_account_lock_constrains_the_role_in_both_of_its_clauses() -> None:
    """Two `role =` predicates, doing two different jobs, and both must survive.

    `owner_memberships_for_update` is a subquery plus an outer selection:

        WHERE organization_id IN (SELECT organization_id
                                  WHERE account_id = :a AND role = :owner)  <- which orgs it owns
          AND role = :owner                                                 <- which rows to lock

    A bare `assert "role =" in sql` is a **disjunction** over both and passes when either survives,
    so it kills neither mutant. Both were verified to escape the earlier version (`#208` review):

    - **Outer predicate dropped** -> PostgreSQL locks *every member row* of each owned
      organization, which is exactly the unnecessary contention this file exists to prevent.
    - **Subquery predicate dropped** -> disabling an account that is merely a *member* of an
      organization locks that organization's owner rows, contending with an unrelated owner change.

    Asserting the *count* is what distinguishes them: two predicates must be present, not one.
    Their pairing with the account filter is asserted separately, because a count alone would pass
    on a statement that filtered the same clause twice.
    """
    sql = str(owner_memberships_for_update("acc_example").compile(dialect=postgresql.dialect()))

    assert sql.count("rca_memberships.role =") == 2, (
        "both role predicates must survive: one selecting the owned organizations, one selecting "
        "the owner rows to lock. Dropping either widens the lock silently"
    )
    subquery, outer = _split_on_subquery(sql)
    assert "rca_memberships.account_id =" in subquery, (
        "the subquery must find organizations by account"
    )
    assert "rca_memberships.role =" in subquery, (
        "the subquery must restrict to organizations this account OWNS -- without it, a mere "
        "member's disablement locks owner rows it has no authority over"
    )
    assert "rca_memberships.role =" in outer, (
        "the outer selection must lock owner rows only -- without it, every member row in every "
        "owned organization is locked"
    )
    assert " OR " not in _where_clause(sql), (
        "both clauses must stay conjunctive. A disjunction anywhere here satisfies every count and "
        "presence check above while widening the lock -- see the sibling organization-lock test"
    )


def test_promotion_issues_no_locking_statement() -> None:
    """The named example from `promote_membership`'s own docstring.

    Promotion raises the owner count, which `FR-013` never constrains, so it has no guard a
    concurrent write could invalidate. Asserted separately from the scan because this is the path a
    later reader is most likely to "fix" by adding a lock for symmetry.
    """
    modules = _rca_modules()

    assert "promote_membership" not in _methods_reaching_a_lock(*modules)


def test_reads_and_account_writes_issue_no_locking_statement() -> None:
    """The remaining surface, enumerated so a lock appearing on any of it fails by name.

    `count_owners` is the interesting entry: it reads the same rows the guard counts, but is called
    *inside* `apply_owner_reducing_change`'s transaction, where the lock is already held. Taking its
    own lock would be the second guard the stop conditions forbid.
    """
    reaching = _methods_reaching_a_lock(*_rca_modules())

    for method in (
        "add_account",
        "save_account",
        "purge_if_still_eligible",
        "accounts_disabled_before",
        "get_account",
        "get_account_by_email",
        "create_organization",
        "get_membership",
        "get_scope",
        "memberships_for_account",
        "count_owners",
    ):
        assert method not in reaching, f"{method} acquired a row lock it has no guard for"
