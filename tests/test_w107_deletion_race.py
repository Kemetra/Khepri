"""Two overlapping deletions of one version end it once (`#526` A-14; `RCA-005` `FR-123`).

`FR-123`: a repeated request for an object already deleted "MUST create **no new deletion
evidence**, and MUST emit **one audit event** (`FR-125`) with outcome `already_deleted`".
`delete_version` decided "already deleted" with an unlocked read taken before its unit of work.
Two requests that both passed that read both entered the unit; the second reached
`set_retention_state`'s idempotent early return -- which said nothing -- and then recorded a second
`completed` event and answered `deleted=True`, exactly as the first had.

**Forced here on SQLite, without threads.** The second request's read is taken, and then the whole
first request runs to completion before the second opens its unit of work -- the interleaving the
defect needs, reproduced every run. `test_concurrent_persistence_postgres.py` runs the genuine
two-connection race against PostgreSQL in CI.
"""

from __future__ import annotations

from sqlalchemy import func, select

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


def _evidence_count(j) -> int:
    from khepri.rra.persistence import DeletionEvidenceRow

    with j.w.factory() as database:
        return database.scalar(select(func.count()).select_from(DeletionEvidenceRow))


def test_a_deletion_overtaken_by_another_records_already_deleted() -> None:
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who, with_run=True)
    first = deletion_service(j)
    second = deletion_service(j)
    real_content = second._end_derived_content
    first_outcome = []

    def overtaken(version_row, now):
        # The second request has read the version live. Before it opens its unit of work, the
        # first request runs to completion.
        real_content(version_row, now)
        first_outcome.append(
            first.delete_version(
                who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
            )
        )

    second._end_derived_content = overtaken  # type: ignore[method-assign]
    outcome = second.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=LATER
    )

    assert first_outcome[0].deleted is True
    assert outcome.deleted is False, "both overlapping deletions answered deleted=True"
    outcomes = [
        event.outcome
        for event in audit_events_for(j, who.owner_id)
        if event.action == ACTION_VERSION_DELETED
    ]
    assert outcomes == [OUTCOME_COMPLETED, OUTCOME_ALREADY_DELETED], outcomes


def test_the_overtaken_deletion_writes_no_new_evidence() -> None:
    """`FR-123` claim 2, on the race path: the loser's content step meets an already-complete job
    and writes no evidence of its own."""
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who, with_run=True)
    first = deletion_service(j)
    second = deletion_service(j)
    real_content = second._end_derived_content
    counts = []

    def overtaken(version_row, now):
        first.delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
        )
        counts.append(_evidence_count(j))
        real_content(version_row, now)

    second._end_derived_content = overtaken  # type: ignore[method-assign]
    second.delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=LATER
    )

    assert counts[0] > 0, "the first deletion wrote no evidence, so this test measures nothing"
    assert _evidence_count(j) == counts[0]


def test_the_store_says_whether_this_call_ended_the_version() -> None:
    """The early return must be distinguishable, or the caller cannot tell a first ending from a
    repeat that was decided under the lock. A foreign scope ends nothing either."""
    j = journey()
    who = member(j.w)
    stranger = member(j.w, email="stranger@example.test", name="Other")
    version, _ = sealed_version(j, who)
    store = j.w.store

    foreign = store.tombstone_dataset_version(
        version.version_id, now=NOW, owner_id=stranger.owner_id
    )
    ended = store.tombstone_dataset_version(version.version_id, now=NOW, owner_id=who.owner_id)
    repeat = store.tombstone_dataset_version(version.version_id, now=LATER, owner_id=who.owner_id)

    assert (foreign, ended, repeat) == (False, True, False)
