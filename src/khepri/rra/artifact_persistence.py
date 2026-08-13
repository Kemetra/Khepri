"""Atomic metadata boundary for complete encrypted report publications."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from khepri.rra.delivery_persistence import (
    ReportDeliveryRow,
    _boundary,
    _commit_delivery,
    _leased_job,
)
from khepri.rra.job_persistence import ReportJobRow
from khepri.rra.jobs import JOB_RUNNING
from khepri.rra.persistence import Base, BetaSessionRow, _utc
from khepri.rra.pipeline import DeliveryRecord, ReportPublication
from khepri.rra.report_artifacts import (
    ARTIFACT_METADATA,
    REQUIRED_ARTIFACT_KINDS,
    ArtifactPayload,
)


class ArtifactConflict(RuntimeError):
    """Stored metadata cannot prove the publication offered for this job."""


class ArtifactCorrupted(ValueError):
    """Stored artifact metadata does not describe one complete report."""


class ReportArtifactRow(Base):
    __tablename__ = "rra_report_artifacts"
    __table_args__ = (
        CheckConstraint(
            "artifact_kind IN ("
            "'web_business_ar','web_business_en','web_evidence_ar','web_evidence_en',"
            "'pdf_ar','pdf_en','excel')",
            name="ck_report_artifact_kind",
        ),
        CheckConstraint(
            "((artifact_kind IN ('web_business_ar','web_business_en') "
            "AND media_type = 'text/html; charset=utf-8' "
            "AND file_name = 'khepri-report.html') OR "
            "(artifact_kind IN ('web_evidence_ar','web_evidence_en') "
            "AND media_type = 'text/html; charset=utf-8' "
            "AND file_name = 'khepri-evidence.html') OR "
            "(artifact_kind IN ('pdf_ar','pdf_en') "
            "AND media_type = 'application/pdf' "
            "AND file_name = 'khepri-report.pdf') OR "
            "(artifact_kind = 'excel' "
            "AND media_type = 'application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet' AND file_name = 'khepri-report.xlsx'))",
            name="ck_report_artifact_metadata",
        ),
        CheckConstraint("length(bundle_id) = 64", name="ck_report_artifact_bundle"),
        CheckConstraint("size_bytes > 0", name="ck_report_artifact_size"),
        CheckConstraint("length(sha256_hex) = 64", name="ck_report_artifact_digest"),
        CheckConstraint(
            "expires_at > created_at", name="ck_report_artifact_expiry"
        ),
        CheckConstraint(
            "encryption_algorithm = 'aws:kms'",
            name="ck_report_artifact_encryption",
        ),
        CheckConstraint(
            "length(object_key) > 0 AND length(kms_key_id) > 0",
            name="ck_report_artifact_storage_identity",
        ),
        ForeignKeyConstraint(
            ["job_id", "bundle_id"],
            ["rra_report_deliveries.job_id", "rra_report_deliveries.bundle_id"],
            name="fk_report_artifact_delivery",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_report_artifact_session_scope",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("object_key", name="uq_report_artifact_object_key"),
        Index("ix_report_artifact_expiry", "expires_at"),
    )

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    artifact_kind: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    bundle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    object_key: Mapped[str] = mapped_column(String, nullable=False)
    media_type: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    encryption_algorithm: Mapped[str] = mapped_column(String, nullable=False)
    kms_key_id: Mapped[str] = mapped_column(String, nullable=False)


@dataclass(frozen=True, slots=True)
class StoredArtifact:
    job_id: str
    artifact_kind: str
    owner_id: str
    session_id: str
    bundle_id: str
    object_key: str
    media_type: str
    file_name: str
    size_bytes: int
    sha256_hex: str
    created_at: datetime
    expires_at: datetime
    encryption_algorithm: str
    kms_key_id: str


@dataclass(frozen=True, slots=True)
class ArtifactBoundary:
    owner_id: str
    session_id: str
    expires_at: datetime
    lease_owner: str
    attempt_number: int


class SqlArtifactRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def commit(
        self,
        publication: ReportPublication,
        artifacts: tuple[StoredArtifact, ...],
        *,
        boundary: ArtifactBoundary,
        committed_at: datetime,
    ) -> DeliveryRecord:
        _validate_publication(publication, artifacts)
        created_at = artifacts[0].created_at
        with self._factory.begin() as database:
            record = publication.delivery.record
            job = _active_publication_job(
                database,
                record,
                boundary=boundary,
                committed_at=committed_at,
            )
            expires_at = _boundary(database, job, generated_at=created_at)
            _require_live_session(database, owner_id=job.owner_id, session_id=job.session_id)
            _validate_scope(
                artifacts,
                owner_id=job.owner_id,
                session_id=job.session_id,
                expires_at=expires_at,
            )
            result = _commit_delivery(
                database,
                publication.delivery,
                owner_id=job.owner_id,
                generated_at=created_at,
                expires_at=expires_at,
            )
            existing = _rows(database, record.job_id)
            if existing:
                if tuple(_from_row(row) for row in existing) != artifacts:
                    raise ArtifactConflict("This job already published other artifacts.")
                return result
            database.add_all(ReportArtifactRow(**_values(item)) for item in artifacts)
            database.flush()
            return result

    def boundary(
        self,
        publication: ReportPublication,
        *,
        created_at: datetime,
    ) -> ArtifactBoundary:
        """Resolve the opaque live storage scope, revalidated again at commit."""
        with self._factory.begin() as database:
            job = _leased_job(database, publication.delivery.record)
            lease_owner = job.lease_owner
            lease_expires_at = _utc(job.lease_expires_at)
            if (
                job.state != JOB_RUNNING
                or lease_owner is None
                or lease_expires_at is None
                or lease_expires_at <= created_at
            ):
                raise ArtifactConflict("Report publication lease is unavailable.")
            expires_at = _boundary(database, job, generated_at=created_at)
            _require_live_session(database, owner_id=job.owner_id, session_id=job.session_id)
            return ArtifactBoundary(
                owner_id=job.owner_id,
                session_id=job.session_id,
                expires_at=expires_at,
                lease_owner=lease_owner,
                attempt_number=job.attempt_count,
            )

    def has_complete(self, job_id: str) -> bool:
        with self._factory() as database:
            delivery = database.get(ReportDeliveryRow, job_id)
            if delivery is None:
                return False
            artifacts = tuple(_from_row(row) for row in _rows(database, job_id))
            if not artifacts:
                return False
            _validate_stored_set(artifacts, delivery=delivery)
            return True

    def find_in_session(
        self,
        *,
        session_id: str,
        job_id: str,
        artifact_kind: str,
        now: datetime,
    ) -> StoredArtifact | None:
        if artifact_kind not in REQUIRED_ARTIFACT_KINDS:
            return None
        available = self.list_for_job(session_id=session_id, job_id=job_id, now=now)
        return next(
            (entry for entry in available if entry.artifact_kind == artifact_kind),
            None,
        )

    def list_for_job(
        self,
        *,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> tuple[StoredArtifact, ...]:
        with self._factory() as database:
            session = database.scalar(
                select(BetaSessionRow).where(BetaSessionRow.session_id == session_id)
            )
            delivery = database.get(ReportDeliveryRow, job_id)
            if not _available(session, delivery, session_id=session_id, now=now):
                return ()
            rows = _rows(database, job_id)
            artifacts = tuple(_from_row(row) for row in rows)
            _validate_stored_set(artifacts, delivery=delivery)
            return artifacts


def _active_publication_job(
    database: Session,
    record: DeliveryRecord,
    *,
    boundary: ArtifactBoundary,
    committed_at: datetime,
) -> ReportJobRow:
    job = _leased_job(database, record)
    expected = (
        JOB_RUNNING,
        boundary.lease_owner,
        boundary.attempt_number,
        boundary.owner_id,
        boundary.session_id,
    )
    actual = (
        job.state,
        job.lease_owner,
        job.attempt_count,
        job.owner_id,
        job.session_id,
    )
    lease_expires_at = _utc(job.lease_expires_at)
    if actual != expected or lease_expires_at is None or lease_expires_at <= committed_at:
        raise ArtifactConflict("Report publication lease is unavailable.")
    return job


def _validate_publication(
    publication: ReportPublication,
    artifacts: tuple[StoredArtifact, ...],
) -> None:
    _require_exact_kinds(artifacts, conflict=ArtifactConflict)
    record = publication.delivery.record
    for payload, stored in zip(publication.artifacts, artifacts, strict=True):
        _validate_published_artifact(record, payload, stored)


def _require_exact_kinds(
    artifacts: tuple[StoredArtifact, ...],
    *,
    conflict: type[ArtifactConflict] | type[ArtifactCorrupted],
) -> None:
    actual = tuple(item.artifact_kind for item in artifacts)
    if actual != REQUIRED_ARTIFACT_KINDS:
        raise conflict("Report metadata is not the exact artifact set.")


def _validate_published_artifact(
    record: DeliveryRecord,
    payload: ArtifactPayload,
    stored: StoredArtifact,
) -> None:
    expected = (
        record.job_id,
        payload.kind,
        record.session_id,
        record.bundle_id,
        payload.media_type,
        payload.file_name,
        len(payload.content),
        payload.sha256_hex,
    )
    actual = (
        stored.job_id,
        stored.artifact_kind,
        stored.session_id,
        stored.bundle_id,
        stored.media_type,
        stored.file_name,
        stored.size_bytes,
        stored.sha256_hex,
    )
    if actual != expected:
        raise ArtifactConflict("Artifact metadata does not prove its payload.")
    _validate_storage_metadata(stored)


def _validate_storage_metadata(stored: StoredArtifact) -> None:
    _require_storage_value(bool(stored.object_key))
    _require_storage_value(stored.encryption_algorithm == "aws:kms")
    _require_storage_value(bool(stored.kms_key_id))
    _require_storage_value(stored.expires_at > stored.created_at)


def _require_storage_value(valid: bool) -> None:
    if not valid:
        raise ArtifactConflict("Artifact storage metadata is invalid.")


def _validate_scope(
    artifacts: tuple[StoredArtifact, ...],
    *,
    owner_id: str,
    session_id: str,
    expires_at: datetime,
) -> None:
    expected = (owner_id, session_id, expires_at, _utc(artifacts[0].created_at))
    if any(_scope(item) != expected for item in artifacts):
        raise ArtifactConflict("Artifact metadata crosses its session boundary.")


def _scope(item: StoredArtifact) -> tuple[str, str, datetime | None, datetime | None]:
    return (
        item.owner_id,
        item.session_id,
        _utc(item.expires_at),
        _utc(item.created_at),
    )


def _available(
    session: BetaSessionRow | None,
    delivery: ReportDeliveryRow | None,
    *,
    session_id: str,
    now: datetime,
) -> bool:
    if session is None or delivery is None:
        return False
    if delivery.session_id != session_id:
        return False
    expires_at = _utc(session.content_expires_at)
    if expires_at is None or expires_at <= now:
        return False
    return _content_is_live(session)


def _content_is_live(session: BetaSessionRow) -> bool:
    state = (session.deletion_requested_at, session.content_deleted_at)
    return state == (None, None)


def _require_live_session(
    database: Session,
    *,
    owner_id: str,
    session_id: str,
) -> None:
    session = database.scalar(
        select(BetaSessionRow)
        .where(
            BetaSessionRow.owner_id == owner_id,
            BetaSessionRow.session_id == session_id,
        )
        .with_for_update()
    )
    if session is None:
        raise ArtifactConflict("Session content is unavailable.")
    if not _content_is_live(session):
        raise ArtifactConflict("Session content is unavailable.")


def _validate_stored_set(
    artifacts: tuple[StoredArtifact, ...],
    *,
    delivery: ReportDeliveryRow,
) -> None:
    _require_exact_kinds(artifacts, conflict=ArtifactCorrupted)
    for artifact in artifacts:
        _validate_stored_artifact(artifact, delivery)


def _validate_stored_artifact(
    artifact: StoredArtifact,
    delivery: ReportDeliveryRow,
) -> None:
    expected = (
        delivery.job_id,
        delivery.session_id,
        delivery.bundle_id,
        _utc(delivery.expires_at),
        ARTIFACT_METADATA[artifact.artifact_kind],
    )
    actual = (
        artifact.job_id,
        artifact.session_id,
        artifact.bundle_id,
        artifact.expires_at,
        (artifact.media_type, artifact.file_name),
    )
    if actual != expected:
        raise ArtifactCorrupted("Stored report artifact metadata is mixed.")


def _rows(database: Session, job_id: str) -> tuple[ReportArtifactRow, ...]:
    found = {
        row.artifact_kind: row
        for row in database.scalars(
            select(ReportArtifactRow).where(ReportArtifactRow.job_id == job_id)
        )
    }
    return tuple(
        found[kind] for kind in REQUIRED_ARTIFACT_KINDS if kind in found
    )


def _from_row(row: ReportArtifactRow) -> StoredArtifact:
    created_at = _utc(row.created_at)
    expires_at = _utc(row.expires_at)
    if created_at is None or expires_at is None:
        raise ArtifactCorrupted("Stored report artifact timestamps are invalid.")
    return StoredArtifact(
        job_id=row.job_id,
        artifact_kind=row.artifact_kind,
        owner_id=row.owner_id,
        session_id=row.session_id,
        bundle_id=row.bundle_id,
        object_key=row.object_key,
        media_type=row.media_type,
        file_name=row.file_name,
        size_bytes=row.size_bytes,
        sha256_hex=row.sha256_hex,
        created_at=created_at,
        expires_at=expires_at,
        encryption_algorithm=row.encryption_algorithm,
        kms_key_id=row.kms_key_id,
    )


def _values(item: StoredArtifact) -> dict[str, object]:
    return {field: getattr(item, field) for field in item.__dataclass_fields__}


__all__ = [
    "ArtifactConflict",
    "ArtifactCorrupted",
    "ArtifactBoundary",
    "ReportArtifactRow",
    "SqlArtifactRepository",
    "StoredArtifact",
]
