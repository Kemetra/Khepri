"""`FR-109` isolation across the `W1-02` workspace: one scope never reads, names or keeps another's.

Split from `test_w102_workspace_guards.py` on `#370` along a seam that names something: every test
here is about a *boundary* -- a child row naming a version or run in another scope, a source profile
whose scope or source could be reassigned, and a tombstoned row that a live read must not return.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
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
    RETENTION_TOMBSTONED,
    AnalysisRunRow,
    DatasetVersionRow,
    SourceProfileRow,
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


# --- One scope never names, keeps or reads another's rows ------------------------------------


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
    store = SqlWorkspaceRecordStore(factory)
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
    store = SqlWorkspaceRecordStore(factory)
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


def test_a_profile_cannot_name_a_version_in_another_scope(factory: sessionmaker) -> None:
    """`owner_id` alone was the only validation, so a profile could claim scope A while naming a
    version belonging to scope B -- a cross-tenant source association the reuse surface would read
    as its own. Review on `#370` found the new table short of the composite key runs and bindings
    already carried.
    """
    other = _scope(factory, email="other@example.test")
    mine = _scope(factory)
    theirs = _version(SqlWorkspaceRecordStore(factory), other)

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
    version = _version(SqlWorkspaceRecordStore(factory), scope)
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
    store = SqlWorkspaceRecordStore(factory)
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
    version = _version(SqlWorkspaceRecordStore(factory), scope)
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


def test_a_tombstoned_version_is_absent_from_every_live_read(factory: sessionmaker) -> None:
    """`DatasetVersion` carries no retention state by `W1-01`'s design, so a tombstoned row read
    back is indistinguishable from a live one and a caller may keep presenting or reusing it.
    Review on `#370` found all four read paths filtering by scope alone. The store still answers
    `retention_state()`; the live reads answer nothing.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
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
    store = SqlWorkspaceRecordStore(factory)
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
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)

    store.tombstone_dataset_version(version.version_id, now=NOW)
    store.tombstone_dataset_version(version.version_id, now=LATER)

    with factory() as database:
        row = database.get(DatasetVersionRow, version.version_id)
        assert row.retention_changed_at is not None
        assert row.retention_state == RETENTION_TOMBSTONED


# --- A deleted input gains no new derivatives ---------------------------------------------------


def test_a_run_cannot_be_added_under_a_tombstoned_version(factory: sessionmaker) -> None:
    """The composite foreign key proves the version exists in this scope, and nothing more.

    A pipeline racing a deletion could create a new *live* run of an input the customer had just
    withdrawn -- inserted after the tombstone, listed by `analysis_runs_for_scope`, and never
    reached by `KHEPRI-DEC-033` §3's cascade because it did not exist when the cascade ran. Review
    on `#370` found it. Refused with a content-free message, like every other refusal here.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)
    store.tombstone_dataset_version(version.version_id, now=NOW)

    with pytest.raises(ValueError, match="has been deleted"):
        store.add_analysis_run(
            AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=LATER)
        )

    assert store.analysis_runs_for_scope(scope) == ()


def test_a_binding_cannot_be_added_under_a_tombstoned_run(factory: sessionmaker) -> None:
    """The same window one level down, which the review did not name.

    A rule covering runs-under-versions and not bindings-under-runs is the asymmetry this module
    was caught on with the read filter: the finding named two of four paths. Both parents now.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    with factory.begin() as database:
        row = database.get(AnalysisRunRow, run.run_id)
        row.retention_state = RETENTION_TOMBSTONED
        row.retention_changed_at = LATER

    with pytest.raises(ValueError, match="has been deleted"):
        store.add_artifact_binding(
            ArtifactBinding.create(
                owner_id=scope,
                run_id=run.run_id,
                artifact=PublishedArtifact(surface="web", artifact_digest="sha256:" + "a" * 64),
                now=LATER,
            )
        )

    assert store.artifact_bindings_for_run(run.run_id) == ()


def test_a_missing_or_foreign_parent_is_still_the_foreign_keys_to_refuse(
    factory: sessionmaker,
) -> None:
    """The liveness check must not have swallowed the schema's own refusals.

    A store check that intercepted a missing or cross-scope parent with `ValueError` would leave the
    composite foreign key unexercised by any test, so dropping it would pass unnoticed. Those two
    cases still reach the database and still fail as `IntegrityError`; the store adds only the case
    the foreign key cannot see -- a parent that is real, ours, and deleted.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)

    with pytest.raises(IntegrityError):
        store.add_analysis_run(
            AnalysisRun.create(owner_id=scope, version_id="dsv_nothere", now=NOW)
        )


def test_bindings_of_a_tombstoned_run_are_absent_from_live_reads(factory: sessionmaker) -> None:
    """The fifth read path. A binding has no retention state; it is read *through* its run.

    Counting getters and listings gave four paths and missed the one that reads by parent. A run
    tombstoned while its bindings remain -- partial, restored or concurrent deletion -- would hand
    back the withdrawn artifacts' digests here while `get_analysis_run` hid the run. Review on
    `#370` found it. Asserted with and without the scope argument, and against a live run too, so
    the join has not emptied the read.
    """
    scope = _scope(factory)
    store = SqlWorkspaceRecordStore(factory)
    version = _version(store, scope)
    kept = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    gone = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=LATER)
    )
    for run in (kept, gone):
        store.add_artifact_binding(
            ArtifactBinding.create(
                owner_id=scope,
                run_id=run.run_id,
                artifact=PublishedArtifact(surface="web", artifact_digest="sha256:" + "b" * 64),
                now=LATER,
            )
        )
    with factory.begin() as database:
        row = database.get(AnalysisRunRow, gone.run_id)
        row.retention_state = RETENTION_TOMBSTONED
        row.retention_changed_at = LATER

    assert store.artifact_bindings_for_run(gone.run_id) == ()
    assert store.artifact_bindings_for_run(gone.run_id, owner_id=scope) == ()
    assert len(store.artifact_bindings_for_run(kept.run_id)) == 1
