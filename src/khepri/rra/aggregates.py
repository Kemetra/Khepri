from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

MAX_COMPARISON_BUCKETS = 20
OTHER_BUCKET_LABEL = "other"
UNLABELLED_BUCKET_LABEL = "unlabelled"
REDACTED_BUCKET_LABEL = "redacted"
RESERVED_LABELS = frozenset(
    {OTHER_BUCKET_LABEL, UNLABELLED_BUCKET_LABEL, REDACTED_BUCKET_LABEL}
)

# A display function returns this to mark a value as unpublishable. Label
# sanitizing strips control characters, so no source value can produce it.
REDACTION_SENTINEL = "\x00redacted"

# The whole generated redaction namespace is reserved, not just the bare word,
# so a source value spelled "redacted 1" cannot collide with a redacted bucket.
_GENERATED_REDACTION = re.compile(rf"{REDACTED_BUCKET_LABEL}(?: \d+)?")

GRANULARITY_DAY = "day"
GRANULARITY_MONTH = "month"
GRANULARITY_DAY_SPAN = 92


@dataclass(frozen=True, slots=True)
class Bucket:
    """One aggregated group carrying exactly one governed measure."""

    label: str
    value: Decimal | None
    rows: int

    def as_document(self, *, precision: int) -> dict[str, object]:
        return {
            "label": self.label,
            "value": None if self.value is None else _text(self.value, precision),
            "rows": self.rows,
        }


@dataclass(frozen=True, slots=True)
class Series:
    granularity: str
    buckets: tuple[Bucket, ...]

    def as_document(self, *, precision: int) -> dict[str, object]:
        return {
            "granularity": self.granularity,
            "points": [bucket.as_document(precision=precision) for bucket in self.buckets],
        }


@dataclass(frozen=True, slots=True)
class Comparison:
    dimension: str
    buckets: tuple[Bucket, ...]
    distinct_values: int
    truncated_values: int
    redacted_values: int = 0

    def as_document(self, *, precision: int) -> dict[str, object]:
        return {
            "dimension": self.dimension,
            "distinct_values": self.distinct_values,
            "truncated_values": self.truncated_values,
            "redacted_values": self.redacted_values,
            "buckets": [bucket.as_document(precision=precision) for bucket in self.buckets],
        }


@dataclass
class _Accumulator:
    total: Decimal = Decimal(0)
    rows: int = 0
    present: bool = False

    def add(self, value: Decimal | None) -> None:
        self.rows += 1
        if value is not None:
            self.total += value
            self.present = True

    def merge(self, other: _Accumulator) -> None:
        self.total += other.total
        self.rows += other.rows
        self.present = self.present or other.present

    def bucket(self, label: str) -> Bucket:
        return Bucket(
            label=label,
            value=self.total if self.present else None,
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
    values: list[Decimal | None],
    granularity: str,
) -> Series:
    accumulators: dict[str, _Accumulator] = {}
    for moment, value in zip(dates, values, strict=True):
        if moment is None:
            continue
        label = period_label(moment, granularity)
        accumulators.setdefault(label, _Accumulator()).add(value)
    return Series(
        granularity=granularity,
        buckets=tuple(accumulators[label].bucket(label) for label in sorted(accumulators)),
    )


def build_comparison(
    *,
    dimension: str,
    keys: list[str | None],
    values: list[Decimal | None],
    display: Callable[[str], str] | None = None,
    limit: int = MAX_COMPARISON_BUCKETS,
) -> Comparison:
    """Group by the source value; sanitize only the label that is displayed.

    Grouping never merges two distinct source values, even when they reduce to
    the same display text. Colliding labels, and any label that would shadow a
    reserved synthetic bucket, are disambiguated by a stable digest of the
    source value so every bucket stays individually identifiable.
    """
    accumulators: dict[str | None, _Accumulator] = {}
    for key, value in zip(keys, values, strict=True):
        accumulators.setdefault(key, _Accumulator()).add(value)

    labels = _labels(list(accumulators), display)
    ordered = sorted(
        accumulators,
        key=lambda key: (-accumulators[key].total, labels[key]),
    )
    kept, dropped = ordered[:limit], ordered[limit:]
    buckets = [accumulators[key].bucket(labels[key]) for key in kept]
    if dropped:
        remainder = _Accumulator()
        for key in dropped:
            remainder.merge(accumulators[key])
        buckets.append(remainder.bucket(OTHER_BUCKET_LABEL))
    return Comparison(
        dimension=dimension,
        buckets=tuple(buckets),
        distinct_values=len(accumulators),
        truncated_values=len(dropped),
        redacted_values=sum(
            1
            for key in accumulators
            if key is not None and display is not None and display(key) == REDACTION_SENTINEL
        ),
    )


def reconciles(
    buckets: tuple[Bucket, ...],
    *,
    total: Decimal | None,
    rows_total: int,
) -> bool:
    if sum(bucket.rows for bucket in buckets) != rows_total:
        return False
    if total is None:
        return all(bucket.value is None for bucket in buckets)
    parts = [bucket.value for bucket in buckets if bucket.value is not None]
    return sum(parts, Decimal(0)) == total


def _labels(
    keys: list[str | None],
    display: Callable[[str], str] | None,
) -> dict[str | None, str]:
    redacted = {
        key: index + 1
        for index, key in enumerate(
            sorted(
                key
                for key in keys
                if key is not None
                and display is not None
                and display(key) == REDACTION_SENTINEL
            )
        )
    }

    rendered: dict[str | None, str] = {}
    for key in keys:
        if key is None:
            rendered[key] = UNLABELLED_BUCKET_LABEL
            continue
        if key in redacted:
            # Positional, never a digest: a short digest of an email or phone
            # number is trivially reversible by enumeration.
            rendered[key] = f"{REDACTED_BUCKET_LABEL} {redacted[key]}"
            continue
        label = display(key) if display is not None else key
        # A source value may never occupy a label reserved for a synthetic or
        # generated bucket, so it yields that text before collisions are counted.
        rendered[key] = (
            f"{label} ({_discriminator(key)})"
            if label in RESERVED_LABELS or _GENERATED_REDACTION.fullmatch(label)
            else label
        )

    return _disambiguate(rendered, protected=set(redacted))


def _disambiguate(
    rendered: dict[str | None, str],
    *,
    protected: set[str],
) -> dict[str | None, str]:
    """Give every bucket a distinct label without ever hashing a protected key.

    A digest is only a hint, not a guarantee: six hex characters do collide, and
    an ordinal suffix can itself match a literal source label. Each label is
    therefore claimed against the labels already assigned, incrementing the
    ordinal until one is free, so uniqueness holds by construction.
    """
    counts: dict[str, int] = {}
    for label in rendered.values():
        counts[label] = counts.get(label, 0) + 1

    suffixed = {
        key: label
        if counts[label] == 1 or key in protected
        else f"{label} ({_discriminator(key)})"
        for key, label in rendered.items()
    }

    # Protected keys claim their labels first so a redacted bucket keeps the
    # canonical generated label and an ordinary value is the one displaced.
    order = sorted(suffixed, key=lambda key: key not in protected)
    taken: set[str] = set()
    final: dict[str | None, str] = {}
    for key in order:
        label = suffixed[key]
        candidate = label
        occurrence = 1
        while candidate in taken:
            occurrence += 1
            candidate = f"{label} #{occurrence}"
        taken.add(candidate)
        final[key] = candidate
    return {key: final[key] for key in rendered}


def _discriminator(key: str | None) -> str:
    return hashlib.sha256(("" if key is None else key).encode()).hexdigest()[:6]


def _text(value: Decimal, precision: int) -> str:
    return str(value.quantize(Decimal(1).scaleb(-precision)))
