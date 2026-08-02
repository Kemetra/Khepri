from __future__ import annotations

import pytest

from khepri.rra.bundle import (
    BUNDLE_VERSION,
    CHART_BAR,
    CHART_GROUPED_BAR,
    CHART_LINE,
    GOVERNED_CHART_KINDS,
    GOVERNED_SECTION_STATES,
    NARRATIVE_OMITTED,
    ORDERED_SECTIONS,
    SECTION_BASKET,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_GROWTH,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    SECTION_REFUSED,
    BundleIdentity,
    ChartSpec,
    ReportBundle,
    Section,
)


def _present(section_id: str) -> Section:
    return Section(
        section_id=section_id,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=(),
        chart=None,
    )


def _identity() -> BundleIdentity:
    """A provenance record with no data behind it.

    Every field is a version string, a digest, or a count, so a bundle can be
    assembled here without building a fact package. These tests are about the
    section sequence a bundle declares and nothing downstream of it.
    """
    return BundleIdentity(
        package_version="rra004.package.v1",
        formula_version="rra004.formula.v1",
        mapping_version="rra004.mapping.v1",
        narrative_version="rra005.narrative.v1",
        profile_digest="0" * 64,
        source_sha256_hex="1" * 64,
        monetary_precision=2,
        row_count=0,
    )


def _bundle(sections: tuple[Section, ...]) -> ReportBundle:
    return ReportBundle(
        identity=_identity(),
        figures=(),
        caveats=(),
        narrative_state=NARRATIVE_OMITTED,
        sections=sections,
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


def test_a_refused_section_may_not_authorize_figures() -> None:
    # The class invariant has to be enforced, not just documented. A refused
    # section carrying figures declares content the refusal branch never
    # renders, so the bundle would authorize figures no surface presents.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_COMPARISON,
            state=SECTION_REFUSED,
            reason="prior_window_absent",
            figure_ids=("F-1",),
            chart=None,
        )


def test_a_refused_section_may_not_authorize_a_chart() -> None:
    # Worse than unused: chart reconciliation requires every plotted figure to
    # appear in what the surface stated, and a refused section states none, so
    # this would refuse the whole bundle for a chart that should not exist.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_COMPARISON,
            state=SECTION_REFUSED,
            reason="prior_window_absent",
            figure_ids=("F-1",),
            chart=ChartSpec(kind=CHART_BAR, figure_ids=("F-1",)),
        )


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


def test_a_bundle_declaring_the_governed_order_is_accepted() -> None:
    bundle = _bundle(tuple(_present(section_id) for section_id in ORDERED_SECTIONS))
    assert bundle.section_ids == ORDERED_SECTIONS


def test_a_bundle_declaring_a_subset_in_governed_order_is_accepted() -> None:
    bundle = _bundle((_present(SECTION_OVERVIEW), _present(SECTION_GROWTH)))
    assert bundle.section_ids == (SECTION_OVERVIEW, SECTION_GROWTH)


def test_a_bundle_with_no_sections_is_accepted() -> None:
    assert _bundle(()).section_ids == ()


def test_a_bundle_may_not_reorder_the_governed_sections() -> None:
    # `section_ids` is the authority every surface's section claim reconciles
    # against, so an order the bundle got wrong is an order every surface
    # follows and reconciles against perfectly. Order is governed data; a
    # caller assembling it is not entitled to choose.
    with pytest.raises(ValueError):
        _bundle((_present(SECTION_GROWTH), _present(SECTION_OVERVIEW)))


def test_a_bundle_may_not_repeat_a_section() -> None:
    with pytest.raises(ValueError):
        _bundle((_present(SECTION_OVERVIEW), _present(SECTION_OVERVIEW)))


def test_the_bundle_version_names_the_document_shape_that_carries_sections() -> None:
    # `sections` joined the hashed document, so every bundle id changed. Two
    # bundles built from identical inputs on either side of that change must
    # not claim the same schema version while having different identities.
    assert BUNDLE_VERSION == "rra006.bundle.v2"
    assert _identity().as_document()["bundle_version"] == BUNDLE_VERSION
