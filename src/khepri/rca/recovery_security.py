"""Khepri-owned security consequences after provider-owned credential recovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from khepri.rca.errors import AUTHENTICATION_FAILURE, AccountOperationFailed, AuthenticationFailed
from khepri.rca.identity import VerifiedIdentity
from khepri.rca.lifecycle import MEMBERSHIP_EVENT_RETENTION_MONTHS, LifecycleService, _months_before
from khepri.rca.records import Sealed, register_sealed, through_door
from khepri.rca.session_service import SessionService


@register_sealed
@dataclass(frozen=True, slots=True)
class RecoverySecurityEvent(Sealed):
    """Content-free evidence that one Khepri recovery consequence completed."""

    event_key_hash: str
    account_id: str
    occurred_at: datetime

    @classmethod
    def record(
        cls, account_id: str, idempotency_key: str, *, now: datetime
    ) -> RecoverySecurityEvent:
        event_key_hash = sha256(idempotency_key.encode()).hexdigest()
        with through_door():
            return cls(
                event_key_hash=event_key_hash,
                account_id=account_id,
                occurred_at=now,
            )

    @classmethod
    def _from_storage(
        cls, event_key_hash: str, account_id: str, occurred_at: datetime
    ) -> RecoverySecurityEvent:
        with through_door():
            return cls(
                event_key_hash=event_key_hash,
                account_id=account_id,
                occurred_at=occurred_at,
            )

    def is_purgeable_at(self, horizon: datetime) -> bool:
        """True at and after the governed twelve-month audit horizon."""
        return self.occurred_at <= horizon


class RecoverySecurityEventStore(Protocol):
    """The minimum persistence surface for recovery security evidence."""

    def get_event(self, event_key_hash: str) -> RecoverySecurityEvent | None: ...

    def append_once(
        self, event: RecoverySecurityEvent
    ) -> RecoverySecurityEvent | None: ...

    def purge_events_before(self, horizon: datetime) -> int: ...


class RecoverySecurityService:
    """Apply only the Khepri-owned consequence of provider-owned recovery."""

    def __init__(
        self,
        sessions: SessionService,
        lifecycle: LifecycleService,
        events: RecoverySecurityEventStore,
    ) -> None:
        self._sessions = sessions
        self._lifecycle = lifecycle
        self._events = events

    def complete(
        self,
        identity: VerifiedIdentity,
        *,
        idempotency_key: str,
        now: datetime,
    ) -> RecoverySecurityEvent:
        """Revalidate identity, revoke local sessions, and append content-free evidence.

        Provider credential replacement has already succeeded before this operation begins. A new
        Khepri session may be minted only after this method returns; its caller must resolve the
        verified identity and account state again rather than trusting this event as authority.
        """
        if not idempotency_key:
            self._reject()
        account_id = self._resolve_live(identity)
        candidate = RecoverySecurityEvent.record(account_id, idempotency_key, now=now)
        existing = self._events.get_event(candidate.event_key_hash)
        if existing is not None:
            if existing.account_id != account_id:
                self._reject()
            return existing

        self._sessions.revoke_all(account_id, now=now)
        if self._resolve_live(identity) != account_id:
            self._reject()
        committed = self._events.append_once(candidate)
        if committed is None or committed.account_id != account_id:
            self._reject()
        return committed

    def _resolve_live(self, identity: VerifiedIdentity) -> str:
        account_id = self._sessions.account_for_identity(
            identity.provider, identity.provider_subject
        )
        if account_id is None:
            self._reject()
        try:
            account = self._lifecycle.assert_account_active(account_id)
        except AccountOperationFailed as refusal:
            raise AuthenticationFailed(AUTHENTICATION_FAILURE) from refusal
        return account.account_id

    @staticmethod
    def _reject() -> None:
        raise AuthenticationFailed(AUTHENTICATION_FAILURE)


@dataclass(frozen=True, slots=True)
class RecoverySecurityPurgeReport:
    """Count-only retention evidence, containing no identity data."""

    purged_events: int


class RecoverySecurityEventSweeper:
    """Purge recovery security evidence at the twelve-month audit horizon."""

    def __init__(
        self,
        events: RecoverySecurityEventStore,
        *,
        retention_months: int = MEMBERSHIP_EVENT_RETENTION_MONTHS,
    ) -> None:
        self._events = events
        self._retention_months = retention_months

    def sweep(self, *, now: datetime) -> RecoverySecurityPurgeReport:
        horizon = _months_before(now, self._retention_months)
        return RecoverySecurityPurgeReport(
            purged_events=self._events.purge_events_before(horizon)
        )


__all__ = [
    "RecoverySecurityEvent",
    "RecoverySecurityEventStore",
    "RecoverySecurityEventSweeper",
    "RecoverySecurityPurgeReport",
    "RecoverySecurityService",
]
