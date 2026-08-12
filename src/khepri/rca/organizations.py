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

    def __post_init__(self) -> None:
        """Reject anything that is not a freshly allocated opaque key.

        FR-032/FR-033 are the reason this slice exists, and validating only in
        `OrganizationService` left them unenforced for any caller reaching the store
        directly — an importer or backfill could persist `owner@example.test` as the
        isolation key, and `resolve_scope` would hand an email address back as the analytical
        boundary. Verified before this check existed.

        Putting the invariant on the type means no layer can bypass it: there is no way to
        construct an `IsolationScope` that the store would then persist.
        """
        if not _is_allocated_owner_id(self.owner_id):
            raise ValueError("owner_id must be an allocated opaque key (see allocate_owner_id)")


_OWNER_ID_PREFIX = "own_"
# secrets.token_urlsafe(18) yields 24 characters from the URL-safe base64 alphabet.
_OWNER_ID_BODY = 24
_OWNER_ID_ALPHABET = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


def _is_allocated_owner_id(owner_id: str) -> bool:
    """Shape check for a key produced by `allocate_owner_id`.

    Shape is all that can be checked after the fact — the value is random by construction,
    so there is nothing to recompute. It is enough to exclude every commercial identifier
    FR-032 names: an email, an organization name, a slug, and a human-readable identifier all
    fail either the prefix, the length, or the alphabet.
    """
    if not owner_id.startswith(_OWNER_ID_PREFIX):
        return False
    body = owner_id.removeprefix(_OWNER_ID_PREFIX)
    return len(body) == _OWNER_ID_BODY and set(body) <= _OWNER_ID_ALPHABET


def allocate_owner_id() -> str:
    """Allocate a fresh opaque isolation key.

    The key is drawn from a CSPRNG and is never derived from organization data, so no
    commercial identifier can appear in it or be recovered from it (FR-032, FR-033).
    """
    return f"{_OWNER_ID_PREFIX}{secrets.token_urlsafe(18)}"


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
