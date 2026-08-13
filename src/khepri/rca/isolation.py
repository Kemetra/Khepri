from __future__ import annotations

from typing import TYPE_CHECKING

from khepri.rca.errors import SCOPE_FAILURE, ScopeAccessDenied

if TYPE_CHECKING:
    from khepri.rca.stores import AccountStore, OrganizationStore


class IsolationService:
    """Resolves an organization to its durable opaque isolation key.

    This is the single choke point for the FR-031 mapping. It returns ``owner_id`` only and
    never constructs a ``SessionScope``: RRA content tables declare composite foreign keys
    onto ``rra_beta_sessions(owner_id, session_id)``, so a session identifier minted here
    could not satisfy them without writing into RRA's tables, which FR-039 forbids.

    **It also refuses a disabled account**, which is why it holds an ``AccountStore``. Slice 1
    left this open — the risk was recorded but inert, because disablement did not exist. It
    becomes live the moment #149 merges: without this check a disabled account would keep
    resolving its organization's isolation scope and reaching every RRA capability behind it,
    which is precisely the authority FR-008 says must stop without waiting for expiry.
    """

    def __init__(self, store: OrganizationStore, accounts: AccountStore) -> None:
        self._store = store
        self._accounts = accounts

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        account = self._accounts.get_account(account_id)
        if account is None or account.is_purged or not account.is_enabled:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        membership = self._store.get_membership(organization_id, account_id)
        if membership is None:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        scope = self._store.get_scope(organization_id)
        if scope is None:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        return scope.owner_id
