"""In-memory `khepri.rca` stores, shared by the test modules that need them.

Extracted when #149 added a third service and a second store dependency: each of
`test_rca001_accounts`, `test_rca001_isolation`, and `test_rca001_organizations` had grown its
own partial copy, and a protocol method added in one place had to be remembered in three.

These are deliberately dumb. They hold records and return them, so a test that passes against a
fake and fails against `SqlAccountStore` is telling you about the SQL, not about the fake.
"""

from __future__ import annotations

from datetime import datetime

from khepri.rca.accounts import Account, canonical_email
from khepri.rca.errors import (
    OWNER_CHANGE_APPLIED,
    OWNER_CHANGE_FINAL_OWNER,
    OWNER_CHANGE_NOT_APPLICABLE,
)
from khepri.rca.invitations import (
    Invitation,
    InvitationLifecycle,
    InvitationOffer,
    StoredInvitationSecret,
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
        self.external_identities: dict[tuple[str, str], str] = {}

    def add_account(self, account: Account) -> bool:
        if any(
            existing.email is not None and existing.email == account.email
            for existing in self.accounts.values()
        ):
            return False
        self.accounts[account.account_id] = account
        return True

    def add_account_with_external_identity(
        self,
        account: Account,
        provider: str,
        provider_subject: str,
        *,
        linked_at: datetime,
    ) -> bool:
        del linked_at
        key = (provider, provider_subject)
        if key in self.external_identities or not self.add_account(account):
            return False
        self.external_identities[key] = account.account_id
        return True

    def account_for_external_identity(self, provider: str, provider_subject: str) -> str | None:
        return self.external_identities.get((provider, provider_subject))

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

    def __init__(self, accounts: MemoryAccountStore, *, fail_on_create: bool = False) -> None:
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
        has_external_identity = account_id in self.accounts.external_identities.values()
        return account is not None and account.can_authenticate(
            has_external_identity=has_external_identity
        )


class MemoryInvitationStore:
    """In-memory `InvitationStore` (`R4-03`).

    Deliberately dumb, like its siblings -- but two behaviours are copied rather than simplified,
    because simplifying them is what would make tests pass wrongly:

    - **`add_invitation` canonicalizes `target_identity`**, as the SQL store does. A fake holding
    the
      raw address would let an addressee-mismatch test pass against `Alice@Example.COM` while
      production matched `alice@example.com`.
    - **`find_for_redemption` destroys an expired verifier**, as the SQL store does. A fake that
      merely returned the row would make `R4-05`'s "the verifier is gone by the time you verify"
      assertions vacuous.
    """

    def __init__(self) -> None:
        self.invitations: dict[str, Invitation] = {}

    def add_invitation(self, invitation: Invitation) -> bool:
        if invitation.invitation_id in self.invitations:
            return False
        self.invitations[invitation.invitation_id] = _canonicalized(invitation)
        return True

    def get_invitation(self, invitation_id: str, *, now: datetime) -> Invitation | None:
        return self._read_destroying_expired(invitation_id, now=now)

    def _read_destroying_expired(self, invitation_id: str, *, now: datetime) -> Invitation | None:
        invitation = self.invitations.get(invitation_id)
        if invitation is None:
            return None
        if invitation.is_expired_at(now) and invitation.verifier is not None:
            invitation = invitation.verifier_destroyed(at=now)
            self.invitations[invitation_id] = invitation
        return invitation

    def find_for_redemption(self, invitation_id: str, *, now: datetime) -> Invitation | None:
        return self._read_destroying_expired(invitation_id, now=now)

    def save_invitation(self, invitation: Invitation) -> bool:
        """Monotonic, matching `SqlInvitationStore`, including its refusal.

        A plain overwrite is what the SQL store did until `#217`, and it let a stale snapshot
        restore a destroyed verifier or clear a terminal timestamp. The fake keeps the same rule
        rather than the simpler one: a fake accepting a write production refuses would make an
        `R4-05` concurrency test pass against a store that loses the race badly.
        """
        stored = self.invitations.get(invitation.invitation_id)
        if stored is None:
            return False

        # A conflicting terminal transition is refused, as the SQL store refuses it. Taking the
        # two fields independently built an invitation with *both* timestamps set -- a state
        # `ck_rca_invitation_terminal_state` forbids, so the fake accepted what production
        # rejects with `IntegrityError`. Found in review on `#217`.
        if (invitation.redeemed_at is not None and stored.revoked_at is not None) or (
            invitation.revoked_at is not None and stored.redeemed_at is not None
        ):
            return False

        lifecycle = InvitationLifecycle(
            redeemed_at=stored.redeemed_at or invitation.redeemed_at,
            revoked_at=stored.revoked_at or invitation.revoked_at,
        )
        verifier = None if invitation.verifier is None else stored.verifier
        self.invitations[invitation.invitation_id] = Invitation._from_storage(
            InvitationOffer(
                organization_id=stored.organization_id,
                intended_role=stored.intended_role,
                target_identity=stored.target_identity,
                issued_by=stored.issued_by,
            ),
            StoredInvitationSecret(
                invitation_id=stored.invitation_id,
                verifier=verifier,
                expires_at=stored.expires_at,
            ),
            issued_at=stored.issued_at,
            lifecycle=lifecycle,
        )
        return True

    def delete_open_invitation(
        self, organization_id: str, invitation_id: str, *, now: datetime
    ) -> bool:
        """All five clauses of the SQL predicate, not four.

        The organization clause and the expiry clause are the two a simplified fake would drop --
        the first because the identifier is already unique in a dict, the second because
        `is_open_at` looks like it covers "still open". Dropping either makes every
        cross-organization and expired-revocation test pass against a store that refuses
        differently, which is the divergence `test_every_fake_implements_its_whole_protocol`
        exists to catch and which shipped once as `count_owners`.

        `is_open_at` is used rather than restating the three timestamp conditions: `R4-01` §5 holds
        that boundary in one predicate, and reaching past it to a local copy is the drift
        `accounts.py:68` warns about for `can_act`.
        """
        invitation = self.invitations.get(invitation_id)
        if invitation is None:
            return False
        if invitation.organization_id != organization_id:
            return False
        if not invitation.is_open_at(now):
            return False
        del self.invitations[invitation_id]
        return True

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
    ) -> bool:
        """The conditional transition, without the row locks a fake has nothing to lock.

        **What is copied and what is not.** The invitation predicate is copied exactly -- open,
        unredeemed, unrevoked, unexpired at `now` -- because a fake that accepted a redemption
        production refuses would make an at-most-once test pass against a store that loses the
        race. The account and session re-reads are **not** modelled: this fake holds no accounts
        or sessions, so it cannot answer those questions, and inventing an answer would be worse
        than declining to. `R4-05`'s liveness tests run against SQL for that reason.

        Recorded rather than left implicit, because the parity test compares signatures and cannot
        see that two implementations answer a different number of questions.
        """
        invitation = self.invitations.get(invitation_id)
        if invitation is None:
            return False
        if invitation.organization_id != organization_id:
            return False
        if not invitation.is_open_at(now):
            return False
        self.invitations[invitation_id] = invitation.redeemed(at=now)
        return True

    def invitations_for_organization(
        self, organization_id: str, *, now: datetime
    ) -> tuple[Invitation, ...]:
        """The organization's invitations, destroying expired verifiers **within that scope only**.

        The filter comes first, and an earlier version had it second. That version called
        `_read_destroying_expired` for every stored identifier, so listing organization A destroyed
        B's expired verifier too -- while `SqlInvitationStore` filters by `organization_id` in the
        `SELECT` and only touches rows it returns. A later fake-backed test could then observe B as
        unverifiable where production would have left it alone. Found in review on `#217`, and it is
        exactly the divergence class the signature-parity test exists to catch: the two
        implementations agreed on shape and disagreed on effect.
        """
        scoped = [
            invitation_id
            for invitation_id, invitation in self.invitations.items()
            if invitation.organization_id == organization_id
        ]
        for invitation_id in scoped:
            self._read_destroying_expired(invitation_id, now=now)
        held = [self.invitations[invitation_id] for invitation_id in scoped]
        held.sort(key=lambda invitation: (invitation.issued_at, invitation.invitation_id))
        return tuple(held)

    def _purge_spent_invitations(self, horizon: datetime, *, now: datetime) -> int:
        """Both lifecycle rules, matching the SQL predicate.

        Implementing only the redeemed branch would leave every expired-verifier test green while
        production purged nothing -- which is the divergence class the parity test exists to catch.
        """
        spent = [
            invitation_id
            for invitation_id, invitation in self.invitations.items()
            if _is_spent(invitation, horizon=horizon, now=now)
        ]
        for invitation_id in spent:
            del self.invitations[invitation_id]
        return len(spent)


def _is_spent(invitation: Invitation, *, horizon: datetime, now: datetime) -> bool:
    if invitation.redeemed_at is not None:
        return invitation.redeemed_at <= horizon
    return invitation.revoked_at is not None or invitation.is_expired_at(now)


def _canonicalized(invitation: Invitation) -> Invitation:
    """The record as the SQL store would hold it, with a canonical `target_identity`."""
    canonical = canonical_email(invitation.target_identity)
    if canonical == invitation.target_identity:
        return invitation
    return Invitation._from_storage(
        InvitationOffer(
            organization_id=invitation.organization_id,
            intended_role=invitation.intended_role,
            target_identity=canonical,
            issued_by=invitation.issued_by,
        ),
        StoredInvitationSecret(
            invitation_id=invitation.invitation_id,
            verifier=invitation.verifier,
            expires_at=invitation.expires_at,
        ),
        issued_at=invitation.issued_at,
        lifecycle=InvitationLifecycle(
            redeemed_at=invitation.redeemed_at, revoked_at=invitation.revoked_at
        ),
    )
