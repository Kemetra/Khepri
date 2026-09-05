"""`W1-04b` -- the seam's own contracts, tested one collaborator at a time.

`test_w104b_pipeline_records_the_workspace.py` proves the composition end to end. These cases pin
the decisions that composition rests on and that an end-to-end pass cannot distinguish: the order
in which a settled job is recorded and completed, which job outcomes reach the workspace, and how
the run-to-job link refuses a second run for one job.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from khepri.rca.workspace.audit import (
    ACTION_VERSION_CREATED,
    ACTOR_PIPELINE,
    OUTCOME_ALREADY_RECORDED,
    OUTCOME_COMPLETED,
    AuditActor,
)
from khepri.rca.workspace.contracts import RUN_STARTED, AdmittedSource, AnalysisRun, DatasetVersion
from khepri.rca.workspace.run_reports import (
    ReportAlreadyLinked,
    RunReport,
    SqlRunReportStore,
)
from khepri.rca.workspace.scopes import SqlIsolationScopes
from khepri.rca.workspace.store import VersionAlreadyRecorded
from khepri.rra.jobs import (
    JOB_DEAD_LETTERED,
    JOB_RETRYABLE,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    FailureRequest,
    LeaseAction,
    LeaseRequest,
    ReportJob,
)
from khepri.runtime.pipeline_recording import SettlingJobStore
from khepri.runtime.workspace_recording import Attempt, Performed
from tests.w104_support import NOW, events, member, world
from tests.w105_support import admitted_version, completed_run

LATER = NOW + timedelta(minutes=1)
SOURCE = AdmittedSource(
    plaintext_digest="sha256:" + "a" * 64,
    ciphertext_digest="sha256:" + "b" * 64,
    size_bytes=2048,
    media_type="text/csv",
    manifest_digest="sha256:" + "c" * 64,
    mapping_version="rra003.mapping.v3",
    admission_outcome="admitted",
)
RETRY = timedelta(seconds=60)


def _job(state: str = JOB_RUNNING) -> ReportJob:
    return ReportJob(
        job_id="job_1",
        owner_id="own_1",
        session_id="ses_1",
        idempotency_key="k",
        state=state,
        queued_at=NOW,
        available_at=NOW,
        attempt_count=1,
        max_attempts=3,
        lease_owner="w",
        lease_expires_at=NOW + timedelta(minutes=5),
        completed_at=None,
        dead_letter_reason=None,
    )


@dataclass
class Ledger:
    """What happened, in the order it happened -- the only thing these cases assert on."""

    calls: list[str]


class FakeJobs:
    def __init__(self, ledger: Ledger, *, fail_to: str) -> None:
        self._ledger = ledger
        self._fail_to = fail_to

    def lease(self, request: LeaseRequest) -> ReportJob | None:
        self._ledger.calls.append("lease")
        return _job()

    def heartbeat(self, request: LeaseRequest) -> ReportJob:
        self._ledger.calls.append("heartbeat")
        return _job()

    def complete(self, request: LeaseAction) -> ReportJob:
        self._ledger.calls.append("complete")
        return replace(_job(JOB_SUCCEEDED), completed_at=request.now)

    def fail(self, request: FailureRequest) -> ReportJob:
        self._ledger.calls.append("fail")
        return _job(self._fail_to)

    def recover_expired(self, *, now: datetime) -> tuple[ReportJob, ...]:
        self._ledger.calls.append("recover_expired")
        return ()

    def recover_orphans(self, *, now: datetime) -> tuple[ReportJob, ...]:
        self._ledger.calls.append("recover_orphans")
        return ()


class FakeReader:
    def find(self, job_id: str) -> ReportJob | None:
        return _job() if job_id == "job_1" else None


class FakeRecorder:
    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger
        self.seen: list[tuple[str, ReportJob, datetime]] = []

    def settled(self, job: ReportJob, *, now: datetime) -> None:
        self._ledger.calls.append("settled")
        self.seen.append(("settled", job, now))

    def abandoned(self, job: ReportJob, *, now: datetime) -> None:
        self._ledger.calls.append("abandoned")
        self.seen.append(("abandoned", job, now))

    def reconcile(self, *, now: datetime) -> int:
        self._ledger.calls.append("reconcile")
        return 0


def _store(fail_to: str = JOB_RETRYABLE) -> tuple[SettlingJobStore, Ledger, FakeRecorder]:
    ledger = Ledger(calls=[])
    recorder = FakeRecorder(ledger)
    store = SettlingJobStore(
        FakeJobs(ledger, fail_to=fail_to), reader=FakeReader(), recorder=recorder
    )
    return store, ledger, recorder


# --- The settling store: order and selection ----------------------------------------------------


def test_the_run_is_recorded_before_the_job_is_completed() -> None:
    """The delivery is already durable when `complete` is called, so the workspace is written
    first: a crash between the two leaves a job another worker will re-run and find delivered,
    not a succeeded job whose run nobody will ever complete."""
    store, ledger, recorder = _store()

    store.complete(LeaseAction(job_id="job_1", worker_id="w", now=LATER))

    assert ledger.calls == ["settled", "complete"]
    assert recorder.seen == [("settled", _job(), LATER)]


def test_a_job_the_reader_cannot_find_is_completed_without_a_record() -> None:
    store, ledger, _recorder = _store()

    store.complete(LeaseAction(job_id="job_unknown", worker_id="w", now=LATER))

    assert ledger.calls == ["complete"]


def test_a_retryable_failure_reaches_the_workspace_as_nothing() -> None:
    store, ledger, _recorder = _store(fail_to=JOB_RETRYABLE)

    store.fail(FailureRequest(lease=LeaseAction("job_1", "w", LATER), retry_at=LATER + RETRY))

    assert ledger.calls == ["fail"]


def test_a_dead_lettered_failure_fails_the_run_after_the_repository_decided() -> None:
    """Which failure is the last is the repository's rule (`ClaimingReportQueue.retry`); the
    workspace is told only once the returned job says the queue stopped."""
    store, ledger, recorder = _store(fail_to=JOB_DEAD_LETTERED)

    returned = store.fail(
        FailureRequest(lease=LeaseAction("job_1", "w", LATER), retry_at=LATER + RETRY)
    )

    assert ledger.calls == ["fail", "abandoned"]
    assert returned.state == JOB_DEAD_LETTERED
    assert recorder.seen == [("abandoned", _job(JOB_DEAD_LETTERED), LATER)]


def test_lease_and_heartbeat_pass_straight_through() -> None:
    store, ledger, _recorder = _store()
    request = LeaseRequest(job_id="job_1", worker_id="w", now=NOW, lease_for=timedelta(minutes=5))

    assert store.lease(request) == _job()
    assert store.heartbeat(request) == _job()
    assert ledger.calls == ["lease", "heartbeat"]


# --- The run-to-job link ------------------------------------------------------------------------


def _run_in(w, who) -> AnalysisRun:
    _session_id, version_id = admitted_version(w, who)
    run = w.services.start_analysis_run(who.caller, version_id=version_id, now=NOW)
    assert run.state == RUN_STARTED
    return run


def test_a_linked_job_finds_its_run_and_only_within_its_scope() -> None:
    w = world()
    who = member(w)
    other = member(w, email="other@example.test", name="Other")
    run = _run_in(w, who)
    store = SqlRunReportStore(w.factory)

    store.link(RunReport(run_id=run.run_id, owner_id=who.owner_id, job_id="job_a"), now=NOW)

    assert store.run_id_for_job(who.owner_id, "job_a") == run.run_id
    assert store.run_id_for_job(other.owner_id, "job_a") is None
    assert store.run_id_for_job(who.owner_id, "job_b") is None
    assert store.job_id_for_run(run.run_id, who.owner_id) == "job_a"
    assert store.job_id_for_run(run.run_id, other.owner_id) is None


def test_one_job_settles_one_run() -> None:
    """The unique constraint on `job_id` is the arbiter between two requests that both found no
    link; the loser learns it as `ReportAlreadyLinked` inside its own transaction, so the caller
    can roll back the run it started and read the winner's instead."""
    w = world()
    who = member(w)
    first = _run_in(w, who)
    second = _run_in(w, who)
    store = SqlRunReportStore(w.factory)
    store.link(RunReport(run_id=first.run_id, owner_id=who.owner_id, job_id="job_a"), now=NOW)

    with pytest.raises(ReportAlreadyLinked):
        store.link(
            RunReport(run_id=second.run_id, owner_id=who.owner_id, job_id="job_a"), now=NOW
        )

    assert store.run_id_for_job(who.owner_id, "job_a") == first.run_id
    assert store.job_id_for_run(second.run_id, who.owner_id) is None


def test_a_run_answers_to_one_job() -> None:
    w = world()
    who = member(w)
    run = _run_in(w, who)
    store = SqlRunReportStore(w.factory)
    store.link(RunReport(run_id=run.run_id, owner_id=who.owner_id, job_id="job_a"), now=NOW)

    with pytest.raises(ReportAlreadyLinked):
        store.link(RunReport(run_id=run.run_id, owner_id=who.owner_id, job_id="job_b"), now=NOW)

    assert store.job_id_for_run(run.run_id, who.owner_id) == "job_a"


def test_a_link_cannot_name_a_run_outside_its_scope() -> None:
    """The composite foreign key holds `(owner_id, run_id)` together: a link under one scope to a
    run in another is unrepresentable, as it is for a binding."""
    w = world()
    who = member(w)
    other = member(w, email="other@example.test", name="Other")
    run = _run_in(w, who)
    store = SqlRunReportStore(w.factory)

    with pytest.raises(IntegrityError):
        store.link(RunReport(run_id=run.run_id, owner_id=other.owner_id, job_id="job_a"), now=NOW)

    assert store.run_id_for_job(other.owner_id, "job_a") is None


# --- Arbitration: the loser of a race reads the winner -------------------------------------------


def test_two_versions_of_one_upload_in_one_scope_are_refused_by_the_database() -> None:
    """Two overlapping profile requests both pass the read-then-insert; only a constraint can
    refuse the second (review on `#375`). Surfaced as the arbitration, in the caller's unit."""
    w = world()
    who = member(w)
    other = member(w, email="other@example.test", name="Other")
    first = DatasetVersion.create(owner_id=who.owner_id, source=SOURCE, now=NOW)
    w.store.add_dataset_version(first)

    with pytest.raises(VersionAlreadyRecorded):
        w.store.add_dataset_version(
            DatasetVersion.create(owner_id=who.owner_id, source=SOURCE, now=LATER)
        )

    # Another scope's version of the same bytes is a different version (`FR-109`).
    w.store.add_dataset_version(
        DatasetVersion.create(owner_id=other.owner_id, source=SOURCE, now=NOW)
    )
    assert [v.version_id for v in w.store.dataset_versions_for_scope(who.owner_id)] == [
        first.version_id
    ]


def test_a_lost_arbitration_is_recorded_as_already_recorded_from_the_winners_row() -> None:
    """`perform`: `act` loses a constraint race, the unit rolls back, and `already` is performed in
    a fresh unit -- one `already_recorded` event, no `completed`, no fault."""
    w = world()
    who = member(w)
    session_id, version_id = admitted_version(w, who)
    version = w.store.get_dataset_version(version_id, who.owner_id)
    recording = w.services._recording
    actor = AuditActor(owner_id=who.owner_id, actor_account_id=who.account_id)

    def loses() -> Performed[DatasetVersion]:
        raise VersionAlreadyRecorded("lost")

    result = recording.perform(
        actor,
        Attempt(
            ACTION_VERSION_CREATED,
            loses,
            already=lambda: recording.existing_version(who.owner_id, session_id, LATER),
        ),
        now=LATER,
    )

    assert result == version
    outcomes = [e.outcome for e in events(w, who) if e.action == ACTION_VERSION_CREATED]
    assert outcomes == [OUTCOME_COMPLETED, OUTCOME_ALREADY_RECORDED]


def test_a_lost_arbitration_with_no_reading_is_the_fault_it_is() -> None:
    w = world()
    who = member(w)
    recording = w.services._recording
    actor = AuditActor(owner_id=who.owner_id, actor_account_id=who.account_id)

    def loses() -> Performed[DatasetVersion]:
        raise VersionAlreadyRecorded("lost")

    with pytest.raises(VersionAlreadyRecorded):
        recording.perform(actor, Attempt(ACTION_VERSION_CREATED, loses), now=NOW)
    assert events(w, who) == ()


def test_recovery_runs_the_reconciliation_sweep_after_the_repository() -> None:
    """A lease reclaimed into the dead letter never passes `fail`; the sweep is what reaches it,
    and it runs after the repository's recovery so it sees the transition it made."""
    store, ledger, _recorder = _store()

    assert store.recover_expired(now=LATER) == ()
    assert store.recover_orphans(now=LATER) == ()

    assert ledger.calls == ["recover_expired", "reconcile", "recover_orphans", "reconcile"]


def test_the_sweep_reads_only_the_links_of_runs_still_started() -> None:
    """`reconcile` must not revisit a settled run: a completed run's link is not returned, so no
    `already_recorded` event is written for it on every claim."""
    w = world()
    who = member(w)
    store = SqlRunReportStore(w.factory)
    _session, _version, completed = completed_run(w, who)
    store.link(RunReport(run_id=completed, owner_id=who.owner_id, job_id="job_done"), now=NOW)
    started = _run_in(w, who)
    store.link(RunReport(run_id=started.run_id, owner_id=who.owner_id, job_id="job_open"), now=NOW)

    assert [link.job_id for link in store.links_of_started_runs()] == ["job_open"]


# --- Which scopes are workspaces -----------------------------------------------------------------


def test_an_organizations_scope_is_a_workspace_and_an_invitations_is_not() -> None:
    w = world()
    who = member(w)
    scopes = SqlIsolationScopes(w.factory)

    assert scopes.exists(who.owner_id) is True
    assert scopes.exists("design-partner-7") is False


def test_the_pipeline_actor_is_not_shaped_like_an_account() -> None:
    """`FR-125` puts an opaque actor on every event. The pipeline's is a fixed system name that
    no account identifier can collide with, so a reader never mistakes it for a member."""
    assert ACTOR_PIPELINE.startswith("system:")
    assert AuditActor(owner_id="own_1", actor_account_id=ACTOR_PIPELINE).actor_account_id == (
        ACTOR_PIPELINE
    )


