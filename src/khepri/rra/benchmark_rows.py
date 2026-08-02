"""The rows a `KHEPRI-BMK-001` dataset contains, as `KHEPRI-DEC-006` fixes them.

**Every field is derived from a digest, not from a random number generator.** The decision
requires generation free of wall-clock, locale, environment, and iteration-order
dependence. Seeding `random` would satisfy that only for as long as the interpreter's
Mersenne Twister stream never changes; deriving each field from
`SHA-256("<seed>:<row_index>")` is reproducible by anyone with the seed and this file,
in any language, forever. A workload that cannot be regenerated identically cannot have
a stable `workload_digest`.

**Money never touches a binary float.** `KHEPRI-DEC-005` makes exact decimals the only
authoritative financial facts, so amounts are assembled from integer minor units and
rendered as text with exactly two fraction digits. Nothing here divides.

**`rows_per_transaction` is a required argument with no default, deliberately.** No
approved artifact settles it, and this module will not invent it: the descriptor must
record the value it used. It matters more than it looks — at one row per transaction,
basket size is exactly 1.00 for every dataset, which is a plausible-looking wrong number
rather than an error, and RRA-008's basket analysis would be measured against a
degenerate population.

**No customer content can reach this module.** Its inputs are a seed and three counts.
Email addresses use the `example.invalid` reserved domain of RFC 2606: never routable,
never customer-derived, never personal data.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from khepri.rra.benchmark_population import (
    PROFILE_CORE,
    PROFILE_EXTENDED,
    columns_for,
)

CURRENCY = "AED"

# The 24 consecutive calendar months the decision fixes, so that year-over-year trends
# and full date-coverage profiling are exercised in every band.
FIRST_DAY = date(2024, 7, 1)
LAST_DAY = date(2026, 6, 30)
DAY_SPAN = (LAST_DAY - FIRST_DAY).days + 1

# Enough to exercise every governed dimension comparison without letting dimension
# cardinality dominate grouping cost.
PRODUCT_COUNT = 500
CATEGORY_COUNT = 12
STORE_COUNT = 25
CHANNEL_COUNT = 3

MAX_UNITS = 20

# Non-zero on this share of rows, by seeded draw, so the conditional-metric and caveat
# paths in RRA-004 are measured rather than skipped.
DISCOUNT_RATE_PERCENT = 30
REFUND_RATE_PERCENT = 5

_UNIT_PRICE_MINOR_FLOOR = 250
_UNIT_PRICE_MINOR_SPAN = 49_750
_COST_SHARE_FLOOR_PERCENT = 45
_COST_SHARE_SPAN_PERCENT = 35
_DISCOUNT_SHARE_SPAN_PERCENT = 25
_REFUND_SHARE_SPAN_PERCENT = 100


class RowsRefused(ValueError):
    """Rows cannot be generated as asked."""


def build_rows(
    seed: int,
    row_count: int,
    column_profile: str,
    rows_per_transaction: int,
) -> list[tuple[str, ...]]:
    """Every row of one dataset, in a fixed order, derived from one seed."""
    _require_positive(row_count, "row_count")
    _require_positive(rows_per_transaction, "rows_per_transaction")
    _require_profile(column_profile)
    return [
        _row(seed, index, column_profile, rows_per_transaction)
        for index in range(row_count)
    ]


def csv_document(column_profile: str, rows: list[tuple[str, ...]]) -> bytes:
    """The dataset as CSV bytes, under the byte discipline the digest depends on.

    UTF-8 without BOM, `\\n` line endings, exactly one final newline. No field this
    module generates can contain a comma, quote, or newline, so no field is ever quoted
    and the quoting rule is trivially explicit.
    """
    _require_profile(column_profile)
    header = ",".join(column for column, _ in columns_for(column_profile))
    lines = [header, *(",".join(row) for row in rows)]
    return ("\n".join(lines) + "\n").encode()


def _row(
    seed: int,
    index: int,
    column_profile: str,
    rows_per_transaction: int,
) -> tuple[str, ...]:
    draw = _draws(seed, index)
    units = draw(0, MAX_UNITS - 1) + 1
    unit_price_minor = _UNIT_PRICE_MINOR_FLOOR + draw(1, _UNIT_PRICE_MINOR_SPAN)
    revenue_minor = unit_price_minor * units
    core = (
        f"TXN-{index // rows_per_transaction:08d}",
        (FIRST_DAY + timedelta(days=draw(2, DAY_SPAN))).isoformat(),
        f"SKU-{draw(3, PRODUCT_COUNT):04d}",
        f"CAT-{draw(4, CATEGORY_COUNT):02d}",
        f"STORE-{draw(5, STORE_COUNT):03d}",
        f"CHANNEL-{draw(6, CHANNEL_COUNT):01d}",
        str(units),
        _money(revenue_minor),
    )
    if column_profile == PROFILE_CORE:
        return core
    return core + _conditional_fields(draw, revenue_minor, index)


def _conditional_fields(
    draw: _Draw,
    revenue_minor: int,
    index: int,
) -> tuple[str, ...]:
    cost_percent = _COST_SHARE_FLOOR_PERCENT + draw(7, _COST_SHARE_SPAN_PERCENT)
    discount_minor = _share_when(
        draw, slot=8, gate=DISCOUNT_RATE_PERCENT, amount=revenue_minor,
        span=_DISCOUNT_SHARE_SPAN_PERCENT,
    )
    refund_minor = _share_when(
        draw, slot=9, gate=REFUND_RATE_PERCENT, amount=revenue_minor,
        span=_REFUND_SHARE_SPAN_PERCENT,
    )
    return (
        _money(revenue_minor * cost_percent // 100),
        _money(discount_minor),
        _money(refund_minor),
        f"shopper.{index:08d}@example.invalid",
    )


def _share_when(draw: _Draw, *, slot: int, gate: int, amount: int, span: int) -> int:
    """A share of `amount`, or nothing, according to a seeded draw against `gate`."""
    if draw(slot, 100) >= gate:
        return 0
    return amount * (draw(slot + 4, span) + 1) // 100


def _money(minor_units: int) -> str:
    """Exact decimal text with exactly two fraction digits, assembled from integers."""
    return f"{minor_units // 100}.{minor_units % 100:02d}"


class _Draw:
    """A bounded integer per slot, derived from the seed and the row index."""

    __slots__ = ("_digest",)

    def __init__(self, digest: bytes) -> None:
        self._digest = digest

    def __call__(self, slot: int, bound: int) -> int:
        start = slot * 3
        chunk = int.from_bytes(self._digest[start : start + 3], "big")
        return chunk % bound


def _draws(seed: int, index: int) -> _Draw:
    return _Draw(hashlib.sha256(f"{seed}:{index}".encode()).digest())


def _require_positive(value: int, name: str) -> None:
    if value <= 0:
        raise RowsRefused(f"{name} must be positive.")


def _require_profile(column_profile: str) -> None:
    if column_profile not in (PROFILE_CORE, PROFILE_EXTENDED):
        raise RowsRefused(f"Unknown column profile {column_profile!r}.")


__all__ = [
    "CATEGORY_COUNT",
    "CHANNEL_COUNT",
    "CURRENCY",
    "DAY_SPAN",
    "DISCOUNT_RATE_PERCENT",
    "FIRST_DAY",
    "LAST_DAY",
    "MAX_UNITS",
    "PRODUCT_COUNT",
    "REFUND_RATE_PERCENT",
    "STORE_COUNT",
    "RowsRefused",
    "build_rows",
    "csv_document",
]
