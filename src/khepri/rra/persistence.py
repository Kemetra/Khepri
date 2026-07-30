from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    delete,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.sql import Select

from khepri.rra.datasets import DatasetProfileRecord
from khepri.rra.deletion import DeletionEvidence, DeletionJob
from khepri.rra.intake import UploadMetadata
from khepri.rra.jobs import (
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RETRYABLE,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    LeaseLost,
    ReportJob,
)
from khepri.rra.packages import FactPackageRecord, PackageVersions
from khepri.rra.sessions import (
    BetaSession,
    CrossSessionAccessDenied,
    Invitation,
    SessionScope,
)


class Base(DeclarativeBase):
    pass


class InvitationRow(Base):
    __tablename__ = "rra_invitations"

    invitation_id: Mapped[str] = mapped_column(String, primary_key=True)
    secret_salt: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    secret_digest: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BetaSessionRow(Base):
    __tablename__ = "rra_beta_sessions"
    __table_args__ = (
        CheckConstraint("content_expires_at > created_at", name="ck_session_expiry_after_creation"),
        CheckConstraint(
            "(consent_version IS NULL) = (consented_at IS NULL)",
            name="ck_session_consent_complete",
        ),
        CheckConstraint(
            "content_deleted_at IS NULL OR deletion_requested_at IS NOT NULL",
            name="ck_session_deletion_order",
        ),
        UniqueConstraint("owner_id", "session_id", name="uq_session_owner_scope"),
    )

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    consent_version: Mapped[str | None] = mapped_column(String)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UploadRow(Base):
    __tablename__ = "rra_uploads"
    __table_args__ = (
        CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 52428800",
            name="ck_upload_size_range",
        ),
        CheckConstraint(
            "length(sha256_hex) = 64",
            name="ck_upload_sha256_length",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_upload_expiry_after_creation",
        ),
        CheckConstraint(
            "encryption_algorithm = 'aws:kms'",
            name="ck_upload_kms_encryption",
        ),
        UniqueConstraint("session_id", name="uq_upload_session"),
        ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_upload_session_scope",
            ondelete="RESTRICT",
        ),
    )

    upload_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    object_key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    encryption_algorithm: Mapped[str] = mapped_column(String, nullable=False)
    kms_key_id: Mapped[str] = mapped_column(String, nullable=False)


class DatasetProfileRow(Base):
    __tablename__ = "rra_dataset_profiles"
    __table_args__ = (
        CheckConstraint("row_count >= 0", name="ck_profile_row_count"),
        CheckConstraint("column_count > 0", name="ck_profile_column_count"),
        CheckConstraint(
            "length(source_sha256_hex) = 64",
            name="ck_profile_source_digest",
        ),
        CheckConstraint(
            "length(profile_digest) = 64",
            name="ck_profile_digest",
        ),
        UniqueConstraint("upload_id", name="uq_profile_upload"),
        UniqueConstraint("session_id", name="uq_profile_session"),
        ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_profile_session_scope",
            ondelete="RESTRICT",
        ),
    )

    profile_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    upload_id: Mapped[str] = mapped_column(String, nullable=False)
    profile_version: Mapped[str] = mapped_column(String, nullable=False)
    mapping_version: Mapped[str] = mapped_column(String, nullable=False)
    source_sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    admissible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    document: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class FactPackageRow(Base):
    __tablename__ = "rra_fact_packages"
    __table_args__ = (
        CheckConstraint("row_count >= 0", name="ck_package_row_count"),
        CheckConstraint(
            "length(source_sha256_hex) = 64",
            name="ck_package_source_digest",
        ),
        CheckConstraint(
            "length(profile_document_digest) = 64",
            name="ck_package_profile_document_digest",
        ),
        CheckConstraint("length(package_digest) = 64", name="ck_package_digest"),
        # A new formula, mapping, or correction is a new version rather than a
        # replacement, so the governed versions are part of the identity. One
        # publication per profile per version triple; history is kept.
        UniqueConstraint(
            "profile_id",
            "package_version",
            "formula_version",
            "mapping_version",
            name="uq_package_profile_versions",
        ),
        Index("ix_package_session", "session_id"),
        ForeignKeyConstraint(
            ["profile_id"],
            ["rra_dataset_profiles.profile_id"],
            name="fk_package_profile",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_package_session_scope",
            ondelete="RESTRICT",
        ),
    )

    package_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    profile_id: Mapped[str] = mapped_column(String, nullable=False)
    package_version: Mapped[str] = mapped_column(String, nullable=False)
    formula_version: Mapped[str] = mapped_column(String, nullable=False)
    mapping_version: Mapped[str] = mapped_column(String, nullable=False)
    profile_document_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    document: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class ReportJobRow(Base):
    __tablename__ = "rra_report_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'running', 'retryable', 'succeeded', 'failed')",
            name="ck_report_job_state",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_report_job_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_report_job_max_attempts"),
        CheckConstraint(
            "length(idempotency_key) = 64",
            name="ck_report_job_idempotency_digest",
        ),
        CheckConstraint(
            "available_at >= queued_at",
            name="ck_report_job_availability",
        ),
        CheckConstraint(
            "attempt_count <= max_attempts",
            name="ck_report_job_attempt_limit",
        ),
        CheckConstraint(
            "(state = 'running') = "
            "(lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_report_job_lease",
        ),
        CheckConstraint(
            "(state IN ('succeeded', 'failed')) = (completed_at IS NOT NULL)",
            name="ck_report_job_completion",
        ),
        UniqueConstraint(
            "session_id",
            "idempotency_key",
            name="uq_report_job_session_idempotency",
        ),
        ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_report_job_session_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_report_job_available", "state", "available_at"),
        Index("ix_report_job_lease_expiry", "lease_expires_at"),
    )

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeletionJobRow(Base):
    __tablename__ = "rra_deletion_jobs"
    __table_args__ = (
        CheckConstraint(
            "reason IN ('immediate', 'expiry')",
            name="ck_deletion_reason",
        ),
        CheckConstraint(
            "state IN ('pending', 'retryable', 'complete')",
            name="ck_deletion_state",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_deletion_attempt_count"),
        CheckConstraint(
            "(state = 'complete') = (completed_at IS NOT NULL)",
            name="ck_deletion_completion",
        ),
        CheckConstraint(
            "(state = 'retryable') = (next_retry_at IS NOT NULL)",
            name="ck_deletion_retry_schedule",
        ),
        UniqueConstraint("session_id", name="uq_deletion_session"),
        ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_deletion_session_scope",
            ondelete="RESTRICT",
        ),
    )

    deletion_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeletionEvidenceRow(Base):
    __tablename__ = "rra_deletion_evidence"
    __table_args__ = (
        CheckConstraint("target_kind = 'input'", name="ck_evidence_target_kind"),
        CheckConstraint(
            "length(location_digest) = 64",
            name="ck_evidence_location_digest",
        ),
        CheckConstraint(
            "length(content_digest) = 64",
            name="ck_evidence_content_digest",
        ),
        CheckConstraint("attempt_number > 0", name="ck_evidence_attempt_number"),
        CheckConstraint(
            "outcome IN ('deleted', 'failed')",
            name="ck_evidence_outcome",
        ),
        CheckConstraint(
            "(outcome = 'failed') = (error_code IS NOT NULL)",
            name="ck_evidence_error_outcome",
        ),
        ForeignKeyConstraint(
            ["deletion_id"],
            ["rra_deletion_jobs.deletion_id"],
            name="fk_evidence_deletion",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "deletion_id",
            "attempt_number",
            name="uq_evidence_deletion_attempt",
        ),
    )

    evidence_id: Mapped[str] = mapped_column(String, primary_key=True)
    deletion_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )
    target_kind: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    location_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String)


def invitation_for_update_statement(
    invitation_id: str,
) -> Select[tuple[InvitationRow]]:
    return (
        select(InvitationRow)
        .where(InvitationRow.invitation_id == invitation_id)
        .with_for_update()
    )


class SqlSessionStore:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def add_invitation(self, invitation: Invitation) -> None:
        with self._factory.begin() as database:
            database.add(
                InvitationRow(
                    invitation_id=invitation.invitation_id,
                    secret_salt=invitation.secret_salt,
                    secret_digest=invitation.secret_digest,
                    expires_at=invitation.expires_at,
                    redeemed_at=invitation.redeemed_at,
                )
            )

    def get_invitation(self, invitation_id: str) -> Invitation | None:
        with self._factory() as database:
            row = database.get(InvitationRow, invitation_id)
            if row is None:
                return None
            return Invitation(
                invitation_id=row.invitation_id,
                secret_salt=row.secret_salt,
                secret_digest=row.secret_digest,
                expires_at=_utc(row.expires_at),
                redeemed_at=_utc(row.redeemed_at),
            )

    def redeem_invitation(
        self,
        invitation_id: str,
        redeemed_at: datetime,
        session: BetaSession,
    ) -> bool:
        with self._factory.begin() as database:
            invitation = database.scalar(invitation_for_update_statement(invitation_id))
            if (
                invitation is None
                or invitation.redeemed_at is not None
                or _utc(invitation.expires_at) <= redeemed_at
            ):
                return False
            invitation.redeemed_at = redeemed_at
            database.add(
                BetaSessionRow(
                    owner_id=session.owner_id,
                    session_id=session.session_id,
                    created_at=session.created_at,
                    content_expires_at=session.content_expires_at,
                    consent_version=session.consent_version,
                    consented_at=session.consented_at,
                    deletion_requested_at=session.deletion_requested_at,
                    content_deleted_at=session.content_deleted_at,
                )
            )
        return True

    def get_session(self, session_id: str) -> BetaSession | None:
        with self._factory() as database:
            row = database.get(BetaSessionRow, session_id)
            if row is None:
                return None
            return _session_from_row(row)

    def update_session(self, session: BetaSession) -> None:
        with self._factory.begin() as database:
            row = database.get(BetaSessionRow, session.session_id)
            if row is None:
                raise LookupError("Session is unavailable.")
            row.consent_version = session.consent_version
            row.consented_at = session.consented_at
            row.deletion_requested_at = session.deletion_requested_at
            row.content_deleted_at = session.content_deleted_at


class SqlUploadRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def add_upload(self, upload: UploadMetadata) -> bool:
        try:
            with self._factory.begin() as database:
                database.add(
                    UploadRow(
                        upload_id=upload.upload_id,
                        owner_id=upload.owner_id,
                        session_id=upload.session_id,
                        object_key=upload.object_key,
                        size_bytes=upload.size_bytes,
                        sha256_hex=upload.sha256_hex,
                        media_type=upload.media_type,
                        created_at=upload.created_at,
                        expires_at=upload.expires_at,
                        encryption_algorithm=upload.encryption_algorithm,
                        kms_key_id=upload.kms_key_id,
                    )
                )
            return True
        except IntegrityError:
            if self.get_upload_for_session(upload.session_id) is not None:
                return False
            raise

    def get_upload_for_session(self, session_id: str) -> UploadMetadata | None:
        statement = select(UploadRow).where(UploadRow.session_id == session_id)
        with self._factory() as database:
            row = database.scalar(statement)
            return None if row is None else _upload_from_row(row)

    def get_upload_in_scope(
        self,
        upload_id: str,
        scope: SessionScope,
    ) -> UploadMetadata | None:
        statement = select(UploadRow).where(
            UploadRow.upload_id == upload_id,
            UploadRow.owner_id == scope.owner_id,
            UploadRow.session_id == scope.session_id,
        )
        with self._factory() as database:
            row = database.scalar(statement)
            return None if row is None else _upload_from_row(row)


class SqlProfileRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def add_profile(self, record: DatasetProfileRecord) -> DatasetProfileRecord:
        try:
            with self._factory.begin() as database:
                database.add(
                    DatasetProfileRow(
                        profile_id=record.profile_id,
                        owner_id=record.owner_id,
                        session_id=record.session_id,
                        upload_id=record.upload_id,
                        profile_version=record.profile_version,
                        mapping_version=record.mapping_version,
                        source_sha256_hex=record.source_sha256_hex,
                        profile_digest=record.profile_digest,
                        row_count=record.row_count,
                        column_count=record.column_count,
                        admissible=record.admissible,
                        created_at=record.created_at,
                        document=record.document,
                    )
                )
            return record
        except IntegrityError:
            existing = self.get_profile_for_upload(record.upload_id, record.scope)
            if existing is None:
                raise
            return existing

    def get_profile_for_upload(
        self,
        upload_id: str,
        scope: SessionScope,
    ) -> DatasetProfileRecord | None:
        statement = select(DatasetProfileRow).where(
            DatasetProfileRow.upload_id == upload_id,
            DatasetProfileRow.owner_id == scope.owner_id,
            DatasetProfileRow.session_id == scope.session_id,
        )
        with self._factory() as database:
            row = database.scalar(statement)
            return None if row is None else _profile_from_row(row)

    def get_profile_for_session(self, session_id: str) -> DatasetProfileRecord | None:
        statement = select(DatasetProfileRow).where(
            DatasetProfileRow.session_id == session_id
        )
        with self._factory() as database:
            row = database.scalar(statement)
            return None if row is None else _profile_from_row(row)


class SqlFactPackageRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def add_package(self, record: FactPackageRecord) -> FactPackageRecord:
        try:
            with self._factory.begin() as database:
                database.add(
                    FactPackageRow(
                        package_id=record.package_id,
                        owner_id=record.owner_id,
                        session_id=record.session_id,
                        profile_id=record.profile_id,
                        package_version=record.package_version,
                        formula_version=record.formula_version,
                        mapping_version=record.mapping_version,
                        profile_document_digest=record.profile_document_digest,
                        source_sha256_hex=record.source_sha256_hex,
                        package_digest=record.package_digest,
                        row_count=record.row_count,
                        created_at=record.created_at,
                        document=record.document,
                    )
                )
            return record
        except IntegrityError:
            existing = self.get_package_for_versions(
                record.profile_id,
                PackageVersions(
                    package_version=record.package_version,
                    formula_version=record.formula_version,
                    mapping_version=record.mapping_version,
                ),
                record.scope,
            )
            if existing is None:
                raise
            return existing

    def get_package_for_versions(
        self,
        profile_id: str,
        versions: PackageVersions,
        scope: SessionScope,
    ) -> FactPackageRecord | None:
        statement = select(FactPackageRow).where(
            FactPackageRow.profile_id == profile_id,
            FactPackageRow.package_version == versions.package_version,
            FactPackageRow.formula_version == versions.formula_version,
            FactPackageRow.mapping_version == versions.mapping_version,
            FactPackageRow.owner_id == scope.owner_id,
            FactPackageRow.session_id == scope.session_id,
        )
        with self._factory() as database:
            row = database.scalar(statement)
            return None if row is None else _package_from_row(row)

    def get_package_for_session(
        self,
        session_id: str,
        versions: PackageVersions,
    ) -> FactPackageRecord | None:
        """The session's package under the given governed versions, latest first."""
        statement = (
            select(FactPackageRow)
            .where(
                FactPackageRow.session_id == session_id,
                FactPackageRow.package_version == versions.package_version,
                FactPackageRow.formula_version == versions.formula_version,
                FactPackageRow.mapping_version == versions.mapping_version,
            )
            .order_by(
                FactPackageRow.created_at.desc(),
                FactPackageRow.package_id.desc(),
            )
        )
        with self._factory() as database:
            row = database.scalar(statement)
            return None if row is None else _package_from_row(row)


class SqlReportJobRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def enqueue(
        self,
        *,
        scope: SessionScope,
        job_id: str,
        idempotency_key: str,
        queued_at: datetime,
        max_attempts: int,
    ) -> ReportJob:
        if len(idempotency_key) != 64:
            raise ValueError("Idempotency key must be a SHA-256 digest.")
        if max_attempts <= 0:
            raise ValueError("Maximum attempts must be positive.")
        try:
            with self._factory.begin() as database:
                session_row = database.scalar(session_scope_for_update_statement(scope))
                if session_row is None:
                    raise CrossSessionAccessDenied("Resource is unavailable.")
                existing = database.scalar(
                    select(ReportJobRow).where(
                        ReportJobRow.session_id == scope.session_id,
                        ReportJobRow.idempotency_key == idempotency_key,
                    )
                )
                if existing is not None:
                    return _report_job_from_row(existing)
                row = ReportJobRow(
                    job_id=job_id,
                    owner_id=scope.owner_id,
                    session_id=scope.session_id,
                    idempotency_key=idempotency_key,
                    state=JOB_QUEUED,
                    queued_at=queued_at,
                    available_at=queued_at,
                    attempt_count=0,
                    max_attempts=max_attempts,
                    lease_owner=None,
                    lease_expires_at=None,
                    completed_at=None,
                )
                database.add(row)
                database.flush()
                return _report_job_from_row(row)
        except IntegrityError:
            with self._factory() as database:
                row = database.scalar(
                    select(ReportJobRow).where(
                        ReportJobRow.session_id == scope.session_id,
                        ReportJobRow.idempotency_key == idempotency_key,
                    )
                )
                if row is None:
                    raise
                return _report_job_from_row(row)

    def lease(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
        lease_for: timedelta,
    ) -> ReportJob | None:
        if lease_for <= timedelta(0):
            raise ValueError("Lease duration must be positive.")
        with self._factory.begin() as database:
            row = database.scalar(
                select(ReportJobRow)
                .where(ReportJobRow.job_id == job_id)
                .with_for_update()
            )
            if (
                row is None
                or row.state not in {JOB_QUEUED, JOB_RETRYABLE}
                or _utc(row.available_at) > now
                or row.attempt_count >= row.max_attempts
            ):
                return None
            row.state = JOB_RUNNING
            row.attempt_count += 1
            row.lease_owner = worker_id
            row.lease_expires_at = now + lease_for
            database.flush()
            return _report_job_from_row(row)

    def recover_expired(self, *, now: datetime) -> tuple[ReportJob, ...]:
        statement = (
            select(ReportJobRow)
            .where(
                ReportJobRow.state == JOB_RUNNING,
                ReportJobRow.lease_expires_at <= now,
            )
            .order_by(ReportJobRow.lease_expires_at, ReportJobRow.job_id)
            .with_for_update(skip_locked=True)
        )
        with self._factory.begin() as database:
            rows = list(database.scalars(statement))
            for row in rows:
                if row.attempt_count >= row.max_attempts:
                    row.state = JOB_FAILED
                    row.completed_at = now
                else:
                    row.state = JOB_RETRYABLE
                    row.available_at = now
                row.lease_owner = None
                row.lease_expires_at = None
            database.flush()
            return tuple(_report_job_from_row(row) for row in rows)

    def fail(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
        retry_at: datetime,
    ) -> ReportJob:
        with self._factory.begin() as database:
            row = self._active_lease(
                database,
                job_id=job_id,
                worker_id=worker_id,
                now=now,
            )
            if row.attempt_count >= row.max_attempts:
                row.state = JOB_FAILED
                row.completed_at = now
            else:
                if retry_at <= now:
                    raise ValueError("Retry time must be in the future.")
                row.state = JOB_RETRYABLE
                row.available_at = retry_at
                row.completed_at = None
            row.lease_owner = None
            row.lease_expires_at = None
            database.flush()
            return _report_job_from_row(row)

    def complete(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
    ) -> ReportJob:
        with self._factory.begin() as database:
            row = self._active_lease(
                database,
                job_id=job_id,
                worker_id=worker_id,
                now=now,
            )
            row.state = JOB_SUCCEEDED
            row.lease_owner = None
            row.lease_expires_at = None
            row.completed_at = now
            database.flush()
            return _report_job_from_row(row)

    def heartbeat(
        self,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
        lease_for: timedelta,
    ) -> ReportJob:
        if lease_for <= timedelta(0):
            raise ValueError("Lease duration must be positive.")
        with self._factory.begin() as database:
            row = self._active_lease(
                database,
                job_id=job_id,
                worker_id=worker_id,
                now=now,
            )
            row.lease_expires_at = now + lease_for
            database.flush()
            return _report_job_from_row(row)

    @staticmethod
    def _active_lease(
        database: Session,
        *,
        job_id: str,
        worker_id: str,
        now: datetime,
    ) -> ReportJobRow:
        row = database.scalar(
            select(ReportJobRow)
            .where(ReportJobRow.job_id == job_id)
            .with_for_update()
        )
        if (
            row is None
            or row.state != JOB_RUNNING
            or row.lease_owner != worker_id
            or _utc(row.lease_expires_at) <= now
        ):
            raise LeaseLost("Report job lease is unavailable.")
        return row


class SqlDeletionRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def begin(
        self,
        *,
        scope: SessionScope,
        deletion_id: str,
        reason: str,
        requested_at: datetime,
    ) -> DeletionJob:
        with self._factory.begin() as database:
            session_row = database.scalar(session_scope_for_update_statement(scope))
            if session_row is None:
                raise CrossSessionAccessDenied("Resource is unavailable.")
            existing = database.scalar(
                select(DeletionJobRow).where(
                    DeletionJobRow.owner_id == scope.owner_id,
                    DeletionJobRow.session_id == scope.session_id,
                )
            )
            if existing is not None:
                return _deletion_from_row(existing)
            session_row.deletion_requested_at = (
                session_row.deletion_requested_at or requested_at
            )
            row = DeletionJobRow(
                deletion_id=deletion_id,
                owner_id=scope.owner_id,
                session_id=scope.session_id,
                reason=reason,
                state="pending",
                requested_at=requested_at,
                attempt_count=0,
                last_attempt_at=None,
                next_retry_at=None,
                completed_at=None,
            )
            database.add(row)
            database.flush()
            return _deletion_from_row(row)

    def get_target(self, job: DeletionJob) -> UploadMetadata | None:
        statement = select(UploadRow).where(
            UploadRow.owner_id == job.owner_id,
            UploadRow.session_id == job.session_id,
        )
        with self._factory() as database:
            row = database.scalar(statement)
            return None if row is None else _upload_from_row(row)

    def complete(
        self,
        *,
        job: DeletionJob,
        evidence: DeletionEvidence | None,
        completed_at: datetime,
    ) -> DeletionJob:
        with self._factory.begin() as database:
            row = self._locked_job(database, job.deletion_id)
            if row.state == "complete":
                return _deletion_from_row(row)
            upload = database.scalar(
                select(UploadRow).where(
                    UploadRow.owner_id == row.owner_id,
                    UploadRow.session_id == row.session_id,
                )
            )
            if evidence is None and upload is not None:
                raise ValueError("Deletion evidence is required for an existing target.")
            # The package references the profile, so it goes first.
            database.execute(
                delete(FactPackageRow).where(
                    FactPackageRow.owner_id == row.owner_id,
                    FactPackageRow.session_id == row.session_id,
                )
            )
            database.execute(
                delete(DatasetProfileRow).where(
                    DatasetProfileRow.owner_id == row.owner_id,
                    DatasetProfileRow.session_id == row.session_id,
                )
            )
            if evidence is not None:
                self._add_evidence(database, row, evidence)
                if upload is None or upload.upload_id != evidence.target_id:
                    raise ValueError("Deletion target no longer matches evidence.")
                database.execute(
                    delete(UploadRow).where(UploadRow.upload_id == upload.upload_id)
                )
                row.attempt_count += 1
                row.last_attempt_at = evidence.attempted_at
            session_row = database.get(BetaSessionRow, row.session_id)
            if session_row is None:
                raise LookupError("Session is unavailable.")
            session_row.content_deleted_at = completed_at
            row.state = "complete"
            row.next_retry_at = None
            row.completed_at = completed_at
            database.flush()
            return _deletion_from_row(row)

    def fail(
        self,
        *,
        job: DeletionJob,
        evidence: DeletionEvidence,
        next_retry_at: datetime,
    ) -> DeletionJob:
        with self._factory.begin() as database:
            row = self._locked_job(database, job.deletion_id)
            if row.state == "complete":
                return _deletion_from_row(row)
            self._add_evidence(database, row, evidence)
            row.state = "retryable"
            row.attempt_count += 1
            row.last_attempt_at = evidence.attempted_at
            row.next_retry_at = next_retry_at
            row.completed_at = None
            database.flush()
            return _deletion_from_row(row)

    def list_evidence(self, deletion_id: str) -> list[DeletionEvidence]:
        statement = (
            select(DeletionEvidenceRow)
            .where(DeletionEvidenceRow.deletion_id == deletion_id)
            .order_by(DeletionEvidenceRow.attempt_number)
        )
        with self._factory() as database:
            return [_evidence_from_row(row) for row in database.scalars(statement)]

    @staticmethod
    def _locked_job(database: Session, deletion_id: str) -> DeletionJobRow:
        row = database.scalar(
            select(DeletionJobRow)
            .where(DeletionJobRow.deletion_id == deletion_id)
            .with_for_update()
        )
        if row is None:
            raise LookupError("Deletion job is unavailable.")
        return row

    @staticmethod
    def _add_evidence(
        database: Session,
        job: DeletionJobRow,
        evidence: DeletionEvidence,
    ) -> None:
        if (
            evidence.deletion_id != job.deletion_id
            or evidence.attempt_number != job.attempt_count + 1
        ):
            raise ValueError("Deletion evidence does not match the current attempt.")
        database.add(
            DeletionEvidenceRow(
                evidence_id=evidence.evidence_id,
                deletion_id=evidence.deletion_id,
                target_kind=evidence.target_kind,
                target_id=evidence.target_id,
                location_digest=evidence.location_digest,
                content_digest=evidence.content_digest,
                attempted_at=evidence.attempted_at,
                attempt_number=evidence.attempt_number,
                outcome=evidence.outcome,
                error_code=evidence.error_code,
            )
        )


def session_scope_for_update_statement(
    scope: SessionScope,
) -> Select[tuple[BetaSessionRow]]:
    return (
        select(BetaSessionRow)
        .where(
            BetaSessionRow.owner_id == scope.owner_id,
            BetaSessionRow.session_id == scope.session_id,
        )
        .with_for_update()
    )


def _session_from_row(row: BetaSessionRow) -> BetaSession:
    return BetaSession(
        owner_id=row.owner_id,
        session_id=row.session_id,
        created_at=_utc(row.created_at),
        content_expires_at=_utc(row.content_expires_at),
        consent_version=row.consent_version,
        consented_at=_utc(row.consented_at),
        deletion_requested_at=_utc(row.deletion_requested_at),
        content_deleted_at=_utc(row.content_deleted_at),
    )


def _upload_from_row(row: UploadRow) -> UploadMetadata:
    return UploadMetadata(
        upload_id=row.upload_id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        object_key=row.object_key,
        size_bytes=row.size_bytes,
        sha256_hex=row.sha256_hex,
        media_type=row.media_type,
        created_at=_utc(row.created_at),
        expires_at=_utc(row.expires_at),
        encryption_algorithm=row.encryption_algorithm,
        kms_key_id=row.kms_key_id,
    )


def _profile_from_row(row: DatasetProfileRow) -> DatasetProfileRecord:
    """Hydrate a stored profile, refusing one that no longer matches its digest."""
    record = DatasetProfileRecord(
        profile_id=row.profile_id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        upload_id=row.upload_id,
        profile_version=row.profile_version,
        mapping_version=row.mapping_version,
        source_sha256_hex=row.source_sha256_hex,
        profile_digest=row.profile_digest,
        row_count=row.row_count,
        column_count=row.column_count,
        admissible=row.admissible,
        created_at=_utc(row.created_at),
        document=dict(row.document),
    )
    record.verify()
    return record


def _package_from_row(row: FactPackageRow) -> FactPackageRecord:
    """Hydrate a stored package, refusing one that no longer matches its digest."""
    record = FactPackageRecord(
        package_id=row.package_id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        profile_id=row.profile_id,
        package_version=row.package_version,
        formula_version=row.formula_version,
        mapping_version=row.mapping_version,
        profile_document_digest=row.profile_document_digest,
        source_sha256_hex=row.source_sha256_hex,
        package_digest=row.package_digest,
        row_count=row.row_count,
        created_at=_utc(row.created_at),
        document=dict(row.document),
    )
    record.verify()
    return record


def _deletion_from_row(row: DeletionJobRow) -> DeletionJob:
    return DeletionJob(
        deletion_id=row.deletion_id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        reason=row.reason,
        state=row.state,
        requested_at=_utc(row.requested_at),
        attempt_count=row.attempt_count,
        last_attempt_at=_utc(row.last_attempt_at),
        next_retry_at=_utc(row.next_retry_at),
        completed_at=_utc(row.completed_at),
    )


def _report_job_from_row(row: ReportJobRow) -> ReportJob:
    return ReportJob(
        job_id=row.job_id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        idempotency_key=row.idempotency_key,
        state=row.state,
        queued_at=_utc(row.queued_at),
        available_at=_utc(row.available_at),
        attempt_count=row.attempt_count,
        max_attempts=row.max_attempts,
        lease_owner=row.lease_owner,
        lease_expires_at=_utc(row.lease_expires_at),
        completed_at=_utc(row.completed_at),
    )


def _evidence_from_row(row: DeletionEvidenceRow) -> DeletionEvidence:
    return DeletionEvidence(
        evidence_id=row.evidence_id,
        deletion_id=row.deletion_id,
        target_kind=row.target_kind,
        target_id=row.target_id,
        location_digest=row.location_digest,
        content_digest=row.content_digest,
        attempted_at=_utc(row.attempted_at),
        attempt_number=row.attempt_number,
        outcome=row.outcome,
        error_code=row.error_code,
    )


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
