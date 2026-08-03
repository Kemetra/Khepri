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

**One period against one period, because no window length is governed.**
`RRA-008` says "a prior window of equal length" and never says what that length
is, and neither `RRA-004` nor the fact package supplies one. So the window is a
single period: period-over-period compares a period with the one before it, and
year-over-year with the same period a year earlier. That is what those two terms
mean, and it is the only reading that invents nothing.

An earlier revision took half the available history as the window, which was
wrong three ways. It invented a boundary; it made the answer depend on how much
*old* data happened to be present, so prepending history changed the reported
delta while recent data was identical; and at 37 settled months it produced an
18-month year-over-year comparison whose two windows overlapped by six months --
a period compared partly against itself.

**Both counterparts are found by label, never by position.** `period_label` keys
each bucket by the period it covers, so the preceding period and the period a year
earlier are both located by arithmetic on that label. Stepping back a fixed
number of buckets compares whatever happens to sit there: with January, March,
April and May in the series, April's predecessor by position is January. The
labels still look plausible and every sum is correct, which is what makes it
dangerous. A missing counterpart refuses rather than substituting a neighbour.

**The final period is excluded, because its completeness is unknowable here.**
`RRA-008` asks that both windows be truncated "to the same day count when the
current window is incomplete" -- comparing fifteen days of this month against a
whole prior month overstates the change. `FactSeries` carries one bucket per
period and no day count, so nothing here can tell a whole month from a partial
one. What *is* knowable is that a period with data on both sides of it is whole:
a later period proves it finished, an earlier one proves it was already running
when the export began. So the comparison runs over settled periods and leaves out
the period at each end.

Both ends, because either can be the period compared. An export beginning on 15
January holds seventeen days in its first bucket, and a year-over-year comparison
landing on it reads a whole January against a part of one: a series billing 3,100
every month reports +82% growth that is an artifact of where the export started.
An earlier revision excluded only the final period, which fixed the boundary the
report was pointed at and left the one it compared against.

That is deliberately not the specification's remedy, which needs a day count the
aggregate does not carry. It is the nearest derivable thing to the requirement's
intent, and the alternatives were worse: including an end bucket compares a
possibly-partial period against a whole one and says nothing, and refusing
whenever a period *might* be partial refuses always, because completeness is
equally undetectable in both directions. The cost is that the comparison lags by
one period and needs one period of run-up.

**The arithmetic runs in the package's own decimal context.** `build_fact_package`
computes under `ARITHMETIC_PRECISION`, and Python's default context is 28 digits.
A valid package can hold enough high-magnitude rows that a ratio against a small
prior period needs more than that: quantizing it then raises `InvalidOperation`
and takes the caller down, rather than returning a fact or a governed refusal.
Borrowing the same precision rather than choosing one keeps this module consistent
with the values it consumes -- if the bound on those values is ever wrong, it is
wrong in one place.

**No truncation caveat, because nothing here can truncate.** A one-period window
either has its counterpart or does not, so there is no shortened window to
disclose, and the day-count truncation `RRA-008` describes is not derivable at
all. A governed caveat with no reachable trigger is worse than an absent one --
it reads as a guarantee that something is being watched. Two `RRA-004` aggregates
would change this: a governed window length, and per-period completeness. Both
belong in the same amendment as the concentration curve and transaction
membership.

**One governed requirement is deferred, not met.** `RRA-008` requires the formula
version recorded as provenance. `COMPARISON_FORMULA_VERSION` is hashed into every
fact identity below, and hashing is not recording -- a serialized fact cannot
disclose which formula produced it, and `mode_of` cannot interpret a fact derived
under a superseded version. Recording it properly needs a field on `Fact`, which
is an `RRA-004` type this specification excludes changing, so it is a fifth item
for that same amendment rather than a change made here.

Until then the obligation falls on the caller: **whichever slice first serializes
these facts must record `COMPARISON_FORMULA_VERSION` alongside them.** Nothing
does today -- no section carries them and no bundle includes them -- so the gap
has no consumer yet, and it acquires one the moment section assembly lands. The
constant is public for that reason and for no other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Context, Decimal, localcontext

from khepri.rra.aggregates import GRANULARITY_MONTH, Bucket
from khepri.rra.facts import (
    ARITHMETIC_PRECISION,
    RATIO_PRECISION,
    REASON_INPUT_UNAVAILABLE,
    REASON_ZERO_DENOMINATOR,
    UNIT_MONETARY,
    UNIT_RATIO,
    Fact,
    FactPackage,
    FactSeries,
    RefusedResult,
    fact_identity,
)
from khepri.rra.mapping import SEMANTIC_REVENUE, SEMANTIC_TRANSACTION_DATE

# This family's own formula version, pinned separately from the package's.
#
# `fact_identity` defaults to the `RRA-004` formula version, which would name
# these facts under a version that says nothing about how they were derived. A
# correction to the comparison alone would then reuse the same fact and citation
# identifiers for a materially different number -- and a stored citation would
# point at an answer that had changed underneath it.
#
# This is not hypothetical for this module. Within one pull request the derivation
# moved from half-history windows to one-period windows and from a percentage to a
# fraction; under the package's version every one of those produced identical
# identifiers. `RRA-008` also requires the formula version recorded as provenance,
# and a version that belongs to a different specification does not record it.
COMPARISON_FORMULA_VERSION = "rra008.comparison.v1"

MODE_PERIOD_OVER_PERIOD = "period_over_period"
MODE_YEAR_OVER_YEAR = "year_over_year"
GOVERNED_MODES = (MODE_PERIOD_OVER_PERIOD, MODE_YEAR_OVER_YEAR)

METRIC_DELTA_ABSOLUTE = "revenue_delta_absolute"
METRIC_DELTA_PERCENT = "revenue_delta_percent"
# Every metric this family states. A whole-mode failure refuses all of them, so
# the list is named rather than implied by whichever one happened to be handy.
GOVERNED_METRICS = (METRIC_DELTA_ABSOLUTE, METRIC_DELTA_PERCENT)

REASON_PRIOR_WINDOW_ABSENT = "prior_window_absent"
REASON_NEGATIVE_BASE = "negative_base"

# Which cause speaks for the family when the two modes refuse for different
# reasons -- a period-over-period predecessor missing while the year-earlier
# counterpart exists but holds no revenue, say. No single reason is true of the
# family then, so one is chosen by a declared order rather than by whichever mode
# `GOVERNED_MODES` happens to name first.
#
# `required_input_unavailable` outranks because it is the more specific finding.
# `prior_window_absent` is the generic "there was nothing to compare against",
# and preferring it while a more specific cause sat recorded is the exact
# mislabel that made a family-level reason worth deriving in the first place.
#
# Reasons absent from this tuple sort last rather than raising: a metric-scoped
# refusal like `negative_base` never reaches here, because the mode that records
# one also produced an absolute delta and so did not refuse wholly.
_REASON_PRECEDENCE = (REASON_INPUT_UNAVAILABLE, REASON_PRIOR_WINDOW_ABSENT)

# What these facts are derived from, named in the governed mapping vocabulary.
# `Fact.inputs` elsewhere holds semantic measures -- the formula version is
# recorded separately by the package, and putting one here would mislabel a
# version string as source provenance and leave the facts declaring no measure.
# The date is an input as much as the revenue: it decides which period a row
# lands in, and therefore which two periods are compared.
_INPUTS = (SEMANTIC_TRANSACTION_DATE, SEMANTIC_REVENUE)

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
    """One settled period beside the period it is compared against.

    `inherited` carries the caveats of the series these buckets came from. A
    delta derived from a trend that excluded undated rows shares that
    limitation, and `RRA-008` requires every derived fact reconciled to its
    source aggregate -- a fact that dropped its source's caveat would be
    presented as covering rows the aggregate never saw.
    """

    current: Bucket
    prior: Bucket
    inherited: tuple[str, ...]

    def totals(self) -> tuple[Decimal | None, Decimal | None]:
        return (self.current.value, self.prior.value)


@dataclass(frozen=True, slots=True)
class _Derivation:
    """What every fact of one mode shares: mode, caveats, precision.

    Carried as one value so building a fact takes three arguments rather than
    five, and so two facts of the same mode cannot disagree about which mode
    produced them.
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
    """Both governed comparisons, or a refusal when neither can be made.

    The refusal carries the reason a mode actually gave rather than a reason
    recomputed here. A compared period holding only null revenue refuses with
    `required_input_unavailable`, and reporting `prior_window_absent` for it
    would explain the refusal wrongly -- the window was there and the measure was
    not.

    The two modes can refuse for *different* reasons, and one field cannot hold
    two. What this returns is therefore a summary and says so: it names the mode
    whose cause it carries. `refusals` is the complete record, and section
    assembly wanting per-mode causes must read that rather than this.
    """
    with localcontext(Context(prec=ARITHMETIC_PRECISION)):
        outcomes = _outcomes(package)
    facts = tuple(fact for outcome in outcomes for fact in outcome.facts)
    if facts:
        return facts
    return _family_refusal(outcomes, package)


def _family_refusal(
    outcomes: tuple[_Outcome, ...],
    package: FactPackage,
) -> RefusedResult:
    """The one refusal that stands for the family, chosen rather than stumbled on.

    Returning a recorded refusal whole, rather than rebuilding one, is what keeps
    the mode in the metric: `revenue_delta_absolute.year_over_year` explains one
    governed comparison and does not claim to explain the other. The previous
    version rebuilt it with a bare metric, so a reason true of one mode was
    presented as the family's.
    """
    recorded = tuple(
        refusal for outcome in outcomes for refusal in outcome.refusals
    )
    if not recorded:
        return RefusedResult(
            metric=METRIC_DELTA_ABSOLUTE,
            reason=_absent_reason(package),
        )
    return min(recorded, key=_precedence)


def _precedence(refusal: RefusedResult) -> tuple[int, str]:
    """Rank a refusal so the summary is a decision and not an accident.

    This used to take whichever refusal `GOVERNED_MODES` happened to list first,
    which meant period-over-period's cause always won and year-over-year's was
    dropped unseen. The metric breaks ties so the choice is total: two modes
    refusing alike now yield the same summary whichever order they were derived.
    """
    ranked = (
        _REASON_PRECEDENCE.index(refusal.reason)
        if refusal.reason in _REASON_PRECEDENCE
        else len(_REASON_PRECEDENCE)
    )
    return (ranked, refusal.metric)


def refusals(package: FactPackage) -> tuple[RefusedResult, ...]:
    """Everything that could not be stated, beside whatever could.

    A report whose year-over-year coverage is short still carries a
    period-over-period comparison, and a percentage refused for a non-positive
    base still leaves its absolute delta standing. Each of those is recorded:
    absence is never the disclosure, so a consumer can tell a governed refusal
    from a metric that was quietly left out.
    """
    with localcontext(Context(prec=ARITHMETIC_PRECISION)):
        outcomes = _outcomes(package)
    return tuple(
        refusal for outcome in outcomes for refusal in outcome.refusals
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
            if fact_identity(
                metric=fact.metric,
                scope=(mode,),
                formula_version=COMPARISON_FORMULA_VERSION,
            )[0]
            == fact.fact_id
        ),
        None,
    )


def _outcomes(package: FactPackage) -> tuple[_Outcome, ...]:
    return tuple(_derive_mode(package, mode) for mode in GOVERNED_MODES)


def _derive_mode(package: FactPackage, mode: str) -> _Outcome:
    window = _window_for(package, mode)
    if window is None:
        return _refused(mode, _absent_reason(package))
    return _compare(window, package, mode)


def _compare(window: _Window, package: FactPackage, mode: str) -> _Outcome:
    current, prior = window.totals()
    if current is None or prior is None:
        return _refused(mode, REASON_INPUT_UNAVAILABLE)
    derivation = _Derivation(
        mode=mode,
        caveats=window.inherited,
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


def _refused(mode: str, reason: str) -> _Outcome:
    """A mode that could state nothing refuses every metric it would have stated.

    Recording only the absolute delta would leave the percentage indistinguishable
    from a metric quietly left out, which is the distinction `refusals` exists to
    preserve. The invalid-base path already records a percentage refusal beside a
    surviving absolute; a whole-mode failure has no survivor and owes two.
    """
    return _Outcome(
        facts=(),
        refusals=tuple(
            RefusedResult(metric=_scoped_metric(metric, mode), reason=reason)
            for metric in GOVERNED_METRICS
        ),
    )


def _window_for(package: FactPackage, mode: str) -> _Window | None:
    """The last settled period, beside the period this mode compares it against.

    The counterpart is looked up by label. A missing one refuses rather than
    substituting whichever bucket happens to be adjacent in the series.
    """
    trend = package.trend()
    if trend is None:
        return None
    buckets = _settled(trend.series.buckets)
    if not buckets:
        return None
    return _against_counterpart(buckets, trend, mode)


def _against_counterpart(
    buckets: tuple[Bucket, ...],
    trend: FactSeries,
    mode: str,
) -> _Window | None:
    current = buckets[-1]
    label = _counterpart_label(current.label, trend.series.granularity, mode)
    prior = {bucket.label: bucket for bucket in buckets}.get(label)
    if prior is None:
        return None
    return _Window(current=current, prior=prior, inherited=trend.caveats)


def _settled(buckets: tuple[Bucket, ...]) -> tuple[Bucket, ...]:
    """Every period known to be whole, which is every one but the two on the ends.

    A period is whole when data exists on both sides of it: a later period proves
    it finished, and an earlier period proves it was already running when the
    export began. The first and last periods each have one open side, and nothing
    in the series says whether that side was cut.

    Both ends matter because either can be the one compared. An export beginning
    on 15 January holds seventeen days in its first bucket; a year-over-year
    comparison landing on it reads a full January against a part of one and
    reports growth that is an artifact of the export window -- 3,100 a month
    throughout becomes +82% because the first January is short. That is the same
    failure the last period was excluded to prevent, and it was left standing at
    the other end.
    """
    return buckets[1:-1]


def _counterpart_label(label: str, granularity: str, mode: str) -> str | None:
    if mode == MODE_PERIOD_OVER_PERIOD:
        return _preceding_label(label, granularity)
    return _year_earlier_label(label, granularity)


def _preceding_label(label: str, granularity: str) -> str | None:
    """The period immediately before this one, at its own granularity."""
    if granularity == GRANULARITY_MONTH:
        return _month_label(label, months_earlier=1)
    return _day_label(label, days_earlier=1)


def _year_earlier_label(label: str, granularity: str) -> str | None:
    """The same period one year earlier.

    A year is expressed by decrementing the year field rather than subtracting a
    number of periods, because twelve months is a year and 365 days is not always
    one. The month form has no day to be invalid; the day form is parsed, so 29
    February simply finds no counterpart and refuses.
    """
    if granularity == GRANULARITY_MONTH:
        return _month_label(label, months_earlier=12)
    return _day_label(label, days_earlier=None)


def _month_label(label: str, *, months_earlier: int) -> str | None:
    parts = label.split("-")
    if len(parts) != 2:
        return None
    index = int(parts[0]) * 12 + int(parts[1]) - 1 - months_earlier
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def _day_label(label: str, *, days_earlier: int | None) -> str | None:
    """One day earlier, or the same day a year earlier when `days_earlier` is None."""
    try:
        moment = date.fromisoformat(label)
    except ValueError:
        return None
    try:
        if days_earlier is not None:
            return (moment - timedelta(days=days_earlier)).isoformat()
        return moment.replace(year=moment.year - 1).isoformat()
    except (ValueError, OverflowError):
        # Two ways a counterpart can fail to be a date, and both refuse rather
        # than reach for the nearest one. 29 February has no counterpart in a
        # non-leap year -- `ValueError`. The day before `0001-01-01` is off the
        # end of the calendar -- `OverflowError`, which is not a `ValueError`,
        # so catching only the latter let it escape both entry points as an
        # abort instead of a governed refusal.
        return None


def _absent_reason(package: FactPackage) -> str:
    if package.trend() is None:
        return REASON_INPUT_UNAVAILABLE
    return REASON_PRIOR_WINDOW_ABSENT


def _fact(derivation: _Derivation, metric: str, value: Decimal) -> Fact:
    unit_kind = _UNITS[metric]
    precision = derivation.precision_for(unit_kind)
    fact_id, citation_id = fact_identity(
        metric=metric,
        scope=(derivation.mode,),
        formula_version=COMPARISON_FORMULA_VERSION,
    )
    return Fact(
        fact_id=fact_id,
        citation_id=citation_id,
        metric=metric,
        value=str(value.quantize(Decimal(1).scaleb(-precision))),
        precision=precision,
        unit_kind=unit_kind,
        inputs=_INPUTS,
        caveats=derivation.caveats,
    )


def _scoped_metric(metric: str, mode: str) -> str:
    return f"{metric}.{mode}"
