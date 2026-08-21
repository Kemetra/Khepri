"""How a commercial session is carried over HTTP, and what an invalid one earns (`R3-06`).

**Its own module, following `rra/session_cookie.py`'s shape.** More than one module will declare
commercial routes, and each needs the cookie's name to read it and the same refusal when it is
unusable. A second definition of either would be a second thing to change: the name is
security-relevant, and a refusal that differs between route groups tells a caller which group it
reached.

**The name differs from RRA's, and the difference is the point.** `R3-01` §5: a browser sends
cookies by name and path, so a name collision on an overlapping path is silent — any route under a
shared prefix would read an RCA cookie as a beta `session_id`. `rra/sessions.py` and
`rca/organizations.py` already mint byte-identical `own_` values distinguishable only by which
table holds them; this is the same ambiguity one layer up, and it is avoided rather than managed.

**A separate refusal literal rather than RRA's `SESSION_UNAVAILABLE`.** The two vocabularies are
allowed to diverge later, and sharing one object now would make that divergence a breaking change
in the wrong module.

**Deliberately transport only.** No route, no service, no session predicate. `R3-01` §4 names RRA
as the counter-example — its expiry predicate is repeated at four call sites because no single
chokepoint owns it. Deciding whether a session is live is `R3-04`'s `resolve`, and duplicating any
part of that judgment here would recreate exactly the drift this package has been avoiding.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any

from fastapi import Cookie

#: Distinct from RRA's `khepri_beta_session`. See the module docstring.
SESSION_COOKIE = "khepri_session"

#: The commercial HTTP surface. Scoped rather than `/`, so it is not offered to beta routes.
SESSION_COOKIE_PATH = "/api/v1/commercial"

# What a caller is told when no usable session reached the route. One sentence for every cause --
# absent cookie, unknown session, expired session, revoked session, disabled account -- because
# FR-004 and FR-022 refuse without revealing which check failed. Distinct from RRA's literal.
SESSION_INVALID = "Session is invalid or unavailable."

#: The one spelling of "this route reads the caller's commercial session cookie".
CommercialSessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


def _attributes() -> dict[str, Any]:
    """The protective flags, defined once so issuing and clearing cannot disagree.

    A logout that dropped `secure` or `httponly` would downgrade the cookie at exactly the moment
    the actor asked for more safety — and a `path` mismatch would leave the original cookie in
    place, so the actor stays logged in after asking to log out.

    `samesite` is Strict rather than Lax: a commercial action reached cross-site is a cross-site
    request forgery, and Lax admits top-level navigations.
    """
    return {
        "key": SESSION_COOKIE,
        "path": SESSION_COOKIE_PATH,
        "httponly": True,
        "secure": True,
        "samesite": "strict",
    }


def issue_session_cookie(token: str, *, lifetime: timedelta) -> dict[str, Any]:
    """The cookie that carries a newly issued session token.

    **`max_age` is derived from the session's own horizon** rather than configured separately. A
    cookie outliving its session leaves the browser presenting a dead token; a cookie expiring
    first logs the actor out early. Neither is a hole on its own, and deriving one from the other
    removes the possibility of both.

    Returns keyword arguments for `Response.set_cookie` rather than touching a response, so the
    transport contract stays testable without a request and the endpoint keeps ownership of when a
    session begins.
    """
    return {**_attributes(), "value": token, "max_age": int(lifetime.total_seconds())}


def clear_session_cookie() -> dict[str, Any]:
    """The cookie that ends a session in the browser (logout).

    Empty value and `max_age=0`, with every protective flag preserved. Clearing is only reliable
    when the name and path match the issued cookie exactly, which `_attributes` guarantees by
    being the single source of both.

    **This is the browser half only.** Revoking the server-side record is `R3-04`'s `revoke`, and
    a logout that cleared the cookie without revoking would leave a live session resolvable by
    anyone holding the token.
    """
    return {**_attributes(), "value": "", "max_age": 0}


__all__ = [
    "SESSION_COOKIE",
    "SESSION_COOKIE_PATH",
    "SESSION_INVALID",
    "CommercialSessionCookie",
    "clear_session_cookie",
    "issue_session_cookie",
]
