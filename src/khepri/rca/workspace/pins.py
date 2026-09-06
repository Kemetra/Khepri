"""`W1-09`'s pins and recency: the two capabilities `KHEPRI-DEC-034` authorizes.

Split from `store.py` for the reason `schema.py` was split from `persistence.py` on `#370` --
CodeScene refused `store.py` at 720 lines against a threshold of 600, and the seam it forced is
the one a reader wants. `store.py` holds the workspace records and their lifecycle; this holds the
two reads and two writes that are *about* those records without being part of them.

**The split is also the boundary the decision draws.** Everything here is authorized by
`KHEPRI-DEC-034` and by nothing else: a pin is not a governed workspace action (`FR-128` emits no
audit event for it), and the recency view retains nothing at all (`FR-129`). Keeping them beside
the lifecycle would have made that distinction a matter of reading docstrings.

**A mixin rather than a second store class.** `SqlWorkspaceRecordStore` composes these methods, so
callers keep one object and the cascade below still runs inside `_tombstone_version`'s
transaction. A separate store over the same factory would be a second object holding one
definition of the scope -- and the cascade would then need a second transaction, which is exactly
what `KHEPRI-DEC-034` §1's "cascades from the pinned object's deletion" forbids.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, literal, select
from sqlalchemy.exc import IntegrityError

from khepri.rca.persistence import _utc
from khepri.rca.workspace.contracts import _identifier
from khepri.rca.workspace.schema import (
    PIN_KIND_FAILURE,
    PIN_KIND_RUN,
    PIN_KIND_VERSION,
    PIN_KINDS,
    RETENTION_ACTIVE,
    AnalysisRunRow,
    DatasetVersionRow,
    WorkspacePinRow,
)
from khepri.rca.workspace.unit_of_work import is_uniqueness_clash, reading, writing


@dataclass(frozen=True, slots=True)
class WorkspacePin:
    """One owner's mark on one object, as a reader sees it (`FR-128`).

    Three fields, and no fourth. There is deliberately no `opened_count`, no `last_opened_at` and
    no ordering weight -- a surface that wanted to rank by use would have to add one, and
    `KHEPRI-DEC-034` §2 refuses exactly that. `pinned_at` says when the mark was made, which is not
    a measurement of use.

    The `pin_id` is not projected: it identifies the row, and a caller addresses a pin by the
    object it names.
    """

    object_id: str
    object_kind: str
    pinned_at: datetime


@dataclass(frozen=True, slots=True)
class RecentItem:
    """One object this scope worked on, as the recency view presents it (`FR-129`).

    `occurred_at` is an instant the underlying record **already carried** -- a version's creation,
    a run's completion or start. It is not a "last opened" time, because nothing records when an
    object was opened: that would be the access record `KHEPRI-DEC-034` §2 refuses.

    There is no `count` and no rank. Recency is an ordering over records that exist; frequency
    would need a record of each visit, which is the thing not authorized.
    """

    object_id: str
    object_kind: str
    occurred_at: datetime



def cascade_to_pins(database, version: DatasetVersionRow) -> None:
    """Remove every pin naming a version being tombstoned, and every pin naming one of its runs.

    `KHEPRI-DEC-034` §1's matrix ends a pin when "the object ends", cascading from the pinned
    object's deletion. Called from inside `_tombstone_version` rather than beside it, so the
    removal shares the transaction that ends the version: one transaction ends the object and
    everything §1 says ends with it, or neither happens.

    Reached only after `set_retention_state`'s idempotency return, so a repeated deletion removes
    nothing a second time -- `_tombstone_version`'s discipline, inherited by being inside it.

    **Deleted outright, with no tombstone and no evidence row.** A pin is a stated preference
    rather than content, so `KHEPRI-DEC-033` §3's allowlist has nothing to say about it, and there
    is no `FR-125` event either: `FR-128` puts a pin outside the governed workspace actions
    entirely, and a cascade is part of its parent's deletion in any case (`KHEPRI-DEC-033` §1).

    Runs are collected rather than assumed absent: a pin may name a run directly, and that run
    ends with its version through `_cascade_tombstone_to_runs`. Reading them here keeps both
    object kinds on one pass instead of leaving the run's pins for a sweep that does not exist.
    """
    run_ids = database.scalars(
        select(AnalysisRunRow.run_id).where(
            AnalysisRunRow.owner_id == version.owner_id,
            AnalysisRunRow.version_id == version.version_id,
        )
    ).all()
    database.execute(
        delete(WorkspacePinRow).where(
            WorkspacePinRow.owner_id == version.owner_id,
            WorkspacePinRow.object_id.in_({version.version_id, *run_ids}),
        )
    )



class PinReads:
    """The pin and recency methods `SqlWorkspaceRecordStore` composes.

    A mixin, so `self._factory` is the store's own factory and every read here is narrowed by the
    same opaque scope the rest of the store uses.
    """

    def pin(self, object_id: str, object_kind: str, *, owner_id: str, now: datetime) -> None:
        """Mark one object for quick return (`FR-128`, under active `KHEPRI-DEC-034`).

        **Idempotent by constraint, not by a preceding read.** A read-then-insert passes under
        SQLite, which serializes writes, and admits a duplicate under PostgreSQL -- the shape
        `set_retention_state` records from `#370`, where the environment supplied the property the
        assertion checked. The clash is translated to a no-op here because a repeat is `FR-128`'s
        idempotent retry.

        **A repeat must not move `pinned_at`.** Rewriting it on every request would turn a stated
        preference into a record of when it was last asserted -- an access record by the back door,
        which `KHEPRI-DEC-034` §2 refuses by name. Doing nothing is the whole of the correct
        behaviour.

        No `FR-125` audit event: `FR-128` puts a pin outside the governed workspace actions and
        adds no member to `AUDIT_ACTIONS`.
        """
        if object_kind not in PIN_KINDS:
            raise ValueError(PIN_KIND_FAILURE)
        with writing(self._factory) as database:
            try:
                with database.begin_nested():
                    database.add(
                        WorkspacePinRow(
                            pin_id=_identifier("pin"),
                            owner_id=owner_id,
                            object_id=object_id,
                            object_kind=object_kind,
                            pinned_at=now,
                        )
                    )
            except IntegrityError as clash:
                if not is_uniqueness_clash(clash):
                    raise
                return

    def unpin(self, object_id: str, *, owner_id: str) -> None:
        """Remove one pin, on demand and idempotently (`KHEPRI-DEC-034` §1).

        Scoped by `owner_id` as well as by the object, so one scope cannot unpin another's mark --
        the filter is the isolation, not an optimization. Removing nothing is success: the
        post-condition a caller wants is that the object is not pinned.
        """
        with writing(self._factory) as database:
            database.execute(
                delete(WorkspacePinRow).where(
                    WorkspacePinRow.owner_id == owner_id,
                    WorkspacePinRow.object_id == object_id,
                )
            )

    def pins_for_scope(self, owner_id: str) -> tuple[WorkspacePin, ...]:
        """Every pin in one scope, most recently pinned first.

        Ordered by `pinned_at`, which is *when the mark was made* -- not by how often or how
        recently the object was opened, neither of which is recorded anywhere. `pin_id` breaks
        ties so a listing is stable across reads.
        """
        with reading(self._factory) as database:
            rows = database.scalars(
                select(WorkspacePinRow)
                .where(WorkspacePinRow.owner_id == owner_id)
                .order_by(WorkspacePinRow.pinned_at.desc(), WorkspacePinRow.pin_id)
            )
            return tuple(
                WorkspacePin(
                    object_id=row.object_id,
                    object_kind=row.object_kind,
                    pinned_at=_utc(row.pinned_at),
                )
                for row in rows
            )

    def recent_activity(self, owner_id: str, *, limit: int = 5) -> tuple[RecentItem, ...]:
        """What this owner last worked on, most recent first (`FR-129`).

        **This writes nothing, and that is the requirement rather than an optimization.**
        `KHEPRI-DEC-034` §1: "a query over dataset versions and analysis runs the workspace already
        stores ... ordered by instants those records already carry. This is the whole of why it
        needs no telemetry: a view that stores no event is not an event stream." A version of this
        that recorded each read -- to rank, to count, to show "most used" -- would be product
        analytics, which `KHEPRI-DEC-015` §3 does not authorize and §2 declines to seek.

        **It reads the workspace records, never `rca_workspace_audit_events`.** Rendering the audit
        trail as a customer-facing feed is the conversion `RCA-005` forbids in advance: the audit
        carve-out "does not reach" product use, and "an audit event that begins to carry a product
        metric has become telemetry and is excluded". The events are the right *shape* for a feed
        and the wrong *source*, which is exactly why the door is closed by name.

        Three filters per arm, not two. Scope and retention state are the obvious pair; the
        revocation predicate is the third, for `dataset_versions_for_scope`'s reason -- a restore
        rewrites `retention_state`, so only the ledger still knows the object ended (`FR-126`).
        Without it a restored version would reappear here after the customer deleted it.

        Ordered by the instants the records already carry -- `created_at` for a version, the run's
        completion or start for a run. Recency, never frequency: how *often* an object was opened
        is not recorded anywhere, and `KHEPRI-DEC-034` §2 refuses the counter that would record it.
        """
        # Imported inside the method: `store.py` imports this module to compose `PinReads`, so a
        # module-level import back would be circular. `_revocation_exists` stays in `store.py`
        # because every other read uses it and it belongs with the lifecycle it guards.
        from khepri.rca.workspace.store import _revocation_exists

        versions = (
            select(
                DatasetVersionRow.version_id.label("object_id"),
                literal(PIN_KIND_VERSION).label("object_kind"),
                DatasetVersionRow.created_at.label("occurred_at"),
            )
            .where(DatasetVersionRow.owner_id == owner_id)
            .where(DatasetVersionRow.retention_state == RETENTION_ACTIVE)
            .where(~_revocation_exists(DatasetVersionRow))
        )
        runs = (
            select(
                AnalysisRunRow.run_id.label("object_id"),
                literal(PIN_KIND_RUN).label("object_kind"),
                func.coalesce(AnalysisRunRow.completed_at, AnalysisRunRow.started_at).label(
                    "occurred_at"
                ),
            )
            .where(AnalysisRunRow.owner_id == owner_id)
            .where(AnalysisRunRow.retention_state == RETENTION_ACTIVE)
            .where(~_revocation_exists(AnalysisRunRow))
        )
        combined = versions.union_all(runs).subquery()
        with reading(self._factory) as database:
            rows = database.execute(
                select(combined)
                .order_by(combined.c.occurred_at.desc(), combined.c.object_id.desc())
                .limit(limit)
            ).all()
        return tuple(
            RecentItem(
                object_id=row.object_id,
                object_kind=row.object_kind,
                occurred_at=_utc(row.occurred_at),
            )
            for row in rows
        )


__all__ = ["PinReads", "RecentItem", "WorkspacePin", "cascade_to_pins"]
