"""Period comparison over a governed trend, in both modes RRA-008 requires.

The packages here are built from real CSV bytes through the real pipeline rather
than assembled by hand. A fabricated `FactPackage` would let a test assert over
an aggregate the package builder would never produce, which is exactly the
failure this family exists to avoid.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.aggregates import GRANULARITY_DAY, GRANULARITY_MONTH
from khepri.rra.analysis import comparison
from khepri.rra.analysis.comparison import (
    CAVEAT_WINDOW_TRUNCATED,
    METRIC_DELTA_ABSOLUTE,
    METRIC_DELTA_PERCENT,
    MODE_PERIOD_OVER_PERIOD,
    MODE_YEAR_OVER_YEAR,
    REASON_PRIOR_WINDOW_ABSENT,
)
from khepri.rra.facts import FactPackage, RefusedResult, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile

HEADER = b"date,revenue,units,invoice_no,category,branch\n"


def csv_for(rows: list[tuple[date, str]]) -> bytes:
    body = b"".join(
        f"{when.isoformat()},{amount},1,INV-{index},Beverages,Cairo\n".encode()
        for index, (when, amount) in enumerate(rows)
    )
    return HEADER + body


def package_for(rows: list[tuple[date, str]]) -> FactPackage:
    content = csv_for(rows)
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


def monthly(months: int, amount: str = "100.00") -> FactPackage:
    """One row on the first of each of `months` consecutive months."""
    start = date(2024, 1, 1)
    rows = [
        (date(start.year + (start.month - 1 + offset) // 12,
              (start.month - 1 + offset) % 12 + 1, 1), amount)
        for offset in range(months)
    ]
    return package_for(rows)


def daily(days: int, amount: str = "100.00") -> FactPackage:
    start = date(2026, 1, 1)
    return package_for([(start + timedelta(days=offset), amount) for offset in range(days)])


def facts_of(package: FactPackage) -> tuple:
    result = comparison.derive(package)
    assert not isinstance(result, RefusedResult), result
    return result


def modes_for(package: FactPackage, metric: str = METRIC_DELTA_ABSOLUTE) -> set[str]:
    return {
        comparison.mode_of(fact) for fact in facts_of(package) if fact.metric == metric
    }


def test_a_month_spanning_trend_is_month_granular() -> None:
    # The premise every year-over-year assertion below rests on: a span over 92
    # days is bucketed by month, so a year earlier is twelve labels back.
    assert monthly(26).trend().series.granularity == GRANULARITY_MONTH
    assert daily(20).trend().series.granularity == GRANULARITY_DAY


def test_both_governed_modes_are_emitted() -> None:
    # RRA-008 requires period-over-period *and* year-over-year. One unnamed
    # current/prior pair satisfies neither fully.
    assert modes_for(monthly(26)) == {MODE_PERIOD_OVER_PERIOD, MODE_YEAR_OVER_YEAR}


def test_the_two_modes_carry_distinct_stable_identities() -> None:
    facts = [f for f in facts_of(monthly(26)) if f.metric == METRIC_DELTA_ABSOLUTE]
    assert len({fact.fact_id for fact in facts}) == 2
    assert len({fact.citation_id for fact in facts}) == 2


def test_identities_are_stable_across_runs_over_the_same_input() -> None:
    # Stable, not merely unique. RRA-008 requires a rerun to reach the same
    # identity, which is what makes a citation followable between reports.
    first = {fact.fact_id for fact in facts_of(monthly(26))}
    second = {fact.fact_id for fact in facts_of(monthly(26))}
    assert first == second


def test_year_over_year_refuses_alone_when_coverage_is_under_a_year() -> None:
    # Eight months has a prior period and no prior year. RRA-008 refuses the
    # affected comparison and not the report, so the other mode survives.
    package = monthly(8)
    assert modes_for(package) == {MODE_PERIOD_OVER_PERIOD}
    reasons = {refusal.reason for refusal in comparison.refusals(package)}
    assert reasons == {REASON_PRIOR_WINDOW_ABSENT}


def test_a_single_mode_refusal_is_not_a_report_refusal() -> None:
    assert not isinstance(comparison.derive(monthly(8)), RefusedResult)


def test_both_modes_refusing_refuses_the_comparison() -> None:
    # One bucket has no prior window of any kind, so there is nothing to state.
    result = comparison.derive(monthly(1))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_PRIOR_WINDOW_ABSENT


def yoy_facts(package: FactPackage) -> list:
    return [
        fact
        for fact in facts_of(package)
        if comparison.mode_of(fact) == MODE_YEAR_OVER_YEAR
    ]


def test_a_prior_year_window_short_of_the_current_one_truncates_and_caveats() -> None:
    # Fifteen months, so the seven-month current window reaches back into a
    # prior-year window that runs off the start of the series. Only three of
    # those months exist, so *both* sides are cut to those three -- the current
    # side too, or the comparison would measure seven months against three.
    facts = yoy_facts(monthly(15))
    assert facts
    assert all(CAVEAT_WINDOW_TRUNCATED in fact.caveats for fact in facts)


@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(MODE_PERIOD_OVER_PERIOD, id="period-over-period"),
        pytest.param(MODE_YEAR_OVER_YEAR, id="year-over-year"),
    ],
)
def test_a_complete_window_carries_no_truncation_caveat(mode: str) -> None:
    # The control the caveat needs to be worth anything. Twenty-six consecutive
    # months gives both modes a full prior window, so neither is shortened and
    # neither claims to have been.
    facts = [
        fact for fact in facts_of(monthly(26)) if comparison.mode_of(fact) == mode
    ]
    assert facts
    assert all(CAVEAT_WINDOW_TRUNCATED not in fact.caveats for fact in facts)


def test_the_prior_year_window_is_located_by_label_not_by_offset() -> None:
    # A month of coverage missing in the middle shifts every bucket after it. A
    # fixed twelve-bucket step would then compare the wrong months while looking
    # perfectly healthy; label arithmetic finds fewer buckets and truncates.
    intact = monthly(26)
    start = date(2024, 1, 1)
    holed = package_for(
        [
            (date(start.year + (start.month - 1 + offset) // 12,
                  (start.month - 1 + offset) % 12 + 1, 1), "100.00")
            for offset in range(26)
            if offset != 5
        ]
    )
    assert len(holed.trend().series.buckets) == len(intact.trend().series.buckets) - 1
    # The intact series has a complete prior-year window and says so. Removing
    # one month leaves the same current window pointing at a year-ago window
    # that is now one bucket short -- so it truncates and says *that*. A fixed
    # twelve-bucket step would have compared a different pair of periods and
    # reported no truncation at all, which is the silent version of being wrong.
    assert all(
        CAVEAT_WINDOW_TRUNCATED not in fact.caveats for fact in yoy_facts(intact)
    )
    assert all(CAVEAT_WINDOW_TRUNCATED in fact.caveats for fact in yoy_facts(holed))


def test_the_absolute_delta_is_exact_over_a_flat_trend() -> None:
    # Equal revenue in both windows is a zero change, to the package's own
    # precision. Computed in Decimal throughout, so it is exactly zero.
    facts = facts_of(monthly(26))
    pop = next(
        fact
        for fact in facts
        if fact.metric == METRIC_DELTA_ABSOLUTE
        and comparison.mode_of(fact) == MODE_PERIOD_OVER_PERIOD
    )
    assert Decimal(pop.value) == Decimal(0)


def test_a_zero_base_refuses_the_percentage_and_keeps_the_absolute() -> None:
    # A percentage of nothing is undefined. RRA-008 refuses it and keeps the
    # absolute, because the change itself is still a fact.
    package = package_for(
        [(date(2026, 1, 1), "0.00"), (date(2026, 1, 2), "50.00")]
    )
    metrics = {fact.metric for fact in facts_of(package)}
    assert METRIC_DELTA_ABSOLUTE in metrics
    assert METRIC_DELTA_PERCENT not in metrics


def test_a_negative_base_refuses_the_percentage() -> None:
    # A shrinking loss would read as growth. The base must be strictly positive.
    package = package_for(
        [(date(2026, 1, 1), "-50.00"), (date(2026, 1, 2), "10.00")]
    )
    metrics = {fact.metric for fact in facts_of(package)}
    assert METRIC_DELTA_PERCENT not in metrics


def test_a_positive_base_emits_the_percentage() -> None:
    package = package_for(
        [(date(2026, 1, 1), "100.00"), (date(2026, 1, 2), "150.00")]
    )
    percent = next(
        fact for fact in facts_of(package) if fact.metric == METRIC_DELTA_PERCENT
    )
    assert Decimal(percent.value) == Decimal(50)


@pytest.mark.parametrize("metric", [METRIC_DELTA_ABSOLUTE, METRIC_DELTA_PERCENT])
def test_every_emitted_fact_names_a_governed_mode(metric: str) -> None:
    facts = [fact for fact in facts_of(monthly(26)) if fact.metric == metric]
    assert facts
    assert all(comparison.mode_of(fact) is not None for fact in facts)
