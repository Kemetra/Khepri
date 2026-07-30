from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from khepri.rra.sessions import SessionScope

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_RETRYABLE = "retryable"
JOB_SUCCEEDED = "succeeded"
JOB_FAILED = "failed"


class LeaseLost(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class EnqueueJob:
    scope: SessionScope
    job_id: str
    idempotency_key: str
    queued_at: datetime
    max_attempts: int


@dataclass(frozen=True, slots=True)
class LeaseRequest:
    job_id: str
    worker_id: str
    now: datetime
    lease_for: timedelta


@dataclass(frozen=True, slots=True)
class LeaseAction:
    job_id: str
    worker_id: str
    now: datetime


@dataclass(frozen=True, slots=True)
class FailureRequest:
    lease: LeaseAction
    retry_at: datetime


@dataclass(frozen=True, slots=True)
class ReportJob:
    job_id: str
    owner_id: str
    session_id: str
    idempotency_key: str
    state: str
    queued_at: datetime
    available_at: datetime
    attempt_count: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    completed_at: datetime | None
