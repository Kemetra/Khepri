from __future__ import annotations

from datetime import UTC, datetime

import pytest

from khepri.rra.jobs import JOB_QUEUED, ReportJob
from khepri.rra.report_publication import QueuedReportRequestService
from khepri.rra.reports import ReportJobView
from khepri.rra.worker import ReportJobMessage

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def queued_view() -> ReportJobView:
    return ReportJobView(
        job=ReportJob(
            job_id="job_alpha",
            owner_id="own_alpha",
            session_id="ses_alpha",
            idempotency_key="ab" * 32,
            state=JOB_QUEUED,
            queued_at=NOW,
            available_at=NOW,
            attempt_count=0,
            max_attempts=3,
            lease_owner=None,
            lease_expires_at=None,
            completed_at=None,
            dead_letter_reason=None,
        )
    )


class RequestServiceStub:
    def __init__(self, *, created: bool = True) -> None:
        self.created = created
        self.requested: list[tuple[str, datetime]] = []
        self.read: list[tuple[str, str, datetime]] = []
        self.view = queued_view()

    def request_session_report(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> tuple[ReportJobView, bool]:
        self.requested.append((session_id, now))
        return self.view, self.created

    def get_session_job(
        self,
        *,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> ReportJobView | None:
        self.read.append((session_id, job_id, now))
        return self.view


class PublisherStub:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.messages: list[ReportJobMessage] = []

    def publish(self, message: ReportJobMessage) -> str:
        self.messages.append(message)
        if self.error is not None:
            raise self.error
        return "msg_alpha"


def service(
    requests: RequestServiceStub,
    publisher: PublisherStub,
) -> QueuedReportRequestService:
    return QueuedReportRequestService(requests=requests, publisher=publisher)


@pytest.mark.parametrize("created", [True, False])
def test_every_successful_request_publishes_the_opaque_job_id(created: bool) -> None:
    requests = RequestServiceStub(created=created)
    publisher = PublisherStub()

    result = service(requests, publisher).request_session_report(
        session_id="ses_alpha",
        now=NOW,
    )

    assert result == (requests.view, created)
    assert publisher.messages == [ReportJobMessage(job_id="job_alpha")]


def test_a_publication_failure_escapes_after_the_durable_request() -> None:
    requests = RequestServiceStub()
    publisher = PublisherStub(error=RuntimeError("queue unavailable"))

    with pytest.raises(RuntimeError, match="queue unavailable"):
        service(requests, publisher).request_session_report(
            session_id="ses_alpha",
            now=NOW,
        )

    assert requests.requested == [("ses_alpha", NOW)]
    assert publisher.messages == [ReportJobMessage(job_id="job_alpha")]


def test_job_reads_are_delegated_without_queue_side_effects() -> None:
    requests = RequestServiceStub()
    publisher = PublisherStub()

    found = service(requests, publisher).get_session_job(
        session_id="ses_alpha",
        job_id="job_alpha",
        now=NOW,
    )

    assert found is requests.view
    assert requests.read == [("ses_alpha", "job_alpha", NOW)]
    assert publisher.messages == []
