"""In-memory `khepri.rca` stores, shared by the test modules that need them.

Extracted when #149 added a third service and a second store dependency: each of
`test_rca001_accounts`, `test_rca001_isolation`, and `test_rca001_organizations` had grown its
own partial copy, and a protocol method added in one place had to be remembered in three.

These are deliberately dumb. They hold records and return them, so a test that passes against a
fake and fails against `SqlAccountStore` is telling you about the SQL, not about the fake.
"""

from __future__ import annotations

from datetime import datetime

from khepri.rca.accounts import Account
from khepri.rca.organizations import OWNER_ROLE, IsolationScope, Membership, Organization


class MemoryAccountStore:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}

    def add_account(self, account: Account) -> bool:
        if any(
            existing.email is not None and existing.email == account.email
            for existing in self.accounts.values()
        ):
            return False
        self.accounts[account.account_id] = account
        return True

    def save_account(self, account: Account) -> bool:
        if account.account_id not in self.accounts:
            return False
        self.accounts[account.account_id] = account
        return True

    def get_account_by_email(self, email: str) -> Account | None:
        for account in self.accounts.values():
            if account.email == email:
                return account
        return None

    def get_account(self, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    def purge_if_still_eligible(self, account_id: str, horizon: datetime) -> bool:
        """Mirror the store's conditional purge, re-checking eligibility at write time."""
        account = self.accounts.get(account_id)
        if (
            account is None
            or account.disabled_at is None
            or account.disabled_at > horizon
            or account.is_purged
        ):
            return False
        self.accounts[account_id] = account.purged()
        return True

    def accounts_disabled_before(self, horizon: datetime) -> list[Account]:
        return [
            account
            for account in self.accounts.values()
            if account.disabled_at is not None
            and account.disabled_at <= horizon
            and account.email is not None
        ]


class MemoryOrganizationStore:
    """The organization store.

    `count_owners` needs account state, which the SQL store gets from a join. Set `accounts` to
    a `MemoryAccountStore` to mirror that; left unset, every membership holder is treated as
    live, which is the right default for tests that never disable anyone.
    """

    def __init__(self, accounts: MemoryAccountStore | None = None) -> None:
        self.organizations: dict[str, Organization] = {}
        self.memberships: dict[tuple[str, str], Membership] = {}
        self.scopes: dict[str, IsolationScope] = {}
        self.accounts = accounts

    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
    ) -> bool:
        self.organizations[organization.organization_id] = organization
        self.memberships[(membership.organization_id, membership.account_id)] = membership
        self.scopes[scope.organization_id] = scope
        return True

    def get_membership(self, organization_id: str, account_id: str) -> Membership | None:
        return self.memberships.get((organization_id, account_id))

    def get_scope(self, organization_id: str) -> IsolationScope | None:
        return self.scopes.get(organization_id)

    def memberships_for_account(self, account_id: str) -> list[Membership]:
        return [
            membership
            for (_, holder), membership in self.memberships.items()
            if holder == account_id
        ]

    def count_owners(self, organization_id: str, *, excluding_account_id: str) -> int:
        """Effective owners, mirroring the SQL store's join onto account state.

        Counting membership rows alone would make this fake disagree with `SqlOrganizationStore`
        on the case that matters: a disabled account keeps its owner-role row, so counting rows
        reports a live owner where there is none. That is a real defect this slice shipped and
        review caught — a fake that kept the old behaviour would let it back in.
        """
        return sum(
            1
            for (org, holder), membership in self.memberships.items()
            if org == organization_id
            and holder != excluding_account_id
            and membership.role == OWNER_ROLE
            and self._can_act(holder)
        )

    def _can_act(self, account_id: str) -> bool:
        if self.accounts is None:
            return True
        account = self.accounts.get_account(account_id)
        return account is not None and account.can_authenticate
