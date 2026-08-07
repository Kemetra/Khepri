"""RRA-009: the business report and separated audit-evidence region."""

from __future__ import annotations

from dataclasses import replace

import pytest

from khepri.rra.bundle import ReportBundle
from khepri.rra.narrative import LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering.html import (
    HtmlReportRenderer,
    HtmlSurface,
    build_cells,
    build_context,
)
from tests.test_rra006_html_sections import ROWS, package_for

Rows = list[tuple[str, int, str]]


def _bundle(rows: Rows | None = None) -> ReportBundle:
    return ReportBundle.of(package_for(ROWS if rows is None else rows))


def _surface(rows: Rows | None = None) -> HtmlSurface:
    return HtmlReportRenderer().render_html(_bundle(rows))


def _context(language: str = LANGUAGE_ENGLISH) -> dict[str, object]:
    bundle = _bundle()
    return build_context(bundle, language, build_cells(bundle, language))


def test_evidence_is_published_for_every_governed_language() -> None:
    surface = _surface()

    assert set(surface.evidence) == set(REQUIRED_LANGUAGES)


def test_evidence_is_non_empty_for_every_language() -> None:
    surface = _surface()

    for language in REQUIRED_LANGUAGES:
        assert surface.evidence[language].strip()


def test_documents_still_publish_exactly_two_languages() -> None:
    surface = _surface()

    assert set(surface.documents) == set(REQUIRED_LANGUAGES)


def test_evidence_refuses_a_missing_governed_language() -> None:
    surface = _surface()

    with pytest.raises(ValueError, match="governed languages in evidence"):
        replace(
            surface,
            evidence={LANGUAGE_ENGLISH: surface.evidence[LANGUAGE_ENGLISH]},
        )


def test_evidence_refuses_an_empty_document() -> None:
    surface = _surface()
    evidence = {**surface.evidence, LANGUAGE_ENGLISH: ""}

    with pytest.raises(ValueError, match=r"evidence\[en\] is required"):
        replace(surface, evidence=evidence)


def test_audit_context_carries_every_region() -> None:
    audit = _context()["audit"]

    assert set(audit) == {
        "figures",
        "sections",
        "caveats",
        "citations",
        "passages",
        "provenance",
    }


def test_audit_figures_cover_every_bundle_figure() -> None:
    bundle = _bundle()
    context = build_context(
        bundle,
        LANGUAGE_ENGLISH,
        build_cells(bundle, LANGUAGE_ENGLISH),
    )

    audited = {cell.figure_id for cell in context["audit"]["figures"]}
    assert audited == {figure.figure_id for figure in bundle.figures}


def test_audit_caveats_equal_the_bundle_caveats() -> None:
    bundle = _bundle()
    context = build_context(
        bundle,
        LANGUAGE_ENGLISH,
        build_cells(bundle, LANGUAGE_ENGLISH),
    )

    audited = {entry["code"] for entry in context["audit"]["caveats"]}
    assert audited == {caveat.code for caveat in bundle.caveats}
