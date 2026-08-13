from __future__ import annotations

from typing import TYPE_CHECKING

from khepri.rca.errors import SCOPE_FAILURE, ScopeAccessDenied

if TYPE_CHECKING:
    from khepri.rca.stores import OrganizationStore


class IsolationService:
    """Resolves an organization to its durable opaque isolation key.

    This is the single choke point for the FR-031 mapping. It returns ``owner_id`` only and
    never constructs a ``SessionScope``: RRA content tables declare composite foreign keys
    onto ``rra_beta_sessions(owner_id, session_id)``, so a session identifier minted here
    could not satisfy them without writing into RRA's tables, which FR-039 forbids.
    """

    def __init__(self, store: OrganizationStore) -> None:
        self._store = store

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        membership = self._store.get_membership(organization_id, account_id)
        if membership is None:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        scope = self._store.get_scope(organization_id)
        if scope is None:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        return scope.owner_id
