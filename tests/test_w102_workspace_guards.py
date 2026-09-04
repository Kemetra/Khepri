"""What the `W1-02` workspace schema and its guards refuse (`FR-112`, `KHEPRI-DEC-033` §3).

Split from `test_w102_workspace_persistence.py`, which had grown to thirteen responsibilities
across eighty functions -- CodeScene flagged it three ways on `#370` and all three were the same
observation. The seam is what each half asserts about: this file covers what the *schema* and the
ORM guards refuse, and the other covers what the store *does*.

The split preserved every test: no function was renamed, merged or dropped, and the counts before
and after are asserted in the commit that made it.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.records import Sealed
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_STATES,
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
    RunOutcome,
)
from khepri.rca.workspace.persistence import (
    _ROW_GUARDS,
    APPEND_ONLY_FAILURE,
    MUTABLE_COLUMNS,
    RETENTION_ACTIVE,
    RETENTION_STATES,
    RETENTION_TOMBSTONED,
    AnalysisRunRow,
    ArtifactBindingRow,
    DatasetVersionRow,
    SourceProfileRow,
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
    exists on the table and the transition is a store operation -- and because the record carries
    no retention state, a tombstoned row is not read back as a `DatasetVersion` at all:
    `retention_state()` is the store's answer, and `get_dataset_version()` answers `None`.

    This test used to assert the record *was* read back unchanged after tombstoning, which is the
    defect review on `#370` found: a caller could keep presenting a version the customer deleted.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    assert store.retention_state(version.version_id) == RETENTION_ACTIVE

    store.tombstone_dataset_version(version.version_id, now=LATER)

    assert store.retention_state(version.version_id) == RETENTION_TOMBSTONED
    # A tombstoned version is not read back as live: the record carries no retention state,
    # so returning it would be indistinguishable from a live one. Review on `#370` found
    # this line asserting the opposite.
    assert store.get_dataset_version(version.version_id) is None


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
    the domain fails here rather than at the first run that reaches it.

    `completed` carries its provenance because `RunOutcome` now requires it -- reading such a row
    back constructs one, and `FR-111` says a completed run names the package it produced. The row
    written here without it was one the domain says cannot exist, which the new rule caught.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    provenance = (
        {
            "package_digest": "sha256:abc",
            "package_version": "1.0.0",
            "formula_version": "1.0.0",
            "completed_at": LATER,
        }
        if state == RUN_COMPLETED
        else {}
    )

    with factory.begin() as database:
        database.add(
            AnalysisRunRow(
                run_id=f"run_{state}",
                version_id=version.version_id,
                owner_id=scope,
                state=state,
                started_at=NOW,
                retention_state=RETENTION_ACTIVE,
                **provenance,
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
    # A tombstoned version is not read back as live: the record carries no retention state,
    # so returning it would be indistinguishable from a live one. Review on `#370` found
    # this line asserting the opposite.
    assert store.get_dataset_version(version.version_id) is None


# --- Round seven: what the schema constrains, and what a guard freezes -------------------------


def test_a_profile_cannot_name_a_version_in_another_scope(factory: sessionmaker) -> None:
    """`owner_id` alone was the only validation, so a profile could claim scope A while naming a
    version belonging to scope B -- a cross-tenant source association the reuse surface would read
    as its own. Review on `#370` found the new table short of the composite key runs and bindings
    already carried.
    """
    other = _scope(factory, email="other@example.test")
    mine = _scope(factory)
    theirs = _version(SqlWorkspaceStore(factory), other)

    with pytest.raises(IntegrityError), factory.begin() as database:
        database.add(
            SourceProfileRow(
                profile_id="prf_cross1",
                owner_id=mine,
                source_version_id=theirs.version_id,
                column_labels="[]",
                proposed_mapping="[]",
                created_at=NOW,
            )
        )


def test_a_profile_cannot_name_a_version_that_does_not_exist(factory: sessionmaker) -> None:
    """The other half of the same key: a dangling association is as unusable as a cross-tenant
    one -- the reuse surface would offer a profile whose source no longer exists.
    """
    scope = _scope(factory)

    with pytest.raises(IntegrityError), factory.begin() as database:
        database.add(
            SourceProfileRow(
                profile_id="prf_anglin",
                owner_id=scope,
                source_version_id="dsv_nothere",
                column_labels="[]",
                proposed_mapping="[]",
                created_at=NOW,
            )
        )


def test_a_profile_cannot_be_reassigned_to_another_scope(factory: sessionmaker) -> None:
    """Loading a profile from scope A and assigning a valid scope-B `owner_id` committed, because
    the foreign key verifies only that B exists. Scope B's next read would then return scope A's
    column labels. Review on `#370` found it, and the exemption that let it through was real but
    narrower than I had applied it: `KHEPRI-DEC-033` §3 exempts the profile from *deletion*
    guarding, never from ownership immutability.
    """
    scope = _scope(factory)
    other = _scope(factory, email="other@example.test")
    version = _version(SqlWorkspaceStore(factory), scope)
    with factory.begin() as database:
        database.add(
            SourceProfileRow(
                profile_id="prf_reassn",
                owner_id=scope,
                source_version_id=version.version_id,
                column_labels='["sku"]',
                proposed_mapping="[]",
                created_at=NOW,
            )
        )

    with pytest.raises(ValueError, match="cannot be reassigned"), factory.begin() as database:
        database.get(SourceProfileRow, "prf_reassn").owner_id = other


def test_a_profile_cannot_be_repointed_at_another_version(factory: sessionmaker) -> None:
    """`source_version_id` is identity too, and no constraint can pin it to its original value:
    repointing within the same scope satisfies the composite key perfectly.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    first = _version(store, scope)
    second = _version(store, scope)
    with factory.begin() as database:
        database.add(
            SourceProfileRow(
                profile_id="prf_repoin",
                owner_id=scope,
                source_version_id=first.version_id,
                column_labels="[]",
                proposed_mapping="[]",
                created_at=NOW,
            )
        )

    with pytest.raises(ValueError, match="cannot be reassigned"), factory.begin() as database:
        database.get(SourceProfileRow, "prf_repoin").source_version_id = second.version_id


def test_a_profile_document_is_still_mutable(factory: sessionmaker) -> None:
    """The freeze covers identity only. `FR-115` makes the document metadata a surface reads to
    pre-fill a form -- it carries no authority, and freezing it would protect nothing. A guard that
    froze the whole row would have made the profile useless for the thing it exists to do.
    """
    scope = _scope(factory)
    version = _version(SqlWorkspaceStore(factory), scope)
    with factory.begin() as database:
        database.add(
            SourceProfileRow(
                profile_id="prf_mutabl",
                owner_id=scope,
                source_version_id=version.version_id,
                column_labels='["old"]',
                proposed_mapping="[]",
                created_at=NOW,
            )
        )

    with factory.begin() as database:
        database.get(SourceProfileRow, "prf_mutabl").column_labels = '["new"]'

    with factory() as database:
        assert database.get(SourceProfileRow, "prf_mutabl").column_labels == '["new"]'


def test_every_workspace_row_class_declares_a_guard_shape() -> None:
    """A row class added later must state which of the three shapes it takes.

    The single registration loop this replaced was how two tables arrived unguarded: it named three
    classes and nothing noticed the other two were absent. Review on `#370` found both.
    """
    from khepri.rca.persistence import Base

    guarded = {row_class.__tablename__ for row_class in _ROW_GUARDS}
    declared = {name for name in Base.metadata.tables if name.startswith("rca_workspace_")}

    assert guarded == declared


def test_a_completion_must_carry_the_provenance_fr_111_requires() -> None:
    """`RunOutcome(state="completed")` validated with every provenance field `None`.

    `complete_analysis_run` then wrote it permanently and the append-only guard refused to fill
    the digest in later, leaving an immutable completed run naming no package. `FR-111` binds a run
    to what it produced, so an outcome that cannot name it is not a completion. Review on `#370`
    found it.
    """
    with pytest.raises(ValueError, match="must carry the package digest"):
        RunOutcome(state=RUN_COMPLETED)


@pytest.mark.parametrize(
    "missing", ["package_digest", "package_version", "formula_version", "completed_at"]
)
def test_a_completion_needs_every_provenance_field(missing: str) -> None:
    """One case per field, because a check reading only the digest passes three of these.

    Verified as a mutant: narrowing `_has_provenance` to `package_digest` alone leaves the
    single-case version of this test green.
    """
    complete = {
        "package_digest": "sha256:abc",
        "package_version": "1.0.0",
        "formula_version": "1.0.0",
        "completed_at": LATER,
    }
    complete[missing] = None

    with pytest.raises(ValueError, match="must carry the package digest"):
        RunOutcome(state=RUN_COMPLETED, **complete)


def test_a_failed_run_needs_no_provenance() -> None:
    """State-specific, not blanket: `failed` produced no package, so it names none."""
    assert RunOutcome(state=RUN_FAILED).package_digest is None


def test_the_retention_transition_locks_the_row_it_reads() -> None:
    """The clock cannot move on a concurrent duplicate, and only a lock can promise that.

    Asserted on the source rather than by racing two sessions, and the reason is the defect's own
    history: SQLite serializes writes, so two calls run in sequence, the second genuinely reads
    `tombstoned`, and the no-op check returns early -- a concurrency test on this engine passes
    with the lock removed. I removed the lock on this PR on exactly that evidence, and two
    reviewers found the PostgreSQL interleaving the engine had hidden: both transactions read
    `active`, both find the check false, and the second overwrites the first deletion instant.

    `test_the_locking_statements_emit_for_update_on_postgres` is the other half -- it compiles the
    statement and asserts the clause is really there.
    """
    import inspect as py_inspect

    source = py_inspect.getsource(SqlWorkspaceStore.set_retention_state)

    assert "version_for_update" in source
    assert "database.get(DatasetVersionRow" not in source


def test_sealing_a_live_version_is_still_allowed(factory: sessionmaker) -> None:
    """The freeze is terminal-state-specific, not a blanket ban on sealing."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    assert store.seal_dataset_version(version.version_id, now=LATER) is True


def test_a_tombstoned_run_cannot_be_completed(factory: sessionmaker) -> None:
    """The terminal check ran *inside* the completion branch's alternative, so it never fired.

    A tombstoned run still reads `started`, so `_refuse_content_update` took the completion branch
    and returned before `_check_terminal_state` -- and a deleted run could be given a package
    digest and a completion instant. Confirmed against the guard before fixing. Review on `#370`
    found it, and the fix is ordering: terminal state is a precondition on every path, not one
    more append-only rule.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    with factory.begin() as database:
        database.get(AnalysisRunRow, run.run_id).retention_state = RETENTION_TOMBSTONED

    with (
        pytest.raises(ValueError, match="accepts no further update"),
        factory.begin() as database,
    ):
        row = database.get(AnalysisRunRow, run.run_id)
        row.state = RUN_COMPLETED
        row.package_digest = "sha256:abc"
        row.package_version = "1.0.0"
        row.formula_version = "1.0.0"
        row.completed_at = LATER


def test_a_live_run_can_still_be_completed(factory: sessionmaker) -> None:
    """The ordering fix must not have made completion itself unreachable.

    The append-only guard had already made run completion impossible once on this PR; a check
    hoisted to run before every branch is exactly the shape that does it again.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )

    completed = store.complete_analysis_run(
        run.run_id,
        RunOutcome(
            state=RUN_COMPLETED,
            package_digest="sha256:abc",
            package_version="1.0.0",
            formula_version="1.0.0",
            completed_at=LATER,
        ),
    )

    assert completed is True


def test_a_binding_has_no_retention_lifecycle_and_the_guard_tolerates_it(
    factory: sessionmaker,
) -> None:
    """`ArtifactBindingRow` carries no `retention_state`, and it must not need one.

    Hoisting the terminal check to every path exposed the assumption that all three guarded row
    classes share the column. They do not, and the fix is for the guard to notice rather than for
    the schema to grow a column no rule reads -- "which rows have a retention lifecycle" is a
    property of the table, not a guard's precondition.
    """
    assert "retention_state" not in ArtifactBindingRow.__table__.columns


@pytest.mark.parametrize(
    "missing", ["package_digest", "package_version", "formula_version", "completed_at"]
)
def test_a_completed_row_without_provenance_is_refused_by_the_schema(
    factory: sessionmaker,
    missing: str,
) -> None:
    """Stated in the schema as well as in `RunOutcome`, and the duplication is the point.

    Enforced only in the dataclass, a malformed row still reaches the database -- and then raises
    on *read*, when `_run_from_row` constructs the `RunOutcome`. `analysis_runs_for_scope` fails
    for the whole scope, so one bad row becomes an outage for every run in the organization.
    Review on `#370` traced that path.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    provenance = {
        "package_digest": "sha256:abc",
        "package_version": "1.0.0",
        "formula_version": "1.0.0",
        "completed_at": LATER,
    }
    provenance[missing] = None

    # One case per field: a `CHECK` naming only `package_digest` satisfies three of these, and a
    # single all-fields-null case cannot tell that apart. Confirmed as mutant `K3`, which survived
    # the unparametrized version of this test.
    with pytest.raises(IntegrityError), factory.begin() as database:
        database.add(
            AnalysisRunRow(
                run_id=f"run_no{missing[:5]}",
                version_id=version.version_id,
                owner_id=scope,
                state=RUN_COMPLETED,
                started_at=NOW,
                retention_state=RETENTION_ACTIVE,
                **provenance,
            )
        )


@pytest.mark.parametrize("state", ["started", "failed"])
def test_a_non_completed_row_needs_no_provenance(factory: sessionmaker, state: str) -> None:
    """Conditional rather than `NOT NULL`: those states produced no package."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with factory.begin() as database:
        database.add(
            AnalysisRunRow(
                run_id=f"run_{state}p",
                version_id=version.version_id,
                owner_id=scope,
                state=state,
                started_at=NOW,
                retention_state=RETENTION_ACTIVE,
            )
        )

    with factory() as database:
        assert database.get(AnalysisRunRow, f"run_{state}p") is not None


@pytest.mark.parametrize(
    "missing", ["package_digest", "package_version", "formula_version", "completed_at"]
)
def test_an_orm_writer_cannot_complete_a_run_without_provenance(
    factory: sessionmaker,
    missing: str,
) -> None:
    """The third layer, and the one the other two miss.

    `RunOutcome.__post_init__` guards the door and `ck_rca_workspace_run_completion_provenance`
    guards the schema, but an ORM writer can load a `started` row and assign **only**
    `state = "completed"` -- which satisfies `_check_completion`'s changed-column allowlist while
    every provenance column stays null, and the `CHECK` is not re-evaluated for columns the
    statement does not touch. The row commits, then raises on *read* when `_run_from_row` builds
    the outcome, failing the whole scope's listing. Review on `#370` found it after the
    `RunOutcome` fix -- the same rule, one layer up.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )

    provenance = {
        "package_digest": "sha256:abc",
        "package_version": "1.0.0",
        "formula_version": "1.0.0",
        "completed_at": LATER,
    }
    provenance.pop(missing)

    # One case per field. This is the third place the same rule lives and the third time a single
    # all-fields-missing case proved too weak to pin it: mutant `L7`, narrowing the guard to
    # `package_digest` alone, survived that version. Any multi-field requirement needs a case per
    # field, because one omission cannot distinguish "checks one" from "checks all".
    with (
        pytest.raises(ValueError, match="must carry the package digest"),
        factory.begin() as database,
    ):
        row = database.get(AnalysisRunRow, run.run_id)
        row.state = RUN_COMPLETED
        for column, value in provenance.items():
            setattr(row, column, value)


def test_the_scope_listing_survives_every_run_a_writer_can_commit(
    factory: sessionmaker,
) -> None:
    """The consequence the finding named, asserted rather than reasoned about.

    A malformed completed row makes `analysis_runs_for_scope` raise for *every* run in the
    organization -- one bad row becomes an outage. With all three layers in place no writer can
    commit one, so the listing is total.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    store.complete_analysis_run(
        run.run_id,
        RunOutcome(
            state=RUN_COMPLETED,
            package_digest="sha256:abc",
            package_version="1.0.0",
            formula_version="1.0.0",
            completed_at=LATER,
        ),
    )

    listed = store.analysis_runs_for_scope(scope)

    assert [entry.run_id for entry in listed] == [run.run_id]


# --- Live reads exclude tombstoned rows --------------------------------------------------------


def test_a_tombstoned_version_is_absent_from_every_live_read(factory: sessionmaker) -> None:
    """`DatasetVersion` carries no retention state by `W1-01`'s design, so a tombstoned row read
    back is indistinguishable from a live one and a caller may keep presenting or reusing it.
    Review on `#370` found all four read paths filtering by scope alone. The store still answers
    `retention_state()`; the live reads answer nothing.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    kept = _version(store, scope)
    deleted = _version(store, scope)

    store.tombstone_dataset_version(deleted.version_id, now=LATER)

    assert store.get_dataset_version(deleted.version_id) is None
    assert store.get_dataset_version(kept.version_id) == kept
    assert [v.version_id for v in store.dataset_versions_for_scope(scope)] == [kept.version_id]
    assert store.retention_state(deleted.version_id) == RETENTION_TOMBSTONED


def test_a_tombstoned_run_is_absent_from_every_live_read(factory: sessionmaker) -> None:
    """The same hole on the run side, which the finding did not name -- a loop cannot miss what it
    never names, and neither can a review; the fix covers every read, not the two reported."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    kept = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    deleted = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=LATER)
    )
    with factory.begin() as database:
        row = database.get(AnalysisRunRow, deleted.run_id)
        row.retention_state = RETENTION_TOMBSTONED
        row.retention_changed_at = LATER

    assert store.get_analysis_run(deleted.run_id) is None
    assert store.get_analysis_run(kept.run_id) == kept
    assert [r.run_id for r in store.analysis_runs_for_scope(scope)] == [kept.run_id]


def test_the_transitions_still_reach_a_tombstoned_row(factory: sessionmaker) -> None:
    """The read filter must not have broken the idempotent retry: `tombstone_dataset_version` on
    an already-tombstoned row returns early *by reading it*, so it needs the weaker predicate."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    store.tombstone_dataset_version(version.version_id, now=NOW)
    store.tombstone_dataset_version(version.version_id, now=LATER)

    with factory() as database:
        row = database.get(DatasetVersionRow, version.version_id)
        assert row.retention_changed_at is not None
        assert row.retention_state == RETENTION_TOMBSTONED
