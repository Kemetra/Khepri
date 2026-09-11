"""The executive decision surface (`D1-03`; active `RCA-008`).

The first surface in `D1-01`'s narrative order: the ten core metrics for one
completed run, each card carrying what says whether its figure may be claimed.

**This module names figures; it never produces them.** Every value, population,
version and caveat arrives already selected in a `CardsReading`, and what
happens here is labelling and layout. `FR-159` admits exactly that split --
"Structure and navigation may come from `RCA-005` records and the `RRA-011`
catalog; figures may not" -- which is why a metric's business name is read from
the governed catalog here rather than carried across the seam: `khepri.rca` may
not import `khepri.rra`, and `landing_api.py` already established that the shell
may, so "a catalog rename reaches this page instead of drifting from it".

**Refusal wording is the projection's own** (`FR-164`): "a refusal is presented
with `RRA-014`'s governed bilingual wording in the page language". That wording
travels on `ViewRefusal.wording`, which is why `D1-02` kept the refusal whole
rather than flattening it to a message. It is deliberately *not* the report
refusal catalog: `refusal_message` serves the `section` and `result` tiers and
knows nothing of a view's causes, so reaching for it here would have meant
either an invented string or a `KeyError` in front of a customer.

**The Period Comparison absence is rendered, not hidden.** `FR-170` requires a
promised surface whose source is unreachable be "held open visibly and asserted
to be unreachable, never rendered as empty or partial". `CardsReading` carries
the flag and this module gives it bilingual words.

**This module does not import `shell_api`**, as `shell_comparison.py` does not:
the shell hands each route module a `ShellRendering` so one definition of the
security headers and the render path serves every surface. That is also why
`render_decisions` takes a `prefix` rather than importing the shell's.

**The route is `D1-04`'s and is here now.** `D1-03` shipped the read model, the
view assembly and the template and deferred the address, because an HTTP surface
no test drives would be worse than a deferred one. `add_decision_routes` is that
address, driven over HTTP by `test_d104_breakdowns_and_limits`.

**The member gate is restated here rather than shared, and that is a boundary
cost rather than an oversight.** `shell_comparison._member_or_none` is the
identical gate. `RCA-008` §Exclusions bars "edits to `RCA-001`, `RCA-002`,
`RCA-005` ... source paths", so this slice may neither lift it into a shared home
-- `shell_invitations.py` is `RCA-002`'s -- nor edit the module that has it; and
importing another specification's private name would bind this surface's
authorization to a symbol `RCA-008` does not govern. The rule it encodes is
`FR-042`'s: the address supplies the surface and the language, the session
supplies the scope, and a disagreement between them fails closed.

**The surface is still not in the frame's navigation.** `organization_frame`'s
destinations are decided in `shell_frame.py`, which is `RCA-002`'s and which
§Exclusions does not admit, so the decision surface is reachable by address and
not by a link until an authority that owns the frame says otherwise. `FR-049`
points the same way meanwhile: a link ships with a complete surface, and `D1`'s
is complete when `D1-06` has finished with it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Response
from jinja2 import Environment

from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.rca.workspace.decision.card import CardsReading, CardsRequest, read_cards
from khepri.rra.rendering.wording import caveat_message, metric_business_name
from khepri.runtime.shell_copy import DIRECTIONS, SHELL_COPY
from khepri.runtime.shell_frame import offers_of, organization_frame
from khepri.runtime.shell_invitations import ShellRendering

__all__ = [
    "COMPARISON_UNREACHABLE",
    "DECISION_COPY",
    "DecisionFrame",
    "add_decision_routes",
    "decision_view",
    "offers_decisions",
    "render_decisions",
]

#: `FR-170`. The Period Comparison source is a two-population bundle and the
#: shipping composition builds one population per run, so the surface is promised
#: and not reachable. Said in both languages because `FR-171` admits no surface
#: that states less in one.
COMPARISON_UNREACHABLE = {
    "en": "Period comparison is not available yet on this workspace.",
    "ar": "مقارنة الفترات غير متاحة بعد في مساحة العمل هذه.",
}

#: This surface's own wording. Kept here rather than in `shell_copy.py` for the
#: reason `landing_copy.py` is separate: one surface's strings, changed with it.
DECISION_COPY = {
    "en": {
        "title": "Decisions",
        "lede": "Governed figures for one completed analysis.",
        "unavailable": "Part of this view is unavailable.",
        "no_rows": "This analysis published no figures.",
        "caveats_label": "Caveats",
    },
    "ar": {
        "title": "القرارات",
        "lede": "أرقام محوكمة لتحليل مكتمل واحد.",
        "unavailable": "جزء من هذا العرض غير متاح.",
        "no_rows": "لم ينشر هذا التحليل أي أرقام.",
        "caveats_label": "تحفظات",
    },
}

def offers_decisions(services: Any) -> bool:
    """Whether this deployment wired the decision read.

    `FR-046`'s shape, as `offers_comparisons` and `offers_pins` have it: a shell
    without the collaborator declares no route at all, so the address is unknown
    rather than a surface that exists and refuses.
    """
    return getattr(services, "decisions", None) is not None


@dataclass(frozen=True, slots=True)
class _CardView:
    """One card as the template reads it: named, and qualified in the same row."""

    metric: str
    label: str
    value: object
    population: object
    status: str
    availability: object | None
    reason: object | None


@dataclass(frozen=True, slots=True)
class _DecisionView:
    """One rendered decision surface.

    `refusal` is the governed message or `None`; it is never the bare cause
    code, which is what `FR-164` forbids a surface from showing.
    """

    cards: tuple[_CardView, ...] = field(default_factory=tuple)
    #: The projection's caveats as governed prose, rendered once.
    #:
    #: Once and not per card, because that is what they are: a `StatedCaveat`
    #: names a *section*, never a metric, so attaching one to an individual
    #: figure would assert an attribution the data does not carry. They qualify
    #: the reading, every card's status already says `caveated`, and `FR-161` is
    #: satisfied by their being on the surface that carries the figures.
    caveats: tuple[str, ...] = field(default_factory=tuple)
    refusal: str | None = None
    unavailable: bool = False
    empty: bool = False
    comparison_unreachable: str | None = None


def _named(card: Any, language: str) -> _CardView:
    """One card, labelled from the governed catalog in the page language."""
    return _CardView(
        metric=card.metric,
        label=metric_business_name(card.metric, language),
        value=card.value,
        population=card.population,
        status=card.status,
        availability=card.availability,
        reason=card.reason,
    )


def _caveat_prose(reading: CardsReading, language: str) -> tuple[str, ...]:
    """The reading's caveats as governed prose, in the page language.

    `caveat_message` and not the code: `FR-164`'s discipline for refusals is the
    same one a caveat needs, and a code in front of a customer qualifies
    nothing. Read from each card because every card carries the projection's
    caveat tuple; the first is representative and the set is the projection's.
    """
    codes = reading.cards[0].caveats if reading.cards else ()
    return tuple(caveat_message(getattr(code, "code", code), language) for code in codes)


def _refusal_text(reading: CardsReading, language: str) -> str | None:
    """`RRA-014`'s own wording for this refusal, or `None` when there was none.

    `.get` rather than `[...]`: a refusal that reached here without wording is a
    contract failure upstream, and `FR-164` would rather this surface show
    nothing than show a cause code to a customer.
    """
    if reading.refusal is None:
        return None
    return reading.refusal.wording.get(language)


def decision_view(reading: CardsReading, *, language: str) -> _DecisionView:
    """The reading as one page in one language. Labels and words, no figures."""
    return _DecisionView(
        cards=tuple(_named(card, language) for card in reading.cards),
        caveats=_caveat_prose(reading, language),
        refusal=_refusal_text(reading, language),
        unavailable=reading.status == "unavailable",
        empty=reading.empty_rule is not None,
        comparison_unreachable=(
            COMPARISON_UNREACHABLE[language] if reading.comparison_unreachable else None
        ),
    )


@dataclass(frozen=True, slots=True)
class DecisionFrame:
    """Where one render is addressed: page language, organization, shell prefix.

    Grouped rather than passed flat, for the reason `ShellRendering`'s own
    docstring gives: spelling those out cost this module the identical CodeScene
    finding at the identical score -- Excess Number of Function Arguments, 9.69.
    They travel together on every call and have no meaning apart.

    `prefix` is carried and not imported: this module may not import
    `shell_api`, which is where the shell's one prefix lives.

    `source_id` is empty on this path and named on the route's, because this
    path renders no frame: with no destinations to mark current and no language
    control to keep a tail for, there is no run for the address to name.
    """

    language: str
    organization_id: str
    prefix: str
    source_id: str = ""


def decision_context(reading: CardsReading, language: str) -> dict[str, Any]:
    """The two keys this surface adds to `RCA-002`'s frame, in one place.

    Both render paths use it -- the frameless one below and the route's, which
    hands the rest to `ShellRendering.render` so the security headers keep one
    definition. Two places assembling a template context is how a key goes
    missing from one of them.
    """
    return {
        "decision": DECISION_COPY[language],
        "view": decision_view(reading, language=language),
    }


def render_decisions(
    environment: Environment, reading: CardsReading, frame: DecisionFrame
) -> str:
    """The decision surface's body, without the shell's frame around it.

    The route below renders through `ShellRendering`; this path exists so the
    template can be driven directly, which `FR-170` needs -- a template nothing
    renders cannot show that the Period Comparison surface is held open.
    """
    return environment.get_template("decision.html.j2").render(
        language=frame.language,
        direction=DIRECTIONS[frame.language],
        copy=SHELL_COPY[frame.language],
        assets=f"{frame.prefix}/assets",
        prefix=frame.prefix,
        alternate="ar" if frame.language == "en" else "en",
        surface_path=decision_tail(frame.organization_id, frame.source_id),
        language_switch=True,
        organization_id=frame.organization_id,
        organization_name=None,
        # The frame's destination list. Empty here because this render path has
        # no organization frame to read; the route passes the real one.
        destinations=(),
        **decision_context(reading, frame.language),
    )


def decision_tail(organization_id: str, source_id: str) -> str:
    """This surface's address below the language segment.

    The run is a path segment rather than a query parameter because `FR-166`
    makes the period a **source selector** -- choosing a completed run -- and not
    a view filter. `/analyses/{run_id}` already spells a chosen run this way.
    """
    return f"/{organization_id}/decisions/{source_id}"


@dataclass(frozen=True, slots=True)
class _RouteCall:
    """One request to this surface, grouped rather than passed as seven arguments.

    `ShellRendering`'s own reason: spelling them flat is the Excess Number of
    Function Arguments finding this programme has now paid three times.
    """

    services: Any
    rendering: ShellRendering
    clock: Callable[[], datetime]
    language: str
    organization: str
    session: str | None
    source_id: str


def add_decision_routes(
    app: FastAPI,
    *,
    services: Any,
    rendering: ShellRendering,
    clock: Callable[[], datetime],
) -> None:
    """Declare the decision route where this deployment offers it (`FR-046`)."""
    if not offers_decisions(services):
        return
    path = f"{rendering.prefix}/{{language}}/{{organization}}/decisions/{{source}}"

    @app.get(path)
    def decisions_get(
        language: str,
        organization: str,
        source: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """One completed run's decision surface, in the language the address names."""
        return _respond(
            _RouteCall(
                services, rendering, clock, language, organization, session, source
            )
        )


def _member_or_none(call: _RouteCall) -> Any:
    """The member gate, or `None` for every reason a reader must not tell apart.

    `FR-042`: the address names the surface and the language, never the scope, so
    the organization segment is *compared* with the session's active one and a
    disagreement fails closed. Absent cookie, unresolvable session, no active
    organization and a disagreeing one all return `None`, and the caller renders
    the one uniform surface `FR-050` requires.

    Restated rather than shared -- see this module's docstring for why the
    identical gate in `shell_comparison.py` cannot be reached for here.
    """
    if call.session is None:
        return None
    try:
        context = call.services.resolver.for_request(
            call.session, organization_id=None, now=call.clock()
        )
    except PermissionError:
        return None
    if context.organization_id is None:
        return None
    if context.organization_id != call.organization:
        return None
    return context


def _respond(call: _RouteCall) -> Response:
    """Resolve the member, read the cards, render. Nothing else happens here."""
    language = call.rendering.language_of(call.language)
    context = _member_or_none(call)
    if context is None:
        return call.rendering.unavailable(call.rendering.environment, language=language)
    reading = read_cards(
        call.services.decisions,
        CardsRequest(
            organization_id=context.organization_id,
            account_id=context.account_id,
            source_id=call.source_id,
        ),
    )
    return _page(call, context, language, reading)


def _page(
    call: _RouteCall, context: Any, language: str, reading: CardsReading
) -> Response:
    """The surface inside `RCA-002`'s organization frame.

    `organization_frame` is *called* and not edited: `RCA-008` §Exclusions bars
    changing `shell_frame.py`, which is also why `surface="decisions"` adds no
    navigation entry -- the destinations that module decides are unchanged by
    this surface existing.
    """
    rendering = call.rendering
    frame = organization_frame(
        call.services.organizations.organizations_for_account(context.account_id),
        context.organization_id,
        surface="decisions",
        offers=offers_of(call.services),
    )
    return rendering.render(
        rendering.environment,
        "decision.html.j2",
        language=language,
        status_code=200,
        organization_id=context.organization_id,
        **{
            **frame,
            "surface_path": decision_tail(context.organization_id, call.source_id),
            **decision_context(reading, language),
        },
    )
