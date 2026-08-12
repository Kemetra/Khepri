from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from khepri.rca.accounts import Account
    from khepri.rca.organizations import IsolationScope, Membership, Organization


class AccountStore(Protocol):
    def add_account(self, account: Account) -> bool: ...

    def get_account_by_email(self, email: str) -> Account | None: ...

    def get_account(self, account_id: str) -> Account | None: ...

    def update_account(self, account: Account) -> None: ...


class OrganizationStore(Protocol):
    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
    ) -> bool: ...

    def get_membership(self, organization_id: str, account_id: str) -> Membership | None: ...

    def get_scope(self, organization_id: str) -> IsolationScope | None: ...
