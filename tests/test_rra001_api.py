from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.api import create_app
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.sessions import InvitationService

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def client_service_store() -> tuple[TestClient, InvitationService, SqlSessionStore]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    store = SqlSessionStore(sessionmaker(engine, expire_on_commit=False))
    service = InvitationService(store)
    app = create_app(service=service, clock=lambda: NOW)
    return TestClient(app, base_url="https://testserver"), service, store


def test_redeem_endpoint_creates_secure_pseudonymous_session_cookie() -> None:
    client, service, _ = client_service_store()
    token = service.issue_invitation(expires_at=NOW + timedelta(hours=1))

    response = client.post("/api/v1/beta/sessions/redeem", json={"token": token})

    assert response.status_code == 201
    assert response.json() == {
        "content_expires_at": "2026-08-05T12:00:00Z",
        "consent_required": True,
    }
    cookie = response.headers["set-cookie"]
    assert "khepri_beta_session=ses_" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert token not in response.text


def test_redeem_endpoint_returns_one_failure_for_invalid_invitation() -> None:
    client, _, _ = client_service_store()

    for token in ("malformed", ""):
        response = client.post(
            "/api/v1/beta/sessions/redeem",
            json={"token": token},
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invitation is invalid or unavailable."}


def test_consent_endpoint_requires_session_cookie() -> None:
    client, _, _ = client_service_store()

    response = client.post(
        "/api/v1/beta/consent",
        json={"consent_version": "beta-privacy-v1"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Session is unavailable."}


def test_consent_endpoint_records_version_for_redeemed_session() -> None:
    client, service, store = client_service_store()
    token = service.issue_invitation(expires_at=NOW + timedelta(hours=1))
    redeem = client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    session_id = redeem.cookies["khepri_beta_session"]

    response = client.post(
        "/api/v1/beta/consent",
        json={"consent_version": "beta-privacy-v1"},
    )

    assert response.status_code == 204
    session = store.get_session(session_id)
    assert session is not None
    assert session.consent_version == "beta-privacy-v1"
    assert session.consented_at == NOW
