"""Rewrite stored `v1` report artifacts as the envelope write version (#535).

`KHEPRI-DEC-028`, amended in #613: format `v1`, sealed without AAD, "stays readable until a
migration slice rewrites every `v1` object as `v2` and verifies that none remains." The owner
split that slice on 2026-09-28. This module is the report-artifact half.

**Why uploads are not here.** A re-seal produces a new ciphertext digest. An artifact's digest is
read by nothing outside `rra_report_artifacts`: its workspace binding records the *plaintext*
digest. An upload's ciphertext digest is recorded in `DatasetVersion.upload_ciphertext_digest`,
which `RCA-005` `FR-112` fixes, and three joins match on it. The owner chose to give versions a
stable upload identity before uploads are rewritten, so they are counted here and left alone.

**One row per transaction, session locked first.** `session_scope_for_update_statement` is the
lock `SqlDeletionRepository.begin` takes before it sets `deletion_requested_at`. So a deletion
cannot begin while an object is being rewritten, and one that already began is seen and deferred
to. The check happens before the artifact row is locked. Deletion removes artifact rows only after
it has set `deletion_requested_at`, so a migration that saw no request is never waiting on a row
a deletion holds, and a deletion is never waiting on a session this holds while holding a row.

**Every failure mode reads as not verified, never as done.** A row whose rewrite faulted stays
`v1` and is counted in `artifacts_remaining`. A crash between the object write and the row commit
leaves the object at `v2` under a `v1` row. That one artifact then reads as unavailable until the
next run adopts it. `EnvelopeMigrationReport.verified` is the only success.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Protocol

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.artifact_persistence import ReportArtifactRow
from khepri.rra.envelope import LEGACY_ENVELOPE_VERSION
from khepri.rra.persistence import (
    BetaSessionRow,
    UploadRow,
    session_scope_for_update_statement,
)
from khepri.rra.sessions import SessionScope, object_in_scope
from khepri.rra.storage import Resealed, StoredEnvelope

_LOG = logging.getLogger(__name__)

RESEALED = "resealed"
ADOPTED = "adopted"
DEFERRED = "deferred"
REFUSED = "refused"
FAILED = "failed"


class ResealingStore(Protocol):
    def reseal(self, key: str, *, envelope: StoredEnvelope, media_type: str) -> Resealed: ...


@dataclass(frozen=True, slots=True)
class EnvelopeMigrationReport:
    """What one pass did, in counts only. No identifier is echoed (`KHEPRI-DEC-015` §7)."""

    #: Rewritten as the write version by this pass.
    resealed: int = 0
    #: Already rewritten by a pass that stopped before its row committed; recorded, not rewritten.
    adopted: int = 0
    #: The session's deletion was requested or completed. The deletion removes the row.
    deferred: int = 0
    #: The row's key lies outside its own session's namespace. Left alone, object and row.
    refused: int = 0
    #: The rewrite raised. The row stays `v1`.
    failed: int = 0
    #: `v1` artifact rows after the pass. `v1` can only be retired from zero.
    artifacts_remaining: int = 0
    #: `v1` upload rows. Not this pass's to rewrite, so they do not decide `verified`.
    uploads_not_migrated: int = 0

    @property
    def verified(self) -> bool:
        """No `v1` artifact remains: `KHEPRI-DEC-028`'s "verifies that none remains".

        `failed` is deliberately not a second condition. A row whose rewrite faulted is still
        `v1`, so it is already counted in `artifacts_remaining`. A fault on a row that a
        concurrent deletion then removed leaves nothing to migrate, and that is done.
        """
        return self.artifacts_remaining == 0

    def as_counts(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _Candidate:
    job_id: str
    artifact_kind: str
    owner_id: str
    session_id: str

    @property
    def scope(self) -> SessionScope:
        return SessionScope(owner_id=self.owner_id, session_id=self.session_id)


class ArtifactEnvelopeMigration:
    """One pass over every `v1` report artifact."""

    def __init__(self, *, factory: sessionmaker[Session], objects: ResealingStore) -> None:
        self._factory = factory
        self._objects = objects

    def migrate(self) -> EnvelopeMigrationReport:
        tally: Counter[str] = Counter()
        for candidate in self._candidates():
            outcome = self._attempt(candidate)
            if outcome is not None:
                tally[outcome] += 1
        return EnvelopeMigrationReport(
            **tally,
            artifacts_remaining=self._legacy_count(ReportArtifactRow),
            uploads_not_migrated=self._legacy_count(UploadRow),
        )

    def _attempt(self, candidate: _Candidate) -> str | None:
        """Migrate one row, isolating its fault from every row after it.

        The exception's type is logged, never its message: a driver error echoes bound
        parameters, which here include an object key naming the owner and session.
        """
        try:
            return self._migrate(candidate)
        except Exception as fault:
            _LOG.error("envelope migration faulted on one artifact: error=%s", type(fault).__name__)
            return FAILED

    def _migrate(self, candidate: _Candidate) -> str | None:
        """`None` when there is nothing left to do: the row went or another pass moved it."""
        with self._factory.begin() as database:
            session = database.scalar(session_scope_for_update_statement(candidate.scope))
            if not _content_is_live(session):
                return DEFERRED
            row = database.scalar(_row_for_update(candidate))
            if row is None or row.envelope_version != LEGACY_ENVELOPE_VERSION:
                return None
            if not object_in_scope(candidate.scope, row.object_key):
                return REFUSED
            resealed = self._objects.reseal(
                row.object_key, envelope=_recorded(row), media_type=row.media_type
            )
            row.envelope_version = resealed.envelope_version
            row.ciphertext_sha256_hex = resealed.ciphertext_sha256_hex
            return RESEALED if resealed.rewritten else ADOPTED

    def _candidates(self) -> tuple[_Candidate, ...]:
        with self._factory() as database:
            rows = database.execute(
                select(
                    ReportArtifactRow.job_id,
                    ReportArtifactRow.artifact_kind,
                    ReportArtifactRow.owner_id,
                    ReportArtifactRow.session_id,
                )
                .where(ReportArtifactRow.envelope_version == LEGACY_ENVELOPE_VERSION)
                .order_by(ReportArtifactRow.job_id, ReportArtifactRow.artifact_kind)
            )
            return tuple(_Candidate(*row) for row in rows)

    def _legacy_count(self, model: type[ReportArtifactRow] | type[UploadRow]) -> int:
        with self._factory() as database:
            count = database.scalar(
                select(func.count())
                .select_from(model)
                .where(model.envelope_version == LEGACY_ENVELOPE_VERSION)
            )
            return int(count or 0)


def _content_is_live(session: BetaSessionRow | None) -> bool:
    if session is None:
        return False
    return (session.deletion_requested_at, session.content_deleted_at) == (None, None)


def _row_for_update(candidate: _Candidate) -> Select[tuple[ReportArtifactRow]]:
    """The candidate row, locked, and only while it still names the candidate's scope."""
    return (
        select(ReportArtifactRow)
        .where(
            ReportArtifactRow.job_id == candidate.job_id,
            ReportArtifactRow.artifact_kind == candidate.artifact_kind,
            ReportArtifactRow.owner_id == candidate.owner_id,
            ReportArtifactRow.session_id == candidate.session_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def _recorded(row: ReportArtifactRow) -> StoredEnvelope:
    return StoredEnvelope(
        ciphertext_sha256_hex=row.ciphertext_sha256_hex,
        sha256_hex=row.sha256_hex,
        encryption_algorithm=row.encryption_algorithm,
        envelope_version=row.envelope_version,
    )


__all__ = [
    "ArtifactEnvelopeMigration",
    "EnvelopeMigrationReport",
    "ResealingStore",
]
