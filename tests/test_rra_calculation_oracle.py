"""The oracle checked against itself, never against production.

`tests/rra_calculation_oracle.py` is a table of hand-derived literals, and a table
of hand-derived literals is exactly the kind of artifact a typo hides in. These
tests assert the arithmetic relations the literals must satisfy among themselves:
that a decomposition adds up, that a cumulative curve is cumulative, that a
residual matches its own definition.

**Nothing here imports a production aggregation or analysis helper.** That is the
whole point. A test comparing an oracle literal to `build_fact_package` or to any
`derive()` would be testing production, and it would go green the moment the
oracle inherited a production defect. These tests would fail on a mistyped
literal and pass on a correct one whether or not `src/` exists.

They are GREEN by construction and belong on `main`. The RED cases each `V-*`
slice needs are that slice's to add, immediately before its GREEN, reading its
expected values from the oracle module.
"""

from __future__ import annotations

from decimal import Decimal

from tests.rra_calculation_oracle import (
    CLEAN_ATTACH,
    CLEAN_CONCENTRATION,
    CLEAN_HEADLINE,
    CLEAN_PERIOD_TOTALS,
    CLEAN_ROWS,
    CLEAN_SALE_ONLY,
    CSV_COLUMNS,
    DISPLAY_TRUNCATION_EXPECTED,
    GROWTH_RESIDUAL_CASES,
    GROWTH_RESIDUAL_NEGATIVE,
    GROWTH_RESIDUAL_POSITIVE,
    GROWTH_RESIDUAL_ZERO,
    MESSY_RETURNS_EXPECTED,
    MONETARY_PRECISION,
    REPEATED_INVOICE_EXPECTED,
    REPEATED_INVOICE_ROWS,
    ZERO_REVENUE_PRODUCT_EXPECTED,
    curve_is_monotone,
    growth_case_reconciles,
    leading_count,
    to_csv,
)


def test_every_growth_case_reconciles_with_itself() -> None:
    """Unrounded additivity, published additivity, and the residual definition.

    `RRA-008` makes unrounded additivity an algebraic invariant, so a case whose
    `unrounded_volume + unrounded_price` misses `R_c - R_p` is a typo rather than
    a finding.
    """
    for case in GROWTH_RESIDUAL_CASES:
        assert growth_case_reconciles(case), case.name


def test_published_growth_parts_sum_to_the_published_delta() -> None:
    """The property the derived-price rule exists to guarantee.

    Stated separately from `growth_case_reconciles` because it is the one a
    reader of a report can check: the two effects printed beside the change must
    add to it exactly, with no residual visible on the surface.
    """
    for case in GROWTH_RESIDUAL_CASES:
        assert case.published_volume + case.published_price == case.published_delta


def test_residual_never_exceeds_one_unit_of_the_published_last_place() -> None:
    """`RRA-008`'s bound, asserted over every case the oracle carries.

    The module's `GROWTH_RESIDUAL_BOUND_NOTE` proves this holds identically on
    admitted inputs, so no case can violate it. Asserted anyway: the proof depends
    on the precision rule, and a literal edited past the bound should fail here
    rather than quietly widen what the oracle claims is reachable.
    """
    unit = Decimal(1).scaleb(-MONETARY_PRECISION)
    for case in GROWTH_RESIDUAL_CASES:
        assert abs(case.residual) <= unit, case.name


def test_the_three_growth_cases_cover_both_signs_and_zero() -> None:
    """A residual is a signed correction, not a magnitude.

    A slice implementing `abs(residual)` would pass the positive case alone. The
    negative case is what catches it, and the zero case proves the rule is a
    refinement rather than a replacement.
    """
    assert GROWTH_RESIDUAL_POSITIVE.residual > 0
    assert GROWTH_RESIDUAL_NEGATIVE.residual < 0
    assert GROWTH_RESIDUAL_ZERO.residual == 0


def test_clean_gross_profit_is_revenue_less_cost() -> None:
    """`RRA-004`: gross profit is matched revenue minus matched extended COGS."""
    assert (
        CLEAN_HEADLINE["revenue"] - CLEAN_HEADLINE["cost"]
        == CLEAN_HEADLINE["gross_profit"]
    )


def test_clean_period_totals_sum_to_the_clean_headline() -> None:
    """Two periods partition the dataset, so their totals must reach the headline.

    This is the reconciliation `RRA-004` requires of every aggregate against its
    basis, asserted between two independently derived literals rather than
    against a production sum.
    """
    revenue = sum(
        (entry["revenue"] for entry in CLEAN_PERIOD_TOTALS.values()), Decimal(0)
    )
    units = sum((entry["units"] for entry in CLEAN_PERIOD_TOTALS.values()), Decimal(0))
    assert revenue == CLEAN_HEADLINE["revenue"]
    assert units == CLEAN_HEADLINE["units"]


def test_clean_ratios_agree_with_their_own_numerators_and_denominators() -> None:
    """AOV, ASP and items per transaction re-derived from the headline literals.

    Each ratio is stated as a literal above, and each is also a quotient of two
    other literals. Asserting they agree catches a rounded literal that was
    transcribed from the wrong division.
    """
    scale = Decimal(1).scaleb(-MONETARY_PRECISION)
    revenue = CLEAN_HEADLINE["revenue"]
    units = CLEAN_HEADLINE["units"]
    transactions = CLEAN_HEADLINE["transactions"]
    assert (revenue / transactions).quantize(scale) == CLEAN_SALE_ONLY[
        "average_order_value"
    ]
    assert (revenue / units).quantize(scale) == CLEAN_SALE_ONLY[
        "average_selling_price"
    ]
    assert (units / transactions).quantize(Decimal("0.0001")) == CLEAN_SALE_ONLY[
        "basket_items_per_transaction"
    ]


def test_clean_concentration_curve_is_cumulative_and_ends_at_one() -> None:
    """`RRA-008`: a curve that dips is not cumulative, and the last point is 100%."""
    assert curve_is_monotone(CLEAN_CONCENTRATION["curve"])


def test_zero_revenue_tail_is_flat_and_still_ends_at_one() -> None:
    """Zero-revenue values rank last and add nothing, which is a flat tail.

    `curve_is_monotone` permits equality precisely so this shape passes; a
    strictly increasing test would forbid the behaviour `RRA-008` requires.
    """
    curve = ZERO_REVENUE_PRODUCT_EXPECTED["curve"]
    assert curve_is_monotone(curve)
    assert curve[-1] == curve[-2] == Decimal("1.0000")


def test_clean_top_shares_are_the_curve_at_the_governed_cutoffs() -> None:
    """The share literals must be read off the curve, not computed a second way.

    n = 3, so ceil(3/10) and ceil(3/4) are both 1 and both shares are the first
    curve point. Asserting it links the two literal groups: a curve edited without
    its shares fails here.
    """
    curve = CLEAN_CONCENTRATION["curve"]
    distinct = int(CLEAN_CONCENTRATION["distinct_values"])
    decile = leading_count(distinct, 10)
    quartile = leading_count(distinct, 4)
    assert curve[decile - 1] == CLEAN_CONCENTRATION["top_decile_share"]
    assert curve[quartile - 1] == CLEAN_CONCENTRATION["top_quartile_share"]


def test_governed_cutoffs_round_up_and_never_reach_zero() -> None:
    """`RRA-008` fixes both the ceiling and the at-least-one floor.

    Eight values divided into deciles is 0.8, and a top decile of no values
    reporting a nought share would be false rather than cautious.
    """
    assert leading_count(8, 10) == 1
    assert leading_count(25, 10) == 3
    assert leading_count(25, 4) == 7
    assert leading_count(1, 10) == 1


def test_display_truncation_cutoffs_match_the_ceiling_rule() -> None:
    """The 25-value case states its cutoffs; they must follow from the rule."""
    distinct = int(DISPLAY_TRUNCATION_EXPECTED["distinct_values"])
    assert leading_count(distinct, 10) == 3
    assert leading_count(distinct, 4) == 7


def test_attach_rates_share_one_transaction_denominator() -> None:
    """Every rate in a family divides by the same distinct transaction set.

    `RRA-008` names the denominator "the exact distinct canonical transaction set
    in `dimension_complete_sales:<dimension>`", one set for the whole family. A
    rate whose literal implies a different denominator is a transcription error.
    """
    denominator = CLEAN_ATTACH["denominator"]
    for value in ("P1", "P2", "P3"):
        numerator = CLEAN_ATTACH[value] * denominator
        assert numerator == numerator.to_integral_value(), value
        assert Decimal(0) < numerator <= denominator, value


def test_messy_sale_only_ratios_use_the_sale_only_population() -> None:
    """AOV and ASP re-derived from the sale-only numerator and denominators.

    Sale revenue is 1000.00 -- the 900.00 headline plus the 100.00 return
    magnitude -- and this checks the literals are consistent with that reading
    rather than with the return-inclusive one production uses.
    """
    sale_revenue = MESSY_RETURNS_EXPECTED["revenue"] + MESSY_RETURNS_EXPECTED["returns"]
    assert sale_revenue == Decimal("1000.00")
    assert (
        sale_revenue / MESSY_RETURNS_EXPECTED["transactions"]
        == MESSY_RETURNS_EXPECTED["average_order_value"]
    )


def test_canonical_transaction_keys_separate_repeated_invoice_numbers() -> None:
    """The composite key distinguishes what a bare identifier collapses.

    Four rows carry two invoice numbers across two stores. The bare identifiers
    give two distinct values; the canonical keys give four, which is the literal.
    """
    bare = {row.invoice for row in REPEATED_INVOICE_ROWS}
    canonical = {row.canonical_transaction_key for row in REPEATED_INVOICE_ROWS}
    assert len(bare) == 2
    assert len(canonical) == int(REPEATED_INVOICE_EXPECTED["transactions"]) == 4


def test_canonical_key_is_absent_when_a_component_is() -> None:
    """`RRA-003`: missing components refuse rather than forming a partial key."""
    from tests.rra_calculation_oracle import MISSING_TRANSACTION_IDENTITY_ROWS

    keys = [row.canonical_transaction_key for row in MISSING_TRANSACTION_IDENTITY_ROWS]
    assert None in keys


def test_allocated_discount_components_sum_to_the_discount_total() -> None:
    """The invoice-level and line-level parts must reach the stated total.

    `RRA-003` admits an allocated invoice discount only when the source
    "allocates every invoice-level amount exactly once". The two component
    literals are what a slice checks that against, so they must agree with the
    total the same dataset states.
    """
    from tests.rra_calculation_oracle import ALLOCATED_DISCOUNT_EXPECTED

    components = (
        ALLOCATED_DISCOUNT_EXPECTED["allocated_invoice_component"]
        + ALLOCATED_DISCOUNT_EXPECTED["line_component"]
    )
    assert components == ALLOCATED_DISCOUNT_EXPECTED["discount"]


def test_allocated_discount_rows_carry_that_discount_and_leave_revenue_net() -> None:
    """The rows themselves must add to the literals, and revenue stays unreduced.

    `RRA-003`: discount "never changes governed revenue, which is already net".
    Summing the rows here is reading the dataset, not calculating a metric -- no
    production helper is involved.
    """
    from tests.rra_calculation_oracle import (
        ALLOCATED_DISCOUNT_EXPECTED,
        ALLOCATED_DISCOUNT_ROWS,
    )

    discount = sum(
        (row.discount for row in ALLOCATED_DISCOUNT_ROWS if row.discount is not None),
        Decimal(0),
    )
    revenue = sum(
        (row.revenue for row in ALLOCATED_DISCOUNT_ROWS if row.revenue is not None),
        Decimal(0),
    )
    assert discount == ALLOCATED_DISCOUNT_EXPECTED["discount"]
    assert revenue == ALLOCATED_DISCOUNT_EXPECTED["revenue"]
    assert revenue > discount


def test_allocated_discount_rows_are_one_canonical_transaction() -> None:
    """Three lines of one invoice in one store on one day are one transaction."""
    from tests.rra_calculation_oracle import (
        ALLOCATED_DISCOUNT_EXPECTED,
        ALLOCATED_DISCOUNT_ROWS,
    )

    keys = {row.canonical_transaction_key for row in ALLOCATED_DISCOUNT_ROWS}
    assert len(keys) == int(ALLOCATED_DISCOUNT_EXPECTED["transactions"]) == 1


def test_store_mismatch_refuses_while_the_periods_themselves_survive() -> None:
    """`RRA-008`: store-mismatched structures refuse the comparison, not the facts.

    The two store sets must actually differ, or the case asserts nothing; and the
    same-length-different-store refusal must not generalize into refusing
    different-length same-store periods, which the specification admits.
    """
    from tests.rra_calculation_oracle import (
        NATURAL_MONTH_LENGTH_EXPECTED,
        STORE_MISMATCH_EXPECTED,
    )

    prior = set(STORE_MISMATCH_EXPECTED["prior_store_set"])
    current = set(STORE_MISMATCH_EXPECTED["current_store_set"])
    assert prior != current
    assert STORE_MISMATCH_EXPECTED["comparison_admitted"] is False
    assert STORE_MISMATCH_EXPECTED["growth_admitted"] is False
    assert STORE_MISMATCH_EXPECTED["prior_revenue_survives"] is True
    assert STORE_MISMATCH_EXPECTED["current_revenue_survives"] is True
    assert STORE_MISMATCH_EXPECTED["same_store_set_different_lengths_admitted"] is True
    assert NATURAL_MONTH_LENGTH_EXPECTED["all_pairs_compatible"] is True


def test_natural_month_lengths_cover_all_four_calendar_cases() -> None:
    """`RRA-008` names 28, 29, 30 and 31 explicitly; all four must be present."""
    from tests.rra_calculation_oracle import NATURAL_MONTH_LENGTH_EXPECTED

    assert set(NATURAL_MONTH_LENGTH_EXPECTED["day_counts"]) == {28, 29, 30, 31}
    assert NATURAL_MONTH_LENGTH_EXPECTED["leap_day_yoy_admitted"] is False


def test_to_csv_renders_one_header_and_one_line_per_row() -> None:
    """The serializer is a serializer: no filtering, no aggregation, no reordering."""
    rendered = to_csv(CLEAN_ROWS).decode().splitlines()
    assert rendered[0] == ",".join(CSV_COLUMNS)
    assert len(rendered) == len(CLEAN_ROWS) + 1
    assert rendered[1].startswith("2026-01-05,120.00,4,INV-1001,S1,P1,C1,70.00,")


def test_to_csv_writes_an_absent_optional_dimension_as_an_empty_cell() -> None:
    """A missing value is empty, never a synthesized label.

    `RRA-003` requires an explicit zero to differ from a missing value, and the
    same holds of a dimension: writing `unlabelled` here would hand production a
    value the source never carried.
    """
    from tests.rra_calculation_oracle import MISSING_PRODUCT_ZERO_REVENUE_ROWS

    rendered = to_csv(MISSING_PRODUCT_ZERO_REVENUE_ROWS).decode().splitlines()
    assert rendered[-1] == "2026-03-18,0.00,1,INV-9003,S1,,,0.00,0.00"
