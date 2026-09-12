"""The visible controls, modelled as what they are (`D1-07`; active `RCA-008`).

`D1-01`'s F-2, which `FR-166` made a requirement: the global controls of an
analytics surface are conventionally "period, workspace, dimensions", and on
this surface none of the three is a view filter.

**The period is a source selector.** No published view names `period` in its
`request_filter_allowlist` -- five name no request filter at all -- because a
period is a property of the run's completed package rather than something a
projection filters on. Choosing a period is therefore choosing a `source_id`,
which `decision_tail` already spells as a path segment.

**The workspace is the organization scope**, resolved by `resolve_scope` before
any read, never sent as a parameter.

**Only `store`, `product` and `category` are real filters**, on the three views
whose definitions admit them.

**The allowlist ROUTES a filter; it never DROPS one.** That distinction is the
slice, and it has three parts.

*Offering*: `offered_filters` decides which controls a surface renders, so a
dimension no view admits is one a reader cannot compose a request from.

*Routing*: `routed_to` sends each view what its own definition admits. This is
not a narrowing -- `read_cards` is already sent nothing at all, because its three
views publish `request_filter_allowlist=()`, and that is not a discard either.
What a discard would be is a reader asking for `product=X` and receiving an
unfiltered population with no statement; what prevents it is that each region
renders its own effective filters from its own outcome, so a region built
without the filter says so beside its own figures (`FR-137`, `FR-161`).

*Refusing*: `unroutable` catches the one case routing could swallow. A parameter
no published view admits -- `period=2026-08`, the modelling error this slice
corrects -- routes to nothing, and a surface that stopped there would render a
clean page for a request it never honored. So it is sent to a read that refuses
it, and `FR-137` answers with `RRA-014`'s governed wording rather than silence.

**Why the allowlist is a literal here and not a registry lookup.** `RCA-006`
forbids `khepri.rca` importing `khepri.rra`, so this side cannot read
`request_filter_allowlist` at request time even if `FR-160`'s reasoning about
version literals did not already apply. The cost of a literal is that it can go
stale, and that cost is paid in test exactly as `seam.py` pays it:
`test_d107_controls` asserts this table against what the registry publishes, for
every view in `DECISION_VIEWS` rather than a named sample, so a widened
allowlist fails visibly.

**There is no `dimensions` control.** `dimension_allowlist` and
`request_filter_allowlist` are different fields -- `ExecutiveOverviewView`
admits the `period` dimension and zero filters -- and `seam.py` deliberately
sends neither `metrics` nor `dimensions` so the registry's own published
selection answers. A control that added a `dimensions` parameter would
contradict that contract. The supported dimension controls are the members of
the three real allowlists, which are filters.

**Nothing here is retained.** `FR-169` bars "no retained preference, layout, or
filter state", so a selection is built from the request and discarded with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rca.workspace.decision.seam import (
    BASKET,
    BRANCH_PERFORMANCE,
    CONCENTRATION,
    EXECUTIVE_OVERVIEW,
    METRIC_AVAILABILITY,
    PERIOD_COMPARISON,
    PRODUCT_CATEGORY,
    REPORT_EVIDENCE,
    ViewIdentity,
)

__all__ = [
    "FILTER_CATEGORY",
    "FILTER_DIMENSIONS",
    "FILTER_PRODUCT",
    "FILTER_STORE",
    "VIEW_FILTERS",
    "ControlSelection",
    "SourceOption",
    "offered_filters",
    "routed_to",
    "selection_from",
    "supported_by",
    "unroutable",
]

#: The three real filter dimensions, spelled as `khepri.rra.facts` spells them.
#: Literals rather than an import: `RCA-006` forbids this package importing
#: `khepri.rra`, and `test_d107_controls` asserts each against the registry.
FILTER_STORE = "store"
FILTER_PRODUCT = "product"
FILTER_CATEGORY = "category"

#: Every dimension any published view admits as a request filter, in the order a
#: surface offers them. Three, and a fourth cannot be invented here: the test
#: asserts this set equals the union of what the registry publishes.
FILTER_DIMENSIONS: tuple[str, ...] = (FILTER_STORE, FILTER_PRODUCT, FILTER_CATEGORY)

#: What each published view admits, by `view_id`. Eight entries and five empty,
#: because the emptiness is the requirement's own finding and a table that
#: listed only the three filterable views would hide it -- and would let a view
#: added to `DECISION_VIEWS` arrive here unnamed. `test_d107_controls` asserts
#: extent against `DECISION_VIEWS` and each value against the registry.
VIEW_FILTERS: dict[str, tuple[str, ...]] = {
    EXECUTIVE_OVERVIEW.view_id: (),
    PERIOD_COMPARISON.view_id: (),
    BRANCH_PERFORMANCE.view_id: (FILTER_STORE,),
    PRODUCT_CATEGORY.view_id: (FILTER_PRODUCT, FILTER_CATEGORY),
    BASKET.view_id: (),
    CONCENTRATION.view_id: (FILTER_PRODUCT, FILTER_CATEGORY),
    REPORT_EVIDENCE.view_id: (),
    METRIC_AVAILABILITY.view_id: (),
}


def supported_by(identity: ViewIdentity) -> tuple[str, ...]:
    """What this view admits as a request filter, in published order.

    `KeyError` rather than a default: a view absent from the table is a view
    this module has not been told about, and answering "none" for it would let a
    surface silently offer nothing where the registry admits something.
    """
    return VIEW_FILTERS[identity.view_id]


def offered_filters(identities: tuple[ViewIdentity, ...]) -> tuple[str, ...]:
    """The dimensions a surface reading these views may offer, deduplicated.

    A surface reads several views and a dimension two of them admit is one
    control, not two. The order is this module's own and not the read order, so
    two surfaces reading the same dimensions offer them identically -- which
    `FR-171` needs: parity is checkable only if control order does not depend on
    which view was read first.
    """
    admitted = {name for identity in identities for name in supported_by(identity)}
    return tuple(name for name in FILTER_DIMENSIONS if name in admitted)


@dataclass(frozen=True, slots=True)
class SourceOption:
    """One completed run a reader may select as this surface's period.

    `FR-166`: the period is a source selector. `source_id` is what the seam
    reads; `completed_at` is what a reader recognizes a run by, carried as the
    record's own value and never reformatted into a period label -- a label
    would be this surface naming a period, which is the modelling error the
    requirement corrects.
    """

    source_id: str
    completed_at: object | None
    selected: bool


@dataclass(frozen=True, slots=True)
class ControlSelection:
    """What one request asked for, built from the address and kept nowhere.

    `filters` is what the reader asked for, **exactly as asked**. Nothing is
    removed here; `routed_to` decides which view receives which pair and
    `unroutable` makes sure a pair no view admits still earns its refusal. The
    module docstring gives the full reason.

    Ordered pairs rather than a mapping, because the seam's `filters` is ordered
    pairs and because a dimension stated twice is two statements -- the same
    reading `_effective_filters` takes of `FR-137`'s applied filters.
    """

    source_id: str
    filters: tuple[tuple[str, str], ...] = ()

    def value_for(self, dimension: str) -> str | None:
        """What was asked for on this dimension, or `None`. For rendering only."""
        for name, member in self.filters:
            if name == dimension:
                return member
        return None


def selection_from(
    source_id: str, parameters: tuple[tuple[str, str], ...]
) -> ControlSelection:
    """One request's selection: the chosen run, and every parameter as asked.

    **Nothing is filtered out here**, and that is the requirement rather than an
    omission. A parameter no view admits reaches the seam and is refused, which
    is what `FR-166` means by "does not get it ignored; it gets a refusal".

    Empty members are dropped because an absent control and a control left blank
    are the same statement -- a reader who never chose a store did not ask for
    `store=`, and sending one would refuse a request nobody made. That is not a
    narrowing: it reads a member, never a dimension name, so an unsupported
    dimension carrying a member still travels.
    """
    return ControlSelection(
        source_id=source_id,
        filters=tuple((name, member) for name, member in parameters if member),
    )


def routed_to(identity: ViewIdentity, selection: ControlSelection) -> tuple[tuple[str, str], ...]:
    """What this view is sent, from what the reader asked for.

    **Routed by the allowlist, never dropped by it**, and the difference is the
    whole of `FR-166`. Every view whose definition admits a dimension receives
    it; a view whose definition does not is not sent it, exactly as `read_cards`
    is sent nothing because its three views publish `request_filter_allowlist=()`
    -- and nobody calls *that* a discard. What would be a discard is a reader
    asking for `product=X` and getting an unfiltered population back with no
    statement, and that is what the per-section effective filters prevent: a
    region built without the filter says so in its own words, from its own
    outcome, beside its own figures (`FR-137`, `FR-161`).

    `BasketView` is why this is per-view rather than per-surface. S-5 is one
    surface reading two views, and `ConcentrationView` admits `product` while
    `BasketView` admits nothing; sending the pair to both would refuse Basket and
    darken half the surface every time a reader filtered by product.
    """
    admitted = supported_by(identity)
    return tuple((name, member) for name, member in selection.filters if name in admitted)


def unroutable(selection: ControlSelection) -> tuple[tuple[str, str], ...]:
    """What no published view admits, and therefore what must still be refused.

    **The one case routing could swallow.** A parameter no view's allowlist names
    -- `period=2026-08`, the modelling error this slice exists to correct -- is
    routed to nothing by `routed_to`, and a surface that stopped there would
    render a clean, unfiltered page for a request it never honored. That is
    precisely the silent discard `FR-137` refuses "before projection rather than
    ignoring it", reached by a different spelling.

    So these travel to a read that will refuse them, and the reader sees
    `RRA-014`'s governed wording for `unknown filter`. The controls never compose
    one; this exists for the address a reader types, edits or was sent.
    """
    every = {name for admitted in VIEW_FILTERS.values() for name in admitted}
    return tuple((name, member) for name, member in selection.filters if name not in every)
