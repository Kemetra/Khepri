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

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    CAVEAT_CHART_NOT_DRAWN,
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

HEADER = b"date,revenue,units,invoice_no,product\n"
START = date(2026, 1, 5)


def package_for(content: bytes) -> FactPackage:
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
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
    """Concentration states two counts and two shares, which share no axis.

    `is_drawable` refuses mixed units, so no chart is attached -- and a section that
    simply looked sparse would leave a reader unable to tell a missing chart from a
    chart that was never possible. The caveat carries that distinction.
    """
    bundle = bundle_of(full_package())
    section = section_of(bundle, SECTION_CONCENTRATION)
    assert section is not None
    assert section.chart is None

    codes = {
        caveat.code
        for caveat in bundle.caveats
        if caveat.section == SECTION_CONCENTRATION
    }
    assert CAVEAT_CHART_NOT_DRAWN in codes


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
    """
    bundle = bundle_of(full_package())
    by_id = {figure.figure_id: figure for figure in bundle.figures}
    for section in bundle.sections:
        figures = tuple(by_id[figure_id] for figure_id in section.figure_ids)
        assert (section.chart is not None) == is_drawable(figures)
