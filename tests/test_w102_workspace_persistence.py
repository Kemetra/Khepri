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

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.workspace.contracts import (
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
)
from khepri.rca.workspace.persistence import (
    RETENTION_ACTIVE,
    RETENTION_TOMBSTONED,
    SECTION_COLUMNS,
    TOMBSTONE_SUBJECTS,
    SourceProfileRow,
    SqlWorkspaceRecordStore,
    WorkspaceTombstoneRow,
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

SECOND_SOURCE = replace(
    SOURCE, plaintext_digest="sha256:" + "d" * 64, ciphertext_digest="sha256:" + "e" * 64
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
    store = SqlWorkspaceRecordStore(factory)
    with pytest.raises(IntegrityError):
        store.add_dataset_version(
            DatasetVersion.create(owner_id="own_never_provisioned", source=SOURCE, now=NOW)
        )


# --- FR-110 / FR-111: what a row preserves ---------------------------------------------------


def test_a_dataset_version_round_trips_through_the_store(factory: sessionmaker) -> None:
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
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
    store = SqlWorkspaceRecordStore(factory)
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
    store = SqlWorkspaceRecordStore(factory)
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
    store = SqlWorkspaceRecordStore(factory)
    with pytest.raises(IntegrityError):
        store.add_analysis_run(
            AnalysisRun.create(owner_id=scope, version_id="dsv_never_written", now=NOW)
        )


def test_an_artifact_binding_round_trips_and_binds_by_digest(factory: sessionmaker) -> None:
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
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
    store = SqlWorkspaceRecordStore(factory)
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

    store = SqlWorkspaceRecordStore(factory)
    mine_early = store.add_dataset_version(
        DatasetVersion.create(owner_id=first, source=SOURCE, now=NOW)
    )
    # A second *upload*: `W1-04b` made one version per admitted upload a database rule
    # (`uq_rca_workspace_version_upload`), so two versions in one scope are two sources.
    mine_late = store.add_dataset_version(
        DatasetVersion.create(owner_id=first, source=SECOND_SOURCE, now=LATER)
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

    store = SqlWorkspaceRecordStore(factory)
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

    store = SqlWorkspaceRecordStore(factory)
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

    signature = py_inspect.signature(getattr(SqlWorkspaceRecordStore, method_name))
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
    store = SqlWorkspaceRecordStore(factory)
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
    store = SqlWorkspaceRecordStore(factory)
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
    # `W1-04` added the sixth, `rca_workspace_audit_events` (`FR-125`), and `W1-04b` the seventh,
    # `rca_workspace_run_reports` (the job a run is settled by), each in the same metadata so the
    # guard-shape test sees every workspace table; they are named here rather than folded into
    # `WORKSPACE_TABLES`, which the isolation tests read as *this* slice's five.
    assert declared == set(WORKSPACE_TABLES) | {
        "rca_workspace_audit_events",
        "rca_workspace_run_reports",
    }


def test_a_source_profile_row_round_trips(factory: sessionmaker) -> None:
    scope = _scope(factory)
    version = _version(SqlWorkspaceRecordStore(factory), scope)
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
    version = _version(SqlWorkspaceRecordStore(factory), scope)
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
    """Both subjects, each carrying `version_id`: on a version's row it restates the subject, which
    the identity `CHECK` now requires; on a run's row it is the parent dataset."""
    scope = _scope(factory)
    with factory.begin() as database:
        database.add(
            WorkspaceTombstoneRow(
                tombstone_id=f"tmb_{subject}",
                subject_kind=subject,
                subject_id="dsv_abc123",
                version_id="dsv_abc123",
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
