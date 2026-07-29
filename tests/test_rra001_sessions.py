from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from khepri.rra.sessions import (
    BetaSession,
    ConsentRequired,
    CrossSessionAccessDenied,
    Invitation,
    InvitationRejected,
    InvitationService,
    SessionExpired,
    SessionScope,
    assert_same_scope,
    require_upload_consent,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
INVITATION_EXPIRY = NOW + timedelta(days=1)


class MemorySessionStore:
    def __init__(self) -> None:
        self.invitations: dict[str, Invitation] = {}
        self.sessions: dict[str, BetaSession] = {}

    def add_invitation(self, invitation: Invitation) -> None:
        self.invitations[invitation.invitation_id] = invitation

    def get_invitation(self, invitation_id: str) -> Invitation | None:
        return self.invitations.get(invitation_id)

    def redeem_invitation(
        self,
        invitation_id: str,
        redeemed_at: datetime,
        session: BetaSession,
    ) -> bool:
        invitation = self.invitations.get(invitation_id)
        if (
            invitation is None
            or invitation.redeemed_at is not None
            or invitation.expires_at <= redeemed_at
        ):
            return False
        self.invitations[invitation_id] = replace(invitation, redeemed_at=redeemed_at)
        self.sessions[session.session_id] = session
        return True

    def update_session(self, session: BetaSession) -> None:
        self.sessions[session.session_id] = session

    def get_session(self, session_id: str) -> BetaSession | None:
        return self.sessions.get(session_id)


def service_and_store() -> tuple[InvitationService, MemorySessionStore]:
    store = MemorySessionStore()
    return InvitationService(store), store


def test_issuing_invitation_persists_only_a_salted_secret_hash() -> None:
    service, store = service_and_store()

    token = service.issue_invitation(expires_at=INVITATION_EXPIRY)

    invitation_id, secret = service.parse_token(token)
    stored = store.invitations[invitation_id]
    assert secret not in repr(stored)
    assert not hasattr(stored, "secret")
    assert stored.secret_salt != stored.secret_digest
    assert service.verify_secret(secret, stored)


def test_redeeming_invitation_creates_opaque_session_with_seven_day_expiry() -> None:
    service, _ = service_and_store()
    token = service.issue_invitation(expires_at=INVITATION_EXPIRY)

    session = service.redeem(token, now=NOW)

    assert session.owner_id.startswith("own_")
    assert session.session_id.startswith("ses_")
    assert session.owner_id not in token
    assert session.session_id not in token
    assert session.created_at == NOW
    assert session.content_expires_at == NOW + timedelta(days=7)
    assert session.consent_version is None
    assert session.consented_at is None


def test_redeemed_invitation_cannot_be_replayed() -> None:
    service, _ = service_and_store()
    token = service.issue_invitation(expires_at=INVITATION_EXPIRY)
    service.redeem(token, now=NOW)

    with pytest.raises(InvitationRejected, match="invalid or unavailable"):
        service.redeem(token, now=NOW)


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda service: "malformed-token",
        lambda service: service.issue_invitation(expires_at=NOW - timedelta(seconds=1)),
        lambda service: service.issue_invitation(expires_at=INVITATION_EXPIRY) + "changed",
    ],
    ids=["malformed", "expired", "wrong-secret"],
)
def test_invalid_invitations_share_one_public_failure(
    token_factory: Callable[[InvitationService], str],
) -> None:
    service, _ = service_and_store()
    token = token_factory(service)

    with pytest.raises(InvitationRejected) as error:
        service.redeem(token, now=NOW)

    assert str(error.value) == "Invitation is invalid or unavailable."


def test_upload_is_blocked_until_versioned_consent_is_recorded() -> None:
    service, store = service_and_store()
    session = service.redeem(
        service.issue_invitation(expires_at=INVITATION_EXPIRY),
        now=NOW,
    )

    with pytest.raises(ConsentRequired):
        require_upload_consent(session, now=NOW)

    consented = service.record_consent(
        session.session_id,
        consent_version="beta-privacy-v1",
        now=NOW + timedelta(minutes=2),
    )
    require_upload_consent(consented, now=NOW + timedelta(minutes=3))

    assert store.sessions[session.session_id].consent_version == "beta-privacy-v1"
    assert store.sessions[session.session_id].consented_at == NOW + timedelta(minutes=2)


def test_expired_session_cannot_accept_upload_even_with_consent() -> None:
    service, _ = service_and_store()
    session = service.redeem(
        service.issue_invitation(expires_at=INVITATION_EXPIRY),
        now=NOW,
    )
    consented = service.record_consent(
        session.session_id,
        consent_version="beta-privacy-v1",
        now=NOW,
    )

    with pytest.raises(SessionExpired):
        require_upload_consent(consented, now=NOW + timedelta(days=7))


def test_empty_consent_version_does_not_enable_upload() -> None:
    service, store = service_and_store()
    session = service.redeem(
        service.issue_invitation(expires_at=INVITATION_EXPIRY),
        now=NOW,
    )

    with pytest.raises(ValueError, match="Consent version is required"):
        service.record_consent(
            session.session_id,
            consent_version="  ",
            now=NOW,
        )

    with pytest.raises(ConsentRequired):
        require_upload_consent(store.sessions[session.session_id], now=NOW)


def test_resource_scope_fails_closed_for_another_session() -> None:
    expected = SessionScope(owner_id="own_expected", session_id="ses_expected")
    resource = SessionScope(owner_id="own_expected", session_id="ses_other")

    with pytest.raises(CrossSessionAccessDenied):
        assert_same_scope(expected, resource)


def test_resource_scope_allows_only_exact_owner_and_session_match() -> None:
    expected = SessionScope(owner_id="own_expected", session_id="ses_expected")

    assert_same_scope(expected, expected)
