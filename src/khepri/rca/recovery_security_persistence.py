"""Persistence for content-free provider-recovery security evidence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, String, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from khepri.rca.persistence import Base, _utc
from khepri.rca.records import assert_sealed
from khepri.rca.recovery_security import RecoverySecurityEvent


class RecoverySecurityEventRow(Base):
    """Exactly the narrow content-free evidence authorized by KHEPRI-DEC-015."""

    __tablename__ = "rca_recovery_security_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id"],
            ["rca_accounts.account_id"],
            name="fk_rca_recovery_security_event_account",
            ondelete="RESTRICT",
        ),
    )

    event_key_hash: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


def _event_from_row(row: RecoverySecurityEventRow) -> RecoverySecurityEvent:
    return RecoverySecurityEvent._from_storage(
        row.event_key_hash,
        row.account_id,
        _utc(row.occurred_at),
    )


class SqlRecoverySecurityEventStore:
    """Append-once evidence and its governed retention operation."""

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def get_event(self, event_key_hash: str) -> RecoverySecurityEvent | None:
        with self._factory() as database:
            row = database.get(RecoverySecurityEventRow, event_key_hash)
            return None if row is None else _event_from_row(row)

    def append_once(
        self, event: RecoverySecurityEvent
    ) -> RecoverySecurityEvent | None:
        """Append once, returning an identical prior event and refusing a foreign binding."""
        assert_sealed(event)
        existing = self.get_event(event.event_key_hash)
        if existing is not None:
            return existing if existing.account_id == event.account_id else None
        try:
            with self._factory.begin() as database:
                database.add(
                    RecoverySecurityEventRow(
                        event_key_hash=event.event_key_hash,
                        account_id=event.account_id,
                        occurred_at=event.occurred_at,
                    )
                )
        except IntegrityError:
            existing = self.get_event(event.event_key_hash)
            if existing is None or existing.account_id != event.account_id:
                return None
            return existing
        return event

    def purge_events_before(self, horizon: datetime) -> int:
        with self._factory.begin() as database:
            purged = database.execute(
                delete(RecoverySecurityEventRow).where(
                    RecoverySecurityEventRow.occurred_at <= horizon
                )
            )
        return purged.rowcount

    def get_event_count(self) -> int:
        """Return the row count for retention and focused persistence evidence."""
        with self._factory() as database:
            return database.execute(
                select(func.count()).select_from(RecoverySecurityEventRow)
            ).scalar_one()


__all__ = ["RecoverySecurityEventRow", "SqlRecoverySecurityEventStore"]
