"""Migration evidence for the recovery security event table."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

REVISION = "20260821_0019"
SLUG = "rca_recovery_security_events"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _migration():
    path = REPO_ROOT / "migrations" / "versions" / f"{REVISION}_{SLUG}.py"
    spec = importlib.util.spec_from_file_location("recovery_security_migration", path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(database_url: str, direction: str) -> None:
    module = _migration()
    engine = create_engine(database_url)
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        token = module.op
        try:
            module.op = operations
            getattr(module, direction)()
        finally:
            module.op = token


def test_the_revision_descends_from_the_current_single_head() -> None:
    module = _migration()
    assert module.revision == REVISION
    assert module.down_revision == "20260818_0018"


def test_upgrade_creates_only_the_content_free_columns(tmp_path: Path) -> None:
    from khepri.rca.recovery_security_persistence import RecoverySecurityEventRow

    database_url = f"sqlite+pysqlite:///{(tmp_path / 'security.db').as_posix()}"
    _run(database_url, "upgrade")
    inspector = inspect(create_engine(database_url))

    migrated = {
        column["name"]
        for column in inspector.get_columns(RecoverySecurityEventRow.__tablename__)
    }
    declared = {column.name for column in RecoverySecurityEventRow.__table__.columns}
    assert migrated == declared == {"event_key_hash", "account_id", "occurred_at"}
    assert inspector.get_pk_constraint(RecoverySecurityEventRow.__tablename__)[
        "constrained_columns"
    ] == ["event_key_hash"]


def test_downgrade_removes_the_event_table(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{(tmp_path / 'security.db').as_posix()}"
    _run(database_url, "upgrade")
    _run(database_url, "downgrade")

    assert "rca_recovery_security_events" not in inspect(
        create_engine(database_url)
    ).get_table_names()
