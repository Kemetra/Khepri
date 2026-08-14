from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from khepri.rca.accounts import Account
    from khepri.rca.organizations import (
        IsolationScope,
        Membership,
        MembershipEvent,
        Organization,
    )


class AccountStore(Protocol):
    def add_account(self, account: Account) -> bool: ...

    def save_account(self, account: Account) -> bool: ...

    def get_account_by_email(self, email: str) -> Account | None: ...

    def get_account(self, account_id: str) -> Account | None: ...

    def accounts_disabled_before(self, horizon: datetime) -> list[Account]: ...

    def purge_if_still_eligible(self, account_id: str, horizon: datetime) -> bool: ...


class OrganizationStore(Protocol):
    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
        event: MembershipEvent,
    ) -> bool: ...

    def get_membership(self, organization_id: str, account_id: str) -> Membership | None: ...

    def get_scope(self, organization_id: str) -> IsolationScope | None: ...

    def memberships_for_account(self, account_id: str) -> list[Membership]: ...

    def count_owners(self, organization_id: str, *, excluding_account_id: str) -> int: ...

    def apply_owner_reducing_change(self, account_id: str, updated: Account) -> str: ...

    def promote_membership(self, membership: Membership, event: MembershipEvent) -> bool: ...
