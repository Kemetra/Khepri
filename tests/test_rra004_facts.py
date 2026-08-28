from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.aggregates import MAX_COMPARISON_BUCKETS, OTHER_BUCKET_LABEL
from khepri.rra.facts import (
    CAVEAT_CURRENCY_NOT_DECLARED,
    CAVEAT_DERIVED_OVER_MATCHED_ROWS,
    CAVEAT_DUPLICATE_ROWS,
    CAVEAT_NEGATIVE_REVENUE,
    CAVEAT_NULL_MEASURE_INPUTS,
    CAVEAT_PERSONAL_VALUES_REDACTED,
    CAVEAT_UNDATED_ROWS_EXCLUDED,
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
    REASON_AMBIGUOUS_MAPPING,
    REASON_INCOMPLETE_COVERAGE,
    REASON_INCOMPLETE_IDENTIFIERS,
    REASON_INPUT_UNAVAILABLE,
    REASON_REPEATED_ROW_SIGNATURE,
    UNIT_COUNT,
    UNIT_MONETARY,
    UNIT_RATIO,
    AdmittedInput,
    FactPackage,
    FactsRefused,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import (
    SEMANTIC_CATEGORY,
    SEMANTIC_CHANNEL,
    SEMANTIC_PRODUCT,
    SEMANTIC_STORE,
    build_mapping,
)
from khepri.rra.profiling import build_profile, canonical_json
from khepri.rra.source_contract import (
    BasisDeclaration,
    ContractAttribution,
    EventDeclaration,
    IdentityDeclaration,
    SourceContract,
    build_source_contract,
)
from tests.rra003_contract_fixtures import (
    PUBLISHED_FORMULA_VERSION,
    PUBLISHED_PACKAGE_VERSION,
    REPEATED_INVOICE_CONTRACT,
    TEST_CONTRACT,
    published_mapping_identity,
)

GOLDEN = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)


def admitted(content: bytes) -> AdmittedInput:
    """The admitted reading these bytes produce, under the shared contract.

    Shared by `package` and by the cases that assert a refusal, so the
    construction under test is written once. A second copy is how the two drift
    and a refusal stops being about the thing it names.
    """
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    # Built under the published mapping identity: this module's subject is the
    # fact package's own arithmetic and refusals, never the version gate. After
    # `V-mapping` moved `MAPPING_VERSION`, a freshly stamped mapping meets an
    # unlisted triple and every build here would refuse before computing
    # anything. `RRA-004` keeps historical packages valid under their recorded
    # versions, so this is the governed reading of the admitted triple.
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
    return AdmittedInput(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
        contract=TEST_CONTRACT,
    )


def package(content: bytes) -> FactPackage:
    # The build is inside the block too, because
    # `facts._assert_derived_from_profile` re-derives the mapping and compares
    # it by value.
    with published_mapping_identity():
        return build_fact_package(admitted(content))


def test_core_kpis_are_computed_exactly() -> None:
    result = package(GOLDEN)

    # The predecessor identity, not `PACKAGE_VERSION`: `package()` builds under
    # the published triple because this module's subject is the package's
    # arithmetic, not the version gate. What a build *combines* and what this
    # build *publishes* are different claims -- conflating them is the defect
    # `facts._build` was corrected for.
    assert result.package_version == PUBLISHED_PACKAGE_VERSION
    # The predecessor identity: `package()` pins the whole triple, and what
    # a build combines is not what this build publishes.
    assert result.formula_version == PUBLISHED_FORMULA_VERSION
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
        b"date,revenue,units,cogs,discount_amount,refund_amount\n"
        b"2026-01-05,200.00,4,120.00,10.00,1.00\n"
        b"2026-01-06,300.00,6,180.00,5.00,2.00\n"
    )

    result = package(content)

    assert result.value(METRIC_COST) == "300.00"
    assert result.value(METRIC_GROSS_PROFIT) == "200.00"
    assert result.value(METRIC_GROSS_MARGIN) == "0.4000"
    assert result.fact(METRIC_GROSS_MARGIN).unit_kind == UNIT_RATIO
    assert result.value(METRIC_DISCOUNT) == "15.00"
    # `refund_amount` is present and correctly ignored: `RRA-003` admits no
    # independently mapped return-amount measure, and every row here is a
    # declared sale, so no return event proves a magnitude.
    assert result.value(METRIC_RETURNS) is None


def test_an_average_never_mixes_two_row_populations() -> None:
    """AOV reads the rows that carry both halves, and says that it did.

    The subject is the *average*, and it is unchanged: the second row has an
    invoice but no revenue, and dividing all revenue by all invoices would
    publish 50.00 for an order that took 100.00.

    The headline moved. `RRA-004`:46 gives revenue "no partial-coverage
    vocabulary" and refuses it when its own column has gaps, so the 100.00 that
    used to publish beside this average is now a refusal -- while transactions,
    whose column is whole, still counts two. That split is the point: the
    refusal is per column, and AOV survives because its population is the
    matched rows rather than the headline.
    """
    content = b"date,revenue,invoice_no\n2026-01-05,100.00,INV-1\n2026-01-06,,INV-2\n"

    result = package(content)

    assert result.fact(METRIC_REVENUE) is None
    assert result.value(METRIC_TRANSACTIONS) == "2"
    assert result.value(METRIC_AVERAGE_ORDER_VALUE) == "100.00"
    assert CAVEAT_DERIVED_OVER_MATCHED_ROWS in result.caveats


def test_selling_price_and_margin_use_the_same_rows_as_their_pair() -> None:
    """The two halves are governed differently, and that is the subject.

    `RRA-004:18` puts "and no unmatched eligible row" on
    `sales_complete_revenue_units` and on no other population, because ASP is a
    *divisor*: dropping a row moves the average rather than the count, and a
    reader cannot detect it from the published figures.
    `financial_complete_revenue_cost` carries no such clause, so gross margin
    narrows to the matched rows and discloses that it did.

    **The ASP half asserted 50.00 and was wrong, which review caught.** The
    second row carries units and no revenue -- eligible and unmatched -- so the
    population does not exist for this dataset. Publishing 50.00 beside a units
    total of 5 left a reader unable to reconcile either figure against the other.
    """
    selling = package(b"date,revenue,units\n2026-01-05,100.00,2\n2026-01-06,,3\n")
    assert selling.value(METRIC_UNITS) == "5"
    assert selling.value(METRIC_AVERAGE_SELLING_PRICE) is None

    margin = package(
        b"date,revenue,units,cogs\n2026-01-05,100.00,2,60.00\n2026-01-06,50.00,1,\n"
    )
    assert margin.value(METRIC_REVENUE) == "150.00"
    assert margin.value(METRIC_GROSS_PROFIT) == "40.00"
    assert margin.value(METRIC_GROSS_MARGIN) == "0.4000"
    assert CAVEAT_DERIVED_OVER_MATCHED_ROWS in margin.caveats


def test_a_measure_absent_altogether_is_not_a_partial_pairing() -> None:
    # No cost column at all refuses the margin; it does not disclose a pairing.
    result = package(b"date,revenue,units\n2026-01-05,100.00,2\n2026-01-06,50.00,3\n")

    assert result.fact(METRIC_GROSS_PROFIT) is None
    assert CAVEAT_DERIVED_OVER_MATCHED_ROWS not in result.caveats


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
    # Refused for want of an eligible row rather than on a zero total.
    # `RRA-003`: "a sale or return event with zero units refuses
    # unit-dependent facts", and `rra004.formula.v2` applies that at the
    # population -- ASP takes "positive posted-sale units only", so a
    # zero-unit row is not in the population at all. The old reason said the
    # denominator summed to zero, which described rows ASP was never
    # entitled to read.
    assert result.refusal(METRIC_AVERAGE_SELLING_PRICE) is not None


def test_null_measure_cells_are_excluded_not_treated_as_zero() -> None:
    """A missing cell is neither a zero nor a summand, and now nor a headline.

    Treating the empty revenue cell as `0.00` would state that the second sale
    took nothing, which the file does not say -- that remains the subject, and
    `units` still publishes 5 because its own column is whole.

    What changed is the revenue headline. Excluding the cell and publishing the
    remaining 100.00 answers a question nobody asked: the revenue of the rows
    that happened to carry one, presented as the revenue of the extract.
    `RRA-004`:46 gives the headlines "no partial-coverage vocabulary and
    therefore refuse when a required admitted column has gaps", so revenue
    refuses. The caveat still discloses the gap.
    """
    content = b"date,revenue,units\n2026-01-05,100.00,2\n2026-01-06,,3\n"

    result = package(content)

    assert result.fact(METRIC_REVENUE) is None
    assert result.value(METRIC_UNITS) == "5"
    assert CAVEAT_NULL_MEASURE_INPUTS in result.caveats


def test_negative_revenue_is_kept_and_disclosed() -> None:
    content = b"date,revenue,units\n2026-01-05,100.00,2\n2026-01-06,-25.00,1\n"

    result = package(content)

    assert result.value(METRIC_REVENUE) == "75.00"
    assert CAVEAT_NEGATIVE_REVENUE in result.caveats


def test_duplicate_rows_are_refused_and_still_disclosed() -> None:
    """Replaces a test that asserted the doubled total was published.

    That test read `RRA-003` as a choice between disclosing `200.00` and
    silently dropping a row, and chose disclosure. Refusal is the third option
    the specification actually names: "a repeated canonical row signature"
    refuses "because a legitimate repeated line cannot be distinguished from a
    duplicated extract". Nothing is removed and no total is invented, and the
    caveat still tells the reader the file contains duplicates.
    """
    content = (
        b"date,revenue,units\n"
        b"2026-01-05,100.00,2\n"
        b"2026-01-05,100.00,2\n"
    )

    result = package(content)

    assert result.fact(METRIC_REVENUE) is None
    assert CAVEAT_DUPLICATE_ROWS in result.caveats


def test_mixed_currency_publishes_no_currency_and_no_monetary_fact() -> None:
    """The case this test was always named for, now actually exercised.

    It asserted the caveat on `GOLDEN`, which declares `EGP` -- so it passed
    because the caveat was appended to *every* package carrying a monetary
    fact, not because its own premise held. Under `rra004.package.v3` the caveat
    is conditional on the admitted currency being absent, which is what makes
    the premise reachable: a package whose currency is genuinely unproven.
    """
    import hashlib

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.profiling import build_profile
    from tests.rra003_contract_fixtures import mixed_currency_contract

    # Two currencies in one extract, which `RRA-003` refuses to reconcile:
    # "Missing, malformed, or mixed currency refuses monetary facts and their
    # derived results but does not suppress independently proven count-only
    # facts." So the package publishes with no proven currency, which is exactly
    # the state this caveat exists to disclose.
    mixed = (
        b"date,revenue,units,invoice_no,currency\n"
        b"2026-01-05,100.00,2,INV-1,EGP\n"
        b"2026-01-06,200.00,4,INV-2,USD\n"
    )
    contract = mixed_currency_contract()
    with published_mapping_identity():
        profile = build_profile(
            content=mixed,
            media_type=CSV_MEDIA_TYPE,
            source_sha256_hex=hashlib.sha256(mixed).hexdigest(),
        )
        mapping = build_mapping(profile, contract=contract)
        result = build_fact_package(
            AdmittedInput(
                content=mixed,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=contract,
            )
        )

    # **The caveat and the refusal are alternatives, not companions.** Mixed
    # currency sets `monetary_refused`, so no monetary fact is published and
    # there is nothing left to caveat -- `RRA-003` refuses those facts outright
    # while leaving count-only facts standing. The caveat discloses the weaker
    # state: monetary facts published while the currency behind them was never
    # declared. Asserting both here would demand two answers to one question.
    assert result.currency is None
    assert CAVEAT_CURRENCY_NOT_DECLARED not in result.caveats
    assert result.value("revenue") is None
    assert result.value("units") == "6"



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
    # Compared under the same identity the package was built with: `package()`
    # pins to the published mapping, so re-deriving outside that block would
    # compare a v2 package against a v3 stamp and fail on the version move
    # rather than on provenance, which is this test's subject.
    with published_mapping_identity():
        expected = build_mapping(profile, contract=TEST_CONTRACT).mapping_version
    assert result.mapping_version == expected


def test_inadmissible_datasets_never_produce_facts() -> None:
    content = b"branch,revenue\nCairo,100.00\n"
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    decision = assess_admissibility(profile, mapping)

    assert decision.admissible is False
    with pytest.raises(FactsRefused):
        build_fact_package(
            AdmittedInput(
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=decision,
                contract=TEST_CONTRACT,
            ),
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
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    other = GOLDEN.replace(b"125.50", b"999.99")

    with pytest.raises(FactsRefused):
        build_fact_package(
            AdmittedInput(
                content=other,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
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
    foreign = build_mapping(other_profile, contract=TEST_CONTRACT)
    assert foreign.for_semantic("transaction_date").column.position == 2

    with pytest.raises(FactsRefused):
        build_fact_package(
            AdmittedInput(
                content=GOLDEN,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=foreign,
                decision=assess_admissibility(
                profile,
                build_mapping(profile, contract=TEST_CONTRACT),
            ),
                contract=TEST_CONTRACT,
            ),
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
            AdmittedInput(
                content=GOLDEN,
                media_type=CSV_MEDIA_TYPE,
                profile=tampered,
                mapping=build_mapping(tampered, contract=TEST_CONTRACT),
                decision=assess_admissibility(
                tampered,
                build_mapping(tampered, contract=TEST_CONTRACT),
            ),
                contract=TEST_CONTRACT,
            ),
        )


def test_an_unimplemented_formula_version_is_refused() -> None:
    profile = build_profile(
        content=GOLDEN,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(GOLDEN).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)

    with pytest.raises(FactsRefused):
        build_fact_package(
            AdmittedInput(
                content=GOLDEN,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
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


def test_a_bare_discount_column_is_refused_rather_than_summed_as_money() -> None:
    # 10 and 20 could be currency, percentages, or counts. Nothing in the label
    # or the values decides, so the figure is not published at all.
    content = (
        b"date,revenue,discount\n"
        b"2026-01-05,100.00,10.00\n"
        b"2026-01-06,200.00,20.00\n"
    )

    result = package(content)

    assert result.fact(METRIC_DISCOUNT) is None
    assert result.refusal(METRIC_DISCOUNT).reason == REASON_AMBIGUOUS_MAPPING


def test_a_discount_amount_is_published_when_the_label_declares_it() -> None:
    for header in (b"discount_amount", b"discount_value", b"total_discount"):
        content = (
            b"date,revenue," + header + b"\n"
            b"2026-01-05,100.00,10.00\n"
            b"2026-01-06,200.00,20.00\n"
        )

        result = package(content)

        assert result.value(METRIC_DISCOUNT) == "30.00", header
        assert result.fact(METRIC_DISCOUNT).unit_kind == UNIT_MONETARY, header


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


def test_a_bare_returns_column_is_refused_rather_than_summed_as_money() -> None:
    # 2 and 3 are far more likely returned items than 5.00 of currency.
    content = b"date,revenue,refunds\n2026-01-05,100.00,2\n2026-01-06,200.00,3\n"

    result = package(content)

    assert result.fact(METRIC_RETURNS) is None
    assert result.refusal(METRIC_RETURNS).reason == REASON_AMBIGUOUS_MAPPING


def test_an_independently_mapped_returns_column_is_not_admitted() -> None:
    """`RRA-003` refuses it by name, and this case asserted the opposite.

    "No independently mapped return-amount measure is admitted. Gross
    merchandise value, tender or tax refunds, fees, exchange value, and
    restocking charges cannot substitute."

    A column labelled `refund_amount` is exactly the ambiguity that rule
    exists for: it may be a tender refund, a restocking charge, or gross
    merchandise value, and none of those is the governed returns magnitude.
    Under `rra004.formula.v2` returns are derived from admitted return
    revenue, so this extract -- every row a declared sale, no return event --
    proves no returns and publishes none.
    """
    content = b"date,revenue,refund_amount\n2026-01-05,100.00,2.00\n2026-01-06,200.00,3.00\n"

    result = package(content)

    assert result.value(METRIC_RETURNS) is None
    assert result.refusal(METRIC_RETURNS) is not None


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

    with pytest.raises(FactsRefused):
        build_fact_package(admitted(content))


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


def test_a_customer_identifier_column_never_becomes_a_published_dimension() -> None:
    # The label mentions "product", so the column mapped to the product
    # dimension and published customer identifiers verbatim as bucket labels.
    content = (
        b"date,revenue,product_customer_id\n"
        b"2026-01-05,10.00,CUST-001\n"
        b"2026-01-06,20.00,CUST-002\n"
    )

    built = package(content)

    assert built.comparison(SEMANTIC_PRODUCT) is None
    assert built.refusal("revenue_by_product").reason == REASON_INPUT_UNAVAILABLE
    assert "CUST" not in canonical_json(built.as_document())


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


# ---------------------------------------------------------------------------
# The basis declaration, reaching the figure a customer actually sees.
#
# `RRA-003` refuses the discount metric on "a bare discount, rate, percentage,
# repeated invoice total, or overlapping component set", and refuses a cost that
# is unit, average, standard or list rather than extended COGS.
# `BasisDeclaration.discount_is_additive` / `.cost_is_extended` are the
# operator's attestations that neither defect is present.
#
# `admission.py` honours them on `AdmittedEvent.discount` / `.cost`. But
# `_totals` builds the *published* figures from `measures.*`, which is read off
# the frame and mapping and never off the admitted events -- so a contract
# disclaiming the basis still published the total. These cases assert the
# refusal on the published figure, which is the only thing a customer sees.
#
# Their subject IS the contract, so they build their own declarations inline
# rather than using `TEST_CONTRACT` -- see `rra003_contract_fixtures`' docstring.
# ---------------------------------------------------------------------------

BASIS_CSV = (
    b"date,revenue,units,cogs,discount_amount,invoice_no\n"
    b"2026-01-05,200.00,4,120.00,10.00,INV-1\n"
    b"2026-01-06,300.00,6,180.00,5.00,INV-2\n"
)


def _basis_contract(
    *, cost_is_extended: bool = True, discount_is_additive: bool = True
) -> SourceContract:
    """`TEST_CONTRACT`'s declaration with one basis attestation withdrawn."""
    return build_source_contract(
        attribution=ContractAttribution(
            contract_id="src_facts_basis",
            evidence="Test fixture: a basis attestation deliberately withheld.",
        ),
        events=EventDeclaration(
            event_kind_column=None,
            sale_only=True,
            status_column=None,
            posted_only=True,
            currency_column=None,
            currency_code="EGP",
        ),
        identity=IdentityDeclaration(
            event_key_columns=(),
            unique_line_grain_attested=True,
            transaction_id_column="invoice_no",
            transaction_key_components=(),
            transaction_id_unique_package_wide=True,
        ),
        basis=BasisDeclaration(
            revenue_vat_exclusive=True,
            revenue_is_net_of_returns=False,
            units_are_integral=True,
            cost_is_extended=cost_is_extended,
            discount_is_additive=discount_is_additive,
        ),
    )


def _basis_package(contract: SourceContract) -> FactPackage:
    """One package built over `BASIS_CSV` under the given declaration."""
    profile = build_profile(
        content=BASIS_CSV,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(BASIS_CSV).hexdigest(),
    )
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=contract)
        return build_fact_package(
            AdmittedInput(
                content=BASIS_CSV,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=contract,
            )
        )


def test_an_attested_basis_still_publishes_cost_and_discount() -> None:
    """The control. Both attestations present, both figures published -- so the
    refusals below are the basis being honoured and not the fixture failing to
    map its columns."""
    result = _basis_package(_basis_contract())

    assert result.value(METRIC_COST) == "300.00"
    assert result.value(METRIC_DISCOUNT) == "15.00"
    assert result.value(METRIC_GROSS_PROFIT) == "200.00"
    assert result.value(METRIC_GROSS_MARGIN) == "0.4000"


def test_a_discount_basis_not_attested_additive_refuses_the_published_total() -> None:
    """`RRA-003` refuses the discount metric where the source does not already
    prevent overlap and allocate every invoice-level amount exactly once.

    The whole point is the *published* figure. A contract disclaiming additivity
    while the report still carries `discount = 15.00` leaves the refusal true of
    an intermediate object and false of the only number anybody reads.
    """
    result = _basis_package(_basis_contract(discount_is_additive=False))

    assert result.fact(METRIC_DISCOUNT) is None
    assert result.refusal(METRIC_DISCOUNT) is not None
    # Revenue is measured on its own basis and is unaffected.
    assert result.value(METRIC_REVENUE) == "500.00"


def test_a_cost_basis_not_attested_extended_refuses_the_published_total() -> None:
    """`RRA-003`: "unit cost, average cost, standard cost, list cost, and a bare
    ambiguous cost label are not additive COGS and are refused.\""""
    result = _basis_package(_basis_contract(cost_is_extended=False))

    assert result.fact(METRIC_COST) is None
    assert result.refusal(METRIC_COST) is not None
    assert result.value(METRIC_REVENUE) == "500.00"


def test_an_unattested_cost_basis_also_refuses_the_results_derived_from_it() -> None:
    """`RRA-003` refuses monetary facts "and their derived results".

    Gross profit and gross margin are computed from the same unattested cost, so
    refusing the `cost` total while publishing a margin derived from it would
    publish the refused number under a different name -- and the margin is the
    figure most likely to be read.
    """
    result = _basis_package(_basis_contract(cost_is_extended=False))

    assert result.fact(METRIC_GROSS_PROFIT) is None
    assert result.fact(METRIC_GROSS_MARGIN) is None
    assert result.refusal(METRIC_GROSS_PROFIT) is not None
    assert result.refusal(METRIC_GROSS_MARGIN) is not None


# --- canonical transaction keys, issue #295 ---------------------------------


def _repeated_invoice_package():
    """The oracle's two-store repeated-invoice case, built under `package.v3`.

    Deliberately *not* pinned: this case is about what `rra004.package.v3`
    publishes, and `RRA-004` assigns canonical transaction keys to that version.
    Building it under the predecessor triple would prove the defect still exists
    in v2, which nobody disputes and nobody may fix.
    """
    import hashlib

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.intake import CSV_MEDIA_TYPE
    from khepri.rra.profiling import build_profile
    from tests.rra_calculation_oracle import REPEATED_INVOICE_ROWS, to_csv

    content = to_csv(REPEATED_INVOICE_ROWS)
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    # The contract that honestly describes this extract. `TEST_CONTRACT`
    # declares the invoice number unique package-wide, which is true of every
    # other fixture and false of this one -- and `RRA-003` admits the bare
    # identifier exactly when that declaration holds, so admission would be
    # right to return it. The defect this case proves is downstream of the
    # declaration, not in it.
    mapping = build_mapping(profile, contract=REPEATED_INVOICE_CONTRACT)
    return build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=REPEATED_INVOICE_CONTRACT,
        )
    )


def test_repeated_invoices_in_two_stores_are_two_transactions_each() -> None:
    """`RRA-003`'s canonical-transaction-key contract, at the point of use.

    "A bare source transaction identifier qualifies only when its recorded
    source contract proves package-wide uniqueness. Otherwise the canonical key
    is an admitted composite containing the source identifier and every field
    required for uniqueness, normally store, business date, and terminal."

    `admission.py` builds that composite correctly and `facts._measures` then
    reloaded the bare mapped column, so INV-1 from S1 and INV-1 from S2
    collapsed into one transaction. Two stores' trading was published as two
    transactions instead of four.

    Expected values from `tests/rra_calculation_oracle.py`, derived by hand
    outside every production helper.
    """
    from tests.rra_calculation_oracle import REPEATED_INVOICE_EXPECTED

    result = _repeated_invoice_package()

    assert result.value("transactions") == str(
        REPEATED_INVOICE_EXPECTED["transactions"]
    )


def test_the_aov_denominator_uses_canonical_keys() -> None:
    """Every transaction-denominated metric inherited the error at exactly 2x.

    AOV is the one this package publishes, so it is the one asserted here.
    Items per transaction is `rra008.basket.v1`'s and is corrected in its own
    family commit.
    """
    from tests.rra_calculation_oracle import REPEATED_INVOICE_EXPECTED

    result = _repeated_invoice_package()

    assert result.value("average_order_value") == str(
        REPEATED_INVOICE_EXPECTED["average_order_value"]
    )


def test_revenue_and_units_are_untouched_by_the_key_correction() -> None:
    """The control, and the proof this is a transaction-identity defect.

    Revenue and units never depended on transaction identity, so a correction
    that moved them would have changed something it was not asked to.
    """
    from tests.rra_calculation_oracle import REPEATED_INVOICE_EXPECTED

    result = _repeated_invoice_package()

    assert result.value("revenue") == str(REPEATED_INVOICE_EXPECTED["revenue"])
    assert result.value("units") == str(REPEATED_INVOICE_EXPECTED["units"])


# --- `rra004.package.v3` provenance -----------------------------------------


def test_a_package_records_the_currency_it_admitted() -> None:
    """`RRA-004`'s provenance list names currency for monetary values.

    `AdmittedEvents.currency` existed and was discarded, so a v3 package would
    have published the field empty while the admission that produced it knew the
    answer.
    """
    result = package(GOLDEN)

    assert result.currency == "EGP"


def test_a_package_that_declares_its_currency_does_not_caveat_it_as_undeclared()  -> None:
    """The caveat was appended to every package carrying a monetary fact.

    Under `rra004.package.v2` that was merely pessimistic: the package recorded
    no currency, so "not declared" was true of the document. `v3` records one,
    and a package stating both `EGP` and "currency not declared" contradicts
    itself -- and `RRA-009` renders caveats to customers, so the contradiction
    would be visible.
    """
    result = package(GOLDEN)

    assert result.currency is not None
    assert CAVEAT_CURRENCY_NOT_DECLARED not in result.caveats


def test_a_package_records_the_filters_its_populations_were_taken_under() -> None:
    """Read off the admitted events, not off the declaration.

    A contract admitting returns over an extract containing none produces a
    sale-only package; recording the declaration would overstate the population
    the figures were computed over.
    """
    result = package(GOLDEN)

    assert result.event_kind_filters == ("sale",)
    assert result.status_filters == ("posted",)


def test_a_package_retains_the_bases_its_facts_cite() -> None:
    """`RRA-004`: "Every derived fact cites exactly one compatible basis or a
    documented set of bases with the same population identity."

    A v3 package retaining none would leave every derived fact citing nothing,
    which satisfies the document shape and not the contract.
    """
    from khepri.rra.bases import GOVERNED_BASES

    result = package(GOLDEN)

    assert {basis.name for basis in result.retained_bases} == GOVERNED_BASES
    assert all(basis.identity for basis in result.retained_bases)


def test_the_retained_bases_agree_with_the_package_they_describe() -> None:
    """Evidence that does not match the package it travels with is not evidence."""
    result = package(GOLDEN)

    for basis in result.retained_bases:
        assert basis.input_digest == result.source_sha256_hex
        assert basis.mapping_version == result.mapping_version


def test_a_transaction_basis_counts_canonical_keys() -> None:
    """The basis behind the transactions figure, over the same keys it counts."""
    from khepri.rra.bases import BASIS_SALES_TRANSACTION

    result = _repeated_invoice_package()

    basis = next(
        entry for entry in result.retained_bases if entry.name == BASIS_SALES_TRANSACTION
    )
    assert basis.transaction_count == 4
    assert result.value("transactions") == "4"


def _duplicate_signature_package() -> FactPackage:
    """The oracle's byte-identical-duplicate case.

    `RRA-003` proves event identity in exactly one of two ways, and every
    fixture here takes the second: no event key, plus an attestation that the
    line grain is unique. A repeated canonical row signature *falsifies that
    attestation*, which is why the contract cannot make this case admissible --
    measured under both identity declarations, the published figures are
    identical, so no declaration makes the doubled total correct.
    """
    from tests.rra003_contract_fixtures import oracle_contract
    from tests.rra_calculation_oracle import DUPLICATE_SIGNATURE_ROWS, to_csv

    content = to_csv(DUPLICATE_SIGNATURE_ROWS)
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    contract = oracle_contract()
    mapping = build_mapping(profile, contract=contract)
    return build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
        )
    )


def test_a_repeated_row_signature_refuses_every_additive_result() -> None:
    """`RRA-003`: a repeated canonical row signature refuses, it does not caveat.

    "A repeated event key, whether identical or conflicting, refuses every
    additive or distinct-transaction result that could include it. Without an
    event key, a repeated canonical row signature has the same effect because a
    legitimate repeated line cannot be distinguished from a duplicated extract."

    The distinguishing word is *cannot*. Disclosing a doubled total with a
    caveat asks the reader to decide which reading is true, and nothing in the
    extract answers: 250.00 twice is either two real sales or one sale twice,
    and the manifest says nothing either way. Publishing 800.00 where the
    un-duplicated data gives 550.00 states one of those readings as fact.
    """
    result = _duplicate_signature_package()

    for metric in (
        METRIC_REVENUE,
        METRIC_UNITS,
        METRIC_TRANSACTIONS,
        METRIC_AVERAGE_ORDER_VALUE,
        METRIC_AVERAGE_SELLING_PRICE,
    ):
        assert result.fact(metric) is None, f"{metric} published over a duplicate"
        refused = result.refusal(metric)
        assert refused is not None
        assert refused.reason == REASON_REPEATED_ROW_SIGNATURE


def test_the_repeated_signature_refusal_reads_from_the_oracle() -> None:
    """The literals this correction is measured against, stated independently.

    `DUPLICATE_SIGNATURE_EXPECTED` refuses all five, derived without calling any
    production helper. Reading them here rather than inlining `None` keeps the
    expectation and the assertion in one place.
    """
    from tests.rra_calculation_oracle import DUPLICATE_SIGNATURE_EXPECTED

    result = _duplicate_signature_package()

    for metric, expected in DUPLICATE_SIGNATURE_EXPECTED.items():
        assert expected is None, f"the oracle expects {metric} to refuse"
        assert result.value(metric) is None


def test_the_duplicate_caveat_still_discloses_what_was_refused() -> None:
    """The refusal replaces the published number, not the disclosure.

    `RRA-009` renders caveats to customers, and "this file contains duplicated
    rows" is the reason the figures are absent. Dropping the caveat when the
    refusal landed would leave a reader with missing metrics and no account of
    why -- and `RRA-004` is explicit that absence is never the disclosure.
    """
    result = _duplicate_signature_package()

    assert CAVEAT_DUPLICATE_ROWS in result.caveats


def test_a_repeated_row_signature_refuses_the_margin_family_too() -> None:
    """The doubled total cannot be refused while its ratio publishes.

    `gross_profit` and `gross_margin` are built from `_margin_inputs`, which
    reads the measure lists rather than the refused totals -- so over a
    duplicated extract they published `355.00` and `0.4438` beside a `cost` that
    had already refused. Both are sums of the repeated row, and `RRA-003`
    refuses "every additive or distinct-transaction result that could include
    it".

    The oracle's `DUPLICATE_SIGNATURE` prose names nine metrics where its
    literals name five, and this is the difference: the prose was right. A page
    stating a margin while refusing the revenue and cost it came from would be
    incoherent on its own face.
    """
    result = _duplicate_signature_package()

    for metric in (METRIC_COST, METRIC_GROSS_PROFIT, METRIC_GROSS_MARGIN):
        assert result.fact(metric) is None, f"{metric} published over a duplicate"
        refused = result.refusal(metric)
        assert refused is not None
        assert refused.reason == REASON_REPEATED_ROW_SIGNATURE


def _disjoint_revenue_units_package() -> FactPackage:
    """The oracle's case where each headline's own column has a gap.

    One row states revenue and no units; the other states units and no revenue.
    Distinct from `PARTIAL_NULL`, where the gap is in *cost* and revenue is
    complete over its own column -- that case publishes, and must keep
    publishing.
    """
    from tests.rra003_contract_fixtures import oracle_contract
    from tests.rra_calculation_oracle import DISJOINT_REVENUE_UNITS_ROWS, to_csv

    content = to_csv(DISJOINT_REVENUE_UNITS_ROWS)
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    contract = oracle_contract()
    mapping = build_mapping(profile, contract=contract)
    return build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
        )
    )


def test_a_headline_refuses_when_its_own_column_has_a_gap() -> None:
    """`RRA-004`:46 -- headlines have "no partial-coverage vocabulary".

    "Headline revenue, cost, units, discounts, and returns have no
    partial-coverage vocabulary and therefore refuse when a required admitted
    column has gaps."

    `_sum_decimal` skips `None` and sums what is left, so it refused only when
    *every* value was missing. One gap published the partial sum as the headline:
    500.00 over a file whose second row states no revenue at all, presented as
    the revenue of the whole extract.
    """
    result = _disjoint_revenue_units_package()

    for metric in (METRIC_REVENUE, METRIC_UNITS):
        assert result.fact(metric) is None, f"{metric} published a partial sum"
        refused = result.refusal(metric)
        assert refused is not None
        # The column is present and incomplete, which is not the same finding as
        # an absent one and does not have the same remedy.
        assert refused.reason == REASON_INCOMPLETE_COVERAGE


def test_a_gap_in_one_column_leaves_the_others_publishing() -> None:
    """The control that proves the refusal is per-column, not package-wide.

    `PARTIAL_NULL` states complete revenue and units with a gap in cost. Cost,
    gross profit and gross margin refuse there -- `financial_complete_revenue_cost`
    is not complete -- while revenue publishes 1000.00, because revenue's own
    column has no gap. A correction that refused every headline whenever any
    column was gapped would take that 1000.00 with it.
    """
    from tests.rra003_contract_fixtures import oracle_contract
    from tests.rra_calculation_oracle import (
        PARTIAL_NULL_EXPECTED,
        PARTIAL_NULL_ROWS,
        to_csv,
    )

    content = to_csv(PARTIAL_NULL_ROWS)
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    contract = oracle_contract()
    mapping = build_mapping(profile, contract=contract)
    result = build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
        )
    )

    assert result.value(METRIC_REVENUE) == str(PARTIAL_NULL_EXPECTED["revenue"])
    assert result.value(METRIC_UNITS) == str(PARTIAL_NULL_EXPECTED["units"])


def test_a_gapped_headline_does_not_take_the_trend_with_it() -> None:
    """`RRA-004`:46 refuses the *headline*, and a period bucket is not one.

    The headline answers "what did this extract take", and a gap in its column
    means no honest answer exists. A monthly bucket answers a narrower question,
    and a gap in January says nothing about February: refusing the trend would
    take periods whose own rows are whole, and with them the comparison and
    growth families that read it.

    The two totals are therefore separate -- the gate applies to what `add`
    publishes, not to what `_series` and `_comparisons` derive from.
    """
    content = (
        b"date,revenue,units\n"
        b"2026-01-05,100.00,2\n"
        b"2026-02-06,,3\n"
        b"2026-03-07,200.00,4\n"
    )

    result = package(content)

    assert result.fact(METRIC_REVENUE) is None
    trend = result.trend()
    assert trend is not None, "a gapped headline refused the whole revenue trend"
    # Bucketed at the granularity this span earns, so the labels are asserted by
    # the days that carry revenue rather than by a month spelling.
    assert {bucket.label for bucket in trend.series.buckets} >= {
        "2026-01-05",
        "2026-03-07",
    }


def test_an_unmapped_column_cannot_hide_a_repeated_row_signature() -> None:
    """`RRA-003` signs the admitted fields, not the file.

    The signature is "a repeated canonical row signature across all admitted
    identity, dimension, and measure fields" -- so a column the mapping never
    admitted has no say in whether two rows are the same event. Comparing whole
    source rows lets a free-text note, an export timestamp or a row id make two
    otherwise identical sales look distinct, and the refusal then fails *open*
    on exactly the input it exists for.

    Both rows here state the same sale in every governed field and differ only
    in a `note` column no semantic claims.
    """
    content = (
        b"date,event_kind,status,revenue,units,invoice_no,store,product,"
        b"category,cost,discount_amount,note\n"
        b"2026-03-04,sale,posted,250.00,5,INV-1,S1,P1,C1,140.00,0.00,alpha\n"
        b"2026-03-04,sale,posted,250.00,5,INV-1,S1,P1,C1,140.00,0.00,beta\n"
    )
    from tests.rra003_contract_fixtures import oracle_contract

    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    contract = oracle_contract()
    mapping = build_mapping(profile, contract=contract)
    result = build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
        )
    )

    assert result.fact(METRIC_REVENUE) is None, "an unmapped note defeated the refusal"
    refused = result.refusal(METRIC_REVENUE)
    assert refused is not None
    assert refused.reason == REASON_REPEATED_ROW_SIGNATURE


def test_a_keyed_contract_is_not_judged_by_the_row_signature() -> None:
    """`RRA-003` proves identity "in exactly one of these ways", and picks one.

    The canonical-row-signature test belongs to the second: "**Without an event
    key**, a repeated canonical row signature has the same effect." A contract
    naming `event_key_columns` has already answered the question, and the same
    paragraph says so from the other side -- "Repeated products or categories in
    one transaction remain valid when their event identities differ."

    Two lines of one invoice, identical in every mapped semantic and distinct in
    their event key: a legitimate repeated line, not a duplicated extract.
    Refusing here would refuse every keyed extract that sells the same product
    twice on one receipt.
    """
    from khepri.rra.source_contract import (
        BasisDeclaration,
        ContractAttribution,
        EventDeclaration,
        IdentityDeclaration,
        build_source_contract,
    )

    contract = build_source_contract(
        attribution=ContractAttribution(
            contract_id="src_keyed", evidence="Test fixture: a keyed extract."
        ),
        events=EventDeclaration(
            event_kind_column=None,
            sale_only=True,
            status_column=None,
            posted_only=True,
            currency_column=None,
            currency_code="EGP",
        ),
        identity=IdentityDeclaration(
            event_key_columns=("line_id",),
            unique_line_grain_attested=False,
            transaction_id_column="invoice_no",
            transaction_key_components=(),
            transaction_id_unique_package_wide=True,
        ),
        basis=BasisDeclaration(
            revenue_vat_exclusive=True,
            revenue_is_net_of_returns=False,
            units_are_integral=True,
            cost_is_extended=True,
            discount_is_additive=True,
        ),
    )
    content = (
        b"date,revenue,units,invoice_no,line_id\n"
        b"2026-03-04,250.00,5,INV-1,L1\n"
        b"2026-03-04,250.00,5,INV-1,L2\n"
    )
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=contract)
    result = build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
        )
    )

    assert result.value(METRIC_REVENUE) == "500.00"
    assert result.value(METRIC_UNITS) == "10"


def _oracle_package(content: bytes) -> FactPackage:
    """A package under the oracle contract, for signature cases needing dimensions."""
    from tests.rra003_contract_fixtures import oracle_contract

    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    contract = oracle_contract()
    mapping = build_mapping(profile, contract=contract)
    return build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
        )
    )


_SIGNATURE_HEADER = (
    b"date,event_kind,status,revenue,units,invoice_no,store,product,"
    b"category,cost,discount_amount\n"
)


def test_the_signature_compares_governed_values_not_source_text() -> None:
    """`250` and `250.00` are one admitted value, so they are one signature.

    `materialize` keeps every column as text, and `RRA-003` signs "admitted
    identity, dimension, and measure fields" -- the values admission produced,
    not the characters the file spelled them with. Comparing the text let a
    trailing `.00`, a padded field or any other equivalent spelling hide a real
    duplicate, so the refusal failed *open* on a file that differs from the
    caught one only in formatting.
    """
    content = (
        _SIGNATURE_HEADER
        + b"2026-03-04,sale,posted,250,5,INV-1,S1,P1,C1,140.00,0.00\n"
        + b"2026-03-04,sale,posted,250.00,5,INV-1,S1,P1,C1,140.00,0.00\n"
    )

    result = _oracle_package(content)

    assert result.fact(METRIC_REVENUE) is None, "a formatting difference hid a duplicate"
    refused = result.refusal(METRIC_REVENUE)
    assert refused is not None
    assert refused.reason == REASON_REPEATED_ROW_SIGNATURE


def test_duplicated_returns_do_not_refuse_the_sale_only_results() -> None:
    """`RRA-003` refuses the results a collision "could include", and no others.

    Transactions, AOV and ASP read posted *sales*. A duplicated return is not in
    any of those populations, so it cannot make them ambiguous -- refusing them
    reports a defect the reader's own sales data does not have. Revenue and units
    do include returns, so they refuse.
    """
    content = (
        _SIGNATURE_HEADER
        + b"2026-03-04,sale,posted,100.00,2,INV-1,S1,P1,C1,50.00,0.00\n"
        + b"2026-03-05,sale,posted,200.00,4,INV-2,S1,P2,C1,90.00,0.00\n"
        + b"2026-03-06,return,posted,-30.00,-1,INV-9,S1,P1,C1,0.00,0.00\n"
        + b"2026-03-06,return,posted,-30.00,-1,INV-9,S1,P1,C1,0.00,0.00\n"
    )

    result = _oracle_package(content)

    # The sale-only populations are untouched: two distinct posted sales.
    assert result.value(METRIC_TRANSACTIONS) == "2"
    assert result.value(METRIC_AVERAGE_ORDER_VALUE) == "150.00"
    # Revenue includes posted returns, so the collision does reach it.
    assert result.fact(METRIC_REVENUE) is None


def test_a_gapped_column_states_a_cause_the_reader_can_act_on() -> None:
    """A present column with blank cells is not an absent column.

    `required_input_unavailable` renders as "the file does not contain
    {column}" and tells the reader to include it in their export. For a headline
    refused under `RRA-004`:46 the column *is* there — some of its cells are
    empty — so that message names a cause that did not occur and gives advice
    that cannot work.
    """
    content = b"date,revenue,units\n2026-01-05,100.00,2\n2026-01-06,,3\n"

    result = package(content)

    refused = result.refusal(METRIC_REVENUE)
    assert refused is not None
    assert refused.reason == REASON_INCOMPLETE_COVERAGE


def test_a_return_row_does_not_gap_the_sale_only_discount() -> None:
    """`RRA-004`:39 scopes discounts to "posted **sales** with complete ... coverage".

    A return carries no discount, and its blank cell is not a gap in the sale
    population -- the row is not in it. Refusing over one reports incomplete
    coverage of a population that is complete, and `RRA-004`:97 requires a
    refusal to leave independently proven facts standing.
    """
    content = (
        _SIGNATURE_HEADER
        + b"2026-03-04,sale,posted,100.00,2,INV-1,S1,P1,C1,50.00,5.00\n"
        + b"2026-03-05,sale,posted,200.00,4,INV-2,S1,P2,C1,90.00,8.00\n"
        + b"2026-03-06,return,posted,-30.00,-1,INV-9,S1,P1,C1,0.00,\n"
    )

    result = _oracle_package(content)

    assert result.value(METRIC_DISCOUNT) == "13.00"


def test_a_complete_bucket_survives_an_incomplete_neighbour() -> None:
    """`RRA-004`:97 — a refusal leaves independently proven facts standing.

    Beverages has one row and it carries revenue; Snacks has two and one of them
    does not. The comparison publishes the bucket that is proven and refuses the
    one that is not, rather than dropping the whole dimension — and the headline
    refuses on its own account, because the file as a whole has a gap.

    Publishing `Snacks 50.00` here would state that Beverages outsold Snacks two
    to one, which the file does not say: the missing amount could be anything.
    """
    content = (
        b"date,revenue,units,invoice_no,category,branch\n"
        b"2026-01-05,100.00,2,INV-1,Beverages,Cairo\n"
        b"2026-01-06,,3,INV-2,Snacks,Giza\n"
        b"2026-01-07,50.00,1,INV-3,Snacks,Giza\n"
    )

    result = package(content)

    assert result.fact(METRIC_REVENUE) is None
    comparison = next(
        entry for entry in result.comparisons if entry.metric == "revenue_by_category"
    )
    buckets = {bucket.label: bucket for bucket in comparison.comparison.buckets}
    assert buckets["Beverages"].value == Decimal("100.00")
    assert buckets["Snacks"].value is None
    # The rows stay counted, so the refusal is legible as incompleteness rather
    # than as a category that sold nothing.
    assert buckets["Snacks"].rows == 2


def test_a_missing_key_component_refuses_only_what_needs_the_key() -> None:
    """`RRA-004`:97 — a refusal leaves independently proven facts standing.

    `RRA-003` refuses "transactions, AOV, items per transaction, and attach
    rate" on a missing key component, and names those four. Revenue, units and
    ASP need no transaction key, so a composite that cannot be built for one row
    must not take them: `_joined_key` raised, `_admitted_events` turned that into
    a package-wide `FactsRefused`, and the whole package was gone.

    `AdmittedEvents.monetary_refused` is the existing shape for exactly this and
    says why in its docstring -- "a field rather than an exception because the
    specification refuses monetary facts *and leaves count-only facts standing*.
    Raising would take both."
    """
    from tests.rra003_contract_fixtures import oracle_contract
    from tests.rra_calculation_oracle import (
        MISSING_TRANSACTION_IDENTITY_EXPECTED,
        MISSING_TRANSACTION_IDENTITY_ROWS,
        to_csv,
    )

    content = to_csv(MISSING_TRANSACTION_IDENTITY_ROWS)
    contract = oracle_contract(
        transaction_key_components=("invoice_no", "store", "date")
    )
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=contract)
    result = build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
        )
    )

    expected = MISSING_TRANSACTION_IDENTITY_EXPECTED
    # The four that need the key refuse.
    for metric in (METRIC_TRANSACTIONS, METRIC_AVERAGE_ORDER_VALUE):
        assert expected[metric] is None
        assert result.fact(metric) is None
    # The three that do not, stand.
    assert result.value(METRIC_REVENUE) == str(expected["revenue"])
    assert result.value(METRIC_UNITS) == str(expected["units"])
    assert result.value(METRIC_AVERAGE_SELLING_PRICE) == str(
        expected["average_selling_price"]
    )
