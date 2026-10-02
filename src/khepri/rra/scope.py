"""The RRA scope of one unit of work, and how each transaction sets it (`RRA-017` `FR-233`).

Every transaction that touches a covered table sets `khepri.owner_id` as its first statement on
one, with `set_config(..., true)`: PostgreSQL's transaction-local form of `SET LOCAL`, which,
unlike `SET LOCAL`, takes a bound parameter, so no `owner_id` is ever spliced into SQL. The
setting therefore never outlives the transaction, and a pooled connection carries no scope into
the next one.

**Where a transaction's owner comes from**, in order:

1. the store verb's own argument (a scope, a record, a job, a lease request);
2. for a read by `session_id` alone, `rra_session_owner` in the same transaction (`FR-265`);
3. the unit `acting_for` has bound, for verbs that name only a job or a deletion.

Every source present must agree, or `ScopeConflict` is raised: a scope already set is never
replaced. A unit bound as *unresolved* (a beta request whose cookie the lookup could not resolve)
runs with no setting, so the policies hide every row and refuse every write.

**Why a `ContextVar` cannot leak.** It is per thread and per asyncio task, `acting_for` resets it
in `finally`, and it is read only when a verb opens a transaction, never at connect or checkout.
It names the unit; the database setting is set afresh by every transaction.

On SQLite there is no policy and nothing to set, so the setting is skipped and only the agreement
checks run. A transaction on PostgreSQL that reaches a covered table with no source at all is
refused loudly by `khepri.runtime.scope_tripwire`, which reads the marker `mark` leaves.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.definer_calls import SqlSessionOwners, session_owner

OWNER_SETTING = "khepri.owner_id"
#: The key, in a connection's `info`, of the scope its current transaction set.
SCOPE_MARK = "khepri.rra.scope"
#: The marker value for a transaction that deliberately runs with no scope.
UNRESOLVED = object()

#: Sets the scope unless this transaction already holds another: `NULL` means it does.
_SET_ONCE = text(
    "SELECT CASE WHEN coalesce(current_setting('khepri.owner_id', true), '') NOT IN ('', :owner) "
    "THEN NULL ELSE set_config('khepri.owner_id', :owner, true) END"
)

class ScopeConflict(RuntimeError):
    """Two sources name different scopes for one unit: a scope set is never replaced."""


class ScopeRequired(RuntimeError):
    """A covered table was reached with no scope from any source (`FR-233`)."""


@dataclass(frozen=True, slots=True)
class UnitScope:
    """The scope a unit acts in. `owner_id` is `None` for a unit whose scope did not resolve."""

    owner_id: str | None


_UNIT: ContextVar[UnitScope | None] = ContextVar("khepri_rra_unit_scope", default=None)


@contextmanager
def acting_for(owner_id: str | None) -> Iterator[UnitScope]:
    """Bind the unit's scope for the block. `None` binds a unit whose scope did not resolve.

    Entering a unit already bound to the same scope joins it; to another scope raises.
    """
    bound = _UNIT.get()
    if bound is not None:
        if bound.owner_id != owner_id:
            raise ScopeConflict("This unit of work already acts in another scope.")
        yield bound
        return
    unit = UnitScope(owner_id)
    token = _UNIT.set(unit)
    try:
        yield unit
    finally:
        _UNIT.reset(token)


def bound_unit() -> UnitScope | None:
    """The unit bound for the current thread or task, if any."""
    return _UNIT.get()


def resolve(owner_id: str | None) -> UnitScope | None:
    """The scope a transaction acts in: the verb's own owner, else the bound unit's."""
    bound = _UNIT.get()
    if owner_id is None:
        return bound
    if bound is not None and bound.owner_id != owner_id:
        raise ScopeConflict("A store verb named a scope other than its unit's.")
    return UnitScope(owner_id)


def mark(database: Session, scope: UnitScope | None) -> None:
    """Set `scope` on this transaction: the marker everywhere, the setting on PostgreSQL."""
    if scope is None:
        return
    connection = database.connection()
    connection.info[SCOPE_MARK] = UNRESOLVED if scope.owner_id is None else scope.owner_id
    if scope.owner_id is None or connection.dialect.name != "postgresql":
        return
    if connection.execute(_SET_ONCE, {"owner": scope.owner_id}).scalar() is None:
        raise ScopeConflict("This transaction already acts in another scope.")


def apply_scope(database: Session, owner_id: str) -> None:
    """Join an already-open transaction (an RCA `unit_of_work`) to `owner_id`'s scope."""
    mark(database, resolve(owner_id))


@contextmanager
def scoped_begin(factory: sessionmaker[Session], owner_id: str | None = None) -> Iterator[Session]:
    """A writing transaction, committed on exit, its scope set first."""
    with factory.begin() as database:
        mark(database, resolve(owner_id))
        yield database


@contextmanager
def scoped_read(factory: sessionmaker[Session], owner_id: str | None = None) -> Iterator[Session]:
    """A reading session whose transaction has its scope set first."""
    with factory() as database:
        mark(database, resolve(owner_id))
        yield database


def bootstrap(database: Session, session_id: str) -> str | None:
    """`FR-265`: learn the scope of `session_id` and set it, inside this transaction.

    Returns the owner, or `None` when the lookup finds nothing, in which case the caller reads
    nothing. Within a bound unit, an answer that differs from the unit's scope raises.
    """
    owner = session_owner(database, session_id)
    bound = _UNIT.get()
    if bound is not None and owner != bound.owner_id:
        raise ScopeConflict("A session of another scope was named in this unit of work.")
    if owner is None:
        mark(database, bound)
        return None
    mark(database, UnitScope(owner))
    return owner


def first_by_session[R](
    factory: sessionmaker[Session], session_id: str, read: Callable[[Session], R]
) -> R | None:
    """Run `read` under the scope `session_id` resolves to, or return `None` without reading."""
    with factory() as database:
        if bootstrap(database, session_id) is None:
            return None
        return read(database)


def require_session_in_scope(database: Session, session_id: str) -> None:
    """A by-`session_id` read inside an already-scoped transaction: the lookup must agree.

    A session the lookup does not find is left to the read after this, which then finds nothing
    and fails closed exactly as it did before (`LookupError`); one of another scope raises here.
    """
    owner = session_owner(database, session_id)
    scope = database.connection().info.get(SCOPE_MARK)
    if owner is not None and owner != scope:
        raise ScopeConflict("A session of another scope was named in this transaction.")


__all__ = [
    "OWNER_SETTING",
    "SCOPE_MARK",
    "UNRESOLVED",
    "ScopeConflict",
    "ScopeRequired",
    "SqlSessionOwners",
    "UnitScope",
    "acting_for",
    "apply_scope",
    "bootstrap",
    "bound_unit",
    "first_by_session",
    "mark",
    "require_session_in_scope",
    "resolve",
    "scoped_begin",
    "scoped_read",
]
