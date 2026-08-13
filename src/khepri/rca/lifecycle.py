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

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from khepri.rca.errors import (
    ACCOUNT_FAILURE,
    FINAL_OWNER_FAILURE,
    AccountOperationFailed,
    FinalOwnerProtected,
)
from khepri.rca.organizations import OWNER_ROLE

if TYPE_CHECKING:
    from khepri.rca.accounts import Account
    from khepri.rca.stores import AccountStore, OrganizationStore

# KHEPRI-DEC-015 §2b: a disabled account's record and login identity are retained for twenty-four
# months from disablement, then the identity fields are purged and only an opaque tombstone
# remains. Expressed in days because `timedelta` has no months and a calendar-accurate horizon
# would make the boundary depend on which months elapsed; the decision's justification (outlasting
# the twelve-month audit horizon, bounded rather than indefinite) is not sensitive to that.
RETENTION_DAYS = 730


class LifecycleService:
    """Disable, re-enable, and gate accounts, with the FR-013 guard.

    **Known limitation: the guard and the write are not in one transaction.** `disable_account`
    reads the account, counts effective owners through the *organization* store, and writes
    through the *account* store — three round trips, each on its own session. Two concurrent
    disablements of a two-owner organization can therefore both pass the check before either
    writes, and both commit, leaving zero owners.

    This is recorded rather than fixed here because fixing it properly needs one transaction
    spanning both stores — either a shared session passed through the store protocols, or
    `SELECT ... FOR UPDATE` on the membership rows — and that is a change to the store seam that
    every RCA service shares, not a change to this service. Doing it inside this slice would mean
    redesigning the persistence boundary in a review loop, which is the failure mode #148 already
    demonstrated and #151 was opened to end.

    What *is* closed here is the sequential path, which needed no concurrency at all: disabling a
    two-owner organization's owners one after another passed the guard both times, because
    `count_owners` counted membership rows rather than owners who can act. See
    `SqlOrganizationStore.count_owners`.

    Scope of the remaining risk: a single-process local stack with no concurrent callers cannot
    hit it. It must be closed before any deployment serves concurrent requests.
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
        self._refuse_if_final_owner(account_id)
        if account.disabled_at is not None:
            return account  # already disabled; idempotent, and the horizon keeps its original start
        disabled = account.disabled(now=now)
        if not self._accounts.save_account(disabled):
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

    def _refuse_if_final_owner(self, account_id: str) -> None:
        """Refuse when this account is the last owner-role member of any organization (`FR-013`).

        Checks every organization the account belongs to, not just one. An account that owns two
        organizations and is the final owner of the second must be refused, and a check that
        stopped at the first would let that through.
        """
        for membership in self._organizations.memberships_for_account(account_id):
            if membership.role != OWNER_ROLE:
                continue
            remaining = self._organizations.count_owners(
                membership.organization_id, excluding_account_id=account_id
            )
            if remaining == 0:
                raise FinalOwnerProtected(FINAL_OWNER_FAILURE)


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

    def __init__(self, accounts: AccountStore, *, retention_days: int = RETENTION_DAYS) -> None:
        self._accounts = accounts
        self._retention_days = retention_days

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
        horizon = now - timedelta(days=self._retention_days)
        purged = 0
        for account in self._accounts.accounts_disabled_before(horizon):
            if self._accounts.save_account(account.purged()):
                purged += 1
        return PurgeReport(purged_accounts=purged)
