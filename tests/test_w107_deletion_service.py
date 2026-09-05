"""`W1-07a` -- the workspace deletion service (`RCA-005` `FR-123`, `FR-124`).

`FR-123` makes three separate claims about a repeated deletion, and they are asserted separately
here because one outcome test passes with two of the three broken: the response is the same, **no
new deletion evidence** is written, and **one** audit event is emitted with outcome
`already_deleted`.

The cascade beneath this service already exists. `store.set_retention_state` locks the version row,
writes its tombstone, cascades to every live run's tombstone, and returns early on a repeat without
moving `retention_changed_at`. This service composes that; it does not reimplement the walk.
"""

from __future__ import annotations

from khepri.rca.workspace.audit import (
    ACTION_VERSION_DELETED,
    OUTCOME_ALREADY_DELETED,
    OUTCOME_COMPLETED,
)
from tests.w104_support import member
from tests.w107_support import (
    LATER,
    NOW,
    audit_events_for,
    deletion_service,
    journey,
    sealed_version,
)


def test_deleting_a_version_tombstones_it_and_its_runs() -> None:
    """`KHEPRI-DEC-033` §1: a named cascade is part of the parent's deletion. The run ends because
    its version did, and the tombstone is what the history spine shows in its place (`FR-117`)."""
    j = journey()
    who = member(j.w)
    version, run = sealed_version(j, who, with_run=True)

    service = deletion_service(j)
    service.delete_version(who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW)

    kinds = {type(t).__name__ for t in j.w.store.tombstones_for_scope(who.owner_id)}
    assert kinds == {"VersionTombstone", "RunTombstone"}
    assert j.w.store.get_dataset_version(version.version_id, who.owner_id) is None
    assert run is not None


def test_a_repeated_deletion_answers_the_same() -> None:
    """`FR-123` claim 1 of 3: a repeat succeeds with the same response as the first."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)
    service = deletion_service(j)

    first = service.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )
    second = service.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=LATER
    )

    assert first.version_id == second.version_id
    assert first.deleted is True
    assert second.deleted is False


def test_a_repeated_deletion_writes_no_second_evidence() -> None:
    """`FR-123` claim 2 of 3, and `FR-124`: evidence is written once per object per ending."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)
    service = deletion_service(j)

    service.delete_version(who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW)
    before = j.w.store.tombstones_for_scope(who.owner_id)
    service.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=LATER
    )

    after = j.w.store.tombstones_for_scope(who.owner_id)
    assert [t.deleted_at for t in after] == [t.deleted_at for t in before], (
        "a repeat re-recorded the ending, moving the horizon it anchors"
    )


def test_a_repeated_deletion_emits_one_already_deleted_event() -> None:
    """`FR-123` claim 3 of 3: one audit event, with the outcome the requirement names."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)
    service = deletion_service(j)

    service.delete_version(who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW)
    service.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=LATER
    )

    outcomes = [
        event.outcome
        for event in audit_events_for(j, who.owner_id)
        if event.action == ACTION_VERSION_DELETED
    ]
    assert outcomes == [OUTCOME_COMPLETED, OUTCOME_ALREADY_DELETED]


def test_a_deleted_version_is_revoked_so_a_restore_cannot_read_it() -> None:
    """`FR-126`. The ledger entry is written as part of the deletion, not by a later pass."""
    from khepri.rca.workspace.audit import OBJECT_VERSION
    from khepri.rca.workspace.revocation import SqlRevocationLedger

    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)

    deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )

    ledger = SqlRevocationLedger(j.w.factory)
    assert ledger.is_revoked(OBJECT_VERSION, version.version_id, who.owner_id) is True
