from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from khepri.rca.errors import ORGANIZATION_FAILURE, OrganizationCreationFailed
from khepri.rca.records import Sealed, register_sealed, through_door

if TYPE_CHECKING:
    from khepri.rca.stores import OrganizationStore

OWNER_ROLE = "owner"
MEMBER_ROLE = "member"

# FR-015: exactly two roles. Named as a set so the domain, the store, and the schema CHECK
# constraint all restrict to the same values rather than each spelling them out.
ROLES = (OWNER_ROLE, MEMBER_ROLE)


@register_sealed
@dataclass(frozen=True, slots=True)
class Organization(Sealed):
    organization_id: str
    name: str
    created_at: datetime

    @classmethod
    def create(cls, name: str, *, now: datetime) -> Organization:
        with through_door():
            return Organization(
                organization_id=f"org_{secrets.token_urlsafe(18)}",
                name=name,
                created_at=now,
            )

    @classmethod
    def _from_storage(cls, organization_id: str, name: str, created_at: datetime) -> Organization:
        with through_door():
            return Organization(organization_id=organization_id, name=name, created_at=created_at)


@register_sealed
@dataclass(frozen=True, slots=True)
class Membership(Sealed):
    """An account's role in an organization, as a state row.

    This records the *current* role only, and deliberately carries no attribution. It cannot
    represent a role transition, so FR-014's "what the prior and resulting roles were" is
    unsatisfiable in this shape; that requirement is met by `MembershipEvent` on an append-only
    table with its own twelve-month horizon (`KHEPRI-DEC-015` §2a).

    The row previously carried `changed_by`/`changed_at`. They are gone as of `20260814_0014`:
    audit data on a row with no expiry outlives its own horizon indefinitely, not by decision
    but by accident of what it rode on. Attribution now has exactly one home, and that home is
    swept. Adding a "last changed by" field back here for convenience would recreate the defect.
    """

    organization_id: str
    account_id: str
    role: str

    @classmethod
    def create(cls, organization_id: str, account_id: str, role: str) -> Membership:
        with through_door():
            return Membership(
                organization_id=organization_id,
                account_id=account_id,
                role=role,
            )

    @classmethod
    def _from_storage(cls, organization_id: str, account_id: str, role: str) -> Membership:
        with through_door():
            return Membership(
                organization_id=organization_id,
                account_id=account_id,
                role=role,
            )


_OWNER_ID_PREFIX = "own_"


def allocate_owner_id() -> str:
    """Allocate a fresh opaque isolation key.

    The key is drawn from a CSPRNG and is never derived from organization data, so no
    commercial identifier can appear in it or be recovered from it (FR-032, FR-033).
    """
    return f"{_OWNER_ID_PREFIX}{secrets.token_urlsafe(18)}"


@register_sealed
@dataclass(frozen=True, slots=True)
class MembershipEvent(Sealed):
    """One attributable change to a membership (`FR-014`), append-only.

    **The event kind is carried by nullability, not by a type column.** A creation has no prior
    role; a revocation has no next role; a role change has both. A separate `event_type` column
    could disagree with them — a row typed `revoked` carrying a non-null `next_role` is
    expressible — and then two fields describe one event, which is the drift Constitution I
    forbids. If a future kind cannot be distinguished this way, that is when to add the column.

    **Content-free, per `KHEPRI-DEC-015` §82 and `FR-040`.** Opaque actor identifier, opaque
    membership identity, prior role, next role, timestamp. No email address, no organization
    name, no retail content — and nothing that is not on that list.

    **Its horizon is twelve months** (`KHEPRI-DEC-015` §2a), swept independently of the account
    record's twenty-four. That ordering is deliberate and load-bearing: the account tombstone
    outlives the audit event so an event never refers to a subject that no longer exists.
    """

    event_id: str
    organization_id: str
    account_id: str
    actor_account_id: str
    prior_role: str | None
    next_role: str | None
    occurred_at: datetime

    @classmethod
    def created(
        cls,
        organization_id: str,
        account_id: str,
        role: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> MembershipEvent:
        """A membership coming into existence. No prior role."""
        return cls._build(
            organization_id, account_id, actor_account_id, None, role, now
        )

    @classmethod
    def role_changed(
        cls,
        organization_id: str,
        account_id: str,
        *,
        prior_role: str,
        next_role: str,
        actor_account_id: str,
        now: datetime,
    ) -> MembershipEvent:
        return cls._build(
            organization_id, account_id, actor_account_id, prior_role, next_role, now
        )

    @classmethod
    def revoked(
        cls,
        organization_id: str,
        account_id: str,
        *,
        prior_role: str,
        actor_account_id: str,
        now: datetime,
    ) -> MembershipEvent:
        """A membership ending. No next role."""
        return cls._build(
            organization_id, account_id, actor_account_id, prior_role, None, now
        )

    @classmethod
    def _build(
        cls,
        organization_id: str,
        account_id: str,
        actor_account_id: str,
        prior_role: str | None,
        next_role: str | None,
        now: datetime,
    ) -> MembershipEvent:
        # The identifier is allocated before the door opens, following `Account.create`: a door
        # authorizes the whole thread while open, so its body holds the constructor call alone.
        event_id = f"mev_{secrets.token_urlsafe(18)}"
        with through_door():
            return MembershipEvent(
                event_id=event_id,
                organization_id=organization_id,
                account_id=account_id,
                actor_account_id=actor_account_id,
                prior_role=prior_role,
                next_role=next_role,
                occurred_at=now,
            )

    @classmethod
    def _from_storage(
        cls,
        event_id: str,
        organization_id: str,
        account_id: str,
        actor_account_id: str,
        prior_role: str | None,
        next_role: str | None,
        occurred_at: datetime,
    ) -> MembershipEvent:
        with through_door():
            return MembershipEvent(
                event_id=event_id,
                organization_id=organization_id,
                account_id=account_id,
                actor_account_id=actor_account_id,
                prior_role=prior_role,
                next_role=next_role,
                occurred_at=occurred_at,
            )

    def is_purgeable_at(self, horizon: datetime) -> bool:
        """True once the twelve-month horizon has elapsed (`KHEPRI-DEC-015` §2a)."""
        return self.occurred_at <= horizon


@register_sealed
@dataclass(frozen=True, slots=True)
class IsolationScope(Sealed):
    """An organization's opaque isolation key (FR-032, FR-033, FR-035).

    `create` takes an organization identifier and nothing else. There is no parameter for
    `owner_id`, so a caller-supplied key is not rejected — it cannot be written down. That is
    the property #148 spent four review rounds failing to reach by validation: a key's *shape*
    cannot establish its provenance, since `own_AcmePharmacy000000000000` is 24 characters of
    the accepted alphabet and still copied from an organization name.

    `_from_storage` preserves the key a row already holds, because FR-035 requires one
    organization to resolve to a *stable* scope for its lifetime — reading must never mint a
    new key. It asserts nothing about the value: the value came from the database, and the
    guarantee is that nothing but `create` could have put it there.
    """

    organization_id: str
    owner_id: str

    @classmethod
    def create(cls, organization_id: str) -> IsolationScope:
        with through_door():
            return IsolationScope(organization_id=organization_id, owner_id=allocate_owner_id())

    @classmethod
    def _from_storage(cls, organization_id: str, owner_id: str) -> IsolationScope:
        with through_door():
            return IsolationScope(organization_id=organization_id, owner_id=owner_id)


class OrganizationService:
    def __init__(self, store: OrganizationStore) -> None:
        self._store = store

    def create_organization(
        self,
        name: str,
        creator_account_id: str,
        *,
        now: datetime,
    ) -> Organization:
        organization = Organization.create(name, now=now)
        membership = Membership.create(
            organization_id=organization.organization_id,
            account_id=creator_account_id,
            role=OWNER_ROLE,
        )
        scope = IsolationScope.create(organization.organization_id)
        # FR-014 covers "every change to a membership", and the initial owner membership is one.
        # Emitting it here rather than only for later changes also keeps the audit trail
        # uniform: the R2-02 backfill synthesizes exactly this event for memberships created
        # before events existed, so omitting it going forward would leave historical rows with
        # a creation event and new ones without.
        event = MembershipEvent.created(
            organization.organization_id,
            creator_account_id,
            OWNER_ROLE,
            actor_account_id=creator_account_id,
            now=now,
        )
        if not self._store.create_organization(organization, membership, scope, event):
            raise OrganizationCreationFailed(ORGANIZATION_FAILURE)
        return organization
