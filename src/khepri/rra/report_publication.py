"""Publish each durable report request as one opaque queue message.

PostgreSQL remains authoritative: the wrapped service creates or finds the
idempotent job first. Publication happens afterwards and on every repeated
request, so a caller retry repairs a failed send without creating another job.
The queue failure is never hidden as a successful HTTP request.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from khepri.rra.reports import ReportJobView, ReportRequestService
from khepri.rra.worker import ReportJobMessage


class ReportPublisher(Protocol):
    def publish(self, message: ReportJobMessage) -> str: ...


class QueuedReportRequestService:
    """Decorate session-scoped report requests with source-queue publication."""

    def __init__(
        self,
        *,
        requests: ReportRequestService,
        publisher: ReportPublisher,
    ) -> None:
        self._requests = requests
        self._publisher = publisher

    def request_session_report(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> tuple[ReportJobView, bool]:
        view, created = self._requests.request_session_report(
            session_id=session_id,
            now=now,
        )
        self._publisher.publish(ReportJobMessage(job_id=view.job.job_id))
        return view, created

    def get_session_job(
        self,
        *,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> ReportJobView | None:
        return self._requests.get_session_job(
            session_id=session_id,
            job_id=job_id,
            now=now,
        )


__all__ = ["QueuedReportRequestService", "ReportPublisher"]
