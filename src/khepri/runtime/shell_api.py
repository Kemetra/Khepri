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
from datetime import timedelta
from importlib.resources import files
from typing import Any, Protocol
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, Response
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from khepri.rca.invitations import InvitationOffer
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

#: How long an issued invitation stays redeemable.
#:
#: `InvitationService.issue` takes `expires_at` with no default, deliberately: `FR-016` requires an
#: explicit expiry and fixes no lifetime, so a constant in the domain would put a product decision
#: there. The shell supplies one, and seven days is chosen to match the seven-day object expiry and
#: backup retention `KHEPRI-DEC-008` fixes -- its rule that "no retention horizon is quietly longer
#: than another" applies to an invitation as much as to content.
INVITATION_LIFETIME = timedelta(days=7)

#: The roles a request may name. `FR-015` fixes exactly two, and an unknown value is refused rather
#: than passed to the domain to reject: a role reaching `Invitation.create` from a form is
#: caller-supplied input, and the allowlist is where it stops.
_ROLES = ("owner", "member")

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


@dataclass(frozen=True, slots=True)
class ShellServices:
    """What the shell needs to render an authenticated frame, and nothing more."""

    resolver: ActorResolver
    organizations: OrganizationReader
    invitations: InvitationGateway | None = None


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
        **context,
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
    environment: Environment, *, language: str, organizations: list[Any]
) -> Response:
    """`FR-051`: only what the reader returned, which is only current memberships."""
    return _render(
        environment,
        "switcher.html.j2",
        language=language,
        status_code=200,
        organizations=organizations,
    )


def _form(body: bytes) -> dict[str, str]:
    """Parse a URL-encoded form body with the standard library.

    **No `python-multipart`, and that is a dependency decision rather than a style one.** FastAPI's
    `Form()` requires it, and the shell posts plain `application/x-www-form-urlencoded` bodies
    because the content security policy admits no inline script to build anything else. Adding a
    runtime dependency to the deployed wheel to parse two fields is a supply-chain surface the
    guardrails' "no external runtime assets" rule exists to avoid.

    Last value wins on a repeated key, matching form semantics; a missing key is absent rather than
    empty, so the caller's `not email` check still distinguishes them.
    """
    parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items() if values}


def _owner_or_none(
    services: ShellServices,
    session: str | None,
    clock: Callable[[], Any],
    *,
    organization_id: str,
) -> Any:
    """The owner gate, or `None` for every reason a caller must not tell apart.

    Absent cookie, unresolvable session, non-owner, and an unwired invitation gateway all return
    `None`, and every caller renders the same `unavailable`. Returning a context rather than a
    boolean follows `require_owner`'s own reasoning: a caller cannot ask the question and ignore
    the answer.

    **`organization_id` is passed in, and its only permitted source is the session.**
    `require_owner` requires a target organization where `for_request` does not, and that asymmetry
    exists because a gate defaulting to the session's active organization would authorize against A
    while the caller mutated B. Handlers here read it from the resolved context, never from the
    path.
    """
    if session is None or services.invitations is None:
        return None
    try:
        return services.resolver.require_owner(
            session, organization_id=organization_id, now=clock()
        )
    except PermissionError:
        return None


def _team_response(
    services: ShellServices,
    environment: Environment,
    *,
    language: str,
    context: Any,
) -> Response:
    """The team surface, rendered from the session's organization."""
    members = services.organizations.memberships_for_organization(context.organization_id)
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

    @app.post(f"{SHELL_PREFIX}/{{language}}/{{organization}}/team/invitations")
    async def issue_invitation(
        request: Request,
        language: str,
        organization: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """Invite one person, as an owner of the session's active organization.

        **`require_owner`, never `for_request`.** `InvitationService.issue` takes
        `actor_account_id` for attribution and checks no authority of its own, so this gate is the
        only thing between a member and the ability to invite. `R6-04` placed the check here
        deliberately; a route reaching for the weaker gate would not fail any test the service owns.

        **The organization named in the path is passed to the gate, not trusted.** `require_owner`
        requires a target precisely so the caller must name it, and it resolves the actor's live
        role in *that* organization before permitting anything -- so a path naming an organization
        the actor does not own is refused there. This is `FR-024`'s comparison happening at the
        gate rather than in the handler, which is what "the organization that was authorized is
        the one in the caller's hand" means.
        """
        rendered = _language(language)
        context = _owner_or_none(
            services, session, clock, organization_id=organization
        )
        if context is None or context.organization_id is None:
            return _unavailable(environment, language=rendered)
        submitted = _form(await request.body())
        email = submitted.get("email", "")
        role = submitted.get("role", "")
        if role not in _ROLES or not email:
            return _unavailable(environment, language=rendered)

        offer = InvitationOffer(
            organization_id=context.organization_id,
            intended_role=role,
            target_identity=email,
            issued_by=context.account_id,
        )
        now = clock()
        token = services.invitations.issue(
            offer, expires_at=now + INVITATION_LIFETIME, now=now
        )
        return _render(
            environment,
            "invitation_issued.html.j2",
            language=rendered,
            status_code=200,
            token=token,
            email=email,
        )

    @app.post(
        f"{SHELL_PREFIX}/{{language}}/{{organization}}/team/invitations/{{invitation}}/revoke"
    )
    def revoke_invitation(
        language: str,
        organization: str,
        invitation: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """Withdraw one open invitation in the session's active organization.

        The service refuses four causes identically -- absent, revoked, redeemed, expired, or
        another organization's -- so this handler adds no check that could distinguish them.
        """
        rendered = _language(language)
        context = _owner_or_none(
            services, session, clock, organization_id=organization
        )
        if context is None or context.organization_id is None:
            return _unavailable(environment, language=rendered)
        try:
            services.invitations.revoke(
                context.organization_id,
                invitation,
                actor_account_id=context.account_id,
                now=clock(),
            )
        except Exception:  # noqa: BLE001 -- one refusal for every cause, per `FR-025`
            return _unavailable(environment, language=rendered)
        return _team_response(services, environment, language=rendered, context=context)

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
            return _switcher(environment, language=language, organizations=organizations)
        return _unavailable(environment, language=language)


__all__ = [
    "SHELL_ASSETS",
    "SHELL_PREFIX",
    "ActorResolver",
    "ShellServices",
    "add_shell_routes",
    "shell_environment",
]
