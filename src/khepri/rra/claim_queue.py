"""PostgreSQL claim-and-redrive delivery for the bounded report worker role.

This module implements the delivery half of RRA-007, which states its obligations as
properties -- "leases, retry limits, restart recovery, and orphan detection" -- and
names no provider mechanism. `KHEPRI-DEC-008` replaces the message broker with this
implementation because PostgreSQL already owns the canonical job state, and a broker
in front of it introduces two clocks that can disagree.

**There is no second queue.** A dead letter is a state transition on the job row
rather than a message moved to another destination, so redrive is visible in the same
place the job's history already lives. `max_attempts` bounds retries exactly as
`maxReceiveCount` did, and it did so before this change too -- the database always
owned that half.

**Claiming and leasing are one act.** `SqlReportJobRepository.lease` selects the row
`FOR UPDATE` and transitions it in the same transaction, so two workers racing for one
job are resolved by the database rather than by a visibility timeout. That is what
makes `receive` safe to call concurrently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.job_persistence import ReportJobRow, SqlReportJobRepository
from khepri.rra.jobs import (
    JOB_QUEUED,
    JOB_RETRYABLE,
    FailureRequest,
    LeaseAction,
    LeaseRequest,
    ReportJob,
)
from khepri.rra.worker import ReportJobMessage

CLAIMABLE_STATES = (JOB_QUEUED, JOB_RETRYABLE)


@dataclass(frozen=True, slots=True)
class ClaimedDelivery:
    """One claimed job: its opaque identifier and the leased row `receive` transitioned.

    The claim already read this job to lease it, so carrying the result spares the
    executor a second read and closes the gap in which the row could change between
    the two. `ReportJob` is job metadata -- identifiers, state, attempt counts, lease
    ownership -- and carries no report content, so this holds the boundary the
    identifier-only shape was protecting.
    """

    message: ReportJobMessage
    job: ReportJob


class ClaimPolicy:
    """Who is claiming, and for how long a claim holds without a heartbeat."""

    __slots__ = ("_lease_for", "_worker_id")

    def __init__(self, *, worker_id: str, lease_for: timedelta) -> None:
        self._worker_id = _named_worker(worker_id)
        self._lease_for = _bounded_lease(lease_for)

    @property
    def worker_id(self) -> str:
        return self._worker_id

    @property
    def lease_for(self) -> timedelta:
        return self._lease_for


class ClaimingReportQueue:
    """Deliver report jobs by claiming them from the job store.

    Offers the port the worker loop already expected of the message broker --
    publish, receive, heartbeat, acknowledge, dead_letter -- so the loop is unchanged
    in shape. What differs is that every operation is a transition on the job row.
    """

    def __init__(
        self,
        *,
        jobs: SqlReportJobRepository,
        factory: sessionmaker[Session],
        policy: ClaimPolicy,
    ) -> None:
        self._jobs = jobs
        self._factory = factory
        self._policy = policy

    def publish(self, message: ReportJobMessage) -> str:
        """Return the identifier of an already-enqueued job.

        Enqueueing *is* the publish, because the row the repository writes is the
        queue entry. Satisfying `ReportPublisher` without sending anything is the
        point: the broker's send was the second write this design removes.
        """
        return _required_text(message.job_id)

    def receive(self, *, now: datetime) -> ClaimedDelivery | None:
        """Claim the job that has been due longest, or return nothing."""
        job_id = self._next_claimable(now=now)
        if job_id is None:
            return None
        leased = self._jobs.lease(
            LeaseRequest(
                job_id=job_id,
                worker_id=self._policy.worker_id,
                now=now,
                lease_for=self._policy.lease_for,
            )
        )
        if leased is None:
            return None
        return ClaimedDelivery(
            message=ReportJobMessage(job_id=leased.job_id),
            job=leased,
        )

    def heartbeat(self, delivery: ClaimedDelivery, *, now: datetime) -> ReportJob:
        """Extend the claim, which is what a visibility-timeout renewal used to do."""
        return self._jobs.heartbeat(
            LeaseRequest(
                job_id=delivery.message.job_id,
                worker_id=self._policy.worker_id,
                now=now,
                lease_for=self._policy.lease_for,
            )
        )

    def acknowledge(self, delivery: ClaimedDelivery, *, now: datetime) -> ReportJob:
        """Settle the delivery by completing its job."""
        return self._jobs.complete(self._lease_action(delivery, now=now))

    def retry(
        self,
        delivery: ClaimedDelivery,
        *,
        now: datetime,
        available_at: datetime,
    ) -> ReportJob:
        """Release the claim and schedule another attempt, or exhaust the limit.

        The repository decides which of those happened: once `attempt_count` reaches
        `max_attempts` it dead-letters instead of rescheduling, so the attempt limit
        is enforced in one place rather than by the caller counting.
        """
        return self._jobs.fail(
            FailureRequest(
                lease=self._lease_action(delivery, now=now),
                retry_at=available_at,
            )
        )

    def recover(self, *, now: datetime) -> tuple[ReportJob, ...]:
        """Return jobs whose holder's claim expired to the claimable set."""
        return self._jobs.recover_expired(now=now)

    def _lease_action(self, delivery: ClaimedDelivery, *, now: datetime) -> LeaseAction:
        return LeaseAction(
            job_id=delivery.message.job_id,
            worker_id=self._policy.worker_id,
            now=now,
        )

    def _next_claimable(self, *, now: datetime) -> str | None:
        """Name the job that has been due longest, without transitioning it.

        Claiming stays `lease`'s job, so two callers racing here are resolved by the
        lease rather than by whichever read first.
        """
        statement = (
            select(ReportJobRow.job_id)
            .where(
                ReportJobRow.state.in_(CLAIMABLE_STATES),
                ReportJobRow.available_at <= now,
                ReportJobRow.attempt_count < ReportJobRow.max_attempts,
            )
            .order_by(ReportJobRow.available_at, ReportJobRow.job_id)
            .limit(1)
        )
        with self._factory() as database:
            return database.execute(statement).scalar_one_or_none()


def _named_worker(worker_id: str) -> str:
    if not isinstance(worker_id, str) or not worker_id.strip():
        raise ValueError("worker_id must name the claiming worker.")
    return worker_id


def _bounded_lease(lease_for: timedelta) -> timedelta:
    if lease_for <= timedelta(0):
        raise ValueError("lease_for must be a positive duration.")
    return lease_for


def _required_text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("job_id must be an opaque non-empty identifier.")
    return value


__all__ = [
    "CLAIMABLE_STATES",
    "ClaimPolicy",
    "ClaimedDelivery",
    "ClaimingReportQueue",
]
