"""Verify RRA-006 §Two-population bundle without retaining it.

Real RRA-004 packages exercise RRA-008 §Composite provenance and §Operand
order, plus RCA-005 §Comparison retention by name."""

from __future__ import annotations

import re
from dataclasses import replace
from decimal import Decimal
from types import ModuleType

import pytest

from khepri.rra import crossversion_assembly as assembly_module
from khepri.rra import crossversion_bundle as crossversion_module
from khepri.rra.analysis.comparison_package import (
    COMPARISON_CROSSVERSION_VERSION,
    OPERAND_ORDER,
    MeasuredPair,
    build_cross_version_fact,
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
    CrossVersionRequest,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import canonical_json
from khepri.rra.rendering import (
    ExcelSurfaceRenderer,
    HtmlReportRenderer,
    PdfReportRenderer,
    wording,
)
from tests.c105_support import (
    PROVENANCE_KEYS,
    _bundle,
    _labels,
    _Printer,
    build_comparison_request,
)


@pytest.fixture(scope="module")
def comparison_request() -> CrossVersionRequest:
    return build_comparison_request()


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
