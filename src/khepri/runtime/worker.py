"""One-at-a-time claim driver for the approved bounded report worker role.

`KHEPRI-DEC-008` replaced the message broker with PostgreSQL claim-and-redrive, so
this loop claims a job rather than receiving a message. The shape is unchanged: claim
one delivery, process it, settle it, repeat. What changed is that there is one clock
instead of two -- the lease is the only thing making a job invisible to another
worker, where before a visibility timeout and a database lease had to agree.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Protocol

from khepri.rra.claim_queue import ClaimedDelivery, ClaimingReportQueue, ClaimPolicy
from khepri.rra.jobs import JOB_SUCCEEDED, LeaseLost, ReportJob
from khepri.rra.rendering.chromium import launch_chromium
from khepri.rra.report_services import JobReader
from khepri.rra.worker import (
    ReportExecutionFailed,
    ReportJobMessage,
    ReportWorker,
    WorkerPolicy,
)
from khepri.runtime.config import RuntimeSettings
from khepri.runtime.wiring import RuntimeStack, build_pipeline, build_stack

LEASE_FOR = timedelta(seconds=300)
RETRY_DELAY = timedelta(seconds=60)
WORKBOOK_DIRECTORY = Path("/tmp/khepri-workbooks")


class QueuePort(Protocol):
    def receive(self, *, now: datetime) -> ClaimedDelivery | None: ...

    def recover(self, *, now: datetime) -> tuple[ReportJob, ...]: ...

    def heartbeat(self, delivery: ClaimedDelivery, *, now: datetime) -> ReportJob: ...

    def acknowledge(self, delivery: ClaimedDelivery, *, now: datetime) -> ReportJob: ...


class WorkerPort(Protocol):
    def process(
        self,
        message: ReportJobMessage,
        *,
        heartbeat: Callable[[], None],
    ) -> ReportJob | None: ...


class JobReaderPort(Protocol):
    def find(self, job_id: str) -> ReportJob | None: ...


class ClaimWorkerLoop:
    """Claim and settle one job at a time."""

    def __init__(
        self,
        *,
        queue: QueuePort,
        worker: WorkerPort,
        jobs: JobReaderPort,
        clock: Callable[[], datetime],
    ) -> None:
        self._queue = queue
        self._worker = worker
        self._jobs = jobs
        self._clock = clock

    def run_once(self) -> bool:
        """Recover expired leases, then claim and settle one job.

        `KHEPRI-DEC-008` replaced the broker with "a claim query and a redrive
        sweep", and the sweep had no caller on the deployed path: the only one was
        `khepri.local.sweeper`, which `pyproject.toml` excludes from the wheel. A
        lease whose holder died was therefore never reclaimed in the image that
        actually runs, and the job stayed `running` until a human intervened.

        **The sweep runs before every claim, not only when the queue is idle.**
        Gating it behind `delivery is None` starves recovery under exactly the
        conditions that produce abandoned leases: a busy queue always has something
        claimable, so the idle branch never runs, so a worker that died mid-job
        holds its lease until traffic stops. Recovery must not depend on the
        absence of work.

        One clock reading serves both calls, so a job cannot be judged expired by
        the sweep and unexpired by the claim within one iteration. `recover` is
        idempotent and bounded by `lease_expires_at <= now`, and reclaiming cannot
        touch this worker's own job because it holds no lease at this point -- the
        previous iteration settled or released it before returning.
        """
        now = self._clock()
        self._queue.recover(now=now)
        delivery = self._queue.receive(now=now)
        if delivery is None:
            return False
        try:
            completed = self._worker.process(
                delivery.message,
                heartbeat=lambda: self._queue.heartbeat(delivery, now=self._clock()),
            )
        except (LeaseLost, ReportExecutionFailed):
            return True
        if completed is not None or self._already_succeeded(delivery.message.job_id):
            self._settle(delivery)
        return True

    def run_forever(self) -> None:
        while True:
            self.run_once()

    def _settle(self, delivery: ClaimedDelivery) -> None:
        """Complete the job unless the worker already did.

        `ReportWorker.process` completes through the same repository, so a job it
        finished is already `succeeded` and acknowledging again would find no active
        lease. Acknowledging only an unsettled delivery keeps this idempotent.
        """
        found = self._jobs.find(delivery.message.job_id)
        if found is not None and found.state == JOB_SUCCEEDED:
            return
        self._queue.acknowledge(delivery, now=self._clock())

    def _already_succeeded(self, job_id: str) -> bool:
        found = self._jobs.find(job_id)
        return found is not None and found.state == JOB_SUCCEEDED


def build_worker_loop(
    stack: RuntimeStack,
    *,
    printer: object,
    workbooks: Path = WORKBOOK_DIRECTORY,
    worker_id: str | None = None,
) -> ClaimWorkerLoop:
    identity = worker_id or f"worker-{socket.gethostname()}"
    queue = ClaimingReportQueue(
        jobs=stack.reports.jobs,
        factory=stack.factory,
        policy=ClaimPolicy(worker_id=identity, lease_for=LEASE_FOR),
    )
    worker = ReportWorker(
        jobs=stack.reports.jobs,
        handler=build_pipeline(stack, workbooks=workbooks, printer=printer),
        clock=stack.clock,
        policy=WorkerPolicy(
            worker_id=identity,
            lease_for=LEASE_FOR,
            retry_delay=RETRY_DELAY,
        ),
    )
    return ClaimWorkerLoop(
        queue=queue,
        worker=worker,
        jobs=JobReader(stack.factory),
        clock=stack.clock,
    )


def main() -> None:
    stack = build_stack(RuntimeSettings.from_environment())
    with launch_chromium() as printer:
        build_worker_loop(stack, printer=printer).run_forever()


if __name__ == "__main__":
    main()
