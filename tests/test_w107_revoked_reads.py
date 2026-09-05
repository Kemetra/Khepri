"""`W1-07a` -- every workspace read excludes a revoked object (`FR-126`).

`test_w107_restore_and_copy` establishes the guarantee on the two reads that go through
`_live_in`. This module is the **extent**: it drives each remaining read path over a restored
version and asserts none of them hands it back.

Why a module of its own, and why the extent test at the end. Review on `#382` found the ledger
consulted by `dataset_versions_for_scope` and by `_live_in`, and by nothing else -- so the retry
lookup, the run listing and both artifact-binding reads returned rows belonging to a version the
customer had deleted. A per-path test fixes the four that exist today; `test_every_scope_read_...`
is what fails when a fifth is added, which is the recurring shape recorded against this repo (*a
guard that names its own scope disarms itself*).

The runs and the bindings carry no revocation of their own. The ledger records the **ending the
owner requested** -- the version -- and everything beneath it is revoked derivatively, through the
parent, exactly as `_cascade_tombstone_to_runs` already tombstones them. A second ledger row per
run would be a second definition of the same fact.
"""

from __future__ import annotations

from sqlalchemy import text

from tests.w104_support import member
from tests.w107_support import NOW, deletion_service, journey, sealed_version


def _restored(j, who) -> object:
    """A version this scope deleted, then put back live beneath the ORM by a restore."""
    version, _run = sealed_version(j, who, with_run=True)
    deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )
    with j.w.factory() as database:
        database.execute(
            text(
                "UPDATE rca_workspace_dataset_versions "
                "SET retention_state='active' WHERE version_id=:v"
            ),
            {"v": version.version_id},
        )
        database.execute(
            text(
                "UPDATE rca_workspace_analysis_runs "
                "SET retention_state='active' WHERE version_id=:v"
            ),
            {"v": version.version_id},
        )
        database.commit()
    return version


def test_the_upload_retry_lookup_does_not_return_a_revoked_version() -> None:
    """`dataset_version_for_upload` is how `W1-04` makes version creation idempotent. A revoked
    version returned here does not merely leak a read: the next upload of the same bytes would be
    *bound to the deleted version* and treated as an already-recorded retry, so the customer's new
    data would join a record they deleted."""
    j = journey()
    who = member(j.w)
    version = _restored(j, who)

    found = j.w.store.dataset_version_for_upload(who.owner_id, version.upload_ciphertext_digest)

    assert found is None


def test_the_run_listing_does_not_return_runs_of_a_revoked_version() -> None:
    """A run outlives its version's `retention_state` under a restore, so the listing must ask the
    ledger about the parent rather than trust the row it is reading."""
    j = journey()
    who = member(j.w)
    _restored(j, who)

    assert j.w.store.analysis_runs_for_scope(who.owner_id) == ()


def test_the_scopes_bindings_do_not_include_a_revoked_versions_artifacts() -> None:
    """The spine reads bindings per scope to state whether each run's report is available. A
    binding handed back here is a live download address for a deleted analysis."""
    j = journey()
    who = member(j.w)
    _restored(j, who)

    assert j.w.store.artifact_bindings_for_scope(who.owner_id) == ()


def test_a_runs_own_bindings_do_not_survive_its_versions_revocation() -> None:
    """The read-by-parent path, which `#370` found was the one the earlier count of four missed."""
    j = journey()
    who = member(j.w)
    version, run = sealed_version(j, who, with_run=True)
    deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )
    with j.w.factory() as database:
        database.execute(
            text(
                "UPDATE rca_workspace_analysis_runs "
                "SET retention_state='active' WHERE version_id=:v"
            ),
            {"v": version.version_id},
        )
        database.commit()

    assert j.w.store.artifact_bindings_for_run(run.run_id, who.owner_id) == ()


def test_every_scope_read_excludes_a_revoked_version() -> None:
    """The extent assertion: a read added later that forgets the ledger fails here.

    Named per read rather than derived from the class, because the store's scope reads do not
    share a signature -- but the list is asserted against the store's own public reads, so a new
    one is not silently outside it.
    """
    j = journey()
    who = member(j.w)
    version = _restored(j, who)
    store = j.w.store

    returned = {
        "dataset_versions_for_scope": store.dataset_versions_for_scope(who.owner_id),
        "analysis_runs_for_scope": store.analysis_runs_for_scope(who.owner_id),
        "artifact_bindings_for_scope": store.artifact_bindings_for_scope(who.owner_id),
        "dataset_version_for_upload": store.dataset_version_for_upload(
            who.owner_id, version.upload_ciphertext_digest
        ),
        "history_for_scope.versions": store.history_for_scope(who.owner_id).versions,
        "history_for_scope.runs": store.history_for_scope(who.owner_id).runs,
        "history_for_scope.bindings": store.history_for_scope(who.owner_id).bindings,
    }

    leaked = {name: rows for name, rows in returned.items() if rows}
    assert not leaked, f"revoked version reachable through: {sorted(leaked)}"

    scope_reads = {
        name
        for name in dir(store)
        if name.endswith("_for_scope") and not name.startswith("_")
    }
    unchecked = scope_reads - {name.split(".")[0] for name in returned}
    assert unchecked <= {"tombstones_for_scope", "audit_events_for_scope"}, (
        f"a scope read this extent test does not cover: {sorted(unchecked)}"
    )
