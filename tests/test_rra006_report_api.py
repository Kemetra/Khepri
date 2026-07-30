from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.api import create_app
from khepri.rra.bundle import (
    NARRATIVE_INCLUDED,
    REASON_BUNDLE_MISMATCH,
    REASON_DUPLICATE_SURFACE,
    REASON_MISSING_SURFACE,
    REASON_UNKNOWN_SURFACE,
    REQUIRED_SURFACES,
    SURFACE_EXCEL,
    SURFACE_PDF,
    SURFACE_WEB,
)
from khepri.rra.datasets import ProfileCorrupted
from khepri.rra.facts import PACKAGE_VERSION
from khepri.rra.jobs import (
    DEAD_LETTER_CONTENT_DELETED,
    DEAD_LETTER_RETRIES_EXHAUSTED,
    JOB_DEAD_LETTERED,
    JOB_QUEUED,
    JOB_RETRYABLE,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    ReportJob,
)
from khepri.rra.packages import PackageCorrupted, PackageRefused
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.pipeline import (
    REASON_PACKAGE_MISSING,
    REASON_STAGE_FAILED,
    DeliveryRecord,
)
from khepri.rra.reports import (
    DeliveredBundle,
    DeliveredSurface,
    DeliveryWithheld,
    ReportJobView,
    ReportPackageMissing,
    ReportServices,
    reconcile_delivery,
)
from khepri.rra.sessions import (
    ConsentRequired,
    CrossSessionAccessDenied,
    InvitationService,
    SessionExpired,
)

NOW = datetime(2026, 7, 30, 16, 0, tzinfo=UTC)
LATER = datetime(2026, 7, 30, 16, 5, tzinfo=UTC)
QUEUED_AT = "2026-07-30T16:00:00Z"
COMPLETED_AT = "2026-07-30T16:05:00Z"
POLL = "/api/v1/beta/reports/{job_id}"
BUNDLE = "/api/v1/beta/reports/{job_id}/bundle"


def report_job(
    job_id: str = "job_alpha",
    *,
    state: str = JOB_QUEUED,
    completed_at: datetime | None = None,
    dead_letter_reason: str | None = None,
) -> ReportJob:
    return ReportJob(
        job_id=job_id,
        owner_id="own_alpha",
        session_id="ses_alpha",
        idempotency_key="a" * 64,
        state=state,
        queued_at=NOW,
        available_at=NOW,
        attempt_count=0,
        max_attempts=3,
        lease_owner=None,
        lease_expires_at=None,
        completed_at=completed_at,
        dead_letter_reason=dead_letter_reason,
    )


def dead_lettered(
    *,
    reason: str = DEAD_LETTER_RETRIES_EXHAUSTED,
    stage_reason: str | None = None,
) -> ReportJobView:
    """A job the queue gave up on, as the store would hold it.

    The two reasons answer different questions and the store keeps both: the
    dead-letter reason says why the queue stopped retrying, the stage reason says
    what the last attempt failed on.
    """
    return ReportJobView(
        job=report_job(
            state=JOB_DEAD_LETTERED,
            completed_at=LATER,
            dead_letter_reason=reason,
        ),
        reason=stage_reason,
    )


def delivery(
    job_id: str = "job_alpha",
    *,
    session_id: str = "ses_alpha",
    bundle_id: str = "bundle_alpha",
) -> DeliveryRecord:
    return DeliveryRecord(
        job_id=job_id,
        session_id=session_id,
        bundle_id=bundle_id,
        package_version=PACKAGE_VERSION,
        narrative_state=NARRATIVE_INCLUDED,
        surfaces=REQUIRED_SURFACES,
    )


def stored_surfaces(
    *names: str,
    bundle_id: str = "bundle_alpha",
) -> tuple[DeliveredSurface, ...]:
    return tuple(DeliveredSurface(surface=name, bundle_id=bundle_id) for name in names)


def delivered_bundle(
    job_id: str = "job_alpha",
    *,
    session_id: str = "ses_alpha",
    stored: tuple[DeliveredSurface, ...] | None = None,
) -> DeliveredBundle:
    return DeliveredBundle(
        record=delivery(job_id, session_id=session_id),
        surfaces=stored_surfaces(*REQUIRED_SURFACES) if stored is None else stored,
    )


class FakeScopedStore[T]:
    """A store keyed by caller and job, the way both report contracts ask.

    Genuinely scoped rather than filtered afterwards: another caller's entry is
    absent from a lookup here, so a route that forgot to pass the caller's own
    session identifier could not pass these tests.
    """

    def __init__(self) -> None:
        self.held: dict[tuple[str, str], T] = {}
        self.error: Exception | None = None

    def read(self, session_id: str, job_id: str) -> T | None:
        if self.error is not None:
            raise self.error
        return self.held.get((session_id, job_id))

    def matching(self, session_id: str) -> T | None:
        if self.error is not None:
            raise self.error
        return next(
            (held for (owner, _), held in self.held.items() if owner == session_id),
            None,
        )


class FakeReportService:
    def __init__(self) -> None:
        self.store: FakeScopedStore[ReportJobView] = FakeScopedStore()
        self.created: list[str] = []

    def request_session_report(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> tuple[ReportJobView, bool]:
        existing = self.store.matching(session_id)
        if existing is not None:
            return existing, False
        job_id = f"job_{len(self.created) + 1}"
        self.created.append(job_id)
        view = ReportJobView(job=report_job(job_id))
        self.store.held[(session_id, job_id)] = view
        return view, True

    def get_session_job(
        self,
        *,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> ReportJobView | None:
        return self.store.read(session_id, job_id)


class FakeBundleService:
    def __init__(self) -> None:
        self.store: FakeScopedStore[DeliveredBundle] = FakeScopedStore()

    def get_session_bundle(
        self,
        *,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> DeliveredBundle | None:
        return self.store.read(session_id, job_id)


@dataclass
class Harness:
    client: TestClient
    invitations: InvitationService
    reports: FakeReportService
    bundles: FakeBundleService


def harness() -> Harness:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    invitations = InvitationService(SqlSessionStore(factory))
    reports = FakeReportService()
    bundles = FakeBundleService()
    app = create_app(
        service=invitations,
        clock=lambda: NOW,
        report_services=ReportServices(jobs=reports, bundles=bundles),
    )
    return Harness(
        client=TestClient(app, base_url="https://testserver"),
        invitations=invitations,
        reports=reports,
        bundles=bundles,
    )


def redeem_and_consent(test: Harness) -> str:
    token = test.invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    test.client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    consented = test.client.post(
        "/api/v1/beta/consent",
        json={"consent_version": "beta-privacy-v1"},
    )
    assert consented.status_code == 204
    return test.client.cookies["khepri_beta_session"]


def seed(test: Harness, session_id: str, view: ReportJobView) -> None:
    test.reports.store.held[(session_id, view.job.job_id)] = view


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("POST", "/api/v1/beta/reports", id="request-a-report"),
        pytest.param("GET", POLL.format(job_id="job_alpha"), id="poll-a-job"),
        pytest.param("GET", BUNDLE.format(job_id="job_alpha"), id="fetch-a-bundle"),
    ],
)
def test_every_report_route_requires_a_beta_session(method: str, path: str) -> None:
    test = harness()

    response = test.client.request(method, path, json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "Session is unavailable."}


def test_requesting_a_report_enqueues_a_job_for_the_published_package() -> None:
    test = harness()
    session_id = redeem_and_consent(test)

    response = test.client.post("/api/v1/beta/reports", json={})

    assert response.status_code == 201
    assert response.json() == {
        "job_id": "job_1",
        "state": JOB_QUEUED,
        "queued_at": QUEUED_AT,
        "completed_at": None,
        "bundle_id": None,
        "reason": None,
        "dead_letter_reason": None,
    }
    assert test.reports.created == ["job_1"]
    assert set(test.reports.store.held) == {(session_id, "job_1")}


def test_re_requesting_a_report_returns_the_same_job() -> None:
    test = harness()
    redeem_and_consent(test)
    first = test.client.post("/api/v1/beta/reports", json={})

    second = test.client.post("/api/v1/beta/reports", json={})

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    # The job the second call reports is the job the first call created, not a
    # second job that happens to look like it.
    assert test.reports.created == ["job_1"]


def test_unknown_report_request_fields_are_refused() -> None:
    test = harness()
    redeem_and_consent(test)

    response = test.client.post("/api/v1/beta/reports", json={"template": "quarterly"})

    assert response.status_code == 422
    assert test.reports.created == []


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(
            SessionExpired("Session content has expired."),
            (401, {"detail": "Session is unavailable."}),
            id="expired-session",
        ),
        pytest.param(
            CrossSessionAccessDenied("Resource is unavailable."),
            (401, {"detail": "Session is unavailable."}),
            id="foreign-session",
        ),
        pytest.param(
            ConsentRequired("Consent is required before upload."),
            (403, {"detail": "Consent is required before upload."}),
            id="unconsented-caller",
        ),
        pytest.param(
            ReportPackageMissing("No fact package is available for this session."),
            (404, {"detail": "No fact package is available for this session."}),
            id="no-published-package",
        ),
        pytest.param(
            PackageRefused("Stored package was published under a superseded version."),
            (409, {"detail": "Stored package was published under a superseded version."}),
            id="superseded-package",
        ),
        pytest.param(
            PackageCorrupted("Stored fact package does not match its digest."),
            (503, {"detail": "Stored fact package is unavailable."}),
            id="corrupt-package",
        ),
        pytest.param(
            ProfileCorrupted("Stored dataset profile does not match its digest."),
            (503, {"detail": "Stored fact package is unavailable."}),
            id="corrupt-profile",
        ),
    ],
)
def test_a_refusal_reaches_every_report_route_as_the_same_status(
    error: Exception,
    expected: tuple[int, dict[str, str]],
) -> None:
    test = harness()
    redeem_and_consent(test)
    test.reports.store.error = error
    test.bundles.store.error = error

    answers = [
        test.client.post("/api/v1/beta/reports", json={}),
        test.client.get(POLL.format(job_id="job_alpha")),
        test.client.get(BUNDLE.format(job_id="job_alpha")),
    ]

    assert [(answer.status_code, answer.json()) for answer in answers] == [expected] * 3
    assert test.reports.created == []


def test_polling_reports_the_governed_state_of_a_queued_job() -> None:
    test = harness()
    redeem_and_consent(test)
    created = test.client.post("/api/v1/beta/reports", json={})

    response = test.client.get(POLL.format(job_id=created.json()["job_id"]))

    assert response.status_code == 200
    assert response.json() == created.json()


def test_polling_an_unknown_job_is_a_not_found() -> None:
    test = harness()
    redeem_and_consent(test)

    response = test.client.get(POLL.format(job_id="job_absent"))

    assert response.status_code == 404
    assert response.json() == {"detail": "No report job is available for this session."}


@pytest.mark.parametrize(
    "template",
    [
        pytest.param(POLL, id="poll-a-job"),
        pytest.param(BUNDLE, id="fetch-a-bundle"),
    ],
)
def test_a_second_session_cannot_reach_another_callers_report(template: str) -> None:
    test = harness()
    first_session = redeem_and_consent(test)
    job_id = test.client.post("/api/v1/beta/reports", json={}).json()["job_id"]
    test.bundles.store.held[(first_session, job_id)] = delivered_bundle(
        job_id,
        session_id=first_session,
    )

    test.client.cookies.clear()
    second_session = redeem_and_consent(test)
    foreign = test.client.get(template.format(job_id=job_id))
    unknown = test.client.get(template.format(job_id="job_absent"))

    assert first_session != second_session
    assert foreign.status_code == 404
    # Byte-identical to an unknown identifier: a caller learns nothing about
    # whether another caller's report exists.
    assert foreign.content == unknown.content


@pytest.mark.parametrize(
    ("view", "expected"),
    [
        pytest.param(
            dead_lettered(stage_reason=REASON_PACKAGE_MISSING),
            {
                "reason": REASON_PACKAGE_MISSING,
                "dead_letter_reason": DEAD_LETTER_RETRIES_EXHAUSTED,
                "bundle_id": None,
                "completed_at": COMPLETED_AT,
            },
            id="dead-lettered-explains-itself-in-governed-words",
        ),
        pytest.param(
            dead_lettered(
                reason=DEAD_LETTER_CONTENT_DELETED,
                stage_reason="provider rejected the row for buyer.one@example.com",
            ),
            {
                "reason": REASON_STAGE_FAILED,
                "dead_letter_reason": DEAD_LETTER_CONTENT_DELETED,
                "bundle_id": None,
                "completed_at": COMPLETED_AT,
            },
            id="ungoverned-stage-reason-is-collapsed",
        ),
        pytest.param(
            ReportJobView(
                job=report_job(state=JOB_RUNNING),
                reason=REASON_PACKAGE_MISSING,
                delivery=delivery(),
            ),
            {
                "reason": None,
                "dead_letter_reason": None,
                "bundle_id": None,
                "completed_at": None,
            },
            id="unfinished-withholds-a-finished-jobs-detail",
        ),
        pytest.param(
            ReportJobView(
                job=report_job(state=JOB_RETRYABLE),
                reason=REASON_PACKAGE_MISSING,
                delivery=delivery(),
            ),
            {
                "reason": None,
                "dead_letter_reason": None,
                "bundle_id": None,
                "completed_at": None,
            },
            id="retrying-is-not-a-verdict-already-reached",
        ),
        pytest.param(
            ReportJobView(
                job=report_job(state=JOB_SUCCEEDED, completed_at=LATER),
                delivery=delivery(),
            ),
            {
                "reason": None,
                "dead_letter_reason": None,
                "bundle_id": "bundle_alpha",
                "completed_at": COMPLETED_AT,
            },
            id="succeeded-names-the-bundle-it-delivered",
        ),
    ],
)
def test_a_polled_job_reports_only_what_its_state_entitles_it_to(
    view: ReportJobView,
    expected: dict[str, str | None],
) -> None:
    test = harness()
    session_id = redeem_and_consent(test)
    seed(test, session_id, view)

    body = test.client.get(POLL.format(job_id="job_alpha")).json()

    assert body["state"] == view.job.state
    assert {key: body[key] for key in expected} == expected


@pytest.mark.parametrize(
    "view",
    [
        pytest.param(
            ReportJobView(job=report_job(state=JOB_SUCCEEDED, completed_at=LATER)),
            id="succeeded-without-a-delivery",
        ),
        pytest.param(
            ReportJobView(
                job=report_job(state=JOB_SUCCEEDED, completed_at=LATER),
                delivery=delivery("job_other"),
            ),
            id="delivery-naming-another-job",
        ),
        pytest.param(
            ReportJobView(job=report_job(state="paused")),
            id="ungoverned-state",
        ),
        pytest.param(
            ReportJobView(
                job=report_job(state=JOB_DEAD_LETTERED, completed_at=LATER),
                reason=REASON_PACKAGE_MISSING,
            ),
            id="dead-lettered-without-a-dead-letter-reason",
        ),
        pytest.param(
            dead_lettered(reason="gave_up"),
            id="ungoverned-dead-letter-reason",
        ),
        pytest.param(
            ReportJobView(
                job=report_job(
                    state=JOB_RUNNING,
                    dead_letter_reason=DEAD_LETTER_RETRIES_EXHAUSTED,
                )
            ),
            id="dead-letter-reason-on-a-live-job",
        ),
    ],
)
def test_a_job_whose_stored_evidence_contradicts_itself_is_unavailable(
    view: ReportJobView,
) -> None:
    test = harness()
    session_id = redeem_and_consent(test)
    seed(test, session_id, view)

    response = test.client.get(POLL.format(job_id="job_alpha"))

    assert response.status_code == 503
    assert response.json() == {"detail": "Report job state is unavailable."}


def test_fetching_a_delivered_bundle_names_every_surface_of_one_version() -> None:
    test = harness()
    session_id = redeem_and_consent(test)
    test.bundles.store.held[(session_id, "job_alpha")] = delivered_bundle(
        session_id=session_id
    )

    response = test.client.get(BUNDLE.format(job_id="job_alpha"))

    assert response.status_code == 200
    assert response.json() == {
        "job_id": "job_alpha",
        "bundle_id": "bundle_alpha",
        "package_version": PACKAGE_VERSION,
        "narrative_state": NARRATIVE_INCLUDED,
        "surfaces": list(REQUIRED_SURFACES),
    }


def test_fetching_a_bundle_before_one_is_delivered_is_a_not_found() -> None:
    test = harness()
    redeem_and_consent(test)

    response = test.client.get(BUNDLE.format(job_id="job_alpha"))

    assert response.status_code == 404
    assert response.json() == {
        "detail": "No delivered report is available for this session."
    }


@pytest.mark.parametrize(
    "stored",
    [
        pytest.param(stored_surfaces(SURFACE_WEB, SURFACE_PDF), id="partial-delivery"),
        pytest.param(
            stored_surfaces(SURFACE_WEB, SURFACE_PDF)
            + (DeliveredSurface(surface=SURFACE_EXCEL, bundle_id="bundle_other"),),
            id="mixture-of-versions",
        ),
    ],
)
def test_a_bundle_that_is_not_wholly_delivered_is_withheld(
    stored: tuple[DeliveredSurface, ...],
) -> None:
    test = harness()
    session_id = redeem_and_consent(test)
    test.bundles.store.held[(session_id, "job_alpha")] = delivered_bundle(
        session_id=session_id,
        stored=stored,
    )

    response = test.client.get(BUNDLE.format(job_id="job_alpha"))

    assert response.status_code == 503
    assert response.json() == {"detail": "Report bundle is unavailable."}


@pytest.mark.parametrize(
    ("job_id", "stored", "expected_reason"),
    [
        pytest.param(
            "job_alpha",
            stored_surfaces(SURFACE_WEB, SURFACE_PDF),
            REASON_MISSING_SURFACE,
            id="partial-delivery",
        ),
        pytest.param(
            "job_alpha",
            stored_surfaces(SURFACE_WEB, SURFACE_PDF, SURFACE_PDF, SURFACE_EXCEL),
            REASON_DUPLICATE_SURFACE,
            id="duplicate-surface",
        ),
        pytest.param(
            "job_alpha",
            stored_surfaces(*REQUIRED_SURFACES, "csv"),
            REASON_UNKNOWN_SURFACE,
            id="unknown-surface",
        ),
        pytest.param(
            "job_alpha",
            stored_surfaces(SURFACE_WEB, SURFACE_PDF)
            + (DeliveredSurface(surface=SURFACE_EXCEL, bundle_id="bundle_other"),),
            REASON_BUNDLE_MISMATCH,
            id="mixture-of-versions",
        ),
        pytest.param(
            "job_other",
            stored_surfaces(*REQUIRED_SURFACES),
            REASON_BUNDLE_MISMATCH,
            id="delivery-naming-another-job",
        ),
    ],
)
def test_an_unservable_delivery_is_withheld_for_a_governed_reason(
    job_id: str,
    stored: tuple[DeliveredSurface, ...],
    expected_reason: str,
) -> None:
    with pytest.raises(DeliveryWithheld) as refusal:
        reconcile_delivery(delivered_bundle(stored=stored), job_id=job_id)

    assert refusal.value.reason == expected_reason


def test_a_wholly_delivered_bundle_reconciles() -> None:
    reconcile_delivery(delivered_bundle(), job_id="job_alpha")
