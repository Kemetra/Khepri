"""Shared setup for `W1-07a`'s deletion tests.

Setup runs through **production verbs** -- the journey submits, the worker settles, the store
seals -- rather than shaping rows directly. Raw setup exempts the transition it skips, so a mutant
of the bypassed verb survives every test built on it; that lesson is recorded against this repo more
than once.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from khepri.rca.workspace.audit import WorkspaceAuditEvent
from khepri.rca.workspace.revocation import SqlRevocationLedger
from tests.w104_support import Member
from tests.w104b_support import Journey, journey
from tests.w106_support import completed_run, submitted

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def sealed_version(j: Journey, who: Member, *, with_run: bool = False) -> tuple[Any, Any]:
    """A dataset version this scope holds, optionally with a completed run over it.

    Both are produced by the real journey: `submitted` admits and attests an upload, and
    `completed_run` drives the worker through settlement.
    """
    if with_run:
        run, _job_id, _session_id = completed_run(j, who)
        (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
        return version, run
    submitted(j, who)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    return version, None


def audit_events_for(j: Journey, owner_id: str) -> tuple[WorkspaceAuditEvent, ...]:
    """Every workspace audit event in one scope, oldest first."""
    return j.w.audit.events_for_scope(owner_id)


def uploads_for(j: Journey, owner_id: str) -> tuple[Any, ...]:
    """Every upload row still held by this scope, read as the store reads them."""
    from sqlalchemy import select

    from khepri.rra.persistence import UploadRow

    with j.w.factory() as database:
        return tuple(database.scalars(select(UploadRow).where(UploadRow.owner_id == owner_id)))


def deletion_jobs_for(j: Journey, owner_id: str) -> tuple[str, ...]:
    """Every `RRA` deletion job this scope has begun, by identifier."""
    from sqlalchemy import select

    from khepri.rra.persistence import DeletionJobRow

    with j.w.factory() as database:
        return tuple(
            database.scalars(
                select(DeletionJobRow.deletion_id).where(DeletionJobRow.owner_id == owner_id)
            )
        )


def deletion_service(j: Journey) -> Any:
    """The deletion service composed as the runtime composes it (`R7-01` §3: the RCA store and the
    RRA deletion path meet here, in `khepri.runtime`, and not inside either package)."""
    from khepri.rra.deletion import DeletionService
    from khepri.rra.persistence import SqlDeletionRepository
    from khepri.runtime.workspace_deletion import WorkspaceDeletion

    return WorkspaceDeletion(
        store=j.w.store,
        audit=j.w.audit,
        ledger=SqlRevocationLedger(j.w.factory),
        content=DeletionService(
            sessions=j.w.sessions,
            deletions=SqlDeletionRepository(j.w.factory),
            objects=j.w.objects,
        ),
        factory=j.w.factory,
    )


__all__ = [
    "LATER",
    "NOW",
    "audit_events_for",
    "deletion_jobs_for",
    "deletion_service",
    "journey",
    "sealed_version",
    "uploads_for",
]
