"""Basket structure: items per transaction, and attach rate per published value.

The test that matters most is that a row count is never a transaction count. Water
below sits in three rows and three invoices while Juice sits in one row and one
invoice, so the two coincide -- and the fixture is built so that the *items* count
(eleven units over four rows) cannot be mistaken for either.

Packages are built from real CSV bytes through the real pipeline, as in the other
`RRA-008` test modules.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.aggregates import UNLABELLED_BUCKET_LABEL
from khepri.rra.analysis import basket
from khepri.rra.analysis.basket import (
    BASKET_FORMULA_VERSION,
    METRIC_ATTACH_RATE,
    METRIC_ITEMS_PER_TRANSACTION,
    REASON_DIMENSION_ABSENT,
    REASON_TRANSACTION_IDENTIFIER_ABSENT,
)
from khepri.rra.bundle import SECTION_BASKET, SECTION_REASONS
from khepri.rra.facts import (
    CAVEAT_BUCKETS_TRUNCATED,
    REASON_INCOMPLETE_IDENTIFIERS,
    REASON_INPUT_UNAVAILABLE,
    UNIT_RATIO,
    AdmittedInput,
    Fact,
    FactPackage,
    RefusedResult,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import SEMANTIC_PRODUCT, build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    published_mapping_identity,
)

# Eleven units over four rows, in three invoices. Water is in all three invoices;
# Juice is in one. No two of {rows, units, transactions} are equal, so a metric
# reading the wrong one cannot pass by coincidence.
GOLDEN = (
    b"date,revenue,units,invoice_no,product\n"
    b"2026-01-05,100.00,3,INV-1,Water\n"
    b"2026-01-05,50.00,2,INV-1,Juice\n"
    b"2026-01-06,200.00,5,INV-2,Water\n"
    b"2026-01-07,60.00,1,INV-3,Water\n"
)


def package_for(content: bytes) -> FactPackage:
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


def facts_of(package: FactPackage) -> tuple[Fact, ...]:
    derived = basket.derive(package)
    assert not isinstance(derived, RefusedResult)
    return derived


def test_items_per_transaction_divides_units_by_transactions() -> None:
    """Eleven units in three transactions, not four rows in three.

    `RRA-008` says *items*, and the governed items measure is `METRIC_UNITS`. Row
    count is line-item count: reading it here would report 1.3333 instead of
    3.6667 and look entirely plausible.
    """
    facts = facts_of(package_for(GOLDEN))
    stated = next(fact for fact in facts if fact.metric == METRIC_ITEMS_PER_TRANSACTION)
    assert stated.value == "3.6667"
    assert stated.unit_kind == UNIT_RATIO


def test_attach_rate_is_the_share_of_transactions_containing_the_value() -> None:
    """Water is in three invoices of three; Juice in one of three.

    Juice occupies one row of four. A rate derived from rows would report 0.2500
    and reconcile perfectly against a row count nobody disputed.
    """
    package = package_for(GOLDEN)
    rates = {
        basket.attached_value_of(fact, package): Decimal(fact.value)
        for fact in facts_of(package)
        if fact.metric == METRIC_ATTACH_RATE
    }
    assert rates == {"Water": Decimal("1.0000"), "Juice": Decimal("0.3333")}


def test_attach_rate_names_one_fact_per_published_value() -> None:
    """Distinct scope, so two values cannot share a citation identifier."""
    package = package_for(GOLDEN)
    attach = [fact for fact in facts_of(package) if fact.metric == METRIC_ATTACH_RATE]
    assert len({fact.fact_id for fact in attach}) == len(attach) == 2
    assert len({fact.citation_id for fact in attach}) == 2


def test_the_truncated_remainder_gets_no_attach_rate() -> None:
    """`other` is not "a given admissible dimension value".

    Its transaction count is the union of everything truncated, so a rate over it
    would state the share of transactions containing *something unnamed* -- true,
    and useless to act on.
    """
    header = b"date,revenue,units,invoice_no,product\n"
    rows = [
        f"2026-01-05,{100 - index}.00,1,INV-{index},P{index:03d}\n".encode()
        for index in range(25)
    ]
    package = package_for(header + b"".join(rows))
    labels = {
        basket.attached_value_of(fact, package)
        for fact in facts_of(package)
        if fact.metric == METRIC_ATTACH_RATE
    }
    assert "other" not in labels
    assert len(labels) == 20


def test_items_per_transaction_survives_the_loss_of_attach_rate() -> None:
    """A partial family is not a broken one.

    `RRA-008` refuses "the affected result", so a dataset with transactions but no
    product or category still states how many items a basket held.
    """
    content = (
        b"date,revenue,units,invoice_no\n"
        b"2026-01-05,100.00,3,INV-1\n"
        b"2026-01-06,200.00,5,INV-2\n"
    )
    package = package_for(content)
    facts = facts_of(package)

    assert {fact.metric for fact in facts} == {METRIC_ITEMS_PER_TRANSACTION}
    # `dimension_absent`, not `aggregate_unavailable`: the aggregate exists now, and
    # a report with no admissible dimension could not carry attach rate even so.
    # Naming the aggregate would explain the wrong failed precondition. Both the
    # plan and bundle.py reserve this code for exactly this case.
    assert [refusal.reason for refusal in basket.refusals(package)] == [
        REASON_DIMENSION_ABSENT
    ]


def test_refuses_both_metrics_when_no_identifier_is_mapped() -> None:
    content = (
        b"date,revenue,units,product\n"
        b"2026-01-05,100.00,3,Water\n"
        b"2026-01-06,200.00,5,Water\n"
    )
    result = basket.derive(package_for(content))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_TRANSACTION_IDENTIFIER_ABSENT

    reasons = {refusal.reason for refusal in basket.refusals(package_for(content))}
    assert reasons == {REASON_TRANSACTION_IDENTIFIER_ABSENT}


def test_an_incomplete_identifier_column_says_so_rather_than_absent() -> None:
    """A column with gaps is not a missing column, and the package already knows.

    `METRIC_TRANSACTIONS` is refused with `incomplete_transaction_identifiers` for
    this input, so the cause is read from the package rather than re-decided here.
    """
    content = (
        b"date,revenue,units,invoice_no,product\n"
        b"2026-01-05,100.00,3,INV-1,Water\n"
        b"2026-01-06,200.00,5,,Water\n"
    )
    result = basket.derive(package_for(content))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_INCOMPLETE_IDENTIFIERS


def test_the_synthetic_unlabelled_bucket_gets_no_attach_rate() -> None:
    """A null is not "a given admissible dimension value", just as `other` is not.

    Rows with no product land in the synthetic `unlabelled` bucket. A rate over it
    would state the share of transactions containing *no value*, which `RRA-008`
    does not authorize and a reader would read as a product.

    A source value literally spelled "unlabelled" is not affected: `build_comparison`
    disambiguates any label that would shadow a reserved synthetic bucket.
    """
    content = (
        b"date,revenue,units,invoice_no,product\n"
        b"2026-01-05,100.00,3,INV-1,Water\n"
        b"2026-01-06,200.00,5,INV-2,\n"
        b"2026-01-07,60.00,1,INV-3,\n"
    )
    package = package_for(content)
    published = package.comparison(SEMANTIC_PRODUCT)
    assert published is not None
    assert UNLABELLED_BUCKET_LABEL in {
        bucket.label for bucket in published.comparison.buckets
    }

    labels = {
        basket.attached_value_of(fact, package)
        for fact in facts_of(package)
        if fact.metric == METRIC_ATTACH_RATE
    }
    assert labels == {"Water"}


def test_attach_rate_uses_whatever_measure_ranked_the_dimension() -> None:
    """Attach rate needs no revenue, so an absent revenue column must not refuse it.

    An input mapping units, an identifier and a product is admissible -- units is a
    core measure -- and the package publishes a *units* comparison carrying the
    transaction counts. Looking only at the revenue comparison refused a rate every
    input for which was present.
    """
    content = (
        b"date,units,invoice_no,product\n"
        b"2026-01-05,3,INV-1,Water\n"
        b"2026-01-05,2,INV-1,Juice\n"
        b"2026-01-06,5,INV-2,Water\n"
    )
    package = package_for(content)
    assert package.comparison(SEMANTIC_PRODUCT) is None  # no revenue comparison exists

    rates = {
        basket.attached_value_of(fact, package): Decimal(fact.value)
        for fact in facts_of(package)
        if fact.metric == METRIC_ATTACH_RATE
    }
    assert rates == {"Water": Decimal("1.0000"), "Juice": Decimal("0.5000")}


def test_attach_rate_carries_the_qualifications_of_the_buckets_it_covers() -> None:
    """These rates cover the *published* buckets, so a truncation caveat applies.

    This is the opposite of the concentration family, which drops the same caveat:
    its curve spans the full distinct set and is not limited by the truncation.
    Attach rate is limited by it exactly, so dropping the qualification would make
    a partial set of rates read as a complete one.

    Items per transaction is dimension-independent and takes none of it.
    """
    header = b"date,revenue,units,invoice_no,product\n"
    rows = [
        f"2026-01-05,{100 - index}.00,1,INV-{index},P{index:03d}\n".encode()
        for index in range(25)
    ]
    package = package_for(header + b"".join(rows))
    published = package.comparison(SEMANTIC_PRODUCT)
    assert published is not None
    assert CAVEAT_BUCKETS_TRUNCATED in published.caveats

    for fact in facts_of(package):
        if fact.metric == METRIC_ATTACH_RATE:
            assert CAVEAT_BUCKETS_TRUNCATED in fact.caveats
        else:
            assert fact.caveats == ()


def test_every_fact_records_this_family_formula_version() -> None:
    for fact in facts_of(package_for(GOLDEN)):
        assert fact.formula_version == BASKET_FORMULA_VERSION


def test_only_the_whole_family_reasons_are_section_reasons() -> None:
    """The section may state a reason only when it has no figure left to show.

    A refused section carries no figures, so admitting a per-metric reason as a
    section state would suppress the metric that survived. The two identifier
    failures take both metrics and belong here; the other two take one each and
    ride on the affected result instead.
    """
    assert REASON_TRANSACTION_IDENTIFIER_ABSENT in SECTION_REASONS[SECTION_BASKET]
    assert REASON_INCOMPLETE_IDENTIFIERS in SECTION_REASONS[SECTION_BASKET]
    # Per-metric when attach rate stands, whole-family when nothing does.
    assert REASON_INPUT_UNAVAILABLE in SECTION_REASONS[SECTION_BASKET]

    # Never a whole-family refusal: reaching one needs items per transaction to
    # have refused as well, and its reason is the one recorded first.
    assert REASON_DIMENSION_ABSENT not in SECTION_REASONS[SECTION_BASKET]


def test_a_family_refusal_only_ever_names_a_reason_the_section_can_state() -> None:
    """Whatever refuses the whole family must be sayable by the section.

    Otherwise assembly has a refused section and no governed reason for it, which
    is the fail-closed hole the reason table exists to close. Every input short of
    a transaction identifier leaves at least one metric standing, so the only
    whole-family refusals are the two identifier failures.
    """
    without_units_or_dimension = (
        b"date,revenue,invoice_no\n"
        b"2026-01-05,100.00,INV-1\n"
        b"2026-01-06,200.00,INV-2\n"
    )
    for content in (without_units_or_dimension, GOLDEN):
        derived = basket.derive(package_for(content))
        if isinstance(derived, RefusedResult):
            assert derived.reason in SECTION_REASONS[SECTION_BASKET]
