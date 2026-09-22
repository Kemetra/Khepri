"""One faulting item must not stop the work around it (`#523`: audit A-07 and A-16).

**The worker (A-07).** `ClaimWorkerLoop.run_once` runs the recovery sweep before every claim, and
through `SettlingJobStore.recover_expired` that sweep is `PipelineRecorder.reconcile`, a loop over
every run still `started`. A deterministic fault on one link used to escape the loop, so every
iteration -- and every restart -- died before `receive`: RRA-007's restart recovery became a crash
loop that claimed nothing. The recording is faked at the `complete_run` seam, the call that records
a run's completion, so the real `reconcile`, `settled` and settling store run.

**The retention sweep (A-16).** `RetentionPasses.run` ran its passes in one expression, and
`RetentionSweeper._expire_sessions` caught only `DeletionRetryRequired`. One session whose deletion
raised anything else aborted every later pass, including `KHEPRI-DEC-015` §2b's account purge and
the invitation `target_identity` purge -- on every run, because the faulting session stays due.
`KHEPRI-DEC-033` §5 asks for a sweep that honours each horizon; a sweep one row can switch off does
not. The fault is still reported: the sweep's report names the faulted passes and `main` exits
non-zero, so a scheduler alerts.

**What a fault log may say.** `KHEPRI-DEC-015` §7 forbids logging a session identifier and RRA-007
forbids logging customer content. An exception's message is not trusted to honour either (a driver
error echoes its bound parameters), so the logs carry the pass or opaque job id and the exception's
type only. The cases below assert that too.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pytest

from khepri.rca.workspace.contracts import RUN_STARTED
from khepri.rca.workspace.run_reports import RunReport
from khepri.rra.jobs import JOB_SUCCEEDED, ReportJob
from khepri.runtime import retention_sweep
from khepri.runtime.pipeline_recording import (
    PipelineRecorder,
    RecorderReads,
    SettlingJobStore,
)
from khepri.runtime.retention_sweep import RetentionCounts, RetentionPasses, RetentionSweeper
from tests.test_runtime_worker import NOW, QueueStub, ReaderStub, WorkerStub, job

# --- A-07: the worker keeps claiming past a link that faults --------------------------------------

SECRET_DETAIL = "detail-that-must-not-be-logged"


class FaultyRecording:
    """Records completions, except for one run whose completion raises."""

    def __init__(self, *, faulty_run: str, fault: BaseException) -> None:
        self._faulty_run = faulty_run
        self._fault = fault
        self.completed: list[str] = []

    def run(self, owner_id: str, run_id: str) -> SimpleNamespace:
        return SimpleNamespace(run_id=run_id, owner_id=owner_id, state=RUN_STARTED)

    def complete_run(
        self, owner_id: str, run_id: str, report: object, now: datetime
    ) -> SimpleNamespace:
        if run_id == self._faulty_run:
            raise self._fault
        self.completed.append(run_id)
        return SimpleNamespace(result=self.run(owner_id, run_id))

    def perform(self, actor: object, attempt: object, *, now: datetime) -> object:
        return attempt.act().result  # type: ignore[attr-defined]


LINKS = (
    RunReport(run_id="run_bad", owner_id="own_alpha", job_id="job_bad"),
    RunReport(run_id="run_good", owner_id="own_alpha", job_id="job_good"),
)


class Links:
    def links_of_started_runs(self) -> tuple[RunReport, ...]:
        return LINKS

    def run_id_for_job(self, owner_id: str, job_id: str) -> str | None:
        return next((link.run_id for link in LINKS if link.job_id == job_id), None)


class SucceededJobs:
    """Every linked job has succeeded, so reconciliation must complete each run."""

    def find(self, job_id: str) -> ReportJob:
        return replace(job(JOB_SUCCEEDED), job_id=job_id)


class RepositoryStub:
    def recover_expired(self, *, now: datetime) -> tuple[ReportJob, ...]:
        return ()


class RecoveringQueue(QueueStub):
    """The claim queue's recovery, delegated to the real settling store and recorder."""

    def __init__(self, store: SettlingJobStore) -> None:
        super().__init__()
        self._store = store

    def recover(self, *, now: datetime) -> tuple[ReportJob, ...]:
        self.recoveries += 1
        return self._store.recover_expired(now=now)


def _worker_loop(
    fault: BaseException,
) -> tuple[object, RecoveringQueue, WorkerStub, FaultyRecording]:
    from khepri.runtime.worker import ClaimWorkerLoop

    recording = FaultyRecording(faulty_run="run_bad", fault=fault)
    recorder = PipelineRecorder(
        recording=recording,  # type: ignore[arg-type]
        reads=RecorderReads(
            sessions=None,  # type: ignore[arg-type]
            scopes=None,  # type: ignore[arg-type]
            reports=Links(),  # type: ignore[arg-type]
            jobs=SucceededJobs(),
        ),
    )
    store = SettlingJobStore(
        RepositoryStub(),  # type: ignore[arg-type]
        reader=SucceededJobs(),
        recorder=recorder,
    )
    queue = RecoveringQueue(store)
    worker = WorkerStub(job(JOB_SUCCEEDED))
    loop = ClaimWorkerLoop(queue=queue, worker=worker, jobs=ReaderStub(), clock=lambda: NOW)
    return loop, queue, worker, recording


def test_a_faulting_link_does_not_stop_the_worker_claiming(
    caplog: pytest.LogCaptureFixture,
) -> None:
    loop, queue, worker, recording = _worker_loop(RuntimeError(SECRET_DETAIL))

    with caplog.at_level(logging.WARNING):
        claimed = loop.run_once()  # type: ignore[attr-defined]

    assert claimed is True, "the claim ran after the sweep"
    assert queue.receives == 1
    assert [message.job_id for message in worker.messages] == ["job_alpha"]
    assert recording.completed == ["run_good"], "the link after the fault was still reconciled"
    logged = caplog.text
    assert "job_bad" in logged and "RuntimeError" in logged, "the fault is reported, not swallowed"
    assert SECRET_DETAIL not in logged, "an exception message is not trusted to be content-free"
    assert "ses_alpha" not in logged, "no session identifier reaches a log (KHEPRI-DEC-015 §7)"


def test_an_interrupt_during_reconciliation_still_stops_the_worker() -> None:
    loop, queue, _worker, _recording = _worker_loop(KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        loop.run_once()  # type: ignore[attr-defined]

    assert queue.receives == 0


# --- A-16: every retention pass runs past one that faults -----------------------------------------


class FakeJobs:
    def __init__(self, *, fault: BaseException | None = None) -> None:
        self._fault = fault

    def recover_expired(self, *, now: datetime) -> tuple[object, ...]:
        if self._fault is not None:
            raise self._fault
        return ()

    def recover_orphans(self, *, now: datetime) -> tuple[object, ...]:
        return ()


class FakeDeletion:
    def __init__(self, *, faulty: str | None = None) -> None:
        self._faulty = faulty
        self.deleted: list[str] = []

    def delete_session_content(self, *, session_id: str, reason: str, now: datetime) -> None:
        if session_id == self._faulty:
            raise ValueError(SECRET_DETAIL)
        self.deleted.append(session_id)


class CountingPass:
    def __init__(self, report: object, *, fault: BaseException | None = None) -> None:
        self._report = report
        self._fault = fault
        self.calls = 0

    def sweep(self, *, now: datetime) -> object:
        self.calls += 1
        if self._fault is not None:
            raise self._fault
        return self._report


class StubSweeper(RetentionSweeper):
    """Overrides only the database read, so the pass logic is the real one."""

    def __init__(
        self, *, jobs: object, deletion: object, expired: list[str], retention: RetentionPasses
    ) -> None:
        self._jobs = jobs  # type: ignore[assignment]
        self._deletion = deletion  # type: ignore[assignment]
        self._expired = expired
        self._retention = retention

    def _expired_session_ids(self, *, now: datetime) -> list[str]:
        return self._expired


def _passes(*, accounts_fault: BaseException | None = None) -> tuple[RetentionPasses, dict]:
    counting = {
        "accounts": CountingPass(SimpleNamespace(purged_accounts=2), fault=accounts_fault),
        "events": CountingPass(SimpleNamespace(purged_events=3)),
        "invitations": CountingPass(SimpleNamespace(purged_invitations=4)),
        "raw_uploads": CountingPass(SimpleNamespace(purged_uploads=5)),
    }
    return RetentionPasses(**counting), counting  # type: ignore[arg-type]


def test_a_faulting_session_does_not_stop_later_sessions_or_passes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    passes, counting = _passes()
    deletion = FakeDeletion(faulty="ses_bad")
    sweeper = StubSweeper(
        jobs=FakeJobs(), deletion=deletion, expired=["ses_bad", "ses_good"], retention=passes
    )

    with caplog.at_level(logging.WARNING):
        report = sweeper.sweep(now=NOW)

    assert deletion.deleted == ["ses_good"], "the session after the fault was still deleted"
    assert report.expired_sessions == 1
    assert report.deletions_faulted == 1
    assert [one.calls for one in counting.values()] == [1, 1, 1, 1], "every later pass ran"
    assert (report.purged_accounts, report.purged_invitations) == (2, 4)
    assert report.faulted_passes == ("expired_sessions",), "the run reports the fault"
    logged = caplog.text
    assert "expired_sessions" in logged and "ValueError" in logged
    assert "ses_bad" not in logged, "no session identifier reaches a log (KHEPRI-DEC-015 §7)"
    assert SECRET_DETAIL not in logged


def test_a_faulting_pass_does_not_stop_the_passes_after_it() -> None:
    passes, counting = _passes(accounts_fault=RuntimeError(SECRET_DETAIL))

    counts = passes.run(now=NOW)

    assert [one.calls for one in counting.values()] == [1, 1, 1, 1]
    assert (counts.accounts, counts.events, counts.invitations, counts.raw_uploads) == (0, 3, 4, 5)
    assert counts.faulted_passes == ("accounts",)


def test_every_retention_pass_runs_and_reports_into_its_own_count() -> None:
    """The isolation loop reads a table; a missing or swapped row must not pass silently.

    `recovery_events` and `workspace_audit` both report `purged_events`, so distinct counts are
    what would expose two swapped rows, and the field-set comparison is what would expose a pass
    added to `RetentionPasses` without a row -- which the loop would skip with no fault recorded.
    """
    table = retention_sweep._RETENTION_PASSES
    assert [row[0] for row in table] == list(RetentionPasses.__dataclass_fields__)
    assert {row[1] for row in table} == set(RetentionCounts.__dataclass_fields__) - {
        "faulted_passes"
    }
    reports = {
        "accounts": SimpleNamespace(purged_accounts=1),
        "events": SimpleNamespace(purged_events=2),
        "sessions": SimpleNamespace(purged_sessions=3),
        "invitations": SimpleNamespace(purged_invitations=4),
        "recovery_events": SimpleNamespace(purged_events=5),
        "workspace_audit": SimpleNamespace(purged_events=6),
        "evidence": SimpleNamespace(purged_evidence=7),
        "raw_uploads": SimpleNamespace(purged_uploads=8),
    }
    counting = {name: CountingPass(report) for name, report in reports.items()}

    counts = RetentionPasses(**counting).run(now=NOW)  # type: ignore[arg-type]

    assert [one.calls for one in counting.values()] == [1] * 8
    assert counts == RetentionCounts(
        accounts=1,
        events=2,
        sessions=3,
        invitations=4,
        recovery_events=5,
        workspace_audit_events=6,
        evidence=7,
        raw_uploads=8,
    )


def test_a_clean_run_reports_no_fault() -> None:
    passes, _counting = _passes()
    sweeper = StubSweeper(
        jobs=FakeJobs(), deletion=FakeDeletion(), expired=["ses_good"], retention=passes
    )

    report = sweeper.sweep(now=NOW)

    assert report.faulted_passes == ()
    assert report.deletions_faulted == 0
    assert "faulted_passes" not in report.as_counts(), "as_counts stays a mapping of counts"


def test_a_faulting_lease_recovery_does_not_stop_retention() -> None:
    passes, counting = _passes()
    sweeper = StubSweeper(
        jobs=FakeJobs(fault=RuntimeError(SECRET_DETAIL)),
        deletion=FakeDeletion(),
        expired=["ses_good"],
        retention=passes,
    )

    report = sweeper.sweep(now=NOW)

    assert report.expired_sessions == 1
    assert [one.calls for one in counting.values()] == [1, 1, 1, 1]
    assert report.faulted_passes == ("expired_leases",)


def test_an_interrupt_during_a_pass_is_not_absorbed() -> None:
    passes, counting = _passes(accounts_fault=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        passes.run(now=NOW)

    assert counting["events"].calls == 0


def test_an_interrupt_during_a_session_deletion_is_not_absorbed() -> None:
    class InterruptedDeletion:
        def delete_session_content(self, *, session_id: str, reason: str, now: datetime) -> None:
            raise KeyboardInterrupt

    passes, _counting = _passes()
    sweeper = StubSweeper(
        jobs=FakeJobs(), deletion=InterruptedDeletion(), expired=["ses_bad"], retention=passes
    )

    with pytest.raises(KeyboardInterrupt):
        sweeper.sweep(now=NOW)


def _run_main(monkeypatch: pytest.MonkeyPatch, sweeper: RetentionSweeper) -> None:
    from khepri.runtime import wiring
    from khepri.runtime.config import RuntimeSettings

    monkeypatch.setattr(RuntimeSettings, "from_environment", classmethod(lambda cls: None))
    monkeypatch.setattr(wiring, "build_stack", lambda settings: SimpleNamespace(clock=lambda: NOW))
    monkeypatch.setattr(wiring, "build_retention_sweep", lambda stack: sweeper)
    retention_sweep.main()


def test_main_exits_non_zero_after_every_pass_when_one_faulted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    passes, counting = _passes(accounts_fault=RuntimeError(SECRET_DETAIL))
    sweeper = StubSweeper(
        jobs=FakeJobs(),
        deletion=FakeDeletion(faulty="ses_bad"),
        expired=["ses_bad"],
        retention=passes,
    )

    with pytest.raises(SystemExit) as exited:
        _run_main(monkeypatch, sweeper)

    assert exited.value.code == 1
    assert [one.calls for one in counting.values()] == [1, 1, 1, 1]
    line = json.loads(capsys.readouterr().out)
    assert line["faulted_passes"] == ["expired_sessions", "accounts"]
    assert line["purged_invitations"] == 4, "the counts line is still printed"


def test_main_exits_cleanly_when_nothing_faulted(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    passes, _counting = _passes()
    sweeper = StubSweeper(
        jobs=FakeJobs(), deletion=FakeDeletion(), expired=["ses_good"], retention=passes
    )

    _run_main(monkeypatch, sweeper)

    line = json.loads(capsys.readouterr().out)
    assert line["faulted_passes"] == []
    assert line["expired_sessions"] == 1
