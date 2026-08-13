"""The driver for the recovery and expiry work nothing currently calls.

**What this fills.** `SqlReportJobRepository.recover_expired` and
`recover_orphans` implement the restart recovery and orphan detection RRA-007
requires, and `DeletionService.delete_session_content` implements the deletion
RRA-002 requires. All three are complete; none of them has a caller. In the
deployed design that caller is whatever runs on a schedule, and no slice has added
one. This is that caller for a local run.

**Expiry deletes, it does not merely mark.** RRA-002 requires content to be gone
at seven days across input, materializations, facts, narrative and exports, so a
session past `content_expires_at` is swept through the same
`delete_session_content` path an immediate request uses, with a different reason.
Sharing the path is the point: an expiry route that deleted differently from the
on-demand route would be a second deletion implementation to keep correct.

**Nothing here is a scheduler.** It runs one pass when called. Choosing a cadence
is an operational decision, and a local loop that invented one would be modelling
a deployment nobody has authorized.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from khepri.rca.lifecycle import AccountRetentionSweeper
from khepri.rra.deletion import DeletionRetryRequired, DeletionService
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.persistence import BetaSessionRow

REASON_EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class SweepReport:
    """What one pass did, in counts only. No identifier is echoed."""

    expired_leases: int
    orphaned_jobs: int
    expired_sessions: int
    deletions_deferred: int
    purged_accounts: int = 0


class LocalSweeper:
    """One recovery-and-expiry pass over the local database."""

    def __init__(
        self,
        *,
        jobs: SqlReportJobRepository,
        deletion: DeletionService,
        factory: sessionmaker[Session],
        accounts: AccountRetentionSweeper | None = None,
    ) -> None:
        self._jobs = jobs
        self._deletion = deletion
        self._factory = factory
        # Optional so a stack with no RCA tables can still sweep RRA content. When present,
        # KHEPRI-DEC-015 §2b's retention pass runs here rather than nowhere: a retention rule
        # whose only caller does not exist is indefinite retention with a policy comment on top.
        self._accounts = accounts

    def sweep(self, *, now: datetime) -> SweepReport:
        """Recover stalled work, delete expired sessions, then apply account retention."""
        expired = self._jobs.recover_expired(now=now)
        orphaned = self._jobs.recover_orphans(now=now)
        swept, deferred = self._expire_sessions(now=now)
        # `getattr` because a stack without RCA tables, and the test stubs that subclass this
        # without calling __init__, legitimately have no retention pass to run.
        retention = getattr(self, "_accounts", None)
        purged = 0 if retention is None else retention.sweep(now=now).purged_accounts
        return SweepReport(
            expired_leases=len(expired),
            orphaned_jobs=len(orphaned),
            expired_sessions=swept,
            deletions_deferred=deferred,
            purged_accounts=purged,
        )

    def _expire_sessions(self, *, now: datetime) -> tuple[int, int]:
        """Delete content for every session past its expiry instant.

        A session whose deletion needs another attempt is counted rather than
        retried here: `DeletionRetryRequired` means the store asked for a later
        try, and looping on it inside one pass would turn a backoff into a spin.
        """
        swept = 0
        deferred = 0
        for session_id in self._expired_session_ids(now=now):
            try:
                self._deletion.delete_session_content(
                    session_id=session_id,
                    reason=REASON_EXPIRED,
                    now=now,
                )
            except DeletionRetryRequired:
                deferred += 1
            else:
                swept += 1
        return swept, deferred

    def _expired_session_ids(self, *, now: datetime) -> Sequence[str]:
        """Sessions past expiry whose content has not already been deleted."""
        with self._factory() as database:
            return list(
                database.execute(
                    select(BetaSessionRow.session_id).where(
                        BetaSessionRow.content_expires_at <= now,
                        BetaSessionRow.content_deleted_at.is_(None),
                    )
                ).scalars()
            )


def build_local_sweeper(
    *,
    jobs: SqlReportJobRepository,
    deletion: DeletionService,
    factory: sessionmaker[Session],
    accounts: AccountRetentionSweeper | None = None,
) -> LocalSweeper:
    return LocalSweeper(jobs=jobs, deletion=deletion, factory=factory, accounts=accounts)


__all__ = [
    "REASON_EXPIRED",
    "LocalSweeper",
    "SweepReport",
    "build_local_sweeper",
]
