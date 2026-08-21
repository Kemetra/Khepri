"""Khepri-owned consequences after provider-owned credential recovery."""

from __future__ import annotations

from dataclasses import fields
from datetime import timedelta

import pytest

from khepri.rca.accounts import AccountService
from khepri.rca.errors import AuthenticationFailed
from khepri.rca.identity import VerifiedIdentity
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from tests.rca_lifecycle_support import CREDENTIAL, EMAIL, NOW, build_factory

LIFETIME = timedelta(hours=12)
IDENTITY = VerifiedIdentity(provider="example-provider", provider_subject="subject-1")


def _stack():
    """Build real stores after importing the event row into the shared RCA metadata."""
    from khepri.rca.recovery_security import RecoverySecurityService
    from khepri.rca.recovery_security_persistence import SqlRecoverySecurityEventStore

    factory = build_factory()
    accounts = SqlAccountStore(factory)
    sessions = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
    lifecycle = LifecycleService(accounts, SqlOrganizationStore(factory))
    events = SqlRecoverySecurityEventStore(factory)
    service = RecoverySecurityService(sessions, lifecycle, events)
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    assert sessions.link_identity(
        IDENTITY.provider,
        IDENTITY.provider_subject,
        account.account_id,
        now=NOW,
    )
    return factory, accounts, sessions, events, service, account


def test_the_event_retains_only_a_hashed_key_account_and_time() -> None:
    """A raw idempotency key or extensible payload would create a shadow identity log."""
    from khepri.rca.recovery_security import RecoverySecurityEvent

    event = RecoverySecurityEvent.record("acc_example", "attempt-1", now=NOW)

    assert {field.name for field in fields(event)} == {
        "event_key_hash",
        "account_id",
        "occurred_at",
    }
    assert event.event_key_hash == (
        "3dafcfaa6218343276ff42263fe100bab5e2b0475a8d98b96abc88c57bfd9992"
    )
    assert "attempt-1" not in repr(event)


def test_completion_revokes_every_existing_session_and_records_one_event() -> None:
    _factory, _accounts, sessions, events, service, account = _stack()
    tokens = [sessions.create(account.account_id, now=NOW) for _ in range(3)]

    event = service.complete(IDENTITY, idempotency_key="attempt-1", now=NOW)

    assert event.account_id == account.account_id
    assert events.get_event(event.event_key_hash) == event
    for token in tokens:
        with pytest.raises(AuthenticationFailed):
            sessions.resolve(token, now=NOW)


def test_repeating_a_completed_consequence_does_not_revoke_the_new_session() -> None:
    _factory, _accounts, sessions, events, service, account = _stack()
    first = service.complete(IDENTITY, idempotency_key="attempt-1", now=NOW)
    new_token = sessions.create(account.account_id, now=NOW)

    repeated = service.complete(IDENTITY, idempotency_key="attempt-1", now=NOW)

    assert repeated == first
    assert events.get_event_count() == 1
    assert sessions.resolve(new_token, now=NOW).account_id == account.account_id


def test_a_key_already_bound_to_another_account_fails_closed() -> None:
    from khepri.rca.recovery_security import RecoverySecurityEvent

    _factory, accounts, _sessions, events, service, _account = _stack()
    foreign_account = AccountService(accounts).create_account(
        "foreign@example.test", CREDENTIAL
    )
    foreign = RecoverySecurityEvent.record(
        foreign_account.account_id, "attempt-1", now=NOW
    )
    assert events.append_once(foreign) == foreign

    with pytest.raises(AuthenticationFailed):
        service.complete(IDENTITY, idempotency_key="attempt-1", now=NOW)


def test_missing_disabled_and_unlinked_identities_fail_uniformly() -> None:
    _factory, accounts, sessions, _events, service, account = _stack()
    missing = VerifiedIdentity(provider="example-provider", provider_subject="missing")
    purged_identity = VerifiedIdentity(
        provider="example-provider", provider_subject="purged"
    )
    purged = AccountService(accounts).create_account("purged@example.test", CREDENTIAL)
    assert sessions.link_identity(
        purged_identity.provider,
        purged_identity.provider_subject,
        purged.account_id,
        now=NOW,
    )
    assert accounts.save_account(purged.disabled(now=NOW).purged())
    lifecycle = LifecycleService(accounts, SqlOrganizationStore(_factory))
    lifecycle.disable_account(account.account_id, now=NOW)

    messages = []
    for identity in (IDENTITY, purged_identity, missing):
        with pytest.raises(AuthenticationFailed) as caught:
            service.complete(identity, idempotency_key="attempt-1", now=NOW)
        messages.append(str(caught.value))

    lifecycle.enable_account(account.account_id)
    assert sessions.unlink_identity(IDENTITY.provider, IDENTITY.provider_subject)
    with pytest.raises(AuthenticationFailed) as caught:
        service.complete(IDENTITY, idempotency_key="attempt-1", now=NOW)
    messages.append(str(caught.value))

    assert len(set(messages)) == 1


def test_a_link_removed_during_completion_is_refused_after_revocation() -> None:
    _factory, accounts, sessions, events, _service, account = _stack()
    old_token = sessions.create(account.account_id, now=NOW)

    class RemovingSessions:
        def account_for_identity(self, provider: str, subject: str) -> str | None:
            return sessions.account_for_identity(provider, subject)

        def revoke_all(self, account_id: str, *, now):
            revoked = sessions.revoke_all(account_id, now=now)
            sessions.unlink_identity(IDENTITY.provider, IDENTITY.provider_subject)
            return revoked

    from khepri.rca.recovery_security import RecoverySecurityService

    service = RecoverySecurityService(
        RemovingSessions(),
        LifecycleService(accounts, SqlOrganizationStore(_factory)),
        events,
    )

    with pytest.raises(AuthenticationFailed):
        service.complete(IDENTITY, idempotency_key="attempt-1", now=NOW)
    with pytest.raises(AuthenticationFailed):
        sessions.resolve(old_token, now=NOW)
    assert events.get_event_count() == 0

def test_the_twelve_month_horizon_is_inclusive() -> None:
    from khepri.rca.recovery_security import RecoverySecurityEventSweeper

    _factory, _accounts, _sessions, events, service, _account = _stack()
    service.complete(IDENTITY, idempotency_key="attempt-1", now=NOW)

    report = RecoverySecurityEventSweeper(events).sweep(
        now=NOW.replace(year=NOW.year + 1)
    )

    assert report.purged_events == 1
    assert events.get_event_count() == 0
