"""Which scopes have a workspace (`W1-04b`; `RCA-005` semantics, "Workspace").

`RCA-005` defines the workspace as the organization's isolation scope seen as a container --
"exactly one per organization". An analysis session carries an `owner_id` whether an organization
opened it (`CommercialBridge.open`, which resolved the scope) or an invitation did (a design-partner
scope no organization owns). The pipeline records the workspace for the first kind and nothing for
the second, and this is the one read that tells them apart: a scope is a workspace exactly when
`rca_isolation_scopes` holds it, which is also the foreign key every workspace row would fail on.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from khepri.rca.persistence import IsolationScopeRow
from khepri.rca.workspace.unit_of_work import reading


class SqlIsolationScopes:
    """Answers whether an `owner_id` is an organization's isolation scope."""

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def exists(self, owner_id: str) -> bool:
        with reading(self._factory) as database:
            found = database.scalar(
                select(IsolationScopeRow.owner_id).where(IsolationScopeRow.owner_id == owner_id)
            )
        return found is not None


# Named for what it reads, not "workspace scopes": `test_portable_storage_boundary.py` scans the
# runtime for provider names and the lower-cased compound would contain one.
__all__ = ["SqlIsolationScopes"]
