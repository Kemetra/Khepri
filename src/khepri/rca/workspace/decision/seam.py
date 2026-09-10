"""The one read every decision surface performs (`D1-02`; active `RCA-008`).

`FR-159` admits a figure only from a semantic-view projection, and `FR-160`
requires each read name its `view_id` and `view_version` exactly. This module is
where both are held: eight `ViewIdentity` literals and one `read`.

**Why the identities are literals and not a registry lookup.** `FR-160`: the
version is "a literal constant in the reading module, never obtained at read
time from `published_versions`, `published_history`, or any other enumeration of
what the registry currently publishes", because resolving it dynamically is the
`latest` alias `FR-143` forbids reached by a different spelling -- it would
follow a republication silently. The cost of a literal is that it can go stale,
and that cost is paid in test: `test_d102_decision_seam` asserts every identity
against what the registry publishes, so a republication fails visibly.

**Why `DecisionRead` names no metric.** `FR-135` forbids retyping a metric code
and `RCA-006` forbids `khepri.rca` importing `khepri.rra`, which looks like a
contradiction until the seam's own contract is read: `SemanticViewRequest`'s "an
empty `metrics` or `dimensions` asks for the definition's own published
selection rather than for nothing". So this module names none, the registry
selects, and a metric added to a core contract arrives with no edit here.

**Why the empty rule sits beside the version.** `FR-163` requires
`stated_no_rows` and `stated_absence` render distinguishably, and a projection
carries `is_empty` without carrying which rule produced it. The rule is view
metadata of the same kind as the version -- pinned here, asserted against the
registry there.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from khepri.rca.semantic_queries.ports import SemanticViewRequest, ViewOutcome
from khepri.rca.semantic_queries.queries import (
    SemanticQueryActions,
    SemanticQueryActor,
    SemanticQueryRequest,
)

__all__ = [
    "BASKET",
    "BRANCH_PERFORMANCE",
    "CONCENTRATION",
    "DECISION_VIEWS",
    "EMPTY_STATED_ABSENCE",
    "EMPTY_STATED_NO_ROWS",
    "EXECUTIVE_OVERVIEW",
    "METRIC_AVAILABILITY",
    "PERIOD_COMPARISON",
    "PRODUCT_CATEGORY",
    "REPORT_EVIDENCE",
    "DecisionRead",
    "ViewIdentity",
    "read",
]

#: The governed source published no value at all -- a refused or unavailable
#: measure. `FR-163`: a different finding, with a different remedy, from the one
#: below.
EMPTY_STATED_ABSENCE = "stated_absence"

#: The admitted request matched nothing -- a store filter naming a store with no
#: sales. Not "we could not compute this".
EMPTY_STATED_NO_ROWS = "stated_no_rows"


@dataclass(frozen=True, slots=True)
class ViewIdentity:
    """One published view, named exactly, with the rule its absences follow."""

    view_id: str
    view_version: str
    empty_rule: str


EXECUTIVE_OVERVIEW = ViewIdentity(
    view_id="ExecutiveOverviewView",
    view_version="sv1.executive_overview.v1",
    empty_rule=EMPTY_STATED_ABSENCE,
)

#: Published and **not reachable**. `RCA-008` §The open question: the adapter
#: builds only single-population bundles, so `FR-136`'s shape predicate refuses
#: this view, and `FR-170` requires the gap be held open visibly rather than
#: rendered as an empty tab. The identity is here so the source map is complete;
#: no read model calls it, and the slice that makes it reachable is the one that
#: removes that assertion.
PERIOD_COMPARISON = ViewIdentity(
    view_id="PeriodComparisonView",
    view_version="sv1.period_comparison.v1",
    empty_rule=EMPTY_STATED_ABSENCE,
)

BRANCH_PERFORMANCE = ViewIdentity(
    view_id="BranchPerformanceView",
    view_version="sv1.branch_performance.v1",
    empty_rule=EMPTY_STATED_NO_ROWS,
)

PRODUCT_CATEGORY = ViewIdentity(
    view_id="ProductCategoryView",
    view_version="sv1.product_category.v1",
    empty_rule=EMPTY_STATED_NO_ROWS,
)

BASKET = ViewIdentity(
    view_id="BasketView",
    view_version="sv1.basket.v1",
    empty_rule=EMPTY_STATED_ABSENCE,
)

CONCENTRATION = ViewIdentity(
    view_id="ConcentrationView",
    view_version="sv1.concentration.v1",
    empty_rule=EMPTY_STATED_ABSENCE,
)

REPORT_EVIDENCE = ViewIdentity(
    view_id="ReportEvidenceView",
    view_version="sv1.report_evidence.v1",
    empty_rule=EMPTY_STATED_ABSENCE,
)

METRIC_AVAILABILITY = ViewIdentity(
    view_id="MetricAvailabilityView",
    view_version="sv1.metric_availability.v1",
    empty_rule=EMPTY_STATED_ABSENCE,
)

#: The closed registry as this side names it (`FR-135`, `FR-160`). Eight, and a
#: ninth cannot be invented here: the source-map test asserts this set equals
#: what the registry publishes.
DECISION_VIEWS: tuple[ViewIdentity, ...] = (
    EXECUTIVE_OVERVIEW,
    PERIOD_COMPARISON,
    BRANCH_PERFORMANCE,
    PRODUCT_CATEGORY,
    BASKET,
    CONCENTRATION,
    REPORT_EVIDENCE,
    METRIC_AVAILABILITY,
)


@dataclass(frozen=True, slots=True)
class DecisionRead:
    """Everything one surface read names, grouped rather than passed flat.

    A value object because CodeScene's gate admits four arguments and the flat
    form carries five; `RRA-014`'s registry made the same trade for the same
    reason. It also makes the omission legible: there is no `metrics` field, and
    that absence is the published-selection contract in the module docstring.

    `filters` carries only what the view's `request_filter_allowlist` names.
    `FR-137` refuses an unsupported filter *before* projection rather than
    dropping it, so a surface that sends one gets a refusal -- which `FR-166`
    makes `D1-07`'s subject, not something to soften here.
    """

    organization_id: str
    account_id: str
    identity: ViewIdentity
    source_ids: tuple[str, ...]
    filters: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def read(actions: SemanticQueryActions, spec: DecisionRead) -> ViewOutcome:
    """One authorized, exactly-versioned read. Selects nothing and computes nothing.

    Each call is independently authorized and can independently answer
    unavailable (`FR-165`), which is what lets a surface render partial success
    rather than failing whole.
    """
    return actions.request(
        SemanticQueryRequest(
            actor=SemanticQueryActor(account_id=spec.account_id),
            organization_id=spec.organization_id,
            view=SemanticViewRequest(
                view_id=spec.identity.view_id,
                view_version=spec.identity.view_version,
                filters=spec.filters,
            ),
            source_ids=spec.source_ids,
        )
    )
