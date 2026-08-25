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
from khepri.runtime.shell_invitations import ShellRendering, add_invitation_routes
from khepri.runtime.shell_journey_entry import add_journey_entry_route

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
_ASSETS = {
    "shell.css": "text/css; charset=utf-8",
    "shell-components.css": "text/css; charset=utf-8",
}


class ActorResolver(Protocol):
    """The canonical checkpoint, as `commercial_api.py` already consumes it.

    Declared structurally so this module depends on the shape it calls rather than on an `RCA`
    class. That is not a second resolution path: there is one implementation, it is the merged
    resolver, and `FR-041`'s prohibition is on resolving *elsewhere*, not on naming the call.
    """

    def for_request(
        self, token: str, *, organization_id: str | None, now: Any
    ) -> Any: ...  # pragma: no cover -- Protocol

    def require_owner(
        self, token: str, *, organization_id: str, now: Any
    ) -> Any: ...  # pragma: no cover -- Protocol


class OrganizationReader(Protocol):
    """Reads the organizations one account currently belongs to (`R8-04`).

    Narrower than `OrganizationStore` deliberately: the shell renders a switcher and must not be
    handed the verbs that create organizations, promote, revoke, or demote. A reader that could
    write would make "the shell changes no membership semantics" a convention rather than a fact.
    """

    def organizations_for_account(
        self, account_id: str
    ) -> list[Any]: ...  # pragma: no cover -- Protocol

    def memberships_for_organization(
        self, organization_id: str
    ) -> list[Any]: ...  # pragma: no cover -- Protocol


class InvitationGateway(Protocol):
    """Listing, issuing, and revoking invitations (`R8-05b`).

    The write verbs appear here and the membership verbs do not, and that asymmetry is the point:
    the shell may invite and un-invite, and may not promote, demote, or revoke a membership. A
    gateway carrying those would make "the shell changes no membership semantics" a convention
    rather than something the type forbids.
    """

    def invitations_for_organization(
        self, organization_id: str, *, now: Any
    ) -> Any: ...  # pragma: no cover -- Protocol

    def issue(
        self, offer: Any, *, expires_at: Any, now: Any
    ) -> str: ...  # pragma: no cover -- Protocol

    def revoke(
        self,
        organization_id: str,
        invitation_id: str,
        *,
        actor_account_id: str,
        now: Any,
    ) -> None: ...  # pragma: no cover -- Protocol


class AnalysisOpener(Protocol):
    """Opens one analysis in an already-resolved scope (`R8-06`).

    `CommercialBridge.open` is the implementation. Narrower than the bridge itself: the shell
    starts analyses and does not resume them, because resuming is reached by returning to the
    journey rather than by a shell surface.
    """

    def open(
        self, *, account_id: str, organization_id: str, now: Any
    ) -> Any: ...  # pragma: no cover -- Protocol


@dataclass(frozen=True, slots=True)
class ShellServices:
    """What the shell needs to render an authenticated frame, and nothing more."""

    resolver: ActorResolver
    organizations: OrganizationReader
    invitations: InvitationGateway | None = None
    bridge: AnalysisOpener | None = None


def shell_environment() -> Environment:
    """`StrictUndefined`, so a missing copy key fails the render rather than rendering a blank."""
    return Environment(
        loader=PackageLoader("khepri.runtime", "shell_templates"),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
    )


#: The language the frame's control switches to, derived from `SHELL_COPY` rather than written out,
#: so adding a third language is a copy change and not also a mapping this module forgot to extend.
#: With exactly two, "the other one" is well defined; a third makes this a list and the control a
#: different component, which is the point at which it should stop being a toggle.
_ALTERNATE = {
    language: next(other for other in SHELL_COPY if other != language) for language in SHELL_COPY
}


def _active_organization_name(organizations: list[Any], organization_id: str) -> str:
    """The display name of the session's active organization, from the list already read.

    Matched on the session's organization, never on the address, which `FR-042` gives no authority.
    An organization the reader holds no membership in is not in this list and so cannot be named,
    which is `FR-051` holding for the same reason the switcher's enumeration does.

    Falls back to the empty string rather than raising. The name is frame decoration: a listing
    whose shape does not carry one should render a frame without it, not turn the team surface into
    a 500. `StrictUndefined` still catches a template referencing a name nobody passed.
    """
    for organization in organizations:
        if getattr(organization, "organization_id", None) == organization_id:
            return str(getattr(organization, "name", ""))
    return ""


def _language(requested: str) -> str:
    """An unknown language code renders in English rather than failing.

    A language that is not offered is not a refusal, and treating it as one would give
    `FR-050`'s uniform surface a sixth cause that is not a denial at all.
    """
    return requested if requested in SHELL_COPY else _DEFAULT_LANGUAGE


def _unavailable(environment: Environment, *, language: str) -> Response:
    """The one surface every refusal reaches. Takes no cause, so it can disclose none."""
    return _render(environment, "unavailable.html.j2", language=language, status_code=404)


def _render(
    environment: Environment,
    template: str,
    *,
    language: str,
    status_code: int,
    **context: Any,
) -> Response:
    """One render path, so no surface can be added that forgets the headers.

    `FR-043` requires every shell response to attach them explicitly, and nothing global will.
    Funnelling every surface through here makes that structural rather than a rule each new
    handler must remember.
    """
    body = environment.get_template(template).render(
        language=language,
        direction=DIRECTIONS[language],
        copy=SHELL_COPY[language],
        assets=SHELL_ASSETS,
        prefix=SHELL_PREFIX,
        # The frame's language control needs the other language. `FR-047` makes the language a
        # property of the address, so switching rewrites one segment and keeps the rest; the
        # alternate is derived here so no surface can forget it and no template has to know how
        # many languages there are. `surface_path` defaults to the organization chooser's empty
        # tail and each surface that has a deeper address overrides it through `context`.
        **{"alternate": _ALTERNATE[language], "surface_path": "", **context},
    )
    return Response(
        content=body,
        status_code=status_code,
        media_type="text/html; charset=utf-8",
        headers=dict(SECURITY_HEADERS),
    )


def _no_membership(environment: Environment, *, language: str) -> Response:
    """`FR-048`: the one edge state that is not collapsed into `unavailable`.

    It is separated because it is different in kind, not in degree: an authenticated account in no
    organization is not being refused anything, and `FR-028` requires the state to be reachable.
    A `200` rather than a `404` for the same reason -- nothing is missing.
    """
    return _render(
        environment, "no_membership.html.j2", language=language, status_code=200
    )


def _switcher(
    environment: Environment,
    *,
    language: str,
    organizations: list[Any],
    active_organization_id: str | None,
) -> Response:
    """`FR-051`: only what the reader returned, which is only current memberships.

    Takes the active organization because the analysis action is only offered where it can
    succeed. `for_request` refuses any organization that is not this session's active one --
    `FR-027` allows exactly one, and honoring a named one would make the active organization
    advisory -- so an action on any other row would post a value the resolver rejects and land the
    reader on the uniform unavailable surface. A dead end reads as a fault; the row keeps its link
    instead, which is the control that does switch.
    """
    return _render(
        environment,
        "switcher.html.j2",
        language=language,
        status_code=200,
        organizations=organizations,
        active_organization_id=active_organization_id,
        # The chooser is where the frame's organization control leads, so the control is not
        # rendered here: a link to the surface you are on is a control that does nothing.
    )


def _team_response(
    services: ShellServices,
    environment: Environment,
    *,
    language: str,
    context: Any,
) -> Response:
    """The team surface, rendered from the session's organization.

    Resolves the organization's display name for the frame itself rather than taking it as an
    argument. This function has two callers -- the dispatcher, and the invitation routes through
    `ShellRendering.team` after an issue or a revoke -- and only one of them holds the organization
    list. A required parameter would have made the frame's name the caller's problem and left the
    revoke path rendering a team surface whose frame was missing an element it had a moment before.
    """
    members = services.organizations.memberships_for_organization(context.organization_id)
    organization_name = _active_organization_name(
        services.organizations.organizations_for_account(context.account_id),
        context.organization_id,
    )
    invitations: tuple[Any, ...] = ()
    if services.invitations is not None:
        invitations = tuple(
            services.invitations.invitations_for_organization(
                context.organization_id, now=None
            )
        )
    return _render(
        environment,
        "team.html.j2",
        language=language,
        status_code=200,
        members=members,
        invitations=invitations,
        is_owner=getattr(context, "is_owner", False),
        organization_id=context.organization_id,
        organization_name=organization_name,
        # The tail the language control returns to, so switching language keeps the surface rather
        # than dropping the reader on the chooser (`FR-054` scenario 11).
        surface_path=f"/{context.organization_id}/team",
        # The invitation gateway is optional, and a shell wired without one still renders this
        # surface. An owner would otherwise see an enabled creation form whose every submission
        # `owner_or_none` refuses, which reaches them as the uniform unavailable surface -- a
        # control that looks available and answers like a fault.
        invitations_available=services.invitations is not None,
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

    rendering = ShellRendering(
        environment=environment,
        prefix=SHELL_PREFIX,
        language_of=_language,
        unavailable=_unavailable,
        render=_render,
        team=_team_response,
    )
    add_invitation_routes(app, services=services, rendering=rendering, clock=clock)
    add_journey_entry_route(app, services=services, rendering=rendering, clock=clock)

    @app.get(f"{SHELL_PREFIX}/{{path:path}}")
    def shell_surface(
        path: str, session: CommercialSessionCookie = None
    ) -> Response:
        """Resolve the actor, then dispatch on the surface the address names.

        **The address supplies the surface name and the language, never the scope.** `FR-042`
        gives the session's active organization that job, so the organization segment of the path
        is not read at all -- there is no parameter on which the comparison could be skipped
        because nothing here consults one.

        A surface this slice does not deliver falls through to `unavailable`, which is `FR-046`
        holding by construction: an unknown surface and a forbidden one are the same response
        because there is no other response to give.
        """
        segments = path.split("/")
        language = _language(segments[0] if segments else "")
        if session is None:
            return _unavailable(environment, language=language)
        try:
            context = services.resolver.for_request(session, organization_id=None, now=clock())
        except PermissionError:
            return _unavailable(environment, language=language)

        organizations = services.organizations.organizations_for_account(context.account_id)
        if not organizations:
            return _no_membership(environment, language=language)

        surface = segments[2] if len(segments) > 2 else ""
        if surface == "team" and context.organization_id is not None:
            return _team_response(
                services, environment, language=language, context=context
            )
        if surface == "":
            return _switcher(
                environment,
                language=language,
                organizations=organizations,
                active_organization_id=context.organization_id,
            )
        return _unavailable(environment, language=language)


__all__ = [
    "SHELL_ASSETS",
    "SHELL_PREFIX",
    "ActorResolver",
    "ShellServices",
    "add_shell_routes",
    "shell_environment",
]
