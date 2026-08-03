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

from khepri.rra import facts
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.aggregates import GRANULARITY_DAY, GRANULARITY_MONTH
from khepri.rra.analysis import comparison
from khepri.rra.analysis.comparison import (
    METRIC_DELTA_ABSOLUTE,
    METRIC_DELTA_PERCENT,
    MODE_PERIOD_OVER_PERIOD,
    MODE_YEAR_OVER_YEAR,
    REASON_NEGATIVE_BASE,
    REASON_PRIOR_WINDOW_ABSENT,
)
from khepri.rra.facts import (
    CAVEAT_UNDATED_ROWS_EXCLUDED,
    REASON_INPUT_UNAVAILABLE,
    REASON_ZERO_DENOMINATOR,
    UNIT_MONETARY,
    UNIT_RATIO,
    FactPackage,
    RefusedResult,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import (
    SEMANTIC_REVENUE,
    SEMANTIC_TRANSACTION_DATE,
    build_mapping,
)
from khepri.rra.profiling import build_profile

HEADER = b"date,revenue,units,invoice_no,category,branch\n"


def package_for(rows: list[tuple[date | None, str]]) -> FactPackage:
    body = b"".join(
        f"{'' if when is None else when.isoformat()},"
        f"{amount},1,INV-{index},Beverages,Cairo\n".encode()
        for index, (when, amount) in enumerate(rows)
    )
    content = HEADER + body
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


def month_start(offset: int, *, year: int = 2024, month: int = 1) -> date:
    index = year * 12 + month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def monthly(months: int, *, skip: int | None = None) -> FactPackage:
    """One row on the first of each of `months` consecutive months.

    `skip` omits one offset, which shifts every bucket after it -- the shape that
    makes positional pairing wrong and label pairing right.
    """
    return package_for(
        [
            (month_start(offset), "100.00")
            for offset in range(months)
            if offset != skip
        ]
    )


def daily(days: int) -> FactPackage:
    start = date(2026, 1, 1)
    return package_for([(start + timedelta(days=n), "100.00") for n in range(days)])


def facts_of(package: FactPackage) -> tuple:
    result = comparison.derive(package)
    assert not isinstance(result, RefusedResult), result
    return result


def modes_for(package: FactPackage) -> set[str]:
    return {
        comparison.mode_of(fact)
        for fact in facts_of(package)
        if fact.metric == METRIC_DELTA_ABSOLUTE
    }


def window(package: FactPackage, mode: str):
    return comparison._window_for(package, mode)


def months_apart(current: str, prior: str) -> int:
    current_year, current_month = (int(part) for part in current.split("-"))
    prior_year, prior_month = (int(part) for part in prior.split("-"))
    return (current_year - prior_year) * 12 + (current_month - prior_month)


def two_settled_days(prior: str, current: str) -> FactPackage:
    """Two days to compare, plus a third so both of them have settled.

    The trailing day is never compared. It exists so the two that matter are
    periods with data after them, which is the only evidence available here that
    a period finished.
    """
    return package_for(
        [
            (date(2026, 1, 1), prior),
            (date(2026, 1, 2), current),
            (date(2026, 1, 3), "1.00"),
        ]
    )


def test_the_trend_granularity_is_what_the_labels_mean() -> None:
    # The premise every label assertion below rests on.
    assert monthly(26).trend().series.granularity == GRANULARITY_MONTH
    assert daily(20).trend().series.granularity == GRANULARITY_DAY


def test_both_governed_modes_are_emitted() -> None:
    # RRA-008 requires period-over-period *and* year-over-year. One unnamed
    # current/prior pair satisfies neither fully.
    assert modes_for(monthly(14)) == {MODE_PERIOD_OVER_PERIOD, MODE_YEAR_OVER_YEAR}


def test_the_two_modes_carry_distinct_stable_identities() -> None:
    facts = [f for f in facts_of(monthly(14)) if f.metric == METRIC_DELTA_ABSOLUTE]
    assert len({fact.fact_id for fact in facts}) == 2
    assert len({fact.citation_id for fact in facts}) == 2


def test_identities_are_stable_across_runs_over_the_same_input() -> None:
    # Stable, not merely unique. RRA-008 requires a rerun to reach the same
    # identity, which is what makes a citation followable between reports.
    assert {f.fact_id for f in facts_of(monthly(14))} == {
        f.fact_id for f in facts_of(monthly(14))
    }


# --- which two periods each mode compares -----------------------------------


@pytest.mark.parametrize(
    ("mode", "expected_gap"),
    [
        pytest.param(MODE_PERIOD_OVER_PERIOD, 1, id="the-immediately-preceding-period"),
        pytest.param(MODE_YEAR_OVER_YEAR, 12, id="the-same-period-a-year-earlier"),
    ],
)
def test_each_mode_compares_the_period_its_name_says(mode: str, expected_gap: int) -> None:
    found = window(monthly(26), mode)
    assert found is not None
    assert months_apart(found.current.label, found.prior.label) == expected_gap


@pytest.mark.parametrize(
    ("mode", "expected_gap"),
    [
        pytest.param(MODE_PERIOD_OVER_PERIOD, 1, id="period-over-period"),
        pytest.param(MODE_YEAR_OVER_YEAR, 12, id="year-over-year"),
    ],
)
def test_a_gap_in_coverage_does_not_move_which_periods_are_compared(
    mode: str,
    expected_gap: int,
) -> None:
    # A missing month shifts every bucket after it, so pairing by position would
    # silently substitute a neighbour: with January, March, April and May in the
    # series, April's predecessor *by position* is January. Every label still
    # looks plausible and every sum is correct, which is what makes it dangerous.
    found = window(monthly(26, skip=5), mode)
    assert found is not None
    assert months_apart(found.current.label, found.prior.label) == expected_gap


def test_a_missing_counterpart_refuses_rather_than_substituting_a_neighbour() -> None:
    # The period right before the compared one is absent, so there is nothing to
    # compare against. It refuses rather than reaching one further back, which is
    # what positional pairing would have done.
    package = monthly(26, skip=23)
    labels = [bucket.label for bucket in package.trend().series.buckets]
    assert "2025-12" not in labels
    assert "2026-01" in labels
    found = window(package, MODE_PERIOD_OVER_PERIOD)
    assert found is None
    # The other mode is unaffected: a year before 2026-01 is present.
    assert window(package, MODE_YEAR_OVER_YEAR) is not None


@pytest.mark.parametrize("months", [14, 26, 38, 62])
def test_the_compared_periods_never_overlap_however_long_the_history(months: int) -> None:
    # An earlier revision took half the available history as the window, which at
    # 37 settled months produced an 18-month year-over-year comparison whose two
    # windows overlapped by six months -- a period compared partly against itself.
    for mode in (MODE_PERIOD_OVER_PERIOD, MODE_YEAR_OVER_YEAR):
        found = window(monthly(months), mode)
        assert found is not None
        assert found.current.label != found.prior.label


def test_older_history_does_not_change_which_periods_are_compared() -> None:
    # The same recent data must give the same answer however much history sits
    # behind it. A window derived from total coverage failed this: prepending old
    # rows moved the boundary and changed the reported delta.
    short = window(monthly(14), MODE_YEAR_OVER_YEAR)
    long = window(monthly(14 + 24), MODE_YEAR_OVER_YEAR)
    assert months_apart(short.current.label, short.prior.label) == 12
    assert months_apart(long.current.label, long.prior.label) == 12


# --- what settles, and what refuses -----------------------------------------


def test_the_final_period_is_left_out_because_its_completeness_is_unknown() -> None:
    # Three days of data compare the second against the first; the third is
    # excluded, because nothing in the series says whether it was cut off partway
    # by wherever the export ended.
    package = two_settled_days("100.00", "150.00")
    assert len(package.trend().series.buckets) == 3
    absolute = next(
        fact for fact in facts_of(package) if fact.metric == METRIC_DELTA_ABSOLUTE
    )
    assert Decimal(absolute.value) == Decimal(50)


def test_one_settled_period_has_nothing_to_compare() -> None:
    result = comparison.derive(
        package_for([(date(2026, 1, 1), "100.00"), (date(2026, 1, 2), "150.00")])
    )
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_PRIOR_WINDOW_ABSENT


def test_year_over_year_refuses_alone_when_coverage_is_under_a_year() -> None:
    # Thirteen months leaves twelve settled, so the latest has a predecessor and
    # no counterpart a year back. RRA-008 refuses the affected comparison and not
    # the report, so the other mode survives.
    package = monthly(13)
    assert modes_for(package) == {MODE_PERIOD_OVER_PERIOD}
    assert REASON_PRIOR_WINDOW_ABSENT in {
        refusal.reason for refusal in comparison.refusals(package)
    }


def test_a_single_mode_refusal_is_not_a_report_refusal() -> None:
    assert not isinstance(comparison.derive(monthly(13)), RefusedResult)


def test_both_modes_refusing_refuses_the_comparison() -> None:
    result = comparison.derive(monthly(1))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_PRIOR_WINDOW_ABSENT


def test_a_leap_day_has_no_counterpart_and_refuses() -> None:
    # 29 February a year earlier is not a date. The nearest day is a different
    # day, and substituting one would state a comparison nobody asked for.
    assert comparison._year_earlier_label("2024-02-29", GRANULARITY_DAY) is None
    assert comparison._year_earlier_label("2024-02-28", GRANULARITY_DAY) == "2023-02-28"


# --- what each fact says ----------------------------------------------------


def test_the_percentage_delta_is_a_fraction_not_a_percentage() -> None:
    # UNIT_RATIO already means a fraction here: gross_margin stores one, and
    # narrative multiplies every ratio by a hundred to render it. Storing 50 for
    # a rise from 100 to 150 would reach a reader as 5000%.
    percent = next(
        fact
        for fact in facts_of(two_settled_days("100.00", "150.00"))
        if fact.metric == METRIC_DELTA_PERCENT
    )
    assert percent.unit_kind == UNIT_RATIO
    assert Decimal(percent.value) == Decimal("0.5")


def test_the_absolute_delta_is_monetary() -> None:
    absolute = next(
        fact
        for fact in facts_of(two_settled_days("100.00", "150.00"))
        if fact.metric == METRIC_DELTA_ABSOLUTE
    )
    assert absolute.unit_kind == UNIT_MONETARY


@pytest.mark.parametrize(
    ("prior", "reason"),
    [
        pytest.param("0.00", REASON_ZERO_DENOMINATOR, id="a-base-of-zero"),
        pytest.param("-50.00", REASON_NEGATIVE_BASE, id="a-negative-base"),
    ],
)
def test_a_non_positive_base_refuses_the_percentage_and_records_it(
    prior: str,
    reason: str,
) -> None:
    # A percentage of zero is undefined and of a negative base it misleads: a
    # shrinking loss reads as growth. The absolute delta stands either way, and
    # the refusal is recorded -- a consumer must be able to tell a governed
    # refusal from a metric quietly left out.
    package = two_settled_days(prior, "10.00")
    metrics = {fact.metric for fact in facts_of(package)}
    assert METRIC_DELTA_ABSOLUTE in metrics
    assert METRIC_DELTA_PERCENT not in metrics
    recorded = comparison.refusals(package)
    assert reason in {refusal.reason for refusal in recorded}
    assert any(METRIC_DELTA_PERCENT in refusal.metric for refusal in recorded)


def test_every_fact_declares_the_governed_measures_it_came_from() -> None:
    # `Fact.inputs` holds semantic measures. A formula version here would
    # mislabel a version string as provenance and leave the fact declaring no
    # measure at all. The date is an input too: it decides which period a row
    # lands in, and so which two periods are compared.
    for fact in facts_of(monthly(14)):
        assert fact.inputs == (SEMANTIC_TRANSACTION_DATE, SEMANTIC_REVENUE)


def test_a_refusal_names_the_reason_the_mode_actually_gave() -> None:
    # The compared period has no revenue at all while its neighbours do, so both
    # counterpart windows exist and the measure is what is missing. Reporting
    # prior_window_absent would explain the refusal wrongly: the window was
    # there.
    package = package_for(
        [
            (date(2026, 1, 1), "100.00"),
            (date(2026, 1, 2), ""),
            (date(2026, 1, 3), "1.00"),
        ]
    )
    result = comparison.derive(package)
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_INPUT_UNAVAILABLE


def test_a_derived_fact_inherits_the_caveats_of_the_series_it_read() -> None:
    # The trend excluded rows with no date, which is a limitation of the
    # aggregate these deltas are derived from. RRA-008 requires every derived
    # fact reconciled to its source aggregate, so a delta that dropped the
    # caveat would be presented as covering rows the aggregate never saw.
    package = package_for(
        [
            (date(2026, 1, 1), "100.00"),
            (date(2026, 1, 2), "150.00"),
            (date(2026, 1, 3), "1.00"),
        ]
        + [(None, "5.00")]
    )
    assert CAVEAT_UNDATED_ROWS_EXCLUDED in package.trend().caveats
    facts = facts_of(package)
    assert facts
    assert all(CAVEAT_UNDATED_ROWS_EXCLUDED in fact.caveats for fact in facts)


def test_a_high_magnitude_ratio_does_not_abort_the_comparison() -> None:
    # A valid package can hold values large enough that the ratio against a small
    # prior period needs more than Python's default 28 digits. Under that context
    # `quantize` raises InvalidOperation and takes the caller down -- neither a
    # fact nor a governed refusal. The derivation borrows the package's own
    # arithmetic precision, which is what `build_fact_package` computes under.
    # Every value here is admissible: 18 digits is the governed maximum and six
    # decimal places the governed monetary maximum. Four hundred such rows against
    # a millionth-scale prior period is enough to need 29 digits, which is one
    # more than the default context allows.
    largest = "9" * 16 + ".99"
    package = package_for(
        [
            (date(2026, 1, 1), "0.000001"),
            *[(date(2026, 1, 2), largest) for _ in range(400)],
            (date(2026, 1, 3), "1.00"),
        ]
    )
    percent = next(
        fact for fact in facts_of(package) if fact.metric == METRIC_DELTA_PERCENT
    )
    # Enormous but stated, rather than an exception escaping the module.
    assert Decimal(percent.value) > Decimal(10) ** 20


def test_the_governed_arithmetic_precision_is_the_packages_own() -> None:
    # Borrowed rather than chosen. If the bound on admissible values is ever
    # wrong, it is wrong in one place instead of two.
    assert comparison.ARITHMETIC_PRECISION == facts.ARITHMETIC_PRECISION


def test_no_fact_claims_a_caveat_this_module_cannot_reach() -> None:
    # A one-period window either has its counterpart or refuses, so there is no
    # shortened window to disclose -- and RRA-008's day-count truncation is not
    # derivable from a period series at all. A governed caveat with no reachable
    # trigger reads as a guarantee that something is being watched.
    assert all(fact.caveats == () for fact in facts_of(monthly(14)))


@pytest.mark.parametrize("metric", [METRIC_DELTA_ABSOLUTE, METRIC_DELTA_PERCENT])
def test_every_emitted_fact_names_a_governed_mode(metric: str) -> None:
    facts = [fact for fact in facts_of(monthly(14)) if fact.metric == metric]
    assert facts
    assert all(comparison.mode_of(fact) is not None for fact in facts)
