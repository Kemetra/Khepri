"""The sweeper recovers stalled work and deletes what has outlived its session.

Fakes again: `recover_expired`, `recover_orphans` and `delete_session_content` are
already covered where they are implemented. What is verified here is that one pass
calls all three, counts what it did, and treats a deferred deletion as deferred
rather than retrying it inside the same pass.
"""

from __future__ import annotations

from datetime import UTC, datetime

from khepri.local.sweeper import REASON_EXPIRED, LocalSweeper
from khepri.rra.deletion import DeletionRetryRequired

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


class FakeJobs:
    def __init__(self, *, expired: int = 0, orphaned: int = 0) -> None:
        self._expired = expired
        self._orphaned = orphaned
        self.calls: list[str] = []

    def recover_expired(self, *, now: datetime) -> tuple[object, ...]:
        self.calls.append("recover_expired")
        return tuple(object() for _ in range(self._expired))

    def recover_orphans(self, *, now: datetime) -> tuple[object, ...]:
        self.calls.append("recover_orphans")
        return tuple(object() for _ in range(self._orphaned))


class FakeDeletion:
    def __init__(self, *, defer: set[str] | None = None) -> None:
        self.deleted: list[tuple[str, str]] = []
        self.defer = defer or set()

    def delete_session_content(self, *, session_id: str, reason: str, now: datetime) -> None:
        if session_id in self.defer:
            raise DeletionRetryRequired("try again later")
        self.deleted.append((session_id, reason))


class StubSweeper(LocalSweeper):
    """Overrides only the database read, so the pass logic is the real one."""

    def __init__(self, *, jobs: object, deletion: object, expired: list[str]) -> None:
        self._jobs = jobs  # type: ignore[assignment]
        self._deletion = deletion  # type: ignore[assignment]
        self._expired = expired

    def _expired_session_ids(self, *, now: datetime) -> list[str]:
        return self._expired


class TestOnePass:
    def test_recovery_runs_before_expiry(self) -> None:
        """A job whose lease expired should be recoverable before its content goes."""
        jobs = FakeJobs()
        sweeper = StubSweeper(jobs=jobs, deletion=FakeDeletion(), expired=[])

        sweeper.sweep(now=NOW)

        assert jobs.calls == ["recover_expired", "recover_orphans"]

    def test_counts_are_reported(self) -> None:
        jobs = FakeJobs(expired=2, orphaned=3)
        sweeper = StubSweeper(jobs=jobs, deletion=FakeDeletion(), expired=["s1", "s2"])

        report = sweeper.sweep(now=NOW)

        assert report.expired_leases == 2
        assert report.orphaned_jobs == 3
        assert report.expired_sessions == 2
        assert report.deletions_deferred == 0

    def test_expired_sessions_are_deleted_with_the_expiry_reason(self) -> None:
        """The same deletion path an immediate request uses, with a different reason."""
        deletion = FakeDeletion()
        sweeper = StubSweeper(jobs=FakeJobs(), deletion=deletion, expired=["s1"])

        sweeper.sweep(now=NOW)

        assert deletion.deleted == [("s1", REASON_EXPIRED)]

    def test_a_deferred_deletion_is_counted_not_retried(self) -> None:
        """Looping on a backoff inside one pass would turn it into a spin."""
        deletion = FakeDeletion(defer={"s2"})
        sweeper = StubSweeper(
            jobs=FakeJobs(),
            deletion=deletion,
            expired=["s1", "s2", "s3"],
        )

        report = sweeper.sweep(now=NOW)

        assert report.expired_sessions == 2
        assert report.deletions_deferred == 1
        assert [entry[0] for entry in deletion.deleted] == ["s1", "s3"]

    def test_nothing_expired_deletes_nothing(self) -> None:
        deletion = FakeDeletion()
        sweeper = StubSweeper(jobs=FakeJobs(), deletion=deletion, expired=[])

        report = sweeper.sweep(now=NOW)

        assert report.expired_sessions == 0
        assert deletion.deleted == []
