from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from khepri.rra.jobs import (
    FailureRequest,
    LeaseAction,
    LeaseLost,
    LeaseRequest,
    ReportJob,
)


class ReportExecutionFailed(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReportJobMessage:
    job_id: str


@dataclass(frozen=True, slots=True)
class WorkerExecution:
    job: ReportJob
    heartbeat: Callable[[], ReportJob]


@dataclass(frozen=True, slots=True)
class WorkerPolicy:
    worker_id: str
    lease_for: timedelta
    retry_delay: timedelta

    def __post_init__(self) -> None:
        _require_positive(self.lease_for, "lease duration")
        _require_positive(self.retry_delay, "retry delay")
        if not self.worker_id:
            raise ValueError("worker_id is required.")


class ReportJobStore(Protocol):
    def lease(self, request: LeaseRequest) -> ReportJob | None: ...

    def heartbeat(self, request: LeaseRequest) -> ReportJob: ...

    def complete(self, request: LeaseAction) -> ReportJob: ...

    def fail(self, request: FailureRequest) -> ReportJob: ...


class ReportWorker:
    def __init__(
        self,
        *,
        jobs: ReportJobStore,
        handler: Callable[[WorkerExecution], None],
        clock: Callable[[], datetime],
        policy: WorkerPolicy,
    ) -> None:
        self._jobs = jobs
        self._handler = handler
        self._clock = clock
        self._policy = policy

    def process(
        self,
        message: ReportJobMessage,
        *,
        heartbeat: Callable[[], None] | None = None,
    ) -> ReportJob | None:
        leased = self._jobs.lease(
            LeaseRequest(
                job_id=message.job_id,
                worker_id=self._policy.worker_id,
                now=self._clock(),
                lease_for=self._policy.lease_for,
            )
        )
        if leased is None:
            return None

        self._execute(leased, heartbeat=heartbeat)
        return self._jobs.complete(self._lease_action(leased))

    def _execute(
        self,
        job: ReportJob,
        *,
        heartbeat: Callable[[], None] | None,
    ) -> None:
        try:
            self._handler(self._execution(job, heartbeat=heartbeat))
        except LeaseLost:
            raise
        except Exception:
            self._record_failure(job)
            raise ReportExecutionFailed("Report job execution failed.") from None

    def _execution(
        self,
        job: ReportJob,
        *,
        heartbeat: Callable[[], None] | None,
    ) -> WorkerExecution:
        return WorkerExecution(
            job=job,
            heartbeat=lambda: self._heartbeat_delivery(job, heartbeat),
        )

    def _heartbeat_delivery(
        self,
        job: ReportJob,
        delivery_heartbeat: Callable[[], None] | None,
    ) -> ReportJob:
        renewed = self._heartbeat(job)
        if delivery_heartbeat is not None:
            delivery_heartbeat()
        return renewed

    def _heartbeat(self, job: ReportJob) -> ReportJob:
        return self._jobs.heartbeat(
            LeaseRequest(
                job_id=job.job_id,
                worker_id=self._policy.worker_id,
                now=self._clock(),
                lease_for=self._policy.lease_for,
            )
        )

    def _record_failure(self, job: ReportJob) -> None:
        failed_at = self._clock()
        self._jobs.fail(
            FailureRequest(
                lease=self._lease_action(job, now=failed_at),
                retry_at=failed_at + self._policy.retry_delay,
            )
        )

    def _lease_action(
        self,
        job: ReportJob,
        *,
        now: datetime | None = None,
    ) -> LeaseAction:
        return LeaseAction(
            job_id=job.job_id,
            worker_id=self._policy.worker_id,
            now=self._clock() if now is None else now,
        )


def _require_positive(value: timedelta, label: str) -> None:
    if value <= timedelta(0):
        raise ValueError(f"{label} must be positive.")
