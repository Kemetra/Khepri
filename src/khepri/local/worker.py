"""Drive `ReportWorker` from PostgreSQL, with no queue in front of it.

**Why there is no local SQS.** `KHEPRI-DEC-007` makes PostgreSQL the owner of
idempotency and leases, and SQS the delivery mechanism only: the visibility timeout
and the database lease are deliberately the same 300 seconds so that neither is
load-bearing alone. A local substitute for the queue would therefore be faking the
part that carries no authority while the real authority sits in the database
already. So this polls the job store for a claimable job and synthesizes the
`ReportJobMessage` that `ReportWorker.process` takes.

That is a genuine difference from the deployed design, and it is stated rather than
hidden: locally there is no dead-letter queue and no `maxReceiveCount`. The
database's own `max_attempts` still bounds retries and still records
`DEAD_LETTER_RETRIES_EXHAUSTED`, because that half lives in `job_persistence`.

**One job at a time.** `KHEPRI-DEC-007` sets in-task concurrency to exactly 1, and
this holds to it — not because a local loop needs the guarantee, but because a
local run that behaved differently from the deployed one would teach the wrong
thing about how the pipeline behaves under load.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.job_persistence import ReportJobRow, SqlReportJobRepository
from khepri.rra.jobs import JOB_QUEUED, JOB_RETRYABLE
from khepri.rra.worker import ReportJobMessage, ReportWorker

# Matches `KHEPRI-DEC-007`: lease 300s, retry delay 60s.
LEASE_FOR = timedelta(seconds=300)
RETRY_DELAY = timedelta(seconds=60)


@dataclass(frozen=True, slots=True)
class ClaimablePoller:
    """Find one job that is due, without transitioning it.

    Claiming is `lease`'s job and stays there: this only answers "is there
    anything to try", so two pollers racing is resolved by the lease rather than
    by whoever read first.
    """

    factory: sessionmaker[Session]

    def next_job_id(self, *, now: datetime) -> str | None:
        with self.factory() as database:
            return database.execute(
                select(ReportJobRow.job_id)
                .where(
                    ReportJobRow.state.in_((JOB_QUEUED, JOB_RETRYABLE)),
                    ReportJobRow.available_at <= now,
                )
                .order_by(ReportJobRow.available_at)
                .limit(1)
            ).scalar_one_or_none()


class LocalReportWorker:
    """Poll for one due job, lease it, run the pipeline, repeat."""

    def __init__(
        self,
        *,
        worker: ReportWorker,
        poller: ClaimablePoller,
        clock: Callable[[], datetime],
    ) -> None:
        self._worker = worker
        self._poller = poller
        self._clock = clock

    def run_once(self) -> str | None:
        """Process at most one job. Returns its identifier, or `None` if idle.

        A failed execution is not re-raised: `ReportWorker` has already recorded
        the attempt and scheduled the retry, and a loop that died on the first
        refused narrative would stop draining every other job behind it.
        """
        job_id = self._poller.next_job_id(now=self._clock())
        if job_id is None:
            return None
        try:
            self._worker.process(ReportJobMessage(job_id=job_id))
        except Exception:  # noqa: BLE001 - recorded by the worker, drained here
            return job_id
        return job_id

    def drain(self, *, limit: int = 100) -> int:
        """Process due jobs until none remain, bounded so a loop cannot run away."""
        processed = 0
        while processed < limit and self.run_once() is not None:
            processed += 1
        return processed


@dataclass(frozen=True, slots=True)
class LocalWorkerPorts:
    """The persistent collaborators behind one local worker."""

    jobs: SqlReportJobRepository
    factory: sessionmaker[Session]
    handler: Callable[..., None]


def build_local_worker(
    ports: LocalWorkerPorts,
    *,
    clock: Callable[[], datetime],
    worker_id: str = "local-worker",
) -> LocalReportWorker:
    """Assemble the worker, its policy, and the poller in front of it."""
    from khepri.rra.worker import WorkerPolicy

    return LocalReportWorker(
        worker=ReportWorker(
            jobs=ports.jobs,
            handler=ports.handler,
            clock=clock,
            policy=WorkerPolicy(
                worker_id=worker_id,
                lease_for=LEASE_FOR,
                retry_delay=RETRY_DELAY,
            ),
        ),
        poller=ClaimablePoller(factory=ports.factory),
        clock=clock,
    )


__all__ = [
    "LEASE_FOR",
    "RETRY_DELAY",
    "ClaimablePoller",
    "LocalReportWorker",
    "LocalWorkerPorts",
    "build_local_worker",
]
