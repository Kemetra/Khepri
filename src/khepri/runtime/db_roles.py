"""The runtime's database roles, and the one place an engine is built (`RRA-017` `FR-270`).

Every composition root names the role it connects as, and `engine_for` is the only call that turns
a URL into an engine. On PostgreSQL each new connection proves its role before it is used: the
login must be the role's own name, and neither a superuser nor a role that bypasses row security.
An environment that hands a runtime process the migration owner's credential therefore refuses to
start its first transaction, instead of running with every policy silently bypassed.

The application and worker engines also carry `khepri.runtime.scope_tripwire`, so a transaction
that reaches a covered table with no scope fails loudly. The sweep engine does not: its four
components read across scopes by design, through policies granted to the sweep role alone
(`FR-271`).
"""

from __future__ import annotations

from enum import Enum

from sqlalchemy import URL, Engine, create_engine, event, text

from khepri.runtime.scope_tripwire import attach_tripwire


class DatabaseRole(Enum):
    """The three roles a runtime process may log in as. Each value is the role's literal name."""

    APPLICATION = "khepri_app"
    WORKER = "khepri_worker"
    SWEEP = "khepri_sweep"


#: The secret variable each role's credential arrives through. The source is `OPS1`'s to choose.
SECRET_VARIABLES = {
    DatabaseRole.APPLICATION: "KHEPRI_DATABASE_SECRET",
    DatabaseRole.WORKER: "KHEPRI_WORKER_DATABASE_SECRET",
    DatabaseRole.SWEEP: "KHEPRI_SWEEP_DATABASE_SECRET",
}
_SCOPED = frozenset({DatabaseRole.APPLICATION, DatabaseRole.WORKER})
_WHO = text(
    "SELECT current_user, session_user, r.rolsuper, r.rolbypassrls "
    "FROM pg_roles AS r WHERE r.rolname = current_user"
)


class RoleMismatch(RuntimeError):
    """A runtime connection logged in as something other than its own non-bypassing role."""


def engine_for(url: URL | str, role: DatabaseRole) -> Engine:
    """A pooled engine for `role`: on PostgreSQL, role-checked and, when scoped, tripwired."""
    engine = create_engine(url, pool_pre_ping=True, future=True)
    if engine.dialect.name != "postgresql":
        return engine
    event.listen(engine, "connect", _role_check(role))
    if role in _SCOPED:
        attach_tripwire(engine)
    return engine


def _role_check(role: DatabaseRole):
    def check(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(str(_WHO))
            found = cursor.fetchone()
        finally:
            cursor.close()
        _require_role(found, role)

    return check


def _require_role(found: tuple | None, role: DatabaseRole) -> None:
    if found is None:
        raise RoleMismatch(f"The connection's role is not a known role; expected {role.value}.")
    current, session, superuser, bypasses = found
    if current != role.value or session != role.value:
        raise RoleMismatch(f"Connected as {session}, expected {role.value}.")
    if superuser or bypasses:
        raise RoleMismatch(f"{role.value} is a superuser or bypasses row security.")


__all__ = ["SECRET_VARIABLES", "DatabaseRole", "RoleMismatch", "engine_for"]
