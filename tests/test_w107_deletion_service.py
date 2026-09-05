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

import pytest

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
    deletion_jobs_for,
    deletion_service,
    journey,
    sealed_version,
    uploads_for,
)


def test_deleting_a_version_tombstones_it_and_its_runs() -> None:
    """`KHEPRI-DEC-033` §1: a named cascade is part of the parent's deletion. The run ends because
    its version did, and the tombstone is what the history spine shows in its place (`FR-117`)."""
    j = journey()
    who = member(j.w)
    version, run = sealed_version(j, who, with_run=True)

    service = deletion_service(j)
    service.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )

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


def test_a_repeated_deletion_performs_no_second_ending() -> None:
    """`FR-123` claim 2 of 3: a repeat writes no new deletion record.

    **Asserted against the store verb, not against the tombstone's instant.** An earlier version of
    this test compared `deleted_at` before and after, and could not fail: `set_retention_state`'s
    own early return (`store.py:631`) already makes a second tombstone a no-op, so the instant is
    unmoved whatever this service does. That assertion tested the *store's* guarantee while
    claiming to test this one -- a redundant guard with no separate evidence.

    What this service controls is whether it reaches the ending at all, so that is what is
    counted. `FR-124`'s evidence record is written by the `RRA` deletion path, which this slice
    does not yet call; when it does, this test gains the evidence count beside the call count.
    """
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)
    service = deletion_service(j)
    endings: list[str] = []
    real = j.w.store.tombstone_dataset_version

    def counted(version_id: str, **kwargs: object) -> None:
        endings.append(version_id)
        return real(version_id, **kwargs)

    j.w.store.tombstone_dataset_version = counted  # type: ignore[method-assign]
    try:
        service.delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
        )
        service.delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=LATER
        )
    finally:
        j.w.store.tombstone_dataset_version = real  # type: ignore[method-assign]

    assert endings == [version.version_id], (
        f"the repeat reached the ending again: {endings}"
    )


def test_a_repeated_deletion_emits_one_already_deleted_event() -> None:
    """`FR-123` claim 3 of 3: one audit event, with the outcome the requirement names."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)
    service = deletion_service(j)

    service.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )
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


def test_deleting_a_version_ends_the_content_it_was_derived_from() -> None:
    """`KHEPRI-DEC-033` §1: derived content never outlives its input's right to exist. Deleting the
    dataset version must end the upload it was admitted from and everything derived, so the ending
    reaches the `RRA` deletion path -- not only the `RCA` records.

    The version holds the upload's *digests* and no session identifier (`KHEPRI-DEC-033` §3 fixes
    what a version may keep), so the runtime bridges on `ciphertext_sha256_hex`, which is already
    the key `dataset_version_for_upload` joins on.
    """
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)

    deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )

    assert uploads_for(j, who.owner_id) == (), "the upload outlived the version derived from it"


def test_a_repeated_deletion_does_not_begin_a_second_rra_job() -> None:
    """`FR-124`: evidence is written once per object per ending, and an `RRA` deletion job is what
    writes it. A repeat that began a second job would write a second evidence record for one
    ending -- `FR-123`'s "no new deletion evidence", reached through the content side."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who)
    service = deletion_service(j)

    service.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )
    first = deletion_jobs_for(j, who.owner_id)
    service.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=LATER
    )

    assert deletion_jobs_for(j, who.owner_id) == first


def test_a_fault_after_the_tombstone_leaves_nothing_partially_ended() -> None:
    """The ending's records commit together or not at all (`FR-123`, `FR-125`).

    Review on `#382` found the tombstone, the revocation and the audit event each committing in
    their own transaction. The fatal ordering was tombstone-then-fault: the version reads back as
    `None`, so `delete_version`'s own already-ended guard treats the next attempt as complete and
    returns `deleted=False` **without ever writing the ledger row**. The deletion is then
    unrepairable by retry -- a version withdrawn from every read, with no revocation recorded, so
    a restore makes it readable again and `FR-126` is silently unmet.

    `W1-04` solved this exact shape for recording (`unit_of_work`'s docstring: "a fault between
    the two left a version persisted with no event"); this asserts the deletion path joins it.

    The fault is injected at the ledger because it sits between the two writes whose disagreement
    is unrecoverable. What is asserted is the *effect* -- the version still reads back -- and not
    the exception, so the test fails if the rollback is missing rather than if the raise is.
    """
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who, with_run=True)

    service = deletion_service(j)

    class _FailingLedger:
        def revoke(self, revoked):
            raise RuntimeError("the ledger write failed")

    object.__setattr__(service._sources, "ledger", _FailingLedger())

    with pytest.raises(RuntimeError, match="the ledger write failed"):
        service.delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
        )

    still_there = j.w.store.get_dataset_version(version.version_id, who.owner_id)
    assert still_there is not None, "the tombstone committed without its revocation"


def test_a_fault_rolls_back_the_endings_audit_event_too() -> None:
    """`FR-125`: one action, one event. A rolled-back ending must leave no `completed` event
    claiming it happened -- which is the same window `#372` found on the recording side."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who, with_run=True)

    service = deletion_service(j)

    class _FailingAudit:
        def __init__(self, real):
            self._real = real

        def record(self, event):
            if event.outcome == "completed":
                raise RuntimeError("the audit write failed")
            return self._real.record(event)

        def events_for_scope(self, owner_id):
            return self._real.events_for_scope(owner_id)

    object.__setattr__(service._sources, "audit", _FailingAudit(j.w.audit))

    with pytest.raises(RuntimeError, match="the audit write failed"):
        service.delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
        )

    assert j.w.store.get_dataset_version(version.version_id, who.owner_id) is not None
    assert not j.w.audit.events_for_scope(who.owner_id) or all(
        event.action != ACTION_VERSION_DELETED
        for event in j.w.audit.events_for_scope(who.owner_id)
    )
