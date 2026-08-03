"""Period comparison: two governed modes over one governed trend.

**`RRA-008` requires two comparisons, not one.** Its wording is "compare a
current window to a prior window of equal length, for period-over-period **and**
year-over-year." A single unnamed current/prior pair satisfies neither fully: it
produces one comparison and leaves a reader unable to tell which window it
compared.

**The modes refuse independently.** A dataset spanning eight months has a prior
period and no prior year at all. `RRA-008` refuses "the affected comparison, and
not the report", so one mode refusing must leave the other standing: `derive`
returns a `RefusedResult` only when *both* refuse, and `refusals` carries every
refusal beside whatever facts survived -- per mode, and per metric within a mode.

**A window is a set of matched pairs, not two independent runs.** Each current
period is paired with the one it is compared against, and a period whose
counterpart is missing takes its pair out of the window rather than shifting the
alignment. Trimming the two sides independently to a common length is how a
year-over-year comparison silently ends up measuring thirteen months against
twelve -- the labels still look plausible and every arithmetic step is correct.

**The prior-year period is found by label, never by offset.** `period_label`
gives `YYYY-MM` at month granularity, so a year earlier is that label with its
year decremented. Stepping back a fixed twelve buckets would compare the wrong
months the moment a month of coverage is missing, and a comparison that quietly
changes which period it means is worse than one that refuses.

**The final period is excluded, because its completeness is unknowable here.**
`RRA-008` asks that both windows be truncated "to the same day count when the
current window is incomplete" -- comparing fifteen days of this month against a
whole prior month overstates the change. `FactSeries` carries one bucket per
period and no day count, so nothing here can tell a complete final month from a
partial one. What *is* knowable is that every period with a later period after it
finished, because data exists beyond it. So the comparison runs over settled
periods and leaves the last one out.

That is deliberately not the specification's remedy, which needs a day count the
aggregate does not carry. It is the nearest derivable thing to the requirement's
intent, and the alternatives were worse: including the final bucket compares a
possibly-partial period against a whole one and says nothing, and refusing
whenever a final period *might* be partial refuses always, because completeness
is equally undetectable in both directions. The cost is that the comparison lags
by one period. An `RRA-004` aggregate carrying period completeness would remove
the need for this, and belongs in the same amendment as the concentration curve.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from khepri.rra.aggregates import GRANULARITY_MONTH, Bucket
from khepri.rra.facts import (
    FORMULA_VERSION,
    RATIO_PRECISION,
    REASON_INPUT_UNAVAILABLE,
    REASON_ZERO_DENOMINATOR,
    UNIT_MONETARY,
    UNIT_RATIO,
    Fact,
    FactPackage,
    RefusedResult,
    fact_identity,
)

MODE_PERIOD_OVER_PERIOD = "period_over_period"
MODE_YEAR_OVER_YEAR = "year_over_year"
GOVERNED_MODES = (MODE_PERIOD_OVER_PERIOD, MODE_YEAR_OVER_YEAR)

METRIC_DELTA_ABSOLUTE = "revenue_delta_absolute"
METRIC_DELTA_PERCENT = "revenue_delta_percent"

CAVEAT_WINDOW_TRUNCATED = "window_truncated"
REASON_PRIOR_WINDOW_ABSENT = "prior_window_absent"
REASON_NEGATIVE_BASE = "negative_base"

# Which unit each governed metric is stated in. A table rather than an argument,
# so a metric cannot be emitted in the wrong unit by a caller passing one.
#
# The percentage delta is a `UNIT_RATIO` and therefore a *fraction*: a rise from
# 100 to 150 is `0.5000`, not `50.0000`. The ratio contract is already in use --
# `gross_margin` stores a fraction, and `narrative` multiplies every ratio by a
# hundred to render it -- so storing a percentage here would reach a reader as
# 5000%.
_UNITS = {
    METRIC_DELTA_ABSOLUTE: UNIT_MONETARY,
    METRIC_DELTA_PERCENT: UNIT_RATIO,
}


@dataclass(frozen=True, slots=True)
class _Window:
    """Matched period pairs, current beside the period each is compared against.

    Pairs rather than two runs, so the alignment cannot drift. `truncated` says a
    current period was dropped for want of its counterpart, which is a shorter
    window and not a rescaled one.
    """

    pairs: tuple[tuple[Bucket, Bucket], ...]
    truncated: bool

    def totals(self) -> tuple[Decimal | None, Decimal | None]:
        return (
            _total(pair[0] for pair in self.pairs),
            _total(pair[1] for pair in self.pairs),
        )


@dataclass(frozen=True, slots=True)
class _Derivation:
    """What every fact of one mode shares: its mode, its caveats, its precision.

    Carried as one value so building a fact takes three arguments rather than
    six, and so two facts of the same mode cannot disagree about which mode they
    came from or whether their window was shortened.
    """

    mode: str
    caveats: tuple[str, ...]
    monetary_precision: int

    def precision_for(self, unit_kind: str) -> int:
        if unit_kind == UNIT_MONETARY:
            return self.monetary_precision
        return RATIO_PRECISION


@dataclass(frozen=True, slots=True)
class _Outcome:
    """One mode's results: what it derived, and what it refused and why."""

    facts: tuple[Fact, ...]
    refusals: tuple[RefusedResult, ...]


def derive(package: FactPackage) -> tuple[Fact, ...] | RefusedResult:
    """Both governed comparisons, or a refusal when neither can be made."""
    facts = tuple(fact for outcome in _outcomes(package) for fact in outcome.facts)
    if facts:
        return facts
    return RefusedResult(
        metric=METRIC_DELTA_ABSOLUTE,
        reason=_absent_reason(package),
    )


def refusals(package: FactPackage) -> tuple[RefusedResult, ...]:
    """Everything that could not be stated, beside whatever could.

    A report whose year-over-year coverage is short still carries a
    period-over-period comparison, and a percentage refused for a non-positive
    base still leaves its absolute delta standing. Each of those is recorded:
    absence is never the disclosure, so a consumer can tell a governed refusal
    from a metric that was quietly left out.
    """
    return tuple(
        refusal for outcome in _outcomes(package) for refusal in outcome.refusals
    )


def mode_of(fact: Fact) -> str | None:
    """Which governed mode produced this fact, recovered from its identity.

    The mode lives in the metric's `scope`, which the identity derivation hashes,
    so it is not readable off the fact -- it is recomputed. Asking which of the
    two identities matches is also a proof that they differ, which is the
    property `RRA-008`'s stable-identifier requirement depends on.
    """
    return next(
        (
            mode
            for mode in GOVERNED_MODES
            if fact_identity(metric=fact.metric, scope=(mode,))[0] == fact.fact_id
        ),
        None,
    )


def _outcomes(package: FactPackage) -> tuple[_Outcome, ...]:
    return tuple(_derive_mode(package, mode) for mode in GOVERNED_MODES)


def _derive_mode(package: FactPackage, mode: str) -> _Outcome:
    window = _window_for(package, mode)
    if window is None:
        return _refused(mode, METRIC_DELTA_ABSOLUTE, _absent_reason(package))
    return _compare(window, package, mode)


def _compare(window: _Window, package: FactPackage, mode: str) -> _Outcome:
    current, prior = window.totals()
    if current is None or prior is None:
        return _refused(mode, METRIC_DELTA_ABSOLUTE, REASON_INPUT_UNAVAILABLE)
    derivation = _Derivation(
        mode=mode,
        caveats=(CAVEAT_WINDOW_TRUNCATED,) if window.truncated else (),
        monetary_precision=package.monetary_precision,
    )
    return _with_percentage(derivation, current - prior, prior)


def _with_percentage(
    derivation: _Derivation,
    change: Decimal,
    base: Decimal,
) -> _Outcome:
    """The absolute delta always; the percentage only against a positive base.

    A percentage of zero is undefined, and of a negative base it misleads -- a
    shrinking loss reads as growth. Either way the refusal is recorded rather
    than the metric simply being absent.
    """
    absolute = _fact(derivation, METRIC_DELTA_ABSOLUTE, change)
    if base > 0:
        return _Outcome(
            facts=(absolute, _fact(derivation, METRIC_DELTA_PERCENT, change / base)),
            refusals=(),
        )
    reason = REASON_ZERO_DENOMINATOR if base == 0 else REASON_NEGATIVE_BASE
    return _Outcome(
        facts=(absolute,),
        refusals=(
            RefusedResult(
                metric=_scoped_metric(METRIC_DELTA_PERCENT, derivation.mode),
                reason=reason,
            ),
        ),
    )


def _refused(mode: str, metric: str, reason: str) -> _Outcome:
    return _Outcome(
        facts=(),
        refusals=(
            RefusedResult(metric=_scoped_metric(metric, mode), reason=reason),
        ),
    )


def _window_for(package: FactPackage, mode: str) -> _Window | None:
    trend = package.trend()
    if trend is None:
        return None
    buckets = _settled(trend.series.buckets)
    length = len(buckets) // 2
    if length < 1:
        return None
    current = buckets[-length:]
    if mode == MODE_PERIOD_OVER_PERIOD:
        return _paired(current, buckets[-2 * length : -length])
    return _year_earlier(current, buckets, trend.series.granularity)


def _settled(buckets: tuple[Bucket, ...]) -> tuple[Bucket, ...]:
    """Every period known to have finished, which is every one but the last.

    A period with a later period after it is complete, because data exists beyond
    it. The final period may have been cut off mid-way by wherever the export
    ended, and nothing in the series says which -- so it is left out rather than
    compared against a whole one.
    """
    return buckets[:-1]


def _paired(
    current: tuple[Bucket, ...],
    prior: tuple[Bucket, ...],
) -> _Window | None:
    """Pair the two runs positionally, oldest aligned with oldest."""
    if len(prior) != len(current):
        return None
    return _Window(pairs=tuple(zip(current, prior, strict=True)), truncated=False)


def _year_earlier(
    current: tuple[Bucket, ...],
    buckets: tuple[Bucket, ...],
    granularity: str,
) -> _Window | None:
    """Pair each current period with the same period one year before it.

    A current period whose counterpart is missing is dropped *with* its pair, so
    every remaining pair is exactly a year apart. Compressing the prior side and
    trimming the current side to match would keep the count equal and the
    alignment wrong.
    """
    known = {bucket.label: bucket for bucket in buckets}
    pairs = tuple(
        (bucket, known[label])
        for bucket in current
        if (label := _label_year_earlier(bucket.label, granularity)) in known
    )
    if not pairs:
        return None
    return _Window(pairs=pairs, truncated=len(pairs) < len(current))


def _label_year_earlier(label: str, granularity: str) -> str | None:
    """The same period one year earlier, in the label form its granularity uses.

    Decrementing the year text rather than doing date arithmetic, because the
    label *is* the governed identity of a period -- `build_series` keys its
    buckets by it -- and reconstructing a date to re-derive a label would be a
    second way of naming the same thing.
    """
    year, _, rest = label.partition("-")
    if not rest:
        return None
    if granularity == GRANULARITY_MONTH and len(rest) != 2:
        return None
    return f"{int(year) - 1:04d}-{rest}"


def _absent_reason(package: FactPackage) -> str:
    if package.trend() is None:
        return REASON_INPUT_UNAVAILABLE
    return REASON_PRIOR_WINDOW_ABSENT


def _fact(derivation: _Derivation, metric: str, value: Decimal) -> Fact:
    unit_kind = _UNITS[metric]
    precision = derivation.precision_for(unit_kind)
    fact_id, citation_id = fact_identity(metric=metric, scope=(derivation.mode,))
    return Fact(
        fact_id=fact_id,
        citation_id=citation_id,
        metric=metric,
        value=str(value.quantize(Decimal(1).scaleb(-precision))),
        precision=precision,
        unit_kind=unit_kind,
        inputs=(FORMULA_VERSION,),
        caveats=derivation.caveats,
    )


def _scoped_metric(metric: str, mode: str) -> str:
    return f"{metric}.{mode}"


def _total(buckets) -> Decimal | None:
    present = [bucket.value for bucket in buckets if bucket.value is not None]
    return sum(present, Decimal(0)) if present else None
