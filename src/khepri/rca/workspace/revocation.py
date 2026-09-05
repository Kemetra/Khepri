"""The workspace revocation ledger (`W1-07a`; `RCA-005` `FR-126`; `KHEPRI-DEC-015` §8).

`FR-126`: a restore from backup MUST NOT make a deleted or tombstoned object readable. Deletion is
immediate and independent of any backup (§8 item 1), but a backup taken before it still holds the
row -- so the guarantee cannot be a property of the delete alone. This ledger is what a read
consults afterwards.

Held to §8 item 6's bound: opaque identifiers, revocation timestamps and status only. See
`WorkspaceRevocationRow` for why there is no status column and no foreign key.

Workspace-scoped by choice. §8 names sessions, memberships and invitations too, and none of them
has a requirement today; their horizon is `OD-3`-bounded, which is a separate approval. Generalizing
this to four consumers on one consumer's requirement would be authoring scope this slice does not
hold (`W1-07a` design §3.5).

## What this ledger does not survive

`WorkspaceRevocationRow` lives in the **same schema as the rows it guards**, so a point-in-time
restore of that schema removes the ledger along with them. State the consequence exactly rather
than leave it implied (review on `#382`):

- `FR-126` **holds** against in-database restoration -- a row put back beneath the ORM, past
  `_check_one_way_transitions`, which is the shape a partial or scripted recovery takes and the
  one the store's read guards refuse.
- `FR-126` **does not hold** against restoring a whole-schema snapshot predating the deletion.
  Both the version and its revocation come back, and nothing is left to consult.

Closing the second needs the ledger to have a backup lifecycle of its own, which is a backup
topology decision `KHEPRI-DEC-008` leaves open while provisioning is frozen -- not something this
module can fix. `test_a_whole_schema_restore_predating_the_deletion_defeats_the_ledger` asserts the
limitation as it stands, so it fails and gets rewritten on the day the ledger moves.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from khepri.rca.workspace.schema import WorkspaceRevocationRow
from khepri.rca.workspace.unit_of_work import reading, writing


@dataclass(frozen=True, slots=True)
class RevokedObject:
    """One ended object, as the ledger records it."""

    object_kind: str
    object_id: str
    owner_id: str
    revoked_at: datetime


class SqlRevocationLedger:
    """Records that an object ended, and answers whether one did."""

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def revoke(self, revoked: RevokedObject) -> None:
        """Record that this object ended. A repeat keeps the first instant.

        `KHEPRI-DEC-033` bounds this ledger by the backup horizon measured from `revoked_at`, so
        overwriting it on a repeat would let repeated requests push that deadline outward. That is
        the defect `store.py:631` records against `retention_changed_at`, reaching the ledger
        through the same idempotent door, so it is refused here the same way.
        """
        with writing(self._factory) as database:
            existing = database.get(
                WorkspaceRevocationRow,
                (revoked.object_kind, revoked.object_id, revoked.owner_id),
            )
            if existing is not None:
                return
            database.add(
                WorkspaceRevocationRow(
                    object_kind=revoked.object_kind,
                    object_id=revoked.object_id,
                    owner_id=revoked.owner_id,
                    revoked_at=revoked.revoked_at,
                )
            )

    def is_revoked(self, object_kind: str, object_id: str, owner_id: str) -> bool:
        """Whether this scope's object of this kind ended. Scoped like every workspace read."""
        return self.revoked_at(object_kind, object_id, owner_id) is not None

    def revoked_at(self, object_kind: str, object_id: str, owner_id: str) -> datetime | None:
        """When it ended, or `None` for an object this scope never revoked."""
        with reading(self._factory) as database:
            found = database.scalar(
                select(WorkspaceRevocationRow.revoked_at).where(
                    WorkspaceRevocationRow.object_kind == object_kind,
                    WorkspaceRevocationRow.object_id == object_id,
                    WorkspaceRevocationRow.owner_id == owner_id,
                )
            )
        if found is None or found.tzinfo is not None:
            return found
        # SQLite hands back naive instants; every instant this module states is UTC.
        return found.replace(tzinfo=UTC)


__all__ = ["RevokedObject", "SqlRevocationLedger"]
