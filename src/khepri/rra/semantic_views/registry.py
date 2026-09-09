"""The eight published semantic views (`SV1-02`; `RRA-014` `FR-134`–`FR-136`).

`FR-135`: "The published registry is closed to the eight named initial views;
metric and dimension members derive from their governing declarations and are
never retyped as a second truth."

Both halves of that sentence are load-bearing here, and the second is the one a
module like this usually gets wrong. Every metric code below is *selected from*
`definitions.FAMILY_METRICS` by the version that publishes it, and every
dimension from `facts.SERIES_DIMENSIONS` -- so a metric added to a governed
family reaches the view that admits that family with no edit here, and a code
this module could not name is one no family publishes. `definitions.py` states
the same rule for the same reason: "no name in this table is one this module
invented."

The view *names*, their versions, and which families each view admits are this
module's own: `RRA-014` names the eight views, and choosing that
`BranchPerformanceView` reads the store dimension rather than the channel one is
a selection a view is *for*. What the module may not do is coin a metric or a
dimension, because those are the governed declarations a view selects among.
"""

from __future__ import annotations

from khepri.rra import definitions, facts
from khepri.rra.semantic_views.contracts import (
    EMPTY_STATED_ABSENCE,
    EMPTY_STATED_NO_ROWS,
    SHAPE_EITHER_BUNDLE,
    SHAPE_SINGLE_POPULATION,
    SHAPE_TWO_POPULATION,
    SemanticViewDefinition,
)

__all__ = ["UnknownView", "define_view", "view_ids"]

# The governed contract versions each view selects from. Read from the module
# that declares them rather than spelled as strings, so a family whose version
# moves cannot leave a view selecting a version that no longer exists.
_CORE = facts.FORMULA_VERSION
_COMPARISON = definitions.comparison.COMPARISON_FORMULA_VERSION
_GROWTH = definitions.growth.GROWTH_FORMULA_VERSION
_BASKET = definitions.basket.BASKET_FORMULA_VERSION
_CONCENTRATION = definitions.concentration.CONCENTRATION_FORMULA_VERSION


class UnknownView(LookupError):
    """A view identifier the closed registry does not publish.

    Raised rather than returning `None`, following `definitions.UnknownCode`:
    a definition invented for an unrecognized identifier would be
    indistinguishable from a published one, and `FR-135`'s closed set means an
    unknown identifier is always a caller defect rather than a missing row.
    """


def _metrics(*versions: str) -> tuple[str, ...]:
    """Every metric the named governed contracts publish, in a stable order.

    Selection, never enumeration. `FR-135` forbids retyping a metric code, so a
    view says which *contracts* it reads and this reads their members out of
    `FAMILY_METRICS`, whose own docstring records the same rule: a metric added
    there "reaches this catalog without an edit here".
    """
    codes: set[str] = set()
    for version in versions:
        codes.update(definitions.FAMILY_METRICS[version])
    return tuple(sorted(codes))


def _series(*dimensions: str) -> tuple[str, ...]:
    """The `<measure>_by_<dimension>` codes for the named dimensions.

    Composed over `facts.SERIES_MEASURES` -- revenue and units -- for the reason
    `definitions.SERIES_METRICS` gives: only those two are aggregated over a
    dimension, so composing over every core metric would admit
    `gross_margin_by_channel`, which no builder emits. A catalog that defines an
    unproducible code is not fail-closed.
    """
    return tuple(
        sorted(
            f"{measure}_by_{dimension}"
            for measure in facts.SERIES_MEASURES
            for dimension in dimensions
        )
    )


def _view(
    view_id: str,
    version: str,
    *,
    shape: str,
    metrics: tuple[str, ...],
    dimensions: tuple[str, ...],
    filters: tuple[str, ...] = (),
    fixed: tuple[tuple[str, str], ...] = (),
    evidence: tuple[str, ...] = (),
    fields: tuple[str, ...],
    empty: str = EMPTY_STATED_NO_ROWS,
) -> SemanticViewDefinition:
    """Build one definition. Keyword-only past the identity, so a published
    allowlist cannot be swapped with another by position."""
    return SemanticViewDefinition(
        view_id=view_id,
        view_version=version,
        accepted_source_shape=shape,
        metric_allowlist=metrics,
        dimension_allowlist=dimensions,
        request_filter_allowlist=filters,
        fixed_filters=fixed,
        required_evidence=evidence,
        output_field_order=fields,
        empty_result_rule=empty,
    )


_PUBLISHED: dict[str, SemanticViewDefinition] = {
    definition.view_id: definition
    for definition in (
        _view(
            "ExecutiveOverviewView",
            "sv1.executive_overview.v1",
            shape=SHAPE_SINGLE_POPULATION,
            metrics=_metrics(_CORE),
            dimensions=(facts.PERIOD_DIMENSION,),
            fields=("metric", "value", "population", "versions"),
            empty=EMPTY_STATED_ABSENCE,
        ),
        _view(
            "PeriodComparisonView",
            "sv1.period_comparison.v1",
            shape=SHAPE_TWO_POPULATION,
            metrics=_metrics(_CORE, _COMPARISON, _GROWTH),
            dimensions=(facts.PERIOD_DIMENSION,),
            fields=("metric", "subject", "baseline", "delta", "versions"),
            empty=EMPTY_STATED_ABSENCE,
        ),
        _view(
            "BranchPerformanceView",
            "sv1.branch_performance.v1",
            shape=SHAPE_SINGLE_POPULATION,
            metrics=_series(facts.SEMANTIC_STORE),
            dimensions=(facts.SEMANTIC_STORE,),
            filters=(facts.SEMANTIC_STORE,),
            fields=("store", "metric", "value", "population"),
        ),
        _view(
            "ProductCategoryView",
            "sv1.product_category.v1",
            shape=SHAPE_SINGLE_POPULATION,
            metrics=_series(facts.SEMANTIC_PRODUCT, facts.SEMANTIC_CATEGORY),
            dimensions=(facts.SEMANTIC_PRODUCT, facts.SEMANTIC_CATEGORY),
            filters=(facts.SEMANTIC_PRODUCT, facts.SEMANTIC_CATEGORY),
            fields=("dimension", "member", "metric", "value", "population"),
        ),
        _view(
            "BasketView",
            "sv1.basket.v1",
            shape=SHAPE_SINGLE_POPULATION,
            metrics=_metrics(_BASKET),
            dimensions=(facts.PERIOD_DIMENSION,),
            fields=("metric", "value", "population", "versions"),
            empty=EMPTY_STATED_ABSENCE,
        ),
        _view(
            "ConcentrationView",
            "sv1.concentration.v1",
            shape=SHAPE_SINGLE_POPULATION,
            metrics=_metrics(_CONCENTRATION),
            dimensions=(facts.SEMANTIC_PRODUCT, facts.SEMANTIC_CATEGORY),
            filters=(facts.SEMANTIC_PRODUCT, facts.SEMANTIC_CATEGORY),
            fields=("dimension", "metric", "value", "population"),
            empty=EMPTY_STATED_ABSENCE,
        ),
        _view(
            "ReportEvidenceView",
            "sv1.report_evidence.v1",
            # Evidence is carried identically by both bundles: `CitedEvidence` is
            # a `RenderableBundle` member, and `C1-05` widened it with one
            # defaulted `provenance` field emitted only when present, keeping
            # every report-bundle evidence document byte-identical.
            shape=SHAPE_EITHER_BUNDLE,
            metrics=_metrics(_CORE),
            dimensions=(facts.PERIOD_DIMENSION,),
            fields=("figure", "evidence", "provenance", "absence"),
            empty=EMPTY_STATED_ABSENCE,
        ),
        _view(
            "MetricAvailabilityView",
            "sv1.metric_availability.v1",
            shape=SHAPE_EITHER_BUNDLE,
            metrics=_metrics(_CORE, _COMPARISON, _GROWTH, _BASKET, _CONCENTRATION),
            dimensions=facts.SERIES_DIMENSIONS,
            fields=("metric", "availability", "reason", "versions"),
            empty=EMPTY_STATED_ABSENCE,
        ),
    )
}


def view_ids() -> frozenset[str]:
    """Every published view identifier. The registry is closed to these."""
    return frozenset(_PUBLISHED)


def define_view(view_id: str) -> SemanticViewDefinition:
    """The published definition for `view_id`, or `UnknownView`.

    Takes no version: `SV1-02` publishes one version per view, and `FR-143`'s
    exact-version resolution over published history is `SV1-06`'s. A caller
    naming a version reaches `SV1-06`'s resolver, which is why this signature
    stays narrow rather than accepting a version it would have to ignore.
    """
    try:
        return _PUBLISHED[view_id]
    except KeyError:
        raise UnknownView(view_id) from None
