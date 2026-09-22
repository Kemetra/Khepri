"""RRA-007: every picker and the lease agree on which report job is claimable (#518).

A job whose session has `deletion_requested_at` set but has not yet been settled by
`defer_for_publication` -- a crash between deletion's two transactions leaves one --
must never be picked. When the pick query and the lease disagreed, the pick named
that job on every poll and the lease refused it every time, so the one-at-a-time
worker stalled every other tenant's jobs behind it.

These run the real claim paths on SQLite, not fakes: what they are about is the
query each picker issues.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.local.worker import LocalWorkerPorts, build_local_worker
from khepri.rra.claim_queue import ClaimingReportQueue, ClaimPolicy
from khepri.rra.job_persistence import ReportJobRow, SqlReportJobRepository
from khepri.rra.jobs import JOB_QUEUED, JOB_RUNNING, JOB_SUCCEEDED, EnqueueJob
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.report_services import JobReader
from khepri.rra.sessions import InvitationService, SessionExpired, SessionScope
from khepri.rra.worker import WorkerExecution

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
STUCK_KEY = "a" * 64
LIVE_KEY = "b" * 64


@dataclass(frozen=True, slots=True)
class Stand:
    factory: sessionmaker[Session]
    jobs: SqlReportJobRepository
    sessions: SqlSessionStore
    reader: JobReader
    deleting: SessionScope
    live: SessionScope

    def enqueue(self, scope: SessionScope, job_id: str, key: str, at: datetime) -> None:
        self.jobs.enqueue(
            EnqueueJob(
                scope=scope,
                job_id=job_id,
                idempotency_key=key,
                queued_at=at,
                max_attempts=3,
            )
        )

    def request_deletion(self, scope: SessionScope) -> None:
        """What `SqlDeletionRepository.begin` commits, with no deferral after it."""
        session = self.sessions.get_session(scope.session_id)
        assert session is not None
        self.sessions.update_session(replace(session, deletion_requested_at=NOW))

    def state_of(self, job_id: str) -> str:
        found = self.reader.find(job_id)
        assert found is not None
        return found.state


def _stand() -> Stand:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    sessions = SqlSessionStore(factory)
    invitations = InvitationService(sessions)

    def redeem() -> SessionScope:
        beta = invitations.redeem(
            invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)),
            now=NOW - timedelta(hours=1),
        )
        return SessionScope(owner_id=beta.owner_id, session_id=beta.session_id)

    return Stand(
        factory=factory,
        jobs=SqlReportJobRepository(factory),
        sessions=sessions,
        reader=JobReader(factory),
        deleting=redeem(),
        live=redeem(),
    )


def stalled_queue() -> Stand:
    """A deletion-requested job due first, and another tenant's live job behind it.

    The stuck job is enqueued before deletion is requested (enqueue now refuses a
    deletion-requested session) and a minute earlier, so a picker without the
    session filter names it first rather than finding the live job by accident.
    """
    stand = _stand()
    stand.enqueue(stand.deleting, "job_stuck", STUCK_KEY, NOW - timedelta(minutes=1))
    stand.enqueue(stand.live, "job_live", LIVE_KEY, NOW)
    stand.request_deletion(stand.deleting)
    return stand


def test_the_claim_queue_claims_the_live_job_past_a_deletion_requested_one() -> None:
    stand = stalled_queue()
    queue = ClaimingReportQueue(
        jobs=stand.jobs,
        factory=stand.factory,
        policy=ClaimPolicy(worker_id="worker-alpha", lease_for=timedelta(seconds=300)),
    )

    delivery = queue.receive(now=NOW)

    assert delivery is not None
    assert delivery.job.job_id == "job_live"
    assert stand.state_of("job_live") == JOB_RUNNING
    assert stand.state_of("job_stuck") == JOB_QUEUED


def test_a_local_drain_counts_only_the_work_it_actually_did() -> None:
    """`processed` was the drain limit while the stuck job was re-picked each poll."""
    stand = stalled_queue()
    handled: list[str] = []

    def handler(execution: WorkerExecution) -> None:
        handled.append(execution.job.job_id)

    worker = build_local_worker(
        LocalWorkerPorts(jobs=stand.jobs, factory=stand.factory, handler=handler),
        clock=lambda: NOW,
    )

    processed = worker.drain(limit=5)

    assert processed == 1
    assert handled == ["job_live"]
    assert stand.state_of("job_live") == JOB_SUCCEEDED
    assert stand.state_of("job_stuck") == JOB_QUEUED


def test_the_shared_pick_names_the_job_due_longest_first() -> None:
    """Both pickers now issue one statement, so its order is pinned once here."""
    stand = _stand()
    stand.enqueue(stand.live, "job_later", LIVE_KEY, NOW)
    stand.enqueue(stand.deleting, "job_earlier", STUCK_KEY, NOW - timedelta(minutes=1))
    handled: list[str] = []
    worker = build_local_worker(
        LocalWorkerPorts(
            jobs=stand.jobs,
            factory=stand.factory,
            handler=lambda execution: handled.append(execution.job.job_id),
        ),
        clock=lambda: NOW,
    )

    assert worker.drain(limit=5) == 2
    assert handled == ["job_earlier", "job_later"]


def test_enqueue_refuses_a_session_whose_deletion_committed_first() -> None:
    """The re-check runs under the session row lock `begin` also takes.

    On SQLite this proves the check exists inside enqueue's own transaction; that it
    closes the interleaving with a concurrent `begin` rests on both taking the same
    `FOR UPDATE` lock on PostgreSQL.
    """
    stand = _stand()
    stand.request_deletion(stand.deleting)

    with pytest.raises(SessionExpired):
        stand.enqueue(stand.deleting, "job_late", STUCK_KEY, NOW)

    with stand.factory() as database:
        count = database.scalar(select(func.count()).select_from(ReportJobRow))
    assert count == 0
