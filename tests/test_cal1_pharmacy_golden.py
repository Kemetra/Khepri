"""A pharmacy dispensing extract, end to end against hand-derived expectations.

`CAL1-12` asks for pharmacy-focused golden fixtures beside the mutation evidence.
The dataset lives in `tests/rra_calculation_oracle.py` with every literal shown as
arithmetic; this module is what drives it through the production path and asserts
the published facts equal those literals.

**Why a pharmacy case earns its place beside the existing golden datasets.** The
oracle's other cases each isolate one defect on data shaped to expose it. This one
is shaped like a customer's month instead, and its value is that the sale-only and
financial populations differ *while the transaction count does not*. The same-day
dispensing reversal shares its prescription identifier with the sale it reverses,
so an implementation that ignored event kind entirely would still publish five
transactions -- the right number -- and an AOV of 191.00 against a governed 209.00.
A dataset where every population differed would not distinguish the two failures.

**Nothing here recomputes an expectation.** The literals come from the oracle, which
imports no production aggregation helper. This module imports production only to
*run* it, which is the separation that makes the comparison meaningful.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.facts import (
    METRIC_AVERAGE_ORDER_VALUE,
    METRIC_AVERAGE_SELLING_PRICE,
    METRIC_COST,
    METRIC_DISCOUNT,
    METRIC_GROSS_MARGIN,
    METRIC_GROSS_PROFIT,
    METRIC_REVENUE,
    METRIC_TRANSACTIONS,
    METRIC_UNITS,
    AdmittedInput,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import oracle_contract
from tests.rra_calculation_oracle import (
    PHARMACY_HEADLINE,
    PHARMACY_ROWS,
    PHARMACY_SALE_ONLY,
    to_csv,
)


def _pharmacy_package():
    """The dispensing extract as a governed package.

    The same construction `test_rra004_formula_populations` uses, so this module
    proves nothing about how a package is built -- only about the figures one
    carries. `oracle_contract()` declares the event-kind and status columns the
    bridge emits, which is what admits the return as a return rather than as a
    negative sale.
    """
    content = to_csv(PHARMACY_ROWS)
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=oracle_contract())
    return build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=oracle_contract(),
        )
    )


def _value(package, metric: str) -> Decimal | None:
    fact = package.fact(metric)
    return None if fact is None else Decimal(fact.value)


def test_the_financial_headline_matches_the_hand_derived_totals() -> None:
    """Revenue, units and cost over `financial_posted`, the return included.

    `RRA-004` sums signed revenue over the financial population, so the posted
    return subtracts from all three. These are the figures a pharmacist would
    reconcile against a till report.
    """
    package = _pharmacy_package()

    assert _value(package, METRIC_REVENUE) == PHARMACY_HEADLINE["revenue"]
    assert _value(package, METRIC_UNITS) == PHARMACY_HEADLINE["units"]
    assert _value(package, METRIC_COST) == PHARMACY_HEADLINE["cost"]


def test_gross_profit_and_margin_reconcile_to_the_headline() -> None:
    """Margin is a ratio of the two figures beside it, not an independent number.

    Asserted together because the reconciliation is the property: a margin that
    matched its literal while profit did not would mean the two were computed over
    different populations, which is the defect `RRA-004` names.
    """
    package = _pharmacy_package()
    profit = _value(package, METRIC_GROSS_PROFIT)
    revenue = _value(package, METRIC_REVENUE)
    cost = _value(package, METRIC_COST)

    assert profit == PHARMACY_HEADLINE["gross_profit"]
    assert profit == revenue - cost
    assert _value(package, METRIC_GROSS_MARGIN) == PHARMACY_HEADLINE["gross_margin"]


def test_the_two_insurance_copays_are_the_whole_discount() -> None:
    """An additive co-pay sums; the explicit zeros beside it are proven absence.

    `RRA-003` reads an explicit zero as an admitted value rather than a missing
    one, so the five zero rows contribute nothing and change nothing.
    """
    package = _pharmacy_package()

    assert _value(package, METRIC_DISCOUNT) == PHARMACY_HEADLINE["discount"]


def test_the_reversal_opens_no_transaction_of_its_own() -> None:
    """Five prescriptions, and the return shares the fifth.

    The canonical key is the composite -- identifier, branch, business date,
    terminal -- so the return carries the key of the sale it reverses. This is the
    figure a return-blind implementation also gets right, which is exactly why the
    two ratios below are the ones that discriminate.
    """
    package = _pharmacy_package()

    assert _value(package, METRIC_TRANSACTIONS) == PHARMACY_HEADLINE["transactions"]


def test_the_order_value_averages_sales_only_over_the_same_prescriptions() -> None:
    """AOV over `sales_complete_revenue_transactions`, which excludes the return.

    209.00, not the 191.00 that dividing return-inclusive revenue by the same five
    transactions produces. Both are exact to the cent and neither looks wrong
    beside the other figures, so this assertion is about which rows were counted
    and nothing else.
    """
    package = _pharmacy_package()

    assert (
        _value(package, METRIC_AVERAGE_ORDER_VALUE)
        == PHARMACY_SALE_ONLY["average_order_value"]
    )


def test_the_selling_price_averages_sale_revenue_over_sale_units() -> None:
    """ASP over `sales_complete_revenue_units`: 1045.00 / 13, half-even, 80.38.

    Both sides of the ratio move when the return is admitted -- 955.00 over 12
    gives 79.58 -- so an implementation that filtered one side and not the other
    lands on neither figure. The literal is derived in the oracle to four places
    before rounding, so the half-even step is checked rather than assumed.
    """
    package = _pharmacy_package()

    assert (
        _value(package, METRIC_AVERAGE_SELLING_PRICE)
        == PHARMACY_SALE_ONLY["average_selling_price"]
    )


def test_the_package_reruns_byte_equivalent() -> None:
    """`RRA-004` requires a rerun to be byte-equivalent, and this is a real dataset.

    Determinism is asserted on the serialized document rather than on the object,
    because that is what a customer receives and what a later verification reads
    back. A dictionary iteration order or an unquantized division would show here
    and nowhere else in this module.
    """
    first = _pharmacy_package()
    second = _pharmacy_package()

    assert first.as_document() == second.as_document()
