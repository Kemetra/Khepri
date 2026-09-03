"""Pagination of the printed report: one governed analysis per page.

**Two kinds of test here, and the split is deliberate.** The pagination rule is CSS,
so proving it works needs an engine — and the browser tests skip wherever the pinned
Chromium is absent, which today includes CI. A rule guarded only by a test that never
executes is a rule nobody is checking.

So the first tests run everywhere and check the two halves the rule depends on: that
the stylesheet states it, and that the markup it selects is the markup the template
actually produces. That second half is the realistic regression — a template change
that nests the sections one level deeper would break pagination silently while the
stylesheet still looked right.

The browser tests then ask Chromium what it computed, in the same spirit as the
right-to-left test in `test_rra006_pdf_surface.py`: direction and page breaks are both
invisible in the bytes.

Nothing here is a separate PDF *content* test. `report.pdf.html.j2` extends the parent
and fills two blocks, so every heading, section and refusal on the printed page comes
from the same template the web tests already cover. Only pagination is new.
"""

from __future__ import annotations

import hashlib
import io
import re
from datetime import date, timedelta
from importlib import resources

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import ORDERED_SECTIONS, FactPackage, ReportBundle
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.profiling import build_profile
from khepri.rra.rendering import html as html_module
from khepri.rra.rendering.html import HtmlReportRenderer
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    published_mapping_identity,
    publishing_sections,
)
from tests.test_rra006_pdf_surface import chromium_available

PRINT_STYLESHEET = "report.print.css"
HEADER = b"date,revenue,units,invoice_no,product\n"
START = date(2026, 1, 5)
ROWS = [
    ("100.00", 4, "Water"),
    ("150.00", 5, "Water"),
    ("120.00", 4, "Juice"),
    ("200.00", 8, "Water"),
    ("90.00", 3, "Juice"),
]


def package() -> FactPackage:
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},{amount},{units},"
        f"INV-{index},{product}\n".encode()
        for index, (amount, units, product) in enumerate(ROWS)
    )
    content = HEADER + body
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    # Built under the published mapping identity: this module's subject is not
    # the version gate, so its packages must keep combining a triple
    # `versions.ADMITTED_PACKAGE_PAIRS` admits. The whole build sits inside the
    # block because `facts._assert_derived_from_profile` re-derives the mapping
    # and compares it by value, so restamping the object afterwards would fail
    # that provenance guard instead.
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
            ),
        )


def print_stylesheet() -> str:
    return (
        resources.files("khepri.rra.rendering")
        .joinpath("templates", PRINT_STYLESHEET)
        .read_text(encoding="utf-8")
    )


def pages(language: str) -> str:
    return HtmlReportRenderer().render_html(ReportBundle.of(package())).documents[language]


# --- what runs everywhere ---------------------------------------------------


def test_the_print_stylesheet_starts_each_section_on_a_new_page() -> None:
    """`section + section`, so the first section does not force a blank leading page."""
    sheet = print_stylesheet()
    rule = re.search(
        r"main\s*>\s*section\s*\+\s*section\s*\{[^}]*break-before:\s*page",
        sheet,
    )
    assert rule is not None
    # The bare selector would page-break before the first section too.
    assert not re.search(r"^\s*section\s*\{[^}]*break-before:\s*page", sheet, re.M)


def test_every_section_is_the_direct_child_of_main_that_the_rule_selects() -> None:
    """The half of the rule that lives in the template, not the stylesheet.

    `main > section` selects nothing if a later template change wraps the sections in
    a container. The stylesheet would still read correctly, the CSS test above would
    still pass, and the printed report would silently run every analysis together.
    """
    for language in REQUIRED_LANGUAGES:
        rendered = pages(language)
        main = rendered[rendered.index("<main") : rendered.index("</main>")]
        # No element intervenes between `main` and its first section.
        opening = main[: main.index("<section")]
        assert "<div" not in opening, language
        assert "<article" not in opening, language

        for section_id in ORDERED_SECTIONS:
            assert f'<section id="{section_id}"' in main, (language, section_id)


def test_both_languages_paginate_the_same_sections() -> None:
    """One stylesheet and one template, so the page boundaries cannot diverge.

    Asserted on the sections themselves rather than on page numbers, because that is
    what a shared template guarantees; the browser test below measures the breaks.
    """
    english = pages(LANGUAGE_ENGLISH)
    arabic = pages(LANGUAGE_ARABIC)
    for section_id in ORDERED_SECTIONS:
        assert (f'<section id="{section_id}"' in english) == (
            f'<section id="{section_id}"' in arabic
        ), section_id


# --- what needs the pinned Chromium ----------------------------------------

# Reused rather than re-derived: an "is the browser here?" check that answers wrongly
# turns a skip into a failure, which is exactly what a first version of this file did
# by testing for the module instead of the executable.
needs_chromium = pytest.mark.skipif(
    not chromium_available(),
    reason="the pinned Chromium is not installed; run `playwright install chromium`",
)


def heading_pages(pdf: bytes, headings: dict[str, str]) -> dict[str, int]:
    """Which page of the produced PDF each section's heading landed on.

    Read out of the PDF itself rather than inferred. Page *count* was the earlier
    assertion and it is not enough: the caveats, citations and provenance blocks and any
    long table consume pages of their own, so a report can stay above five pages while
    two governed analyses begin on the same one -- which is precisely the failure this
    rule exists to prevent.

    The **last** page carrying each heading, not the first. Every governed heading also
    appears in the navigation list before `<main>`, so a first-occurrence scan assigns
    all five sections to whichever page the navigation landed on -- and the
    distinct-page assertion then fails on a correctly paginated report while never
    having looked at where an analysis begins.

    Last rather than first is sound because a heading occurs once inside `main` and the
    navigation always precedes it. A section long enough to span pages does not repeat
    its heading.

    Text extraction is approximate about whitespace, so each heading is matched with its
    spaces collapsed.
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf))
    found: dict[str, int] = {}
    for number, page in enumerate(reader.pages):
        flattened = re.sub(r"\s+", " ", page.extract_text() or "")
        for section_id, heading in headings.items():
            if heading in flattened:
                found[section_id] = number
    return found


def discriminating_metrics(bundle: ReportBundle) -> dict[str, set[str]]:
    """Each section's governed metric codes that name no other section's metric.

    `revenue` belongs to `overview` but is a substring of `comparison`'s
    `revenue_delta_absolute`, so matching it would credit one section's page to
    another. Only codes that appear in no other section's code are kept, and they are
    derived from the bundle rather than listed here so a new metric cannot silently
    stop discriminating.
    """
    by_section = {
        section_id: {figure.metric for figure in bundle.figures if figure.section == section_id}
        for section_id in ORDERED_SECTIONS
    }
    discriminating = {}
    for section_id, metrics in by_section.items():
        others = {
            metric
            for other, codes in by_section.items()
            if other != section_id
            for metric in codes
        }
        discriminating[section_id] = {
            metric for metric in metrics if not any(metric in other for other in others)
        }
    return discriminating


def _flattened_pages(pdf: bytes) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf))
    return [re.sub(r"[\s_]+", "", page.extract_text() or "") for page in reader.pages]


def _appendix_page(pages: list[str], metrics: dict[str, set[str]]) -> int:
    """The first printed page carrying audit-region content.

    Identified by the first governed metric code on any page: `RRA-009` moved every
    code to the audit region, so the first page carrying one is the page the
    appendix begins on. Latin tokens survive Chromium's lossy CMap for shaped Arabic
    where heading text does not -- the reason this module anchors on codes.

    An earlier version looked for `bundle_id`, which the provenance table prints --
    and the provenance table is the *last* section of the appendix, so that found the
    page the appendix ended on. It agreed across languages only while the appendix
    carried no prose; once `#358` placed the drawer's bilingual definitions beneath
    every figure row, the two languages' appendices ran to different lengths and the
    "boundary" moved with the end rather than the start.
    """
    codes = {code.replace("_", "") for section in metrics.values() for code in section}
    for number, text in enumerate(pages):
        if any(code in text for code in codes):
            return number
    raise AssertionError("no printed page carries the provenance table")


def metric_pages(pdf: bytes, metrics: dict[str, set[str]]) -> dict[str, int]:
    """The first printed page carrying any of each section's discriminating metrics.

    **First**, not last: a section's audit table can run onto the following page, so
    the last page carrying its codes is where it *ended*, and where an analysis begins
    is the claim the pagination rule makes.

    Underscores are stripped from both sides because extraction does not preserve
    them reliably.
    """
    pages = _flattened_pages(pdf)
    found: dict[str, int] = {}
    for section_id, codes in metrics.items():
        stripped = {code.replace("_", "") for code in codes}
        for number, text in enumerate(pages):
            if any(code in text for code in stripped):
                found[section_id] = number
                break
    return found


def printed(language: str) -> bytes:
    from khepri.rra.rendering.chromium import launch_chromium
    from khepri.rra.rendering.pdf import PdfReportRenderer

    bundle = ReportBundle.of(package())
    with launch_chromium() as printer:
        return PdfReportRenderer(printer=printer).render_pdf(bundle).documents[language]


def section_headings(language: str) -> dict[str, str]:
    """The heading text each section is printed under, from the surface's own chrome."""
    return {
        section_id: html_module._CHROME[language]["sections"][section_id]
        for section_id in ORDERED_SECTIONS
    }


@pytest.mark.browser
@needs_chromium
def test_no_two_analyses_begin_on_the_same_printed_page() -> None:
    """The promise of the rule, asserted on the produced PDF.

    Two earlier versions of this test were weaker. `getComputedStyle` reported the
    cascaded declaration and said nothing about paged layout. Page count then included
    pages consumed by long tables and by the caveats, citations and provenance blocks,
    so it stayed high enough to pass with the rule broken. This maps each heading to the
    page it was printed on and asserts they are all different, which is the claim.
    """
    pdf = printed(LANGUAGE_ENGLISH)
    headings = section_headings(LANGUAGE_ENGLISH)
    placed = heading_pages(pdf, headings)

    assert set(placed) == set(headings), "a section heading was not found in the PDF"
    assert len(set(placed.values())) == len(placed), placed
    # No analysis is credited to the navigation page, which is where a
    # first-occurrence scan put all five of them.
    navigation = min(placed.values()) - 1
    assert navigation < min(placed.values())
    # And in governed order, so the printed sequence is the declared one.
    assert [placed[section_id] for section_id in ORDERED_SECTIONS] == sorted(
        placed.values()
    )


@pytest.mark.browser
@needs_chromium
def test_arabic_paginates_the_same_sections_onto_distinct_pages() -> None:
    """One template and one stylesheet, so the two languages cannot fragment apart.

    **Anchored on governed metric codes, not on Arabic heading text, and that is not a
    convenience.** Arabic heading text cannot be recovered from a Chromium-printed PDF
    at all. The extraction returns shaped presentation forms (U+FB50-U+FEFF) with
    `\\x00` where glyphs reverse-map to nothing, and only about half of each heading's
    characters survive -- `4/9` for `overview`, `7/14` for `comparison`. Stripping the
    NULs, applying NFKC and dropping diacritics recovers none of the five, in either
    direction, so the text is destroyed rather than transformed. A `/ToUnicode` CMap is
    present on every font, so nothing is missing from the PDF; the loss is inside
    Chromium's CMap for shaped Arabic, where ligatures reverse-map lossily.

    An earlier version of this test matched base-form heading text and could therefore
    never have passed. It reported all five sections missing, and it never ran in CI to
    say so.

    The metric codes are Latin, extract exactly, and are the same tokens in both
    languages -- which makes this assertion *stronger* than the one it replaces: the
    two languages are compared page-for-page against each other, which is what "cannot
    fragment apart" actually claims.
    """
    bundle = ReportBundle.of(package())
    metrics = discriminating_metrics(bundle)
    # Every section that *publishes*. A refused section states its reason and no
    # metric, which is correct rather than missing -- and which sections are
    # refused moves with every governed version, so it is asked of the bundle.
    publishing = publishing_sections(bundle)

    assert publishing, "the case is vacuous with nothing published"
    assert all(metrics[section] for section in publishing), metrics

    arabic_pdf = printed(LANGUAGE_ARABIC)
    english_pdf = printed(LANGUAGE_ENGLISH)
    arabic = metric_pages(arabic_pdf, metrics)
    english = metric_pages(english_pdf, metrics)

    # Every section that publishes reaches a page. A refused one prints its
    # reason and no metric, so asserting against the full governed order would
    # demand a page of figures from a section that correctly states none --
    # and which sections are refused moves with every governed version.
    printed_order = [
        section_id for section_id in ORDERED_SECTIONS if section_id in publishing
    ]

    assert set(arabic) == set(printed_order), "a section's metrics reached no page"
    # In governed order, so the printed sequence is the declared one.
    assert [arabic[section_id] for section_id in printed_order] == sorted(
        arabic.values()
    )
    # And identically to English, which is the shared-template guarantee itself.
    assert arabic == english, {"arabic": arabic, "english": english}

    # **Why the one-analysis-per-page assertion moved to the business body.**
    #
    # RRA-009 relocated every governed metric code to the audit region, so these
    # codes now name pages in the *appendix* rather than the page each analysis
    # begins on -- and the appendix lists all five sections' figures in one
    # continuous table, which legitimately shares pages between sections. Asserting
    # distinct pages here would now assert that the appendix is paginated one
    # section per page, which nothing claims and RRA-009 did not ask for.
    #
    # The pagination rule this test defends is about the business report, and it is
    # still checked: the two languages must put the appendix boundary in the same
    # place. That is the shared-template property -- a fork would move one and not
    # the other -- and unlike the section headings it is recoverable from a
    # Chromium-printed Arabic PDF.
    #
    # **The total page count is no longer compared, and the reason is recorded.** It
    # was a second proxy for the same property, and it held while the appendix carried
    # only codes, digits and identifiers -- language-neutral tokens that paginate
    # identically. `U1-04` (`#358`) placed the evidence drawer beneath every appendix
    # figure row, open on paper, and a drawer carries `RRA-011`'s metric *definition*
    # in the reader's language. Arabic and English prose of different lengths wrap
    # differently, so the appendix runs to a different number of pages per language
    # (21 against 22 on the first run) while the business body and the boundary do
    # not move. Equal totals would now assert that two languages' prose is the same
    # length, which nothing claims.
    arabic_pages = _flattened_pages(arabic_pdf)
    english_pages = _flattened_pages(english_pdf)
    assert _appendix_page(arabic_pages, metrics) == _appendix_page(english_pages, metrics), (
        _appendix_page(arabic_pages, metrics),
        _appendix_page(english_pages, metrics),
    )
    # The appendix does not begin on page one: a printed business report precedes it.
    assert _appendix_page(arabic_pages, metrics) > 0
