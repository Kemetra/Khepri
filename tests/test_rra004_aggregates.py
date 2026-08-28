from __future__ import annotations

from datetime import date
from decimal import Decimal

from khepri.rra.aggregates import (
    GRANULARITY_DAY,
    GRANULARITY_MONTH,
    MAX_COMPARISON_BUCKETS,
    OTHER_BUCKET_LABEL,
    REDACTION_SENTINEL,
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


def test_a_redacted_bucket_never_yields_its_label_to_a_source_value() -> None:
    comparison = build_comparison(
        dimension="category",
        keys=["buyer@example.com", "redacted 1"],
        values=[Decimal("1.00"), Decimal("2.00")],
        display=lambda value: (
            REDACTION_SENTINEL if "@" in value else value
        ),
    )

    labels = {bucket.value: bucket.label for bucket in comparison.buckets}
    # The personal value keeps the plain generated label; the ordinary source
    # value spelled the same way is the one pushed aside.
    assert labels[Decimal("1.00")] == "redacted 1"
    assert labels[Decimal("2.00")].startswith("redacted 1 (")
    assert len(set(labels.values())) == 2


def test_colliding_discriminators_still_produce_distinct_labels() -> None:
    # Both sanitize to "Online" and share the six-hex discriminator 93f4f2.
    comparison = build_comparison(
        dimension="channel",
        keys=["Online*<@", "Online~\\>"],
        values=[Decimal("1.00"), Decimal("2.00")],
        display=lambda value: "Online",
    )

    labels = [bucket.label for bucket in comparison.buckets]
    assert comparison.distinct_values == 2
    assert len(set(labels)) == 2
    assert sum(bucket.value for bucket in comparison.buckets) == Decimal("3.00")


def test_an_ordinal_suffix_never_collides_with_a_literal_source_label() -> None:
    # The first two share the discriminator 93f4f2, so the loser becomes
    # "Online (93f4f2) #2" -- which the third value spells literally.
    comparison = build_comparison(
        dimension="channel",
        keys=["Online*<@", "Online~\\>", "Online (93f4f2) #2"],
        values=[Decimal("1.00"), Decimal("2.00"), Decimal("3.00")],
        display=lambda value: "Online" if value.startswith("Online*") or value.startswith(
            "Online~"
        ) else value,
    )

    labels = [bucket.label for bucket in comparison.buckets]
    assert comparison.distinct_values == 3
    assert len(set(labels)) == 3
    assert sum(bucket.value for bucket in comparison.buckets) == Decimal("6.00")


def test_a_bucket_with_a_gapped_row_refuses_rather_than_publishing_a_part() -> None:
    """`RRA-004`:33 gives period and dimension revenue the headline's population.

    "Revenue, period revenue, revenue comparison" is one row of the metric
    assignment table with one population, and `RRA-004`:46 gives it "no
    partial-coverage vocabulary". A bucket holding one row with revenue and one
    without is a bucket whose own population has a gap, so summing the row that
    carried a value publishes a part as though it were the whole.

    Its neighbour is untouched: the refusal is per bucket, because each bucket is
    its own population.
    """
    series = build_series(
        dates=[date(2026, 1, 5), date(2026, 2, 6), date(2026, 2, 7)],
        values=[Decimal("100.00"), None, Decimal("50.00")],
        granularity=GRANULARITY_MONTH,
    )

    whole, gapped = series.buckets
    assert whole.value == Decimal("100.00")
    assert gapped.value is None
    # The evidence that says why, and the reason a reader is not left guessing:
    # two rows are in the bucket and neither a zero nor an absence explains it.
    assert gapped.rows == 2


def test_a_dimension_bucket_with_a_gapped_row_refuses_too() -> None:
    """The same rule, on the comparison the customer actually ranks by.

    Publishing `Snacks 50.00` beside `Beverages 100.00` states that Beverages
    outsold Snacks two to one, which the file does not say: the Snacks row
    without revenue might carry any amount at all.
    """
    comparison = build_comparison(
        dimension="category",
        keys=["Beverages", "Snacks", "Snacks"],
        values=[Decimal("100.00"), None, Decimal("50.00")],
    )

    by_label = {bucket.label: bucket for bucket in comparison.buckets}
    assert by_label["Beverages"].value == Decimal("100.00")
    assert by_label["Snacks"].value is None


def test_an_incomplete_sale_revenue_value_refuses_the_whole_curve() -> None:
    """`RRA-008`:131 -- concentration "refuses when the full distinct set cannot
    be computed".

    An admissible value carrying an unknown amount is exactly that case, and the
    refusal must be total. Dropping Snacks from the ranking instead would leave
    Beverages published as 1.0000 -- one product holding 100% of a revenue total
    that is itself partial, which is a more confident statement than the complete
    data would have supported, not a more cautious one.

    `RRA-008`:117 sets the precedent on the same kind of hole: for attach rate,
    "one missing value refuses that dimension" rather than narrowing it. And
    `RRA-004`:117 defines the basis this reconciles to as "complete sale revenue
    by **every** admissible value", so a curve over the survivors reconciles to
    no retained basis at all.

    This is distinct from the return-only exclusion above it. A value no sale
    ever carried was never in the posted-sale population, so omitting it narrows
    nothing; a gapped sale row *is* in the population, and its revenue is
    unknown rather than absent.

    The refusal surfaces as `distinct_set_uncomputable`, which is the reason
    `RRA-008`:131 names -- so no new vocabulary, and the top-decile and
    top-quartile shares read off `curve.shares` refuse with it.
    """
    comparison = build_comparison(
        dimension="category",
        keys=["Beverages", "Snacks", "Snacks"],
        values=[Decimal("100.00"), None, Decimal("50.00")],
    )

    assert comparison.curve is None
    # The buckets still publish: `#321` made each judge its own completeness, so
    # Beverages stands and Snacks refuses. Only the curve, which needs the whole
    # set to state a share, is refused here.
    by_label = {bucket.label: bucket for bucket in comparison.buckets}
    assert by_label["Beverages"].value == Decimal("100.00")
    assert by_label["Snacks"].value is None


def test_a_complete_two_value_set_still_publishes_its_curve() -> None:
    """The control: the refusal above is caused by the gap, not by the shape.

    Without this, filling `_curve` with an unconditional `return None` would pass
    the test above and every other assertion in this module that only ever looks
    at buckets.
    """
    comparison = build_comparison(
        dimension="category",
        keys=["Beverages", "Snacks", "Snacks"],
        values=[Decimal("100.00"), Decimal("30.00"), Decimal("50.00")],
    )

    assert comparison.curve is not None
    assert comparison.curve.shares == (Decimal("0.5556"), Decimal("1.0000"))
    assert comparison.curve.distinct_values == 2
