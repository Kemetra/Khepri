from __future__ import annotations

import hashlib

from khepri.rra.admissibility import (
    REASON_IRRECONCILABLE_TYPES,
    REASON_MISSING_REQUESTED_SEMANTIC,
    REASON_NO_CORE_MEASURE,
    REASON_NO_DATA_ROWS,
    REASON_NO_TIME_FIELD,
    REASON_UNRESOLVED_AMBIGUITY,
    ReportRequest,
    assess_admissibility,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import (
    MAPPING_VERSION,
    REQUIREMENT_CORE_MEASURE,
    REQUIREMENT_OPTIONAL,
    REQUIREMENT_REQUIRED,
    SEMANTIC_CATEGORY,
    SEMANTIC_CHANNEL,
    SEMANTIC_COST,
    SEMANTIC_DISCOUNT,
    SEMANTIC_PRODUCT,
    SEMANTIC_RETURNS,
    SEMANTIC_REVENUE,
    SEMANTIC_STORE,
    SEMANTIC_TRANSACTION_DATE,
    SEMANTIC_TRANSACTION_ID,
    SEMANTIC_UNITS,
    STATE_AMBIGUOUS,
    STATE_CONFLICTING,
    STATE_MAPPED,
    STATE_UNAVAILABLE,
    RetailMapping,
    build_mapping,
)
from khepri.rra.profiling import build_profile


def mapped(content: bytes) -> RetailMapping:
    return build_mapping(_profile(content))


def _profile(content: bytes):
    return build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )


def test_full_retail_schema_maps_every_governed_semantic() -> None:
    content = (
        b"date,revenue,units,invoice_no,sku,category,branch,channel,"
        b"cogs,discount,refunds\n"
        b"2026-01-05,125.50,3,INV-1,SKU-1,Beverages,Cairo,online,80.00,5.00,1\n"
        b"2026-01-06,90.00,2,INV-2,SKU-2,Snacks,Giza,retail,60.00,0.00,0\n"
    )

    mapping = mapped(content)

    assert mapping.mapping_version == MAPPING_VERSION
    assert set(mapping.mapped_semantics) == {
        SEMANTIC_TRANSACTION_DATE,
        SEMANTIC_REVENUE,
        SEMANTIC_UNITS,
        SEMANTIC_TRANSACTION_ID,
        SEMANTIC_PRODUCT,
        SEMANTIC_CATEGORY,
        SEMANTIC_STORE,
        SEMANTIC_CHANNEL,
        SEMANTIC_COST,
        SEMANTIC_DISCOUNT,
        SEMANTIC_RETURNS,
    }


def test_requirements_are_distinguished_per_semantic() -> None:
    mapping = mapped(b"date,revenue\n2026-01-05,1.50\n")

    assert mapping.for_semantic(SEMANTIC_TRANSACTION_DATE).requirement == (
        REQUIREMENT_REQUIRED
    )
    assert mapping.for_semantic(SEMANTIC_REVENUE).requirement == REQUIREMENT_CORE_MEASURE
    assert mapping.for_semantic(SEMANTIC_UNITS).requirement == REQUIREMENT_CORE_MEASURE
    assert mapping.for_semantic(SEMANTIC_STORE).requirement == REQUIREMENT_OPTIONAL


def test_mapped_semantic_carries_confidence_evidence_and_safe_label() -> None:
    mapping = mapped(b"date,net_sales\n2026-01-05,125.50\n")

    revenue = mapping.for_semantic(SEMANTIC_REVENUE)
    assert revenue.state == STATE_MAPPED
    assert revenue.column is not None
    assert revenue.column.safe_label == "net_sales"
    assert revenue.confidence == "1.00"
    assert revenue.evidence == ("label_exact", "type_confirmed")


def test_partial_label_match_yields_lower_confidence() -> None:
    mapping = mapped(b"date,total_sales_amount\n2026-01-05,125.50\n")

    revenue = mapping.for_semantic(SEMANTIC_REVENUE)
    assert revenue.state == STATE_MAPPED
    assert revenue.confidence == "0.85"
    assert revenue.evidence == ("label_token", "type_confirmed")


def test_two_equally_strong_candidates_are_ambiguous_not_guessed() -> None:
    content = b"date,revenue,sales\n2026-01-05,125.50,120.00\n"

    revenue = mapped(content).for_semantic(SEMANTIC_REVENUE)

    assert revenue.state == STATE_AMBIGUOUS
    assert [candidate.safe_label for candidate in revenue.candidates] == [
        "revenue",
        "sales",
    ]


def test_irreconcilable_type_is_conflicting_not_unavailable() -> None:
    content = b"date,revenue\n2026-01-05,one hundred\n2026-01-06,ninety\n"

    revenue = mapped(content).for_semantic(SEMANTIC_REVENUE)

    assert revenue.state == STATE_CONFLICTING
    assert revenue.evidence == ("label_exact", "type_conflict")


def test_fractional_units_conflict_with_the_integer_contract() -> None:
    content = b"date,units\n2026-01-05,3.5\n2026-01-06,2.5\n"

    assert mapped(content).state_of(SEMANTIC_UNITS) == STATE_CONFLICTING


def test_absent_semantic_is_unavailable() -> None:
    mapping = mapped(b"date,revenue\n2026-01-05,1.50\n")

    assert mapping.state_of(SEMANTIC_CHANNEL) == STATE_UNAVAILABLE
    assert mapping.for_semantic(SEMANTIC_CHANNEL).candidates == ()


def test_a_single_date_typed_column_maps_without_a_label_match() -> None:
    content = b"when,revenue\n2026-01-05,125.50\n2026-01-06,90.00\n"

    date = mapped(content).for_semantic(SEMANTIC_TRANSACTION_DATE)

    assert date.state == STATE_MAPPED
    assert date.evidence == ("type_only",)
    assert date.confidence == "0.55"


def test_two_unlabelled_date_columns_stay_ambiguous() -> None:
    content = b"when,posted,revenue\n2026-01-05,2026-01-07,125.50\n"

    assert mapped(content).state_of(SEMANTIC_TRANSACTION_DATE) == STATE_AMBIGUOUS


def test_personal_data_columns_are_excluded_from_every_mapping() -> None:
    content = (
        b"date,store,units\n"
        b"2026-01-05,buyer.one@example.com,1\n"
        b"2026-01-06,buyer.two@example.com,2\n"
    )

    mapping = mapped(content)

    assert mapping.excluded_positions == (1,)
    assert mapping.state_of(SEMANTIC_STORE) == STATE_UNAVAILABLE


def test_arabic_headers_map_to_governed_semantics() -> None:
    content = "التاريخ,المبيعات,الكمية\n2026-01-05,125.50,3\n".encode()

    mapping = mapped(content)

    assert mapping.state_of(SEMANTIC_TRANSACTION_DATE) == STATE_MAPPED
    assert mapping.state_of(SEMANTIC_REVENUE) == STATE_MAPPED
    assert mapping.state_of(SEMANTIC_UNITS) == STATE_MAPPED


def test_admissible_dataset_has_a_time_field_and_a_core_measure() -> None:
    content = b"date,revenue\n2026-01-05,125.50\n2026-01-06,90.00\n"
    profile = _profile(content)

    decision = assess_admissibility(profile, build_mapping(profile))

    assert decision.admissible is True
    assert decision.reasons == ()


def test_units_alone_answers_the_core_measure() -> None:
    content = b"date,units\n2026-01-05,3\n2026-01-06,2\n"
    profile = _profile(content)

    assert assess_admissibility(profile, build_mapping(profile)).admissible is True


def test_missing_time_field_is_inadmissible() -> None:
    content = b"store,revenue\nCairo,125.50\nGiza,90.00\n"
    profile = _profile(content)

    decision = assess_admissibility(profile, build_mapping(profile))

    assert decision.admissible is False
    assert REASON_NO_TIME_FIELD in decision.reasons


def test_missing_core_measure_is_inadmissible() -> None:
    content = b"date,store\n2026-01-05,Cairo\n2026-01-06,Giza\n"
    profile = _profile(content)

    decision = assess_admissibility(profile, build_mapping(profile))

    assert decision.admissible is False
    assert REASON_NO_CORE_MEASURE in decision.reasons


def test_ambiguous_core_measure_is_inadmissible() -> None:
    content = b"date,revenue,sales\n2026-01-05,125.50,120.00\n"
    profile = _profile(content)

    decision = assess_admissibility(profile, build_mapping(profile))

    assert decision.admissible is False
    assert REASON_NO_CORE_MEASURE in decision.reasons
    assert REASON_UNRESOLVED_AMBIGUITY in decision.reasons


def test_conflicting_core_measure_types_are_inadmissible() -> None:
    content = b"date,revenue\n2026-01-05,one hundred\n2026-01-06,ninety\n"
    profile = _profile(content)

    decision = assess_admissibility(profile, build_mapping(profile))

    assert decision.admissible is False
    assert REASON_IRRECONCILABLE_TYPES in decision.reasons


def test_requested_semantic_that_is_unavailable_is_inadmissible() -> None:
    content = b"date,revenue\n2026-01-05,125.50\n"
    profile = _profile(content)

    decision = assess_admissibility(
        profile,
        build_mapping(profile),
        request=ReportRequest(requested_semantics=frozenset({SEMANTIC_CATEGORY})),
    )

    assert decision.admissible is False
    assert REASON_MISSING_REQUESTED_SEMANTIC in decision.reasons
    assert decision.requested_semantics == (SEMANTIC_CATEGORY,)


def test_ambiguity_only_blocks_semantics_the_report_needs() -> None:
    content = (
        b"date,units,branch,outlet\n"
        b"2026-01-05,3,Cairo,Downtown\n"
        b"2026-01-06,2,Giza,Mall\n"
    )
    profile = _profile(content)
    mapping = build_mapping(profile)

    assert mapping.state_of(SEMANTIC_STORE) == STATE_AMBIGUOUS
    assert assess_admissibility(profile, mapping).admissible is True

    requested = assess_admissibility(
        profile,
        mapping,
        request=ReportRequest(requested_semantics=frozenset({SEMANTIC_STORE})),
    )
    assert requested.admissible is False
    assert REASON_UNRESOLVED_AMBIGUITY in requested.reasons


def test_header_only_dataset_is_inadmissible() -> None:
    profile = _profile(b"date,revenue\n")

    decision = assess_admissibility(profile, build_mapping(profile))

    assert decision.admissible is False
    assert REASON_NO_DATA_ROWS in decision.reasons


def test_optional_semantics_do_not_block_admissibility() -> None:
    content = b"date,revenue,cogs\n2026-01-05,125.50,eighty\n"
    profile = _profile(content)
    mapping = build_mapping(profile)

    assert mapping.state_of(SEMANTIC_COST) == STATE_CONFLICTING
    assert mapping.state_of(SEMANTIC_DISCOUNT) == STATE_UNAVAILABLE
    assert mapping.state_of(SEMANTIC_RETURNS) == STATE_UNAVAILABLE
    assert assess_admissibility(profile, mapping).admissible is True


def test_per_unit_money_columns_are_not_mapped_as_row_measures() -> None:
    content = (
        b"date,revenue,units,unit_cost,price_per_item\n"
        b"2026-01-05,200.00,4,120.00,50.00\n"
        b"2026-01-06,300.00,6,180.00,50.00\n"
    )

    mapping = mapped(content)

    assert mapping.state_of(SEMANTIC_COST) == STATE_UNAVAILABLE
    assert mapping.for_semantic(SEMANTIC_UNITS).column.safe_label == "units"


def test_an_integer_unit_price_is_never_absorbed_into_units() -> None:
    content = b"date,revenue,unit_price\n2026-01-05,200.00,50\n2026-01-06,300.00,50\n"

    assert mapped(content).state_of(SEMANTIC_UNITS) == STATE_UNAVAILABLE


def test_total_cost_synonyms_still_map() -> None:
    content = b"date,revenue,total_cost\n2026-01-05,200.00,120.00\n"

    assert mapped(content).state_of(SEMANTIC_COST) == STATE_MAPPED


def test_per_unit_and_average_revenue_labels_are_refused() -> None:
    for header in (b"sales_per_unit", b"average_sales", b"salesperunit"):
        content = (
            b"date," + header + b",units\n"
            b"2026-01-05,10.00,2\n"
            b"2026-01-06,20.00,3\n"
        )
        assert mapped(content).state_of(SEMANTIC_REVENUE) == STATE_UNAVAILABLE, header


def test_ordinary_labels_containing_a_disqualifier_substring_still_map() -> None:
    # "supermarket" contains "per"; "opportunity" contains "unit". Neither is a
    # per-unit measure, and a bare substring test would refuse both.
    sales = b"date,supermarket_sales,units\n2026-01-05,10.00,2\n"
    assert mapped(sales).state_of(SEMANTIC_REVENUE) == STATE_MAPPED

    cost = b"date,revenue,opportunity_cost\n2026-01-05,10.00,4.00\n"
    assert mapped(cost).state_of(SEMANTIC_COST) == STATE_MAPPED


def test_a_disqualifier_never_overrides_an_exact_vocabulary_term() -> None:
    content = b"date,revenue,unit\n2026-01-05,10.00,2\n2026-01-06,20.00,3\n"

    assert mapped(content).for_semantic(SEMANTIC_UNITS).column.safe_label == "unit"


def test_arabic_per_unit_labels_are_refused_like_english_ones() -> None:
    for header in ("مبيعات لكل وحدة", "متوسط المبيعات"):
        content = f"date,{header},units\n2026-01-05,10.00,2\n".encode()
        assert mapped(content).state_of(SEMANTIC_REVENUE) == STATE_UNAVAILABLE, header

    cost = "date,revenue,تكلفة الوحدة\n2026-01-05,10.00,4.00\n".encode()
    assert mapped(cost).state_of(SEMANTIC_COST) == STATE_UNAVAILABLE


def test_arabic_row_level_measures_still_map() -> None:
    content = "التاريخ,المبيعات,الكمية,التكلفة\n2026-01-05,125.50,3,80.00\n".encode()

    mapping = mapped(content)

    assert mapping.state_of(SEMANTIC_TRANSACTION_DATE) == STATE_MAPPED
    assert mapping.state_of(SEMANTIC_REVENUE) == STATE_MAPPED
    assert mapping.state_of(SEMANTIC_UNITS) == STATE_MAPPED
    assert mapping.state_of(SEMANTIC_COST) == STATE_MAPPED


def test_the_arabic_singular_unit_still_answers_units() -> None:
    content = "date,revenue,وحدة\n2026-01-05,10.00,2\n2026-01-06,20.00,3\n".encode()

    assert mapped(content).for_semantic(SEMANTIC_UNITS).column.safe_label == "وحدة"


def test_one_column_may_not_answer_two_governed_measures() -> None:
    content = b"date,sales quantity\n2026-01-05,10\n2026-01-06,20\n"

    mapping = mapped(content)

    assert mapping.state_of(SEMANTIC_REVENUE) == STATE_CONFLICTING
    assert mapping.state_of(SEMANTIC_UNITS) == STATE_CONFLICTING


def test_a_shared_column_makes_the_dataset_inadmissible() -> None:
    content = b"date,sales quantity\n2026-01-05,10\n2026-01-06,20\n"
    profile = _profile(content)

    decision = assess_admissibility(profile, build_mapping(profile))

    assert decision.admissible is False
    assert REASON_NO_CORE_MEASURE in decision.reasons
    assert REASON_IRRECONCILABLE_TYPES in decision.reasons


def test_a_compact_per_denominator_label_is_refused() -> None:
    for header in (b"salesperkg", b"sales_per_kg", b"salesperitem"):
        content = b"date," + header + b",units\n2026-01-05,10.00,2\n"
        assert mapped(content).state_of(SEMANTIC_REVENUE) == STATE_UNAVAILABLE, header
