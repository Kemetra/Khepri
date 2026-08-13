from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import select

from khepri.rra.artifact_persistence import ReportArtifactRow, SqlArtifactRepository
from khepri.rra.artifact_publication import ReportArtifactPublisher
from khepri.rra.deletion import DeletionRetryRequired, DeletionService, DeletionTarget
from khepri.rra.intake import CSV_MEDIA_TYPE, UploadMetadata
from khepri.rra.persistence import (
    SqlDeletionRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from tests.test_rra002_deletion import (
    NOW,
    MemoryDeletionObjectStore,
    MemoryDeletionRepository,
    MemorySessionReader,
    session,
)
from tests.test_rra006_artifact_persistence import _publication
from tests.test_rra006_artifact_publication import MemoryObjects
from tests.test_rra006_delivery_persistence import harness


def _targets() -> tuple[DeletionTarget, ...]:
    input_target = DeletionTarget(
        target_kind="input",
        target_id="upl_alpha",
        owner_id="own_alpha",
        session_id="ses_alpha",
        object_key="owners/own_alpha/sessions/ses_alpha/inputs/upl_alpha",
        content_digest="a" * 64,
    )
    artifacts = tuple(
        DeletionTarget(
            target_kind="report_artifact",
            target_id=kind,
            owner_id="own_alpha",
            session_id="ses_alpha",
            object_key=f"owners/own_alpha/sessions/ses_alpha/reports/{'b' * 64}/{kind}",
            content_digest=f"{index + 1:x}" * 64,
        )
        for index, kind in enumerate(REQUIRED_ARTIFACT_KINDS)
    )
    return (input_target, *artifacts)


class TargetsRepository(MemoryDeletionRepository):
    def __init__(self) -> None:
        super().__init__(None)
        self.targets = _targets()

    def get_targets(self, job):
        return self.targets

    def complete(self, *, job, evidence, completed_at):
        result = super().complete(job=job, evidence=evidence, completed_at=completed_at)
        self.targets = ()
        return result


def _service(repository: TargetsRepository, objects: MemoryDeletionObjectStore):
    evidence_ids = iter(f"dev_{index}" for index in range(100))
    return DeletionService(
        sessions=MemorySessionReader(session()),
        deletions=repository,
        objects=objects,
        new_deletion_id=lambda: "del_alpha",
        new_evidence_id=lambda: next(evidence_ids),
    )


def test_one_attempt_deletes_upload_and_all_seven_report_artifacts() -> None:
    repository = TargetsRepository()
    objects = MemoryDeletionObjectStore()

    result = _service(repository, objects).delete_session_content(
        session_id="ses_alpha", reason="immediate", now=NOW
    )

    assert result.state == "complete"
    assert objects.deleted_keys == [target.object_key for target in _targets()]
    assert len(repository.evidence) == 8
    assert {entry.attempt_number for entry in repository.evidence} == {1}
    assert [entry.target_kind for entry in repository.evidence] == [
        "input",
        *("report_artifact" for _ in range(7)),
    ]


def test_one_object_failure_keeps_metadata_retryable_then_finishes_safely() -> None:
    repository = TargetsRepository()
    fourth_key = _targets()[3].object_key
    objects = MemoryDeletionObjectStore(fail_keys={fourth_key})
    deletion = _service(repository, objects)

    with pytest.raises(DeletionRetryRequired):
        deletion.delete_session_content(
            session_id="ses_alpha", reason="immediate", now=NOW
        )

    assert repository.job is not None
    assert repository.job.state == "retryable"
    assert repository.targets == _targets()
    assert len(repository.evidence) == 8
    assert repository.evidence[3].outcome == "failed"

    completed = deletion.delete_session_content(
        session_id="ses_alpha",
        reason="immediate",
        now=NOW + timedelta(minutes=5),
    )

    assert completed.state == "complete"
    assert completed.attempt_count == 2
    assert repository.targets == ()
    assert {entry.attempt_number for entry in repository.evidence[8:]} == {2}


def test_sql_completion_removes_upload_and_artifact_metadata_together() -> None:
    test = harness()
    objects = MemoryObjects()
    publication = _publication(test)
    publisher = ReportArtifactPublisher(
        repository=SqlArtifactRepository(test.factory),
        deliveries=test.store,
        objects=objects,
        now=lambda: NOW,
    )
    publisher.publish(publication)
    input_content = b"date,revenue\n2026-01,1\n"
    input_key = (
        f"owners/{test.session.owner_id}/sessions/{test.session.session_id}/inputs/upl_alpha"
    )
    input_digest = hashlib.sha256(input_content).hexdigest()
    SqlUploadRepository(test.factory).add_upload(
        UploadMetadata(
            upload_id="upl_alpha",
            owner_id=test.session.owner_id,
            session_id=test.session.session_id,
            object_key=input_key,
            size_bytes=len(input_content),
            sha256_hex=input_digest,
            media_type=CSV_MEDIA_TYPE,
            created_at=NOW,
            expires_at=test.session.content_expires_at,
            encryption_algorithm="aws:kms",
            kms_key_id="arn:aws:kms:me-central-1:123456789012:key/example",
        )
    )
    objects.values[input_key] = (input_content, CSV_MEDIA_TYPE, input_digest)
    deletions = SqlDeletionRepository(test.factory)
    evidence_ids = iter(f"dev_{index}" for index in range(20))
    service = DeletionService(
        sessions=SqlSessionStore(test.factory),
        deletions=deletions,
        objects=objects,
        new_deletion_id=lambda: "del_alpha",
        new_evidence_id=lambda: next(evidence_ids),
    )

    result = service.delete_session_content(
        session_id=test.session.session_id,
        reason="immediate",
        now=NOW,
    )

    assert result.state == "complete"
    assert len(deletions.list_evidence("del_alpha")) == 8
    assert objects.values == {}
    with test.factory() as database:
        assert list(database.scalars(select(ReportArtifactRow))) == []
    assert SqlUploadRepository(test.factory).get_upload_for_session(
        test.session.session_id
    ) is None
