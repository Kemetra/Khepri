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

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.records import Sealed
from khepri.rca.workspace.contracts import (
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
)
from khepri.rca.workspace.persistence import (
    RETENTION_ACTIVE,
    RETENTION_STATES,
    RETENTION_TOMBSTONED,
    ArtifactBindingRow,
    SqlWorkspaceStore,
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


# --- FR-112: append-only, and the one thing that may change ----------------------------------


def test_a_stored_dataset_version_is_returned_sealed(factory: sessionmaker) -> None:
    """What comes back is a record the domain trusts, reconstructed through `_from_storage`."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    read = store.get_dataset_version(_version(store, scope).version_id)

    assert read is not None
    assert isinstance(read, Sealed)


def test_writing_the_same_version_twice_is_refused(factory: sessionmaker) -> None:
    """`FR-112`: append-only. A second write under one identifier is a content change by another
    route -- the row would be replaced rather than appended -- so it is refused rather than
    silently upserted."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with pytest.raises(IntegrityError):
        store.add_dataset_version(version)


def test_retention_state_is_the_only_thing_a_later_operation_changes(
    factory: sessionmaker,
) -> None:
    """`FR-112`: "Only retention state and tombstoning may change a row."

    `W1-01`'s `DatasetVersion` deliberately carries no retention field -- its docstring says the
    state "changes, which `W1-02` holds in the store rather than on this record". So the column
    exists on the table and the transition is a store operation, and the record read back is
    unchanged by it.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    assert store.retention_state(version.version_id) == RETENTION_ACTIVE

    store.tombstone_dataset_version(version.version_id, now=LATER)

    assert store.retention_state(version.version_id) == RETENTION_TOMBSTONED
    assert store.get_dataset_version(version.version_id) == version


def test_a_retention_state_the_domain_does_not_define_is_refused(factory: sessionmaker) -> None:
    """The vocabulary is enforced by the schema, not merely published.

    This is the `RUN_STATES` defect `W1-01` closed, in its schema form: a tuple that only
    *documents* its values leaves the constraint with prose and no code path. Here the CHECK
    constraint is that path.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with pytest.raises(ValueError, match="not one of the retention states"):
        store.set_retention_state(version.version_id, "archived", now=LATER)


@pytest.mark.parametrize("state", RETENTION_STATES)
def test_every_published_retention_state_is_accepted(factory: sessionmaker, state: str) -> None:
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    store.set_retention_state(version.version_id, state, now=LATER)

    assert store.retention_state(version.version_id) == state


def test_the_refusal_does_not_echo_the_rejected_value(factory: sessionmaker) -> None:
    """Content-free refusals per `rca/errors.py`: a message must not carry caller input."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with pytest.raises(ValueError) as caught:
        store.set_retention_state(version.version_id, "acme-pharmacy-archived", now=LATER)
    assert "acme" not in str(caught.value).lower()


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


# --- Cross-scope children, which independent foreign keys allowed ---------------------------


def test_a_run_cannot_claim_one_scope_while_naming_another_scopes_version(
    factory: sessionmaker,
) -> None:
    """`FR-109`: two independent foreign keys are checked independently.

    Found by review on `#370`, and the isolation tests above could not see it: each of them writes
    one scope's rows *consistently*, so none ever constructs the mismatched pair. A run naming
    `owner_id=A` and a version belonging to `B` satisfied both constraints separately, appeared in
    A's listing, and pointed into B's data.

    The parent key is now composite -- `(owner_id, version_id)` -- so the mismatch is not a row the
    database will store, rather than one no test happened to build.
    """
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")
    store = SqlWorkspaceStore(factory)
    theirs = store.add_dataset_version(
        DatasetVersion.create(owner_id=second, source=SOURCE, now=NOW)
    )

    with pytest.raises(IntegrityError):
        store.add_analysis_run(
            AnalysisRun.create(owner_id=first, version_id=theirs.version_id, now=NOW)
        )


def test_a_binding_cannot_claim_one_scope_while_naming_another_scopes_run(
    factory: sessionmaker,
) -> None:
    """The same defect one level down: `(owner_id, run_id)` is the binding's parent key."""
    first = _scope(factory)
    second = _scope(factory, email="other@example.test", name="Other Pharmacy")
    store = SqlWorkspaceStore(factory)
    theirs = store.add_dataset_version(
        DatasetVersion.create(owner_id=second, source=SOURCE, now=NOW)
    )
    their_run = store.add_analysis_run(
        AnalysisRun.create(owner_id=second, version_id=theirs.version_id, now=NOW)
    )

    with pytest.raises(IntegrityError):
        store.add_artifact_binding(
            ArtifactBinding.create(
                owner_id=first,
                run_id=their_run.run_id,
                artifact=PublishedArtifact(surface="web", artifact_digest="sha256:" + "f" * 64),
                now=NOW,
            )
        )


def test_one_run_may_hold_two_bindings_for_the_same_surface(factory: sessionmaker) -> None:
    """The refusal the migration documents must hold in the code that writes the row.

    The docstring says there is no `UNIQUE (run_id, surface)` "and that is the decision rather than
    an omission" -- and the first version of `add_artifact_binding` then derived `binding_id` from
    exactly that pair, reimposing the constraint through the primary key. Prose and code
    contradicted each other and the code won silently, which review on `#370` caught.

    A republished surface is the case that matters: `FR-111` reads completeness from the *set* a
    run names, and a store that refused the second row would decide that question in the wrong
    place.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )

    for digest in ("sha256:" + "1" * 64, "sha256:" + "2" * 64):
        store.add_artifact_binding(
            ArtifactBinding.create(
                owner_id=scope,
                run_id=run.run_id,
                artifact=PublishedArtifact(surface="web", artifact_digest=digest),
                now=NOW,
            )
        )

    assert len(store.artifact_bindings_for_run(run.run_id)) == 2


def test_a_binding_identifier_is_allocated_rather_than_derived(factory: sessionmaker) -> None:
    """A derived key is the uniqueness constraint again, wearing a different name.

    Asserted against the stored identifier rather than only through the two-row case above,
    because a key derived from any caller-supplied value is also the `FR-109` question: an opaque
    identifier must not make its subject recoverable from the key.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    store.add_artifact_binding(
        ArtifactBinding.create(
            owner_id=scope,
            run_id=run.run_id,
            artifact=PublishedArtifact(surface="web", artifact_digest="sha256:" + "3" * 64),
            now=NOW,
        )
    )

    with factory() as database:
        stored = database.execute(select(ArtifactBindingRow.binding_id)).scalars().all()

    assert len(stored) == 1
    assert stored[0].startswith("abn_")
    assert run.run_id not in stored[0]
    assert "web" not in stored[0]
