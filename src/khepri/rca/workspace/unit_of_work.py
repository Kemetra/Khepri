"""One transaction across the workspace stores (`W1-04`; `RCA-005` `FR-125`).

`FR-125` says every workspace action emits one audit event. With each store opening its own
transaction, the action's write committed and *then* the event's transaction began, so a fault
between the two left a version, run, completion or profile persisted with no event -- and a retry
recorded only `already_recorded`. Review on `#372` found the window.

**The ambient unit of work.** `unit_of_work(factory)` opens one transaction and publishes its
session through a `ContextVar`; every store method then reaches the database through `writing` or
`reading`, which join the ambient session when one is open and behave exactly as before -- one
transaction per call -- when none is. The service wraps the action and its event in one unit, so
either both commit or neither does, and no store had to change its signature.

**Why a `ContextVar` and not a parameter.** Threading a session through every store method would
change fourteen signatures and every caller, for a property that belongs to the *service* layer:
the stores do not know they are being composed. A context variable is scoped to the task that set
it, so two concurrent requests never see each other's session.

**Reads join too.** A service that writes a completion and re-reads the run inside the same unit
must see its own write, which only the same session can show it before commit. Autoflush makes the
pending change visible to the query, and the mapper guards still fire at that flush.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy.orm import Session, sessionmaker

_AMBIENT: ContextVar[Session | None] = ContextVar("khepri_workspace_unit_of_work", default=None)


@contextmanager
def unit_of_work(factory: sessionmaker) -> Iterator[Session]:
    """One transaction for everything the block does through the workspace stores.

    Nested units join the outer one rather than opening a second transaction, so a service method
    that calls another stays in one unit. Committed on a normal exit, rolled back on an exception.
    """
    existing = _AMBIENT.get()
    if existing is not None:
        yield existing
        return
    with factory.begin() as database:
        token = _AMBIENT.set(database)
        try:
            yield database
        finally:
            _AMBIENT.reset(token)


@contextmanager
def writing(factory: sessionmaker) -> Iterator[Session]:
    """A session to write through: the ambient one if a unit of work is open, else its own
    transaction, committed on exit -- what `factory.begin()` gave every store before."""
    ambient = _AMBIENT.get()
    if ambient is not None:
        yield ambient
        return
    with factory.begin() as database:
        yield database


@contextmanager
def reading(factory: sessionmaker) -> Iterator[Session]:
    """A session to read through: the ambient one if a unit of work is open, else a fresh one."""
    ambient = _AMBIENT.get()
    if ambient is not None:
        yield ambient
        return
    with factory() as database:
        yield database
