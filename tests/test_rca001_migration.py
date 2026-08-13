from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from khepri.rca.persistence import Base as RcaBase
from tests.local_stack_support import requires_local_stack

REPO_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_HEAD = "20260730_0009"
# Every RCA revision, oldest first. `_run` applies the whole chain, so adding a revision here is
# all that is needed for the column-parity and round-trip tests below to cover it -- an earlier
# version drove one hardcoded module, which meant a second revision would have gone unexercised
# while `test_migration_columns_match_the_declared_models` still reported green.
RCA_REVISIONS = (
    ("20260812_0010", "rca_identity_spine"),
    ("20260813_0011", "rca_account_lifecycle"),
)
RCA_REVISION = RCA_REVISIONS[0][0]
RCA_TABLES = {
    "rca_accounts",
    "rca_organizations",
    "rca_memberships",
    "rca_isolation_scopes",
}


def _rca_migration_module(revision: str = RCA_REVISION, slug: str = "rca_identity_spine"):
    """Load a revision by path, the way Alembic does.

    `migrations/versions/` has no `__init__.py` — Alembic loads revision files directly —
    so a normal import cannot reach it.
    """
    path = REPO_ROOT / "migrations" / "versions" / f"{revision}_{slug}.py"
    spec = importlib.util.spec_from_file_location(f"rca_migration_{revision}", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(name="sqlite_url")
def _sqlite_url(tmp_path: Path) -> str:
    return f"sqlite+pysqlite:///{(tmp_path / 'migration.db').as_posix()}"


def _run(database_url: str, direction: str) -> None:
    """Apply every RCA revision's upgrade or downgrade, in order.

    The full chain cannot replay on SQLite: four earlier RRA migrations use ALTER-style
    constraint operations the SQLite dialect refuses. Those revisions are exercised against
    Postgres, so this drives only the RCA revisions' own operations, against a real engine
    and a real DDL dialect.

    Downgrades run in reverse, so an upgrade/downgrade round trip returns to the starting state
    rather than tripping over a dependency the later revision added.
    """
    ordered = RCA_REVISIONS if direction == "upgrade" else tuple(reversed(RCA_REVISIONS))
    engine = create_engine(database_url)
    for revision, slug in ordered:
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            operations = Operations(context)
            module = _rca_migration_module(revision, slug)
            token = module.op
            try:
                module.op = operations
                getattr(module, direction)()  # noqa: B009 — direction is a runtime parameter
            finally:
                module.op = token


def test_the_revisions_form_an_unbroken_chain() -> None:
    """Each RCA revision must point at its predecessor, and the first at the last RRA head.

    A revision whose `down_revision` skips one would still upgrade cleanly here while leaving
    Alembic with two heads in production.
    """
    expected_parent = PREVIOUS_HEAD
    for revision, slug in RCA_REVISIONS:
        module = _rca_migration_module(revision, slug)
        assert module.revision == revision
        assert module.down_revision == expected_parent, (
            f"{revision} points at {module.down_revision}, expected {expected_parent}"
        )
        expected_parent = revision


def test_upgrade_creates_every_rca_table(sqlite_url: str) -> None:
    """The documented `alembic upgrade head` path must create the RCA tables.

    The store tests build their schema with `Base.metadata.create_all`, which would mask a
    missing migration: production initializes through Alembic, so without one the first
    SqlAccountStore call would fail with an undefined-table error.
    """
    _run(sqlite_url, "upgrade")

    present = set(inspect(create_engine(sqlite_url)).get_table_names())
    assert present >= RCA_TABLES, f"missing: {sorted(RCA_TABLES - present)}"


def test_downgrade_removes_every_rca_table(sqlite_url: str) -> None:
    _run(sqlite_url, "upgrade")
    _run(sqlite_url, "downgrade")

    present = set(inspect(create_engine(sqlite_url)).get_table_names())
    assert not (RCA_TABLES & present), f"left behind: {sorted(RCA_TABLES & present)}"


def test_migration_columns_match_the_declared_models(sqlite_url: str) -> None:
    """Guards drift between the migration and `khepri.rca.persistence`.

    Adding a mapped column without a migration fails here rather than at the first
    production write.
    """
    _run(sqlite_url, "upgrade")
    inspector = inspect(create_engine(sqlite_url))

    for table_name, table in RcaBase.metadata.tables.items():
        migrated = {column["name"] for column in inspector.get_columns(table_name)}
        declared = {column.name for column in table.columns}
        assert declared == migrated, f"{table_name}: declared {declared} vs migrated {migrated}"


def test_rca_metadata_stays_separate_from_rra() -> None:
    """FR-039: RCA declares its own Base, so Alembic must carry both metadata objects."""
    from khepri.rra.persistence import Base as RraBase  # noqa: PLC0415

    assert RcaBase.metadata is not RraBase.metadata
    assert all(name.startswith("rca_") for name in RcaBase.metadata.tables)


@requires_local_stack()
def test_full_chain_upgrades_to_head_on_postgres() -> None:
    """The real production path, end to end, on the dialect production actually uses."""
    database_url = os.environ.get("KHEPRI_DATABASE_URL")
    if not database_url:
        pytest.skip("KHEPRI_DATABASE_URL is not set")

    config = _alembic_config(database_url)
    command.upgrade(config, "head")

    present = set(inspect(create_engine(database_url)).get_table_names())
    assert present >= RCA_TABLES, f"missing: {sorted(RCA_TABLES - present)}"
