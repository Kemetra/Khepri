"""RRA-009: the business report and separated audit-evidence region."""

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from khepri.rra.bundle import ReportBundle
from khepri.rra.facts import METRIC_REVENUE
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    REQUIRED_LANGUAGES,
)
from khepri.rra.rendering import wording
from khepri.rra.rendering.html import (
    HtmlReportRenderer,
    HtmlSurface,
    build_cells,
    build_context,
)
from tests.test_rra006_html_sections import ROWS, package_for

Rows = list[tuple[str, int, str]]

_DERIVED_ARABIC_NAMES = {
    "basket_items_per_transaction": "عدد الأصناف لكل عملية بيع",
    "basket_attach_rate": "نسبة عمليات البيع التي تتضمن المنتج أو الفئة",
    "concentration_top_decile_share": "حصة أعلى عُشر من المبيعات",
    "concentration_top_quartile_share": "حصة أعلى ربع من المبيعات",
    "concentration_distinct_values": "عدد المنتجات أو الفروع المحتسبة",
    "concentration_ranked_values": "المساهمة حسب الترتيب",
}


def _bundle(rows: Rows | None = None) -> ReportBundle:
    return ReportBundle.of(package_for(ROWS if rows is None else rows))


def _surface(rows: Rows | None = None) -> HtmlSurface:
    return HtmlReportRenderer().render_html(_bundle(rows))


def _context(language: str = LANGUAGE_ENGLISH) -> dict[str, object]:
    bundle = _bundle()
    return build_context(bundle, language, build_cells(bundle, language))


def _evidence(language: str = LANGUAGE_ENGLISH) -> str:
    return _surface().evidence[language]


def _visible_text(document: str) -> str:
    return re.sub(r"<[^>]+>", " ", document)


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


def test_figure_cells_carry_a_business_metric_name() -> None:
    cells = build_cells(_bundle(), LANGUAGE_ENGLISH)
    revenue = next(cell for cell in cells if cell.metric == METRIC_REVENUE)

    assert revenue.metric_name == "Revenue"


def test_business_metric_name_is_translated() -> None:
    cells = build_cells(_bundle(), LANGUAGE_ARABIC)
    revenue = next(cell for cell in cells if cell.metric == METRIC_REVENUE)

    assert revenue.metric_name == "الإيرادات"


def test_the_raw_metric_code_survives_on_the_cell() -> None:
    cells = build_cells(_bundle(), LANGUAGE_ENGLISH)

    assert all(cell.metric for cell in cells)


def test_every_row_has_something_to_be_called() -> None:
    for language in REQUIRED_LANGUAGES:
        for cell in build_cells(_bundle(), language):
            assert cell.metric_name or cell.label, (cell.metric, language)


def test_a_series_row_is_named_by_its_label_not_a_metric_name() -> None:
    cells = build_cells(_bundle(), LANGUAGE_ENGLISH)
    series = [cell for cell in cells if cell.metric == "revenue_by_period"]

    assert series, "fixture carries no revenue_by_period figure"
    assert all(cell.metric_name is None and cell.label for cell in series)


def test_a_labelless_derived_metric_is_named_from_the_derived_table() -> None:
    cells = build_cells(_bundle(), LANGUAGE_ENGLISH)
    for metric in (
        "basket_items_per_transaction",
        "concentration_top_decile_share",
        "concentration_top_quartile_share",
        "concentration_distinct_values",
        "concentration_ranked_values",
    ):
        matching = [cell for cell in cells if cell.metric == metric]
        assert matching, f"fixture carries no {metric} figure"
        assert all(cell.metric_name for cell in matching), metric


@pytest.mark.parametrize(("metric", "expected"), _DERIVED_ARABIC_NAMES.items())
def test_accepted_arabic_derived_metric_name(metric: str, expected: str) -> None:
    assert wording.business_metric_name(metric, LANGUAGE_ARABIC) == expected


def test_evidence_page_carries_every_figure_identifier() -> None:
    bundle = _bundle()
    rendered = _evidence()

    for figure in bundle.figures:
        assert figure.figure_id in rendered, figure.figure_id


def test_evidence_page_carries_every_citation_identifier() -> None:
    bundle = _bundle()
    rendered = _evidence()

    for citation in {figure.citation_id for figure in bundle.figures}:
        assert citation in rendered, citation


def test_evidence_page_carries_the_raw_reason_code() -> None:
    surface = _surface(ROWS[:2])

    assert "prior_window_absent" in surface.evidence[LANGUAGE_ENGLISH]


def test_business_page_states_a_refusal_as_customer_prose_not_a_code() -> None:
    surface = _surface(ROWS[:2])

    for language in REQUIRED_LANGUAGES:
        visible = _visible_text(surface.documents[language])
        assert "prior_window_absent" not in visible
        assert wording.refusal_message(
            "prior_window_absent",
            context="section",
            language=language,
        ) in visible


def test_business_page_states_every_caveat_as_customer_prose_not_a_code() -> None:
    bundle = _bundle()
    surface = HtmlReportRenderer().render_html(bundle)

    for language in REQUIRED_LANGUAGES:
        visible = _visible_text(surface.documents[language])
        for caveat in bundle.caveats:
            assert caveat.code not in visible
            assert wording.caveat_prose(caveat.code, language) in visible


def test_evidence_page_keeps_each_caveat_code_beside_customer_prose() -> None:
    bundle = _bundle()
    surface = HtmlReportRenderer().render_html(bundle)

    for language in REQUIRED_LANGUAGES:
        rendered = surface.evidence[language]
        visible = _visible_text(rendered)
        for caveat in bundle.caveats:
            assert caveat.code in rendered
            assert wording.caveat_prose(caveat.code, language) in visible


def test_evidence_page_carries_provenance() -> None:
    rendered = _evidence()

    assert "bundle_id" in rendered
    assert "html_surface_version" in rendered


def test_evidence_page_renders_in_both_languages() -> None:
    for language in REQUIRED_LANGUAGES:
        assert _evidence(language).strip()


def test_evidence_page_escapes_customer_labels() -> None:
    bundle = _bundle()
    labelled = next(figure for figure in bundle.figures if figure.label is not None)
    hostile = replace(labelled, label="<script>alert(1)</script>")
    figures = tuple(hostile if figure is labelled else figure for figure in bundle.figures)
    rendered = HtmlReportRenderer().render_html(
        replace(bundle, figures=figures)
    ).evidence[LANGUAGE_ENGLISH]

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<script>alert(1)</script>" not in rendered
