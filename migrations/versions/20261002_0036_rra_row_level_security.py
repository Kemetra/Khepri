"""Row-level security beneath the RRA scope (RRA-017, #595).

`KHEPRI-DEC-035` §1 makes PostgreSQL row-level security the only admissible anchor for the RRA
scope, and `RRA-017` states what it covers. This revision creates, on PostgreSQL only:

- **Four roles** (`FR-270`): `khepri_app`, `khepri_worker` and `khepri_sweep` log in;
  `khepri_definer` does not. None is a superuser, bypasses row security, or may create roles or
  databases. Roles are cluster-wide, so each is created only if it does not exist, and an existing
  one is checked, not altered: changing `SUPERUSER` or `BYPASSRLS` needs a superuser, which the
  migration owner need not be. No password is set here. The migration owner is whichever role
  runs this revision, and it is the role that owns the tables.
- **The policies.** Every `rra_` table with `owner_id` (`FR-230`) and the four scope-owned tables
  without one (`FR-269`) have row security enabled and forced. `rra_owner_scope` compares
  `owner_id` with `NULLIF(current_setting('khepri.owner_id', true), '')`: the `NULLIF` is what
  makes an unset setting on a pooled connection, which reads back as `''`, match nothing, a row
  whose `owner_id` is `''` included (`FR-232`). `rra_parent_scope` is an `EXISTS` over the parent,
  which the parent's own policy filters. The definer and the sweep cross the policies only
  through permissive `SELECT`/`DELETE` policies granted to them alone (`FR-264`, `FR-271`).
- **The four definer functions** (`FR-264`, `FR-265`, `FR-267`), owned by `khepri_definer`, each
  `STABLE`, schema-qualified, with its `search_path` pinned and `pg_temp` last.
- **The grants** (`FR-234`, `FR-270`, `FR-271`). Each later migration grants its own new tables;
  there are deliberately no default privileges, which would grant DML on a table before its
  policy exists.

Every name is spelled literally rather than imported, so a later edit to the model cannot rewrite
what this revision did. The downgrade drops the policies, the functions and the grants, and never
drops a role: parallel databases on one cluster share them.

The migration head is pinned in three places and this revision moves all of them:
`tests/test_rca001_migration.py` `RCA_UNREPLAYED`,
`tests/test_rca001_session_persistence.py`'s `alembic heads` assertion, and
`specs/001-rca-001-commercial-identity/STATUS.md`.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261002_0036"
down_revision: str | None = "20261002_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP = "khepri_app"
WORKER = "khepri_worker"
SWEEP = "khepri_sweep"
DEFINER = "khepri_definer"
LOGIN_ROLES = (APP, WORKER, SWEEP)
SCOPED = f"{APP}, {WORKER}"

OWNER_TABLES = (
    "rra_beta_sessions",
    "rra_dataset_profiles",
    "rra_deletion_jobs",
    "rra_fact_packages",
    "rra_report_artifacts",
    "rra_report_deliveries",
    "rra_report_jobs",
    "rra_uploads",
)
#: `FR-269`: each scope-owned table without `owner_id`, its parent, and the key it names it by.
PARENT_WALLED = {
    "rra_report_job_attempts": ("rra_report_jobs", ("job_id", "session_id")),
    "rra_operational_events": ("rra_report_jobs", ("job_id", "session_id")),
    "rra_report_delivery_surfaces": ("rra_report_deliveries", ("job_id", "bundle_id")),
    "rra_deletion_evidence": ("rra_deletion_jobs", ("deletion_id",)),
}
COVERED = (*OWNER_TABLES, *PARENT_WALLED)

SCOPE = "owner_id = NULLIF(current_setting('khepri.owner_id', true), '')"
SEARCH_PATH = "SET search_path = public, pg_catalog, pg_temp"

#: `FR-271`: the sweep role's column grants.
SWEEP_COLUMNS = {
    "rra_beta_sessions": ("session_id", "owner_id", "content_expires_at", "content_deleted_at"),
    "rra_uploads": ("upload_id", "owner_id", "session_id", "object_key", "ciphertext_sha256_hex"),
    "rra_deletion_evidence": ("attempted_at",),
    "rca_workspace_dataset_versions": ("owner_id", "upload_ciphertext_digest", "sealed_at"),
}
#: `FR-265` and `FR-267`: exactly the columns the four bodies read.
DEFINER_COLUMNS = {
    "rra_beta_sessions": ("session_id", "owner_id", "deletion_requested_at", "content_deleted_at"),
    "rra_report_jobs": (
        "job_id",
        "owner_id",
        "session_id",
        "state",
        "available_at",
        "attempt_count",
        "max_attempts",
        "lease_expires_at",
        "queued_at",
    ),
}

_LIVE_SESSIONS = (
    "SELECT s.session_id FROM public.rra_beta_sessions AS s "
    "WHERE s.deletion_requested_at IS NULL AND s.content_deleted_at IS NULL"
)
_DELETED_SESSIONS = (
    "SELECT s.session_id FROM public.rra_beta_sessions AS s WHERE s.content_deleted_at IS NOT NULL"
)
_PICKED = "SELECT j.job_id::text, j.owner_id::text FROM public.rra_report_jobs AS j WHERE "
_PICKER = "RETURNS TABLE (job_id text, owner_id text)"

#: Each function: its signature, return clause, body, and the roles holding `EXECUTE`.
FUNCTIONS = {
    "rra_session_owner(p_session_id text)": (
        "RETURNS text",
        "SELECT s.owner_id::text FROM public.rra_beta_sessions AS s "
        "WHERE p_session_id <> '' AND s.session_id = p_session_id",
        (APP, WORKER),
    ),
    "rra_next_claimable_job(p_now timestamptz)": (
        _PICKER,
        _PICKED + "j.state IN ('queued', 'retryable') AND j.available_at <= p_now "
        "AND j.attempt_count < j.max_attempts "
        f"AND j.session_id IN ({_LIVE_SESSIONS}) ORDER BY j.available_at, j.job_id LIMIT 1",
        (WORKER,),
    ),
    "rra_expired_lease_jobs(p_now timestamptz)": (
        _PICKER,
        _PICKED + "j.state = 'running' AND j.lease_expires_at <= p_now "
        "ORDER BY j.lease_expires_at, j.job_id",
        (WORKER, SWEEP),
    ),
    # `p_now` is the signature `FR-267` names; the predicate it mirrors has no time clause.
    "rra_orphaned_jobs(p_now timestamptz)": (
        _PICKER,
        _PICKED + f"j.session_id IN ({_DELETED_SESSIONS}) "
        "AND j.state NOT IN ('succeeded', 'dead_lettered') ORDER BY j.queued_at, j.job_id",
        (WORKER, SWEEP),
    ),
}

_CREATE_ROLE = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
    CREATE ROLE {role} {login} NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB NOINHERIT;
  END IF;
END $$
"""
_CHECK_ROLES = f"""
DO $$ BEGIN
  IF EXISTS (
    SELECT FROM pg_roles WHERE rolname IN ('{APP}', '{WORKER}', '{SWEEP}', '{DEFINER}')
    AND (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb)
  ) OR EXISTS (SELECT FROM pg_roles WHERE rolname = '{DEFINER}' AND rolcanlogin)
  THEN
    RAISE EXCEPTION 'an RRA-017 role exists with an attribute FR-234 forbids';
  END IF;
END $$
"""
_CONNECT = f"""
DO $$ BEGIN
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO {APP}, {WORKER}, {SWEEP}', current_database());
END $$
"""
_REVOKE_CONNECT = f"""
DO $$ BEGIN
  EXECUTE format(
    'REVOKE CONNECT ON DATABASE %I FROM {APP}, {WORKER}, {SWEEP}', current_database()
  );
END $$
"""
#: A non-superuser runner may give a function to the definer only as a member of it (`FR-264`).
_JOIN_DEFINER = f"""
DO $$ BEGIN
  IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
    EXECUTE format('GRANT {DEFINER} TO %I', current_user);
  END IF;
END $$
"""
_LEAVE_DEFINER = f"""
DO $$ BEGIN
  IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user) THEN
    EXECUTE format('REVOKE {DEFINER} FROM %I', current_user);
  END IF;
END $$
"""


def _on_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _run(*statements: str) -> None:
    for statement in statements:
        op.execute(statement)


def _create_roles() -> None:
    for role in LOGIN_ROLES:
        _run(_CREATE_ROLE.format(role=role, login="LOGIN"))
    _run(_CREATE_ROLE.format(role=DEFINER, login="NOLOGIN"), _CHECK_ROLES)


def _parent_policy(table: str) -> str:
    parent, key = PARENT_WALLED[table]
    joined = " AND ".join(f"p.{column} = {table}.{column}" for column in key)
    exists = f"EXISTS (SELECT 1 FROM public.{parent} AS p WHERE {joined})"
    return (
        f"CREATE POLICY rra_parent_scope ON public.{table} AS PERMISSIVE FOR ALL "
        f"TO {SCOPED} USING ({exists}) WITH CHECK ({exists})"
    )


def _enable_policies() -> None:
    for table in COVERED:
        _run(
            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY",
        )
    for table in OWNER_TABLES:
        _run(
            f"CREATE POLICY rra_owner_scope ON public.{table} AS PERMISSIVE FOR ALL "
            f"TO {SCOPED} USING ({SCOPE}) WITH CHECK ({SCOPE})"
        )
    _run(*(_parent_policy(table) for table in PARENT_WALLED))
    for table in DEFINER_COLUMNS:
        _run(
            f"CREATE POLICY rra_definer_read ON public.{table} AS PERMISSIVE FOR SELECT "
            f"TO {DEFINER} USING (true)"
        )
    for table in ("rra_beta_sessions", "rra_uploads", "rra_deletion_evidence"):
        _run(
            f"CREATE POLICY rra_sweep_read ON public.{table} AS PERMISSIVE FOR SELECT "
            f"TO {SWEEP} USING (true)"
        )
    _run(
        "CREATE POLICY rra_sweep_purge ON public.rra_deletion_evidence AS PERMISSIVE "
        f"FOR DELETE TO {SWEEP} USING (true)"
    )


def _column_grants(role: str, columns: dict[str, tuple[str, ...]]) -> None:
    for table, names in columns.items():
        _run(f"GRANT SELECT ({', '.join(names)}) ON public.{table} TO {role}")


def _grant_tables() -> None:
    _run(
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        f"GRANT USAGE ON SCHEMA public TO {APP}, {WORKER}, {SWEEP}, {DEFINER}",
        _CONNECT,
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {SCOPED}",
        f"REVOKE ALL ON TABLE public.alembic_version FROM {SCOPED}",
        f"GRANT DELETE ON public.rra_deletion_evidence TO {SWEEP}",
    )
    _column_grants(SWEEP, SWEEP_COLUMNS)
    _column_grants(DEFINER, DEFINER_COLUMNS)


def _create_functions() -> None:
    for signature, (returns, body, holders) in FUNCTIONS.items():
        _run(
            f"CREATE FUNCTION public.{signature} {returns} LANGUAGE sql STABLE "
            f"SECURITY DEFINER {SEARCH_PATH} AS $body$ {body} $body$",
            f"REVOKE EXECUTE ON FUNCTION public.{_name(signature)} FROM PUBLIC",
            f"GRANT EXECUTE ON FUNCTION public.{_name(signature)} TO {', '.join(holders)}",
        )
    _run(f"GRANT CREATE ON SCHEMA public TO {DEFINER}", _JOIN_DEFINER)
    for signature in FUNCTIONS:
        _run(f"ALTER FUNCTION public.{_name(signature)} OWNER TO {DEFINER}")
    _run(_LEAVE_DEFINER, f"REVOKE CREATE ON SCHEMA public FROM {DEFINER}")


def _name(signature: str) -> str:
    """`rra_session_owner(p_session_id text)` -> `rra_session_owner(text)`."""
    name, arguments = signature.rstrip(")").split("(")
    return f"{name}({arguments.split()[-1]})"


def upgrade() -> None:
    if not _on_postgres():
        return
    _create_roles()
    _grant_tables()
    _create_functions()
    _enable_policies()


def _drop_policies() -> None:
    names = ("rra_owner_scope", "rra_parent_scope", "rra_definer_read", "rra_sweep_read")
    for table in COVERED:
        _run(*(f"DROP POLICY IF EXISTS {name} ON public.{table}" for name in names))
        _run(
            f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY",
            f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY",
        )
    _run("DROP POLICY IF EXISTS rra_sweep_purge ON public.rra_deletion_evidence")


def downgrade() -> None:
    if not _on_postgres():
        return
    _drop_policies()
    _run(*(f"DROP FUNCTION IF EXISTS public.{_name(s)}" for s in FUNCTIONS))
    every = f"{APP}, {WORKER}, {SWEEP}, {DEFINER}"
    _run(
        f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {every}",
        f"REVOKE USAGE ON SCHEMA public FROM {every}",
        _REVOKE_CONNECT,
    )
