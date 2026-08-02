from __future__ import annotations

import pytest

from khepri.rra.bundle import (
    CHART_BAR,
    CHART_GROUPED_BAR,
    CHART_LINE,
    GOVERNED_CHART_KINDS,
    GOVERNED_SECTION_STATES,
    ORDERED_SECTIONS,
    SECTION_BASKET,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_GROWTH,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    SECTION_REFUSED,
    ChartSpec,
    Section,
)


def test_ordered_sections_starts_with_overview() -> None:
    assert ORDERED_SECTIONS[0] == SECTION_OVERVIEW
    assert SECTION_COMPARISON in ORDERED_SECTIONS


def test_ordered_sections_is_the_governed_order_of_the_five_families() -> None:
    # Order is governed data, not a renderer's choice. A renderer permitted to
    # choose it would let the PDF and the workbook disagree about what a reader
    # sees first, and both would still reconcile.
    assert ORDERED_SECTIONS == (
        SECTION_OVERVIEW,
        SECTION_COMPARISON,
        SECTION_CONCENTRATION,
        SECTION_GROWTH,
        SECTION_BASKET,
    )


def test_present_section_carries_no_reason() -> None:
    section = Section(
        section_id=SECTION_OVERVIEW,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=("F-1",),
        chart=None,
    )
    assert section.reason is None


def test_refused_section_requires_a_reason() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_REFUSED,
            reason=None,
            figure_ids=(),
            chart=None,
        )


def test_present_section_may_not_carry_a_reason() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_PRESENT,
            reason="prior_window_absent",
            figure_ids=("F-1",),
            chart=None,
        )


def test_a_state_outside_the_governed_set_is_rejected() -> None:
    # A state the governed set does not contain must fail construction, not be
    # judged by the reason rules. `pending` with no reason satisfies both of
    # those rules by matching neither, and a renderer testing
    # `state == SECTION_REFUSED` then draws an invented state as a present one.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state="pending",
            reason=None,
            figure_ids=(),
            chart=None,
        )


def test_the_governed_state_set_is_exactly_present_and_refused() -> None:
    assert frozenset({SECTION_PRESENT, SECTION_REFUSED}) == GOVERNED_SECTION_STATES


def test_an_unknown_section_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id="invented",
            state=SECTION_PRESENT,
            reason=None,
            figure_ids=(),
            chart=None,
        )


def test_chart_must_plot_at_least_one_figure() -> None:
    with pytest.raises(ValueError):
        ChartSpec(kind=CHART_BAR, figure_ids=())


def test_chart_kind_must_be_governed() -> None:
    with pytest.raises(ValueError):
        ChartSpec(kind="waterfall", figure_ids=("F-1",))


def test_the_governed_chart_kinds_are_the_three_the_design_fixes() -> None:
    assert frozenset({CHART_BAR, CHART_GROUPED_BAR, CHART_LINE}) == GOVERNED_CHART_KINDS


def test_a_chart_may_not_plot_a_figure_outside_its_section() -> None:
    # Structural rather than validated: a chart can only reference figures the
    # section already declared, and those are already reconciled by exact
    # string comparison. There is no parallel mechanism to keep in step.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_PRESENT,
            reason=None,
            figure_ids=("F-1",),
            chart=ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        )


def test_a_chart_plotting_a_subset_of_its_section_is_accepted() -> None:
    section = Section(
        section_id=SECTION_CONCENTRATION,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=("F-1", "F-2", "F-3"),
        chart=ChartSpec(kind=CHART_LINE, figure_ids=("F-1", "F-2")),
    )
    assert section.chart is not None
    assert section.chart.kind == CHART_LINE


def test_a_refused_section_carries_no_figures_and_still_constructs() -> None:
    # The shape the refusal path depends on. A refused family renders its
    # heading and its reason, so it must be representable with no figures at
    # all -- which is also why section coverage can never be inferred from
    # figure rows.
    section = Section(
        section_id=SECTION_GROWTH,
        state=SECTION_REFUSED,
        reason="units_absent",
        figure_ids=(),
        chart=None,
    )
    assert section.figure_ids == ()
    assert section.chart is None


def test_section_document_is_serializable_for_the_bundle_digest() -> None:
    section = Section(
        section_id=SECTION_BASKET,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=("F-9",),
        chart=ChartSpec(kind=CHART_GROUPED_BAR, figure_ids=("F-9",)),
    )
    assert section.as_document() == {
        "section_id": SECTION_BASKET,
        "state": SECTION_PRESENT,
        "reason": None,
        "figure_ids": ["F-9"],
        "chart": {"kind": CHART_GROUPED_BAR, "figure_ids": ["F-9"]},
    }
