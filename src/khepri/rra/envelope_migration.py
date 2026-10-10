"""Rewrite stored `v1` report artifacts as the envelope write version (#535).

`KHEPRI-DEC-028`, amended in #613: format `v1`, sealed without AAD, "stays readable until a
migration slice rewrites every `v1` object as `v2` and verifies that none remains." The owner
split that slice on 2026-09-28. This module is the report-artifact half.

**Why uploads are counted, not re-sealed.** A re-seal produces a new ciphertext digest. An
artifact's digest is read by nothing outside `rra_report_artifacts`: its workspace binding records
the *plaintext* digest. An upload's ciphertext digest is recorded in
`DatasetVersion.upload_ciphertext_digest`, which `RCA-005` `FR-112` fixes. Three joins matched on it
until `FR-259`-`FR-261` re-keyed them onto the version's stable `upload_id`. Re-sealing uploads is
a later, separately gated slice (`FR-263`), so they are counted here and left alone. A `v1` upload
still blocks "verified": `RRA-017` `FR-273` reports it only when both counts reach zero.

**One session at a time (`RRA-017` `FR-273`).** The one cross-scope read is the session listing,
`EnvelopeSessionLister`, which reads `rra_beta_sessions (session_id, owner_id)` and nothing else; in
the deployed command it runs on the sweep role's engine. Every candidate read, re-seal and count
then runs on the scoped engine with that session's `owner_id` set. The walk is complete because
both content tables key onto their session (`fk_report_artifact_session_scope`,
`fk_upload_session_scope`). A listed session whose `owner_id` is `''` cannot be read by any scoped
read (`FR-232`), so it is counted in `sessions_unscoped` and never as zero; a session whose reads
fault is counted in `sessions_faulted`. Either one blocks "verified".

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
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Protocol

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.artifact_persistence import ReportArtifactRow
from khepri.rra.envelope import LEGACY_ENVELOPE_VERSION
from khepri.rra.persistence import (
    BetaSessionRow,
    UploadRow,
    session_scope_for_update_statement,
)
from khepri.rra.scope import scoped_begin, scoped_read
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


class SessionLister(Protocol):
    def sessions(self) -> Sequence[tuple[str, str]]: ...


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
    #: `v1` upload rows. Not this pass's to rewrite (`FR-263`), but they block `verified`.
    uploads_not_migrated: int = 0
    #: Listed sessions whose `owner_id` is `''`: no scoped read can count them (`FR-273`).
    sessions_unscoped: int = 0
    #: Listed sessions whose candidate read or count raised: their counts are unknown.
    sessions_faulted: int = 0

    @property
    def verified(self) -> bool:
        """No `v1` row remains in any listed session (`KHEPRI-DEC-028`, `RRA-017` `FR-273`).

        `failed` is deliberately not a condition. A row whose rewrite faulted is still `v1`, so it
        is already counted in `artifacts_remaining`. A fault on a row that a concurrent deletion
        then removed leaves nothing to migrate, and that is done.
        """
        return (
            self.artifacts_remaining,
            self.uploads_not_migrated,
            self.sessions_unscoped,
            self.sessions_faulted,
        ) == (0, 0, 0, 0)

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


class EnvelopeSessionLister:
    """Every session, with its owner, across every scope (`RRA-017` `FR-273`).

    Reads `rra_beta_sessions.session_id` and `owner_id` and nothing else: the columns `FR-271`
    already grants the sweep role, through the `rra_sweep_read` policy it already holds.
    """

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def sessions(self) -> tuple[tuple[str, str], ...]:
        with self._factory() as database:
            rows = database.execute(
                select(BetaSessionRow.session_id, BetaSessionRow.owner_id).order_by(
                    BetaSessionRow.session_id
                )
            )
            return tuple((session_id, owner_id) for session_id, owner_id in rows)


class ArtifactEnvelopeMigration:
    """One pass over every listed session's `v1` report artifacts.

    `factory` is the scoped engine. `lister` reads across scopes; without one (SQLite, and the
    databases `FR-272` lets run as before) it lists through `factory`.
    """

    def __init__(
        self,
        *,
        factory: sessionmaker[Session],
        objects: ResealingStore,
        lister: SessionLister | None = None,
    ) -> None:
        self._factory = factory
        self._objects = objects
        self._lister = lister or EnvelopeSessionLister(factory)

    def migrate(self) -> EnvelopeMigrationReport:
        tally: Counter[str] = Counter()
        for session_id, owner_id in self._lister.sessions():
            if not owner_id:
                tally["sessions_unscoped"] += 1
                continue
            self._walk(SessionScope(owner_id=owner_id, session_id=session_id), tally)
        return EnvelopeMigrationReport(**tally)

    def _walk(self, scope: SessionScope, tally: Counter[str]) -> None:
        """One session's candidates and counts, its fault isolated from every session after it.

        What the session did before a fault stays counted. As in `_attempt`, the exception's type
        is logged, never its message.
        """
        try:
            for candidate in self._candidates(scope):
                outcome = self._attempt(candidate)
                if outcome is not None:
                    tally[outcome] += 1
            tally.update(self._legacy_counts(scope))
        except Exception as fault:
            _LOG.error("envelope migration faulted on one session: error=%s", type(fault).__name__)
            tally["sessions_faulted"] += 1

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
        with scoped_begin(self._factory, candidate.scope.owner_id) as database:
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

    def _candidates(self, scope: SessionScope) -> tuple[_Candidate, ...]:
        with scoped_read(self._factory, scope.owner_id) as database:
            rows = database.execute(
                select(
                    ReportArtifactRow.job_id,
                    ReportArtifactRow.artifact_kind,
                    ReportArtifactRow.owner_id,
                    ReportArtifactRow.session_id,
                )
                .where(*_legacy_in(ReportArtifactRow, scope))
                .order_by(ReportArtifactRow.job_id, ReportArtifactRow.artifact_kind)
            )
            return tuple(_Candidate(*row) for row in rows)

    def _legacy_counts(self, scope: SessionScope) -> Counter[str]:
        """The session's two `v1` counts, in one transaction with its scope set."""
        with scoped_read(self._factory, scope.owner_id) as database:
            return Counter(
                artifacts_remaining=_count(database, ReportArtifactRow, scope),
                uploads_not_migrated=_count(database, UploadRow, scope),
            )


_Content = type[ReportArtifactRow] | type[UploadRow]


def _legacy_in(model: _Content, scope: SessionScope) -> tuple[ColumnElement[bool], ...]:
    """`v1` rows of `model` in `scope`'s own session, named by both scope columns."""
    return (
        model.owner_id == scope.owner_id,
        model.session_id == scope.session_id,
        model.envelope_version == LEGACY_ENVELOPE_VERSION,
    )


def _count(database: Session, model: _Content, scope: SessionScope) -> int:
    statement = select(func.count()).select_from(model).where(*_legacy_in(model, scope))
    return int(database.scalar(statement) or 0)


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
    "EnvelopeSessionLister",
    "ResealingStore",
    "SessionLister",
]
