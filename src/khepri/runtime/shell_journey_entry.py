"""Starting an analysis from the shell and handing off to the journey (`R8-06`).

**Route, not embed.** The roadmap offers either; the code decides. `page(request, language, step)`
in `khepri.rra.journey.routes` takes no session and renders a static template -- the browser then
fetches `/api/v1/beta/journey`, and *that* is what reads the beta cookie. There is nothing to
embed: the workflow already lives behind an API, and reproducing it in the shell would be a second
implementation of the journey.

**What this hands over is a cookie, not a session.** `CommercialBridge.open` already writes a real
`BetaSessionRow` through `open_commercial_session_row`, so the analysis is readable by the
journey's own reader the moment it exists. This module mints nothing, stores nothing, and adds no
session semantics; it sets the transport the journey already expects and redirects.

**The two cookies do not collide.** `khepri_session` is the commercial one; `khepri_beta_session`
is scoped to `/api/v1/beta`, which is exactly where the journey's XHR goes and nowhere the shell
serves. `R3-01` requires the names to differ "regardless of path" for precisely this reason -- a
browser holds both at once here, and each route reads only its own.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse

from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.rra.session_cookie import SESSION_COOKIE as BETA_SESSION_COOKIE
from khepri.runtime.shell_invitations import ShellRendering

#: The journey step an analysis starts on. Named rather than inlined so the handoff target is one
#: value a reader can find, and so a later journey change moves one constant.
JOURNEY_ENTRY_STEP = "upload"

#: The beta session's transport, matching `rra/api.py`'s redeem endpoint exactly.
#:
#: **Matched deliberately rather than by coincidence.** Two routes now issue this cookie -- the
#: invitation redemption and this one -- and a weaker set of flags on either would be a downgrade
#: reachable by taking that route instead of the other. `path` is `/api/v1/beta` because that is
#: where the journey's client fetches state; the pages themselves read no cookie.
BETA_COOKIE_PATH = "/api/v1/beta"
BETA_COOKIE_MAX_AGE = 7 * 24 * 60 * 60


def add_journey_entry_route(
    app: FastAPI,
    *,
    services: Any,
    rendering: ShellRendering,
    clock: Callable[[], Any],
) -> None:
    """Declare the entry route, or none at all when no bridge is wired.

    The null guard follows `add_commercial_routes`: with no bridge the route is never declared, so
    a beta-only deployment has no commercial entry rather than one that exists and refuses.
    """
    if services.bridge is None:
        return

    environment = rendering.environment
    language_of = rendering.language_of
    unavailable = rendering.unavailable

    @app.post(f"{rendering.prefix}/{{language}}/{{organization}}/analyses")
    def start_analysis(
        language: str,
        organization: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """Open an analysis, then hand the browser to the journey.

        Every refusal is the same `unavailable` surface, and **no cookie is set on that path**: a
        `Set-Cookie` accompanying a refusal would hand a session to a caller who was just denied
        one.
        """
        rendered = language_of(language)
        if session is None:
            return unavailable(environment, language=rendered)
        now = clock()
        try:
            context = services.resolver.for_request(
                session, organization_id=organization, now=now
            )
            opened = services.bridge.open(
                account_id=context.account_id,
                organization_id=context.organization_id,
                now=now,
            )
        except PermissionError:
            return unavailable(environment, language=rendered)

        response = RedirectResponse(
            url=f"/beta/{rendered}/{JOURNEY_ENTRY_STEP}", status_code=303
        )
        hand_off_session(response, opened.session_id)
        return response


def hand_off_session(response: Response, session_id: str) -> None:
    """Set the beta cookie for one analysis session, with the one set of flags -- and the shell's
    security headers, which `FR-043` puts on every shell response and a redirect is one.

    Shared with the artifact handoff (`W1-06`): three routes now issue this cookie, and a weaker
    set of flags or headers on any of them would be a downgrade reachable by taking that route
    instead (review on `#376`).
    """
    response.headers.update(SECURITY_HEADERS)
    response.set_cookie(
        key=BETA_SESSION_COOKIE,
        value=session_id,
        max_age=BETA_COOKIE_MAX_AGE,
        secure=True,
        httponly=True,
        samesite="strict",
        path=BETA_COOKIE_PATH,
    )


__all__ = [
    "BETA_COOKIE_MAX_AGE",
    "BETA_COOKIE_PATH",
    "JOURNEY_ENTRY_STEP",
    "add_journey_entry_route",
    "hand_off_session",
]
