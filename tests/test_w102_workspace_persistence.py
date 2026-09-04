"""`W1-02`: the workspace tables and their store (`RCA-005` `FR-109`--`FR-113`).

`W1-01` wrote the domain contracts and deliberately held no persistence. This module asserts what
the schema is, which is a different property from what the dataclass is: a column can be added to a
table without touching a record, and `test_w101_workspace_contracts.py`'s field-set equalities would
stay green through it. So every structural assertion here reads the **emitted schema** through
`inspect(...)` rather than the model's fields.

`FR-113` -- one Alembic head -- is asserted where it already lives, in
`test_rca001_session_persistence.py`, whose pinned revision this slice updates rather than
duplicates. A second head test would be a second place to forget.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
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
    RETENTION_ACTIVE,
    RETENTION_TOMBSTONED,
    SECTION_COLUMNS,
    TOMBSTONE_SUBJECTS,
    AnalysisRunRow,
    DatasetVersionRow,
    SourceProfileRow,
    SqlWorkspaceStore,
    WorkspaceTombstoneRow,
    run_for_update,
    version_for_update,
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


def _version(store: SqlWorkspaceStore, scope: str) -> DatasetVersion:
    return store.add_dataset_version(DatasetVersion.create(owner_id=scope, source=SOURCE, now=NOW))


# --- FR-109: the schema is keyed by the opaque scope and names no customer -------------------


def test_every_workspace_table_exists(factory: sessionmaker) -> None:
    tables = set(inspect(factory.kw["bind"]).get_table_names())
    assert set(WORKSPACE_TABLES) <= tables


@pytest.mark.parametrize("table", WORKSPACE_TABLES)
def test_no_workspace_table_names_a_commercial_identifier(
    factory: sessionmaker, table: str
) -> None:
    """`FR-109` asks for a test over the *tables*, not over the records.

    `RCA-001` `FR-033` forbids a commercial identifier appearing in or being derivable from the
    isolation key. A column called `email`, `organization_name` or `slug` would be that identifier
    arriving by another name, and it could be added to a table without touching any dataclass --
    so `test_w101_workspace_contracts.py`'s field-set equalities cannot see it. This reads the
    emitted schema.
    """
    forbidden = {
        "email",
        "organization_name",
        "organisation_name",
        "name",
        "slug",
        "display_name",
        "company",
        "organization_id",
    }
    columns = {column["name"] for column in inspect(factory.kw["bind"]).get_columns(table)}
    assert columns & forbidden == set(), f"{table} names a commercial identifier"


@pytest.mark.parametrize("table", WORKSPACE_TABLES)
def test_every_workspace_table_is_keyed_by_the_opaque_scope(
    factory: sessionmaker, table: str
) -> None:
    """Every row carries `owner_id`, and it is a foreign key onto the isolation scope.

    A bare column would let a caller write any string; the constraint is what makes the scope a
    key rather than a label.
    """
    columns = {column["name"] for column in inspect(factory.kw["bind"]).get_columns(table)}
    assert "owner_id" in columns

    targets = {
        (constraint["referred_table"], tuple(constraint["referred_columns"]))
        for constraint in inspect(factory.kw["bind"]).get_foreign_keys(table)
    }
    assert ("rca_isolation_scopes", ("owner_id",)) in targets


def test_a_row_cannot_name_a_scope_that_does_not_exist(factory: sessionmaker) -> None:
    """The foreign key is enforced, not merely declared.

    Asserted by writing rather than by reading the constraint, because a declared constraint that
    the engine does not enforce is the shape `build_factory`'s `PRAGMA foreign_keys=ON` exists to
    prevent -- and a test that only read the declaration would pass with the pragma removed.
    """
    store = SqlWorkspaceStore(factory)
    with pytest.raises(IntegrityError):
        store.add_dataset_version(
            DatasetVersion.create(owner_id="own_never_provisioned", source=SOURCE, now=NOW)
        )


# --- FR-110 / FR-111: what a row preserves ---------------------------------------------------


def test_a_dataset_version_round_trips_through_the_store(factory: sessionmaker) -> None:
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    written = _version(store, scope)

    read = store.get_dataset_version(written.version_id)

    assert read is not None
    assert read == written


def test_a_dataset_version_preserves_its_admission(factory: sessionmaker) -> None:
    """`FR-110`: the row records the outcome and mapping version it was admitted under.

    Asserted field by field rather than by equality alone, because an equality against a record
    this test also built would pass if both sides dropped the same field.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    read = store.get_dataset_version(_version(store, scope).version_id)

    assert read is not None
    assert read.admission_outcome == "admitted"
    assert read.mapping_version == "rra003.mapping.v3"
    assert read.manifest_digest == SOURCE.manifest_digest
    assert read.upload_plaintext_digest == SOURCE.plaintext_digest
    assert read.upload_ciphertext_digest == SOURCE.ciphertext_digest
    assert read.upload_size_bytes == 2048


def test_an_analysis_run_round_trips_and_names_its_version(factory: sessionmaker) -> None:
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    written = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    read = store.get_analysis_run(written.run_id)

    assert read is not None
    assert read == written
    assert read.version_id == version.version_id
    assert read.package_digest is None


def test_a_run_cannot_name_a_dataset_version_that_does_not_exist(factory: sessionmaker) -> None:
    """`FR-111`: a run is a derivation *over a version*, so an orphan run is not a run."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    with pytest.raises(IntegrityError):
        store.add_analysis_run(
            AnalysisRun.create(owner_id=scope, version_id="dsv_never_written", now=NOW)
        )


def test_an_artifact_binding_round_trips_and_binds_by_digest(factory: sessionmaker) -> None:
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )

    digest = "sha256:" + "d" * 64
    written = store.add_artifact_binding(
        ArtifactBinding.create(
            owner_id=scope,
            run_id=run.run_id,
            artifact=PublishedArtifact(surface="web", artifact_digest=digest),
            now=NOW,
        )
    )
    read = store.artifact_bindings_for_run(run.run_id)

    assert read == (written,)
    assert read[0].artifact_digest == digest


def test_a_binding_cannot_name_a_run_that_does_not_exist(factory: sessionmaker) -> None:
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    with pytest.raises(IntegrityError):
        store.add_artifact_binding(
            ArtifactBinding.create(
                owner_id=scope,
                run_id="run_never_written",
                artifact=PublishedArtifact(surface="web", artifact_digest="sha256:" + "e" * 64),
                now=NOW,
            )
        )


# --- Isolation: one scope never reads another's rows -----------------------------------------


def test_listing_is_scoped_and_returns_newest_first(factory: sessionmaker) -> None:
    """`FR-109` isolation, asserted by writing two scopes and reading one.

    A single-scope test cannot see a missing `WHERE`: with one organization's rows in the table,
    an unfiltered query returns exactly the same result as a filtered one.
    """
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")

    store = SqlWorkspaceStore(factory)
    mine_early = store.add_dataset_version(
        DatasetVersion.create(owner_id=first, source=SOURCE, now=NOW)
    )
    mine_late = store.add_dataset_version(
        DatasetVersion.create(owner_id=first, source=SOURCE, now=LATER)
    )
    store.add_dataset_version(DatasetVersion.create(owner_id=second, source=SOURCE, now=NOW))

    listed = store.dataset_versions_for_scope(first)

    assert [version.version_id for version in listed] == [
        mine_late.version_id,
        mine_early.version_id,
    ]


def test_runs_are_listed_only_within_their_own_scope(factory: sessionmaker) -> None:
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")

    store = SqlWorkspaceStore(factory)
    mine = store.add_dataset_version(DatasetVersion.create(owner_id=first, source=SOURCE, now=NOW))
    theirs = store.add_dataset_version(
        DatasetVersion.create(owner_id=second, source=SOURCE, now=NOW)
    )
    store.add_analysis_run(AnalysisRun.create(owner_id=first, version_id=mine.version_id, now=NOW))
    store.add_analysis_run(
        AnalysisRun.create(owner_id=second, version_id=theirs.version_id, now=NOW)
    )

    assert len(store.analysis_runs_for_scope(first)) == 1
    assert len(store.analysis_runs_for_scope(second)) == 1


def test_a_foreign_scope_reads_nothing_by_identifier(factory: sessionmaker) -> None:
    """Reading by identifier is scoped too, or an identifier leak becomes a data leak."""
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")

    store = SqlWorkspaceStore(factory)
    mine = store.add_dataset_version(DatasetVersion.create(owner_id=first, source=SOURCE, now=NOW))

    assert store.get_dataset_version(mine.version_id, owner_id=second) is None
    assert store.get_dataset_version(mine.version_id, owner_id=first) == mine


# --- Every read narrows by scope, asserted over the API rather than one example ---------------


SCOPED_READS = (
    "get_dataset_version",
    "get_analysis_run",
    "artifact_bindings_for_run",
    "retention_state",
    "set_retention_state",
    "tombstone_dataset_version",
)


@pytest.mark.parametrize("method_name", SCOPED_READS)
def test_every_scoped_method_accepts_an_owner(method_name: str) -> None:
    """Asserted over the named set rather than one hand-picked method.

    `test_a_foreign_scope_reads_nothing_by_identifier` proved the property for
    `get_dataset_version` alone, and three other methods took no `owner_id` at all -- the module
    stating one isolation rule and implementing it in half its reads, which review on `#370`
    caught. A per-method assertion is what makes the *next* unscoped read fail rather than pass
    unnoticed.
    """
    import inspect as py_inspect

    signature = py_inspect.signature(getattr(SqlWorkspaceStore, method_name))
    assert "owner_id" in signature.parameters, f"{method_name} cannot be narrowed by scope"


def test_a_foreign_scope_cannot_read_or_change_retention(factory: sessionmaker) -> None:
    """Reading and writing retention are both scoped.

    **A foreign-scope write returns silently rather than raising**, matching what the method
    already does for a version that does not exist: from the caller's side those are the same
    answer -- no such row here -- and distinguishing them would confirm that an identifier from
    another scope is real. `W1-04` decides what a *user* is told; this is a filter, not a grant.
    """
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")
    store = SqlWorkspaceStore(factory)
    mine = store.add_dataset_version(DatasetVersion.create(owner_id=first, source=SOURCE, now=NOW))

    assert store.retention_state(mine.version_id, owner_id=second) is None
    assert store.retention_state(mine.version_id, owner_id=first) == RETENTION_ACTIVE

    store.tombstone_dataset_version(mine.version_id, now=LATER, owner_id=second)
    assert store.retention_state(mine.version_id, owner_id=first) == RETENTION_ACTIVE

    store.tombstone_dataset_version(mine.version_id, now=LATER, owner_id=first)
    assert store.retention_state(mine.version_id, owner_id=first) == RETENTION_TOMBSTONED


def test_a_foreign_scope_lists_none_of_another_scopes_bindings(factory: sessionmaker) -> None:
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")
    store = SqlWorkspaceStore(factory)
    version = _version(store, first)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=first, version_id=version.version_id, now=NOW)
    )
    store.add_artifact_binding(
        ArtifactBinding.create(
            owner_id=first,
            run_id=run.run_id,
            artifact=PublishedArtifact(surface="web", artifact_digest="sha256:" + "7" * 64),
            now=NOW,
        )
    )

    assert store.artifact_bindings_for_run(run.run_id, owner_id=second) == ()
    assert len(store.artifact_bindings_for_run(run.run_id, owner_id=first)) == 1


# --- Sealing, the transition `W1-01` defined and nothing performed ----------------------------


def test_a_version_can_be_sealed_once(factory: sessionmaker) -> None:
    """`W1-01` made sealing an event rather than a creation argument, and nothing performed it.

    Two of its tests assert `create` has no `sealed_at` parameter, which is right -- but no
    operation ever set the column, so every stored version stayed unsealed and
    `KHEPRI-DEC-033`'s seven-day raw-upload purge clock could never start. Review on `#370` found
    the missing half of a transition this repository had already reasoned about carefully.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
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
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    store.seal_dataset_version(version.version_id, now=NOW)

    assert store.seal_dataset_version(version.version_id, now=LATER) is False

    sealed = store.get_dataset_version(version.version_id)
    assert sealed is not None
    assert sealed.sealed_at == NOW


def test_a_foreign_scope_cannot_seal_a_version(factory: sessionmaker) -> None:
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")
    store = SqlWorkspaceStore(factory)
    mine = store.add_dataset_version(DatasetVersion.create(owner_id=first, source=SOURCE, now=NOW))

    assert store.seal_dataset_version(mine.version_id, now=LATER, owner_id=second) is False

    unsealed = store.get_dataset_version(mine.version_id)
    assert unsealed is not None
    assert unsealed.sealed_at is None


def test_sealing_changes_nothing_else_about_the_record(factory: sessionmaker) -> None:
    """Sealing is one column. A transition that rewrote content would defeat `FR-112` from the
    inside -- through the one operation permitted to write."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
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


# --- Completion: the transition `FR-111` requires and the guard had made impossible ------------


def _started_run(store: SqlWorkspaceStore, scope: str) -> AnalysisRun:
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


def test_a_started_run_can_record_what_it_produced(factory: sessionmaker) -> None:
    """The defect this closes: a run written through this store could never be completed.

    `W1-01` creates a run incomplete on purpose, because `FR-111` puts the digest and the governed
    versions on the real pipeline. The append-only guard then refused every write that would fill
    them, so the record had fields no operation could ever set -- `FR-112` enforced as "after
    writing" where its text says "after sealing or completion". Review on `#370` found it.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
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
    store = SqlWorkspaceStore(factory)
    run = _started_run(store, scope)

    assert store.complete_analysis_run(run.run_id, RunOutcome(state="failed")) is True

    failed = store.get_analysis_run(run.run_id)
    assert failed is not None
    assert failed.state == "failed"
    assert failed.package_digest is None


def test_completing_twice_is_refused(factory: sessionmaker) -> None:
    """One way, like sealing: a completed run does not re-derive a different result."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
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
    store = SqlWorkspaceStore(factory)
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
    store = SqlWorkspaceStore(factory)
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
    store = SqlWorkspaceStore(factory)
    run = _started_run(store, first)

    assert store.complete_analysis_run(run.run_id, COMPLETED_OUTCOME, owner_id=second) is False

    untouched = store.get_analysis_run(run.run_id)
    assert untouched is not None
    assert untouched.state == "started"


def test_completing_into_the_started_state_is_refused(factory: sessionmaker) -> None:
    """`started` is not a completion, so passing it is a caller error rather than a no-op."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    run = _started_run(store, scope)

    with pytest.raises(ValueError, match="cannot be completed again"):
        store.complete_analysis_run(run.run_id, RunOutcome(state="started"))


# --- The two tables the `W1-02` plan assigns and the first draft omitted -----------------------


def test_the_slice_delivers_every_table_its_plan_assigns() -> None:
    """The `W1-02` plan names five tables; the first draft of this slice delivered three.

    Review on `#370` found it against
    `docs/superpowers/plans/2026-09-03-g3-04-workspace-implementation-plan.md`, which assigns
    "tables for dataset versions, runs, artifact bindings, source profiles and tombstones". I had
    argued on an earlier thread that the profile table belonged to `W1-04` because nothing reads
    it yet -- which confused "no consumer" with "no table". A persistence slice delivering storage
    ahead of its reader is the normal shape.

    Asserted against the emitted metadata rather than by listing names in prose, so a table
    dropped later fails here.
    """
    from khepri.rca.persistence import Base

    declared = {name for name in Base.metadata.tables if name.startswith("rca_workspace_")}
    assert declared == set(WORKSPACE_TABLES)


def test_a_source_profile_row_round_trips(factory: sessionmaker) -> None:
    scope = _scope(factory)
    version = _version(SqlWorkspaceStore(factory), scope)
    with factory.begin() as database:
        database.add(
            SourceProfileRow(
                profile_id="prf_abc123",
                owner_id=scope,
                source_version_id=version.version_id,
                column_labels='["date", "sku", "qty"]',
                proposed_mapping='[["date", "transaction_date"]]',
                created_at=NOW,
            )
        )

    with factory() as database:
        row = database.get(SourceProfileRow, "prf_abc123")
        assert row is not None
        assert row.owner_id == scope
        assert row.source_version_id == version.version_id


def test_a_source_profile_is_deletable(factory: sessionmaker) -> None:
    """The one workspace table exempt from the *delete* guard, and the exemption is the decision.

    `KHEPRI-DEC-033` §3's tombstone table gives a row to dataset versions and to runs, and for a
    source profile says **"none -- purged, not tombstoned"** -- because the live profile holds
    sanitized customer column headers and min/max values, none of which may survive. A blanket
    delete guard would have made the purge the decision prescribes impossible, which is the same
    shape as the guard that had made run completion impossible.

    **This test previously asserted the defect.** It was called "mutable and deletable" and it
    reassigned `source_version_id` to prove the point -- so the guard gap and the test agreeing
    with it arrived in the same commit, which is exactly the pair that cannot corroborate itself.
    Review on `#370` read §3 more carefully than I had: the exemption is from *deletion*, and it
    never extended to identity. `test_a_profile_cannot_be_repointed_at_another_version` is now the
    assertion this line used to contradict, and the document stays mutable under `FR-115` in
    `test_a_profile_document_is_still_mutable`.
    """
    scope = _scope(factory)
    version = _version(SqlWorkspaceStore(factory), scope)
    with factory.begin() as database:
        database.add(
            SourceProfileRow(
                profile_id="prf_mutable",
                owner_id=scope,
                source_version_id=version.version_id,
                column_labels="[]",
                proposed_mapping="[]",
                created_at=NOW,
            )
        )

    with factory.begin() as database:
        database.delete(database.get(SourceProfileRow, "prf_mutable"))

    with factory() as database:
        assert database.get(SourceProfileRow, "prf_mutable") is None


@pytest.mark.parametrize("subject", TOMBSTONE_SUBJECTS)
def test_a_tombstone_row_round_trips_for_each_subject(factory: sessionmaker, subject: str) -> None:
    scope = _scope(factory)
    with factory.begin() as database:
        database.add(
            WorkspaceTombstoneRow(
                tombstone_id=f"tmb_{subject}",
                subject_kind=subject,
                subject_id="dsv_abc123",
                owner_id=scope,
                deleted_at=LATER,
            )
        )

    with factory() as database:
        row = database.get(WorkspaceTombstoneRow, f"tmb_{subject}")
        assert row is not None
        assert row.subject_kind == subject


def test_a_tombstone_cannot_be_about_a_source_profile(factory: sessionmaker) -> None:
    """`KHEPRI-DEC-033` §3: a source profile is "none -- purged, not tombstoned".

    So there are deliberately two subjects and not three, and the `CHECK` says so rather than the
    comment alone. A `profile` tombstone would be sanitized customer headers surviving a deletion
    that was supposed to erase them.
    """
    scope = _scope(factory)

    with pytest.raises(IntegrityError), factory.begin() as database:
        database.add(
            WorkspaceTombstoneRow(
                tombstone_id="tmb_profile",
                subject_kind="profile",
                subject_id="prf_abc123",
                owner_id=scope,
                deleted_at=LATER,
            )
        )


def test_the_tombstone_columns_are_exactly_the_two_allowlists(factory: sessionmaker) -> None:
    """`KHEPRI-DEC-033` §3 defines a tombstone by what it **may** contain, never by what was
    removed -- so the column set is asserted as an equality against §3's two rows.

    `W1-03` builds the projection and writes the field-set equality test §3 promises against it.
    This asserts the *table* it will fill, which is what this slice owns: a column arriving here
    without an entry in §3 is content surviving a deletion, and the equality fails before the
    projection can carry it.
    """
    columns = {
        column["name"]
        for column in inspect(factory.kw["bind"]).get_columns("rca_workspace_tombstones")
    }

    identity = {"tombstone_id", "subject_kind", "subject_id", "owner_id", "deleted_at"}
    version_allowlist = {
        "version_id",
        "created_at",
        "sealed_at",
        "upload_plaintext_digest",
        "upload_ciphertext_digest",
        "upload_size_bytes",
        "upload_media_type",
        "manifest_digest",
        "mapping_version",
        "admission_outcome",
    }
    run_allowlist = {
        "started_at",
        "completed_at",
        "package_digest",
        "package_version",
        "formula_version",
        *SECTION_COLUMNS,
    }

    assert columns == identity | version_allowlist | run_allowlist


def test_no_tombstone_column_can_hold_free_text_from_the_live_record(
    factory: sessionmaker,
) -> None:
    """`KHEPRI-DEC-033` §3 names what never survives: filenames, column labels, values, manifest
    text, the mapping itself, figures, narrative and refusal prose.

    The live profile holds sanitized customer column headers and the coverage manifest holds free
    text (`attested_by`, `aggregate_scope`, exception notes). A column named for any of them here
    would be that content outliving the deletion that was meant to erase it.
    """
    forbidden = {
        "filename",
        "column_labels",
        "proposed_mapping",
        "attested_by",
        "aggregate_scope",
        "exception_notes",
        "narrative",
        "refusal_reason",
        "figures",
    }
    columns = {
        column["name"]
        for column in inspect(factory.kw["bind"]).get_columns("rca_workspace_tombstones")
    }

    assert columns & forbidden == set()


# --- Read-then-write windows, and a clock that must not move -----------------------------------


@pytest.mark.parametrize(
    ("statement", "table"),
    [
        (run_for_update("run_abc123"), "rca_workspace_analysis_runs"),
        (version_for_update("dsv_abc123"), "rca_workspace_dataset_versions"),
    ],
)
def test_the_locking_statements_emit_for_update_on_postgres(statement, table: str) -> None:
    """Compiled against the PostgreSQL dialect, because SQLite cannot show this.

    `rca/persistence.py` states the reason at `account_for_update`: SQLite emits no `FOR UPDATE`
    and SQLAlchemy silently omits it for that dialect, so a lock someone later removed would leave
    the whole suite green. Naming the statement is what makes it compilable here without a
    database, and this test is the half that makes the naming worth anything.
    """
    from sqlalchemy.dialects import postgresql

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in compiled
    assert table in compiled


def test_completing_a_run_locks_the_row_it_reads(factory: sessionmaker) -> None:
    """`complete_analysis_run` reads the state and then writes on it, which is not atomic.

    Two workers could both read `started`, both pass the check, and the second overwrite the
    first's package digest and version provenance while both reported success. `FR-111` binds a run
    to the versions it actually derived under, so a lost write there is lost provenance. Review on
    `#370` found it.

    Asserted on the *statement* rather than by racing two threads, because SQLite serializes writes
    anyway and a concurrency test on this engine would pass with the lock removed -- the guard
    would be green against the defect it exists to catch.
    """
    import inspect as py_inspect

    source = py_inspect.getsource(SqlWorkspaceStore.complete_analysis_run)

    assert "run_for_update" in source
    assert "database.get(AnalysisRunRow" not in source


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
    store = SqlWorkspaceStore(factory)
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
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with factory() as database:
        assert database.get(DatasetVersionRow, version.version_id).retention_changed_at is None

    store.tombstone_dataset_version(version.version_id, now=LATER)

    # Compared through `_utc` because SQLite hands back a naive datetime; the store applies it on
    # every read path and this test reads the raw row to see the column rather than the record.
    with factory() as database:
        stored = database.get(DatasetVersionRow, version.version_id).retention_changed_at
    assert _utc(stored) == LATER


@pytest.mark.parametrize(
    ("statement", "table"),
    [
        (run_for_update("run_abc123", "own_abc123"), "rca_workspace_analysis_runs"),
        (version_for_update("dsv_abc123", "own_abc123"), "rca_workspace_dataset_versions"),
    ],
)
def test_a_scoped_lock_names_the_scope_in_its_predicate(statement, table: str) -> None:
    """When the caller passes `owner_id`, the lock statement constrains it -- so a cross-tenant
    identifier locks nothing rather than holding another tenant's row for the transaction.

    Compiled against PostgreSQL like its unscoped sibling above, and asserted on the predicate's
    presence: SQLite cannot show a lock, and a race across two tenants here would pass regardless.
    """
    from sqlalchemy.dialects import postgresql

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in compiled
    assert table in compiled
    assert "owner_id =" in compiled
