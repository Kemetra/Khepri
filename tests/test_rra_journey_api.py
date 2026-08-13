from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from khepri.rra.api import create_app
from khepri.rra.journey.routes import JourneyServices
from khepri.rra.journey.state import snapshot
from tests.test_rra006_report_api import invitation_service

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class Reader:
    def read(self, session_id: str, now: datetime):
        if session_id != "ses_alpha":
            return None
        return snapshot(
            content_expires_at=NOW + timedelta(days=7),
            consent_recorded=True,
            upload_present=True,
            profile_present=True,
            profile_admissible=True,
            row_count=42,
        )


def client() -> TestClient:
    app = create_app(
        service=invitation_service(),
        clock=lambda: NOW,
        journey_services=JourneyServices(reader=Reader()),
    )
    test = TestClient(app, base_url="https://testserver")
    test.cookies.set("khepri_beta_session", "ses_alpha", path="/api/v1/beta")
    return test


def test_journey_endpoint_returns_only_content_minimized_state() -> None:
    response = client().get("/api/v1/beta/journey")
    assert response.status_code == 200
    assert response.json()["step"] == "review"
    assert response.json()["row_count"] == 42
    assert response.headers["cache-control"] == "private, no-store"
    assert "object_key" not in response.text


def test_journey_endpoint_requires_a_usable_session() -> None:
    test = client()
    test.cookies.clear()
    response = test.get("/api/v1/beta/journey")
    assert response.status_code == 401
    assert response.json() == {"detail": "Session is unavailable."}
