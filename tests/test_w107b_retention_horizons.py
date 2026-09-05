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


def _evidence_aged(j, who, *, attempted_at: datetime) -> int:
    """One real deletion's evidence, aged to `attempted_at`. Returns how many rows exist.

    Produced by the **production verb** -- the deletion service ends a sealed version and the
    `RRA` path writes its own evidence -- rather than by inserting rows. Raw setup exempts the
    transition it skips, so a mutant of the bypassed verb survives every test built on it. Only
    the *clock* is faked, with a single `UPDATE`, because a test cannot wait thirteen months.
    """
    from sqlalchemy import text

    from tests.w107_support import deletion_service, sealed_version

    version, _run = sealed_version(j, who, with_run=True)
    deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )
    with j.w.factory() as database:
        aged = database.execute(
            text("UPDATE rra_deletion_evidence SET attempted_at = :t"),
            {"t": attempted_at},
        ).rowcount
        database.commit()
    assert aged > 0, "the deletion wrote no evidence to age"
    return aged


def test_deletion_evidence_past_twelve_months_is_purged() -> None:
    """`KHEPRI-DEC-033` `OD-2`: twelve months, "on `KHEPRI-DEC-015` §2a's discipline that no
    horizon is quietly longer than another". Rejected there: indefinite, by Constitution VII's
    least-data default."""
    from khepri.rra.evidence_retention import DeletionEvidenceSweeper
    from khepri.rra.persistence import SqlDeletionRepository

    j = journey()
    who = member(j.w)
    written = _evidence_aged(j, who, attempted_at=THIRTEEN_MONTHS_AGO)

    report = DeletionEvidenceSweeper(SqlDeletionRepository(j.w.factory)).sweep(now=NOW)

    assert report.purged_evidence == written


def test_deletion_evidence_inside_twelve_months_survives() -> None:
    """Evidence is what proves content ended (`FR-124`). Purging it early destroys the proof, so
    the boundary matters in both directions."""
    from khepri.rra.evidence_retention import DeletionEvidenceSweeper
    from khepri.rra.persistence import SqlDeletionRepository

    j = journey()
    who = member(j.w)
    _evidence_aged(j, who, attempted_at=ELEVEN_MONTHS_AGO)

    report = DeletionEvidenceSweeper(SqlDeletionRepository(j.w.factory)).sweep(now=NOW)

    assert report.purged_evidence == 0


def test_the_two_twelve_month_horizons_agree() -> None:
    """One decision, restated across a package boundary `R7-01` §3 forbids crossing.

    `KHEPRI-DEC-033` §2 gives audit events and deletion evidence the same twelve months, and
    `khepri.rra` may not import `khepri.rca`, so the number appears in both packages. This is what
    keeps that a restatement of one decision rather than two policies: move one and this fails.
    """
    from khepri.rca.lifecycle import MEMBERSHIP_EVENT_RETENTION_MONTHS
    from khepri.rra.evidence_retention import EVIDENCE_RETENTION_MONTHS

    assert EVIDENCE_RETENTION_MONTHS == MEMBERSHIP_EVENT_RETENTION_MONTHS
