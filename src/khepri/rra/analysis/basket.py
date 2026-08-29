"""Basket structure: items per transaction, and attach rate per published value.

**Never a row count.** `RRA-008` forbids substituting row count for transaction
count, and the two are easy to confuse because both are integers that look right.
Four line items in three invoices is 1.3333 rows per transaction and 3.6667 items
per transaction, and only the second answers the question.

This module counts nothing itself. Items per transaction divides
`FactPackage.sale_units_total` by
`METRIC_TRANSACTIONS`, both governed facts, and `METRIC_TRANSACTIONS` is already a
distinct count that the package refuses outright when the identifier column has
gaps. Attach rate divides `Bucket.transactions` by `Comparison.distinct_transactions`,
both retained by `APP-014` as distinct counts and both unioned rather than summed.
Reading governed aggregates rather than recounting is what satisfies the
requirement -- there is no place here for a row count to creep in.

**Items, not lines, and sales only.** An earlier plan revision had items per
transaction dividing row count by transaction count. Row count *is* line-item
count; `RRA-008` says items. The governed measure is
`FactPackage.sale_units_total` rather than `METRIC_UNITS`: the latter's
population is `financial_posted` and includes
posted return units, while the denominator is sale-only, so a dataset with
returns published a basket understated by the returned units.

**One attach-rate fact per published value, and none for `other`.** Attach rate is
inherently per value, and each rate is a separate claim a reader can act on, so
each needs its own citation. The count is bounded by `MAX_COMPARISON_BUCKETS`,
which is why per-value facts are right here and wrong for the concentration curve:
that curve spans the full distinct set and is deliberately label-free.

`other` is excluded because it is not "a given admissible dimension value". Its
transaction count is the union of everything truncated, so a rate over it would
state the share of transactions containing something unnamed -- true, and useless.

**Products or categories, as the specification says.** Attach rate needs "an
admissible product or category dimension". Product is preferred for the same
reason the concentration family prefers it: finer grain, and a category answer is
derivable from it while the reverse is not.

**Any measure's comparison will do.** Attach rate reads transaction counts, not the
measure, and `build_comparison` counts the same transactions per key whichever
total it ranks by. Revenue is preferred only because it is the ranking a reader is
otherwise shown. Reading revenue *exclusively* refused a rate whose every input was
present: an input mapping units, an identifier and a product is admissible with no
revenue column at all, and the package then publishes a units comparison carrying
the counts.

**Attach rate inherits its comparison's caveats; items per transaction does not.**
These rates cover the published buckets exactly, so a truncation or redaction
qualification on those buckets qualifies them too -- dropping it would make a
partial set of rates read as a complete one. That is the opposite of the
concentration family, which drops the truncation caveat because its curve spans the
full distinct set and is not limited by it. Items per transaction divides two
whole-dataset totals and is qualified by neither.

**A partial family is not a broken one.** `RRA-008` refuses "the affected result",
so a dataset with transactions but no product dimension still states items per
transaction, and the attach-rate refusal is carried beside it by `refusals`.
Absence is never the disclosure.

**The refusal cause is read, not re-decided.** An unmapped identifier column and one
with gaps are different findings, and the fact package already recorded which
happened when it refused `METRIC_TRANSACTIONS`. This module reports that reason
rather than forming its own opinion, so the two cannot disagree.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext

from khepri.rra.aggregates import (
    OTHER_BUCKET_LABEL,
    UNLABELLED_BUCKET_LABEL,
    Bucket,
)
from khepri.rra.facts import (
    ARITHMETIC_PRECISION,
    EVENT_SALE,
    METRIC_REVENUE,
    METRIC_TRANSACTIONS,
    METRIC_UNITS,
    RATIO_PRECISION,
    REASON_INPUT_UNAVAILABLE,
    UNIT_RATIO,
    Fact,
    FactComparison,
    FactPackage,
    RefusedResult,
    fact_identity,
)
from khepri.rra.mapping import (
    SEMANTIC_CATEGORY,
    SEMANTIC_PRODUCT,
    SEMANTIC_TRANSACTION_ID,
    SEMANTIC_UNITS,
)

# This family's own formula version, pinned separately from the package's, so a
# correction here cannot reuse the identifiers of a materially different number.
BASKET_FORMULA_VERSION = "rra008.basket.v2"

METRIC_ITEMS_PER_TRANSACTION = "basket_items_per_transaction"
METRIC_ATTACH_RATE = "basket_attach_rate"
#: The metrics this family publishes, in the shape `comparison` and `growth`
#: already use. Stated rather than left to a scan of this module's `METRIC_*`
#: names, because those include `METRIC_REVENUE`, `METRIC_TRANSACTIONS` and
#: `METRIC_UNITS` imported from `facts` -- a scan would attribute three core
#: metrics to the basket family.
GOVERNED_METRICS = (METRIC_ITEMS_PER_TRANSACTION, METRIC_ATTACH_RATE)

REASON_TRANSACTION_IDENTIFIER_ABSENT = "transaction_identifier_absent"
# Reserved for this case by the merged plan and by `bundle.py`, which says it
# "can never be a section state, so it belongs with the fact package's result-level
# reasons, which is where the basket slice will put it". This is that slice.
#
# Not `aggregate_unavailable`: that named the missing `RRA-004` aggregate, and
# `APP-014` has since supplied it. A report with no admissible dimension could not
# carry attach rate even with the aggregate in place, so the dimension is the
# failed precondition and naming the aggregate would explain the wrong one. With
# the aggregate present, `aggregate_unavailable` is no longer reachable here at
# all, and an unreachable governed reason is worse than an absent one.
REASON_DIMENSION_ABSENT = "dimension_absent"

# Distinct from the reason above, and the distinction is the point. `dimension_absent`
# means no governed dimension was mapped at all -- there is nothing to state a rate
# over. This means one *was* mapped and some eligible row does not carry its value.
#
# `RRA-008`: "Every eligible sale row must carry the dimension value; one missing
# value refuses that dimension's entire attach family rather than silently entering
# only the denominator." Under `rra008.basket.v1` an unlabelled row was kept out of
# the numerator by `_SYNTHETIC_LABELS` and left in the denominator, so every rate
# published was too low by an amount no reader could see or bound.
REASON_DIMENSION_INCOMPLETE = "dimension_values_incomplete"

# Which dimensions `RRA-008` allows attach rate over, in the order preferred.
GOVERNED_DIMENSIONS = (SEMANTIC_PRODUCT, SEMANTIC_CATEGORY)

REQUIRED_INPUTS = (SEMANTIC_UNITS, SEMANTIC_TRANSACTION_ID)

# The two buckets `build_comparison` synthesizes rather than reads from a source
# value. Neither is an admissible dimension value, so neither gets an attach rate.
_SYNTHETIC_LABELS = frozenset({OTHER_BUCKET_LABEL, UNLABELLED_BUCKET_LABEL})


@dataclass(frozen=True, slots=True)
class _Basket:
    """The two governed counts every basket metric divides by."""

    units: Decimal
    transactions: Decimal


def derive(package: FactPackage) -> tuple[Fact, ...] | RefusedResult:
    """Whatever the package can state about basket structure, or one refusal.

    A refusal is returned only when *nothing* could be stated. When items per
    transaction stands and attach rate does not, the facts come back and the
    refusal is carried by `refusals` -- which is `RRA-008`'s "refuse the affected
    result" rather than the affected family.
    """
    with localcontext(Context(prec=ARITHMETIC_PRECISION)):
        facts = _facts(package)
    if facts:
        return facts
    return _summary(package)


def refusals(package: FactPackage) -> tuple[RefusedResult, ...]:
    """Everything that could not be stated, beside whatever could."""
    with localcontext(Context(prec=ARITHMETIC_PRECISION)):
        return _refusals(package)


def attached_value_of(fact: Fact, package: FactPackage) -> str | None:
    """Which published value this attach rate belongs to, from its identity.

    The label lives in the identity's hashed scope, so it is recomputed against
    the package's own buckets rather than read off the fact. That also proves two
    values cannot collide on one identifier.

    **Searched across every dimension the family published**, not just the first.
    `_attach_facts` states product and category rates independently, and a
    category fact's identity is hashed over the category scope -- so looking only
    at `_dimension()` matched no bucket and returned `None` for a fact the
    package had published. Found in review.
    """
    return next(
        (
            bucket.label
            for dimension, entry in _dimensions(package)
            for bucket in _attachable(entry)
            if _identity(fact.metric, (dimension, bucket.label))[0] == fact.fact_id
        ),
        None,
    )


def attached_label_of(fact: Fact, package: FactPackage) -> str | None:
    """The display label for an attach rate, naming the dimension it belongs to.

    Distinct from `attached_value_of`, which answers *which value* a rate is
    about and is what a caller resolving a bucket needs. This is what a surface
    shows: once product and category families both publish, two buckets can carry
    the same source value -- a product `Water` and a category `Water` -- and a
    bare label renders them as indistinguishable rows and bars.

    Qualified rather than deduplicated, because both rates are real and a reader
    needs to see which is which.
    """
    found = next(
        (
            (dimension, bucket.label)
            for dimension, entry in _dimensions(package)
            for bucket in _attachable(entry)
            if _identity(fact.metric, (dimension, bucket.label))[0] == fact.fact_id
        ),
        None,
    )
    if found is None:
        return None
    dimension, label = found
    return f"{label} ({dimension})"

def _facts(package: FactPackage) -> tuple[Fact, ...]:
    """Each metric stands or falls on its own inputs.

    Attach rate needs no units and items per transaction needs no dimension, so
    neither may be suppressed by the other's missing input. Deriving them together
    once made an absent units measure refuse a rate it could have stated.
    """
    stated = (_items(package), *_attach_facts(package))
    return tuple(fact for fact in stated if fact is not None)


def _refusals(package: FactPackage) -> tuple[RefusedResult, ...]:
    """Per metric, and only for what actually failed.

    A missing identifier is the one failure that takes both, because `RRA-008`
    requires it for each. Everything else refuses one metric beside the other's
    surviving figure.
    """
    if not _identified(package):
        reason = _identifier_reason(package)
        return (
            RefusedResult(metric=METRIC_ITEMS_PER_TRANSACTION, reason=reason),
            RefusedResult(metric=METRIC_ATTACH_RATE, reason=reason),
        )
    refused: list[RefusedResult] = []
    if _items(package) is None:
        refused.append(
            RefusedResult(
                metric=METRIC_ITEMS_PER_TRANSACTION,
                reason=REASON_INPUT_UNAVAILABLE,
            )
        )
    found = _dimensions(package)
    if not found:
        refused.append(
            RefusedResult(
                metric=METRIC_ATTACH_RATE,
                reason=REASON_DIMENSION_ABSENT,
            )
        )
    elif any(_incomplete(entry) for _, entry in found):
        # One refusal per incomplete dimension, because `RRA-008` admits the
        # families independently: a complete category publishes its rates
        # while an incomplete product refuses, and both are stated. Refusing
        # only when *every* dimension was incomplete published the surviving
        # family and left the affected one silently absent -- a customer saw
        # no product rates and no reason for their absence.
        #
        # Stated once rather than per dimension: `RefusedResult` carries no
        # scope, and adding one would widen the governed document for a
        # disclosure the reason already makes.
        refused.append(
            RefusedResult(
                metric=METRIC_ATTACH_RATE,
                reason=REASON_DIMENSION_INCOMPLETE,
            )
        )
    return tuple(refused)


def _identified(package: FactPackage) -> bool:
    """Whether the package could count transactions at all."""
    return package.fact(METRIC_TRANSACTIONS) is not None


def _items(package: FactPackage) -> Fact | None:
    basket = _counts(package)
    if basket is None:
        return None
    # No comparison caveats: this metric reads two whole-dataset totals and is not
    # qualified by anything that happened to a dimension's buckets.
    return _fact(
        METRIC_ITEMS_PER_TRANSACTION,
        (),
        basket.units / basket.transactions,
        (),
    )


def _summary(package: FactPackage) -> RefusedResult:
    """The refusal that stands for the family when it stated nothing at all."""
    recorded = _refusals(package)
    if recorded:
        return recorded[0]
    return RefusedResult(
        metric=METRIC_ITEMS_PER_TRANSACTION,
        reason=REASON_INPUT_UNAVAILABLE,
    )


def _sale_units(package: FactPackage) -> int | None:
    """The basket numerator, from the package or from a package that predates it.

    `sale_units_total` reads back as `None` for a package stored before the field
    existed. Refusing there would take items per transaction away from every
    historical package -- including ones that published the correct figure,
    because their extract admitted no returns and the sale-only sum equals the
    headline units total.

    So a package that proves it admitted sales alone falls back to `METRIC_UNITS`.
    One that admitted returns cannot: for it the two totals genuinely differ, and
    the older figure was the defective `23 / 2` this slice corrected. Absence of
    the field is not evidence the difference is nil.
    """
    if package.sale_units_total is not None:
        return package.sale_units_total
    if any(kind != EVENT_SALE for kind in package.event_kind_filters):
        return None
    headline = package.fact(METRIC_UNITS)
    return None if headline is None else int(Decimal(headline.value))

def _counts(package: FactPackage) -> _Basket | None:
    """Units and transactions as governed facts, or nothing divisible.

    The numerator is `FactPackage.sale_units_total`, not `METRIC_UNITS`. The latter is
    `financial_posted` and includes posted return units, while the denominator
    counts sale transactions only -- so a dataset with returns published a
    basket understated by the returned units, and no reader could detect it
    from the figures beside it. `RRA-008` puts returns in "neither numerator
    nor denominator".
    """
    units = _sale_units(package)
    transactions = package.fact(METRIC_TRANSACTIONS)
    if units is None or transactions is None:
        return None
    counted = Decimal(transactions.value)
    if counted == 0:
        return None
    return _Basket(units=Decimal(units), transactions=counted)


def _identifier_reason(package: FactPackage) -> str:
    """Why the transaction count is missing, as the package itself recorded it.

    An unmapped column and one with gaps are different findings, and the package
    already decided which occurred. `required_input_unavailable` there means the
    column was never mapped, which is this family's
    `transaction_identifier_absent`; anything else is reported verbatim.
    """
    refused = package.refusal(METRIC_TRANSACTIONS)
    if refused is None or refused.reason == REASON_INPUT_UNAVAILABLE:
        return REASON_TRANSACTION_IDENTIFIER_ABSENT
    return refused.reason


def _dimension(package: FactPackage) -> tuple[str, FactComparison] | None:
    """The dimension to state attach rate over, and the comparison that ranked it.

    Any measure will do, because attach rate reads transaction counts and not the
    measure: `build_comparison` counts the same transactions per key whichever
    total it ranks by. Revenue is preferred only because it is the ranking a
    reader is otherwise shown.

    Looking solely at the revenue comparison refused a rate whose every input was
    present: an input mapping units, an identifier and a product is admissible
    without any revenue column, and the package then publishes a units comparison
    carrying the counts.
    """
    found = _dimensions(package)
    return found[0] if found else None


def _dimensions(package: FactPackage) -> tuple[tuple[str, FactComparison], ...]:
    """Every governed dimension the package ranked, in governed order.

    `RRA-008`: product and category attach families "are admitted
    independently and neither suppresses the other."

    `_dimension` returned the first admissible dimension and the caller then
    refused the whole family if it was incomplete -- so a missing product
    value suppressed category rates whose own population was provably
    complete. Enumerating them lets each be judged on its own completeness.
    """
    found = []
    for dimension in GOVERNED_DIMENSIONS:
        entry = _ranked(package, dimension)
        if entry is not None:
            found.append((dimension, entry))
    return tuple(found)


def _ranked(package: FactPackage, dimension: str) -> FactComparison | None:
    """A comparison of this dimension that counted transactions, revenue first."""
    counted = [
        entry
        for entry in package.comparisons
        if entry.comparison.dimension == dimension
        and entry.comparison.distinct_transactions
    ]
    if not counted:
        return None
    return next(
        (entry for entry in counted if entry.measure == METRIC_REVENUE),
        counted[0],
    )


def _attachable(entry: FactComparison) -> tuple[Bucket, ...]:
    """Published buckets that name a real value and carry a transaction count.

    Both synthetic buckets are excluded, because neither is "a given admissible
    dimension value". `other` is the union of everything truncated, so a rate over
    it states the share of transactions containing something unnamed; `unlabelled`
    holds the rows with no value at all, so a rate over it states the share
    containing *nothing* -- which a reader would read as a product.

    A source value literally spelled `other` or `unlabelled` is unaffected:
    `build_comparison` disambiguates any label that would shadow a reserved
    synthetic bucket, so these two labels only ever mean the synthetic ones.
    A value carried only by a *return* is excluded too. `RRA-008` puts attach
    rate on `dimension_complete_sales:<dimension>`, so a product no sale ever
    carried is outside the population -- and because return transaction keys
    are masked it published a plausible `0.0000`, which reads as "never bought
    alongside anything" for something never bought at all.
    """
    return tuple(
        bucket
        for bucket in entry.comparison.buckets
        if bucket.label not in _SYNTHETIC_LABELS
        and bucket.transactions is not None
        and bucket.sold
    )


def _incomplete(entry: FactComparison) -> bool:
    """Whether some eligible row did not carry this dimension's value.

    Read off `Comparison.incomplete_values`, which `build_comparison` records
    when it accumulates a null key -- so this asks the aggregate what it
    already recorded rather than re-deriving completeness from the rows.

    **Not a scan of the published buckets.** That is where this looked before,
    and it self-disarmed: a dimension with more than `MAX_COMPARISON_BUCKETS`
    values whose `unlabelled` bucket ranks below the limit has that bucket
    folded into `other`, and the scan then found nothing and let every rate
    publish against an unproven population. The flag is set before any
    truncation decision, so display cannot change what completeness the
    package claims.

    The redacted buckets are deliberately *not* treated as incomplete: a redacted
    value is present and known, withheld only from display, so it counts in both
    numerator and denominator without making any rate unknowable.
    """
    return entry.comparison.incomplete_values


def _attach_facts(package: FactPackage) -> tuple[Fact, ...]:
    """Every dimension whose own population is complete, judged separately.

    An incomplete dimension still refuses its *whole* family rather than its
    unlabelled value alone: every other rate in it divides by a denominator
    that transaction inflates. What changed is the scope of that refusal --
    `RRA-008` admits the families independently, so one incomplete dimension
    no longer takes a complete one with it.
    """
    stated: list[Fact] = []
    for dimension, entry in _dimensions(package):
        if _incomplete(entry):
            continue
        total = Decimal(entry.comparison.distinct_transactions or 0)
        if total <= 0:
            continue
        stated.extend(
            _fact(
                METRIC_ATTACH_RATE,
                (dimension, bucket.label),
                Decimal(bucket.transactions or 0) / total,
                entry.caveats,
            )
            for bucket in _attachable(entry)
        )
    return tuple(stated)


def _identity(metric: str, scope: tuple[str, ...]) -> tuple[str, str]:
    return fact_identity(
        metric=metric,
        scope=scope,
        formula_version=BASKET_FORMULA_VERSION,
    )


def _fact(
    metric: str,
    scope: tuple[str, ...],
    value: Decimal,
    caveats: tuple[str, ...],
) -> Fact:
    fact_id, citation_id = _identity(metric, scope)
    return Fact(
        fact_id=fact_id,
        citation_id=citation_id,
        metric=metric,
        value=str(value.quantize(Decimal(1).scaleb(-RATIO_PRECISION))),
        precision=RATIO_PRECISION,
        unit_kind=UNIT_RATIO,
        inputs=REQUIRED_INPUTS if not scope else (scope[0], SEMANTIC_TRANSACTION_ID),
        caveats=caveats,
        formula_version=BASKET_FORMULA_VERSION,
    )
