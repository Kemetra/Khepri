"""Concentration over the full distinct-value set, never over the display buckets.

**This family was impossible until `APP-014`.** `RRA-008` requires concentration
"over the full admissible distinct-value set, never over the truncated display
buckets", and `Comparison` published `MAX_COMPARISON_BUCKETS` ranked buckets plus
one aggregated `other`. The omitted values and their revenues were discarded at
truncation, so a curve over fifty-seven values could not be recovered from
twenty-one buckets. Ranking the survivors and labelling the result a full-set
statistic is the precise failure that wording forbids -- and a test asserting
`distinct.value == "57"` would have passed on exactly that fabrication.

`ConcentrationCurve` is now retained before truncation, so this module reads a
measured curve rather than reconstructing one. It never touches
`Comparison.buckets`: a module that reads the display while claiming the full set
is one edit away from ranking it.

**Four scalar facts, and the curve stays where it was measured.** `RRA-008` asks
for the cumulative share curve emitted, and a curve is not a scalar. Emitting one
fact per ranked point would mint fifty-seven governed figures and citation
identifiers for a single statement, and every surface would then have to reconcile
all of them. The curve is already a cited part of the fact package, so the surface
reads it there -- `curve_for` is the one governed way to reach it -- and what this
module derives is the four numbers a reader is actually given: how many values
exist, how many were ranked, and what the top decile and quartile hold.

**Products or categories, and nothing else.** `RRA-008` names those two. Store and
channel are admissible comparison dimensions, and ranking branches by revenue
would answer a question nobody governed. Product is preferred when both exist,
because it is the finer grain and a category ranking is derivable from it while
the reverse is not.

**Deciles and quartiles round up.** A decile of ten ranked values is one value. Ten
divided by ten rounded down is also one, but eight divided by ten rounded down is
zero, and reporting that the top decile holds nought per cent of revenue is false
rather than conservative. Rounding up states the share of at least one value,
which is what a reader of "the top decile" is owed on a small set.

**No classification bands.** `RRA-008` forbids them in as many words. "Highly
concentrated" is a judgement about a threshold nobody approved; a measured share
lets a reader apply their own.

**The truncation caveat is deliberately not inherited.** `CAVEAT_BUCKETS_TRUNCATED`
qualifies the published buckets, and these facts are not those. Attaching it would
disclose the opposite of the truth -- that the figure is limited by a truncation it
was specifically derived to see past. Every other caveat on the source aggregate is
inherited, because `RRA-008` requires each derived fact reconciled to the aggregate
it came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext

from khepri.rra.aggregates import Bucket, ConcentrationCurve, Series
from khepri.rra.facts import (
    ARITHMETIC_PRECISION,
    CAVEAT_BUCKETS_TRUNCATED,
    RATIO_PRECISION,
    UNIT_COUNT,
    UNIT_RATIO,
    Fact,
    FactComparison,
    FactPackage,
    FactSeries,
    RefusedResult,
    fact_identity,
)
from khepri.rra.mapping import SEMANTIC_CATEGORY, SEMANTIC_PRODUCT, SEMANTIC_REVENUE

# This family's own formula version, pinned separately from the package's.
#
# `fact_identity` defaults to the `RRA-004` version, which would name these facts
# under a version saying nothing about how they were derived. A correction to the
# decile rule alone would then reuse the same fact and citation identifiers for a
# materially different number, and a stored citation would point at an answer that
# had changed underneath it.
CONCENTRATION_FORMULA_VERSION = "rra008.concentration.v2"

METRIC_CURVE = "concentration_curve"
METRIC_DISTINCT_VALUES = "concentration_distinct_values"
METRIC_RANKED_VALUES = "concentration_ranked_values"
METRIC_TOP_DECILE_SHARE = "concentration_top_decile_share"
METRIC_TOP_QUARTILE_SHARE = "concentration_top_quartile_share"

REASON_AGGREGATE_UNAVAILABLE = "aggregate_unavailable"
REASON_DISTINCT_SET_UNCOMPUTABLE = "distinct_set_uncomputable"

# Which dimensions `RRA-008` names, in the order this family prefers them.
GOVERNED_DIMENSIONS = (SEMANTIC_PRODUCT, SEMANTIC_CATEGORY)

# The axis a concentration curve is stated over. `Series.granularity` names the unit
# of a bucket's position, and for this series that unit is rank rather than time.
GRANULARITY_RANK = "rank"

DECILE = 10
QUARTILE = 4

# Which unit each governed metric is stated in. A table rather than an argument,
# so a metric cannot be emitted in the wrong unit by a caller passing one, and so
# building a fact takes three arguments rather than five.
#
# The shares are `UNIT_RATIO` and therefore *fractions*: a top decile holding a
# fifth of revenue is `0.2000`, not `20.0000`. The ratio contract is already in
# use -- `gross_margin` stores a fraction and `narrative` multiplies every ratio
# by a hundred to render it -- so storing a percentage here would reach a reader
# as 2000%.
_UNITS = {
    METRIC_DISTINCT_VALUES: UNIT_COUNT,
    METRIC_RANKED_VALUES: UNIT_COUNT,
    METRIC_TOP_DECILE_SHARE: UNIT_RATIO,
    METRIC_TOP_QUARTILE_SHARE: UNIT_RATIO,
}


@dataclass(frozen=True, slots=True)
class _Source:
    """One measured curve, beside the dimension and caveats it came from.

    Carried as one value so building a fact takes three arguments rather than
    five, and so two facts of the same family cannot disagree about which
    dimension produced them. The curve here is never absent: `derive` refuses
    before constructing one.
    """

    dimension: str
    curve: ConcentrationCurve
    caveats: tuple[str, ...]

    def precision_for(self, metric: str) -> int:
        return 0 if _UNITS[metric] == UNIT_COUNT else RATIO_PRECISION


def derive(package: FactPackage) -> tuple[Fact, ...] | RefusedResult:
    """The four governed concentration facts, or one refusal explaining why not.

    The refusal distinguishes its two causes. No product or category dimension at
    all is `aggregate_unavailable`: there was nothing to rank. A dimension that
    exists while its curve does not is `distinct_set_uncomputable`: the set was
    there and no share over it can be stated, which is what a non-positive revenue
    total or a negative ranked total means.
    """
    found = _found(package)
    if found is None:
        return RefusedResult(
            metric=METRIC_DISTINCT_VALUES,
            reason=REASON_AGGREGATE_UNAVAILABLE,
        )
    dimension, entry = found
    curve = entry.comparison.curve
    if curve is None:
        return RefusedResult(
            metric=METRIC_DISTINCT_VALUES,
            reason=REASON_DISTINCT_SET_UNCOMPUTABLE,
        )
    source = _Source(
        dimension=dimension,
        curve=curve,
        caveats=_inherited(entry.caveats),
    )
    with localcontext(Context(prec=ARITHMETIC_PRECISION)):
        return _facts(source)


def curve_series(package: FactPackage) -> FactSeries | None:
    """The measured curve as one governed series, so a surface can draw it.

    **Why a series and not one fact per point, and not the raw aggregate.** A chart
    inherits the citation reconciliation of the figures it plots -- that is what
    `ChartSpec` exists for -- so a chart drawn from a retained aggregate would be a
    picture nothing reconciles. But four scalar facts are not a curve either: they
    are two counts beside two ratios, which share no axis and are refused as a chart
    for exactly that reason.

    A `FactSeries` is the shape already used for trends, and the bundle already turns
    one into a figure per bucket sharing a single citation. An earlier note claimed
    one figure per point would mint dozens of citation identifiers; that was wrong,
    and it is the reason this took a second look.

    Bucket labels are rank ordinals, never value labels. The display truncates
    precisely so a report cannot name every distinct value, and labelling the curve
    would hand a surface the list the truncation withheld.
    """
    found = _found(package)
    if found is None:
        return None
    dimension, entry = found
    curve = entry.comparison.curve
    if curve is None:
        return None
    fact_id, citation_id = _identity(METRIC_CURVE, (dimension,))
    return FactSeries(
        fact_id=fact_id,
        citation_id=citation_id,
        metric=METRIC_CURVE,
        measure=SEMANTIC_REVENUE,
        precision=RATIO_PRECISION,
        unit_kind=UNIT_RATIO,
        series=Series(
            granularity=GRANULARITY_RANK,
            buckets=tuple(
                Bucket(label=str(rank + 1), value=share, rows=1)
                for rank, share in enumerate(curve.shares)
            ),
        ),
        caveats=_inherited(entry.caveats),
        formula_version=CONCENTRATION_FORMULA_VERSION,
    )


def curve_for(package: FactPackage) -> ConcentrationCurve | None:
    """The measured curve a surface should draw, from the dimension this family chose.

    Public so the chart never picks a dimension of its own. Two surfaces choosing
    independently would draw a product curve beside a category count and reconcile
    perfectly, because reconciliation compares the text beside a chart.
    """
    found = _found(package)
    return None if found is None else found[1].comparison.curve


def dimension_of(fact: Fact) -> str | None:
    """Which dimension produced this fact, recovered from its identity.

    The dimension lives in the identity's hashed scope, so it is recomputed rather
    than read. Asking which of the two matches is also a proof that they differ,
    which is the property the stable-identifier requirement depends on.
    """
    return next(
        (
            dimension
            for dimension in GOVERNED_DIMENSIONS
            if fact_identity(
                metric=fact.metric,
                scope=(dimension,),
                formula_version=CONCENTRATION_FORMULA_VERSION,
            )[0]
            == fact.fact_id
        ),
        None,
    )


def _found(package: FactPackage) -> tuple[str, FactComparison] | None:
    """The first governed dimension the package published, with its comparison."""
    for dimension in GOVERNED_DIMENSIONS:
        entry = package.comparison(dimension)
        if entry is not None:
            return (dimension, entry)
    return None


def _inherited(caveats: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(caveat for caveat in caveats if caveat != CAVEAT_BUCKETS_TRUNCATED)


def _facts(source: _Source) -> tuple[Fact, ...]:
    return (
        _count(source, METRIC_DISTINCT_VALUES, source.curve.distinct_values),
        _count(source, METRIC_RANKED_VALUES, source.curve.ranked_values),
        _share(source, METRIC_TOP_DECILE_SHARE, DECILE),
        _share(source, METRIC_TOP_QUARTILE_SHARE, QUARTILE),
    )


def _share(source: _Source, metric: str, fraction: int) -> Fact:
    """The cumulative share held by the leading fraction of ranked values.

    Read off the curve at the last value in the fraction, because the curve is
    already cumulative. Recomputing the sum here would be a second derivation of
    the same number and a second thing to get wrong.
    """
    shares = source.curve.shares
    index = _leading(len(shares), fraction) - 1
    return _fact(source, metric, shares[index])


def _leading(ranked: int, fraction: int) -> int:
    """How many values the leading fraction covers, at least one.

    Rounded up: eight values divided into deciles is 0.8, and a top decile of no
    values reporting a nought share would be false rather than cautious.
    """
    return -(-ranked // fraction)


def _count(source: _Source, metric: str, value: int) -> Fact:
    return _fact(source, metric, Decimal(value))


def _identity(metric: str, scope: tuple[str, ...]) -> tuple[str, str]:
    return fact_identity(
        metric=metric,
        scope=scope,
        formula_version=CONCENTRATION_FORMULA_VERSION,
    )


def _fact(source: _Source, metric: str, value: Decimal) -> Fact:
    precision = source.precision_for(metric)
    fact_id, citation_id = _identity(metric, (source.dimension,))
    return Fact(
        fact_id=fact_id,
        citation_id=citation_id,
        metric=metric,
        value=str(value.quantize(Decimal(1).scaleb(-precision))),
        precision=precision,
        unit_kind=_UNITS[metric],
        inputs=(source.dimension, SEMANTIC_REVENUE),
        caveats=source.caveats,
        formula_version=CONCENTRATION_FORMULA_VERSION,
    )
