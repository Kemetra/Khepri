"""The `FR-262` repair: fill a dataset version's missing upload identity (`RCA-005`, #535).

`20261003_0037` gave every version the `upload_id` of the upload it was admitted from. A process
still running code from before that revision would insert a version with a null `upload_id` while
its upload still exists. No purge, deletion or retry lookup could then find that upload
(`FR-259`-`FR-261`). This is step 2 of that revision's backfill, re-runnable:

- it sets a null `upload_id` from the one upload row in the version's scope whose ciphertext digest
  equals the version's recorded `upload_ciphertext_digest`;
- it refuses, and leaves null, a version whose digest matches more than one upload row, or one
  upload another version already names (`uq_rca_workspace_version_upload_id` would refuse the
  write, and the whole scope's repair with it);
- it never overwrites a value.

**Why the digest match is still valid here.** A digest names one stored copy of one upload until
that upload is re-sealed. `FR-263`(c) runs this repair, under the upload's session lock, before any
re-seal. This module and the migration are `FR-258`'s named exception to the rule that no query
keys on the digest.

**Under which role.** Each scope is repaired in its own transaction with that scope set
(`scoped_begin`), so on PostgreSQL the application role's `rra_owner_scope` policy admits exactly
that scope's uploads (`RRA-017` `FR-232`). The scopes to visit are read from
`rca_workspace_dataset_versions`, an RCA table that carries no policy (`RRA-017` Open item 1). No
cross-scope RRA read, no new role, no policy. The write is a Core `UPDATE`: the ORM's append-only
guard refuses any ORM write to `upload_id` (`FR-256`), and this repair is the one write `FR-262`
admits.

Who runs it across every environment, and when, is a deployment question. `FR-263`(b) and (c)
record it for the re-seal slice. This module gives that slice the operation and no caller.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select, update
from sqlalchemy.orm import Session, sessionmaker

from khepri.rca.workspace.persistence import DatasetVersionRow
from khepri.rra.persistence import UploadRow
from khepri.rra.scope import scoped_begin

_VERSIONS = DatasetVersionRow.__table__
_UPLOADS = UploadRow.__table__
_NAMED = _VERSIONS.alias("named")


@dataclass(frozen=True, slots=True)
class RepairOutcome:
    """What one repair did, as counts. No identifier, so it is safe to log."""

    filled: int
    refused: int

    def __add__(self, other: RepairOutcome) -> RepairOutcome:
        return RepairOutcome(self.filled + other.filled, self.refused + other.refused)


def _digest_match() -> ColumnElement[bool]:
    """The upload rows in the version's scope that carry the version's recorded digest."""
    return (_UPLOADS.c.owner_id == _VERSIONS.c.owner_id) & (
        _UPLOADS.c.ciphertext_sha256_hex == _VERSIONS.c.upload_ciphertext_digest
    )


def _matches() -> ColumnElement[int]:
    return select(func.count()).select_from(_UPLOADS).where(_digest_match()).scalar_subquery()


def _identity() -> ColumnElement[str]:
    """The matched upload's key, correlated to the outer version row at any nesting depth."""
    return (
        select(_UPLOADS.c.upload_id).where(_digest_match()).correlate(_VERSIONS).scalar_subquery()
    )


def _already_named() -> ColumnElement[bool]:
    """Another version in the scope already names the one upload the digest matches."""
    return (
        exists()
        .where(_NAMED.c.owner_id == _VERSIONS.c.owner_id, _NAMED.c.upload_id == _identity())
        .correlate(_VERSIONS)
    )


def _unfilled(owner_id: str) -> tuple[ColumnElement[bool], ...]:
    return (_VERSIONS.c.owner_id == owner_id, _VERSIONS.c.upload_id.is_(None))


def _refused(owner_id: str) -> Select[tuple[int]]:
    unsafe = or_(_matches() > 1, and_(_matches() == 1, _already_named()))
    return select(func.count()).select_from(_VERSIONS).where(*_unfilled(owner_id), unsafe)


def _repair_in(database: Session, owner_id: str) -> RepairOutcome:
    safe = and_(_matches() == 1, ~_already_named())
    filled = database.execute(
        update(_VERSIONS).where(*_unfilled(owner_id), safe).values(upload_id=_identity())
    )
    refused = database.execute(_refused(owner_id)).scalar_one()
    return RepairOutcome(filled=filled.rowcount or 0, refused=refused)


def repair_scope(factory: sessionmaker[Session], owner_id: str) -> RepairOutcome:
    """Repair one scope's versions, in one transaction, with that scope set."""
    with scoped_begin(factory, owner_id) as database:
        return _repair_in(database, owner_id)


def scopes_to_repair(factory: sessionmaker[Session]) -> tuple[str, ...]:
    """Every scope holding a version whose `upload_id` is null, read from the RCA table."""
    with factory() as database:
        rows = database.execute(
            select(_VERSIONS.c.owner_id)
            .where(_VERSIONS.c.upload_id.is_(None))
            .distinct()
            .order_by(_VERSIONS.c.owner_id)
        )
        return tuple(rows.scalars())


def repair_upload_identity(factory: sessionmaker[Session]) -> RepairOutcome:
    """Run `FR-262`'s repair over every scope that needs it, one scope per transaction."""
    total = RepairOutcome(filled=0, refused=0)
    for owner_id in scopes_to_repair(factory):
        total = total + repair_scope(factory, owner_id)
    return total


__all__ = [
    "RepairOutcome",
    "repair_scope",
    "repair_upload_identity",
    "scopes_to_repair",
]
