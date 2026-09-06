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

from collections.abc import Iterable
from dataclasses import dataclass
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

__all__ = ["PurgedEvents", "SqlWorkspaceAuditStore", "WorkspaceAuditEventRow"]


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


@dataclass(frozen=True, slots=True)
class PurgedEvents:
    """What one purge removed: how many rows, and the scopes they belonged to.

    The two travel together because they come from one statement. Returning a bare count and
    asking a second query which scopes were affected is the shape that let evidence outlive the
    purge it attests (`#384`).
    """

    count: int
    scopes: tuple[str, ...]

    @classmethod
    def of(cls, owner_ids: Iterable[str]) -> PurgedEvents:
        """From the `owner_id` of every deleted row -- one per row, so the count is the rows and
        the scopes are those rows deduplicated, order preserved for a stable audit trail."""
        deleted = tuple(owner_ids)
        return cls(count=len(deleted), scopes=tuple(dict.fromkeys(deleted)))


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

    def purge_events_before(self, horizon: datetime) -> PurgedEvents:
        """Remove every event that occurred before `horizon`, saying what went (`W1-07b`).

        **Across scopes**, because the horizon is a property of the *event* and not of any
        organization: `KHEPRI-DEC-015` §2a fixes one twelve-month audit horizon for every event
        this table holds. A per-scope sweep would leave a closed organization's events
        indefinitely -- and those are precisely the rows nobody will read again, which is what the
        horizon exists to bound.

        Deleted rather than tombstoned. This table *is* the record of what happened; a tombstone
        of an audit event would be a second record of the same fact with none of its content, and
        `KHEPRI-DEC-033` §2's row for this class says "purge on elapse".

        **`RETURNING`, so the scopes are the rows this statement removed.** The sweep records one
        event per scope it purged from, and it used to learn those scopes from a separate read
        issued before the delete. Between the two statements the rows can go: two overlapping
        `khepri-retention-sweep` invocations both read the scope, one deletes its rows and the
        other deletes none, and both then record `retention_swept` -- an audit record for a purge
        that did not happen, which a reader cannot tell from the real thing. Review on `#384` found
        the window. One statement cannot be interleaved with itself, so the count and the scopes
        agree by construction rather than by timing.
        """
        with writing(self._factory) as database:
            purged = database.execute(
                delete(WorkspaceAuditEventRow)
                .where(WorkspaceAuditEventRow.occurred_at < horizon)
                .returning(WorkspaceAuditEventRow.owner_id)
            ).scalars()
            return PurgedEvents.of(purged)

    def events_for_scope(self, owner_id: str) -> tuple[WorkspaceAuditEvent, ...]:
        """Every event in one scope, oldest first. Keyed by the scope and nothing else."""
        with reading(self._factory) as database:
            rows = database.scalars(
                select(WorkspaceAuditEventRow)
                .where(WorkspaceAuditEventRow.owner_id == owner_id)
                .order_by(WorkspaceAuditEventRow.occurred_at, WorkspaceAuditEventRow.event_id)
            )
            return tuple(_event_from_row(row) for row in rows)
