from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from khepri.rca.errors import ORGANIZATION_FAILURE, OrganizationCreationFailed

if TYPE_CHECKING:
    from khepri.rca.stores import OrganizationStore

OWNER_ROLE = "owner"


@dataclass(frozen=True, slots=True)
class Organization:
    organization_id: str
    name: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Membership:
    organization_id: str
    account_id: str
    role: str
    changed_by: str
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class IsolationScope:
    organization_id: str
    owner_id: str


def allocate_owner_id() -> str:
    """Allocate a fresh opaque isolation key.

    The key is drawn from a CSPRNG and is never derived from organization data, so no
    commercial identifier can appear in it or be recovered from it (FR-032, FR-033).
    """
    return f"own_{secrets.token_urlsafe(18)}"


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
        organization = Organization(
            organization_id=f"org_{secrets.token_urlsafe(18)}",
            name=name,
            created_at=now,
        )
        membership = Membership(
            organization_id=organization.organization_id,
            account_id=creator_account_id,
            role=OWNER_ROLE,
            changed_by=creator_account_id,
            changed_at=now,
        )
        scope = IsolationScope(
            organization_id=organization.organization_id,
            owner_id=allocate_owner_id(),
        )
        if not self._store.create_organization(organization, membership, scope):
            raise OrganizationCreationFailed(ORGANIZATION_FAILURE)
        return organization
