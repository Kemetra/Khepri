"""The populations `rra004.formula.v2` computes each metric over.

`RRA-004`'s core-formula table assigns each metric an exact population, and
`RRA-004`:92 states the rule the current code breaks in four places:
"Transactions count posted sales only."

`facts` applies no event-kind filter anywhere. `admission` records each event's
kind and then selects rows on status alone, so a return survives into the
transaction count, both sides of the AOV ratio, and both sides of ASP. Returns
themselves are read off a separately mapped column, which `RRA-003` forbids
outright: "No independently mapped return-amount measure is admitted."

Expected values come from `tests/rra_calculation_oracle.py`, hand-derived
outside every production helper.
"""

from __future__ import annotations

import hashlib

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.facts import (
    METRIC_AVERAGE_SELLING_PRICE,
    REASON_INPUT_UNAVAILABLE,
    AdmittedInput,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import oracle_contract
from tests.rra_calculation_oracle import (
    MESSY_RETURNS_EXPECTED,
    MESSY_RETURNS_ROWS,
    to_csv,
)


def _package_from(content: bytes, contract):
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
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


def _returns_package():
    """Two posted sales and one posted return, admitted as what they are."""
    return _package_from(to_csv(MESSY_RETURNS_ROWS), oracle_contract())


def test_a_return_is_not_a_transaction() -> None:
    """`RRA-004`:92 -- "Transactions count posted sales only."

    `_measures` reads one transaction key per admitted event and `_distinct`
    counts them with no event-kind filter, so the return event is counted as a
    third transaction.
    """
    assert _returns_package().value("transactions") == str(
        MESSY_RETURNS_EXPECTED["transactions"]
    )


def test_aov_divides_sale_revenue_by_sale_transactions() -> None:
    """Population `sales_complete_revenue_transactions`, per `RRA-004`:36.

    Production computes return-inclusive revenue over a return-contaminated
    denominator -- the wrong number twice, in the same ratio.
    """
    assert _returns_package().value("average_order_value") == str(
        MESSY_RETURNS_EXPECTED["average_order_value"]
    )


def test_asp_divides_sale_revenue_by_positive_sale_units() -> None:
    """`RRA-003`: "ASP and basket calculations use positive posted-sale units
    only, including free or bonus items."

    Production nets the return into both numerator and denominator.
    """
    assert _returns_package().value("average_selling_price") == str(
        MESSY_RETURNS_EXPECTED["average_selling_price"]
    )


def test_returns_are_derived_from_admitted_return_revenue() -> None:
    """`RRA-004`:83 -- `-sum(non-positive return revenue)`.

    `RRA-003` forbids the alternative outright: "No independently mapped
    return-amount measure is admitted." This extract carries no returns column
    and does not need one -- the return event states its own magnitude -- yet
    production refuses the metric for want of a column it may not read.
    """
    assert _returns_package().value("returns") == str(
        MESSY_RETURNS_EXPECTED["returns"]
    )


def test_headline_revenue_and_units_still_include_the_return() -> None:
    """The control, and the boundary of this change.

    `RRA-004`:92 keeps posted returns inside revenue and units: they are net
    figures. Only the sale-only populations exclude the return, so a correction
    that moved these has corrected something it was not asked to.
    """
    package = _returns_package()

    assert package.value("revenue") == str(MESSY_RETURNS_EXPECTED["revenue"])
    assert package.value("units") == str(MESSY_RETURNS_EXPECTED["units"])


# --- guards the messy-returns case does not reach --------------------------
#
# Each exists because a mutant of its guard survived the cases above: that
# dataset happens not to exercise the condition, so the guard could be deleted
# with the suite green.


def test_a_zero_unit_sale_refuses_asp_rather_than_leaving_the_population() -> None:
    """`RRA-003`: "a sale or return event with zero units refuses
    unit-dependent facts", and ASP takes "positive posted-sale units only".

    **This case asserted 50.00 and was wrong, which review caught.** It read
    "refuses unit-dependent facts" as "excludes the row from them", and those are
    different acts. `RRA-004:18` settles it: `sales_complete_revenue_units` is
    `sales_posted` with complete revenue, strictly positive units, "and no
    unmatched eligible row". That last clause is on this population and on none of
    the plain `sales_complete_*` filters beside it, because this one is a divisor.

    Excluding the row published 50.00 beside a revenue of 150.00 and 2 units: a
    reader dividing the two published figures gets 75.00, and neither number
    reconciles against the other. `MESSY_RETURNS_ROWS` carries no zero-unit sale,
    so the positivity filter is unreached there and this is the case that proves
    the rule is applied at all.
    """
    content = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-02-01,sale,100.00,2,INV-1\n"
        b"2026-02-02,sale,50.00,0,INV-2\n"
    )

    result = _package_from(content, oracle_contract(status_column=None))

    assert result.value("average_selling_price") is None
    refused = {refusal.metric: refusal.reason for refusal in result.refusals}
    assert METRIC_AVERAGE_SELLING_PRICE in refused, refused
    # The revenue and units beside it are unaffected: `RRA-004` refuses the
    # affected result, and a whole-dataset total is not unit-paired.
    assert result.value("revenue") == "150.00"
    assert result.value("units") == "2"


def test_returns_state_nothing_where_no_return_event_was_admitted() -> None:
    """`RRA-003`: "absence of event-kind evidence cannot establish zero."

    A package that admitted returns and found none may state zero; one that
    proved nothing about returns must state nothing. `MESSY_RETURNS_ROWS`
    contains a return, so it never reaches this branch -- the guard could be
    deleted and that case would still pass while every sale-only extract
    started publishing a zero it never proved.
    """
    content = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-02-01,sale,100.00,2,INV-1\n"
        b"2026-02-02,sale,50.00,1,INV-2\n"
    )

    result = _package_from(content, oracle_contract(status_column=None))

    assert result.value("returns") is None
    assert result.refusal("returns") is not None


# --- `sales_complete_revenue_units` admits no unmatched eligible row --------


def test_asp_refuses_when_an_eligible_sale_row_is_unmatched() -> None:
    """`RRA-004`: the population is `sales_posted` with complete revenue,
    strictly positive units, **and no unmatched eligible row**.

    A sale carrying revenue but zero units is eligible -- it is a posted sale
    with revenue -- and unmatched, because it contributes no positive units. The
    population therefore does not exist for this dataset and ASP has nothing to
    average.

    **It published 50.00.** 100.00 over 2 units, with the second sale's 50.00
    dropped: a reader dividing the published revenue of 150.00 by the published
    2 units gets 75.00 and cannot reconcile either number against the other.
    `CAVEAT_DERIVED_OVER_MATCHED_ROWS` was attached, but it names no metric and
    no quantity, so it cannot be used to reconcile the gap it discloses.

    Found in review. The unmatched row is what distinguishes this from the
    ordinary narrowing the other `sales_complete_*` populations do: those are
    filters over a *sum*, and this one is a divisor.
    """
    unmatched = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-01-05,sale,100.00,2,INV-1\n"
        b"2026-01-06,sale,50.00,0,INV-2\n"
    )
    package = _package_from(unmatched, oracle_contract(status_column=None))

    stated = {fact.metric for fact in package.facts}
    assert METRIC_AVERAGE_SELLING_PRICE not in stated, "ASP averaged a partial population"

    refused = {refusal.metric: refusal.reason for refusal in package.refusals}
    assert METRIC_AVERAGE_SELLING_PRICE in refused, refused
    assert refused[METRIC_AVERAGE_SELLING_PRICE] == REASON_INPUT_UNAVAILABLE


def test_asp_still_states_a_population_with_no_unmatched_row() -> None:
    """The converse, so the refusal cannot become "refuse whenever units vary".

    Every sale here carries revenue and positive units, so nothing is unmatched
    and the average is over the population `RRA-004` names.
    """
    matched = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-01-05,sale,100.00,2,INV-1\n"
        b"2026-01-06,sale,50.00,1,INV-2\n"
    )
    package = _package_from(matched, oracle_contract(status_column=None))
    asp = next(
        fact for fact in package.facts
        if fact.metric == METRIC_AVERAGE_SELLING_PRICE
    )
    assert asp.value == "50.00"
