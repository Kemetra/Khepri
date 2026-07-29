from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MAX_COMPARISON_BUCKETS = 20
OTHER_BUCKET_LABEL = "other"
UNLABELLED_BUCKET_LABEL = "unlabelled"

GRANULARITY_DAY = "day"
GRANULARITY_MONTH = "month"
GRANULARITY_DAY_SPAN = 92


@dataclass(frozen=True, slots=True)
class Bucket:
    label: str
    revenue: Decimal | None
    units: int | None
    rows: int

    def as_document(self, *, revenue_precision: int) -> dict[str, object]:
        return {
            "label": self.label,
            "revenue": _decimal_text(self.revenue, revenue_precision),
            "units": self.units,
            "rows": self.rows,
        }


@dataclass(frozen=True, slots=True)
class Series:
    granularity: str
    buckets: tuple[Bucket, ...]

    def as_document(self, *, revenue_precision: int) -> dict[str, object]:
        return {
            "granularity": self.granularity,
            "points": [
                bucket.as_document(revenue_precision=revenue_precision)
                for bucket in self.buckets
            ],
        }


@dataclass(frozen=True, slots=True)
class Comparison:
    dimension: str
    buckets: tuple[Bucket, ...]
    distinct_values: int
    truncated_values: int

    def as_document(self, *, revenue_precision: int) -> dict[str, object]:
        return {
            "dimension": self.dimension,
            "distinct_values": self.distinct_values,
            "truncated_values": self.truncated_values,
            "buckets": [
                bucket.as_document(revenue_precision=revenue_precision)
                for bucket in self.buckets
            ],
        }


@dataclass
class _Accumulator:
    revenue: Decimal = Decimal(0)
    units: int = 0
    rows: int = 0
    has_revenue: bool = False
    has_units: bool = False

    def add(self, revenue: Decimal | None, units: int | None) -> None:
        self.rows += 1
        if revenue is not None:
            self.revenue += revenue
            self.has_revenue = True
        if units is not None:
            self.units += units
            self.has_units = True

    def merge(self, other: _Accumulator) -> None:
        self.revenue += other.revenue
        self.units += other.units
        self.rows += other.rows
        self.has_revenue = self.has_revenue or other.has_revenue
        self.has_units = self.has_units or other.has_units

    def bucket(self, label: str) -> Bucket:
        return Bucket(
            label=label,
            revenue=self.revenue if self.has_revenue else None,
            units=self.units if self.has_units else None,
            rows=self.rows,
        )


def granularity_for(dates: list[date]) -> str:
    if not dates:
        return GRANULARITY_DAY
    span = (max(dates) - min(dates)).days
    return GRANULARITY_MONTH if span > GRANULARITY_DAY_SPAN else GRANULARITY_DAY


def period_label(value: date, granularity: str) -> str:
    if granularity == GRANULARITY_MONTH:
        return f"{value.year:04d}-{value.month:02d}"
    return value.isoformat()


def build_series(
    *,
    dates: list[date | None],
    revenues: list[Decimal | None],
    units: list[int | None],
    granularity: str,
) -> Series:
    accumulators: dict[str, _Accumulator] = {}
    for value, revenue, unit in zip(dates, revenues, units, strict=True):
        if value is None:
            continue
        label = period_label(value, granularity)
        accumulators.setdefault(label, _Accumulator()).add(revenue, unit)
    return Series(
        granularity=granularity,
        buckets=tuple(
            accumulators[label].bucket(label) for label in sorted(accumulators)
        ),
    )


def build_comparison(
    *,
    dimension: str,
    labels: list[str | None],
    revenues: list[Decimal | None],
    units: list[int | None],
    limit: int = MAX_COMPARISON_BUCKETS,
) -> Comparison:
    accumulators: dict[str, _Accumulator] = {}
    for label, revenue, unit in zip(labels, revenues, units, strict=True):
        key = label if label is not None else UNLABELLED_BUCKET_LABEL
        accumulators.setdefault(key, _Accumulator()).add(revenue, unit)

    ordered = sorted(
        accumulators,
        key=lambda label: (
            -accumulators[label].revenue,
            -accumulators[label].units,
            label,
        ),
    )
    kept, dropped = ordered[:limit], ordered[limit:]
    buckets = [accumulators[label].bucket(label) for label in kept]
    if dropped:
        remainder = _Accumulator()
        for label in dropped:
            remainder.merge(accumulators[label])
        buckets.append(remainder.bucket(OTHER_BUCKET_LABEL))
    return Comparison(
        dimension=dimension,
        buckets=tuple(buckets),
        distinct_values=len(accumulators),
        truncated_values=len(dropped),
    )


def reconciles(
    buckets: tuple[Bucket, ...],
    *,
    revenue_total: Decimal | None,
    units_total: int | None,
    rows_total: int,
) -> bool:
    if sum(bucket.rows for bucket in buckets) != rows_total:
        return False
    if revenue_total is not None:
        parts = [bucket.revenue for bucket in buckets if bucket.revenue is not None]
        if sum(parts, Decimal(0)) != revenue_total:
            return False
    if units_total is not None:
        counted = [bucket.units for bucket in buckets if bucket.units is not None]
        if sum(counted) != units_total:
            return False
    return True


def _decimal_text(value: Decimal | None, precision: int) -> str | None:
    if value is None:
        return None
    return str(value.quantize(Decimal(1).scaleb(-precision)))
