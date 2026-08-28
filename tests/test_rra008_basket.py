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
from khepri.rra.mapping import (
    SEMANTIC_CATEGORY,
    SEMANTIC_PRODUCT,
    build_mapping,
)
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    oracle_contract,
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


#: More products than `MAX_COMPARISON_BUCKETS`, with the row carrying no
#: product value ranked last on revenue -- so display truncation folds the
#: synthetic `unlabelled` bucket into `other` and hides it from a scan of the
#: published buckets.
TRUNCATED_INCOMPLETE_DIMENSION = (
    b"date,revenue,units,invoice_no,product\n"
    b"2026-01-01,990.00,2,INV-1,P01\n"
    b"2026-01-02,980.00,2,INV-2,P02\n"
    b"2026-01-03,970.00,2,INV-3,P03\n"
    b"2026-01-04,960.00,2,INV-4,P04\n"
    b"2026-01-05,950.00,2,INV-5,P05\n"
    b"2026-01-06,940.00,2,INV-6,P06\n"
    b"2026-01-07,930.00,2,INV-7,P07\n"
    b"2026-01-08,920.00,2,INV-8,P08\n"
    b"2026-01-09,910.00,2,INV-9,P09\n"
    b"2026-01-10,900.00,2,INV-10,P10\n"
    b"2026-01-11,890.00,2,INV-11,P11\n"
    b"2026-01-12,880.00,2,INV-12,P12\n"
    b"2026-01-13,870.00,2,INV-13,P13\n"
    b"2026-01-14,860.00,2,INV-14,P14\n"
    b"2026-01-15,850.00,2,INV-15,P15\n"
    b"2026-01-16,840.00,2,INV-16,P16\n"
    b"2026-01-17,830.00,2,INV-17,P17\n"
    b"2026-01-18,820.00,2,INV-18,P18\n"
    b"2026-01-19,810.00,2,INV-19,P19\n"
    b"2026-01-20,800.00,2,INV-20,P20\n"
    b"2026-01-21,790.00,2,INV-21,P21\n"
    b"2026-01-22,780.00,2,INV-22,P22\n"
    b"2026-01-28,1.00,1,INV-99,\n"
)


#: Every category present; one product missing. `RRA-008` admits the two
#: attach families independently, so the category rates must survive.
PRODUCT_GAP_CATEGORY_COMPLETE = (
    b"date,revenue,units,invoice_no,product,category\n"
    b"2026-01-05,100.00,3,INV-1,Water,Drinks\n"
    b"2026-01-06,200.00,5,INV-2,,Drinks\n"
    b"2026-01-07,60.00,1,INV-3,Juice,Snacks\n"
)


#: Every product and every category present, so both attach families publish.
GOLDEN_WITH_CATEGORY = (
    b"date,revenue,units,invoice_no,product,category\n"
    b"2026-01-05,100.00,3,INV-1,Water,Drinks\n"
    b"2026-01-06,200.00,5,INV-2,Juice,Drinks\n"
    b"2026-01-07,60.00,1,INV-3,Water,Snacks\n"
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


def _package_with_returns(content: bytes) -> FactPackage:
    """A package over an extract naming its event kinds.

    `TEST_CONTRACT` declares no event-kind column, so a return cannot be
    expressed through it at all. `oracle_contract` does, which is what the
    return-sensitive cases in this module need.
    """
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    contract = oracle_contract(status_column=None)
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=contract)
        return build_fact_package(
            AdmittedInput(
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=contract,
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


# A product column blank on two of three invoices. `rra008.basket.v1` published
# Water at 0.3333 against a denominator of three -- counting two transactions
# whose product is unknown as transactions that do not contain Water. They might.
INCOMPLETE_DIMENSION = (
    b"date,revenue,units,invoice_no,product\n"
    b"2026-01-05,100.00,3,INV-1,Water\n"
    b"2026-01-06,200.00,5,INV-2,\n"
    b"2026-01-07,60.00,1,INV-3,\n"
)


def test_one_missing_dimension_value_refuses_the_whole_attach_family() -> None:
    """`RRA-008`: "Every eligible sale row must carry the dimension value; one
    missing value refuses that dimension's entire attach family rather than
    silently entering only the denominator."

    **This test asserted the opposite under `rra008.basket.v1`.** It checked that
    Water still received a rate, which is exactly the silent-denominator entry the
    specification forbids: `_SYNTHETIC_LABELS` kept the unlabelled bucket from
    *getting* a rate, and nothing kept it out of the denominator every other rate
    divides by. Every published rate was therefore too low by an amount no reader
    could see or bound.

    Refusing is the honest answer because the true rate is not merely unmeasured:
    an unlabelled transaction may or may not contain Water, and nothing in the
    package decides which.
    """
    package = package_for(INCOMPLETE_DIMENSION)
    published = package.comparison(SEMANTIC_PRODUCT)
    assert published is not None
    assert UNLABELLED_BUCKET_LABEL in {
        bucket.label for bucket in published.comparison.buckets
    }

    attach = [
        fact for fact in facts_of(package) if fact.metric == METRIC_ATTACH_RATE
    ]
    assert not attach, [fact.value for fact in attach]

    refused = basket.refusals(package)
    assert any(
        entry.reason == basket.REASON_DIMENSION_INCOMPLETE
        and entry.metric == METRIC_ATTACH_RATE
        for entry in refused
    ), refused


def test_a_complete_dimension_still_states_every_attach_rate() -> None:
    """The other half of the rule, and the reason it is not simply "refuse".

    Refusing whenever a synthetic bucket exists would be indistinguishable from
    refusing whenever the data is imperfect. Every row here carries a product, so
    every value keeps its rate.
    """
    package = package_for(GOLDEN)
    labels = {
        basket.attached_value_of(fact, package)
        for fact in facts_of(package)
        if fact.metric == METRIC_ATTACH_RATE
    }
    assert labels == {"Water", "Juice"}


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

def test_items_per_transaction_excludes_posted_return_units() -> None:
    """Sales of 10 and 15 units with a return of -2 is 12.5000, never 11.5000.

    `_counts` divided `METRIC_UNITS` -- whose population is `financial_posted`
    and therefore includes posted *return* units -- by a transaction count that
    is sale-only. `RRA-008` is explicit: items per transaction is
    `sum(positive posted-sale units)` over the canonical sale transaction key,
    and returns enter "neither numerator nor denominator".

    The published figure moves the wrong way and stays entirely plausible: a
    reader cannot detect a basket understated by the returned units from the
    numbers beside it.
    """
    content = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-02-01,sale,400.00,10,INV-1\n"
        b"2026-02-02,sale,600.00,15,INV-2\n"
        b"2026-02-03,return,-90.00,-2,INV-3\n"
    )

    package = _package_with_returns(content)
    facts = facts_of(package)
    stated = next(
        fact for fact in facts if fact.metric == METRIC_ITEMS_PER_TRANSACTION
    )

    # Proved first: without an admitted return this case cannot show the
    # numerator excluding one, and would pass vacuously.
    assert package.event_kind_filters == ("return", "sale"), (
        "no return was admitted, so this proves nothing about excluding one"
    )
    assert stated.value == "12.5000", (
        "the return units were netted into the numerator: 23 / 2 = 11.5000"
    )
def test_display_truncation_does_not_hide_an_incomplete_dimension() -> None:
    """The refusal above, defeated by the display limit.

    `_incomplete` detected the missing value by scanning the published buckets
    for the synthetic `unlabelled` label. When a dimension carries more than
    `MAX_COMPARISON_BUCKETS` values and that bucket ranks below the limit,
    `build_comparison` folds it into `other` and the scan no longer sees it --
    so attach rates publish against an unproven dimension-complete population,
    the exact case `rra008.basket.v2`'s refusal exists for.

    A guard that cannot see the surface the risky input moved to has disarmed
    itself. The signal is now taken where the null key is *accumulated*,
    before any truncation decision, so display cannot change what completeness
    the package claims.
    """
    package = package_for(TRUNCATED_INCOMPLETE_DIMENSION)
    published = package.comparison(SEMANTIC_PRODUCT)
    assert published is not None

    # The premise: the null value really is hidden from the published buckets.
    assert UNLABELLED_BUCKET_LABEL not in {
        bucket.label for bucket in published.comparison.buckets
    }, 'the unlabelled bucket is still visible, so this proves nothing'
    assert published.comparison.truncated_values, (
        'nothing was truncated, so the hiding this case is about never happened'
    )

    attach = [
        fact for fact in facts_of(package) if fact.metric == METRIC_ATTACH_RATE
    ]
    assert not attach, [fact.value for fact in attach]

    refused = basket.refusals(package)
    assert any(
        entry.reason == basket.REASON_DIMENSION_INCOMPLETE
        and entry.metric == METRIC_ATTACH_RATE
        for entry in refused
    ), refused


def test_a_redacted_value_is_not_an_incomplete_dimension() -> None:
    """Redaction withholds a value from display; it does not make it unknown.

    Pinned beside the truncation case because both are display concerns and
    only one is a completeness concern. A flag keyed off the redaction
    sentinel rather than off a null source value would refuse every rate over
    a personal dimension, which `_incomplete` deliberately does not do.
    """
    package = package_for(GOLDEN)
    published = package.comparison(SEMANTIC_PRODUCT)
    assert published is not None

    attach = [
        fact for fact in facts_of(package) if fact.metric == METRIC_ATTACH_RATE
    ]
    assert attach, 'a complete dimension must still publish its rates'
def test_an_incomplete_product_does_not_suppress_category_attach() -> None:
    """`RRA-008`: product and category attach families "are admitted
    independently and neither suppresses the other."

    `_dimension` preferred product and returned the *first* admissible
    dimension, so the incomplete-dimension refusal took the whole attach
    family -- including a category whose every value is present and whose own
    population is provably complete. The customer lost a rate the package
    could prove, because a different dimension could not be proven.
    """
    package = package_for(PRODUCT_GAP_CATEGORY_COMPLETE)

    attach = [
        fact for fact in facts_of(package) if fact.metric == METRIC_ATTACH_RATE
    ]
    scopes = {input_name for fact in attach for input_name in fact.inputs}

    assert SEMANTIC_CATEGORY in scopes, (
        'category is complete and was suppressed by the product gap'
    )
    assert SEMANTIC_PRODUCT not in scopes, (
        'the product dimension has a missing value and must still refuse'
    )
def test_attach_rate_divides_by_sale_transactions_only() -> None:
    """`RRA-008` names the denominator as "the exact distinct canonical
    transaction set in `dimension_complete_sales:<product|category>`" -- which
    is sale-only. Returns enter "neither numerator nor denominator".

    `_attach_facts` reads `FactComparison.distinct_transactions`, which counted
    every posted transaction rather than every posted *sale* transaction. A
    dataset with returns therefore divided by a set larger than the population
    the rate claims, and every published rate came out too low.

    Two sale transactions, one of which contains Water, plus a return in its
    own transaction: the rate is 1/2, not 1/3.
    """
    content = (
        b"date,event_kind,revenue,units,invoice_no,product\n"
        b"2026-02-01,sale,400.00,10,INV-1,Water\n"
        b"2026-02-02,sale,600.00,15,INV-2,Juice\n"
        b"2026-02-03,return,-90.00,-2,INV-3,Water\n"
    )

    package = _package_with_returns(content)

    # Proved first: a return really was admitted, or this shows nothing.
    assert package.event_kind_filters == ("return", "sale")

    rates = {
        basket.attached_value_of(fact, package): fact.value
        for fact in facts_of(package)
        if fact.metric == METRIC_ATTACH_RATE
    }
    assert rates.get("Water") == "0.5000", rates
def test_every_published_attach_fact_resolves_its_value() -> None:
    """`attached_value_of` must follow `_attach_facts` across dimensions.

    Once the attach family began publishing product *and* category rates,
    `attached_value_of` still searched only the first ranked dimension through
    `_dimension()`. A category fact's identity is hashed over the category
    scope, so it matched no product bucket and the helper returned `None` for a
    fact the package had published -- a surface asking which value a rate
    belongs to would be told nothing. Found in review.
    """
    package = package_for(GOLDEN_WITH_CATEGORY)
    attach = [
        fact for fact in facts_of(package) if fact.metric == METRIC_ATTACH_RATE
    ]
    dimensions = {
        name for fact in attach for name in fact.inputs if name != 'transaction_id'
    }

    # The premise: both families really are published, or this proves nothing.
    assert dimensions == {SEMANTIC_PRODUCT, SEMANTIC_CATEGORY}, dimensions

    unresolved = [
        fact for fact in attach if basket.attached_value_of(fact, package) is None
    ]
    assert not unresolved, (
        'these published attach facts name no value: '
        f'{[fact.fact_id for fact in unresolved]}'
    )
def test_an_independently_refused_dimension_still_states_its_reason() -> None:
    """A published sibling must not erase the refusal for the affected family.

    When product is incomplete and category is not, the category rates publish --
    which is `RRA-008` admitting the two families independently. The first version
    of that change stated the family refusal only when *every* dimension was
    incomplete, so the product family vanished with no reason beside it: a
    customer saw category rates, no product rates, and nothing explaining the
    difference. Found in review.
    """
    package = package_for(PRODUCT_GAP_CATEGORY_COMPLETE)

    attach = [
        fact for fact in facts_of(package) if fact.metric == METRIC_ATTACH_RATE
    ]
    scopes = {name for fact in attach for name in fact.inputs}
    # The premise: one family published and the other did not.
    assert SEMANTIC_CATEGORY in scopes and SEMANTIC_PRODUCT not in scopes

    refused = basket.refusals(package)

    assert any(
        entry.metric == METRIC_ATTACH_RATE
        and entry.reason == basket.REASON_DIMENSION_INCOMPLETE
        for entry in refused
    ), (
        'the product family is absent with no stated reason, so its absence '
        f'reads as having nothing to say: {refused}'
    )
def test_a_return_only_value_receives_no_attach_rate() -> None:
    """`RRA-008` puts attach rate on `dimension_complete_sales:<dimension>`.

    A product carried only by a return is outside that population. It was
    published anyway, and because return transaction keys are masked it published
    `0.0000` -- which reads as "never bought alongside anything" for something
    never bought at all. The most plausible wrong number on the page.

    The earlier fix filtered the concentration ranking, which is a different
    consumer: the published buckets still carried the value and
    `_attachable` turned every one of them into a fact. Found in review.
    """
    content = (
        b"date,event_kind,revenue,units,invoice_no,product\n"
        b"2026-02-01,sale,400.00,10,INV-1,Water\n"
        b"2026-02-02,sale,600.00,15,INV-2,Juice\n"
        b"2026-02-03,return,-90.00,-2,INV-3,GhostItem\n"
    )

    package = _package_with_returns(content)
    assert package.event_kind_filters == ("return", "sale")

    rates = {
        basket.attached_value_of(fact, package): fact.value
        for fact in facts_of(package)
        if fact.metric == METRIC_ATTACH_RATE
    }

    assert 'GhostItem' not in rates, rates
    # The values that were actually sold are unaffected.
    assert rates == {'Water': '0.5000', 'Juice': '0.5000'}
def test_a_sales_only_package_predating_the_field_still_states_the_basket() -> None:
    """A historical package must not lose a figure it published correctly.

    `sale_units_total` reads back as `None` for a package stored before the field
    existed. Refusing there took items per transaction from every historical
    package -- including ones whose extract admitted no returns, where the
    sale-only sum and the headline units total are the same number and the older
    figure was right. Found in review.
    """
    from dataclasses import replace

    package = package_for(GOLDEN)
    stated = next(
        fact for fact in facts_of(package)
        if fact.metric == METRIC_ITEMS_PER_TRANSACTION
    )

    legacy = replace(package, sale_units_total=None)
    recovered = next(
        fact for fact in facts_of(legacy)
        if fact.metric == METRIC_ITEMS_PER_TRANSACTION
    )

    assert recovered.value == stated.value


def test_a_package_admitting_returns_cannot_fall_back_to_headline_units() -> None:
    """The fallback is for packages that prove the two totals agree.

    A package admitting returns is exactly the case where they differ, and where
    the headline total gives the defective figure this slice corrected. Absence of
    the field is not evidence the difference is nil.

    Paired with the case above so a fallback that always fires fails here.
    """
    from dataclasses import replace

    content = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-02-01,sale,400.00,10,INV-1\n"
        b"2026-02-02,sale,600.00,15,INV-2\n"
        b"2026-02-03,return,-90.00,-2,INV-3\n"
    )
    legacy = replace(_package_with_returns(content), sale_units_total=None)
    assert "return" in legacy.event_kind_filters

    # Asked of `derive` rather than `facts_of`: with no numerator and no
    # dimension the family refuses outright, which `facts_of` asserts against.
    derived = basket.derive(legacy)
    stated = (
        ()
        if isinstance(derived, RefusedResult)
        else tuple(
            fact for fact in derived
            if fact.metric == METRIC_ITEMS_PER_TRANSACTION
        )
    )

    assert not stated, (
        'the headline units total includes the return, so this would republish '
        f'the 11.5000 the slice corrected: {[f.value for f in stated]}'
    )
def test_attach_labels_name_the_dimension_they_belong_to() -> None:
    """Two families publishing means two buckets can carry the same value.

    A product `Water` and a category `Water` are different rates about different
    things. `ReportBundle._analysis_figure` stores the resolved name as the sole
    row and chart label, so a bare bucket label rendered them as indistinguishable
    bars. Found in review.

    `attached_value_of` is unchanged: it answers *which value* a rate is about,
    which is what a caller resolving a bucket needs. The qualification belongs at
    the display boundary.
    """
    content = (
        b"date,revenue,units,invoice_no,product,category\n"
        b"2026-01-05,100.00,3,INV-1,Water,Water\n"
        b"2026-01-06,200.00,5,INV-2,Juice,Drinks\n"
    )
    package = package_for(content)
    attach = [
        fact for fact in facts_of(package) if fact.metric == METRIC_ATTACH_RATE
    ]

    labels = {basket.attached_label_of(fact, package) for fact in attach}
    values = [basket.attached_value_of(fact, package) for fact in attach]

    # The premise: a value really is shared across the two dimensions.
    assert values.count('Water') == 2, values
    # And the display labels tell them apart.
    assert len(labels) == len(attach), labels
    assert 'Water (product)' in labels and 'Water (category)' in labels, labels
