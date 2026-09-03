"""RRA-013: the bundle carries the evidence the drawer needs, and the contexts carry it on.

These began as the RED tests `#354` landed, every one `xfail(strict=True)`; the strict
marker did its job and the markers came off when the supply landed. Each docstring
still says what the test waited for.

**The fixture publishes every section.** Built under the published triple so the
comparison family runs, the package carries all three record shapes `RRA-013` FR-102
distinguishes: a retained `Fact`, a retained `FactSeries`, and a derived analysis
figure retained by no record.

Plan: `docs/superpowers/plans/2026-09-03-rra-013-evidence-supply-plan.md`.
Authority: active `RRA-013` FR-102 to FR-108.
"""

from __future__ import annotations

import dataclasses
import hashlib
import inspect
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from khepri.rra import bundle as bundle_module
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.analysis import comparison
from khepri.rra.bundle import (
    BUNDLE_VERSION,
    SECTION_COMPARISON,
    FactPackage,
    ReportBundle,
)
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import build_cells, build_context
from khepri.rra.rendering.pdf import PdfReportRenderer
from khepri.rra.report_artifacts import MaterializedRenderer
from tests.rra003_contract_fixtures import TEST_CONTRACT, manifest_for_csv
from tests.test_rra006_pdf_surface import FakePrinter

HEADER = b"date,revenue,units,invoice_no,product\n"
START = date(2026, 1, 1)
#: Enough days for the comparison family to publish a prior window.
ROWS = [(f"{100 + 10 * index}.00", 2 + index % 3, "Alpha") for index in range(70)]
ARABIC_SCRIPT = re.compile(r"[\u0600-\u06ff]")

#: Exactly the keys an evidence entry may carry (FR-106). An allow-list, because the
#: visibility matrix's Internal tier is open-ended -- a session id, a storage key, a
#: lease -- and a denylist of the five names we thought of cannot see the sixth.
GOVERNED_EVIDENCE_KEYS = {
    "citation_id",
    "metric",
    "unit_kind",
    "formula_version",
    "precision",
    "inputs",
    "definition",
}


def package_for(rows: list[tuple[str, int, str]]) -> FactPackage:
    """One package built under the published triple, so every family publishes."""
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},{amount},{units},"
        f"INV-{index},{product}\n".encode()
        for index, (amount, units, product) in enumerate(rows)
    )
    content = HEADER + body
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    return build_fact_package(
        AdmittedInput(
            manifest=manifest_for_csv(content, TEST_CONTRACT),
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=TEST_CONTRACT,
        )
    )


@pytest.fixture(scope="module")
def package() -> FactPackage:
    return package_for(ROWS)


@pytest.fixture(scope="module")
def bundle(package: FactPackage) -> ReportBundle:
    built = ReportBundle.of(package)
    present = {entry.section_id for entry in built.sections if entry.reason is None}
    assert SECTION_COMPARISON in present, "the fixture must publish a derived section"
    return built


def evidence_by_citation(bundle: ReportBundle) -> dict[str, object]:
    records = getattr(bundle, "evidence", None)
    assert records is not None, "ReportBundle carries no evidence"
    return {record.citation_id: record for record in records}


def retained(package: FactPackage) -> dict[str, object]:
    return {
        record.citation_id: record
        for record in (*package.facts, *package.series, *package.comparisons)
    }


# --------------------------------------------------------------------------
# FR-102 -- one record per citation, shaped by what the record type carries
# --------------------------------------------------------------------------


def test_every_cited_figure_has_exactly_one_evidence_record(bundle: ReportBundle) -> None:
    """FR-102's extent assertion: the set of citations, not a sample of them."""
    cited = {figure.citation_id for figure in bundle.figures}
    assert cited, "no figures -- the fixture proves nothing"
    records = list(bundle.evidence)
    assert {record.citation_id for record in records} == cited
    assert len(records) == len(cited), "a citation carries more than one record"


def test_a_retained_fact_supplies_its_precision_inputs_and_version(
    bundle: ReportBundle, package: FactPackage
) -> None:
    """FR-102, row 1: a `Fact` states all three, and the evidence repeats them."""
    facts = {fact.citation_id: fact for fact in package.facts}
    assert facts
    evidence = evidence_by_citation(bundle)
    for citation_id, fact in facts.items():
        record = evidence[citation_id]
        assert record.precision == fact.precision
        assert record.inputs == tuple(fact.inputs)
        assert record.formula_version == fact.formula_version
        assert record.metric == fact.metric and record.unit_kind == fact.unit_kind


def test_a_retained_series_has_no_inputs_and_its_own_version(
    bundle: ReportBundle, package: FactPackage
) -> None:
    """FR-102, row 2: `FactSeries` has no `inputs` field; `None` is the governed absence."""
    assert package.series, "the fixture carries no series"
    evidence = evidence_by_citation(bundle)
    for entry in package.series:
        record = evidence[entry.citation_id]
        assert record.inputs is None, "inputs were invented for a series record"
        assert record.precision == entry.precision
        assert record.formula_version == entry.formula_version


def test_a_retained_comparison_has_no_inputs_and_its_own_version(
    bundle: ReportBundle, package: FactPackage
) -> None:
    """FR-102, row 2 for the other retained aggregate (`#354` review).

    A retained `FactComparison` is a stored record with its own precision and version
    and no `inputs` field. Without this test an implementation could treat every
    retained comparison as derived -- `None` precision, a family version -- and still
    satisfy the extent test, which checks citation identifiers alone.
    """
    assert package.comparisons, "the fixture carries no retained comparison"
    evidence = evidence_by_citation(bundle)
    for entry in package.comparisons:
        record = evidence[entry.citation_id]
        assert record.inputs is None, "inputs were invented for a comparison record"
        assert record.precision == entry.precision
        assert record.formula_version == entry.formula_version
        assert record.formula_version != comparison.COMPARISON_FORMULA_VERSION, (
            "a retained comparison was given the derived family's version"
        )


def test_a_derived_figure_carries_its_family_version_and_absent_records(
    bundle: ReportBundle, package: FactPackage
) -> None:
    """FR-102, row 3, and the version trap check 1 of the plan names.

    A comparison figure is retained by no record: precision and inputs are `None`.
    Its version is the comparison family's -- not `package.formula_version`, which
    names the `RRA-004` package formula. The two constants differ on this tree, so
    the assertion cannot pass by coincidence.
    """
    derived = [
        figure
        for figure in bundle.figures
        if figure.section == SECTION_COMPARISON and figure.citation_id not in retained(package)
    ]
    assert derived, "no derived comparison figure -- the fixture proves nothing"
    assert package.formula_version != comparison.COMPARISON_FORMULA_VERSION
    evidence = evidence_by_citation(bundle)
    for figure in derived:
        record = evidence[figure.citation_id]
        assert record.precision is None and record.inputs is None
        assert record.formula_version == comparison.COMPARISON_FORMULA_VERSION


# --------------------------------------------------------------------------
# FR-103, FR-104, FR-105 -- sources, coverage once, identity
# --------------------------------------------------------------------------


def test_no_evidence_value_is_a_figure_value(bundle: ReportBundle) -> None:
    """FR-103/FR-106: the evidence says what a figure is made of, never what it measured."""
    stated = {figure.value for figure in bundle.figures if figure.value is not None}
    stated |= {text for figure in bundle.figures for text in figure.renderings.values()}
    assert stated
    for record in bundle.evidence:
        for value in dataclasses.asdict(record).values():
            assert value not in stated, f"evidence repeats a figure value: {value!r}"


def test_coverage_lives_in_the_identity_once_and_on_no_record(
    bundle: ReportBundle, package: FactPackage
) -> None:
    """FR-104/FR-105: coverage is bundle-level provenance, never attributed to a figure."""
    identity = bundle.identity
    assert identity.coverage_manifest_identity == package.coverage_manifest_identity
    assert tuple(identity.coverage_signatures) == tuple(
        signature.identity for signature in package.coverage_signatures
    )
    for record in bundle.evidence:
        assert not any(name.startswith("coverage") for name in dataclasses.asdict(record)), (
            "a per-citation record carries coverage"
        )


def test_a_coverage_only_difference_changes_the_bundle_id(package: FactPackage) -> None:
    """FR-105: two packages identical but for their coverage manifest are two reports."""
    other = dataclasses.replace(
        package, coverage_manifest_identity=f"{package.coverage_manifest_identity}-other"
    )
    assert other.facts == package.facts, "the variant changed more than coverage"
    assert ReportBundle.of(package).bundle_id != ReportBundle.of(other).bundle_id


def test_the_bundle_version_advanced_with_the_identity_shape(bundle: ReportBundle) -> None:
    """FR-105: the identity document gained two fields, so its version moves once."""
    assert BUNDLE_VERSION == "rra006.bundle.v8"
    document = bundle.identity.as_document()
    assert {"coverage_manifest_identity", "coverage_signatures"} <= set(document)
    assert document["bundle_version"] == BUNDLE_VERSION


def test_identical_packages_yield_identical_bundle_ids(package: FactPackage) -> None:
    """Determinism, which the identity change must preserve. Not RED: it holds today."""
    assert ReportBundle.of(package).bundle_id == ReportBundle.of(package).bundle_id


# --------------------------------------------------------------------------
# FR-106, FR-107 -- what reaches the templates, and on which surface
# --------------------------------------------------------------------------


@pytest.mark.parametrize("language", sorted(REQUIRED_LANGUAGES))
def test_the_audit_context_carries_evidence_and_coverage_in_both_languages(
    bundle: ReportBundle, language: str
) -> None:
    """FR-106: `evidence` keyed by citation with the language's definition; `coverage` once."""
    context = build_context(bundle, language, build_cells(bundle, language))
    audit = context["audit"]
    assert set(audit["evidence"]) == {figure.citation_id for figure in bundle.figures}
    definitions = [entry["definition"] for entry in audit["evidence"].values()]
    assert all(definitions), "an evidence entry carries no definition text"
    if language == LANGUAGE_ARABIC:
        assert all(ARABIC_SCRIPT.search(text) for text in definitions), (
            "the Arabic context carries a definition that is not Arabic"
        )
    coverage = audit["coverage"]
    assert set(coverage) == {"manifest_identity", "signatures"}
    assert coverage["manifest_identity"] == bundle.identity.coverage_manifest_identity


def test_the_business_context_carries_neither_key(bundle: ReportBundle) -> None:
    """FR-106's tier boundary: citation identifiers, versions and coverage are tier A."""
    context = build_context(bundle, LANGUAGE_ENGLISH, build_cells(bundle, LANGUAGE_ENGLISH))
    assert "evidence" in context["audit"], "the audit context carries no evidence -- RED"
    assert "evidence" not in context and "coverage" not in context


def test_evidence_carries_exactly_the_governed_keys(bundle: ReportBundle) -> None:
    """FR-106: no figure value and no Internal-tier field, proven by the exact key set."""
    context = build_context(bundle, LANGUAGE_ENGLISH, build_cells(bundle, LANGUAGE_ENGLISH))
    entries = context["audit"]["evidence"].values()
    assert entries
    for entry in entries:
        assert set(entry) == GOVERNED_EVIDENCE_KEYS, (
            f"evidence entry keys drifted: {sorted(set(entry) ^ GOVERNED_EVIDENCE_KEYS)}"
        )


def test_the_print_context_opens_the_drawer_and_the_web_does_not_carry_the_key(
    bundle: ReportBundle,
) -> None:
    """FR-107, read literally: the web MUST NOT set `evidence_open`, so the key is absent.

    A closed `<details>` prints collapsed, so the print surface sets it true. The
    placement template reads `evidence_open | default(false)`; that is its concern.
    """
    cells = build_cells(bundle, LANGUAGE_ENGLISH)
    web = build_context(bundle, LANGUAGE_ENGLISH, cells)
    assert "evidence_open" not in web, "the web surface sets evidence_open"
    printed = PdfReportRenderer(printer=FakePrinter())._context(bundle, LANGUAGE_ENGLISH, cells)
    assert printed["evidence_open"] is True, "the print surface leaves the drawer closed"


# --------------------------------------------------------------------------
# FR-108 -- the guard this slice must not trip
# --------------------------------------------------------------------------


def test_the_renderer_contract_and_pipeline_call_are_unchanged() -> None:
    """FR-108. Not RED: it holds today and must still hold when the supply lands.

    Read from the signature and the call site rather than asserted as a constant, so
    a widened contract fails here whatever name the new parameter is given.
    """
    parameters = list(inspect.signature(MaterializedRenderer.render_materialized).parameters)
    assert parameters == ["self", "bundle"], f"the renderer contract widened: {parameters}"
    pipeline = Path("src/khepri/rra/pipeline.py").read_text(encoding="utf-8")
    assert "self._renderer.render_materialized(bundle)" in pipeline, (
        "the pipeline no longer calls the renderer with the bundle alone"
    )
    assert not hasattr(bundle_module, "render_evidence"), "the bundle module grew a renderer"
