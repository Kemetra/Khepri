"""Encrypted publication and verified retrieval of complete report artifacts."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from khepri.rra.artifact_persistence import (
    ArtifactBoundary,
    ArtifactConflict,
    ArtifactCorrupted,
    StoredArtifact,
)
from khepri.rra.intake import StoragePolicyViolation
from khepri.rra.pipeline import DeliveryRecord, ReportPublication
from khepri.rra.report_artifacts import ARTIFACT_METADATA, ArtifactPayload
from khepri.rra.storage import PutResult


class ArtifactUnavailable(RuntimeError):
    """The artifact boundary failed without exposing storage or scope detail."""


@dataclass(frozen=True, slots=True)
class ArtifactDocument:
    content: bytes
    media_type: str
    file_name: str


class ArtifactObjectStore(Protocol):
    def put_or_verify(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
        encryption_context: dict[str, str],
    ) -> PutResult: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class DeliveryReader(Protocol):
    def find_delivery(self, job_id: str) -> DeliveryRecord | None: ...


class ArtifactRepository(Protocol):
    def has_complete(self, job_id: str) -> bool: ...

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
        existing = self.find_delivery(publication.delivery.record.job_id)
        if existing is not None:
            if existing.bundle_id != publication.delivery.record.bundle_id:
                raise ArtifactUnavailable("Report artifacts are unavailable.")
            return existing

        created_at = self._now()
        created_keys: list[str] = []
        try:
            boundary = self._repository.boundary(publication, created_at=created_at)
            stored: list[StoredArtifact] = []
            for payload in publication.artifacts:
                key = (
                    f"owners/{boundary.owner_id}/sessions/{boundary.session_id}/reports/"
                    f"{publication.delivery.record.bundle_id}/{payload.kind}"
                )
                result = self._objects.put_or_verify(
                    key=key,
                    content=payload.content,
                    media_type=payload.media_type,
                    sha256_hex=payload.sha256_hex,
                    encryption_context={
                        "owner_id": boundary.owner_id,
                        "session_id": boundary.session_id,
                        "job_id": publication.delivery.record.job_id,
                        "bundle_id": publication.delivery.record.bundle_id,
                        "artifact_kind": payload.kind,
                    },
                )
                _require_proven(result, key=key, publication=payload)
                if result.created:
                    created_keys.append(key)
                stored.append(
                    StoredArtifact(
                        job_id=publication.delivery.record.job_id,
                        artifact_kind=payload.kind,
                        owner_id=boundary.owner_id,
                        session_id=boundary.session_id,
                        bundle_id=publication.delivery.record.bundle_id,
                        object_key=key,
                        media_type=payload.media_type,
                        file_name=payload.file_name,
                        size_bytes=len(payload.content),
                        sha256_hex=payload.sha256_hex,
                        created_at=created_at,
                        expires_at=boundary.expires_at,
                        encryption_algorithm=result.stored.encryption_algorithm,
                        kms_key_id=result.stored.kms_key_id,
                    )
                )
            return self._repository.commit(publication, tuple(stored))
        except (ArtifactConflict, ArtifactCorrupted, StoragePolicyViolation) as error:
            self._rollback(created_keys)
            raise ArtifactUnavailable("Report artifacts are unavailable.") from error
        except Exception as error:
            self._rollback(created_keys)
            raise ArtifactUnavailable("Report artifacts are unavailable.") from error

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
            content = self._objects.get(metadata.object_key)
            if (
                len(content) != metadata.size_bytes
                or hashlib.sha256(content).hexdigest() != metadata.sha256_hex
                or ARTIFACT_METADATA.get(metadata.artifact_kind)
                != (metadata.media_type, metadata.file_name)
            ):
                raise ArtifactUnavailable("Report artifacts are unavailable.")
            return ArtifactDocument(
                content=content,
                media_type=metadata.media_type,
                file_name=metadata.file_name,
            )
        except ArtifactUnavailable:
            raise
        except Exception as error:
            raise ArtifactUnavailable("Report artifacts are unavailable.") from error

    def _rollback(self, keys: list[str]) -> None:
        try:
            for key in reversed(keys):
                self._objects.delete(key)
        except Exception as error:
            raise ArtifactUnavailable("Report artifacts are unavailable.") from error


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
        "aws:kms",
    )
    actual = (
        result.stored.key,
        result.stored.size_bytes,
        result.stored.sha256_hex,
        result.stored.media_type,
        result.stored.encryption_algorithm,
    )
    if actual != expected or not result.stored.kms_key_id:
        raise StoragePolicyViolation("Object storage did not prove publication policy.")


__all__ = [
    "ArtifactDocument",
    "ArtifactUnavailable",
    "ReportArtifactPublisher",
]
