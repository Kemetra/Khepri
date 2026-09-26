"""The chooser's switch: make another organization the session's active one (#594).

`RCA-001` `FR-029`: switching MUST succeed only into an organization in which the actor holds a
current membership, and MUST take effect for every later decision in that session. Before this
route nothing switched inside a session. The chooser's rows linked to addresses that only *compare*
against the active organization (`FR-042`), so a reader whose active organization had been revoked
found every row answering `unavailable`, and its exit led back to the chooser. The owner's
2026-09-26 decision on #594 requires the reader to be able to select another organization they
still belong to before organization-scoped work continues. `RCA-002` `FR-051a` makes this route
the chooser's selection.

**A POST, not a link.** It changes session state, and a GET that mutates is a GET a browser may
prefetch. Cross-site submission is refused by the app-wide `require_same_origin` middleware, as for
every other shell POST.

**Refusals are the uniform `unavailable` surface.** `OrganizationSwitcher.switch` refuses an
unknown organization and a non-member identically (`FR-004`, `FR-022`), and so does this route: no
session, a dead session, or no membership all render the same page with no `Location`.

**Where it lands.** The organization's entry surface, decided the way the chooser decides it:
Overview when this deployment holds a workspace reader, Team when it does not (`FR-049`).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse

from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.runtime.shell_frame import offers_workspace
from khepri.runtime.shell_invitations import ShellRendering

__all__ = ["add_switch_route", "entry_surface", "offers_switching"]


def offers_switching(services: Any) -> bool:
    return getattr(services, "switcher", None) is not None


def entry_surface(services: Any) -> str:
    """Where an organization opens: Overview with a workspace reader, Team without (`FR-049`)."""
    return "overview" if offers_workspace(services) else "team"


def add_switch_route(
    app: FastAPI,
    *,
    services: Any,
    rendering: ShellRendering,
    clock: Callable[[], datetime],
) -> None:
    """Declare the switch route, where this deployment offers switching."""
    if not offers_switching(services):
        return

    environment = rendering.environment
    language_of = rendering.language_of
    unavailable = rendering.unavailable

    @app.post(f"{rendering.prefix}/{{language}}/{{organization}}/switch")
    def switch_organization(
        language: str,
        organization: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """Point this session at `organization`, or refuse with no trace of why."""
        rendered = language_of(language)
        if session is None:
            return unavailable(environment, language=rendered)
        try:
            services.switcher.switch(session, organization, now=clock())
        except PermissionError:
            return unavailable(environment, language=rendered)
        response = RedirectResponse(
            url=f"{rendering.prefix}/{rendered}/{organization}/{entry_surface(services)}",
            status_code=303,
        )
        response.headers.update(SECURITY_HEADERS)
        return response
