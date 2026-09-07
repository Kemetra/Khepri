"""The ordered pair `rra008.crossversion.v1` compares, and the period rule it applies.

`C1-01` is the period model and nothing else: which two dataset versions may be
named as a pair, in which order, and whether their two periods are comparable as
stated. It states no delta and reads no fact -- `C1-02` detects incompatibility
across the other five predicates and `C1-03` builds the package.

Every rule asserted here is quoted from `RRA-008` §Two-population comparison,
frozen by `G4-04` §Frozen contracts. Three of them exist because a plausible
implementation gets them backwards:

**The pair is ordered, and the order is an input.** §Operand order: "the
requesting slice states which, and this specification does not infer it from
sealing time, identifier, or period." A model that sorted the pair -- by date, by
identifier, by anything -- would silently flip the sign of every delta built on
it, and both orders would look correct.

**A natural calendar length difference is not a refusal.** §Period rule inherits
§Period comparison's rule that "natural calendar length differences, including
28-, 29-, 30-, and 31-day months, do not make otherwise complete full periods
incompatible." February against March is the ordinary case. An implementation that
compared lengths would refuse it.

**The prefix concession does not cross versions.** §Period rule declines it
because it "would require reconciling two coverage manifests, which no active
artifact authorizes", so `D-6` requires both periods complete. An incomplete
period refuses here even though the same shape is admissible within one
population.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from khepri.rra.analysis.dataset_period import (
    GRANULARITY_DAY,
    GRANULARITY_MONTH,
    DatasetPeriod,
    UnorderedPairRefused,
    VersionPair,
    periods_comparable,
)


def _month(year: int, month: int, last_day: int) -> DatasetPeriod:
    """One complete, month-granular period with no retail-day offset.

    The comparable case, and the only constructor in this file. A test that needs
    an incomparable period derives it with `replace`, naming the single field it
    changes -- which keeps the reason a test refuses the only thing visible in it.

    `#401` went through two worse shapes first: four near-identical inline
    constructions (CodeScene: Code Duplication), then one helper with seven
    keywords (CodeScene: Excess Number of Function Arguments). `replace` on a
    frozen dataclass needs neither.
    """
    return DatasetPeriod(
        dataset_version_id=f"dsv_{year:04d}{month:02d}",
        start=date(year, month, 1),
        end=date(year, month, last_day),
        granularity=GRANULARITY_MONTH,
        retail_day_start_hour=0,
        complete=True,
    )


FEBRUARY = _month(2026, 2, 28)
MARCH = _month(2026, 3, 31)


class TestOrderedPair:
    """§Operand order: the order is stated by the caller, never derived."""

    def test_pair_keeps_the_order_it_was_given(self) -> None:
        pair = VersionPair(subject=MARCH, baseline=FEBRUARY)

        assert pair.subject is MARCH
        assert pair.baseline is FEBRUARY

    def test_reversed_pair_is_a_different_pair(self) -> None:
        forward = VersionPair(subject=MARCH, baseline=FEBRUARY)
        reversed_ = VersionPair(subject=FEBRUARY, baseline=MARCH)

        assert forward != reversed_

    def test_pair_does_not_reorder_by_date(self) -> None:
        """An earlier subject against a later baseline is legal and preserved."""
        pair = VersionPair(subject=FEBRUARY, baseline=MARCH)

        assert pair.subject.start < pair.baseline.start

    def test_naming_one_version_twice_refuses_as_unordered(self) -> None:
        with pytest.raises(UnorderedPairRefused) as refused:
            VersionPair(subject=MARCH, baseline=MARCH)

        assert refused.value.cause == "unordered pair"


class TestPeriodRule:
    """§Period rule: compared as stated, never aligned."""

    def test_natural_calendar_length_difference_is_admitted(self) -> None:
        """28 days against 31 is UC-1's ordinary case, not a refusal."""
        assert periods_comparable(VersionPair(subject=MARCH, baseline=FEBRUARY)) is None

    def test_differing_granularity_refuses(self) -> None:
        daily = replace(MARCH, granularity=GRANULARITY_DAY)

        assert periods_comparable(VersionPair(subject=daily, baseline=FEBRUARY)) == (
            "granularity mismatch"
        )

    def test_differing_retail_day_boundary_refuses(self) -> None:
        shifted = replace(MARCH, retail_day_start_hour=6)

        assert periods_comparable(VersionPair(subject=shifted, baseline=FEBRUARY)) == (
            "retail day boundary mismatch"
        )

    def test_incomplete_subject_refuses(self) -> None:
        """`D-6` requires both complete; the prefix concession does not cross versions."""
        partial = replace(MARCH, complete=False)

        assert periods_comparable(VersionPair(subject=partial, baseline=FEBRUARY)) == (
            "incomplete coverage"
        )

    def test_incomplete_baseline_refuses(self) -> None:
        partial = replace(FEBRUARY, complete=False)

        assert periods_comparable(VersionPair(subject=MARCH, baseline=partial)) == (
            "incomplete coverage"
        )

    def test_granularity_is_reported_before_completeness(self) -> None:
        """One stated cause per refusal, and the structural one is stated first."""
        partial_daily = replace(MARCH, granularity=GRANULARITY_DAY, complete=False)

        assert periods_comparable(VersionPair(subject=partial_daily, baseline=FEBRUARY)) == (
            "granularity mismatch"
        )


class TestNoAlignment:
    """§Period rule: no truncation, rescaling, or per-day normalization."""

    def test_model_exposes_no_alignment_helper(self) -> None:
        """A truncating helper here is how the prefix concession would leak in.

        Matched as a substring, not an exact name: the first version of this test
        compared whole names, so a `truncate_to_shorter` added as a mutant passed
        it. A guard that cannot fail against the defect it names is not a guard.
        """
        import khepri.rra.analysis.dataset_period as module

        forbidden = ("truncat", "align", "rescal", "normali")
        exported = [name for name in dir(module) if not name.startswith("_")]

        offending = [name for name in exported if any(word in name.lower() for word in forbidden)]
        assert offending == []

    def test_period_reports_its_own_day_count_without_comparing(self) -> None:
        assert FEBRUARY.days == 28
        assert MARCH.days == 31
