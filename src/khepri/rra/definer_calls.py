"""The only module that calls `RRA-017`'s four definer functions (`FR-264`).

Each function answers one pre-scope question, the only reads that cross the policies before a
unit of work has a scope: whose session a `session_id` is (`FR-265`), and which jobs are due for a
claim or a recovery, with their owners (`FR-267`). Every call returns scope keys, never a row's
content, and the caller then sets the scope it learned before it reads anything else.

**The SQLite path is gated by dialect, not by whether a function exists.** On PostgreSQL every call
reaches its function; on SQLite, which has no policy to cross, it runs the Python statement the
function mirrors. Any other dialect raises, so no unforeseen backend silently takes the fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import column, select, table, text
from sqlalchemy.orm import Session, sessionmaker

_SESSIONS = table("rra_beta_sessions", column("session_id"), column("owner_id"))
_LOOKUP = text("SELECT rra_session_owner(:session_id)")
_NEXT_CLAIMABLE = text("SELECT job_id, owner_id FROM rra_next_claimable_job(:now)")
_EXPIRED = text("SELECT job_id, owner_id FROM rra_expired_lease_jobs(:now)")
_ORPHANED = text("SELECT job_id, owner_id FROM rra_orphaned_jobs(:now)")


@dataclass(frozen=True, slots=True)
class Candidate:
    """A job named across scopes: its identifier and the scope to act on it in. Nothing else."""

    job_id: str
    owner_id: str


def _on_postgres(database: Session) -> bool:
    dialect = database.get_bind().dialect.name
    if dialect not in ("postgresql", "sqlite"):
        raise RuntimeError(f"RRA-017 has no definer-call path for the {dialect} dialect.")
    return dialect == "postgresql"


def session_owner(database: Session, session_id: str | None) -> str | None:
    """`rra_session_owner`: the owner of exactly this session, or `None`."""
    if not session_id:
        return None
    if _on_postgres(database):
        return database.execute(_LOOKUP, {"session_id": session_id}).scalar()
    statement = select(_SESSIONS.c.owner_id).where(_SESSIONS.c.session_id == session_id)
    return database.execute(statement).scalar()


class SqlSessionOwners:
    """The lookup as a port, for a caller that reads no covered table itself (`FR-266`)."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def owner_of(self, session_id: str | None) -> str | None:
        if not session_id:
            return None
        with self._factory() as database:
            return session_owner(database, session_id)


def next_claimable(database: Session, now: datetime) -> Candidate | None:
    """`rra_next_claimable_job`: the job due longest, with its owner, or `None`. No lock."""
    if _on_postgres(database):
        found = database.execute(_NEXT_CLAIMABLE, {"now": now}).first()
    else:
        from khepri.rra.job_persistence import (  # noqa: PLC0415
            ReportJobRow,
            next_claimable_statement,
        )

        found = database.execute(next_claimable_statement(now).add_columns(ReportJobRow.owner_id))
        found = found.first()
    return None if found is None else Candidate(*found)


class RecoveryCandidates:
    """The two recovery pickers, over the engine of whichever role may call them."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def expired(self, now: datetime) -> tuple[Candidate, ...]:
        from khepri.rra.job_persistence import expired_lease_statement  # noqa: PLC0415

        return self._pick(_EXPIRED, now, expired_lease_statement(now))

    def orphaned(self, now: datetime) -> tuple[Candidate, ...]:
        from khepri.rra.job_persistence import orphaned_statement  # noqa: PLC0415

        return self._pick(_ORPHANED, now, orphaned_statement())

    def _pick(self, function: object, now: datetime, fallback: object) -> tuple[Candidate, ...]:
        with self._factory() as database:
            if _on_postgres(database):
                rows = database.execute(function, {"now": now}).all()
            else:
                rows = database.execute(fallback).all()
        return tuple(Candidate(*found) for found in rows)


__all__ = [
    "Candidate",
    "RecoveryCandidates",
    "SqlSessionOwners",
    "next_claimable",
    "session_owner",
]
