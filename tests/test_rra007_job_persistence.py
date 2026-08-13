from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.jobs import (
    EnqueueJob,
    FailureRequest,
    JobAttempt,
    LeaseAction,
    LeaseLost,
    LeaseRequest,
    ReportJob,
    UnknownJobState,
    orphanable,
)
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.sessions import (
    CrossSessionAccessDenied,
    InvitationService,
    SessionScope,
)

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
IDEMPOTENCY_KEY = "8f99c79c1c79c892c1a30a74fcc1b536b04e409ee4562acfb82d8d76fb750d7d"


@dataclass(frozen=True, slots=True)
class Harness:
    jobs: SqlReportJobRepository
    sessions: SqlSessionStore
    scope: SessionScope
    factory: sessionmaker

    def enqueue(
        self,
        *,
        job_id: str = "job_alpha",
        queued_at: datetime = NOW,
        max_attempts: int = 3,
    ) -> ReportJob:
        return self.jobs.enqueue(
            EnqueueJob(
                scope=self.scope,
                job_id=job_id,
                idempotency_key=IDEMPOTENCY_KEY,
                queued_at=queued_at,
                max_attempts=max_attempts,
            )
        )

    def lease(
        self,
        job_id: str,
        worker_id: str,
        *,
        now: datetime = NOW,
    ) -> ReportJob | None:
        return self.jobs.lease(
            LeaseRequest(
                job_id=job_id,
                worker_id=worker_id,
                now=now,
                lease_for=timedelta(minutes=2),
            )
        )

    def fail(
        self,
        job: ReportJob,
        worker_id: str,
        *,
        now: datetime,
        retry_at: datetime,
    ) -> ReportJob:
        return self.jobs.fail(
            FailureRequest(
                lease=LeaseAction(
                    job_id=job.job_id,
                    worker_id=worker_id,
                    now=now,
                ),
                retry_at=retry_at,
            )
        )

    def delete_content(self, *, at: datetime) -> None:
        session = self.sessions.get_session(self.scope.session_id)
        assert session is not None
        self.sessions.update_session(
            replace(session, deletion_requested_at=at, content_deleted_at=at)
        )

    def attempts(self, job_id: str) -> tuple[JobAttempt, ...]:
        return self.jobs.list_attempts(scope=self.scope, job_id=job_id)


def harness() -> Harness:
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
    return Harness(
        jobs=SqlReportJobRepository(factory),
        sessions=sessions,
        scope=scope,
        factory=factory,
    )


def test_duplicate_enqueue_returns_the_original_job() -> None:
    test = harness()

    original = test.enqueue(job_id="job_original")
    duplicate = test.enqueue(
        job_id="job_duplicate",
        queued_at=NOW + timedelta(minutes=1),
        max_attempts=5,
    )

    assert duplicate == original
    assert duplicate.job_id == "job_original"
    assert duplicate.state == "queued"
    assert duplicate.attempt_count == 0
    assert duplicate.max_attempts == 3


def test_only_one_worker_can_hold_an_unexpired_lease() -> None:
    test = harness()
    queued = test.enqueue()

    leased = test.lease(queued.job_id, "worker_alpha")
    competing = test.lease(
        queued.job_id,
        "worker_beta",
        now=NOW + timedelta(minutes=1),
    )

    assert leased is not None
    assert leased.state == "running"
    assert leased.attempt_count == 1
    assert leased.lease_owner == "worker_alpha"
    assert leased.lease_expires_at == NOW + timedelta(minutes=2)
    assert competing is None


def test_a_restarted_worker_recovers_and_releases_an_expired_lease() -> None:
    test = harness()
    queued = test.enqueue()
    test.lease(queued.job_id, "worker_stopped")

    restarted = Harness(
        jobs=SqlReportJobRepository(test.factory),
        sessions=test.sessions,
        scope=test.scope,
        factory=test.factory,
    )
    recovered = restarted.jobs.recover_expired(now=NOW + timedelta(minutes=2))
    leased_again = restarted.lease(
        queued.job_id,
        "worker_restarted",
        now=NOW + timedelta(minutes=2),
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
    test = harness()
    queued = test.enqueue(max_attempts=2)
    first = test.lease(queued.job_id, "worker_alpha")
    assert first is not None

    retryable = test.jobs.fail(
        FailureRequest(
            lease=LeaseAction(
                job_id=first.job_id,
                worker_id="worker_alpha",
                now=NOW + timedelta(seconds=30),
            ),
            retry_at=NOW + timedelta(minutes=1),
        )
    )
    second = test.lease(
        queued.job_id,
        "worker_beta",
        now=NOW + timedelta(minutes=1),
    )
    assert second is not None
    exhausted = test.jobs.fail(
        FailureRequest(
            lease=LeaseAction(
                job_id=second.job_id,
                worker_id="worker_beta",
                now=NOW + timedelta(minutes=1, seconds=30),
            ),
            retry_at=NOW + timedelta(minutes=2),
        )
    )
    impossible_retry = test.lease(
        queued.job_id,
        "worker_gamma",
        now=NOW + timedelta(minutes=2),
    )

    assert retryable.state == "retryable"
    assert retryable.available_at == NOW + timedelta(minutes=1)
    assert retryable.dead_letter_reason is None
    assert exhausted.state == "dead_lettered"
    assert exhausted.dead_letter_reason == "retries_exhausted"
    assert exhausted.attempt_count == 2
    assert exhausted.completed_at == NOW + timedelta(minutes=1, seconds=30)
    assert impossible_retry is None


def test_only_the_current_lease_holder_can_complete_a_job() -> None:
    test = harness()
    queued = test.enqueue()
    leased = test.lease(queued.job_id, "worker_alpha")
    assert leased is not None

    with pytest.raises(LeaseLost):
        test.jobs.complete(
            LeaseAction(
                job_id=leased.job_id,
                worker_id="worker_stale",
                now=NOW + timedelta(minutes=1),
            )
        )
    completed = test.jobs.complete(
        LeaseAction(
            job_id=leased.job_id,
            worker_id="worker_alpha",
            now=NOW + timedelta(minutes=1),
        )
    )

    assert completed.state == "succeeded"
    assert completed.completed_at == NOW + timedelta(minutes=1)
    assert completed.lease_owner is None
    assert completed.lease_expires_at is None


def test_a_heartbeat_keeps_an_active_job_out_of_orphan_recovery() -> None:
    test = harness()
    queued = test.enqueue()
    leased = test.lease(queued.job_id, "worker_alpha")
    assert leased is not None

    extended = test.jobs.heartbeat(
        LeaseRequest(
            job_id=leased.job_id,
            worker_id="worker_alpha",
            now=NOW + timedelta(minutes=1),
            lease_for=timedelta(minutes=3),
        )
    )
    recovered = test.jobs.recover_expired(now=NOW + timedelta(minutes=2))

    assert extended.lease_expires_at == NOW + timedelta(minutes=4)
    assert recovered == ()


def test_a_job_cannot_start_after_session_deletion_is_requested() -> None:
    test = harness()
    queued = test.enqueue()
    beta_session = test.sessions.get_session(test.scope.session_id)
    assert beta_session is not None
    test.sessions.update_session(replace(beta_session, deletion_requested_at=NOW))

    assert test.lease(queued.job_id, "worker_alpha") is None


def test_attempt_evidence_carries_only_content_free_identifiers() -> None:
    names = {field.name for field in fields(JobAttempt)}

    assert names == {
        "job_id",
        "session_id",
        "attempt_number",
        "released_at",
        "disposition",
        "available_at",
    }


@pytest.mark.parametrize(
    ("attempt_number", "disposition", "available_at"),
    [
        (1, "retries_exhausted", NOW),
        (1, "retry_scheduled", None),
        (1, "abandoned", NOW),
        (0, "retry_scheduled", NOW),
    ],
)
def test_attempt_evidence_rejects_unbounded_or_incoherent_outcomes(
    attempt_number: int,
    disposition: str,
    available_at: datetime | None,
) -> None:
    with pytest.raises(ValueError):
        JobAttempt(
            job_id="job_alpha",
            session_id="ses_alpha",
            attempt_number=attempt_number,
            released_at=NOW,
            disposition=disposition,
            available_at=available_at,
        )


def test_exhausted_retries_retain_content_free_attempt_history() -> None:
    test = harness()
    queued = test.enqueue(max_attempts=2)
    first = test.lease(queued.job_id, "worker_alpha")
    assert first is not None
    test.fail(
        first,
        "worker_alpha",
        now=NOW + timedelta(seconds=30),
        retry_at=NOW + timedelta(minutes=1),
    )
    second = test.lease(
        queued.job_id,
        "worker_beta",
        now=NOW + timedelta(minutes=1),
    )
    assert second is not None
    test.fail(
        second,
        "worker_beta",
        now=NOW + timedelta(minutes=1, seconds=30),
        retry_at=NOW + timedelta(minutes=2),
    )

    history = test.attempts(queued.job_id)

    assert [item.attempt_number for item in history] == [1, 2]
    assert [item.disposition for item in history] == [
        "retry_scheduled",
        "retries_exhausted",
    ]
    assert [item.released_at for item in history] == [
        NOW + timedelta(seconds=30),
        NOW + timedelta(minutes=1, seconds=30),
    ]
    assert [item.available_at for item in history] == [
        NOW + timedelta(minutes=1),
        None,
    ]
    assert {item.job_id for item in history} == {queued.job_id}
    assert {item.session_id for item in history} == {test.scope.session_id}


def test_attempt_history_is_unavailable_outside_the_owning_session() -> None:
    test = harness()
    queued = test.enqueue()

    with pytest.raises(CrossSessionAccessDenied):
        test.jobs.list_attempts(
            scope=SessionScope(owner_id="own_intruder", session_id="ses_intruder"),
            job_id=queued.job_id,
        )


def test_a_reclaimed_lease_records_a_bounded_retry_in_the_history() -> None:
    test = harness()
    queued = test.enqueue()
    test.lease(queued.job_id, "worker_stopped")

    test.jobs.recover_expired(now=NOW + timedelta(minutes=2))
    history = test.attempts(queued.job_id)

    assert len(history) == 1
    assert history[0].attempt_number == 1
    assert history[0].disposition == "lease_reclaimed"
    assert history[0].released_at == NOW + timedelta(minutes=2)
    assert history[0].available_at == NOW + timedelta(minutes=2)


def test_an_expired_lease_at_the_attempt_limit_is_dead_lettered() -> None:
    test = harness()
    queued = test.enqueue(max_attempts=1)
    test.lease(queued.job_id, "worker_stopped")

    recovered = test.jobs.recover_expired(now=NOW + timedelta(minutes=2))
    history = test.attempts(queued.job_id)

    assert len(recovered) == 1
    assert recovered[0].state == "dead_lettered"
    assert recovered[0].dead_letter_reason == "retries_exhausted"
    assert recovered[0].completed_at == NOW + timedelta(minutes=2)
    assert recovered[0].lease_owner is None
    assert recovered[0].lease_expires_at is None
    assert [item.disposition for item in history] == ["retries_exhausted"]


def test_deleted_session_content_orphans_its_unfinished_job() -> None:
    test = harness()
    queued = test.enqueue()
    test.delete_content(at=NOW + timedelta(minutes=1))

    orphaned = test.jobs.recover_orphans(now=NOW + timedelta(minutes=2))
    impossible_lease = test.lease(
        queued.job_id,
        "worker_alpha",
        now=NOW + timedelta(minutes=3),
    )

    assert len(orphaned) == 1
    assert orphaned[0].job_id == queued.job_id
    assert orphaned[0].state == "dead_lettered"
    assert orphaned[0].dead_letter_reason == "content_deleted"
    assert orphaned[0].completed_at == NOW + timedelta(minutes=2)
    assert orphaned[0].lease_owner is None
    assert orphaned[0].lease_expires_at is None
    assert impossible_lease is None


def test_intact_session_content_leaves_unfinished_jobs_alone() -> None:
    test = harness()
    test.enqueue()

    assert test.jobs.recover_orphans(now=NOW + timedelta(minutes=2)) == ()


def test_orphan_recovery_never_reclaims_a_live_lease() -> None:
    test = harness()
    queued = test.enqueue()
    leased = test.lease(queued.job_id, "worker_alpha")
    test.delete_content(at=NOW + timedelta(seconds=30))

    orphaned = test.jobs.recover_orphans(now=NOW + timedelta(minutes=1))

    assert leased is not None
    assert orphaned == ()


def test_a_reclaimed_orphan_is_dead_lettered_on_the_next_sweep() -> None:
    test = harness()
    queued = test.enqueue()
    test.lease(queued.job_id, "worker_stopped")
    test.delete_content(at=NOW + timedelta(seconds=30))

    reclaimed = test.jobs.recover_expired(now=NOW + timedelta(minutes=2))
    orphaned = test.jobs.recover_orphans(now=NOW + timedelta(minutes=3))

    assert [item.state for item in reclaimed] == ["retryable"]
    assert [item.state for item in orphaned] == ["dead_lettered"]
    assert orphaned[0].dead_letter_reason == "content_deleted"


def test_settled_jobs_are_never_orphaned() -> None:
    test = harness()
    queued = test.enqueue()
    leased = test.lease(queued.job_id, "worker_alpha")
    assert leased is not None
    test.jobs.complete(
        LeaseAction(
            job_id=leased.job_id,
            worker_id="worker_alpha",
            now=NOW + timedelta(minutes=1),
        )
    )
    test.delete_content(at=NOW + timedelta(minutes=2))

    assert test.jobs.recover_orphans(now=NOW + timedelta(minutes=3)) == ()


@pytest.mark.parametrize("state", ["queued", "retryable"])
def test_unleased_non_terminal_jobs_are_orphanable(state: str) -> None:
    assert orphanable(state) is True


@pytest.mark.parametrize("state", ["running", "succeeded", "dead_lettered"])
def test_leased_or_settled_jobs_are_not_orphanable(state: str) -> None:
    assert orphanable(state) is False


@pytest.mark.parametrize("state", ["failed", "bogus", "", "QUEUED"])
def test_an_unknown_job_state_is_never_treated_as_recoverable(state: str) -> None:
    with pytest.raises(UnknownJobState):
        orphanable(state)
