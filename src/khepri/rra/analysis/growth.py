"""Splitting one governed revenue change between price and volume.

The formula is fixed by `RRA-008` and not chosen here:

    (average_selling_price_prior * units_change) + (units_current * price_change)

The two terms are the volume effect and the price effect. They sum to the revenue
change identically, not approximately -- expand them and everything cancels but
`revenue_current - revenue_prior`. `RRA-008` therefore requires the sum asserted as
an **exact equality** and treats any inequality as a reconciliation failure, so this
module refuses rather than publishing a split that does not account for the change
it claims to explain.

**The interaction term goes to price, and that is visible in the formula.** The
price term multiplies by `units_current` rather than `units_prior`, so the
price-times-volume cross term lands there. It is the only part of the decomposition
a reader cannot recover from the totals, which is why `RRA-008` requires the
assignment recorded.

**Recorded as a caveat, not as a fact.** `Fact.value` is a decimal string that every
consumer parses -- the workbook writes it, the narrative validates its numbers
against it. A fact whose value read "price" would be a number-shaped hole in that
contract. A caveat is the governed channel for a qualification that must reach a
reader in both languages, and it is attached to the price effect because that is
where the term went.

**One change, shared with the comparison family.** Which two periods are compared is
`windows.compared_labels`, the same function `comparison.py` uses. If this module
chose its own window, the report would state a revenue delta in the comparison
section and decompose a different delta in the growth section, and both would
reconcile perfectly, because reconciliation compares rendered strings.

**Period-over-period only.** `RRA-008` asks the comparison family for two modes in as
many words and asks this one for "a revenue change" without naming any. The mode is
recorded in each fact's identity scope, so what was split is never ambiguous, and
extending to year-over-year is a design decision rather than a specification
requirement.

**Quantized once, at the end.** Both effects are derived at the package's arithmetic
precision and rounded only when stated. An average selling price is a division and
rarely terminates; quantizing it first would leave the published parts summing to
something other than the published change, and the additivity guard would then
refuse a decomposition that is arithmetically fine.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext

from khepri.rra.aggregates import Bucket
from khepri.rra.analysis.windows import MODE_PERIOD_OVER_PERIOD, compared_labels
from khepri.rra.facts import (
    ARITHMETIC_PRECISION,
    METRIC_UNITS,
    REASON_INPUT_UNAVAILABLE,
    UNIT_MONETARY,
    Fact,
    FactPackage,
    FactSeries,
    RefusedResult,
    fact_identity,
)
from khepri.rra.mapping import SEMANTIC_REVENUE, SEMANTIC_TRANSACTION_DATE, SEMANTIC_UNITS

# This family's own formula version, pinned separately from the package's, so a
# correction to the decomposition alone cannot reuse the identifiers of a
# materially different number.
GROWTH_FORMULA_VERSION = "rra008.growth.v1"

METRIC_REVENUE_CHANGE = "growth_revenue_change"
METRIC_PRICE_EFFECT = "growth_price_effect"
METRIC_VOLUME_EFFECT = "growth_volume_effect"
GOVERNED_METRICS = (METRIC_REVENUE_CHANGE, METRIC_PRICE_EFFECT, METRIC_VOLUME_EFFECT)

REASON_UNITS_ABSENT = "units_absent"
REASON_NOT_ADDITIVE = "decomposition_not_additive"
# Shared wording with the comparison family, because it is the same finding about
# the same window: there was no prior period to compare against.
REASON_PRIOR_WINDOW_ABSENT = "prior_window_absent"

# Where the price-times-volume cross term was placed. A governed disclosure rather
# than a fact, because a fact states a number.
CAVEAT_INTERACTION_ASSIGNED_TO_PRICE = "growth_interaction_assigned_to_price"

# What these facts are derived from, in the governed mapping vocabulary. The date
# is an input as much as the measures: it decides which two periods are compared.
_INPUTS = (SEMANTIC_TRANSACTION_DATE, SEMANTIC_REVENUE, SEMANTIC_UNITS)


@dataclass(frozen=True, slots=True)
class _Period:
    """One period's revenue and units, with an average selling price it can state."""

    revenue: Decimal
    units: Decimal

    def average_selling_price(self) -> Decimal:
        return self.revenue / self.units


@dataclass(frozen=True, slots=True)
class _Split:
    """A decomposition and the caveats its facts inherit.

    Carried as one value so building a fact takes three arguments rather than six,
    and so two facts of the same split cannot disagree about which periods they
    came from.
    """

    change: Decimal
    price: Decimal
    volume: Decimal
    caveats: tuple[str, ...]

    def value_of(self, metric: str) -> Decimal:
        if metric == METRIC_PRICE_EFFECT:
            return self.price
        if metric == METRIC_VOLUME_EFFECT:
            return self.volume
        return self.change

    def caveats_of(self, metric: str) -> tuple[str, ...]:
        if metric == METRIC_PRICE_EFFECT:
            return (*self.caveats, CAVEAT_INTERACTION_ASSIGNED_TO_PRICE)
        return self.caveats


def derive(package: FactPackage) -> tuple[Fact, ...] | RefusedResult:
    """The decomposition, or the one refusal that explains why there is none.

    Four causes, each named for what actually happened rather than for whichever
    reason was nearest to hand.

    - No revenue trend at all: `required_input_unavailable`.
    - A trend with no comparable pair, which is any dataset short of two settled
      periods: `prior_window_absent`. Calling that "units absent" would blame a
      measure for a coverage gap.
    - Units unmapped, absent, or zero in either period: `units_absent`, because an
      average selling price over no units is not a number.
    - Parts that do not sum to the change: `decomposition_not_additive`, which
      `RRA-008` defines as a reconciliation failure and not a rounding artifact.
    """
    with localcontext(Context(prec=ARITHMETIC_PRECISION)):
        return _derive(package)


def _derive(package: FactPackage) -> tuple[Fact, ...] | RefusedResult:
    revenue = package.trend()
    if revenue is None:
        return RefusedResult(
            metric=METRIC_REVENUE_CHANGE,
            reason=REASON_INPUT_UNAVAILABLE,
        )
    labels = compared_labels(revenue.series, MODE_PERIOD_OVER_PERIOD)
    if labels is None:
        return RefusedResult(
            metric=METRIC_REVENUE_CHANGE,
            reason=REASON_PRIOR_WINDOW_ABSENT,
        )
    periods = _periods(package, labels)
    if periods is None:
        return RefusedResult(metric=METRIC_REVENUE_CHANGE, reason=REASON_UNITS_ABSENT)
    return _split(periods, revenue.caveats, package.monetary_precision)


def _periods(
    package: FactPackage,
    labels: tuple[str, str],
) -> tuple[_Period, _Period] | None:
    """The compared pair as revenue and units, or nothing statable.

    Units come from the units trend rather than from a total, because the split is
    of one period against another and a whole-dataset unit count would silently
    decompose the wrong thing.
    """
    units = package.trend(METRIC_UNITS)
    revenue = package.trend()
    if units is None or revenue is None:
        return None
    current = _period(revenue, units, labels[0])
    prior = _period(revenue, units, labels[1])
    if current is None or prior is None:
        return None
    return (current, prior)


def _period(revenue: FactSeries, units: FactSeries, label: str) -> _Period | None:
    """One period, or nothing when it cannot state an average selling price."""
    measured = _measure_at(revenue, label)
    counted = _divisor_at(units, label)
    if measured is None or counted is None:
        return None
    return _Period(revenue=measured, units=counted)


def _measure_at(series: FactSeries, label: str) -> Decimal | None:
    """One period's measure, absent when the bucket or its value is."""
    bucket = _bucket_at(series, label)
    return None if bucket is None else bucket.value


def _divisor_at(series: FactSeries, label: str) -> Decimal | None:
    """Units that can divide a revenue: present, and not zero.

    Zero refuses here rather than dividing. A price per nothing is not a number,
    and `RRA-008` requires the refusal instead of a substituted figure.
    """
    units = _measure_at(series, label)
    if units is None or units == 0:
        return None
    return units


def _bucket_at(series: FactSeries, label: str) -> Bucket | None:
    return next(
        (bucket for bucket in series.series.buckets if bucket.label == label),
        None,
    )


def _split(
    periods: tuple[_Period, _Period],
    inherited: tuple[str, ...],
    precision: int,
) -> tuple[Fact, ...] | RefusedResult:
    """The two effects and the change, quantized once and checked for additivity."""
    current, prior = periods
    scale = Decimal(1).scaleb(-precision)
    volume = (
        prior.average_selling_price() * (current.units - prior.units)
    ).quantize(scale)
    price = (
        current.units
        * (current.average_selling_price() - prior.average_selling_price())
    ).quantize(scale)
    change = (current.revenue - prior.revenue).quantize(scale)
    if price + volume != change:
        return RefusedResult(metric=METRIC_REVENUE_CHANGE, reason=REASON_NOT_ADDITIVE)
    split = _Split(change=change, price=price, volume=volume, caveats=inherited)
    return tuple(_fact(split, metric, precision) for metric in GOVERNED_METRICS)


def mode_of(fact: Fact) -> str | None:
    """Which change this fact decomposes, recovered from its identity.

    Only one mode is derived today. Recomputing rather than asserting keeps the
    check honest when a second one arrives, and proves the identity depends on it.
    """
    return (
        MODE_PERIOD_OVER_PERIOD
        if fact_identity(
            metric=fact.metric,
            scope=(MODE_PERIOD_OVER_PERIOD,),
            formula_version=GROWTH_FORMULA_VERSION,
        )[0]
        == fact.fact_id
        else None
    )


def _fact(split: _Split, metric: str, precision: int) -> Fact:
    fact_id, citation_id = fact_identity(
        metric=metric,
        scope=(MODE_PERIOD_OVER_PERIOD,),
        formula_version=GROWTH_FORMULA_VERSION,
    )
    return Fact(
        fact_id=fact_id,
        citation_id=citation_id,
        metric=metric,
        value=str(split.value_of(metric)),
        precision=precision,
        unit_kind=UNIT_MONETARY,
        inputs=_INPUTS,
        caveats=split.caveats_of(metric),
        formula_version=GROWTH_FORMULA_VERSION,
    )
