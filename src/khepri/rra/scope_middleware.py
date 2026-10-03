"""Each beta request is one unit of work in the scope its cookie resolves to (`RRA-017` `FR-233`).

The routes read and write through store verbs, some of which name only a job or a delivery. Those
take their scope from the unit this middleware binds: `rra_session_owner` resolves the cookie in
the threadpool, and `acting_for` binds the answer around the rest of the request. A cookie the
lookup cannot resolve binds a deliberately *unresolved* unit, so the policies hide every row and
the route answers as it does for any unavailable session.

**Why it cannot leak.** The value lives in a `ContextVar`. Starlette copies the context into the
task that runs `call_next` and into the threadpool a sync handler runs in, so the binding reaches
the request and nothing else, and `acting_for` resets it when the request ends. Redemption is
excluded: it mints a new scope, and a stale cookie must never stop it (`FR-233`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from fastapi import FastAPI, Request, Response
from starlette.concurrency import run_in_threadpool

from khepri.rra.scope import acting_for
from khepri.rra.session_cookie import SESSION_COOKIE

BETA_PREFIX = "/api/v1/beta"
REDEEM_PATH = f"{BETA_PREFIX}/sessions/redeem"


class SessionOwnerLookup(Protocol):
    def owner_of(self, session_id: str | None) -> str | None: ...


def add_scope_unit(app: FastAPI, owners: SessionOwnerLookup) -> None:
    """Bind every beta request but redemption to the scope its session cookie resolves to."""

    @app.middleware("http")
    async def _scope_unit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        session_id = request.cookies.get(SESSION_COOKIE)
        if not session_id or not _in_a_unit(request.url.path):
            return await call_next(request)
        owner_id = await run_in_threadpool(owners.owner_of, session_id)
        with acting_for(owner_id):
            return await call_next(request)


def _in_a_unit(path: str) -> bool:
    """A beta path other than redemption, which mints its own scope (`FR-233`)."""
    return path.startswith(BETA_PREFIX) and path != REDEEM_PATH


__all__ = ["BETA_PREFIX", "REDEEM_PATH", "SessionOwnerLookup", "add_scope_unit"]
