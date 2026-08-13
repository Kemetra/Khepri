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

    This records the *current* role only. It cannot represent a role transition, so FR-014's
    "what the prior and resulting roles were" is unsatisfiable in this shape, and the
    `changed_by`/`changed_at` columns hold audit data on a row with no expiry while
    `KHEPRI-DEC-015` gives role/membership audit events a 12-month horizon. Both are #150's:
    attribution moves to an append-only `rca_membership_events` table that expires on its own.
    """

    organization_id: str
    account_id: str
    role: str
    changed_by: str
    changed_at: datetime

    @classmethod
    def create(
        cls,
        organization_id: str,
        account_id: str,
        role: str,
        *,
        changed_by: str,
        now: datetime,
    ) -> Membership:
        with through_door():
            return Membership(
                organization_id=organization_id,
                account_id=account_id,
                role=role,
                changed_by=changed_by,
                changed_at=now,
            )

    @classmethod
    def _from_storage(
        cls,
        organization_id: str,
        account_id: str,
        role: str,
        changed_by: str,
        changed_at: datetime,
    ) -> Membership:
        with through_door():
            return Membership(
                organization_id=organization_id,
                account_id=account_id,
                role=role,
                changed_by=changed_by,
                changed_at=changed_at,
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
            changed_by=creator_account_id,
            now=now,
        )
        scope = IsolationScope.create(organization.organization_id)
        if not self._store.create_organization(organization, membership, scope):
            raise OrganizationCreationFailed(ORGANIZATION_FAILURE)
        return organization
