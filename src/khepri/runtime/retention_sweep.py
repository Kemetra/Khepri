"""The retention and recovery sweep, and the caller `KHEPRI-DEC-033` §5 requires.

**Why this module is in `khepri.runtime`.** The wheel excludes `src/khepri/local`, so a sweep
composed there is absent from the image that must run it -- which is what §5 measured and named as
the reason no retention horizon is enforced. `pyproject.toml` records the same reasoning for
`khepri-clerk-hard-stop`: a command in `khepri.local` "would be absent from the image that actually
needs to run it".

**Named `RetentionSweeper`, not `LocalSweeper`.** Once this ships in the wheel it is *the*
sweeper. A name saying "local" would misdescribe the deployed artifact to the next reader, which
is how a later slice comes to write a second one for "real" deployments.

**What this fills.** `SqlReportJobRepository.recover_expired` and
`recover_orphans` implement the restart recovery and orphan detection RRA-007
requires, and `DeletionService.delete_session_content` implements the deletion
RRA-002 requires. Before `W1-07b` all three were complete and none had a caller in the
shipped image; `khepri-retention-sweep` is that caller.

**Expiry deletes, it does not merely mark.** RRA-002 requires content to be gone
at seven days across input, materializations, facts, narrative and exports, so a
session past `content_expires_at` is swept through the same
`delete_session_content` path an immediate request uses, with a different reason.
Sharing the path is the point: an expiry route that deleted differently from the
on-demand route would be a second deletion implementation to keep correct.

**Nothing here is a scheduler.** It runs one pass when called. Choosing a cadence
is an operational decision, and a loop that invented one would be modelling a
deployment nobody has authorized. `KHEPRI-DEC-033` decides no cadence; §5 asks for
*a caller present in the shipped image*, which a console script in the wheel is.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from khepri.rca.invitation_retention import InvitationRetentionSweeper
from khepri.rca.lifecycle import AccountRetentionSweeper, MembershipEventSweeper
from khepri.rca.recovery_security import RecoverySecurityEventSweeper
from khepri.rca.session_retention import SessionRetentionSweeper
from khepri.rca.workspace.audit_retention import WorkspaceAuditSweeper
from khepri.rra.deletion import DeletionRetryRequired, DeletionService
from khepri.rra.evidence_retention import DeletionEvidenceSweeper
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
    purged_events: int = 0
    # Distinct from `expired_sessions` above, which counts RRA beta sessions whose *content* was
    # deleted. This counts commercial session records removed after their retention horizon
    # (`R3-07`). Two different tables and two different policies; one name for both would make a
    # report that reads as consistent while measuring unrelated things.
    purged_sessions: int = 0
    # `R4-03`'s invitation horizon. Distinct from every count above for the same reason
    # `purged_sessions` is distinct from `expired_sessions`: a different table and a different
    # policy. This one carries a privacy obligation the others do not -- an invitation row holds a
    # `target_identity`, so a pass that purged none when it should have is a retention failure
    # rather than a housekeeping one.
    purged_invitations: int = 0
    # `KHEPRI-DEC-025` §4's recovery security evidence. Named apart from `purged_events` above
    # rather than folded into it: that field counts FR-014 membership events, this one counts
    # content-free provider-recovery evidence, and two different tables under one name would make
    # a report that reads as consistent while measuring unrelated things.
    purged_recovery_events: int = 0
    # `W1-07b`'s two `KHEPRI-DEC-033` §2 horizons. Named apart from every count above for the
    # reason `purged_sessions` is named apart from `expired_sessions`: different tables under
    # different rules, and one name for two would make a report that reads as consistent while
    # measuring unrelated things.
    purged_workspace_audit_events: int = 0
    purged_evidence: int = 0


    def as_counts(self) -> dict[str, int]:
        """Every count by name, for the entry point's one JSON line."""
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class RetentionCounts:
    """What the retention passes purged, by name.

    Replaces a positional five-tuple. Every field is a distinct table under a distinct governed
    horizon, so position is the wrong way to tell them apart.
    """

    accounts: int = 0
    events: int = 0
    sessions: int = 0
    invitations: int = 0
    recovery_events: int = 0
    #: `W1-07b`'s two `KHEPRI-DEC-033` §2 horizons, which had no implementation before it.
    workspace_audit_events: int = 0
    evidence: int = 0


@dataclass(frozen=True, slots=True)
class RetentionPasses:
    """`KHEPRI-DEC-015`'s two horizons, travelling together.

    They are one parameter rather than two because they are one concern with one reason to be
    absent: a stack with no RCA tables has neither. Passing them separately also pushed
    `RetentionSweeper.__init__` to five arguments, which CodeScene flagged — the signature had been
    accumulating one collaborator per slice, and the smell was real rather than incidental.

    Both stay optional so a stack that sweeps only RRA content can construct this with nothing.
    """

    accounts: AccountRetentionSweeper | None = None
    events: MembershipEventSweeper | None = None
    sessions: SessionRetentionSweeper | None = None
    invitations: InvitationRetentionSweeper | None = None
    # `KHEPRI-DEC-025` §4's recovery security evidence, anchored to the same twelve-month audit
    # horizon as `events` above. A fifth pass rather than a reuse of `events`: both purge at
    # twelve months, but they are different tables under different requirements, and one sweeper
    # covering both would purge either by accident if a horizon later moved.
    recovery_events: RecoverySecurityEventSweeper | None = None
    #: `KHEPRI-DEC-033` §2's twelve-month workspace audit horizon (`W1-07b`). Optional for the
    #: reason every field here is: a stack with no RCA workspace tables has nothing to sweep.
    workspace_audit: WorkspaceAuditSweeper | None = None
    #: `KHEPRI-DEC-033` `OD-2`'s twelve-month deletion-evidence horizon (`W1-07b`).
    evidence: DeletionEvidenceSweeper | None = None

    def run(self, *, now: datetime) -> RetentionCounts:
        """All five passes, returning the purged counts by name.

        Independent of each other: §2a's twelve-month audit horizon is shorter than §2b's
        twenty-four month account horizon, so an event never outlives the account it refers to,
        and neither pass depends on the other having run. `R3-07`'s session horizon is shorter
        still and references neither — a session record is an operational artifact, so purging one
        removes no audit evidence and changes no authority.

        **The invitation pass is anchored to the event pass but does not depend on it having run.**
        `R4-03`'s redeemed-invitation horizon is `MEMBERSHIP_EVENT_RETENTION_MONTHS`, so the two
        move
        together by construction — but each evaluates its own predicate against `now`, and running
        them in either order over the same instant gives the same result. Ordering here is field
        order, not a dependency.

        **The recovery-evidence pass is independent of all four.** It purges only the content-free
        `RecoverySecurityEvent` rows, which reference an account but carry no identity data, so it
        neither depends on nor blocks any other horizon.

        Returns a named record rather than a tuple: this began as a four-element tuple destructured
        by position, and a fifth pass is where that stops being readable. The same reasoning made
        these sweepers one value object in the first place.
        """
        return RetentionCounts(
            accounts=0 if self.accounts is None else self.accounts.sweep(now=now).purged_accounts,
            events=0 if self.events is None else self.events.sweep(now=now).purged_events,
            sessions=(
                0 if self.sessions is None else self.sessions.sweep(now=now).purged_sessions
            ),
            invitations=(
                0
                if self.invitations is None
                else self.invitations.sweep(now=now).purged_invitations
            ),
            recovery_events=(
                0
                if self.recovery_events is None
                else self.recovery_events.sweep(now=now).purged_events
            ),
            workspace_audit_events=(
                0
                if self.workspace_audit is None
                else self.workspace_audit.sweep(now=now).purged_events
            ),
            evidence=(
                0 if self.evidence is None else self.evidence.sweep(now=now).purged_evidence
            ),
        )


class RetentionSweeper:
    """One recovery-and-expiry pass over the local database."""

    def __init__(
        self,
        *,
        jobs: SqlReportJobRepository,
        deletion: DeletionService,
        factory: sessionmaker[Session],
        retention: RetentionPasses | None = None,
    ) -> None:
        self._jobs = jobs
        self._deletion = deletion
        self._factory = factory
        # Optional so a stack with no RCA tables can still sweep RRA content. When present,
        # KHEPRI-DEC-015's retention passes run here rather than nowhere: a retention rule whose
        # only caller does not exist is indefinite retention with a policy comment on top.
        self._retention = retention

    def sweep(self, *, now: datetime) -> SweepReport:
        """Recover stalled work, delete expired sessions, then apply both retention horizons."""
        expired = self._jobs.recover_expired(now=now)
        orphaned = self._jobs.recover_orphans(now=now)
        swept, deferred = self._expire_sessions(now=now)
        # `getattr` because a stack without RCA tables, and the test stubs that subclass this
        # without calling __init__, legitimately have no retention pass to run.
        retention = getattr(self, "_retention", None) or RetentionPasses()
        purged = retention.run(now=now)
        return SweepReport(
            expired_leases=len(expired),
            orphaned_jobs=len(orphaned),
            expired_sessions=swept,
            deletions_deferred=deferred,
            purged_accounts=purged.accounts,
            purged_events=purged.events,
            purged_sessions=purged.sessions,
            purged_invitations=purged.invitations,
            purged_recovery_events=purged.recovery_events,
            purged_workspace_audit_events=purged.workspace_audit_events,
            purged_evidence=purged.evidence,
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


def build_retention_sweeper(
    *,
    jobs: SqlReportJobRepository,
    deletion: DeletionService,
    factory: sessionmaker[Session],
    retention: RetentionPasses | None = None,
) -> RetentionSweeper:
    return RetentionSweeper(jobs=jobs, deletion=deletion, factory=factory, retention=retention)


def main() -> None:
    """One retention pass over the configured database (`KHEPRI-DEC-033` §5).

    Prints one content-free JSON line of counts -- no identifier is echoed, per `KHEPRI-DEC-015`
    §7 -- so an operator or a scheduled invocation has a record of what a pass did without the
    pass becoming a channel for customer data.

    Builds through `build_stack`, which already constructs the engine, the session factory and the
    object store `DeletionService` needs. A bespoke construction here would be a second wiring of
    the same collaborators, which this module's own docstring records as the thing to avoid.
    """
    import json
    from datetime import UTC, datetime

    from khepri.runtime.config import RuntimeSettings
    from khepri.runtime.wiring import build_retention_sweep, build_stack

    now = datetime.now(UTC)
    stack = build_stack(RuntimeSettings.from_environment())
    report = build_retention_sweep(stack).sweep(now=now)
    print(
        json.dumps(
            {"event": "retention_sweep", "occurred_at": now.isoformat()} | report.as_counts(),
            sort_keys=True,
        )
    )


__all__ = [
    "REASON_EXPIRED",
    "RetentionCounts",
    "RetentionPasses",
    "RetentionSweeper",
    "SweepReport",
    "build_retention_sweeper",
    "main",
]
