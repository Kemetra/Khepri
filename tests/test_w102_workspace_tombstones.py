"""What a tombstone may contain, and what it must never (`KHEPRI-DEC-033` §3).

Split from `test_w102_workspace_guards.py`, which CodeScene put at nine responsibilities. This is
a real third one rather than a line budget: §3 gives the tombstone two subject allowlists and a
governed vocabulary, and every assertion here is about that table's content rules -- the two
allowlists and their overlap, the subject-specific `CHECK`s, immutability of a deletion record,
and the section-state shape.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.workspace.contracts import (
    AdmittedSource,
    DatasetVersion,
)
from khepri.rca.workspace.persistence import (
    MAX_SECTION_STATES,
    RETENTION_TOMBSTONED,
    RUN_TOMBSTONE_COLUMNS,
    VERSION_TOMBSTONE_COLUMNS,
    DatasetVersionRow,
    SqlWorkspaceStore,
    WorkspaceTombstoneRow,
    validate_section_states,
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


def _tombstone(factory: sessionmaker, scope: str, **overrides: object) -> str:
    fields: dict[str, object] = {
        "tombstone_id": "tmb_abc123",
        "subject_kind": "version",
        "subject_id": "dsv_abc123",
        "owner_id": scope,
        "deleted_at": NOW,
    }
    fields.update(overrides)
    with factory.begin() as database:
        database.add(WorkspaceTombstoneRow(**fields))
    return str(fields["tombstone_id"])


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("subject_kind", "run"),
        ("subject_id", "dsv_rewrit"),
        ("deleted_at", LATER),
        ("manifest_digest", "sha256:rewritten"),
    ],
)
def test_a_tombstone_cannot_be_rewritten(factory: sessionmaker, column: str, value: object) -> None:
    """It sat outside both registrations, so an ordinary session could rewrite its owner, its
    subject identifiers, the deletion instant, or the digests it preserves. `KHEPRI-DEC-033` §5
    anchors a bounded horizon to `deleted_at`, so a movable one moves a deadline. Review on `#370`
    found it.
    """
    scope = _scope(factory)
    _tombstone(factory, scope)

    with pytest.raises(ValueError, match="cannot be rewritten"), factory.begin() as database:
        setattr(database.get(WorkspaceTombstoneRow, "tmb_abc123"), column, value)


def test_a_tombstone_cannot_be_deleted_by_an_ordinary_session(factory: sessionmaker) -> None:
    """The later lifecycle purge is `W1-07`'s, and it must take an explicit exemption to remove
    one -- which is the conversation this guard exists to force, in the same spirit as the
    profile's delete exemption being stated rather than assumed.
    """
    scope = _scope(factory)
    _tombstone(factory, scope)

    with pytest.raises(ValueError), factory.begin() as database:
        database.delete(database.get(WorkspaceTombstoneRow, "tmb_abc123"))


def test_a_version_tombstone_cannot_carry_a_runs_fields(factory: sessionmaker) -> None:
    """`KHEPRI-DEC-033` §3 gives each subject its own allowlist, and the only constraint validated
    the discriminator -- so `subject_kind='version'` could persist a run's `section_states`, and
    content §3 says never survives a deletion would survive it. Review on `#370` found it.
    """
    scope = _scope(factory)

    with pytest.raises(IntegrityError):
        _tombstone(factory, scope, tombstone_id="tmb_mixed1", section_states='{"a": "ok"}')


def test_a_run_tombstone_cannot_carry_a_versions_fields(factory: sessionmaker) -> None:
    """The same allowlist from the other side -- the direction a symmetric guard would miss."""
    scope = _scope(factory)

    with pytest.raises(IntegrityError):
        _tombstone(
            factory,
            scope,
            tombstone_id="tmb_mixed2",
            subject_kind="run",
            subject_id="run_abc123",
            upload_plaintext_digest="sha256:leak",
        )


def test_each_subject_persists_its_own_allowlist(factory: sessionmaker) -> None:
    """The positive direction, so the checks are not merely refusing everything."""
    scope = _scope(factory)
    _tombstone(factory, scope, tombstone_id="tmb_okvers", manifest_digest="sha256:kept")
    _tombstone(
        factory,
        scope,
        tombstone_id="tmb_okruns",
        subject_kind="run",
        subject_id="run_abc123",
        section_states='{"a": "ok"}',
    )

    with factory() as database:
        assert database.get(WorkspaceTombstoneRow, "tmb_okvers") is not None
        assert database.get(WorkspaceTombstoneRow, "tmb_okruns") is not None


def test_the_tombstone_allowlists_cover_every_optional_column() -> None:
    """Every optional column belongs to at least one subject.

    A column in neither allowlist is unconstrained -- it could carry anything under either
    discriminator, which is the defect these checks close, arriving through a column added later.

    **Coverage, not partition.** An earlier version of this test asserted the two sets were
    disjoint, and it passed because I had built the schema from the same misreading it encoded:
    `KHEPRI-DEC-033` §3 gives a version id to *both* rows, so the correct relation is overlap.
    Review on `#370` found the constant; the test agreeing with it was written in the same commit,
    which is why it could not be the thing that caught the error.
    """
    required = {"tombstone_id", "subject_kind", "subject_id", "owner_id", "deleted_at"}
    optional = {
        column.key
        for column in WorkspaceTombstoneRow.__table__.columns
        if column.key not in required
    }

    assert set(VERSION_TOMBSTONE_COLUMNS) | set(RUN_TOMBSTONE_COLUMNS) == optional
    assert set(VERSION_TOMBSTONE_COLUMNS) & set(RUN_TOMBSTONE_COLUMNS) == {"version_id"}, (
        "§3 puts a version id on both tombstone rows; any other overlap is unintended"
    )


def test_a_run_tombstone_keeps_the_version_it_derived_from(factory: sessionmaker) -> None:
    """§3's run row reads "opaque run id, **version id** and scope".

    The first draft nulled `version_id` under `subject_kind='run'`, so `W1-03` could not have
    projected a run deletion without dropping the dataset linkage. Review on `#370` found it.
    """
    scope = _scope(factory)
    _tombstone(
        factory,
        scope,
        tombstone_id="tmb_runver",
        subject_kind="run",
        subject_id="run_abc123",
        version_id="dsv_abc123",
    )

    with factory() as database:
        row = database.get(WorkspaceTombstoneRow, "tmb_runver")
        assert row is not None
        assert row.version_id == "dsv_abc123"


def test_the_migration_states_the_same_allowlists_the_models_do() -> None:
    """The migration keeps literal strings by this repo's convention, so the two can drift.

    `W1-03`'s projection is built against the model constants; the database enforces the migration's
    literals. A silent divergence would let the projection emit a field the table rejects, or --
    worse -- stop rejecting one §3 excludes. Compared by the column names each clause mentions
    rather than by string equality, which whitespace would break for no reason.
    """
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1]
    source = (root / "migrations" / "versions" / "20260904_0021_rca_workspace.py").read_text(
        encoding="utf-8"
    )

    def mentioned(constant: str) -> set[str]:
        body = source.split(f"{constant} = (", 1)[1].split("\n)", 1)[0]
        return set(re.findall(r"(\w+) IS NULL", body))

    # Each check names the columns *exclusive* to the other subject. Not the other list wholesale:
    # `version_id` is on both allowlists (§3), so nulling it under either discriminator would
    # forbid a column that subject is entitled to.
    version_only = set(VERSION_TOMBSTONE_COLUMNS) - set(RUN_TOMBSTONE_COLUMNS)
    run_only = set(RUN_TOMBSTONE_COLUMNS) - set(VERSION_TOMBSTONE_COLUMNS)

    assert mentioned("_TOMBSTONE_VERSION_FIELDS_CHECK") == run_only
    assert mentioned("_TOMBSTONE_RUN_FIELDS_CHECK") == version_only


@pytest.mark.parametrize("column", ["sealed_at", "retention_changed_at"])
def test_a_tombstoned_version_accepts_no_further_update(factory: sessionmaker, column: str) -> None:
    """The one-way rule refused only a change *away* from `tombstoned`, leaving the row open.

    An unsealed tombstoned version could still be sealed, which restarts the seven-day purge clock
    `KHEPRI-DEC-033` §2 starts at sealing -- on a version already deleted. And
    `retention_changed_at` could be rewritten, moving the §5 horizon after the fact. Both were
    confirmed against the guard before this fix, not reasoned about. Review on `#370` found it.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    store.tombstone_dataset_version(version.version_id, now=NOW)

    with (
        pytest.raises(ValueError, match="accepts no further update"),
        factory.begin() as database,
    ):
        setattr(database.get(DatasetVersionRow, version.version_id), column, LATER)


def test_the_tombstoning_update_itself_still_passes(factory: sessionmaker) -> None:
    """Checked on the *prior* state, so the transition into `tombstoned` is not self-refusing.

    A guard reading the new value would make tombstoning impossible -- the same shape as the
    append-only guard that had made run completion impossible earlier on this PR.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    store.tombstone_dataset_version(version.version_id, now=NOW)

    with factory() as database:
        row = database.get(DatasetVersionRow, version.version_id)
        assert row.retention_state == RETENTION_TOMBSTONED
        assert row.retention_changed_at is not None


@pytest.mark.parametrize(
    "document",
    [
        None,
        '{"revenue": "answered"}',
        '{"revenue": "answered", "margin": "caveated", "cohort": "refused"}',
        '{"revenue": "present"}',
    ],
)
def test_a_governed_section_state_document_is_accepted(document: str | None) -> None:
    """Both candidate vocabularies validate, which is the point of checking shape rather than codes.

    `KHEPRI-DEC-033` §3 names `(answered, caveated, refused)`; `rra/bundle.py` enforces
    `{present, refused}` for whether a surface renders a chart or a refusal notice -- a rendering
    concern, not a retention one. `W1-03` builds the projection that writes this column and §3
    gives it the allowlist equality test, so the code set is its choice. Constraining shape here
    closes the leak without handing `W1-03` a constraint it must match.
    """
    validate_section_states(document)


@pytest.mark.parametrize(
    ("document", "why"),
    [
        ('{"revenue": "Sales fell 12% in Q3 on supply issues"}', "narrative as a state"),
        ('{"Acme Pharmacy Ltd": "answered"}', "a customer label as a section key"),
        ('["answered", "refused"]', "a list, so no section is named"),
        ('"answered"', "a bare string"),
        ("not json at all", "unparseable"),
        ('{"revenue": 42}', "a non-string state"),
        ('{"revenue": {"nested": "answered"}}', "a nested document"),
    ],
)
def test_ungoverned_section_state_content_is_refused(document: str, why: str) -> None:
    """§3 excludes "any figure, series, label, narrative, refusal prose" from a tombstone.

    A `Text` column accepting anything let all of it become an immutable retained deletion record,
    and the two allowlist `CHECK`s could not see it -- they only decide whether a column must be
    *null* for the other subject. Review on `#370` found it.
    """
    with pytest.raises(ValueError, match="short codes"):
        validate_section_states(document)


def test_too_many_section_states_is_refused() -> None:
    """A cap a narrative cannot slip under by splitting itself across valid-looking entries."""
    crowded = json.dumps({f"s{index}": "answered" for index in range(MAX_SECTION_STATES + 1)})

    with pytest.raises(ValueError, match="short codes"):
        validate_section_states(crowded)


def test_the_tombstone_refuses_ungoverned_section_states_at_insert(
    factory: sessionmaker,
) -> None:
    """Wired, not merely written: the validator runs on the real insert path.

    `before_insert` rather than `before_update`, because `_refuse_any_update` already refuses every
    update -- insertion is the only moment this column can be written.
    """
    scope = _scope(factory)

    with pytest.raises(ValueError, match="short codes"):
        _tombstone(
            factory,
            scope,
            tombstone_id="tmb_prose1",
            subject_kind="run",
            subject_id="run_abc123",
            section_states='{"revenue": "Sales fell 12% in Q3"}',
        )
