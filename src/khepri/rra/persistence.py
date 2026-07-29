from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.sql import Select

from khepri.rra.intake import UploadMetadata
from khepri.rra.sessions import BetaSession, Invitation, SessionScope


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


def _session_from_row(row: BetaSessionRow) -> BetaSession:
    return BetaSession(
        owner_id=row.owner_id,
        session_id=row.session_id,
        created_at=_utc(row.created_at),
        content_expires_at=_utc(row.content_expires_at),
        consent_version=row.consent_version,
        consented_at=_utc(row.consented_at),
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


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
