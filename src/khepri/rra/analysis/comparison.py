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

from dataclasses import dataclass, replace
from decimal import Context, Decimal, localcontext

from khepri.rra.aggregates import Bucket
from khepri.rra.analysis.windows import (
    GOVERNED_MODES,
    MODE_PERIOD_OVER_PERIOD,
    MODE_YEAR_OVER_YEAR,
    compared_labels,
)
from khepri.rra.coverage_signature import COVERAGE_MODE_PREFIX
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
COMPARISON_FORMULA_VERSION = "rra008.comparison.v2"

# The modes and the window rule now live in `windows.py`, shared with the growth
# family. Re-exported here because both were this module's public names before the
# extraction, and a stable import path costs nothing.
__all__ = [
    "COMPARISON_FORMULA_VERSION",
    "GOVERNED_MODES",
    "MODE_PERIOD_OVER_PERIOD",
    "MODE_YEAR_OVER_YEAR",
    "derive",
    "mode_of",
    "refusals",
]

METRIC_DELTA_ABSOLUTE = "revenue_delta_absolute"
METRIC_DELTA_PERCENT = "revenue_delta_percent"
# Every metric this family states. A whole-mode failure refuses all of them, so
# the list is named rather than implied by whichever one happened to be handy.
GOVERNED_METRICS = (METRIC_DELTA_ABSOLUTE, METRIC_DELTA_PERCENT)

REASON_PRIOR_WINDOW_ABSENT = "prior_window_absent"
REASON_NEGATIVE_BASE = "negative_base"
#: `RRA-008`: "Sparse, non-contiguous, count-equal, gap-containing,
#: scope-mismatched, store-mismatched, or filter-mismatched structures refuse.
#: Equal counts, observed rows, date bounds, and generated date spines never
#: prove alignment."
REASON_COVERAGE_INCOMPATIBLE = "coverage_structurally_incompatible"

#: `RRA-008` admits an incomplete current month against the prior period's
#: day-`1..k` projection, and requires the result to carry "the bilingual
#: partial-window caveat required by `RRA-009`".
CAVEAT_PARTIAL_WINDOW = "comparison_partial_window"

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
_REASON_PRECEDENCE = (
    REASON_INPUT_UNAVAILABLE,
    REASON_COVERAGE_INCOMPATIBLE,
    REASON_PRIOR_WINDOW_ABSENT,
)

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


def accepted_window(package: FactPackage, mode: str = MODE_PERIOD_OVER_PERIOD):
    """The window this family accepted for `mode`, or `None` if it accepted none.

    **The seam `RRA-008` requires of growth**: "Growth consumes the exact PoP
    window selected by period comparison and may not select another", over "the
    structural coverage compatibility already accepted by comparison".

    Growth used to call `windows.compared_labels` itself and land on the same
    two labels, which looked equivalent and is not: that shares the *rule*, not
    the *acceptance*. Once this family refuses a window on coverage grounds --
    a sparse structure, a scope mismatch, an unproven prefix -- the rule still
    returns those labels, and a growth family re-deriving them would decompose
    a window comparison declined to state. The gap is invisible while the two
    agree and silent when they stop.

    Returned as the window rather than the labels, because the labels are what
    growth could already compute. What it could not compute is that comparison
    accepted them.
    """
    return _window_for(package, mode)


def window_refusal(package: FactPackage, mode: str = MODE_PERIOD_OVER_PERIOD) -> str:
    """Why this family accepted no window for `mode`.

    The companion to `accepted_window`, for the same reason that exists: growth
    consumes this family's *acceptance*, so it must also report this family's
    *cause* rather than assume the window was simply absent. Four causes reach
    one `None`, and a customer told the wrong one is sent to a fix that cannot
    work -- re-exporting history does not make two windows comparable.
    """
    return _absent_reason(package, mode)


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
        return _refused(mode, _absent_reason(package, mode))
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

    Which two periods those are is `windows.compared_labels`, shared with the
    growth family so the delta stated here is the delta decomposed there.
    """
    trend = package.trend()
    if trend is None:
        return None
    labels = compared_labels(trend.series, mode)
    if labels is None:
        return None
    if not _structurally_compatible(package, labels):
        return None
    window = _against_counterpart(labels, trend)
    if window is None:
        return None
    if not _is_partial(package):
        return window
    # `RRA-008`: a partial-prefix comparison "carries the bilingual
    # partial-window caveat required by `RRA-009`". Carried on the window so
    # every fact derived from it inherits the disclosure, rather than being
    # attached per metric where one could be missed.
    return replace(window, inherited=(*window.inherited, CAVEAT_PARTIAL_WINDOW))


def _structurally_compatible(package: FactPackage, labels: tuple[str, str]) -> bool:
    """Whether the package proves these two windows comparable.

    `RRA-008`: "Complete full calendar periods are structurally compatible when
    they have the same governed aggregate scope or complete admitted store set
    and the same event-kind and status filters. Natural calendar length
    differences, including 28-, 29-, 30-, and 31-day months, do not make
    otherwise complete full periods incompatible."

    Compared on the **retained structural signatures**, never on observed data:
    the same specification says "Equal counts, observed rows, date bounds, and
    generated date spines never prove alignment", and those are precisely what a
    data-derived check would consult. `rra004.package.v3` retains signatures
    that exclude absolute dates and every measure value for this reason -- so a
    28-day February and a 31-day March of identical shape compare equal, which
    is the natural-length rule falling out of the representation rather than
    being special-cased.

    **A package that retains no signature is not thereby compatible.** It is
    unproven, and `RRA-008` refuses completeness-dependent comparison "without
    an authoritative valid manifest". Returning `True` here would restore the
    inference the signature exists to replace.
    """
    signatures = package.coverage_signatures
    if not signatures:
        return False
    # **The scope set, not one scope.** `RRA-008` admits "the same governed
    # aggregate scope *or* complete admitted store set", and a roster is the
    # second form: one scope expressed as several stores, attested together.
    # Requiring a single scope string refused every multi-store export -- an
    # ordinary retail case, not an edge one -- because a per-store manifest
    # emits one signature per store.
    #
    # What must agree is the *shape* every signature shares: each covers the
    # same ordinals over the same window under the same filters. Two windows
    # covered by different rosters, or by rosters covering different days,
    # therefore still refuse -- which is the rule this exists to enforce.
    filters = {
        (signature.event_kinds, signature.statuses) for signature in signatures
    }
    coverage = {
        (signature.mode, signature.covered_ordinals, signature.window_days)
        for signature in signatures
    }
    return len(filters) == 1 and len(coverage) == 1


def _is_partial(package: FactPackage) -> bool:
    """Whether the accepted coverage is a prefix rather than a whole period.

    `RRA-008` admits "an incomplete current month" against the prior period's
    day-`1..k` projection, and requires the result to say so. The signature
    already records which shape was attested, so this reads the recorded
    structure rather than re-deciding it from dates -- the same division that
    keeps `_structurally_compatible` off the data.
    """
    return any(
        signature.mode == COVERAGE_MODE_PREFIX
        for signature in package.coverage_signatures
    )


def _against_counterpart(
    labels: tuple[str, str],
    trend: FactSeries,
) -> _Window | None:
    current, prior = labels
    buckets = {bucket.label: bucket for bucket in trend.series.buckets}
    return _Window(
        current=buckets[current],
        prior=buckets[prior],
        inherited=trend.caveats,
    )


def _absent_reason(package: FactPackage, mode: str) -> str:
    """Which of the causes behind `_window_for`'s `None` actually happened.

    Four reach that one `return`, and they are different findings a reader acts
    on differently. Reported in the order the window is built, so each cause is
    only considered once the ones before it have been excluded:

    - No trend at all: `required_input_unavailable`.
    - A trend, but the manifest does not prove the two windows structurally
      comparable: `coverage_structurally_incompatible`. Saying
      `prior_window_absent` here tells a customer their file covers a single
      period when it covers several, and sends them to re-export more history --
      which produces the same refusal again.
    - Otherwise no comparable pair exists at all: `prior_window_absent`.
    """
    trend = package.trend()
    if trend is None:
        return REASON_INPUT_UNAVAILABLE
    labels = compared_labels(trend.series, mode)
    if labels is not None and not _structurally_compatible(package, labels):
        return REASON_COVERAGE_INCOMPATIBLE
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
        formula_version=COMPARISON_FORMULA_VERSION,
    )


def _scoped_metric(metric: str, mode: str) -> str:
    return f"{metric}.{mode}"
