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
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from khepri.rca.persistence import Base as RcaBase
from tests.local_stack_support import requires_local_stack

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_REVISION = "20260813_0012"
PREVIOUS_HEAD = "20260730_0009"
# Every RCA revision, oldest first, as (revision, slug, expected parent). `_run` applies the whole
# chain, so adding a revision here is all that is needed for the column-parity and round-trip tests
# below to cover it -- an earlier version drove one hardcoded module, which meant a second revision
# would have gone unexercised while `test_migration_columns_match_the_declared_models` still
# reported green.
#
# The parent is stated explicitly rather than derived from the previous entry, because the chain is
# no longer RCA-contiguous: the RRA artifact revision `20260813_0012` sits between two RCA
# revisions, so `20260814_0013` descends from it and not from the RCA revision before it. A test
# that assumed contiguity would demand the wrong parent and, worse, would keep asserting it
# silently as more revisions interleave.
RCA_REVISIONS = (
    ("20260812_0010", "rca_identity_spine", "20260730_0009"),
    ("20260813_0011", "rca_account_lifecycle", "20260812_0010"),
    ("20260814_0013", "rca_membership_events", "20260813_0012"),
)
RCA_REVISION = RCA_REVISIONS[0][0]
RCA_TABLES = {
    "rca_accounts",
    "rca_organizations",
    "rca_memberships",
    "rca_membership_events",
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
    for revision, slug, _parent in ordered:
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
    """Each RCA revision must point at the revision that actually precedes it.

    A revision whose `down_revision` skips one would still upgrade cleanly here while leaving
    Alembic with two heads in production.

    The parent is read from the table rather than assumed to be the previous RCA revision. The
    chain interleaves: `20260813_0012` is an RRA revision sitting between two RCA ones, so
    `20260814_0013` descends from it. Deriving the parent positionally would assert the wrong
    thing here, and would go on asserting it silently as more revisions interleave.
    """
    for revision, slug, expected_parent in RCA_REVISIONS:
        module = _rca_migration_module(revision, slug)
        assert module.revision == revision
        assert module.down_revision == expected_parent, (
            f"{revision} points at {module.down_revision}, expected {expected_parent}"
        )


def test_report_artifacts_are_chained_after_the_rca_revision_it_followed() -> None:
    """The artifact revision descends from whichever revision preceded it when it landed.

    This previously read `RCA_REVISIONS[-1]`, meaning "the newest RCA revision" -- which was
    true while the artifact revision *was* the head, and became false the moment
    `20260814_0013` landed after it. The relationship being asserted is historical: an already
    merged revision's parent does not change when a later one arrives.

    So the parent is named. The chain as a whole is covered by
    `test_the_revisions_form_an_unbroken_chain`, and a single head is enforced by
    `test_only_one_migration_head_exists`.
    """
    module = _artifact_migration_module()
    assert module.revision == ARTIFACT_REVISION
    assert module.down_revision == "20260813_0011"


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


def test_the_backfill_synthesizes_one_creation_event_per_existing_membership(
    sqlite_url: str,
) -> None:
    """`20260814_0013` must not lose the attribution it is replacing.

    `rca_memberships.changed_by` and `changed_at` are the only attribution that exists for
    memberships created before events did. `R2-03` drops those columns, so if this backfill is
    wrong the data is gone with them — which is exactly why the two are separate revisions.

    A backfilled event is a reconstruction rather than an observed one: it asserts the
    membership existed at this role, attributed to this account, at this time. All true, all
    supported by the source columns, and none of it emitted by an operation.
    """
    _run(sqlite_url, "upgrade")
    engine = create_engine(sqlite_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO rca_organizations (organization_id, name, created_at) "
                "VALUES ('org_a', 'Acme', '2026-01-01 00:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO rca_accounts (account_id, email) VALUES ('acc_a', 'a@example.test')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO rca_memberships "
                "(organization_id, account_id, role, changed_by, changed_at) "
                "VALUES ('org_a', 'acc_a', 'owner', 'acc_a', '2026-02-03 04:05:06')"
            )
        )
        connection.execute(text("DELETE FROM rca_membership_events"))

    module = _rca_migration_module("20260814_0013", "rca_membership_events")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        token = module.op
        module.op = Operations(context)
        try:
            module._backfill_creation_events()  # noqa: SLF001
        finally:
            module.op = token

    with engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT organization_id, account_id, actor_account_id, prior_role, next_role, "
                "occurred_at FROM rca_membership_events"
            )
        ).fetchall()

    assert len(rows) == 1
    row = rows[0]
    assert row.organization_id == "org_a"
    assert row.account_id == "acc_a"
    assert row.actor_account_id == "acc_a", "changed_by becomes the actor"
    assert row.prior_role is None, "a reconstructed creation has no prior role"
    assert row.next_role == "owner", "the current role becomes the resulting role"
    assert "2026-02-03" in str(row.occurred_at), "changed_at becomes the timestamp"


def test_the_backfill_is_idempotent(sqlite_url: str) -> None:
    """Re-running must not produce a second event for the same membership.

    The identifier is derived from the membership's own identity rather than generated, so a
    downgrade-and-replay collides on the primary key instead of silently doubling the audit
    trail. A random identifier would make the second run succeed and leave two creation events
    for one membership.
    """
    _run(sqlite_url, "upgrade")
    engine = create_engine(sqlite_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO rca_organizations (organization_id, name, created_at) "
                "VALUES ('org_b', 'Beta', '2026-01-01 00:00:00')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO rca_accounts (account_id, email) VALUES ('acc_b', 'b@example.test')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO rca_memberships "
                "(organization_id, account_id, role, changed_by, changed_at) "
                "VALUES ('org_b', 'acc_b', 'owner', 'acc_b', '2026-02-03 04:05:06')"
            )
        )
        connection.execute(text("DELETE FROM rca_membership_events"))

    module = _rca_migration_module("20260814_0013", "rca_membership_events")

    def replay() -> None:
        with engine.begin() as connection:
            context = MigrationContext.configure(connection)
            token = module.op
            module.op = Operations(context)
            try:
                module._backfill_creation_events()  # noqa: SLF001
            finally:
                module.op = token

    replay()
    with pytest.raises(IntegrityError):
        replay()

    with engine.begin() as connection:
        count = connection.execute(
            text("SELECT COUNT(*) FROM rca_membership_events")
        ).scalar()
    assert count == 1, "one membership, one creation event, however many replays"
