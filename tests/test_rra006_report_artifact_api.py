from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from khepri.rra.api import create_app
from khepri.rra.artifact_publication import ArtifactDocument, ArtifactUnavailable
from khepri.rra.report_api import _REPORT_REFUSALS, _refusal_for
from khepri.rra.reports import ReportServices
from tests.test_rra006_report_api import (
    NOW,
    FakeBundleService,
    FakeReportService,
    invitation_service,
)

ROUTES = {
    "/api/v1/beta/reports/job_alpha/surfaces/web/ar": "web_business_ar",
    "/api/v1/beta/reports/job_alpha/surfaces/web/en": "web_business_en",
    "/api/v1/beta/reports/job_alpha/surfaces/evidence/ar": "web_evidence_ar",
    "/api/v1/beta/reports/job_alpha/surfaces/evidence/en": "web_evidence_en",
    "/api/v1/beta/reports/job_alpha/surfaces/pdf/ar": "pdf_ar",
    "/api/v1/beta/reports/job_alpha/surfaces/pdf/en": "pdf_en",
    "/api/v1/beta/reports/job_alpha/surfaces/excel": "excel",
}


class Artifacts:
    def __init__(self) -> None:
        self.held: dict[tuple[str, str, str], ArtifactDocument] = {}
        self.error: Exception | None = None

    def get_session_artifact(
        self,
        *,
        session_id: str,
        job_id: str,
        artifact_kind: str,
        now: datetime,
    ) -> ArtifactDocument | None:
        if self.error is not None:
            raise self.error
        return self.held.get((session_id, job_id, artifact_kind))


def _harness(*, raise_server_exceptions: bool = True) -> tuple[TestClient, object, Artifacts]:
    invitations = invitation_service()
    artifacts = Artifacts()
    app = create_app(
        service=invitations,
        clock=lambda: NOW,
        report_services=ReportServices(
            jobs=FakeReportService(),
            bundles=FakeBundleService(),
            artifacts=artifacts,
        ),
    )
    client = TestClient(
        app,
        base_url="https://testserver",
        raise_server_exceptions=raise_server_exceptions,
    )
    return client, invitations, artifacts


def _redeem(client: TestClient, invitations) -> str:
    token = invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    return client.cookies["khepri_beta_session"]


def test_every_closed_artifact_route_returns_exact_bytes_and_private_headers() -> None:
    client, invitations, artifacts = _harness()
    session_id = _redeem(client, invitations)
    for route, kind in ROUTES.items():
        if kind.startswith("web_"):
            media_type = "text/html; charset=utf-8"
            file_name = "khepri-evidence.html" if "evidence" in kind else "khepri-report.html"
        elif kind.startswith("pdf_"):
            media_type, file_name = "application/pdf", "khepri-report.pdf"
        else:
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            file_name = "khepri-report.xlsx"
        artifacts.held[(session_id, "job_alpha", kind)] = ArtifactDocument(
            content=f"bytes:{kind}".encode(),
            media_type=media_type,
            file_name=file_name,
        )

        response = client.get(route)

        assert response.status_code == 200
        assert response.content == f"bytes:{kind}".encode()
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["content-disposition"] == f'attachment; filename="{file_name}"'


def test_artifact_routes_require_the_session_cookie() -> None:
    client, _, _ = _harness()
    response = client.get(next(iter(ROUTES)))
    assert response.status_code == 401
    assert response.json() == {"detail": "Session is unavailable."}


def test_foreign_and_unknown_artifacts_are_byte_identical_absences() -> None:
    client, invitations, artifacts = _harness()
    first = _redeem(client, invitations)
    artifacts.held[(first, "job_alpha", "excel")] = ArtifactDocument(
        content=b"xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_name="khepri-report.xlsx",
    )
    client.cookies.clear()
    _redeem(client, invitations)

    foreign = client.get("/api/v1/beta/reports/job_alpha/surfaces/excel")
    unknown = client.get("/api/v1/beta/reports/job_absent/surfaces/excel")

    assert foreign.status_code == 404
    assert foreign.content == unknown.content


def test_artifact_boundary_failures_are_one_generic_unavailability() -> None:
    client, invitations, artifacts = _harness()
    _redeem(client, invitations)
    artifacts.error = ArtifactUnavailable("provider/key detail")

    response = client.get("/api/v1/beta/reports/job_alpha/surfaces/excel")

    assert response.status_code == 503
    assert response.json() == {"detail": "Report artifact is unavailable."}
    assert "provider" not in response.text


@pytest.mark.parametrize(
    "kind",
    [kind for kind, _, _ in _REPORT_REFUSALS],
    ids=lambda kind: kind.__name__,
)
def test_artifact_routes_map_every_governed_refusal_through_the_table(
    kind: type[Exception],
) -> None:
    # Iterates the table rather than a literal list, so an entry added later is
    # covered without editing this test. The expectation is whatever
    # `_refusal_for` answers, so the route cannot keep a mapping of its own.
    client, invitations, artifacts = _harness()
    _redeem(client, invitations)
    artifacts.error = kind("A governed refusal sentence.")
    expected = _refusal_for(artifacts.error)

    response = client.get("/api/v1/beta/reports/job_alpha/surfaces/excel")

    assert (response.status_code, response.json()) == (
        expected.status_code,
        {"detail": expected.detail},
    )


class _Unexpected(Exception):
    """A failure no governed refusal names."""


def test_an_unmapped_artifact_failure_is_not_described_as_a_refusal() -> None:
    # `ReportArtifactPublisher.read` already turns every storage failure into
    # `ArtifactUnavailable`. Anything else reaching the route is a broken
    # reader, and it fails closed as a server error rather than being reported
    # to the caller as a governed unavailability -- and without its own text.
    client, invitations, artifacts = _harness(raise_server_exceptions=False)
    _redeem(client, invitations)
    artifacts.error = _Unexpected("private db detail")

    response = client.get("/api/v1/beta/reports/job_alpha/surfaces/excel")

    assert response.status_code == 500
    assert "private db detail" not in response.text
