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
        _validate_governed_state(self)
        _validate_bundle_state(self)
        _validate_profile_state(self)
        _validate_job_identity(self)


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
    return JourneySnapshot(
        step=_journey_step(
            bundle_complete=bundle_complete,
            job_state=job_state,
            package_present=package_present,
            profile_present=profile_present,
        ),
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
            live = _live_session(database, session_id, now)
            if live is None:
                return None
            session, expires_at = live
            profile = _profile(database, session_id)
            job = _latest_job(database, session_id)
            delivery = _delivery(database, job)
            return snapshot(
                content_expires_at=expires_at,
                consent_recorded=session.consented_at is not None,
                upload_present=_exists(database, UploadRow, session_id),
                profile_present=profile is not None,
                profile_admissible=None if profile is None else profile.admissible,
                package_present=_exists(database, FactPackageRow, session_id),
                job_id=None if job is None else job.job_id,
                job_state=None if job is None else job.state,
                row_count=None if profile is None else profile.row_count,
                generated_at=None if delivery is None else _utc(delivery.generated_at),
                bundle_complete=_bundle_complete(database, job, delivery),
            )


def _validate_governed_state(state: JourneySnapshot) -> None:
    _validate_optional_member(
        state.step,
        JOURNEY_STEPS,
        "Journey step is not governed.",
    )
    _validate_optional_member(
        state.job_state,
        JOB_STATES,
        "Journey job state is not governed.",
    )
    _validate_optional_member(
        state.job_reason,
        GOVERNED_REASONS,
        "Journey job reason is not governed.",
    )


def _validate_optional_member(
    value: str | None,
    allowed: frozenset[str],
    message: str,
) -> None:
    if value is None:
        return
    if value not in allowed:
        raise ValueError(message)


def _validate_bundle_state(state: JourneySnapshot) -> None:
    if not state.bundle_complete:
        return
    if (state.job_state, state.step) != ("succeeded", "report"):
        raise ValueError("A complete bundle requires a succeeded report step.")


def _validate_profile_state(state: JourneySnapshot) -> None:
    if state.profile_admissible is None:
        return
    if not state.profile_present:
        raise ValueError("Admissibility requires a profile.")


def _validate_job_identity(state: JourneySnapshot) -> None:
    if state.job_state is None:
        return
    if state.job_id is None:
        raise ValueError("A job state requires a job identifier.")


def _journey_step(
    *,
    bundle_complete: bool,
    job_state: str | None,
    package_present: bool,
    profile_present: bool,
) -> str:
    if (bundle_complete, job_state) == (True, "succeeded"):
        return "report"
    if package_present:
        return "processing"
    if profile_present:
        return "review"
    return "upload"


def _live_session(
    database: Session,
    session_id: str,
    now: datetime,
) -> tuple[BetaSessionRow, datetime] | None:
    session = database.get(BetaSessionRow, session_id)
    if session is None:
        return None
    expires_at = _utc(session.content_expires_at)
    if expires_at is None:
        return None
    if not _content_available(session, expires_at, now):
        return None
    return session, expires_at


def _content_available(
    session: BetaSessionRow,
    expires_at: datetime,
    now: datetime,
) -> bool:
    if expires_at <= now:
        return False
    if session.deletion_requested_at is not None:
        return False
    return session.content_deleted_at is None


def _profile(database: Session, session_id: str) -> DatasetProfileRow | None:
    return database.scalar(
        select(DatasetProfileRow).where(DatasetProfileRow.session_id == session_id)
    )


def _latest_job(database: Session, session_id: str) -> ReportJobRow | None:
    return database.scalar(
        select(ReportJobRow)
        .where(ReportJobRow.session_id == session_id)
        .order_by(ReportJobRow.queued_at.desc(), ReportJobRow.job_id.desc())
        .limit(1)
    )


def _delivery(database: Session, job: ReportJobRow | None) -> ReportDeliveryRow | None:
    return None if job is None else database.get(ReportDeliveryRow, job.job_id)


def _bundle_complete(
    database: Session,
    job: ReportJobRow | None,
    delivery: ReportDeliveryRow | None,
) -> bool:
    if job is None or delivery is None:
        return False
    actual = (job.state, _artifact_count(database, delivery))
    expected = ("succeeded", len(REQUIRED_ARTIFACT_KINDS))
    return actual == expected


def _artifact_count(database: Session, delivery: ReportDeliveryRow) -> int:
    count = database.scalar(
        select(func.count())
        .select_from(ReportArtifactRow)
        .where(
            ReportArtifactRow.job_id == delivery.job_id,
            ReportArtifactRow.bundle_id == delivery.bundle_id,
        )
    )
    return int(count or 0)


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
