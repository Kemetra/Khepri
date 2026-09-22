"""The workspace row locks, observed on PostgreSQL (`#529` T-07; `W1-02`, `RCA-005` `FR-111`).

`test_w102_workspace_locks.py` proves each lock by compiling its statement and by finding
`run_for_update(...)` in the method's source -- the honest maximum on SQLite, which emits no
`FOR UPDATE`. A source match cannot tell a lock that is taken from one that is written and never
executed. These tests watch the lock itself: each method runs inside an open workspace unit of
work (`unit_of_work`), so its transaction is still open when it returns, and a second connection
then asks for the same row with `NOWAIT`. A held lock refuses at once with `lock_not_available`;
a removed one lets the probe through.

**Deterministic, so one run is evidence.** Nothing here races: the first transaction holds the
lock by construction before the probe is issued, so there is no interleaving to get lucky with,
and the contention-repeat rule `test_rca001_concurrent_final_owner.py` follows does not apply.

**The probe is `FOR NO KEY UPDATE NOWAIT`, not `FOR UPDATE NOWAIT`.** Both conflict with the
`FOR UPDATE` these methods take. The narrower one does *not* conflict with the `FOR KEY SHARE`
PostgreSQL takes on a parent row when a child row referencing it is inserted, so an add path
whose insert had been flushed still could not pass this test on the foreign key's lock alone.
Each transition is also driven down the path that writes nothing (a repeat), so no `UPDATE`
can supply the lock either -- only the method's own `SELECT ... FOR UPDATE` can.

Marked `concurrency`, so CI runs them against its PostgreSQL service and fails if they skip (see
`.github/scripts/require_concurrency_tests.py`). Locally they skip when
`KHEPRI_TEST_DATABASE_URL` is unset.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import Base, SqlAccountStore, SqlOrganizationStore
from khepri.rca.workspace.contracts import (
    RUN_FAILED,
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
    RunOutcome,
)
from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore
from khepri.rca.workspace.schema import RETENTION_ACTIVE
from khepri.rca.workspace.unit_of_work import unit_of_work

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
CREDENTIAL = "correct horse battery staple"
#: PostgreSQL's SQLSTATE for `NOWAIT` meeting a held row lock.
LOCK_NOT_AVAILABLE = "55P03"

SOURCE = AdmittedSource(
    plaintext_digest="sha256:" + "a" * 64,
    ciphertext_digest="sha256:" + "b" * 64,
    size_bytes=2048,
    media_type="text/csv",
    manifest_digest="sha256:" + "c" * 64,
    mapping_version="rra003.mapping.v3",
    admission_outcome="admitted",
)

pytestmark = pytest.mark.concurrency

DATABASE_URL = os.environ.get("KHEPRI_TEST_DATABASE_URL")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason="KHEPRI_TEST_DATABASE_URL is unset; a row lock is only observable on PostgreSQL",
)


@pytest.fixture(name="factory")
def factory_fixture():
    """A PostgreSQL session factory whose sessions get independent connections.

    Deliberately not `StaticPool`: the default `QueuePool` hands the probe its own connection,
    which is the property every test in this file depends on.
    """
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _scope(factory: sessionmaker) -> str:
    """One organization's opaque isolation scope, through the real services."""
    account = AccountService(SqlAccountStore(factory)).create_account(
        "owner@example.test", CREDENTIAL
    )
    organizations = SqlOrganizationStore(factory)
    organization = OrganizationService(organizations).create_organization(
        "Acme Pharmacy", account.account_id, now=NOW
    )
    scope = organizations.get_scope(organization.organization_id)
    assert scope is not None
    return scope.owner_id


def _version(store: SqlWorkspaceRecordStore, scope: str) -> DatasetVersion:
    return store.add_dataset_version(DatasetVersion.create(owner_id=scope, source=SOURCE, now=NOW))


def _run(store: SqlWorkspaceRecordStore, scope: str) -> AnalysisRun:
    version = _version(store, scope)
    return store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )


@dataclass(frozen=True)
class Row:
    """One row, named the way the probe's SQL needs it."""

    table: str
    key: str
    value: str


def _run_row(run_id: str) -> Row:
    return Row("rca_workspace_analysis_runs", "run_id", run_id)


def _version_row(version_id: str) -> Row:
    return Row("rca_workspace_dataset_versions", "version_id", version_id)


def _probe(factory: sessionmaker, row: Row) -> None:
    """Ask for the row from a second connection, refusing to wait. Raises if it is locked."""
    with factory.kw["bind"].connect() as connection:
        try:
            connection.execute(
                text(
                    f"SELECT 1 FROM {row.table} WHERE {row.key} = :value FOR NO KEY UPDATE NOWAIT"
                ),
                {"value": row.value},
            )
        finally:
            connection.rollback()


def _assert_locked_until_commit(factory: sessionmaker, row: Row, perform) -> None:
    """`perform` inside an open unit of work holds the row; after the commit it is free."""
    with unit_of_work(factory):
        perform()
        with pytest.raises(OperationalError) as refused:
            _probe(factory, row)
        assert getattr(refused.value.orig, "sqlstate", None) == LOCK_NOT_AVAILABLE
    # The control: the same probe succeeds once the transaction ends, so the refusal above was
    # the method's lock and not a probe that fails for some other reason.
    _probe(factory, row)


@requires_postgres
def test_complete_analysis_run_holds_the_run_row(factory) -> None:
    store = SqlWorkspaceRecordStore(factory)
    scope = _scope(factory)
    run = _run(store, scope)
    assert store.complete_analysis_run(run.run_id, RunOutcome(state=RUN_FAILED), owner_id=scope)

    def repeat() -> None:
        assert not store.complete_analysis_run(
            run.run_id, RunOutcome(state=RUN_FAILED), owner_id=scope
        )

    _assert_locked_until_commit(factory, _run_row(run.run_id), repeat)


@requires_postgres
def test_set_retention_state_holds_the_version_row(factory) -> None:
    store = SqlWorkspaceRecordStore(factory)
    scope = _scope(factory)
    version = _version(store, scope)

    def repeat() -> None:
        # The idempotent retry: the row already holds this state, so nothing is written.
        store.set_retention_state(version.version_id, RETENTION_ACTIVE, now=LATER, owner_id=scope)

    _assert_locked_until_commit(factory, _version_row(version.version_id), repeat)


@requires_postgres
def test_seal_dataset_version_holds_the_version_row(factory) -> None:
    store = SqlWorkspaceRecordStore(factory)
    scope = _scope(factory)
    version = _version(store, scope)
    assert store.seal_dataset_version(version.version_id, now=NOW, owner_id=scope)

    def repeat() -> None:
        assert not store.seal_dataset_version(version.version_id, now=LATER, owner_id=scope)

    _assert_locked_until_commit(factory, _version_row(version.version_id), repeat)


@requires_postgres
def test_add_analysis_run_holds_its_parent_version(factory) -> None:
    store = SqlWorkspaceRecordStore(factory)
    scope = _scope(factory)
    version = _version(store, scope)

    def add() -> None:
        store.add_analysis_run(
            AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
        )

    _assert_locked_until_commit(factory, _version_row(version.version_id), add)


@requires_postgres
def test_add_artifact_binding_holds_its_parent_run(factory) -> None:
    store = SqlWorkspaceRecordStore(factory)
    scope = _scope(factory)
    run = _run(store, scope)

    def add() -> None:
        store.add_artifact_binding(
            ArtifactBinding.create(
                owner_id=scope,
                run_id=run.run_id,
                artifact=PublishedArtifact(surface="web", artifact_digest="sha256:" + "d" * 64),
                now=NOW,
            )
        )

    _assert_locked_until_commit(factory, _run_row(run.run_id), add)
