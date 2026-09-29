"""`RRA-018`: the governed report is read in place, names what it refused, and reaches its evidence.

Authority: active `RRA-018` (merged `149ce11`, `#626`), FR-240 to FR-254, and its §Verification.

**Expectations are written out, not derived.** Every name and header below is a literal, so a
defect in the code that composes it cannot also compose the expectation. The golden package's
nine refusals are the ones `test_issue531_bundle_refusals.py` pins, stated independently here.

**The golden bundle cannot prove grouping on its own.** Its nine refusals record no input, so
all nine resolve to one sentence, and every entry lands in one group. The grouping cases
therefore replace the bundle's refusals with identical, partially shared, and fully distinct
prose, and with a refusal that recorded its input (`#560`'s path, which names the column).
Replacing them also makes the bundle's refusals differ from its package's, so a renderer that
read the package instead of the bundle (`#531`: "must not bypass `RenderableBundle`") fails.
"""

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from khepri.rra.bundle import ReportBundle
from khepri.rra.facts import RefusedResult
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering import refused_results, wording
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.pdf import PdfReportRenderer
from tests.rra_workbooks import read
from tests.test_rra006_bundle import package
from tests.test_rra006_pdf_surface import FakePrinter

LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)
REFUSED = "required_input_unavailable"

#: The golden package's refusals in package order, and what each is called on the page.
GOLDEN_NAMES = {
    LANGUAGE_ENGLISH: (
        ("cost", "Cost of goods sold"),
        ("discount", "Discounts given"),
        ("gross_margin", "Gross margin"),
        ("gross_profit", "Gross profit"),
        ("returns", "Returns"),
        ("revenue_by_channel", "Revenue — Sales channel"),
        ("revenue_by_product", "Revenue — Product"),
        ("units_by_channel", "Units sold — Sales channel"),
        ("units_by_product", "Units sold — Product"),
    ),
    LANGUAGE_ARABIC: (
        ("cost", "تكلفة المبيعات"),
        ("discount", "الخصومات الممنوحة"),
        ("gross_margin", "هامش الربح الإجمالي"),
        ("gross_profit", "إجمالي الربح"),
        ("returns", "المرتجعات"),
        ("revenue_by_channel", "الإيرادات — قناة البيع"),
        ("revenue_by_product", "الإيرادات — المنتج"),
        ("units_by_channel", "الوحدات المبيعة — قناة البيع"),
        ("units_by_product", "الوحدات المبيعة — المنتج"),
    ),
}

#: The one sentence every golden refusal resolves to: no input was recorded (`#575`).
GOLDEN_PROSE = (
    "This analysis — not available. The figures this analysis needs are not present in the "
    "file. The rest of the review is unaffected. Include the missing column in your export "
    "and this becomes available."
)


def _golden() -> ReportBundle:
    return ReportBundle.of(package())


def _with(*refusals: RefusedResult) -> ReportBundle:
    return replace(_golden(), refusals=refusals)


def _html(bundle: ReportBundle) -> tuple[dict[str, str], dict[str, str]]:
    surface = HtmlReportRenderer().render_html(bundle)
    return surface.documents, surface.evidence


def _pdf_html(bundle: ReportBundle) -> dict[str, str]:
    printer = FakePrinter()
    PdfReportRenderer(printer=printer).render_pdf(bundle)
    return printer.printed


def _region(document: str) -> str | None:
    found = re.search(
        r'<section[^>]*data-component="refused-results".*?</section>', document, re.DOTALL
    )
    return None if found is None else found.group(0)


def _groups(region: str) -> list[tuple[str, list[str]]]:
    """Each group's sentence and the names listed under it, in document order."""
    groups = re.findall(
        r'<div class="refused-results__group">\s*<p>(.*?)</p>\s*<ul>(.*?)</ul>',
        region,
        re.DOTALL,
    )
    return [
        (prose.strip(), [name.strip() for name in re.findall(r"<li>(.*?)</li>", names)])
        for prose, names in groups
    ]


# --- FR-246 / FR-247: every refused result named, its reason stated once --------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_golden_refusals_are_named_in_package_order_under_their_one_sentence(
    language: str,
) -> None:
    documents, _ = _html(_golden())
    region = _region(documents[language])
    assert region is not None, "the golden bundle refuses nine results and shows no region"

    groups = _groups(region)

    assert [names for _, names in groups] == [[name for _, name in GOLDEN_NAMES[language]]]
    if language == LANGUAGE_ENGLISH:
        assert groups[0][0] == GOLDEN_PROSE


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_printed_report_names_the_same_refusals(language: str) -> None:
    region = _region(_pdf_html(_golden())[language])
    assert region is not None
    assert [names for _, names in _groups(region)] == [[name for _, name in GOLDEN_NAMES[language]]]


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_composed_breakdown_carries_its_dimension_so_it_cannot_read_as_the_total(
    language: str,
) -> None:
    """`revenue_by_channel` named "Revenue" would tell the reader revenue was refused."""
    region = _region(_html(_golden())[0][language])
    assert region is not None
    listed = [name for _, names in _groups(region) for name in names]
    total = wording.business_metric_name("revenue", language)

    assert total not in listed
    assert all(" — " in name for name in listed if name.startswith(total))


def test_identical_prose_is_stated_once_above_every_name_it_covers() -> None:
    bundle = _with(
        RefusedResult(metric="gross_margin", reason=REFUSED),
        RefusedResult(metric="gross_profit", reason=REFUSED),
    )
    groups = _groups(_region(_html(bundle)[0][LANGUAGE_ENGLISH]) or "")

    assert groups == [(GOLDEN_PROSE, ["Gross margin", "Gross profit"])]


def test_partially_shared_prose_keeps_the_distinct_sentence_apart() -> None:
    bundle = _with(
        RefusedResult(metric="gross_margin", reason=REFUSED),
        RefusedResult(metric="cost", reason=REFUSED, input="cost"),
        RefusedResult(metric="gross_profit", reason=REFUSED),
    )
    groups = _groups(_region(_html(bundle)[0][LANGUAGE_ENGLISH]) or "")

    assert [names for _, names in groups] == [
        ["Gross margin", "Gross profit"],
        ["Cost of goods sold"],
    ]
    assert groups[0][0] == GOLDEN_PROSE
    assert groups[0][0] != groups[1][0]


def test_fully_distinct_prose_gives_one_group_per_refusal() -> None:
    bundle = _with(
        RefusedResult(metric="discount", reason="incomplete_column_coverage", input="discount"),
        RefusedResult(metric="revenue_by_period", reason="reconciliation_failed"),
    )
    groups = _groups(_region(_html(bundle)[0][LANGUAGE_ENGLISH]) or "")

    assert [names for _, names in groups] == [["Discounts given"], ["Revenue — Period"]]
    assert len({prose for prose, _ in groups}) == 2


def test_a_refusal_that_recorded_its_input_takes_the_sentence_naming_the_column() -> None:
    """`#560` item 2: the recorded input is named by its journey label."""
    bundle = _with(RefusedResult(metric="gross_margin", reason=REFUSED, input="cost"))
    groups = _groups(_region(_html(bundle)[0][LANGUAGE_ENGLISH]) or "")

    assert groups == [
        (
            "Gross margin is not shown — the file does not contain Cost. The other figures "
            "in this section are unaffected.",
            ["Gross margin"],
        )
    ]


def test_the_region_reads_the_bundle_and_not_the_package_it_came_from() -> None:
    bundle = _with(RefusedResult(metric="gross_margin", reason=REFUSED))
    region = _region(_html(bundle)[0][LANGUAGE_ENGLISH]) or ""

    assert "Gross margin" in region
    assert "Cost of goods sold" not in region, "a refusal only the package carries was shown"


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_bundle_with_no_refusals_renders_no_region(language: str) -> None:
    documents, evidence = _html(_with())

    assert _region(documents[language]) is None
    assert 'data-component="refused-results"' not in evidence[language]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_business_page_never_shows_a_raw_refusal_code(language: str) -> None:
    document = _html(_golden())[0][language]
    region = _region(document) or ""

    for code, _ in GOLDEN_NAMES[language]:
        assert f">{code}<" not in document
        assert code not in region
    assert REFUSED not in document


# --- FR-248: the quality summary still counts sections ---------------------------------------


def test_the_quality_summary_counts_sections_not_refused_results() -> None:
    document = _html(_golden())[0][LANGUAGE_ENGLISH]
    summary = re.search(r'data-component="quality-summary".*?</dl>', document, re.DOTALL)
    assert summary is not None
    counts = re.findall(r"<dd>(\d+)</dd>", summary.group(0))

    # The golden Overview answers with caveats; the other four families refuse. Nine refused
    # *results* must not move these counts, which are counts of sections (`RRA-012` FR-092).
    assert counts == ["0", "1", "4"], "sections are counted, not refused results"


# --- FR-249: the audit region states the codes -------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_evidence_surface_lists_the_raw_codes_in_package_order(language: str) -> None:
    _, evidence = _html(_golden())
    table = re.search(
        r'<section id="evidence-refusals".*?</section>', evidence[language], re.DOTALL
    )
    assert table is not None
    rows = re.findall(
        r"<tr>\s*<th scope=\"row\"><code>([^<]+)</code></th>\s*<td><code>([^<]+)</code></td>",
        table.group(0),
    )

    assert rows == [(code, REFUSED) for code, _ in GOLDEN_NAMES[language]]


def test_the_evidence_surface_states_a_recorded_input() -> None:
    bundle = _with(RefusedResult(metric="gross_margin", reason=REFUSED, input="cost"))
    table = re.search(
        r'<section id="evidence-refusals".*?</section>', _html(bundle)[1]["en"], re.DOTALL
    )
    assert table is not None
    assert "<code>cost</code>" in table.group(0)


# --- FR-250: the workbook agrees ---------------------------------------------------------------


def _limitations(bundle: ReportBundle, language: str) -> list[list[str]]:
    workbook = read(ExcelSurfaceRenderer()._build(bundle))
    name = {"en": "Data Limitations", "ar": "حدود البيانات"}[language]
    return workbook.cells[name]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_limitations_sheet_names_every_refused_result(language: str) -> None:
    texts = [cell for row in _limitations(_golden(), language) for cell in row if cell]

    for _, name in GOLDEN_NAMES[language]:
        assert name in texts, name


def test_the_limitations_sheet_states_the_shared_sentence_once() -> None:
    texts = [cell for row in _limitations(_golden(), LANGUAGE_ENGLISH) for cell in row]

    assert texts.count(GOLDEN_PROSE) == 1


# --- FR-246 guard: every refusable code names itself, distinctly -----------------------------


def test_every_refusable_code_composes_a_distinct_name_in_every_language() -> None:
    assert refused_results.REFUSABLE_RESULT_CODES, "an empty governed set makes this vacuous"
    assert "revenue_by_period" in refused_results.REFUSABLE_RESULT_CODES
    for language in LANGUAGES:
        names = [
            refused_results.refused_result_name(code, language)
            for code in sorted(refused_results.REFUSABLE_RESULT_CODES)
        ]
        assert len(set(names)) == len(names), language


def test_the_guard_fails_when_a_breakdown_has_no_qualifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trimmed = {language: {} for language in wording.BREAKDOWN_QUALIFIERS}
    monkeypatch.setattr(wording, "BREAKDOWN_QUALIFIERS", trimmed)

    with pytest.raises(RuntimeError, match="refused result"):
        refused_results.assert_refused_result_names_complete()


def test_the_guard_fails_when_two_codes_would_read_the_same(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collided = {
        language: {"period": wording.column_label("product", language)}
        for language in wording.BREAKDOWN_QUALIFIERS
    }
    monkeypatch.setattr(wording, "BREAKDOWN_QUALIFIERS", collided)

    with pytest.raises(RuntimeError, match="refused result"):
        refused_results.assert_refused_result_names_complete()


def test_an_ungoverned_code_is_refused_rather_than_rendered() -> None:
    with pytest.raises(KeyError):
        refused_results.refused_result_name("revenue_by_weather", LANGUAGE_ENGLISH)


# --- FR-244: header metadata is a closed set ---------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_header_carries_only_title_disclosure_reference_and_quality(language: str) -> None:
    document = _html(_golden())[0][language]
    header = re.search(r"<header>(.*?)</header>", document, re.DOTALL)
    assert header is not None
    opening = re.findall(r"<(h1|p|dl)\b([^>]*)>", header.group(1))

    assert [tag for tag, _ in opening] == ["h1", "p", "p", "dl"]
    classes = [re.search(r'class="([^"]+)"', attrs) for _, attrs in opening[1:]]
    assert [found.group(1) if found else None for found in classes] == [
        "disclosure",
        "report-reference",
        "quality-summary",
    ]
    reference = re.search(r'<p class="report-reference">(.*?)</p>', header.group(1))
    assert reference is not None
    assert re.search(r"\b[0-9A-F]{8}\b", reference.group(1))


# --- FR-245: the index states each section's state -------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_index_lists_the_sections_in_governed_order_with_their_badges(language: str) -> None:
    document = _html(_golden())[0][language]
    nav = re.search(r"<nav\b.*?</nav>", document, re.DOTALL)
    assert nav is not None
    entries = re.findall(
        r'<li><a href="#([a-z]+)">[^<]*</a>\s*<span data-component="status-badge" '
        r'class="badge badge--([a-z]+)">',
        nav.group(0),
    )

    assert entries == [
        ("overview", "present"),
        ("comparison", "refused"),
        ("concentration", "refused"),
        ("growth", "refused"),
        ("basket", "refused"),
    ]
    assert "<td" not in nav.group(0) and 'class="figure' not in nav.group(0)


# --- FR-251 to FR-253: summary, detail, evidence ---------------------------------------------


_SECTION = re.compile(
    r'<section id="(overview|comparison|concentration|growth|basket)".*?</section>', re.DOTALL
)


def _sections(document: str) -> dict[str, str]:
    return {match.group(1): match.group(0) for match in _SECTION.finditer(document)}


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_present_section_links_to_its_own_evidence_row(language: str) -> None:
    documents, evidence = _html(_golden())
    sections = _sections(documents[language])
    assert set(sections) == {"overview", "comparison", "concentration", "growth", "basket"}

    for section_id, markup in sections.items():
        links = re.findall(r'data-component="section-evidence-link"[^>]*href="([^"]+)"', markup)
        if section_id == "overview":
            assert links == [f"../evidence/{language}#evidence-section-{section_id}"]
            assert f'id="evidence-section-{section_id}"' in evidence[language]
        else:
            assert links == [], f"the refused {section_id} section links to evidence"


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_section_row_on_the_evidence_surface_is_an_anchor(language: str) -> None:
    _, evidence = _html(_golden())
    for section_id in ("overview", "comparison", "concentration", "growth", "basket"):
        assert f'id="evidence-section-{section_id}"' in evidence[language], section_id


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_business_page_embeds_no_route_host_or_citation_in_a_link(language: str) -> None:
    hrefs = re.findall(r'href="([^"]+)"', _html(_golden())[0][language])

    assert hrefs
    assert not [href for href in hrefs if "/api/" in href or "://" in href]
    assert not [href for href in hrefs if "citation" in href]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_evidence_surface_leads_back_to_its_report(language: str) -> None:
    _, evidence = _html(_golden())
    links = re.findall(
        r'data-component="report-return-link"[^>]*href="([^"]+)"', evidence[language]
    )

    assert links == [f"../web/{language}"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_printed_report_carries_neither_cross_surface_link(language: str) -> None:
    printed = _pdf_html(_golden())[language]

    assert "../evidence/" not in printed
    assert "../web/" not in printed
    assert 'data-component="section-evidence-link"' not in printed
    assert 'data-component="report-return-link"' not in printed
    assert 'href="#overview"' in printed, "in-page anchors stay in the PDF (FR-253)"


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_evidence_link_says_which_section_it_opens(language: str) -> None:
    """FR-254: a list of links reading "Evidence" five times tells a screen reader nothing."""
    document = _html(_golden())[0][language]
    link = re.search(
        r'<a data-component="section-evidence-link"[^>]*>(.*?)</a>', document, re.DOTALL
    )
    assert link is not None
    heading = wording.SECTION_HEADINGS[language]["overview"]

    assert heading in link.group(1)


# --- FR-254: every label is chrome in both languages -----------------------------------------


def test_the_new_labels_are_component_chrome_in_both_languages() -> None:
    for key in ("refused_results", "section_evidence", "back_to_report"):
        english = wording.COMPONENT_CHROME[LANGUAGE_ENGLISH][key]
        arabic = wording.COMPONENT_CHROME[LANGUAGE_ARABIC][key]
        assert english and arabic and english != arabic, key


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_region_is_a_landmark_named_by_its_heading(language: str) -> None:
    region = _region(_html(_golden())[0][language]) or ""
    labelled = re.search(r'aria-labelledby="([^"]+)"', region)
    assert labelled is not None
    heading = re.search(rf'<h2 id="{labelled.group(1)}">([^<]+)</h2>', region)

    assert heading is not None
    assert heading.group(1) == wording.COMPONENT_CHROME[language]["refused_results"]
