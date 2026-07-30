from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.jobs import EnqueueJob, LeaseLost, ReportJob
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.sessions import InvitationService, SessionScope
from khepri.rra.worker import (
    ReportExecutionFailed,
    ReportJobMessage,
    ReportWorker,
    WorkerExecution,
    WorkerPolicy,
)

NOW = datetime(2026, 7, 30, 16, 0, tzinfo=UTC)
IDEMPOTENCY_KEY = "8f99c79c1c79c892c1a30a74fcc1b536b04e409ee4562acfb82d8d76fb750d7d"


class Clock:
    def __init__(self, *values: datetime) -> None:
        self._values = iter(values)

    def __call__(self) -> datetime:
        return next(self._values)


class Handler:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.jobs: list[ReportJob] = []

    def __call__(self, execution: WorkerExecution) -> None:
        self.jobs.append(execution.job)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("customer content must not escape the handler")


class HeartbeatHandler(Handler):
    def __init__(self) -> None:
        super().__init__()
        self.heartbeats: list[ReportJob] = []

    def __call__(self, execution: WorkerExecution) -> None:
        self.jobs.append(execution.job)
        self.heartbeats.append(execution.heartbeat())


class Harness:
    def __init__(self, *, max_attempts: int = 3) -> None:
        engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        factory = sessionmaker(engine, expire_on_commit=False)
        sessions = SqlSessionStore(factory)
        invitations = InvitationService(sessions)
        beta_session = invitations.redeem(
            invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)),
            now=NOW,
        )
        self.scope = SessionScope(
            owner_id=beta_session.owner_id,
            session_id=beta_session.session_id,
        )
        self.jobs = SqlReportJobRepository(factory)
        self.queued = self.jobs.enqueue(
            EnqueueJob(
                scope=self.scope,
                job_id="job_alpha",
                idempotency_key=IDEMPOTENCY_KEY,
                queued_at=NOW,
                max_attempts=max_attempts,
            )
        )


def worker(
    test: Harness,
    handler: Handler,
    clock: Clock,
    policy: WorkerPolicy | None = None,
) -> ReportWorker:
    return ReportWorker(
        jobs=test.jobs,
        handler=handler,
        clock=clock,
        policy=policy
        or WorkerPolicy(
            worker_id="worker_alpha",
            lease_for=timedelta(minutes=2),
            retry_delay=timedelta(minutes=1),
        ),
    )


def test_successful_delivery_completes_the_leased_job_once() -> None:
    test = Harness()
    handler = Handler()
    report_worker = worker(test, handler, Clock(NOW, NOW + timedelta(seconds=30)))

    completed = report_worker.process(ReportJobMessage(job_id=test.queued.job_id))
    duplicate = worker(
        test,
        handler,
        Clock(NOW + timedelta(minutes=1)),
    ).process(ReportJobMessage(job_id=test.queued.job_id))

    assert completed is not None
    assert completed.state == "succeeded"
    assert completed.attempt_count == 1
    assert completed.completed_at == NOW + timedelta(seconds=30)
    assert len(handler.jobs) == 1
    assert duplicate is None


def test_handler_failure_is_sanitized_and_scheduled_for_retry() -> None:
    test = Harness()
    handler = Handler(failures=1)
    report_worker = worker(test, handler, Clock(NOW, NOW + timedelta(seconds=15)))

    with pytest.raises(ReportExecutionFailed, match="failed") as captured:
        report_worker.process(ReportJobMessage(job_id=test.queued.job_id))

    assert captured.value.__cause__ is None
    assert "customer content" not in str(captured.value)
    retried = worker(
        test,
        handler,
        Clock(
            NOW + timedelta(minutes=1, seconds=15),
            NOW + timedelta(minutes=1, seconds=30),
        ),
    ).process(ReportJobMessage(job_id=test.queued.job_id))
    assert retried is not None
    assert retried.state == "succeeded"
    assert retried.attempt_count == 2


def test_failures_stop_at_the_job_attempt_limit() -> None:
    test = Harness(max_attempts=2)
    handler = Handler(failures=2)

    with pytest.raises(ReportExecutionFailed):
        worker(test, handler, Clock(NOW, NOW + timedelta(seconds=10))).process(
            ReportJobMessage(job_id=test.queued.job_id)
        )
    with pytest.raises(ReportExecutionFailed) as exhausted:
        worker(
            test,
            handler,
            Clock(
                NOW + timedelta(minutes=1, seconds=10),
                NOW + timedelta(minutes=1, seconds=20),
            ),
        ).process(ReportJobMessage(job_id=test.queued.job_id))

    assert exhausted.value.__cause__ is None
    assert len(handler.jobs) == 2
    assert worker(
        test,
        handler,
        Clock(NOW + timedelta(minutes=3)),
    ).process(ReportJobMessage(job_id=test.queued.job_id)) is None


def test_stale_worker_cannot_complete_after_its_lease_expires() -> None:
    test = Harness()
    handler = Handler()
    report_worker = worker(
        test,
        handler,
        Clock(NOW, NOW + timedelta(minutes=2)),
        WorkerPolicy(
            worker_id="worker_alpha",
            lease_for=timedelta(minutes=1),
            retry_delay=timedelta(minutes=1),
        ),
    )

    with pytest.raises(LeaseLost):
        report_worker.process(ReportJobMessage(job_id=test.queued.job_id))

    recovered = test.jobs.recover_expired(now=NOW + timedelta(minutes=2))
    assert len(recovered) == 1
    assert recovered[0].state == "retryable"


def test_timely_heartbeat_extends_a_long_running_worker_lease() -> None:
    test = Harness()
    handler = HeartbeatHandler()
    policy = WorkerPolicy(
        worker_id="worker_alpha",
        lease_for=timedelta(minutes=1),
        retry_delay=timedelta(minutes=1),
    )
    report_worker = worker(
        test,
        handler,
        Clock(NOW, NOW + timedelta(seconds=50), NOW + timedelta(seconds=90)),
        policy,
    )

    completed = report_worker.process(ReportJobMessage(job_id=test.queued.job_id))

    assert completed is not None
    assert completed.state == "succeeded"
    assert handler.heartbeats[0].lease_expires_at == NOW + timedelta(seconds=110)


def test_late_heartbeat_cannot_revive_an_expired_lease() -> None:
    test = Harness()
    handler = HeartbeatHandler()
    report_worker = worker(
        test,
        handler,
        Clock(NOW, NOW + timedelta(minutes=1)),
        WorkerPolicy(
            worker_id="worker_alpha",
            lease_for=timedelta(minutes=1),
            retry_delay=timedelta(minutes=1),
        ),
    )

    with pytest.raises(LeaseLost):
        report_worker.process(ReportJobMessage(job_id=test.queued.job_id))

    recovered = test.jobs.recover_expired(now=NOW + timedelta(minutes=1))
    assert len(recovered) == 1
    assert recovered[0].state == "retryable"


def test_worker_policy_rejects_unbounded_or_immediate_retries() -> None:
    with pytest.raises(ValueError, match="lease"):
        WorkerPolicy(
            worker_id="worker_alpha",
            lease_for=timedelta(0),
            retry_delay=timedelta(minutes=1),
        )
    with pytest.raises(ValueError, match="retry"):
        WorkerPolicy(
            worker_id="worker_alpha",
            lease_for=timedelta(minutes=1),
            retry_delay=timedelta(0),
        )


def test_queue_message_contains_only_an_opaque_job_identifier() -> None:
    names = {field.name for field in fields(ReportJobMessage)}

    assert names == {"job_id"}
