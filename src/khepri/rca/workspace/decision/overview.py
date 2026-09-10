"""S-1, the Executive Overview read model (`D1-02`; active `RCA-008`).

The smallest complete answer, and the first surface in `D1-01`'s narrative
order: the ten core metrics for one run, from `ExecutiveOverviewView` at its
pinned version.

**This module selects, names and passes through. It computes nothing.** `FR-159`
admits "select, order, group for layout, and pass through" and bars sum,
average, difference, rank, score, normalize, threshold and percentage alike --
"whatever the arithmetic's size", which is why `test_d102_decision_seam` asserts
the ban against this module's AST rather than trusting its author.

Zipping `fields` to a row is the "group for layout" half, and it is `strict`:
a projection row narrower than its published field order would otherwise lose a
governed field silently, and `population` or `versions` going missing is exactly
the qualification `FR-161` exists to keep beside the figure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from khepri.rca.semantic_queries.ports import (
    KIND_ADMITTED,
    ViewOutcome,
    ViewProjection,
    ViewRefusal,
)
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision.seam import EXECUTIVE_OVERVIEW, DecisionRead, read

__all__ = ["OverviewFigure", "OverviewReading", "OverviewRequest", "read_overview"]


@dataclass(frozen=True, slots=True)
class OverviewFigure:
    """One projected figure and the qualification published beside it.

    `value` and `population` are `object` rather than a narrowed type on
    purpose: the projection's cell is whatever the governed source published,
    and coercing it here would be the first arithmetic. `FR-161` is why
    `population` and `versions` travel with the value rather than beside it --
    a claim is presented only where the reader can reach whether it is allowed
    to be made.
    """

    metric: str
    value: object
    population: object
    versions: object


@dataclass(frozen=True, slots=True)
class OverviewReading:
    """What one S-1 read yielded, in the shape a surface renders.

    There is no `reason` field and that is `FR-165`: the unavailable outcome is
    content-free, so a surface "may say a part is unavailable and may never say
    why". A field here would be the place a why leaked in.

    `refusal` carries `ViewRefusal` whole rather than a flattened message, so
    `D1-03` can render `FR-164`'s governed bilingual wording in the page
    language instead of inventing a string.

    `empty_rule` is set only when the projection is empty. `FR-163`:
    `stated_no_rows` and `stated_absence` are different findings with different
    remedies, and a surface rendering both as an empty table misstates the
    customer's data.
    """

    status: str
    figures: tuple[OverviewFigure, ...] = field(default_factory=tuple)
    caveats: tuple[object, ...] = field(default_factory=tuple)
    refusal: ViewRefusal | None = None
    empty_rule: str | None = None


@dataclass(frozen=True, slots=True)
class OverviewRequest:
    """Who is asking, in which organization, over which completed run.

    The run is a `source_id` rather than a period, and `FR-166` is why: no
    published view names `period` in its `request_filter_allowlist`, so the
    period control is a **source selector**. Naming it `source_id` here is what
    stops `D1-07` from being able to pass a period as a filter.

    The view is not a parameter. This surface reads `ExecutiveOverviewView` and
    no other, which is `FR-160`'s pin expressed as a type rather than as a
    convention.
    """

    organization_id: str
    account_id: str
    source_id: str


def _figure(fields: tuple[str, ...], row: tuple[object, ...]) -> OverviewFigure:
    """One row, named by the view's published field order. Layout, not derivation."""
    cell = dict(zip(fields, row, strict=True))
    return OverviewFigure(
        metric=str(cell["metric"]),
        value=cell["value"],
        population=cell["population"],
        versions=cell["versions"],
    )


def _admitted(projection: ViewProjection) -> OverviewReading:
    """An admitted projection, in source order, with its absence rule if empty."""
    figures = tuple(_figure(projection.fields, row) for row in projection.rows)
    return OverviewReading(
        status=KIND_ADMITTED,
        figures=figures,
        caveats=projection.caveats,
        empty_rule=EXECUTIVE_OVERVIEW.empty_rule if projection.is_empty else None,
    )


def _reading(outcome: ViewOutcome) -> OverviewReading:
    """The outcome as a surface reads it, dispatched on the kind it declares.

    Dispatching on `kind` and not on `projection is None` is the fail-closed
    half, and the difference is not theoretical: `ViewOutcome` is a frozen
    dataclass with no kind-to-payload validation, so a refused outcome carrying
    a projection is constructible. Branching on the payload would render its
    rows under an admitted status and drop the refusal -- showing a customer
    figures the package refused, which is precisely what §Invariants' "no
    partial projection" and `FR-164`'s "no surface ... softens a refusal"
    forbid. An admitted outcome with no projection falls here too, and yields
    no figures rather than inventing any.
    """
    if outcome.kind != KIND_ADMITTED or outcome.projection is None:
        return OverviewReading(status=outcome.kind, refusal=outcome.refusal)
    return _admitted(outcome.projection)


def read_overview(actions: SemanticQueryActions, request: OverviewRequest) -> OverviewReading:
    """Read S-1 for one run, at the pinned version, deriving nothing."""
    outcome = read(
        actions,
        DecisionRead(
            organization_id=request.organization_id,
            account_id=request.account_id,
            identity=EXECUTIVE_OVERVIEW,
            source_ids=(request.source_id,),
        ),
    )
    return _reading(outcome)
