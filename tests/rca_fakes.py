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
from khepri.rca.errors import (
    OWNER_CHANGE_APPLIED,
    OWNER_CHANGE_FINAL_OWNER,
    OWNER_CHANGE_NOT_APPLICABLE,
)
from khepri.rca.organizations import (
    MEMBER_ROLE,
    OWNER_ROLE,
    IsolationScope,
    Membership,
    MembershipEvent,
    Organization,
)


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
        if account is None or not account.is_purgeable_at(horizon):
            return False
        self.accounts[account_id] = account.purged()
        return True

    def accounts_disabled_before(self, horizon: datetime) -> list[Account]:
        return [a for a in self.accounts.values() if a.is_purgeable_at(horizon)]


class MemoryOrganizationStore:
    """The organization store.

    `accounts` is **required**, not optional. `count_owners` needs account state, which the SQL
    store gets from a join, and an earlier version defaulted it to `None` and then treated every
    membership holder as live. That is precisely the semantics the join was added to defeat, so
    the default let a test pass against the fake and fail against `SqlOrganizationStore` on the
    one case FR-013 turns on. Requiring the argument converts a convention into an obligation the
    type enforces.

    `fail_on_create` models a store that refuses the write, for the caller that needs to see
    `OrganizationCreationFailed`. It replaces a second class of the same name that shadowed this
    one from a test module and implemented a narrower subset of the protocol.
    """

    def __init__(
        self, accounts: MemoryAccountStore, *, fail_on_create: bool = False
    ) -> None:
        self.organizations: dict[str, Organization] = {}
        self.memberships: dict[tuple[str, str], Membership] = {}
        self.scopes: dict[str, IsolationScope] = {}
        self.events: list[MembershipEvent] = []
        self.accounts = accounts
        self.fail_on_create = fail_on_create

    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
        event: MembershipEvent,
    ) -> bool:
        if self.fail_on_create:
            return False
        self.organizations[organization.organization_id] = organization
        self.memberships[(membership.organization_id, membership.account_id)] = membership
        self.scopes[scope.organization_id] = scope
        self.events.append(event)
        return True

    def apply_owner_reducing_change(self, account_id: str, updated: Account) -> str:
        """Guard and write with no interleaving, mirroring the SQL store's outcomes.

        A single-threaded dictionary cannot interleave, so this models the *sequential* contract
        only and must never be read as concurrency evidence. Proving that two overlapping callers
        cannot both pass needs two real PostgreSQL connections -- see
        `tests/test_rca001_concurrent_final_owner.py`.

        What it must match exactly is the outcome vocabulary, because every test that asserts a
        refusal against this fake is only meaningful if the real store refuses the same cases.
        """
        if self.accounts.get_account(account_id) is None:
            return OWNER_CHANGE_NOT_APPLICABLE
        for membership in self.memberships_for_account(account_id):
            if membership.role != OWNER_ROLE:
                continue
            if self.count_owners(membership.organization_id, excluding_account_id=account_id) == 0:
                return OWNER_CHANGE_FINAL_OWNER
        if not self.accounts.save_account(updated):
            return OWNER_CHANGE_NOT_APPLICABLE
        return OWNER_CHANGE_APPLIED

    def promote_membership(self, membership: Membership, event: MembershipEvent) -> bool:
        """Mirror `SqlOrganizationStore.promote_membership`'s refusals exactly.

        The identifier checks are not decoration. The event carries no foreign key, so nothing
        but these stops one naming a different membership than the row it claims to describe --
        and a fake that accepted a mismatched pair would let a test prove attribution the real
        store rejects.
        """
        if event.organization_id != membership.organization_id:
            return False
        if event.account_id != membership.account_id:
            return False
        if event.next_role != membership.role:
            return False
        key = (membership.organization_id, membership.account_id)
        stored = self.memberships.get(key)
        if stored is None:
            return False
        # Against the stored role, not the caller's claim, exactly as the SQL store does: it is
        # the only defense of FR-014's "what the prior role was", and checking the destination
        # alone would let a false transition commit.
        if event.prior_role != stored.role:
            return False
        self.memberships[key] = membership
        self.events.append(event)
        return True

    def revoke_membership(
        self,
        organization_id: str,
        account_id: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> str:
        """Mirror `SqlOrganizationStore.revoke_membership`'s outcomes.

        Sequential contract only -- a dictionary cannot interleave, so this is never concurrency
        evidence. The FR-013 guard is proven against two real PostgreSQL connections in
        `tests/test_rca001_concurrent_final_owner.py`.

        Deleting only this key is what FR-012 asks for, and it is trivially true here; the
        clause that can actually break is the SQL one, where a DELETE with the wrong WHERE takes
        the account's other memberships with it.
        """
        def revoke(key, membership: Membership) -> MembershipEvent:
            del self.memberships[key]
            return MembershipEvent.revoked(
                organization_id,
                account_id,
                prior_role=membership.role,
                actor_account_id=actor_account_id,
                now=now,
            )

        return self._apply_membership_change(organization_id, account_id, revoke)

    def demote_membership(
        self,
        organization_id: str,
        account_id: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> str:
        """Mirror `SqlOrganizationStore.demote_membership`'s outcomes."""

        def demote(key, membership: Membership) -> MembershipEvent:
            self.memberships[key] = membership.demoted()
            return MembershipEvent.role_changed(
                organization_id,
                account_id,
                prior_role=membership.role,
                next_role=MEMBER_ROLE,
                actor_account_id=actor_account_id,
                now=now,
            )

        return self._apply_membership_change(organization_id, account_id, demote)

    def _apply_membership_change(self, organization_id: str, account_id: str, write) -> str:
        """The fake's single owner-reducing guard, mirroring the store's shared body.

        Both stores route revoke and demote through one guard rather than two, because the
        roadmap forbids independent final-owner guards -- and a fake with two could disagree
        with the store on one operation while agreeing on the other, which is the divergence
        that makes a refusal test meaningless.
        """
        key = (organization_id, account_id)
        membership = self.memberships.get(key)
        if membership is None:
            return OWNER_CHANGE_NOT_APPLICABLE
        if membership.role == OWNER_ROLE and (
            self.count_owners(organization_id, excluding_account_id=account_id) == 0
        ):
            return OWNER_CHANGE_FINAL_OWNER
        self.events.append(write(key, membership))
        return OWNER_CHANGE_APPLIED

    def _purge_expired_events(self, horizon: datetime) -> int:
        """Mirrors `SqlOrganizationStore._purge_expired_events`, boundary included.

        Delegates the comparison to `MembershipEvent.is_purgeable_at` so this fake cannot drift
        from the domain on the `<=` boundary — an inclusive horizon here and an exclusive one in
        SQL would make the same event purgeable in unit tests and retained in production.
        """
        expired = [event for event in self.events if event.is_purgeable_at(horizon)]
        self.events = [event for event in self.events if not event.is_purgeable_at(horizon)]
        return len(expired)

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
        account = self.accounts.get_account(account_id)
        return account is not None and account.can_authenticate
