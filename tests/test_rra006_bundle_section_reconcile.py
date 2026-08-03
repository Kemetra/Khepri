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
    SECTION_REFUSED,
    BundleRefused,
    ChartSpec,
    ReportBundle,
    Section,
    StatedFigure,
    SurfaceContent,
    reconcile,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from tests.test_rra006_bundle import language_of, package, surface_of


def bundle_of() -> ReportBundle:
    """The package's own figures under one present section, and nothing else.

    Trimmed to the overview deliberately. This file tests *reconciliation* -- what
    happens when a surface misstates the sections it was handed -- and the four
    `RRA-008` families now place four more sections, so every helper here would
    otherwise have to rebuild a five-section index in order to exercise a rule that
    needs one. The assembly has its own tests; this keeps the smallest bundle that
    can be misstated.

    Report-level caveats only, because a caveat scoped to a section this bundle no
    longer declares is rejected by the constructor -- which is itself one of the
    rules under test here.
    """
    full = ReportBundle.of(package())
    figures = tuple(
        figure for figure in full.figures if figure.section == SECTION_OVERVIEW
    )
    return replace(
        full,
        figures=figures,
        caveats=tuple(caveat for caveat in full.caveats if caveat.section is None),
        sections=(
            Section(
                section_id=SECTION_OVERVIEW,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=tuple(figure.figure_id for figure in figures),
                chart=None,
            ),
        ),
    )


def section_of(
    bundle: ReportBundle,
    section_id: str = SECTION_OVERVIEW,
    *,
    figures: tuple[str, ...] | None = None,
    chart: ChartSpec | None = None,
) -> Section:
    """One present section over the bundle's figures, or a named subset."""
    return Section(
        section_id=section_id,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=(
            tuple(figure.figure_id for figure in bundle.figures)
            if figures is None
            else figures
        ),
        chart=chart,
    )


def across_two_sections(bundle: ReportBundle) -> ReportBundle:
    """The same bundle with its first figure genuinely moved to comparison.

    The figure's own `section` moves with it, because a bundle may not index a
    figure under a section other than the one it claims. An earlier version of
    this helper only rewrote the index, which built a bundle contradicting
    itself -- a section indexing an overview figure as comparison, and that
    figure indexed twice. The constructor now rejects it, which is the point.
    """
    moved, *rest = bundle.figures
    replaced = replace(moved, section=SECTION_COMPARISON)
    return replace(
        bundle,
        figures=(replaced, *rest),
        sections=(
            section_of(
                bundle,
                figures=tuple(figure.figure_id for figure in rest),
            ),
            section_of(
                bundle,
                SECTION_COMPARISON,
                figures=(replaced.figure_id,),
            ),
        ),
    )


def bend(bundle: ReportBundle, *, both: bool = False, **fields: object) -> SurfaceContent:
    """A faithful surface with one field bent, in Arabic alone or in both.

    Which of the two matters: bending Arabic alone produces a disagreement
    between the surfaces, and bending both produces a disagreement with the
    bundle. Those are different failures with different governed reasons, so
    every test says explicitly which one it is reaching for.
    """
    return surface_of(
        bundle,
        languages=(
            language_of(bundle, LANGUAGE_ARABIC, **fields),  # type: ignore[arg-type]
            language_of(bundle, LANGUAGE_ENGLISH, **(fields if both else {})),  # type: ignore[arg-type]
        ),
    )


def restated(bundle: ReportBundle, section: str) -> tuple[StatedFigure, ...]:
    """Every figure of one language, claimed under a section of our choosing."""
    return tuple(
        replace(entry, section=section)
        for entry in language_of(bundle, LANGUAGE_ARABIC).stated
    )


def refusal_for(content: SurfaceContent, bundle: ReportBundle) -> str:
    with pytest.raises(BundleRefused) as refused:
        reconcile(content, bundle=bundle)
    return str(refused.value)


def test_the_bundle_places_every_rra004_figure_in_the_overview() -> None:
    # Asserted against the real bundle rather than the trimmed one above, because
    # the claim is about where the package's own figures land now that the four
    # RRA-008 families also place figures. A family's fact belongs to its own
    # section; a package total belongs to the overview, and the arrival of the
    # families must not have moved one.
    bundle = ReportBundle.of(package())
    citations = {
        *(fact.citation_id for fact in package().facts),
        *(entry.citation_id for entry in package().series),
        *(entry.citation_id for entry in package().comparisons),
    }
    placed = {
        figure.section
        for figure in bundle.figures
        if figure.citation_id in citations
    }
    assert placed == {SECTION_OVERVIEW}

    # And the trimmed bundle this file reconciles against declares only that one.
    assert bundle_of().section_ids == (SECTION_OVERVIEW,)


# One bend of a faithful surface, and the reason that names what went wrong.
#
# Tabulated rather than written out, because these cases differ only in the bend
# and the reason -- and the taxonomy is the substance here. Every row reconciles
# perfectly by text; each fails somewhere else:
#
#   * a figure under another section's heading is cited right and read wrong
#   * an invented name is a distinct failure from a wrong-but-governed one, so a
#     refusal record can say which happened
#   * one language dropping a section disagrees with the other language, while
#     both dropping it disagrees with the report -- and the second is the case no
#     tuple derived from figure rows could ever catch, since the two surfaces
#     agree with each other
#   * claiming more than the bundle assembled is as wrong as claiming less: a
#     heading for an analysis nobody ran
BENT_SURFACES = [
    pytest.param(
        lambda bundle: {"stated": restated(bundle, SECTION_COMPARISON)},
        REASON_FIGURE_MISPLACED,
        id="a-figure-under-another-sections-heading",
    ),
    pytest.param(
        lambda bundle: {"stated": restated(bundle, "invented")},
        REASON_UNKNOWN_SECTION,
        id="a-figure-under-an-invented-heading",
    ),
    pytest.param(
        lambda bundle: {"both": True, "sections": ()},
        REASON_SECTION_NOT_PRESENTED,
        id="a-section-dropped-from-both-languages",
    ),
    pytest.param(
        lambda bundle: {"sections": ()},
        REASON_SECTION_COVERAGE_DIFFERS,
        id="a-section-dropped-from-one-language",
    ),
    pytest.param(
        lambda bundle: {"both": True, "sections": ("invented",)},
        REASON_UNKNOWN_SECTION,
        id="a-claim-naming-a-section-that-does-not-exist",
    ),
    pytest.param(
        lambda bundle: {"both": True, "sections": (SECTION_OVERVIEW, SECTION_GROWTH)},
        REASON_SECTION_NOT_PRESENTED,
        id="a-claim-the-bundle-never-assembled",
    ),
]


@pytest.mark.parametrize(("fields", "reason"), BENT_SURFACES)
def test_a_bent_surface_refuses_with_the_reason_that_names_it(
    fields: object,
    reason: str,
) -> None:
    bundle = bundle_of()
    assert refusal_for(bend(bundle, **fields(bundle)), bundle) == reason  # type: ignore[operator]


def test_section_order_differing_by_language_refuses() -> None:
    # Same set, different sequence. Order is compared as a tuple and membership
    # as a set, so a reordering and an omission are told apart rather than
    # collapsed into one ambiguous refusal.
    bundle = across_two_sections(bundle_of())
    assert bundle.section_ids == (SECTION_OVERVIEW, SECTION_COMPARISON)
    content = bend(bundle, sections=(SECTION_COMPARISON, SECTION_OVERVIEW))
    assert refusal_for(content, bundle) == REASON_SECTION_ORDER_DIFFERS


def test_every_new_section_reason_is_governed() -> None:
    # A reason a refusal record may not carry is a reason that cannot be
    # recorded, so each must be in the gate that keeps those records free of
    # customer content.
    for reason in (
        REASON_UNKNOWN_SECTION,
        REASON_FIGURE_MISPLACED,
        REASON_SECTION_NOT_PRESENTED,
        REASON_SECTION_COVERAGE_DIFFERS,
        REASON_SECTION_ORDER_DIFFERS,
        REASON_CHART_FIGURE_NOT_STATED,
    ):
        assert reason in GOVERNED_REASONS


def charted(bundle: ReportBundle) -> ReportBundle:
    """The same bundle with its overview section plotting its first two figures."""
    return replace(
        bundle,
        sections=(
            section_of(
                bundle,
                chart=ChartSpec(
                    kind=CHART_BAR,
                    figure_ids=(
                        bundle.figures[0].figure_id,
                        bundle.figures[1].figure_id,
                    ),
                ),
            ),
        ),
    )


def test_a_chart_plotting_a_figure_the_surface_did_not_state_refuses() -> None:
    # The one gap the structural subset rule leaves open. A chart may only
    # reference figures its section declared, but the surface can still omit one
    # from what it says it presented -- leaving a mark with no text behind it.
    bundle = charted(bundle_of())
    withheld = bundle.figures[0].figure_id
    content = bend(
        bundle,
        stated=tuple(
            entry
            for entry in language_of(bundle, LANGUAGE_ARABIC).stated
            if entry.figure_id != withheld
        ),
    )
    assert refusal_for(content, bundle) == REASON_CHART_FIGURE_NOT_STATED


@pytest.mark.parametrize(
    "prepare",
    [
        pytest.param(lambda bundle: bundle, id="without-a-chart"),
        pytest.param(charted, id="with-a-chart-plotting-only-stated-figures"),
    ],
)
def test_a_faithful_surface_reconciles(prepare: object) -> None:
    bundle = prepare(bundle_of())  # type: ignore[operator]
    reconcile(surface_of(bundle), bundle=bundle)


# A bundle that contradicts itself, which no amount of reconciliation can catch.
#
# `reconcile` compares a surface against the bundle and never the bundle against
# itself, so every surface would faithfully copy both halves of the contradiction
# into its claim -- `bundle.section_ids` on one side and each figure's own section
# on the other -- and reconcile perfectly. Deriving the index in `of` protects
# only callers who use `of`, and the constructor is public.
CONTRADICTORY_BUNDLES = [
    pytest.param(
        lambda bundle: {"sections": ()},
        id="figures-placed-in-a-section-the-bundle-never-declares",
    ),
    pytest.param(
        lambda bundle: {
            "sections": (section_of(bundle, figures=("F-does-not-exist",)),)
        },
        id="a-section-indexing-a-figure-that-does-not-exist",
    ),
    pytest.param(
        lambda bundle: {
            "sections": (
                section_of(bundle),
                section_of(
                    bundle,
                    SECTION_COMPARISON,
                    figures=(bundle.figures[0].figure_id,),
                ),
            )
        },
        id="one-figure-indexed-under-two-sections",
    ),
    pytest.param(
        lambda bundle: {
            "sections": (
                section_of(
                    bundle,
                    SECTION_COMPARISON,
                    figures=tuple(f.figure_id for f in bundle.figures),
                ),
            )
        },
        id="a-figure-indexed-under-a-section-other-than-its-own",
    ),
]


@pytest.mark.parametrize("fields", CONTRADICTORY_BUNDLES)
def test_a_bundle_may_not_disagree_with_itself_about_placement(fields: object) -> None:
    bundle = bundle_of()
    with pytest.raises(ValueError):
        replace(bundle, **fields(bundle))  # type: ignore[operator]


def test_a_refused_section_needs_no_figures_to_index() -> None:
    # Refused sections are exempt for free: they carry no figures, so they
    # contribute nothing to the index, and a present section always carries one.
    bundle = bundle_of()
    widened = replace(
        bundle,
        sections=(
            section_of(bundle),
            Section(
                section_id=SECTION_GROWTH,
                state=SECTION_REFUSED,
                reason="units_absent",
                figure_ids=(),
                chart=None,
            ),
        ),
    )
    assert widened.section_ids == (SECTION_OVERVIEW, SECTION_GROWTH)


def test_a_stated_figure_carries_its_section_as_a_claim() -> None:
    # Not copied from the bundle at construction and not validated there. A
    # surface that looked the answer up would agree with itself by definition,
    # and the placement check would pass on every surface including a broken one.
    stated = StatedFigure(figure_id="F-1", text="500.00", section="invented")
    assert stated.section == "invented"
