"""What a tombstone may contain, and what it must never (`KHEPRI-DEC-033` §3).

Split from `test_w102_workspace_guards.py`, which CodeScene put at nine responsibilities. This is
a real third one rather than a line budget: §3 gives the tombstone two subject allowlists and a
governed vocabulary, and every assertion here is about that table's content rules -- the two
allowlists and their overlap, the subject-specific `CHECK`s, immutability of a deletion record,
and the section-state shape.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select
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
    GOVERNED_SECTION_STATE_CODES,
    RETENTION_TOMBSTONED,
    RUN_TOMBSTONE_COLUMNS,
    SECTION_COLUMNS,
    SECTION_STATE_CODES,
    TOMBSTONE_SECTIONS,
    VERSION_TOMBSTONE_COLUMNS,
    DatasetVersionRow,
    SqlWorkspaceStore,
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
        _tombstone(
            factory,
            scope,
            tombstone_id="tmb_mixed1",
            section_overview="answered",
        )


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
        section_overview="answered",
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


# --- Section states: one column per report section, one CHECK per column -----------------------


@pytest.mark.parametrize("column", SECTION_COLUMNS)
@pytest.mark.parametrize("state", SECTION_STATE_CODES)
def test_every_section_column_accepts_every_governed_state(
    factory: sessionmaker, column: str, state: str
) -> None:
    """Fifteen cells: five report sections by `KHEPRI-DEC-033` §3's three retention outcomes.

    Parametrized over `SECTION_STATE_CODES` rather than a literal list, so the cells follow the
    constant -- which is also why this test shrank from twenty when `present` left it.
    """
    scope = _scope(factory)
    _tombstone(
        factory,
        scope,
        tombstone_id=f"tmb_{column[8:13]}{state[:3]}",
        subject_kind="run",
        subject_id="run_abc123",
        **{column: state},
    )

    with factory() as database:
        rows = database.execute(select(WorkspaceTombstoneRow)).scalars().all()
        assert getattr(rows[0], column) == state


@pytest.mark.parametrize("column", SECTION_COLUMNS)
@pytest.mark.parametrize(
    "value",
    [
        "Sales fell 12% in Q3 on supply issues",
        "made_up",
        "Acme Pharmacy Ltd",
        "ANSWERED",
        "",
        # `rra/bundle.py`'s rendering state. Admitted by an earlier draft as a "union" of two
        # governed vocabularies; §3's allowlist is exhaustive and a rendering code is not a
        # retention outcome. Refused at the database like every other ungoverned value.
        "present",
    ],
)
def test_a_section_column_refuses_an_ungoverned_state(
    factory: sessionmaker, column: str, value: str
) -> None:
    """Refused by the database, not by Python -- `IntegrityError`, on every section column.

    §3 excludes "any figure, series, label, narrative, refusal prose". The previous design held a
    JSON document that only a mapper `before_insert` listener validated, and a Core or raw-SQL
    insert never fires one. Review on `#370` found that gap; a `CHECK` per column closes it for
    every writer.
    """
    scope = _scope(factory)

    with pytest.raises(IntegrityError):
        _tombstone(
            factory,
            scope,
            tombstone_id="tmb_badstate",
            subject_kind="run",
            subject_id="run_abc123",
            **{column: value},
        )


def test_a_core_insert_meets_the_same_rule_as_the_orm(factory: sessionmaker) -> None:
    """The finding, exactly: a Core `insert()` bypasses every mapper listener.

    Under the JSON design this statement committed prose into an immutable deletion record. Now
    the rule is the column's `CHECK`, and Core, bulk and raw SQL all meet it.
    """
    scope = _scope(factory)

    with pytest.raises(IntegrityError), factory.begin() as database:
        database.execute(
            insert(WorkspaceTombstoneRow.__table__).values(
                tombstone_id="tmb_coreins",
                subject_kind="run",
                subject_id="run_abc123",
                owner_id=scope,
                deleted_at=NOW,
                section_overview="Sales fell 12% in Q3",
            )
        )


def test_a_section_that_is_not_a_report_section_is_unrepresentable() -> None:
    """`acme_pharmacy` is not a section, and there is no column to put it in.

    The JSON design's last leak was a customer label that *looked* like a code. With one column per
    section, the section vocabulary is the column set: nothing to validate, because nothing else
    can be named.
    """
    columns = {column.key for column in WorkspaceTombstoneRow.__table__.columns}

    assert set(SECTION_COLUMNS) <= columns
    assert "section_acme_pharmacy" not in columns
    assert not any(
        column.startswith("section_") and column not in SECTION_COLUMNS for column in columns
    )


def test_the_section_columns_match_the_report_sections_the_bundle_publishes() -> None:
    """`TOMBSTONE_SECTIONS` must equal `rra/bundle.py`'s `ORDERED_SECTIONS`, in content.

    Restated in `persistence.py` because `R7-01` §3 forbids `khepri.rca` importing `khepri.rra`;
    a test may import both, so this is where drift is caught. The previous constant restated the
    wrong vocabulary entirely -- 22 metric names where §3 means the five report sections -- and
    passed its own drift test because that test compared it to the wrong source too. This one
    compares to what a `Section.section_id` actually is.
    """
    from khepri.rra.bundle import ORDERED_SECTIONS

    assert set(TOMBSTONE_SECTIONS) == set(ORDERED_SECTIONS)
    assert tuple(f"section_{section}" for section in TOMBSTONE_SECTIONS) == SECTION_COLUMNS


def test_the_state_codes_are_exactly_dec033s_three() -> None:
    """`KHEPRI-DEC-033` §3's allowlist, exhaustively -- and the rendering vocabulary kept out.

    This test used to assert the *union* with `rra/bundle.py`'s `GOVERNED_SECTION_STATES`, on the
    argument that both sets were real. Review on `#370` read §3 more strictly than I had: "per-
    section state codes (answered, caveated, refused)" is the whole list, and `present` -- a surface
    drew a chart -- is not a retention outcome. A test that had encoded the widening is why it is
    asserted in both directions now: the three are present, and the rendering code is not.
    """
    from khepri.rra.bundle import GOVERNED_SECTION_STATES, SECTION_PRESENT

    assert {"answered", "caveated", "refused"} == GOVERNED_SECTION_STATE_CODES
    assert SECTION_PRESENT not in GOVERNED_SECTION_STATE_CODES
    # `refused` is in both vocabularies; it is admitted because §3 names it, and this line only
    # records that the two sets do overlap there, so a future reader does not "fix" it.
    assert {"refused"} == GOVERNED_SECTION_STATES & GOVERNED_SECTION_STATE_CODES


def test_the_migration_states_the_same_section_columns_and_states() -> None:
    """The migration restates both vocabularies as literals; they must agree with the constants."""
    import pathlib as _pathlib

    root = _pathlib.Path(__file__).resolve().parents[1]
    source = (root / "migrations" / "versions" / "20260904_0021_rca_workspace.py").read_text(
        encoding="utf-8"
    )
    literal_columns = set(re.findall(r'"(section_[a-z]+)"', source))
    states_clause = re.search(r"_SECTION_STATES = \"\((.*?)\)\"", source)
    assert states_clause is not None
    literal_states = set(re.findall(r"'([a-z]+)'", states_clause.group(1)))

    assert literal_columns == set(SECTION_COLUMNS)
    assert literal_states == set(SECTION_STATE_CODES)
