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
from dataclasses import dataclass
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

# The shortest and longest a rendered line can be, newline included.
#
# Core: 54 bytes of fixed-width identifiers, dates and labels, plus 7 commas, plus units
# at 1 to 2 digits, plus revenue at 4 to 7 characters -- 66 to 70, so 67 to 71 with the
# newline. Extended adds 4 commas, three amounts of 4 to 7 characters each, and a
# 32-byte address: 114 to 127, so 115 to 128.
#
# Both ranges are contiguous, which is what makes exact byte targeting always solvable
# rather than a search that can fail. A drift guard in the tests asserts generated rows
# stay inside them.
LINE_BYTE_RANGE: dict[str, tuple[int, int]] = {
    PROFILE_CORE: (67, 71),
    PROFILE_EXTENDED: (115, 128),
}

# The window exact sizing may select from, which is narrower than what is possible.
#
# Length frequency is badly skewed, because it is driven by decimal digit counts. A core
# line of 67 bytes needs both a single-digit unit count and a revenue under ten, and
# occurs in about one row in eight hundred; 68 occurs in one in forty. Planning against
# the full range therefore starves the search near the end of a document, where the
# remaining budget has to be met exactly. Every length below occurs in at least six per
# cent of rows, so each is findable within a bounded number of attempts.
#
# This is deliberately a property of the *planner*, not of the generator: rows outside
# this window are still generated normally and are still valid. Only the exact-size path
# declines to depend on a length it cannot reliably obtain.
_SELECTABLE_LINE_RANGE: dict[str, tuple[int, int]] = {
    PROFILE_CORE: (69, 71),
    PROFILE_EXTENDED: (119, 124),
}

_UNIT_PRICE_MINOR_FLOOR = 250
_UNIT_PRICE_MINOR_SPAN = 49_750
_COST_SHARE_FLOOR_PERCENT = 45
_COST_SHARE_SPAN_PERCENT = 35

# Row indices reserved for length selection: above any natural row index, so a chosen
# filler cannot coincide with a row the sequence would have produced anyway, and below
# the point where the transaction ordinal stops fitting `TXN-%08d`.
#
# That ceiling is not cosmetic. The ordinal is `index // rows_per_transaction`, so an
# index large enough to need nine digits makes every filler row exactly one byte longer
# than any natural row -- which silently removes the very lengths the search needs, and
# presents as an unsatisfiable budget far from its cause. The bound below holds even at
# one row per transaction, the worst case.
_FILLER_INDEX_BASE = 20_000_000
_FILLER_INDEX_STRIDE = 300_007
_MAX_LENGTH_ATTEMPTS = 256
_MAX_TRANSACTION_ORDINAL = 100_000_000


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


def plan_exact_row_count(target_bytes: int, column_profile: str) -> int:
    """How many rows can sum, with the header, to exactly `target_bytes`.

    Because the achievable line lengths are contiguous, any budget between `n` shortest
    lines and `n` longest lines is reachable with exactly `n` rows: lengthening one row
    by one byte is always available until the budget is met.

    The count is chosen so the *average* row sits mid-range rather than at either edge.
    The fewest feasible rows would be the fastest to generate, and is the wrong choice:
    it demands that almost every row come out at its maximum length, which the length
    distribution supplies only occasionally, so the selection search starves near the
    end. A mid-range target leaves slack in both directions at every step.
    """
    _require_profile(column_profile)
    smallest, largest = _SELECTABLE_LINE_RANGE[column_profile]
    budget = target_bytes - _header_bytes(column_profile)
    if budget < smallest:
        raise RowsRefused("Target is too small for a header and one row.")
    fewest = -(-budget // largest)
    most = budget // smallest
    if fewest > most:
        raise RowsRefused("No row count sums to the target exactly.")
    balanced = round(budget / ((smallest + largest) / 2))
    return max(fewest, min(most, balanced))


def csv_document_of_exact_size(
    seed: int,
    target_bytes: int,
    column_profile: str,
    rows_per_transaction: int,
) -> bytes:
    """A CSV dataset whose stored size equals `target_bytes` exactly.

    `KHEPRI-DEC-006` requires each band to contain at least one CSV dataset sitting
    exactly on the band's upper edge. Sizes are hit by selecting each row's length as it
    is placed, never by padding: a padded field would not be a retail value, and the
    dataset has to remain one `RRA-003` admits.
    """
    _require_positive(rows_per_transaction, "rows_per_transaction")
    row_count = plan_exact_row_count(target_bytes, column_profile)
    plan = _ExactPlan(seed, column_profile, rows_per_transaction)
    budget = target_bytes - _header_bytes(column_profile)
    lines: list[str] = []
    for position in range(row_count):
        line = plan.choose(position, budget, row_count - position - 1)
        lines.append(line)
        budget -= len(line) + 1
    header = ",".join(column for column, _ in columns_for(column_profile))
    return ("\n".join([header, *lines]) + "\n").encode()


def _header_bytes(column_profile: str) -> int:
    header = ",".join(column for column, _ in columns_for(column_profile))
    return len(header.encode()) + 1


@dataclass(frozen=True, slots=True)
class _ExactPlan:
    """The fixed inputs of one exactly-sized document, so helpers stay narrow."""

    seed: int
    column_profile: str
    rows_per_transaction: int

    def line_at(self, index: int) -> str:
        row = _row(self.seed, index, self.column_profile, self.rows_per_transaction)
        return ",".join(row)

    def choose(self, position: int, budget: int, remaining: int) -> str:
        """A row whose length leaves a budget the remaining rows can still hit exactly."""
        smallest, largest = _SELECTABLE_LINE_RANGE[self.column_profile]
        for attempt in range(_MAX_LENGTH_ATTEMPTS):
            line = self.line_at(_candidate_index(position, attempt))
            rest = budget - (len(line) + 1)
            if remaining * smallest <= rest <= remaining * largest:
                return line
        raise RowsRefused("No row length fits the remaining budget.")


def _candidate_index(position: int, attempt: int) -> int:
    """The natural row first, then a reserved index space that cannot collide with it."""
    if attempt == 0:
        return position
    index = _FILLER_INDEX_BASE + attempt * _FILLER_INDEX_STRIDE + position
    if index >= _MAX_TRANSACTION_ORDINAL:
        raise RowsRefused("Document is too large for the reserved selection indices.")
    return index


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


@dataclass(frozen=True, slots=True)
class _ShareRule:
    """How often a conditional amount appears, and how large it is when it does."""

    slot: int
    gate_percent: int
    span_percent: int


_DISCOUNT_RULE = _ShareRule(slot=8, gate_percent=DISCOUNT_RATE_PERCENT, span_percent=25)
_REFUND_RULE = _ShareRule(slot=9, gate_percent=REFUND_RATE_PERCENT, span_percent=100)


def _conditional_fields(
    draw: _Draw,
    revenue_minor: int,
    index: int,
) -> tuple[str, ...]:
    cost_percent = _COST_SHARE_FLOOR_PERCENT + draw(7, _COST_SHARE_SPAN_PERCENT)
    return (
        _money(revenue_minor * cost_percent // 100),
        _money(_share_when(draw, _DISCOUNT_RULE, revenue_minor)),
        _money(_share_when(draw, _REFUND_RULE, revenue_minor)),
        f"shopper.{index:08d}@example.invalid",
    )


def _share_when(draw: _Draw, rule: _ShareRule, amount: int) -> int:
    """A share of `amount`, or nothing, according to a seeded draw against the rule."""
    if draw(rule.slot, 100) >= rule.gate_percent:
        return 0
    return amount * (draw(rule.slot + 100, rule.span_percent) + 1) // 100


def _money(minor_units: int) -> str:
    """Exact decimal text with exactly two fraction digits, assembled from integers."""
    return f"{minor_units // 100}.{minor_units % 100:02d}"


class _Draw:
    """A bounded integer per slot, derived from the seed and the row index.

    Each slot gets its own digest rather than a slice of a shared one. A shared digest
    is only 32 bytes, so a slot past the end silently yields an empty slice and a
    constant zero -- a degenerate value that looks like data and is not.
    """

    __slots__ = ("_key",)

    def __init__(self, key: str) -> None:
        self._key = key

    def __call__(self, slot: int, bound: int) -> int:
        digest = hashlib.sha256(f"{self._key}:{slot}".encode()).digest()
        return int.from_bytes(digest[:8], "big") % bound


def _draws(seed: int, index: int) -> _Draw:
    return _Draw(f"{seed}:{index}")


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
    "LINE_BYTE_RANGE",
    "MAX_UNITS",
    "PRODUCT_COUNT",
    "REFUND_RATE_PERCENT",
    "STORE_COUNT",
    "RowsRefused",
    "build_rows",
    "csv_document",
    "csv_document_of_exact_size",
    "plan_exact_row_count",
]
