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
from khepri.runtime.shell_frame import organization_frame
from khepri.runtime.shell_invitations import ShellRendering, add_invitation_routes
from khepri.runtime.shell_journey_entry import add_journey_entry_route
from khepri.runtime.shell_workspace import data_rows, overview_view

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


class WorkspaceReader(Protocol):
    """Reads one scope's data versions and analysis runs (`W1-05`).

    `SqlWorkspaceRecordStore` is the implementation; this names the two reads Overview and Data
    make and none of the writes. The shell presents retained rows and creates, completes and
    deletes nothing, and a reader that could write would make that a convention.
    """

    def dataset_versions_for_scope(
        self, owner_id: str
    ) -> tuple[Any, ...]: ...  # pragma: no cover -- Protocol

    def analysis_runs_for_scope(
        self, owner_id: str
    ) -> tuple[Any, ...]: ...  # pragma: no cover -- Protocol


class ScopeResolver(Protocol):
    """Resolves an organization to the opaque scope the workspace rows are keyed by (`FR-031`).

    `IsolationService.resolve_scope` is the implementation and the one door: the workspace store
    filters on `owner_id`, which is *not* the commercial `organization_id` the session carries,
    and `WorkspaceActions` writes every row under the scope this same call returns. Review on
    `#373` found the shell passing the organization identifier to the store, so both surfaces
    would have rendered their empty states over a scope full of rows. Reading through the same
    door the writer used is what makes the shell show what the actions recorded.
    """

    def resolve_scope(
        self, account_id: str, organization_id: str
    ) -> str: ...  # pragma: no cover -- Protocol


@dataclass(frozen=True, slots=True)
class ShellServices:
    """What the shell needs to render an authenticated frame, and nothing more.

    `records` and `isolation` are optional the way `invitations` and `bridge` are, and they come
    as a pair: a shell wired without both has no Overview and no Data surface and no link to
    either (`FR-049`), rather than two surfaces that exist and refuse -- or, worse, two surfaces
    that read a scope the session does not own.
    """

    resolver: ActorResolver
    organizations: OrganizationReader
    invitations: InvitationGateway | None = None
    bridge: AnalysisOpener | None = None
    records: WorkspaceReader | None = None
    isolation: ScopeResolver | None = None


def _offers_workspace(services: ShellServices) -> bool:
    """Whether Overview and Data exist on this shell: both halves of the read are wired."""
    return services.records is not None and services.isolation is not None



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


def _language(requested: str) -> str:
    """An unknown language code renders in English rather than failing.

    A language that is not offered is not a refusal, and treating it as one would give
    `FR-050`'s uniform surface a sixth cause that is not a denial at all.
    """
    return requested if requested in SHELL_COPY else _DEFAULT_LANGUAGE


#: The tail the refusal's language control keeps. Three segments, so `shell_surface` reads a
#: surface name that is present and unimplemented and answers `unavailable` -- which is `FR-046`
#: ("an unknown path MUST resolve to the shared unavailable surface") used as written rather than
#: worked around. It is a constant, so it names no organization and no object, and it is identical
#: whichever cause produced the refusal. `test_the_canonical_refusal_tail_reaches_the_refusal`
#: fails the day a surface is implemented under this name, which is what keeps a link that resolves
#: correctly *because* nothing is there from becoming a link that quietly resolves somewhere else.
_UNAVAILABLE_TAIL = "/-/unavailable"


def _unavailable(
    environment: Environment,
    *,
    language: str,
    language_switch: bool = True,
) -> Response:
    """The one surface every refusal reaches. Takes no cause, so it can disclose none.

    **Its language control keeps the refusal, and cannot keep the address.** With no tail it took
    `_render`'s empty default and pointed at `{prefix}/{alternate}` -- the organization chooser,
    answering `200`. That is the "returning them to an entry surface" `FR-055` names outright.

    Echoing the reader's own address would preserve the position exactly, and this surface may not:
    merged cases assert a refusal carries neither the organization it was asked about nor the
    object identifier, with no exception for a value the reader supplied, and an `href` is body.

    So the control keeps the *surface* rather than the address. A reader who reaches a refusal in a
    language they cannot read has one discoverable way into the other -- the recovery exit is in
    the language they cannot read too -- and `FR-054` puts that reader in scope. The constant
    discloses nothing and does not vary with the cause, so `FR-050` and `FR-052` hold by
    construction rather than by care.

    `language_switch=False` is for the one refusal rendered without resolving the actor: an
    unlisted asset name. The tail is a refusal only for a reader the dispatcher would refuse, and
    an authenticated account in no organization is not one -- `FR-048` puts it on the next-step
    surface at `200` before any surface name is read, which is what `FR-048` is for. That reader
    would have followed the control off a `404` and onto a next step. An asset name is not a
    surface a reader is on, so it offers no control, rather than the dispatcher learning an
    exception that would have to outrank `FR-048`.
    """
    return _render(
        environment,
        "unavailable.html.j2",
        language=language,
        status_code=404,
        surface_path=_UNAVAILABLE_TAIL,
        language_switch=language_switch,
    )


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
        #
        # `language_switch` defaults to rendering the control, because every surface with a
        # destination the frame may name can honour it. `invitation_issued` is the one that cannot:
        # no address of its own and one unrepeatable secret. It opts out here rather than in the
        # template, where a surface added later would have had to know to.
        **{
            "alternate": _ALTERNATE[language],
            "surface_path": "",
            "language_switch": True,
            **context,
        },
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
    entry_surface: str,
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
        entry_surface=entry_surface,
        # The chooser is where the frame's organization control leads, so the control is not
        # rendered here: a link to the surface you are on is a control that does nothing.
    )


def _workspace_reads(services: ShellServices, context: Any, *, surface: str) -> dict[str, Any]:
    """What Overview and Data both need: the frame, and the scope's versions and runs.

    `FR-042`: the scope is resolved from `context.organization_id`, which the resolver returned
    from the session; the address's organization segment was never read. The resolution goes
    through `ScopeResolver` -- the same door `WorkspaceActions` writes under -- because the store
    is keyed by the opaque `owner_id` and not by the organization. A refusal there is a
    `PermissionError` and reaches the reader as the one uniform unavailable surface.

    Both surfaces read both tables because Overview shows the latest of each and Data shows
    which runs used which data.
    """
    assert services.records is not None and services.isolation is not None  # dispatched wired
    owner_id = services.isolation.resolve_scope(context.account_id, context.organization_id)
    frame = organization_frame(
        services.organizations.organizations_for_account(context.account_id),
        context.organization_id,
        surface=surface,
        offers_records=True,
    )
    return {
        **frame,
        "organization_id": context.organization_id,
        "versions": services.records.dataset_versions_for_scope(owner_id),
        "runs": services.records.analysis_runs_for_scope(owner_id),
    }


def _overview_response(
    services: ShellServices, environment: Environment, *, language: str, context: Any
) -> Response:
    """`FR-120`. The rows are shaped in `shell_workspace.py`; the template can only iterate."""
    reads = _workspace_reads(services, context, surface="overview")
    view = overview_view(reads.pop("versions"), reads.pop("runs"))
    return _render(
        environment,
        "overview.html.j2",
        language=language,
        status_code=200,
        view=view,
        bridge_available=services.bridge is not None,
        **reads,
    )


def _data_response(
    services: ShellServices, environment: Environment, *, language: str, context: Any
) -> Response:
    """Blueprint §7.2, with `FR-117`'s row vocabulary."""
    reads = _workspace_reads(services, context, surface="data")
    rows = data_rows(reads.pop("versions"), reads.pop("runs"))
    return _render(
        environment, "data.html.j2", language=language, status_code=200, rows=rows, **reads
    )


#: The two surfaces `records` delivers, by the name the address carries, and what renders each.
_WORKSPACE_SURFACES = {"overview": _overview_response, "data": _data_response}


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
    frame = organization_frame(
        services.organizations.organizations_for_account(context.account_id),
        context.organization_id,
        surface="team",
        offers_records=_offers_workspace(services),
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
        # The organization name the frame shows and the tail its language control keeps. Resolved
        # through the shared helper rather than spelled here, so the invitation-issued surface --
        # which this function does not render -- cannot drift out of step with the team surface an
        # owner reaches it from.
        **frame,
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
            # No language control: the one refusal rendered without resolving the actor, so the
            # canonical tail is not a refusal for every reader who could reach it. See
            # `_unavailable`.
            return _unavailable(
                environment, language=_DEFAULT_LANGUAGE, language_switch=False
            )
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
        # `W1-05`. Dispatched only when a reader is wired, so a shell without one has no such
        # surface -- the address falls through to `unavailable` like any other unknown name.
        workspace_ready = _offers_workspace(services) and context.organization_id is not None
        if surface in _WORKSPACE_SURFACES and workspace_ready:
            try:
                return _WORKSPACE_SURFACES[surface](
                    services, environment, language=language, context=context
                )
            except PermissionError:
                # The scope door refused -- a disabled account, a membership gone since the
                # session was resolved. `FR-050`: the same surface as every other refusal.
                return _unavailable(environment, language=language)
        # The chooser answers the language address and nothing else. `surface` is read at index 2,
        # so it is also `""` for `/{language}/{anything}` -- and testing that name alone made an
        # unknown two-segment path render the chooser at `200`, the one answer `FR-046` says an
        # unknown path may not get. What separates them is whether anything past the language
        # carries a name: `/en` and `/en/` are the same address, and `/en/no-such-surface` is not.
        if surface == "" and not any(segment for segment in segments[1:]):
            return _switcher(
                environment,
                language=language,
                organizations=organizations,
                active_organization_id=context.organization_id,
                entry_surface="overview" if _offers_workspace(services) else "team",
            )
        return _unavailable(environment, language=language)


__all__ = [
    "SHELL_ASSETS",
    "SHELL_PREFIX",
    "ActorResolver",
    "ScopeResolver",
    "ShellServices",
    "WorkspaceReader",
    "add_shell_routes",
    "shell_environment",
]
