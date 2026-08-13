from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from khepri.rra.intake import SessionReader
from khepri.rra.sessions import (
    SessionExpired,
    SessionScope,
    assert_same_scope,
)

_RETRY_DELAY = timedelta(minutes=5)
_REASONS = frozenset({"immediate", "expiry"})


class DeletionRetryRequired(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DeletionJob:
    deletion_id: str
    owner_id: str
    session_id: str
    reason: str
    state: str
    requested_at: datetime
    attempt_count: int
    last_attempt_at: datetime | None
    next_retry_at: datetime | None
    completed_at: datetime | None

    @property
    def scope(self) -> SessionScope:
        return SessionScope(owner_id=self.owner_id, session_id=self.session_id)


@dataclass(frozen=True, slots=True)
class DeletionEvidence:
    evidence_id: str
    deletion_id: str
    target_kind: str
    target_id: str
    location_digest: str
    content_digest: str
    attempted_at: datetime
    attempt_number: int
    outcome: str
    error_code: str | None


@dataclass(frozen=True, slots=True)
class DeletionTarget:
    target_kind: str
    target_id: str
    owner_id: str
    session_id: str
    object_key: str
    content_digest: str

    @property
    def scope(self) -> SessionScope:
        return SessionScope(owner_id=self.owner_id, session_id=self.session_id)


def evidence_tuple(
    evidence: DeletionEvidence | tuple[DeletionEvidence, ...] | None,
) -> tuple[DeletionEvidence, ...]:
    if evidence is None:
        return ()
    if isinstance(evidence, DeletionEvidence):
        return (evidence,)
    return evidence


def validate_completed_evidence(
    evidence: tuple[DeletionEvidence, ...],
    targets: tuple[DeletionTarget, ...],
) -> None:
    if not evidence:
        if targets:
            raise ValueError("Deletion evidence is required for an existing target.")
        return
    evidence_ids = {deletion_identity(item) for item in evidence}
    target_ids = {deletion_identity(item) for item in targets}
    if evidence_ids != target_ids:
        raise ValueError("Deletion evidence does not match every target.")
    if any(item.outcome != "deleted" for item in evidence):
        raise ValueError("Deletion evidence does not match every target.")


def deletion_identity(
    item: DeletionEvidence | DeletionTarget,
) -> tuple[str, str]:
    return item.target_kind, item.target_id


class DeletionRepository(Protocol):
    def begin(
        self,
        *,
        scope: SessionScope,
        deletion_id: str,
        reason: str,
        requested_at: datetime,
    ) -> DeletionJob: ...

    def get_targets(self, job: DeletionJob) -> tuple[DeletionTarget, ...]: ...

    def complete(
        self,
        *,
        job: DeletionJob,
        evidence: tuple[DeletionEvidence, ...],
        completed_at: datetime,
    ) -> DeletionJob: ...

    def fail(
        self,
        *,
        job: DeletionJob,
        evidence: tuple[DeletionEvidence, ...],
        next_retry_at: datetime,
    ) -> DeletionJob: ...


class DeletionObjectStore(Protocol):
    def abort_multipart_uploads(self, prefix: str) -> None: ...

    def delete(self, key: str) -> None: ...


class DeletionService:
    def __init__(
        self,
        *,
        sessions: SessionReader,
        deletions: DeletionRepository,
        objects: DeletionObjectStore,
        new_deletion_id: Callable[[], str] | None = None,
        new_evidence_id: Callable[[], str] | None = None,
    ) -> None:
        self._sessions = sessions
        self._deletions = deletions
        self._objects = objects
        self._new_deletion_id = new_deletion_id or (
            lambda: f"del_{secrets.token_urlsafe(18)}"
        )
        self._new_evidence_id = new_evidence_id or (
            lambda: f"dev_{secrets.token_urlsafe(18)}"
        )

    def delete_session_content(
        self,
        *,
        session_id: str,
        reason: str,
        now: datetime,
    ) -> DeletionJob:
        if reason not in _REASONS:
            raise ValueError("Deletion reason is invalid.")
        session = self._sessions.get_session(session_id)
        if session is None:
            raise SessionExpired("Session is unavailable.")
        scope = SessionScope(owner_id=session.owner_id, session_id=session.session_id)
        job = self._deletions.begin(
            scope=scope,
            deletion_id=self._new_deletion_id(),
            reason=reason,
            requested_at=now,
        )
        if job.state == "complete":
            return job
        targets = self._deletions.get_targets(job)
        if not targets:
            return self._deletions.complete(
                job=job,
                evidence=(),
                completed_at=now,
            )
        for target in targets:
            assert_same_scope(job.scope, target.scope)

        prefix = f"owners/{job.owner_id}/sessions/{job.session_id}/"
        evidence: list[DeletionEvidence] = []
        try:
            self._objects.abort_multipart_uploads(prefix)
        except Exception as error:
            evidence = [
                self._evidence(
                    job=job,
                    target=target,
                    attempted_at=now,
                    outcome="failed",
                    error_code="object_store_error",
                )
                for target in targets
            ]
            return self._retry_or_complete(
                job=job,
                evidence=tuple(evidence),
                now=now,
                error=error,
            )

        failed = False
        last_error: Exception | None = None
        for target in targets:
            try:
                self._objects.delete(target.object_key)
                outcome = "deleted"
                error_code = None
            except Exception as error:
                failed = True
                last_error = error
                outcome = "failed"
                error_code = "object_store_error"
            evidence.append(
                self._evidence(
                    job=job,
                    target=target,
                    attempted_at=now,
                    outcome=outcome,
                    error_code=error_code,
                )
            )
        if failed:
            assert last_error is not None
            return self._retry_or_complete(
                job=job,
                evidence=tuple(evidence),
                now=now,
                error=last_error,
            )
        return self._deletions.complete(
            job=job,
            evidence=tuple(evidence),
            completed_at=now,
        )

    def _retry_or_complete(
        self,
        *,
        job: DeletionJob,
        evidence: tuple[DeletionEvidence, ...],
        now: datetime,
        error: Exception,
    ) -> DeletionJob:
        result = self._deletions.fail(
            job=job,
            evidence=evidence,
            next_retry_at=now + _RETRY_DELAY,
        )
        if result.state == "complete":
            return result
        raise DeletionRetryRequired("Content deletion must be retried.") from error

    def _evidence(
        self,
        *,
        job: DeletionJob,
        target: DeletionTarget,
        attempted_at: datetime,
        outcome: str,
        error_code: str | None,
    ) -> DeletionEvidence:
        return DeletionEvidence(
            evidence_id=self._new_evidence_id(),
            deletion_id=job.deletion_id,
            target_kind=target.target_kind,
            target_id=target.target_id,
            location_digest=hashlib.sha256(target.object_key.encode()).hexdigest(),
            content_digest=target.content_digest,
            attempted_at=attempted_at,
            attempt_number=job.attempt_count + 1,
            outcome=outcome,
            error_code=error_code,
        )
