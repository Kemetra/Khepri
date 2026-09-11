"""S-3, S-4 and S-5 -- the governed breakdowns (`D1-04`; active `RCA-008`).

Four views, three surfaces. Branch Performance and Product/Category are one
surface each; Basket and Concentration are **one surface reading two views**,
and `FR-165` makes those two reads independent -- Basket may be admitted while
Concentration is unavailable, and the surface renders that rather than failing
whole.

**A row is named by its own view's published field order.** The four definitions
publish four different orders -- `("store", "metric", "value", "population")` for
one and five differently-named fields for another -- so a common flattened record
would have to invent a name for at least one of them. Zipping each row to its
projection's `fields` is `FR-159`'s "group for layout" and nothing more, and it
is `strict`: a row narrower than its published order would lose a governed field
silently.

**That is also how `FR-167` holds by construction, which is the point.**
`MetricAvailabilityView` publishes no series metric, so "no surface may state a
four-state availability for a per-store, per-product or per-category figure, and
none may synthesize one from the core metric it aggregates". A row that carries
exactly what its view published cannot carry a state that view does not publish,
whatever a later slice reaches for. `test_d104_breakdowns_and_limits` asserts it
negatively as well -- on the shapes, on the rows, and on this module's own AST.

**Filters are passed through verbatim and are never narrowed here.** `FR-137`
refuses an unsupported filter *before* projection and `FR-166` says a parameter a
view's `request_filter_allowlist` does not name "does not get it ignored; it gets
a refusal". A reader that filtered the filters would hold a second copy of the
allowlist and would drop exactly what the requirement says must refuse. Which
controls a surface *offers* is `D1-07`'s; that what is asked for is asked for is
this module's.

**Both governed empty rules meet here.** S-3 and S-4 are the only surfaces whose
rule is `stated_no_rows`; S-5's two views state absence. `FR-163`: a store filter
naming a store with no sales is not a refused measure, and a surface that
rendered both as an empty table would misstate the customer's data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from khepri.rca.semantic_queries.ports import KIND_ADMITTED, ViewProjection, ViewRefusal
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision.seam import (
    BASKET,
    BRANCH_PERFORMANCE,
    CONCENTRATION,
    PRODUCT_CATEGORY,
    DecisionRead,
    ViewIdentity,
    admitted_projection,
    read,
)

__all__ = [
    "BasketSurface",
    "BreakdownReading",
    "BreakdownRequest",
    "BreakdownRow",
    "read_basket",
    "read_basket_surface",
    "read_branches",
    "read_concentration",
    "read_products",
]


@dataclass(frozen=True, slots=True)
class BreakdownRow:
    """One projected row, named by its own view's published field order.

    Ordered pairs rather than named attributes, for the reason the module
    docstring gives: four views, four field orders, and a field this shape does
    not name is a field it cannot invent. `cells` keeps the published order,
    which `FR-134` makes part of view identity; `values` is the same content as
    a mapping the caller may keep.
    """

    cells: tuple[tuple[str, object], ...]

    @property
    def values(self) -> dict[str, object]:
        """The row as a fresh mapping, in the view's own published order."""
        return dict(self.cells)


@dataclass(frozen=True, slots=True)
class BreakdownReading:
    """What one breakdown read yielded, in the shape a surface renders.

    **There is no availability and no reason here, and that is `FR-167`.** The
    only governed four-state lives on `MetricAvailabilityView`, which publishes
    no series metric; a field here would be the place one got synthesized from
    the core metric a breakdown aggregates.

    There is no `reason` for the unavailable case either, which is `FR-165`: the
    unavailable outcome is content-free, so a surface "may say a part is
    unavailable and may never say why".

    `refusal` carries `ViewRefusal` whole rather than a flattened message, so the
    surface renders `FR-164`'s governed bilingual wording in the page language
    instead of inventing a string.
    """

    view_id: str
    status: str
    rows: tuple[BreakdownRow, ...] = field(default_factory=tuple)
    caveats: tuple[object, ...] = field(default_factory=tuple)
    population_qualifiers: tuple[object, ...] = field(default_factory=tuple)
    evidence_absences: tuple[str, ...] = field(default_factory=tuple)
    refusal: ViewRefusal | None = None
    empty_rule: str | None = None


@dataclass(frozen=True, slots=True)
class BreakdownRequest:
    """Who is asking, in which organization, over which completed run.

    A `source_id` and not a period: `FR-166` makes the period a **source
    selector**, and naming it this way is what stops a period being passed as a
    filter. `filters` carries what the reader asked for, unnarrowed -- see the
    module docstring.
    """

    organization_id: str
    account_id: str
    source_id: str
    filters: tuple[tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class BasketSurface:
    """S-5: one surface, two independently authorized reads (`FR-165`).

    Two readings rather than one merged reading, because merging them would make
    the surface fail whole the moment either half missed -- and `FR-165` requires
    the opposite. Neither half is privileged: either may be the one that answers.
    """

    basket: BreakdownReading
    concentration: BreakdownReading


def _row(fields: tuple[str, ...], row: tuple[object, ...]) -> BreakdownRow:
    """One row, zipped to its view's published fields. Layout, not derivation."""
    return BreakdownRow(cells=tuple(zip(fields, row, strict=True)))


def _admitted(identity: ViewIdentity, projection: ViewProjection) -> BreakdownReading:
    """An admitted projection, in source order, with its absence rule if empty."""
    return BreakdownReading(
        view_id=identity.view_id,
        status=KIND_ADMITTED,
        rows=tuple(_row(projection.fields, row) for row in projection.rows),
        caveats=projection.caveats,
        population_qualifiers=projection.population_qualifiers,
        evidence_absences=projection.evidence_absences,
        empty_rule=identity.empty_rule if projection.is_empty else None,
    )


def _read_breakdown(
    actions: SemanticQueryActions, request: BreakdownRequest, identity: ViewIdentity
) -> BreakdownReading:
    """One breakdown, at its pinned version, deriving nothing.

    The kind decides and never the payload -- `seam.admitted_projection` holds
    that rule for every read model under this specification.
    """
    outcome = read(
        actions,
        DecisionRead(
            organization_id=request.organization_id,
            account_id=request.account_id,
            identity=identity,
            source_ids=(request.source_id,),
            filters=request.filters,
        ),
    )
    projection = admitted_projection(outcome)
    if projection is None:
        return BreakdownReading(
            view_id=identity.view_id, status=outcome.kind, refusal=outcome.refusal
        )
    return _admitted(identity, projection)


def read_branches(
    actions: SemanticQueryActions, request: BreakdownRequest
) -> BreakdownReading:
    """S-3 -- per-store figures from `BranchPerformanceView`. Empty means no rows."""
    return _read_breakdown(actions, request, BRANCH_PERFORMANCE)


def read_products(
    actions: SemanticQueryActions, request: BreakdownRequest
) -> BreakdownReading:
    """S-4 -- per-product and per-category figures. Empty means no rows."""
    return _read_breakdown(actions, request, PRODUCT_CATEGORY)


def read_basket(actions: SemanticQueryActions, request: BreakdownRequest) -> BreakdownReading:
    """S-5a -- basket figures. Empty means the source published no value."""
    return _read_breakdown(actions, request, BASKET)


def read_concentration(
    actions: SemanticQueryActions, request: BreakdownRequest
) -> BreakdownReading:
    """S-5b -- concentration figures. Empty means the source published no value."""
    return _read_breakdown(actions, request, CONCENTRATION)


def read_basket_surface(
    actions: SemanticQueryActions, request: BreakdownRequest
) -> BasketSurface:
    """S-5 -- both halves, each authorized and answered on its own (`FR-165`)."""
    return BasketSurface(
        basket=read_basket(actions, request),
        concentration=read_concentration(actions, request),
    )
