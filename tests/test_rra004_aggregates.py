from __future__ import annotations

from datetime import date
from decimal import Decimal

from khepri.rra.aggregates import (
    GRANULARITY_DAY,
    GRANULARITY_MONTH,
    MAX_COMPARISON_BUCKETS,
    OTHER_BUCKET_LABEL,
    UNLABELLED_BUCKET_LABEL,
    Bucket,
    build_comparison,
    build_series,
    granularity_for,
    period_label,
    reconciles,
)


def test_granularity_switches_to_months_only_past_the_documented_span() -> None:
    short = [date(2026, 1, 1), date(2026, 3, 1)]
    long_span = [date(2026, 1, 1), date(2026, 6, 1)]

    assert granularity_for(short) == GRANULARITY_DAY
    assert granularity_for(long_span) == GRANULARITY_MONTH
    assert granularity_for([]) == GRANULARITY_DAY


def test_period_labels_are_stable_for_each_granularity() -> None:
    assert period_label(date(2026, 1, 5), GRANULARITY_DAY) == "2026-01-05"
    assert period_label(date(2026, 1, 5), GRANULARITY_MONTH) == "2026-01"


def test_series_orders_periods_and_sums_exactly() -> None:
    series = build_series(
        dates=[date(2026, 1, 6), date(2026, 1, 5), date(2026, 1, 6)],
        revenues=[Decimal("1.10"), Decimal("2.20"), Decimal("3.30")],
        units=[1, 2, 3],
        granularity=GRANULARITY_DAY,
    )

    assert [bucket.label for bucket in series.buckets] == ["2026-01-05", "2026-01-06"]
    assert [str(bucket.revenue) for bucket in series.buckets] == ["2.20", "4.40"]
    assert [bucket.units for bucket in series.buckets] == [2, 4]


def test_series_skips_rows_without_a_date() -> None:
    series = build_series(
        dates=[date(2026, 1, 5), None],
        revenues=[Decimal("1.00"), Decimal("9.00")],
        units=[1, 9],
        granularity=GRANULARITY_DAY,
    )

    assert len(series.buckets) == 1
    assert series.buckets[0].rows == 1


def test_comparison_ranks_by_revenue_then_units_then_label() -> None:
    comparison = build_comparison(
        dimension="store",
        labels=["Giza", "Cairo", "Giza"],
        revenues=[Decimal("1.00"), Decimal("5.00"), Decimal("2.00")],
        units=[1, 5, 2],
    )

    assert [bucket.label for bucket in comparison.buckets] == ["Cairo", "Giza"]
    assert comparison.distinct_values == 2
    assert comparison.truncated_values == 0


def test_comparison_gives_unlabelled_rows_their_own_bucket() -> None:
    comparison = build_comparison(
        dimension="store",
        labels=["Cairo", None],
        revenues=[Decimal("1.00"), Decimal("2.00")],
        units=[1, 2],
    )

    labels = [bucket.label for bucket in comparison.buckets]
    assert UNLABELLED_BUCKET_LABEL in labels


def test_comparison_folds_the_tail_into_one_disclosed_bucket() -> None:
    size = MAX_COMPARISON_BUCKETS + 3
    comparison = build_comparison(
        dimension="category",
        labels=[f"c{index:02d}" for index in range(size)],
        revenues=[Decimal(index + 1) for index in range(size)],
        units=[1] * size,
    )

    assert len(comparison.buckets) == MAX_COMPARISON_BUCKETS + 1
    assert comparison.buckets[-1].label == OTHER_BUCKET_LABEL
    assert comparison.truncated_values == 3
    assert comparison.buckets[-1].rows == 3


def test_measures_absent_from_every_row_stay_absent() -> None:
    comparison = build_comparison(
        dimension="store",
        labels=["Cairo"],
        revenues=[None],
        units=[None],
    )

    assert comparison.buckets[0].revenue is None
    assert comparison.buckets[0].units is None
    assert comparison.buckets[0].rows == 1


def test_reconciliation_accepts_matching_totals() -> None:
    buckets = (
        Bucket(label="a", revenue=Decimal("1.50"), units=1, rows=1),
        Bucket(label="b", revenue=Decimal("2.50"), units=3, rows=2),
    )

    assert reconciles(
        buckets,
        revenue_total=Decimal("4.00"),
        units_total=4,
        rows_total=3,
    )


def test_reconciliation_rejects_a_drifted_measure_or_row_count() -> None:
    buckets = (
        Bucket(label="a", revenue=Decimal("1.50"), units=1, rows=1),
        Bucket(label="b", revenue=Decimal("2.50"), units=3, rows=2),
    )

    assert not reconciles(
        buckets,
        revenue_total=Decimal("4.01"),
        units_total=4,
        rows_total=3,
    )
    assert not reconciles(
        buckets,
        revenue_total=Decimal("4.00"),
        units_total=5,
        rows_total=3,
    )
    assert not reconciles(
        buckets,
        revenue_total=Decimal("4.00"),
        units_total=4,
        rows_total=4,
    )
