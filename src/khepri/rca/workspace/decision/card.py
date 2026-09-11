"""The `FR-162` metric card and its four-status selection (`D1-03`; active `RCA-008`).

A card is what a customer reads one figure through: the value, and everything
that says whether the figure is allowed to be claimed. `FR-161` is why those
travel together -- "a claim is presented only where the reader can also reach
whether it is allowed to be made".

**A card is four projections plus the catalog**, which `D1-01` §5 found and this
module does not re-derive. Two of the four are reachable today: S-1 supplies the
value, population, versions and caveats; S-6 supplies the governed availability
and reason. The other two are named and absent -- the comparison because
`FR-170` holds its source open, the evidence action because `D1-05` builds it.
**Named rather than omitted**, so a later slice fills a line that already exists
instead of discovering one that does not.

**The label is not here.** `khepri.rca` may not import `khepri.rra`, and a metric
name is `RRA-011`'s catalog. The card carries the governed metric *code* and the
surface names it, as `landing_api.py` already does -- `FR-159` admits structure
from the catalog and bars figures from it.

**The availability literals are pinned, and that costs what pinning costs.**
`definitions.AVAILABLE` and its two siblings are `khepri.rra`'s; this side cannot
import them. So they are literals here and `test_d103_metric_card` asserts them
against that module, exactly as `seam.py`'s view versions are asserted against
the registry. Drift fails visibly rather than silently.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from khepri.rca.semantic_queries.ports import (
    KIND_ADMITTED,
    KIND_REFUSED,
    KIND_UNAVAILABLE,
    ViewOutcome,
    ViewProjection,
    ViewRefusal,
)
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision.seam import (
    EXECUTIVE_OVERVIEW,
    METRIC_AVAILABILITY,
    DecisionRead,
    read,
)

__all__ = [
    "AVAILABILITY_AVAILABLE",
    "AVAILABILITY_PARTIAL",
    "AVAILABILITY_UNAVAILABLE",
    "STATUS_CAVEATED",
    "STATUS_REFUSED",
    "STATUS_UNAVAILABLE",
    "STATUS_VERIFIED",
    "CardsReading",
    "CardsRequest",
    "MetricCard",
    "card_status",
    "read_cards",
]

#: Every declared input the metric needs is resolved (`definitions.AVAILABLE`).
AVAILABILITY_AVAILABLE = "available"
#: Some are resolved and some are not (`definitions.PARTIAL`).
AVAILABILITY_PARTIAL = "partial"
#: None of what it needs is resolved (`definitions.UNAVAILABLE`).
AVAILABILITY_UNAVAILABLE = "unavailable"

#: Admitted, uncaveated, and the governed availability says available.
STATUS_VERIFIED = "verified"
#: Admitted, but the projection carries caveats or the availability is partial.
STATUS_CAVEATED = "caveated"
#: `FR-141`'s governed contract refusal. Carries no figure.
STATUS_REFUSED = KIND_REFUSED
#: `FR-146`'s content-free miss, or an availability of unavailable.
STATUS_UNAVAILABLE = KIND_UNAVAILABLE


@dataclass(frozen=True, slots=True)
class MetricCard:
    """One figure and everything `FR-162` requires beside it.

    `comparison` and `evidence` are always `None` today and are fields anyway:
    `FR-162` names them, `FR-170` explains the first, and `D1-05` fills the
    second. A card that omitted them would let a later slice add a line the
    contract already required, which is how a required line goes missing.
    """

    metric: str
    value: object
    population: object
    versions: object
    status: str
    availability: object | None = None
    reason: object | None = None
    caveats: tuple[object, ...] = field(default_factory=tuple)
    comparison: None = None
    evidence: None = None


@dataclass(frozen=True, slots=True)
class CardsReading:
    """What one decision read yielded, in the shape a surface renders.

    `comparison_unreachable` is `FR-170` stated in the data rather than in the
    template: the surface must say the Period Comparison source is unreachable,
    and a flag the read model sets is harder to drop than a paragraph.
    """

    status: str
    cards: tuple[MetricCard, ...] = field(default_factory=tuple)
    refusal: ViewRefusal | None = None
    empty_rule: str | None = None
    comparison_unreachable: bool = True


@dataclass(frozen=True, slots=True)
class CardsRequest:
    """Who is asking, in which organization, over which completed run.

    A `source_id` and not a period: `FR-166` makes the period a source selector,
    and naming it this way is what stops `D1-07` passing one as a filter.
    """

    organization_id: str
    account_id: str
    source_id: str


def card_status(
    kind: str, availability: object | None, caveats: tuple[object, ...]
) -> str:
    """Which of the four states this figure is in. Selected, never counted.

    The order is the fail-closed one. A refusal outranks everything because it
    is a statement about the request. An unavailable figure outranks a caveated
    one because a caveat qualifies a value that exists. `partial` and a non-empty
    caveat tuple both mean caveated, which is `D1-01` §5's mapping.

    `if caveats` is a truth test on a tuple and not `len(caveats)`: `FR-159`
    bars counting, and the distinction is the requirement rather than a style.
    """
    if kind == KIND_REFUSED:
        return STATUS_REFUSED
    if kind != KIND_ADMITTED or availability == AVAILABILITY_UNAVAILABLE:
        return STATUS_UNAVAILABLE
    if caveats or availability == AVAILABILITY_PARTIAL:
        return STATUS_CAVEATED
    return STATUS_VERIFIED


def _cells(projection: ViewProjection) -> tuple[dict[str, object], ...]:
    """Each row named by the view's published field order. Layout, not derivation."""
    return tuple(
        dict(zip(projection.fields, row, strict=True)) for row in projection.rows
    )


def _admitted_projection(outcome: ViewOutcome | None) -> ViewProjection | None:
    """The projection an admitted outcome carries, or `None` for any other answer.

    One test per line rather than one compound conditional: CodeScene reads the
    compound form as a Complex Conditional, and the three cases are genuinely
    different -- no read, a read that was not admitted, and an admitted read
    with nothing on it.

    This is also where the rule carried from `D1-02` lives, in one place for
    both reads: the kind decides, never the payload. `ViewOutcome` has no
    kind-to-payload validation, so a refused outcome carrying a projection is
    constructible and must not be mistaken for an admitted one.
    """
    if outcome is None:
        return None
    if outcome.kind != KIND_ADMITTED:
        return None
    return outcome.projection


def _qualifiers(outcome: ViewOutcome | None) -> dict[str, dict[str, object]]:
    """S-6's availability and reason per metric, or nothing it could not supply.

    `FR-165`: this read is independently able to answer unavailable, and when it
    does the figures still render -- unqualified, never hidden and never given a
    status invented to fill the gap.
    """
    projection = _admitted_projection(outcome)
    if projection is None:
        return {}
    return {str(cell["metric"]): cell for cell in _cells(projection)}


def _card(
    cell: dict[str, object], qualifier: dict[str, object], caveats: tuple[object, ...]
) -> MetricCard:
    """One admitted figure, qualified by what S-6 published about it."""
    availability = qualifier.get("availability")
    return MetricCard(
        metric=str(cell["metric"]),
        value=cell["value"],
        population=cell["population"],
        versions=cell["versions"],
        status=card_status(KIND_ADMITTED, availability, caveats),
        availability=availability,
        reason=qualifier.get("reason"),
        caveats=caveats,
    )


def _admitted(
    projection: ViewProjection, qualifiers: dict[str, dict[str, object]]
) -> CardsReading:
    """The S-1 projection as cards, in the projection's own order."""
    caveats = projection.caveats
    cards = tuple(
        _card(cell, qualifiers.get(str(cell["metric"]), {}), caveats)
        for cell in _cells(projection)
    )
    return CardsReading(
        status=KIND_ADMITTED,
        cards=cards,
        empty_rule=EXECUTIVE_OVERVIEW.empty_rule if projection.is_empty else None,
    )


def read_cards(actions: SemanticQueryActions, request: CardsRequest) -> CardsReading:
    """Read S-1 and S-6 for one run and compose the cards, deriving nothing.

    Dispatching on the declared kind rather than on the payload is carried from
    `D1-02`, where branching on `projection is None` would have rendered a
    refused outcome's rows under an admitted status. `ViewOutcome` still has no
    kind-to-payload validation, so the rule travels with the shape.
    """
    overview = read(actions, _spec(request, EXECUTIVE_OVERVIEW))
    projection = _admitted_projection(overview)
    if projection is None:
        return CardsReading(status=overview.kind, refusal=overview.refusal)
    qualifiers = _qualifiers(read(actions, _spec(request, METRIC_AVAILABILITY)))
    return _admitted(projection, qualifiers)


def _spec(request: CardsRequest, identity: object) -> DecisionRead:
    """One read of one view for this request. No metric is named (`FR-135`)."""
    return DecisionRead(
        organization_id=request.organization_id,
        account_id=request.account_id,
        identity=identity,  # type: ignore[arg-type]
        source_ids=(request.source_id,),
    )
