"""Whether two `RRA-004` packages may be compared, and the one cause when they may not.

`RRA-008` §Admission lists six predicates and requires **all six** hold before
any figure is derived. `dataset_period` holds `D-6`'s completeness, because that
is a property of one period; this module holds the five that compare two
packages' provenance.

**One cause, not a list.** §Refusals and caveats freezes a set of single causes,
and a refusal naming two leaves a caller unable to say which to fix. So the
checks are ordered and the first match returns.

**Scope is checked first**, and not only because it is `D-1`. A
cross-organization pair must disclose nothing about the other scope -- `RCA-005`
`FR-130` requires the uniform refusal "disclosing nothing about whether it
exists" -- and naming a version difference would disclose that a version exists
to differ. Mapping before formula for a weaker reason: mapping drift explains
formula drift, so it is the more useful of the two to report.

**`D-5` requires the store set be identical, not merely complete on both
sides.** Two sets each complete and different are a breakdown across one
population's dimension members, which is `RRA-004`'s work rather than a
comparison. `#394` removed that pair from `G4-01` UC-2 and `#400` restated it in
the frozen contract.

Sets are compared as sets: `RRA-004` serializes filters and stores sorted, so
order carries no meaning and two packages listing the same stores differently
are the same population.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "CAUSE_CURRENCY",
    "CAUSE_FILTERS",
    "CAUSE_FORMULA_DRIFT",
    "CAUSE_MAPPING_DRIFT",
    "CAUSE_PACKAGE_DRIFT",
    "CAUSE_SCOPE",
    "CAUSE_STORE_SET",
    "ComparisonCandidate",
    "packages_compatible",
]

#: `RRA-008` §Admission's causes, worded as that section words them. `D-1`'s
#: cause is shared with a differing aggregate scope: both say the two packages
#: describe different scopes, and neither may say more than that.
CAUSE_SCOPE = "cross-organization or scope mismatch"
CAUSE_MAPPING_DRIFT = "mapping drift"
CAUSE_FORMULA_DRIFT = "formula drift"
CAUSE_PACKAGE_DRIFT = "package drift"
CAUSE_CURRENCY = "incomparable basis"
CAUSE_STORE_SET = "store mismatch"
CAUSE_FILTERS = "filter mismatch"


@dataclass(frozen=True, slots=True)
class ComparisonCandidate:
    """One package's provenance, as much of it as §Admission reads.

    A projection rather than the `FactPackage` itself: this module decides
    admissibility and must not be able to read a figure, so it is given only the
    provenance fields `D-1`-`D-5` name.
    """

    organization_scope: str
    mapping_version: str
    formula_version: str
    package_version: str
    currency: str | None
    aggregate_scope: str
    admitted_store_set: tuple[str, ...]
    event_kind_filters: tuple[str, ...]
    status_filters: tuple[str, ...]


def _same(left: object, right: object) -> bool:
    """Two scalar provenance values are the same value."""
    return left == right


def _same_members(left: object, right: object) -> bool:
    """Two collections hold the same members, whatever their order.

    `RRA-004` serializes filters and stores sorted, so order carries no meaning.
    Equality of members, never overlap: `D-5` requires the store set be
    *identical*, so a partly overlapping pair refuses as surely as a disjoint one.
    """
    return set(left) == set(right)  # type: ignore[call-overload]


#: Every predicate `D-1`-`D-5` reads, in the order a refusal reports them.
#:
#: A table rather than a chain of `if`s, for two reasons the checker found: nine
#: sequential branches scored cyclomatic complexity 10 against a threshold of 9,
#: and splitting them into two loops then scored as a Bumpy Road. One loop over
#: one table has neither, and the order -- the meaningful part -- is now a list
#: to audit rather than control flow to trace.
_PREDICATES: tuple[tuple[str, str, object], ...] = (
    ("organization_scope", CAUSE_SCOPE, _same),
    ("mapping_version", CAUSE_MAPPING_DRIFT, _same),
    ("formula_version", CAUSE_FORMULA_DRIFT, _same),
    ("package_version", CAUSE_PACKAGE_DRIFT, _same),
    ("currency", CAUSE_CURRENCY, _same),
    ("aggregate_scope", CAUSE_SCOPE, _same),
    ("admitted_store_set", CAUSE_STORE_SET, _same_members),
    ("event_kind_filters", CAUSE_FILTERS, _same_members),
    ("status_filters", CAUSE_FILTERS, _same_members),
)


def packages_compatible(
    subject: ComparisonCandidate,
    baseline: ComparisonCandidate,
) -> str | None:
    """The first refusal cause for this pair, or `None` when all five hold."""
    return next(
        (
            cause
            for field, cause, holds in _PREDICATES
            if not holds(getattr(subject, field), getattr(baseline, field))  # type: ignore[operator]
        ),
        None,
    )
