"""A caveat qualifies something, and which something is reconciled.

`RRA-008` caveats are per-family: a caveat naming a truncated comparison window
belongs to the comparison, not to the report. With bare codes a surface could
render that caveat under the basket section and reconcile perfectly, because the
comparison against `bundle.caveats` saw only the code. Pairing the code with its
section closes that without a new refusal reason -- the existing set comparison
now compares pairs, so a misplaced caveat fails it exactly as a missing one does.
"""

from __future__ import annotations

import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from khepri.rra.bundle import (
    REASON_CAVEAT_COVERAGE_DIFFERS,
    SECTION_BASKET,
    SECTION_COMPARISON,
    SECTION_OVERVIEW,
    BundleRefused,
    ReportBundle,
    StatedCaveat,
    reconcile,
)
from khepri.rra.facts import CAVEAT_BUCKETS_TRUNCATED
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.wording import caveat_prose
from tests.test_rra006_bundle import language_of, package, surface_of


def bundle_of() -> ReportBundle:
    return ReportBundle.of(package())


def rescoped(bundle: ReportBundle, section: str | None) -> tuple[StatedCaveat, ...]:
    return tuple(replace(caveat, section=section) for caveat in bundle.caveats)


def bend(
    bundle: ReportBundle,
    caveats: tuple[StatedCaveat, ...],
    *,
    both: bool = False,
) -> object:
    """A faithful surface with its caveats bent, in Arabic alone or in both."""
    return surface_of(
        bundle,
        languages=(
            language_of(bundle, LANGUAGE_ARABIC, caveats=caveats),
            language_of(
                bundle,
                LANGUAGE_ENGLISH,
                caveats=caveats if both else None,
            ),
        ),
    )


@pytest.mark.parametrize(
    ("section", "expected"),
    [
        pytest.param(None, None, id="report-level-carries-no-section"),
        pytest.param(SECTION_COMPARISON, SECTION_COMPARISON, id="scoped-to-a-family"),
    ],
)
def test_a_caveat_carries_the_section_it_qualifies(
    section: str | None,
    expected: str | None,
) -> None:
    assert StatedCaveat(code="window_truncated", section=section).section == expected


def test_a_section_scoped_caveat_must_name_a_governed_section() -> None:
    with pytest.raises(ValueError):
        StatedCaveat(code="window_truncated", section="invented")


def test_every_rra004_caveat_is_report_level() -> None:
    # They qualify the dataset rather than one analysis: a currency that was
    # never declared is not a fact about the comparison.
    #
    # The RRA-008 families have since arrived and do bring section-scoped caveats,
    # so this is now a statement about the package's own codes rather than about
    # every caveat a bundle carries. Asserting the latter would have made the
    # arrival of the families look like a regression.
    source = package()
    bundle = ReportBundle.of(source)
    assert source.caveats
    report_level = {
        caveat.code for caveat in bundle.caveats if caveat.section is None
    }
    assert set(source.caveats) <= report_level

    scoped = {caveat.code for caveat in bundle.caveats if caveat.section is not None}
    assert scoped.isdisjoint(set(source.caveats))


def test_a_familys_caveat_is_scoped_to_the_section_that_derived_it() -> None:
    # The other half of the rule above, and the reason pairing exists at all: a
    # caveat about one analysis may not arrive report-level, or a reader is told
    # the whole dataset is qualified by it.
    bundle = bundle_of()
    scoped = [caveat for caveat in bundle.caveats if caveat.section is not None]
    assert scoped
    for caveat in scoped:
        assert caveat.section in bundle.section_ids


def test_the_caveat_document_carries_the_pair() -> None:
    assert StatedCaveat(code="rows_redacted", section=SECTION_BASKET).as_document() == {
        "code": "rows_redacted",
        "section": SECTION_BASKET,
    }


def test_a_faithful_surface_reconciles_its_caveats() -> None:
    bundle = bundle_of()
    reconcile(surface_of(bundle), bundle=bundle)


# Every way a surface can misstate a caveat, and the one reason all of them earn.
#
# No new refusal reason was needed for any of this, which is the design's claim:
# the existing comparison against `bundle.caveats` now compares pairs, so moving
# a caveat fails it exactly as dropping one already did.
#
#   * moved to a section it does not qualify -- every code still matches, and the
#     reader attributes a caveat to the wrong analysis
#   * scoped when the bundle left it report-level -- telling the reader one
#     analysis is qualified when the whole dataset is
#   * dropped -- the failure the flat tuple already caught, which pairing must
#     not lose
MISSTATED_CAVEATS = [
    pytest.param(
        lambda bundle: (rescoped(bundle, SECTION_BASKET), False),
        id="moved-to-a-section-it-does-not-qualify",
    ),
    pytest.param(
        lambda bundle: (rescoped(bundle, SECTION_OVERVIEW), True),
        id="scoped-when-the-bundle-left-it-report-level",
    ),
    pytest.param(
        lambda bundle: (bundle.caveats[:-1], False),
        id="dropped-from-one-language",
    ),
]


@pytest.mark.parametrize("prepare", MISSTATED_CAVEATS)
def test_a_misstated_caveat_refuses(prepare: object) -> None:
    bundle = bundle_of()
    caveats, both = prepare(bundle)  # type: ignore[operator]
    with pytest.raises(BundleRefused) as refused:
        reconcile(bend(bundle, caveats, both=both), bundle=bundle)
    assert str(refused.value) == REASON_CAVEAT_COVERAGE_DIFFERS


def test_a_caveat_may_not_be_scoped_to_a_section_the_bundle_never_declared() -> None:
    # The vocabulary says the name exists, not that this report has that
    # section. A caveat scoped to an absent one has no heading to be rendered
    # under, so a surface drops it or misfiles it -- and it still reconciles,
    # because reconciliation compares the pair against the bundle, not the page.
    # Built by hand rather than from a package: every family now either states or
    # refuses, so `ReportBundle.of` always declares all five sections and no real
    # package can produce the absent one this rule guards against.
    bundle = replace(
        bundle_of(),
        figures=(),
        caveats=(),
        sections=(),
    )
    assert SECTION_COMPARISON not in bundle.section_ids
    with pytest.raises(ValueError):
        replace(
            bundle,
            caveats=(StatedCaveat(code="window_truncated", section=SECTION_COMPARISON),),
        )


def test_a_caveat_scoped_to_a_declared_section_is_accepted() -> None:
    bundle = bundle_of()
    scoped = replace(
        bundle,
        caveats=(StatedCaveat(code="window_truncated", section=SECTION_OVERVIEW),),
    )
    assert scoped.caveats[0].section == SECTION_OVERVIEW


@pytest.mark.parametrize(
    "render",
    [
        pytest.param(
            lambda bundle: HtmlReportRenderer().render_html(bundle),
            id="web",
        ),
        pytest.param(
            lambda bundle: ExcelSurfaceRenderer(
                directory=Path(tempfile.mkdtemp())
            ).render(bundle),
            id="workbook",
        ),
    ],
)
def test_a_surface_places_a_scoped_caveat_rather_than_refusing_it(
    render: object,
) -> None:
    # This test used to assert the opposite. Both surfaces refused a scoped caveat
    # because each had one caveats heading, and both options open to them
    # misinformed: under the report's heading it says the whole dataset is
    # qualified, and omitted it drops a caveat RRA-008 requires while the claim
    # still carries it -- which passes reconciliation, because that compares the
    # claim against the bundle and never against the page.
    #
    # Refusing was the honest answer only while neither surface could place one.
    # The per-section slice arrived, so refusing now would reject every report the
    # four families produce. The page renders a scoped caveat inside its own
    # section; the workbook names the section in the cell beside the code until the
    # per-section sheet slice moves it onto that sheet.
    scoped = replace(
        bundle_of(),
        caveats=(
            StatedCaveat(
                code=CAVEAT_BUCKETS_TRUNCATED,
                section=SECTION_OVERVIEW,
            ),
        ),
    )
    rendered = render(scoped)  # type: ignore[operator]
    assert rendered is not None


def test_the_page_places_a_scoped_caveat_inside_the_section_it_qualifies() -> None:
    # The positive claim behind the inversion above. Under the report's own
    # heading would tell a reader the whole dataset is qualified.
    scoped = replace(
        bundle_of(),
        caveats=(
            StatedCaveat(
                code=CAVEAT_BUCKETS_TRUNCATED,
                section=SECTION_OVERVIEW,
            ),
        ),
    )
    page = HtmlReportRenderer().render_html(scoped).documents[LANGUAGE_ENGLISH]

    section_at = page.index(f'<section id="{SECTION_OVERVIEW}"')
    caveats_at = page.index('<section id="caveats"')
    prose_at = page.index(
        caveat_prose(CAVEAT_BUCKETS_TRUNCATED, LANGUAGE_ENGLISH)
    )
    assert section_at < prose_at < caveats_at
