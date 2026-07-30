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
        values=[Decimal("1.10"), Decimal("2.20"), Decimal("3.30")],
        granularity=GRANULARITY_DAY,
    )

    assert [bucket.label for bucket in series.buckets] == ["2026-01-05", "2026-01-06"]
    assert [str(bucket.value) for bucket in series.buckets] == ["2.20", "4.40"]
    assert [bucket.rows for bucket in series.buckets] == [1, 2]


def test_series_skips_rows_without_a_date() -> None:
    series = build_series(
        dates=[date(2026, 1, 5), None],
        values=[Decimal("1.00"), Decimal("9.00")],
        granularity=GRANULARITY_DAY,
    )

    assert len(series.buckets) == 1
    assert series.buckets[0].rows == 1


def test_comparison_ranks_by_measure_then_label() -> None:
    comparison = build_comparison(
        dimension="store",
        keys=["Giza", "Cairo", "Giza"],
        values=[Decimal("1.00"), Decimal("5.00"), Decimal("2.00")],
    )

    assert [bucket.label for bucket in comparison.buckets] == ["Cairo", "Giza"]
    assert comparison.distinct_values == 2
    assert comparison.truncated_values == 0


def test_comparison_gives_unlabelled_rows_their_own_bucket() -> None:
    comparison = build_comparison(
        dimension="store",
        keys=["Cairo", None],
        values=[Decimal("1.00"), Decimal("2.00")],
    )

    assert UNLABELLED_BUCKET_LABEL in [bucket.label for bucket in comparison.buckets]


def test_comparison_folds_the_tail_into_one_disclosed_bucket() -> None:
    size = MAX_COMPARISON_BUCKETS + 3
    comparison = build_comparison(
        dimension="category",
        keys=[f"c{index:02d}" for index in range(size)],
        values=[Decimal(index + 1) for index in range(size)],
    )

    assert len(comparison.buckets) == MAX_COMPARISON_BUCKETS + 1
    assert comparison.buckets[-1].label == OTHER_BUCKET_LABEL
    assert comparison.truncated_values == 3
    assert comparison.buckets[-1].rows == 3


def test_a_measure_absent_from_every_row_stays_absent() -> None:
    comparison = build_comparison(
        dimension="store",
        keys=["Cairo"],
        values=[None],
    )

    assert comparison.buckets[0].value is None
    assert comparison.buckets[0].rows == 1


def test_reconciliation_accepts_matching_totals() -> None:
    buckets = (
        Bucket(label="a", value=Decimal("1.50"), rows=1),
        Bucket(label="b", value=Decimal("2.50"), rows=2),
    )

    assert reconciles(buckets, total=Decimal("4.00"), rows_total=3)


def test_reconciliation_rejects_a_drifted_measure_or_row_count() -> None:
    buckets = (
        Bucket(label="a", value=Decimal("1.50"), rows=1),
        Bucket(label="b", value=Decimal("2.50"), rows=2),
    )

    assert not reconciles(buckets, total=Decimal("4.01"), rows_total=3)
    assert not reconciles(buckets, total=Decimal("4.00"), rows_total=4)


def test_reconciliation_rejects_values_that_should_be_absent() -> None:
    present = (Bucket(label="a", value=Decimal("1.50"), rows=1),)
    absent = (Bucket(label="a", value=None, rows=1),)

    assert not reconciles(present, total=None, rows_total=1)
    assert reconciles(absent, total=None, rows_total=1)


def test_distinct_values_that_share_a_display_label_are_never_merged() -> None:
    comparison = build_comparison(
        dimension="channel",
        keys=["=Online", "Online"],
        values=[Decimal("1.00"), Decimal("2.00")],
        display=lambda value: value.lstrip("="),
    )

    assert comparison.distinct_values == 2
    assert len(comparison.buckets) == 2
    assert sum(bucket.value for bucket in comparison.buckets) == Decimal("3.00")
    labels = [bucket.label for bucket in comparison.buckets]
    assert len(set(labels)) == 2
    assert all(label.startswith("Online (") for label in labels)


def test_labels_that_do_not_collide_keep_their_plain_display_text() -> None:
    comparison = build_comparison(
        dimension="channel",
        keys=["=Online", "Retail"],
        values=[Decimal("1.00"), Decimal("2.00")],
        display=lambda value: value.lstrip("="),
    )

    assert sorted(bucket.label for bucket in comparison.buckets) == ["Online", "Retail"]


def test_a_source_value_never_occupies_a_reserved_bucket_label() -> None:
    comparison = build_comparison(
        dimension="store",
        keys=[OTHER_BUCKET_LABEL, UNLABELLED_BUCKET_LABEL, None],
        values=[Decimal("1.00"), Decimal("2.00"), Decimal("3.00")],
    )

    labels = {bucket.label for bucket in comparison.buckets}
    assert comparison.distinct_values == 3
    assert len(labels) == 3
    assert UNLABELLED_BUCKET_LABEL in labels
    assert OTHER_BUCKET_LABEL not in labels


def test_a_truncated_remainder_is_distinguishable_from_a_source_named_other() -> None:
    size = MAX_COMPARISON_BUCKETS + 2
    keys = [OTHER_BUCKET_LABEL, *(f"c{index:02d}" for index in range(size))]
    values = [Decimal(1000), *(Decimal(index + 1) for index in range(size))]

    comparison = build_comparison(dimension="category", keys=keys, values=values)

    labels = [bucket.label for bucket in comparison.buckets]
    assert labels.count(OTHER_BUCKET_LABEL) == 1
    assert comparison.buckets[-1].label == OTHER_BUCKET_LABEL
    assert labels[0].startswith(f"{OTHER_BUCKET_LABEL} (")
    assert len(set(labels)) == len(labels)
    assert sum(bucket.value for bucket in comparison.buckets) == sum(values)
