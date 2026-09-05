"""The pipeline door: the deployed analysis flow records the workspace (`W1-04b`; `RCA-005`
`FR-110`, `FR-111`, `FR-125`; `RCA-002` `FR-049`).

Review on `#373` found that nothing in `src/khepri` called the workspace actions. The shell's entry
route (`R8-06`) opens a journey session and the journey's own routes admit, derive and report; the
workspace learned of none of it, so Overview would have told a customer with three finished analyses
that nothing had been submitted. This module is the composition that closes that: three decorators,
placed at the composition root around the objects `build_web_app` and `build_worker_loop` already
construct, each recording what its stage produced and nothing more.

```
POST /api/v1/beta/profile   RecordingProfilingService   -> the version (FR-110)
POST /api/v1/beta/reports   RecordingReportRequests     -> the run, started and bound to its job
worker settles the job      SettlingJobStore            -> the run completed (FR-111) or failed
```

## Where the run's identity comes from

A run is started in the web process and settled in the worker, which holds only a job. `FR-111`
makes the run a product of the pipeline, so the run is created when the pipeline's unit of work --
the report job -- is queued, and linked to that job in `rca_workspace_run_reports`. The worker asks
the link which run its job settles. A run therefore exists exactly when a job does, is `started`
while the job is queued, running or retryable (Overview: processing), `completed` when it succeeds,
and `failed` when the queue dead-letters it. A retryable failure is not yet an outcome and records
nothing.

## Who the actor is

The beta cookie names a session, not an account: the member who opened it is not recoverable at the
admission or report route without persisting an account identifier beside a bearer-adjacent session
identifier, which `KHEPRI-DEC-015` §7 rules out. The events therefore name the pipeline as their
actor (`ACTOR_PIPELINE`), in the scope the session carries. That scope was minted by
`resolve_scope` when `CommercialBridge.open` opened the session, so authorization happened once, at
the door the customer came through; the pipeline re-verifies only that the scope is a workspace.

## What is not recorded, deliberately

- **A session no organization owns.** An invitation-redeemed session carries a design-partner scope
  with no row in `rca_isolation_scopes`; there is no workspace to record into, and every workspace
  row's foreign key would refuse it. The pipeline serves it as before and records nothing.
- **A source without a coverage attestation.** `W1-01` made the manifest part of a version and
  `KHEPRI-DEC-033` §3 keeps its digest, while the journey's attestation is optional (`upload.js`).
  An unattested profile is not a dataset version, so neither it nor its run is recorded, and no
  event is written because no action was attempted. Recording it would need an `RCA-005` reading.

## Failure is closed

A recording fault propagates. At admission the route returns an error and the client's retry finds
the profile idempotent and the recording idempotent by digest; at the report request the job is
durable and published before the workspace is written, so a retry converges on `already_recorded`
and no queued job is hidden from the worker. In the worker the completion is recorded *before* the
job is marked succeeded, because the delivery is already durable: a crash between the two leaves a
job another worker re-runs, finds delivered, and settles, rather than a succeeded job whose run
nobody will ever complete. Two concurrent report requests that both find no link are arbitrated by
the unique constraint on `job_id`: the loser's unit of work rolls back the run it started and it
reads the winner's -- SQLite serializes writes, so no test here can show the race; the store test
shows the constraint.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from khepri.rca.workspace.audit import (
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    ACTION_RUN_STARTED,
    ACTION_VERSION_CREATED,
    ACTOR_PIPELINE,
    OUTCOME_ALREADY_RECORDED,
    AuditActor,
)
from khepri.rca.workspace.contracts import RUN_STARTED, AnalysisRun, DatasetVersion
from khepri.rca.workspace.run_reports import RunReport, SqlRunReportStore
from khepri.rca.workspace.scopes import SqlIsolationScopes
from khepri.rra.datasets import (
    DatasetProfileRecord,
    ProfileObjectReader,
    ProfileRepository,
    ProfilingService,
)
from khepri.rra.datasets import (
    SessionReader as ProfilingSessionReader,
)
from khepri.rra.intake import UploadRepository
from khepri.rra.jobs import (
    JOB_DEAD_LETTERED,
    JOB_SUCCEEDED,
    FailureRequest,
    LeaseAction,
    LeaseRequest,
    ReportJob,
)
from khepri.rra.reports import ReportJobView, ReportRequestService
from khepri.rra.sessions import BetaSession
from khepri.runtime.workspace_recording import (
    Attempt,
    Performed,
    ReportLocator,
    WorkspaceRecording,
    subject_of_run,
)


class SessionReader(Protocol):
    def get_session(self, session_id: str) -> BetaSession | None: ...


class JobReaderPort(Protocol):
    def find(self, job_id: str) -> ReportJob | None: ...


class ReportJobStore(Protocol):
    """What the worker and the claim queue ask of the job store, together."""

    def lease(self, request: LeaseRequest) -> ReportJob | None: ...

    def heartbeat(self, request: LeaseRequest) -> ReportJob: ...

    def complete(self, request: LeaseAction) -> ReportJob: ...

    def fail(self, request: FailureRequest) -> ReportJob: ...

    def recover_expired(self, *, now: datetime) -> tuple[ReportJob, ...]: ...

    def recover_orphans(self, *, now: datetime) -> tuple[ReportJob, ...]: ...


class RunRecorder(Protocol):
    """What a settled job tells the workspace, and the sweep that catches what a crash missed."""

    def settled(self, job: ReportJob, *, now: datetime) -> AnalysisRun | None: ...

    def abandoned(self, job: ReportJob, *, now: datetime) -> AnalysisRun | None: ...

    def reconcile(self, *, now: datetime) -> int: ...


@dataclass(frozen=True, slots=True)
class RecorderReads:
    """What the recorder reads to place a stage's product: the session's scope, whether that
    scope is a workspace, the run-to-report link, and the job's current state."""

    sessions: SessionReader
    scopes: SqlIsolationScopes
    reports: SqlRunReportStore
    jobs: JobReaderPort


class PipelineRecorder:
    """Records, in a scope the session already carries, what each pipeline stage produced."""

    def __init__(self, *, recording: WorkspaceRecording, reads: RecorderReads) -> None:
        self._recording = recording
        self._sessions = reads.sessions
        self._scopes = reads.scopes
        self._reports = reads.reports
        self._jobs = reads.jobs

    @property
    def recording(self) -> WorkspaceRecording:
        return self._recording

    # --- FR-110: admission -> version -------------------------------------------------------------

    def admitted(self, session_id: str, *, now: datetime) -> DatasetVersion | None:
        """The session's admission, recorded as a version if it is one: admitted, attested, and in
        a scope that is a workspace. Otherwise nothing, and no event -- see the module docstring."""
        owner_id = self._workspace_of(session_id)
        if owner_id is None or not self._recording.records_a_version(owner_id, session_id, now):
            return None
        return self._recording.perform(
            self._actor(owner_id),
            Attempt(
                ACTION_VERSION_CREATED,
                lambda: self._recording.create_version(owner_id, session_id, now),
                already=lambda: self._recording.existing_version(owner_id, session_id, now),
            ),
            now=now,
        )

    # --- FR-111: the job -> the run, started; the delivery -> the run, completed ----------------

    def requested(self, job: ReportJob, *, now: datetime) -> AnalysisRun | None:
        """Start the run this job is the pipeline's execution of, once, and bind the two.

        The scope is checked where the version is made (`admitted`): a version exists only in a
        workspace scope, so finding one is the check, and a session whose admission recorded none
        is given the chance here -- the safety net for an admission recorded out of order.
        """
        version = self._recording.version_for_session(job.owner_id, job.session_id, now)
        if version is None:
            version = self.admitted(job.session_id, now=now)
        if version is None:
            return None
        actor = self._actor(job.owner_id)
        run = self._recording.perform(
            actor,
            Attempt(
                ACTION_RUN_STARTED,
                lambda: self._start_linked(job, version.version_id, now),
                # A request that finds the job already linked -- an idempotent repeat, or the
                # loser of two concurrent requests -- reads the linked run. The unique constraint
                # on the link is the arbiter; there is no read-then-decide here for it to race.
                already=lambda: self._linked_run_already(job),
            ),
            now=now,
        )
        # The job was durable and claimable before this run existed, so a worker may already
        # have settled it and found no run to record against (review on `#375`). Re-read the
        # job now that the link is committed: whichever side wrote second sees the other.
        return self.reconcile_job(job.job_id, now=now) or run

    def _start_linked(
        self, job: ReportJob, version_id: str, now: datetime
    ) -> Performed[AnalysisRun]:
        performed = self._recording.start_run(job.owner_id, version_id, now)
        self._reports.link(
            RunReport(run_id=performed.result.run_id, owner_id=job.owner_id, job_id=job.job_id),
            now=now,
        )
        return performed

    def _linked_run_already(self, job: ReportJob) -> Performed[AnalysisRun]:
        run_id = self._reports.run_id_for_job(job.owner_id, job.job_id)
        run = None if run_id is None else self._recording.run(job.owner_id, run_id)
        if run is None:  # pragma: no cover -- the constraint that raised names a row
            raise LookupError(job.job_id)
        return Performed(run, OUTCOME_ALREADY_RECORDED, subject_of_run(run))

    # --- reconciliation: a run's state follows its job's, whichever side wrote second -------

    def reconcile_job(self, job_id: str, *, now: datetime) -> AnalysisRun | None:
        """Settle or fail the run of one job from the job's *current* state, if terminal."""
        job = self._jobs.find(job_id)
        if job is None:
            return None
        if job.state == JOB_SUCCEEDED:
            return self.settled(job, now=now)
        if job.state == JOB_DEAD_LETTERED:
            return self.abandoned(job, now=now)
        return None

    def reconcile(self, *, now: datetime) -> int:
        """Every run still `started`, brought level with its job. The worker calls this before
        each claim (`SettlingJobStore.recover_expired`), so a run left behind by a crash between
        a job's terminal transition and its recording -- or by a lease reclaimed into the dead
        letter -- is settled within one loop iteration. Returns how many runs moved."""
        moved = 0
        for link in self._reports.links_of_started_runs():
            if self.reconcile_job(link.job_id, now=now) is not None:
                moved += 1
        return moved

    def settled(self, job: ReportJob, *, now: datetime) -> AnalysisRun | None:
        """The job delivered: complete its run from the delivery, binding every artifact."""
        actor, run = self._linked_run(job)
        if run is None:
            return None
        if run.state != RUN_STARTED:
            return self._already(actor, ACTION_RUN_COMPLETED, run.run_id, now)
        report = ReportLocator(session_id=job.session_id, job_id=job.job_id)
        return self._recording.perform(
            actor,
            Attempt(
                ACTION_RUN_COMPLETED,
                lambda: self._recording.complete_run(job.owner_id, run.run_id, report, now),
            ),
            now=now,
        )

    def abandoned(self, job: ReportJob, *, now: datetime) -> AnalysisRun | None:
        """The queue stopped retrying the job: its run ends as `failed`."""
        actor, run = self._linked_run(job)
        if run is None:
            return None
        if run.state != RUN_STARTED:
            return self._already(actor, ACTION_RUN_FAILED, run.run_id, now)
        return self._recording.perform(
            actor,
            Attempt(
                ACTION_RUN_FAILED,
                lambda: self._recording.fail_run(job.owner_id, run.run_id, now),
            ),
            now=now,
        )

    # --- helpers --------------------------------------------------------------------------------

    def _workspace_of(self, session_id: str) -> str | None:
        """The session's scope, when that scope is a workspace; else `None`."""
        session = self._sessions.get_session(session_id)
        if session is None or not self._scopes.exists(session.owner_id):
            return None
        return session.owner_id

    def _linked_run(self, job: ReportJob) -> tuple[AuditActor, AnalysisRun | None]:
        """The run this job settles, or `None` for a job no run was started for -- a session no
        organization owns, an unattested source, or a job queued before this seam existed."""
        actor = self._actor(job.owner_id)
        run_id = self._reports.run_id_for_job(job.owner_id, job.job_id)
        if run_id is None:
            return actor, None
        return actor, self._recording.run(job.owner_id, run_id)

    def _already(self, actor: AuditActor, action: str, run_id: str, now: datetime) -> AnalysisRun:
        """A repeat of an action the pipeline already recorded: one `already_recorded` event."""
        run = self._recording.run(actor.owner_id, run_id)
        if run is None:  # pragma: no cover -- the link's foreign key names a live run
            raise LookupError(run_id)
        return self._recording.perform(
            actor,
            Attempt(action, lambda: Performed(run, OUTCOME_ALREADY_RECORDED, subject_of_run(run))),
            now=now,
        )

    @staticmethod
    def _actor(owner_id: str) -> AuditActor:
        return AuditActor(owner_id=owner_id, actor_account_id=ACTOR_PIPELINE)


@dataclass(frozen=True, slots=True)
class AdmissionPorts:
    """What a `ProfilingService` is built over -- the four repositories, named once."""

    sessions: ProfilingSessionReader
    uploads: UploadRepository
    objects: ProfileObjectReader
    profiles: ProfileRepository


class RecordingProfilingService(ProfilingService):
    """`ProfilingService`, recording each admission it performs.

    A subclass rather than a wrapper because `create_app` and `WorkspacePorts` type the service
    concretely, and because the read side (`get_session_profile`) must stay the same object the
    admission wrote through. Only the admitting method is extended; the recording runs after the
    service has decided, on every call including an idempotent repeat, so a client retry after a
    recording fault records what the first call could not.
    """

    def __init__(self, ports: AdmissionPorts, *, recorder: PipelineRecorder) -> None:
        super().__init__(
            sessions=ports.sessions,
            uploads=ports.uploads,
            objects=ports.objects,
            profiles=ports.profiles,
        )
        self._recorder = recorder

    @property
    def recorder(self) -> PipelineRecorder:
        return self._recorder

    def profile_session_upload(self, **request: Any) -> tuple[DatasetProfileRecord, bool]:
        """The parent's signature, forwarded whole -- `session_id`, `contract`, `now`, and the
        optional `request` and `attestation` -- so this override adds one effect and does not
        restate five parameters the parent owns. The recording runs after the service decided."""
        record, created = super().profile_session_upload(**request)
        self._recorder.admitted(request["session_id"], now=request["now"])
        return record, created


class RecordingReportRequests:
    """`ReportRequestService`, starting the run for each job it queues.

    Wraps the queued service, not the adapter beneath it, so the job is durable *and published*
    before the workspace is written: a recording fault fails the request, and the retry finds the
    same job and records `already_recorded`. Nothing the worker needs waits on the workspace.
    """

    def __init__(self, requests: ReportRequestService, *, recorder: PipelineRecorder) -> None:
        self._requests = requests
        self._recorder = recorder

    @property
    def requests(self) -> ReportRequestService:
        return self._requests

    @property
    def recorder(self) -> PipelineRecorder:
        return self._recorder

    def request_session_report(
        self, *, session_id: str, now: datetime
    ) -> tuple[ReportJobView, bool]:
        view, created = self._requests.request_session_report(session_id=session_id, now=now)
        self._recorder.requested(view.job, now=now)
        return view, created

    def get_session_job(
        self, *, session_id: str, job_id: str, now: datetime
    ) -> ReportJobView | None:
        return self._requests.get_session_job(session_id=session_id, job_id=job_id, now=now)


class SettlingJobStore:
    """The worker's job store, telling the workspace how each job ended.

    `complete` records first and completes second -- the module docstring says why the order is
    load-bearing. `fail` completes first and records second, because whether a failure is the
    last one is the repository's decision (`attempt_count` against `max_attempts`), read from the
    job it returns; a retryable failure reaches the workspace as nothing. The crash window that
    order leaves -- a dead-lettered job whose run stayed `started` -- is closed by `reconcile`,
    which `recover_expired` runs before every claim; the same sweep catches a lease the queue
    reclaimed straight into the dead letter, which never passes `fail` at all. Handed to the
    worker *and* to the claim queue, so both settle through it.
    """

    def __init__(
        self, jobs: ReportJobStore, *, reader: JobReaderPort, recorder: RunRecorder
    ) -> None:
        self._jobs = jobs
        self._reader = reader
        self._recorder = recorder

    @property
    def jobs(self) -> ReportJobStore:
        return self._jobs

    @property
    def recorder(self) -> RunRecorder:
        return self._recorder

    def lease(self, request: LeaseRequest) -> ReportJob | None:
        return self._jobs.lease(request)

    def heartbeat(self, request: LeaseRequest) -> ReportJob:
        return self._jobs.heartbeat(request)

    def complete(self, request: LeaseAction) -> ReportJob:
        job = self._reader.find(request.job_id)
        if job is not None:
            self._recorder.settled(job, now=request.now)
        return self._jobs.complete(request)

    def fail(self, request: FailureRequest) -> ReportJob:
        job = self._jobs.fail(request)
        if job.state == JOB_DEAD_LETTERED:
            self._recorder.abandoned(job, now=request.lease.now)
        return job

    def recover_expired(self, *, now: datetime) -> tuple[ReportJob, ...]:
        """The claim loop's sweep, then the workspace's: a lease reclaimed into the dead letter
        never passes `fail`, and a crash between any terminal transition and its recording
        leaves a run `started` -- both are caught here, before every claim."""
        recovered = self._jobs.recover_expired(now=now)
        self._recorder.reconcile(now=now)
        return recovered

    def recover_orphans(self, *, now: datetime) -> tuple[ReportJob, ...]:
        orphaned = self._jobs.recover_orphans(now=now)
        self._recorder.reconcile(now=now)
        return orphaned


__all__ = [
    "AdmissionPorts",
    "JobReaderPort",
    "PipelineRecorder",
    "RecorderReads",
    "RecordingProfilingService",
    "RecordingReportRequests",
    "ReportJobStore",
    "RunRecorder",
    "SessionReader",
    "SettlingJobStore",
]
