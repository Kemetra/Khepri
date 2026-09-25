from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
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


# --- #434 §7: every well-formed refusal pays the same one scrypt ----------------------------


def _unknown(service: InvitationService, client: TestClient) -> str:
    return "kiv1.inv_" + "A" * 24 + ".secret"


def _malformed(service: InvitationService, client: TestClient) -> str:
    return "not-a-token"


def _expired(service: InvitationService, client: TestClient) -> str:
    return service.issue_invitation(expires_at=NOW)


def _redeemed(service: InvitationService, client: TestClient) -> str:
    token = service.issue_invitation(expires_at=NOW + timedelta(hours=1))
    assert client.post("/api/v1/beta/sessions/redeem", json={"token": token}).status_code == 201
    return token


def _wrong_secret(service: InvitationService, client: TestClient) -> str:
    prefix, invitation_id, _secret = service.issue_invitation(
        expires_at=NOW + timedelta(hours=1)
    ).split(".")
    return f"{prefix}.{invitation_id}.not-the-secret"


@pytest.mark.parametrize(
    "token_for",
    [
        pytest.param(_unknown, id="unknown_invitation"),
        pytest.param(_malformed, id="malformed"),
        pytest.param(_expired, id="expired"),
        pytest.param(_redeemed, id="already_redeemed"),
        pytest.param(_wrong_secret, id="wrong_secret_control"),
    ],
)
def test_every_well_formed_refusal_pays_one_hash(token_for, monkeypatch) -> None:
    """`RRA-001`: a refusal must not reveal which check failed, and time is a channel.

    A wrong secret pays one scrypt. A malformed token, or an unknown, expired, or already redeemed
    invitation, used to short-circuit before the hash, so a caller could tell those apart by
    latency. The seam counts derivations rather than timing them.
    """
    client, service, _ = client_service_store()
    token = token_for(service, client)
    derivations: list[bytes] = []
    real_digest = InvitationService._digest

    def counting(secret: str, salt: bytes) -> bytes:
        derivations.append(salt)
        return real_digest(secret, salt)

    monkeypatch.setattr(InvitationService, "_digest", staticmethod(counting))

    response = client.post("/api/v1/beta/sessions/redeem", json={"token": token})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invitation is invalid or unavailable."}
    assert len(derivations) == 1, "each refusal must cost exactly one scrypt"
