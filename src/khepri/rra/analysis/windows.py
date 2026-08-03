"""Which two periods a governed comparison compares, defined once.

Extracted from `comparison.py` when `growth.py` needed the same answer. A second
copy of this rule is how two families come to split different numbers: the
comparison section would state a revenue delta, the growth section would decompose
a delta from a different pair of periods, and both would reconcile perfectly
because reconciliation compares rendered strings.

Two rules live here, and each earned its wording the hard way.

**Counterparts are found by label, never by position.** With January, March, April
and May in a series, April's predecessor by position is January. Every sum is
correct and every label looks plausible, which is what makes it dangerous. A
missing counterpart yields nothing rather than the nearest neighbour.

**The period at each end is excluded, because completeness is unknowable here.**
`FactSeries` carries one bucket per period; `Bucket.days` now says how many dates
a bucket covers but not how many the period holds, so nothing here can tell a
whole month from a partial one. What *is* knowable is that a period with data on
both sides of it is whole: a later period proves it finished, an earlier one proves
it was already running when the export began.

Both ends, because either can be the period compared. An export beginning on 15
January holds seventeen days in its first bucket, and a year-over-year comparison
landing on it reads a whole January against a part of one: a series billing 3,100
every month reports +82% growth that is an artifact of where the export started.
"""

from __future__ import annotations

from datetime import date, timedelta

from khepri.rra.aggregates import GRANULARITY_MONTH, Bucket, Series

MODE_PERIOD_OVER_PERIOD = "period_over_period"
MODE_YEAR_OVER_YEAR = "year_over_year"
GOVERNED_MODES = (MODE_PERIOD_OVER_PERIOD, MODE_YEAR_OVER_YEAR)


def settled(buckets: tuple[Bucket, ...]) -> tuple[Bucket, ...]:
    """Every period known to be whole, which is every one but the two on the ends."""
    return buckets[1:-1]


def compared_labels(series: Series, mode: str) -> tuple[str, str] | None:
    """The labels of the two settled periods this mode compares, current first.

    Returns nothing when no settled period exists, or when the counterpart the
    mode names is not itself settled. Both are refusals rather than substitutions.
    """
    buckets = settled(series.buckets)
    if not buckets:
        return None
    current = buckets[-1].label
    prior = counterpart_label(current, series.granularity, mode)
    if prior is None or prior not in {bucket.label for bucket in buckets}:
        return None
    return (current, prior)


def counterpart_label(label: str, granularity: str, mode: str) -> str | None:
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
        # end of the calendar -- `OverflowError`, which is not a `ValueError`, so
        # catching only the latter let it escape as an abort instead of a
        # governed refusal.
        return None
