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

**No route ships here, deliberately.** A decision route needs the session and
membership resolution `shell_comparison.py` reaches through `_RouteCall`, and
driving it needs the `W1-04b` journey harness. `D1-04` ships it, with the
breakdowns and the limits surface it should render beside -- and with a test
that drives it. An HTTP surface no test drives would be worse than a deferred
one, and the surface is unreachable in a deployment regardless until the
`wiring.py` question this slice raised is answered. `offers_decisions` is the
`FR-046` predicate that route will need and is asserted now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from jinja2 import Environment

from khepri.rca.workspace.decision.card import CardsReading
from khepri.rra.rendering.wording import metric_business_name
from khepri.runtime.shell_copy import DIRECTIONS, SHELL_COPY

__all__ = [
    "COMPARISON_UNREACHABLE",
    "DECISION_COPY",
    "DecisionFrame",
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
    },
    "ar": {
        "title": "القرارات",
        "lede": "أرقام محوكمة لتحليل مكتمل واحد.",
        "unavailable": "جزء من هذا العرض غير متاح.",
        "no_rows": "لم ينشر هذا التحليل أي أرقام.",
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
    caveats: tuple[object, ...]


@dataclass(frozen=True, slots=True)
class _DecisionView:
    """One rendered decision surface.

    `refusal` is the governed message or `None`; it is never the bare cause
    code, which is what `FR-164` forbids a surface from showing.
    """

    cards: tuple[_CardView, ...] = field(default_factory=tuple)
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
        caveats=card.caveats,
    )


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
    """

    language: str
    organization_id: str
    prefix: str


def render_decisions(
    environment: Environment, reading: CardsReading, frame: DecisionFrame
) -> str:
    """The decision surface's body, under `RCA-002`'s frame."""
    return environment.get_template("decision.html.j2").render(
        language=frame.language,
        direction=DIRECTIONS[frame.language],
        copy=SHELL_COPY[frame.language],
        decision=DECISION_COPY[frame.language],
        assets=f"{frame.prefix}/assets",
        prefix=frame.prefix,
        alternate="ar" if frame.language == "en" else "en",
        surface_path=f"/{frame.organization_id}/decisions",
        language_switch=True,
        organization_id=frame.organization_id,
        organization_name=None,
        tail=None,
        # The frame's destination list. Empty here because this render path has
        # no organization frame to read; the route slice passes the real one.
        destinations=(),
        view=decision_view(reading, language=frame.language),
    )
