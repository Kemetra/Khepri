"""Shared fixtures for the `W1-05` integration cases over `tests/w104_support.py`'s world.

The modules -- public Overview and Data, then the staged Analyses renderer -- drive the same shape:
a member whose `owner_id` differs from their `organization_id`, rows written by the real
`WorkspaceActions` through the real `RRA-003` admission, and rendering over the same stores and a
real `IsolationService`. Holding that here keeps each module to its cases and lets CodeScene see
one definition of the wiring rather than two similar ones.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.isolation import IsolationService
from khepri.rca.persistence import SqlAccountStore
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.runtime.shell_api import (
    SHELL_PREFIX,
    ShellServices,
    _analyses_response,
    add_shell_routes,
    shell_environment,
)
from khepri.runtime.workspace import ReportLocator
from tests.w104_support import (
    JOB,
    LATER,
    NOW,
    Member,
    World,
    admitted_session,
    derived,
)


@dataclass
class Context:
    account_id: str
    organization_id: str | None
    role: str | None = "owner"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


class StubResolver:
    """The session checkpoint, stubbed: what it returns is the real member's identifiers."""

    def __init__(self, context: Context) -> None:
        self._context = context

    def for_request(self, token: str, *, organization_id: str | None, now: object) -> Context:
        return self._context

    def require_owner(self, token: str, *, organization_id: str, now: object) -> Context:
        return self._context


def services_over(w: World, who: Member) -> ShellServices:
    """The real stores and isolation boundary the shell receives."""
    return ShellServices(
        resolver=StubResolver(Context(who.account_id, who.organization_id)),
        organizations=w.organizations,
        records=w.store,
        isolation=IsolationService(w.organizations, SqlAccountStore(w.factory)),
    )


def shell_over(w: World, who: Member) -> TestClient:
    """The shell over the world's own stores, the way `build_shell_services` wires it."""
    app = FastAPI()
    add_shell_routes(app, services=services_over(w, who), clock=lambda: LATER)
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def page(w: World, who: Member, surface: str) -> str:
    """The surface as the member sees it, addressed by their own organization."""
    return shell_over(w, who).get(f"{SHELL_PREFIX}/en/{who.organization_id}/{surface}").text


def staged_analyses_page(w: World, who: Member) -> str:
    """Render the hardened Analyses staging boundary without exposing its public route.

    `FR-049` withholds that route until live runs persist trust state and a valid next action can
    be followed. These tests still exercise the read model that will back the eventual surface.
    """
    response = _analyses_response(
        services_over(w, who),
        shell_environment(),
        language="en",
        context=Context(who.account_id, who.organization_id),
    )
    return response.body.decode()


def admitted_version(w: World, who: Member, content: bytes | None = None) -> tuple[str, str]:
    """One version created by the real actions from a session the real admission admitted.
    Returns the session and the version identifiers."""
    session_id = (
        admitted_session(w, who.owner_id)
        if content is None
        else admitted_session(w, who.owner_id, content)
    )
    version = w.services.create_dataset_version(who.caller, session_id=session_id, now=NOW)
    return session_id, version.version_id


def started_run(w: World, who: Member) -> tuple[str, str, str]:
    """A version and a run started over it. Returns session, version and run identifiers."""
    session_id, version_id = admitted_version(w, who)
    run = w.services.start_analysis_run(who.caller, version_id=version_id, now=LATER)
    return session_id, version_id, run.run_id


def completed_run(w: World, who: Member) -> tuple[str, str, str]:
    """A run completed by the real actions over the real `RRA-004` package and the report
    boundary's fakes, so every required artifact is bound."""
    session_id, version_id, run_id = started_run(w, who)
    derived(w, session_id)
    w.services.complete_analysis_run(
        who.caller, run_id=run_id, report=ReportLocator(session_id, JOB), now=LATER
    )
    return session_id, version_id, run_id
