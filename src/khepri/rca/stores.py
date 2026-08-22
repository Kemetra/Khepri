from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from khepri.rca.accounts import Account
    from khepri.rca.invitations import Invitation
    from khepri.rca.organizations import (
        IsolationScope,
        Membership,
        MembershipEvent,
        Organization,
    )


class AccountStore(Protocol):
    def add_account(self, account: Account) -> bool: ...

    def add_account_with_external_identity(
        self,
        account: Account,
        provider: str,
        provider_subject: str,
        *,
        linked_at: datetime,
    ) -> bool: ...

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

    #: The only member of this protocol permitted to remove an `FR-014` event, and the only
    #: underscore-prefixed one. The name is not a style slip: `R2-07`'s source audit fails closed
    #: against any production function that deletes a `MembershipEventRow` and reserved exactly
    #: this name for the retention sweep, so keeping it is what keeps the audit meaningful. It is
    #: private because no caller other than `MembershipEventSweeper` may reach it.
    def _purge_expired_events(self, horizon: datetime) -> int: ...

    def get_scope(self, organization_id: str) -> IsolationScope | None: ...

    def memberships_for_account(self, account_id: str) -> list[Membership]: ...

    def organizations_for_account(self, account_id: str) -> list[Organization]: ...

    def count_owners(self, organization_id: str, *, excluding_account_id: str) -> int: ...

    def apply_owner_reducing_change(self, account_id: str, updated: Account) -> str: ...

    def promote_membership(self, membership: Membership, event: MembershipEvent) -> bool: ...

    def revoke_membership(
        self,
        organization_id: str,
        account_id: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> str: ...

    def demote_membership(
        self,
        organization_id: str,
        account_id: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> str: ...


class InvitationStore(Protocol):
    """The invitation persistence surface (`R4-03`).

    **Declared as a Protocol with a fake, unlike `R3-03`'s session store**, which
    `SessionRetentionSweeper` and `SessionService` both take concretely. Two reasons for the
    departure, recorded so the inconsistency is a decision rather than drift:

    - The parity test this enables (`test_every_fake_implements_its_whole_protocol`) caught a real
      shipped divergence once -- `MemoryOrganizationStore.count_owners` counted rows where the SQL
      store counted *effective* owners, which made unit tests pass wrongly about the one invariant
      `FR-013` exists to protect. An invitation fake has the same hazard: its purge predicate is two
      lifecycle rules, and a fake implementing one of them would pass every domain test.
    - `R4-04` through `R4-07` are four more slices against this surface. A Protocol now costs one
      declaration; retrofitting one after four consumers exist costs four.

    `_purge_spent_invitations` is underscore-prefixed and named here anyway, following
    `OrganizationStore._purge_expired_events`: `R2-07`'s source audit reserved that spelling for a
    retention sweep, and a sweeper's entry point that no service may call still has to appear in the
    contract its sweeper types against.
    """

    def add_invitation(self, invitation: Invitation) -> bool: ...

    def get_invitation(self, invitation_id: str, *, now: datetime) -> Invitation | None: ...

    def find_for_redemption(
        self, invitation_id: str, *, now: datetime
    ) -> Invitation | None: ...

    def save_invitation(self, invitation: Invitation) -> bool: ...

    #: `R4-04`'s revocation, as one conditional statement rather than a read and a write.
    #: Scoped by `(organization_id, invitation_id)` because `FR-023` gives an identifier no
    #: authority, and returning a bool rather than raising keeps the four non-open causes
    #: indistinguishable at this layer -- the statement cannot tell them apart either.
    def delete_open_invitation(
        self, organization_id: str, invitation_id: str, *, now: datetime
    ) -> bool: ...

    #: `R4-05`'s redemption: consume the invitation and create its membership in one transaction,
    #: holding the account row locked. One bool for every failure cause, because `FR-025` requires
    #: the caller to be unable to distinguish them.
    def redeem_into_membership(
        self,
        invitation_id: str,
        *,
        account_id: str,
        organization_id: str,
        role: str,
        now: datetime,
        membership: Membership,
        event: MembershipEvent,
        session_id_hash: str,
    ) -> bool: ...

    def invitations_for_organization(
        self, organization_id: str, *, now: datetime
    ) -> tuple[Invitation, ...]: ...

    def _purge_spent_invitations(self, horizon: datetime, *, now: datetime) -> int: ...
