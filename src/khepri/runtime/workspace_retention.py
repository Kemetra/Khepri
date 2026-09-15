"""Retention operations that join workspace records to RRA content.

The two packages deliberately do not import each other.  This composition layer
is therefore where a session becomes durable after its admitted upload is
recorded as an organization-owned dataset version.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, sessionmaker

from khepri.rca.workspace.audit import (
    ACTION_RETENTION_SWEPT,
    ACTOR_RETENTION,
    AuditActor,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.schema import DatasetVersionRow
from khepri.rca.workspace.unit_of_work import unit_of_work, writing
from khepri.rra.artifact_persistence import ReportArtifactRow
from khepri.rra.delivery_persistence import ReportDeliveryRow
from khepri.rra.persistence import BetaSessionRow, UploadRow

# A storage sentinel for DEC-033's deliberately unbounded active lifetime.  It
# is not a retention horizon: dataset/run deletion and organization closure are
# the ending triggers.  Keeping the existing non-null columns avoids teaching
# every beta consumer that its seven-day deadline may be absent.
WORKSPACE_CONTENT_END = datetime(9999, 12, 31, tzinfo=UTC)
RAW_UPLOAD_RETENTION = timedelta(days=7)


class _ObjectDeleter(Protocol):
    def delete(self, key: str) -> None: ...


@dataclass(frozen=True, slots=True)
class RawUploadPurgeReport:
    """What one pass purged, without exposing a customer identifier."""

    purged_uploads: int


@dataclass(frozen=True, slots=True)
class _RawUpload:
    upload_id: str
    owner_id: str
    object_key: str


def retain_workspace_content(
    factory: sessionmaker[Session], *, owner_id: str, session_id: str
) -> bool:
    """Move one live session's derived content from the beta timer to DEC-033.

    The write joins the caller's ambient workspace transaction.  A deletion
    already requested or completed is never revived.
    """
    with writing(factory) as database:
        session = database.scalar(
            select(BetaSessionRow).where(
                BetaSessionRow.owner_id == owner_id,
                BetaSessionRow.session_id == session_id,
            )
        )
        if session is None:
            return False
        if session.deletion_requested_at is not None:
            return False
        if session.content_deleted_at is not None:
            return False
        session.content_expires_at = WORKSPACE_CONTENT_END
        for row in (UploadRow, ReportDeliveryRow, ReportArtifactRow):
            database.execute(
                update(row)
                .where(row.owner_id == owner_id, row.session_id == session_id)
                .values(expires_at=WORKSPACE_CONTENT_END)
            )
        return True


class RawUploadRetentionSweeper:
    """Purge workspace upload bytes seven days after their version is sealed."""

    def __init__(
        self,
        *,
        factory: sessionmaker[Session],
        objects: _ObjectDeleter,
        audit: SqlWorkspaceAuditStore,
    ) -> None:
        self._factory = factory
        self._objects = objects
        self._audit = audit

    def sweep(self, *, now: datetime) -> RawUploadPurgeReport:
        grouped: dict[str, list[_RawUpload]] = defaultdict(list)
        for upload in self._due(now=now):
            grouped[upload.owner_id].append(upload)
        purged = sum(
            self._purge_scope(owner_id, uploads, now)
            for owner_id, uploads in grouped.items()
        )
        return RawUploadPurgeReport(purged_uploads=purged)

    def _purge_scope(
        self, owner_id: str, uploads: list[_RawUpload], now: datetime
    ) -> int:
        for upload in uploads:
            self._objects.delete(upload.object_key)
        with unit_of_work(self._factory):
            count = sum(self._delete_row(upload) for upload in uploads)
            if count:
                self._audit.record(
                    WorkspaceAuditEvent.completed(
                        AuditActor(owner_id=owner_id, actor_account_id=ACTOR_RETENTION),
                        ACTION_RETENTION_SWEPT,
                        None,
                        now=now,
                    )
                )
        return count

    def _delete_row(self, upload: _RawUpload) -> int:
        with writing(self._factory) as database:
            result = database.execute(
                delete(UploadRow).where(
                    UploadRow.upload_id == upload.upload_id,
                    UploadRow.owner_id == upload.owner_id,
                )
            )
            return result.rowcount or 0

    def _due(self, *, now: datetime) -> tuple[_RawUpload, ...]:
        horizon = now - RAW_UPLOAD_RETENTION
        with self._factory() as database:
            rows = database.execute(
                select(UploadRow.upload_id, UploadRow.owner_id, UploadRow.object_key)
                .join(
                    DatasetVersionRow,
                    (DatasetVersionRow.owner_id == UploadRow.owner_id)
                    & (
                        DatasetVersionRow.upload_ciphertext_digest
                        == UploadRow.ciphertext_sha256_hex
                    ),
                )
                .where(
                    DatasetVersionRow.sealed_at.is_not(None),
                    DatasetVersionRow.sealed_at <= horizon,
                )
                .order_by(UploadRow.owner_id, UploadRow.upload_id)
            )
            return tuple(_RawUpload(*row) for row in rows)


__all__ = [
    "RAW_UPLOAD_RETENTION",
    "WORKSPACE_CONTENT_END",
    "RawUploadPurgeReport",
    "RawUploadRetentionSweeper",
    "retain_workspace_content",
]
