"""Ending the caller's own Khepri session: logout (`RCA-001` `FR-219`).

**Revoke in the store, then clear the cookie.** `FR-219` orders the two halves: the session is
revoked server-side *before* the cookie is cleared, so no copy of the token -- a second tab, a
proxy log, a stolen cookie -- authorizes anything afterwards. `clear_session_cookie` is the browser
half only; its own docstring names this route's `revoke` as the half that makes logout real.

**One answer for every cause.** A live session, an already-revoked or expired one, an unknown
token, and no cookie at all each receive the same empty `204` that clears the cookie. `FR-219`
requires the response to be identical whether or not the presented session was live, and
`SessionService.revoke` refuses an absent or already-revoked session, so that refusal is caught
here rather than surfaced. Every governed refusal is a `PermissionError`, so the broader class is
what is caught.

**Only this session.** `revoke(token)` ends the one record the cookie names. The account's other
sessions are untouched, which `FR-219` requires; `revoke_all` is recovery's and disablement's verb
(`FR-007`, `FR-008`), not logout's.

**Registered whether or not an identity provider is configured.** Sessions are minted only by the
provider handoff, but they outlive the provider's configuration: `clerk_hard_stop` runs after the
disabled configuration is deployed, so a provider-less app can still be presented a live session.
Logout needs no provider call, and a logout that disappeared with the provider would leave those
sessions with no way to end them. Its own module for that reason, beside rather than inside
`external_auth_api.py`, whose registrar returns early when no provider is configured.

**No CSRF token, matching the shell's posture** (`shell_pins.py`). The deployed app registers
`rra/journey/security.py`'s `require_same_origin` as app-global middleware, so a cross-site POST is
refused with 403 before this route runs and never receives the clearing `Set-Cookie` -- a forced
logout is refused, not merely harmless. The cookie is also `SameSite=Strict`.

**A revoke that fails for any other reason is not swallowed.** Only the governed refusal
(`PermissionError`) is answered as success. A store outage propagates, so the cookie is not cleared
while the token still authorizes -- the one outcome `FR-219`'s ordering exists to forbid.

**Not a provider sign-out.** `FR-219` excludes propagating the end of a session to an external
identity provider; this route never calls one.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from datetime import datetime

from fastapi import FastAPI, Response, status

from khepri.rca.session_cookie import CommercialSessionCookie, clear_session_cookie
from khepri.rca.session_service import SessionService
from khepri.runtime.commercial_api import COMMERCIAL_PREFIX

SESSION_END_PATH = f"{COMMERCIAL_PREFIX}/auth/logout"


def add_session_end_route(
    app: FastAPI,
    *,
    sessions: SessionService,
    clock: Callable[[], datetime],
) -> None:
    """Register the logout route. Unconditional: see the module docstring."""

    @app.post(SESSION_END_PATH, status_code=status.HTTP_204_NO_CONTENT)
    def end_session(khepri_session: CommercialSessionCookie = None) -> Response:
        if khepri_session:
            # Absent, unknown, or already revoked: FR-219 answers these as it answers a live
            # session, so the refusal is not surfaced.
            with suppress(PermissionError):
                sessions.revoke(khepri_session, now=clock())
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        response.set_cookie(**clear_session_cookie())
        return response


__all__ = ["SESSION_END_PATH", "add_session_end_route"]
