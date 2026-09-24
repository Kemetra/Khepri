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

from fastapi import FastAPI, Request, Response
from jinja2 import Environment

from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.rca.workspace.decision.breakdowns import (
    BasketSurface,
    BreakdownReading,
    BreakdownRequest,
    read_basket,
    read_branches,
    read_concentration,
    read_products,
)
from khepri.rca.workspace.decision.card import CardsReading, CardsRequest, read_cards
from khepri.rca.workspace.decision.controls import (
    ControlSelection,
    SourceOption,
    routed_to,
    selection_from,
    unroutable,
)
from khepri.rca.workspace.decision.evidence import (
    EvidenceAction,
    EvidenceEntry,
    EvidenceReading,
)
from khepri.rca.workspace.decision.seam import (
    BASKET,
    BRANCH_PERFORMANCE,
    CONCENTRATION,
    EMPTY_STATED_ABSENCE,
    EMPTY_STATED_NO_ROWS,
    PRODUCT_CATEGORY,
    ViewIdentity,
)
from khepri.rra import definitions
from khepri.rra.facts import UNIT_COUNT, UNIT_MONETARY, UNIT_RATIO
from khepri.rra.rendering.wording import (
    CAVEAT_WORDING,
    business_metric_name,
    caveat_message,
    metric_business_name,
)
from khepri.runtime.shell_controls import (
    CONTROL_COPY,
    controls_view,
    inbound_parameters,
    partition_print,
    selection_query,
    source_options,
)
from khepri.runtime.shell_copy import DIRECTIONS, SHELL_COPY
from khepri.runtime.shell_frame import offers_of, organization_frame
from khepri.runtime.shell_invitations import ShellRendering
from khepri.runtime.shell_refusals import SHELL_REFUSALS

__all__ = [
    "ABSENCE_WORDING",
    "DECISION_COPY",
    "EMPTY_WORDING",
    "SECTION_BASKET",
    "SECTION_BRANCHES",
    "SECTION_CONCENTRATION",
    "SECTION_COPY",
    "SECTION_PRODUCTS",
    "UNIT_WORDING",
    "DecisionControls",
    "DecisionFrame",
    "DecisionReadings",
    "add_decision_routes",
    "applied_filters",
    "decision_sections",
    "decision_view",
    "offers_decisions",
    "read_surface",
    "render_decisions",
]

#: S-3. One section key per breakdown, stable and not a heading: the heading is
#: language-dependent and this is what the template and its tests address.
SECTION_BRANCHES = "branches"
#: S-4.
SECTION_PRODUCTS = "products"
#: S-5a.
SECTION_BASKET = "basket"
#: S-5b. A section of its own because `FR-165` makes it an independent read:
#: Basket may be admitted while Concentration is unavailable, and one surface
#: that failed whole would be the partial projection `RCA-008` §Invariants bars.
SECTION_CONCENTRATION = "concentration"

#: The three governed unit kinds, named for a reader. The keys are `RRA-004`'s
#: own constants rather than strings retyped here: the shell may import
#: `khepri.rra`, so a unit kind renamed there is an import error and not a
#: silently missing line.
UNIT_WORDING = {
    "en": {UNIT_MONETARY: "Currency", UNIT_COUNT: "Count", UNIT_RATIO: "Ratio"},
    "ar": {UNIT_MONETARY: "عملة", UNIT_COUNT: "عدد", UNIT_RATIO: "نسبة"},
}

#: What a governed evidence absence is called. `RRA-014` names the three, and
#: `FR-140` makes each a positive statement -- "the record says there is none" --
#: so each gets words rather than a blank cell.
#:
#: **The keys are literals, and `RCA-007` is why.** `ABSENCE_PRECISION` and its
#: two siblings live in `khepri.rra.semantic_views.projection`, and
#: `test_the_adapter_is_the_only_runtime_module_reaching_the_projection` asserts
#: that `semantic_view_adapter.py` is the **one** runtime module importing that
#: package -- a second one is what a second composition root would look like.
#: So they are literals here and `test_d105_evidence_drawer` asserts them against
#: that module, exactly as `card.py`'s availability literals are asserted against
#: `khepri.rra.definitions`. Drift fails visibly rather than silently. The unit
#: kinds above need no such treatment: `khepri.rra.facts` is not the semantic-view
#: package and the shell may import it.
ABSENCE_WORDING = {
    "en": {
        "precision": "Precision is not stated by the source.",
        "inputs": "The inputs are not stated by the source.",
        "provenance": "Provenance is not stated by the source.",
    },
    "ar": {
        "precision": "لم يذكر المصدر الدقة.",
        "inputs": "لم يذكر المصدر المدخلات.",
        "provenance": "لم يذكر المصدر مصدر البيانات.",
    },
}

#: The four breakdown headings. Coined here and not read from a catalog because
#: a section is this surface's own structure rather than a governed figure --
#: `FR-159` admits structure, and there is no governed vocabulary for "Branches".
SECTION_COPY = {
    "en": {
        SECTION_BRANCHES: "By branch",
        SECTION_PRODUCTS: "By product and category",
        SECTION_BASKET: "Basket",
        SECTION_CONCENTRATION: "Concentration",
    },
    "ar": {
        SECTION_BRANCHES: "حسب الفرع",
        SECTION_PRODUCTS: "حسب المنتج والفئة",
        SECTION_BASKET: "سلة الشراء",
        SECTION_CONCENTRATION: "التركز",
    },
}

#: `FR-163`: "the two governed empty rules render distinguishably". They are
#: different findings with different remedies -- a store filter naming a store
#: with no sales is not a refused measure -- and a surface rendering both as an
#: empty table would misstate the customer's data. Keyed by `seam`'s own
#: constants, so a third rule cannot be invented here and a renamed one is an
#: import error rather than a missing sentence.
EMPTY_WORDING = {
    "en": {
        EMPTY_STATED_NO_ROWS: "Nothing matched this request.",
        EMPTY_STATED_ABSENCE: "The source published no value for this.",
    },
    "ar": {
        EMPTY_STATED_NO_ROWS: "لا يوجد ما يطابق هذا الطلب.",
        EMPTY_STATED_ABSENCE: "لم ينشر المصدر أي قيمة لهذا.",
    },
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
        "evidence_label": "Evidence and definition",
        "definition_label": "Definition",
        "formula_label": "Formula version",
        "versions_label": "Contract versions",
        "filters_label": "Effective filters",
        "period_label": "Period",
        "unit_label": "Unit",
        "precision_label": "Precision",
        "inputs_label": "Inputs",
        "provenance_label": "Provenance",
        "not_stated": "Not stated by the source.",
        "no_filters": "No filter applied.",
        "evidence_absent": "This analysis cited no evidence for this figure.",
        "evidence_unavailable": "Evidence is unavailable.",
        "status_verified": "Verified",
        "status_caveated": "Caveated",
        "status_refused": "Refused",
        "status_unavailable": "Unavailable",
        "availability_available": "Available",
        "availability_partial": "Partial",
        "availability_unavailable": "Unavailable",
    },
    "ar": {
        "title": "القرارات",
        "lede": "أرقام محوكمة لتحليل مكتمل واحد.",
        "unavailable": "جزء من هذا العرض غير متاح.",
        "no_rows": "لم ينشر هذا التحليل أي أرقام.",
        "caveats_label": "تحفظات",
        "evidence_label": "الأدلة والتعريف",
        "definition_label": "التعريف",
        "formula_label": "إصدار الصيغة",
        "versions_label": "إصدارات العقد",
        "filters_label": "المرشحات المطبقة",
        "period_label": "الفترة",
        "unit_label": "الوحدة",
        "precision_label": "الدقة",
        "inputs_label": "المدخلات",
        "provenance_label": "مصدر البيانات",
        "not_stated": "لم يذكره المصدر.",
        "no_filters": "لم يطبق أي مرشح.",
        "evidence_absent": "لم يستشهد هذا التحليل بأي دليل لهذا الرقم.",
        "evidence_unavailable": "الأدلة غير متاحة.",
        "status_verified": "مثبت",
        "status_caveated": "متحفَّظ عليه",
        "status_refused": "مرفوض",
        "status_unavailable": "غير متاح",
        "availability_available": "متاح",
        "availability_partial": "جزئي",
        "availability_unavailable": "غير متاح",
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
class _EntryView:
    """One cited evidence record as the drawer reads it.

    `absences` is governed prose and not codes, for `FR-164`'s reason applied to
    data rather than to a refusal: a code in front of a customer states nothing.
    Each of `precision`, `inputs` and `provenance` is the record's own value or
    `None`, and a `None` here is always accompanied by the absence that names it.
    """

    citation: str
    unit: str | None
    precision: object | None
    inputs: object | None
    provenance: object | None
    absences: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class _DrawerView:
    """`FR-162`'s evidence action: the two halves, from their two authorities.

    `definition` and `formula_version` are `RRA-011`'s catalog -- structure,
    which `FR-159` admits from it in as many words. `entries` are
    `ReportEvidenceView`'s. `units` is one unit per entry, in the entries' own
    order and undeduplicated: a single unit chosen from several would be a
    choice made on the reader's behalf.

    `unavailable` is S-9 having answered content-free (`FR-165`) and is a
    different statement from an empty `entries`, which is this projection having
    cited nothing for this metric.
    """

    definition: str
    formula_version: object
    entries: tuple[_EntryView, ...] = field(default_factory=tuple)
    units: tuple[str, ...] = field(default_factory=tuple)
    unavailable: bool = False


@dataclass(frozen=True, slots=True)
class _CardView:
    """One card as the template reads it: named, and qualified in the same row."""

    metric: str
    label: str
    value: object
    population: object
    status: str
    status_label: str
    availability: object | None
    availability_label: str | None
    reason: object | None
    versions: object = None
    caveat_count: int = 0
    drawer: _DrawerView | None = None


@dataclass(frozen=True, slots=True)
class _DecisionView:
    """One rendered decision surface.

    `refusal` is the governed message or `None`; it is never the bare cause
    code, which is what `FR-164` forbids a surface from showing.
    """

    cards: tuple[_CardView, ...] = field(default_factory=tuple)
    #: `FR-137`'s applied filters, which `FR-162` requires be reachable from the
    #: card. Page-level because one read produced every card on it.
    filters: tuple[str, ...] = field(default_factory=tuple)
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
    empty: str | None = None


def _named(card: Any, language: str) -> _CardView:
    """One card, labelled from the governed catalog in the page language.

    `caveat_count` is `FR-162`'s "caveat or refusal count" and is the one place
    this surface counts anything. It is not a figure and cannot become one:
    `card_status` selects from the outcome kind, the governed availability and
    whether caveats exist at all -- `if not caveats`, never `len` -- so the
    number rendered here reaches no decision. `test_d105_evidence_drawer` asserts
    that by giving two readings different counts and one status.
    """
    copy = DECISION_COPY[language]
    availability = card.availability
    return _CardView(
        metric=card.metric,
        label=metric_business_name(card.metric, language),
        value=card.value,
        population=_population(card.population, language),
        status=card.status,
        status_label=copy[f"status_{card.status}"],
        availability=availability,
        availability_label=(
            # `.get` rather than `[...]`, for `_refusal_text`'s stated reason:
            # `availability` is typed `object | None` on `MetricCard`, so a
            # projection emitting one the catalog does not name reaches here.
            # `FR-164` would rather this surface show nothing than show a bare
            # code to a customer, and a `KeyError` shows a 500 instead.
            copy.get(f"availability_{availability}") if availability else None
        ),
        reason=card.reason,
        versions=_stated_versions(card.versions),
        caveat_count=len(card.caveats),
        drawer=_drawer(card.metric, card.evidence, language),
    )


def _stated_versions(versions: object) -> object:
    """The projection's `(name, version)` pairs as one line, never a Python tuple (#519).

    `FR-139`'s versions reach the card as ordered pairs now that the view reads them; the
    drawer states them as written. Any other value is shown exactly as before.
    """
    if isinstance(versions, tuple) and all(
        isinstance(pair, tuple) and len(pair) == 2 for pair in versions
    ):
        return ", ".join(f"{name} {version}" for name, version in versions)
    return versions


def _drawer(metric: str, action: EvidenceAction | None, language: str) -> _DrawerView:
    """The evidence action for one metric: the catalog half and the view half.

    The catalog is read here and not across the seam because `khepri.rca` may not
    import `khepri.rra`, which is the same boundary that leaves a metric's
    business name to this module. `FR-159` admits it: "Structure and navigation
    may come from `RCA-005` records and the `RRA-011` catalog; figures may not",
    and a definition and a formula version are structure.
    """
    entries = tuple(
        _entry(one, language) for one in getattr(action, "entries", ())
    )
    return _DrawerView(
        definition=definitions.describe_metric(metric, language),
        formula_version=definitions.define_metric(metric).formula_version,
        entries=entries,
        units=tuple(one.unit for one in entries if one.unit is not None),
        unavailable=bool(getattr(action, "unavailable", False)),
    )


def _entry(entry: EvidenceEntry, language: str) -> _EntryView:
    """One record as the drawer reads it, with its absences in governed prose."""
    return _EntryView(
        citation=entry.citation,
        unit=UNIT_WORDING[language].get(str(entry.unit_kind)),
        precision=entry.precision,
        inputs=entry.inputs,
        provenance=entry.provenance,
        absences=tuple(
            ABSENCE_WORDING[language][kind]
            for kind in entry.absences
            if kind in ABSENCE_WORDING[language]
        ),
    )


def applied_filters(effective: Any) -> tuple[str, ...]:
    """`FR-137`'s applied filters, requested and definition-fixed alike.

    Both halves, because the requirement names both and a surface showing only
    what the reader asked for would hide the ones the view itself applies. The
    order is the effective request's own; nothing here sorts or dedupes, because
    a filter stated twice by two mechanisms is two statements.

    **It takes the `EffectiveRequest` and not a reading**, because `D1-07` made
    it serve two callers: the cards' drawer and each breakdown section, which
    carry different effective requests once filters are routed per view. One
    definition of what "applied" reads like, used by every region that states it.
    """
    if effective is None:
        return ()
    applied = tuple(effective.requested_filters) + tuple(effective.fixed_filters)
    return tuple(f"{dimension}={member}" for dimension, member in applied)


def _caveat_prose(reading: CardsReading, language: str) -> tuple[str, ...]:
    """The reading's caveats as governed prose, in the page language.

    `caveat_message` and not the code: `FR-164`'s discipline for refusals is the
    same one a caveat needs, and a code in front of a customer qualifies
    nothing. Read from each card because every card carries the projection's
    caveat tuple; the first is representative and the set is the projection's.
    """
    codes = reading.cards[0].caveats if reading.cards else ()
    return _governed_caveats(codes, language)


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
    empty = EMPTY_WORDING[language][reading.empty_rule] if reading.empty_rule is not None else None
    return _DecisionView(
        cards=tuple(_named(card, language) for card in reading.cards),
        filters=applied_filters(reading.effective),
        caveats=_caveat_prose(reading, language),
        refusal=_refusal_text(reading, language),
        unavailable=reading.status == "unavailable",
        empty=empty,
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

    **`source_id` has no default, and review on `#448` is why.** It defaulted to
    `""`, which made `surface_path` `/{organization}/decisions/` while the frame
    still rendered its language control -- a link to an address `add_decision_routes`
    does not serve, because the route requires a run segment. `FR-054`
    scenario 11 asks that switching language keep the surface, and a control
    pointing at an unserved address keeps nothing. Requiring the field removes
    the state rather than hiding the control in it: this surface always renders
    exactly one completed run, so a frame that names none was never valid.
    """

    language: str
    organization_id: str
    prefix: str
    source_id: str

    def __post_init__(self) -> None:
        """Refuse the empty run as the missing one is refused (`#448`, second round).

        Dropping the default made the *omitted* field a `TypeError`; an explicit
        `source_id=""` still built a frame whose tail is `/decisions/`, an address
        the route does not serve -- the router 404s it, having no run segment to
        match. No caller can reach that state today: nothing in `src/` constructs
        this frame, and the route's `{source}` segment cannot arrive empty. The
        guard is here so the invariant lives on the type rather than in that
        argument, which holds only while both remain true.

        **`organization_id` is checked beside it for the same reason**, because
        the invariant is the *address* and not the run: an empty organization
        yields `//decisions/{run}`, which the router 404s identically, and the
        argument for guarding it is word-for-word the one above. Closing one
        half of an invariant is the shape this branch has now been caught by
        twice -- `decisions` unwired while `deletion` and `pins` were named, and
        the omitted run refused while the empty one built -- which is what
        `test_the_built_image_wires_every_optional_field` exists to stop.
        """
        if not self.source_id:
            raise ValueError("DecisionFrame.source_id must name a run")
        if not self.organization_id:
            raise ValueError("DecisionFrame.organization_id must name an organization")


#: `#564` item 4: the cells a breakdown row prints as they stand -- the two
#: customer-controlled names and the published figure. Everything else is a code:
#: `metric` is named by the row's label and `versions` by its drawer, a
#: `dimension` by the controls' own label and an absent `population` by "not
#: stated". A population *code* has no customer wording, so it is withheld rather
#: than printed (`FR-164`); no view projects one today (`RRA-014`'s `population`
#: absence). An unknown field is withheld too, so a later view version cannot
#: print a new code by default.
_VERBATIM_CELLS = frozenset({"store", "member", "value"})


@dataclass(frozen=True, slots=True)
class _RowView:
    """One breakdown row as the template reads it.

    `cells` keeps the row's own published field order, which is how `FR-167`
    holds through the render as well as through the read: a row named by its
    view's own fields cannot carry a four-state availability, because no
    breakdown view publishes one.

    `label` is the governed business name or `None`. `business_metric_name`
    returns `None` rather than the raw code when the row's own dimension cell
    names the figure -- a series metric like `revenue_by_store` is named by its
    `store` cell -- and "the raw code is never a fallback: returning it would
    quietly expose an internal identifier on a customer surface".
    """

    cells: tuple[tuple[str, object], ...]
    label: str | None = None
    drawer: _DrawerView | None = None
    versions: object = None


@dataclass(frozen=True, slots=True)
class _SectionView:
    """One breakdown surface: its figures, and everything qualifying them.

    `refusal`, `empty` and `unavailable` are three different answers and the
    template renders three different things. `FR-163` separates the two empty
    rules, `FR-164` gives a refusal its governed wording, and `FR-165` makes an
    unavailable read content-free -- so a section that collapsed them would be
    misstating the customer's data in whichever direction it collapsed.

    `filters` is this section's own applied request (`FR-137`), read from its
    own outcome. `D1-07` routes a filter only to the views whose definitions
    admit it, so two sections of one page can stand over different populations
    -- `ConcentrationView` admits `product` and `BasketView` admits nothing --
    and `FR-161` puts the qualification on the surface carrying the figure. A
    page-level filter line would state one population for all four and be wrong
    for at least one of them.
    """

    section: str
    heading: str
    rows: tuple[_RowView, ...] = field(default_factory=tuple)
    caveats: tuple[str, ...] = field(default_factory=tuple)
    refusal: str | None = None
    empty: str | None = None
    unavailable: bool = False
    filters: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DecisionReadings:
    """Every read one decision page performs, gathered before it renders.

    Each view is read exactly once for the page. `FR-168` bars a cache and
    `FR-135` bars a second truth, and a surface that re-read S-9 per figure or
    S-6 per card would be both -- which is also why the evidence reading travels
    on `CardsReading` rather than being fetched again for the breakdown rows.

    The breakdowns default to `None` so the frameless render path, which exists
    for the template to be driven directly, can render the cards alone.

    `unsupported` is `D1-07`'s, and it is a read rather than a computed message.
    A parameter no published view admits routes to no view, and a page that
    stopped there would render clean and unfiltered for a request it never
    honored -- the silent discard `FR-137` refuses, reached by another spelling.
    So the pair is sent to a view that must refuse it, and what renders is
    `RRA-014`'s own governed wording rather than a string this module invents
    (`FR-164`). `None` when the reader asked for nothing unsupported, which is
    every request the controls themselves can compose.
    """

    cards: CardsReading
    branches: BreakdownReading | None = None
    products: BreakdownReading | None = None
    basket: BasketSurface | None = None
    unsupported: BreakdownReading | None = None


def _section(
    section: str,
    reading: BreakdownReading | None,
    language: str,
    evidence: EvidenceReading | None,
) -> _SectionView | None:
    """One breakdown as one section, or `None` when this page did not read it."""
    if reading is None:
        return None
    return _SectionView(
        section=section,
        heading=SECTION_COPY[language][section],
        rows=tuple(_row(row, language, evidence) for row in reading.rows),
        caveats=_governed_caveats(reading.caveats, language),
        refusal=_wording_of(reading.refusal, language),
        empty=EMPTY_WORDING[language].get(reading.empty_rule or ""),
        unavailable=reading.status == "unavailable",
        filters=applied_filters(reading.effective),
    )


def _row(row: Any, language: str, evidence: EvidenceReading | None) -> _RowView:
    """One row, named by its own view's fields and carrying its own drawer."""
    metric = str(row.values.get("metric", ""))
    return _RowView(
        cells=_presented(row.cells, language),
        label=business_metric_name(metric, language),
        drawer=_drawer(metric, _action_for(evidence, metric), language),
        versions=_stated_versions(row.values.get("versions")),
    )


def _presented(
    cells: tuple[tuple[str, object], ...], language: str
) -> tuple[tuple[str, object], ...]:
    """The cells a customer reads, in the view's own order (`#564` item 4)."""
    shown = ((name, _cell_text(name, value, language)) for name, value in cells)
    return tuple((name, text) for name, text in shown if text is not None)


def _cell_text(name: str, value: object, language: str) -> object:
    """One cell in the page language, or `None` when it must not print."""
    if name in _VERBATIM_CELLS:
        return value
    if name == "dimension":
        return CONTROL_COPY[language].get(str(value))
    if name == "population":
        return _population(value, language)
    return None


def _population(value: object, language: str) -> str | None:
    """`FR-140`'s absence as the governed "not stated"; a code has no customer wording."""
    return DECISION_COPY[language]["not_stated"] if value is None else None


def _action_for(evidence: EvidenceReading | None, metric: str) -> EvidenceAction:
    """This metric's slice of the page's one S-9 read, or the content-free miss.

    **`None` here is unavailable and not an absence**, which is the distinction
    this function exists for. `read_cards` returns before reading S-9 when S-1 is
    refused, so a page can render breakdown figures with no evidence reading
    behind them at all -- and a drawer that then said "this analysis cited no
    evidence for this figure" would be asserting something the page never
    checked. `FR-165`'s content-free unavailable is the true answer: a part is
    missing, and the surface may not say why.
    """
    if evidence is None:
        return EvidenceAction(metric=metric, unavailable=True)
    return evidence.for_metric(metric)


def _governed_caveats(caveats: tuple[object, ...], language: str) -> tuple[str, ...]:
    """Governed prose for each caveat that has wording. Unknown codes are omitted (`FR-164`)."""
    wording = CAVEAT_WORDING[language]
    messages = []
    for item in caveats:
        token = str(getattr(item, "code", item))
        if token in wording:
            messages.append(caveat_message(token, language))
    return tuple(messages)


def _wording_of(refusal: Any, language: str) -> str | None:
    """`RRA-014`'s own wording for a refusal, or `None` when there was none."""
    if refusal is None:
        return None
    return refusal.wording.get(language)


def decision_sections(
    readings: DecisionReadings, language: str
) -> tuple[_SectionView, ...]:
    """S-3, S-4, S-5a and S-5b, in `D1-01`'s narrative order.

    Four sections and not three: `FR-165` makes Basket and Concentration
    independent reads, so one may be admitted while the other is unavailable and
    the page renders partial success rather than failing whole.
    """
    basket = readings.basket
    built = (
        _section(SECTION_BRANCHES, readings.branches, language, readings.cards.evidence),
        _section(SECTION_PRODUCTS, readings.products, language, readings.cards.evidence),
        _section(
            SECTION_BASKET,
            basket.basket if basket else None,
            language,
            readings.cards.evidence,
        ),
        _section(
            SECTION_CONCENTRATION,
            basket.concentration if basket else None,
            language,
            readings.cards.evidence,
        ),
    )
    return tuple(section for section in built if section is not None)


def read_surface(
    actions: Any, request: CardsRequest, *, selection: ControlSelection
) -> DecisionReadings:
    """Every read this page performs, each view exactly once.

    Seven reads and seven views: S-1 and S-6 and S-9 through `read_cards`, then
    S-3, S-4 and S-5's two. Each is independently authorized and can
    independently answer unavailable (`FR-165`), which is what lets the page
    render partial success rather than failing whole.

    **`selection` is keyword-only and has no default**, because a defaulted
    filter channel is how this ships unfed a second time: `D1-04` built
    `BreakdownRequest.filters` and this function constructed it with three
    arguments, so the channel existed and carried nothing until `D1-07` found it.
    A caller that forgets it now fails rather than quietly rendering the
    unfiltered page.

    **Each view is sent what its own definition admits** (`controls.routed_to`),
    which is why S-5's two halves are built separately here rather than from one
    request: `ConcentrationView` admits `product` and `BasketView` admits
    nothing, and one shared request would refuse Basket every time a reader
    filtered by product. Each reading carries its own `effective`, so a section
    built without a filter states that beside its own figures (`FR-161`).

    **S-6 is not read again here**, and that is `FR-161` rather than an omission.
    "Availability, caveats and refusals are reachable from the surface carrying
    the figure they qualify and are not deferred to a terminal page", so S-6
    renders distributed -- the four-state in the card's own row, each section's
    caveats and refusal in that section. A consolidated limits section would
    read `MetricAvailabilityView` a second time for a page whose cards already
    carry it, which `FR-168` bars as a cache and `FR-135` as a second truth.
    """
    def routed(identity: ViewIdentity) -> BreakdownRequest:
        """This view's request, carrying what its own definition admits."""
        return BreakdownRequest(
            organization_id=request.organization_id,
            account_id=request.account_id,
            source_id=request.source_id,
            filters=routed_to(identity, selection),
        )

    return DecisionReadings(
        cards=read_cards(actions, request),
        branches=read_branches(actions, routed(BRANCH_PERFORMANCE)),
        products=read_products(actions, routed(PRODUCT_CATEGORY)),
        basket=BasketSurface(
            basket=read_basket(actions, routed(BASKET)),
            concentration=read_concentration(actions, routed(CONCENTRATION)),
        ),
        unsupported=_unsupported_read(actions, request, selection),
    )


def _unsupported_read(
    actions: Any, request: CardsRequest, selection: ControlSelection
) -> BreakdownReading | None:
    """The refusal a parameter no view admits must earn, or `None`.

    One extra read and only when the reader asked for something unroutable, so
    an ordinary request performs exactly the seven the page always did -- this
    adds no read to the path `FR-168` governs.

    `BRANCH_PERFORMANCE` carries it because a view must actually be named to be
    read; which one is immaterial, since the request refuses on the parameter
    before projection and every view refuses it identically (`FR-137`).
    """
    asked = unroutable(selection)
    if not asked:
        return None
    return read_branches(
        actions,
        BreakdownRequest(
            organization_id=request.organization_id,
            account_id=request.account_id,
            source_id=request.source_id,
            filters=asked,
        ),
    )


def decision_context(
    readings: DecisionReadings, language: str, controls: DecisionControls
) -> dict[str, Any]:
    """The keys this surface adds to `RCA-002`'s frame, in one place.

    Both render paths use it -- the frameless one below and the route's, which
    hands the rest to `ShellRendering.render` so the security headers keep one
    definition. Two places assembling a template context is how a key goes
    missing from one of them.

    **`period` is the run, and that is `FR-166` rather than a shortcut.**
    `FR-162` requires a card expose "the effective filters and period"; the
    period is "a source selector, choosing a completed run", so the period this
    surface states is the run it is addressed by. It arrives on `controls` and
    not from the reading because a reading does not know its own address.

    `unsupported` is the governed wording for a parameter no view admits, so the
    page states the refusal it earned rather than rendering as though the filter
    had never been asked for (`FR-137`, `FR-164`).
    """
    return {
        "decision": DECISION_COPY[language],
        "period": controls.selection.source_id,
        "view": decision_view(readings.cards, language=language),
        "sections": decision_sections(readings, language),
        "controls": controls_view(controls.selection, controls.sources, language),
        "unsupported": _wording_of(
            readings.unsupported.refusal if readings.unsupported else None, language
        ),
    }


@dataclass(frozen=True, slots=True)
class DecisionControls:
    """What this request chose, and what it could have chosen.

    Grouped for the reason `DecisionFrame` and `_RouteCall` are: these travel
    together through every render path and spelling them flat is the Excess
    Number of Function Arguments finding this module has already paid for.

    `sources` is empty when the deployment wires no record reader, which
    `FR-165` makes a degraded control rather than a failed page.
    """

    selection: ControlSelection
    sources: tuple[SourceOption, ...] = ()


def render_decisions(
    environment: Environment,
    readings: DecisionReadings,
    frame: DecisionFrame,
    controls: DecisionControls,
) -> str:
    """The decision surface's body, without the shell's frame around it.

    The route below renders through `ShellRendering`; this path exists so the
    template can be driven directly, which the surface's own tests need -- a
    template nothing renders cannot be shown to render what it claims.
    """
    return environment.get_template("decision.html.j2").render(
        language=frame.language,
        direction=DIRECTIONS[frame.language],
        copy=SHELL_COPY[frame.language],
        assets=f"{frame.prefix}/assets",
        prefix=frame.prefix,
        alternate="ar" if frame.language == "en" else "en",
        surface_path=decision_tail(
            frame.organization_id, frame.source_id, controls.selection
        ),
        language_switch=True,
        organization_id=frame.organization_id,
        organization_name=None,
        # The frame's destination list. Empty here because this render path has
        # no organization frame to read; the route passes the real one.
        destinations=(),
        **decision_context(readings, frame.language, controls),
    )


def decision_tail(
    organization_id: str, source_id: str, selection: ControlSelection | None = None
) -> str:
    """This surface's address below the language segment, filters included.

    The run is a path segment rather than a query parameter because `FR-166`
    makes the period a **source selector** -- choosing a completed run -- and not
    a view filter. `/analyses/{run_id}` already spells a chosen run this way.

    **The filters are in the tail because the language switch is built from it.**
    `shell.html.j2` renders the alternate language as
    `{prefix}/{alternate}{surface_path}`, so a tail without the query string
    would drop every applied filter the moment a reader switched to Arabic --
    applied state lost on the most ordinary action, with `FR-169` barring the
    remembered state that would otherwise mask it. `selection` defaults to `None`
    so the address of an unfiltered surface is unchanged.
    """
    tail = f"/{organization_id}/decisions/{source_id}"
    if selection is None:
        return tail
    return tail + selection_query(selection)


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
    parameters: tuple[tuple[str, str], ...] = ()
    #: `D1-08`: the rendering mode, partitioned from the filter statements at the
    #: route boundary because an unadmitted filter name is refused at the seam.
    printable: bool = False


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
        request: Request,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """One completed run's decision surface, in the language the address names.

        Every query parameter is read and none is declared: a declared one would
        be silently dropped when it did not match, and `FR-137` requires the
        opposite. What each view is sent is `controls.routed_to`'s.
        """
        printable, filters = partition_print(
            inbound_parameters(request.query_params)
        )
        return _respond(
            _RouteCall(
                services,
                rendering,
                clock,
                language,
                organization,
                session,
                source,
                filters,
                printable,
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
    """Resolve the member, read the surface, render. Nothing else happens here."""
    language = call.rendering.language_of(call.language)
    context = _member_or_none(call)
    if context is None:
        return call.rendering.unavailable(call.rendering.environment, language=language)
    controls = DecisionControls(
        selection=selection_from(call.source_id, call.parameters),
        sources=_sources_for(call, context),
    )
    # Every view read re-resolves the scope, so a membership revoked since the gate refuses
    # here. The reader is then not a member, and `FR-050` gives that the gate's own surface.
    try:
        readings = read_surface(
            call.services.decisions,
            CardsRequest(
                organization_id=context.organization_id,
                account_id=context.account_id,
                source_id=call.source_id,
            ),
            selection=controls.selection,
        )
    except SHELL_REFUSALS:
        return call.rendering.unavailable(call.rendering.environment, language=language)
    return _page(
        call,
        _Resolved(
            context=context,
            language=language,
            readings=readings,
            controls=controls,
        ),
    )


def _sources_for(call: _RouteCall, context: Any) -> tuple[SourceOption, ...]:
    """The completed runs this reader may select, through the existing scope door.

    `resolve_scope` and not a second scope path: `FR-166` makes the workspace
    "the organization scope resolved before any read", and `RCA-001`'s bridge is
    the one definition of which opaque `owner_id` a commercial identity reaches.
    `_workspace_reads` already resolves it this way for the record surfaces.

    **An absent or unreadable record store degrades this control alone**
    (`FR-165`): the page renders with no selector rather than failing whole, and
    says nothing about why -- the unavailable outcome is content-free.

    **The read is probed for, not assumed**, and the full suite is why. A
    `records` collaborator wired for the surfaces that need only a history read
    does not necessarily carry `analysis_runs_for_scope`, and asserting the
    field is not `None` let an `AttributeError` reach the page -- six failures
    in `test_r807_shell_quality`, on a decision surface that had rendered fine
    until this slice asked its services for one more thing. `FR-165` makes a
    reader that cannot answer a degraded control, never a failed page.
    """
    records = getattr(call.services, "records", None)
    isolation = getattr(call.services, "isolation", None)
    reader = getattr(records, "analysis_runs_for_scope", None)
    if isolation is None or reader is None:
        return ()
    try:
        owner_id = isolation.resolve_scope(context.account_id, context.organization_id)
        runs = reader(owner_id)
    except PermissionError:
        return ()
    return source_options(runs, call.source_id)


@dataclass(frozen=True, slots=True)
class _Resolved:
    """One resolved request: who is asking, in what language, and what it read.

    Grouped for the reason `DecisionRead`, `ShellRendering`, `DecisionFrame` and
    `_RouteCall` are each grouped -- CodeScene admits four arguments and `D1-07`
    made `_page` carry five. The pre-flight named it before this shipped
    (Excess Number of Function Arguments, `_page`, 5), which is the fifth time
    this programme has paid for the flat form.

    These four are one thing: the context, the language, the readings and the
    controls are all products of resolving one request, and none has meaning
    without the others.
    """

    context: Any
    language: str
    readings: DecisionReadings
    controls: DecisionControls


def _page(call: _RouteCall, resolved: _Resolved) -> Response:
    """The surface inside `RCA-002`'s organization frame.

    `organization_frame` is *called* and not edited: `RCA-008` §Exclusions bars
    changing `shell_frame.py`, which is also why `surface="decisions"` adds no
    navigation entry -- the destinations that module decides are unchanged by
    this surface existing.
    """
    rendering = call.rendering
    context = resolved.context
    frame = organization_frame(
        call.services.organizations.organizations_for_account(context.account_id),
        context.organization_id,
        surface="decisions",
        offers=offers_of(call.services),
    )
    return rendering.render(
        rendering.environment,
        "decision_print.html.j2" if call.printable else "decision.html.j2",
        language=resolved.language,
        status_code=200,
        organization_id=context.organization_id,
        **{
            **frame,
            "surface_path": decision_tail(
                context.organization_id, call.source_id, resolved.controls.selection
            ),
            **decision_context(resolved.readings, resolved.language, resolved.controls),
        },
    )
