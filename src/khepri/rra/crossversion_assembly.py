"""Derive the read-time cells admitted by RRA-006's two-population bundle.

RRA-008 §Composite provenance and §Operand order supply every comparison fact;
RRA-006 §Two-population bundle supplies only presentation assembly; RCA-005
§Comparison retention by name is why this module imports no store or persistence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext

from khepri.rra.analysis.comparison import METRIC_DELTA_PERCENT
from khepri.rra.analysis.comparison_narrative import refusal_wording
from khepri.rra.analysis.comparison_package import (
    COMPARISON_CROSSVERSION_VERSION,
    CrossVersionFact,
    MeasuredPair,
    PairProvenance,
    build_cross_version_fact,
)
from khepri.rra.analysis.compatibility import (
    CAUSE_SCOPE,
    ComparisonCandidate,
    packages_compatible,
)
from khepri.rra.analysis.dataset_period import (
    CAUSE_INCOMPLETE,
    DatasetPeriod,
    UnorderedPairRefused,
    VersionPair,
    periods_comparable,
)
from khepri.rra.bases import (
    BASIS_FINANCIAL_REVENUE,
    BASIS_FINANCIAL_REVENUE_COST,
    BASIS_FINANCIAL_UNITS,
    BASIS_SALES_REVENUE,
    BASIS_SALES_REVENUE_TRANSACTION,
    BASIS_SALES_REVENUE_UNITS,
    BASIS_SALES_TRANSACTION,
    RetainedBasis,
)
from khepri.rra.bundle import (
    KIND_VALUE,
    SECTION_CROSSVERSION,
    CitedEvidence,
    CitedFigure,
    StatedCaveat,
    _figure_id,
    _renderings,
)
from khepri.rra.crossversion_bundle import (
    CAVEAT_CROSSVERSION_ADMITTED_PAIR,
    LABEL_BASELINE,
    LABEL_DIFFERENCE,
    LABEL_PERCENTAGE_DIFFERENCE,
    LABEL_SUBJECT,
    CrossVersionBundle,
    CrossVersionCitationProvenance,
    CrossVersionIdentity,
    CrossVersionPackageIdentity,
    CrossVersionRefusal,
    CrossVersionRequest,
    CrossVersionSection,
)
from khepri.rra.facts import (
    ARITHMETIC_PRECISION,
    GOVERNED_METRICS,
    METRIC_AVERAGE_ORDER_VALUE,
    METRIC_AVERAGE_SELLING_PRICE,
    METRIC_COST,
    METRIC_DISCOUNT,
    METRIC_GROSS_MARGIN,
    METRIC_GROSS_PROFIT,
    METRIC_RETURNS,
    METRIC_REVENUE,
    METRIC_TRANSACTIONS,
    METRIC_UNITS,
    UNIT_RATIO,
    Fact,
    FactPackage,
)
from khepri.rra.narrative import NARRATIVE_VERSION

__all__ = ["assemble_crossversion"]

_BASIS_BY_METRIC = {
    METRIC_REVENUE: BASIS_FINANCIAL_REVENUE,
    METRIC_UNITS: BASIS_FINANCIAL_UNITS,
    METRIC_TRANSACTIONS: BASIS_SALES_TRANSACTION,
    METRIC_AVERAGE_ORDER_VALUE: BASIS_SALES_REVENUE_TRANSACTION,
    METRIC_AVERAGE_SELLING_PRICE: BASIS_SALES_REVENUE_UNITS,
    METRIC_COST: BASIS_FINANCIAL_REVENUE_COST,
    METRIC_GROSS_PROFIT: BASIS_FINANCIAL_REVENUE_COST,
    METRIC_GROSS_MARGIN: BASIS_FINANCIAL_REVENUE_COST,
    METRIC_DISCOUNT: BASIS_SALES_REVENUE,
    METRIC_RETURNS: BASIS_FINANCIAL_REVENUE,
}


def _assert_basis_map_complete(table: Mapping[str, str]) -> None:
    """Every governed metric names a basis, and nothing else does.

    An import-time guard on the same pattern as the wording tables. Without it a
    metric added to `GOVERNED_METRICS` later would fail `_find_basis` for every pair
    and refuse under `incomplete coverage` -- a cause that means something else --
    instead of failing here, once, where the omission is.
    """
    missing = GOVERNED_METRICS - set(table)
    unknown = set(table) - GOVERNED_METRICS
    if missing or unknown:
        raise ValueError(
            f"basis map disagrees with the governed metrics: missing {sorted(missing)}, "
            f"unknown {sorted(unknown)}"
        )


_assert_basis_map_complete(_BASIS_BY_METRIC)


#: `facts.RATIO_PRECISION` as a quantum: every `UNIT_RATIO` figure that reaches a
#: surface is a four-place fraction, which is what lets `bundle._percentage` scale it
#: to two places exactly, with no rounding mode chosen at presentation.
_RATIO_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class _FigureCell:
    """One rendered cell of a cross-version fact.

    `presented_as` is the metric whose presentation rule the cell borrows; it is
    the fact's own metric for every cell but the percentage difference, which is
    a ratio and is shown as the period-comparison family shows its percentage
    delta. The figure's `metric` is always the fact's, so the rule that a figure's
    metric is its fact's metric holds.
    """

    label: str
    value: Decimal
    unit_kind: str
    text: str
    presented_as: str


def assemble_crossversion(
    request: CrossVersionRequest,
) -> CrossVersionBundle | CrossVersionRefusal:
    """Build one admitted pair, or its complete refusal and nothing else."""
    cause = _admission_cause(request)
    if cause is not None:
        return CrossVersionRefusal(cause=cause, wording=refusal_wording(cause))
    facts = _crossversion_facts(request)
    if not facts:
        # Two admitted packages that state no metric in common -- each gapped in the
        # columns the other retains -- have nothing to compare. Column gaps are not
        # provenance, so admission cannot see them, and a bundle with no figures is
        # refused by its own rules; that raise is neither a bundle nor a governed
        # refusal. The cause is `incomplete coverage`: one side's coverage of the
        # compared measures is incomplete, the same reading `_admission_cause` gives a
        # package that cannot name its coverage manifest.
        return CrossVersionRefusal(
            cause=CAUSE_INCOMPLETE, wording=refusal_wording(CAUSE_INCOMPLETE)
        )
    figures = tuple(figure for fact in facts for figure in _figures(fact))
    section = CrossVersionSection(tuple(figure.figure_id for figure in figures))
    return CrossVersionBundle(
        identity=_identity(request, facts),
        figures=figures,
        caveats=(StatedCaveat(CAVEAT_CROSSVERSION_ADMITTED_PAIR, SECTION_CROSSVERSION),),
        sections=(section,),
        evidence=tuple(_evidence(fact) for fact in facts),
    )


def _admission_cause(request: CrossVersionRequest) -> str | None:
    """The first RRA-008 cause that refuses the pair, or None.

    A package with no coverage-manifest identity or no retained basis refuses under
    `CAUSE_INCOMPLETE`, deliberately: `D-6` requires completeness "per the
    authoritative RRA-003 coverage manifest", and a package that cannot name its
    manifest cannot establish it. RRA-008 §Frozen contracts freezes the cause set,
    so a provenance-specific cause is not this slice's to add.
    """
    if request.subject_organization_scope != request.baseline_organization_scope:
        return CAUSE_SCOPE
    cause = packages_compatible(
        _candidate(
            request.subject, request.subject_organization_scope, request.subject_aggregate_scope
        ),
        _candidate(
            request.baseline, request.baseline_organization_scope, request.baseline_aggregate_scope
        ),
    )
    if cause is not None:
        return cause
    if not _has_composite_provenance(request):
        return CAUSE_INCOMPLETE
    try:
        pair = VersionPair(request.subject_period, request.baseline_period)
    except UnorderedPairRefused as refusal:
        return refusal.cause
    return periods_comparable(pair)


def _candidate(
    package: FactPackage,
    organization_scope: str,
    aggregate_scope: str | None,
) -> ComparisonCandidate:
    aggregate_scope, stores = _population_scope(package, aggregate_scope)
    return ComparisonCandidate(
        organization_scope=organization_scope,
        mapping_version=package.mapping_version,
        formula_version=package.formula_version,
        package_version=package.package_version,
        currency=package.currency,
        aggregate_scope=aggregate_scope,
        admitted_store_set=stores,
        event_kind_filters=package.event_kind_filters,
        status_filters=package.status_filters,
    )


def _population_scope(
    package: FactPackage,
    aggregate_scope: str | None,
) -> tuple[str, tuple[str, ...]]:
    """`D-5`'s two shapes, exactly one slot filled: aggregate scope, or store roster.

    The shape is the caller's statement of `CoverageManifest.aggregate_scope`; a
    package does not carry its manifest, so nothing here can tell an aggregate label
    from a single store identifier. An earlier version inferred the shape from
    `daily_bases`, which `facts` also empties for a repeated row signature, so two
    datasets of one organization refused as a scope mismatch; a later one compared
    the attested sets alone, which let an aggregate label and an identically named
    single-store roster pass as one population (review of `#408`). A stated label
    fills the aggregate slot; `None` -- a roster -- fills the store slot with the
    attested set, and the compatibility table's own causes then apply.
    """
    if aggregate_scope is not None:
        return (aggregate_scope, ())
    return ("", tuple(sorted({entry.scope for entry in package.coverage_signatures})))


def _has_composite_provenance(request: CrossVersionRequest) -> bool:
    """Both manifests named, and a retained basis on both sides for every shared metric.

    Checked at admission so that a package missing the basis a matched metric cites
    refuses under `incomplete coverage` rather than raising from `_basis_id` after
    the pair was admitted -- review of `#408` found that path.
    """
    packages = (request.subject, request.baseline)
    if any(package.coverage_manifest_identity is None for package in packages):
        return False
    return all(
        _find_basis(package, metric) is not None
        for package in packages
        for metric in _shared_metrics(request)
    )


def _shared_metrics(request: CrossVersionRequest) -> set[str]:
    """The metrics both packages state with the same unit -- the ones compared."""
    subject = {fact.metric: fact.unit_kind for fact in request.subject.facts}
    return {
        fact.metric for fact in request.baseline.facts if subject.get(fact.metric) == fact.unit_kind
    }


def _crossversion_facts(request: CrossVersionRequest) -> tuple[CrossVersionFact, ...]:
    _require_one_fact_per_metric(request.subject)
    _require_one_fact_per_metric(request.baseline)
    baseline = {fact.metric: fact for fact in request.baseline.facts}
    return tuple(
        _crossversion_fact(subject, counterpart, request)
        for subject in request.subject.facts
        if (counterpart := baseline.get(subject.metric)) is not None
        and counterpart.unit_kind == subject.unit_kind
    )


def _require_one_fact_per_metric(package: FactPackage) -> None:
    """An `RRA-004` population states each metric once; anything else is not one.

    Not a refusal: `RRA-008` §Frozen contracts places an input `RRA-004` does not
    admit upstream of this family ("this family emits nothing"), and every frozen
    cause would misdescribe it. `build_fact_package` cannot produce a duplicate, so
    this is reachable only by direct construction, and it fails here, named, rather
    than downstream as a repeated figure identifier (review of `#408`).
    """
    metrics = [fact.metric for fact in package.facts]
    if len(metrics) == len(set(metrics)):
        return
    raise ValueError("fact package states a metric twice and is not an RRA-004 population")


def _crossversion_fact(
    subject: Fact,
    baseline: Fact,
    request: CrossVersionRequest,
) -> CrossVersionFact:
    measured = MeasuredPair(
        metric=subject.metric,
        subject_value=Decimal(subject.value),
        baseline_value=Decimal(baseline.value),
        precision=max(subject.precision, baseline.precision),
        unit_kind=subject.unit_kind,
    )
    return build_cross_version_fact(measured, _pair_provenance(subject.metric, request))


def _pair_provenance(metric: str, request: CrossVersionRequest) -> PairProvenance:
    return PairProvenance(
        subject_version_id=request.subject_period.dataset_version_id,
        subject_basis_id=_basis_id(request.subject, metric),
        subject_manifest_id=_manifest_id(request.subject),
        baseline_version_id=request.baseline_period.dataset_version_id,
        baseline_basis_id=_basis_id(request.baseline, metric),
        baseline_manifest_id=_manifest_id(request.baseline),
    )


def _basis_id(package: FactPackage, metric: str) -> str:
    """The cited basis for an admitted metric; admission already proved it exists."""
    found = _find_basis(package, metric)
    if found is None:
        raise ValueError(f"metric {metric!r} has no retained reconciliation basis")
    return found.identity


def _find_basis(package: FactPackage, metric: str) -> RetainedBasis | None:
    """The package's own basis for a metric: right name, and bound to this package.

    A basis binds to the input it reconciled (`input_digest`) and the mapping it was
    built under; `retain_bases` stamps both from the package, so a basis carrying
    another digest or mapping is not this package's, whatever its name, and a pair
    citing one refuses at admission rather than publishing a foreign identity.
    """
    expected = (
        _BASIS_BY_METRIC.get(metric),
        package.source_sha256_hex,
        package.mapping_version,
    )
    return next(
        (
            basis
            for basis in package.retained_bases
            if (basis.name, basis.input_digest, basis.mapping_version) == expected
        ),
        None,
    )


def _manifest_id(package: FactPackage) -> str:
    if package.coverage_manifest_identity is None:
        raise ValueError("admitted pair has no coverage-manifest identity")
    return package.coverage_manifest_identity


def _figures(fact: CrossVersionFact) -> tuple[CitedFigure, ...]:
    cells = [
        _FigureCell(
            LABEL_SUBJECT,
            fact.subject_value,
            fact.unit_kind,
            str(fact.subject_value),
            fact.metric,
        ),
        _FigureCell(
            LABEL_BASELINE,
            fact.baseline_value,
            fact.unit_kind,
            str(fact.baseline_value),
            fact.metric,
        ),
        _FigureCell(
            LABEL_DIFFERENCE,
            fact.absolute_delta,
            fact.unit_kind,
            str(fact.absolute_delta),
            fact.metric,
        ),
    ]
    if fact.percentage_delta is not None:
        cells.append(
            _FigureCell(
                LABEL_PERCENTAGE_DIFFERENCE,
                _percentage_ratio(fact),
                UNIT_RATIO,
                str(_percentage_ratio(fact)),
                METRIC_DELTA_PERCENT,
            )
        )
    return tuple(_figure(fact, cell, position) for position, cell in enumerate(cells))


def _percentage_ratio(fact: CrossVersionFact) -> Decimal:
    """The percentage difference as the four-place fraction a ratio figure carries.

    `CrossVersionFact.percentage_delta` states the value scaled by one hundred and
    unquantized; a surface shows a ratio, and `bundle._percentage` scales a
    four-place fraction to two places exactly. So the cell carries
    `(subject - baseline) / baseline` quantized to `RATIO_PRECISION`, as the
    period-comparison family's `revenue_delta_percent` fact does. Review of `#408`
    found the earlier cell pre-formatted a percent sign into text the shared
    formatter could not parse, so it was published ungrouped at full precision.

    Computed under `ARITHMETIC_PRECISION`, as `facts` and the period-comparison
    family compute every ratio, so this module holds no arithmetic assumption of
    its own. Review of `#408` asked whether the governed extremes -- a sixteen-digit
    subject over a six-decimal baseline -- overflow Python's default 28-digit
    context; they do not (26 digits), and the governed context makes the question
    moot for any magnitude the package contract could later admit.
    """
    # Rounded, and deliberately so: a quotient is not exact in general (one third
    # has no four-place form), which is why this is a fact-boundary quantization on
    # the period-comparison family's precedent and not `bundle._EXACT`, whose
    # `Inexact` trap guards the exact scale-by-one-hundred of a value already
    # quantized here. The mode is the standard library's default, stated so it is
    # read as chosen.
    with localcontext(Context(prec=ARITHMETIC_PRECISION)):
        return (fact.absolute_delta / fact.baseline_value).quantize(
            _RATIO_QUANTUM, rounding=ROUND_HALF_EVEN
        )


def _figure(fact: CrossVersionFact, cell: _FigureCell, position: int) -> CitedFigure:
    return CitedFigure(
        figure_id=_figure_id(fact.citation_id, KIND_VALUE, position),
        citation_id=fact.citation_id,
        fact_id=fact.fact_id,
        metric=fact.metric,
        unit_kind=cell.unit_kind,
        kind=KIND_VALUE,
        section=SECTION_CROSSVERSION,
        label=cell.label,
        value=cell.value,
        renderings=_renderings(
            cell.text,
            unit_kind=cell.unit_kind,
            metric=cell.presented_as,
        ),
    )


def _evidence(fact: CrossVersionFact) -> CitedEvidence:
    return CitedEvidence(
        citation_id=fact.citation_id,
        metric=fact.metric,
        unit_kind=fact.unit_kind,
        formula_version=COMPARISON_CROSSVERSION_VERSION,
        precision=None,
        inputs=None,
        provenance=CrossVersionCitationProvenance(
            fact.citation_id, fact.metric, fact.provenance
        ).provenance_pairs(),
    )


def _identity(
    request: CrossVersionRequest,
    facts: tuple[CrossVersionFact, ...],
) -> CrossVersionIdentity:
    return CrossVersionIdentity(
        subject=_package_identity(request.subject, request.subject_period),
        baseline=_package_identity(request.baseline, request.baseline_period),
        package_version=request.subject.package_version,
        package_formula_version=request.subject.formula_version,
        mapping_version=request.subject.mapping_version,
        comparison_formula_version=COMPARISON_CROSSVERSION_VERSION,
        narrative_version=NARRATIVE_VERSION,
        citations=tuple(
            CrossVersionCitationProvenance(fact.citation_id, fact.metric, fact.provenance)
            for fact in facts
        ),
    )


def _package_identity(
    package: FactPackage,
    period: DatasetPeriod,
) -> CrossVersionPackageIdentity:
    return CrossVersionPackageIdentity(
        dataset_version_id=period.dataset_version_id,
        package_digest=package.digest,
        profile_digest=package.profile_digest,
        source_sha256_hex=package.source_sha256_hex,
        coverage_manifest_identity=_manifest_id(package),
        coverage_signatures=tuple(entry.identity for entry in package.coverage_signatures),
    )
