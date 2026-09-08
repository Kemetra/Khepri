"""Verify RRA-006 §Two-population bundle without retaining it.

Real RRA-004 packages exercise RRA-008 §Composite provenance and §Operand
order, plus RCA-005 §Comparison retention by name.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from types import ModuleType

import pytest

from khepri.rra import crossversion_assembly as assembly_module
from khepri.rra import crossversion_bundle as crossversion_module
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.analysis.comparison_narrative import CROSSVERSION_REFUSALS
from khepri.rra.analysis.comparison_package import (
    COMPARISON_CROSSVERSION_VERSION,
    OPERAND_ORDER,
    MeasuredPair,
    build_cross_version_fact,
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
    # The identity document's slots follow the caller's order, not a canonical one.
    # Mutation testing found this gap: an identity that sorted its two packages still
    # produced a distinct bundle_id, because figures and citations are order-sensitive on
    # their own, while the document named the wrong package as subject.
    subject_id = request.subject_period.dataset_version_id
    baseline_id = request.baseline_period.dataset_version_id
    assert forward.identity.as_document()["subject.dataset_version_id"] == subject_id
    assert forward.identity.as_document()["baseline.dataset_version_id"] == baseline_id
    assert backward.identity.as_document()["subject.dataset_version_id"] == baseline_id
    assert backward.identity.as_document()["baseline.dataset_version_id"] == subject_id


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
    bundle = _bundle(request)
    document = bundle.identity.as_document()

    assert document["subject.dataset_version_id"] == request.subject_period.dataset_version_id
    assert document["baseline.dataset_version_id"] == request.baseline_period.dataset_version_id
    assert (
        document["subject.coverage_manifest_identity"] == request.subject.coverage_manifest_identity
    )
    assert (
        document["baseline.coverage_manifest_identity"]
        == request.baseline.coverage_manifest_identity
    )
    assert document["operand_order"] == ",".join(OPERAND_ORDER)
    # The retained bases are per citation and live on the evidence records, which the
    # rules bind to the identity's citations; the identity document itself is flat.
    basis_ids = {
        value
        for record in bundle.evidence
        for key, value in (record.provenance or ())
        if key.endswith("_basis_id")
    }
    for provenance in bundle.identity.pair_provenance:
        assert {provenance.subject_basis_id, provenance.baseline_basis_id} <= basis_ids


def test_percentage_ratio_survives_the_governed_magnitude_extremes(
    comparison_request: CrossVersionRequest,
) -> None:
    """The governed maximum subject over the governed minimum baseline derives.

    Review of #408 (debate-review) suspected this pair overflowed Python's default
    28-digit context. Checked: the quotient is 26 digits and fits, so there was no
    live defect. The ratio is nonetheless computed under `ARITHMETIC_PRECISION` as
    every other ratio in the repository is, and this pins that the extreme pair
    derives to a four-place fraction rather than raising out of assembly.
    """
    fact = build_cross_version_fact(
        MeasuredPair(
            metric="revenue",
            subject_value=Decimal("9" * 16 + ".99"),
            baseline_value=Decimal("0.000001"),
            precision=2,
            unit_kind="monetary",
        ),
        _bundle(comparison_request).identity.pair_provenance[0],
    )

    ratio = assembly_module._percentage_ratio(fact)

    assert ratio.as_tuple().exponent == -4
    assert ratio > Decimal("1e21")


def test_pair_sharing_no_metric_refuses_rather_than_raising(
    comparison_request: CrossVersionRequest,
) -> None:
    """Admission reads provenance, not columns; the empty comparison is a refusal.

    Review of #408 (debate-review): two admitted packages gapped in each other's
    columns passed every predicate, produced no facts, and the bundle's own rules
    then raised -- neither a bundle nor governed wording. It is now a refusal under
    `incomplete coverage`, with wording in both languages and no figure.
    """
    request = comparison_request
    disjoint = replace(request, baseline=replace(request.baseline, facts=()))

    result = build_crossversion_bundle(disjoint)

    assert isinstance(result, CrossVersionRefusal)
    assert result.cause == CAUSE_INCOMPLETE
    assert set(result.wording) == {LANGUAGE_ARABIC, LANGUAGE_ENGLISH}
    assert result.figures == ()
    assert result.bundle is None


def test_workbook_writes_the_sibling_cells_to_their_own_sheet(
    comparison_request: CrossVersionRequest,
    tmp_path,
) -> None:
    """A workbook cell states which population it belongs to.

    Review of #408 (debate-review): the business sheets are keyed by metric, so a
    subject, a baseline and a difference row were written to Executive Summary as if
    they were that package's headline totals. They now go to one sheet under the
    section's governed heading, named measure-then-role, and no business sheet is
    written for the sibling.
    """
    from tests import rra_workbooks

    bundle = _bundle(comparison_request)
    renderer = ExcelSurfaceRenderer(directory=tmp_path)
    renderer.render(bundle)
    workbook = rra_workbooks.read(renderer.path_for(bundle).read_bytes())

    names = set(workbook.sheets)
    for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
        assert wording.SECTION_HEADINGS[language][SECTION_CROSSVERSION] in names
        assert wording.BUSINESS_SHEET_NAMES[language]["executive_summary"] not in names
    texts = set(workbook.texts)
    assert "Revenue — Subject dataset" in texts
    assert "Revenue — Baseline dataset" in texts
    assert "Revenue — Difference" in texts


def test_matched_metric_without_a_retained_basis_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    """A basis the cited metric needs but the package does not retain is a refusal.

    Review of #408: admission checked only that each package retained *some* basis,
    so a package missing the one a matched metric cites raised from the basis
    lookup after the pair was admitted. Admission now checks every shared metric on
    both sides and refuses under `incomplete coverage`.
    """
    request = comparison_request
    without_revenue_basis = tuple(
        basis
        for basis in request.baseline.retained_bases
        if basis.name != "financial_revenue_basis"
    )
    assert len(without_revenue_basis) == len(request.baseline.retained_bases) - 1
    thinned = replace(
        request, baseline=replace(request.baseline, retained_bases=without_revenue_basis)
    )

    result = build_crossversion_bundle(thinned)

    assert isinstance(result, CrossVersionRefusal)
    assert result.cause == CAUSE_INCOMPLETE
    assert result.bundle is None


def test_basis_map_covers_every_governed_metric_and_nothing_else(
    comparison_request: CrossVersionRequest,
) -> None:
    """The import-time guard, asserted against the emitted set and exercised.

    Review of #408 (debate-review): without this a metric added to GOVERNED_METRICS
    later would refuse every pair under `incomplete coverage` instead of failing
    once at import. The guard is called with a broken table so the test proves it
    can fail, not only that the shipped table passes it.
    """
    from khepri.rra.facts import GOVERNED_METRICS

    table = assembly_module._BASIS_BY_METRIC
    assert set(table) == GOVERNED_METRICS
    assert {figure.metric for figure in _bundle(comparison_request).figures} <= set(table)

    missing_one = {metric: basis for metric, basis in table.items() if metric != "revenue"}
    with pytest.raises(ValueError, match="missing \\['revenue'\\]"):
        assembly_module._assert_basis_map_complete(missing_one)
    with pytest.raises(ValueError, match="unknown \\['invented'\\]"):
        assembly_module._assert_basis_map_complete({**table, "invented": "some_basis"})


def test_identity_document_is_flat(comparison_request: CrossVersionRequest) -> None:
    """Every value is one governed string, so no surface can print a Python repr.

    Review of #408 (debate-review) found the earlier nested document reaching the
    HTML provenance table and the workbook provenance sheet as dict and list reprs,
    because both flatten the identity document value by value with str().
    """
    document = _bundle(comparison_request).identity.as_document()

    assert all(isinstance(value, str) for value in document.values()), document
    assert "citations" not in document
    assert not any("{" in value or "[" in value for value in document.values())


def test_changing_a_cited_basis_changes_the_bundle_id(
    comparison_request: CrossVersionRequest,
) -> None:
    """One content address authenticates one audit record.

    The reproducer from review of #408 (debate-review): swap one citation's
    subject basis and update its evidence record in lockstep. The bundle still
    constructs -- the rules cannot see the source packages to check a basis -- but
    its identity now digests every citation, so the address changes.
    """
    bundle = _bundle(comparison_request)
    first, *rest = bundle.identity.citations
    forged = replace(first, pair=replace(first.pair, subject_basis_id="basis_forged"))
    identity = replace(bundle.identity, citations=(forged, *rest))
    evidence = tuple(
        replace(record, provenance=forged.provenance_pairs())
        if record.citation_id == first.citation_id
        else record
        for record in bundle.evidence
    )

    tampered = replace(bundle, identity=identity, evidence=evidence)

    assert tampered.bundle_id != bundle.bundle_id
    assert (
        identity.as_document()["citations_digest"]
        != bundle.identity.as_document()["citations_digest"]
    )


def test_pair_coverage_identity_is_a_digest(comparison_request: CrossVersionRequest) -> None:
    """The Protocol's one manifest slot carries a digest, not a JSON blob."""
    identity = _bundle(comparison_request).identity

    assert re.fullmatch(r"[0-9a-f]{64}", identity.coverage_manifest_identity)


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


def test_evidence_without_composite_provenance_keeps_legacy_shape(
    comparison_request: CrossVersionRequest,
) -> None:
    """A record with no composite provenance serializes exactly as it did before.

    That is what keeps every report-bundle evidence document byte-identical: the
    `provenance` key appears only when there is provenance to carry.
    """
    record = replace(_bundle(comparison_request).evidence[0], provenance=None)

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


# --- Review round 1 (#408): the invariants a directly constructed bundle must hold ----


def test_citation_naming_a_different_pair_than_its_identity_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    """Every identity citation is bound to the identity's own ordered pair."""
    identity = _bundle(comparison_request).identity
    first, *rest = identity.citations
    swapped_pair = replace(
        first.pair,
        subject_version_id=first.pair.baseline_version_id,
        baseline_version_id=first.pair.subject_version_id,
    )

    with pytest.raises(ValueError, match="different pair"):
        replace(identity, citations=(replace(first, pair=swapped_pair), *rest))


def test_identity_repeating_a_citation_refuses(comparison_request: CrossVersionRequest) -> None:
    """Keyed by identifier downstream, a repeated citation would silently collapse."""
    identity = _bundle(comparison_request).identity
    first, *rest = identity.citations

    with pytest.raises(ValueError, match="repeats a citation"):
        replace(identity, citations=(first, first, *rest))


def test_group_with_a_repeated_operand_refuses(comparison_request: CrossVersionRequest) -> None:
    """Two subject cells are not one subject; a set of labels would not notice."""
    bundle = _bundle(comparison_request)
    subject = next(figure for figure in bundle.figures if figure.label == LABEL_SUBJECT)
    duplicate = replace(subject, figure_id=f"{subject.figure_id}-again")
    figures = (*bundle.figures, duplicate)
    section = replace(bundle.sections[0], figure_ids=tuple(figure.figure_id for figure in figures))

    with pytest.raises(ValueError, match="repeats"):
        replace(bundle, figures=figures, sections=(section,))


def test_group_without_an_absolute_difference_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    """Subject and baseline alone are two numbers, not a comparison."""
    bundle = _bundle(comparison_request)
    kept = tuple(figure for figure in bundle.figures if figure.label != LABEL_DIFFERENCE)
    section = replace(bundle.sections[0], figure_ids=tuple(figure.figure_id for figure in kept))

    with pytest.raises(ValueError, match="difference"):
        replace(bundle, figures=kept, sections=(section,))


def test_duplicate_evidence_record_refuses(comparison_request: CrossVersionRequest) -> None:
    bundle = _bundle(comparison_request)

    with pytest.raises(ValueError, match="repeats"):
        replace(bundle, evidence=(*bundle.evidence, bundle.evidence[0]))


def test_evidence_with_a_different_metric_than_its_figure_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    bundle = _bundle(comparison_request)
    first, *rest = bundle.evidence

    with pytest.raises(ValueError, match="disagrees"):
        replace(bundle, evidence=(replace(first, metric="another_metric"), *rest))


def test_forged_provenance_under_a_real_citation_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    """A real citation identifier does not launder a different pair."""
    bundle = _bundle(comparison_request)
    first, *rest = bundle.evidence
    assert first.provenance is not None
    forged = tuple(
        (key, {"subject_version_id": "dsv_forged"}.get(key, value))
        for key, value in first.provenance
    )

    with pytest.raises(ValueError, match="different pair"):
        replace(bundle, evidence=(replace(first, provenance=forged), *rest))


def test_percentage_cell_is_a_ratio_presented_as_a_percentage(
    comparison_request: CrossVersionRequest,
) -> None:
    """120 against 100 is the fraction 0.2000, shown as 20.00%.

    Review of #408 (debate-review) found the cell pre-formatted `"20%"` into the
    text handed to `_renderings`, which could not parse it and returned it
    verbatim: ungrouped, unquantized, and at up to 28 significant digits for a
    non-terminating ratio. The cell now carries the four-place fraction every
    ratio figure carries, and the shared formatter scales it.
    """
    bundle = _bundle(comparison_request)
    cells = [
        figure
        for figure in bundle.figures
        if figure.label == LABEL_PERCENTAGE_DIFFERENCE and figure.metric == "revenue"
    ]
    assert len(cells) == 1
    cell = cells[0]

    assert cell.value == Decimal("0.2000")
    assert cell.renderings[LANGUAGE_ENGLISH] == "20.00%"
    arabic = cell.renderings[LANGUAGE_ARABIC]
    # The Arabic form carries the Arabic percent sign (U+066A), not the ASCII one.
    assert arabic.endswith("٪")
    assert not any(character.isascii() and character.isdigit() for character in arabic)
