from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from khepri.rra.jobs import (
    FailureRequest,
    LeaseAction,
    LeaseRequest,
    ReportJob,
)


class ReportExecutionFailed(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ReportJobMessage:
    job_id: str


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

    def complete(self, request: LeaseAction) -> ReportJob: ...

    def fail(self, request: FailureRequest) -> ReportJob: ...


class ReportWorker:
    def __init__(
        self,
        *,
        jobs: ReportJobStore,
        handler: Callable[[ReportJob], None],
        clock: Callable[[], datetime],
        policy: WorkerPolicy,
    ) -> None:
        self._jobs = jobs
        self._handler = handler
        self._clock = clock
        self._policy = policy

    def process(self, message: ReportJobMessage) -> ReportJob | None:
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
        try:
            self._handler(leased)
        except Exception:
            self._record_failure(leased)
            raise ReportExecutionFailed("Report job execution failed.") from None
        return self._jobs.complete(self._lease_action(leased))

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
