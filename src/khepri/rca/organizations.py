from __future__ import annotations

import secrets
from dataclasses import dataclass, field
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


_OWNER_ID_PREFIX = "own_"


def allocate_owner_id() -> str:
    """Allocate a fresh opaque isolation key.

    The key is drawn from a CSPRNG and is never derived from organization data, so no
    commercial identifier can appear in it or be recovered from it (FR-032, FR-033).
    """
    return f"{_OWNER_ID_PREFIX}{secrets.token_urlsafe(18)}"


@dataclass(frozen=True, slots=True)
class IsolationScope:
    """An organization's opaque isolation key. The key cannot be supplied by a caller.

    FR-032/FR-033 are the reason this slice exists, and enforcing them anywhere other than
    here left a gap. Validating in `OrganizationService` missed every caller reaching the
    store directly — verified: such a caller could persist `owner@example.test`, and
    `resolve_scope` handed that email back as the analytical boundary. Validating the key's
    *shape* then missed `own_AcmePharmacy000000000000`, which is 24 characters of the
    accepted alphabet and still copied straight from an organization name.

    Shape cannot establish provenance, so this type does not check provenance — it owns it.
    `owner_id` is allocated in `__post_init__` and there is no parameter to override it, so
    no layer can construct a scope carrying an untrusted key.
    """

    organization_id: str
    owner_id: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", allocate_owner_id())

    @classmethod
    def restore(cls, organization_id: str, owner_id: str) -> IsolationScope:
        """Rebuild a scope from storage, preserving the key that was allocated originally.

        Reading must not mint a new key: FR-035 requires one organization to resolve to a
        *stable* scope for its lifetime. This is the only way to set `owner_id` from outside,
        and it exists for the persistence read path — a store converting a row it previously
        wrote. It asserts nothing about the value because the value came from the database;
        the guarantee is that nothing but an allocation could have put it there.
        """
        scope = cls(organization_id=organization_id)
        object.__setattr__(scope, "owner_id", owner_id)
        return scope


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
        scope = IsolationScope(organization_id=organization.organization_id)
        if not self._store.create_organization(organization, membership, scope):
            raise OrganizationCreationFailed(ORGANIZATION_FAILURE)
        return organization
