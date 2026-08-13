"""KHEPRI-DEC-015 §2b: the 24-month retention horizon and the opaque tombstone."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import (
    AccountOperationFailed,
    AuthenticationFailed,
)
from khepri.rca.lifecycle import (
    RETENTION_MONTHS,
    AccountRetentionSweeper,
    LifecycleService,
    _months_before,
)
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
        pytest.param(729, False, id="just_before_the_horizon"),
        pytest.param(760, True, id="one_day_after_the_horizon"),
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

    AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=760))

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
        now=NOW + timedelta(days=3800)
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
    later = NOW + timedelta(days=760)

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

    AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=760))

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
    AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=760))

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
    # The cutoff a sweep 24 calendar months after NOW computes: disabled strictly before this
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
        now=NOW + timedelta(days=760)
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
    later = NOW + timedelta(days=760)

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




# --- the horizon is calendar months, and the purge re-checks eligibility ------------------


@pytest.mark.parametrize(
    ("disabled_on", "swept_on", "expect_purged"),
    [
        # 730 days from 2027-01-01 lands on 2028-12-31, a day before the 24-month anniversary,
        # because the interval contains a leap day. Purging identity even a day early is a
        # retention breach under DEC-015 §2b.
        pytest.param(datetime(2027, 1, 1, tzinfo=UTC), datetime(2028, 12, 31, tzinfo=UTC), False,
                     id="one_day_before_the_anniversary"),
        pytest.param(datetime(2027, 1, 1, tzinfo=UTC), datetime(2029, 1, 1, tzinfo=UTC), True,
                     id="on_the_anniversary"),
    ],
)
def test_the_horizon_is_twenty_four_calendar_months(
    disabled_on: datetime, swept_on: datetime, expect_purged: bool
) -> None:
    accounts = MemoryAccountStore()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    LifecycleService(accounts, MemoryOrganizationStore(accounts)).disable_account(
        account.account_id, now=disabled_on
    )

    AccountRetentionSweeper(accounts).sweep(now=swept_on)

    stored = accounts.get_account(account.account_id)
    assert stored is not None
    assert stored.is_purged is expect_purged


def test_a_re_enabled_account_is_not_purged_by_an_in_flight_sweep(
    factory: sessionmaker,
) -> None:
    """The selection and the write are separate transactions, so the write must re-check.

    Reproduced before `purge_if_still_eligible` existed: `enable_account` landing between the
    two made the sweeper write its stale snapshot back, erasing a re-enabled account's email
    and restoring its old `disabled_at`. §2b's purge is deliberately non-recoverable, so that
    was irreversible data loss from an ordinary interleaving.
    """
    accounts = SqlAccountStore(factory)
    lifecycle = LifecycleService(accounts, SqlOrganizationStore(factory))
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    lifecycle.disable_account(account.account_id, now=NOW)

    horizon = _months_before(NOW + timedelta(days=800), RETENTION_MONTHS)
    selected = accounts.accounts_disabled_before(horizon)
    assert selected, "the account must be eligible at selection time"

    lifecycle.enable_account(account.account_id)  # interleaved

    for stale in selected:
        assert not accounts.purge_if_still_eligible(stale.account_id, horizon)

    survivor = accounts.get_account(account.account_id)
    assert survivor is not None
    assert survivor.email == EMAIL, "the re-enabled account keeps its identity"
    assert survivor.is_enabled


@pytest.mark.parametrize(
    ("disabled_on", "expected_horizon_source"),
    [
        # A day-of-month that does not exist 24 months earlier must clamp to the month's last
        # day, not overflow or raise. Without the clamp these are ValueError or a wrong date,
        # and the end-to-end sweep tests never reach them because they all disable on the 1st.
        pytest.param(datetime(2028, 2, 29, tzinfo=UTC), datetime(2026, 2, 28, tzinfo=UTC),
                     id="leap_day_clamps_to_28th"),
        pytest.param(datetime(2027, 3, 31, tzinfo=UTC), datetime(2025, 3, 31, tzinfo=UTC),
                     id="thirty_first_survives_a_31_day_month"),
        pytest.param(datetime(2027, 5, 31, tzinfo=UTC), datetime(2025, 5, 31, tzinfo=UTC),
                     id="may_31st_round_trips"),
    ],
)
def test_the_horizon_clamps_a_day_the_target_month_lacks(
    disabled_on: datetime, expected_horizon_source: datetime
) -> None:
    """`_months_before` is calendar arithmetic, and calendars have ragged months."""
    assert _months_before(disabled_on, RETENTION_MONTHS) == expected_horizon_source


def test_the_horizon_clamps_a_short_target_month_directly() -> None:
    """The clamp itself, at one month's distance, where the ragged edge is unambiguous."""
    assert _months_before(datetime(2027, 3, 31, tzinfo=UTC), 1) == datetime(
        2027, 2, 28, tzinfo=UTC
    )
    assert _months_before(datetime(2028, 3, 31, tzinfo=UTC), 1) == datetime(
        2028, 2, 29, tzinfo=UTC
    ), "a leap February clamps to the 29th, not the 28th"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        pytest.param(
            lambda a: a.enabled(),
            "re-enabled between selection and write",
            id="re_enabled",
        ),
        pytest.param(lambda a: a.purged(), "already a tombstone", id="already_purged"),
    ],
)
def test_the_conditional_purge_refuses_a_row_that_stopped_qualifying(
    factory: sessionmaker, mutate, reason: str
) -> None:
    """`purge_if_still_eligible` re-checks each condition, not merely that the row exists.

    Tested directly rather than only through a sweep: the end-to-end path filters eligible rows
    before calling this, so an implementation that dropped its predicate entirely still passed
    every sweep test. Verified by mutation — replacing the whole condition with `or False` left
    the suite green.
    """
    accounts = SqlAccountStore(factory)
    lifecycle = LifecycleService(accounts, SqlOrganizationStore(factory))
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    lifecycle.disable_account(account.account_id, now=NOW)
    horizon = _months_before(NOW + timedelta(days=800), RETENTION_MONTHS)

    stored = accounts.get_account(account.account_id)
    assert stored is not None
    accounts.save_account(mutate(stored))

    assert not accounts.purge_if_still_eligible(account.account_id, horizon), reason


def test_the_conditional_purge_refuses_a_row_inside_its_horizon(factory: sessionmaker) -> None:
    """The horizon half of the predicate, isolated from the selection query."""
    accounts = SqlAccountStore(factory)
    lifecycle = LifecycleService(accounts, SqlOrganizationStore(factory))
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    lifecycle.disable_account(account.account_id, now=NOW)

    too_early = _months_before(NOW, RETENTION_MONTHS)
    assert not accounts.purge_if_still_eligible(account.account_id, too_early)

    survivor = accounts.get_account(account.account_id)
    assert survivor is not None and survivor.email == EMAIL
