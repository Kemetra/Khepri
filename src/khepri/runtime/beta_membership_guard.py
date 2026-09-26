"""A workspace analysis is reachable through the beta cookie only while membership holds (#594).

The shell's journey entry (`R8-06`) and artifact handoff (`W1-06`) open an analysis in an
organization's isolation scope and hand the browser `khepri_beta_session`. `khepri.rra`'s beta
routes authorize on that cookie alone, by design: RRA knows sessions, not accounts. So once a
member's membership was revoked, the cookie they already held kept uploading, profiling,
publishing, downloading and deleting in the revoked organization's scope. `RCA-001` `FR-030`
forbids exactly that: "A session whose active organization membership has been revoked MUST cease
to authorize actions in that organization". The owner's 2026-09-26 decision on #594 adds that no
protected operation may proceed using the revoked membership.

**Where the check lives.** Here, in the composition, not in `khepri.rra`: `R7-01` bars RRA from
importing RCA, and a second authorization site inside RRA is what `pipeline_recording` warns
against. The guard wraps every `/api/v1/beta/*` request.

**What it asks, per request, from live state.** A beta session whose scope is an organization's
isolation scope (`SqlIsolationScopes`, the read `pipeline_recording` uses to decide "is this a
workspace") requires a live `khepri_session`. `AuthorizationResolver.for_request`, naming no
organization, proves that session
live and its account active, and `IsolationService.resolve_scope` for that account and *the
organization owning this analysis's scope* must succeed. Both re-read membership and
account state on every call, so revocation takes effect on the next request. Nothing is cached,
and no account identifier is stored beside the session (`KHEPRI-DEC-015` §7).

**Bound to the analysis's own organization, not the active one** (owner decision, 2026-09-26).
`FR-030` refuses a *revoked* member. A member who is still in the organization and has made
another one active keeps the analysis open in their other tab.

**What passes untouched.** A request with no beta cookie, or naming a session that does not exist,
reaches the route, which refuses it itself. An invitation-redeemed session carries a
design-partner scope with no organization, so there is no membership to hold (`KHEPRI-DEC-023`).
Redemption itself (`REDEEM_PATH`) is never checked: it mints a new design-partner session and acts
in no workspace scope, so a stale workspace cookie in the same browser must not block it.

**Refusal.** RRA's own `401 {"detail": "Session is unavailable."}`, so the journey client handles
it as it handles any lost session, and no new shape exists to learn. Any lookup that refuses
(`PermissionError`) refuses the request; a store fault propagates as a 500, which still admits
nothing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from khepri.rca.authorization import AuthorizationContext
from khepri.rca.isolation import IsolationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_cookie import SESSION_COOKIE as RCA_SESSION_COOKIE
from khepri.rca.workspace.scopes import SqlIsolationScopes
from khepri.rra.persistence import SqlSessionStore
from khepri.rra.session_cookie import SESSION_COOKIE as BETA_SESSION_COOKIE
from khepri.rra.session_cookie import SESSION_UNAVAILABLE
from khepri.rra.sessions import BetaSession

__all__ = ["BETA_PREFIX", "REDEEM_PATH", "BetaMembershipGuard", "add_beta_membership_guard"]

BETA_PREFIX = "/api/v1/beta"
#: Mints a new design-partner session; acts in no workspace scope, so the guard never checks it.
REDEEM_PATH = f"{BETA_PREFIX}/sessions/redeem"


class _Sessions(Protocol):
    def get_session(self, session_id: str) -> BetaSession | None: ...


class _Scopes(Protocol):
    def organization_of(self, owner_id: str) -> str | None: ...


class _Resolver(Protocol):
    def for_request(
        self, token: str, *, organization_id: str | None = None, now: datetime
    ) -> AuthorizationContext: ...


class _Isolation(Protocol):
    def resolve_scope(self, account_id: str, organization_id: str) -> str: ...


@dataclass(frozen=True, slots=True)
class BetaMembershipGuard:
    """Decides whether one beta request may reach its route. Reads live state; stores nothing."""

    sessions: _Sessions
    scopes: _Scopes
    resolver: _Resolver
    isolation: _Isolation
    clock: Callable[[], datetime]

    @classmethod
    def over(
        cls, factory: sessionmaker, *, resolver: _Resolver, clock: Callable[[], datetime]
    ) -> BetaMembershipGuard:
        """The deployed guard over one database, around the commercial routes' own resolver, so
        the two cannot disagree about membership."""
        return cls(
            sessions=SqlSessionStore(factory),
            scopes=SqlIsolationScopes(factory),
            resolver=resolver,
            isolation=IsolationService(SqlOrganizationStore(factory), SqlAccountStore(factory)),
            clock=clock,
        )

    def admits(self, beta_session_id: str | None, rca_token: str | None) -> bool:
        organization_id = self._owning_organization(beta_session_id)
        if organization_id is None:
            return True
        return rca_token is not None and self._holds(rca_token, organization_id)

    def _owning_organization(self, beta_session_id: str | None) -> str | None:
        """The organization owning the session's scope, or `None` (the route decides)."""
        if not beta_session_id:
            return None
        session = self.sessions.get_session(beta_session_id)
        return None if session is None else self.scopes.organization_of(session.owner_id)

    def _holds(self, rca_token: str, organization_id: str) -> bool:
        """Whether this live RCA session's account can still act in the analysis's organization.

        `resolve_scope` is the membership test: it refuses an account that cannot act or holds no
        membership. Its return value is not compared with the session's scope, because the
        organization was read *from* that scope and organizations and scopes are one-to-one, so
        the comparison could never be false.
        """
        try:
            # No organization named: `for_request` then asks exactly what `resolve` asks (live
            # session, active account), and the chokepoint admits only `for_request` callers.
            context = self.resolver.for_request(rca_token, now=self.clock())
            self.isolation.resolve_scope(context.account_id, organization_id)
        except PermissionError:
            return False
        return True


def add_beta_membership_guard(app: FastAPI, guard: BetaMembershipGuard) -> None:
    """Refuse every `/api/v1/beta/*` request the guard does not admit."""

    @app.middleware("http")
    async def _beta_membership(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if path.startswith(BETA_PREFIX) and path != REDEEM_PATH:
            admitted = await run_in_threadpool(
                guard.admits,
                request.cookies.get(BETA_SESSION_COOKIE),
                request.cookies.get(RCA_SESSION_COOKIE),
            )
            if not admitted:
                return JSONResponse({"detail": SESSION_UNAVAILABLE}, status_code=401)
        return await call_next(request)
