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

from datetime import datetime

from sqlalchemy import delete, select
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
from khepri.rca.workspace.unit_of_work import reading, writing

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
        with writing(self._factory) as database:
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

    def purge_events_before(self, horizon: datetime) -> int:
        """Remove every event that occurred before `horizon`, returning how many (`W1-07b`).

        **Across scopes**, because the horizon is a property of the *event* and not of any
        organization: `KHEPRI-DEC-015` §2a fixes one twelve-month audit horizon for every event
        this table holds. A per-scope sweep would leave a closed organization's events
        indefinitely -- and those are precisely the rows nobody will read again, which is what the
        horizon exists to bound.

        Deleted rather than tombstoned. This table *is* the record of what happened; a tombstone
        of an audit event would be a second record of the same fact with none of its content, and
        `KHEPRI-DEC-033` §2's row for this class says "purge on elapse".
        """
        with writing(self._factory) as database:
            return database.execute(
                delete(WorkspaceAuditEventRow).where(
                    WorkspaceAuditEventRow.occurred_at < horizon
                )
            ).rowcount

    def events_for_scope(self, owner_id: str) -> tuple[WorkspaceAuditEvent, ...]:
        """Every event in one scope, oldest first. Keyed by the scope and nothing else."""
        with reading(self._factory) as database:
            rows = database.scalars(
                select(WorkspaceAuditEventRow)
                .where(WorkspaceAuditEventRow.owner_id == owner_id)
                .order_by(WorkspaceAuditEventRow.occurred_at, WorkspaceAuditEventRow.event_id)
            )
            return tuple(_event_from_row(row) for row in rows)
