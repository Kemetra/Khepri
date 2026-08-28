from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

MAX_COMPARISON_BUCKETS = 20
# The same four places `facts.RATIO_PRECISION` uses, for the same reason: a share
# is a fraction, and four places is what the governed ratio contract states.
SHARE_PRECISION = 4
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
    """One aggregated group carrying exactly one governed measure.

    `days` and `transactions` are the two retained counts `RRA-004` requires, and
    exactly one of them is populated per aggregate kind: a time bucket knows how
    many distinct dates it covers, a dimension bucket how many distinct
    transactions it contains. The other stays `None` rather than zero, because
    "not counted here" and "counted, and none" are different findings.
    """

    label: str
    value: Decimal | None
    rows: int
    days: int | None = None
    transactions: int | None = None
    #: Whether a posted *sale* row landed in this bucket.
    #:
    #: `RRA-008` puts attach rate on `dimension_complete_sales:<dimension>`, so
    #: a value carried only by a return is outside that population. Without
    #: this the bucket still published, and because return transaction keys are
    #: masked it published a plausible `0.0000` -- a value that reads as "never
    #: bought with anything" for something never sold at all.
    #:
    #: Defaults `True` so a time bucket, and any caller with no event kinds to
    #: offer, is unaffected.
    sold: bool = True

    def as_document(self, *, precision: int) -> dict[str, object]:
        return {
            "label": self.label,
            "value": None if self.value is None else _text(self.value, precision),
            "rows": self.rows,
            "days": self.days,
            # Absence serializes as absence: a bucket a sale landed in is
            # the ordinary case, so only the exception is recorded and a
            # legacy document round-trips unchanged.
            **({} if self.sold else {"sold": False}),
            "transactions": self.transactions,
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
class ConcentrationCurve:
    """The ranked cumulative revenue share over the full distinct-value set.

    Retained before display truncation, because it cannot be recovered after it.
    `MAX_COMPARISON_BUCKETS` survivors plus one aggregated `other` cannot yield a
    curve over fifty-seven values, and ranking the survivors while calling the
    result a full-set statistic is what `RRA-008` forbids in as many words.

    **Shares only, and no labels.** The display truncates precisely so a report
    cannot name every distinct value; a curve carrying labels would reintroduce
    all of them through the aggregate and hand a surface the list the truncation
    withheld.

    `ranked_values` is not always `distinct_values`. A value whose measure is
    absent has no rank, so both counts are recorded and a consumer can see how
    much of the set the curve speaks for.
    """

    distinct_values: int
    ranked_values: int
    shares: tuple[Decimal, ...]

    def as_document(self) -> dict[str, object]:
        return {
            "distinct_values": self.distinct_values,
            "ranked_values": self.ranked_values,
            "shares": [_text(share, SHARE_PRECISION) for share in self.shares],
        }


@dataclass(frozen=True, slots=True)
class Comparison:
    dimension: str
    buckets: tuple[Bucket, ...]
    distinct_values: int
    truncated_values: int
    redacted_values: int = 0
    distinct_transactions: int | None = None
    curve: ConcentrationCurve | None = None
    #: Whether any grouped row carried no dimension value.
    #:
    #: Recorded when the rows are accumulated, before the display limit is
    #: applied, because truncation is not reversible: a consumer scanning the
    #: published buckets for the synthetic `unlabelled` label stops seeing it
    #: the moment it ranks below the limit and is folded into `other`, and
    #: then reports a dimension complete that never was.
    #:
    #: A *redacted* value is not incomplete. It is present and known, withheld
    #: only from display, so it never sets this.
    incomplete_values: bool = False

    def as_document(self, *, precision: int) -> dict[str, object]:
        return {
            "dimension": self.dimension,
            "distinct_values": self.distinct_values,
            "truncated_values": self.truncated_values,
            "redacted_values": self.redacted_values,
            "distinct_transactions": self.distinct_transactions,
            # Absence serializes as absence. `package_source` compares the
            # rebuilt digest against the stored one, so emitting a key a legacy
            # comparison does not carry makes that document re-digest
            # differently and a validly stored package is refused as corrupt.
            # `False` is the value a legacy document means, so omitting it
            # loses nothing.
            **(
                {}
                if not self.incomplete_values
                else {"incomplete_values": self.incomplete_values}
            ),
            "curve": None if self.curve is None else self.curve.as_document(),
            "buckets": [bucket.as_document(precision=precision) for bucket in self.buckets],
        }


@dataclass
class _Accumulator:
    total: Decimal = Decimal(0)
    rows: int = 0
    present: bool = False
    #: Whether any row in this bucket carried no value. `RRA-004`:33 gives period
    #: and dimension revenue the headline's population, and `:46` gives that
    #: population "no partial-coverage vocabulary" -- so a bucket holding one row
    #: with a value and one without has a gap in its *own* population, and the
    #: sum of what happened to be there is a part published as a whole.
    absent: bool = False
    keys: set[str] = field(default_factory=set)
    #: The same total over posted sales alone, which is what the
    #: concentration curve ranks. `RRA-008` ranks "posted-sale revenue", while
    #: the published buckets stay `financial_posted` because `RRA-004` assigns
    #: the revenue comparison that population deliberately. Kept beside
    #: `total` rather than replacing it so one accumulation serves both.
    sale_total: Decimal = Decimal(0)
    sale_present: bool = False
    #: Whether any posted *sale* row carried this key at all, measure or not.
    #: Distinct from `sale_present`, which needs a value: a sale with no revenue
    #: is in the dimension set and not in the revenue ranking.
    sale_row: bool = False
    #: Whether a posted *sale* row on this value carried no revenue. `RRA-008`
    #: ranks the set "with complete sale revenue", so such a value is outside the
    #: population -- ranking it on the rows that did carry an amount states a
    #: share of a base missing an unknown quantity.
    sale_absent: bool = False

    def add(
        self,
        value: Decimal | None,
        key: str | None = None,
        *,
        sale: bool = True,
    ) -> None:
        self.rows += 1
        if sale:
            self.sale_row = True
        if value is None:
            self.absent = True
            if sale:
                self.sale_absent = True
        else:
            self.total += value
            self.present = True
            if sale:
                self.sale_total += value
                self.sale_present = True
        if key is not None:
            self.keys.add(key)

    def merge(self, other: _Accumulator) -> None:
        self.total += other.total
        self.rows += other.rows
        self.present = self.present or other.present
        self.absent = self.absent or other.absent
        self.sale_total += other.sale_total
        self.sale_present = self.sale_present or other.sale_present
        self.sale_row = self.sale_row or other.sale_row
        self.sale_absent = self.sale_absent or other.sale_absent
        # Unioned, never summed. Every dropped value may share one transaction,
        # and adding their counts would report five where the truth is one --
        # the row-count substitution `RRA-008` forbids, one level up.
        self.keys |= other.keys

    @property
    def whole(self) -> Decimal | None:
        """The total, or nothing when this bucket's own rows are incomplete."""
        return self.total if self.present and not self.absent else None

    def time_bucket(self, label: str) -> Bucket:
        return Bucket(
            label=label,
            value=self.whole,
            rows=self.rows,
            days=len(self.keys),
        )

    def value_bucket(self, label: str, *, counted: bool) -> Bucket:
        return Bucket(
            label=label,
            value=self.whole,
            rows=self.rows,
            transactions=len(self.keys) if counted else None,
            sold=self.sale_row,
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
        accumulators.setdefault(label, _Accumulator()).add(value, moment.isoformat())
    return Series(
        granularity=granularity,
        buckets=tuple(
            accumulators[label].time_bucket(label) for label in sorted(accumulators)
        ),
    )


def build_comparison(
    *,
    dimension: str,
    keys: list[str | None],
    values: list[Decimal | None],
    display: Callable[[str], str] | None = None,
    transactions: list[str | None] | None = None,
    sales: list[bool] | None = None,
    limit: int = MAX_COMPARISON_BUCKETS,
) -> Comparison:
    """Group by the source value; sanitize only the label that is displayed.

    Grouping never merges two distinct source values, even when they reduce to
    the same display text. Colliding labels, and any label that would shadow a
    reserved synthetic bucket, are disambiguated by a stable digest of the
    source value so every bucket stays individually identifiable.

    The concentration curve is derived here, before `limit` is applied, because
    truncation is not reversible: the dropped values and their revenues are gone
    once they have been folded into `other`.

    `sales` says which rows are posted sales, for the concentration curve, which
    `RRA-008` ranks over posted-sale revenue while the published buckets stay
    `financial_posted`. Absent, every row counts as a sale.

    `transactions` is the mapped transaction identifier per row, or `None` when
    no identifier is mapped. Absent, every transaction count stays `None` -- a
    row count never stands in for one.
    """
    accumulators: dict[str | None, _Accumulator] = {}
    members = transactions if transactions is not None else [None] * len(keys)
    # Absent, every row counts as a sale: a caller with no event kinds to
    # offer has admitted no returns to exclude.
    kinds = sales if sales is not None else [True] * len(keys)
    for key, value, member, is_sale in zip(
        keys, values, members, kinds, strict=True
    ):
        accumulators.setdefault(key, _Accumulator()).add(
            value, member, sale=is_sale
        )

    labels = _labels(list(accumulators), display)
    # Display order ranks the published `financial_posted` total, which is what
    # the buckets show. `_curve` re-ranks on sale revenue for the same reason it
    # sums it: `RRA-008` ranks posted-sale revenue, and a value with heavy
    # returns must not be placed below its true sale contribution.
    ordered = sorted(
        accumulators,
        key=lambda key: (-accumulators[key].total, labels[key]),
    )
    # Return-only values are not in the posted-sale set at all: `RRA-008` ranks
    # "the full, non-null, admissible product or category set with complete sale
    # revenue", and a value no sale ever carried is none of those. Left in, it
    # inflated `distinct_values`, which a reader takes as the size of the set the
    # curve speaks for.
    ranked_order = sorted(
        (
            key
            for key in accumulators
            if accumulators[key].sale_row and not accumulators[key].sale_absent
        ),
        key=lambda key: (-accumulators[key].sale_total, labels[key]),
    )
    counted = transactions is not None
    kept, dropped = ordered[:limit], ordered[limit:]
    buckets = [accumulators[key].value_bucket(labels[key], counted=counted) for key in kept]
    if dropped:
        remainder = _Accumulator()
        for key in dropped:
            remainder.merge(accumulators[key])
        buckets.append(remainder.value_bucket(OTHER_BUCKET_LABEL, counted=counted))
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
        distinct_transactions=_distinct_members(accumulators) if counted else None,
        # Asked of the accumulator keys, which are the source values, rather
        # than of the buckets, which are what display kept -- and only of the
        # keys a *sale* landed on. `RRA-008` puts attach rate and concentration
        # on posted-sale populations, so a return carrying no product said
        # nothing about whether the sale dimension is complete, and refused a
        # provably complete one.
        incomplete_values=any(
            key is None and accumulators[key].sale_row for key in accumulators
        ),
        curve=_curve([accumulators[key] for key in ranked_order]),
    )


def _distinct_members(accumulators: dict[str | None, _Accumulator]) -> int:
    """The full-set transaction total, unioned across every value.

    Summing the per-bucket counts would count a transaction once per value it
    contains, so a four-line invoice would report four transactions.
    """
    return len({key for entry in accumulators.values() for key in entry.keys})


def _curve(ordered: list[_Accumulator]) -> ConcentrationCurve | None:
    """The cumulative share of each ranked value, or nothing statable.

    Only values with a present measure are ranked; one with no revenue at all has
    no place in a revenue ranking. Both counts are recorded so a consumer can see
    how much of the distinct set the curve speaks for.

    A non-positive total, or any negative ranked total, yields no curve. Shares
    against a zero or negative base do not mean what a reader takes them to mean,
    and a "cumulative" curve that dips is not one. Refusing here leaves the
    governed refusal to the analysis family rather than publishing a curve whose
    shape contradicts its name.
    """
    # `RRA-008` ranks posted-sale revenue. Reading `total` here ranked
    # return-inclusive financial revenue, so a value with heavy returns was
    # placed below its true sale contribution -- and the top-decile and
    # top-quartile shares read off this curve inherited the same base.
    ranked = [entry.sale_total for entry in ordered if entry.sale_present]
    total = sum(ranked, Decimal(0))
    if total <= 0 or any(value < 0 for value in ranked):
        return None
    running = Decimal(0)
    shares: list[Decimal] = []
    for value in ranked:
        running += value
        # Quantized here rather than at serialization, so the curve holds the
        # precision it publishes. A full-precision share would not survive its own
        # document: `rebuild_fact_package` would return a curve unequal to the one
        # it was published from, and `RRA-004` requires reruns byte-equivalent.
        shares.append((running / total).quantize(Decimal(1).scaleb(-SHARE_PRECISION)))
    return ConcentrationCurve(
        distinct_values=len(ordered),
        ranked_values=len(ranked),
        shares=tuple(shares),
    )


def reconciles(
    buckets: tuple[Bucket, ...],
    *,
    total: Decimal | None,
    rows_total: int,
    gapped: bool = False,
) -> bool:
    """Whether the published buckets account for every row and every value.

    **The row count is checked unconditionally, and the sum only against the
    buckets that published one.** A bucket refuses when its own rows are
    incomplete (`RRA-004`:33 gives period and dimension revenue the headline's
    population, and `:46` gives that population no partial-coverage vocabulary),
    so a package whose headline refuses can still carry complete buckets beside
    incomplete ones. Requiring every bucket to be absent whenever the headline is
    would drop the whole comparison and take the buckets that *are* proven with
    it -- the collateral refusal `RRA-004`:97 forbids.

    `gapped` is that state, and it is passed rather than inferred: a `total` of
    `None` also means "no measure was mapped at all", where a bucket holding a
    value is carrying one from nowhere and must still be rejected. The caller
    knows which of the two it has.
    """
    if sum(bucket.rows for bucket in buckets) != rows_total:
        return False
    parts = [bucket.value for bucket in buckets if bucket.value is not None]
    if not gapped:
        if total is None:
            # No measure to bucket at all, so a bucket holding a value is
            # carrying one from nowhere.
            return not parts
        return sum(parts, Decimal(0)) == total
    # The measure exists and some row of it does not. Every bucket over an
    # incomplete row refused, so what published is a strict subset of `total` by
    # construction and comparing the two proves nothing. The row count above is
    # what still holds every row to account.
    return True


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
