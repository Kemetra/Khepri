"""RRA-017's PostgreSQL harness: the migrated schema, the runtime roles, the role guard (`#595`).

**A superuser run passes without testing anything.** CI's `khepri` user, and the throwaway
cluster's, is a superuser, and a superuser bypasses row-level security even under `FORCE`. So
every engine this module hands a test is a *guarded* engine: each new physical connection asserts
`current_user` and `session_user` are both the intended role and that the role is neither a
superuser nor `BYPASSRLS`, and raises `HarnessError` otherwise. `session_user` is checked too, so
a `SET ROLE` shortcut on a superuser connection cannot pass for the role.
`test_rra017_harness_postgres.py` proves the guard refuses a superuser and a `SET ROLE`.

**Three failures, kept apart**, so a strict `xfail` pinning RRA-017's absence cannot absorb the
others:

- `Rra017Absent` when the slice is not implemented: its migration, a role it creates, or an API it
  adds is missing. The only failure the RED tests' `xfail(raises=...)` names for a PostgreSQL test.
- `Rra017Gap` when a code-inspection property RRA-017 requires does not hold yet. Named, with
  `Rra017Absent`, by the RED tests that read the code rather than the database.
- `HarnessError` (from `#388`'s harness) when the instrument failed: a guard tripped, a database
  not named as a test database. Never an `AssertionError`, so no RED test can absorb it.

**Roles are cluster-wide; grants are per database.** The migration creates the roles if they do
not exist, with no password. This harness sets a fixed test-only password on each before it
connects (CI authenticates with scram, so a fixture that forgot would fail there even where a
trust-auth cluster lets it through), and never drops a role: parallel test databases on one
cluster share them.

**The schema is migrated once and emptied per test.** `alembic upgrade head` costs seconds, so the
harness migrates only when the database is not at head (the `#388` harness drops `public` between
its own tests) and otherwise truncates every table but `alembic_version`.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, Table, create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from tests.rra017_rows import PRIMARY_KEYS, TOUCH_COLUMNS, Row, Scope, key_of
from tests.w110_postgres_support import (
    DATABASE_URL,
    TEST_DATABASE_NAME,
    HarnessError,
    _empty_public_schema,
    requires_postgres,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The revision RRA-017's migration takes. Its `down_revision` is `20261002_0035`.
RRA017_REVISION = "20261002_0036"
#: The transaction-local setting every policy compares `owner_id` with.
OWNER_SETTING = "khepri.owner_id"

APPLICATION = "khepri_app"
WORKER = "khepri_worker"
SWEEP = "khepri_sweep"
DEFINER = "khepri_definer"
RUNTIME_ROLES = (APPLICATION, WORKER, SWEEP)
#: The two roles `FR-232` and `FR-269` apply to.
SCOPED_ROLES = (APPLICATION, WORKER)
ROLE_PASSWORD = "rra017-test-only"

INSUFFICIENT_PRIVILEGE = "42501"
FOREIGN_KEY_VIOLATION = "23503"

#: `FR-230`: the tables that carry `owner_id`.
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
#: `FR-269`: the scope-owned tables without `owner_id`, walled through their parents.
PARENT_WALLED = (
    "rra_deletion_evidence",
    "rra_operational_events",
    "rra_report_delivery_surfaces",
    "rra_report_job_attempts",
)
COVERED_TABLES = OWNER_TABLES + PARENT_WALLED
#: `FR-231`: pre-scope, and carries no policy.
PRE_SCOPE_TABLES = ("rra_invitations",)

RED_REASON = "RRA-017 (#595) is not implemented at 0c1475f: phase 2 makes this pass"


class Rra017Absent(AssertionError):
    """RRA-017's migration, a role it creates, or an API it adds does not exist on this tree."""


class Rra017Gap(AssertionError):
    """A code-inspection property RRA-017 requires does not hold on this tree."""


#: A test RED because the slice is absent. Only `Rra017Absent` is expected.
RED = pytest.mark.xfail(raises=Rra017Absent, strict=True, reason=RED_REASON)
#: A code-inspection test RED because the slice is absent or its property does not hold yet.
RED_STATIC = pytest.mark.xfail(raises=(Rra017Absent, Rra017Gap), strict=True, reason=RED_REASON)
POSTGRES = (pytest.mark.concurrency, requires_postgres)


def require(condition: bool, message: str) -> None:
    """Raise `Rra017Gap` unless `condition` holds."""
    if not condition:
        raise Rra017Gap(message)


def future(module: str, name: str) -> Any:
    """An API RRA-017 adds, or `Rra017Absent` while it does not exist."""
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError) as error:
        raise Rra017Absent(f"{module}.{name} does not exist yet") from error


def rra_tables() -> dict[str, Table]:
    """Every `khepri.rra` table, after importing every module under the package (`FR-230`)."""
    import khepri.rra as rra
    from khepri.rra.persistence import Base

    for module in pkgutil.walk_packages(rra.__path__, "khepri.rra."):
        importlib.import_module(module.name)
    return dict(Base.metadata.tables)


# -- the schema ------------------------------------------------------------------------------


def alembic_config() -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", DATABASE_URL or "")
    return config


def require_migration() -> None:
    """`Rra017Absent` unless RRA-017's revision is in the chain. Checked before migrating."""
    try:
        revision = ScriptDirectory.from_config(alembic_config()).get_revision(RRA017_REVISION)
    except Exception as error:  # noqa: BLE001 -- alembic raises several types for an unknown id
        raise Rra017Absent(f"migration {RRA017_REVISION} does not exist") from error
    if revision is None:
        raise Rra017Absent(f"migration {RRA017_REVISION} does not exist")


def migrated_owner_engine() -> Engine:
    """The migration owner's engine over an emptied head schema. Not guarded: it is the owner."""
    engine = create_engine(DATABASE_URL)
    _refuse_unmarked(engine)
    if _at_head(engine):
        _truncate(engine)
    else:
        _empty_public_schema(engine)
        command.upgrade(alembic_config(), "head")
    return engine


def _refuse_unmarked(engine: Engine) -> None:
    name = engine.url.database or ""
    if not TEST_DATABASE_NAME.search(name):
        raise HarnessError(f"refusing to use database {name!r}: its name does not mark a test")


#: Whether the migration's objects survive: another suite's `drop_all`/`create_all` on this
#: database keeps `alembic_version` at head and silently loses every policy and function.
_INTACT = (
    "SELECT to_regprocedure('public.rra_session_owner(text)') IS NOT NULL "
    "AND (SELECT relforcerowsecurity FROM pg_class "
    "WHERE oid = to_regclass('public.rra_beta_sessions'))"
)


def _at_head(engine: Engine) -> bool:
    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    with engine.connect() as connection:
        if connection.scalar(text("SELECT to_regclass('public.alembic_version')")) is None:
            return False
        if connection.scalar(text("SELECT version_num FROM alembic_version")) != head:
            return False
        return bool(connection.scalar(text(_INTACT)))


def _truncate(engine: Engine) -> None:
    with engine.begin() as connection:
        names = connection.scalars(
            text(
                "SELECT quote_ident(tablename) FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ).all()
        connection.execute(text(f"TRUNCATE TABLE {', '.join(names)} CASCADE"))


def _set_passwords(owner: Engine) -> None:
    """Give each runtime role the test-only password. A missing role is the slice absent."""
    with owner.begin() as connection:
        for role in RUNTIME_ROLES:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
            )
            if exists is None:
                raise Rra017Absent(f"role {role} does not exist")
            # A utility statement takes no bind parameters; both names are constants above.
            connection.execute(text(f"ALTER ROLE {role} PASSWORD '{ROLE_PASSWORD}'"))


# -- the role guard --------------------------------------------------------------------------

_IDENTITY = (
    "SELECT current_user, session_user, r.rolsuper, r.rolbypassrls "
    "FROM pg_roles AS r WHERE r.rolname = current_user"
)


def assert_connected_as(dbapi_connection: Any, role: str) -> None:
    """`HarnessError` unless this connection is `role`, for both users, with no bypass."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute(_IDENTITY)
        identity = tuple(cursor.fetchone())
    finally:
        cursor.close()
    if identity != (role, role, False, False):
        raise HarnessError(f"connected as {identity}, not as the non-bypassing role {role}")


def guarded_engine(url: Any, role: str, **options: Any) -> Engine:
    """An engine whose every new connection is checked by `assert_connected_as` before use."""
    engine = create_engine(url, **options)

    def _check(dbapi_connection: Any, _record: Any) -> None:
        assert_connected_as(dbapi_connection, role)
        dbapi_connection.rollback()

    event.listen(engine, "connect", _check)
    return engine


def role_url(role: str) -> Any:
    return make_url(DATABASE_URL).set(username=role, password=ROLE_PASSWORD)


@dataclass
class RlsDatabase:
    """The migrated, emptied database, and a guarded engine per runtime role."""

    owner: Engine
    _engines: dict[str, Engine] = field(default_factory=dict)

    def engine(self, role: str, **options: Any) -> Engine:
        key = f"{role}:{sorted(options.items())}"
        if key not in self._engines:
            self._engines[key] = guarded_engine(role_url(role), role, **options)
        return self._engines[key]

    def factory(self, role: str) -> sessionmaker[Session]:
        return sessionmaker(self.engine(role), expire_on_commit=False)

    def seed(self, rows: Iterable[tuple[str, Row]]) -> None:
        """Write rows as the migration owner, which crosses the policies (`FR-270`)."""
        tables = rra_tables()
        with self.owner.begin() as connection:
            for table, values in rows:
                connection.execute(tables[table].insert().values(**values))

    def as_owner(self, sql: str, **params: Any) -> list[Any]:
        with self.owner.begin() as connection:
            result = connection.execute(text(sql), params)
            return list(result) if result.returns_rows else []

    def dispose(self) -> None:
        for engine in self._engines.values():
            engine.dispose()
        self.owner.dispose()


@contextmanager
def rls_database() -> Iterator[RlsDatabase]:
    """RRA-017's database, or `Rra017Absent` before any work while the slice is absent."""
    require_migration()
    database = RlsDatabase(owner=migrated_owner_engine())
    try:
        _set_passwords(database.owner)
        yield database
    finally:
        database.dispose()


@pytest.fixture(name="rls")
def rls_fixture() -> Iterator[RlsDatabase]:
    """`rls_database()` per test. Import it into a test module to use it."""
    with rls_database() as database:
        yield database


# -- statements a unit of work runs -----------------------------------------------------------


def scoped(connection: Connection, owner_id: str) -> None:
    """Set this transaction's scope, as `FR-233` requires every unit of work to."""
    connection.execute(
        text("SELECT set_config(:name, :owner, true)"),
        {"name": OWNER_SETTING, "owner": owner_id},
    )


def scope_set_by(statement: str, parameters: Any) -> str | None:
    """The owner a `set_config` of `OWNER_SETTING` sets, or `None` for any other statement.

    Accepts the setting's name in the SQL text or bound, so the detector does not depend on
    which of the two forms the helper emits.
    """
    if "set_config" not in statement:
        return None
    values = list(parameters.values()) if isinstance(parameters, dict) else list(parameters or ())
    if OWNER_SETTING not in statement and OWNER_SETTING not in values:
        return None
    owners = [value for value in values if isinstance(value, str) and value != OWNER_SETTING]
    return owners[0] if owners else None


def sqlstate_of(action: Callable[[], Any]) -> str | None:
    """The SQLSTATE `action` raised, or `None` when it did not raise."""
    try:
        action()
    except DBAPIError as error:
        return getattr(error.orig, "sqlstate", None)
    return None


def attempt(engine: Engine, owner_id: str | None, run: Callable[[Connection], Any]) -> str | None:
    """Run `run` in its own transaction, scoped to `owner_id` unless it is `None`.

    Returns the SQLSTATE it raised, or `None`. Its own transaction, because a refused statement
    aborts the transaction it ran in.
    """

    def _transaction() -> None:
        with engine.begin() as connection:
            if owner_id is not None:
                scoped(connection, owner_id)
            run(connection)

    return sqlstate_of(_transaction)


def insert(table: str, values: Row) -> Callable[[Connection], Any]:
    return lambda connection: connection.execute(rra_tables()[table].insert().values(**values))


def visible_keys(connection: Connection, table: str) -> set[tuple[Any, ...]]:
    """The primary keys of every row of `table` this transaction can see."""
    model = rra_tables()[table]
    columns = [model.c[name] for name in PRIMARY_KEYS[table]]
    return {tuple(found) for found in connection.execute(select(*columns))}


def _where_key(table: str, key: tuple[Any, ...]) -> list[Any]:
    model = rra_tables()[table]
    return [model.c[name] == value for name, value in zip(PRIMARY_KEYS[table], key, strict=True)]


def touch(connection: Connection, table: str, scope: Scope | None = None) -> int:
    """`UPDATE table SET c = c`, over `scope`'s row or every visible row: rows affected."""
    model = rra_tables()[table]
    column = model.c[TOUCH_COLUMNS[table]]
    statement = model.update().values({column.name: column})
    if scope is not None:
        statement = statement.where(*_where_key(table, key_of(scope, table)))
    return connection.execute(statement).rowcount


def remove(connection: Connection, table: str, scope: Scope | None = None) -> int:
    """`DELETE FROM table`, over `scope`'s row or every visible row: rows affected."""
    model = rra_tables()[table]
    statement = model.delete()
    if scope is not None:
        statement = statement.where(*_where_key(table, key_of(scope, table)))
    return connection.execute(statement).rowcount


def repoint(table: str, scope: Scope, values: Row) -> Callable[[Connection], Any]:
    """Re-point `scope`'s row in `table` at the scope columns in `values`."""
    model = rra_tables()[table]
    statement = model.update().where(*_where_key(table, key_of(scope, table))).values(**values)
    return lambda connection: connection.execute(statement)


__all__ = [
    "APPLICATION",
    "COVERED_TABLES",
    "DEFINER",
    "FOREIGN_KEY_VIOLATION",
    "INSUFFICIENT_PRIVILEGE",
    "OWNER_SETTING",
    "OWNER_TABLES",
    "PARENT_WALLED",
    "POSTGRES",
    "PRE_SCOPE_TABLES",
    "RED",
    "RED_STATIC",
    "RRA017_REVISION",
    "RUNTIME_ROLES",
    "SCOPED_ROLES",
    "SWEEP",
    "WORKER",
    "HarnessError",
    "RlsDatabase",
    "Rra017Absent",
    "Rra017Gap",
    "assert_connected_as",
    "attempt",
    "future",
    "guarded_engine",
    "insert",
    "migrated_owner_engine",
    "remove",
    "repoint",
    "require",
    "require_migration",
    "rls_database",
    "rls_fixture",
    "rra_tables",
    "scope_set_by",
    "scoped",
    "sqlstate_of",
    "touch",
    "visible_keys",
]
