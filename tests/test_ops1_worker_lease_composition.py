"""The deployed loop must render a report, not lease the same job twice.

`ClaimingReportQueue.receive` claims by calling `SqlReportJobRepository.lease`,
which transitions the row to `running`. `ReportWorker.process` then called `lease`
again on that same row, and `lease` admits only `queued`/`retryable`, so the second
call returned `None`: the handler never ran, the loop never settled, and the job sat
`running` until the redrive sweep reclaimed it -- burning one attempt per cycle until
`max_attempts` dead-lettered it. No report rendered on the deployed path.

Every existing loop test stubs both `QueuePort` and `WorkerPort`, so the defect lives
exactly where nothing looked: in the composition of the two real objects. These cases
build the real pair the way `build_worker_loop` does and assert the effect -- the
handler ran, the job succeeded -- rather than the absence of an exception.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.claim_queue import ClaimingReportQueue, ClaimPolicy
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.jobs import JOB_SUCCEEDED, EnqueueJob, ReportJob
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.report_services import JobReader
from khepri.rra.sessions import InvitationService, SessionScope
from khepri.rra.worker import ReportWorker, WorkerExecution, WorkerPolicy
from khepri.runtime.worker import (
    LEASE_FOR,
    RETRY_DELAY,
    ClaimWorkerLoop,
    build_worker_loop,
)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)
IDEMPOTENCY_KEY = "8f99c79c1c79c892c1a30a74fcc1b536b04e409ee4562acfb82d8d76fb750d7d"
WORKER_ID = "worker-deployed"


class Handler:
    def __init__(self) -> None:
        self.jobs: list[ReportJob] = []

    def __call__(self, execution: WorkerExecution) -> None:
        self.jobs.append(execution.job)


class HeartbeatHandler(Handler):
    def __call__(self, execution: WorkerExecution) -> None:
        self.jobs.append(execution.job)
        execution.heartbeat()


class Harness:
    """The real queue and the real worker, composed as `build_worker_loop` does."""

    def __init__(self, handler: Handler, *, max_attempts: int = 3) -> None:
        engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.factory = sessionmaker(engine, expire_on_commit=False)
        invitations = InvitationService(SqlSessionStore(self.factory))
        beta_session = invitations.redeem(
            invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)),
            now=NOW,
        )
        self.scope = SessionScope(
            owner_id=beta_session.owner_id,
            session_id=beta_session.session_id,
        )
        self.jobs = SqlReportJobRepository(self.factory)
        self.queued = self.jobs.enqueue(
            EnqueueJob(
                scope=self.scope,
                job_id="job_alpha",
                idempotency_key=IDEMPOTENCY_KEY,
                queued_at=NOW,
                max_attempts=max_attempts,
            )
        )
        self.handler = handler
        self.loop = ClaimWorkerLoop(
            queue=ClaimingReportQueue(
                jobs=self.jobs,
                factory=self.factory,
                policy=ClaimPolicy(worker_id=WORKER_ID, lease_for=LEASE_FOR),
            ),
            worker=ReportWorker(
                jobs=self.jobs,
                handler=handler,
                clock=lambda: NOW,
                policy=WorkerPolicy(
                    worker_id=WORKER_ID,
                    lease_for=LEASE_FOR,
                    retry_delay=RETRY_DELAY,
                ),
            ),
            jobs=JobReader(self.factory),
            clock=lambda: NOW,
        )

    def state(self) -> str:
        found = JobReader(self.factory).find(self.queued.job_id)
        assert found is not None
        return found.state

    def attempts(self) -> int:
        found = JobReader(self.factory).find(self.queued.job_id)
        assert found is not None
        return found.attempt_count


def test_the_claimed_job_reaches_the_handler() -> None:
    """The defect: the handler never ran, because the second lease refused."""
    test = Harness(Handler())

    assert test.loop.run_once() is True
    assert [job.job_id for job in test.handler.jobs] == [test.queued.job_id]


def test_the_claimed_job_succeeds() -> None:
    """The consequence: a claimed job must settle, not linger `running`."""
    test = Harness(Handler())

    test.loop.run_once()

    assert test.state() == JOB_SUCCEEDED


def test_one_pass_costs_exactly_one_attempt() -> None:
    """Two leases would bill the job twice and exhaust `max_attempts` early."""
    test = Harness(Handler())

    test.loop.run_once()

    assert test.attempts() == 1


def test_heartbeating_through_the_loop_keeps_the_lease() -> None:
    """Both heartbeat paths write the same row; neither may reject the other."""
    test = Harness(HeartbeatHandler())

    assert test.loop.run_once() is True
    assert test.state() == JOB_SUCCEEDED


def _worker_id_arguments(call: ast.Call) -> list[str]:
    return [
        ast.unparse(keyword.value)
        for keyword in call.keywords
        if keyword.arg == "worker_id"
    ]


def test_the_built_loop_names_one_worker_identity_for_both_policies() -> None:
    """Drifting the two identities silently re-creates the defect this slice fixed.

    The queue claims as its `ClaimPolicy.worker_id`; the executor settles as its
    `WorkerPolicy.worker_id`. `_active_lease` matches `lease_owner` against the
    caller's name, so two different names make `complete` raise `LeaseLost`, which
    `run_once` swallows -- the job sits `running` until the sweep, exactly the
    symptom just removed. Before this slice the mismatch was masked, because the
    second lease refused whichever names were used. It is load-bearing now.

    Asserted structurally, over the source of `build_worker_loop`, because the
    property is about how the two policies are constructed and holds for every
    `worker_id` rather than for one value a fixture happens to pass.
    """
    source = ast.parse(inspect.getsource(build_worker_loop))
    policies = [
        node
        for node in ast.walk(source)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"ClaimPolicy", "WorkerPolicy"}
    ]
    named = {node.func.id: _worker_id_arguments(node) for node in policies}  # type: ignore[union-attr]

    assert set(named) == {"ClaimPolicy", "WorkerPolicy"}, (
        "both policies must be built here, or this guard stopped watching them"
    )
    assert named["ClaimPolicy"] == named["WorkerPolicy"] != [], (
        f"the two policies must claim and settle under one identity, got {named}"
    )
