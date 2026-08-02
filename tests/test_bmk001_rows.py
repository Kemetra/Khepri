"""KHEPRI-BMK-001's row content, as KHEPRI-DEC-006 fixes it.

Determinism is the property under test throughout. A workload that cannot be
regenerated identically cannot have a stable `workload_digest`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from khepri.rra.benchmark_population import (
    CORE_COLUMNS,
    EXTENDED_COLUMNS,
    PROFILE_CORE,
    PROFILE_EXTENDED,
)
from khepri.rra.benchmark_rows import (
    CATEGORY_COUNT,
    CHANNEL_COUNT,
    CURRENCY,
    FIRST_DAY,
    LAST_DAY,
    MAX_UNITS,
    PRODUCT_COUNT,
    STORE_COUNT,
    RowsRefused,
    build_rows,
    csv_document,
)

SEED = 0x0123456789ABCDEF
ROWS_PER_TRANSACTION = 4


def _rows(profile: str = PROFILE_CORE, count: int = 200) -> list[tuple[str, ...]]:
    return build_rows(SEED, count, profile, ROWS_PER_TRANSACTION)


def test_date_span_is_the_twenty_four_governed_months() -> None:
    assert date(2024, 7, 1) == FIRST_DAY
    assert date(2026, 6, 30) == LAST_DAY
    assert (LAST_DAY - FIRST_DAY).days + 1 == 730


def test_cardinalities_match_the_decision() -> None:
    assert (PRODUCT_COUNT, CATEGORY_COUNT, STORE_COUNT, CHANNEL_COUNT) == (500, 12, 25, 3)
    assert CURRENCY == "AED"
    assert MAX_UNITS == 20


def test_row_count_and_width_match_the_profile() -> None:
    core = _rows(PROFILE_CORE, 10)
    extended = _rows(PROFILE_EXTENDED, 10)
    assert len(core) == 10
    assert all(len(row) == len(CORE_COLUMNS) for row in core)
    assert all(len(row) == len(EXTENDED_COLUMNS) for row in extended)


def test_generation_is_deterministic_for_one_seed() -> None:
    assert _rows() == _rows()


def test_a_different_seed_changes_the_rows() -> None:
    assert build_rows(SEED, 50, PROFILE_CORE, ROWS_PER_TRANSACTION) != build_rows(
        SEED + 1, 50, PROFILE_CORE, ROWS_PER_TRANSACTION
    )


def test_dates_stay_inside_the_governed_span_and_are_iso() -> None:
    for row in _rows():
        parsed = date.fromisoformat(row[1])
        assert FIRST_DAY <= parsed <= LAST_DAY


def test_units_are_integers_within_the_governed_range() -> None:
    for row in _rows():
        units = int(row[6])
        assert 1 <= units <= MAX_UNITS


def test_money_is_exact_decimal_text_with_two_fraction_digits() -> None:
    """No binary floating-point value is ever an authoritative financial fact."""
    for row in _rows(PROFILE_EXTENDED):
        for index in (7, 8, 9, 10):
            text = row[index]
            assert "." in text and len(text.split(".")[1]) == 2
            assert Decimal(text) >= Decimal("0.00")


def test_dimension_cardinalities_are_respected() -> None:
    rows = _rows(PROFILE_CORE, 4000)
    assert len({row[2] for row in rows}) <= PRODUCT_COUNT
    assert len({row[3] for row in rows}) <= CATEGORY_COUNT
    assert len({row[4] for row in rows}) <= STORE_COUNT
    assert len({row[5] for row in rows}) <= CHANNEL_COUNT


def test_rows_group_into_transactions_of_the_requested_size() -> None:
    """Basket structure is only measurable when a transaction spans several rows."""
    rows = _rows(PROFILE_CORE, 40)
    identifiers = [row[0] for row in rows]
    assert len(set(identifiers)) == 40 // ROWS_PER_TRANSACTION
    assert identifiers[0] == identifiers[ROWS_PER_TRANSACTION - 1]
    assert identifiers[0] != identifiers[ROWS_PER_TRANSACTION]


def test_discount_and_refund_appear_at_the_governed_rates() -> None:
    rows = _rows(PROFILE_EXTENDED, 4000)
    discounted = sum(1 for row in rows if Decimal(row[9]) > 0)
    refunded = sum(1 for row in rows if Decimal(row[10]) > 0)
    assert abs(discounted / len(rows) - 0.30) < 0.03
    assert abs(refunded / len(rows) - 0.05) < 0.02


def test_conditional_amounts_vary_rather_than_being_a_constant_share() -> None:
    """A draw slot past the end of a shared digest yields a constant that looks like data.

    Before per-slot digests, every discount and refund was exactly 1% of revenue: the gate
    fired at the right rate, so a rate-only test passed while the amounts were degenerate.
    """
    rows = _rows(PROFILE_EXTENDED, 2000)
    discount_shares = {
        (Decimal(row[9]) * 100 / Decimal(row[7])).quantize(Decimal("1"))
        for row in rows
        if Decimal(row[9]) > 0
    }
    refund_shares = {
        (Decimal(row[10]) * 100 / Decimal(row[7])).quantize(Decimal("1"))
        for row in rows
        if Decimal(row[10]) > 0
    }
    assert len(discount_shares) > 5
    assert len(refund_shares) > 5


def test_personal_data_column_uses_the_reserved_invalid_domain() -> None:
    for row in _rows(PROFILE_EXTENDED):
        assert row[11].endswith("@example.invalid")


def test_csv_document_carries_the_governed_byte_discipline() -> None:
    document = csv_document(PROFILE_CORE, _rows(PROFILE_CORE, 5))
    assert isinstance(document, bytes)
    assert not document.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" not in document
    assert document.endswith(b"\n")
    header = document.split(b"\n")[0]
    assert header == ",".join(column for column, _ in CORE_COLUMNS).encode()
    assert len(document.rstrip(b"\n").split(b"\n")) == 6


def test_csv_document_is_deterministic() -> None:
    assert csv_document(PROFILE_CORE, _rows()) == csv_document(PROFILE_CORE, _rows())


def test_no_generated_field_needs_csv_quoting() -> None:
    """Explicit quoting rules are simplest to hold when no field can require them."""
    for row in _rows(PROFILE_EXTENDED, 500):
        for field in row:
            assert "," not in field
            assert '"' not in field
            assert "\n" not in field


@pytest.mark.parametrize("count", [0, -1])
def test_a_non_positive_row_count_is_refused(count: int) -> None:
    with pytest.raises(RowsRefused):
        build_rows(SEED, count, PROFILE_CORE, ROWS_PER_TRANSACTION)


@pytest.mark.parametrize("size", [0, -3])
def test_a_non_positive_transaction_size_is_refused(size: int) -> None:
    with pytest.raises(RowsRefused):
        build_rows(SEED, 10, PROFILE_CORE, size)


def test_an_ungoverned_profile_is_refused() -> None:
    with pytest.raises(RowsRefused):
        build_rows(SEED, 10, "everything", ROWS_PER_TRANSACTION)
