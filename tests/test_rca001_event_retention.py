"""KHEPRI-DEC-015 §2a: the twelve-month horizon on `FR-014` membership events (`R2-08`).

The sibling account horizon (§2b, 24 months) is tested in `test_rca001_retention.py`. The two are
swept independently and the ordering between them is asserted in `test_rca001_membership_events.py`;
what this file establishes is that the audit horizon is enforced at all, at the right boundary, and
without touching live membership state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.lifecycle import (
    MEMBERSHIP_EVENT_RETENTION_MONTHS,
    MembershipEventSweeper,
    _months_before,
)
from khepri.rca.organizations import OWNER_ROLE, OrganizationService
from khepri.rca.persistence import (
    MembershipEventRow,
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
)

# One day past twelve calendar months from NOW, and one day short of it. Computed from the horizon
# helper rather than written as day counts: 365 days is twelve months only when no leap day
# intervenes, which is the bug `_months_before` exists to prevent.
_HORIZON_ELAPSED = _months_before(NOW, -MEMBERSHIP_EVENT_RETENTION_MONTHS) + timedelta(days=1)
_HORIZON_PENDING = _months_before(NOW, -MEMBERSHIP_EVENT_RETENTION_MONTHS) - timedelta(days=1)


def _event_count(factory: sessionmaker) -> int:
    with factory() as database:
        return database.execute(select(func.count()).select_from(MembershipEventRow)).scalar()


def _membership_count(factory: sessionmaker) -> int:
    with factory() as database:
        return database.execute(select(func.count()).select_from(MembershipRow)).scalar()


def _grant_owner(factory: sessionmaker, organization_id: str, account_id: str) -> None:
    """A second owner-role row, written directly.

    No service operation creates a membership beyond the founding owner — invitations are `R4` — so
    a test needing a co-owner writes the row. It emits no event deliberately: these tests count
    events, and a helper that added one would make the counts describe the helper.
    """
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization_id, account_id=account_id, role=OWNER_ROLE
            )
        )


def _organization_with_one_event(factory: sessionmaker) -> str:
    """An organization whose creation emitted exactly one event, returning the owner's id."""
    accounts = SqlAccountStore(factory)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    OrganizationService(SqlOrganizationStore(factory)).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    return owner.account_id


# --- the horizon boundary ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("swept_at", "expect_purged"),
    [
        pytest.param(_HORIZON_PENDING, False, id="one_day_before_the_horizon"),
        pytest.param(_HORIZON_ELAPSED, True, id="one_day_after_the_horizon"),
    ],
)
def test_an_event_survives_until_its_horizon_elapses(
    factory: sessionmaker, swept_at: datetime, expect_purged: bool
) -> None:
    _organization_with_one_event(factory)
    assert _event_count(factory) == 1, "the creation event was written"

    report = MembershipEventSweeper(SqlOrganizationStore(factory)).sweep(now=swept_at)

    assert _event_count(factory) == (0 if expect_purged else 1)
    assert report.purged_events == (1 if expect_purged else 0)


def test_the_horizon_instant_itself_purges(factory: sessionmaker) -> None:
    """`<=`, agreeing with `MembershipEvent.is_purgeable_at`.

    The domain method and the SQL predicate must share the boundary. If they disagreed, the same
    event would be purgeable according to the domain and retained by the sweeper.
    """
    _organization_with_one_event(factory)

    swept = MembershipEventSweeper(SqlOrganizationStore(factory)).sweep(
        now=_months_before(NOW, -MEMBERSHIP_EVENT_RETENTION_MONTHS)
    )

    assert swept.purged_events == 1
    assert _event_count(factory) == 0


def test_the_horizon_is_calendar_months_not_a_day_count(factory: sessionmaker) -> None:
    """365 days is twelve months only when no leap day intervenes.

    The horizon is `now` shifted back twelve calendar months, so an event dated 2028-02-29 is
    swept on the first pass whose horizon reaches it. February 2028 has 29 days and February 2029
    has 28, so the horizon clamps: sweeping on 2029-02-28 yields a 2028-02-28 horizon, which does
    *not* reach the leap-day event. It becomes eligible on 2029-03-01.

    A `timedelta(days=365)` horizon would place it at 2028-02-29 on a 2029-02-28 sweep and purge
    the event a day early. Purging governed audit data before its horizon is a retention breach in
    the same way `§2b`'s day-count bug was, which is why `_months_before` is calendar arithmetic.
    """
    leap_day = datetime(2028, 2, 29, 12, 0, tzinfo=UTC)
    accounts = SqlAccountStore(factory)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    OrganizationService(SqlOrganizationStore(factory)).create_organization(
        "Acme", owner.account_id, now=leap_day
    )
    sweeper = MembershipEventSweeper(SqlOrganizationStore(factory))

    # The clamped anniversary does not reach a 29th; a day-count horizon would.
    assert sweeper.sweep(now=datetime(2029, 2, 28, 12, 0, tzinfo=UTC)).purged_events == 0
    assert sweeper.sweep(now=datetime(2029, 3, 1, 12, 0, tzinfo=UTC)).purged_events == 1


# --- the pass leaves live state alone -------------------------------------------------------


def test_purging_events_leaves_membership_state_intact(factory: sessionmaker) -> None:
    """`FR-014` data expiring must not disturb the membership it described.

    This is the property that made the R2-03 column drop safe: attribution lives on an expiring
    table precisely so that its expiry is not a change to live state.
    """
    owner_id = _organization_with_one_event(factory)
    store = SqlOrganizationStore(factory)
    organization = store.memberships_for_account(owner_id)[0].organization_id
    assert _membership_count(factory) == 1

    MembershipEventSweeper(store).sweep(now=_HORIZON_ELAPSED)

    assert _membership_count(factory) == 1, "the membership row outlived its audit event"
    surviving = store.get_membership(organization, owner_id)
    assert surviving is not None
    assert surviving.role == OWNER_ROLE, "the role is unchanged"


def test_only_expired_events_are_purged(factory: sessionmaker) -> None:
    """A selective horizon, not a truncation.

    Two events on one membership at different times: the older passes its horizon while the newer
    has not. A sweeper that ignored `occurred_at` would empty the table and still satisfy a test
    that only counted zero.
    """
    store = SqlOrganizationStore(factory)
    owner_id = _organization_with_one_event(factory)
    organization = store.memberships_for_account(owner_id)[0].organization_id
    # A second event eleven months later, so one horizon elapses and the other does not. Demotion
    # of a *second* owner, because demoting the only owner is what FR-013 refuses.
    second = AccountService(SqlAccountStore(factory)).create_account(OTHER_EMAIL, CREDENTIAL)
    _grant_owner(factory, organization, second.account_id)
    later = _months_before(NOW, -11)
    OrganizationService(store).demote_to_member(
        organization, second.account_id, actor_account_id=owner_id, now=later
    )
    assert _event_count(factory) == 2

    report = MembershipEventSweeper(store).sweep(now=_HORIZON_ELAPSED)

    assert report.purged_events == 1
    with factory() as database:
        remaining = database.scalars(select(MembershipEventRow)).all()
    assert len(remaining) == 1
    assert remaining[0].occurred_at.replace(tzinfo=UTC) == later, "the newer event survived"


def test_a_pass_over_no_expired_events_purges_nothing(factory: sessionmaker) -> None:
    _organization_with_one_event(factory)

    report = MembershipEventSweeper(SqlOrganizationStore(factory)).sweep(now=NOW)

    assert report.purged_events == 0
    assert _event_count(factory) == 1


def test_the_pass_is_idempotent(factory: sessionmaker) -> None:
    """Running twice purges once. The second pass finds nothing rather than failing."""
    _organization_with_one_event(factory)
    sweeper = MembershipEventSweeper(SqlOrganizationStore(factory))

    assert sweeper.sweep(now=_HORIZON_ELAPSED).purged_events == 1
    assert sweeper.sweep(now=_HORIZON_ELAPSED).purged_events == 0


# --- the report is content-free (FR-040) ----------------------------------------------------


def test_the_report_carries_counts_only() -> None:
    """`FR-040`: no identifier is echoed by a retention pass."""
    accounts = MemoryAccountStore()
    organizations = MemoryOrganizationStore(accounts)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    OrganizationService(organizations).create_organization("Acme", owner.account_id, now=NOW)

    report = MembershipEventSweeper(organizations).sweep(now=_HORIZON_ELAPSED)

    assert report.purged_events == 1
    rendered = repr(report)
    assert owner.account_id not in rendered
    assert EMAIL not in rendered


# --- the fake agrees with SQL ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("swept_at", "expected"),
    [
        pytest.param(_HORIZON_PENDING, 0, id="before"),
        pytest.param(_months_before(NOW, -MEMBERSHIP_EVENT_RETENTION_MONTHS), 1, id="at"),
        pytest.param(_HORIZON_ELAPSED, 1, id="after"),
    ],
)
def test_the_memory_store_matches_sql_at_every_boundary(
    factory: sessionmaker, swept_at: datetime, expected: int
) -> None:
    """The fake and the real store must agree, including on the inclusive boundary.

    A fake that purged exclusively where SQL purges inclusively would make unit tests disagree with
    production about the one instant the horizon turns on.
    """
    accounts = MemoryAccountStore()
    organizations = MemoryOrganizationStore(accounts)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    OrganizationService(organizations).create_organization("Acme", owner.account_id, now=NOW)
    _organization_with_one_event(factory)

    in_memory = MembershipEventSweeper(organizations).sweep(now=swept_at)
    in_sql = MembershipEventSweeper(SqlOrganizationStore(factory)).sweep(now=swept_at)

    assert in_memory.purged_events == expected
    assert in_sql.purged_events == expected


# --- a configured horizon is respected ------------------------------------------------------


def test_the_retention_window_is_configurable_for_tests_only() -> None:
    """The default is the governed twelve months; the parameter exists so a test can compress it.

    Mirrors `AccountRetentionSweeper`. Production wiring passes no override, which
    `test_local_sweeper.py` asserts.
    """
    accounts = MemoryAccountStore()
    organizations = MemoryOrganizationStore(accounts)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    OrganizationService(organizations).create_organization("Acme", owner.account_id, now=NOW)

    one_month = MembershipEventSweeper(organizations, retention_months=1)

    assert one_month.sweep(now=_months_before(NOW, -1)).purged_events == 1
