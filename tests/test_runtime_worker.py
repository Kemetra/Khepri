from __future__ import annotations

from datetime import UTC, datetime

import pytest

from khepri.rra.jobs import (
    JOB_DEAD_LETTERED,
    JOB_QUEUED,
    JOB_RETRYABLE,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    ReportJob,
)
from khepri.rra.sqs_queue import QueueDelivery
from khepri.rra.worker import ReportExecutionFailed, ReportJobMessage
from khepri.runtime.worker import LEASE_FOR, RETRY_DELAY, SqsWorkerLoop

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def job(state: str) -> ReportJob:
    return ReportJob(
        job_id="job_alpha",
        owner_id="own_alpha",
        session_id="ses_alpha",
        idempotency_key="ab" * 32,
        state=state,
        queued_at=NOW,
        available_at=NOW,
        attempt_count=1,
        max_attempts=3,
        lease_owner=None,
        lease_expires_at=None,
        completed_at=NOW if state in {JOB_SUCCEEDED, JOB_DEAD_LETTERED} else None,
        dead_letter_reason="retries_exhausted" if state == JOB_DEAD_LETTERED else None,
    )


DELIVERY = QueueDelivery(
    message=ReportJobMessage(job_id="job_alpha"),
    receipt_handle="receipt_alpha",
)


class QueueStub:
    def __init__(self, delivery: QueueDelivery | None = DELIVERY) -> None:
        self.delivery = delivery
        self.receives = 0
        self.acknowledged: list[QueueDelivery] = []
        self.heartbeats: list[QueueDelivery] = []

    def receive(self) -> QueueDelivery | None:
        self.receives += 1
        delivery, self.delivery = self.delivery, None
        return delivery

    def acknowledge(self, delivery: QueueDelivery) -> None:
        self.acknowledged.append(delivery)

    def heartbeat(self, delivery: QueueDelivery) -> None:
        self.heartbeats.append(delivery)


class WorkerStub:
    def __init__(
        self,
        result: ReportJob | None = None,
        *,
        error: Exception | None = None,
        pulse: bool = False,
    ) -> None:
        self.result = result
        self.error = error
        self.pulse = pulse
        self.messages: list[ReportJobMessage] = []

    def process(self, message: ReportJobMessage, *, heartbeat: object) -> ReportJob | None:
        self.messages.append(message)
        if self.pulse:
            heartbeat()  # type: ignore[operator]
        if self.error is not None:
            raise self.error
        return self.result


class ReaderStub:
    def __init__(self, found: ReportJob | None = None) -> None:
        self.found = found
        self.lookups: list[str] = []

    def find(self, job_id: str) -> ReportJob | None:
        self.lookups.append(job_id)
        return self.found


def loop(queue: QueueStub, worker: WorkerStub, reader: ReaderStub) -> SqsWorkerLoop:
    return SqsWorkerLoop(queue=queue, worker=worker, jobs=reader)


def test_empty_receive_does_no_work() -> None:
    queue = QueueStub(None)

    assert loop(queue, WorkerStub(), ReaderStub()).run_once() is False
    assert queue.acknowledged == []


def test_successful_processing_acknowledges_the_delivery() -> None:
    queue = QueueStub()

    assert loop(queue, WorkerStub(job(JOB_SUCCEEDED)), ReaderStub()).run_once() is True
    assert queue.acknowledged == [DELIVERY]


def test_duplicate_delivery_is_acknowledged_only_when_postgresql_says_succeeded() -> None:
    queue = QueueStub()
    reader = ReaderStub(job(JOB_SUCCEEDED))

    loop(queue, WorkerStub(None), reader).run_once()

    assert reader.lookups == ["job_alpha"]
    assert queue.acknowledged == [DELIVERY]


@pytest.mark.parametrize(
    "state",
    [JOB_QUEUED, JOB_RUNNING, JOB_RETRYABLE, JOB_DEAD_LETTERED],
)
def test_non_succeeded_duplicate_is_left_for_sqs_redrive(state: str) -> None:
    queue = QueueStub()

    loop(queue, WorkerStub(None), ReaderStub(job(state))).run_once()

    assert queue.acknowledged == []


def test_recorded_execution_failure_does_not_acknowledge_or_stop_the_loop() -> None:
    queue = QueueStub()

    processed = loop(
        queue,
        WorkerStub(error=ReportExecutionFailed("failed")),
        ReaderStub(job(JOB_RETRYABLE)),
    ).run_once()

    assert processed is True
    assert queue.acknowledged == []


def test_worker_heartbeat_extends_the_sqs_delivery_visibility() -> None:
    queue = QueueStub()

    loop(queue, WorkerStub(job(JOB_SUCCEEDED), pulse=True), ReaderStub()).run_once()

    assert queue.heartbeats == [DELIVERY]


def test_runtime_policy_is_the_approved_bounded_policy() -> None:
    assert LEASE_FOR.total_seconds() == 300
    assert RETRY_DELAY.total_seconds() == 60
