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
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import oracle_contract
from tests.rra_calculation_oracle import (
    MESSY_RETURNS_EXPECTED,
    MESSY_RETURNS_ROWS,
    to_csv,
)


def _returns_package():
    """Two posted sales and one posted return, admitted as what they are."""
    content = to_csv(MESSY_RETURNS_ROWS)
    contract = oracle_contract()
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


def test_a_zero_unit_sale_is_not_in_the_asp_population() -> None:
    """`RRA-003`: "a sale or return event with zero units refuses
    unit-dependent facts", and ASP takes "positive posted-sale units only".

    `MESSY_RETURNS_ROWS` carries no zero-unit sale, so the positivity filter is
    unreached there and could be deleted with that case still green. Here a
    zero-unit row would drag the denominator up and the price down if counted.

    ASP over the one eligible row is 100.00 / 2 = 50.00. Counting the zero-unit
    sale would give 150.00 / 2 = 75.00.
    """
    content = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-02-01,sale,100.00,2,INV-1\n"
        b"2026-02-02,sale,50.00,0,INV-2\n"
    )

    result = _package_from(content, oracle_contract(status_column=None))

    assert result.value("average_selling_price") == "50.00"


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
