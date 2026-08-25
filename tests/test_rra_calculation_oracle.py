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
    ALLOCATED_DISCOUNT_EXPECTED,
    ALLOCATED_DISCOUNT_ROWS,
    CLEAN_ATTACH,
    CLEAN_COMPARISON,
    CLEAN_CONCENTRATION,
    CLEAN_HEADLINE,
    CLEAN_PERIOD_TOTALS,
    CLEAN_ROWS,
    CLEAN_SALE_ONLY,
    CSV_COLUMNS,
    DISPLAY_TRUNCATION_EXPECTED,
    DISPLAY_TRUNCATION_ROWS,
    GROWTH_RESIDUAL_CASES,
    GROWTH_RESIDUAL_NEGATIVE,
    GROWTH_RESIDUAL_POSITIVE,
    GROWTH_RESIDUAL_ZERO,
    HIGH_PRECISION_EXPECTED,
    HIGH_PRECISION_ROWS,
    MESSY_RETURNS_EXPECTED,
    MESSY_RETURNS_ROWS,
    MISSING_PRODUCT_ZERO_REVENUE_EXPECTED,
    MISSING_PRODUCT_ZERO_REVENUE_ROWS,
    MONETARY_PRECISION,
    PARTIAL_NULL_EXPECTED,
    PARTIAL_NULL_ROWS,
    RATIO_PRECISION,
    REPEATED_INVOICE_EXPECTED,
    REPEATED_INVOICE_ROWS,
    YEAR_OVER_YEAR_COMPARISON,
    YEAR_OVER_YEAR_PERIOD_TOTALS,
    YEAR_OVER_YEAR_ROWS,
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


# ---------------------------------------------------------------------------
# Row-derived guards.
#
# Every assertion below recomputes a literal from the dataset rows that literal
# describes, so corrupting the literal fails. That is the difference between a
# test that consumes a number and a test that discriminates it: an earlier
# revision of this file asserted `rate * 8` was integral and in range, which a
# transposed attach rate satisfies just as well as the correct one.
#
# The recomputation is arithmetic over `OracleRow` fields -- summing a column,
# counting a set -- and never a call into `src/`. Reading the oracle's own rows
# is not consulting production.
# ---------------------------------------------------------------------------

SCALE = Decimal(1).scaleb(-MONETARY_PRECISION)
RATIO_SCALE = Decimal(1).scaleb(-RATIO_PRECISION)


def _revenue_of(rows) -> Decimal:
    return sum((row.revenue for row in rows if row.revenue is not None), Decimal(0))


def _units_of(rows) -> Decimal:
    return sum((Decimal(row.units) for row in rows if row.units is not None), Decimal(0))


def _revenue_by_product(rows) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for row in rows:
        if row.product is None or row.revenue is None:
            continue
        totals[row.product] = totals.get(row.product, Decimal(0)) + row.revenue
    return totals


def _cumulative_curve(totals: dict[str, Decimal]) -> tuple[Decimal, ...]:
    """The ranked cumulative share curve over one dimension's revenue totals."""
    ranked = sorted(totals, key=lambda key: (-totals[key], key))
    grand = sum(totals.values(), Decimal(0))
    running = Decimal(0)
    shares: list[Decimal] = []
    for key in ranked:
        running += totals[key]
        shares.append((running / grand).quantize(RATIO_SCALE))
    return tuple(shares)


def test_high_precision_aov_is_the_half_even_quotient_of_its_own_rows() -> None:
    """The half-even tie, recomputed rather than trusted.

    The module's docstring calls this "the property most easily lost", and until
    this assertion existed the literal could be edited from 15.388888 to
    15.388889 with the whole suite still green -- a headline property with no
    discriminating guard, which is the failure mode this project has hit before.

    30.777777 / 2 = 15.3888885 exactly. The digit past the retained place is 5
    with nothing after it, and the retained digit 8 is already even, so half-even
    keeps it. Round-half-up and binary floating point both give ...889.
    """
    revenue = _revenue_of(HIGH_PRECISION_ROWS)
    keys = {row.canonical_transaction_key for row in HIGH_PRECISION_ROWS}
    scale = Decimal(1).scaleb(-int(HIGH_PRECISION_EXPECTED["monetary_precision"]))
    assert revenue == HIGH_PRECISION_EXPECTED["revenue"]
    assert len(keys) == 2
    assert revenue / Decimal(len(keys)) == Decimal("15.3888885")
    assert (revenue / Decimal(len(keys))).quantize(scale) == HIGH_PRECISION_EXPECTED[
        "average_order_value"
    ]


def test_high_precision_asp_and_margin_come_from_the_same_rows() -> None:
    """ASP and gross margin recomputed from the row columns they summarize."""
    revenue = _revenue_of(HIGH_PRECISION_ROWS)
    units = _units_of(HIGH_PRECISION_ROWS)
    cost = sum(
        (row.cost for row in HIGH_PRECISION_ROWS if row.cost is not None), Decimal(0)
    )
    scale = Decimal(1).scaleb(-int(HIGH_PRECISION_EXPECTED["monetary_precision"]))
    assert cost == HIGH_PRECISION_EXPECTED["cost"]
    assert revenue - cost == HIGH_PRECISION_EXPECTED["gross_profit"]
    assert (revenue / units).quantize(scale) == HIGH_PRECISION_EXPECTED[
        "average_selling_price"
    ]
    assert ((revenue - cost) / revenue).quantize(RATIO_SCALE) == HIGH_PRECISION_EXPECTED[
        "gross_margin"
    ]


def test_high_precision_scale_is_the_largest_input_scale() -> None:
    """`RRA-004`: the published scale is the largest admitted monetary input scale."""
    scales = [
        -int(row.revenue.as_tuple().exponent)
        for row in HIGH_PRECISION_ROWS
        if row.revenue is not None
    ]
    assert max(scales) == HIGH_PRECISION_EXPECTED["monetary_precision"] == 6


def test_clean_concentration_curve_is_recomputed_from_the_rows() -> None:
    """Every curve point, including the interior ones, derived from row revenue.

    `curve_is_monotone` checks ordering and the endpoint only, and both cutoff
    assertions read `curve[0]`, so the interior point 0.8696 was unguarded --
    0.8697 and even 0.5000 both passed. This pins all three.
    """
    totals = _revenue_by_product(CLEAN_ROWS)
    assert sorted(totals, key=lambda key: (-totals[key], key)) == ["P3", "P1", "P2"]
    assert sum(totals.values(), Decimal(0)) == CLEAN_HEADLINE["revenue"]
    assert _cumulative_curve(totals) == CLEAN_CONCENTRATION["curve"]
    assert Decimal(len(totals)) == CLEAN_CONCENTRATION["distinct_values"]
    assert Decimal(len(totals)) == CLEAN_CONCENTRATION["ranked_values"]


def test_clean_top_shares_are_recomputed_at_the_governed_cutoffs() -> None:
    """The two shares read off the recomputed curve, not off the stated one."""
    curve = _cumulative_curve(_revenue_by_product(CLEAN_ROWS))
    distinct = len(_revenue_by_product(CLEAN_ROWS))
    assert curve[leading_count(distinct, 10) - 1] == CLEAN_CONCENTRATION[
        "top_decile_share"
    ]
    assert curve[leading_count(distinct, 4) - 1] == CLEAN_CONCENTRATION[
        "top_quartile_share"
    ]


def test_clean_attach_rates_are_recomputed_from_transaction_membership() -> None:
    """Each rate is its own value's distinct containing keys over the whole set.

    The previous assertion only checked `rate * 8` was integral and within range,
    which a transposed P1/P2 pair satisfies. Recomputing memberships catches both
    a transposition and a wrong denominator, and proves the `RRA-003` rule that
    P1's two lines inside INV-1001 count once.
    """
    keys = {row.canonical_transaction_key for row in CLEAN_ROWS}
    assert Decimal(len(keys)) == CLEAN_ATTACH["denominator"]
    for value in ("P1", "P2", "P3"):
        containing = {
            row.canonical_transaction_key for row in CLEAN_ROWS if row.product == value
        }
        expected = (Decimal(len(containing)) / Decimal(len(keys))).quantize(RATIO_SCALE)
        assert expected == CLEAN_ATTACH[value], value


def test_clean_period_totals_are_recomputed_per_period() -> None:
    """Revenue, units, transaction count and distinct dates, per month bucket."""
    for label, stated in CLEAN_PERIOD_TOTALS.items():
        rows = [
            row
            for row in CLEAN_ROWS
            if f"{row.day.year:04d}-{row.day.month:02d}" == label
        ]
        assert _revenue_of(rows) == stated["revenue"], label
        assert _units_of(rows) == stated["units"], label
        keys = {row.canonical_transaction_key for row in rows}
        assert Decimal(len(keys)) == stated["transactions"], label
        assert Decimal(len({row.day for row in rows})) == stated["distinct_dates"], label


def test_clean_comparison_deltas_follow_from_the_period_totals() -> None:
    """`RRA-008`: absolute delta is current - prior; percentage divides by prior."""
    current = CLEAN_PERIOD_TOTALS["2026-05"]["revenue"]
    prior = CLEAN_PERIOD_TOTALS["2026-01"]["revenue"]
    assert current - prior == CLEAN_COMPARISON["revenue_delta_absolute"]
    assert ((current - prior) / prior).quantize(RATIO_SCALE) == CLEAN_COMPARISON[
        "revenue_delta_percent"
    ]
    units_change = (
        CLEAN_PERIOD_TOTALS["2026-05"]["units"] - CLEAN_PERIOD_TOTALS["2026-01"]["units"]
    )
    assert units_change == CLEAN_COMPARISON["units_delta_absolute"]


def test_clean_headline_and_ratios_are_recomputed_from_the_rows() -> None:
    """The whole clean headline block, derived from the twelve rows."""
    revenue = _revenue_of(CLEAN_ROWS)
    units = _units_of(CLEAN_ROWS)
    cost = sum((row.cost for row in CLEAN_ROWS if row.cost is not None), Decimal(0))
    keys = Decimal(len({row.canonical_transaction_key for row in CLEAN_ROWS}))
    assert revenue == CLEAN_HEADLINE["revenue"]
    assert units == CLEAN_HEADLINE["units"]
    assert cost == CLEAN_HEADLINE["cost"]
    assert keys == CLEAN_HEADLINE["transactions"]
    assert revenue - cost == CLEAN_HEADLINE["gross_profit"]
    assert ((revenue - cost) / revenue).quantize(RATIO_SCALE) == CLEAN_HEADLINE[
        "gross_margin"
    ]
    assert (revenue / keys).quantize(SCALE) == CLEAN_SALE_ONLY["average_order_value"]
    assert (revenue / units).quantize(SCALE) == CLEAN_SALE_ONLY["average_selling_price"]
    assert (units / keys).quantize(RATIO_SCALE) == CLEAN_SALE_ONLY[
        "basket_items_per_transaction"
    ]


def test_display_truncation_literals_are_recomputed_from_its_rows() -> None:
    """Distinct count and both shares derived from the 25 generated rows.

    `distinct_values` was consumed by the cutoff test but not discriminated by
    it: ceil(26/10) = 3 and ceil(26/4) = 7 exactly as for 25, so a corrupted 26
    passed. Counting the rows' own products fixes that.
    """
    totals = _revenue_by_product(DISPLAY_TRUNCATION_ROWS)
    assert Decimal(len(totals)) == DISPLAY_TRUNCATION_EXPECTED["distinct_values"]
    assert Decimal(len(totals)) == DISPLAY_TRUNCATION_EXPECTED["ranked_values"]
    ranked = sorted(totals, key=lambda key: (-totals[key], key))
    grand = sum(totals.values(), Decimal(0))
    assert grand == Decimal("32500.00")
    for fraction, metric in ((10, "top_decile_share"), (4, "top_quartile_share")):
        cutoff = leading_count(len(totals), fraction)
        cumulative = sum((totals[key] for key in ranked[:cutoff]), Decimal(0))
        assert (cumulative / grand).quantize(RATIO_SCALE) == DISPLAY_TRUNCATION_EXPECTED[
            metric
        ], metric


def test_display_truncation_presentation_stays_under_the_sampling_bound() -> None:
    """`RRA-008` caps presentation sampling at 100 points; 25 is under it."""
    assert DISPLAY_TRUNCATION_EXPECTED["presentation_points"] == Decimal(
        len(DISPLAY_TRUNCATION_ROWS)
    )
    assert DISPLAY_TRUNCATION_EXPECTED["sampling_applied"] is False


def test_messy_returns_literals_are_recomputed_from_its_rows() -> None:
    """Return-inclusive headlines and the sale-only ratios, from the three rows."""
    sales = [row for row in MESSY_RETURNS_ROWS if row.event_kind == "sale"]
    returned = [row for row in MESSY_RETURNS_ROWS if row.event_kind == "return"]
    assert _revenue_of(MESSY_RETURNS_ROWS) == MESSY_RETURNS_EXPECTED["revenue"]
    assert _units_of(MESSY_RETURNS_ROWS) == MESSY_RETURNS_EXPECTED["units"]
    assert -_revenue_of(returned) == MESSY_RETURNS_EXPECTED["returns"]
    sale_keys = Decimal(len({row.canonical_transaction_key for row in sales}))
    assert sale_keys == MESSY_RETURNS_EXPECTED["transactions"]
    sale_revenue = _revenue_of(sales)
    sale_units = _units_of(sales)
    assert (sale_revenue / sale_keys).quantize(SCALE) == MESSY_RETURNS_EXPECTED[
        "average_order_value"
    ]
    assert (sale_revenue / sale_units).quantize(SCALE) == MESSY_RETURNS_EXPECTED[
        "average_selling_price"
    ]
    assert (sale_units / sale_keys).quantize(RATIO_SCALE) == MESSY_RETURNS_EXPECTED[
        "basket_items_per_transaction"
    ]


def test_surviving_literals_on_refusing_datasets_come_from_their_rows() -> None:
    """Where a case refuses one metric, the survivors are still recomputed.

    `PARTIAL_NULL` and `MISSING_PRODUCT_ZERO_REVENUE` both state a refusal beside
    a surviving revenue, and the surviving number was unguarded.
    """
    assert _revenue_of(PARTIAL_NULL_ROWS) == PARTIAL_NULL_EXPECTED["revenue"]
    assert _units_of(PARTIAL_NULL_ROWS) == PARTIAL_NULL_EXPECTED["units"]
    assert PARTIAL_NULL_EXPECTED["cost"] is None
    assert (
        _revenue_of(MISSING_PRODUCT_ZERO_REVENUE_ROWS)
        == MISSING_PRODUCT_ZERO_REVENUE_EXPECTED["revenue"]
    )
    assert (
        _units_of(MISSING_PRODUCT_ZERO_REVENUE_ROWS)
        == MISSING_PRODUCT_ZERO_REVENUE_EXPECTED["units"]
    )
    keys = {row.canonical_transaction_key for row in MISSING_PRODUCT_ZERO_REVENUE_ROWS}
    assert Decimal(len(keys)) == MISSING_PRODUCT_ZERO_REVENUE_EXPECTED["transactions"]


def test_zero_revenue_curve_is_recomputed_including_its_flat_tail() -> None:
    """The tail points are curve values, not padding, so they are derived too."""
    from tests.rra_calculation_oracle import ZERO_REVENUE_PRODUCT_ROWS

    totals = _revenue_by_product(ZERO_REVENUE_PRODUCT_ROWS)
    assert _cumulative_curve(totals) == ZERO_REVENUE_PRODUCT_EXPECTED["curve"]
    assert Decimal(len(totals)) == ZERO_REVENUE_PRODUCT_EXPECTED["distinct_values"]
    zeroes = sum(1 for value in totals.values() if value == 0)
    assert Decimal(zeroes) == ZERO_REVENUE_PRODUCT_EXPECTED["zero_revenue_values"]


def test_allocated_discount_total_is_recomputed_from_its_rows() -> None:
    """The discount total and the untouched revenue, from the three lines."""
    discount = sum(
        (row.discount for row in ALLOCATED_DISCOUNT_ROWS if row.discount is not None),
        Decimal(0),
    )
    assert discount == ALLOCATED_DISCOUNT_EXPECTED["discount"]
    assert _revenue_of(ALLOCATED_DISCOUNT_ROWS) == ALLOCATED_DISCOUNT_EXPECTED["revenue"]


def test_year_over_year_period_totals_are_recomputed_per_period() -> None:
    """Both compared months derived from the rows that fall in them."""
    for label, stated in YEAR_OVER_YEAR_PERIOD_TOTALS.items():
        rows = [
            row
            for row in YEAR_OVER_YEAR_ROWS
            if f"{row.day.year:04d}-{row.day.month:02d}" == label
        ]
        assert _revenue_of(rows) == stated["revenue"], label
        assert _units_of(rows) == stated["units"], label
        keys = {row.canonical_transaction_key for row in rows}
        assert Decimal(len(keys)) == stated["transactions"], label


def test_year_over_year_deltas_follow_from_the_period_totals() -> None:
    """`RRA-008`: YoY compares the exact same calendar period one year earlier.

    170.00 / 560.00 = 0.30357142857..., which rounds to 0.3036 at four places.
    The ratio is deliberately non-terminating: a round 0.5000 would pass under
    every rounding mode and discriminate nothing.
    """
    current = YEAR_OVER_YEAR_PERIOD_TOTALS[YEAR_OVER_YEAR_COMPARISON["current_label"]]
    prior = YEAR_OVER_YEAR_PERIOD_TOTALS[YEAR_OVER_YEAR_COMPARISON["prior_label"]]
    change = current["revenue"] - prior["revenue"]
    assert change == YEAR_OVER_YEAR_COMPARISON["revenue_delta_absolute"]
    assert (change / prior["revenue"]).quantize(RATIO_SCALE) == (
        YEAR_OVER_YEAR_COMPARISON["revenue_delta_percent"]
    )
    assert current["units"] - prior["units"] == (
        YEAR_OVER_YEAR_COMPARISON["units_delta_absolute"]
    )


def test_year_over_year_labels_are_exactly_one_year_apart() -> None:
    """The counterpart is the same calendar month, not the nearest observed one.

    The dataset carries 2025-04 and 2026-06 precisely so a positional or
    nearest-neighbour selection would pick a different pair and fail here.
    """
    current = YEAR_OVER_YEAR_COMPARISON["current_label"]
    prior = YEAR_OVER_YEAR_COMPARISON["prior_label"]
    current_year, current_month = (int(part) for part in current.split("-"))
    prior_year, prior_month = (int(part) for part in prior.split("-"))
    assert current_month == prior_month
    assert current_year - prior_year == 1
    observed = {f"{row.day.year:04d}-{row.day.month:02d}" for row in YEAR_OVER_YEAR_ROWS}
    assert {current, prior} <= observed
    # Both neighbours exist and are NOT the counterpart.
    assert {"2025-04", "2026-06"} <= observed


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
