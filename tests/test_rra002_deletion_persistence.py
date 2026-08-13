from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.artifact_persistence import ReportArtifactRow  # noqa: F401
from khepri.rra.deletion import DeletionEvidence
from khepri.rra.intake import CSV_MEDIA_TYPE, UploadMetadata
from khepri.rra.persistence import (
    Base,
    DeletionEvidenceRow,
    SqlDeletionRepository,
    SqlSessionStore,
    SqlUploadRepository,
    session_scope_for_update_statement,
)
from khepri.rra.sessions import (
    InvitationService,
    SessionExpired,
    SessionScope,
    require_upload_consent,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
CONTENT_DIGEST = "492d5ea496056f1a6a6592241032fab764c321596317930b4fa0e1e8bc3b7470"
LOCATION_DIGEST = "83390a61bb59fdbfad2f36666488f781ef73ddcf8042b4bd7315e82a535c1682"


def repositories() -> tuple[
    SqlSessionStore,
    SqlUploadRepository,
    SqlDeletionRepository,
]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    return (
        SqlSessionStore(factory),
        SqlUploadRepository(factory),
        SqlDeletionRepository(factory),
    )


def session_and_upload(
    sessions: SqlSessionStore,
    uploads: SqlUploadRepository,
) -> SessionScope:
    invitations = InvitationService(sessions)
    beta_session = invitations.redeem(
        invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)),
        now=NOW,
    )
    invitations.record_consent(
        beta_session.session_id,
        consent_version="beta-privacy-v1",
        now=NOW,
    )
    metadata = UploadMetadata(
        upload_id="upl_alpha",
        owner_id=beta_session.owner_id,
        session_id=beta_session.session_id,
        object_key=(
            f"owners/{beta_session.owner_id}/sessions/"
            f"{beta_session.session_id}/inputs/upl_alpha"
        ),
        size_bytes=8,
        sha256_hex=CONTENT_DIGEST,
        media_type=CSV_MEDIA_TYPE,
        created_at=NOW,
        expires_at=NOW + timedelta(days=7),
        encryption_algorithm="aws:kms",
        kms_key_id="kms-beta-content",
    )
    assert uploads.add_upload(metadata)
    return SessionScope(
        owner_id=beta_session.owner_id,
        session_id=beta_session.session_id,
    )


def evidence(*, outcome: str, attempt: int, evidence_id: str) -> DeletionEvidence:
    return DeletionEvidence(
        evidence_id=evidence_id,
        deletion_id="del_alpha",
        target_kind="input",
        target_id="upl_alpha",
        location_digest=LOCATION_DIGEST,
        content_digest=CONTENT_DIGEST,
        attempted_at=NOW + timedelta(minutes=attempt - 1),
        attempt_number=attempt,
        outcome=outcome,
        error_code="object_store_error" if outcome == "failed" else None,
    )


def test_sql_deletion_success_is_atomic_and_content_free() -> None:
    sessions, uploads, deletions = repositories()
    scope = session_and_upload(sessions, uploads)
    job = deletions.begin(
        scope=scope,
        deletion_id="del_alpha",
        reason="immediate",
        requested_at=NOW,
    )

    pending_session = sessions.get_session(scope.session_id)
    assert pending_session is not None
    assert pending_session.deletion_requested_at == NOW
    with pytest.raises(SessionExpired):
        require_upload_consent(pending_session, now=NOW)

    completed = deletions.complete(
        job=job,
        evidence=evidence(outcome="deleted", attempt=1, evidence_id="dev_success"),
        completed_at=NOW,
    )

    assert completed.state == "complete"
    assert uploads.get_upload_for_session(scope.session_id) is None
    deleted_session = sessions.get_session(scope.session_id)
    assert deleted_session is not None
    assert deleted_session.content_deleted_at == NOW
    assert deletions.list_evidence("del_alpha") == [
        evidence(outcome="deleted", attempt=1, evidence_id="dev_success")
    ]
    columns = inspect(DeletionEvidenceRow).columns
    assert "object_key" not in columns
    assert "filename" not in columns
    assert "error_message" not in columns
    assert "content" not in columns


def test_sql_deletion_failure_is_retryable_without_removing_metadata() -> None:
    sessions, uploads, deletions = repositories()
    scope = session_and_upload(sessions, uploads)
    job = deletions.begin(
        scope=scope,
        deletion_id="del_alpha",
        reason="immediate",
        requested_at=NOW,
    )

    retryable = deletions.fail(
        job=job,
        evidence=evidence(outcome="failed", attempt=1, evidence_id="dev_failed"),
        next_retry_at=NOW + timedelta(minutes=5),
    )

    assert retryable.state == "retryable"
    assert retryable.attempt_count == 1
    assert uploads.get_upload_for_session(scope.session_id) is not None
    assert deletions.list_evidence("del_alpha") == [
        evidence(outcome="failed", attempt=1, evidence_id="dev_failed")
    ]


def test_sql_deletion_begin_is_idempotent_for_the_session() -> None:
    sessions, uploads, deletions = repositories()
    scope = session_and_upload(sessions, uploads)
    first = deletions.begin(
        scope=scope,
        deletion_id="del_alpha",
        reason="immediate",
        requested_at=NOW,
    )

    second = deletions.begin(
        scope=scope,
        deletion_id="del_other",
        reason="expiry",
        requested_at=NOW + timedelta(minutes=1),
    )

    assert second == first


def test_late_failed_attempt_cannot_downgrade_completed_deletion() -> None:
    sessions, uploads, deletions = repositories()
    scope = session_and_upload(sessions, uploads)
    job = deletions.begin(
        scope=scope,
        deletion_id="del_alpha",
        reason="immediate",
        requested_at=NOW,
    )
    deleted = evidence(outcome="deleted", attempt=1, evidence_id="dev_deleted")
    completed = deletions.complete(
        job=job,
        evidence=deleted,
        completed_at=NOW,
    )

    result = deletions.fail(
        job=job,
        evidence=evidence(outcome="failed", attempt=1, evidence_id="dev_late"),
        next_retry_at=NOW + timedelta(minutes=5),
    )

    assert result == completed
    assert deletions.list_evidence(job.deletion_id) == [deleted]


def test_deletion_request_locks_the_exact_session_scope_on_postgresql() -> None:
    statement = session_scope_for_update_statement(
        SessionScope(owner_id="own_alpha", session_id="ses_alpha")
    )

    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "rra_beta_sessions.owner_id =" in sql
    assert "rra_beta_sessions.session_id =" in sql
    assert "FOR UPDATE" in sql
