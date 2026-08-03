"""Reconciling where a surface put governed content, not only what it said.

Every check here fails on a surface whose *text* reconciles perfectly. That is
the point: `reconcile` compares rendered strings, so a surface can copy every
figure faithfully and still present it under the wrong heading, drop a whole
section, or plot a mark with no reconciled text behind it.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from khepri.rra.bundle import (
    CHART_BAR,
    GOVERNED_REASONS,
    REASON_CHART_FIGURE_NOT_STATED,
    REASON_FIGURE_MISPLACED,
    REASON_SECTION_COVERAGE_DIFFERS,
    REASON_SECTION_NOT_PRESENTED,
    REASON_SECTION_ORDER_DIFFERS,
    REASON_UNKNOWN_SECTION,
    SECTION_COMPARISON,
    SECTION_GROWTH,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    BundleRefused,
    ChartSpec,
    Section,
    StatedFigure,
    reconcile,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from tests.test_rra006_bundle import language_of, package, surface_of

from khepri.rra.bundle import ReportBundle  # isort: skip


def bundle_of() -> ReportBundle:
    return ReportBundle.of(package())


def test_a_faithful_surface_reconciles() -> None:
    bundle = bundle_of()
    reconcile(surface_of(bundle), bundle=bundle)


def test_the_bundle_places_every_rra004_figure_in_the_overview() -> None:
    # The four RRA-008 families are separate slices. Nothing here may claim a
    # section for an analysis that has not been implemented.
    bundle = bundle_of()
    assert bundle.section_ids == (SECTION_OVERVIEW,)
    assert {figure.section for figure in bundle.figures} == {SECTION_OVERVIEW}


def test_a_figure_stated_in_the_wrong_section_refuses() -> None:
    # Every string still matches. The reader attributes an overview number to
    # comparison analysis, and text reconciliation cannot see it.
    bundle = bundle_of()
    moved = tuple(
        replace(entry, section=SECTION_COMPARISON)
        for entry in language_of(bundle, LANGUAGE_ARABIC).stated
    )
    content = surface_of(
        bundle,
        languages=(
            language_of(bundle, LANGUAGE_ARABIC, stated=moved),
            language_of(bundle, LANGUAGE_ENGLISH),
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_FIGURE_MISPLACED


def test_a_figure_stated_in_an_invented_section_refuses_as_unknown() -> None:
    # An invented name and a wrong-but-governed name are different failures and
    # get different reasons, so a refusal record says which one happened.
    bundle = bundle_of()
    invented = tuple(
        replace(entry, section="invented")
        for entry in language_of(bundle, LANGUAGE_ARABIC).stated
    )
    content = surface_of(
        bundle,
        languages=(
            language_of(bundle, LANGUAGE_ARABIC, stated=invented),
            language_of(bundle, LANGUAGE_ENGLISH),
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_UNKNOWN_SECTION


def test_a_section_dropped_from_both_languages_refuses() -> None:
    # The case no derived tuple could ever catch: both languages agree with each
    # other and disagree with the report that was assembled.
    bundle = bundle_of()
    content = surface_of(
        bundle,
        languages=tuple(
            language_of(bundle, language, sections=())
            for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_SECTION_NOT_PRESENTED


def test_a_section_claim_naming_an_unknown_section_refuses() -> None:
    bundle = bundle_of()
    content = surface_of(
        bundle,
        languages=tuple(
            language_of(bundle, language, sections=("invented",))
            for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_UNKNOWN_SECTION


def test_a_section_claim_the_bundle_never_assembled_refuses() -> None:
    # Claiming *more* than the bundle declares is the same failure as claiming
    # less: the surface is presenting a heading for an analysis nobody ran.
    bundle = bundle_of()
    content = surface_of(
        bundle,
        languages=tuple(
            language_of(bundle, language, sections=(SECTION_OVERVIEW, SECTION_GROWTH))
            for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_SECTION_NOT_PRESENTED


def test_a_section_dropped_from_one_language_only_refuses_as_a_disagreement() -> None:
    # One language dropping a section is a disagreement between surfaces; both
    # dropping it is a disagreement with the report. They get different reasons,
    # which is why the cross-language comparison runs before the bundle one.
    bundle = bundle_of()
    content = surface_of(
        bundle,
        languages=(
            language_of(bundle, LANGUAGE_ARABIC, sections=()),
            language_of(bundle, LANGUAGE_ENGLISH),
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_SECTION_COVERAGE_DIFFERS


def test_section_order_differing_by_language_refuses() -> None:
    # Same set, different sequence. Order is compared as a tuple and membership
    # as a set, so a reordering and an omission are told apart rather than
    # collapsed into one ambiguous refusal.
    base = bundle_of()
    bundle = replace(
        base,
        sections=(
            Section(
                section_id=SECTION_OVERVIEW,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=tuple(f.figure_id for f in base.figures),
                chart=None,
            ),
            Section(
                section_id=SECTION_COMPARISON,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=(base.figures[0].figure_id,),
                chart=None,
            ),
        ),
    )
    swapped = (SECTION_COMPARISON, SECTION_OVERVIEW)
    content = surface_of(
        bundle,
        languages=(
            language_of(bundle, LANGUAGE_ARABIC, sections=swapped),
            language_of(bundle, LANGUAGE_ENGLISH),
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_SECTION_ORDER_DIFFERS


def test_every_new_section_reason_is_governed() -> None:
    # A reason a refusal record may not carry is a reason that cannot be
    # recorded, so each must be in the gate that keeps those records
    # free of customer content.
    for reason in (
        REASON_UNKNOWN_SECTION,
        REASON_FIGURE_MISPLACED,
        REASON_SECTION_NOT_PRESENTED,
        REASON_SECTION_COVERAGE_DIFFERS,
        REASON_SECTION_ORDER_DIFFERS,
        REASON_CHART_FIGURE_NOT_STATED,
    ):
        assert reason in GOVERNED_REASONS


def test_a_chart_plotting_a_figure_the_surface_did_not_state_refuses() -> None:
    # The one gap the structural subset rule leaves open. The chart may only
    # reference figures its section declared, but the surface can still omit one
    # from what it says it presented -- leaving a mark with no text behind it.
    base = bundle_of()
    plotted = base.figures[0].figure_id
    bundle = replace(
        base,
        sections=(
            Section(
                section_id=SECTION_OVERVIEW,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=tuple(f.figure_id for f in base.figures),
                chart=ChartSpec(
                    kind=CHART_BAR,
                    figure_ids=(plotted, base.figures[1].figure_id),
                ),
            ),
        ),
    )
    withheld = tuple(
        entry
        for entry in language_of(bundle, LANGUAGE_ARABIC).stated
        if entry.figure_id != plotted
    )
    content = surface_of(
        bundle,
        languages=(
            language_of(bundle, LANGUAGE_ARABIC, stated=withheld),
            language_of(bundle, LANGUAGE_ENGLISH),
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_CHART_FIGURE_NOT_STATED


def test_a_chart_whose_figures_are_all_stated_reconciles() -> None:
    base = bundle_of()
    bundle = replace(
        base,
        sections=(
            Section(
                section_id=SECTION_OVERVIEW,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=tuple(f.figure_id for f in base.figures),
                chart=ChartSpec(
                    kind=CHART_BAR,
                    figure_ids=(base.figures[0].figure_id, base.figures[1].figure_id),
                ),
            ),
        ),
    )
    reconcile(surface_of(bundle), bundle=bundle)


def test_a_stated_figure_carries_its_section_as_a_claim() -> None:
    # Not copied from the bundle at construction and not validated there. A
    # surface that looked the answer up would agree with itself by definition,
    # and the placement check would pass on every surface including a broken one.
    stated = StatedFigure(figure_id="F-1", text="500.00", section="invented")
    assert stated.section == "invented"
