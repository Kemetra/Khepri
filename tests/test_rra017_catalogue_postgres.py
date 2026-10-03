"""RRA-017 Verification 6 and 14, and the grant matrix, read from the migrated catalogue (`#595`).

The covered tables are derived from the catalogue (`FR-230`: every `rra_` table with an
`owner_id` column) and joined with `FR-269`'s four, so a table a later migration adds is covered
or fails here. The grant test is the rule that keeps later migrations covered: every table is
derived from the catalogue, and each runtime role must hold exactly the privileges its row of the
matrix names. A table whose migration granted nothing fails it.

Pinned RED at `f1639c1`, before `20261002_0036` existed; green from that revision.
"""

from __future__ import annotations

import pytest

from tests.rra017_support import (
    APPLICATION,
    DEFINER,
    PARENT_WALLED,
    POSTGRES,
    RUNTIME_ROLES,
    SCOPED_ROLES,
    SWEEP,
    WORKER,
    RlsDatabase,
    rls_fixture,  # noqa: F401 -- the `rls` fixture
)

pytestmark = list(POSTGRES)

DML = frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"})
TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
SCOPE_POLICIES = frozenset({"rra_owner_scope", "rra_parent_scope"})

#: `FR-264`: each definer function, and the roles holding `EXECUTE` on it.
DEFINER_FUNCTIONS = {
    "rra_session_owner": frozenset({APPLICATION, WORKER}),
    "rra_next_claimable_job": frozenset({WORKER}),
    "rra_expired_lease_jobs": frozenset({WORKER, SWEEP}),
    "rra_orphaned_jobs": frozenset({WORKER, SWEEP}),
}
SEARCH_PATH = ["search_path=public, pg_catalog, pg_temp"]

#: `FR-271`'s column grants to the sweep role, with the `_due` read of the RCA table.
SWEEP_COLUMNS = frozenset(
    {
        ("rra_beta_sessions", "session_id", "SELECT"),
        ("rra_beta_sessions", "owner_id", "SELECT"),
        ("rra_beta_sessions", "content_expires_at", "SELECT"),
        ("rra_beta_sessions", "content_deleted_at", "SELECT"),
        ("rra_uploads", "upload_id", "SELECT"),
        ("rra_uploads", "owner_id", "SELECT"),
        ("rra_uploads", "session_id", "SELECT"),
        ("rra_uploads", "object_key", "SELECT"),
        ("rra_uploads", "ciphertext_sha256_hex", "SELECT"),
        ("rra_deletion_evidence", "attempted_at", "SELECT"),
        ("rca_workspace_dataset_versions", "owner_id", "SELECT"),
        ("rca_workspace_dataset_versions", "upload_ciphertext_digest", "SELECT"),
        ("rca_workspace_dataset_versions", "sealed_at", "SELECT"),
    }
)
#: `FR-264` and `FR-267`'s column grants to the definer role.
DEFINER_COLUMNS = frozenset(
    {
        ("rra_beta_sessions", column, "SELECT")
        for column in (
            "session_id",
            "owner_id",
            "deletion_requested_at",
            "content_deleted_at",
        )
    }
    | {
        ("rra_report_jobs", column, "SELECT")
        for column in (
            "job_id",
            "owner_id",
            "session_id",
            "state",
            "available_at",
            "attempt_count",
            "max_attempts",
            "lease_expires_at",
            "queued_at",
        )
    }
)

_COLUMN_GRANTS = """
SELECT c.relname, a.attname, x.privilege_type
FROM pg_attribute AS a
JOIN pg_class AS c ON c.oid = a.attrelid
JOIN pg_namespace AS n ON n.oid = c.relnamespace AND n.nspname = 'public'
CROSS JOIN LATERAL aclexplode(a.attacl) AS x
WHERE x.grantee = to_regrole(:role)
"""


def _covered(rls: RlsDatabase) -> set[str]:
    rows = rls.as_owner(
        "SELECT table_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND column_name = 'owner_id' AND table_name LIKE 'rra\\_%'"
    )
    return {name for (name,) in rows} | set(PARENT_WALLED)


def _public_tables(rls: RlsDatabase) -> list[str]:
    rows = rls.as_owner(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
        "AND tablename <> 'alembic_version' ORDER BY 1"
    )
    return [name for (name,) in rows]


def _held(rls: RlsDatabase, role: str, table: str) -> set[str]:
    return {
        privilege
        for privilege in TABLE_PRIVILEGES
        if rls.as_owner(
            "SELECT has_table_privilege(:role, :table, :privilege)",
            role=role,
            table=f"public.{table}",
            privilege=privilege,
        )[0][0]
    }


def test_every_covered_table_enables_and_forces_row_security(rls: RlsDatabase) -> None:
    """`FR-230` and `FR-269`: the property, from the catalogue, plus the four."""
    forced = rls.as_owner(
        "SELECT relname FROM pg_class WHERE relkind = 'r' AND relname LIKE 'rra\\_%' "
        "AND relrowsecurity AND relforcerowsecurity"
    )
    assert {name for (name,) in forced} == _covered(rls)


def test_every_covered_table_has_its_scope_policy_for_both_scoped_roles(rls: RlsDatabase) -> None:
    rows = rls.as_owner(
        "SELECT tablename FROM pg_policies WHERE schemaname = 'public' "
        "AND policyname IN ('rra_owner_scope', 'rra_parent_scope') AND cmd = 'ALL' "
        "AND roles @> ARRAY[:app, :worker]::name[] AND qual IS NOT NULL "
        "AND with_check IS NOT NULL",
        app=APPLICATION,
        worker=WORKER,
    )
    assert {name for (name,) in rows} == _covered(rls)


def test_no_policy_but_the_scope_policies_applies_to_a_scoped_role(rls: RlsDatabase) -> None:
    """`FR-270`: no policy that admits rows across scopes reaches the application or the worker."""
    rows = rls.as_owner(
        "SELECT DISTINCT policyname FROM pg_policies "
        "WHERE roles && ARRAY[:app, :worker]::name[] OR 'public' = ANY(roles)",
        app=APPLICATION,
        worker=WORKER,
    )
    assert {name for (name,) in rows} == SCOPE_POLICIES


@pytest.mark.parametrize("role", RUNTIME_ROLES)
def test_a_runtime_role_logs_in_and_holds_no_ddl_or_bypass_attribute(
    rls: RlsDatabase, role: str
) -> None:
    """`FR-234`, for each of the three runtime roles."""
    attributes = rls.as_owner(
        "SELECT rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb "
        "FROM pg_roles WHERE rolname = :role",
        role=role,
    )
    assert [tuple(found) for found in attributes] == [(True, False, False, False, False)]


@pytest.mark.parametrize("role", RUNTIME_ROLES)
def test_a_runtime_role_owns_nothing(rls: RlsDatabase, role: str) -> None:
    owned = rls.as_owner(
        "SELECT (SELECT count(*) FROM pg_class WHERE relowner = to_regrole(:r))"
        " + (SELECT count(*) FROM pg_proc WHERE proowner = to_regrole(:r))"
        " + (SELECT count(*) FROM pg_namespace WHERE nspowner = to_regrole(:r))"
        " + (SELECT count(*) FROM pg_type WHERE typowner = to_regrole(:r))"
        " + (SELECT count(*) FROM pg_database WHERE datdba = to_regrole(:r))",
        r=role,
    )
    assert owned[0][0] == 0


@pytest.mark.parametrize("role", RUNTIME_ROLES)
def test_a_runtime_role_may_create_in_no_database_and_no_schema(
    rls: RlsDatabase, role: str
) -> None:
    """`FR-234`. `TEMPORARY` is not `CREATE`: Verification 14's shadowing test needs it."""
    database = rls.as_owner(
        "SELECT has_database_privilege(:role, current_database(), 'CREATE')", role=role
    )
    schemas = rls.as_owner(
        "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg\\_temp\\_%' "
        "AND nspname NOT LIKE 'pg\\_toast\\_temp\\_%' "
        "AND has_schema_privilege(:role, nspname, 'CREATE')",
        role=role,
    )
    assert (database[0][0], schemas) == (False, [])


def test_the_definer_cannot_log_in_and_only_the_migration_owner_bypasses(
    rls: RlsDatabase,
) -> None:
    """Verification 6. The migration owner is the role that owns the tables."""
    owner = rls.as_owner("SELECT tableowner FROM pg_tables WHERE tablename = 'rra_beta_sessions'")
    five = (*RUNTIME_ROLES, DEFINER, owner[0][0])
    rows = rls.as_owner(
        "SELECT rolname, rolcanlogin, rolbypassrls FROM pg_roles WHERE rolname = ANY(:five)",
        five=list(five),
    )
    found = {name: (login, bypass) for name, login, bypass in rows}
    assert found[DEFINER] == (False, False)
    assert {name for name, (_login, bypass) in found.items() if bypass} == {owner[0][0]}


def test_no_runtime_role_is_a_member_of_another_of_the_five(rls: RlsDatabase) -> None:
    """Verification 6, from `pg_auth_members`: no runtime role inherits another's policy."""
    owner = rls.as_owner("SELECT tableowner FROM pg_tables WHERE tablename = 'rra_beta_sessions'")
    rows = rls.as_owner(
        "SELECT member::regrole::text, roleid::regrole::text FROM pg_auth_members "
        "WHERE member::regrole::text = ANY(:runtime) OR roleid::regrole::text = ANY(:granted)",
        runtime=list(RUNTIME_ROLES),
        granted=[*RUNTIME_ROLES, DEFINER, owner[0][0]],
    )
    assert rows == []


def test_every_table_grants_each_scoped_role_exactly_dml(rls: RlsDatabase) -> None:
    """The future-migration rule: each table, derived from the catalogue, grants its own."""
    for table in _public_tables(rls):
        for role in SCOPED_ROLES:
            assert _held(rls, role, table) == DML, (table, role)


def test_no_runtime_role_reaches_the_migration_bookkeeping(rls: RlsDatabase) -> None:
    for role in (*RUNTIME_ROLES, DEFINER):
        assert _held(rls, role, "alembic_version") == set(), role


def test_the_sweep_holds_only_its_columns_and_the_evidence_delete(rls: RlsDatabase) -> None:
    """`FR-271`: column-level `SELECT`, one table-level `DELETE`, nothing else."""
    columns = {tuple(found) for found in rls.as_owner(_COLUMN_GRANTS, role=SWEEP)}
    tables = {
        (table, privilege)
        for table in _public_tables(rls)
        for privilege in _held(rls, SWEEP, table)
    }
    assert (columns, tables) == (SWEEP_COLUMNS, {("rra_deletion_evidence", "DELETE")})


def test_the_definer_holds_only_the_columns_its_bodies_read(rls: RlsDatabase) -> None:
    """Verification 14: `FR-265` and `FR-267`'s column lists, and no table-level privilege."""
    columns = {tuple(found) for found in rls.as_owner(_COLUMN_GRANTS, role=DEFINER)}
    tables = [table for table in _public_tables(rls) if _held(rls, DEFINER, table)]
    assert (columns, tables) == (DEFINER_COLUMNS, [])


def test_no_default_privilege_is_left_for_any_runtime_role(rls: RlsDatabase) -> None:
    """The rule is per-migration grants, not `ALTER DEFAULT PRIVILEGES` (fail-open on a new
    table before its policy exists)."""
    rows = rls.as_owner(
        "SELECT count(*) FROM pg_default_acl AS d CROSS JOIN LATERAL aclexplode(d.defaclacl) AS x "
        "WHERE x.grantee::regrole::text = ANY(:roles)",
        roles=[*RUNTIME_ROLES, DEFINER],
    )
    assert rows[0][0] == 0


def test_exactly_four_definer_functions_exist_each_owned_by_the_definer_and_stable(
    rls: RlsDatabase,
) -> None:
    """Verification 14. No other `SECURITY DEFINER` function exists in the schema at all."""
    rows = rls.as_owner(
        "SELECT p.proname, pg_get_userbyid(p.proowner), p.provolatile FROM pg_proc AS p "
        "JOIN pg_namespace AS n ON n.oid = p.pronamespace "
        "WHERE p.prosecdef AND n.nspname = 'public'"
    )
    assert {tuple(found) for found in rows} == {(name, DEFINER, "s") for name in DEFINER_FUNCTIONS}


def test_each_definer_function_pins_its_search_path_ending_in_pg_temp(rls: RlsDatabase) -> None:
    rows = rls.as_owner(
        "SELECT proname, proconfig FROM pg_proc WHERE proname = ANY(:names)",
        names=list(DEFINER_FUNCTIONS),
    )
    assert {name: config for name, config in rows} == dict.fromkeys(DEFINER_FUNCTIONS, SEARCH_PATH)


def test_each_definer_function_is_executable_by_exactly_its_named_roles(rls: RlsDatabase) -> None:
    """`PUBLIC` (grantee 0) holds `EXECUTE` on none of them."""
    for name, holders in DEFINER_FUNCTIONS.items():
        rows = rls.as_owner(
            "SELECT CASE WHEN x.grantee = 0 THEN 'PUBLIC' ELSE x.grantee::regrole::text END "
            "FROM pg_proc AS p CROSS JOIN LATERAL aclexplode(p.proacl) AS x "
            "WHERE p.proname = :name AND x.privilege_type = 'EXECUTE' "
            "AND x.grantee <> p.proowner",
            name=name,
        )
        assert {grantee for (grantee,) in rows} == holders, name


def test_the_lookup_returns_a_scalar_and_each_picker_two_columns(rls: RlsDatabase) -> None:
    rows = rls.as_owner(
        "SELECT proname, proretset, pg_get_function_result(oid) FROM pg_proc "
        "WHERE proname = ANY(:names)",
        names=list(DEFINER_FUNCTIONS),
    )
    pickers = "TABLE(job_id text, owner_id text)"
    assert {name: (setof, result) for name, setof, result in rows} == {
        "rra_session_owner": (False, "text"),
        "rra_next_claimable_job": (True, pickers),
        "rra_expired_lease_jobs": (True, pickers),
        "rra_orphaned_jobs": (True, pickers),
    }


def test_the_definer_holds_only_its_two_select_policies(rls: RlsDatabase) -> None:
    rows = rls.as_owner(
        "SELECT tablename, policyname, cmd, permissive FROM pg_policies "
        "WHERE :definer = ANY(roles)",
        definer=DEFINER,
    )
    assert {tuple(found) for found in rows} == {
        ("rra_beta_sessions", "rra_definer_read", "SELECT", "PERMISSIVE"),
        ("rra_report_jobs", "rra_definer_read", "SELECT", "PERMISSIVE"),
    }


def test_the_sweep_holds_only_its_permissive_read_and_purge_policies(rls: RlsDatabase) -> None:
    rows = rls.as_owner(
        "SELECT tablename, policyname, cmd FROM pg_policies WHERE :sweep = ANY(roles)",
        sweep=SWEEP,
    )
    assert {tuple(found) for found in rows} == {
        ("rra_beta_sessions", "rra_sweep_read", "SELECT"),
        ("rra_uploads", "rra_sweep_read", "SELECT"),
        ("rra_deletion_evidence", "rra_sweep_read", "SELECT"),
        ("rra_deletion_evidence", "rra_sweep_purge", "DELETE"),
    }
