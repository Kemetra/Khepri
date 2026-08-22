from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.api import create_app
from khepri.rra.artifact_persistence import ReportArtifactRow  # noqa: F401
from khepri.rra.deletion import DeletionService
from khepri.rra.intake import IntakeService, StoredObject
from khepri.rra.persistence import (
    Base,
    SqlDeletionRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.sessions import InvitationService

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
CSV = b"date,revenue\n2026-01,1\n"


class LifecycleMemoryObjectStore:
    def __init__(self, *, delete_failures: int = 0) -> None:
        self.delete_failures = delete_failures
        self.objects: dict[str, bytes] = {}
        self.abort_prefixes: list[str] = []

    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
    ) -> StoredObject:
        self.objects[key] = content
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256_hex=sha256_hex,
            media_type=media_type,
            encryption_algorithm="AES-256-GCM",
            envelope_version=1,
            ciphertext_sha256_hex="c" * 64,
        )

    def abort_multipart_uploads(self, prefix: str) -> None:
        self.abort_prefixes.append(prefix)

    def delete_prefix(self, prefix: str) -> None:
        for key in tuple(self.objects):
            if key.startswith(prefix):
                self.objects.pop(key)

    def delete(self, key: str) -> None:
        if self.delete_failures:
            self.delete_failures -= 1
            raise RuntimeError("private object detail")
        self.objects.pop(key, None)


def client_and_repositories(
    *,
    delete_failures: int = 0,
    clock_offset: Callable[[], timedelta] = lambda: timedelta(0),
) -> tuple[
    TestClient,
    InvitationService,
    SqlUploadRepository,
    SqlDeletionRepository,
    LifecycleMemoryObjectStore,
]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    sessions = SqlSessionStore(factory)
    uploads = SqlUploadRepository(factory)
    deletions = SqlDeletionRepository(factory)
    objects = LifecycleMemoryObjectStore(delete_failures=delete_failures)
    invitations = InvitationService(sessions)
    intake = IntakeService(
        sessions=sessions,
        uploads=uploads,
        objects=objects,
        new_upload_id=lambda: "upl_example",
    )
    evidence_ids = iter(("dev_example", "dev_retry", "dev_third"))
    deletion = DeletionService(
        sessions=sessions,
        deletions=deletions,
        objects=objects,
        new_deletion_id=lambda: "del_example",
        new_evidence_id=lambda: next(evidence_ids),
    )
    app = create_app(
        service=invitations,
        intake_service=intake,
        deletion_service=deletion,
        clock=lambda: NOW + clock_offset(),
    )
    return (
        TestClient(app, base_url="https://testserver"),
        invitations,
        uploads,
        deletions,
        objects,
    )


def redeem_and_consent(
    client: TestClient,
    invitations: InvitationService,
) -> str:
    token = invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    redeemed = client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    session_id = redeemed.cookies["khepri_beta_session"]
    consented = client.post(
        "/api/v1/beta/consent",
        json={"consent_version": "beta-privacy-v1"},
    )
    assert consented.status_code == 204
    return session_id


def test_delete_content_requires_a_beta_session() -> None:
    client, _, _, _, _ = client_and_repositories()

    response = client.delete("/api/v1/beta/content")

    assert response.status_code == 401
    assert response.json() == {"detail": "Session is unavailable."}


def test_delete_content_removes_input_and_clears_session_cookie() -> None:
    client, invitations, uploads, deletions, objects = client_and_repositories()
    session_id = redeem_and_consent(client, invitations)
    uploaded = client.post("/api/v1/beta/uploads", content=CSV)
    assert uploaded.status_code == 201

    response = client.delete("/api/v1/beta/content")

    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert uploads.get_upload_for_session(session_id) is None
    assert objects.objects == {}
    evidence = deletions.list_evidence("del_example")
    assert len(evidence) == 1
    assert evidence[0].outcome == "deleted"


def test_delete_failure_returns_retryable_response_without_private_detail() -> None:
    elapsed: list[timedelta] = []
    client, invitations, uploads, deletions, objects = client_and_repositories(
        delete_failures=1,
        clock_offset=lambda: sum(elapsed, timedelta(0)),
    )
    session_id = redeem_and_consent(client, invitations)
    client.post("/api/v1/beta/uploads", content=CSV)

    failed = client.delete("/api/v1/beta/content")

    assert failed.status_code == 503
    assert failed.json() == {"detail": "Content deletion is pending retry."}
    assert "private object detail" not in failed.text
    assert uploads.get_upload_for_session(session_id) is not None
    assert deletions.list_evidence("del_example")[0].error_code == "object_store_error"

    # Immediately: the failure path scheduled the next attempt, and reaching the
    # object store before that deadline would defeat the backoff it just recorded.
    too_soon = client.delete("/api/v1/beta/content")

    assert too_soon.status_code == 503
    assert uploads.get_upload_for_session(session_id) is not None
    assert len(deletions.list_evidence("del_example")) == 1

    elapsed.append(timedelta(minutes=5))
    completed = client.delete("/api/v1/beta/content")

    assert completed.status_code == 204
    assert uploads.get_upload_for_session(session_id) is None
    assert objects.objects == {}


def test_deletion_request_makes_the_session_terminal_for_future_uploads() -> None:
    client, invitations, _, _, _ = client_and_repositories(delete_failures=1)
    session_id = redeem_and_consent(client, invitations)
    client.post("/api/v1/beta/uploads", content=CSV)
    failed = client.delete("/api/v1/beta/content")
    assert failed.status_code == 503

    client.cookies.set("khepri_beta_session", session_id)
    response = client.post("/api/v1/beta/uploads", content=CSV)

    assert response.status_code == 401
    assert response.json() == {"detail": "Session is unavailable."}
