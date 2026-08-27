"""Price and volume decomposition of one governed revenue change.

Additivity is asserted as **exact equality, never a tolerance**. That is the point
of the family: a split whose parts do not sum to the change it claims to explain is
a reconciliation failure, and `RRA-008` says to treat it as one.

Packages are built from real CSV bytes through the real pipeline, as in the other
two `RRA-008` test modules.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.analysis import comparison, growth
from khepri.rra.analysis.comparison import METRIC_DELTA_ABSOLUTE, MODE_PERIOD_OVER_PERIOD
from khepri.rra.analysis.growth import (
    CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,
    GROWTH_FORMULA_VERSION,
    METRIC_PRICE_EFFECT,
    METRIC_REVENUE_CHANGE,
    METRIC_VOLUME_EFFECT,
    REASON_NOT_ADDITIVE,
    REASON_PRIOR_WINDOW_ABSENT,
    REASON_UNITS_ABSENT,
)
from khepri.rra.bundle import SECTION_GROWTH, SECTION_REASONS
from khepri.rra.facts import (
    REASON_INPUT_UNAVAILABLE,
    UNIT_MONETARY,
    AdmittedInput,
    Fact,
    FactPackage,
    RefusedResult,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    published_mapping_identity,
)

HEADER = b"date,revenue,units,invoice_no\n"
START = date(2026, 1, 5)


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


def daily(rows: list[tuple[str, int]]) -> FactPackage:
    """One row per consecutive day, so the compared pair is the third and fourth.

    A period is settled when data exists on both sides of it, so four days leave
    two settled ones: day two and day three. The pair compared is therefore the
    third row against the second.
    """
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},{amount},{units},INV-{index}\n".encode()
        for index, (amount, units) in enumerate(rows)
    )
    return package_for(HEADER + body)


def fact_for(facts: tuple[Fact, ...], metric: str) -> Fact:
    return next(fact for fact in facts if fact.metric == metric)


def decimal_for(facts: tuple[Fact, ...], metric: str) -> Decimal:
    return Decimal(fact_for(facts, metric).value)


# Prior period: 100.00 over 10 units, so an average selling price of 10.00.
# Current period: 180.00 over 12 units, so 15.00. The change is 80.00, of which
# volume explains 10.00 * 2 = 20.00 and price explains 12 * 5.00 = 60.00.
EXACT = [("50.00", 5), ("100.00", 10), ("180.00", 12), ("60.00", 6)]


def test_parts_sum_exactly_to_the_revenue_change() -> None:
    facts = growth.derive(daily(EXACT))
    assert not isinstance(facts, RefusedResult)

    price = decimal_for(facts, METRIC_PRICE_EFFECT)
    volume = decimal_for(facts, METRIC_VOLUME_EFFECT)
    change = decimal_for(facts, METRIC_REVENUE_CHANGE)
    assert price + volume == change
    assert change == Decimal("80.00")


def test_the_interaction_term_lands_in_the_price_effect() -> None:
    """`units_current` multiplies the price change, not `units_prior`.

    That choice is what assigns the interaction term to price, and it is the only
    part of the formula a reader cannot infer from the totals.
    """
    facts = growth.derive(daily(EXACT))
    assert not isinstance(facts, RefusedResult)

    assert decimal_for(facts, METRIC_VOLUME_EFFECT) == Decimal("20.00")
    assert decimal_for(facts, METRIC_PRICE_EFFECT) == Decimal("60.00")
    assert fact_for(facts, METRIC_PRICE_EFFECT).unit_kind == UNIT_MONETARY


def test_the_interaction_assignment_is_recorded_where_a_reader_sees_it() -> None:
    """A caveat, not a fact.

    `Fact.value` is a decimal string every consumer parses -- the workbook writes
    it, the narrative validates numbers against it. A fact whose value read
    "price" would be a number-shaped hole in that contract. `RRA-008` requires the
    assignment recorded, and a caveat is the governed channel for a qualification
    carried into both languages.
    """
    facts = growth.derive(daily(EXACT))
    assert not isinstance(facts, RefusedResult)

    assert CAVEAT_INTERACTION_ASSIGNED_TO_PRICE in fact_for(facts, METRIC_PRICE_EFFECT).caveats
    # The volume effect does not carry it: it is not where the term went.
    assert CAVEAT_INTERACTION_ASSIGNED_TO_PRICE not in (
        fact_for(facts, METRIC_VOLUME_EFFECT).caveats
    )


def test_additivity_survives_a_non_terminating_average_selling_price() -> None:
    """10.01 over 3 units does not divide evenly, and the split must still add up.

    Both effects are derived at the package's arithmetic precision and quantized
    once, at the end. Quantizing an intermediate average would leave the published
    parts summing to something other than the published change.
    """
    facts = growth.derive(daily([("5.00", 2), ("10.01", 3), ("20.02", 7), ("8.00", 4)]))
    assert not isinstance(facts, RefusedResult)

    price = decimal_for(facts, METRIC_PRICE_EFFECT)
    volume = decimal_for(facts, METRIC_VOLUME_EFFECT)
    assert price + volume == decimal_for(facts, METRIC_REVENUE_CHANGE)


def test_refuses_when_units_are_zero_in_either_period() -> None:
    """An average selling price over no units is not a number."""
    result = growth.derive(daily([("50.00", 5), ("100.00", 0), ("180.00", 12), ("60.00", 6)]))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_UNITS_ABSENT


def test_refuses_when_no_units_are_mapped() -> None:
    content = (
        b"date,revenue,invoice_no\n"
        b"2026-01-05,50.00,INV-0\n"
        b"2026-01-06,100.00,INV-1\n"
        b"2026-01-07,180.00,INV-2\n"
        b"2026-01-08,60.00,INV-3\n"
    )
    result = growth.derive(package_for(content))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_UNITS_ABSENT


def test_refuses_with_the_cause_when_no_pair_of_periods_is_settled() -> None:
    """A coverage gap is not "units absent", and saying so would blame the measure.

    Three days leave one settled period, whose predecessor is the unsettled first
    day. There is nothing to compare, and the units were never the problem.
    """
    result = growth.derive(daily([("50.00", 5), ("100.00", 10), ("180.00", 12)]))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_PRIOR_WINDOW_ABSENT


def test_the_change_decomposed_is_the_change_the_comparison_family_states() -> None:
    """Two families, one delta.

    If growth picked its own window, the report would state a revenue delta in the
    comparison section and split a different delta in the growth section, and both
    would reconcile perfectly.
    """
    package = daily(EXACT)
    split = growth.derive(package)
    compared = comparison.derive(package)
    assert not isinstance(split, RefusedResult)
    assert not isinstance(compared, RefusedResult)

    stated = next(
        fact
        for fact in compared
        if fact.metric == METRIC_DELTA_ABSOLUTE
        and comparison.mode_of(fact) == MODE_PERIOD_OVER_PERIOD
    )
    assert decimal_for(split, METRIC_REVENUE_CHANGE) == Decimal(stated.value)


def test_every_fact_records_this_family_formula_version() -> None:
    facts = growth.derive(daily(EXACT))
    assert not isinstance(facts, RefusedResult)
    for fact in facts:
        assert fact.formula_version == GROWTH_FORMULA_VERSION


def test_every_refusal_reason_is_a_governed_section_reason() -> None:
    """All four, or a section could not state why it has nothing to show."""
    for reason in (
        REASON_UNITS_ABSENT,
        REASON_NOT_ADDITIVE,
        REASON_PRIOR_WINDOW_ABSENT,
        REASON_INPUT_UNAVAILABLE,
    ):
        assert reason in SECTION_REASONS[SECTION_GROWTH]
