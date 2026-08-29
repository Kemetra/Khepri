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
from khepri.rra.mapping import STATE_MAPPED
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

#: The series and comparison metrics `facts.py` composes, as
#: `<measure>_by_<dimension>` over the two governed constants the builders
#: themselves iterate. `revenue_by_period` and `units_by_product` reach published
#: figures, so a reader looking at one of those charts must be able to ask what it
#: means -- and before this they got `UnknownCode`.
#:
#: Derived from the cross-product rather than listed, which is what makes this a
#: reading of a governed declaration rather than a set of codes this module coined.
#: A dimension added to `SERIES_DIMENSIONS` or a measure to `SERIES_MEASURES`
#: reaches the catalog with no edit here.
#:
#: The measure axis is `SERIES_MEASURES`, not `GOVERNED_METRICS`: only revenue and
#: units are aggregated over a dimension, so composing over all ten core metrics
#: admitted forty codes -- `gross_margin_by_channel`, `transactions_by_period` --
#: that no builder can emit. A catalog that defines an unproducible code is not
#: fail-closed, so the axis reads the constant the builders are asserted against.
#:
#: The cross-product is complete rather than per-package on purpose. Which of these
#: a given run publishes depends on the columns its mapping resolved, and that is
#: package scope; what each *means* does not vary by run, which is why the catalog
#: can answer it without one.
SERIES_METRICS: frozenset[str] = frozenset(
    f"{measure}_by_{dimension}"
    for measure in facts.SERIES_MEASURES
    for dimension in facts.SERIES_DIMENSIONS
)

#: Every metric code any governed family publishes, plus the series and comparison
#: metrics composed from them.
METRIC_CODES: frozenset[str] = frozenset(
    code for codes in FAMILY_METRICS.values() for code in codes
) | SERIES_METRICS

#: Every population code that is a constant. Family members are admitted by
#: `admits_population` instead, which is `populations`' own rule.
POPULATION_CODES: frozenset[str] = frozenset(populations.GOVERNED_POPULATIONS)

_METRIC_VERSIONS: dict[str, str] = {
    code: version for version, codes in FAMILY_METRICS.items() for code in codes
} | {
    # A series metric is the same measure resolved over a dimension, so it is
    # computed by the same contract and reports that contract's version. Reading
    # `facts.FORMULA_VERSION` rather than looking the measure up keeps this true
    # for a measure that has none of its own.
    f"{measure}_by_{dimension}": facts.FORMULA_VERSION
    for measure in facts.SERIES_MEASURES
    for dimension in facts.SERIES_DIMENSIONS
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


def _series_parts(code: str) -> tuple[str, str] | None:
    """`(measure, dimension)` if this code is a composed series, else `None`.

    Split against the governed dimensions rather than on the last `_by_`, because
    a measure could contain that substring and a positional split would then read
    a real metric as a series over a dimension that does not exist.

    The measure is checked against `SERIES_MEASURES`, the same axis
    `SERIES_METRICS` composes over: a splitter admitting a wider set would
    decompose `gross_margin_by_channel` into parts and answer for a code the
    catalog does not hold.
    """
    for dimension in facts.SERIES_DIMENSIONS:
        measure = code.removesuffix(f"_by_{dimension}")
        if measure != code and measure in facts.SERIES_MEASURES:
            return measure, dimension
    return None


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
    parts = _series_parts(code)
    if parts is None:
        return wording.metric_description(code, language)
    # A series is its measure resolved over a dimension, so its meaning is composed
    # the way its code is. Authoring fifty independent sentences would restate each
    # measure's meaning once per dimension and let the copies drift -- and it would
    # be authored vocabulary for codes no run may publish, since which series exist
    # depends on the columns a mapping resolved.
    measure, dimension = parts
    return wording.series_description(
        wording.metric_description(measure, language), dimension, language
    )


def not_meant(code: str, language: str) -> str:
    """The reading this metric invites and does not support, or `UnknownCode`."""
    if not admits_metric(code):
        raise UnknownCode(code)
    parts = _series_parts(code)
    code = code if parts is None else parts[0]
    return wording.metric_not_meant(code, language)


def synonyms(code: str, language: str) -> tuple[str, ...]:
    """Names a reader may recognize this metric by, or `UnknownCode`.

    The third of the three things `RRA-011` names as the catalog's vocabulary,
    beside the description and the unsupported reading. A synonym maps a phrase a
    reader arrives with onto the one governed metric; it never defines a second.
    """
    if not admits_metric(code):
        raise UnknownCode(code)
    parts = _series_parts(code)
    # A series offers its measure's synonyms: a reader who knows revenue as "sales"
    # recognizes the by-product series by the same word.
    code = code if parts is None else parts[0]
    return wording.metric_synonyms(code, language)


@dataclass(frozen=True, slots=True)
class ReasonDefinition:
    """A refusal reason code, and the scope at which it is stated.

    `RRA-009` states a section reason and a result reason in different words --
    one says an analysis is unavailable, the other that a figure inside a
    surviving analysis is -- so the scope is part of what a reader is asking
    about, not an implementation detail. A code governed at both scopes reports
    both.
    """

    code: str
    #: `("section",)`, `("result",)`, or both, in `RRA-009`'s own order.
    scopes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CaveatDefinition:
    """A caveat code. Unscoped: a caveat qualifies whatever states it."""

    code: str


#: Every refusal reason `RRA-009` renders, and the scopes each is rendered at.
#: Read from the wording registries rather than listed again -- those sets are the
#: repository's existing declaration of which reasons exist, and a second list here
#: is the duplicate truth this specification's third scope test forbids.
REASON_SCOPES: dict[str, tuple[str, ...]] = {
    code: tuple(
        scope for scope in wording.GOVERNED_REASON_SCOPES if code in wording.reason_codes(scope)
    )
    for scope in wording.GOVERNED_REASON_SCOPES
    for code in wording.reason_codes(scope)
}

#: Every refusal reason code, at any scope.
REASON_CODES: frozenset[str] = frozenset(REASON_SCOPES)

#: Every caveat code the governed calculation can state.
CAVEAT_CODES: frozenset[str] = frozenset(wording.caveat_codes())


def admits_reason(code: str) -> bool:
    """Whether `RRA-009` states this refusal reason at any scope."""
    return code in REASON_CODES


def admits_caveat(code: str) -> bool:
    """Whether `RRA-009` states this caveat."""
    return code in CAVEAT_CODES


def define_reason(code: str) -> ReasonDefinition:
    """The definition for one refusal reason, or `UnknownCode`."""
    scopes = REASON_SCOPES.get(code)
    if scopes is None:
        raise UnknownCode(code)
    return ReasonDefinition(code=code, scopes=scopes)


def define_caveat(code: str) -> CaveatDefinition:
    """The definition for one caveat code, or `UnknownCode`."""
    if not admits_caveat(code):
        raise UnknownCode(code)
    return CaveatDefinition(code=code)


def explain_reason(code: str, language: str, scope: str) -> str:
    """What this refusal tells a customer, or `UnknownCode`.

    Returned as `RRA-009` authored it, placeholders included. The sentence for a
    result refusal names the metric it withheld -- `{metric} is not shown` -- and
    only the surface rendering one knows which. Filling it here would need a fact
    the catalog does not have, and substituting the code would put a raw
    identifier in a customer's sentence, which the wording layer already refuses.
    """
    if scope not in wording.GOVERNED_REASON_SCOPES:
        # An unrecognized scope refuses the same way an unrecognized code does.
        # Left to `reason_codes` it escaped as `KeyError`, so a caller catching the
        # catalog's own refusal saw an unhandled exception from one entry point and
        # a governed refusal from every other.
        raise UnknownCode(scope)
    if code not in wording.reason_codes(scope):
        raise UnknownCode(code)
    return wording.reason_wording(code, language, scope)


def explain_caveat(code: str, language: str) -> str:
    """What this caveat tells a customer, or `UnknownCode`."""
    if not admits_caveat(code):
        raise UnknownCode(code)
    return wording.caveat_wording_for(code, language)


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
    #: Which analyses answered, in the order the bundle carries them, so the
    #: summary reads in the order the report renders. `RRA-011`:184-187 asks
    #: *which* results were published rather than only how many: two packages
    #: publishing different analyses produced identical summaries while this was
    #: a bare count.
    #:
    #: `section_id` rather than `Section`: the identity is Audit-tier and already
    #: travels in `refusals`, while `Section.state` is Internal and appears on no
    #: customer surface.
    answered_sections: tuple[str, ...]
    #: Which of those analyses carried a qualification. **A subset of
    #: `answered_sections`, not a disjoint set** -- a caveated analysis was still
    #: answered, and the reader still gets it. That mirrors the counts, where
    #: `caveated` is counted within `answered`, and keeps `len(list) == count`
    #: true of both pairs. A surface rendering both lists must not add them.
    caveated_sections: tuple[str, ...]
    #: `(code, section_id)` for each caveat that qualifies one analysis, sorted.
    #:
    #: The pairs rather than two lists, because one code can qualify several
    #: sections -- `chart_not_drawn` routinely does -- and a reader given the
    #: codes and the sections separately cannot tell one code hitting two
    #: sections from two codes hitting one each.
    #:
    #: A report-level caveat qualifies the dataset and no single analysis, so it
    #: is absent here and travels in `caveats`. Scoped result refusals are absent
    #: too: they travel in `refused_results`, and pairing them here would render
    #: one refusal as a qualification as well.
    caveat_sections: tuple[tuple[str, str], ...]


def _partition_caveats(caveats) -> tuple[tuple, tuple]:
    """`(scoped, qualifying)` — the two things one caveat channel carries.

    A refusal code is not also a caveat. Both `summarize` fields read
    `bundle.caveats`, so partitioning is what stops the same refused result being
    counted as a qualification, listed under `caveats`, and rendered twice to a
    reader who shows both.

    Split here rather than inline so `summarize` reads as the grouping it is:
    the separator test is one rule about one channel, and it is stated once.
    """
    scoped = tuple(caveat for caveat in caveats if ":" in caveat.code)
    qualifying = tuple(caveat for caveat in caveats if ":" not in caveat.code)
    return scoped, qualifying


def _group_answered(sections, qualified) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """`(answered_sections, caveated_sections)` — the identities behind two counts.

    Both walk `sections` in the bundle's own order, so the summary lists analyses
    in the order the report renders them rather than in an order this module
    chose. The second is filtered from the first rather than built separately,
    which is what makes it a subset by construction: `caveated` is counted within
    `answered`, and a caveated analysis the reader still receives cannot be
    missing from the answered list.

    Grouped here rather than inline because `summarize` sits one branch under
    CodeScene's complexity threshold, and these are one concept -- the sections
    that answered, and which of them were qualified.
    """
    answered = tuple(
        section.section_id for section in sections if section.reason is None
    )
    caveated = tuple(code for code in answered if code in qualified)
    return answered, caveated


def _associate_caveats(qualifying) -> tuple[tuple[str, str], ...]:
    """`(code, section_id)` for every caveat that qualifies one analysis.

    Sorted for determinism, matching `caveats`. A report-level caveat carries
    `section=None` and is dropped: it qualifies the dataset rather than an
    analysis, and pairing it with a section would state a scope the bundle never
    claimed.

    `qualifying` is already partitioned, so scoped result refusals never reach
    here -- pairing one would report a refusal as a qualification on top of
    `refused_results`.
    """
    return tuple(
        sorted(
            (caveat.code, caveat.section)
            for caveat in qualifying
            if caveat.section is not None
        )
    )


def summarize(bundle) -> AnalysisQualitySummary:
    """Group one bundle's outcomes without recomputing any of them.

    Flat by construction: comprehensions over `bundle.sections` and the
    partitioned caveats, no branch nesting. The tiering is the bundle's own — a
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
    scoped, qualifying = _partition_caveats(bundle.caveats)
    refusals = tuple(
        (section.section_id, section.reason)
        for section in bundle.sections
        if section.reason is not None
    )
    refused_results = tuple(
        (result, reason)
        for result, _, reason in (caveat.code.rpartition(":") for caveat in scoped)
    )
    # `section is None` is a report-level caveat -- `currency_not_declared`
    # qualifies the dataset, not one analysis -- so it qualifies no section and
    # is filtered out. The filter is belt-and-braces rather than load-bearing:
    # `None` matches no `section_id`, so the intersection below is the same
    # either way. Kept because the set is named `qualified` and a reader should
    # not have to work out that a report-level caveat is silently excluded by
    # arithmetic rather than by intent.
    qualified = {
        caveat.section for caveat in qualifying if caveat.section is not None
    }
    answered_sections, caveated_sections = _group_answered(bundle.sections, qualified)
    return AnalysisQualitySummary(
        # Counted from the identity lists rather than beside them. A count and a
        # list derived separately are two readings that can disagree; taken this
        # way `len(list) == count` holds by construction rather than by test.
        answered=len(answered_sections),
        caveated=len(caveated_sections),
        refused=len(refusals),
        refusals=refusals,
        refused_results=refused_results,
        caveats=tuple(sorted({caveat.code for caveat in qualifying})),
        answered_sections=answered_sections,
        caveated_sections=caveated_sections,
        caveat_sections=_associate_caveats(qualifying),
    )


#: Every declared input this analysis needs is resolved in the mapping.
AVAILABLE = "available"
#: Some are resolved and some are not. The analysis may still publish part of
#: what it states, and `missing` names what stands between it and the rest.
PARTIAL = "partial"
#: None of what it needs is resolved.
UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CapabilityAvailability:
    """Whether one analysis is supportable on the admitted data, before it runs.

    **Availability, never certainty.** `RRA-011`:188-192 excludes a confidence
    score, a quality score, a likelihood, and a completeness percentage by name.
    This answers set membership -- are the semantics this family declares
    resolved in the mapping -- and computes nothing, so there is no arithmetic
    here for a score to hide in. A reader learns what the system will be able to
    answer, not how good the answer will be.

    **Pre-analysis by construction.** `KHEPRI_PRODUCT_UX_BLUEPRINT.md`:201 places
    the Impact Preview at `Review -> Impact Preview -> Analyze`, so no
    `ReportBundle` exists when this is read. It takes a `RetailMapping` and
    nothing else, which is what lets it be honest before the analysis step.

    **Not a promise.** An analysis reported available can still refuse once it
    runs -- on a zero denominator, a reconciliation failure, or a repeated row
    signature, none of which a mapping can foresee. This states that the
    *inputs* are present, which is the only thing knowable at this point.
    """

    section: str
    state: str
    #: What this mapping has not resolved, as one group per gap, in the family's
    #: own order. A bare state tells a customer an analysis will not run and not
    #: what to fix; this names the gap, which is the half they can act on.
    #:
    #: **Groups rather than names**, because some gaps are choices. Basket's
    #: attach rate needs a governed dimension *and* a core measure, so
    #: `('units',), ('product', 'category'), ('revenue', 'units')` is three
    #: pieces of work while the flattened four names read as four required
    #: fields -- misstating the work by two. A one-member group is a plain
    #: requirement and a longer one is a disjunction, so a surface renders
    #: "product or category" from the same shape it renders "units" from.
    missing: tuple[tuple[str, ...], ...]


def _is_resolved(mapping, semantic: str) -> bool:
    """Whether the mapping resolved this semantic to a column.

    A semantic counts as resolved only at `STATE_MAPPED`. `RRA-003` leaves a
    column stating no measure kind ambiguous, and `facts._unavailable_reason`
    already treats that as unavailable with a reason of its own: the data is
    present and the *label* falls short. Counting it as resolved would promise
    an analysis that refuses the moment it runs.

    A semantic absent from the mapping raises `KeyError` from `state_of`. A
    mapping built for a narrower contract legitimately omits one, so absence
    reads as unresolved rather than as an error.
    """
    try:
        return mapping.state_of(semantic) == STATE_MAPPED
    except KeyError:
        return False


def _unmet(mapping, requirement) -> tuple[tuple[str, ...], ...]:
    """What stands between this mapping and one result, in the family's order.

    `requirement` is `(required, groups)`: every semantic in `required` must be
    resolved, and at least one member of each group in `groups`.

    Groups rather than one alternative set, because a metric can face two
    independent choices -- basket's attach rate needs a governed dimension *and*
    a core measure to rank by, and a dimension does not substitute for a
    measure. Collapsing them into one set would report the metric supportable on
    two dimensions and no measure.

    Each gap is returned as a group: a required semantic as a one-member group
    and an unsatisfied choice as all of its members, so a caller can say "product
    or category" and tell it apart from two separate requirements.
    """
    required, groups = requirement
    missing = tuple(
        (code,) for code in required if not _is_resolved(mapping, code)
    )
    for group in groups:
        if not any(_is_resolved(mapping, code) for code in group):
            missing = (*missing, tuple(group))
    return missing


def _assert_mapping_admitted(mapping) -> None:
    """Refuse a mapping this build cannot pair with its own versions.

    `facts.assert_versions_admitted` refuses such a mapping before `_build`
    produces anything, so every analysis is unavailable in the strongest sense:
    not "this data does not support it" but "no package can be built at all".
    Reading only semantic states would report every family available and promise
    a reader analyses that cannot run.

    Checked against **this build's** `PACKAGE_VERSION` and `FORMULA_VERSION`,
    not against membership in any historical triple. `ADMITTED_PACKAGE_PAIRS`
    retains superseded rows, and during a version migration those name mapping
    versions the builder no longer accepts -- `rra003.mapping.v2` sits only
    beside `package.v2`/`formula.v1`. Asking the weaker question would admit a
    mapping `_build` refuses, which is the promise this guard exists to prevent.

    Derived from the constants rather than naming a version, so a version move
    carries this with it instead of needing an edit here.

    Fail-closed on the mapping argument, as `availability_for` already is on the
    section argument.
    """
    if not facts.admits_package(
        mapping_version=mapping.mapping_version,
        package_version=facts.PACKAGE_VERSION,
        formula_version=facts.FORMULA_VERSION,
    ):
        raise UnknownCode(mapping.mapping_version)


def availability(mapping) -> tuple[CapabilityAvailability, ...]:
    """What each governed analysis can be answered on this mapping, before it runs.

    One entry per family in `bundle._FAMILIES`, so a surface renders the report
    without keeping a second list of which analyses exist. Each family's
    requirement is read from the family itself through that table, never
    restated here: `RRA-011` requires a slice to *reduce* the repository's
    hand-maintained code lists, and a copy of four input tuples would be the
    fourth.
    """
    from khepri.rra.bundle import _FAMILIES

    _assert_mapping_admitted(mapping)
    return tuple(
        _availability_of(mapping, section, family)
        for section, family in _FAMILIES.items()
    )


def availability_for(mapping, section: str) -> CapabilityAvailability:
    """One analysis's availability, or `UnknownCode`.

    Fail-closed like every other lookup here: an unrecognized section returning
    `UNAVAILABLE` would be indistinguishable from a real analysis that cannot
    run, and a surface would render a capability the product does not have.
    """
    from khepri.rra.bundle import _FAMILIES

    _assert_mapping_admitted(mapping)
    family = _FAMILIES.get(section)
    if family is None:
        raise UnknownCode(section)
    return _availability_of(mapping, section, family)


def _availability_of(mapping, section: str, family) -> CapabilityAvailability:
    """One family's availability, from what its metrics can actually publish.

    The state is a claim about **results**, not about inputs. Counting resolved
    inputs cannot tell "half of this publishes" from "none of it does": every
    growth metric decomposes from the same date, revenue and units, so a mapping
    holding two of the three publishes nothing, while basket states items per
    transaction on units and an identifier and its attach rate on a dimension
    besides, so the same arithmetic there leaves one metric standing.

    So each metric is checked against its own requirement and the states follow:
    every metric publishable is `available`, none is `unavailable`, and some is
    `partial` -- which is the only reading under which `partial` promises a
    reader something they will actually receive.

    `missing` is the union of what the unpublishable metrics lack, deduplicated
    on the group so a choice two metrics share is stated once, in first-seen
    order -- one list of work rather than one per metric.
    """
    requirements = family.result_requirements()
    unmet = {
        metric: _unmet(mapping, requirement)
        for metric, requirement in requirements.items()
    }
    blocked = [gap for gap in unmet.values() if gap]
    if not blocked:
        return CapabilityAvailability(section=section, state=AVAILABLE, missing=())
    state = UNAVAILABLE if len(blocked) == len(requirements) else PARTIAL
    return CapabilityAvailability(
        section=section,
        state=state,
        missing=tuple(dict.fromkeys(group for gap in blocked for group in gap)),
    )
