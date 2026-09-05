"""The workspace audit horizon (`W1-07b`; `KHEPRI-DEC-033` §2; `RCA-005` `FR-125`).

§2 gives the retention/lifecycle audit event twelve months, "the `KHEPRI-DEC-015` §2a horizon,
adopted rather than re-derived" -- so this takes `MEMBERSHIP_EVENT_RETENTION_MONTHS` and
`_months_before` from `rca/lifecycle.py` rather than spelling twelve again. Two literals for one
decided number is how they come to disagree the day one moves.

**Nothing implemented this horizon before `W1-07b`.** `KHEPRI-DEC-033` §5 records that no
retention horizon had a caller in the shipped image, which understates this one: the workspace
audit event had no sweeper at all. `W1-07a` shipped the deletion that writes these rows; this is
where they gain an ending.

Composed into the sweep through `RetentionPasses`, so it runs from `khepri-retention-sweep` -- a
retention rule whose only caller does not exist is indefinite retention with a policy comment on
top, which is the shape §5 exists to close.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from khepri.rca.lifecycle import MEMBERSHIP_EVENT_RETENTION_MONTHS, _months_before
from khepri.rca.workspace.audit import (
    ACTION_RETENTION_SWEPT,
    ACTOR_RETENTION,
    AuditActor,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore


@dataclass(frozen=True, slots=True)
class WorkspaceAuditSweepReport:
    """What one pass purged, in counts only. No identifier is echoed (`KHEPRI-DEC-015` §7)."""

    purged_events: int


class WorkspaceAuditSweeper:
    """Purges workspace audit events past `KHEPRI-DEC-015` §2a's twelve-month horizon.

    No horizon override in production: `retention_months` exists so a test can name a boundary
    without waiting a year, and `RetentionPasses` constructs this with the default. The same
    discipline `local/wiring.py` records for the other five passes.
    """

    def __init__(
        self,
        audit: SqlWorkspaceAuditStore,
        *,
        retention_months: int = MEMBERSHIP_EVENT_RETENTION_MONTHS,
    ) -> None:
        self._audit = audit
        self._retention_months = retention_months

    def sweep(self, *, now: datetime) -> WorkspaceAuditSweepReport:
        """One pass.

        Measured from the event's own instant, which is when the action happened -- not from any
        later reference. An event's twelve months begin when it is written; nothing that happens
        afterwards extends them, which is what keeps the horizon from being pushed outward by
        activity elsewhere in the scope.

        **The pass records itself** (`FR-125`, which names `sweep` literally), one event per scope
        it purged from -- `owner_id` is `nullable=False`, so a cross-scope pass cannot write one
        global event, and a customer's trail should show the sweeps that touched their rows.

        **It cannot purge its own evidence.** The event is written at `now` and the horizon is
        twelve months earlier, so no correctly ordered pass reaches it. That is asserted by
        `test_the_sweep_does_not_purge_its_own_evidence` rather than assumed, because it becomes
        false the day a later slice moves the horizon or reorders these two statements.
        """
        horizon = _months_before(now, self._retention_months)
        # Read before deleting: afterwards the rows that named these scopes are gone.
        scopes = self._audit.scopes_with_events_before(horizon)
        purged = self._audit.purge_events_before(horizon)
        for owner_id in scopes:
            self._audit.record(
                WorkspaceAuditEvent.completed(
                    AuditActor(owner_id=owner_id, actor_account_id=ACTOR_RETENTION),
                    ACTION_RETENTION_SWEPT,
                    # No subject: a sweep acts on a class over a horizon, not on an object.
                    None,
                    now=now,
                )
            )
        return WorkspaceAuditSweepReport(purged_events=purged)


__all__ = ["WorkspaceAuditSweepReport", "WorkspaceAuditSweeper"]
