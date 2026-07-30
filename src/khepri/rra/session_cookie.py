"""How a beta session is carried over HTTP, and what a missing one earns.

**Why this is its own module.** More than one module declares routes, and each
of them needs the cookie's name to read it and the same refusal when it is
absent. A second definition of either would be a second thing to change: the
cookie's name is security-relevant, and a refusal that differs between route
groups tells a caller which group it reached.

**Why not `sessions`.** That module is the session *domain* -- invitations,
scopes, consent, expiry -- and it is imported by the storage and service layers,
none of which should learn a cookie name or depend on a web framework. RRA-001
governs what a session is; how one is transported is a separate decision, and
this is where that decision lives.

**Deliberately only the identification contract.** No route, no service, no
policy. The cookie's `secure`, `httponly`, `samesite` and `path` attributes are
set where the cookie is issued and cleared, because those belong to the endpoint
that owns the session's lifetime rather than to every endpoint that reads it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie

SESSION_COOKIE = "khepri_beta_session"

# What a caller is told when no usable session reached the route. One sentence
# for every cause -- absent cookie, expired session, another caller's resource --
# because RRA-001 refuses without revealing which check failed.
SESSION_UNAVAILABLE = "Session is unavailable."

# The one spelling of "this route reads the caller's beta session cookie".
BetaSessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]

__all__ = [
    "SESSION_COOKIE",
    "SESSION_UNAVAILABLE",
    "BetaSessionCookie",
]
