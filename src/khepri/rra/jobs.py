from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from khepri.rra.sessions import SessionScope

JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_RETRYABLE = "retryable"
JOB_SUCCEEDED = "succeeded"
JOB_DEAD_LETTERED = "dead_lettered"

JOB_STATES = frozenset(
    {
        JOB_QUEUED,
        JOB_RUNNING,
        JOB_RETRYABLE,
        JOB_SUCCEEDED,
        JOB_DEAD_LETTERED,
    }
)

DEAD_LETTER_RETRIES_EXHAUSTED = "retries_exhausted"
DEAD_LETTER_CONTENT_DELETED = "content_deleted"

DEAD_LETTER_REASONS = frozenset(
    {
        DEAD_LETTER_RETRIES_EXHAUSTED,
        DEAD_LETTER_CONTENT_DELETED,
    }
)

ATTEMPT_RETRY_SCHEDULED = "retry_scheduled"
ATTEMPT_LEASE_RECLAIMED = "lease_reclaimed"
ATTEMPT_RETRIES_EXHAUSTED = "retries_exhausted"

ATTEMPT_DISPOSITIONS = frozenset(
    {
        ATTEMPT_RETRY_SCHEDULED,
        ATTEMPT_LEASE_RECLAIMED,
        ATTEMPT_RETRIES_EXHAUSTED,
    }
)

# A job can only be orphaned while nobody legitimately holds it, so a leased or
# already settled job is never resolved by an orphan sweep.
_ORPHANABLE_STATES = frozenset({JOB_QUEUED, JOB_RETRYABLE})


class LeaseLost(RuntimeError):
    pass


class UnknownJobState(ValueError):
    pass


def orphanable(state: str) -> bool:
    """Whether a job in this state may be terminally resolved as an orphan."""
    if state not in JOB_STATES:
        raise UnknownJobState("Report job state is unrecognized.")
    return state in _ORPHANABLE_STATES


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
    dead_letter_reason: str | None


@dataclass(frozen=True, slots=True)
class JobAttempt:
    """Content-free evidence of one released attempt and its bounded outcome."""

    job_id: str
    session_id: str
    attempt_number: int
    released_at: datetime
    disposition: str
    available_at: datetime | None

    def __post_init__(self) -> None:
        _require_identifier(self.job_id, "job_id")
        _require_identifier(self.session_id, "session_id")
        if self.attempt_number <= 0:
            raise ValueError("attempt_number must be positive.")
        if self.disposition not in ATTEMPT_DISPOSITIONS:
            raise ValueError("disposition is not a governed attempt outcome.")
        exhausted = self.disposition == ATTEMPT_RETRIES_EXHAUSTED
        if exhausted != (self.available_at is None):
            raise ValueError("Only a retried attempt may schedule availability.")


def _require_identifier(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required.")
