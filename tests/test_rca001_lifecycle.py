"""Account lifecycle: disablement, the FR-013 guard, and the KHEPRI-DEC-015 retention horizon."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import AccountService
from khepri.rca.errors import (
    AccountOperationFailed,
    AuthenticationFailed,
    FinalOwnerProtected,
    ScopeAccessDenied,
)
from khepri.rca.isolation import IsolationService
from khepri.rca.lifecycle import (
    RETENTION_DAYS,
    AccountRetentionSweeper,
    LifecycleService,
)
from khepri.rca.organizations import OWNER_ROLE, Membership, OrganizationService
from khepri.rca.persistence import (
    AccountRow,
    Base,
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
EMAIL = "owner@example.test"
OTHER_EMAIL = "other@example.test"
CREDENTIAL = "correct horse battery staple"


def _factory() -> sessionmaker:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(name="factory")
def _factory_fixture() -> sessionmaker:
    return _factory()


def _memory() -> tuple[MemoryAccountStore, MemoryOrganizationStore, LifecycleService]:
    accounts = MemoryAccountStore()
    # The fake counts effective owners only when it can see account state, matching the SQL
    # store's join. Without this wiring the fake would disagree with production on exactly the
    # case FR-013 turns on.
    organizations = MemoryOrganizationStore(accounts)
    return accounts, organizations, LifecycleService(accounts, organizations)


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
    LifecycleService(accounts, MemoryOrganizationStore()).disable_account(
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
                changed_by=owner.account_id,
                changed_at=NOW,
            )
        )
    isolation = IsolationService(organizations, accounts)

    assert isolation.resolve_scope(member.account_id, organization.organization_id)

    LifecycleService(accounts, organizations).disable_account(member.account_id, now=NOW)

    with pytest.raises(ScopeAccessDenied):
        isolation.resolve_scope(member.account_id, organization.organization_id)


# --- FR-013: the final owner ------------------------------------------------------------


def test_disabling_the_final_owner_fails_closed() -> None:
    accounts, organizations, lifecycle = _memory()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", owner.account_id, now=NOW
    )

    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(owner.account_id, now=NOW)

    # Fails *closed*: the account is still enabled and the organization still has its owner.
    # A guard that raised after writing would pass the assertion above and fail these.
    stored = accounts.get_account(owner.account_id)
    assert stored is not None and stored.is_enabled
    assert organizations.count_owners(organization.organization_id, excluding_account_id="") == 1


def test_the_final_owner_refusal_names_its_cause() -> None:
    """FR-013 requires the refusal to "state that the final owner cannot be removed".

    A deliberate exception to FR-004's content-free discipline: the caller is already an
    authenticated member, so there is nothing to leak, and a uniform refusal would leave an
    owner unable to distinguish this from a generic failure. Writing this guard with the
    surrounding style's uniform message would satisfy every other test and violate FR-013.
    """
    accounts, organizations, lifecycle = _memory()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    OrganizationService(organizations).create_organization("Acme", owner.account_id, now=NOW)

    with pytest.raises(FinalOwnerProtected) as caught:
        lifecycle.disable_account(owner.account_id, now=NOW)

    assert "final owner" in str(caught.value).lower()


def test_a_non_final_owner_can_be_disabled() -> None:
    """The guard must not refuse every owner — only the last one."""
    accounts, organizations, lifecycle = _memory()
    first = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", first.account_id, now=NOW
    )
    organizations.memberships[(organization.organization_id, second.account_id)] = (
        Membership.create(
            organization.organization_id,
            second.account_id,
            OWNER_ROLE,
            changed_by=first.account_id,
            now=NOW,
        )
    )

    disabled = lifecycle.disable_account(first.account_id, now=NOW)
    assert not disabled.is_enabled


def test_a_non_owner_member_can_be_disabled() -> None:
    accounts, organizations, lifecycle = _memory()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    organizations.memberships[(organization.organization_id, member.account_id)] = (
        Membership.create(
            organization.organization_id,
            member.account_id,
            "member",
            changed_by=owner.account_id,
            now=NOW,
        )
    )

    assert not lifecycle.disable_account(member.account_id, now=NOW).is_enabled


def test_the_guard_checks_every_organization_not_only_the_first() -> None:
    """An account owning two organizations must be refused if it is the last owner of either.

    A guard that returned after inspecting one membership would let this through, and which
    membership comes first is an ordering accident.
    """
    accounts, organizations, lifecycle = _memory()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second_owner = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    shared = OrganizationService(organizations).create_organization(
        "Shared", owner.account_id, now=NOW
    )
    organizations.memberships[(shared.organization_id, second_owner.account_id)] = (
        Membership.create(
            shared.organization_id,
            second_owner.account_id,
            OWNER_ROLE,
            changed_by=owner.account_id,
            now=NOW,
        )
    )
    # The second organization has this account as its only owner.
    OrganizationService(organizations).create_organization("Solo", owner.account_id, now=NOW)

    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(owner.account_id, now=NOW)


def test_the_guard_does_not_abandon_the_scan_at_a_non_owner_membership() -> None:
    """A plain membership encountered first must not stop the scan.

    The distinction from the test above is the *skip* branch, not the loop length. There every
    membership is owner-role, so a guard that returned on the non-owner branch would never
    execute that line and the test would pass while the bug was live — confirmed by mutation
    (`continue` to `return` stayed green). Here the account is a plain member of one
    organization and the sole owner of another, which is the realistic shape of this bug.
    """
    accounts, organizations, lifecycle = _memory()
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    other = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    # A plain membership in someone else's organization...
    theirs = OrganizationService(organizations).create_organization(
        "Theirs", other.account_id, now=NOW
    )
    organizations.memberships[(theirs.organization_id, owner.account_id)] = Membership.create(
        theirs.organization_id,
        owner.account_id,
        "member",
        changed_by=other.account_id,
        now=NOW,
    )
    # ...and sole ownership of their own.
    OrganizationService(organizations).create_organization("Solo", owner.account_id, now=NOW)

    scanned = [m.role for m in organizations.memberships_for_account(owner.account_id)]
    assert "member" in scanned and OWNER_ROLE in scanned, "both membership kinds must be present"

    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(owner.account_id, now=NOW)


# --- re-enablement ----------------------------------------------------------------------


def test_disabling_owners_one_after_another_cannot_strand_an_organization(
    factory: sessionmaker,
) -> None:
    """FR-013 counts owners who can act, not owner-role rows.

    The defect this pins, confirmed against the real store before the fix: disablement never
    touches `rca_memberships`, so a disabled account kept its owner-role row and was counted as
    a live owner by the guard meant to prevent stranding. Disabling a two-owner organization's
    owners one after the other passed the guard *both times* and left the organization with zero
    owners able to authenticate, resolve a scope, or act at all.

    No concurrency and no forgery — two ordinary API calls. This is the same harm the
    `khepri.rca.accounts` module docstring records slice 1 having caused by a different route.
    """
    accounts = SqlAccountStore(factory)
    organizations = SqlOrganizationStore(factory)
    lifecycle = LifecycleService(accounts, organizations)
    first = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", first.account_id, now=NOW
    )
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=second.account_id,
                role=OWNER_ROLE,
                changed_by=first.account_id,
                changed_at=NOW,
            )
        )

    # The first is permitted: the second is still live.
    lifecycle.disable_account(first.account_id, now=NOW)

    # The second must now be refused, because the first no longer counts.
    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(second.account_id, now=NOW)

    survivor = accounts.get_account(second.account_id)
    assert survivor is not None and survivor.is_enabled
    assert (
        organizations.count_owners(organization.organization_id, excluding_account_id="") == 1
    ), "exactly one owner remains, and they can act"


def test_the_memory_fake_counts_owners_the_same_way_the_store_does() -> None:
    """Guards the fake against drifting from `SqlOrganizationStore`.

    Every FR-013 test that uses `_memory()` is only meaningful if the fake's `count_owners`
    agrees with production on the case FR-013 turns on: a disabled account keeps its owner-role
    row and must stop counting. A fake that counted rows would make those tests pass while the
    real store had the defect — which is how the row-counting bug reached review in the first
    place.
    """
    accounts, organizations, lifecycle = _memory()
    first = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", first.account_id, now=NOW
    )
    organizations.memberships[(organization.organization_id, second.account_id)] = (
        Membership.create(
            organization.organization_id,
            second.account_id,
            OWNER_ROLE,
            changed_by=first.account_id,
            now=NOW,
        )
    )
    assert organizations.count_owners(organization.organization_id, excluding_account_id="") == 2

    lifecycle.disable_account(first.account_id, now=NOW)

    assert organizations.count_owners(organization.organization_id, excluding_account_id="") == 1, (
        "the disabled owner keeps its membership row but must stop counting as an owner"
    )
    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(second.account_id, now=NOW)


def test_a_purged_owner_does_not_count_as_an_owner(factory: sessionmaker) -> None:
    """A tombstone keeps its membership row, because the foreign key is RESTRICT.

    So the guard has to discount it by the holder's state or a purged account would be counted
    as an owner forever — the sharpest form of the row-counting defect.
    """
    accounts = SqlAccountStore(factory)
    organizations = SqlOrganizationStore(factory)
    lifecycle = LifecycleService(accounts, organizations)
    first = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", first.account_id, now=NOW
    )
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=second.account_id,
                role=OWNER_ROLE,
                changed_by=first.account_id,
                changed_at=NOW,
            )
        )

    lifecycle.disable_account(first.account_id, now=NOW)
    AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=RETENTION_DAYS + 1))

    # The membership row survived the purge...
    with factory() as database:
        assert (
            database.get(MembershipRow, (organization.organization_id, first.account_id))
            is not None
        )
    # ...but it is not an owner any more.
    assert organizations.count_owners(organization.organization_id, excluding_account_id="") == 1
    with pytest.raises(FinalOwnerProtected):
        lifecycle.disable_account(second.account_id, now=NOW)


def test_a_re_enabled_account_still_cannot_authenticate_with_the_old_credential() -> None:
    """KHEPRI-DEC-015 §5 gives a destroyed verifier no path back.

    Re-enablement exists because §2b justifies the 24-month horizon partly by it. It restores
    the account's ability to act, not its old credential.
    """
    accounts = MemoryAccountStore()
    service = AccountService(accounts)
    account = service.create_account(EMAIL, CREDENTIAL)
    lifecycle = LifecycleService(accounts, MemoryOrganizationStore())

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
    lifecycle = LifecycleService(accounts, MemoryOrganizationStore())

    first = lifecycle.disable_account(account.account_id, now=NOW)
    later = lifecycle.disable_account(account.account_id, now=NOW + timedelta(days=100))

    assert later.disabled_at == first.disabled_at


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


# --- FR-008 clause 2: the chokepoint the session slice must use -------------------------


def test_assert_account_active_refuses_disabled_purged_and_missing() -> None:
    """The chokepoint FR-008's session clause requires, shipped before its caller exists.

    All three refusals are the same exception with the same message (FR-004): a disabled
    account, a tombstone, and an account that never existed are indistinguishable here.
    """
    accounts = MemoryAccountStore()
    lifecycle = LifecycleService(accounts, MemoryOrganizationStore())
    live = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    doomed = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)

    assert lifecycle.assert_account_active(live.account_id).account_id == live.account_id

    lifecycle.disable_account(doomed.account_id, now=NOW)
    messages = []
    for account_id in (doomed.account_id, "acc_never_existed"):
        with pytest.raises(AccountOperationFailed) as caught:
            lifecycle.assert_account_active(account_id)
        messages.append(str(caught.value))

    AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=RETENTION_DAYS + 1))
    with pytest.raises(AccountOperationFailed) as caught:
        lifecycle.assert_account_active(doomed.account_id)
    messages.append(str(caught.value))

    assert len(set(messages)) == 1, "disabled, purged, and missing must be indistinguishable"


# --- composition with #151 ---------------------------------------------------------------


def test_lifecycle_state_cannot_be_changed_by_copying() -> None:
    """#149 and #151 compose: re-enabling by field substitution is refused.

    `dataclasses.replace(account, disabled_at=None)` is the obvious way to write a re-enable
    and would bypass every guard in `LifecycleService` — including the FR-013 check. The
    construction rule from #151 blocks it, which is exactly the trap that slice was closed to
    prevent this one from walking into.
    """
    accounts = MemoryAccountStore()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    disabled = LifecycleService(accounts, MemoryOrganizationStore()).disable_account(
        account.account_id, now=NOW
    )

    with pytest.raises(TypeError, match="create\\(\\) or _from_storage\\(\\)"):
        dataclasses.replace(disabled, disabled_at=None)
