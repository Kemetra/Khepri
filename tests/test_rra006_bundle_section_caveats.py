"""A caveat qualifies something, and which something is reconciled.

`RRA-008` caveats are per-family: a caveat naming a truncated comparison window
belongs to the comparison, not to the report. With bare codes a surface could
render that caveat under the basket section and reconcile perfectly, because the
comparison against `bundle.caveats` saw only the code. Pairing the code with its
section closes that without a new refusal reason -- the existing set comparison
now compares pairs, so a misplaced caveat fails it exactly as a missing one does.
"""

from __future__ import annotations

from dataclasses import replace

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
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
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
    # never declared is not a fact about the comparison. The four RRA-008
    # families bring their own section-scoped caveats when those slices arrive.
    bundle = bundle_of()
    assert bundle.caveats
    assert all(caveat.section is None for caveat in bundle.caveats)


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
