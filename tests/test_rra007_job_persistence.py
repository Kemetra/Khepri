from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.jobs import LeaseLost
from khepri.rra.persistence import Base, SqlReportJobRepository, SqlSessionStore
from khepri.rra.sessions import InvitationService, SessionScope

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
IDEMPOTENCY_KEY = "8f99c79c1c79c892c1a30a74fcc1b536b04e409ee4562acfb82d8d76fb750d7d"


def repositories() -> tuple[
    SqlReportJobRepository,
    SessionScope,
    sessionmaker,
]:
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
    return SqlReportJobRepository(factory), scope, factory


def test_duplicate_enqueue_returns_the_original_job() -> None:
    jobs, scope, _ = repositories()

    original = jobs.enqueue(
        scope=scope,
        job_id="job_original",
        idempotency_key=IDEMPOTENCY_KEY,
        queued_at=NOW,
        max_attempts=3,
    )
    duplicate = jobs.enqueue(
        scope=scope,
        job_id="job_duplicate",
        idempotency_key=IDEMPOTENCY_KEY,
        queued_at=NOW + timedelta(minutes=1),
        max_attempts=5,
    )

    assert duplicate == original
    assert duplicate.job_id == "job_original"
    assert duplicate.state == "queued"
    assert duplicate.attempt_count == 0
    assert duplicate.max_attempts == 3


def test_only_one_worker_can_hold_an_unexpired_lease() -> None:
    jobs, scope, _ = repositories()
    queued = jobs.enqueue(
        scope=scope,
        job_id="job_alpha",
        idempotency_key=IDEMPOTENCY_KEY,
        queued_at=NOW,
        max_attempts=3,
    )

    leased = jobs.lease(
        job_id=queued.job_id,
        worker_id="worker_alpha",
        now=NOW,
        lease_for=timedelta(minutes=2),
    )
    competing = jobs.lease(
        job_id=queued.job_id,
        worker_id="worker_beta",
        now=NOW + timedelta(minutes=1),
        lease_for=timedelta(minutes=2),
    )

    assert leased is not None
    assert leased.state == "running"
    assert leased.attempt_count == 1
    assert leased.lease_owner == "worker_alpha"
    assert leased.lease_expires_at == NOW + timedelta(minutes=2)
    assert competing is None


def test_a_restarted_worker_recovers_and_releases_an_expired_lease() -> None:
    jobs, scope, factory = repositories()
    queued = jobs.enqueue(
        scope=scope,
        job_id="job_alpha",
        idempotency_key=IDEMPOTENCY_KEY,
        queued_at=NOW,
        max_attempts=3,
    )
    jobs.lease(
        job_id=queued.job_id,
        worker_id="worker_stopped",
        now=NOW,
        lease_for=timedelta(minutes=2),
    )

    restarted = SqlReportJobRepository(factory)
    recovered = restarted.recover_expired(now=NOW + timedelta(minutes=2))
    leased_again = restarted.lease(
        job_id=queued.job_id,
        worker_id="worker_restarted",
        now=NOW + timedelta(minutes=2),
        lease_for=timedelta(minutes=2),
    )

    assert len(recovered) == 1
    assert recovered[0].state == "retryable"
    assert recovered[0].lease_owner is None
    assert recovered[0].lease_expires_at is None
    assert leased_again is not None
    assert leased_again.state == "running"
    assert leased_again.attempt_count == 2
    assert leased_again.lease_owner == "worker_restarted"


def test_failures_stop_after_the_configured_attempt_limit() -> None:
    jobs, scope, _ = repositories()
    queued = jobs.enqueue(
        scope=scope,
        job_id="job_alpha",
        idempotency_key=IDEMPOTENCY_KEY,
        queued_at=NOW,
        max_attempts=2,
    )
    first = jobs.lease(
        job_id=queued.job_id,
        worker_id="worker_alpha",
        now=NOW,
        lease_for=timedelta(minutes=2),
    )
    assert first is not None

    retryable = jobs.fail(
        job_id=first.job_id,
        worker_id="worker_alpha",
        now=NOW + timedelta(seconds=30),
        retry_at=NOW + timedelta(minutes=1),
    )
    second = jobs.lease(
        job_id=queued.job_id,
        worker_id="worker_beta",
        now=NOW + timedelta(minutes=1),
        lease_for=timedelta(minutes=2),
    )
    assert second is not None
    exhausted = jobs.fail(
        job_id=second.job_id,
        worker_id="worker_beta",
        now=NOW + timedelta(minutes=1, seconds=30),
        retry_at=NOW + timedelta(minutes=2),
    )
    impossible_retry = jobs.lease(
        job_id=queued.job_id,
        worker_id="worker_gamma",
        now=NOW + timedelta(minutes=2),
        lease_for=timedelta(minutes=2),
    )

    assert retryable.state == "retryable"
    assert retryable.available_at == NOW + timedelta(minutes=1)
    assert exhausted.state == "failed"
    assert exhausted.attempt_count == 2
    assert exhausted.completed_at == NOW + timedelta(minutes=1, seconds=30)
    assert impossible_retry is None


def test_only_the_current_lease_holder_can_complete_a_job() -> None:
    jobs, scope, _ = repositories()
    queued = jobs.enqueue(
        scope=scope,
        job_id="job_alpha",
        idempotency_key=IDEMPOTENCY_KEY,
        queued_at=NOW,
        max_attempts=3,
    )
    leased = jobs.lease(
        job_id=queued.job_id,
        worker_id="worker_alpha",
        now=NOW,
        lease_for=timedelta(minutes=2),
    )
    assert leased is not None

    with pytest.raises(LeaseLost):
        jobs.complete(
            job_id=leased.job_id,
            worker_id="worker_stale",
            now=NOW + timedelta(minutes=1),
        )
    completed = jobs.complete(
        job_id=leased.job_id,
        worker_id="worker_alpha",
        now=NOW + timedelta(minutes=1),
    )

    assert completed.state == "succeeded"
    assert completed.completed_at == NOW + timedelta(minutes=1)
    assert completed.lease_owner is None
    assert completed.lease_expires_at is None


def test_a_heartbeat_keeps_an_active_job_out_of_orphan_recovery() -> None:
    jobs, scope, _ = repositories()
    queued = jobs.enqueue(
        scope=scope,
        job_id="job_alpha",
        idempotency_key=IDEMPOTENCY_KEY,
        queued_at=NOW,
        max_attempts=3,
    )
    leased = jobs.lease(
        job_id=queued.job_id,
        worker_id="worker_alpha",
        now=NOW,
        lease_for=timedelta(minutes=2),
    )
    assert leased is not None

    extended = jobs.heartbeat(
        job_id=leased.job_id,
        worker_id="worker_alpha",
        now=NOW + timedelta(minutes=1),
        lease_for=timedelta(minutes=3),
    )
    recovered = jobs.recover_expired(now=NOW + timedelta(minutes=2))

    assert extended.lease_expires_at == NOW + timedelta(minutes=4)
    assert recovered == ()
