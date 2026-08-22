"""Encrypted publication and verified retrieval of complete report artifacts."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from khepri.rra.artifact_persistence import (
    ArtifactBoundary,
    ArtifactCorrupted,
    StoredArtifact,
)
from khepri.rra.envelope import ALGORITHM_AES_256_GCM, ENVELOPE_VERSION
from khepri.rra.intake import StoragePolicyViolation
from khepri.rra.pipeline import DeliveryRecord, ReportPublication
from khepri.rra.report_artifacts import ARTIFACT_METADATA, ArtifactPayload
from khepri.rra.storage import ObjectWrite, PutResult, StoredEnvelope

_ATTEMPT_ID = re.compile(r"^[0-9a-f]{32}$")


class ArtifactUnavailable(RuntimeError):
    """The artifact boundary failed without exposing storage or scope detail."""


@dataclass(frozen=True, slots=True)
class ArtifactDocument:
    content: bytes
    media_type: str
    file_name: str


@dataclass(frozen=True, slots=True)
class PublicationContext:
    boundary: ArtifactBoundary
    record: DeliveryRecord
    created_at: datetime
    attempt_id: str


@dataclass(frozen=True, slots=True)
class PublishedObject:
    artifact: StoredArtifact
    created: bool


class ArtifactObjectStore(Protocol):
    def put_or_verify(self, request: ObjectWrite) -> PutResult: ...

    def get(self, key: str, *, envelope: StoredEnvelope) -> bytes: ...

    def delete(self, key: str) -> None: ...


class DeliveryReader(Protocol):
    def find_delivery(self, job_id: str) -> DeliveryRecord | None: ...


class ArtifactRepository(Protocol):
    def has_complete(self, job_id: str) -> bool: ...

    def is_committed(self, artifacts: tuple[StoredArtifact, ...]) -> bool: ...

    def boundary(
        self,
        publication: ReportPublication,
        *,
        created_at: datetime,
    ) -> ArtifactBoundary: ...

    def commit(
        self,
        publication: ReportPublication,
        artifacts: tuple[StoredArtifact, ...],
        *,
        boundary: ArtifactBoundary,
        committed_at: datetime,
    ) -> DeliveryRecord: ...

    def find_in_session(
        self,
        *,
        session_id: str,
        job_id: str,
        artifact_kind: str,
        now: datetime,
    ) -> StoredArtifact | None: ...


class ReportArtifactPublisher:
    def __init__(
        self,
        *,
        repository: ArtifactRepository,
        deliveries: DeliveryReader,
        objects: ArtifactObjectStore,
        now: Callable[[], datetime],
    ) -> None:
        self._repository = repository
        self._deliveries = deliveries
        self._objects = objects
        self._now = now

    def find_delivery(self, job_id: str) -> DeliveryRecord | None:
        record = self._deliveries.find_delivery(job_id)
        if record is None:
            return None
        try:
            return record if self._repository.has_complete(job_id) else None
        except ArtifactCorrupted as error:
            raise ArtifactUnavailable("Report artifacts are unavailable.") from error

    def publish(self, publication: ReportPublication) -> DeliveryRecord:
        existing = self._existing(publication)
        if existing is not None:
            return existing
        return self._publish_new(publication)

    def _existing(self, publication: ReportPublication) -> DeliveryRecord | None:
        existing = self.find_delivery(publication.delivery.record.job_id)
        if existing is None:
            return None
        if existing.bundle_id != publication.delivery.record.bundle_id:
            raise ArtifactUnavailable("Report artifacts are unavailable.")
        return existing

    def _publish_new(self, publication: ReportPublication) -> DeliveryRecord:
        created_at = self._now()
        created_keys: list[str] = []
        try:
            boundary = self._repository.boundary(publication, created_at=created_at)
            context = PublicationContext(
                boundary=boundary,
                record=publication.delivery.record,
                created_at=created_at,
                attempt_id=_require_attempt_id(_new_attempt_id()),
            )
            artifacts = self._store_all(context, publication.artifacts, created_keys)
        except Exception as error:
            self._rollback(created_keys)
            raise ArtifactUnavailable("Report artifacts are unavailable.") from error
        return self._commit_or_reconcile(
            publication,
            artifacts,
            boundary=boundary,
            created_keys=created_keys,
        )

    def _commit_or_reconcile(
        self,
        publication: ReportPublication,
        artifacts: tuple[StoredArtifact, ...],
        *,
        boundary: ArtifactBoundary,
        created_keys: list[str],
    ) -> DeliveryRecord:
        try:
            return self._repository.commit(
                publication,
                artifacts,
                boundary=boundary,
                committed_at=self._now(),
            )
        except Exception as error:
            try:
                committed = self._repository.is_committed(artifacts)
            except Exception as reconciliation_error:
                raise ArtifactUnavailable(
                    "Report artifacts are unavailable."
                ) from reconciliation_error
            if committed:
                return publication.delivery.record
            self._rollback(created_keys)
            raise ArtifactUnavailable("Report artifacts are unavailable.") from error

    def _store_all(
        self,
        context: PublicationContext,
        payloads: tuple[ArtifactPayload, ...],
        created_keys: list[str],
    ) -> tuple[StoredArtifact, ...]:
        stored: list[StoredArtifact] = []
        for payload in payloads:
            published = self._store_one(context, payload)
            stored.append(published.artifact)
            if published.created:
                created_keys.append(published.artifact.object_key)
        return tuple(stored)

    def _store_one(
        self,
        context: PublicationContext,
        payload: ArtifactPayload,
    ) -> PublishedObject:
        key = _object_key(context, payload.kind)
        result = self._objects.put_or_verify(
            ObjectWrite(
                key=key,
                content=payload.content,
                media_type=payload.media_type,
                sha256_hex=payload.sha256_hex,
            )
        )
        _require_proven(result, key=key, publication=payload)
        return PublishedObject(
            artifact=_stored_artifact(context, payload, key, result),
            created=result.created,
        )

    def read(
        self,
        *,
        session_id: str,
        job_id: str,
        artifact_kind: str,
        now: datetime,
    ) -> ArtifactDocument | None:
        try:
            metadata = self._repository.find_in_session(
                session_id=session_id,
                job_id=job_id,
                artifact_kind=artifact_kind,
                now=now,
            )
            if metadata is None:
                return None
            return self._read_document(metadata)
        except ArtifactUnavailable:
            raise
        except Exception as error:
            raise ArtifactUnavailable("Report artifacts are unavailable.") from error

    def _read_document(self, metadata: StoredArtifact) -> ArtifactDocument:
        content = self._objects.get(
            metadata.object_key,
            envelope=StoredEnvelope(
                ciphertext_sha256_hex=metadata.ciphertext_sha256_hex,
                sha256_hex=metadata.sha256_hex,
                encryption_algorithm=metadata.encryption_algorithm,
                envelope_version=metadata.envelope_version,
            ),
        )
        _require_verified_content(metadata, content)
        return ArtifactDocument(
            content=content,
            media_type=metadata.media_type,
            file_name=metadata.file_name,
        )

    def _rollback(self, keys: list[str]) -> None:
        try:
            for key in reversed(keys):
                self._objects.delete(key)
        except Exception as error:
            raise ArtifactUnavailable("Report artifacts are unavailable.") from error


def _object_key(context: PublicationContext, artifact_kind: str) -> str:
    boundary = context.boundary
    return (
        f"owners/{boundary.owner_id}/sessions/{boundary.session_id}/reports/"
        f"{context.record.bundle_id}/attempts/{context.attempt_id}/{artifact_kind}"
    )



def _new_attempt_id() -> str:
    return uuid4().hex


def _require_attempt_id(attempt_id: str) -> str:
    if _ATTEMPT_ID.fullmatch(attempt_id) is None:
        raise ValueError("Publication attempt identity is invalid.")
    return attempt_id


def _stored_artifact(
    context: PublicationContext,
    payload: ArtifactPayload,
    key: str,
    result: PutResult,
) -> StoredArtifact:
    return StoredArtifact(
        job_id=context.record.job_id,
        artifact_kind=payload.kind,
        owner_id=context.boundary.owner_id,
        session_id=context.boundary.session_id,
        bundle_id=context.record.bundle_id,
        object_key=key,
        media_type=payload.media_type,
        file_name=payload.file_name,
        size_bytes=len(payload.content),
        sha256_hex=payload.sha256_hex,
        created_at=context.created_at,
        expires_at=context.boundary.expires_at,
        encryption_algorithm=result.stored.encryption_algorithm,
        envelope_version=result.stored.envelope_version,
        ciphertext_sha256_hex=result.stored.ciphertext_sha256_hex,
    )


def _require_verified_content(metadata: StoredArtifact, content: bytes) -> None:
    expected = (
        metadata.size_bytes,
        metadata.sha256_hex,
        (metadata.media_type, metadata.file_name),
    )
    actual = (
        len(content),
        hashlib.sha256(content).hexdigest(),
        ARTIFACT_METADATA.get(metadata.artifact_kind),
    )
    if actual != expected:
        raise ArtifactUnavailable("Report artifacts are unavailable.")


def _require_proven(
    result: PutResult,
    *,
    key: str,
    publication: ArtifactPayload,
) -> None:
    expected = (
        key,
        len(publication.content),
        publication.sha256_hex,
        publication.media_type,
        ALGORITHM_AES_256_GCM,
        ENVELOPE_VERSION,
    )
    actual = (
        result.stored.key,
        result.stored.size_bytes,
        result.stored.sha256_hex,
        result.stored.media_type,
        result.stored.encryption_algorithm,
        result.stored.envelope_version,
    )
    if actual != expected or len(result.stored.ciphertext_sha256_hex) != 64:
        raise StoragePolicyViolation("Object storage did not prove publication policy.")


__all__ = [
    "ArtifactDocument",
    "ArtifactUnavailable",
    "ReportArtifactPublisher",
]
