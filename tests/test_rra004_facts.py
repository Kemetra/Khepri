from __future__ import annotations

import hashlib

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.aggregates import MAX_COMPARISON_BUCKETS, OTHER_BUCKET_LABEL
from khepri.rra.facts import (
    CAVEAT_CURRENCY_NOT_DECLARED,
    CAVEAT_DUPLICATE_ROWS,
    CAVEAT_NEGATIVE_REVENUE,
    CAVEAT_NULL_MEASURE_INPUTS,
    CAVEAT_RETURNS_NOT_NETTED,
    CAVEAT_UNDATED_ROWS_EXCLUDED,
    FORMULA_VERSION,
    METRIC_AVERAGE_ORDER_VALUE,
    METRIC_AVERAGE_SELLING_PRICE,
    METRIC_COST,
    METRIC_DISCOUNT,
    METRIC_GROSS_MARGIN,
    METRIC_GROSS_PROFIT,
    METRIC_RETURNS,
    METRIC_REVENUE,
    METRIC_TRANSACTIONS,
    METRIC_UNITS,
    PACKAGE_VERSION,
    REASON_INCOMPLETE_IDENTIFIERS,
    REASON_INPUT_UNAVAILABLE,
    REASON_ZERO_DENOMINATOR,
    UNIT_COUNT,
    UNIT_MONETARY,
    UNIT_RATIO,
    FactPackage,
    FactsRefused,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import (
    SEMANTIC_CATEGORY,
    SEMANTIC_CHANNEL,
    SEMANTIC_STORE,
    build_mapping,
)
from khepri.rra.profiling import build_profile

GOLDEN = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)


def package(content: bytes) -> FactPackage:
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


def test_core_kpis_are_computed_exactly() -> None:
    result = package(GOLDEN)

    assert result.package_version == PACKAGE_VERSION
    assert result.formula_version == FORMULA_VERSION
    assert result.row_count == 4
    assert result.value(METRIC_REVENUE) == "500.00"
    assert result.value(METRIC_UNITS) == "11"
    assert result.value(METRIC_TRANSACTIONS) == "3"


def test_derived_kpis_use_exact_decimal_division() -> None:
    result = package(GOLDEN)

    assert result.value(METRIC_AVERAGE_ORDER_VALUE) == "166.67"
    assert result.value(METRIC_AVERAGE_SELLING_PRICE) == "45.45"


def test_units_are_counted_and_money_is_monetary() -> None:
    result = package(GOLDEN)

    assert result.fact(METRIC_REVENUE).unit_kind == UNIT_MONETARY
    assert result.fact(METRIC_UNITS).unit_kind == UNIT_COUNT
    assert result.fact(METRIC_TRANSACTIONS).unit_kind == UNIT_COUNT


def test_conditional_metrics_are_refused_when_inputs_are_absent() -> None:
    result = package(GOLDEN)

    for metric in (METRIC_COST, METRIC_GROSS_PROFIT, METRIC_GROSS_MARGIN):
        assert result.fact(metric) is None
        assert result.refusal(metric).reason == REASON_INPUT_UNAVAILABLE


def test_conditional_metrics_appear_when_their_inputs_exist() -> None:
    content = (
        b"date,revenue,units,unit_cost,discount,refunds\n"
        b"2026-01-05,200.00,4,120.00,10.00,1.00\n"
        b"2026-01-06,300.00,6,180.00,5.00,2.00\n"
    )

    result = package(content)

    assert result.value(METRIC_COST) == "300.00"
    assert result.value(METRIC_GROSS_PROFIT) == "200.00"
    assert result.value(METRIC_GROSS_MARGIN) == "0.4000"
    assert result.fact(METRIC_GROSS_MARGIN).unit_kind == UNIT_RATIO
    assert result.value(METRIC_DISCOUNT) == "15.00"
    assert result.value(METRIC_RETURNS) == "3.00"
    assert CAVEAT_RETURNS_NOT_NETTED in result.caveats


def test_precision_follows_the_governed_input_scale() -> None:
    content = b"date,revenue,units\n2026-01-05,10.125,1\n2026-01-06,10.125,1\n"

    result = package(content)

    assert result.monetary_precision == 3
    assert result.value(METRIC_REVENUE) == "20.250"


def test_zero_denominator_refuses_the_derived_metric() -> None:
    content = b"date,revenue,units\n2026-01-05,10.00,0\n2026-01-06,20.00,0\n"

    result = package(content)

    assert result.value(METRIC_REVENUE) == "30.00"
    assert result.fact(METRIC_AVERAGE_SELLING_PRICE) is None
    assert result.refusal(METRIC_AVERAGE_SELLING_PRICE).reason == (
        REASON_ZERO_DENOMINATOR
    )


def test_null_measure_cells_are_excluded_not_treated_as_zero() -> None:
    content = b"date,revenue,units\n2026-01-05,100.00,2\n2026-01-06,,3\n"

    result = package(content)

    assert result.value(METRIC_REVENUE) == "100.00"
    assert result.value(METRIC_UNITS) == "5"
    assert CAVEAT_NULL_MEASURE_INPUTS in result.caveats


def test_negative_revenue_is_kept_and_disclosed() -> None:
    content = b"date,revenue,units\n2026-01-05,100.00,2\n2026-01-06,-25.00,1\n"

    result = package(content)

    assert result.value(METRIC_REVENUE) == "75.00"
    assert CAVEAT_NEGATIVE_REVENUE in result.caveats


def test_duplicate_rows_are_disclosed_rather_than_silently_removed() -> None:
    content = (
        b"date,revenue,units\n"
        b"2026-01-05,100.00,2\n"
        b"2026-01-05,100.00,2\n"
    )

    result = package(content)

    assert result.value(METRIC_REVENUE) == "200.00"
    assert CAVEAT_DUPLICATE_ROWS in result.caveats


def test_currency_is_declared_as_unknown_while_no_currency_is_mapped() -> None:
    assert CAVEAT_CURRENCY_NOT_DECLARED in package(GOLDEN).caveats


def test_time_series_reconciles_to_the_revenue_total() -> None:
    result = package(GOLDEN)

    series = result.series[0]
    assert series.series.granularity == "day"
    assert [bucket.label for bucket in series.series.buckets] == [
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
    ]
    assert [str(bucket.revenue) for bucket in series.series.buckets] == [
        "125.50",
        "90.00",
        "284.50",
    ]
    assert sum(bucket.units for bucket in series.series.buckets) == 11


def test_long_spans_roll_up_to_months() -> None:
    rows = [b"date,revenue,units"]
    for month in range(1, 7):
        rows.append(f"2026-{month:02d}-05,100.00,1".encode())
    content = b"\n".join(rows) + b"\n"

    series = package(content).series[0].series

    assert series.granularity == "month"
    assert [bucket.label for bucket in series.buckets] == [
        "2026-01",
        "2026-02",
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
    ]


def test_dimension_comparisons_reconcile_to_the_total() -> None:
    result = package(GOLDEN)

    category = result.comparison(SEMANTIC_CATEGORY)
    assert [bucket.label for bucket in category.comparison.buckets] == [
        "Beverages",
        "Snacks",
    ]
    assert [str(bucket.revenue) for bucket in category.comparison.buckets] == [
        "335.75",
        "164.25",
    ]

    store = result.comparison(SEMANTIC_STORE)
    assert sum(
        bucket.revenue for bucket in store.comparison.buckets
    ) == sum(bucket.revenue for bucket in category.comparison.buckets)


def test_unavailable_dimensions_are_refused_not_invented() -> None:
    result = package(GOLDEN)

    assert result.comparison(SEMANTIC_CHANNEL) is None
    assert result.refusal("revenue_by_channel").reason == REASON_INPUT_UNAVAILABLE


def test_comparison_truncation_is_disclosed_and_still_reconciles() -> None:
    rows = [b"date,revenue,units,category"]
    for index in range(MAX_COMPARISON_BUCKETS + 5):
        rows.append(f"2026-01-05,{index + 1}.00,1,Cat {index:02d}".encode())
    content = b"\n".join(rows) + b"\n"

    result = package(content)
    comparison = result.comparison(SEMANTIC_CATEGORY).comparison

    assert comparison.distinct_values == MAX_COMPARISON_BUCKETS + 5
    assert comparison.truncated_values == 5
    assert comparison.buckets[-1].label == OTHER_BUCKET_LABEL
    assert sum(bucket.revenue for bucket in comparison.buckets) == sum(
        range(1, MAX_COMPARISON_BUCKETS + 6)
    )


def test_dimension_labels_are_reduced_to_safe_display_labels() -> None:
    content = (
        b'date,revenue,units,category\n'
        b'2026-01-05,10.00,1,"=HYPERLINK(""http://x"",""click"")"\n'
    )

    comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison

    assert not comparison.buckets[0].label.startswith("=")


def test_rows_without_a_date_are_excluded_from_the_series_and_disclosed() -> None:
    content = (
        b"date,revenue,units,invoice_no\n"
        b"2026-01-05,100.00,2,INV-1\n"
        b",50.00,1,INV-2\n"
    )

    result = package(content)

    assert result.value(METRIC_REVENUE) == "150.00"
    assert str(result.series[0].series.buckets[0].revenue) == "100.00"
    assert CAVEAT_UNDATED_ROWS_EXCLUDED in result.caveats
    assert CAVEAT_UNDATED_ROWS_EXCLUDED in result.series[0].caveats


def test_reruns_are_byte_equivalent() -> None:
    first = package(GOLDEN)
    second = package(GOLDEN)

    assert first.digest == second.digest
    assert first.as_document() == second.as_document()


def test_package_digest_changes_with_the_input() -> None:
    changed = GOLDEN.replace(b"125.50", b"125.51")

    assert package(GOLDEN).digest != package(changed).digest


def test_fact_and_citation_identifiers_are_stable_and_unique() -> None:
    first = package(GOLDEN)
    second = package(GOLDEN)

    citations = first.citation_ids
    assert len(citations) == len(set(citations))
    assert citations == second.citation_ids
    assert all(citation.startswith("cit_") for citation in citations)
    assert all(fact.fact_id.startswith("fct_") for fact in first.facts)


def test_package_records_its_provenance() -> None:
    profile = build_profile(
        content=GOLDEN,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(GOLDEN).hexdigest(),
    )
    result = package(GOLDEN)

    assert result.profile_digest == profile.digest
    assert result.source_sha256_hex == hashlib.sha256(GOLDEN).hexdigest()
    assert result.mapping_version == build_mapping(profile).mapping_version


def test_inadmissible_datasets_never_produce_facts() -> None:
    content = b"branch,revenue\nCairo,100.00\n"
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile)
    decision = assess_admissibility(profile, mapping)

    assert decision.admissible is False
    with pytest.raises(FactsRefused):
        build_fact_package(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=decision,
        )


def test_every_emitted_metric_declares_its_governed_inputs() -> None:
    result = package(GOLDEN)

    for fact in result.facts:
        assert fact.inputs
        assert fact.precision >= 0


def test_content_that_does_not_match_the_profile_is_refused() -> None:
    profile = build_profile(
        content=GOLDEN,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(GOLDEN).hexdigest(),
    )
    mapping = build_mapping(profile)
    other = GOLDEN.replace(b"125.50", b"999.99")

    with pytest.raises(FactsRefused):
        build_fact_package(
            content=other,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
        )


def test_a_mapping_from_another_schema_is_refused() -> None:
    profile = build_profile(
        content=GOLDEN,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(GOLDEN).hexdigest(),
    )
    reordered = b"units,revenue,date\n3,125.50,2026-01-05\n2,90.00,2026-01-06\n"
    other_profile = build_profile(
        content=reordered,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(reordered).hexdigest(),
    )
    foreign = build_mapping(other_profile)
    assert foreign.for_semantic("transaction_date").column.position == 2

    with pytest.raises(FactsRefused):
        build_fact_package(
            content=GOLDEN,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=foreign,
            decision=assess_admissibility(profile, build_mapping(profile)),
        )


def test_a_units_only_dataset_never_emits_a_revenue_series() -> None:
    content = b"date,units,category\n2026-01-05,3,Beverages\n2026-01-06,2,Snacks\n"

    result = package(content)

    assert result.fact(METRIC_REVENUE) is None
    assert result.series[0].metric == "units_by_period"
    assert result.refusal("revenue_by_period").reason == REASON_INPUT_UNAVAILABLE
    assert result.comparison(SEMANTIC_CATEGORY).metric == "units_by_category"
    assert result.refusal("revenue_by_category").reason == REASON_INPUT_UNAVAILABLE


def test_a_revenue_dataset_still_names_its_aggregates_by_revenue() -> None:
    result = package(GOLDEN)

    assert result.series[0].metric == "revenue_by_period"
    assert result.comparison(SEMANTIC_CATEGORY).metric == "revenue_by_category"
    assert result.refusal("units_by_period").reason == REASON_INPUT_UNAVAILABLE


def test_incomplete_transaction_identifiers_refuse_the_affected_metrics() -> None:
    content = (
        b"date,revenue,units,invoice_no\n"
        b"2026-01-05,100.00,2,INV-1\n"
        b"2026-01-06,50.00,1,\n"
    )

    result = package(content)

    assert result.value(METRIC_REVENUE) == "150.00"
    assert result.fact(METRIC_TRANSACTIONS) is None
    assert result.fact(METRIC_AVERAGE_ORDER_VALUE) is None
    assert result.refusal(METRIC_TRANSACTIONS).reason == REASON_INCOMPLETE_IDENTIFIERS
    assert result.refusal(METRIC_AVERAGE_ORDER_VALUE).reason == (
        REASON_INCOMPLETE_IDENTIFIERS
    )


def test_complete_transaction_identifiers_still_produce_the_metrics() -> None:
    content = (
        b"date,revenue,units,invoice_no\n"
        b"2026-01-05,100.00,2,INV-1\n"
        b"2026-01-06,50.00,1,INV-2\n"
    )

    result = package(content)

    assert result.value(METRIC_TRANSACTIONS) == "2"
    assert result.value(METRIC_AVERAGE_ORDER_VALUE) == "75.00"
