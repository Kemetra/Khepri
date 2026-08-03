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
import re
from datetime import date, timedelta
from importlib import resources

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import ORDERED_SECTIONS, FactPackage, ReportBundle
from khepri.rra.facts import build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import HtmlReportRenderer
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
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
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


def printed_page_count(pdf: bytes) -> int:
    """How many pages the produced PDF actually has.

    Counted from the page objects rather than from `/Count`, which appears on every
    node of the page tree. `[^s]` excludes `/Type /Pages`, the tree node itself.
    """
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def printed(language: str) -> bytes:
    from khepri.rra.rendering.chromium import launch_chromium
    from khepri.rra.rendering.pdf import PdfReportRenderer

    bundle = ReportBundle.of(package())
    with launch_chromium() as printer:
        return PdfReportRenderer(printer=printer).render_pdf(bundle).documents[language]


@pytest.mark.browser
@needs_chromium
def test_the_printed_pdf_has_a_page_for_every_section() -> None:
    """Measured on the produced PDF, not on the declaration that asks for it.

    An earlier version of this test read `getComputedStyle(node).breakBefore`, which
    reports the cascaded declaration and nothing about paged layout: Chromium can
    retain the declaration while fragmentation places two sections on one page, and
    that test would have passed with the promised pagination broken.

    Page *count* is the property this rule changes and a real PDF exposes. Each
    section forced onto a new page means at least one page per section, so the count
    collapsing is what a broken rule looks like from outside. Mapping each heading to
    its page number would say more, and needs a PDF text extractor this project does
    not depend on -- worth adding when something else needs one, not for this.
    """
    bundle = ReportBundle.of(package())

    assert printed_page_count(printed(LANGUAGE_ENGLISH)) >= len(bundle.sections)


@pytest.mark.browser
@needs_chromium
def test_arabic_paginates_identically() -> None:
    """One template and one stylesheet, so the two languages cannot fragment apart."""
    assert printed_page_count(printed(LANGUAGE_ARABIC)) == printed_page_count(
        printed(LANGUAGE_ENGLISH)
    )
