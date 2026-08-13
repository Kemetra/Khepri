from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from khepri.rca.persistence import Base as RcaBase
from tests.local_stack_support import requires_local_stack

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_REVISION = "20260813_0012"
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


def _artifact_migration_module():
    path = (
        REPO_ROOT
        / "migrations"
        / "versions"
        / f"{ARTIFACT_REVISION}_rra_report_artifacts.py"
    )
    spec = importlib.util.spec_from_file_location(
        f"rra_migration_{ARTIFACT_REVISION}", path
    )
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


def _run_artifact(database_url: str, direction: str) -> None:
    engine = create_engine(database_url)
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        operations = Operations(context)
        module = _artifact_migration_module()
        token = module.op
        try:
            module.op = operations
            if direction == "upgrade":
                module._create_artifact_table()  # noqa: SLF001
            else:
                module._drop_artifact_table()  # noqa: SLF001
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


def test_report_artifacts_are_chained_after_the_rca_head() -> None:
    """The artifact revision must descend from the *last* RCA revision, not a fixed one.

    Derived from `RCA_REVISIONS[-1]` rather than written as a literal. This assertion named
    `20260812_0010` while that happened to be the newest RCA revision, and stayed green as a
    statement about the wrong revision the moment `20260813_0011` landed beside it -- git
    reported no conflict here, because only the constant it reads through had moved.
    """
    module = _artifact_migration_module()
    assert module.revision == ARTIFACT_REVISION
    assert module.down_revision == RCA_REVISIONS[-1][0]


def test_report_artifact_migration_matches_its_declared_columns(sqlite_url: str) -> None:
    from khepri.rra.artifact_persistence import ReportArtifactRow  # noqa: PLC0415

    _run_artifact(sqlite_url, "upgrade")
    inspector = inspect(create_engine(sqlite_url))
    migrated = {
        column["name"]
        for column in inspector.get_columns(ReportArtifactRow.__tablename__)
    }
    declared = {column.name for column in ReportArtifactRow.__table__.columns}
    assert migrated == declared


def test_report_artifact_migration_downgrades_cleanly(sqlite_url: str) -> None:
    _run_artifact(sqlite_url, "upgrade")
    _run_artifact(sqlite_url, "downgrade")
    assert "rra_report_artifacts" not in inspect(create_engine(sqlite_url)).get_table_names()


def test_artifact_migration_requeues_live_legacy_deliveries() -> None:
    module = _artifact_migration_module()
    operation = Mock()
    token = module.op
    try:
        module.op = operation
        module._requeue_deliveries_without_artifacts()  # noqa: SLF001
    finally:
        module.op = token
    statement = str(operation.execute.call_args.args[0])
    assert "SET state = 'queued'" in statement
    assert "state = 'succeeded'" in statement
    assert "content_expires_at > CURRENT_TIMESTAMP" in statement
    assert "attempt_count = 0" not in statement
    assert "max_attempts = max_attempts + attempt_count" in statement


def test_artifact_downgrade_discards_incompatible_report_evidence() -> None:
    module = _artifact_migration_module()
    operation = Mock()
    token = module.op
    try:
        module.op = operation
        module._discard_report_artifact_evidence()  # noqa: SLF001
    finally:
        module.op = token
    statement = str(operation.execute.call_args.args[0])
    assert "DELETE FROM rra_deletion_evidence" in statement
    assert "target_kind = 'report_artifact'" in statement


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


def test_migration_preserves_constraints_and_nullability(sqlite_url: str) -> None:
    """A batch rebuild must not silently drop a constraint.

    `20260813_0011` uses `batch_alter_table` to make `email` nullable, and on SQLite that drops
    and recreates the table from reflection — a documented way to lose constraints. If
    `uq_rca_account_email` did not survive, A-1 would be unenforced in production while every
    store test stayed green, because those build their schema from `Base.metadata.create_all`
    (which has the constraint from the model, not from the migration).

    Column *names* alone cannot catch this, which is why it is asserted separately from the
    parity test below.
    """
    _run(sqlite_url, "upgrade")
    inspector = inspect(create_engine(sqlite_url))

    unique = {c["name"] for c in inspector.get_unique_constraints("rca_accounts")}
    assert "uq_rca_account_email" in unique, f"A-1 constraint lost in the rebuild: {unique}"

    nullable = {c["name"]: c["nullable"] for c in inspector.get_columns("rca_accounts")}
    assert nullable["email"] is True, "the post-horizon tombstone needs a nullable email"
    assert nullable["disabled_at"] is True, "an enabled account has no disablement timestamp"
    assert nullable["account_id"] is False, "the opaque identifier survives every purge"


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
