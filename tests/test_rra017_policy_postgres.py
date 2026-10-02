"""RRA-017 Verification 1 to 4: the policies, as the application and the worker role (`#595`).

Every covered table is exercised: `FR-230`'s eight with `owner_id`, and `FR-269`'s four walled
through their parents, whose rows are seeded beneath A's and B's parents. "Refused" means
SQLSTATE `42501` for a write the policy rejects, never `23503`: every parent the refused row names
exists when the write is attempted, so a foreign-key failure cannot stand in for the policy.

RED at `0c1475f`: the migration, its roles and its policies do not exist, so `rls_database()`
raises `Rra017Absent` before any statement runs.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.rra017_rows import Scope, before, chain, key_of, repointed, row
from tests.rra017_support import (
    COVERED_TABLES,
    INSUFFICIENT_PRIVILEGE,
    OWNER_SETTING,
    POSTGRES,
    RED,
    SCOPED_ROLES,
    RlsDatabase,
    attempt,
    insert,
    remove,
    repoint,
    rls_fixture,  # noqa: F401 -- the `rls` fixture
    scoped,
    touch,
    visible_keys,
)

pytestmark = [*POSTGRES, RED]

A = Scope("own_a", "a")
B = Scope("own_b", "b")
#: A scope whose `owner_id` is `''`: `FR-232` says an empty setting matches nothing, this included.
EMPTY = Scope("", "e")

roles = pytest.mark.parametrize("role", SCOPED_ROLES)
tables = pytest.mark.parametrize("table", COVERED_TABLES)


@roles
@tables
def test_a_unit_scoped_to_a_reads_and_writes_a_and_reads_none_of_b(
    rls: RlsDatabase, role: str, table: str
) -> None:
    """Verification 1. The positive half defeats a `USING (false)` policy."""
    rls.seed(chain(A) + chain(B))
    with rls.engine(role).begin() as connection:
        scoped(connection, A.owner_id)
        assert visible_keys(connection, table) == {key_of(A, table)}
        assert touch(connection, table) == 1


@roles
def test_a_unit_scoped_to_a_inserts_a_whole_chain_of_its_own(rls: RlsDatabase, role: str) -> None:
    """Verification 1, inserts: every table accepts a row of the unit's own scope."""
    fresh = Scope(A.owner_id, "a2")
    with rls.engine(role).begin() as connection:
        scoped(connection, A.owner_id)
        for table, values in chain(fresh):
            insert(table, values)(connection)
        assert visible_keys(connection, "rra_report_jobs") == {key_of(fresh, "rra_report_jobs")}


@roles
@tables
def test_a_row_naming_another_scope_is_refused_by_the_policy(
    rls: RlsDatabase, role: str, table: str
) -> None:
    """Verification 2. B's parents exist, so the refusal is the policy's, not a foreign key's."""
    rls.seed(chain(A) + before(B, table))
    refused = attempt(rls.engine(role), A.owner_id, insert(table, row(B, table)))
    assert refused == INSUFFICIENT_PRIVILEGE


@roles
@tables
def test_an_empty_owner_row_with_an_empty_setting_is_refused(
    rls: RlsDatabase, role: str, table: str
) -> None:
    """Verification 2. The empty owner's parents exist; no setting admits its row."""
    rls.seed(before(EMPTY, table))
    refused = attempt(rls.engine(role), None, insert(table, row(EMPTY, table)))
    assert refused == INSUFFICIENT_PRIVILEGE


@roles
@tables
def test_updates_and_deletes_scoped_to_a_reach_none_of_b(
    rls: RlsDatabase, role: str, table: str
) -> None:
    """Verification 3. "Refused" for `UPDATE` and `DELETE` is zero rows affected."""
    rls.seed(chain(A) + chain(B))
    with rls.engine(role).begin() as connection:
        scoped(connection, A.owner_id)
        assert touch(connection, table, B) == 0
        assert remove(connection, table, B) == 0
    with rls.owner.connect() as connection:
        assert key_of(B, table) in visible_keys(connection, table)


@roles
@tables
def test_repointing_a_row_of_a_at_b_is_refused(rls: RlsDatabase, role: str, table: str) -> None:
    """Verification 3. B's parent exists and B holds no row of this table to collide with."""
    rls.seed(chain(A) + before(B, table))
    refused = attempt(rls.engine(role), A.owner_id, repoint(table, A, repointed(A, B, table)))
    assert refused == INSUFFICIENT_PRIVILEGE


@roles
@tables
def test_a_pooled_connection_with_no_setting_sees_and_writes_nothing(
    rls: RlsDatabase, role: str, table: str
) -> None:
    """Verification 4, on one physical connection, with an empty-owner row present."""
    rls.seed(chain(A) + chain(EMPTY))
    engine = rls.engine(role, pool_size=1, max_overflow=0)
    with engine.connect() as connection:
        backend = connection.scalar(text("SELECT pg_backend_pid()"))
        with connection.begin():
            scoped(connection, A.owner_id)
            assert visible_keys(connection, table) == {key_of(A, table)}
        assert connection.scalar(text("SELECT pg_backend_pid()")) == backend
        with connection.begin():
            # The pooled-connection case `FR-232` names: the missing setting reads as `''`.
            assert connection.scalar(text(f"SELECT current_setting('{OWNER_SETTING}', true)")) == ""
            assert visible_keys(connection, table) == set()
            assert touch(connection, table) == 0
            assert remove(connection, table) == 0
    fresh = Scope("", "e2")
    rls.seed(before(fresh, table))
    assert attempt(engine, None, insert(table, row(fresh, table))) == INSUFFICIENT_PRIVILEGE
