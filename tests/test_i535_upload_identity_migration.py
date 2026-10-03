"""#535: `20261003_0037`, the foreign key it adds, and `FR-262`'s repair, on PostgreSQL.

`RCA-005` `FR-262`'s Verification, run from the prior head: the revision populates `upload_id`
for a version whose upload row exists and leaves it null for one whose upload was purged, aborts on
a version that matches two upload rows, replaces the index, and its downgrade runs before a re-seal
and aborts after one. `FR-256`: removing an upload row clears its version's `upload_id` and nothing
else, a tombstoned version included, and a version cannot name another scope's upload. The repair
fills a null written by code without the column, leaves set values alone, and refuses an ambiguous
version, as the application role under `RRA-017`'s policies.

PostgreSQL only, under the `concurrency` marker so a skip in CI fails the build: the key's
`ON DELETE SET NULL (upload_id)` form and the row-security policies exist only there.
**Not a `test_rra*` file** (`RCA-001` `FR-037`).
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from types import ModuleType
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from khepri.rca.persistence import Base as RcaBase
from tests.rra017_rows import HOUR, NOW, Scope, row
from tests.rra017_support import (
    APPLICATION,
    DATABASE_URL,
    POSTGRES,
    SWEEP,
    WORKER,
    RlsDatabase,
    alembic_config,
    rls_fixture,  # noqa: F401 -- the `rls` fixture
    rra_tables,
)

pytestmark = list(POSTGRES)

REVISION = "20261003_0037"
PARENT = "20261002_0036"
VERSIONS = "rca_workspace_dataset_versions"
IDENTITY_INDEX = "uq_rca_workspace_version_upload_id"
DIGEST_INDEX = "uq_rca_workspace_version_upload"
KEY = "fk_rca_workspace_version_upload"

A = Scope("own_a", "a")
B = Scope("own_b", "b")


def _migration() -> ModuleType:
    script = ScriptDirectory.from_config(alembic_config()).get_revision(REVISION)
    spec = importlib.util.spec_from_file_location("migration_0037", script.path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="database")
def database_fixture() -> Iterator[tuple[Config, Engine]]:
    """An emptied schema at head; left at head for the next module."""
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    config = alembic_config()
    command.upgrade(config, "head")
    try:
        yield config, engine
    finally:
        engine.dispose()
        with create_engine(DATABASE_URL).begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
        command.upgrade(config, "head")


def _scope_rows(scope: Scope) -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "rca_organizations",
            {"organization_id": f"org_{scope.tag}", "name": scope.tag, "created_at": NOW},
        ),
        (
            "rca_isolation_scopes",
            {"organization_id": f"org_{scope.tag}", "owner_id": scope.owner_id},
        ),
    ]


def _version(scope: Scope, tag: str, digest: str, **extra: Any) -> tuple[str, dict[str, Any]]:
    return (
        VERSIONS,
        {
            "version_id": f"ver_{tag}",
            "owner_id": scope.owner_id,
            "upload_plaintext_digest": "p" * 64,
            "upload_ciphertext_digest": digest,
            "upload_size_bytes": 10,
            "upload_media_type": "text/csv",
            "manifest_digest": "m" * 64,
            "mapping_version": "v1",
            "admission_outcome": "admitted",
            "created_at": NOW - 10 * 24 * HOUR,
            "sealed_at": NOW - 8 * 24 * HOUR,
            "retention_state": "active",
            "retention_changed_at": None,
            **extra,
        },
    )


def _uploaded(scope: Scope, tag: str, digest: str) -> list[tuple[str, dict[str, Any]]]:
    """One upload, `upl_<tag>`, in its own session: `rra_uploads` holds one upload per session."""
    session = Scope(scope.owner_id, tag)
    return [
        ("rra_beta_sessions", row(session, "rra_beta_sessions")),
        ("rra_uploads", row(session, "rra_uploads", ciphertext_sha256_hex=digest)),
    ]


def _seed(engine: Engine, *, rca: list, rra: list) -> None:
    tables = {**rra_tables(), **RcaBase.metadata.tables}
    with engine.begin() as connection:
        for table, values in [*rra, *rca]:
            connection.execute(tables[table].insert().values(**values))


def _identities(engine: Engine) -> dict[str, str | None]:
    with engine.connect() as connection:
        rows = connection.execute(text(f"SELECT version_id, upload_id FROM {VERSIONS}"))
        return dict(rows.all())


def _indexes(engine: Engine) -> set[str]:
    return {index["name"] for index in inspect(engine).get_indexes(VERSIONS)}


# --- the revision, from the prior head ------------------------------------------------------------


def test_the_upgrade_backfills_existing_uploads_and_leaves_purged_ones_null(database) -> None:
    config, engine = database
    command.downgrade(config, PARENT)
    _seed(
        engine,
        rca=_scope_rows(A) + [_version(A, "kept", "k" * 64), _version(A, "purged", "g" * 64)],
        rra=[*_uploaded(A, "kept", "k" * 64)],
    )

    command.upgrade(config, "head")

    assert _identities(engine) == {"ver_kept": "upl_kept", "ver_purged": None}
    with engine.connect() as connection:
        live_but_null = connection.execute(
            text(
                f"SELECT count(*) FROM {VERSIONS} v JOIN rra_uploads u ON u.owner_id = v.owner_id "
                "AND u.ciphertext_sha256_hex = v.upload_ciphertext_digest WHERE v.upload_id IS NULL"
            )
        ).scalar_one()
    assert live_but_null == 0


def test_the_backfill_never_matches_across_scopes(database) -> None:
    config, engine = database
    command.downgrade(config, PARENT)
    _seed(
        engine,
        rca=_scope_rows(A) + _scope_rows(B) + [_version(A, "a", "s" * 64)],
        rra=[*_uploaded(B, "b", "s" * 64)],
    )

    command.upgrade(config, "head")

    assert _identities(engine) == {"ver_a": None}


def test_the_upgrade_aborts_on_a_version_matching_two_uploads(database) -> None:
    config, engine = database
    command.downgrade(config, PARENT)
    _seed(
        engine,
        rca=_scope_rows(A) + [_version(A, "twice", "t" * 64)],
        rra=[*_uploaded(A, "one", "t" * 64), *_uploaded(A, "two", "t" * 64)],
    )

    with pytest.raises(RuntimeError, match="more than one upload row"):
        command.upgrade(config, "head")

    assert "upload_id" not in {c["name"] for c in inspect(engine).get_columns(VERSIONS)}


def test_the_upgrade_replaces_the_index_and_keys_onto_the_upload(database) -> None:
    _config, engine = database

    assert IDENTITY_INDEX in _indexes(engine)
    assert DIGEST_INDEX not in _indexes(engine)
    (key,) = [k for k in inspect(engine).get_foreign_keys(VERSIONS) if k["name"] == KEY]
    assert key["referred_table"] == "rra_uploads"
    assert key["constrained_columns"] == ["owner_id", "upload_id"]
    assert key["referred_columns"] == ["owner_id", "upload_id"]


def test_the_downgrade_runs_before_a_reseal(database) -> None:
    config, engine = database
    _seed(
        engine,
        rca=_scope_rows(A) + [_version(A, "kept", "k" * 64, upload_id="upl_kept")],
        rra=[*_uploaded(A, "kept", "k" * 64)],
    )

    command.downgrade(config, PARENT)

    assert DIGEST_INDEX in _indexes(engine)
    assert IDENTITY_INDEX not in _indexes(engine)
    assert "upload_id" not in {c["name"] for c in inspect(engine).get_columns(VERSIONS)}


def test_the_downgrade_aborts_after_a_reseal(database) -> None:
    config, engine = database
    _seed(
        engine,
        rca=_scope_rows(A) + [_version(A, "kept", "k" * 64, upload_id="upl_kept")],
        rra=[*_uploaded(A, "kept", "k" * 64)],
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE rra_uploads SET ciphertext_sha256_hex = :new WHERE upload_id = 'upl_kept'"
            ),
            {"new": "r" * 64},
        )

    with pytest.raises(RuntimeError, match="re-sealed"):
        command.downgrade(config, PARENT)

    assert IDENTITY_INDEX in _indexes(engine)


def test_one_head_remains() -> None:
    assert ScriptDirectory.from_config(alembic_config()).get_heads() == [REVISION]


def test_a_runner_subject_to_row_security_is_detected(database) -> None:
    """`FR-270`: a runner without `BYPASSRLS` would backfill against an empty read."""
    _config, engine = database
    blind = _migration()._BLIND  # noqa: SLF001 -- the guard's own statement, asserted directly

    with engine.begin() as connection:
        assert connection.execute(text(blind)).scalar_one() is False
        connection.execute(text(f"SET LOCAL ROLE {APPLICATION}"))
        assert connection.execute(text(blind)).scalar_one() is True


# --- FR-256: the key clears, and confines ---------------------------------------------------------


def _keyed(engine: Engine, *, retention: str = "active") -> None:
    _seed(
        engine,
        rca=_scope_rows(A)
        + _scope_rows(B)
        + [
            _version(
                A,
                "kept",
                "k" * 64,
                upload_id="upl_kept",
                retention_state=retention,
                retention_changed_at=None if retention == "active" else NOW,
            )
        ],
        rra=[*_uploaded(A, "kept", "k" * 64), *_uploaded(B, "b", "b" * 64)],
    )


def _version_row(engine: Engine) -> dict[str, Any]:
    with engine.connect() as connection:
        found = connection.execute(text(f"SELECT * FROM {VERSIONS} WHERE version_id = 'ver_kept'"))
        return dict(found.mappings().one())


@pytest.mark.parametrize("retention", ["active", "tombstoned"])
def test_removing_the_upload_clears_only_upload_id(database, retention: str) -> None:
    _config, engine = database
    _keyed(engine, retention=retention)
    before = _version_row(engine)

    with engine.begin() as connection:
        connection.execute(text("DELETE FROM rra_uploads WHERE upload_id = 'upl_kept'"))

    after = _version_row(engine)
    assert after["upload_id"] is None
    assert {k: v for k, v in after.items() if k != "upload_id"} == {
        k: v for k, v in before.items() if k != "upload_id"
    }


def test_a_version_cannot_name_another_scopes_upload(database) -> None:
    _config, engine = database
    _keyed(engine)

    with pytest.raises(IntegrityError):
        _seed(engine, rca=[_version(A, "stolen", "x" * 64, upload_id="upl_b")], rra=[])


def test_inserting_a_version_whose_upload_is_gone_is_a_fault(database) -> None:
    """Not `VersionAlreadyRecorded`: a foreign-key failure stays the driver error it is."""
    from sqlalchemy.orm import sessionmaker

    from khepri.rca.workspace.contracts import AdmittedSource, DatasetVersion
    from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore

    _config, engine = database
    _keyed(engine)
    store = SqlWorkspaceRecordStore(sessionmaker(engine, expire_on_commit=False))
    source = AdmittedSource("p" * 64, "y" * 64, 10, "text/csv", "m" * 64, "v1", "admitted")
    version = DatasetVersion.create(
        owner_id=A.owner_id, upload_id="upl_gone", source=source, now=NOW
    )

    with pytest.raises(IntegrityError) as fault:
        store.add_dataset_version(version)

    assert "foreign key" in str(fault.value.orig).lower()


# --- FR-262's repair, as the application role under the policies ----------------------------------


def _null_written_by_old_code(rls: RlsDatabase) -> None:
    """Two scopes. In A: one version set, one left null by an old writer, one ambiguous."""
    rls.seed(
        [
            *_uploaded(A, "set", "s" * 64),
            *_uploaded(A, "late", "l" * 64),
            *_uploaded(A, "one", "t" * 64),
            *_uploaded(A, "two", "t" * 64),
            *_uploaded(B, "late_b", "q" * 64),
        ]
    )
    _seed(
        rls.owner,
        rca=_scope_rows(A)
        + _scope_rows(B)
        + [
            _version(A, "set", "s" * 64, upload_id="upl_set"),
            _version(A, "late", "l" * 64),
            _version(A, "twice", "t" * 64),
            _version(B, "late_b", "q" * 64),
            _version(A, "purged", "g" * 64),
        ],
        rra=[],
    )


def test_the_repair_fills_old_writers_nulls_in_every_scope(rls: RlsDatabase) -> None:
    from khepri.runtime.upload_identity_repair import RepairOutcome, repair_upload_identity

    _null_written_by_old_code(rls)

    outcome = repair_upload_identity(rls.factory(APPLICATION))

    assert outcome == RepairOutcome(filled=2, refused=1)
    assert _identities(rls.owner) == {
        "ver_set": "upl_set",
        "ver_late": "upl_late",
        "ver_twice": None,
        "ver_late_b": "upl_late_b",
        "ver_purged": None,
    }


def test_the_repair_is_rerunnable_and_never_overwrites(rls: RlsDatabase) -> None:
    from khepri.runtime.upload_identity_repair import RepairOutcome, repair_upload_identity

    _null_written_by_old_code(rls)
    repair_upload_identity(rls.factory(APPLICATION))
    first = _identities(rls.owner)

    again = repair_upload_identity(rls.factory(APPLICATION))

    assert again == RepairOutcome(filled=0, refused=1)
    assert _identities(rls.owner) == first


def test_the_repair_of_one_scope_touches_no_other(rls: RlsDatabase) -> None:
    """`repair_scope` is the per-scope unit `FR-263`(c) runs under one upload's session lock."""
    from khepri.runtime.upload_identity_repair import repair_scope

    _null_written_by_old_code(rls)

    outcome = repair_scope(rls.factory(APPLICATION), B.owner_id)

    assert outcome.filled == 1
    assert _identities(rls.owner)["ver_late"] is None


def test_the_upload_horizon_survives_the_repair(rls: RlsDatabase) -> None:
    """The purge finds an old writer's upload once the repair has named it (`FR-259`)."""
    from khepri.runtime.upload_identity_repair import repair_scope
    from khepri.runtime.workspace_retention import DueUploadLister
    from tests.rra017_support import SWEEP

    _null_written_by_old_code(rls)
    lister = DueUploadLister(rls.factory(SWEEP))
    before = {upload.upload_id for upload in lister.due(now=NOW)}

    repair_scope(rls.factory(APPLICATION), A.owner_id)

    after = {upload.upload_id for upload in lister.due(now=NOW + timedelta(seconds=1))}
    assert "upl_late" not in before
    assert "upl_late" in after


@pytest.mark.parametrize("role", [APPLICATION, WORKER, SWEEP])
def test_the_revision_refuses_to_run_while_an_application_is_connected(
    rls: RlsDatabase, role: str
) -> None:
    """`FR-262`'s no-writer rule, enforced: stop web, worker and sweep, then migrate."""
    config = alembic_config()
    with (
        rls.engine(role).connect(),
        pytest.raises(RuntimeError, match="stop web, worker and sweep"),
    ):
        command.downgrade(config, PARENT)
    rls.engine(role).dispose()
    command.downgrade(config, PARENT)

    with (
        rls.engine(role).connect(),
        pytest.raises(RuntimeError, match="stop web, worker and sweep"),
    ):
        command.upgrade(config, "head")
    rls.engine(role).dispose()
    command.upgrade(config, "head")

    assert ScriptDirectory.from_config(config).get_current_head() == REVISION


@contextmanager
def _operations_on(connection: Any) -> Iterator[ModuleType]:
    """The revision module with `op` bound to `connection`, as `test_rca001_migration` binds it."""
    module = _migration()
    module.op = Operations(MigrationContext.configure(connection))
    yield module


@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_a_runner_that_cannot_cross_row_security_is_refused(database, direction: str) -> None:
    """`RRA-017` `FR-270`: refused before any DDL, so no backfill runs against an empty read."""
    _config, engine = database

    with engine.connect() as connection, _operations_on(connection) as module:
        connection.execute(text(f"SET ROLE {APPLICATION}"))
        with pytest.raises(RuntimeError, match="row security"):
            getattr(module, direction)()  # noqa: B009 -- the direction is the parameter
        connection.rollback()


def test_the_revision_holds_off_a_writer_until_it_commits(database) -> None:
    """The `EXCLUSIVE` locks taken first block a version insert from any other connection."""
    _config, engine = database
    _keyed(engine)

    with engine.connect() as holder, _operations_on(holder) as module:
        module._hold_off_writers()  # noqa: SLF001 -- the step `upgrade` and `downgrade` open with
        with engine.connect() as writer:
            writer.execute(text("SET lock_timeout = '200ms'"))
            with pytest.raises(OperationalError, match="lock timeout"):
                _seed_on(writer, [_version(A, "late", "z" * 64)])
        holder.rollback()


def _seed_on(connection: Any, rows: list) -> None:
    tables = RcaBase.metadata.tables
    for table, values in rows:
        connection.execute(tables[table].insert().values(**values))


def test_the_repair_refuses_a_version_whose_upload_another_already_names(rls: RlsDatabase) -> None:
    """The unique identity index would refuse the write, and with it the scope's whole repair."""
    from khepri.runtime.upload_identity_repair import RepairOutcome, repair_scope

    rls.seed(_uploaded(A, "shared", "d" * 64))
    _seed(
        rls.owner,
        rca=_scope_rows(A)
        + [
            _version(A, "named", "d" * 64, upload_id="upl_shared"),
            _version(A, "second", "d" * 64),
            _version(A, "late", "l" * 64),
        ],
        rra=_uploaded(A, "late", "l" * 64),
    )

    outcome = repair_scope(rls.factory(APPLICATION), A.owner_id)

    assert outcome == RepairOutcome(filled=1, refused=1)
    identities = _identities(rls.owner)
    assert (identities["ver_named"], identities["ver_second"]) == ("upl_shared", None)
    assert identities["ver_late"] == "upl_late"


def test_the_repair_refuses_two_old_writes_of_one_upload_and_goes_on(rls: RlsDatabase) -> None:
    """Old code arbitrated retries on the dropped digest index, so it can leave two null versions
    for one upload. Filling both would clash; filling one would pick an owner. Both are refused,
    and the next scope is still repaired."""
    from khepri.runtime.upload_identity_repair import RepairOutcome, repair_upload_identity

    rls.seed([*_uploaded(A, "twice", "w" * 64), *_uploaded(B, "late_b", "q" * 64)])
    _seed(
        rls.owner,
        rca=_scope_rows(A)
        + _scope_rows(B)
        + [
            _version(A, "first_write", "w" * 64),
            _version(A, "second_write", "w" * 64),
            _version(B, "late_b", "q" * 64),
        ],
        rra=[],
    )

    outcome = repair_upload_identity(rls.factory(APPLICATION))

    assert outcome == RepairOutcome(filled=1, refused=2)
    assert _identities(rls.owner) == {
        "ver_first_write": None,
        "ver_second_write": None,
        "ver_late_b": "upl_late_b",
    }
