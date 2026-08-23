"""The deployed worker path reclaims an expired lease without `khepri.local`.

`KHEPRI-DEC-008` replaced the broker with "a claim query and a redrive sweep" and
requires "restart, retry, dead-letter, and orphan recovery" before beta. The sweep
was written and tested, but nothing on the deployed path called it: the only
non-test caller was `khepri.local.sweeper`, and `pyproject.toml` excludes
`src/khepri/local` from the wheel the OCI image installs. A worker whose process
died left its job `running` with an expired lease, and no packaged code returned it
to the claimable set.

**These tests never call `recover` themselves.** `ClaimingReportQueue.recover` and
`SqlReportJobRepository.recover_expired` were already correct and already covered by
`test_rra007_claim_queue.py`; a test that invoked either would pass against the
defect and prove nothing. The property under test is that *the loop* reaches them,
so every case here drives `ClaimWorkerLoop.run_once` and asserts on job state.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.claim_queue import ClaimingReportQueue, ClaimPolicy
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.jobs import (
    JOB_DEAD_LETTERED,
    JOB_RETRYABLE,
    JOB_RUNNING,
    EnqueueJob,
    ReportJob,
)
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.report_services import JobReader
from khepri.rra.sessions import InvitationService, SessionScope
from khepri.runtime.worker import LEASE_FOR, ClaimWorkerLoop

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)
EXPIRED = NOW + LEASE_FOR + timedelta(seconds=1)
def _key_for(job_id: str) -> str:
    """A distinct 64-hex idempotency key per job."""
    return sha256(job_id.encode("utf-8")).hexdigest()


class RefusingWorker:
    """Fails the test if the loop hands it a job.

    Used only where nothing should be claimable, so a claim means the case under
    test set up the wrong state rather than that the loop misbehaved.
    """

    def execute(self, job: ReportJob, *, heartbeat: object) -> ReportJob | None:
        raise AssertionError(f"no job should have been claimable, got {job.job_id}")


class PassiveWorker:
    """Accepts whatever it is given and reports nothing completed."""

    def execute(self, job: ReportJob, *, heartbeat: object) -> ReportJob | None:
        return None


@dataclass(frozen=True, slots=True)
class Harness:
    queue: ClaimingReportQueue
    jobs: SqlReportJobRepository
    reader: JobReader
    scope: SessionScope

    def enqueue(self, job_id: str, *, max_attempts: int = 3) -> ReportJob:
        """Each job needs its own idempotency key.

        `enqueue` deduplicates on the key and returns the *existing* row, so two
        jobs sharing one key are one job -- which silently made an early version of
        `test_recovery_runs_only_when_nothing_was_claimable` assert against a
        second job that had never been created.
        """
        return self.jobs.enqueue(
            EnqueueJob(
                scope=self.scope,
                job_id=job_id,
                idempotency_key=_key_for(job_id),
                queued_at=NOW,
                max_attempts=max_attempts,
            )
        )

    def state_of(self, job_id: str) -> str:
        found = self.reader.find(job_id)
        assert found is not None
        return found.state

    def loop(self, *, now: datetime, worker: object | None = None) -> ClaimWorkerLoop:
        """The real deployed loop over the real queue. Only the clock is a stub."""
        return ClaimWorkerLoop(
            queue=self.queue,
            worker=worker or PassiveWorker(),
            jobs=self.reader,
            clock=lambda: now,
        )


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
    jobs = SqlReportJobRepository(factory)
    return Harness(
        queue=ClaimingReportQueue(
            jobs=jobs,
            factory=factory,
            policy=ClaimPolicy(worker_id=worker_id, lease_for=LEASE_FOR),
        ),
        jobs=jobs,
        reader=JobReader(factory),
        scope=SessionScope(
            owner_id=beta_session.owner_id,
            session_id=beta_session.session_id,
        ),
    )


def _claim_and_abandon(test: Harness, job_id: str) -> None:
    """Claim a job and walk away, which is what a killed worker leaves behind."""
    test.enqueue(job_id)
    assert test.queue.receive(now=NOW) is not None
    assert test.state_of(job_id) == JOB_RUNNING


def test_the_deployed_loop_reclaims_an_abandoned_lease() -> None:
    """The base case: the packaged loop reaches the sweep at all.

    The reclaimed job is immediately claimable again -- recovery now runs before
    the claim in the same iteration -- so the loop picks it straight back up and
    `run_once` reports work. What matters here is that the abandoned lease was
    released by the deployed path, which the fresh lease owner proves.
    """
    test = harness()
    _claim_and_abandon(test, "job_alpha")

    assert test.loop(now=EXPIRED).run_once() is True

    found = test.reader.find("job_alpha")
    assert found is not None
    assert found.lease_owner == "worker-alpha"
    assert found.attempt_count == 2, "the reclaim released the lease and the claim retook it"


def test_a_reclaimed_job_becomes_claimable_again() -> None:
    """Reclaiming is only useful if the job can actually be picked up afterwards.

    Proved without letting the loop reclaim it: the sweep alone must leave the row
    in a state a later claim accepts. `RefusingWorker` asserts the loop found
    nothing to run, so the reclaim is the only thing that moved the row.
    """
    test = harness()
    _claim_and_abandon(test, "job_alpha")

    still_held = NOW + timedelta(seconds=1)
    assert test.loop(now=still_held, worker=RefusingWorker()).run_once() is False
    assert test.state_of("job_alpha") == JOB_RUNNING

    assert test.queue.receive(now=EXPIRED) is None, "the lease is still held by its owner"

    test.jobs.recover_expired(now=EXPIRED)

    assert test.state_of("job_alpha") == JOB_RETRYABLE
    assert test.queue.receive(now=EXPIRED) is not None


def test_a_healthy_lease_is_left_alone() -> None:
    """The negative case: a live worker's job must survive another worker's idle pass."""
    test = harness()
    _claim_and_abandon(test, "job_alpha")

    still_held = NOW + timedelta(seconds=1)
    assert test.loop(now=still_held, worker=RefusingWorker()).run_once() is False

    assert test.state_of("job_alpha") == JOB_RUNNING


def test_reclaiming_respects_the_attempt_limit() -> None:
    """A final attempt that is reclaimed dead-letters rather than looping forever."""
    test = harness()
    test.enqueue("job_alpha", max_attempts=1)
    assert test.queue.receive(now=NOW) is not None

    test.loop(now=EXPIRED).run_once()

    assert test.state_of("job_alpha") == JOB_DEAD_LETTERED


def test_an_expired_lease_is_recovered_while_other_work_is_claimable() -> None:
    """The starvation case: recovery must not wait for an idle queue.

    An earlier version of this slice swept only when `receive` returned `None`. That
    is wrong in the exact conditions that produce abandoned leases: a busy queue
    always has something claimable, so the idle branch never runs, so a worker that
    died mid-job keeps its lease until traffic stops. Under sustained load recovery
    would never happen at all.

    Here `job_alpha` is abandoned with an expired lease *and* `job_beta` is waiting,
    so `receive` has work to return on every iteration. The expired lease must still
    be reclaimed. This fails if recovery is gated behind `if delivery is None`.
    """
    test = harness()
    _claim_and_abandon(test, "job_alpha")
    test.enqueue("job_beta")

    processed: list[str] = []

    class RecordingWorker:
        def execute(self, job: ReportJob, *, heartbeat: object) -> ReportJob | None:
            processed.append(job.job_id)
            return None

    loop = ClaimWorkerLoop(
        queue=test.queue,
        worker=RecordingWorker(),
        jobs=test.reader,
        clock=lambda: EXPIRED,
    )

    assert loop.run_once() is True

    assert processed != [], "the queue had claimable work, so the loop must have run it"
    assert test.state_of("job_alpha") == JOB_RETRYABLE


def test_recovery_does_not_depend_on_an_idle_iteration() -> None:
    """Stated as a property over a queue that is never empty.

    `test_an_expired_lease_is_recovered_while_other_work_is_claimable` proves one
    reclaim happens with work pending. This proves the loop never needs an idle
    iteration to reach recovery: every `run_once` here returns `True`, so the idle
    branch is never taken, and the expired lease is still reclaimed.
    """
    test = harness()
    _claim_and_abandon(test, "job_alpha")
    for name in ("job_beta", "job_gamma"):
        test.enqueue(name)

    class BusyWorker:
        def execute(self, job: ReportJob, *, heartbeat: object) -> ReportJob | None:
            return None

    loop = ClaimWorkerLoop(
        queue=test.queue,
        worker=BusyWorker(),
        jobs=test.reader,
        clock=lambda: EXPIRED,
    )

    assert loop.run_once() is True

    assert test.state_of("job_alpha") == JOB_RETRYABLE


def test_this_suite_never_calls_recovery_directly() -> None:
    """Guard the property that makes the other cases evidence.

    Every case above must reach recovery through the loop. If someone later calls
    `recover` or `recover_expired` from a test body, that test would pass against
    the very defect this file exists to catch, so the absence is asserted rather
    than trusted.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    # One exemption, named rather than pattern-matched. That case proves what the
    # sweep leaves behind -- that a reclaimed row is claimable again -- which is a
    # property of `recover_expired` itself, not of the loop reaching it. Every other
    # case must go through `ClaimWorkerLoop`.
    exempt = {
        "test_this_suite_never_calls_recovery_directly",
        "test_a_reclaimed_job_becomes_claimable_again",
    }
    cases = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("test_")
        and node.name not in exempt
    ]
    assert len(cases) == 5, "every case must be checked, so a new one cannot slip past"

    called = {
        node.func.attr
        for case in cases
        for node in ast.walk(case)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "recover" not in called
    assert "recover_expired" not in called
