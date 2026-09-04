"""The `W1-02` store's transitions: sealing, completion, and the retention clock.

Split from `test_w102_workspace_persistence.py` on `#370`, which had grown to hold both what the
store persists and reads and what it *changes*. Each transition here is one-way, refuses a repeat
rather than moving an instant, and is narrowed by scope -- the properties `FR-111`, `FR-112` and
`KHEPRI-DEC-033` §5 ask for, tested on the store rather than on the guard.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore, _utc
from khepri.rca.workspace.contracts import (
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
    RunOutcome,
)
from khepri.rca.workspace.persistence import (
    COMPLETION_COLUMNS,
    RETENTION_TOMBSTONED,
    AnalysisRunRow,
    DatasetVersionRow,
    SqlWorkspaceRecordStore,
)
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    factory_fixture,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)

SOURCE = AdmittedSource(
    plaintext_digest="sha256:" + "a" * 64,
    ciphertext_digest="sha256:" + "b" * 64,
    size_bytes=2048,
    media_type="text/csv",
    manifest_digest="sha256:" + "c" * 64,
    mapping_version="rra003.mapping.v3",
    admission_outcome="admitted",
)

WORKSPACE_TABLES = (
    "rca_workspace_dataset_versions",
    "rca_workspace_analysis_runs",
    "rca_workspace_artifact_bindings",
    "rca_workspace_source_profiles",
    "rca_workspace_tombstones",
)


def _scope(factory: sessionmaker, email: str = EMAIL, name: str = "Acme Pharmacy") -> str:
    """One organization, returning the opaque isolation scope every workspace row is keyed by.

    Built through the real service rather than by inserting a row, because the workspace tables
    carry a foreign key onto `rca_isolation_scopes.owner_id` and a hand-made scope would not
    satisfy it -- which is the constraint several tests here are about.

    Parameterized by email so an isolation test can raise a *second* scope, which is the only way
    to see a missing `WHERE`: with one organization's rows in the table, an unfiltered query
    returns exactly what a filtered one does.
    """
    accounts = SqlAccountStore(factory)
    account = AccountService(accounts).create_account(email, CREDENTIAL)
    organizations = SqlOrganizationStore(factory)
    organization = OrganizationService(organizations).create_organization(
        name, account.account_id, now=NOW
    )
    scope = organizations.get_scope(organization.organization_id)
    assert scope is not None, "creating an organization allocates its isolation scope"
    return scope.owner_id


def _version(store: SqlWorkspaceRecordStore, scope: str) -> DatasetVersion:
    return store.add_dataset_version(DatasetVersion.create(owner_id=scope, source=SOURCE, now=NOW))


def _started_run(store: SqlWorkspaceRecordStore, scope: str) -> AnalysisRun:
    version = _version(store, scope)
    return store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )


COMPLETED_OUTCOME = RunOutcome(
    state="completed",
    package_digest="sha256:" + "c" * 64,
    package_version="rra008.package.v2",
    formula_version="rra004.formula.v5",
    completed_at=LATER,
)


# --- Sealing, completion, and the clock that must not move --------------------------------


def test_a_version_can_be_sealed_once(factory: sessionmaker) -> None:
    """`W1-01` made sealing an event rather than a creation argument, and nothing performed it.

    Two of its tests assert `create` has no `sealed_at` parameter, which is right -- but no
    operation ever set the column, so every stored version stayed unsealed and
    `KHEPRI-DEC-033`'s seven-day raw-upload purge clock could never start. Review on `#370` found
    the missing half of a transition this repository had already reasoned about carefully.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)

    assert version.sealed_at is None
    assert store.seal_dataset_version(version.version_id, now=LATER) is True

    sealed = store.get_dataset_version(version.version_id)
    assert sealed is not None
    assert sealed.sealed_at == LATER


def test_sealing_twice_is_refused_rather_than_moving_the_instant(factory: sessionmaker) -> None:
    """The purge clock starts at the first sealing, so a second must not extend it.

    Re-sealing would push a deletion deadline outward, which is the one direction
    `KHEPRI-DEC-033` cannot tolerate -- an object staying retrievable longer than the decision
    allows. Asserted on both the return value and the stored instant, because a method that
    returned `False` while still writing would pass a return-only test.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)
    store.seal_dataset_version(version.version_id, now=NOW)

    assert store.seal_dataset_version(version.version_id, now=LATER) is False

    sealed = store.get_dataset_version(version.version_id)
    assert sealed is not None
    assert sealed.sealed_at == NOW


def test_a_foreign_scope_cannot_seal_a_version(factory: sessionmaker) -> None:
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")
    store = SqlWorkspaceRecordStore(factory)
    mine = store.add_dataset_version(DatasetVersion.create(owner_id=first, source=SOURCE, now=NOW))

    assert store.seal_dataset_version(mine.version_id, now=LATER, owner_id=second) is False

    unsealed = store.get_dataset_version(mine.version_id)
    assert unsealed is not None
    assert unsealed.sealed_at is None


def test_sealing_changes_nothing_else_about_the_record(factory: sessionmaker) -> None:
    """Sealing is one column. A transition that rewrote content would defeat `FR-112` from the
    inside -- through the one operation permitted to write."""
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)
    store.seal_dataset_version(version.version_id, now=LATER)

    sealed = store.get_dataset_version(version.version_id)
    assert sealed is not None

    # Compared field by field rather than through `dataclasses.replace`, which `records.py`
    # refuses on a sealed record -- correctly: substitution is one of the construction bypasses it
    # exists to close, and a test may not open it to make an assertion convenient.
    unchanged = {field.name for field in fields(DatasetVersion) if field.name != "sealed_at"}
    for name in unchanged:
        assert getattr(sealed, name) == getattr(version, name), name


def test_a_started_run_can_record_what_it_produced(factory: sessionmaker) -> None:
    """The defect this closes: a run written through this store could never be completed.

    `W1-01` creates a run incomplete on purpose, because `FR-111` puts the digest and the governed
    versions on the real pipeline. The append-only guard then refused every write that would fill
    them, so the record had fields no operation could ever set -- `FR-112` enforced as "after
    writing" where its text says "after sealing or completion". Review on `#370` found it.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    run = _started_run(store, scope)

    assert store.complete_analysis_run(run.run_id, COMPLETED_OUTCOME) is True

    completed = store.get_analysis_run(run.run_id)
    assert completed is not None
    assert completed.state == "completed"
    assert completed.package_digest == COMPLETED_OUTCOME.package_digest
    assert completed.package_version == COMPLETED_OUTCOME.package_version
    assert completed.formula_version == COMPLETED_OUTCOME.formula_version
    assert completed.completed_at == LATER


def test_a_run_can_also_record_that_it_failed(factory: sessionmaker) -> None:
    """`failed` is a terminal state the domain publishes, so it is a completion like any other."""
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    run = _started_run(store, scope)

    assert store.complete_analysis_run(run.run_id, RunOutcome(state="failed")) is True

    failed = store.get_analysis_run(run.run_id)
    assert failed is not None
    assert failed.state == "failed"
    assert failed.package_digest is None


def test_completing_twice_is_refused(factory: sessionmaker) -> None:
    """One way, like sealing: a completed run does not re-derive a different result."""
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    run = _started_run(store, scope)
    store.complete_analysis_run(run.run_id, COMPLETED_OUTCOME)

    other = RunOutcome(state="failed", completed_at=LATER)
    assert store.complete_analysis_run(run.run_id, other) is False

    unchanged = store.get_analysis_run(run.run_id)
    assert unchanged is not None
    assert unchanged.state == "completed"
    assert unchanged.package_digest == COMPLETED_OUTCOME.package_digest


def test_a_completed_run_is_immutable_through_the_orm_too(factory: sessionmaker) -> None:
    """The store returning `False` is politeness; the guard refusing the write is the property.

    Asserted through a loaded row rather than only through the method, for the reason the sealing
    equivalent is: an earlier version of this module had a path that wrote around the guard, and a
    return-value test cannot see one.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    run = _started_run(store, scope)
    store.complete_analysis_run(run.run_id, COMPLETED_OUTCOME)

    with (
        pytest.raises(ValueError, match="cannot be completed again"),
        factory.begin() as database,
    ):
        row = database.get(AnalysisRunRow, run.run_id)
        row.package_digest = "sha256:" + "0" * 64


def test_completion_cannot_smuggle_a_content_change(factory: sessionmaker) -> None:
    """The transition writes its own columns and no others.

    A completion permitted to touch `version_id` would rewrite which dataset a run derived from --
    provenance, changed through the one write the guard allows. `COMPLETION_COLUMNS` is asserted
    as an equality for the same reason `MUTABLE_COLUMNS` is.
    """
    assert {
        "state",
        "package_digest",
        "package_version",
        "formula_version",
        "completed_at",
    } == COMPLETION_COLUMNS

    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    run = _started_run(store, scope)

    with (
        pytest.raises(ValueError, match="cannot change after it is written"),
        factory.begin() as database,
    ):
        row = database.get(AnalysisRunRow, run.run_id)
        row.state = "completed"
        row.version_id = "dsv_somewhere_else"


def test_a_foreign_scope_cannot_complete_a_run(factory: sessionmaker) -> None:
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")
    store = SqlWorkspaceRecordStore(factory)
    run = _started_run(store, first)

    assert store.complete_analysis_run(run.run_id, COMPLETED_OUTCOME, owner_id=second) is False

    untouched = store.get_analysis_run(run.run_id)
    assert untouched is not None
    assert untouched.state == "started"


def test_completing_into_the_started_state_is_refused(factory: sessionmaker) -> None:
    """`started` is not a completion, so passing it is a caller error rather than a no-op."""
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    run = _started_run(store, scope)

    with pytest.raises(ValueError, match="cannot be completed again"):
        store.complete_analysis_run(run.run_id, RunOutcome(state="started"))


def test_an_idempotent_tombstone_does_not_move_the_deletion_clock(
    factory: sessionmaker,
) -> None:
    """`FR-123` requires a repeated deletion to succeed; `KHEPRI-DEC-033` §5 anchors a horizon to
    `retention_changed_at`. Both, so a retry must succeed *without* moving the clock.

    Overwriting the timestamp on every retry would let repeated requests extend a deletion deadline
    outward -- the same defect re-sealing was guarded against, arriving through the timestamp
    instead of the state. The guard could not see it: assigning an equal value is not a change, so
    `_one_way` has nothing to refuse. Review on `#370` found it.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)

    store.tombstone_dataset_version(version.version_id, now=NOW)
    with factory() as database:
        first = database.get(DatasetVersionRow, version.version_id).retention_changed_at

    store.tombstone_dataset_version(version.version_id, now=LATER)
    with factory() as database:
        after_retry = database.get(DatasetVersionRow, version.version_id).retention_changed_at

    assert first is not None
    assert after_retry == first, "an idempotent retry moved the deletion clock"


def test_a_real_transition_does_move_the_clock(factory: sessionmaker) -> None:
    """The no-op check must not have frozen the timestamp for an actual state change."""
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)

    with factory() as database:
        assert database.get(DatasetVersionRow, version.version_id).retention_changed_at is None

    store.tombstone_dataset_version(version.version_id, now=LATER)

    # Compared through `_utc` because SQLite hands back a naive datetime; the store applies it on
    # every read path and this test reads the raw row to see the column rather than the record.
    with factory() as database:
        stored = database.get(DatasetVersionRow, version.version_id).retention_changed_at
    assert _utc(stored) == LATER


# --- A version's deletion cascades to every derivative below (`KHEPRI-DEC-033` §3) ----------------


def test_tombstoning_a_version_tombstones_its_live_runs(factory: sessionmaker) -> None:
    """A run that existed *before* the deletion kept `active` and stayed readable, completable and
    able to receive bindings while its source version was gone. `add_analysis_run`'s parent check
    covered only runs created after. Review on `#370` found the pre-existing case.

    Asserted through every door the run had: both reads, completion, and binding -- each now
    behaves as it does for any tombstoned run, because it *is* one. An unrelated version's run is
    untouched, so the cascade is by parent and not by scope.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    deleted = _version(store, scope)
    other = _version(store, scope)
    doomed = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=deleted.version_id, now=NOW)
    )
    spared = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=other.version_id, now=NOW)
    )

    store.tombstone_dataset_version(deleted.version_id, now=LATER)

    assert store.get_analysis_run(doomed.run_id) is None
    assert [run.run_id for run in store.analysis_runs_for_scope(scope)] == [spared.run_id]
    with pytest.raises(ValueError, match="accepts no further update"):
        store.complete_analysis_run(
            doomed.run_id,
            RunOutcome(
                state="completed",
                package_digest="sha256:abc",
                package_version="1.0.0",
                formula_version="1.0.0",
                completed_at=LATER,
            ),
        )
    with pytest.raises(ValueError, match="has been deleted"):
        store.add_artifact_binding(
            ArtifactBinding.create(
                owner_id=scope,
                run_id=doomed.run_id,
                artifact=PublishedArtifact(surface="web", artifact_digest="sha256:" + "c" * 64),
                now=LATER,
            )
        )
    with factory() as database:
        row = database.get(AnalysisRunRow, doomed.run_id)
        assert row.retention_state == RETENTION_TOMBSTONED
        assert _utc(row.retention_changed_at) == LATER, (
            "a cascaded run's clock is the deletion instant"
        )


def test_the_cascade_skips_a_run_already_tombstoned(factory: sessionmaker) -> None:
    """Only *live* runs are cascaded, and not as an optimisation.

    `_check_terminal_state` refuses every update to a tombstoned row, so a run already tombstoned
    on its own would make the whole cascade raise -- and roll back the version's deletion with it.
    The filter is what keeps the cascade able to run at all; this test is what keeps the filter.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)
    earlier = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    later = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    with factory.begin() as database:
        row = database.get(AnalysisRunRow, earlier.run_id)
        row.retention_state = RETENTION_TOMBSTONED
        row.retention_changed_at = NOW

    store.tombstone_dataset_version(version.version_id, now=LATER)

    with factory() as database:
        assert database.get(DatasetVersionRow, version.version_id).retention_state == (
            RETENTION_TOMBSTONED
        )
        assert database.get(AnalysisRunRow, later.run_id).retention_state == RETENTION_TOMBSTONED
        # The run tombstoned earlier keeps its own clock; the cascade did not touch it.
        assert _utc(database.get(AnalysisRunRow, earlier.run_id).retention_changed_at) == NOW


def test_a_repeated_version_deletion_does_not_move_a_cascaded_runs_clock(
    factory: sessionmaker,
) -> None:
    """`FR-123`'s idempotent retry, one level down: the second call returns at the version and the
    cascade does not run again, so no child clock moves either."""
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    much_later = LATER.replace(hour=LATER.hour + 5)

    store.tombstone_dataset_version(version.version_id, now=LATER)
    store.tombstone_dataset_version(version.version_id, now=much_later)

    with factory() as database:
        assert _utc(database.get(AnalysisRunRow, run.run_id).retention_changed_at) == LATER
