"""#517: no session write may clear or re-date `revoked_at` from a caller's snapshot.

**The defect.** `SqlSessionStore.save_session` wrote `row.revoked_at = session.revoked_at` from the
record the caller held. A caller holding a snapshot read *before* account recovery's `revoke_all`
(`FR-007`) could write it back after, and the write set `revoked_at = NULL`: the session survived
recovery. `KHEPRI-DEC-015` requires a revoked session to authorize nothing "from the trigger
instant". The shipped path is `external_auth_api`: mint a session, then `switcher.switch(...)`, with
recovery able to commit between the two.

**Why every test re-reads through a fresh store.** The defect is in what is persisted, not in what is
returned, so an assertion on the returned record cannot see it.

**How the interleaving is made deterministic on SQLite.** `OrganizationSwitcher` and
`SessionService.revoke` read the session *inside* the call, so the stale snapshot cannot be handed
in from outside. `_RecoveryDuringRead` runs the real `revoke_all_for_account` immediately after the
real read returns and before the caller writes -- exactly the window recovery commits into. Every
write still goes through the real `SqlSessionStore`.
"""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.errors import AuthenticationFailed
from khepri.rca.persistence import SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.sessions import Session, hash_session_id
from khepri.rca.switching import OrganizationSwitcher
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    NOW,
    factory_fixture,
    two_owner_organization,
)

LIFETIME = timedelta(hours=12)
RECOVERED_AT = NOW + timedelta(minutes=1)
LATER = NOW + timedelta(minutes=2)


class _RecoveryDuringRead(SqlSessionStore):
    """A real store where account recovery commits right after the first session read."""

    def __init__(self, factory: sessionmaker, account_id: str, *, at: datetime) -> None:
        super().__init__(factory)
        self._account_id = account_id
        self._at = at
        self._fired = False

    def get_session(self, session_id_hash: str) -> Session | None:
        snapshot = super().get_session(session_id_hash)
        if not self._fired:
            self._fired = True
            assert self.revoke_all_for_account(self._account_id, now=self._at) == 1
        return snapshot


def _stored(factory: sessionmaker, token: str) -> Session:
    stored = SqlSessionStore(factory).get_session(hash_session_id(token))
    assert stored is not None
    return stored


def _assert_still_revoked(factory: sessionmaker, token: str) -> None:
    """Refused by a fresh service, and `revoked_at` is recovery's instant, not moved or cleared."""
    fresh = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
    with pytest.raises(AuthenticationFailed):
        fresh.resolve(token, now=LATER)
    assert _stored(factory, token).revoked_at == RECOVERED_AT


def _live_session(factory: sessionmaker) -> tuple[str, str, str]:
    """An account with one organization and one live session: (account, organization, token)."""
    stack = two_owner_organization(factory)
    account_id = stack.first.account_id
    token = SessionService(SqlSessionStore(factory), lifetime=LIFETIME).create(account_id, now=NOW)
    return account_id, stack.organization.organization_id, token


class TestPointingAStaleSnapshot:
    """The reproduction from #517, against the real store."""

    def test_a_switch_from_a_snapshot_taken_before_recovery_does_not_un_revoke(
        self, factory: sessionmaker
    ) -> None:
        account_id, organization_id, token = _live_session(factory)
        service = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
        stale = service.resolve(token, now=NOW)

        assert service.revoke_all(account_id, now=RECOVERED_AT) == 1
        with pytest.raises(AuthenticationFailed):
            service.resolve(token, now=LATER)

        with suppress(AuthenticationFailed):
            service.point_at_organization(stale, organization_id)

        _assert_still_revoked(factory, token)

    def test_clearing_from_a_snapshot_taken_before_recovery_does_not_un_revoke(
        self, factory: sessionmaker
    ) -> None:
        account_id, _, token = _live_session(factory)
        service = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
        stale = service.resolve(token, now=NOW)
        service.revoke_all(account_id, now=RECOVERED_AT)

        with suppress(AuthenticationFailed):
            service.point_at_organization(stale, None)

        _assert_still_revoked(factory, token)

    def test_pointing_a_revoked_session_is_refused(self, factory: sessionmaker) -> None:
        """The refusal is the uniform one `resolve` gives, not a silent success."""
        account_id, organization_id, token = _live_session(factory)
        service = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
        stale = service.resolve(token, now=NOW)
        service.revoke_all(account_id, now=RECOVERED_AT)

        with pytest.raises(AuthenticationFailed):
            service.point_at_organization(stale, organization_id)


class TestTheSwitcherRacingRecovery:
    """`OrganizationSwitcher` resolves inside the call; recovery commits between read and write."""

    def _switcher(self, factory: sessionmaker, account_id: str) -> OrganizationSwitcher:
        store = _RecoveryDuringRead(factory, account_id, at=RECOVERED_AT)
        service = SessionService(store, lifetime=LIFETIME)
        return OrganizationSwitcher(service, SqlOrganizationStore(factory))

    def test_clear_does_not_un_revoke(self, factory: sessionmaker) -> None:
        account_id, _, token = _live_session(factory)

        with pytest.raises(AuthenticationFailed):
            self._switcher(factory, account_id).clear(token, now=NOW)

        _assert_still_revoked(factory, token)

    def test_switch_does_not_un_revoke(self, factory: sessionmaker) -> None:
        """The shipped path: `external_auth_api` mints a session and then switches."""
        account_id, organization_id, token = _live_session(factory)

        with pytest.raises(AuthenticationFailed):
            self._switcher(factory, account_id).switch(token, organization_id, now=NOW)

        _assert_still_revoked(factory, token)
        assert _stored(factory, token).active_organization_id is None


class TestRevokeRacingRecovery:
    """`revoke` must not re-date a revocation that landed after its read (logout, `FR-219`)."""

    def test_revoke_does_not_re_date_a_concurrent_recovery(self, factory: sessionmaker) -> None:
        account_id, _, token = _live_session(factory)
        store = _RecoveryDuringRead(factory, account_id, at=RECOVERED_AT)
        service = SessionService(store, lifetime=LIFETIME)

        with pytest.raises(AuthenticationFailed):
            service.revoke(token, now=LATER)

        _assert_still_revoked(factory, token)

    def test_revoke_ends_a_live_session_in_the_store(self, factory: sessionmaker) -> None:
        _, _, token = _live_session(factory)
        service = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)

        returned = service.revoke(token, now=RECOVERED_AT)

        assert returned.revoked_at == RECOVERED_AT
        _assert_still_revoked(factory, token)

    def test_revoke_leaves_the_accounts_other_sessions_live(self, factory: sessionmaker) -> None:
        account_id, _, token = _live_session(factory)
        service = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
        other = service.create(account_id, now=NOW)

        service.revoke(token, now=RECOVERED_AT)

        assert service.resolve(other, now=LATER).revoked_at is None
