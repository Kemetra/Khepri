"""The read-only catalog of governed vocabulary, derived and never restated.

**What this module is.** One place to ask which metrics, populations, reasons and
caveats the governed calculation can publish, and what each is called. `RRA-011`
authorizes it as a catalog over calculation that already exists: it adds no
arithmetic, admits no code, and decides nothing about what a figure means.

**Derived, not retyped.** Every code here is read from the module that already
governs it — `facts.GOVERNED_METRICS`, `populations.GOVERNED_POPULATIONS`, and
each `RRA-008` family's own `GOVERNED_METRICS`. That is `RRA-011`'s third scope
test, and it is stated against *hand-maintenance* rather than duplication in
general: a set computed from the governed source at import is the same truth read
twice, while a retyped list is a second truth that nothing makes wrong when the
source moves. `wording.py` carried such a list until this slice replaced it.

**Two scopes, and the discipline is not conflating them.** A metric's identity is
a constant; its precision and the population it was computed over are properties
of a run. `facts.py` reads monetary precision from the admitted data, and no
governed record ties a metric to a population, so neither appears on a definition
here. A catalog that published them would be guessing in a field named as though
it knew, which is the fabrication the fail-closed rule exists to prevent. A reader
who needs them reads the package that carries them.

**Family codes are admitted by their family's own rule.** A population like
`dimension_complete_sales:category` is a member of a family whose members are
whichever dimensions the mapping resolved, so `GOVERNED_POPULATIONS` excludes them
by design and `populations.is_governed_population` admits them by prefix. This
module delegates to that predicate rather than testing set membership, which would
reject a population real packages carry.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra import facts, populations
from khepri.rra.analysis import basket, comparison, concentration, growth
from khepri.rra.rendering import wording


class UnknownCode(LookupError):
    """A code no governed module admits.

    Raised rather than returning `None` or the code itself. `RRA-011` requires a
    lookup to fail closed: a definition invented for an unrecognized code would
    be indistinguishable from a real one, and the raw identifier reaching a
    customer surface is the failure the wording layer already refuses.
    """


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """What is knowable about a metric without a package.

    The code, and the governed version of the contract that computes it.
    Everything else a reader might want -- the value, its precision, the rows
    behind it -- belongs to a produced package and is read from there.
    """

    code: str
    #: The governed version of the contract that computes this metric --
    #: `rra004.formula.v2` for a core metric, `rra008.<family>.v2` for an
    #: analysis family. A governed constant read from the module that declares
    #: it, never a label this module coins: `RRA-011` admits no code of its own,
    #: and a family name invented here would be one.
    formula_version: str


@dataclass(frozen=True, slots=True)
class PopulationDefinition:
    """A population code, and whether it names a family rather than a constant."""

    code: str
    is_family: bool


#: Which governed contract publishes which metrics, keyed by that contract's own
#: version constant. Both halves are read from the module that declares them, so
#: a metric added there reaches this catalog without an edit here, and no name in
#: this table is one this module invented.
FAMILY_METRICS: dict[str, tuple[str, ...]] = {
    facts.FORMULA_VERSION: tuple(sorted(facts.GOVERNED_METRICS)),
    comparison.COMPARISON_FORMULA_VERSION: tuple(comparison.GOVERNED_METRICS),
    growth.GROWTH_FORMULA_VERSION: tuple(growth.GOVERNED_METRICS),
    basket.BASKET_FORMULA_VERSION: tuple(basket.GOVERNED_METRICS),
    concentration.CONCENTRATION_FORMULA_VERSION: tuple(
        concentration.GOVERNED_METRICS
    ),
}

#: Every metric code any governed family publishes.
METRIC_CODES: frozenset[str] = frozenset(
    code for codes in FAMILY_METRICS.values() for code in codes
)

#: Every population code that is a constant. Family members are admitted by
#: `admits_population` instead, which is `populations`' own rule.
POPULATION_CODES: frozenset[str] = frozenset(populations.GOVERNED_POPULATIONS)

_METRIC_VERSIONS: dict[str, str] = {
    code: version for version, codes in FAMILY_METRICS.items() for code in codes
}


def admits_metric(code: str) -> bool:
    """Whether any governed family publishes this metric."""
    return code in METRIC_CODES


def admits_population(code: str) -> bool:
    """Whether `RRA-004` defines this population, constant or family member.

    Delegates to `populations.is_governed_population` rather than testing
    `POPULATION_CODES`, so a `dimension_complete_sales:<dimension>` member is
    admitted by the same rule the rest of the system admits it by.
    """
    return populations.is_governed_population(code)


def define_metric(code: str) -> MetricDefinition:
    """The definition for one metric code, or `UnknownCode`."""
    formula_version = _METRIC_VERSIONS.get(code)
    if formula_version is None:
        raise UnknownCode(code)
    return MetricDefinition(code=code, formula_version=formula_version)


def define_population(code: str) -> PopulationDefinition:
    """The definition for one population code, or `UnknownCode`.

    A family member is reported as one. The dimension it names is the package's
    to state, not this catalog's: the same code means a different set of rows in
    two packages, and only the package knows which.
    """
    if not admits_population(code):
        raise UnknownCode(code)
    return PopulationDefinition(code=code, is_family=code not in POPULATION_CODES)


def describe_metric(code: str, language: str) -> str:
    """What this metric means, or `UnknownCode`.

    The wording itself lives in `rendering.wording`, which `RRA-011` names as
    its home: descriptions sit beside the business names `RRA-009` governs
    because they are one rendering surface. This is the catalog's door to it,
    so a caller reading definitions needs one import rather than two.

    No fallback to another language: an Arabic reader gets Arabic or an error,
    because a silently English answer on an Arabic surface is the parity failure
    `RRA-006` forbids.
    """
    if not admits_metric(code):
        raise UnknownCode(code)
    return wording.metric_description(code, language)


def not_meant(code: str, language: str) -> str:
    """The reading this metric invites and does not support, or `UnknownCode`."""
    if not admits_metric(code):
        raise UnknownCode(code)
    return wording.metric_not_meant(code, language)


def synonyms(code: str, language: str) -> tuple[str, ...]:
    """Names a reader may recognize this metric by, or `UnknownCode`.

    The third of the three things `RRA-011` names as the catalog's vocabulary,
    beside the description and the unsupported reading. A synonym maps a phrase a
    reader arrives with onto the one governed metric; it never defines a second.
    """
    if not admits_metric(code):
        raise UnknownCode(code)
    return wording.metric_synonyms(code, language)


@dataclass(frozen=True, slots=True)
class AnalysisQualitySummary:
    """What one package answered, answered with a qualification, and refused.

    **An aggregation, never a measurement.** Every number here counts outcomes
    the bundle already carries. Nothing is computed, scored, or weighted, and
    `RRA-011` excludes a confidence score, a quality score, and a completeness
    percentage by name — a reader learns what the system could and could not
    answer, not how much to trust an answer it gave.

    **No Internal-tier field.** `Section.state` is Internal and `RRA-009` renders
    an Internal field on no customer surface, so this classifies a section by
    whether it carries a refusal reason. That reaches the same answer from
    Audit-tier evidence: `RRA-008` refuses the affected analysis rather than the
    report, and a refused section is the one that states why.

    `refusals` and `caveats` carry codes rather than prose. What a code *says* to
    a customer is `RRA-009`'s, and restating it here would put the same sentence
    in two places to drift apart.
    """

    answered: int
    caveated: int
    #: How many *analyses* refused outright. Counts sections, so
    #: `answered + refused` is always the section count -- an invariant a reader
    #: and a surface can both rely on, and one that mixing in result refusals
    #: would quietly break.
    refused: int
    #: `(section_id, reason)` for each refused analysis, so a reader learns which
    #: and why rather than only how many.
    refusals: tuple[tuple[str, str], ...]
    #: `(result, reason)` for each figure a surviving analysis could not compute.
    #:
    #: Separate from `refusals` because they are different units and answer
    #: different questions: an analysis that refused is unavailable, while a
    #: refused result is one missing figure inside an analysis the reader still
    #: gets. Counting them together told a reader two things had been refused
    #: without saying which kind, and reporting only sections told them nothing
    #: had been refused at all while two results had.
    refused_results: tuple[tuple[str, str], ...]
    #: Every caveat code the bundle states, deduplicated and ordered. Scoped
    #: result refusals travel in `refused_results` instead, so no code appears in
    #: both and no surface rendering both shows one refusal twice.
    caveats: tuple[str, ...]


def summarize(bundle) -> AnalysisQualitySummary:
    """Group one bundle's outcomes without recomputing any of them.

    Flat by construction: three comprehensions over `bundle.sections` and
    `bundle.caveats`, no branch nesting. The tiering is the bundle's own — a
    section carrying a reason is refused, and one carrying none is not — so this
    never re-derives what `RRA-009` already decided.
    """
    # Two kinds of refusal, reported as two fields.
    #
    # A family that could state nothing refuses its whole section and carries the
    # reason on the section. A family that stated *something* refuses only the
    # results it could not compute -- comparison publishes an absolute delta and
    # refuses the percentage -- and `bundle._scoped` carries each of those as a
    # caveat coded `<result>:<reason>` on a section that has no reason of its own.
    #
    # They are kept apart rather than summed. `answered + refused` is the section
    # count, which a surface relies on, and a refused result is not a refused
    # analysis: the reader still gets that analysis, minus one figure. Summing them
    # broke the invariant and told a reader two things were refused without saying
    # which kind.
    #
    # A scoped refusal is selected by the separator and then split on it, rather
    # than split first and filtered on what falls out. Both partition helpers return
    # a three-tuple for a code with no colon, so a filter reading one of its slots
    # depends on which helper was used and silently admits every caveat when that
    # changes -- the selection is the load-bearing half and it is stated here.
    #
    # `rpartition` because a result identity is mode-qualified with a dot and the
    # reason never contains a colon, so the last one is the boundary even if a
    # future identity carries its own.
    scoped = tuple(caveat for caveat in bundle.caveats if ":" in caveat.code)
    refusals = tuple(
        (section.section_id, section.reason)
        for section in bundle.sections
        if section.reason is not None
    )
    refused_results = tuple(
        (result, reason)
        for result, _, reason in (caveat.code.rpartition(":") for caveat in scoped)
    )
    answered = tuple(
        section for section in bundle.sections if section.reason is None
    )
    # `section is None` is a report-level caveat -- `currency_not_declared`
    # qualifies the dataset, not one analysis -- so it qualifies no section and
    # is filtered out. The filter is belt-and-braces rather than load-bearing:
    # `None` matches no `section_id`, so the intersection below is the same
    # either way. Kept because the set is named `qualified` and a reader should
    # not have to work out that a report-level caveat is silently excluded by
    # arithmetic rather than by intent.
    # A refusal code is not also a caveat. Both fields read `bundle.caveats`, which
    # is one channel carrying two things, so partitioning here is what stops the
    # same refused result being counted as a qualification, listed under `caveats`,
    # and rendered twice to a reader who shows both.
    qualifying = tuple(caveat for caveat in bundle.caveats if ":" not in caveat.code)
    qualified = {
        caveat.section for caveat in qualifying if caveat.section is not None
    }
    return AnalysisQualitySummary(
        answered=len(answered),
        caveated=len({s.section_id for s in answered} & qualified),
        refused=len(refusals),
        refusals=refusals,
        refused_results=refused_results,
        caveats=tuple(sorted({caveat.code for caveat in qualifying})),
    )
