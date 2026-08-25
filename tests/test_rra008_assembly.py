"""Assembling the four `RRA-008` families into the sections a bundle declares.

Until now every figure a bundle carried was an `RRA-004` overview figure, and the
four analysis families existed with no way to reach a reader. This is the seam: a
family that states facts becomes a present section, a family that refuses becomes a
refused section carrying its reason, and a section whose figures cannot be drawn
says so rather than looking sparse.

Packages are built from real CSV bytes through the real pipeline, as in the other
`RRA-008` test modules.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from khepri.rra import bundle as bundle_module
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.analysis import concentration
from khepri.rra.bundle import (
    CAVEAT_CHART_NOT_DRAWN,
    CHART_LINE,
    SECTION_BASKET,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_GROWTH,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    SECTION_REFUSED,
    FactPackage,
    ReportBundle,
    Section,
    is_drawable,
)
from khepri.rra.facts import build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import TEST_CONTRACT

HEADER = b"date,revenue,units,invoice_no,product\n"
START = date(2026, 1, 5)


def package_for(content: bytes) -> FactPackage:
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
        contract=TEST_CONTRACT,
    )


def full_package() -> FactPackage:
    """Five consecutive days over two products: every family can state something.

    Four settled periods either side means the comparison and growth families both
    have a pair to work with, and two products give concentration and basket a
    dimension.
    """
    rows = [
        ("100.00", 4, "Water"),
        ("150.00", 5, "Water"),
        ("120.00", 4, "Juice"),
        ("200.00", 8, "Water"),
        ("90.00", 3, "Juice"),
    ]
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},{amount},{units},"
        f"INV-{index},{product}\n".encode()
        for index, (amount, units, product) in enumerate(rows)
    )
    return package_for(HEADER + body)


def bundle_of(package: FactPackage) -> ReportBundle:
    return ReportBundle.of(package)


def section_of(bundle: ReportBundle, section_id: str) -> Section | None:
    return next(
        (entry for entry in bundle.sections if entry.section_id == section_id),
        None,
    )


def test_the_overview_still_carries_the_package_figures() -> None:
    """The regression this slice is most likely to cause.

    Every `RRA-004` figure was an overview figure before the families arrived, and
    placing the analysis families must not move them.
    """
    bundle = bundle_of(full_package())
    overview = section_of(bundle, SECTION_OVERVIEW)
    assert overview is not None
    assert overview.state == SECTION_PRESENT
    assert overview.figure_ids


def test_a_family_that_states_facts_becomes_a_present_section() -> None:
    bundle = bundle_of(full_package())
    for section_id in (SECTION_COMPARISON, SECTION_CONCENTRATION, SECTION_BASKET):
        section = section_of(bundle, section_id)
        assert section is not None, section_id
        assert section.state == SECTION_PRESENT
        assert section.figure_ids


def test_a_family_that_refuses_becomes_a_refused_section_with_its_reason() -> None:
    """Two days cannot settle a period, so the comparison and growth both refuse.

    A refused section carries no figures and still exists: a reader cannot tell
    "there was nothing to show" from "we could not show it" unless the heading and
    the reason are both present.
    """
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},100.00,4,INV-{index},Water\n".encode()
        for index in range(2)
    )
    bundle = bundle_of(package_for(HEADER + body))

    for section_id in (SECTION_COMPARISON, SECTION_GROWTH):
        section = section_of(bundle, section_id)
        assert section is not None, section_id
        assert section.state == SECTION_REFUSED
        assert section.reason
        assert section.figure_ids == ()
        assert section.chart is None


def test_sections_stay_in_governed_order() -> None:
    """`ORDERED_SECTIONS` is what every surface is reconciled against."""
    bundle = bundle_of(full_package())
    claimed = [entry.section_id for entry in bundle.sections]
    assert claimed == [
        section_id
        for section_id in (
            SECTION_OVERVIEW,
            SECTION_COMPARISON,
            SECTION_CONCENTRATION,
            SECTION_GROWTH,
            SECTION_BASKET,
        )
        if section_id in set(claimed)
    ]


def test_a_familys_caveat_is_scoped_to_its_own_section() -> None:
    """`RRA-004` caveats qualify the dataset; a family's qualify its analysis.

    A bare code could be rendered under the basket heading while describing the
    comparison, and the surface would reconcile perfectly.
    """
    bundle = bundle_of(full_package())
    scoped = {caveat.section for caveat in bundle.caveats if caveat.section is not None}
    report_level = {caveat.code for caveat in bundle.caveats if caveat.section is None}

    assert scoped <= set(bundle.section_ids)
    # The package's own caveats stay report-level.
    assert report_level


def test_a_section_whose_figures_cannot_be_drawn_says_so() -> None:
    """Returning no chart is not a disclosure: the section would look merely sparse.

    Stated over every present section rather than over one named example. The earlier
    version named concentration, whose curve was unchartable for an unrelated defect;
    when that was fixed the test failed while the behaviour it describes was intact.
    A rule asserted of one section is a rule that rots when that section changes.
    """
    bundle = bundle_of(full_package())
    scoped = {
        (caveat.section, caveat.code)
        for caveat in bundle.caveats
        if caveat.code == CAVEAT_CHART_NOT_DRAWN
    }
    undrawable = {
        section.section_id
        for section in bundle.sections
        if section.state == SECTION_PRESENT and section.chart is None
    }
    # Not vacuous: this dataset has one comparison mode, and a single point is a number
    # the table states better.
    assert undrawable

    assert {section_id for section_id, _ in scoped} == undrawable
    # And no section that *did* draw one claims otherwise.
    for section in bundle.sections:
        if section.chart is not None:
            assert (section.section_id, CAVEAT_CHART_NOT_DRAWN) not in scoped


def test_a_drawable_section_carries_a_chart_of_its_own_figures() -> None:
    """Basket's attach rates share one unit, so they are drawable."""
    bundle = bundle_of(full_package())
    section = section_of(bundle, SECTION_BASKET)
    assert section is not None
    assert section.chart is not None
    assert set(section.chart.figure_ids) <= set(section.figure_ids)


def test_drawability_is_decided_once_and_shared_with_the_geometry() -> None:
    """The rule lives with the types, so a bundle and a chart cannot disagree.

    `charts.py` imports `bundle`, so the predicate cannot live there without the
    bundle duplicating it -- and a bundle that attached a spec the geometry then
    refused would promise a chart no surface could draw.

    Asked of the figures the section *plots*, not of every figure it carries. An
    earlier version asked it of all of them and passed by coincidence: concentration
    carries two counts and two ratios beside its curve, so the whole set is undrawable
    and the section had no chart, and the two agreed for unrelated reasons.
    """
    bundle = bundle_of(full_package())
    by_id = {figure.figure_id: figure for figure in bundle.figures}
    for section in bundle.sections:
        figures = tuple(by_id[figure_id] for figure_id in section.figure_ids)
        plotted = bundle_module._plottable(section.section_id, figures)
        assert (section.chart is not None) == is_drawable(plotted), section.section_id


def test_a_bucket_figure_carries_the_metric_of_the_fact_it_cites() -> None:
    """A figure's metric is its fact's metric, whichever path built the figure.

    The two paths disagreed. A scalar analysis fact became a figure carrying
    `fact.metric`, while a series or comparison bucket became one carrying the owner's
    **`measure`** -- so a trend over revenue reported `revenue` where the fact says
    `revenue_by_period`. That is what made the concentration curve unchartable: the
    family asks to plot `concentration_curve` and every curve figure claimed to be
    `revenue`.
    """
    package = full_package()
    bundle = bundle_of(package)

    figures = {figure.citation_id: figure for figure in bundle.figures}
    entries = (*package.series, *package.comparisons)
    assert entries
    for entry in entries:
        assert figures[entry.citation_id].metric == entry.metric, entry.metric


def test_the_concentration_curve_is_charted_as_a_cumulative_line() -> None:
    """The one chart `RRA-008` requires by specification rather than by design.

    It was drawn on no surface: `_plottable` matched nothing, so `Section.chart` was
    `None` for concentration on every dataset. Every chart test derived its bundle from
    a dataset and asserted over whichever sections happened to be charted, so a section
    that was never charted was invisible to all of them.
    """
    bundle = bundle_of(full_package())
    section = section_of(bundle, SECTION_CONCENTRATION)
    assert section is not None
    assert section.chart is not None
    assert section.chart.kind == CHART_LINE

    # The curve, and not the four scalars beside it: two counts and two ratios share no
    # axis, and charting them would scale a ratio to invisibility against a count.
    by_id = {figure.figure_id: figure for figure in bundle.figures}
    plotted = [by_id[figure_id] for figure_id in section.chart.figure_ids]
    assert len(plotted) > 1
    assert {figure.metric for figure in plotted} == {concentration.METRIC_CURVE}
