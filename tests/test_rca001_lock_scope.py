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

1. **Statically**, over the source: exactly two methods may reach a locking statement, named here.
   A third one appearing fails the test rather than passing unnoticed.
2. **By compilation**, for the statements the lock-free paths actually issue.

The static half is what makes this durable. A test that only compiled today's statements would say
nothing about a lock added tomorrow to a method this file never thought to name.
"""

from __future__ import annotations

import ast
import pathlib

from sqlalchemy.dialects import postgresql

from khepri.rca.persistence import (
    organization_owners_for_update,
    owner_memberships_for_update,
)

_PERSISTENCE = pathlib.Path("src/khepri/rca/persistence.py")

#: The two module-level statements that carry `FOR UPDATE`, plus the raw SQLAlchemy call, so a
#: method reaching for the lock by any of the three routes is caught.
_LOCK_ROUTES = frozenset({"owner_memberships_for_update", "organization_owners_for_update"})
_LOCK_CALL = "with_for_update"

#: The only methods permitted to lock, each with the guard that justifies it.
#:
#: `apply_owner_reducing_change` counts effective owners and then writes, so a concurrent write can
#: invalidate the count between the two. `_apply_membership_change` is the shared boundary behind
#: `revoke_membership` and `demote_membership`, both of which can remove an organization's final
#: owner. Every other write either raises the owner count or cannot change it.
#:
#: Adding a name here is the review conversation this allowlist exists to force, in the same spirit
#: as `R6-08`'s `VERB_CALLER_ALLOWLIST`. It is not a list to extend for convenience.
_MAY_LOCK = frozenset({"apply_owner_reducing_change", "_apply_membership_change"})


def _methods_reaching_a_lock(source: str) -> set[str]:
    """Every method in `source` whose body can reach a locking statement.

    Walks each function body for a reference to one of the named locking statements or a direct
    `.with_for_update()` call. Deliberately *not* transitive: a method that locks by calling a
    helper that locks is a different shape, and `_apply_membership_change` -- the one such helper --
    is named in `_MAY_LOCK` in its own right, so its callers are correctly reported as lock-free.
    """
    reaching: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef):
            continue
        names = {inner.id for inner in ast.walk(node) if isinstance(inner, ast.Name)}
        attributes = {inner.attr for inner in ast.walk(node) if isinstance(inner, ast.Attribute)}
        if names & _LOCK_ROUTES or _LOCK_CALL in attributes:
            reaching.add(node.name)
    return reaching


def test_only_the_two_owner_reducing_writes_reach_a_lock() -> None:
    """The load-bearing assertion. A new locking path fails here before it can add contention.

    Mutation-checked: adding `owner_memberships_for_update` to `promote_membership` fails this
    test, and removing `_apply_membership_change` from `_MAY_LOCK` fails it too -- so the
    allowlist cannot be quietly widened without the diff showing it.
    """
    reaching = _methods_reaching_a_lock(_PERSISTENCE.read_text(encoding="utf-8"))

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
    reaching = _methods_reaching_a_lock(_PERSISTENCE.read_text(encoding="utf-8"))

    assert "apply_owner_reducing_change" in reaching, "the scanner found no lock at all"
    assert "_apply_membership_change" in reaching

    planted = _methods_reaching_a_lock(
        "def innocent():\n"
        "    return 1\n"
        "def guilty():\n"
        "    return owner_memberships_for_update('acc_x')\n"
        "def also_guilty():\n"
        "    return select(Row).with_for_update()\n"
    )
    assert planted == {"guilty", "also_guilty"}


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
    """"Leave unrelated organizations independent" (`R1` design requirements).

    `organization_owners_for_update` locks by organization, so two organizations' owner-reducing
    operations do not contend. A statement that dropped the predicate would serialize every
    organization in the table against every other -- correct, and unusably slow.
    """
    sql = str(organization_owners_for_update("org_example").compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in sql
    assert "rca_memberships.organization_id =" in sql, "the lock must be scoped to one organization"
    assert "rca_memberships.role =" in sql, "only owner rows are locked, not every membership"


def test_the_account_lock_is_scoped_to_one_account() -> None:
    """The sibling scope claim. The disable path locks by *account*, because one disablement can
    reduce owners in every organization that account owns -- so its scope is that account's owner
    rows, not one organization's."""
    sql = str(owner_memberships_for_update("acc_example").compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in sql
    assert "rca_memberships.account_id =" in sql, "the lock must be scoped to one account"
    assert "rca_memberships.role =" in sql, "only owner rows are locked, not every membership"


def test_promotion_issues_no_locking_statement() -> None:
    """The named example from `promote_membership`'s own docstring.

    Promotion raises the owner count, which `FR-013` never constrains, so it has no guard a
    concurrent write could invalidate. Asserted separately from the scan because this is the path a
    later reader is most likely to "fix" by adding a lock for symmetry.
    """
    source = _PERSISTENCE.read_text(encoding="utf-8")

    assert "promote_membership" not in _methods_reaching_a_lock(source)


def test_reads_and_account_writes_issue_no_locking_statement() -> None:
    """The remaining surface, enumerated so a lock appearing on any of it fails by name.

    `count_owners` is the interesting entry: it reads the same rows the guard counts, but is called
    *inside* `apply_owner_reducing_change`'s transaction, where the lock is already held. Taking its
    own lock would be the second guard the stop conditions forbid.
    """
    reaching = _methods_reaching_a_lock(_PERSISTENCE.read_text(encoding="utf-8"))

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
