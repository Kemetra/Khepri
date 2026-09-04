"""`W1-03` -- the tombstone allowlist (`RCA-005` `FR-112`, `KHEPRI-DEC-033` §3).

Written before `khepri.rca.workspace.tombstones` exists. `W1-02` built the table and its `CHECK`
constraints and wrote nothing into it; this slice builds the projection that fills it, and these
tests pin the one property §3 promises a test for:

    "A test asserts each tombstone's field set equals its allowlist exactly, so a field added to
    the live record cannot leak into the tombstone by default."

**Equality, not subset.** A subset assertion passes when a new sensitive field arrives on the
tombstone, because every allowlisted field is still present. The equality is what makes a new
field fail until someone states, in the same commit, that §3 permits it. The same discipline as
`test_w101_workspace_contracts.py`, applied to the record that survives a deletion.

**Built by construction, not by removal.** The plan's one named risk for this slice is
`del d["filename"]`: a tombstone made by deleting fields from the live record carries every field
nobody thought to delete. So one test hands the projection a live record that has grown a field,
and asserts the tombstone did not.

**The section vocabulary is translated, not copied.** The report bundle says `present` or
`refused`; §3 says `answered`, `caveated` or `refused`. `present` is a rendering outcome -- a
surface drew the section -- and a retention record keeps the *analysis* outcome. The translation
is asserted here against the bundle's own constants, from the one place that may import both
packages (`R7-01` §3).
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    AdmittedSource,
    AnalysisRun,
    DatasetVersion,
    RunOutcome,
    RunSubject,
)
from khepri.rca.workspace.persistence import (
    RETENTION_TOMBSTONED,
    RUN_TOMBSTONE_COLUMNS,
    SECTION_STATE_CODES,
    TOMBSTONE_SECTIONS,
    VERSION_TOMBSTONE_COLUMNS,
    AnalysisRunRow,
    SqlWorkspaceStore,
    WorkspaceTombstoneRow,
)
from khepri.rca.workspace.tombstones import (
    RENDERED_PRESENT,
    RENDERED_REFUSED,
    RENDERED_STATES,
    RunTombstone,
    SectionStates,
    VersionTombstone,
)
from khepri.rra.bundle import GOVERNED_SECTION_STATES, SECTION_PRESENT, SECTION_REFUSED
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    factory_fixture,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
COMPLETED = datetime(2026, 9, 4, 12, 30, tzinfo=UTC)
LATER = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)
MUCH_LATER = datetime(2026, 9, 4, 18, 0, tzinfo=UTC)
SCOPE = "own_3f7a9c21b4e85d06"

SOURCE = AdmittedSource(
    plaintext_digest="sha256:" + "a" * 64,
    ciphertext_digest="sha256:" + "b" * 64,
    size_bytes=2048,
    media_type="text/csv",
    manifest_digest="sha256:" + "c" * 64,
    mapping_version="rra003.mapping.v3",
    admission_outcome="admitted",
)

OUTCOME = RunOutcome(
    state=RUN_COMPLETED,
    package_digest="sha256:" + "d" * 64,
    package_version="rra004.v7",
    formula_version="rra008.v2",
    completed_at=COMPLETED,
)

ALL_ANSWERED = SectionStates(
    overview="answered",
    comparison="answered",
    concentration="answered",
    growth="answered",
    basket="answered",
)
MIXED = SectionStates(
    overview="answered",
    comparison="refused",
    concentration="caveated",
    growth="answered",
    basket="refused",
)

# The columns §3 gives to one subject and not the other. A version's tombstone row must hold
# nothing in the second set, a run's nothing in the first.
RUN_ONLY_COLUMNS = frozenset(RUN_TOMBSTONE_COLUMNS) - frozenset(VERSION_TOMBSTONE_COLUMNS)
VERSION_ONLY_COLUMNS = frozenset(VERSION_TOMBSTONE_COLUMNS) - frozenset(RUN_TOMBSTONE_COLUMNS)


def _field_names(record_type: type) -> set[str]:
    return {f.name for f in fields(record_type)}


def _version() -> DatasetVersion:
    return DatasetVersion.create(owner_id=SCOPE, source=SOURCE, now=NOW)


def _completed_run(version: DatasetVersion) -> AnalysisRun:
    return AnalysisRun._from_storage(
        subject=RunSubject(run_id="run_abc123", owner_id=SCOPE, version_id=version.version_id),
        outcome=OUTCOME,
        started_at=NOW,
    )


# --- §3: each tombstone's field set equals its allowlist exactly -------------------------------


def test_version_tombstone_fields_equal_dec033s_allowlist() -> None:
    """The version allowlist, plus the two things every tombstone has: whose it is and when it
    ended. `version_id` is on the allowlist itself, because §3 keeps the "opaque version id"."""
    assert _field_names(VersionTombstone) == {"owner_id", "deleted_at"} | set(
        VERSION_TOMBSTONE_COLUMNS
    )


def test_run_tombstone_fields_equal_dec033s_allowlist() -> None:
    """The run allowlist, plus identity and ending. Operational `state` is on the live record and
    *not* here -- §3 keeps "started, completed and deleted instants", not the state machine -- which
    is the first concrete field this projection must drop rather than copy."""
    assert _field_names(RunTombstone) == {"run_id", "owner_id", "deleted_at"} | set(
        RUN_TOMBSTONE_COLUMNS
    )
    assert "state" not in _field_names(RunTombstone)


def test_section_states_fields_are_exactly_the_report_sections() -> None:
    """One field per report section, and no other, so the value type and the five columns cannot
    drift: `SECTION_COLUMNS` is derived from the same tuple."""
    assert _field_names(SectionStates) == set(TOMBSTONE_SECTIONS)


# --- Built by construction -----------------------------------------------------------------------


def test_a_version_projection_carries_each_allowlisted_value() -> None:
    version = _version()

    tombstone = VersionTombstone.project(version, deleted_at=LATER)

    assert tombstone.version_id == version.version_id
    assert tombstone.owner_id == version.owner_id
    assert tombstone.deleted_at == LATER
    assert tombstone.created_at == version.created_at
    assert tombstone.sealed_at is None
    assert tombstone.upload_plaintext_digest == SOURCE.plaintext_digest
    assert tombstone.upload_ciphertext_digest == SOURCE.ciphertext_digest
    assert tombstone.upload_size_bytes == SOURCE.size_bytes
    assert tombstone.upload_media_type == SOURCE.media_type
    assert tombstone.manifest_digest == SOURCE.manifest_digest
    assert tombstone.mapping_version == SOURCE.mapping_version
    assert tombstone.admission_outcome == SOURCE.admission_outcome


def test_a_run_projection_carries_each_allowlisted_value_and_drops_state() -> None:
    run = _completed_run(_version())

    tombstone = RunTombstone.project(run, sections=MIXED, deleted_at=LATER)

    assert tombstone.run_id == run.run_id
    assert tombstone.version_id == run.version_id
    assert tombstone.owner_id == run.owner_id
    assert tombstone.deleted_at == LATER
    assert tombstone.started_at == NOW
    assert tombstone.completed_at == COMPLETED
    assert tombstone.package_digest == OUTCOME.package_digest
    assert tombstone.package_version == OUTCOME.package_version
    assert tombstone.formula_version == OUTCOME.formula_version
    assert tombstone.section_overview == "answered"
    assert tombstone.section_comparison == "refused"
    assert tombstone.section_concentration == "caveated"
    assert tombstone.section_growth == "answered"
    assert tombstone.section_basket == "refused"
    assert not hasattr(tombstone, "state")


def test_a_run_projected_without_sections_records_none_for_each() -> None:
    """A `started` or `failed` run has no sections to record; §3 says *may* contain."""
    run = _completed_run(_version())

    tombstone = RunTombstone.project(run, sections=None, deleted_at=LATER)

    assert [getattr(tombstone, f"section_{section}") for section in TOMBSTONE_SECTIONS] == [
        None
    ] * len(TOMBSTONE_SECTIONS)


def test_a_field_added_to_the_live_record_does_not_reach_the_tombstone() -> None:
    """The plan's named risk: a tombstone built by *removing* fields from the live record carries
    every field nobody thought to remove. This live record has grown the two fields §3 names as
    never permitted -- a filename and column labels -- and the projection must not notice them.
    """
    version = _version()
    grown = SimpleNamespace(
        **{name: getattr(version, name) for name in _field_names(DatasetVersion)},
        filename="acme_sales_2026Q3.csv",
        column_labels=("Product", "Branch", "Net Sales"),
    )

    tombstone = VersionTombstone.project(grown, deleted_at=LATER)

    assert not hasattr(tombstone, "filename")
    assert not hasattr(tombstone, "column_labels")
    assert tombstone == VersionTombstone.project(version, deleted_at=LATER)


# --- The section vocabulary ----------------------------------------------------------------------


@pytest.mark.parametrize("section", TOMBSTONE_SECTIONS)
@pytest.mark.parametrize("code", ["present", "", "unknown", "ANSWERED"])
def test_section_states_refuse_a_code_outside_dec033s_three(section: str, code: str) -> None:
    """Per field, because a check that loops over some fields passes for the ones it names.
    `present` is the rendering vocabulary and is refused here: it must be translated first."""
    kwargs = dict.fromkeys(TOMBSTONE_SECTIONS, "answered")
    kwargs[section] = code
    with pytest.raises(ValueError, match="Section state"):
        SectionStates(**kwargs)


def test_section_states_accept_each_governed_code_in_each_section() -> None:
    for code in SECTION_STATE_CODES:
        states = SectionStates(**dict.fromkeys(TOMBSTONE_SECTIONS, code))
        assert all(getattr(states, section) == code for section in TOMBSTONE_SECTIONS)


def test_from_rendering_translates_the_bundles_vocabulary() -> None:
    """`present` with no caveat on the section is `answered`; `present` with a section-scoped
    caveat is `caveated`; `refused` is `refused` whether or not a caveat also names it."""
    states = SectionStates.from_rendering(
        {
            "overview": RENDERED_PRESENT,
            "comparison": RENDERED_PRESENT,
            "concentration": RENDERED_REFUSED,
            "growth": RENDERED_REFUSED,
            "basket": RENDERED_PRESENT,
        },
        caveated={"comparison", "growth"},
    )

    assert states == SectionStates(
        overview="answered",
        comparison="caveated",
        concentration="refused",
        growth="refused",
        basket="answered",
    )


@pytest.mark.parametrize("missing", TOMBSTONE_SECTIONS)
def test_from_rendering_requires_every_section(missing: str) -> None:
    """Fail closed: a report that says nothing about a section has not answered it, and this
    projection does not invent an answer. Per section, for the reason the refusal test is."""
    rendered = dict.fromkeys(TOMBSTONE_SECTIONS, RENDERED_PRESENT)
    del rendered[missing]
    with pytest.raises(ValueError, match="every report section"):
        SectionStates.from_rendering(rendered)


def test_from_rendering_refuses_a_section_that_is_not_a_report_section() -> None:
    rendered = dict.fromkeys(TOMBSTONE_SECTIONS, RENDERED_PRESENT)
    rendered["narrative"] = RENDERED_PRESENT
    with pytest.raises(ValueError, match="every report section"):
        SectionStates.from_rendering(rendered)


@pytest.mark.parametrize("code", ["answered", "caveated", "", "drawn"])
def test_from_rendering_refuses_a_state_the_bundle_does_not_publish(code: str) -> None:
    """The input is the *rendering* vocabulary. `answered` arriving here means a caller skipped
    the translation and is handing this projection a retention code as if it were rendered."""
    rendered = dict.fromkeys(TOMBSTONE_SECTIONS, RENDERED_PRESENT)
    rendered["basket"] = code
    with pytest.raises(ValueError, match="Rendered section state"):
        SectionStates.from_rendering(rendered)


def test_the_rendering_vocabulary_matches_the_bundles() -> None:
    """Restated in `khepri.rca` rather than imported, because `R7-01` §3 forbids the import in
    either direction. This is the drift test that makes the restatement safe, from the one module
    that may import both."""
    assert RENDERED_PRESENT == SECTION_PRESENT
    assert RENDERED_REFUSED == SECTION_REFUSED
    assert frozenset(RENDERED_STATES) == GOVERNED_SECTION_STATES


# --- The store writes the projection when it tombstones ------------------------------------------


def _scope(factory: sessionmaker, email: str = EMAIL, name: str = "Acme Pharmacy") -> str:
    accounts = SqlAccountStore(factory)
    account = AccountService(accounts).create_account(email, CREDENTIAL)
    organizations = SqlOrganizationStore(factory)
    organization = OrganizationService(organizations).create_organization(
        name, account.account_id, now=NOW
    )
    scope = organizations.get_scope(organization.organization_id)
    assert scope is not None
    return scope.owner_id


def _stored_version(store: SqlWorkspaceStore, scope: str) -> DatasetVersion:
    return store.add_dataset_version(DatasetVersion.create(owner_id=scope, source=SOURCE, now=NOW))


def _stored_run(
    store: SqlWorkspaceStore, scope: str, version: DatasetVersion, *, complete: bool
) -> AnalysisRun:
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    if complete:
        store.complete_analysis_run(run.run_id, OUTCOME)
        completed = store.get_analysis_run(run.run_id)
        assert completed is not None
        return completed
    return run


def _rows(factory: sessionmaker) -> list[WorkspaceTombstoneRow]:
    with factory() as database:
        return list(database.scalars(select(WorkspaceTombstoneRow)).all())


def test_tombstoning_a_version_writes_its_tombstone(factory: sessionmaker) -> None:
    """The row `W1-02` left empty, now written -- and read back equal to the projection, so the
    store's row mapping and the projection agree field for field."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _stored_version(store, scope)
    assert store.tombstones_for_scope(scope) == ()

    store.tombstone_dataset_version(version.version_id, now=LATER)

    assert store.tombstones_for_scope(scope) == (
        VersionTombstone.project(version, deleted_at=LATER),
    )


def test_a_cascaded_run_gets_its_own_tombstone_with_the_callers_sections(
    factory: sessionmaker,
) -> None:
    """The store does not know a run's section states -- the live run record carries none, and
    the bundle that does is `khepri.rra`'s. The caller that deletes supplies them, per run, and
    the cascade projects each run with what it was given.

    Every run's `version_id` is the parent (§3: a run's tombstone keeps "the version id"), and
    every clock is the deletion instant (§3: a cascaded deletion is the run's own trigger).
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _stored_version(store, scope)
    finished = _stored_run(store, scope, version, complete=True)
    unfinished = _stored_run(store, scope, version, complete=False)
    sections = {finished.run_id: MIXED}

    store.tombstone_dataset_version(
        version.version_id, now=LATER, sections_of=lambda run: sections.get(run.run_id)
    )

    tombstones = store.tombstones_for_scope(scope)
    runs = {t.run_id: t for t in tombstones if isinstance(t, RunTombstone)}
    assert set(runs) == {finished.run_id, unfinished.run_id}
    assert runs[finished.run_id] == RunTombstone.project(finished, sections=MIXED, deleted_at=LATER)
    assert runs[unfinished.run_id] == RunTombstone.project(
        unfinished, sections=None, deleted_at=LATER
    )
    assert {t.version_id for t in runs.values()} == {version.version_id}
    assert [t for t in tombstones if isinstance(t, VersionTombstone)] == [
        VersionTombstone.project(version, deleted_at=LATER)
    ]


def test_the_written_rows_hold_nothing_outside_their_subjects_allowlist(
    factory: sessionmaker,
) -> None:
    """Read at the row, below the projection: the `CHECK` constraints `W1-02` wrote refuse a
    run-only column on a version row and vice versa, so a row that reached the table already
    satisfies them -- this asserts the mapping filled the right side rather than none. The version
    is sealed and the run completed first, so every column on each side has a value to carry."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _stored_version(store, scope)
    assert store.seal_dataset_version(version.version_id, now=COMPLETED)
    run = _stored_run(store, scope, version, complete=True)

    store.tombstone_dataset_version(
        version.version_id, now=LATER, sections_of=lambda _run: ALL_ANSWERED
    )

    by_kind = {row.subject_kind: row for row in _rows(factory)}
    version_row, run_row = by_kind["version"], by_kind["run"]
    assert version_row.subject_id == version_row.version_id == version.version_id
    assert all(getattr(version_row, column) is None for column in RUN_ONLY_COLUMNS)
    assert all(getattr(version_row, column) is not None for column in VERSION_ONLY_COLUMNS)
    assert run_row.subject_id == run.run_id
    assert run_row.version_id == version.version_id
    assert all(getattr(run_row, column) is None for column in VERSION_ONLY_COLUMNS)
    assert all(getattr(run_row, column) is not None for column in RUN_ONLY_COLUMNS)


def test_a_run_already_tombstoned_gets_no_second_tombstone(factory: sessionmaker) -> None:
    """The cascade skips a run that is not live (`W1-02`), and so must the projection: a run
    tombstoned on its own trigger already has its record, and a second would be a second deletion
    of the same thing. Here the run was tombstoned by a raw write and has no row at all -- the
    cascade must still not write one, because it was not this deletion that ended it."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _stored_version(store, scope)
    earlier = _stored_run(store, scope, version, complete=False)
    later = _stored_run(store, scope, version, complete=False)
    with factory.begin() as database:
        row = database.get(AnalysisRunRow, earlier.run_id)
        row.retention_state = RETENTION_TOMBSTONED
        row.retention_changed_at = NOW

    store.tombstone_dataset_version(version.version_id, now=LATER)

    run_tombstones = [t for t in store.tombstones_for_scope(scope) if isinstance(t, RunTombstone)]
    assert [t.run_id for t in run_tombstones] == [later.run_id]


def test_a_repeated_deletion_writes_no_second_tombstone(factory: sessionmaker) -> None:
    """`FR-123`: a repeated request "MUST create no new deletion evidence". The tombstone is the
    record that survives the deletion, and there is one deletion."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _stored_version(store, scope)
    _stored_run(store, scope, version, complete=True)

    store.tombstone_dataset_version(version.version_id, now=LATER)
    store.tombstone_dataset_version(version.version_id, now=MUCH_LATER)

    tombstones = store.tombstones_for_scope(scope)
    assert len(tombstones) == 2
    assert {t.deleted_at for t in tombstones} == {LATER}


def test_tombstones_are_read_by_scope(factory: sessionmaker) -> None:
    """Two scopes, one read -- the only shape that can see a missing `WHERE`."""
    ours = _scope(factory)
    theirs = _scope(factory, email="other@example.com", name="Other Pharmacy")
    store = SqlWorkspaceStore(factory)
    our_version = _stored_version(store, ours)
    their_version = _stored_version(store, theirs)
    store.tombstone_dataset_version(our_version.version_id, now=LATER)
    store.tombstone_dataset_version(their_version.version_id, now=LATER)

    assert [t.version_id for t in store.tombstones_for_scope(ours)] == [our_version.version_id]
    assert [t.version_id for t in store.tombstones_for_scope(theirs)] == [their_version.version_id]


def test_a_deletion_under_a_foreign_scope_writes_nothing(factory: sessionmaker) -> None:
    ours = _scope(factory)
    theirs = _scope(factory, email="other@example.com", name="Other Pharmacy")
    store = SqlWorkspaceStore(factory)
    version = _stored_version(store, ours)

    store.tombstone_dataset_version(version.version_id, now=LATER, owner_id=theirs)

    assert _rows(factory) == []
    assert store.get_dataset_version(version.version_id) == version
