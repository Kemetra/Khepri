from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Protocol

_INVITATION_FAILURE = "Invitation is invalid or unavailable."


class InvitationRejected(ValueError):
    pass


class ConsentRequired(PermissionError):
    pass


class SessionExpired(PermissionError):
    pass


class CrossSessionAccessDenied(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class Invitation:
    invitation_id: str
    secret_salt: bytes
    secret_digest: bytes
    expires_at: datetime
    redeemed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class SessionScope:
    owner_id: str
    session_id: str


@dataclass(frozen=True, slots=True)
class BetaSession:
    owner_id: str
    session_id: str
    created_at: datetime
    content_expires_at: datetime
    consent_version: str | None = None
    consented_at: datetime | None = None
    deletion_requested_at: datetime | None = None
    content_deleted_at: datetime | None = None


class SessionStore(Protocol):
    def add_invitation(self, invitation: Invitation) -> None: ...

    def get_invitation(self, invitation_id: str) -> Invitation | None: ...

    def redeem_invitation(
        self,
        invitation_id: str,
        redeemed_at: datetime,
        session: BetaSession,
    ) -> bool: ...

    def update_session(self, session: BetaSession) -> None: ...

    def get_session(self, session_id: str) -> BetaSession | None: ...

    def open_commercial_session_row(self, session: BetaSession) -> None: ...

    def get_session_for_owner(self, owner_id: str, session_id: str) -> BetaSession | None: ...


def open_commercial_session(
    store: SessionStore,
    *,
    owner_id: str,
    now: datetime,
) -> BetaSession:
    """Open an analysis session for an already-resolved organization scope (`R7-07`).

    Sibling to `InvitationService.redeem`, and deliberately unlike it in two ways.

    **It accepts the `owner_id` rather than minting one.** `redeem` mints `own_...` per redemption
    because a beta participant has no organization behind them. Here the organization's scope *is*
    the analysis scope (`KHEPRI-DEC-019` §1), `allocate_owner_id` in `khepri.rca` is that key's
    single definition, and `R7-01` §4 lists "mint an `owner_id` of its own" among the things the
    bridge must never do -- a second minting site is how `FR-035`'s stability breaks.

    **It performs no authorization, and takes nothing it could authorize with.** The parameters are
    a store, an opaque key, and a clock. No `account_id`, `organization_id`, name, slug, or email
    reaches this function, so `FR-032` and `FR-033` hold by absence rather than by inspection.
    Authorization happens one layer up, in `khepri.runtime`'s bridge, through
    `IsolationService.resolve_scope`. Two authorization sites is how two authorization answers
    eventually differ.

    `session_id` stays RRA's to mint: it is per-analysis, not per-organization, and one scope now
    holds many sessions -- which is what migration `20260817_0017` enabled. `content_expires_at`
    follows `redeem`'s horizon so a commercial analysis and a beta one age out identically; nothing
    in `KHEPRI-DEC-021` authorizes a different one.
    """
    session = BetaSession(
        owner_id=owner_id,
        session_id=f"ses_{secrets.token_urlsafe(18)}",
        created_at=now,
        content_expires_at=now + timedelta(days=7),
    )
    store.open_commercial_session_row(session)
    return session


class InvitationService:
    def __init__(self, store: SessionStore) -> None:
        self._store = store

    def issue_invitation(self, *, expires_at: datetime) -> str:
        invitation_id = f"inv_{secrets.token_urlsafe(18)}"
        secret = secrets.token_urlsafe(32)
        salt = secrets.token_bytes(16)
        invitation = Invitation(
            invitation_id=invitation_id,
            secret_salt=salt,
            secret_digest=self._digest(secret, salt),
            expires_at=expires_at,
        )
        self._store.add_invitation(invitation)
        return f"kiv1.{invitation_id}.{secret}"

    def parse_token(self, token: str) -> tuple[str, str]:
        try:
            prefix, invitation_id, secret = token.split(".")
        except ValueError as error:
            raise InvitationRejected(_INVITATION_FAILURE) from error
        if prefix != "kiv1" or not invitation_id.startswith("inv_") or not secret:
            raise InvitationRejected(_INVITATION_FAILURE)
        return invitation_id, secret

    def verify_secret(self, secret: str, invitation: Invitation) -> bool:
        candidate = self._digest(secret, invitation.secret_salt)
        return hmac.compare_digest(candidate, invitation.secret_digest)

    @staticmethod
    def _digest(secret: str, salt: bytes) -> bytes:
        return hashlib.scrypt(
            secret.encode(),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )

    def redeem(self, token: str, *, now: datetime) -> BetaSession:
        invitation_id, secret = self.parse_token(token)
        invitation = self._store.get_invitation(invitation_id)
        if (
            invitation is None
            or invitation.redeemed_at is not None
            or invitation.expires_at <= now
            or not self.verify_secret(secret, invitation)
        ):
            raise InvitationRejected(_INVITATION_FAILURE)

        session = BetaSession(
            owner_id=f"own_{secrets.token_urlsafe(18)}",
            session_id=f"ses_{secrets.token_urlsafe(18)}",
            created_at=now,
            content_expires_at=now + timedelta(days=7),
        )
        if not self._store.redeem_invitation(invitation_id, now, session):
            raise InvitationRejected(_INVITATION_FAILURE)
        return session

    def record_consent(
        self,
        session_id: str,
        *,
        consent_version: str,
        now: datetime,
    ) -> BetaSession:
        consent_version = consent_version.strip()
        if not consent_version:
            raise ValueError("Consent version is required.")
        session = self._store.get_session(session_id)
        if (
            session is None
            or now >= session.content_expires_at
            or session.deletion_requested_at is not None
        ):
            raise SessionExpired("Session content has expired.")
        consented = replace(
            session,
            consent_version=consent_version,
            consented_at=now,
        )
        self._store.update_session(consented)
        return consented


def require_upload_consent(session: BetaSession, *, now: datetime) -> None:
    if now >= session.content_expires_at or session.deletion_requested_at is not None:
        raise SessionExpired("Session content has expired.")
    if session.consent_version is None or session.consented_at is None:
        raise ConsentRequired("Consent is required before upload.")


def assert_same_scope(expected: SessionScope, resource: SessionScope) -> None:
    if expected != resource:
        raise CrossSessionAccessDenied("Resource is unavailable.")
