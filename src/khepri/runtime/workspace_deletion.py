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

    #: `rra_deletion_jobs` admits `immediate` and `expiry`. An owner-requested deletion is the
    #: first: `FR-123` makes it immediate, and `expiry` is `W1-07b`'s retention-triggered purge.
    REASON_IMMEDIATE = "immediate"

    def __init__(
        self, *, store: Any, audit: Any, ledger: Any, content: Any, factory: Any
    ) -> None:
        self._store = store
        self._audit = audit
        self._ledger = ledger
        self._content = content
        self._factory = factory

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
        version = self._store.get_dataset_version(version_id, owner_id)
        self._end_derived_content(version, now)
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

    def _session_of_upload(self, owner_id: str, ciphertext_digest: str) -> str | None:
        """The session that admitted this upload, by the digest the version retains.

        Read here rather than through a new `SqlUploadRepository` verb: the join is this ending's,
        not the upload store's, and `R7-01` §3 puts a read that serves an `RCA` ending over an
        `RRA` row at the composition seam. Scoped by `owner_id` as well as the digest, so a digest
        two organizations happen to share cannot address the other's session.
        """
        from sqlalchemy import select

        from khepri.rra.persistence import UploadRow

        with self._factory() as database:
            return database.scalar(
                select(UploadRow.session_id).where(
                    UploadRow.owner_id == owner_id,
                    UploadRow.ciphertext_sha256_hex == ciphertext_digest,
                )
            )

    def _end_derived_content(self, version: Any, now: datetime) -> None:
        """End the upload this version was admitted from, and everything derived from it.

        `KHEPRI-DEC-033` §1: *derived content never outlives its input's right to exist*. Ending
        only the `RCA` records would leave the customer's upload, fact packages and artifacts in
        place under a version they withdrew.

        **Bridged on the ciphertext digest**, because a `DatasetVersion` holds the upload's digests
        and no session identifier -- §3 fixes what a version may keep, and a session identifier is
        not on that list. The upload row carries both the digest and its session, and the digest is
        already the key `dataset_version_for_upload` joins on, so this reuses an existing link
        rather than inventing one. Resolved here, in `khepri.runtime`, because it reads an `RRA`
        row on behalf of an `RCA` ending and `R7-01` §3 forbids either package importing the other.

        Through `DeletionService.delete_session_content`, which is the one implementation of this
        ending -- `local/sweeper.py` records why: *"an expiry route that deleted differently from
        the on-demand route would be a second deletion implementation to keep correct"*. It is also
        what writes `FR-124`'s content-free evidence, so the evidence arrives by using the existing
        path rather than by this slice writing a second kind.

        The job it begins is idempotent per session, so a repeat that reached here would not start
        a second ending -- but the caller returns before this on the already-deleted path, so a
        repeat does not reach it at all.
        """
        session_id = self._session_of_upload(
            version.owner_id, version.upload_ciphertext_digest
        )
        if session_id is None:
            # The upload already ended -- its own seven-day horizon, or an earlier deletion. The
            # version's ending is not blocked by content that is already gone.
            return
        self._content.delete_session_content(
            session_id=session_id, reason=self.REASON_IMMEDIATE, now=now
        )


__all__ = ["DeletionOutcome", "WorkspaceDeletion"]
