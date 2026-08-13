from __future__ import annotations

import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import select

from khepri.rra.artifact_persistence import ReportArtifactRow, SqlArtifactRepository
from khepri.rra.artifact_publication import ReportArtifactPublisher
from khepri.rra.deletion import DeletionRetryRequired, DeletionService, DeletionTarget
from khepri.rra.intake import CSV_MEDIA_TYPE, UploadMetadata
from khepri.rra.job_persistence import ReportJobRow
from khepri.rra.jobs import (
    DEAD_LETTER_CONTENT_DELETED,
    JOB_QUEUED,
    JOB_RETRYABLE,
    EnqueueJob,
    FailureRequest,
    LeaseAction,
    LeaseRequest,
)
from khepri.rra.persistence import (
    DeletionJobRow,
    SqlDeletionRepository,
    SqlSessionStore,
    SqlUploadRepository,
    _utc,
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


def test_sql_deletion_defers_while_a_report_publication_is_in_flight() -> None:
    test = harness()
    test.leased()
    objects = MemoryObjects()
    service = DeletionService(
        sessions=SqlSessionStore(test.factory),
        deletions=SqlDeletionRepository(test.factory),
        objects=objects,
        new_deletion_id=lambda: "del_alpha",
    )

    with pytest.raises(DeletionRetryRequired):
        service.delete_session_content(
            session_id=test.session.session_id,
            reason="immediate",
            now=NOW,
        )

    assert objects.aborted == []
    assert objects.deleted == []


@pytest.mark.parametrize("job_state", [JOB_QUEUED, JOB_RETRYABLE])
def test_sql_deletion_settles_an_unleased_report_before_cleanup(job_state: str) -> None:
    test = harness()
    queued_at = test.session.created_at
    deletion_at = queued_at + timedelta(minutes=3)
    test.jobs.enqueue(
        EnqueueJob(
            scope=test.scope,
            job_id="job_alpha",
            idempotency_key="c" * 64,
            queued_at=queued_at,
            max_attempts=3,
        )
    )
    if job_state == JOB_RETRYABLE:
        leased = test.jobs.lease(
            LeaseRequest(
                job_id="job_alpha",
                worker_id="worker_alpha",
                now=queued_at,
                lease_for=timedelta(minutes=1),
            )
        )
        assert leased is not None
        test.jobs.fail(
            FailureRequest(
                lease=LeaseAction(
                    job_id="job_alpha",
                    worker_id="worker_alpha",
                    now=queued_at,
                ),
                retry_at=queued_at + timedelta(minutes=2),
            )
        )
    objects = MemoryObjects()
    service = DeletionService(
        sessions=SqlSessionStore(test.factory),
        deletions=SqlDeletionRepository(test.factory),
        objects=objects,
        new_deletion_id=lambda: "del_alpha",
    )

    result = service.delete_session_content(
        session_id=test.session.session_id,
        reason="immediate",
        now=deletion_at,
    )

    assert result.state == "complete"
    with test.factory() as database:
        report = database.get(ReportJobRow, "job_alpha")
        assert report is not None
        assert report.state == "dead_lettered"
        assert report.dead_letter_reason == DEAD_LETTER_CONTENT_DELETED


def test_expired_final_publisher_is_drained_before_a_later_prefix_sweep() -> None:
    test = harness()
    queued_at = test.session.created_at
    test.jobs.enqueue(
        EnqueueJob(
            scope=test.scope,
            job_id="job_alpha",
            idempotency_key="d" * 64,
            queued_at=queued_at,
            max_attempts=1,
        )
    )
    leased = test.jobs.lease(
        LeaseRequest(
            job_id="job_alpha",
            worker_id="worker_alpha",
            now=queued_at,
            lease_for=timedelta(minutes=1),
        )
    )
    assert leased is not None
    expired_at = queued_at + timedelta(minutes=1)
    exhausted = test.jobs.recover_expired(now=expired_at)
    assert exhausted[0].state == "dead_lettered"
    objects = MemoryObjects()
    service = DeletionService(
        sessions=SqlSessionStore(test.factory),
        deletions=SqlDeletionRepository(test.factory),
        objects=objects,
        new_deletion_id=lambda: "del_alpha",
    )

    with pytest.raises(DeletionRetryRequired):
        service.delete_session_content(
            session_id=test.session.session_id,
            reason="immediate",
            now=expired_at,
        )
    late_key = (
        f"owners/{test.session.owner_id}/sessions/{test.session.session_id}/"
        "reports/late-attempt/web_business_en"
    )
    objects.values[late_key] = (b"late", "text/html", hashlib.sha256(b"late").hexdigest())
    with pytest.raises(DeletionRetryRequired):
        service.delete_session_content(
            session_id=test.session.session_id,
            reason="immediate",
            now=expired_at + timedelta(minutes=4),
        )

    result = service.delete_session_content(
        session_id=test.session.session_id,
        reason="immediate",
        now=expired_at + timedelta(minutes=5),
    )

    assert result.state == "complete"
    assert objects.values == {}


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
    test.jobs.complete(
        LeaseAction(job_id="job_alpha", worker_id="worker_alpha", now=NOW)
    )
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


def test_exhaustion_observed_after_the_saved_deadline_still_drains() -> None:
    """Deferring for a *running* worker must not spend that worker's drain interval.

    The first deferral is taken while the publisher still holds a live lease, so the
    deadline it records describes when to look again -- not a drain. If recovery only
    marks the job exhausted after that deadline has passed, the sweep that observes
    the terminal transition is the first one that could drain it, and it must start a
    fresh interval rather than treat the elapsed deadline as one already served.
    """
    test = harness()
    queued_at = test.session.created_at
    test.jobs.enqueue(
        EnqueueJob(
            scope=test.scope,
            job_id="job_alpha",
            idempotency_key="e" * 64,
            queued_at=queued_at,
            max_attempts=1,
        )
    )
    leased = test.jobs.lease(
        LeaseRequest(
            job_id="job_alpha",
            worker_id="worker_alpha",
            now=queued_at,
            lease_for=timedelta(minutes=30),
        )
    )
    assert leased is not None
    objects = MemoryObjects()
    service = DeletionService(
        sessions=SqlSessionStore(test.factory),
        deletions=SqlDeletionRepository(test.factory),
        objects=objects,
        new_deletion_id=lambda: "del_alpha",
    )

    # The publisher is still running, so deletion defers and records a deadline.
    with pytest.raises(DeletionRetryRequired):
        service.delete_session_content(
            session_id=test.session.session_id,
            reason="immediate",
            now=queued_at,
        )

    # The lease expires long after that deadline; this sweep is the first one that
    # can see the job as terminal.
    late = queued_at + timedelta(minutes=30)
    exhausted = test.jobs.recover_expired(now=late)
    assert exhausted[0].state == "dead_lettered"

    with pytest.raises(DeletionRetryRequired):
        service.delete_session_content(
            session_id=test.session.session_id,
            reason="immediate",
            now=late,
        )

    # The expired worker lands an in-flight write after that sweep. A drain that
    # started when exhaustion was observed still covers it.
    late_key = (
        f"owners/{test.session.owner_id}/sessions/{test.session.session_id}/"
        "reports/late-attempt/web_business_en"
    )
    objects.values[late_key] = (b"late", "text/html", hashlib.sha256(b"late").hexdigest())

    result = service.delete_session_content(
        session_id=test.session.session_id,
        reason="immediate",
        now=late + timedelta(minutes=5),
    )

    assert result.state == "complete"
    assert objects.values == {}


def test_the_drain_deferral_schedules_past_the_drain_it_is_waiting_on() -> None:
    """The recorded deadline must describe the drain, not the earlier deferral.

    `_needs_drain` refuses the sweep on its own, so a stale deadline cannot delete
    content early. It does decide when a poller returns, and a deadline left over
    from a deferral taken against a still-running publisher sends it back before
    the drain can possibly have run -- a wake-up that can only defer again.
    """
    test = harness()
    queued_at = test.session.created_at
    test.jobs.enqueue(
        EnqueueJob(
            scope=test.scope,
            job_id="job_alpha",
            idempotency_key="f" * 64,
            queued_at=queued_at,
            max_attempts=1,
        )
    )
    leased = test.jobs.lease(
        LeaseRequest(
            job_id="job_alpha",
            worker_id="worker_alpha",
            now=queued_at,
            lease_for=timedelta(minutes=30),
        )
    )
    assert leased is not None
    service = DeletionService(
        sessions=SqlSessionStore(test.factory),
        deletions=SqlDeletionRepository(test.factory),
        objects=MemoryObjects(),
        new_deletion_id=lambda: "del_alpha",
    )

    with pytest.raises(DeletionRetryRequired):
        service.delete_session_content(
            session_id=test.session.session_id,
            reason="immediate",
            now=queued_at,
        )

    late = queued_at + timedelta(minutes=30)
    test.jobs.recover_expired(now=late)
    with pytest.raises(DeletionRetryRequired):
        service.delete_session_content(
            session_id=test.session.session_id,
            reason="immediate",
            now=late,
        )

    with test.factory() as database:
        deletion = database.get(DeletionJobRow, "del_alpha")
        assert deletion is not None
        assert deletion.next_retry_at is not None
        assert _utc(deletion.next_retry_at) > late
