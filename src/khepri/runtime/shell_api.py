"""The commercial application shell: the base frame and the shared unavailable surface (`R8-02`).

**Authorized by `RCA-002`**, which fixes what this module may not depart from: `FR-041` (one
canonical checkpoint, no second resolution path), `FR-042` (scope from the session, never from the
path), `FR-043` (headers attached explicitly), `FR-045` (the journey's policy, not a copy of it),
`FR-046` (a closed surface set), and `FR-050`/`FR-052` (one indistinguishable refusal, carrying
nothing about the object).

## Why this module is in `khepri.runtime`

The same reason `commercial_api.py` is. `R7-07` asserts a flat two-way prohibition -- `khepri.rca`
imports no `khepri.rra` module and `khepri.rra` imports no `khepri.rca` module -- and a shell route
needs `AuthorizationResolver` (RCA) while rendering with RRA's security policy. The composition
root is the one layer allowed to know both sides.

A design handoff placed this under `khepri.rra.journey` and passed that boundary test only by
declaring its own membership Protocol instead of using the resolver. `FR-041` forbids exactly that:
the seam it would have created is a second definition of membership resolution beside the merged
`resolve_scope`.

## Every refusal is one response

`FR-050` collapses expired, deleted, deletion-requested, session-unavailable, and
actor-not-a-member into one surface. `AuthenticationFailed` and `ScopeAccessDenied` both derive
from `PermissionError` (`rca/errors.py`), so one handler covers both and the uniformity is
structural rather than a convention two branches must remember. An absent cookie takes the same
path, because a caller must not learn that a session was the thing that was missing.

The response carries no object identifier, no cause, and no organization name, which is `FR-052`
examined without comparison: a shell leaking the same field in all five states would still be
perfectly indistinguishable across them.

## The surface set is closed

`FR-046` requires an unknown path to reach the shared unavailable surface rather than a distinct
not-found page. One catch-all route is how that is met structurally: there is no path under the
prefix that is *not* the unavailable surface until a later slice adds one, so a missing surface
cannot be distinguished from a forbidden one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import files
from typing import Any, Protocol

from fastapi import FastAPI, Response
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.runtime.shell_copy import DIRECTIONS, SHELL_COPY

#: Where the shell is addressed. `FR-047` requires one language-parameterised prefix, so every
#: surface below this point takes its language from the address rather than from stored state.
SHELL_PREFIX = "/app"

#: Where the shell's own assets are served. The journey's allowlist at `/beta/assets/{name}` is
#: tied to the journey app and does not serve this prefix; `RCA-002` excludes changing it.
SHELL_ASSETS = f"{SHELL_PREFIX}/assets"

_DEFAULT_LANGUAGE = "en"

#: What the shell serves, by exact name. `shell.css` ships from `R8-01` and lives beside the
#: journey's assets; it is read from there rather than copied, because two copies of a stylesheet
#: are two things to keep in step and `test_r801_shell_tokens.py` asserts against the original.
_ASSETS = {"shell.css": "text/css; charset=utf-8"}


class ActorResolver(Protocol):
    """The canonical checkpoint, as `commercial_api.py` already consumes it.

    Declared structurally so this module depends on the shape it calls rather than on an `RCA`
    class. That is not a second resolution path: there is one implementation, it is the merged
    resolver, and `FR-041`'s prohibition is on resolving *elsewhere*, not on naming the call.
    """

    def for_request(
        self, token: str, *, organization_id: str | None, now: Any
    ) -> Any: ...  # pragma: no cover -- Protocol


@dataclass(frozen=True, slots=True)
class ShellServices:
    """What the shell needs to render an authenticated frame, and nothing more."""

    resolver: ActorResolver


def shell_environment() -> Environment:
    """`StrictUndefined`, so a missing copy key fails the render rather than rendering a blank."""
    return Environment(
        loader=PackageLoader("khepri.runtime", "shell_templates"),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
    )


def _language(requested: str) -> str:
    """An unknown language code renders in English rather than failing.

    A language that is not offered is not a refusal, and treating it as one would give
    `FR-050`'s uniform surface a sixth cause that is not a denial at all.
    """
    return requested if requested in SHELL_COPY else _DEFAULT_LANGUAGE


def _unavailable(environment: Environment, *, language: str) -> Response:
    """The one surface every refusal reaches. Takes no cause, so it can disclose none."""
    body = environment.get_template("unavailable.html.j2").render(
        language=language,
        direction=DIRECTIONS[language],
        copy=SHELL_COPY[language],
        assets=SHELL_ASSETS,
    )
    return Response(
        content=body,
        status_code=404,
        media_type="text/html; charset=utf-8",
        headers=dict(SECURITY_HEADERS),
    )


def add_shell_routes(
    app: FastAPI,
    *,
    services: ShellServices | None,
    clock: Callable[[], Any],
) -> None:
    """Declare the shell surface group, or none at all when it is unwired.

    The null guard is load-bearing in the same way `commercial_api.py`'s is: with no services the
    group is never declared, so a beta-only deployment has no shell surface rather than one that
    exists and refuses.
    """
    if services is None:
        return

    environment = shell_environment()

    @app.get(f"{SHELL_ASSETS}/{{name}}")
    def shell_asset(name: str) -> Response:
        """Serve the shell's own assets from its own allowlist.

        Not the journey's route: `/beta/assets/{name}` is tied to the journey app and does not
        serve this prefix, and `RCA-002` excludes changing the beta surface. The allowlist is a
        `dict` rather than a directory listing so a file dropped into the package is not served by
        arriving, and the name is never joined onto a path from the request.
        """
        media_type = _ASSETS.get(name)
        if media_type is None:
            return _unavailable(environment, language=_DEFAULT_LANGUAGE)
        content = files("khepri.rra.journey").joinpath("assets", name).read_bytes()
        return Response(
            content=content,
            media_type=media_type,
            headers=dict(SECURITY_HEADERS),
        )

    @app.get(f"{SHELL_PREFIX}/{{path:path}}")
    def shell_surface(
        path: str, session: CommercialSessionCookie = None
    ) -> Response:
        """Resolve the actor, then render.

        Until a later slice adds an addressable surface, every resolved request reaches the same
        page as an unresolved one. That is `FR-046` holding by construction rather than by a check:
        an unknown path and a forbidden one are the same response because there is no other
        response to give.
        """
        language = _language(path.split("/")[0] if path else "")
        if session is None:
            return _unavailable(environment, language=language)
        try:
            services.resolver.for_request(session, organization_id=None, now=clock())
        except PermissionError:
            return _unavailable(environment, language=language)
        return _unavailable(environment, language=language)


__all__ = [
    "SHELL_ASSETS",
    "SHELL_PREFIX",
    "ActorResolver",
    "ShellServices",
    "add_shell_routes",
    "shell_environment",
]
