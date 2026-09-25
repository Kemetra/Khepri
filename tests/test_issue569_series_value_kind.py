"""#569 -- a view publishing `value` publishes the measure, never a row count.

Authority: active `RRA-014` `FR-139` ("Projected typed values ... equal the
source records; no re-rounding, relabelling outside governed vocabulary, or
substitution is allowed"), `FR-138` ("Projection may select"), `FR-140` (every
refusal, caveat, population qualifier, evidence value and absence survives),
`FR-134` (no contract field changes, so no new version), and the consumer
`RCA-008` `FR-159`/`FR-167` reads through.

**Driven over the real projector and the real golden bundle.** On
`ReportBundle.of(package())` a series cell yields two `CitedFigure`s -- one of
kind `value` and one of kind `rows` -- and both carry the series metric. The
branch and product/category views published both under the one `value` column,
so `Revenue - Cairo - 2` sat beside `Revenue - Cairo - 335.75` on the decision
surface: a count of rows read as revenue.

The expected rows below are **literals** read off the golden fixture, not
derived from the projector or from a filter over `bundle.figures` that restates
the fix: a restatement would pass every mutant of the predicate it restates.
"""

from __future__ import annotations

import re
from dataclasses import replace
from decimal import Decimal

import pytest

from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision import breakdowns
from khepri.rca.workspace.decision.card import CardsRequest
from khepri.rca.workspace.decision.controls import ControlSelection
from khepri.rra.bundle import KIND_ROWS, KIND_VALUE, ReportBundle
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.semantic_views import compatibility, projection, published, registry
from khepri.runtime import shell_decisions
from khepri.runtime.shell_api import shell_environment
from tests.test_issue519_semantic_view_readers import (
    _figure,
    _Isolation,
    _ProjectingPort,
    _report,
    _Sources,
)
from tests.test_rra006_bundle import package

_BRANCH = registry.define_view("BranchPerformanceView")
_PRODUCT = registry.define_view("ProductCategoryView")
_SELECTION = ControlSelection(source_id="run-1")

#: The golden package's per-store measures, as the fixture states them.
_BRANCH_ROWS = (
    ("Cairo", "revenue_by_store", Decimal("335.75"), None),
    ("Giza", "revenue_by_store", Decimal("164.25"), None),
    ("Cairo", "units_by_store", Decimal("8"), None),
    ("Giza", "units_by_store", Decimal("3"), None),
)

#: The golden package's per-category measures. It states no product series.
_PRODUCT_ROWS = (
    ("category", "Beverages", "revenue_by_category", Decimal("335.75"), None),
    ("category", "Snacks", "revenue_by_category", Decimal("164.25"), None),
    ("category", "Beverages", "units_by_category", Decimal("8"), None),
    ("category", "Snacks", "units_by_category", Decimal("3"), None),
)


def _bundle() -> ReportBundle:
    return ReportBundle.of(package())


def _projected(definition: object, bundle: ReportBundle) -> projection.ViewProjection:
    outcome = projection.project(
        compatibility.SemanticViewRequest(
            view_id=definition.view_id,  # type: ignore[attr-defined]
            view_version=definition.view_version,  # type: ignore[attr-defined]
        ),
        (bundle,),
    )
    assert outcome.admitted, outcome.refusal
    assert outcome.projection is not None
    return outcome.projection


def _actions() -> SemanticQueryActions:
    return SemanticQueryActions(_Isolation(), _Sources(), _ProjectingPort(_bundle()))


def _request() -> breakdowns.BreakdownRequest:
    return breakdowns.BreakdownRequest(
        organization_id="org-1", account_id="acct-1", source_id="run-1"
    )


# --- the precondition: the fixture really does carry both kinds -------------


def test_the_golden_bundle_states_a_row_count_beside_every_series_measure() -> None:
    """Without this, the tests below could pass on a fixture carrying no counts.

    Pinned as extents: 19 value figures and 14 row counts, 4 of each on the store
    series and 4 of each on the category series.
    """
    figures = _bundle().figures
    kinds = [figure.kind for figure in figures]
    assert kinds.count(KIND_VALUE) == 19
    assert kinds.count(KIND_ROWS) == 14
    for suffix in ("_by_store", "_by_category"):
        series = [figure.kind for figure in figures if figure.metric.endswith(suffix)]
        assert series.count(KIND_VALUE) == 4, suffix
        assert series.count(KIND_ROWS) == 4, suffix


# --- the projector (RRA-014 FR-139, FR-138) ----------------------------------


def test_branch_performance_publishes_each_measure_and_no_row_count() -> None:
    """4 rows, not 8: the 4 value figures, in source order, and no count."""
    assert _projected(_BRANCH, _bundle()).rows == _BRANCH_ROWS


def test_product_category_publishes_each_measure_and_no_row_count() -> None:
    assert _projected(_PRODUCT, _bundle()).rows == _PRODUCT_ROWS


def test_selecting_the_measure_suppresses_no_caveat_or_evidence() -> None:
    """`FR-140` -- what must survive projection still does, whole."""
    bundle = _bundle()
    for definition in (_BRANCH, _PRODUCT):
        projected = _projected(definition, bundle)
        assert projected.caveats == bundle.caveats
        assert projected.evidence == bundle.evidence


def test_a_view_publishing_no_value_column_keeps_its_rows() -> None:
    """The selection is by the published `value` field, not applied to every view.

    `MetricAvailabilityView` publishes `availability`, and its rows are per
    metric; `ReportEvidenceView` publishes `figure`. Both keep the extents they
    had before `#569` over the golden bundle.
    """
    bundle = _bundle()
    availability = _projected(registry.define_view("MetricAvailabilityView"), bundle)
    evidence = _projected(registry.define_view("ReportEvidenceView"), bundle)
    assert len(availability.rows) == 22
    assert len(evidence.rows) == 5


def test_a_view_whose_row_is_a_figure_address_still_addresses_a_row_count() -> None:
    """The gate itself, which the golden bundle cannot exercise.

    `ReportEvidenceView` publishes `figure`, not `value`: its row addresses a
    cell and states no measure, so a row-count cell is still one it addresses.
    The golden bundle admits no row count into this view (its series are keyed
    by a dimension the view does not admit), so a bundle is built with one.
    """
    measure = _figure("revenue", value="500.50")
    count = replace(measure, figure_id="fig_revenue_rows", kind=KIND_ROWS, value=Decimal("3"))
    projected = _projected(registry.define_view("ReportEvidenceView"), _report((measure, count)))
    assert [row[0] for row in projected.rows] == [measure.figure_id, count.figure_id]


def test_no_published_definition_changed_so_no_version_moved() -> None:
    """`FR-134` -- selecting inside the projector changes no contract field."""
    for view_id in registry.view_ids():
        definition = registry.define_view(view_id)
        assert (
            published.definition_digest(definition)
            == published.PUBLISHED_DIGESTS[definition.view_version]
        ), view_id


# --- the RCA-008 read models over the real projector -------------------------


@pytest.mark.parametrize(
    ("reader", "expected"),
    [(breakdowns.read_branches, _BRANCH_ROWS), (breakdowns.read_products, _PRODUCT_ROWS)],
)
def test_a_breakdown_reading_carries_only_the_measures(reader, expected) -> None:
    reading = reader(_actions(), _request())
    assert tuple(tuple(row.values.values()) for row in reading.rows) == expected


# --- the surface a customer reads --------------------------------------------


def _render(language: str) -> str:
    actions = _actions()
    readings = shell_decisions.read_surface(
        actions,
        CardsRequest(organization_id="org-1", account_id="acct-1", source_id="run-1"),
        selection=_SELECTION,
    )
    return shell_decisions.render_decisions(
        shell_environment(),
        readings,
        shell_decisions.DecisionFrame(
            language=language, prefix="/app", organization_id="org-1", source_id="run-1"
        ),
        shell_decisions.DecisionControls(selection=_SELECTION, sources=()),
    )


@pytest.mark.parametrize("language", [LANGUAGE_ENGLISH, LANGUAGE_ARABIC])
def test_the_decision_surface_prints_eight_breakdown_values_not_sixteen(language: str) -> None:
    """4 branch + 4 category measures; the 8 row counts no longer print as values."""
    values = re.findall(r'data-cell="value"[^>]*>([^<]*)<', _render(language))
    assert len(values) == 8
