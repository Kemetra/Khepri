from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import pytest
from sqlalchemy import select

from khepri.rra.artifact_persistence import ReportArtifactRow, SqlArtifactRepository
from khepri.rra.artifact_publication import (
    ArtifactUnavailable,
    ReportArtifactPublisher,
)
from khepri.rra.delivery_persistence import ReportDeliveryRow
from khepri.rra.intake import StoragePolicyViolation, StoredObject
from khepri.rra.storage import PutResult
from tests.test_rra006_artifact_persistence import _publication
from tests.test_rra006_delivery_persistence import NOW, harness


@dataclass
class MemoryObjects:
    fail_on: int | None = None
    values: dict[str, tuple[bytes, str, str]] = field(default_factory=dict)
    put_calls: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    aborted: list[str] = field(default_factory=list)

    def put_or_verify(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
        encryption_context: dict[str, str],
    ) -> PutResult:
        del encryption_context
        self.put_calls.append(key)
        if self.fail_on is not None and len(self.put_calls) == self.fail_on:
            raise StoragePolicyViolation("provider detail must not escape")
        existing = self.values.get(key)
        if existing is not None:
            if existing != (content, media_type, sha256_hex):
                raise StoragePolicyViolation("conflicting object")
            created = False
        else:
            self.values[key] = (content, media_type, sha256_hex)
            created = True
        return PutResult(
            stored=StoredObject(
                key=key,
                size_bytes=len(content),
                sha256_hex=sha256_hex,
                media_type=media_type,
                encryption_algorithm="aws:kms",
                kms_key_id="arn:aws:kms:me-central-1:123456789012:key/example",
            ),
            created=created,
        )

    def get(self, key: str) -> bytes:
        return self.values[key][0]

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.values.pop(key, None)

    def abort_multipart_uploads(self, prefix: str) -> None:
        self.aborted.append(prefix)


def _publisher(objects: MemoryObjects):
    test = harness()
    return (
        test,
        ReportArtifactPublisher(
            repository=SqlArtifactRepository(test.factory),
            deliveries=test.store,
            objects=objects,
            now=lambda: NOW,
        ),
    )


def test_publication_writes_seven_encrypted_objects_then_one_metadata_set() -> None:
    objects = MemoryObjects()
    test, publisher = _publisher(objects)
    publication = _publication(test)

    record = publisher.publish(publication)

    assert record == publication.delivery.record
    assert len(objects.values) == 7
    assert len(objects.put_calls) == 7
    with test.factory() as database:
        assert len(list(database.scalars(select(ReportDeliveryRow)))) == 1
        assert len(list(database.scalars(select(ReportArtifactRow)))) == 7


def test_committed_identical_retry_does_not_rewrite_objects() -> None:
    objects = MemoryObjects()
    test, publisher = _publisher(objects)
    publication = _publication(test)
    first = publisher.publish(publication)

    second = publisher.publish(publication)

    assert second == first
    assert len(objects.put_calls) == 7
    assert objects.deleted == []


def test_failure_on_artifact_four_removes_only_this_attempt_and_commits_nothing() -> None:
    objects = MemoryObjects(fail_on=4)
    test, publisher = _publisher(objects)
    publication = _publication(test)

    with pytest.raises(ArtifactUnavailable, match="unavailable") as raised:
        publisher.publish(publication)

    assert "provider" not in str(raised.value)
    assert len(objects.deleted) == 3
    assert objects.values == {}
    with test.factory() as database:
        assert list(database.scalars(select(ReportDeliveryRow))) == []
        assert list(database.scalars(select(ReportArtifactRow))) == []


def test_rollback_never_deletes_a_preexisting_verified_object() -> None:
    objects = MemoryObjects(fail_on=4)
    test, publisher = _publisher(objects)
    publication = _publication(test)
    first = publication.artifacts[0]
    first_key = (
        f"owners/{test.session.owner_id}/sessions/{test.session.session_id}/reports/"
        f"{publication.delivery.record.bundle_id}/{first.kind}"
    )
    objects.values[first_key] = (first.content, first.media_type, first.sha256_hex)

    with pytest.raises(ArtifactUnavailable):
        publisher.publish(publication)

    assert objects.deleted == [
        key for key in reversed(objects.put_calls[1:3])
    ]
    assert objects.values == {
        first_key: (first.content, first.media_type, first.sha256_hex)
    }


def test_metadata_failure_removes_all_objects_created_by_the_attempt() -> None:
    objects = MemoryObjects()
    test = harness()
    inner = SqlArtifactRepository(test.factory)

    class FailingRepository:
        def has_complete(self, job_id: str) -> bool:
            return inner.has_complete(job_id)

        def boundary(self, publication, *, created_at):
            return inner.boundary(publication, created_at=created_at)

        def commit(self, publication, artifacts):
            raise RuntimeError("database provider detail")

        def find_in_session(self, **details):
            return inner.find_in_session(**details)

    publisher = ReportArtifactPublisher(
        repository=FailingRepository(),
        deliveries=test.store,
        objects=objects,
        now=lambda: NOW,
    )

    with pytest.raises(ArtifactUnavailable, match="unavailable") as raised:
        publisher.publish(_publication(test))

    assert "database" not in str(raised.value)
    assert len(objects.deleted) == 7
    assert objects.values == {}


def test_verified_read_rechecks_digest_and_hides_storage_failures() -> None:
    objects = MemoryObjects()
    test, publisher = _publisher(objects)
    publication = _publication(test)
    publisher.publish(publication)
    document = publisher.read(
        session_id=test.session.session_id,
        job_id=publication.delivery.record.job_id,
        artifact_kind="excel",
        now=NOW,
    )
    assert document is not None
    assert document.content == publication.artifacts[-1].content
    assert document.file_name == "khepri-report.xlsx"

    excel_key = next(key for key in objects.values if key.endswith("/excel"))
    _, media_type, _ = objects.values[excel_key]
    objects.values[excel_key] = (
        b"tampered",
        media_type,
        hashlib.sha256(b"tampered").hexdigest(),
    )
    with pytest.raises(ArtifactUnavailable, match="unavailable"):
        publisher.read(
            session_id=test.session.session_id,
            job_id=publication.delivery.record.job_id,
            artifact_kind="excel",
            now=NOW,
        )


def test_foreign_session_cannot_resolve_an_object_key() -> None:
    objects = MemoryObjects()
    test, publisher = _publisher(objects)
    publication = _publication(test)
    publisher.publish(publication)

    assert publisher.read(
        session_id="ses_foreign",
        job_id=publication.delivery.record.job_id,
        artifact_kind="excel",
        now=NOW,
    ) is None
