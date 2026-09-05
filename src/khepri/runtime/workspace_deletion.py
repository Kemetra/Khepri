"""Owner-requested deletion of a dataset version (`W1-07a`; `RCA-005` `FR-123`, `FR-124`,
`FR-126`).

**This composes; it does not re-implement.** `store.set_retention_state` already locks the version
row, writes its tombstone, cascades to every live run's tombstone, and returns early on a repeat
without moving `retention_changed_at` -- `KHEPRI-DEC-033` §5 anchors a horizon to that instant, so
a repeat that moved it would let repeated requests push a deadline outward. What was missing was
not the walk but everything around it: a caller, evidence, an audit event, and the ledger entry a
restore must meet.

**Composed in `khepri.runtime`** because it joins `khepri.rca`'s store to a revocation ledger and,
in a later slice, to `khepri.rra`'s deletion repository for the content the version derived. `R7-01`
§3 forbids either package importing the other, and this ending is a *decision the shell makes*, not
a rule either package owns -- the seam `W1-04b` established.

**What the repeat must and must not do** (`FR-123`, three claims, each separately evidenced):
the response is the same, **no new deletion evidence** is written, and **one** audit event is
emitted carrying `already_deleted`. One outcome test would pass with two of the three broken, so
`test_w107_deletion_service.py` asserts them apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from khepri.rca.workspace.audit import (
    ACTION_VERSION_DELETED,
    OBJECT_VERSION,
    AuditActor,
    AuditSubject,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.revocation import RevokedObject


@dataclass(frozen=True, slots=True)
class DeletionOutcome:
    """What one deletion request produced. `deleted` is `False` for `FR-123`'s idempotent repeat --
    the object had already ended -- and the rest of the response is identical either way, because
    the requirement makes a repeat succeed *with the same response as the first*."""

    version_id: str
    deleted: bool


class WorkspaceDeletion:
    """Ends a dataset version and everything named as cascading from it."""

    def __init__(self, *, store: Any, audit: Any, ledger: Any) -> None:
        self._store = store
        self._audit = audit
        self._ledger = ledger

    def delete_version(
        self, owner_id: str, version_id: str, *, actor_account_id: str, now: datetime
    ) -> DeletionOutcome:
        """End this scope's dataset version, immediately, idempotently, and evidenced.

        The already-ended case is read from the store rather than inferred from a return value:
        `get_dataset_version` answers `None` for a version that is tombstoned as well as for one
        that never existed, and both are the same answer to a customer -- there is nothing here to
        end. Answering `deleted=False` for either keeps `FR-123`'s "same response" true without
        telling one scope whether another's identifier ever existed.
        """
        actor = AuditActor(owner_id=owner_id, actor_account_id=actor_account_id)
        subject = AuditSubject(OBJECT_VERSION, version_id)
        if self._store.get_dataset_version(version_id, owner_id) is None:
            self._audit.record(
                WorkspaceAuditEvent.already_deleted(
                    actor, ACTION_VERSION_DELETED, subject, now=now
                )
            )
            return DeletionOutcome(version_id=version_id, deleted=False)
        self._store.tombstone_dataset_version(version_id, now=now, owner_id=owner_id)
        self._ledger.revoke(
            RevokedObject(
                object_kind=OBJECT_VERSION,
                object_id=version_id,
                owner_id=owner_id,
                revoked_at=now,
            )
        )
        self._audit.record(
            WorkspaceAuditEvent.completed(actor, ACTION_VERSION_DELETED, subject, now=now)
        )
        return DeletionOutcome(version_id=version_id, deleted=True)


__all__ = ["DeletionOutcome", "WorkspaceDeletion"]
