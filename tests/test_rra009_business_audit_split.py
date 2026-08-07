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


def test_the_business_body_shows_no_figure_or_citation_identifier() -> None:
    """RRA-009 allows exactly one identifier in the business region, and it is
    the short report reference -- not a figure id and not a citation id."""
    bundle = _bundle()
    surface = HtmlReportRenderer().render_html(bundle)
    for language in REQUIRED_LANGUAGES:
        visible = _visible_text(surface.documents[language])
        for figure in bundle.figures:
            assert figure.figure_id not in visible, (figure.figure_id, language)
            assert figure.citation_id not in visible, (figure.citation_id, language)


def test_the_business_body_carries_no_data_figure_id_attribute() -> None:
    """Removed from the markup, not merely from the visible text.

    `presentation-visibility-matrix.md` §A.2 draws the rule: an identifier may
    survive in an attribute only where the reader uses it. An `id=` anchor is
    navigation and survives; `data-figure-id` was a hook for tooling, and a
    business report is not a tooling surface.
    """
    surface = _surface()
    for language in REQUIRED_LANGUAGES:
        assert "data-figure-id" not in surface.documents[language], language


def test_the_business_body_names_rows_in_business_language() -> None:
    visible = _visible_text(_surface().documents[LANGUAGE_ENGLISH])
    assert "Revenue" in visible


def test_the_business_body_carries_the_report_reference() -> None:
    """The one identifier the business region is allowed, and it is short enough
    to read aloud -- which a digest is not."""
    bundle = _bundle()
    surface = HtmlReportRenderer().render_html(bundle)
    reference = bundle.bundle_id[:8].upper()
    for language in REQUIRED_LANGUAGES:
        assert reference in _visible_text(surface.documents[language]), language


def test_the_business_body_points_at_the_evidence() -> None:
    """A report that never mentions its own evidence cannot be forwarded to an
    auditor by someone who does not know the evidence exists."""
    surface = _surface()
    for language in REQUIRED_LANGUAGES:
        assert "colophon" in surface.documents[language], language


def test_business_figures_are_the_strings_the_bundle_produced() -> None:
    """Relocation must not become reformatting. `html.py` leaves the renderer no
    `Decimal` to format; this asserts the string survived the restructure."""
    bundle = _bundle()
    surface = HtmlReportRenderer().render_html(bundle)
    for language in REQUIRED_LANGUAGES:
        visible = _visible_text(surface.documents[language])
        for figure in bundle.figures:
            assert figure.renderings[language] in visible, (figure.figure_id, language)


def test_the_business_body_drops_the_audit_only_column_headers() -> None:
    """The six-column identifier table becomes a two-column business statement.

    Asserted on the `<th scope="col">` cells rather than on the visible text.
    A plain substring search over the rendered page reports a false positive: the
    governed Arabic disclosure contains `الإسناد` as ordinary prose, and that
    disclosure is immutable (`bundle.py` compares it in full), so the page is
    correct and a text search is the wrong instrument. What must be true is that
    no *column header* names an audit field.
    """
    from khepri.rra.rendering.html import _CHROME

    surface = _surface()
    for language in REQUIRED_LANGUAGES:
        business_headers = set(
            re.findall(r'<th scope="col">([^<]+)</th>', surface.documents[language])
        )
        evidence_headers = set(
            re.findall(r'<th scope="col">([^<]+)</th>', surface.evidence[language])
        )
        for key in ("metric", "kind", "unit", "citation"):
            heading = _CHROME[language][key]
            assert heading not in business_headers, (key, language)
            assert heading in evidence_headers, (key, language)
        # And the business table keeps exactly its two.
        assert business_headers == {
            _CHROME[language]["business_figure"],
            _CHROME[language]["value"],
        }, language


def _printed_html(language: str = LANGUAGE_ENGLISH) -> str:
    """The HTML the PDF printer would be handed, rendered without a browser.

    `pdf.py` is deliberately verifiable with no Chromium -- rendering is expressed
    against a `PagePrinter` port precisely so the surface can be asserted on with
    a fake and no external binary. This asserts on the markup rather than on bytes.
    """
    from khepri.rra.rendering.html import build_environment
    from khepri.rra.rendering.pdf import PDF_SURFACE_VERSION, PDF_TEMPLATE_NAME

    bundle = _bundle()
    template = build_environment().get_template(PDF_TEMPLATE_NAME)
    context = build_context(
        bundle,
        language,
        build_cells(bundle, language),
        extra_provenance={"pdf_surface_version": PDF_SURFACE_VERSION},
    )
    context["print_stylesheet_name"] = "report.print.css"
    context["fonts"] = []
    return template.render(context)


def test_the_printed_report_carries_the_appendix() -> None:
    bundle = _bundle()
    printed = _printed_html()
    for figure in bundle.figures:
        assert figure.figure_id in printed, figure.figure_id


def test_the_printed_business_body_still_hides_identifiers() -> None:
    """The appendix carries the identifiers and the body does not, in one
    document -- so this is the assertion that the separation is real rather than
    a matter of which file the reader happened to open."""
    printed = _printed_html()
    body = printed.split('id="appendix"')[0]
    assert "data-figure-id" not in body


def test_the_printed_appendix_carries_provenance() -> None:
    printed = _printed_html()
    appendix = printed.split('id="appendix"')[1]
    assert "bundle_id" in appendix
    assert "pdf_surface_version" in appendix


def test_the_web_report_carries_no_appendix() -> None:
    """The parent block stays empty on the screen surface: a web reader gets the
    separate evidence document instead, and rendering both would put the audit
    region inside the business page it was separated from."""
    surface = _surface()
    for language in REQUIRED_LANGUAGES:
        assert 'id="appendix"' not in surface.documents[language], language


def test_a_row_with_both_a_name_and_a_label_shows_both() -> None:
    """The defect this pins was found by an existing security test, not by this
    file, and it was a real one.

    An earlier version of the business table rendered `metric_name` in preference
    to `label`. Four cells in this fixture carry both -- two `basket_attach_rate`
    rows whose labels are `Water` and `Juice`, and the two `revenue_delta_*` rows
    whose label is the comparison window. Showing the name alone rendered two
    rows reading `Attach rate` with different numbers beside them, which is not a
    presentation choice but a misstatement, and it silently dropped the
    customer's own product name from the report.
    """
    bundle = _bundle()
    surface = HtmlReportRenderer().render_html(bundle)
    for language in REQUIRED_LANGUAGES:
        visible = _visible_text(surface.documents[language])
        for cell in build_cells(bundle, language):
            if cell.metric_name and cell.label:
                assert cell.metric_name in visible, (cell.metric, language)
                assert cell.label in visible, (cell.metric, cell.label, language)


def test_a_customer_label_reaches_the_business_body_escaped() -> None:
    """A bucket label is customer text and must survive into the business report,
    escaped rather than dropped -- absence would pass a naive injection check."""
    bundle = _bundle()
    surface = HtmlReportRenderer().render_html(bundle)
    labels = {cell.label for cell in build_cells(bundle, LANGUAGE_ENGLISH) if cell.label}
    visible = _visible_text(surface.documents[LANGUAGE_ENGLISH])
    for label in labels:
        assert label in visible, label


def test_no_internal_field_reaches_a_customer_surface() -> None:
    """RRA-009: an Internal field is rendered on no customer surface, including
    the audit region -- so unlike an Audit field it is not relocated at all.

    `presentation-visibility-matrix.md` §A.2 and §A.4 name two: the section
    `state` attribute and `narrative_state`. Both were emitted as `data-`
    attributes on the business page, which is invisible to a reader and therefore
    easy to leave behind -- the leak check reads visible text and would never have
    caught either.
    """
    bundle = _bundle(ROWS[:2])
    surface = HtmlReportRenderer().render_html(bundle)
    for language in REQUIRED_LANGUAGES:
        for document in (surface.documents[language], surface.evidence[language]):
            assert "data-narrative-state" not in document, language
            # The field name, not the value: `narrative_state` can be `refused`,
            # which is also the CSS class a refused section's prose carries.
            assert "narrative_state" not in document, language
            # `section.state` is Internal too, and this bundle carries both a
            # present and a refused section -- so `refused` reaching either
            # document would be the leak, and `present` likewise.
            for state in ("present", "refused"):
                assert f"<code>{state}</code>" not in document, (state, language)
    # And the refusal is still evidenced: the reason code is Audit-tier and stays.
    assert "prior_window_absent" in surface.evidence[LANGUAGE_ENGLISH]


def test_the_governed_disclosure_survives_verbatim() -> None:
    """Removing the attribute must not touch the prose beside it. `bundle.py`
    compares the disclosure in full and raises `disclosure_altered` on any edit,
    so this is the assertion that the removal was surgical."""
    bundle = _bundle()
    surface = HtmlReportRenderer().render_html(bundle)
    for language in REQUIRED_LANGUAGES:
        assert bundle.disclosure(language) in surface.documents[language], language
