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
from decimal import Context, Decimal, localcontext

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.analysis import comparison, growth
from khepri.rra.analysis.comparison import METRIC_DELTA_ABSOLUTE, MODE_PERIOD_OVER_PERIOD
from khepri.rra.analysis.growth import (
    CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,
    CAVEAT_ROUNDING_RESIDUAL,
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
    ARITHMETIC_PRECISION,
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
    attesting_manifest,
    oracle_contract,
    published_mapping_identity,
)

HEADER = b"date,revenue,units,invoice_no\n"
START = date(2026, 1, 5)


def _package_with_returns(content: bytes, days: tuple = ()) -> FactPackage:
    """A package over an extract naming its event kinds, coverage attested.

    `TEST_CONTRACT` declares no event-kind column, so a return cannot be
    expressed through it at all; `oracle_contract` can. Coverage is attested
    so the refusal under test comes from the returns rather than from an
    unproven window.
    """
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    contract = oracle_contract(status_column=None)
    manifest = (
        attesting_manifest(content=content, contract=contract, days=days)
        if days
        else None
    )
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=contract)
        return build_fact_package(
            AdmittedInput(
                manifest=manifest,
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=contract,
            ),
        )


def package_for(
    content: bytes,
    *,
    days: tuple[date, ...] = (),
) -> FactPackage:
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
    # Coverage is attested for exactly the days these rows carry. Growth
    # consumes the window `rra008.comparison.v2` accepted, and that family
    # refuses a window no manifest proves -- so a module whose subject is the
    # decomposition arithmetic has to attest its own coverage or every case
    # refuses as `prior_window_absent` before reaching the arithmetic it was
    # written to prove. Absent `days` leaves the package unattested, which is
    # what this module's refusal cases require.
    manifest = (
        attesting_manifest(content=content, contract=TEST_CONTRACT, days=days)
        if days
        else None
    )
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                manifest=manifest,
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
    days = tuple(START + timedelta(days=index) for index in range(len(rows)))
    return package_for(HEADER + body, days=days)


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
    # Coverage attested, so the refusal comes from the measure rather than from
    # an unproven window. Without it this refuses as `prior_window_absent` and
    # the case would prove nothing about units at all.
    days = tuple(START + timedelta(days=index) for index in range(5))
    result = growth.derive(package_for(content, days=days))
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


#: Marks the case `V-growth` must restore. Grep this name to find it.
def test_the_change_decomposed_is_the_change_the_comparison_family_states() -> None:
    """Two families, one delta.

    If growth picked its own window, the report would state a revenue delta in the
    comparison section and split a different delta in the growth section, and both
    would reconcile perfectly.

    **Consumed, not recomputed.** `growth.derive` asks
    `comparison.accepted_window` for the window that family *accepted*, rather
    than calling `windows.compared_labels` and landing on the same two labels.
    Those looked equivalent while both families agreed, and are not: the labels
    are the picking rule, blind to coverage, while acceptance is the rule plus
    the structural compatibility `rra008.comparison.v2` proves. Once comparison
    refuses a window no manifest attests, a growth family re-deriving labels
    would decompose a delta comparison declined to state.
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


# `RRA-008` publishes the price effect by subtraction rather than by independent
# rounding, so displayed reconciliation is exact by construction:
#
#   published change = round(Rc - Rp)
#   published volume = round(unrounded volume)
#   published price  = published change - published volume
#   rounding residual = published price - round(unrounded price)
#
# 8,963,136 exhaustive cases and 300,000 random ones across five precisions put
# the residual at no more than one unit of the published last place, and never
# above it. `RESIDUAL` is one of the 330 measured cases where independent
# rounding disagreed by exactly one ULP -- the whole population `rra008.growth.v1`
# refused and `v2` publishes.
#
# Prior: 100.01 over 2 units. Current: 20.02 over 1 unit.
RESIDUAL = [("5.00", 1), ("100.01", 2), ("20.02", 1), ("8.00", 1)]


def test_a_one_ulp_rounding_disagreement_is_published_rather_than_refused() -> None:
    """`rra008.growth.v1` refused this dataset. Publishing it is the change.

    Independent rounding put price at -29.98 and volume at -50.00 against a
    change of -79.99, so the additivity guard refused a decomposition that is
    arithmetically fine. `RRA-008` publishes price by subtraction instead, and
    records the disagreement as audit evidence.
    """
    facts = growth.derive(daily(RESIDUAL))
    assert not isinstance(facts, RefusedResult), facts

    change = decimal_for(facts, METRIC_REVENUE_CHANGE)
    price = decimal_for(facts, METRIC_PRICE_EFFECT)
    volume = decimal_for(facts, METRIC_VOLUME_EFFECT)
    assert change == Decimal("-79.99")
    assert volume == Decimal("-50.00")
    # By subtraction, so the published parts reconcile exactly on the page.
    assert price == change - volume == Decimal("-29.99")


def test_the_rounding_residual_is_disclosed_where_an_auditor_finds_it() -> None:
    """A published value that differs from the independently rounded one is a
    disclosure, not a silent correction.

    `RRA-008` requires the residual recorded as audit evidence. It is carried on
    the price effect, because that is the value subtraction assigned, and as a
    caveat rather than a fact -- `Fact.value` is a decimal string every consumer
    parses, and a residual is a qualification rather than a governed figure.
    """
    facts = growth.derive(daily(RESIDUAL))
    assert not isinstance(facts, RefusedResult)
    assert CAVEAT_ROUNDING_RESIDUAL in fact_for(facts, METRIC_PRICE_EFFECT).caveats

    # Absent when there is nothing to disclose: a residual-free split must not
    # carry a caveat saying its price was adjusted.
    exact = growth.derive(daily(EXACT))
    assert not isinstance(exact, RefusedResult)
    assert CAVEAT_ROUNDING_RESIDUAL not in fact_for(exact, METRIC_PRICE_EFFECT).caveats


def independently_rounded_price(rows: list[tuple[str, int]], precision: int) -> Decimal:
    """`round(U_c * (ASP_c - ASP_p))`, computed from the source rows.

    The second value the residual is measured against, and deliberately *not*
    derived from the published figures: production defines the published price as
    `change - volume`, so any quantity built from those three is that identity
    restated and cannot disagree with itself.

    `daily` lays one row per consecutive day and the compared pair is the third
    row against the second, so those two are the periods this reads.
    """
    (_, prior_units), (_, current_units) = (rows[1], rows[2])
    prior_revenue, current_revenue = Decimal(rows[1][0]), Decimal(rows[2][0])
    with localcontext(Context(prec=ARITHMETIC_PRECISION)):
        prior_asp = prior_revenue / Decimal(prior_units)
        current_asp = current_revenue / Decimal(current_units)
        unrounded = Decimal(current_units) * (current_asp - prior_asp)
        return unrounded.quantize(Decimal(1).scaleb(-precision))


def test_the_residual_never_exceeds_one_unit_of_the_published_last_place() -> None:
    """The bound `RRA-008` sets, asserted over the measured population.

    The residual is `published price - round(unrounded price)`. **The second term
    is recomputed from the source rows on purpose**: an earlier version of this
    test compared the published price against `change - volume`, which is what
    production defines it to be, so the difference was exactly zero for every
    input and the assertion held whatever the arithmetic did.

    Three roundings each move a value by at most half a unit, which would bound
    the residual at 1.5 units if they were independent. They are not -- `price` is
    derived from `change` and `volume`, so their errors partly cancel and the
    reachable bound is one unit. `RESIDUAL` is a case that actually reaches it,
    so the assertion is not vacuously satisfied by a population of zeroes.
    """
    reached = False
    for rows in (RESIDUAL, EXACT, [("5.00", 2), ("10.01", 3), ("20.02", 7), ("8.00", 4)]):
        facts = growth.derive(daily(rows))
        assert not isinstance(facts, RefusedResult), rows
        price = fact_for(facts, METRIC_PRICE_EFFECT)
        ulp = Decimal(1).scaleb(-price.precision)
        residual = Decimal(price.value) - independently_rounded_price(
            rows, price.precision
        )
        assert abs(residual) <= ulp, (rows, residual)
        reached = reached or residual != 0
    assert reached, "no case produced a residual, so the bound was never exercised"


def test_a_total_refusal_is_recorded_once_rather_than_twice() -> None:
    """`refusals` is the per-mode record a *partly* refusing family needs.

    Growth splits one mode into three metrics from a single `_Split`: either all
    three are stated or none is. `derive` already returns a total refusal as the
    section's own reason, so repeating it here would render each disclosure twice
    -- once as the section reason and once as a caveat scoped to that section.

    Asserted against a dataset that genuinely refuses, so the empty tuple is the
    considered answer for a real refusal rather than a vacuous pass over a
    package that had nothing to refuse.
    """
    package = daily([("50.00", 5), ("100.00", 0), ("180.00", 12), ("60.00", 6)])
    refused = growth.derive(package)
    assert isinstance(refused, RefusedResult)
    assert refused.reason == REASON_UNITS_ABSENT
    assert growth.refusals(package) == ()



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


def test_growth_reports_the_cause_comparison_gave_for_the_window() -> None:
    """Growth consumes comparison's acceptance, so it reports comparison's cause.

    An unattested package has a prior period; what it lacks is proof the two
    windows are comparable. Reporting `prior_window_absent` told the customer to
    export more history, which produces the same refusal again -- the same
    misattribution `comparison._absent_reason` was corrected for, one module
    over. Found in review.
    """
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},{amount},{units},INV-{index}\n".encode()
        for index, (amount, units) in enumerate(EXACT)
    )
    unattested = package_for(HEADER + body)
    assert not unattested.coverage_signatures, "the case needs coverage unproven"

    refused = growth.derive(unattested)
    assert isinstance(refused, RefusedResult)
    assert refused.reason == comparison.REASON_COVERAGE_INCOMPATIBLE


def test_a_dataset_with_no_prior_period_still_says_so() -> None:
    """The converse, so the coverage reason cannot swallow the absent one."""
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},{amount},{units},INV-{index}\n".encode()
        for index, (amount, units) in enumerate(EXACT[:2])
    )
    days = tuple(START + timedelta(days=index) for index in range(2))
    refused = growth.derive(package_for(HEADER + body, days=days))
    assert isinstance(refused, RefusedResult)
    assert refused.reason == REASON_PRIOR_WINDOW_ABSENT
def test_a_return_in_a_compared_window_refuses_growth() -> None:
    """`RRA-008`: both aligned windows must be "return-free posted-sale
    populations over `sales_complete_revenue_units`", and "a return \u2026
    refuses growth."

    `_periods` reads the revenue and units trends, whose totals are
    `financial_posted` and therefore include posted returns. A window
    containing a return published a decomposition without proving a
    return-free basis -- and the specification does not ask for the returns to
    be netted out, it asks for the decomposition to be refused.
    """
    # The return must land inside a *compared* window. `windows.settled` drops
    # the first and last buckets, so with five days the compared pair is the
    # 7th against the 6th -- an earlier draft of this test put the return on
    # the 8th, outside both, and passed only because the refusal was
    # package-wide. Review caught it.
    content = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-01-05,sale,100.00,10,INV-1\n"
        b"2026-01-06,sale,200.00,20,INV-2\n"
        b"2026-01-07,sale,300.00,25,INV-3\n"
        b"2026-01-07,return,-50.00,-5,INV-4\n"
        b"2026-01-09,sale,120.00,8,INV-5\n"
    )
    days = tuple(START + timedelta(days=index) for index in range(4))

    package = _package_with_returns(content, days=days)
    # Proved first: a return really was admitted, or this shows nothing.
    assert package.event_kind_filters == ("return", "sale")

    result = growth.derive(package)

    assert isinstance(result, RefusedResult), result
    assert result.reason == growth.REASON_RETURNS_PRESENT, result
def test_a_return_outside_both_windows_does_not_refuse_growth() -> None:
    """`RRA-008` makes returns a *window-level* precondition, not a package one.

    "Both aligned windows must be return-free posted-sale populations" -- so a
    return in some period neither compared window covers says nothing about
    either. The first version of this guard read a package-wide caveat and
    refused a decomposition that was perfectly valid. Found in review.

    Paired with the case above so a guard that simply never refuses fails there,
    and one that always refuses fails here.
    """
    content = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-01-05,sale,100.00,10,INV-1\n"
        b"2026-01-06,sale,200.00,20,INV-2\n"
        b"2026-01-07,sale,300.00,25,INV-3\n"
        b"2026-01-09,sale,120.00,8,INV-5\n"
        b"2026-01-09,return,-50.00,-5,INV-6\n"
    )
    days = tuple(START + timedelta(days=index) for index in range(5))

    package = _package_with_returns(content, days=days)
    assert package.event_kind_filters == ("return", "sale")
    # The premise: the return is in a period neither compared window covers.
    window = comparison.accepted_window(package, MODE_PERIOD_OVER_PERIOD)
    assert window is not None
    compared = {window.current.label, window.prior.label}
    assert not compared & set(package.returning_periods), (
        f'the return landed inside a compared window: {compared} vs '
        f'{package.returning_periods}'
    )

    result = growth.derive(package)

    assert not isinstance(result, RefusedResult), result
