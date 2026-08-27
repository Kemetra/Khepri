"""Basket structure: items per transaction, and attach rate per published value.

**Never a row count.** `RRA-008` forbids substituting row count for transaction
count, and the two are easy to confuse because both are integers that look right.
Four line items in three invoices is 1.3333 rows per transaction and 3.6667 items
per transaction, and only the second answers the question.

This module counts nothing itself. Items per transaction divides `METRIC_UNITS` by
`METRIC_TRANSACTIONS`, both governed facts, and `METRIC_TRANSACTIONS` is already a
distinct count that the package refuses outright when the identifier column has
gaps. Attach rate divides `Bucket.transactions` by `Comparison.distinct_transactions`,
both retained by `APP-014` as distinct counts and both unioned rather than summed.
Reading governed aggregates rather than recounting is what satisfies the
requirement -- there is no place here for a row count to creep in.

**Items, not lines.** An earlier plan revision had items per transaction dividing
row count by transaction count. Row count *is* line-item count; `RRA-008` says
items, and the governed items measure is `METRIC_UNITS`.

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

_ITEMS_INPUTS = (SEMANTIC_UNITS, SEMANTIC_TRANSACTION_ID)

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
    """
    found = _dimension(package)
    if found is None:
        return None
    dimension, entry = found
    return next(
        (
            bucket.label
            for bucket in _attachable(entry)
            if _identity(fact.metric, (dimension, bucket.label))[0] == fact.fact_id
        ),
        None,
    )


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
    found = _dimension(package)
    if found is None:
        refused.append(
            RefusedResult(
                metric=METRIC_ATTACH_RATE,
                reason=REASON_DIMENSION_ABSENT,
            )
        )
    elif _incomplete(found[1]):
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


def _counts(package: FactPackage) -> _Basket | None:
    """Units and transactions as governed facts, or nothing divisible."""
    units = package.fact(METRIC_UNITS)
    transactions = package.fact(METRIC_TRANSACTIONS)
    if units is None or transactions is None:
        return None
    counted = Decimal(transactions.value)
    if counted == 0:
        return None
    return _Basket(units=Decimal(units.value), transactions=counted)


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
    for dimension in GOVERNED_DIMENSIONS:
        entry = _ranked(package, dimension)
        if entry is not None:
            return (dimension, entry)
    return None


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
    """
    return tuple(
        bucket
        for bucket in entry.comparison.buckets
        if bucket.label not in _SYNTHETIC_LABELS and bucket.transactions is not None
    )


def _incomplete(entry: FactComparison) -> bool:
    """Whether some eligible row did not carry this dimension's value.

    Read off the synthetic `unlabelled` bucket, which is exactly where
    `build_comparison` puts a null key -- so this asks the aggregate what it
    already recorded rather than re-deriving completeness from the rows.

    The redacted buckets are deliberately *not* treated as incomplete: a redacted
    value is present and known, withheld only from display, so it counts in both
    numerator and denominator without making any rate unknowable.
    """
    return any(
        bucket.label == UNLABELLED_BUCKET_LABEL
        for bucket in entry.comparison.buckets
    )


def _attach_facts(package: FactPackage) -> tuple[Fact, ...]:
    found = _dimension(package)
    if found is None:
        return ()
    dimension, entry = found
    if _incomplete(entry):
        # The whole family, not the unlabelled value alone: every other rate
        # divides by a denominator this transaction inflates.
        return ()
    total = Decimal(entry.comparison.distinct_transactions or 0)
    return tuple(
        _fact(
            METRIC_ATTACH_RATE,
            (dimension, bucket.label),
            Decimal(bucket.transactions or 0) / total,
            entry.caveats,
        )
        for bucket in _attachable(entry)
    )


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
        inputs=_ITEMS_INPUTS if not scope else (scope[0], SEMANTIC_TRANSACTION_ID),
        caveats=caveats,
        formula_version=BASKET_FORMULA_VERSION,
    )
