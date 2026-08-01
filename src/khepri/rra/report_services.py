"""Session-scoped adapters between the report routes and the stores.

**These close a real gap, not a local one.** `report_api` needs a
`ReportRequestService` and a `DeliveredBundleReader`, both keyed by the caller's
own session. `SqlReportJobRepository` speaks only the worker's language — every
method on it is a state transition (`enqueue`, `lease`, `complete`, `fail`) or a
recovery sweep, and there is no read-by-identifier at all, because until now
nothing needed one. `SqlDeliveryStore` is keyed by job alone and knows nothing
about sessions. So the report routes have never been served by anything but test
fakes, and the bridge is where session scoping and the package-exists
precondition live. That makes this isolation code, not glue.

**Absent, never forbidden.** Both readers return `None` for a job belonging to
another session, exactly as the Protocol docstrings require: `report_api._found`
turns that into the same 404 an unknown identifier gets, so no response can
confirm another caller's report exists.

**The idempotency key is the session's published package.** Re-requesting a report
for the same session and the same package returns the same job, which is what
`request_session_report` promises by reporting whether *this* call created it. A
key derived from a clock would make every poll a new report.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.delivery_persistence import SqlDeliveryStore
from khepri.rra.job_persistence import ReportJobRow, SqlReportJobRepository
from khepri.rra.jobs import EnqueueJob, ReportJob
from khepri.rra.packages import FactPackageRecord
from khepri.rra.reports import DeliveredBundle, ReportJobView, ReportPackageMissing
from khepri.rra.sessions import SessionScope

MAX_ATTEMPTS = 3


class SessionPackages(Protocol):
    """Where this session's published fact package is read from."""

    def get_session_package(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> FactPackageRecord | None: ...


class JobReader:
    """Read one job by identifier, which the worker-facing store does not offer.

    Kept apart from the two services because both need it and neither owns it.
    It reads `ReportJobRow` through the same factory the repository writes with,
    so a job is visible here exactly when it is committed there.
    """

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def find(self, job_id: str) -> ReportJob | None:
        with self._factory() as database:
            row = database.execute(
                select(ReportJobRow).where(ReportJobRow.job_id == job_id)
            ).scalar_one_or_none()
            return None if row is None else _job_from_row(row)

    def find_in_session(self, job_id: str, session_id: str) -> ReportJob | None:
        """The caller's own job, or nothing. Another session's job is nothing."""
        job = self.find(job_id)
        return None if job is None or job.session_id != session_id else job


class ReportRequestAdapter:
    """Ask for this session's report, or read one back, scoped to the caller."""

    def __init__(
        self,
        *,
        jobs: SqlReportJobRepository,
        reader: JobReader,
        packages: SessionPackages,
        deliveries: SqlDeliveryStore,
    ) -> None:
        self._jobs = jobs
        self._reader = reader
        self._packages = packages
        self._deliveries = deliveries

    def request_session_report(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> tuple[ReportJobView, bool]:
        record = self._packages.get_session_package(session_id=session_id, now=now)
        if record is None:
            # Nothing to report on. `report_api` maps this onto a 404 rather
            # than queueing a job whose only possible outcome is failure.
            raise ReportPackageMissing("No fact package is available for this session.")
        key = _idempotency_key(record.scope, record.package_digest)
        job_id = f"job_{key[:24]}"
        created = self._reader.find(job_id) is None
        job = self._jobs.enqueue(
            EnqueueJob(
                scope=record.scope,
                job_id=job_id,
                idempotency_key=key,
                queued_at=now,
                max_attempts=MAX_ATTEMPTS,
            )
        )
        return self._view(job), created

    def get_session_job(
        self,
        *,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> ReportJobView | None:
        job = self._reader.find_in_session(job_id, session_id)
        return None if job is None else self._view(job)

    def _view(self, job: ReportJob) -> ReportJobView:
        """One job beside the delivery record its state is checked against.

        The record is not optional decoration. `job_outcome` treats a succeeded
        job with no delivery as evidence contradicting itself and fails closed,
        so a view that omitted it would report every finished report as a 503.
        """
        return ReportJobView(job=job, delivery=self._deliveries.find_delivery(job.job_id))


class DeliveredBundleAdapter:
    """Read one delivered report back, scoped to the caller's own session."""

    def __init__(self, *, deliveries: SqlDeliveryStore, reader: JobReader) -> None:
        self._deliveries = deliveries
        self._reader = reader

    def get_session_bundle(
        self,
        *,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> DeliveredBundle | None:
        if self._reader.find_in_session(job_id, session_id) is None:
            return None
        record = self._deliveries.find_delivery(job_id)
        if record is None:
            return None
        return DeliveredBundle(
            record=record,
            surfaces=self._deliveries.find_surfaces(job_id),
        )


def _idempotency_key(scope: SessionScope, package_digest: str) -> str:
    """One key per session and published package, so a re-request is one job."""
    return hashlib.sha256(
        f"{scope.owner_id}|{scope.session_id}|{package_digest}".encode()
    ).hexdigest()


def _job_from_row(row: ReportJobRow) -> ReportJob:
    return ReportJob(
        job_id=row.job_id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        idempotency_key=row.idempotency_key,
        state=row.state,
        queued_at=row.queued_at,
        available_at=row.available_at,
        attempt_count=row.attempt_count,
        max_attempts=row.max_attempts,
        lease_owner=row.lease_owner,
        lease_expires_at=row.lease_expires_at,
        completed_at=row.completed_at,
        dead_letter_reason=row.dead_letter_reason,
    )


__all__ = [
    "MAX_ATTEMPTS",
    "JobReader",
    "DeliveredBundleAdapter",
    "ReportRequestAdapter",
    "SessionPackages",
]
