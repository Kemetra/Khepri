from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.api import create_app
from khepri.rra.intake import (
    IntakeService,
    StoredObject,
)
from khepri.rra.persistence import Base, SqlSessionStore, SqlUploadRepository
from khepri.rra.sessions import InvitationService

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
CSV = b"date,revenue\n2026-01,1\n"


class KmsMemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
        encryption_context: dict[str, str],
    ) -> StoredObject:
        self.objects[key] = content
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256_hex=sha256_hex,
            media_type=media_type,
            encryption_algorithm="aws:kms",
            kms_key_id="kms-beta-content",
        )

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


def client_and_services() -> tuple[
    TestClient,
    InvitationService,
    SqlUploadRepository,
    KmsMemoryObjectStore,
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
    objects = KmsMemoryObjectStore()
    invitations = InvitationService(sessions)
    intake = IntakeService(
        sessions=sessions,
        uploads=uploads,
        objects=objects,
        new_upload_id=lambda: "upl_example",
    )
    app = create_app(
        service=invitations,
        intake_service=intake,
        clock=lambda: NOW,
    )
    return (
        TestClient(app, base_url="https://testserver"),
        invitations,
        uploads,
        objects,
    )


def redeem(client: TestClient, invitations: InvitationService) -> str:
    token = invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    response = client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    return response.cookies["khepri_beta_session"]


def consent(client: TestClient) -> None:
    response = client.post(
        "/api/v1/beta/consent",
        json={"consent_version": "beta-privacy-v1"},
    )
    assert response.status_code == 204


def test_upload_endpoint_requires_a_beta_session() -> None:
    client, _, _, _ = client_and_services()

    response = client.post("/api/v1/beta/uploads", content=CSV)

    assert response.status_code == 401
    assert response.json() == {"detail": "Session is unavailable."}


def test_upload_endpoint_requires_consent_before_storage() -> None:
    client, invitations, _, objects = client_and_services()
    redeem(client, invitations)

    response = client.post("/api/v1/beta/uploads", content=CSV)

    assert response.status_code == 403
    assert response.json() == {"detail": "Consent is required before upload."}
    assert objects.objects == {}


def test_upload_endpoint_ignores_declared_type_and_returns_governed_metadata() -> None:
    client, invitations, uploads, objects = client_and_services()
    session_id = redeem(client, invitations)
    consent(client)

    response = client.post(
        "/api/v1/beta/uploads",
        content=CSV,
        headers={"content-type": "application/pdf"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "upload_id": "upl_example",
        "size_bytes": 23,
        "sha256_hex": "c7ba25578e7a4da1612a90a32602fc7a207eb286f2f41ccf41e9607d10c96c90",
        "media_type": "text/csv",
        "expires_at": "2026-08-05T12:00:00Z",
    }
    stored = uploads.get_upload_for_session(session_id)
    assert stored is not None
    assert stored.owner_id.startswith("own_")
    assert objects.objects[stored.object_key] == CSV


def test_upload_endpoint_rejects_oversized_content_length_before_storage() -> None:
    client, invitations, _, objects = client_and_services()
    redeem(client, invitations)
    consent(client)

    response = client.post(
        "/api/v1/beta/uploads",
        content=b"small",
        headers={"content-length": str(50 * 1024 * 1024 + 1)},
    )

    assert response.status_code == 413
    assert objects.objects == {}


def test_upload_endpoint_rejects_malformed_content_without_storage() -> None:
    client, invitations, _, objects = client_and_services()
    redeem(client, invitations)
    consent(client)

    response = client.post(
        "/api/v1/beta/uploads",
        content=b'header,value\n"unterminated,1\n',
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Upload content is invalid or unsupported."}
    assert objects.objects == {}


def test_upload_endpoint_rejects_a_second_input_for_the_session() -> None:
    client, invitations, _, _ = client_and_services()
    redeem(client, invitations)
    consent(client)
    first = client.post("/api/v1/beta/uploads", content=CSV)

    second = client.post("/api/v1/beta/uploads", content=CSV)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "This beta session already has an upload."}
