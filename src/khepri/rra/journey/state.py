"""Content-minimized, resumable state for the client journey."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.artifact_persistence import ReportArtifactRow
from khepri.rra.delivery_persistence import ReportDeliveryRow
from khepri.rra.job_persistence import ReportJobRow
from khepri.rra.jobs import JOB_STATES
from khepri.rra.persistence import (
    BetaSessionRow,
    DatasetProfileRow,
    FactPackageRow,
    UploadRow,
    _utc,
)
from khepri.rra.pipeline import GOVERNED_REASONS
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS

JOURNEY_STEPS = frozenset({"upload", "review", "processing", "report"})


@dataclass(frozen=True, slots=True)
class JourneySnapshot:
    step: str
    content_expires_at: datetime
    consent_recorded: bool
    upload_present: bool
    profile_present: bool
    profile_admissible: bool | None
    package_present: bool
    job_id: str | None
    job_state: str | None
    job_reason: str | None
    row_count: int | None
    generated_at: datetime | None
    bundle_complete: bool

    def __post_init__(self) -> None:
        if self.step not in JOURNEY_STEPS:
            raise ValueError("Journey step is not governed.")
        if self.job_state is not None and self.job_state not in JOB_STATES:
            raise ValueError("Journey job state is not governed.")
        if self.job_reason is not None and self.job_reason not in GOVERNED_REASONS:
            raise ValueError("Journey job reason is not governed.")
        if self.bundle_complete and (
            self.job_state != "succeeded" or self.step != "report"
        ):
            raise ValueError("A complete bundle requires a succeeded report step.")
        if self.profile_present is False and self.profile_admissible is not None:
            raise ValueError("Admissibility requires a profile.")
        if self.job_id is None and self.job_state is not None:
            raise ValueError("A job state requires a job identifier.")


def snapshot(
    *,
    content_expires_at: datetime,
    consent_recorded: bool = False,
    upload_present: bool = False,
    profile_present: bool = False,
    profile_admissible: bool | None = None,
    package_present: bool = False,
    job_id: str | None = None,
    job_state: str | None = None,
    job_reason: str | None = None,
    row_count: int | None = None,
    generated_at: datetime | None = None,
    bundle_complete: bool = False,
) -> JourneySnapshot:
    if bundle_complete and job_state == "succeeded":
        step = "report"
    elif package_present:
        step = "processing"
    elif profile_present:
        step = "review"
    else:
        step = "upload"
    return JourneySnapshot(
        step=step,
        content_expires_at=content_expires_at,
        consent_recorded=consent_recorded,
        upload_present=upload_present,
        profile_present=profile_present,
        profile_admissible=profile_admissible,
        package_present=package_present,
        job_id=job_id,
        job_state=job_state,
        job_reason=job_reason,
        row_count=row_count,
        generated_at=generated_at,
        bundle_complete=bundle_complete,
    )


class JourneyReader(Protocol):
    def read(self, session_id: str, now: datetime) -> JourneySnapshot | None: ...


class SqlJourneyReader:
    """Derive browser workflow state without selecting customer documents."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def read(self, session_id: str, now: datetime) -> JourneySnapshot | None:
        with self._factory() as database:
            session = database.get(BetaSessionRow, session_id)
            if session is None:
                return None
            expires_at = _utc(session.content_expires_at)
            if (
                expires_at is None
                or expires_at <= now
                or session.deletion_requested_at is not None
                or session.content_deleted_at is not None
            ):
                return None
            upload_present = _exists(database, UploadRow, session_id)
            profile = database.scalar(
                select(DatasetProfileRow).where(DatasetProfileRow.session_id == session_id)
            )
            package_present = _exists(database, FactPackageRow, session_id)
            job = database.scalar(
                select(ReportJobRow)
                .where(ReportJobRow.session_id == session_id)
                .order_by(ReportJobRow.queued_at.desc(), ReportJobRow.job_id.desc())
                .limit(1)
            )
            delivery = None if job is None else database.get(ReportDeliveryRow, job.job_id)
            artifact_count = 0
            if delivery is not None:
                artifact_count = int(
                    database.scalar(
                        select(func.count())
                        .select_from(ReportArtifactRow)
                        .where(
                            ReportArtifactRow.job_id == delivery.job_id,
                            ReportArtifactRow.bundle_id == delivery.bundle_id,
                        )
                    )
                    or 0
                )
            complete = bool(
                job is not None
                and job.state == "succeeded"
                and delivery is not None
                and artifact_count == len(REQUIRED_ARTIFACT_KINDS)
            )
            return snapshot(
                content_expires_at=expires_at,
                consent_recorded=session.consented_at is not None,
                upload_present=upload_present,
                profile_present=profile is not None,
                profile_admissible=None if profile is None else profile.admissible,
                package_present=package_present,
                job_id=None if job is None else job.job_id,
                job_state=None if job is None else job.state,
                row_count=None if profile is None else profile.row_count,
                generated_at=None if delivery is None else _utc(delivery.generated_at),
                bundle_complete=complete,
            )


def _exists(database: Session, model: type, session_id: str) -> bool:
    found = database.scalar(
        select(model.session_id).where(model.session_id == session_id)
    )
    return found is not None


__all__ = [
    "JOURNEY_STEPS",
    "JourneyReader",
    "JourneySnapshot",
    "SqlJourneyReader",
    "snapshot",
]
