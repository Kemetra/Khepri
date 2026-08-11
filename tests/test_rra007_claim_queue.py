"""RRA-007 delivery controls over the PostgreSQL claim-and-redrive queue.

These assertions are carried over from `test_rra007_sqs_queue.py`. `RRA-007` states
the obligations as properties -- "leases, retry limits, restart recovery, and orphan
detection" -- and names no provider mechanism, so replacing the delivery mechanism
must leave every one of them observable.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.claim_queue import ClaimedDelivery, ClaimingReportQueue
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.jobs import (
    JOB_DEAD_LETTERED,
    JOB_QUEUED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    EnqueueJob,
    ReportJob,
)
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.report_services import JobReader
from khepri.rra.sessions import InvitationService, SessionScope
from khepri.rra.worker import ReportJobMessage

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)
LEASE_FOR = timedelta(seconds=300)
RETRY_DELAY = timedelta(seconds=60)
IDEMPOTENCY_KEY = "8f99c79c1c79c892c1a30a74fcc1b536b04e409ee4562acfb82d8d76fb750d7d"


@dataclass(frozen=True, slots=True)
class Harness:
    queue: ClaimingReportQueue
    jobs: SqlReportJobRepository
    reader: JobReader
    scope: SessionScope

    def enqueue(self, job_id: str = "job_alpha", *, max_attempts: int = 3) -> ReportJob:
        return self.jobs.enqueue(
            EnqueueJob(
                scope=self.scope,
                job_id=job_id,
                idempotency_key=IDEMPOTENCY_KEY,
                queued_at=NOW,
                max_attempts=max_attempts,
            )
        )

    def state_of(self, job_id: str) -> str:
        found = self.reader.find(job_id)
        assert found is not None
        return found.state

    def lease_expiry_of(self, job_id: str) -> datetime | None:
        found = self.reader.find(job_id)
        assert found is not None
        return found.lease_expires_at


def harness(worker_id: str = "worker-alpha") -> Harness:
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
    scope = SessionScope(
        owner_id=beta_session.owner_id,
        session_id=beta_session.session_id,
    )
    jobs = SqlReportJobRepository(factory)
    return Harness(
        queue=ClaimingReportQueue(
            jobs=jobs,
            factory=factory,
            policy=_policy(worker_id),
        ),
        jobs=jobs,
        reader=JobReader(factory),
        scope=scope,
    )


def _policy(worker_id: str):
    from khepri.rra.claim_queue import ClaimPolicy

    return ClaimPolicy(worker_id=worker_id, lease_for=LEASE_FOR)


def test_publish_returns_the_opaque_identifier_and_leaves_the_job_claimable() -> None:
    """Publishing records no separate message; the enqueued row is the queue."""
    stand = harness()
    job = stand.enqueue()

    published = stand.queue.publish(ReportJobMessage(job_id=job.job_id))

    assert published == job.job_id
    assert stand.state_of(job.job_id) == JOB_QUEUED


def test_receive_claims_one_due_job_and_marks_it_running() -> None:
    stand = harness()
    job = stand.enqueue()

    delivery = stand.queue.receive(now=NOW)

    assert delivery is not None
    assert delivery.message.job_id == job.job_id
    assert stand.state_of(job.job_id) == JOB_RUNNING


def test_receive_returns_nothing_when_no_job_is_due() -> None:
    stand = harness()

    assert stand.queue.receive(now=NOW) is None


def test_a_claimed_job_is_invisible_to_a_second_worker() -> None:
    """The lease is the exclusivity boundary, replacing the visibility timeout."""
    stand = harness()
    stand.enqueue()

    first = stand.queue.receive(now=NOW)
    second = stand.queue.receive(now=NOW)

    assert first is not None
    assert second is None


def test_heartbeat_extends_the_lease_of_a_running_job() -> None:
    stand = harness()
    stand.enqueue()
    delivery = stand.queue.receive(now=NOW)
    assert delivery is not None

    later = NOW + timedelta(seconds=120)
    extended = stand.queue.heartbeat(delivery, now=later)

    # Compared naively because SQLite drops the timezone on round-trip; the value,
    # not the tzinfo, is what this asserts.
    assert extended.lease_expires_at is not None
    expiry = stand.lease_expiry_of(delivery.message.job_id)
    assert expiry is not None
    assert expiry.replace(tzinfo=UTC) == later + LEASE_FOR


def test_acknowledge_completes_the_job_exactly_once() -> None:
    stand = harness()
    stand.enqueue()
    delivery = stand.queue.receive(now=NOW)
    assert delivery is not None

    stand.queue.acknowledge(delivery, now=NOW + timedelta(seconds=5))

    assert stand.state_of(delivery.message.job_id) == JOB_SUCCEEDED


def test_an_expired_lease_returns_the_job_to_the_claimable_set() -> None:
    """Restart recovery: a worker that dies mid-flight does not strand its job."""
    stand = harness()
    stand.enqueue()
    first = stand.queue.receive(now=NOW)
    assert first is not None

    expired = NOW + LEASE_FOR + timedelta(seconds=1)
    reclaimed = stand.queue.recover(now=expired)

    assert len(reclaimed) == 1
    assert stand.queue.receive(now=expired) is not None


def test_redrive_is_a_state_transition_not_a_second_queue() -> None:
    """A dead letter is reachable only by exhausting attempts, never by a bypass.

    In the broker design `dead_letter` was a separate action because the queue and
    the job state were two systems that could disagree. With PostgreSQL owning both,
    a job with attempts remaining cannot be redriven at all -- which is a stronger
    invariant than the mechanism it replaces.
    """
    stand = harness()
    stand.enqueue(max_attempts=1)
    delivery = stand.queue.receive(now=NOW)
    assert delivery is not None

    released = NOW + timedelta(seconds=5)
    stand.queue.retry(delivery, now=released, available_at=released + RETRY_DELAY)

    assert stand.state_of(delivery.message.job_id) == JOB_DEAD_LETTERED
    assert not hasattr(stand.queue, "dead_letter")


def test_retry_schedules_the_job_beyond_the_retry_delay() -> None:
    stand = harness()
    stand.enqueue()
    delivery = stand.queue.receive(now=NOW)
    assert delivery is not None

    released = NOW + timedelta(seconds=5)
    stand.queue.retry(delivery, now=released, available_at=released + RETRY_DELAY)

    assert stand.queue.receive(now=released) is None
    assert stand.queue.receive(now=released + RETRY_DELAY) is not None


def test_retries_stop_at_the_attempt_limit() -> None:
    stand = harness()
    stand.enqueue(max_attempts=1)
    delivery = stand.queue.receive(now=NOW)
    assert delivery is not None

    released = NOW + timedelta(seconds=5)
    stand.queue.retry(delivery, now=released, available_at=released + RETRY_DELAY)

    assert stand.state_of(delivery.message.job_id) == JOB_DEAD_LETTERED
    assert stand.queue.receive(now=released + RETRY_DELAY) is None


def test_claim_policy_rejects_an_unbounded_lease() -> None:
    from khepri.rra.claim_queue import ClaimPolicy

    with pytest.raises(ValueError):
        ClaimPolicy(worker_id="worker-alpha", lease_for=timedelta(0))


def test_claim_policy_rejects_an_anonymous_worker() -> None:
    from khepri.rra.claim_queue import ClaimPolicy

    with pytest.raises(ValueError):
        ClaimPolicy(worker_id="   ", lease_for=LEASE_FOR)


def test_delivery_carries_only_the_opaque_identifier() -> None:
    """Content-free evidence: a delivery names a job and nothing about its data."""
    stand = harness()
    stand.enqueue()
    delivery = stand.queue.receive(now=NOW)

    assert delivery is not None
    assert isinstance(delivery, ClaimedDelivery)
    assert delivery.message == ReportJobMessage(job_id="job_alpha")
    assert [field.name for field in fields(delivery.message)] == ["job_id"]
