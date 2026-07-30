from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.aggregates import MAX_COMPARISON_BUCKETS, OTHER_BUCKET_LABEL
from khepri.rra.facts import (
    CAVEAT_CURRENCY_NOT_DECLARED,
    CAVEAT_DISCOUNT_AS_AMOUNT,
    CAVEAT_DUPLICATE_ROWS,
    CAVEAT_NEGATIVE_REVENUE,
    CAVEAT_NULL_MEASURE_INPUTS,
    CAVEAT_PERSONAL_VALUES_REDACTED,
    CAVEAT_RETURNS_AS_AMOUNT,
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
        b"date,revenue,units,cogs,discount,refunds\n"
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

    revenue = result.trend()
    assert revenue.series.granularity == "day"
    assert [bucket.label for bucket in revenue.series.buckets] == [
        "2026-01-05",
        "2026-01-06",
        "2026-01-07",
    ]
    assert [str(bucket.value) for bucket in revenue.series.buckets] == [
        "125.50",
        "90.00",
        "284.50",
    ]
    units = result.trend(METRIC_UNITS)
    assert sum(bucket.value for bucket in units.series.buckets) == 11


def test_long_spans_roll_up_to_months() -> None:
    rows = [b"date,revenue,units"]
    for month in range(1, 7):
        rows.append(f"2026-{month:02d}-05,100.00,1".encode())
    content = b"\n".join(rows) + b"\n"

    series = package(content).trend().series

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
    assert [str(bucket.value) for bucket in category.comparison.buckets] == [
        "335.75",
        "164.25",
    ]

    store = result.comparison(SEMANTIC_STORE)
    assert sum(
        bucket.value for bucket in store.comparison.buckets
    ) == sum(bucket.value for bucket in category.comparison.buckets)


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
    assert sum(bucket.value for bucket in comparison.buckets) == sum(
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
    assert str(result.trend().series.buckets[0].value) == "100.00"
    assert CAVEAT_UNDATED_ROWS_EXCLUDED in result.caveats
    assert CAVEAT_UNDATED_ROWS_EXCLUDED in result.trend().caveats


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
    assert result.trend() is None
    assert result.trend(METRIC_UNITS).metric == "units_by_period"
    assert result.refusal("revenue_by_period").reason == REASON_INPUT_UNAVAILABLE
    assert result.comparison(SEMANTIC_CATEGORY) is None
    assert result.comparison(SEMANTIC_CATEGORY, METRIC_UNITS).metric == "units_by_category"
    assert result.refusal("revenue_by_category").reason == REASON_INPUT_UNAVAILABLE


def test_each_available_measure_gets_its_own_cited_aggregate() -> None:
    result = package(GOLDEN)

    assert {entry.metric for entry in result.series} == {
        "revenue_by_period",
        "units_by_period",
    }
    assert result.comparison(SEMANTIC_CATEGORY).metric == "revenue_by_category"
    assert result.comparison(SEMANTIC_CATEGORY, METRIC_UNITS).metric == "units_by_category"
    assert result.refusal("units_by_period") is None
    assert result.refusal("units_by_category") is None
    citations = result.citation_ids
    assert len(citations) == len(set(citations))


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


def test_compact_per_unit_headers_are_refused_like_separated_ones() -> None:
    content = (
        b"date,revenue,units,unitcost\n"
        b"2026-01-05,200.00,4,120.00\n"
        b"2026-01-06,300.00,6,180.00\n"
    )

    result = package(content)

    assert result.fact(METRIC_COST) is None
    assert result.refusal(METRIC_COST).reason == REASON_INPUT_UNAVAILABLE
    assert result.refusal(METRIC_GROSS_PROFIT).reason == REASON_INPUT_UNAVAILABLE


def test_a_profile_that_misstates_the_content_is_refused() -> None:
    profile = build_profile(
        content=GOLDEN,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(GOLDEN).hexdigest(),
    )
    columns = list(profile.columns)
    columns[1] = replace(columns[1], safe_label="units")
    tampered = replace(profile, columns=tuple(columns))
    assert tampered.source_sha256_hex == profile.source_sha256_hex
    assert tampered != profile

    with pytest.raises(FactsRefused):
        build_fact_package(
            content=GOLDEN,
            media_type=CSV_MEDIA_TYPE,
            profile=tampered,
            mapping=build_mapping(tampered),
            decision=assess_admissibility(tampered, build_mapping(tampered)),
        )


def test_an_unimplemented_formula_version_is_refused() -> None:
    profile = build_profile(
        content=GOLDEN,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(GOLDEN).hexdigest(),
    )
    mapping = build_mapping(profile)

    with pytest.raises(FactsRefused):
        build_fact_package(
            content=GOLDEN,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            formula_version="rra004.formula.v99",
        )


def test_a_minority_personal_value_is_redacted_from_dimension_labels() -> None:
    content = (
        b"date,revenue,category\n"
        b"2026-01-05,10.00,Beverages\n"
        b"2026-01-06,20.00,Snacks\n"
        b"2026-01-07,30.00,buyer@example.com\n"
    )

    result = package(content)
    comparison = result.comparison(SEMANTIC_CATEGORY).comparison

    labels = [bucket.label for bucket in comparison.buckets]
    assert "buyer@example.com" not in labels
    assert "redacted 1" in labels
    assert comparison.redacted_values == 1
    assert CAVEAT_PERSONAL_VALUES_REDACTED in result.caveats
    assert sum(bucket.value for bucket in comparison.buckets) == Decimal("60.00")


def test_redacted_labels_never_carry_a_digest_of_the_source_value() -> None:
    content = (
        b"date,revenue,category\n"
        b"2026-01-05,10.00,Beverages\n"
        b"2026-01-06,20.00,Snacks\n"
        b"2026-01-07,30.00,Bakery\n"
        b"2026-01-08,40.00,buyer.one@example.com\n"
        b"2026-01-09,50.00,buyer.two@example.com\n"
    )

    comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison

    labels = sorted(bucket.label for bucket in comparison.buckets)
    assert comparison.redacted_values == 2
    assert labels == ["Bakery", "Beverages", "Snacks", "redacted 1", "redacted 2"]


def test_monetary_precision_beyond_the_governed_maximum_is_refused() -> None:
    content = b"date,revenue,units\n2026-01-05,0.0000004,1\n2026-01-06,0.0000004,1\n"

    with pytest.raises(FactsRefused):
        package(content)


def test_serialized_aggregates_reconcile_at_the_declared_precision() -> None:
    content = b"date,revenue,units\n2026-01-05,0.000004,1\n2026-01-06,0.000004,1\n"

    result = package(content)
    document = result.as_document()

    assert result.monetary_precision == 6
    total = Decimal(document["facts"][0]["value"])
    points = [
        Decimal(point["value"])
        for entry in document["series"]
        if entry["measure"] == METRIC_REVENUE
        for point in entry["points"]
    ]
    assert sum(points) == total


def test_a_discount_amount_declares_its_interpretation() -> None:
    content = (
        b"date,revenue,discount\n"
        b"2026-01-05,100.00,10.00\n"
        b"2026-01-06,200.00,20.00\n"
    )

    result = package(content)

    assert result.value(METRIC_DISCOUNT) == "30.00"
    assert CAVEAT_DISCOUNT_AS_AMOUNT in result.caveats


def test_a_discount_rate_column_is_never_summed_as_money() -> None:
    content = (
        b"date,revenue,discount_rate\n"
        b"2026-01-05,100.00,10\n"
        b"2026-01-06,200.00,20\n"
    )

    result = package(content)

    assert result.fact(METRIC_DISCOUNT) is None
    assert result.refusal(METRIC_DISCOUNT).reason == REASON_INPUT_UNAVAILABLE


def test_a_lowercase_iban_is_redacted_like_an_uppercase_one() -> None:
    content = (
        b"date,revenue,category\n"
        b"2026-01-05,10.00,Beverages\n"
        b"2026-01-06,20.00,Snacks\n"
        b"2026-01-07,30.00,Bakery\n"
        b"2026-01-08,40.00,gb82 west 1234 5698 7654 32\n"
    )

    comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison

    labels = [bucket.label for bucket in comparison.buckets]
    assert not any("gb82" in label.lower() for label in labels)
    assert comparison.redacted_values == 1


def test_large_monetary_totals_are_summed_without_silent_rounding() -> None:
    content = (
        b"date,revenue,units\n"
        b"2026-01-05,1234567890123456.78,1\n"
        b"2026-01-06,0.10,1\n"
    )

    result = package(content)

    assert result.value(METRIC_REVENUE) == "1234567890123456.88"


def test_monetary_magnitude_beyond_the_governed_maximum_is_refused() -> None:
    content = (
        b"date,revenue,units\n"
        b"2026-01-05,1234567890123456789012345678.90,1\n"
        b"2026-01-06,0.10,1\n"
    )

    with pytest.raises(FactsRefused):
        package(content)


def test_an_emitted_returns_total_declares_its_interpretation() -> None:
    content = b"date,revenue,refunds\n2026-01-05,100.00,2\n2026-01-06,200.00,3\n"

    result = package(content)

    assert result.value(METRIC_RETURNS) == "5.00"
    assert CAVEAT_RETURNS_AS_AMOUNT in result.caveats


def test_count_magnitude_beyond_the_governed_maximum_is_refused() -> None:
    huge = b"9" * 70
    content = b"date,revenue,units\n2026-01-05,10.00," + huge + b"\n2026-01-06,20.00,1\n"

    with pytest.raises(FactsRefused):
        package(content)


def test_a_per_unit_revenue_column_never_becomes_a_revenue_total() -> None:
    content = (
        b"date,sales_per_unit,units\n"
        b"2026-01-05,10.00,2\n"
        b"2026-01-06,20.00,3\n"
    )

    result = package(content)

    assert result.fact(METRIC_REVENUE) is None
    assert result.refusal(METRIC_REVENUE).reason == REASON_INPUT_UNAVAILABLE
    assert result.value(METRIC_UNITS) == "5"


def test_unicode_grouping_spaces_cannot_carry_an_iban_past_redaction() -> None:
    iban = "GB82 WEST 1234 5698 7654 32"
    content = (
        "date,revenue,category\n"
        "2026-01-05,10.00,Beverages\n"
        "2026-01-06,20.00,Snacks\n"
        "2026-01-07,30.00,Bakery\n"
        f"2026-01-08,40.00,{iban}\n"
    ).encode()

    comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison

    labels = [bucket.label for bucket in comparison.buckets]
    assert not any("GB82" in label for label in labels)
    assert comparison.redacted_values == 1


def test_an_internationalized_email_is_redacted_like_an_ascii_one() -> None:
    for address in ("buyer@xn--mgbh0fb.xn--wgbh1c", "buyer@مثال.مصر"):
        content = (
            "date,revenue,category\n"
            "2026-01-05,10.00,Beverages\n"
            "2026-01-06,20.00,Snacks\n"
            "2026-01-07,30.00,Bakery\n"
            f"2026-01-08,40.00,{address}\n"
        ).encode()

        comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison
        labels = [bucket.label for bucket in comparison.buckets]
        assert not any("buyer" in label for label in labels), address
        assert comparison.redacted_values == 1, address


def test_ordinary_text_is_not_mistaken_for_an_email() -> None:
    content = (
        b"date,revenue,category\n"
        b"2026-01-05,10.00,Beverages\n"
        b"2026-01-06,20.00,Snacks\n"
    )

    comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison

    assert comparison.redacted_values == 0
    assert sorted(bucket.label for bucket in comparison.buckets) == ["Beverages", "Snacks"]


def test_a_column_answering_two_measures_never_produces_facts() -> None:
    content = b"date,sales quantity\n2026-01-05,10\n2026-01-06,20\n"
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile)

    with pytest.raises(FactsRefused):
        build_fact_package(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
        )


def test_a_dotted_phone_number_is_redacted() -> None:
    content = (
        b"date,revenue,category\n"
        b"2026-01-05,10.00,Beverages\n"
        b"2026-01-06,20.00,Snacks\n"
        b"2026-01-07,30.00,Bakery\n"
        b"2026-01-08,40.00,+1.212.555.1212\n"
    )

    comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison

    labels = [bucket.label for bucket in comparison.buckets]
    assert not any("212" in label for label in labels)
    assert comparison.redacted_values == 1


def test_a_forecast_column_never_becomes_governed_revenue() -> None:
    content = (
        b"date,forecast_sales,units\n"
        b"2026-01-05,10.00,2\n"
        b"2026-01-06,20.00,3\n"
    )

    result = package(content)

    assert result.fact(METRIC_REVENUE) is None
    assert result.refusal(METRIC_REVENUE).reason == REASON_INPUT_UNAVAILABLE
    assert result.value(METRIC_UNITS) == "5"


def test_an_identifier_embedded_in_a_larger_value_is_redacted() -> None:
    embedded = (
        "Jane Doe <buyer@example.com>",
        "IBAN: GB82 WEST 1234 5698 7654 32",
        "call 212.555.1212 now",
    )
    for value in embedded:
        content = (
            "date,revenue,category\n"
            "2026-01-05,10.00,Beverages\n"
            "2026-01-06,20.00,Snacks\n"
            "2026-01-07,30.00,Bakery\n"
            f"2026-01-08,40.00,{value}\n"
        ).encode()

        comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison
        labels = [bucket.label for bucket in comparison.buckets]
        assert comparison.redacted_values == 1, value
        assert all("Jane" not in label and "212" not in label for label in labels), value
        assert sum(bucket.value for bucket in comparison.buckets) == Decimal("100.00")


def test_aggregate_facts_declare_their_unit_kind() -> None:
    built = package(GOLDEN)
    document = built.as_document()

    for measure, unit_kind in ((METRIC_REVENUE, UNIT_MONETARY), (METRIC_UNITS, UNIT_COUNT)):
        assert built.trend(measure).unit_kind == unit_kind
        assert built.comparison(SEMANTIC_CATEGORY, measure).unit_kind == unit_kind

    # A report consumer reads the serialized document, not the objects, so the
    # unit has to survive serialization rather than be inferred from the metric.
    for entry in (*document["series"], *document["comparisons"]):
        assert entry["unit_kind"] in {UNIT_MONETARY, UNIT_COUNT}


def test_an_address_literal_mailbox_is_redacted_like_a_domain_one() -> None:
    # A bracketed host has no domain labels and no alphabetic suffix, so the
    # structural domain check rejects it and the label sanitizer would publish
    # the whole identifier as "buyer192.0.2.1".
    for value in ("buyer@[192.0.2.1]", "Jane <buyer@[192.0.2.1]>", "buyer@[IPv6:2001:db8::1]"):
        content = (
            "date,revenue,category\n"
            "2026-01-05,10.00,Beverages\n"
            "2026-01-06,20.00,Snacks\n"
            "2026-01-07,30.00,Bakery\n"
            f"2026-01-08,40.00,{value}\n"
        ).encode()

        comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison
        labels = [bucket.label for bucket in comparison.buckets]
        assert comparison.redacted_values == 1, value
        assert all("192" not in label and "buyer" not in label for label in labels), value
        assert all("db8" not in label for label in labels), value
        assert sum(bucket.value for bucket in comparison.buckets) == Decimal("100.00")


def test_an_ordinary_label_containing_an_at_sign_is_not_redacted() -> None:
    content = (
        b"date,revenue,branch\n"
        b"2026-01-05,10.00,Cairo @ Festival City\n"
        b"2026-01-06,20.00,Giza\n"
    )

    comparison = package(content).comparison(SEMANTIC_STORE).comparison

    assert comparison.redacted_values == 0
    assert "Cairo Festival City" in [bucket.label for bucket in comparison.buckets]


def test_a_grouped_phone_number_inside_a_larger_value_is_redacted() -> None:
    # Splitting the value on whitespace breaks the grouping the number is
    # written in, leaving fragments too short to recognize.
    grouped = (
        "tel 212 555 1212 ext 4",
        "ring me on 020 7946 0958",
        "contact: 0100 123 4567",
    )
    for value in grouped:
        content = (
            "date,revenue,category\n"
            "2026-01-05,10.00,Beverages\n"
            "2026-01-06,20.00,Snacks\n"
            "2026-01-07,30.00,Bakery\n"
            f"2026-01-08,40.00,{value}\n"
        ).encode()

        comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison
        labels = [bucket.label for bucket in comparison.buckets]
        assert comparison.redacted_values == 1, value
        assert all("555" not in label and "7946" not in label for label in labels), value
        assert all("4567" not in label for label in labels), value
        assert sum(bucket.value for bucket in comparison.buckets) == Decimal("100.00")


def test_an_identifier_stays_recognized_when_other_numbers_sit_beside_it() -> None:
    # Concatenating every digit in the value loses a card as soon as any other
    # number is nearby, and splitting on whitespace loses its grouping.
    for value in (
        "4111 1111 1111 1111 exp 1230",
        "Card 4111 1111 1111 1111 expires 12/30",
        "4111 1111 1111 1111 / 5",
        # Grouping punctuation the separator list did not name.
        "Card 4111.1111.1111.1111 expires 12/30",
        "4111.1111.1111.1111 exp 1230",
        "4111/1111/1111/1111",
    ):
        content = (
            "date,revenue,category\n"
            "2026-01-05,10.00,Beverages\n"
            "2026-01-06,20.00,Snacks\n"
            "2026-01-07,30.00,Bakery\n"
            f"2026-01-08,40.00,{value}\n"
        ).encode()

        comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison
        labels = [bucket.label for bucket in comparison.buckets]
        assert comparison.redacted_values == 1, value
        assert all("4111" not in label for label in labels), value
        assert sum(bucket.value for bucket in comparison.buckets) == Decimal("100.00")


def test_a_mailbox_ending_a_sentence_is_redacted() -> None:
    # The candidate span is greedy on the host, so a sentence-final stop makes
    # the last domain label empty and the address fails validation intact.
    for value in ("Contact buyer@example.com.", "see buyer@example.com!"):
        content = (
            "date,revenue,category\n"
            "2026-01-05,10.00,Beverages\n"
            "2026-01-06,20.00,Snacks\n"
            "2026-01-07,30.00,Bakery\n"
            f"2026-01-08,40.00,{value}\n"
        ).encode()

        comparison = package(content).comparison(SEMANTIC_CATEGORY).comparison
        labels = [bucket.label for bucket in comparison.buckets]
        assert comparison.redacted_values == 1, value
        assert all("buyer" not in label and "example" not in label for label in labels), value
        assert sum(bucket.value for bucket in comparison.buckets) == Decimal("100.00")


def test_ordinary_multiword_labels_are_not_redacted() -> None:
    content = (
        b"date,revenue,branch\n"
        b"2026-01-05,10.00,Cairo Downtown 2026\n"
        b"2026-01-06,20.00,Store 12\n"
    )

    comparison = package(content).comparison(SEMANTIC_STORE).comparison

    assert comparison.redacted_values == 0
    assert sorted(bucket.label for bucket in comparison.buckets) == [
        "Cairo Downtown 2026",
        "Store 12",
    ]
