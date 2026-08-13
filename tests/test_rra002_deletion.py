from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from khepri.rra.deletion import (
    DeletionEvidence,
    DeletionJob,
    DeletionRepository,
    DeletionRetryRequired,
    DeletionService,
    DeletionTarget,
)
from khepri.rra.intake import CSV_MEDIA_TYPE, UploadMetadata
from khepri.rra.sessions import (
    BetaSession,
    CrossSessionAccessDenied,
    SessionScope,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
LOCATION_DIGEST = "83390a61bb59fdbfad2f36666488f781ef73ddcf8042b4bd7315e82a535c1682"
CONTENT_DIGEST = "492d5ea496056f1a6a6592241032fab764c321596317930b4fa0e1e8bc3b7470"


def session() -> BetaSession:
    return BetaSession(
        owner_id="own_alpha",
        session_id="ses_alpha",
        created_at=NOW,
        content_expires_at=NOW + timedelta(days=7),
        consent_version="beta-privacy-v1",
        consented_at=NOW,
    )


def upload() -> UploadMetadata:
    return UploadMetadata(
        upload_id="upl_alpha",
        owner_id="own_alpha",
        session_id="ses_alpha",
        object_key="owners/own_alpha/sessions/ses_alpha/inputs/upl_alpha",
        size_bytes=8,
        sha256_hex=CONTENT_DIGEST,
        media_type=CSV_MEDIA_TYPE,
        created_at=NOW,
        expires_at=NOW + timedelta(days=7),
        encryption_algorithm="aws:kms",
        kms_key_id="kms-beta-content",
    )


class MemorySessionReader:
    def __init__(self, value: BetaSession) -> None:
        self.value = value

    def get_session(self, session_id: str) -> BetaSession | None:
        return self.value if session_id == self.value.session_id else None


class MemoryDeletionRepository(DeletionRepository):
    def __init__(self, target: UploadMetadata | None) -> None:
        self.target = target
        self.job: DeletionJob | None = None
        self.evidence: list[DeletionEvidence] = []

    def begin(
        self,
        *,
        scope: SessionScope,
        deletion_id: str,
        reason: str,
        requested_at: datetime,
    ) -> DeletionJob:
        if self.job is None:
            self.job = DeletionJob(
                deletion_id=deletion_id,
                owner_id=scope.owner_id,
                session_id=scope.session_id,
                reason=reason,
                state="pending",
                requested_at=requested_at,
                attempt_count=0,
                last_attempt_at=None,
                next_retry_at=None,
                completed_at=None,
            )
        return self.job

    def get_targets(self, job: DeletionJob) -> tuple[DeletionTarget, ...]:
        if self.target is None:
            return ()
        return (
            DeletionTarget(
                target_kind="input",
                target_id=self.target.upload_id,
                owner_id=self.target.owner_id,
                session_id=self.target.session_id,
                object_key=self.target.object_key,
                content_digest=self.target.sha256_hex,
            ),
        )

    def defer_for_publication(
        self,
        job: DeletionJob,
        *,
        now: datetime,
        next_retry_at: datetime,
    ) -> bool:
        return False

    def complete(
        self,
        *,
        job: DeletionJob,
        evidence: tuple[DeletionEvidence, ...],
        completed_at: datetime,
    ) -> DeletionJob:
        self.evidence.extend(evidence)
        self.target = None
        self.job = replace(
            job,
            state="complete",
            attempt_count=job.attempt_count + (1 if evidence else 0),
            last_attempt_at=completed_at if evidence else job.last_attempt_at,
            next_retry_at=None,
            completed_at=completed_at,
        )
        return self.job

    def fail(
        self,
        *,
        job: DeletionJob,
        evidence: tuple[DeletionEvidence, ...],
        next_retry_at: datetime,
    ) -> DeletionJob:
        self.evidence.extend(evidence)
        self.job = replace(
            job,
            state="retryable",
            attempt_count=job.attempt_count + 1,
            last_attempt_at=evidence[0].attempted_at,
            next_retry_at=next_retry_at,
        )
        return self.job


class MemoryDeletionObjectStore:
    def __init__(self, *, failures: int = 0, fail_keys: set[str] | None = None) -> None:
        self.failures = failures
        self.fail_keys = fail_keys or set()
        self.abort_prefixes: list[str] = []
        self.deleted_prefixes: list[str] = []
        self.deleted_keys: list[str] = []

    def abort_multipart_uploads(self, prefix: str) -> None:
        self.abort_prefixes.append(prefix)

    def delete_prefix(self, prefix: str) -> None:
        self.deleted_prefixes.append(prefix)

    def delete(self, key: str) -> None:
        self.deleted_keys.append(key)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("customer filename must never enter evidence")
        if key in self.fail_keys:
            self.fail_keys.discard(key)
            raise RuntimeError("customer filename must never enter evidence")


class ConcurrentCompletionRepository(MemoryDeletionRepository):
    def fail(
        self,
        *,
        job: DeletionJob,
        evidence: tuple[DeletionEvidence, ...],
        next_retry_at: datetime,
    ) -> DeletionJob:
        self.target = None
        self.job = replace(
            job,
            state="complete",
            attempt_count=1,
            last_attempt_at=evidence[0].attempted_at,
            next_retry_at=None,
            completed_at=evidence[0].attempted_at,
        )
        return self.job


class PublishingRepository(MemoryDeletionRepository):
    def defer_for_publication(
        self,
        job: DeletionJob,
        *,
        now: datetime,
        next_retry_at: datetime,
    ) -> bool:
        self.job = replace(job, state="retryable", next_retry_at=next_retry_at)
        return True


def service(
    repository: MemoryDeletionRepository,
    objects: MemoryDeletionObjectStore,
    *,
    beta_session: BetaSession | None = None,
) -> DeletionService:
    evidence_ids = iter(f"dev_{index}" for index in range(100))
    return DeletionService(
        sessions=MemorySessionReader(beta_session or session()),
        deletions=repository,
        objects=objects,
        new_deletion_id=lambda: "del_alpha",
        new_evidence_id=lambda: next(evidence_ids),
    )


def test_successful_deletion_records_only_content_free_evidence() -> None:
    repository = MemoryDeletionRepository(upload())
    objects = MemoryDeletionObjectStore()

    result = service(repository, objects).delete_session_content(
        session_id="ses_alpha",
        reason="immediate",
        now=NOW,
    )

    assert result.state == "complete"
    assert result.attempt_count == 1
    assert repository.target is None
    assert objects.abort_prefixes == ["owners/own_alpha/sessions/ses_alpha/"]
    assert objects.deleted_prefixes == ["owners/own_alpha/sessions/ses_alpha/"]
    assert objects.deleted_keys == [
        "owners/own_alpha/sessions/ses_alpha/inputs/upl_alpha"
    ]
    assert repository.evidence == [
        DeletionEvidence(
            evidence_id="dev_0",
            deletion_id="del_alpha",
            target_kind="input",
            target_id="upl_alpha",
            location_digest=LOCATION_DIGEST,
            content_digest=CONTENT_DIGEST,
            attempted_at=NOW,
            attempt_number=1,
            outcome="deleted",
            error_code=None,
        )
    ]


def test_in_flight_publication_defers_deletion_before_storage_sweep() -> None:
    repository = PublishingRepository(upload())
    objects = MemoryDeletionObjectStore()

    with pytest.raises(DeletionRetryRequired):
        service(repository, objects).delete_session_content(
            session_id="ses_alpha",
            reason="immediate",
            now=NOW,
        )

    assert repository.job is not None
    assert repository.job.state == "retryable"
    assert repository.job.next_retry_at == NOW + timedelta(minutes=5)
    assert objects.abort_prefixes == []
    assert objects.deleted_prefixes == []
    assert objects.deleted_keys == []
    assert repository.evidence == []


def test_completed_deletion_is_idempotent_without_repeating_storage_calls() -> None:
    repository = MemoryDeletionRepository(upload())
    objects = MemoryDeletionObjectStore()
    deletion = service(repository, objects)
    first = deletion.delete_session_content(
        session_id="ses_alpha",
        reason="immediate",
        now=NOW,
    )

    second = deletion.delete_session_content(
        session_id="ses_alpha",
        reason="immediate",
        now=NOW + timedelta(minutes=1),
    )

    assert second == first
    assert len(objects.deleted_keys) == 1
    assert len(repository.evidence) == 1


def test_failure_is_sanitized_and_a_later_attempt_can_complete() -> None:
    repository = MemoryDeletionRepository(upload())
    objects = MemoryDeletionObjectStore(failures=1)
    deletion = service(repository, objects)

    with pytest.raises(DeletionRetryRequired):
        deletion.delete_session_content(
            session_id="ses_alpha",
            reason="immediate",
            now=NOW,
        )

    assert repository.job is not None
    assert repository.job.state == "retryable"
    assert repository.job.next_retry_at == NOW + timedelta(minutes=5)
    assert repository.evidence[0].outcome == "failed"
    assert repository.evidence[0].error_code == "object_store_error"
    assert "filename" not in repr(repository.evidence[0])

    completed = deletion.delete_session_content(
        session_id="ses_alpha",
        reason="immediate",
        now=NOW + timedelta(minutes=5),
    )

    assert completed.state == "complete"
    assert completed.attempt_count == 2
    assert [item.outcome for item in repository.evidence] == ["failed", "deleted"]
    assert repository.target is None


def test_concurrent_completion_wins_over_a_late_storage_failure() -> None:
    repository = ConcurrentCompletionRepository(upload())
    objects = MemoryDeletionObjectStore(failures=1)

    result = service(repository, objects).delete_session_content(
        session_id="ses_alpha",
        reason="immediate",
        now=NOW,
    )

    assert result.state == "complete"
    assert repository.evidence == []


def test_cross_session_target_is_rejected_before_storage_access() -> None:
    repository = MemoryDeletionRepository(
        replace(upload(), owner_id="own_other", session_id="ses_other")
    )
    objects = MemoryDeletionObjectStore()

    with pytest.raises(CrossSessionAccessDenied):
        service(repository, objects).delete_session_content(
            session_id="ses_alpha",
            reason="immediate",
            now=NOW,
        )

    assert objects.abort_prefixes == []
    assert objects.deleted_keys == []
    assert repository.evidence == []


def test_session_without_content_completes_without_fabricated_evidence() -> None:
    repository = MemoryDeletionRepository(None)
    objects = MemoryDeletionObjectStore()

    result = service(repository, objects).delete_session_content(
        session_id="ses_alpha",
        reason="immediate",
        now=NOW,
    )

    assert result.state == "complete"
    assert result.attempt_count == 0
    assert repository.evidence == []
    assert objects.deleted_keys == []
    assert objects.deleted_prefixes == ["owners/own_alpha/sessions/ses_alpha/"]
