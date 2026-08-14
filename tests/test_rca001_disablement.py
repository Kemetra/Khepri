"""Disablement and re-enablement: verifier destruction and FR-008 (`RCA-001` #149)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import (
    AuthenticationFailed,
    ScopeAccessDenied,
)
from khepri.rca.isolation import IsolationService
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import (
    AccountRow,
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
    memory_stack,
)

# --- FR-008: a disabled account fails authentication ------------------------------------


def test_disablement_destroys_the_verifier(factory: sessionmaker) -> None:
    """KHEPRI-DEC-015: destruction is "immediate, non-recoverable" on disablement.

    Asserts the database columns, not the returned object. An implementation that cleared the
    verifier on the record it returned but wrote the old row back would satisfy an
    object-level assertion while leaving a recoverable credential at rest.
    """
    accounts = SqlAccountStore(factory)
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    lifecycle = LifecycleService(accounts, SqlOrganizationStore(factory))

    lifecycle.disable_account(account.account_id, now=NOW)

    with factory() as database:
        row = database.get(AccountRow, account.account_id)
        assert row is not None
        assert row.credential_salt is None
        assert row.credential_digest is None
        assert (row.kdf_n, row.kdf_r, row.kdf_p) == (None, None, None)
        assert row.disabled_at is not None
        assert row.email == EMAIL, "the identity survives until the 24-month horizon"


def test_a_disabled_account_fails_authentication(factory: sessionmaker) -> None:
    accounts = SqlAccountStore(factory)
    service = AccountService(accounts)
    account = service.create_account(EMAIL, CREDENTIAL)
    LifecycleService(accounts, SqlOrganizationStore(factory)).disable_account(
        account.account_id, now=NOW
    )

    with pytest.raises(AuthenticationFailed):
        service.authenticate(EMAIL, CREDENTIAL)


def test_a_disabled_account_fails_authentication_even_with_a_surviving_verifier() -> None:
    """FR-008 must not depend on verifier destruction having succeeded.

    Disablement destroys the verifier, so in practice a disabled account is already
    unverifiable. This drives the *other* guard: a row that is disabled but still holds
    material — a partial write, a restore, a future code path that forgets — must still refuse.
    Without the `is_enabled` check in `_is_verifiable`, this test fails.
    """
    accounts = MemoryAccountStore()
    service = AccountService(accounts)
    account = service.create_account(EMAIL, CREDENTIAL)
    still_verifiable = account.__class__._from_storage(
        account_id=account.account_id,
        email=account.email,
        verifier=account.verifier,  # deliberately NOT destroyed
        disabled_at=NOW,
    )
    accounts.save_account(still_verifiable)

    with pytest.raises(AuthenticationFailed):
        service.authenticate(EMAIL, CREDENTIAL)


def test_a_disabled_account_is_refused_uniformly(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004: the disabled path must cost what every other rejection path costs.

    Placing the disabled check in `authenticate` as an early raise would satisfy FR-008 and
    reintroduce the enumeration oracle FR-004 forbids, because it would skip the hash. This
    reuses the existing uniform-cost harness rather than building a second one.
    """
    from tests.test_rca001_accounts import _rejection_work

    accounts = MemoryAccountStore()
    service = AccountService(accounts)
    account = service.create_account(EMAIL, CREDENTIAL)
    service.create_account(OTHER_EMAIL, CREDENTIAL)
    LifecycleService(accounts, MemoryOrganizationStore(accounts)).disable_account(
        account.account_id, now=NOW
    )

    issued = _rejection_work(
        service,
        monkeypatch,
        (
            ("missing", "nobody@example.test", CREDENTIAL),
            ("disabled", EMAIL, CREDENTIAL),
            ("wrong_credential", OTHER_EMAIL, "wrong credential"),
        ),
    )

    from khepri.rca.credentials import DEFAULT_KDF

    assert issued == dict.fromkeys(issued, [DEFAULT_KDF])


# --- the carried risk: resolve_scope ----------------------------------------------------


def test_resolve_scope_refuses_a_disabled_account(factory: sessionmaker) -> None:
    """Recorded as a carried risk on slice 1; live the moment disablement exists.

    Without this, a disabled account keeps resolving its organization's isolation scope and
    reaching every RRA capability behind it — the authority FR-008 says must stop.
    """
    accounts = SqlAccountStore(factory)
    organizations = SqlOrganizationStore(factory)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=member.account_id,
                role="member",
            )
        )
    isolation = IsolationService(organizations, accounts)

    assert isolation.resolve_scope(member.account_id, organization.organization_id)

    LifecycleService(accounts, organizations).disable_account(member.account_id, now=NOW)

    with pytest.raises(ScopeAccessDenied):
        isolation.resolve_scope(member.account_id, organization.organization_id)




def test_a_re_enabled_account_still_cannot_authenticate_with_the_old_credential() -> None:
    """KHEPRI-DEC-015 §5 gives a destroyed verifier no path back.

    Re-enablement exists because §2b justifies the 24-month horizon partly by it. It restores
    the account's ability to act, not its old credential.
    """
    accounts = MemoryAccountStore()
    service = AccountService(accounts)
    account = service.create_account(EMAIL, CREDENTIAL)
    lifecycle = LifecycleService(accounts, MemoryOrganizationStore(accounts))

    lifecycle.disable_account(account.account_id, now=NOW)
    re_enabled = lifecycle.enable_account(account.account_id)

    assert re_enabled.is_enabled
    assert re_enabled.verifier is None
    with pytest.raises(AuthenticationFailed):
        service.authenticate(EMAIL, CREDENTIAL)


def test_disablement_is_idempotent_and_keeps_the_original_horizon() -> None:
    """A second disablement must not restart the 24-month clock."""
    accounts = MemoryAccountStore()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    lifecycle = LifecycleService(accounts, MemoryOrganizationStore(accounts))

    first = lifecycle.disable_account(account.account_id, now=NOW)
    later = lifecycle.disable_account(account.account_id, now=NOW + timedelta(days=100))

    assert later.disabled_at == first.disabled_at


