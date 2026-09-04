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
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore, _utc
from khepri.rca.records import Sealed
from khepri.rca.workspace.contracts import (
    RUN_STATES,
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
    RunOutcome,
)
from khepri.rca.workspace.persistence import (
    APPEND_ONLY_FAILURE,
    COMPLETION_COLUMNS,
    MUTABLE_COLUMNS,
    RETENTION_ACTIVE,
    RETENTION_STATES,
    RETENTION_TOMBSTONED,
    TOMBSTONE_SUBJECTS,
    AnalysisRunRow,
    ArtifactBindingRow,
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


# --- FR-112 enforced, not merely claimed ------------------------------------------------------


def test_a_content_field_cannot_be_changed_after_the_row_is_written(
    factory: sessionmaker,
) -> None:
    """`FR-112`: "a change to any content field after sealing or completion is refused".

    Nothing in this slice refused one until review on `#370` said so.
    `test_writing_the_same_version_twice_is_refused` covers a second *insert* under one identifier
    -- the primary key does that -- but a session that loads the row and commits a changed digest
    rewrites provenance through an ordinary `UPDATE`, and the append-only claim was resting on a
    test that never exercised it.

    The same shape `W1-01` paid for one layer up: sealing proves a record came through a door,
    never that anything refuses a later write.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with (
        pytest.raises(ValueError, match="cannot change after it is written"),
        factory.begin() as database,
    ):
        row = database.get(DatasetVersionRow, version.version_id)
        row.upload_plaintext_digest = "sha256:" + "9" * 64

    assert store.get_dataset_version(version.version_id) == version


def test_a_run_that_never_completed_cannot_have_a_package_written_to_it(
    factory: sessionmaker,
) -> None:
    """`FR-111` puts the digest on the pipeline, and only the completion transition records it.

    Writing a package field without moving the state is not a completion -- it is a run claiming a
    result it never declared finishing -- so it is refused even while the run is still `started`.
    `complete_analysis_run` is the one path that writes these columns.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )

    with (
        pytest.raises(ValueError, match="cannot be completed again"),
        factory.begin() as database,
    ):
        row = database.get(AnalysisRunRow, run.run_id)
        row.package_digest = "sha256:" + "8" * 64


def test_the_guard_permits_exactly_the_retention_columns(factory: sessionmaker) -> None:
    """The allowlist is asserted as an equality, not as "retention still works".

    A guard widened to admit one more column would keep every other test here green, because they
    all exercise the *permitted* path. This names the extent, the way `W1-01`'s field-set tests do.

    `sealed_at` is in the set and is not a loosening: it is writable *once*, and
    `_refuse_content_update` refuses the second change through `_one_way`. The unconditional
    allowlist and the one-way rules are separate properties, so they get separate tests --
    collapsing them would let a mutant that dropped the one-way check pass on this one.
    """
    assert {"retention_state", "retention_changed_at", "sealed_at"} == MUTABLE_COLUMNS


def test_the_append_only_refusal_is_the_constant_and_nothing_else(
    factory: sessionmaker,
) -> None:
    """The message is exactly `APPEND_ONLY_FAILURE`, with nothing appended.

    Added because a mutant survived: appending `changed={...}` -- the set of column names the
    caller touched -- left all forty tests green. The content-free test below could not see it,
    because it asserts the absence of caller *values* and column names are not values, so it
    passed for a reason unrelated to what the mutant did.

    Column names are schema rather than customer data, so this is a weaker leak than echoing a
    value. But `rca/errors.py`'s discipline is that a refusal names the constraint, and a message
    that varies with what the caller touched says more than that. Asserting equality with the
    constant is the only form of this test a message-shaped mutant cannot slip past.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with pytest.raises(ValueError) as caught, factory.begin() as database:
        row = database.get(DatasetVersionRow, version.version_id)
        row.upload_media_type = "text/plain"

    assert str(caught.value) == APPEND_ONLY_FAILURE


def test_the_append_only_refusal_does_not_echo_the_rejected_content(
    factory: sessionmaker,
) -> None:
    """Content-free per `rca/errors.py`: refusing a write must not log what was being written."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with pytest.raises(ValueError) as caught, factory.begin() as database:
        row = database.get(DatasetVersionRow, version.version_id)
        row.upload_media_type = "text/acme-pharmacy-secret"
    assert "acme" not in str(caught.value).lower()


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


# --- The run-state vocabulary is enforced at the schema boundary too --------------------------


def test_the_run_state_column_refuses_a_state_the_domain_does_not_name(
    factory: sessionmaker,
) -> None:
    """`W1-01` enforced `RUN_STATES` in `RunOutcome.__post_init__`; the column had no constraint.

    The asymmetry was the defect, and this module's own docstring had claimed the vocabulary was
    "enforced twice" while saying so only about retention. A row written by any path other than
    this store could hold an unnamed state, and the read that rebuilt it would raise inside
    `RunOutcome` -- so one malformed row broke a whole scoped listing rather than itself.

    Written through the row class directly, because that is the path a constraint has to cover:
    the store cannot produce this row, which is exactly why the store is not where the check
    belongs.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with pytest.raises(IntegrityError), factory.begin() as database:
        database.add(
            AnalysisRunRow(
                run_id="run_forged",
                version_id=version.version_id,
                owner_id=scope,
                state="cancelled",
                started_at=NOW,
                retention_state=RETENTION_ACTIVE,
            )
        )


@pytest.mark.parametrize("state", RUN_STATES)
def test_the_column_accepts_every_state_the_domain_publishes(
    factory: sessionmaker, state: str
) -> None:
    """Asserted over `RUN_STATES` rather than a hand-picked value, so a constraint narrower than
    the domain fails here rather than at the first run that reaches it."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with factory.begin() as database:
        database.add(
            AnalysisRunRow(
                run_id=f"run_{state}",
                version_id=version.version_id,
                owner_id=scope,
                state=state,
                started_at=NOW,
                retention_state=RETENTION_ACTIVE,
            )
        )

    read = store.get_analysis_run(f"run_{state}")
    assert read is not None
    assert read.state == state


# --- One-way transitions, which an allowlist alone does not express ---------------------------


def test_a_tombstoned_version_cannot_return_to_active(factory: sessionmaker) -> None:
    """`KHEPRI-DEC-033`: a tombstone is not an undoable soft delete.

    `set_retention_state` accepted any member of `RETENTION_STATES`, so `active` after
    `tombstoned` un-deleted the row and a later read presented something the decision says is
    gone. Review on `#370` found it -- the same shape as re-sealing, which this slice already
    refused for the same reason, applied to the transition it had shipped rather than the one it
    had reasoned about.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    store.tombstone_dataset_version(version.version_id, now=LATER)

    with pytest.raises(ValueError, match="cannot return to an earlier retention state"):
        store.set_retention_state(version.version_id, RETENTION_ACTIVE, now=LATER)

    assert store.retention_state(version.version_id) == RETENTION_TOMBSTONED


def test_a_tombstone_may_be_repeated(factory: sessionmaker) -> None:
    """Setting `tombstoned` on a tombstoned row is not a reversal, so it is not refused.

    `FR-123` requires deletion to be idempotent -- "a repeated request for an object already
    deleted or tombstoned MUST succeed with the same response as the first". A guard that refused
    every write to a tombstoned row would satisfy the one-way rule and break idempotency, so the
    check is on the *direction* rather than on the prior state alone.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    store.tombstone_dataset_version(version.version_id, now=NOW)
    store.tombstone_dataset_version(version.version_id, now=LATER)

    assert store.retention_state(version.version_id) == RETENTION_TOMBSTONED


def test_sealing_is_refused_by_the_guard_and_not_only_by_the_store(
    factory: sessionmaker,
) -> None:
    """The one-way rule holds for a caller who does not use `seal_dataset_version`.

    `seal_dataset_version` returns `False` on a second call, which is the store being polite. The
    property that matters is that the *guard* refuses the write, because an earlier version of
    this code used bulk DML to write around the guard -- and a mapper listener does not fire for
    bulk DML, which made the guard's coverage claim false. That bypass is gone; this asserts the
    guard rather than the method.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    store.seal_dataset_version(version.version_id, now=NOW)

    with pytest.raises(ValueError, match="cannot be sealed again"), factory.begin() as database:
        row = database.get(DatasetVersionRow, version.version_id)
        row.sealed_at = LATER


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


# --- A binding is immutable, and no workspace row is deleted -----------------------------------


def _published(store: SqlWorkspaceStore, scope: str) -> tuple[str, str]:
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    store.add_artifact_binding(
        ArtifactBinding.create(
            owner_id=scope,
            run_id=run.run_id,
            artifact=PublishedArtifact(surface="web", artifact_digest="sha256:" + "a" * 64),
            now=NOW,
        )
    )
    with store._factory() as database:
        binding_id = database.execute(select(ArtifactBindingRow.binding_id)).scalars().one()
    return version.version_id, binding_id


def test_a_published_binding_cannot_be_repointed_at_other_content(
    factory: sessionmaker,
) -> None:
    """`FR-111` binds a retained artifact *by digest*, so the digest is the provenance.

    The update guard was registered on dataset versions and runs and not on bindings -- so a
    caller could change `artifact_digest` and silently repoint a published result at different
    content, which is precisely what binding by digest exists to prevent. Review on `#370` found
    the omission, and it is the kind a parity check between two of three tables would miss.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    _, binding_id = _published(store, scope)

    with (
        pytest.raises(ValueError, match="cannot change after it is written"),
        factory.begin() as database,
    ):
        database.get(ArtifactBindingRow, binding_id).artifact_digest = "sha256:" + "b" * 64


@pytest.mark.parametrize("column", ["surface", "run_id", "owner_id"])
def test_no_field_of_a_binding_may_change(factory: sessionmaker, column: str) -> None:
    """Asserted per column rather than on the digest alone: repointing the *surface* or the
    parent run rewrites the same provenance from a different direction."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    _, binding_id = _published(store, scope)

    with (
        pytest.raises(ValueError, match="cannot change after it is written"),
        factory.begin() as database,
    ):
        setattr(database.get(ArtifactBindingRow, binding_id), column, "reassigned")


@pytest.mark.parametrize(
    "row_class",
    [DatasetVersionRow, AnalysisRunRow, ArtifactBindingRow],
)
def test_no_workspace_row_can_be_deleted(factory: sessionmaker, row_class: type) -> None:
    """`ondelete="RESTRICT"` protects a *referenced* row, and an unreferenced one deleted cleanly.

    A dataset version with no runs, or any binding, has no referent -- so the append-only
    guarantee held only for rows that happened to have children, which review on `#370` named.
    `KHEPRI-DEC-033` moves a record out of use by tombstoning rather than erasure, because
    deletion has to leave evidence and an erased row leaves none.

    Parameterized over all three tables because the earlier update guard covered two of them, and
    a guard applied to a subset is how this class of gap appears.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version_id, binding_id = _published(store, scope)
    identifier = {
        DatasetVersionRow: version_id,
        ArtifactBindingRow: binding_id,
    }.get(row_class)
    if identifier is None:
        with factory() as database:
            identifier = database.execute(select(AnalysisRunRow.run_id)).scalars().one()

    with (
        pytest.raises(ValueError, match="removed through its retention lifecycle"),
        factory.begin() as database,
    ):
        database.delete(database.get(row_class, identifier))


def test_tombstoning_remains_the_way_a_record_leaves_use(factory: sessionmaker) -> None:
    """The delete guard must not have closed the path `KHEPRI-DEC-033` actually prescribes."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    store.tombstone_dataset_version(version.version_id, now=LATER)

    assert store.retention_state(version.version_id) == RETENTION_TOMBSTONED
    assert store.get_dataset_version(version.version_id) == version


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
    with factory.begin() as database:
        database.add(
            SourceProfileRow(
                profile_id="prf_abc123",
                owner_id=scope,
                source_version_id="dsv_abc123",
                column_labels='["date", "sku", "qty"]',
                proposed_mapping='[["date", "transaction_date"]]',
                created_at=NOW,
            )
        )

    with factory() as database:
        row = database.get(SourceProfileRow, "prf_abc123")
        assert row is not None
        assert row.owner_id == scope
        assert row.source_version_id == "dsv_abc123"


def test_a_source_profile_is_mutable_and_deletable(factory: sessionmaker) -> None:
    """The one workspace table exempt from both guards, and the exemption is the decision.

    `KHEPRI-DEC-033` §3's tombstone table gives a row to dataset versions and to runs, and for a
    source profile says **"none -- purged, not tombstoned"** -- because the live profile holds
    sanitized customer column headers and min/max values, none of which may survive. A blanket
    delete guard would have made the purge the decision prescribes impossible, which is the same
    shape as the guard that had made run completion impossible.

    It is mutable for a separate reason: `FR-115` makes a profile descriptive metadata a surface
    reads, never authority, so freezing it would protect nothing.
    """
    scope = _scope(factory)
    with factory.begin() as database:
        database.add(
            SourceProfileRow(
                profile_id="prf_mutable",
                owner_id=scope,
                source_version_id="dsv_abc123",
                column_labels="[]",
                proposed_mapping="[]",
                created_at=NOW,
            )
        )

    with factory.begin() as database:
        database.get(SourceProfileRow, "prf_mutable").source_version_id = "dsv_later"

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
        "section_states",
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
