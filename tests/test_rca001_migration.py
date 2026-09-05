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
from khepri.rca.workspace.persistence import (  # noqa: F401 -- registers the tables
    AnalysisRunRow,
    ArtifactBindingRow,
    DatasetVersionRow,
)
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
    ("20260814_0014", "rca_drop_membership_attribution", "20260814_0013"),
    ("20260814_0015", "rca_membership_role_check", "20260814_0014"),
    (
        "20260815_0016",
        "rca_sessions_and_external_identities",
        "20260814_0015",
    ),
    # Parent is `20260817_0017`, an *RRA* revision -- the interleaving this block's comment warns
    # about, now with an RCA revision on the far side of it.
    ("20260818_0018", "rca_invitations", "20260817_0017"),
    # `#240`'s recovery security evidence. **This registration was missing**: the migration merged
    # without being listed here, so every test driven by `_run` stopped one revision short of head
    # and `test_migration_columns_match_the_declared_models` could not see the new table at all.
    # It went unnoticed because the guard reads `RcaBase.metadata.tables`, which is populated by
    # import side effects -- until some module imported `recovery_security_persistence`, the table
    # was absent from *both* sides of the comparison and the equality held vacuously. A drift guard
    # whose inputs depend on import order can pass while covering nothing.
    ("20260821_0019", "rca_recovery_security_events", "20260818_0018"),
    # `W1-02`'s five workspace tables. Registered here in the same commit that adds
    # the revision, which is what the `#240` note above asks for: a table absent from
    # this list is a table every `_run`-driven test stops short of.
    ("20260904_0021", "rca_workspace", "20260822_0020"),
    # `W1-04`'s audit event table (`FR-125`), registered in the commit that adds it.
    ("20260905_0022", "rca_workspace_audit_events", "20260904_0021"),
    # `W1-04b`'s run-to-report link, which is how the worker finds the run a job settles.
    ("20260905_0023", "rca_workspace_run_reports", "20260905_0022"),
    # `W1-06`'s provenance record, retained with the run (`KHEPRI-DEC-033` §2).
    ("20260905_0024", "rca_workspace_run_provenance", "20260905_0023"),
    # `W1-08`'s `rra008.*` family versions, added as columns on `20260905_0024`'s record rather
    # than as a table of their own (`FR-116`). The middle element is the revision file's slug, not
    # the table it touches, so it names this migration's own file.
    ("20260905_0025", "rca_workspace_run_family_versions", "20260905_0024"),
    # `W1-07a`'s deletion vocabulary: a `CHECK` rewrite on `20260905_0022`'s table, so the slug
    # names this migration's own file rather than the table it widens.
    ("20260906_0026", "rca_workspace_deletion_audit", "20260905_0025"),
)
# The revision that backfilled `rca_membership_events` from the attribution columns. Tests that
# insert `changed_by`/`changed_at` must stop here: `20260814_0014` drops those columns, so running
# them to head would fail on the INSERT rather than on the behavior they assert.
BACKFILL_REVISION = "20260814_0013"
RCA_REVISION = RCA_REVISIONS[0][0]
RCA_TABLES = {
    "rca_accounts",
    "rca_organizations",
    "rca_memberships",
    "rca_membership_events",
    "rca_isolation_scopes",
    "rca_sessions",
    "rca_external_identities",
    "rca_invitations",
    # `#240`'s table, omitted from this set for the same reason it was missing from
    # `RCA_REVISIONS` above.
    "rca_recovery_security_events",
    "rca_workspace_dataset_versions",
    "rca_workspace_analysis_runs",
    "rca_workspace_artifact_bindings",
    # The two tables the first `W1-02` draft omitted. Their absence here was the `#240` shape
    # again -- missing from the models *and* from this set, so the equality held over both.
    "rca_workspace_source_profiles",
    "rca_workspace_tombstones",
    "rca_workspace_audit_events",
    "rca_workspace_run_reports",
    "rca_workspace_run_provenance",
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
    path = REPO_ROOT / "migrations" / "versions" / f"{ARTIFACT_REVISION}_rra_report_artifacts.py"
    spec = importlib.util.spec_from_file_location(f"rra_migration_{ARTIFACT_REVISION}", path)
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


def _run(database_url: str, direction: str, *, through: str | None = None) -> None:
    """Apply every RCA revision's upgrade or downgrade, in order.

    The full chain cannot replay on SQLite: four earlier RRA migrations use ALTER-style
    constraint operations the SQLite dialect refuses. Those revisions are exercised against
    Postgres, so this drives only the RCA revisions' own operations, against a real engine
    and a real DDL dialect.

    Downgrades run in reverse, so an upgrade/downgrade round trip returns to the starting state
    rather than tripping over a dependency the later revision added.

    `through` stops an upgrade after the named revision, for tests that assert against a schema
    an intermediate revision produced. It is not an escape hatch for a test that a later
    revision breaks: a test pinned here must be asserting something about *that* revision's own
    behavior, and one that fails at head for any other reason is reporting a real defect.
    """
    ordered = RCA_REVISIONS if direction == "upgrade" else tuple(reversed(RCA_REVISIONS))
    if through is not None:
        assert direction == "upgrade", "`through` stops an upgrade; downgrades run the full chain"
        names = [revision for revision, _slug, _parent in ordered]
        assert through in names, f"unknown revision {through}"
        ordered = ordered[: names.index(through) + 1]
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


# What `20260822_0020` changes about `rra_report_artifacts`. Stated here rather than
# replayed, because that revision swaps CHECK constraints and SQLite cannot ALTER a
# constraint -- nor drop a column a CHECK still references. The revision's real DDL is
# proved against PostgreSQL in `test_rra_portable_encryption_migration.py`; this guard
# is about model/migration column parity, so it applies the delta as data.
_PORTABLE_ENCRYPTION_REMOVES = frozenset({"kms_key_id"})
_PORTABLE_ENCRYPTION_ADDS = frozenset({"envelope_version", "ciphertext_sha256_hex"})


def test_report_artifact_migration_matches_its_declared_columns(sqlite_url: str) -> None:
    """The declared model must match the schema after every revision that touches it.

    `20260813_0012` creates the table and `20260822_0020` retires `kms_key_id` for the
    envelope columns, so comparing the model against `0012` alone would report drift
    that does not exist. Both revisions are accounted for.
    """
    from khepri.rra.artifact_persistence import ReportArtifactRow  # noqa: PLC0415

    _run_artifact(sqlite_url, "upgrade")
    inspector = inspect(create_engine(sqlite_url))
    created = {column["name"] for column in inspector.get_columns(ReportArtifactRow.__tablename__)}
    # The delta must actually apply to what `0012` created, or this guard would pass
    # while describing a migration that could not run.
    assert created >= _PORTABLE_ENCRYPTION_REMOVES
    assert not _PORTABLE_ENCRYPTION_ADDS & created

    migrated = (created - _PORTABLE_ENCRYPTION_REMOVES) | _PORTABLE_ENCRYPTION_ADDS
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

    # FR-015's role CHECK faces the same hazard, and twice over: `20260814_0014` rebuilds
    # `rca_memberships` to drop two columns, and `20260814_0015` rebuilds it again to add this
    # constraint. The parity test below compares column *names* only and cannot see a lost
    # constraint, so an unconstrained `role` would reach production with every store test green.
    checks = {c["name"] for c in inspector.get_check_constraints("rca_memberships")}
    assert "ck_rca_membership_role" in checks, f"FR-015 constraint lost in the rebuild: {checks}"


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

    Pinned to `BACKFILL_REVISION`: this asserts what `20260814_0013` did to columns that
    `20260814_0014` has since removed, so it must run against the schema of its own revision.
    """
    _run(sqlite_url, "upgrade", through=BACKFILL_REVISION)
    engine = create_engine(sqlite_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO rca_organizations (organization_id, name, created_at) "
                "VALUES ('org_a', 'Acme', '2026-01-01 00:00:00')"
            )
        )
        connection.execute(
            text("INSERT INTO rca_accounts (account_id, email) VALUES ('acc_a', 'a@example.test')")
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

    Pinned to `BACKFILL_REVISION` for the same reason as the test above.
    """
    _run(sqlite_url, "upgrade", through=BACKFILL_REVISION)
    engine = create_engine(sqlite_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO rca_organizations (organization_id, name, created_at) "
                "VALUES ('org_b', 'Beta', '2026-01-01 00:00:00')"
            )
        )
        connection.execute(
            text("INSERT INTO rca_accounts (account_id, email) VALUES ('acc_b', 'b@example.test')")
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
        count = connection.execute(text("SELECT COUNT(*) FROM rca_membership_events")).scalar()
    assert count == 1, "one membership, one creation event, however many replays"


def test_the_attribution_columns_are_gone_at_head(sqlite_url: str) -> None:
    """`R2-03`: `rca_memberships` carries live state only.

    `changed_by` and `changed_at` recorded who last touched the row and when. That is audit
    data, and `KHEPRI-DEC-015` gives membership audit a twelve-month horizon, while the state
    row it sat on has no expiry at all. Attribution outliving its horizon because it rode on a
    row that never expires is the defect `20260814_0013` moved it off, and this asserts the
    source is now actually gone rather than merely duplicated.
    """
    _run(sqlite_url, "upgrade")
    columns = {c["name"] for c in inspect(create_engine(sqlite_url)).get_columns("rca_memberships")}

    assert columns == {"organization_id", "account_id", "role"}, (
        f"the state row must carry live membership state only, found {sorted(columns)}"
    )


def test_the_downgrade_reconstructs_attribution_from_the_events(sqlite_url: str) -> None:
    """Downgrading must restore the columns *with their values*, not merely their shape.

    `20260812_0010` declares both columns `NOT NULL`, so a downgrade that re-adds them empty
    cannot populate a table that has rows -- it fails on the constraint, and it fails only
    against real data, which is the worst time to discover it. An empty-table test would pass
    against exactly that defect, so this one inserts a membership first.

    The creation events are the source: `actor_account_id` becomes `changed_by` and
    `occurred_at` becomes `changed_at`, inverting the backfill. The reconstruction is exact for
    any membership whose creation event is still inside its twelve-month horizon, and lossy for
    one whose event has been swept -- that is inherent to giving audit data a shorter life than
    the row it describes, and it is the point of the move rather than a defect in it.
    """
    _run(sqlite_url, "upgrade")
    engine = create_engine(sqlite_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO rca_organizations (organization_id, name, created_at) "
                "VALUES ('org_c', 'Gamma', '2026-01-01 00:00:00')"
            )
        )
        connection.execute(
            text("INSERT INTO rca_accounts (account_id, email) VALUES ('acc_c', 'c@example.test')")
        )
        connection.execute(
            text(
                "INSERT INTO rca_memberships (organization_id, account_id, role) "
                "VALUES ('org_c', 'acc_c', 'owner')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO rca_membership_events (event_id, organization_id, account_id, "
                " actor_account_id, prior_role, next_role, occurred_at) "
                "VALUES ('mev_c', 'org_c', 'acc_c', 'acc_actor', NULL, 'owner', "
                " '2026-02-03 04:05:06')"
            )
        )

    module = _rca_migration_module("20260814_0014", "rca_drop_membership_attribution")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        token = module.op
        module.op = Operations(context)
        try:
            module.downgrade()
        finally:
            module.op = token

    with engine.begin() as connection:
        row = connection.execute(text("SELECT changed_by, changed_at FROM rca_memberships")).one()

    assert row.changed_by == "acc_actor", "the event's actor becomes the row's attribution again"
    assert "2026-02-03" in str(row.changed_at), "the event's timestamp comes back with it"

    nullable = {c["name"]: c["nullable"] for c in inspect(engine).get_columns("rca_memberships")}
    assert nullable["changed_by"] is False, "20260812_0010 declares it NOT NULL"
    assert nullable["changed_at"] is False, "20260812_0010 declares it NOT NULL"


def test_the_downgrade_marks_attribution_it_cannot_reconstruct(sqlite_url: str) -> None:
    """A membership whose creation event has been swept downgrades to an explicit placeholder.

    This is the lossy case, and it is inherent rather than accidental: `KHEPRI-DEC-015` §2a
    gives the event twelve months and the membership row no expiry at all, so a row can outlive
    the only record of who created it. That asymmetry is the point of moving attribution off the
    row, not a defect in having done so.

    What the downgrade must not do is paper over it. The placeholder is deliberately not a
    plausible account identifier, so a reader can tell reconstructed-unknown from
    genuinely-recorded. A downgrade that invented a credible-looking actor would be forging the
    audit record it is supposed to be restoring, and nothing downstream could detect it.
    """
    _run(sqlite_url, "upgrade")
    engine = create_engine(sqlite_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO rca_organizations (organization_id, name, created_at) "
                "VALUES ('org_d', 'Delta', '2026-01-01 00:00:00')"
            )
        )
        connection.execute(
            text("INSERT INTO rca_accounts (account_id, email) VALUES ('acc_d', 'd@example.test')")
        )
        # A membership with no creation event: its own has already passed the twelve-month
        # horizon and been swept.
        connection.execute(
            text(
                "INSERT INTO rca_memberships (organization_id, account_id, role) "
                "VALUES ('org_d', 'acc_d', 'member')"
            )
        )

    module = _rca_migration_module("20260814_0014", "rca_drop_membership_attribution")
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        token = module.op
        module.op = Operations(context)
        try:
            module.downgrade()
        finally:
            module.op = token

    with engine.begin() as connection:
        row = connection.execute(text("SELECT changed_by, changed_at FROM rca_memberships")).one()

    assert row.changed_by == module._UNKNOWN_ACTOR, (  # noqa: SLF001
        "a swept event must downgrade to the placeholder, not to a plausible account identifier"
    )
    assert not row.changed_by.startswith("acc_"), (
        "the placeholder must not be mistakable for a real account identifier"
    )
    # The NOT NULL tighten that follows catches a placeholder that never landed at all. It
    # cannot catch one that landed wrong, and the timestamp is bound as a `datetime` rather
    # than a string precisely because PostgreSQL will not implicitly cast text into a
    # `TIMESTAMPTZ` here. Without this, that bind has no assertion behind it.
    assert "1970" in str(row.changed_at), "a swept event downgrades to the epoch placeholder"


def test_every_invitation_check_agrees_between_the_migration_and_the_model(
    sqlite_url: str,
) -> None:
    """`R4-03`'s four constraints have two homes and must say the same thing.

    The invitation counterpart of the role test below, and broader: it compares constraint *names*
    as sets rather than one constraint's values, because `rca_invitations` carries four and a test
    pinning only the role check would leave three free to exist in one place. All four are
    load-bearing -- the role CHECK, the redeemed-or-revoked exclusion, expiry-after-issuance, and
    the five-column verifier invariant that `AccountRow` lacks.

    `test_migration_columns_match_the_declared_models` cannot catch any of it: it compares column
    names, and a CHECK is not a column.
    """
    from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

    from khepri.rca.persistence import Base  # noqa: PLC0415

    _run(sqlite_url, "upgrade")
    migrated = inspect(create_engine(sqlite_url)).get_check_constraints("rca_invitations")

    model_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(model_engine)
    sessionmaker(model_engine)
    declared = inspect(model_engine).get_check_constraints("rca_invitations")

    expected = {
        "ck_rca_invitation_role",
        "ck_rca_invitation_terminal_state",
        "ck_rca_invitation_expiry_after_issuance",
        "ck_rca_invitation_verifier_whole",
    }
    assert {c["name"] for c in migrated} == expected, "migration declares the wrong set"
    assert {c["name"] for c in declared} == expected, "model declares the wrong set"

    def roles_named(constraints) -> set[str]:
        joined = " ".join(c["sqltext"] for c in constraints)
        return {role for role in ("owner", "member", "admin") if f"'{role}'" in joined}

    assert roles_named(migrated) == roles_named(declared) == {"owner", "member"}, (
        f"migration names {roles_named(migrated)}, model names {roles_named(declared)}"
    )

    # Every one of the five verifier columns must appear in the whole-verifier CHECK on both sides.
    # A clause mentioning four would let a half-destroyed verifier through the fifth.
    def verifier_columns(constraints) -> set[str]:
        text = " ".join(
            c["sqltext"] for c in constraints if c["name"] == "ck_rca_invitation_verifier_whole"
        )
        return {
            column
            for column in ("secret_salt", "secret_digest", "kdf_n", "kdf_r", "kdf_p")
            if column in text
        }

    assert verifier_columns(migrated) == verifier_columns(declared)
    assert len(verifier_columns(migrated)) == 5, (
        f"the whole-verifier CHECK omits a column: {verifier_columns(migrated)}"
    )


def test_the_role_check_agrees_between_the_migration_and_the_model(sqlite_url: str) -> None:
    """FR-015's constraint has two homes and they must say the same thing.

    The model builds it from `ROLES` so the domain cannot add a role without the column
    noticing; the migration spells the values out so a past revision keeps meaning what it meant
    when it ran. Those are the right choices for each, and they are also exactly the conditions
    under which two sources drift apart -- so this pins them together at head.

    `test_migration_columns_match_the_declared_models` cannot catch this: it compares column
    names and a CHECK constraint is not a column.
    """
    from sqlalchemy.orm import sessionmaker  # noqa: PLC0415

    from khepri.rca.persistence import Base  # noqa: PLC0415

    _run(sqlite_url, "upgrade")
    migrated = inspect(create_engine(sqlite_url)).get_check_constraints("rca_memberships")

    model_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(model_engine)
    sessionmaker(model_engine)
    declared = inspect(model_engine).get_check_constraints("rca_memberships")

    def roles_named(constraints) -> set[str]:
        joined = " ".join(c["sqltext"] for c in constraints)
        return {role for role in ("owner", "member", "admin") if f"'{role}'" in joined}

    assert roles_named(migrated) == roles_named(declared) == {"owner", "member"}, (
        f"migration names {roles_named(migrated)}, model names {roles_named(declared)}"
    )
