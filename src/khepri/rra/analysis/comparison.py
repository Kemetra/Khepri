"""Period comparison: two governed modes over one governed trend.

**`RRA-008` requires two comparisons, not one.** Its wording is "compare a
current window to a prior window of equal length, for period-over-period **and**
year-over-year." A single unnamed current/prior pair satisfies neither fully: it
produces one comparison and leaves a reader unable to tell which window it
compared.

**The modes refuse independently.** A dataset spanning eight months has a prior
period and no prior year at all. `RRA-008` refuses "the affected comparison, and
not the report", so one mode refusing must leave the other standing: `derive`
returns a `RefusedResult` only when *both* refuse, and `refusals` carries a
single-mode refusal beside the other mode's facts.

**The prior-year window is found by label, never by offset.** `period_label`
gives `YYYY-MM` at month granularity, so the window one year earlier is located
by decrementing the year in each label and keeping the buckets that exist.
Stepping back a fixed twelve buckets would silently compare the wrong months the
moment a month of coverage is missing -- and a comparison that quietly changes
which period it means is worse than one that refuses.

**One caveat this module cannot emit, and why it is not simply missing.**
`RRA-008` also asks that both windows be truncated "to the same day count when
the current window is incomplete" -- comparing fifteen days of this month against
a whole prior month overstates the change. That is not derivable here. The
governed trend carries one bucket per period, and at month granularity the days
inside a bucket are already summed away, so nothing in `FactSeries` says whether
the most recent month is complete. This is the same shape of gap as
concentration's: an aggregate that discarded the detail a requirement needs.
`window_truncated` below is therefore about a *shorter window*, which is real and
reachable -- a prior-year window missing months to a coverage gap -- and not about
a partial final period, which needs an `RRA-004` aggregate that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from khepri.rra.aggregates import GRANULARITY_MONTH, Bucket
from khepri.rra.facts import (
    FORMULA_VERSION,
    RATIO_PRECISION,
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
GOVERNED_METRICS = (METRIC_DELTA_ABSOLUTE, METRIC_DELTA_PERCENT)

CAVEAT_WINDOW_TRUNCATED = "window_truncated"
REASON_PRIOR_WINDOW_ABSENT = "prior_window_absent"
REASON_TREND_UNAVAILABLE = "required_input_unavailable"

# A percentage of one hundred, as an exact Decimal. `RRA-008` requires the
# arithmetic stay exact, so the scale factor is not a float.
_PERCENT = Decimal(100)


@dataclass(frozen=True, slots=True)
class _Window:
    """A current run of buckets and the prior run it is compared against.

    Equal length by construction: whichever side has fewer buckets decides the
    length, and `truncated` records that it cost the other side some. Comparing
    unequal windows would report a change that is partly a change in how much
    period each side covers.
    """

    current: tuple[Bucket, ...]
    prior: tuple[Bucket, ...]
    truncated: bool


# Which unit each governed metric is stated in. A table rather than an argument,
# so a metric cannot be emitted in the wrong unit by a caller passing one.
_UNITS = {
    METRIC_DELTA_ABSOLUTE: UNIT_MONETARY,
    METRIC_DELTA_PERCENT: UNIT_RATIO,
}


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


def derive(package: FactPackage) -> tuple[Fact, ...] | RefusedResult:
    """Both governed comparisons, or a refusal when neither can be made."""
    facts = tuple(
        fact for mode in GOVERNED_MODES for fact in _mode_facts(package, mode)
    )
    if facts:
        return facts
    return RefusedResult(
        metric=METRIC_DELTA_ABSOLUTE,
        reason=_absent_reason(package),
    )


def refusals(package: FactPackage) -> tuple[RefusedResult, ...]:
    """The modes that could not be compared, when at least one other could.

    Beside the facts rather than instead of them. A report whose year-over-year
    coverage is short still carries a period-over-period comparison, and a reader
    is told which one is missing and why.
    """
    return tuple(
        RefusedResult(metric=_scoped_metric(METRIC_DELTA_ABSOLUTE, mode), reason=reason)
        for mode in GOVERNED_MODES
        if (reason := _mode_refusal(package, mode)) is not None
    )


def mode_of(fact: Fact) -> str | None:
    """Which governed mode produced this fact, recovered from its identity.

    The mode lives in the metric's `scope`, which `_identity` hashes, so it is
    not readable off the fact -- it is recomputed. Asking which of the two
    identities matches is also a proof that they differ, which is the property
    `RRA-008`'s stable-identifier requirement depends on.
    """
    return next(
        (
            mode
            for mode in GOVERNED_MODES
            if fact_identity(metric=fact.metric, scope=(mode,))[0] == fact.fact_id
        ),
        None,
    )


def _mode_facts(package: FactPackage, mode: str) -> tuple[Fact, ...]:
    window = _window_for(package, mode)
    if window is None:
        return ()
    return _facts_for(
        window,
        _Derivation(
            mode=mode,
            caveats=(CAVEAT_WINDOW_TRUNCATED,) if window.truncated else (),
            monetary_precision=package.monetary_precision,
        ),
    )


def _facts_for(window: _Window, derivation: _Derivation) -> tuple[Fact, ...]:
    current = _total(window.current)
    prior = _total(window.prior)
    if current is None or prior is None:
        return ()
    absolute = _fact(derivation, METRIC_DELTA_ABSOLUTE, current - prior)
    if not _percentage_is_defined(prior):
        # The absolute delta always, the percentage only against a positive
        # base. A percentage of zero is undefined, and of a negative base it
        # misleads: a shrinking loss reads as growth.
        return (absolute,)
    return (
        absolute,
        _fact(derivation, METRIC_DELTA_PERCENT, (current - prior) / prior * _PERCENT),
    )


def _window_for(package: FactPackage, mode: str) -> _Window | None:
    trend = package.trend()
    if trend is None:
        return None
    buckets = trend.series.buckets
    length = len(buckets) // 2
    if length < 1:
        return None
    current = buckets[-length:]
    if mode == MODE_PERIOD_OVER_PERIOD:
        return _matched(current, buckets[-2 * length : -length])
    return _matched(current, _year_earlier(current, buckets, trend.series.granularity))


def _matched(
    current: tuple[Bucket, ...],
    prior: tuple[Bucket, ...],
) -> _Window | None:
    """Cut both runs to the shorter, so the two windows cover equal period."""
    if not prior:
        return None
    length = min(len(current), len(prior))
    return _Window(
        current=current[-length:],
        prior=prior[-length:],
        truncated=length < len(current),
    )


def _year_earlier(
    current: tuple[Bucket, ...],
    buckets: tuple[Bucket, ...],
    granularity: str,
) -> tuple[Bucket, ...]:
    """The buckets one year before each of `current`, by label and not by offset.

    Only the ones that exist. A missing month makes this window shorter, which
    `_matched` turns into a like-for-like truncation and a caveat, rather than
    letting a fixed step land on the wrong period.
    """
    known = {bucket.label: bucket for bucket in buckets}
    wanted = (_label_year_earlier(bucket.label, granularity) for bucket in current)
    return tuple(known[label] for label in wanted if label in known)


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


def _mode_refusal(package: FactPackage, mode: str) -> str | None:
    if _mode_facts(package, mode):
        return None
    return _absent_reason(package)


def _absent_reason(package: FactPackage) -> str:
    if package.trend() is None:
        return REASON_TREND_UNAVAILABLE
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


def _total(buckets: tuple[Bucket, ...]) -> Decimal | None:
    present = [bucket.value for bucket in buckets if bucket.value is not None]
    return sum(present, Decimal(0)) if present else None


def _percentage_is_defined(base: Decimal | None) -> bool:
    if base is None:
        return False
    return base > 0
