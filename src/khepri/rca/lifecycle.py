"""Account lifecycle: disablement, re-enablement, and the retention horizon (`RCA-001` #149).

**Why this is its own service.** `FR-013` forbids an organization from reaching zero owner-role
members, and names disabling the final owner as one of the operations that must fail closed. That
question cannot be answered from accounts alone or from organizations alone: it needs the account
being disabled *and* every membership it holds, decided together. `AccountService` has no
membership visibility and `OrganizationService` has no account visibility, so the operation lives
in a third service that holds both stores rather than widening either.

**What this does not do.** Sessions do not exist yet, so `FR-008`'s second clause — every
pre-existing session must cease to authorize, without waiting for expiry — has nothing to attach
to. `assert_account_active` is the chokepoint that clause requires and ships here unused, so the
session slice inherits it instead of inventing its own. See the class docstring for why that
matters.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from khepri.rca.errors import (
    ACCOUNT_FAILURE,
    FINAL_OWNER_FAILURE,
    OWNER_CHANGE_APPLIED,
    OWNER_CHANGE_FINAL_OWNER,
    AccountOperationFailed,
    FinalOwnerProtected,
)

if TYPE_CHECKING:
    from khepri.rca.accounts import Account
    from khepri.rca.stores import AccountStore, OrganizationStore

# KHEPRI-DEC-015 §2b: a disabled account's record and login identity are retained for twenty-four
# months from disablement, then the identity fields are purged and only an opaque tombstone
# remains.
#
# Counted in calendar months, not days. An earlier version used 730 days, which is 24 months only
# when the interval contains no leap day: an account disabled 2027-01-01 became eligible on
# 2028-12-31, one day before its 2029-01-01 anniversary. Purging identity even a day before the
# governed horizon is a retention breach, and §2b bounds retention precisely because an unbounded
# one is indefinite retention by omission.
RETENTION_MONTHS = 24


def _months_before(moment: datetime, months: int) -> datetime:
    """`moment` shifted back by whole calendar months, clamping a short target month.

    `timedelta` has no month unit and a fixed day count drifts across leap years, so the horizon
    is computed on the calendar. A day-of-month that does not exist in the target month (31 March
    going back to February) clamps to that month's last day, which keeps the horizon monotonic.
    """
    month_index = moment.month - 1 - months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


class LifecycleService:
    """Disable, re-enable, and gate accounts, with the FR-013 guard.

    **The guard and the write are one transaction (`#155`, closed).** `disable_account` computes
    the disabled account, then hands it to `apply_owner_reducing_change`, which locks the
    account's owner-role memberships, counts effective owners on the locked rows, and either
    writes or refuses -- all inside one transaction. Competing owner-reducing operations on the
    same organization block at the lock and therefore observe each other's writes.

    Before that, the guard and the write were three round trips on three sessions. Two
    concurrent disablements could both count a live co-owner, both pass, and both commit.
    `tests/test_rca001_concurrent_final_owner.py` reproduced it deterministically against
    PostgreSQL: three contending owners left the organization with zero.

    **Why the store decides rather than this service.** The invariant is an organization-level
    question and the lock belongs on the membership rows, so the check and the write have to sit
    together in persistence. What stays here is the *translation* -- an outcome becomes
    `FinalOwnerProtected` or `AccountOperationFailed` -- so the whole refusal vocabulary,
    including FR-013's deliberately non-uniform message, lives in one place.
    """

    def __init__(self, accounts: AccountStore, organizations: OrganizationStore) -> None:
        self._accounts = accounts
        self._organizations = organizations

    def disable_account(self, account_id: str, *, now: datetime) -> Account:
        """Disable an account, destroying its verifier, unless it is some organization's last owner.

        Failing closed is the point: if the account owns any organization that would be left with
        no owner-role member, nothing is written and `FinalOwnerProtected` is raised (`FR-013`).
        """
        account = self._accounts.get_account(account_id)
        if account is None or account.is_purged:
            raise AccountOperationFailed(ACCOUNT_FAILURE)
        if account.disabled_at is not None:
            return account  # already disabled; idempotent, and the horizon keeps its original start
        # Built before the transaction opens, deliberately. `Account.disabled` goes through a
        # door, and `records.py` records that a door authorizes the thread rather than one call
        # -- so holding one across a lock wait would be a far wider grant than it looks.
        disabled = account.disabled(now=now)
        outcome = self._organizations.apply_owner_reducing_change(account_id, disabled)
        if outcome == OWNER_CHANGE_FINAL_OWNER:
            raise FinalOwnerProtected(FINAL_OWNER_FAILURE)
        if outcome != OWNER_CHANGE_APPLIED:
            raise AccountOperationFailed(ACCOUNT_FAILURE)
        return disabled

    def enable_account(self, account_id: str) -> Account:
        """Re-enable a disabled account. Its verifier stays destroyed.

        `KHEPRI-DEC-015` §2b justifies the twenty-four month horizon partly so an account can be
        re-enabled "after a dispute, an erroneous disablement, or a lapsed commercial
        relationship", so the capability has to exist for the horizon's rationale to hold.

        §5 gives a destroyed verifier no path back, so this returns an account that cannot
        authenticate until a new credential is set. That is the correct outcome, not a gap: the
        alternative is retaining a verifier through disablement, which §5 forbids outright.

        A purged account cannot be re-enabled — its identity is gone, so there is nothing to
        re-enable it *as*.
        """
        account = self._accounts.get_account(account_id)
        if account is None or account.is_purged:
            raise AccountOperationFailed(ACCOUNT_FAILURE)
        if account.disabled_at is None:
            return account
        enabled = account.enabled()
        if not self._accounts.save_account(enabled):
            raise AccountOperationFailed(ACCOUNT_FAILURE)
        return enabled

    def assert_account_active(self, account_id: str) -> Account:
        """Resolve an account that is currently permitted to act, or fail closed.

        **This is the chokepoint `FR-008` requires and it ships before its caller exists.**
        FR-008 says a disabled account's pre-existing sessions must cease to authorize "with no
        dependence on session expiry". The only way to satisfy that is to consult account state at
        every authorization decision. An implementation that copies an `enabled` flag into the
        session record at login satisfies the type checker and fails the requirement: the copy goes
        stale the instant the account is disabled, and authority then survives until expiry.

        So the session slice must call this on each authorization, not read a cached flag.

        The refusal is uniform (`FR-004`): a disabled account, a purged tombstone, and an account
        that never existed are indistinguishable here.
        """
        account = self._accounts.get_account(account_id)
        if account is None or not account.can_act:
            raise AccountOperationFailed(ACCOUNT_FAILURE)
        return account


@dataclass(frozen=True, slots=True)
class PurgeReport:
    """What one retention pass did, in counts only. No identifier is echoed (`FR-040`)."""

    purged_accounts: int


class AccountRetentionSweeper:
    """Applies `KHEPRI-DEC-015` §2b's twenty-four month horizon to disabled accounts.

    **Why a sweeper rather than lazy evaluation on read.** §2b bounds *retention*, not visibility.
    Under lazy evaluation an account nobody reads is an account whose identity data is never
    purged, so the horizon would elapse and the email address would remain — indefinite retention
    with a policy comment on top, which is exactly what §2b exists to refuse.

    **This is not a scheduler**, following `khepri.local.sweeper`: it runs one pass when called.
    Choosing a cadence is an operational decision, and a loop that invented one here would model a
    deployment nobody has authorized.
    """

    def __init__(
        self, accounts: AccountStore, *, retention_months: int = RETENTION_MONTHS
    ) -> None:
        self._accounts = accounts
        self._retention_months = retention_months

    def sweep(self, *, now: datetime) -> PurgeReport:
        """Purge every account whose retention horizon has elapsed.

        **No FR-013 check here, deliberately, and this is safe only because of where the guard
        actually lives.** A purge does not change who owns an organization: `count_owners` counts
        *effective* owners, and an account must already be disabled to be swept, so it has
        already stopped counting as an owner at the moment of disablement — not at the moment of
        purge. Adding an ownership check here would therefore refuse nothing that
        `disable_account` had not already refused, while implying the purge path is what protects
        FR-013. It is not; disablement is.

        The reason that ordering matters: a purged account keeps its membership row, because
        `fk_rca_membership_account` is `RESTRICT` and the row cannot be deleted. So the guard has
        to discount the *holder's state*, which is what it does. If a later slice ever makes an
        account purgeable without first disabling it, this reasoning breaks and the check has to
        move here.
        """
        horizon = _months_before(now, self._retention_months)
        purged = 0
        for account in self._accounts.accounts_disabled_before(horizon):
            # Re-checked inside the write, not trusted from the selection above: `enable_account`
            # landing between the two would otherwise let this write a stale snapshot back and
            # irreversibly purge an account that is no longer eligible.
            if self._accounts.purge_if_still_eligible(account.account_id, horizon):
                purged += 1
        return PurgeReport(purged_accounts=purged)
