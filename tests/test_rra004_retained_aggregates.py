"""The five items the `RRA-004` amendment (`APP-014`) requires the package to keep.

Three are retained values that construction already computes and then discards: the
ranked share curve over the full distinct set, distinct transaction counts, and the
dates a time bucket covers. Two are recordings: the governed comparison window
length, and the formula version as a field a serialized fact discloses rather than
only as an input to its identifier.

Every test here fails against `rra004.package.v1` for a reason no implementation
could fix without the amendment -- the values are gone by the time anything can ask
for them.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.aggregates import MAX_COMPARISON_BUCKETS, OTHER_BUCKET_LABEL
from khepri.rra.facts import (
    COMPARISON_WINDOW_PERIODS,
    METRIC_REVENUE,
    PACKAGE_VERSION,
    AdmittedInput,
    FactPackage,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import SEMANTIC_PRODUCT, build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import (
    PUBLISHED_FORMULA_VERSION,
    TEST_CONTRACT,
    published_mapping_identity,
)

# Two products, four rows, two invoices, two dates. Deliberately not a row count:
# Water sits in three rows and two invoices, so a row count would report three.
GOLDEN = (
    b"date,revenue,units,invoice_no,product\n"
    b"2026-01-05,100.00,3,INV-1,Water\n"
    b"2026-01-05,50.00,2,INV-1,Juice\n"
    b"2026-01-06,200.00,5,INV-2,Water\n"
    b"2026-01-06,50.00,1,INV-2,Water\n"
)


def package(content: bytes) -> FactPackage:
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    # Built under the published mapping identity: this module's subject is not
    # the version gate, so its packages must keep combining a triple
    # `versions.ADMITTED_PACKAGE_PAIRS` admits. The whole build sits inside the
    # block because `facts._assert_derived_from_profile` re-derives the mapping
    # and compares it by value, so restamping the object afterwards would fail
    # that provenance guard instead.
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
        )


def wide_source(distinct_products: int) -> bytes:
    """One row per product, revenue descending, so the rank order is known.

    More products than `MAX_COMPARISON_BUCKETS` so the display truncates while the
    curve must not: that gap is the whole point of the retained aggregate.
    """
    header = b"date,revenue,units,invoice_no,product\n"
    rows = [
        f"2026-01-05,{(distinct_products - index) * 10}.00,1,INV-{index},P{index:03d}\n".encode()
        for index in range(distinct_products)
    ]
    return header + b"".join(rows)


def test_package_version_moves_to_the_amended_shape() -> None:
    """`V-package` publishes `rra004.package.v3`, and this is the assertion.

    **The two halves say different things, and keeping them apart is the point.**
    `PACKAGE_VERSION` is what this build *publishes*. The package's own
    `package_version` is what that object *combines* -- and every package this
    module builds is pinned to the published predecessor triple, because its
    subject is retained aggregates rather than the version gate. Collapsing the
    two is the defect `facts._build` was corrected for: it read the module
    constant while checking a mapping the caller supplied.
    """
    assert PACKAGE_VERSION == "rra004.package.v3"
    assert package(GOLDEN).package_version == "rra004.package.v2"


def test_every_fact_discloses_the_formula_version_that_produced_it() -> None:
    """A hashed version names a fact; it cannot be read back off one.

    `fact_identity` mixes the formula version into the identifier, which makes two
    versions produce different ids but leaves a stored citation unable to say which
    formula produced the number it cites. That is the provenance `RRA-008` requires
    and hashing does not supply.
    """
    result = package(GOLDEN)

    assert result.facts
    # The pinned predecessor throughout: this module builds under the admitted
    # triple, so what its facts combine is not what this build publishes.
    for fact in result.facts:
        assert fact.formula_version == PUBLISHED_FORMULA_VERSION
        assert fact.as_document()["formula_version"] == PUBLISHED_FORMULA_VERSION

    for entry in (*result.series, *result.comparisons):
        assert entry.formula_version == PUBLISHED_FORMULA_VERSION
        assert entry.as_document()["formula_version"] == PUBLISHED_FORMULA_VERSION


def test_package_records_the_governed_comparison_window() -> None:
    """One period, recorded rather than chosen by whichever module needs it.

    An earlier comparison revision took half the available history as its window,
    so prepending old rows changed a reported delta while recent rows were
    identical. A window length the package states cannot drift per derivation.
    """
    assert COMPARISON_WINDOW_PERIODS == 1
    document = package(GOLDEN).as_document()
    assert document["comparison_window_periods"] == 1


def test_curve_ranks_the_full_distinct_set_while_the_display_truncates() -> None:
    distinct = MAX_COMPARISON_BUCKETS + 5
    result = package(wide_source(distinct))
    comparison = result.comparison(SEMANTIC_PRODUCT, METRIC_REVENUE)
    assert comparison is not None

    published = comparison.comparison
    assert published.truncated_values == 5
    assert len(published.buckets) == MAX_COMPARISON_BUCKETS + 1
    assert published.buckets[-1].label == OTHER_BUCKET_LABEL

    curve = published.curve
    assert curve is not None
    assert curve.distinct_values == distinct
    assert curve.ranked_values == distinct
    # The count that matters: 25 shares, not the 21 the display kept.
    assert len(curve.shares) == distinct


def test_curve_is_cumulative_monotonic_and_reaches_one() -> None:
    result = package(wide_source(MAX_COMPARISON_BUCKETS + 5))
    comparison = result.comparison(SEMANTIC_PRODUCT, METRIC_REVENUE)
    assert comparison is not None
    curve = comparison.comparison.curve
    assert curve is not None

    shares = curve.shares
    assert shares[0] > 0
    assert all(later >= earlier for earlier, later in zip(shares, shares[1:], strict=False))
    assert shares[-1] == Decimal(1)


def test_curve_carries_no_value_labels() -> None:
    """Shares only, because a full-set curve is not a publishable value list.

    The display truncates to twenty buckets precisely so a report cannot name
    every distinct value; a curve carrying labels would reintroduce all of them
    through the aggregate and hand a surface the list the truncation withheld.
    """
    result = package(wide_source(MAX_COMPARISON_BUCKETS + 5))
    comparison = result.comparison(SEMANTIC_PRODUCT, METRIC_REVENUE)
    assert comparison is not None
    curve = comparison.comparison.curve
    assert curve is not None

    document = curve.as_document()
    assert set(document) == {"distinct_values", "ranked_values", "shares"}
    rendered = str(document)
    assert "P000" not in rendered
    assert "Water" not in rendered


def test_bucket_counts_distinct_transactions_not_rows() -> None:
    """Water sits in three rows and two invoices. Three would be the wrong answer."""
    result = package(GOLDEN)
    comparison = result.comparison(SEMANTIC_PRODUCT, METRIC_REVENUE)
    assert comparison is not None

    by_label = {bucket.label: bucket for bucket in comparison.comparison.buckets}
    assert by_label["Water"].rows == 3
    assert by_label["Water"].transactions == 2
    assert by_label["Juice"].rows == 1
    assert by_label["Juice"].transactions == 1
    assert by_label["Water"].as_document(precision=2)["transactions"] == 2


def test_comparison_records_the_full_set_transaction_total() -> None:
    published = package(GOLDEN).comparison(SEMANTIC_PRODUCT, METRIC_REVENUE)
    assert published is not None
    # Two invoices across four rows, counted once each across the whole set. Summing
    # the buckets would report three, because INV-1 holds both Water and Juice.
    assert published.comparison.distinct_transactions == 2
    assert published.comparison.as_document(precision=2)["distinct_transactions"] == 2


def test_truncated_remainder_counts_transactions_distinctly() -> None:
    """`other` unions its transactions; summing them would double-count.

    Every dropped value here shares one invoice, so a sum reports five and the
    truth is one. Aggregating a distinct count by addition is the same error as
    substituting a row count, one level up.
    """
    header = b"date,revenue,units,invoice_no,product\n"
    kept = [
        f"2026-01-05,{(100 - index)}.00,1,INV-K{index},K{index:03d}\n".encode()
        for index in range(MAX_COMPARISON_BUCKETS)
    ]
    dropped = [
        f"2026-01-05,1.00,1,INV-SHARED,D{index:03d}\n".encode() for index in range(5)
    ]
    published = package(header + b"".join(kept) + b"".join(dropped)).comparison(
        SEMANTIC_PRODUCT,
        METRIC_REVENUE,
    )
    assert published is not None

    remainder = published.comparison.buckets[-1]
    assert remainder.label == OTHER_BUCKET_LABEL
    assert remainder.rows == 5
    assert remainder.transactions == 1


def test_time_bucket_records_the_dates_it_covers() -> None:
    """Per-period completeness, which nothing could previously tell.

    The comparison excludes the period at each end because a partial period is
    indistinguishable from a whole one, and its truncation caveat therefore has no
    reachable trigger. A day count is what makes both derivable.
    """
    trend = package(GOLDEN).trend(METRIC_REVENUE)
    assert trend is not None

    by_label = {bucket.label: bucket for bucket in trend.series.buckets}
    assert by_label["2026-01-05"].rows == 2
    assert by_label["2026-01-05"].days == 1
    assert by_label["2026-01-06"].days == 1
    assert by_label["2026-01-05"].as_document(precision=2)["days"] == 1


def test_transaction_counts_are_absent_rather_than_guessed_when_unmapped() -> None:
    """No identifier mapped means no count, never a row count standing in."""
    unmapped = (
        b"date,revenue,units,product\n"
        b"2026-01-05,100.00,3,Water\n"
        b"2026-01-06,200.00,5,Water\n"
    )
    published = package(unmapped).comparison(SEMANTIC_PRODUCT, METRIC_REVENUE)
    assert published is not None

    assert published.comparison.distinct_transactions is None
    assert all(bucket.transactions is None for bucket in published.comparison.buckets)
