"""Derive the read-time cells admitted by RRA-006's two-population bundle.

RRA-008 §Composite provenance and §Operand order supply every comparison fact;
RRA-006 §Two-population bundle supplies only presentation assembly; RCA-005
§Comparison retention by name is why this module imports no store or persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

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
    CROSSVERSION_ADMITTED_CAVEAT,
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


@dataclass(frozen=True, slots=True)
class _FigureCell:
    label: str
    value: Decimal
    unit_kind: str
    text: str


def assemble_crossversion(
    request: CrossVersionRequest,
) -> CrossVersionBundle | CrossVersionRefusal:
    """Build one admitted pair, or its complete refusal and nothing else."""
    cause = _admission_cause(request)
    if cause is not None:
        return CrossVersionRefusal(cause=cause, wording=refusal_wording(cause))
    facts = _crossversion_facts(request)
    figures = tuple(figure for fact in facts for figure in _figures(fact))
    section = CrossVersionSection(tuple(figure.figure_id for figure in figures))
    return CrossVersionBundle(
        identity=_identity(request, facts),
        figures=figures,
        caveats=(StatedCaveat(CROSSVERSION_ADMITTED_CAVEAT, SECTION_CROSSVERSION),),
        sections=(section,),
        evidence=tuple(_evidence(fact) for fact in facts),
    )


def _admission_cause(request: CrossVersionRequest) -> str | None:
    if request.subject_organization_scope != request.baseline_organization_scope:
        return CAUSE_SCOPE
    cause = packages_compatible(
        _candidate(request.subject, request.subject_organization_scope),
        _candidate(request.baseline, request.baseline_organization_scope),
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


def _candidate(package: FactPackage, organization_scope: str) -> ComparisonCandidate:
    aggregate_scope, stores = _population_scope(package)
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


def _population_scope(package: FactPackage) -> tuple[str, tuple[str, ...]]:
    scopes = tuple(sorted({entry.scope for entry in package.coverage_signatures}))
    if package.daily_bases:
        return ("|".join(scopes), ())
    return ("", scopes)


def _has_composite_provenance(request: CrossVersionRequest) -> bool:
    packages = (request.subject, request.baseline)
    return all(
        package.coverage_manifest_identity is not None and package.retained_bases
        for package in packages
    )


def _crossversion_facts(request: CrossVersionRequest) -> tuple[CrossVersionFact, ...]:
    baseline = {fact.metric: fact for fact in request.baseline.facts}
    return tuple(
        _crossversion_fact(subject, counterpart, request)
        for subject in request.subject.facts
        if (counterpart := baseline.get(subject.metric)) is not None
        and counterpart.unit_kind == subject.unit_kind
    )


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
    basis_name = _BASIS_BY_METRIC.get(metric)
    found = next(
        (basis for basis in package.retained_bases if basis.name == basis_name),
        None,
    )
    if found is None:
        raise ValueError(f"metric {metric!r} has no retained reconciliation basis")
    return found.identity


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
        ),
        _FigureCell(
            LABEL_BASELINE,
            fact.baseline_value,
            fact.unit_kind,
            str(fact.baseline_value),
        ),
        _FigureCell(
            LABEL_DIFFERENCE,
            fact.absolute_delta,
            fact.unit_kind,
            str(fact.absolute_delta),
        ),
    ]
    if fact.percentage_delta is not None:
        cells.append(
            _FigureCell(
                LABEL_PERCENTAGE_DIFFERENCE,
                fact.percentage_delta,
                UNIT_RATIO,
                f"{fact.percentage_delta}%",
            )
        )
    return tuple(_figure(fact, cell, position) for position, cell in enumerate(cells))


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
            metric=fact.metric,
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
        provenance=_provenance_pairs(fact.provenance),
    )


def _provenance_pairs(pair: PairProvenance) -> tuple[tuple[str, str], ...]:
    document = dict(pair.as_document())
    document["operand_order"] = ",".join(document["operand_order"])
    return tuple((key, str(value)) for key, value in document.items())


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
