"""The audit event store (`W1-04`; `RCA-005` `FR-125`).

The row lives in `schema.py` with the other workspace rows, so `_ROW_GUARDS` registers its update
guard at import with the rest and `test_w102_workspace_guards.py`'s shape test sees every workspace
table on one page. This module holds the store: one append, one scoped read.

**Append-only, and purgeable.** An event is written once and never rewritten -- `schema.py` refuses
every `UPDATE` -- but it carries no delete guard, because `KHEPRI-DEC-015` §2a gives it a
twelve-month horizon and `W1-07`'s sweep must be able to purge it. The same asymmetry as the
tombstone row, for the same reason.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from khepri.rca.persistence import _utc
from khepri.rca.records import assert_sealed
from khepri.rca.workspace.audit import (
    AuditAction,
    AuditActor,
    AuditEntry,
    AuditSubject,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.schema import WorkspaceAuditEventRow

__all__ = ["SqlWorkspaceAuditStore", "WorkspaceAuditEventRow"]


def _event_from_row(row: WorkspaceAuditEventRow) -> WorkspaceAuditEvent:
    subject = (
        None
        if row.object_kind is None
        else AuditSubject(object_kind=row.object_kind, object_id=row.object_id)
    )
    return WorkspaceAuditEvent._from_storage(
        event_id=row.event_id,
        entry=AuditEntry(
            actor=AuditActor(owner_id=row.owner_id, actor_account_id=row.actor_account_id),
            action=AuditAction(action=row.action, outcome=row.outcome),
            subject=subject,
        ),
        occurred_at=_utc(row.occurred_at),
    )


class SqlWorkspaceAuditStore:
    """Rows for `WorkspaceAuditEvent`. Nothing here authorizes; see `SqlWorkspaceRecordStore`."""

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def record(self, event: WorkspaceAuditEvent) -> WorkspaceAuditEvent:
        """Append one event. A second write under the same identifier raises."""
        assert_sealed(event)
        with self._factory.begin() as database:
            database.add(
                WorkspaceAuditEventRow(
                    event_id=event.event_id,
                    owner_id=event.owner_id,
                    actor_account_id=event.actor_account_id,
                    action=event.action,
                    outcome=event.outcome,
                    object_kind=event.object_kind,
                    object_id=event.object_id,
                    occurred_at=event.occurred_at,
                )
            )
        return event

    def events_for_scope(self, owner_id: str) -> tuple[WorkspaceAuditEvent, ...]:
        """Every event in one scope, oldest first. Keyed by the scope and nothing else."""
        with self._factory() as database:
            rows = database.scalars(
                select(WorkspaceAuditEventRow)
                .where(WorkspaceAuditEventRow.owner_id == owner_id)
                .order_by(WorkspaceAuditEventRow.occurred_at, WorkspaceAuditEventRow.event_id)
            )
            return tuple(_event_from_row(row) for row in rows)
