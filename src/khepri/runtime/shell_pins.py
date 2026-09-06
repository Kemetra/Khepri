"""The owner-only routes that pin and unpin a workspace object (`W1-09`; `RCA-005` `FR-128`).

Its own module, as `shell_invitations.py`, `shell_artifact_handoff.py` and `shell_deletion.py`
are: `shell_api.py` dispatches the read surfaces, and mutating routes that grew inside it would
push that module past what CodeScene admits while burying the writes among the reads.

**Addressed by surface, not by kind.** The routes are `/data/{version_id}/pin` and
`/analyses/{run_id}/pin`, following `/data/{version_id}/delete`. A single
`/pins/{object_kind}/{object_id}` route would have put `dataset_version` on the wire as a new
vocabulary, and every existing shell route addresses an object through the surface that lists it.
The kind is implied by the address, exactly as the deletion route implies it.

**Owner-only, through a gate of its own** rather than `shell_invitations.owner_or_none`, for
`shell_deletion.py`'s reason: that one answers `None` when `services.invitations is None`, so a
deployment with pins wired and invitations absent would refuse every pin for a reason that has
nothing to do with pinning. Every cause a caller must not tell apart still answers `None` --
absent cookie, unresolvable session, non-owner, disagreeing organization -- and each renders the
same uniform refusal (`FR-050`).

**No `FR-125` audit event, by requirement.** `FR-128` puts a pin outside the governed workspace
actions: it "emits **no** `FR-125` audit event and adds no member to `AUDIT_ACTIONS`". A pin
changes nothing about the content; it records what one person wants to find again, and an event
for it would put a behavioural trace into the record `KHEPRI-DEC-015` §7 reserves for security and
audit.

**No CSRF token, matching the sibling.** `shell_deletion.py`'s route is protected by the session
cookie, `require_owner`, and the organization-segment comparison below, and carries no token. A
new mechanism introduced here would be one this shell applies to its least consequential write and
not to its most, which is worse than the consistent posture. If the shell gains CSRF tokens, both
routes take them together.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Path, Response
from fastapi.responses import RedirectResponse

from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.rca.workspace.schema import PIN_KIND_RUN, PIN_KIND_VERSION
from khepri.runtime.shell_invitations import ShellRendering


@dataclass(frozen=True, slots=True)
class PinRoute:
    """One pin route's identity: which surface, which path segment, which kind, and which verb.

    Grouped rather than passed flat because seven parameters trips CodeScene's Excess Number of
    Function Arguments -- the same gate `DeletionSources` answers in `workspace_deletion.py` and
    `Acting` answers in the `W1-07a` tests. The grouping is not only for the gate: these four
    travel together and describe one thing, so a caller cannot supply three of them.

    `surface` is both the address segment and the redirect destination, which is what makes each
    route's object kind implicit in its address rather than carried on the wire.
    """

    surface: str
    parameter: str
    kind: str
    pinning: bool

    @property
    def verb(self) -> str:
        return "pin" if self.pinning else "unpin"

    def address(self, prefix: str) -> str:
        scoped = f"{prefix}/{{language}}/{{organization}}"
        return f"{scoped}/{self.surface}/{{{self.parameter}}}/{self.verb}"


#: The four routes this module declares, as data.
PIN_ROUTES = (
    PinRoute(surface="data", parameter="version_id", kind=PIN_KIND_VERSION, pinning=True),
    PinRoute(surface="data", parameter="version_id", kind=PIN_KIND_VERSION, pinning=False),
    PinRoute(surface="analyses", parameter="run_id", kind=PIN_KIND_RUN, pinning=True),
    PinRoute(surface="analyses", parameter="run_id", kind=PIN_KIND_RUN, pinning=False),
)


def offers_pins(services: Any) -> bool:
    """Whether this deployment wired the pin store.

    A shell without it does not declare the routes at all, so the address is unknown rather than
    refused differently (`FR-046`) -- the posture every optional shell capability takes.
    """
    return getattr(services, "pins", None) is not None


def _owner_or_none(
    services: Any, session: str | None, clock: Callable[[], datetime], *, organization_id: str
) -> Any:
    """The owner gate these routes need, and nothing beyond it."""
    if session is None:
        return None
    try:
        return services.resolver.require_owner(
            session, organization_id=organization_id, now=clock()
        )
    except PermissionError:
        return None


def _scope_or_none(
    services: Any,
    session: str | None,
    clock: Callable[[], datetime],
    *,
    organization: str,
) -> tuple[Any, str] | None:
    """The resolved context and its opaque scope, or `None` for every refusable cause.

    The organization segment is **compared** rather than trusted (`FR-042`). `require_owner`
    resolves the actor's role in the organization it is given, so a correct resolver has already
    refused a mismatch -- but review on `#373` found that segment ignored on a read surface, which
    rendered one organization's records under another's address. These routes write, so they do
    not get to assume every resolver they are composed with enforces the comparison.
    """
    context = _owner_or_none(services, session, clock, organization_id=organization)
    if context is None or context.organization_id is None:
        return None
    if context.organization_id != organization:
        return None
    return context, services.isolation.resolve_scope(context.account_id, context.organization_id)


def add_pin_routes(
    app: FastAPI,
    *,
    services: Any,
    rendering: ShellRendering,
    clock: Callable[[], datetime],
) -> None:
    """Declare the four pin routes, where this deployment offers pins."""
    if not offers_pins(services):
        return

    environment = rendering.environment
    language_of = rendering.language_of
    unavailable = rendering.unavailable

    def _act(
        language: str,
        organization: str,
        session: str | None,
        *,
        object_id: str,
        object_kind: str,
        pinning: bool,
        destination: str,
    ) -> Response:
        """One body for all four routes: resolve, refuse uniformly, act, redirect.

        A pin on an object this scope does not hold is accepted and lists nothing afterwards --
        the same outcome a genuine repeat gets -- so the route cannot be used to learn whether
        another organization's identifier exists. `pins_for_scope` reads by scope, so a pin whose
        object is not in that scope can never be rendered.
        """
        rendered = language_of(language)
        resolved = _scope_or_none(services, session, clock, organization=organization)
        if resolved is None:
            return unavailable(environment, language=rendered)
        context, owner_id = resolved
        if pinning:
            services.pins.pin(object_id, object_kind, owner_id=owner_id, now=clock())
        else:
            services.pins.unpin(object_id, owner_id=owner_id)
        # A `303` rather than a rendered page, for the deletion route's reason: this slice's
        # surfaces are rendered by the Overview and Data routes, and a POST result that
        # re-rendered on refresh would repeat the request. Both verbs are idempotent, so the
        # repeat is harmless -- the redirect is what makes that irrelevant rather than merely
        # survivable.
        return RedirectResponse(
            url=f"{rendering.prefix}/{rendered}/{context.organization_id}/{destination}",
            status_code=303,
        )

    # Declared by one loop over `PIN_ROUTES`. Written out as four decorated functions first,
    # which CodeScene refused at 111 lines against a threshold of 70 -- and the refusal was right:
    # the bodies differed only in which identifier they read and which surface they return to, so
    # four of them were four places for those two facts to drift apart.
    for route in PIN_ROUTES:
        _declare(app, route, rendering.prefix, _act)


def _declare(app: FastAPI, route: PinRoute, prefix: str, act: Any) -> None:
    """Declare one pin route, reading its object identifier from the segment `route` names.

    The handler is given an explicit signature rather than `**path`, because FastAPI binds path
    segments by inspecting parameter *names* and a `**kwargs` handler exposes none for it to bind
    -- the first attempt here declared the routes and then raised on every request. The identifier
    parameter is named `object_id` in the signature and mapped from the surface's own segment name
    (`version_id`, `run_id`) by an alias, so one function serves both surfaces without either
    accepting a segment it does not have.
    """

    @app.post(route.address(prefix), name=f"{route.surface}_{route.verb}")
    def handler(
        language: str,
        organization: str,
        object_id: str = Path(alias=route.parameter),
        session: CommercialSessionCookie = None,
    ) -> Response:
        return act(
            language,
            organization,
            session,
            object_id=object_id,
            object_kind=route.kind,
            pinning=route.pinning,
            destination=route.surface,
        )


__all__ = ["add_pin_routes", "offers_pins"]
