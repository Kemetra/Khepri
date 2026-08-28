"""Concentration over the full distinct-value set, never over the display buckets.

Packages are built from real CSV bytes through the real pipeline, as in
`test_rra008_comparison.py`. A fabricated `FactPackage` could assert a curve the
builder would never produce, and the failure this family exists to prevent is
exactly a full-set statistic that was never measured over the full set.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.aggregates import MAX_COMPARISON_BUCKETS, OTHER_BUCKET_LABEL
from khepri.rra.analysis import concentration
from khepri.rra.analysis.concentration import (
    CONCENTRATION_FORMULA_VERSION,
    METRIC_DISTINCT_VALUES,
    METRIC_RANKED_VALUES,
    METRIC_TOP_DECILE_SHARE,
    METRIC_TOP_QUARTILE_SHARE,
    REASON_AGGREGATE_UNAVAILABLE,
    REASON_DISTINCT_SET_UNCOMPUTABLE,
)
from khepri.rra.bundle import SECTION_CONCENTRATION, SECTION_REASONS
from khepri.rra.facts import (
    CAVEAT_BUCKETS_TRUNCATED,
    UNIT_COUNT,
    UNIT_RATIO,
    AdmittedInput,
    Fact,
    FactPackage,
    RefusedResult,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import SEMANTIC_CATEGORY, SEMANTIC_PRODUCT, build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    oracle_contract,
    published_mapping_identity,
)

PRODUCT_HEADER = b"date,revenue,units,invoice_no,product\n"
CATEGORY_HEADER = b"date,revenue,units,invoice_no,category\n"
BARE_HEADER = b"date,revenue,units,invoice_no\n"


def _package_with_returns(content: bytes) -> FactPackage:
    """A package over an extract naming its event kinds.

    The module contract declares no event-kind column, so a return cannot be
    expressed through it; `oracle_contract` does.
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


def ranked_products(revenues: list[int], header: bytes = PRODUCT_HEADER) -> FactPackage:
    """One row per value, so the rank order is exactly the order given."""
    body = b"".join(
        f"2026-01-{5 + index % 20:02d},{amount}.00,1,INV-{index},V{index:03d}\n".encode()
        for index, amount in enumerate(revenues)
    )
    return package_for(header + body)


def fact_for(facts: tuple[Fact, ...], metric: str) -> Fact:
    return next(fact for fact in facts if fact.metric == metric)


def test_counts_are_the_full_distinct_set_not_the_published_buckets() -> None:
    """The whole point of the family, and of the `RRA-004` amendment behind it.

    Twenty-five values reach the package as twenty buckets plus `other`. A count
    of twenty-one would be the display talking, and a count of twenty-five taken
    from those buckets would be a fabrication.
    """
    distinct = MAX_COMPARISON_BUCKETS + 5
    package = ranked_products([(distinct - index) * 10 for index in range(distinct)])

    published = package.comparison(SEMANTIC_PRODUCT)
    assert published is not None
    assert len(published.comparison.buckets) == MAX_COMPARISON_BUCKETS + 1
    assert published.comparison.buckets[-1].label == OTHER_BUCKET_LABEL

    facts = concentration.derive(package)
    assert not isinstance(facts, RefusedResult)
    assert fact_for(facts, METRIC_DISTINCT_VALUES).value == str(distinct)
    assert fact_for(facts, METRIC_RANKED_VALUES).value == str(distinct)
    assert fact_for(facts, METRIC_DISTINCT_VALUES).unit_kind == UNIT_COUNT


def test_top_decile_and_quartile_shares_are_measured() -> None:
    """Ten values summing to 550: the top one holds 100, the top three hold 270.

    A decile of ten ranked values is one value and a quartile is three, both
    rounded up. Rounding down would give a decile of zero values and report a
    nought per cent share, which is false rather than conservative.
    """
    facts = concentration.derive(ranked_products([100, 90, 80, 70, 60, 50, 40, 30, 20, 10]))
    assert not isinstance(facts, RefusedResult)

    decile = fact_for(facts, METRIC_TOP_DECILE_SHARE)
    quartile = fact_for(facts, METRIC_TOP_QUARTILE_SHARE)
    assert decile.value == "0.1818"
    assert quartile.value == "0.4909"
    assert decile.unit_kind == UNIT_RATIO
    assert Decimal(quartile.value) > Decimal(decile.value)


def test_no_classification_bands_are_assigned() -> None:
    """`RRA-008` forbids fixed bands, so no fact may name one.

    "Highly concentrated" is a judgement about a threshold nobody approved, and a
    measured share lets a reader apply their own.
    """
    facts = concentration.derive(ranked_products([100, 50, 25]))
    assert not isinstance(facts, RefusedResult)
    metrics = {fact.metric for fact in facts}
    assert not any("class" in metric or "band" in metric for metric in metrics)
    assert metrics == {
        METRIC_DISTINCT_VALUES,
        METRIC_RANKED_VALUES,
        METRIC_TOP_DECILE_SHARE,
        METRIC_TOP_QUARTILE_SHARE,
    }


def test_product_is_preferred_when_both_dimensions_are_admissible() -> None:
    content = (
        b"date,revenue,units,invoice_no,product,category\n"
        b"2026-01-05,100.00,1,INV-1,Water,Drinks\n"
        b"2026-01-06,50.00,1,INV-2,Juice,Drinks\n"
    )
    facts = concentration.derive(package_for(content))
    assert not isinstance(facts, RefusedResult)
    # Two products, one category. A count of one would mean category won.
    assert fact_for(facts, METRIC_DISTINCT_VALUES).value == "2"
    assert concentration.dimension_of(fact_for(facts, METRIC_DISTINCT_VALUES)) == (
        SEMANTIC_PRODUCT
    )


def test_category_is_used_when_no_product_dimension_is_mapped() -> None:
    facts = concentration.derive(
        ranked_products([100, 90, 80], header=CATEGORY_HEADER),
    )
    assert not isinstance(facts, RefusedResult)
    assert fact_for(facts, METRIC_DISTINCT_VALUES).value == "3"
    assert concentration.dimension_of(fact_for(facts, METRIC_DISTINCT_VALUES)) == (
        SEMANTIC_CATEGORY
    )


def test_refuses_when_neither_product_nor_category_is_available() -> None:
    """Store and channel are not concentration dimensions.

    `RRA-008` says "rank products or categories", and ranking branches by revenue
    would answer a question nobody governed.
    """
    body = b"2026-01-05,100.00,1,INV-1\n2026-01-06,50.00,1,INV-2\n"
    result = concentration.derive(package_for(BARE_HEADER + body))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_AGGREGATE_UNAVAILABLE


def test_refuses_rather_than_stating_shares_of_a_non_positive_total() -> None:
    """A share of nothing is not zero, and a share of a loss is not a share.

    The curve is absent by construction here, so the family refuses instead of
    dividing by a total that makes every result meaningless.
    """
    result = concentration.derive(ranked_products([100, -100]))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_DISTINCT_SET_UNCOMPUTABLE


def test_a_full_set_figure_does_not_inherit_the_truncation_caveat() -> None:
    """The caveat qualifies the published buckets, and these facts are not those.

    Attaching it here would disclose the opposite of the truth: that the figure is
    limited by a truncation it was specifically derived to see past.
    """
    distinct = MAX_COMPARISON_BUCKETS + 5
    package = ranked_products([(distinct - index) * 10 for index in range(distinct)])
    published = package.comparison(SEMANTIC_PRODUCT)
    assert published is not None
    assert CAVEAT_BUCKETS_TRUNCATED in published.caveats

    facts = concentration.derive(package)
    assert not isinstance(facts, RefusedResult)
    for fact in facts:
        assert CAVEAT_BUCKETS_TRUNCATED not in fact.caveats


def test_every_fact_records_this_family_formula_version() -> None:
    """Not the package's, which would say nothing about how these were derived."""
    facts = concentration.derive(ranked_products([100, 50]))
    assert not isinstance(facts, RefusedResult)
    for fact in facts:
        assert fact.formula_version == CONCENTRATION_FORMULA_VERSION


def test_both_refusal_reasons_are_governed_section_reasons() -> None:
    """A section that cannot state its reason fails misleadingly, not closed."""
    assert REASON_AGGREGATE_UNAVAILABLE in SECTION_REASONS[SECTION_CONCENTRATION]
    assert REASON_DISTINCT_SET_UNCOMPUTABLE in SECTION_REASONS[SECTION_CONCENTRATION]
#: One eligible posted sale carrying no product value. `build_comparison`
#: retains it as the synthetic `unlabelled` accumulator.
_MISSING_PRODUCT_VALUE = (
    b"date,revenue,units,invoice_no,product\n"
    b"2026-01-05,100.00,3,INV-1,Water\n"
    b"2026-01-06,200.00,5,INV-2,\n"
    b"2026-01-07,60.00,1,INV-3,Juice\n"
)

def test_a_missing_dimension_value_refuses_the_curve() -> None:
    """`RRA-008`: "A missing dimension on any eligible posted sale, including a
    zero-revenue row, refuses that dimension. `None` and synthetic
    `unlabelled` are never ranked."

    `_found` checked only that a comparison existed. An eligible sale with no
    product is retained by `build_comparison` as a synthetic `unlabelled`
    accumulator and entered the curve, so the published shares -- and the
    top-decile and top-quartile figures read off them -- described a
    distribution containing an unnamed accumulator.
    """
    package = package_for(_MISSING_PRODUCT_VALUE)

    result = concentration.derive(package)

    assert isinstance(result, RefusedResult), result
    assert concentration.curve_series(package) is None, (
        'the curve still publishes the distribution containing the unnamed value'
    )
def test_concentration_ranks_posted_sale_revenue_not_net_revenue() -> None:
    """`RRA-008`: concentration "ranks posted-sale revenue over the full,
    non-null, admissible product or category set with complete sale revenue".

    The family read the ordinary revenue comparison, built from
    return-inclusive financial revenue, so a value with heavy returns ranked
    below its true sale contribution -- and the top-decile and top-quartile
    shares beside the curve inherited the same base.

    Water sells 1000 and is returned 900; Juice sells 600. On sale revenue
    Water leads with 1000 of 1600; on net revenue it trails with 100 of 700,
    so the leading share is 0.6250 rather than 0.8571.
    """
    content = (
        b"date,event_kind,revenue,units,invoice_no,product\n"
        b"2026-02-01,sale,1000.00,10,INV-1,Water\n"
        b"2026-02-02,sale,600.00,6,INV-2,Juice\n"
        b"2026-02-03,return,-900.00,-9,INV-3,Water\n"
    )

    package = _package_with_returns(content)
    assert package.event_kind_filters == ("return", "sale")

    published = package.comparison(SEMANTIC_PRODUCT)
    assert published is not None
    curve = published.comparison.curve
    assert curve is not None, 'no curve was retained, so nothing is ranked'

    leading = curve.shares[0]
    assert str(leading) == '0.6250', (
        'the curve ranks net financial revenue: Water is placed by 100 rather '
        'than by the 1000 it sold'
    )
