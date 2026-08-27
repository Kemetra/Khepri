"""The day-by-day revenue and units a comparison is allowed to reconcile against.

`RRA-004` retains these "separately from the structural signature", and the
separation is the point. A structural signature says *what shape* was attested
and carries no measure; a daily basis carries the measures and the absolute
dates the signature deliberately excludes. Keeping them apart is what lets two
windows be compared for structural compatibility without their values entering
that question.

Each basis records, per the same section, "exact start and end dates, store or
aggregate scope, event and status filters, population identity, currency and
precision where applicable, and daily revenue and unit values, including
attested zero-activity days".

**An attested zero-activity day is a value, not a hole.** `RRA-003` says a
closure "proves complete zero activity" while an extraction gap does not, so a
closed day carries `0` here and a day nobody attested is simply not present.
Collapsing the two would let a shut store read as missing data, or -- far worse
-- missing data read as a quiet day.

**Nothing here infers a day.** `RRA-004`: "Observed day counts, distinct-date
counts, date bounds, equal row counts, and generated date spines are evidence
but are not coverage-manifest completeness proof." So the days come from the
manifest's attested pairs, and a day with no admitted event is zero only where
the manifest says it was covered.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from khepri.rra.populations import is_governed_population
from khepri.rra.profiling import canonical_json


class DailyBasisRefused(ValueError):
    """A daily basis that cannot be retained completely.

    Per `RRA-004`, this refuses only the facts that would have cited it.
    """


@dataclass(frozen=True, slots=True)
class DailyValue:
    """One attested day and what was measured on it."""

    day: date
    revenue: Decimal | None
    units: int | None

    def as_document(self) -> dict[str, object]:
        return {
            "day": self.day.isoformat(),
            "revenue": None if self.revenue is None else str(self.revenue),
            "units": self.units,
        }


@dataclass(frozen=True, slots=True)
class AlignedDailyBasis:
    """Daily revenue and units over one scope, bound to one accepted window."""

    scope: str
    start: date
    end: date
    population: str
    event_kinds: tuple[str, ...]
    statuses: tuple[str, ...]
    values: tuple[DailyValue, ...]
    precision: int
    #: `None` for a basis carrying units alone, which never depended on one
    #: currency being proven.
    currency: str | None = None

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise DailyBasisRefused("A daily basis cannot end before it starts.")
        if not is_governed_population(self.population):
            raise DailyBasisRefused(
                f"A daily basis cannot cite {self.population!r}, "
                "which names no governed population."
            )
        days = [value.day for value in self.values]
        if len(days) != len(set(days)):
            raise DailyBasisRefused("A daily basis states a day more than once.")
        if any(day < self.start or day > self.end for day in days):
            raise DailyBasisRefused(
                "A daily basis states a day outside the window it covers."
            )

    @property
    def identity(self) -> str:
        """The stable identity of this basis, over every field that defines it.

        The values are inside the digest, unlike a structural signature's: a
        daily basis exists precisely to be reconciled against, so two bases over
        one window with different daily values are different evidence and must
        not share an identity.
        """
        return hashlib.sha256(
            canonical_json(self.as_document()).encode()
        ).hexdigest()

    def as_document(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "population": self.population,
            "event_kinds": sorted(self.event_kinds),
            "statuses": sorted(self.statuses),
            "currency": self.currency,
            "precision": self.precision,
            "values": [value.as_document() for value in self.values],
        }

    def restricted_to(self, *, days: int) -> AlignedDailyBasis:
        """The first `days` days of this basis, for a prefix projection.

        `RRA-004` says a projection "restricts the parent daily bases to that
        prefix" and "never ... changes a parent measure value", so this selects
        from what is already retained and computes nothing.
        """
        if days < 1:
            raise DailyBasisRefused("A restriction covers at least its first day.")
        span = (self.end - self.start).days + 1
        if days > span:
            raise DailyBasisRefused(
                "A restriction cannot cover more days than its parent basis."
            )
        last = date.fromordinal(self.start.toordinal() + days - 1)
        return AlignedDailyBasis(
            scope=self.scope,
            start=self.start,
            end=last,
            population=self.population,
            event_kinds=self.event_kinds,
            statuses=self.statuses,
            values=tuple(value for value in self.values if value.day <= last),
            precision=self.precision,
            currency=self.currency,
        )
