from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, LargeBinary, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.sql import Select

from khepri.rra.sessions import BetaSession, Invitation


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


def _session_from_row(row: BetaSessionRow) -> BetaSession:
    return BetaSession(
        owner_id=row.owner_id,
        session_id=row.session_id,
        created_at=_utc(row.created_at),
        content_expires_at=_utc(row.content_expires_at),
        consent_version=row.consent_version,
        consented_at=_utc(row.consented_at),
    )


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
