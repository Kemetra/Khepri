"""`W1-07b` -- the two `KHEPRI-DEC-033` §2 horizons that had no implementation anywhere.

§5 says every horizon in §2 is unenforced because no sweeper has a caller in the shipped image.
That is true of five sweepers; it understates these two, which had no code at all. `W1-07a` shipped
the deletion that *writes* both classes, so `W1-07b` is where they gain an ending.

Both are twelve months, and both take that number from a named constant rather than a literal: §2
says the horizon is "adopted rather than re-derived", and two literals for one decided number is how
they come to disagree the day one moves.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from khepri.rca.workspace.audit import (
    ACTION_VERSION_CREATED,
    AuditActor,
    AuditSubject,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.audit_retention import WorkspaceAuditSweeper
from tests.w104_support import member
from tests.w107_support import journey

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
#: Comfortably past the twelve-month horizon, and comfortably inside it. Written as day offsets
#: rather than month arithmetic so the fixture does not restate the code under test.
THIRTEEN_MONTHS_AGO = NOW - timedelta(days=396)
ELEVEN_MONTHS_AGO = NOW - timedelta(days=334)


def _event(store: SqlWorkspaceAuditStore, owner_id: str, account_id: str, when: datetime) -> None:
    """One real audit event, through the store's own verb."""
    store.record(
        WorkspaceAuditEvent.completed(
            AuditActor(owner_id=owner_id, actor_account_id=account_id),
            ACTION_VERSION_CREATED,
            AuditSubject("version", "dsv_example"),
            now=when,
        )
    )


def test_an_audit_event_past_twelve_months_is_purged() -> None:
    """`KHEPRI-DEC-033` §2: the retention/lifecycle audit event is purged on elapse of twelve
    months, "the `KHEPRI-DEC-015` §2a horizon, adopted rather than re-derived"."""
    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, THIRTEEN_MONTHS_AGO)

    report = WorkspaceAuditSweeper(audit).sweep(now=NOW)

    assert report.purged_events == 1


def test_an_audit_event_inside_twelve_months_survives() -> None:
    """The horizon is a boundary, not a purge-everything.

    A sweeper that removed live evidence would destroy the attribution `FR-125` exists to keep --
    which is a worse failure than the unbounded growth this pass was written to stop.
    """
    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, ELEVEN_MONTHS_AGO)

    report = WorkspaceAuditSweeper(audit).sweep(now=NOW)

    assert report.purged_events == 0
    assert len(audit.events_for_scope(who.owner_id)) == 1
