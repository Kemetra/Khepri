"""Verify RRA-006 §Two-population bundle without retaining it.

Real RRA-004 packages exercise RRA-008 §Composite provenance and §Operand
order, plus RCA-005 §Comparison retention by name.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from datetime import date, timedelta
from types import ModuleType

import pytest

from khepri.rra import crossversion_bundle as crossversion_module
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.analysis.comparison_narrative import CROSSVERSION_REFUSALS
from khepri.rra.analysis.comparison_package import (
    COMPARISON_CROSSVERSION_VERSION,
    OPERAND_ORDER,
)
from khepri.rra.analysis.compatibility import (
    CAUSE_CURRENCY,
    CAUSE_FILTERS,
    CAUSE_FORMULA_DRIFT,
    CAUSE_MAPPING_DRIFT,
    CAUSE_PACKAGE_DRIFT,
    CAUSE_SCOPE,
    CAUSE_STORE_SET,
)
from khepri.rra.analysis.dataset_period import (
    CAUSE_GRANULARITY,
    CAUSE_INCOMPLETE,
    CAUSE_RETAIL_DAY,
    CAUSE_UNORDERED_PAIR,
    GRANULARITY_DAY,
    GRANULARITY_MONTH,
    DatasetPeriod,
)
from khepri.rra.bundle import (
    KIND_VALUE,
    NARRATIVE_OMITTED,
    OUTCOME_DELIVERED,
    REQUIRED_SURFACES,
    BundleAssembler,
    CitedEvidence,
    reconcile,
)
from khepri.rra.crossversion_bundle import (
    CROSSVERSION_ADMITTED_CAVEAT,
    CROSSVERSION_FIGURE_LABELS,
    LABEL_BASELINE,
    LABEL_DIFFERENCE,
    LABEL_PERCENTAGE_DIFFERENCE,
    LABEL_SUBJECT,
    SECTION_CROSSVERSION,
    CrossVersionBundle,
    CrossVersionRefusal,
    CrossVersionRequest,
    build_crossversion_bundle,
)
from khepri.rra.facts import AdmittedInput, FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile, canonical_json
from khepri.rra.rendering import (
    ExcelSurfaceRenderer,
    HtmlReportRenderer,
    PdfReportRenderer,
    PrintablePage,
    wording,
)
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    attesting_manifest,
    published_mapping_identity,
)

HEADER = b"date,revenue,units,invoice_no,category,branch\n"
START = date(2026, 3, 1)
SCOPE = "org_a"
PROVENANCE_KEYS = {
    "subject_version_id",
    "subject_basis_id",
    "subject_manifest_id",
    "baseline_version_id",
    "baseline_basis_id",
    "baseline_manifest_id",
    "operand_order",
}


def _content(revenue: str) -> tuple[bytes, tuple[date, ...]]:
    days = tuple(START + timedelta(days=offset) for offset in range(3))
    rows = b"".join(
        f"{day.isoformat()},{revenue},2,INV-{index},Drinks,Cairo\n".encode()
        for index, day in enumerate(days, start=1)
    )
    return HEADER + rows, days


def _package(revenue: str) -> FactPackage:
    content, days = _content(revenue)
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    manifest = attesting_manifest(content=content, contract=TEST_CONTRACT, days=days)
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
                manifest=manifest,
            )
        )


def _period(version_id: str) -> DatasetPeriod:
    return DatasetPeriod(
        dataset_version_id=version_id,
        start=START,
        end=START + timedelta(days=2),
        granularity=GRANULARITY_DAY,
        retail_day_start_hour=0,
        complete=True,
    )


@pytest.fixture(scope="module")
def comparison_request() -> CrossVersionRequest:
    return CrossVersionRequest(
        subject=_package("120.00"),
        baseline=_package("100.00"),
        subject_organization_scope=SCOPE,
        baseline_organization_scope=SCOPE,
        subject_period=_period("dsv_subject"),
        baseline_period=_period("dsv_baseline"),
    )


def _bundle(request: CrossVersionRequest) -> CrossVersionBundle:
    result = build_crossversion_bundle(request)
    assert isinstance(result, CrossVersionBundle)
    return result


def _labels(bundle: CrossVersionBundle, metric: str) -> set[str | None]:
    return {figure.label for figure in bundle.figures if figure.metric == metric}


def test_reversed_pair_changes_bundle_and_figure_identities(
    comparison_request: CrossVersionRequest,
) -> None:
    request = comparison_request
    forward = _bundle(request)
    backward = _bundle(
        CrossVersionRequest(
            subject=request.baseline,
            baseline=request.subject,
            subject_organization_scope=request.baseline_organization_scope,
            baseline_organization_scope=request.subject_organization_scope,
            subject_period=request.baseline_period,
            baseline_period=request.subject_period,
        )
    )

    assert forward.bundle_id != backward.bundle_id
    assert {figure.figure_id for figure in forward.figures}.isdisjoint(
        figure.figure_id for figure in backward.figures
    )


def test_every_delta_has_both_operands(comparison_request: CrossVersionRequest) -> None:
    bundle = _bundle(comparison_request)
    for metric in {figure.metric for figure in bundle.figures}:
        labels = _labels(bundle, metric)
        if labels & {LABEL_DIFFERENCE, LABEL_PERCENTAGE_DIFFERENCE}:
            assert {LABEL_SUBJECT, LABEL_BASELINE} <= labels

    delta = next(figure for figure in bundle.figures if figure.label == LABEL_DIFFERENCE)
    with pytest.raises(ValueError, match="delta.*operands"):
        replace(
            bundle,
            figures=tuple(
                figure
                for figure in bundle.figures
                if not (figure.metric == delta.metric and figure.label == LABEL_BASELINE)
            ),
        )


def test_non_positive_baseline_omits_only_percentage(
    comparison_request: CrossVersionRequest,
) -> None:
    request = comparison_request
    baseline_facts = tuple(
        replace(fact, value="0.00") if fact.metric == "revenue" else fact
        for fact in request.baseline.facts
    )
    changed = replace(request, baseline=replace(request.baseline, facts=baseline_facts))
    labels = _labels(_bundle(changed), "revenue")

    assert LABEL_DIFFERENCE in labels
    assert LABEL_PERCENTAGE_DIFFERENCE not in labels


def _refusal(result: CrossVersionBundle | CrossVersionRefusal) -> CrossVersionRefusal:
    assert isinstance(result, CrossVersionRefusal)
    assert result.bundle is None
    assert result.figures == ()
    assert set(result.wording) == {LANGUAGE_ARABIC, LANGUAGE_ENGLISH}
    return result


def _store_request(request: CrossVersionRequest, *, other: str) -> CrossVersionRequest:
    def signatures(package: FactPackage, scope: str):
        return tuple(replace(entry, scope=scope) for entry in package.coverage_signatures)

    subject = replace(
        request.subject,
        daily_bases=(),
        coverage_signatures=signatures(request.subject, "store_a"),
    )
    baseline = replace(
        request.baseline,
        daily_bases=(),
        coverage_signatures=signatures(request.baseline, other),
    )
    return replace(request, subject=subject, baseline=baseline)


def _compatibility_cases(request: CrossVersionRequest):
    baseline = request.baseline
    return (
        (CAUSE_SCOPE, replace(request, baseline_organization_scope="org_b")),
        (
            CAUSE_MAPPING_DRIFT,
            replace(request, baseline=replace(baseline, mapping_version="map.v0")),
        ),
        (
            CAUSE_FORMULA_DRIFT,
            replace(request, baseline=replace(baseline, formula_version="formula.v0")),
        ),
        (
            CAUSE_PACKAGE_DRIFT,
            replace(request, baseline=replace(baseline, package_version="package.v0")),
        ),
        (CAUSE_CURRENCY, replace(request, baseline=replace(baseline, currency="USD"))),
        (CAUSE_STORE_SET, _store_request(request, other="store_b")),
        (
            CAUSE_FILTERS,
            replace(
                request,
                baseline=replace(baseline, event_kind_filters=("return",)),
            ),
        ),
    )


def _period_cases(request: CrossVersionRequest):
    baseline = request.baseline_period
    return (
        (
            CAUSE_GRANULARITY,
            replace(
                request,
                baseline_period=replace(baseline, granularity=GRANULARITY_MONTH),
            ),
        ),
        (
            CAUSE_RETAIL_DAY,
            replace(
                request,
                baseline_period=replace(baseline, retail_day_start_hour=4),
            ),
        ),
        (
            CAUSE_INCOMPLETE,
            replace(request, baseline_period=replace(baseline, complete=False)),
        ),
        (
            CAUSE_UNORDERED_PAIR,
            replace(
                request,
                baseline_period=replace(
                    baseline,
                    dataset_version_id=request.subject_period.dataset_version_id,
                ),
            ),
        ),
    )


def test_every_refusal_cause_returns_wording_and_no_bundle(
    comparison_request: CrossVersionRequest,
) -> None:
    request = comparison_request
    cases = (*_compatibility_cases(request), *_period_cases(request))
    assert {cause for cause, _ in cases} == set(CROSSVERSION_REFUSALS)
    for expected, changed in cases:
        refused = _refusal(build_crossversion_bundle(changed))
        assert refused.cause == expected
        assert refused.wording == CROSSVERSION_REFUSALS[expected]


def test_identity_discloses_composite_provenance(
    comparison_request: CrossVersionRequest,
) -> None:
    request = comparison_request
    document = _bundle(request).identity.as_document()
    serialized = canonical_json(document)
    expected = (
        request.subject_period.dataset_version_id,
        request.baseline_period.dataset_version_id,
        request.subject.coverage_manifest_identity,
        request.baseline.coverage_manifest_identity,
    )
    assert all(value is not None and value in serialized for value in expected)
    assert all(
        provenance.subject_basis_id in serialized and provenance.baseline_basis_id in serialized
        for provenance in _bundle(request).identity.pair_provenance
    )
    assert document["operand_order"] == list(OPERAND_ORDER)


def test_every_evidence_record_uses_crossversion_formula(
    comparison_request: CrossVersionRequest,
) -> None:
    versions = {record.formula_version for record in _bundle(comparison_request).evidence}
    assert versions == {COMPARISON_CROSSVERSION_VERSION}
    assert "rra008.comparison.v2" not in versions


def test_every_evidence_record_carries_ordered_pair_provenance(
    comparison_request: CrossVersionRequest,
) -> None:
    request = comparison_request
    forward = _bundle(request)
    backward = _bundle(
        CrossVersionRequest(
            subject=request.baseline,
            baseline=request.subject,
            subject_organization_scope=request.baseline_organization_scope,
            baseline_organization_scope=request.subject_organization_scope,
            subject_period=request.baseline_period,
            baseline_period=request.subject_period,
        )
    )
    reversed_by_metric = {record.metric: record for record in backward.evidence}

    for record in forward.evidence:
        provenance = dict(record.provenance or ())
        reversed_provenance = dict(reversed_by_metric[record.metric].provenance or ())
        assert set(provenance) == PROVENANCE_KEYS
        assert provenance["operand_order"] == "subject,baseline"
        for name in ("version_id", "basis_id", "manifest_id"):
            assert reversed_provenance[f"subject_{name}"] == provenance[f"baseline_{name}"]
            assert reversed_provenance[f"baseline_{name}"] == provenance[f"subject_{name}"]


def test_evidence_without_composite_provenance_keeps_legacy_shape() -> None:
    record = CitedEvidence(
        citation_id="citation",
        metric="revenue",
        unit_kind="monetary",
        formula_version="formula",
        precision=None,
        inputs=None,
    )

    assert "provenance" not in record.as_entry("d")


def test_crossversion_wording_has_one_script_per_language() -> None:
    label_keys = tuple(f"label.{label}" for label in CROSSVERSION_FIGURE_LABELS)
    arabic = (
        *(wording.LABEL_WORDING[LANGUAGE_ARABIC][key] for key in label_keys),
        wording.SECTION_HEADINGS[LANGUAGE_ARABIC][SECTION_CROSSVERSION],
        wording.COMPONENT_CHROME[LANGUAGE_ARABIC]["sources_compared"],
        wording.CAVEAT_WORDING[LANGUAGE_ARABIC][CROSSVERSION_ADMITTED_CAVEAT],
    )
    english = (
        *(wording.LABEL_WORDING[LANGUAGE_ENGLISH][key] for key in label_keys),
        wording.SECTION_HEADINGS[LANGUAGE_ENGLISH][SECTION_CROSSVERSION],
        wording.COMPONENT_CHROME[LANGUAGE_ENGLISH]["sources_compared"],
        wording.CAVEAT_WORDING[LANGUAGE_ENGLISH][CROSSVERSION_ADMITTED_CAVEAT],
    )

    assert all(not re.search(r"[a-zA-Z0-9]", text) for text in arabic)
    assert all(not re.search(r"[\u0600-\u06ff]", text) for text in english)


class _Printer:
    def print_to_pdf(self, page: PrintablePage) -> bytes:
        del page
        return (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/MarkInfo<</Marked true>>"
            b"/StructTreeRoot 9 0 R/Lang(ar)>>endobj\n"
            b"2 0 obj<</Type/FontDescriptor/FontName/AAAAAA+NotoSansArabic-Regular"
            b"/FontFile2 3 0 R>>endobj\n%%EOF\n"
        )


def test_all_surfaces_assemble_and_reconcile(
    comparison_request: CrossVersionRequest,
    tmp_path,
) -> None:
    bundle = _bundle(comparison_request)
    result = BundleAssembler(
        renderers=(
            HtmlReportRenderer(),
            PdfReportRenderer(printer=_Printer()),
            ExcelSurfaceRenderer(directory=tmp_path),
        )
    ).assemble(bundle)

    assert result.attempt.outcome == OUTCOME_DELIVERED
    assert result.surfaces is not None
    assert {surface.surface for surface in result.surfaces} == set(REQUIRED_SURFACES)
    for surface in result.surfaces:
        reconcile(surface, bundle=bundle)
        arabic = next(item for item in surface.languages if item.language == LANGUAGE_ARABIC)
        assert arabic.direction == "rtl"


def test_every_surface_states_the_admitted_pair_caveat(
    comparison_request: CrossVersionRequest,
    tmp_path,
) -> None:
    result = BundleAssembler(
        renderers=(
            HtmlReportRenderer(),
            PdfReportRenderer(printer=_Printer()),
            ExcelSurfaceRenderer(directory=tmp_path),
        )
    ).assemble(_bundle(comparison_request))

    assert result.surfaces is not None
    for surface in result.surfaces:
        for language in surface.languages:
            assert {caveat.code for caveat in language.caveats} == {CROSSVERSION_ADMITTED_CAVEAT}


def test_html_evidence_renders_each_composite_provenance_field(
    comparison_request: CrossVersionRequest,
) -> None:
    bundle = _bundle(comparison_request)
    surface = HtmlReportRenderer().render_html(bundle)

    for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH):
        document = surface.evidence[language]
        assert wording.COMPONENT_CHROME[language]["sources_compared"] in document
        for name, value in bundle.evidence[0].provenance or ():
            assert name in document
            assert value in document


def test_bundle_is_chartless_without_not_drawn_caveat(
    comparison_request: CrossVersionRequest,
) -> None:
    bundle = _bundle(comparison_request)
    assert bundle.sections[0].section_id == SECTION_CROSSVERSION
    assert bundle.sections[0].chart is None
    assert all(caveat.code != "chart_not_drawn" for caveat in bundle.caveats)
    assert all(figure.kind == KIND_VALUE for figure in bundle.figures)
    assert bundle.narrative_state == NARRATIVE_OMITTED


def test_module_imports_no_persistence(comparison_request: CrossVersionRequest) -> None:
    _bundle(comparison_request)
    imported = (
        value.__name__
        for value in vars(crossversion_module).values()
        if isinstance(value, ModuleType)
    )
    assert all("persistence" not in name for name in imported)


def test_same_pair_serializes_byte_identically(
    comparison_request: CrossVersionRequest,
) -> None:
    first = canonical_json(_bundle(comparison_request).as_document()).encode()
    second = canonical_json(_bundle(comparison_request).as_document()).encode()
    assert first == second
