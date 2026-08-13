"""KHEPRI-DEC-015 §2b: the 24-month retention horizon and the opaque tombstone."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import (
    AccountOperationFailed,
    AuthenticationFailed,
)
from khepri.rca.lifecycle import RETENTION_DAYS, AccountRetentionSweeper, LifecycleService
from khepri.rca.persistence import (
    AccountRow,
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

# --- KHEPRI-DEC-015 §2b: the 24-month horizon -------------------------------------------


@pytest.mark.parametrize(
    ("elapsed_days", "expect_purged"),
    [
        pytest.param(RETENTION_DAYS - 1, False, id="one_day_before_the_horizon"),
        pytest.param(RETENTION_DAYS + 1, True, id="one_day_after_the_horizon"),
    ],
)
def test_the_sweeper_purges_only_after_the_horizon(
    elapsed_days: int, expect_purged: bool
) -> None:
    accounts = MemoryAccountStore()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    LifecycleService(accounts, MemoryOrganizationStore()).disable_account(
        account.account_id, now=NOW
    )

    report = AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=elapsed_days))

    stored = accounts.get_account(account.account_id)
    assert stored is not None
    assert stored.is_purged is expect_purged
    assert report.purged_accounts == (1 if expect_purged else 0)


def test_the_sweeper_leaves_an_opaque_tombstone() -> None:
    """§2b: "an opaque account identifier and the disablement timestamp -- no email address,
    no credential verifier, no profile data"."""
    accounts = MemoryAccountStore()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    lifecycle = LifecycleService(accounts, MemoryOrganizationStore())
    disabled = lifecycle.disable_account(account.account_id, now=NOW)

    AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=RETENTION_DAYS + 1))

    tombstone = accounts.get_account(account.account_id)
    assert tombstone is not None
    assert tombstone.account_id == account.account_id
    assert tombstone.disabled_at == disabled.disabled_at
    assert tombstone.email is None
    assert tombstone.verifier is None
    assert EMAIL not in repr(tombstone)


def test_an_enabled_account_is_never_swept() -> None:
    """The horizon runs from disablement. An account that was never disabled has no horizon."""
    accounts = MemoryAccountStore()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)

    report = AccountRetentionSweeper(accounts).sweep(
        now=NOW + timedelta(days=RETENTION_DAYS * 10)
    )

    assert report.purged_accounts == 0
    stored = accounts.get_account(account.account_id)
    assert stored is not None and not stored.is_purged


def test_sweeping_twice_purges_once() -> None:
    """The count a pass reports must be work it did, not rows it re-examined."""
    accounts = MemoryAccountStore()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    LifecycleService(accounts, MemoryOrganizationStore()).disable_account(
        account.account_id, now=NOW
    )
    sweeper = AccountRetentionSweeper(accounts)
    later = NOW + timedelta(days=RETENTION_DAYS + 1)

    assert sweeper.sweep(now=later).purged_accounts == 1
    assert sweeper.sweep(now=later).purged_accounts == 0


def test_a_purged_address_can_be_registered_again(factory: sessionmaker) -> None:
    """§2b: uniqueness is "a constraint over existing identities, not a permanent reservation".

    This is the A-1 release the nullable email column exists to make possible.
    """
    accounts = SqlAccountStore(factory)
    service = AccountService(accounts)
    account = service.create_account(EMAIL, CREDENTIAL)
    LifecycleService(accounts, SqlOrganizationStore(factory)).disable_account(
        account.account_id, now=NOW
    )

    # Still reserved before the horizon.
    with pytest.raises(AuthenticationFailed):
        service.create_account(EMAIL, "another credential")

    AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=RETENTION_DAYS + 1))

    reborn = service.create_account(EMAIL, "another credential")
    assert reborn.account_id != account.account_id
    with factory() as database:
        rows = database.scalars(select(AccountRow)).all()
        assert len(rows) == 2, "the tombstone survives alongside the new identity"


def test_a_purged_account_cannot_be_re_enabled_or_disabled() -> None:
    """A tombstone has no identity to re-enable it as."""
    accounts = MemoryAccountStore()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    lifecycle = LifecycleService(accounts, MemoryOrganizationStore())
    lifecycle.disable_account(account.account_id, now=NOW)
    AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=RETENTION_DAYS + 1))

    with pytest.raises(AccountOperationFailed):
        lifecycle.enable_account(account.account_id)
    with pytest.raises(AccountOperationFailed):
        lifecycle.disable_account(account.account_id, now=NOW)


# --- the same horizon rules, against real SQL --------------------------------------------
#
# Every sweeper test above runs against MemoryAccountStore, whose `accounts_disabled_before` is
# a second, independent implementation of the selection rule. Mutating the SQL predicate left
# all of them green — verified — so the store's own filtering was entirely unverified. These
# drive `SqlAccountStore` directly. See the warning in `tests/rca_fakes.py`, which this slice
# wrote and then initially ignored.


def test_the_store_selects_only_disabled_unpurged_accounts_past_the_horizon(
    factory: sessionmaker,
) -> None:
    accounts = SqlAccountStore(factory)
    service = AccountService(accounts)
    lifecycle = LifecycleService(accounts, SqlOrganizationStore(factory))
    # The cutoff a sweep at NOW + RETENTION_DAYS would compute: disabled strictly before this
    # instant has elapsed its horizon, disabled after it has not.
    horizon = NOW

    enabled = service.create_account("enabled@example.test", CREDENTIAL)
    recent = service.create_account("recent@example.test", CREDENTIAL)
    elapsed = service.create_account("elapsed@example.test", CREDENTIAL)
    already = service.create_account("already@example.test", CREDENTIAL)

    lifecycle.disable_account(recent.account_id, now=NOW + timedelta(days=1))
    lifecycle.disable_account(elapsed.account_id, now=NOW - timedelta(days=1))
    lifecycle.disable_account(already.account_id, now=NOW - timedelta(days=1))
    purged = accounts.get_account(already.account_id)
    assert purged is not None
    accounts.save_account(purged.purged())

    selected = {
        account.account_id for account in accounts.accounts_disabled_before(horizon)
    }

    assert selected == {elapsed.account_id}, (
        "an enabled account has no horizon; a recently disabled one has not reached it; "
        "a tombstone has already been purged and must not be selected again"
    )
    assert enabled.account_id not in selected


def test_the_sweeper_purges_through_real_sql(factory: sessionmaker) -> None:
    """End to end against the database, so the row state is what is asserted."""
    accounts = SqlAccountStore(factory)
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    LifecycleService(accounts, SqlOrganizationStore(factory)).disable_account(
        account.account_id, now=NOW
    )

    report = AccountRetentionSweeper(accounts).sweep(
        now=NOW + timedelta(days=RETENTION_DAYS + 1)
    )

    assert report.purged_accounts == 1
    with factory() as database:
        row = database.get(AccountRow, account.account_id)
        assert row is not None
        assert row.email is None
        assert row.disabled_at is not None
        assert row.credential_digest is None


def test_sweeping_twice_through_real_sql_purges_once(factory: sessionmaker) -> None:
    """The idempotence rule, against the store that actually implements it.

    The fake-backed version of this test cannot see the SQL predicate: swapping
    `email IS NOT NULL` for a clause every row satisfies leaves it green while the store
    re-selects tombstones on every pass, re-writing rows and reporting work it did not do.
    """
    accounts = SqlAccountStore(factory)
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    LifecycleService(accounts, SqlOrganizationStore(factory)).disable_account(
        account.account_id, now=NOW
    )
    sweeper = AccountRetentionSweeper(accounts)
    later = NOW + timedelta(days=RETENTION_DAYS + 1)

    assert sweeper.sweep(now=later).purged_accounts == 1
    assert sweeper.sweep(now=later).purged_accounts == 0
    assert accounts.accounts_disabled_before(later) == []


def test_saving_an_account_that_does_not_exist_reports_failure(factory: sessionmaker) -> None:
    """A no-op write must not look like a successful one.

    `save_account` returning True for a missing row would make `disable_account` report success
    while nothing was written — the account would stay enabled and the caller would believe it
    had been disabled.
    """
    accounts = SqlAccountStore(factory)
    ghost = AccountService(MemoryAccountStore()).create_account(EMAIL, CREDENTIAL)

    assert accounts.save_account(ghost) is False
    assert accounts.get_account(ghost.account_id) is None


def test_disabling_an_account_the_store_lost_fails_closed() -> None:
    """The service must convert a failed write into a refusal, not return a phantom record."""

    class LosesWrites(MemoryAccountStore):
        def save_account(self, account):  # type: ignore[no-untyped-def]
            return False

    accounts = LosesWrites()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)

    with pytest.raises(AccountOperationFailed):
        LifecycleService(accounts, MemoryOrganizationStore()).disable_account(
            account.account_id, now=NOW
        )


