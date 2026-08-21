"""The sweeper recovers stalled work and deletes what has outlived its session.

Fakes again: `recover_expired`, `recover_orphans` and `delete_session_content` are
already covered where they are implemented. What is verified here is that one pass
calls all three, counts what it did, and treats a deferred deletion as deferred
rather than retrying it inside the same pass.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import UTC, datetime
from types import SimpleNamespace

from khepri.local.sweeper import REASON_EXPIRED, LocalSweeper, RetentionPasses
from khepri.rca.lifecycle import EventPurgeReport, PurgeReport
from khepri.rca.session_retention import SessionSweepReport
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

    def __init__(
        self,
        *,
        jobs: object,
        deletion: object,
        expired: list[str],
        retention: RetentionPasses | None = None,
    ) -> None:
        self._jobs = jobs  # type: ignore[assignment]
        self._deletion = deletion  # type: ignore[assignment]
        self._expired = expired
        self._retention = retention

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


class TestTheRetentionPassesAreWired:
    """`KHEPRI-DEC-015`'s horizons are enforced by whatever calls them, and nothing else.

    Both `AccountRetentionSweeper` and `MembershipEventSweeper` shipped correct and uncalled — the
    defect that pattern produces is not a failing test but a policy that quietly does nothing. So
    the wiring itself is asserted, not just the classes.
    """

    def test_a_stack_with_no_retention_configured_sweeps_rra_content_only(self) -> None:
        """The optional half: a stack with no RCA tables still runs the session passes."""
        sweeper = StubSweeper(jobs=FakeJobs(), deletion=FakeDeletion(), expired=["s1"])

        report = sweeper.sweep(now=NOW)

        assert report.expired_sessions == 1
        assert report.purged_accounts == 0
        assert report.purged_events == 0

    def test_both_horizons_run_in_one_pass(self) -> None:
        """A pass reports both counts, so neither horizon can be silently skipped."""

        class CountingPass:
            def __init__(self, report: object) -> None:
                self._report = report
                self.calls = 0

            def sweep(self, *, now: datetime) -> object:
                self.calls += 1
                return self._report

        accounts = CountingPass(PurgeReport(purged_accounts=2))
        events = CountingPass(EventPurgeReport(purged_events=3))
        sessions = CountingPass(SessionSweepReport(purged_sessions=4))
        sweeper = StubSweeper(
            jobs=FakeJobs(),
            deletion=FakeDeletion(),
            expired=[],
            retention=RetentionPasses(  # type: ignore[arg-type]
                accounts=accounts, events=events, sessions=sessions
            ),
        )

        report = sweeper.sweep(now=NOW)

        assert (accounts.calls, events.calls, sessions.calls) == (1, 1, 1), (
            "each horizon ran exactly once"
        )
        assert report.purged_accounts == 2
        assert report.purged_events == 3
        assert report.purged_sessions == 4

    def test_the_session_count_is_distinct_from_rra_content_expiry(self) -> None:
        """`expired_sessions` and `purged_sessions` measure unrelated things.

        The first counts RRA beta sessions whose *content* was deleted; the second counts
        commercial session records removed after `R3-07`'s horizon. Collapsing them would produce
        a report that reads as consistent while summing two different tables under two different
        policies.
        """
        sessions = SimpleNamespace(sweep=lambda *, now: SessionSweepReport(purged_sessions=5))
        sweeper = StubSweeper(
            jobs=FakeJobs(),
            deletion=FakeDeletion(),
            expired=["beta-1", "beta-2"],
            retention=RetentionPasses(sessions=sessions),  # type: ignore[arg-type]
        )

        report = sweeper.sweep(now=NOW)

        assert report.expired_sessions == 2
        assert report.purged_sessions == 5

    def test_production_wires_both_horizons_with_no_override(self) -> None:
        """`build_worker_stack` passes every retention pass, none with a compressed horizon.

        **Why the source and not the built object.** Constructing a real stack needs PostgreSQL and
        an object endpoint, so the equivalent assertion in `test_local_journey.py` is gated behind
        `@requires_local_stack()` and skips in CI. A wiring assertion that never executes is not
        evidence, so this runs unconditionally on the syntax tree.

        **A first version matched raw text and was worthless.** Mutation-testing showed it passed
        both with the events pass deleted from production outright *and* with `retention_months=1`
        spliced in: the string slice meant to bound the search ended before the lines it intended to
        read. An AST cannot mis-slice — the keyword is either in the call or it is not.
        """
        tree = ast.parse(pathlib.Path("src/khepri/local/wiring.py").read_text(encoding="utf-8"))
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and any(word.arg == "retention" for word in node.keywords)
        ]
        assert len(calls) == 1, "exactly one sweeper wiring site"

        passes = next(word.value for word in calls[0].keywords if word.arg == "retention")
        wired = {word.arg: ast.unparse(word.value) for word in passes.keywords}  # type: ignore[attr-defined]

        assert set(wired) == {
            "accounts",
            "events",
            "sessions",
            "invitations",
            "recovery_events",
        }, "all five horizons are wired"
        assert "AccountRetentionSweeper" in wired["accounts"]
        assert "MembershipEventSweeper" in wired["events"]
        assert "SessionRetentionSweeper" in wired["sessions"]
        # `KHEPRI-DEC-025` §4. Recorded as unwired by the `#240` post-merge audit: the sweeper and
        # its store existed and were tested, and nothing constructed them, so the twelve-month
        # horizon was enforced by nothing.
        assert "RecoverySecurityEventSweeper" in wired["recovery_events"]
        # `R4-03`. An unwired invitation sweeper would satisfy every sentence in its own module and
        # destroy nothing, which is the failure `R4-01` §8.1 names -- and unlike the three above,
        # the
        # rows it fails to purge hold a `target_identity`.
        assert "InvitationRetentionSweeper" in wired["invitations"]
        for name, expression in wired.items():
            assert "retention_months" not in expression, (
                f"the {name} horizon must be the governed default, not an override"
            )
            assert "retention_days" not in expression, (
                f"the {name} horizon must be the governed default, not an override"
            )
