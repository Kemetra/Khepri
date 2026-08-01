"""One-at-a-time SQS driver for the approved bounded report worker role."""

from __future__ import annotations

import socket
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Protocol

from khepri.rra.jobs import JOB_SUCCEEDED, LeaseLost, ReportJob
from khepri.rra.rendering.chromium import launch_chromium
from khepri.rra.report_services import JobReader
from khepri.rra.sqs_queue import QueueDelivery, SqsReportQueue
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
    def receive(self) -> QueueDelivery | None: ...

    def heartbeat(self, delivery: QueueDelivery) -> None: ...

    def acknowledge(self, delivery: QueueDelivery) -> None: ...


class WorkerPort(Protocol):
    def process(
        self,
        message: ReportJobMessage,
        *,
        heartbeat: Callable[[], None],
    ) -> ReportJob | None: ...


class JobReaderPort(Protocol):
    def find(self, job_id: str) -> ReportJob | None: ...


class SqsWorkerLoop:
    """Long-poll and settle one source delivery at a time."""

    def __init__(self, *, queue: QueuePort, worker: WorkerPort, jobs: JobReaderPort) -> None:
        self._queue = queue
        self._worker = worker
        self._jobs = jobs

    def run_once(self) -> bool:
        delivery = self._queue.receive()
        if delivery is None:
            return False
        try:
            completed = self._worker.process(
                delivery.message,
                heartbeat=lambda: self._queue.heartbeat(delivery),
            )
        except (LeaseLost, ReportExecutionFailed):
            return True
        if completed is not None or self._already_succeeded(delivery.message.job_id):
            self._queue.acknowledge(delivery)
        return True

    def run_forever(self) -> None:
        while True:
            self.run_once()

    def _already_succeeded(self, job_id: str) -> bool:
        found = self._jobs.find(job_id)
        return found is not None and found.state == JOB_SUCCEEDED


def build_worker_loop(
    stack: RuntimeStack,
    *,
    printer: object,
    workbooks: Path = WORKBOOK_DIRECTORY,
    worker_id: str | None = None,
) -> SqsWorkerLoop:
    queue = SqsReportQueue(
        client=stack.clients.sqs,
        queue_url=stack.settings.queue_url,
        dead_letter_queue_url=stack.settings.dead_letter_queue_url,
        visibility_timeout_seconds=int(LEASE_FOR.total_seconds()),
    )
    worker = ReportWorker(
        jobs=stack.reports.jobs,
        handler=build_pipeline(stack, workbooks=workbooks, printer=printer),
        clock=stack.clock,
        policy=WorkerPolicy(
            worker_id=worker_id or f"worker-{socket.gethostname()}",
            lease_for=LEASE_FOR,
            retry_delay=RETRY_DELAY,
        ),
    )
    return SqsWorkerLoop(queue=queue, worker=worker, jobs=JobReader(stack.factory))


def main() -> None:
    stack = build_stack(RuntimeSettings.from_environment())
    with launch_chromium() as printer:
        build_worker_loop(stack, printer=printer).run_forever()


if __name__ == "__main__":
    main()
