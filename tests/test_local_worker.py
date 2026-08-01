"""The local worker drains from the database rather than from a queue.

No stack is needed here: the poller and the worker are exercised against fakes,
because what these tests are about is the loop's decisions — what it claims, what
it does when a job fails, and where it stops — not PostgreSQL's behaviour, which
`test_rra007_job_persistence` already covers.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from khepri.local.worker import LEASE_FOR, RETRY_DELAY, LocalReportWorker
from khepri.rra.worker import ReportJobMessage

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


class FakePoller:
    """Hands out the queued identifiers in order, then reports an empty queue."""

    def __init__(self, job_ids: list[str]) -> None:
        self.job_ids = list(job_ids)
        self.calls = 0

    def next_job_id(self, *, now: datetime) -> str | None:
        self.calls += 1
        return self.job_ids.pop(0) if self.job_ids else None


class RecordingWorker:
    def __init__(self, *, failing: set[str] | None = None) -> None:
        self.processed: list[str] = []
        self.failing = failing or set()

    def process(self, message: ReportJobMessage) -> None:
        self.processed.append(message.job_id)
        if message.job_id in self.failing:
            raise RuntimeError("execution failed")


def worker(poller: FakePoller, inner: RecordingWorker) -> LocalReportWorker:
    return LocalReportWorker(worker=inner, poller=poller, clock=lambda: NOW)


class TestRunOnce:
    def test_an_empty_queue_processes_nothing(self) -> None:
        inner = RecordingWorker()

        assert worker(FakePoller([]), inner).run_once() is None
        assert inner.processed == []

    def test_one_due_job_is_processed(self) -> None:
        inner = RecordingWorker()

        assert worker(FakePoller(["job_a"]), inner).run_once() == "job_a"
        assert inner.processed == ["job_a"]

    def test_a_failed_execution_does_not_escape(self) -> None:
        """The worker already recorded the attempt; a raise here stops the drain."""
        inner = RecordingWorker(failing={"job_a"})

        assert worker(FakePoller(["job_a"]), inner).run_once() == "job_a"


class TestDrain:
    def test_every_due_job_is_processed(self) -> None:
        inner = RecordingWorker()

        processed = worker(FakePoller(["a", "b", "c"]), inner).drain()

        assert processed == 3
        assert inner.processed == ["a", "b", "c"]

    def test_draining_stops_at_the_limit(self) -> None:
        """A bound, so a queue that refills faster than it drains cannot spin."""
        inner = RecordingWorker()

        processed = worker(FakePoller(["a", "b", "c", "d"]), inner).drain(limit=2)

        assert processed == 2
        assert inner.processed == ["a", "b"]

    def test_a_failing_job_does_not_stop_the_others(self) -> None:
        inner = RecordingWorker(failing={"b"})

        processed = worker(FakePoller(["a", "b", "c"]), inner).drain()

        assert processed == 3
        assert inner.processed == ["a", "b", "c"]

    def test_an_empty_queue_drains_nothing(self) -> None:
        assert worker(FakePoller([]), RecordingWorker()).drain() == 0


class TestThePolicyMatchesTheApprovedSizing:
    """`KHEPRI-DEC-007` fixes both; drifting locally would teach the wrong thing."""

    def test_the_lease_is_five_minutes(self) -> None:
        assert LEASE_FOR.total_seconds() == 300

    def test_the_retry_delay_is_one_minute(self) -> None:
        assert RETRY_DELAY.total_seconds() == 60

    @pytest.mark.parametrize("value", [LEASE_FOR, RETRY_DELAY])
    def test_both_are_positive(self, value: object) -> None:
        assert value.total_seconds() > 0  # type: ignore[attr-defined]
