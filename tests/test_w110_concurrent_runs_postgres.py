"""`FR-127`'s concurrent class at the run level, over PostgreSQL (`#388`, `W1-10`).

`#388` names "two concurrent runs against one version -- `FOR UPDATE` actually held". Two doors
can race a version's runs, and both are driven here with a forced overlap and a lock-wait proof:

- **A second run over one version, racing its deletion.** `add_analysis_run` locks the parent
  version (`store.py`, `version_for_update`) so a run is either added before the deletion, and
  cascades with it, or refused after. Driven through `WorkspaceRecording.start_run` inside
  `perform`, the unit `PipelineRecorder.requested` opens for it.
- **A run failing (`fail_run`, which takes only `run_for_update`) while it is deleted or settled.**
  The dead-letter door (`PipelineRecorder.abandoned`), against `delete_version`'s cascade
  (`live_runs_for_update`) and against a settlement (`record_completion`). This is where
  `run_for_update` is the only lock between the two.

**One run, two settling doors** is also here, and is labelled for what it is: the worker's
settlement and the reconcile sweep completing the *same* run. It is not `#388`'s two-runs case.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from khepri.rca.workspace.audit import (
    ACTION_RUN_COMPLETED,
    ACTION_RUN_STARTED,
    ACTOR_PIPELINE,
    OUTCOME_COMPLETED,
    AuditActor,
)
from khepri.rca.workspace.contracts import RUN_COMPLETED, RUN_FAILED
from khepri.rca.workspace.tombstones import RunTombstone
from khepri.runtime.workspace_recording import Attempt, WorkspaceRefused
from tests.w104_support import LATER, Member, member
from tests.w104b_support import Journey
from tests.w106_support import completed_run, started_run
from tests.w107_support import NOW, deletion_service, sealed_version
from tests.w110_postgres_support import (
    DefectStillPresent,
    Overlap,
    delivered_unsettled,
    outcomes_of,
    overlap_on_lock,
    postgres_journey,
    requires_postgres,
    tombstones_of,
)

pytestmark = [pytest.mark.concurrency, requires_postgres]

VERSIONS = "rca_workspace_dataset_versions"
RUNS = "rca_workspace_analysis_runs"


def _start_run(j: Journey, who: Member, version_id: str):
    """A run over `version_id`, started as `PipelineRecorder.requested` starts one: `start_run`
    inside `perform`'s unit of work."""
    recording = j.recorder.recording
    return lambda: recording.perform(
        AuditActor(owner_id=who.owner_id, actor_account_id=ACTOR_PIPELINE),
        Attempt(ACTION_RUN_STARTED, lambda: recording.start_run(who.owner_id, version_id, LATER)),
        now=LATER,
    )


def _delete(j: Journey, who: Member, version_id: str):
    return lambda: deletion_service(j).delete_version(
        who.owner_id, version_id, actor_account_id=who.account_id, now=NOW
    )


def _abandon(j: Journey, job_id: str, now):
    """The dead-letter door: the queue stopped retrying, so the run ends `failed` (`fail_run`)."""
    return lambda: j.recorder.abandoned(j.reader.find(job_id), now=now)


def _live_runs(j: Journey, who: Member, version_id: str) -> list:
    return [
        r for r in j.w.store.analysis_runs_for_scope(who.owner_id) if r.version_id == version_id
    ]


def _refused_or_returned(failure: BaseException | None) -> bool:
    return failure is None or isinstance(failure, WorkspaceRefused)


def _active_rows(j: Journey, version_id: str) -> list[str]:
    """Every run row under `version_id` still `active`, read raw.

    Not `analysis_runs_for_scope`: its revocation filter hides a run whose version is in the
    ledger, so a live run committed under a tombstoned version would be invisible to it.
    """
    with j.w.factory() as database:
        return list(
            database.execute(
                text(
                    "SELECT run_id FROM rca_workspace_analysis_runs "
                    "WHERE version_id = :v AND retention_state = 'active'"
                ),
                {"v": version_id},
            ).scalars()
        )


class TestTwoRunsOverOneVersion:
    """A second run over a version, and the version's deletion, overlapping on the version lock."""

    def test_a_run_started_while_its_version_is_deleted_is_refused(self) -> None:
        """The deletion holds the version lock; a run over it is started.

        The start's unlocked read sees the version live -- the tombstone has not committed -- so
        the lock in `add_analysis_run` is all that stops a live derivative of withdrawn input.
        Asserted: the start waited on the deletion's lock -- in its `FOR UPDATE`, not on a foreign
        key's `FOR KEY SHARE` -- was refused with the store's refusal, and no `active` run row
        remains under the version, read raw.
        """
        with postgres_journey() as j:
            who = member(j.w)
            _run, _job, _session = completed_run(j, who)
            (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)

            both = overlap_on_lock(
                j,
                VERSIONS,
                _delete(j, who, version.version_id),
                _start_run(j, who, version.version_id),
            )

            assert both.first.result().deleted
            refusal = both.second.failure()
            assert isinstance(refusal, WorkspaceRefused), f"the start was not refused: {refusal!r}"
            assert _active_rows(j, version.version_id) == [], (
                "a run was added live under a version whose deletion it waited on"
            )

    def test_a_deletion_arriving_while_a_run_is_added_cascades_to_it(self) -> None:
        """The start holds the version lock, inserting a second run; the deletion arrives.

        The other legitimate order: the run is added first, so the deletion must see it and end it
        with the rest. Asserted: the deletion waited on the start's lock, and the new run is
        tombstoned, not left live.
        """
        with postgres_journey() as j:
            who = member(j.w)
            _run, _job, _session = completed_run(j, who)
            (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)

            both = overlap_on_lock(
                j,
                VERSIONS,
                _start_run(j, who, version.version_id),
                _delete(j, who, version.version_id),
            )

            added = both.first.result()
            assert both.second.result().deleted
            assert _live_runs(j, who, version.version_id) == []
            assert len(tombstones_of(j, who.owner_id, RunTombstone, added.run_id)) == 1, (
                "the run added before the deletion escaped its cascade"
            )

    def test_two_runs_started_over_one_version_serialise_on_its_lock(self) -> None:
        """`#388`'s literal case: two runs started over one live version at once.

        Both are legitimate and both must land. What is asserted is that the version lock is held
        between them -- the second start waits in its `FOR UPDATE` on the first's lock -- and that
        each ends as its own live run.
        """
        with postgres_journey() as j:
            who = member(j.w)
            version, _ = sealed_version(j, who)

            both = overlap_on_lock(
                j,
                VERSIONS,
                _start_run(j, who, version.version_id),
                _start_run(j, who, version.version_id),
            )

            first, second = both.first.result(), both.second.result()
            assert first.run_id != second.run_id
            assert sorted(_active_rows(j, version.version_id)) == sorted(
                [first.run_id, second.run_id]
            )


class TestARunFailingWhileEnded:
    """`fail_run` holds only `run_for_update`: the lock the deletion cascade and a settlement
    must wait on."""

    def test_a_deletion_waits_for_a_failing_run_and_records_its_failure(self) -> None:
        """The run is failing, its lock held; the deletion's cascade reaches it.

        `live_runs_for_update` must wait and read the row the failure left, so the tombstone -- the
        only record that survives -- says the run failed at the instant it did.
        """
        with postgres_journey() as j:
            who = member(j.w)
            run, job_id, _session = started_run(j, who)

            both = overlap_on_lock(
                j, RUNS, _abandon(j, job_id, LATER), _delete(j, who, run.version_id)
            )

            both.first.result()
            assert both.second.result().deleted
            (stone,) = tombstones_of(j, who.owner_id, RunTombstone, run.run_id)
            assert stone.completed_at == LATER, (
                "the tombstone was projected from the pre-failure row"
            )

    def _failure_under_the_cascade(self, j: Journey, who: Member) -> tuple[str, Overlap]:
        """The deletion's cascade holds the run; the dead-letter door tries to fail it."""
        run, job_id, _session = started_run(j, who)
        both = overlap_on_lock(j, RUNS, _delete(j, who, run.version_id), _abandon(j, job_id, LATER))
        assert both.first.result().deleted
        both.second.failure()
        return run.run_id, both

    def test_a_run_the_cascade_holds_is_not_failed_under_it(self) -> None:
        """The failure waits on the cascade, and the ended run's record is not changed by it.

        A failure written after the tombstone would change a row the deletion record says has
        ended. The loser's own outcome is `#610`'s, below.
        """
        with postgres_journey() as j:
            who = member(j.w)
            run_id, _both = self._failure_under_the_cascade(j, who)

            (stone,) = tombstones_of(j, who.owner_id, RunTombstone, run_id)
            assert stone.completed_at is None, "the run was failed after its tombstone was written"
            assert j.w.store.get_analysis_run(run_id, who.owner_id) is None

    def test_the_failure_under_the_cascade_is_refused_not_faulted(self) -> None:
        """The loser's answer is the refusal `perform` records, not the tombstone guard's fault."""
        with postgres_journey() as j:
            who = member(j.w)
            _run_id, both = self._failure_under_the_cascade(j, who)

            failure = both.second.failure()
            if _refused_or_returned(failure):
                return
            assert isinstance(failure, ValueError) and "tombstoned" in str(failure), (
                f"not #611's failure: {failure!r}"
            )
            raise DefectStillPresent("the failure passed the liveness guard (#611)")

    def test_a_settlement_waits_for_a_failing_run_and_does_not_complete_it(self) -> None:
        """The run is failing, its lock held; a settlement of the same run arrives.

        The settlement locks the version, then waits on the run -- the lock-wait proof passes. When
        it gets the row the run has failed, and a completion written over it turns a failed run into
        a completed one: durable, because `fail_run` writes no provenance row to collide with.
        """
        with postgres_journey() as j:
            who = member(j.w)
            run, job_id, _session = started_run(j, who)
            delivered_unsettled(j, job_id)
            job = j.reader.find(job_id)

            both = overlap_on_lock(
                j, RUNS, _abandon(j, job_id, LATER), lambda: j.recorder.settled(job, now=NOW)
            )

            both.first.result()
            both.second.failure()
            ended = j.w.store.get_analysis_run(run.run_id, who.owner_id)
            assert ended is not None, "the run vanished, which is not #610"
            if (ended.state, ended.completed_at) == (RUN_FAILED, LATER):
                return
            assert ended.state == RUN_COMPLETED, f"not #610's outcome: {ended.state!r}"
            raise DefectStillPresent("a settlement completed a run that had already failed (#610)")


def _overlapping_settlements(j: Journey, who: Member) -> tuple[str, Overlap]:
    """The worker's settlement and the reconcile sweep, both reaching `record_completion` for one
    run, the sweep started while the settlement holds the version lock."""
    run, job_id, _session = started_run(j, who)
    delivered_unsettled(j, job_id)
    job = j.reader.find(job_id)
    both = overlap_on_lock(
        j,
        VERSIONS,
        lambda: j.recorder.settled(job, now=NOW),
        lambda: j.recorder.reconcile_job(job_id, now=LATER),
    )
    both.first.result()
    both.second.failure()
    return run.run_id, both


class TestOneRunTwoSettlingDoors:
    """Not `#388`'s two-runs case: one run, completed by two doors at once."""

    def test_two_settlements_of_one_run_complete_it_once(self) -> None:
        """What survives the overlap: the first settlement's completion, each surface bound once,
        one `completed` event.

        The sweep's own outcome is not read here. Today it ends in a fault that only the provenance
        row's primary key produces (`#606`, below); the durable state is what this test claims.
        """
        with postgres_journey() as j:
            who = member(j.w)
            run_id, _both = _overlapping_settlements(j, who)

            completed = j.w.store.get_analysis_run(run_id, who.owner_id)
            bindings = j.w.store.artifact_bindings_for_scope(who.owner_id)
            assert completed is not None and completed.completed_at == NOW
            assert bindings, "nothing was bound, so nothing is proven"
            assert len(bindings) == len({binding.surface for binding in bindings}), (
                "a surface was bound twice: both settlements completed the run"
            )
            assert outcomes_of(j, who.owner_id, ACTION_RUN_COMPLETED).count(OUTCOME_COMPLETED) == 1

    def test_the_losing_settlement_is_refused_not_faulted(self) -> None:
        """The loser's answer: the refusal `perform` records, or nothing -- never a database fault.

        The observed fault is checked to *be* `#606`'s before the defect is declared, so a different
        failure reads as a failure, not as the pinned defect.
        """
        with postgres_journey() as j:
            who = member(j.w)
            _run_id, both = _overlapping_settlements(j, who)

            failure = both.second.failure()
            if _refused_or_returned(failure):
                return
            assert isinstance(failure, IntegrityError), f"not #606's failure: {failure!r}"
            raise DefectStillPresent("the losing settlement passed the lock guard (#606)")
