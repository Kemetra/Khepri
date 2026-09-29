"""A retail report as a customer's file produces it, rendered for screen and for paper.

SCRUM-21's first acceptance run found three presentation defects on this shape of file
(`docs/superpowers/plans/2026-09-29-scrum-21-u1-acceptance-evidence.md`, A1-A3): a
category and a branch column beside date, revenue, units and invoice. The smaller
fixtures elsewhere carry one product column and unique invoices, so they publish no
basket chart and no five-column breakdown, and every defect below was invisible to
them.

**The documents measured are the ones the PDF renderer prints.** `PdfReportRenderer`
hands each language's document to its `PagePrinter`; `Recording` keeps that document
while the real Chromium prints it, so a test measures the exact HTML and stylesheet
that became the PDF rather than a second rendering of its own.
"""

from __future__ import annotations

import hashlib
import random
import re
from datetime import date, timedelta
from functools import cache
from importlib import resources

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import ReportBundle
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.pdf import PagePrinter, PrintablePage
from tests.rra003_contract_fixtures import TEST_CONTRACT, manifest_for_csv

LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)

#: 96 CSS pixels to the inch, 25.4 millimetres to the inch.
_PX_PER_MM = 96 / 25.4
_A4_WIDTH_MM = 210


def retail_csv(rows: int = 160, *, seed: int = 21) -> bytes:
    """Two months of seeded sales across three categories and two branches.

    Paired invoice numbers give the basket analysis something to count, and the two
    months give the period comparison and growth their prior window.
    """
    rng = random.Random(seed)
    start = date(2026, 1, 5)
    lines = [b"date,revenue,units,invoice_no,category,branch\n"]
    for index in range(rows):
        day = start + timedelta(days=index % 55)
        category = rng.choice(("Beverages", "Snacks", "Dairy"))
        branch = rng.choice(("Cairo", "Giza"))
        lines.append(
            f"{day.isoformat()},{rng.randint(1000, 30000) / 100:.2f},{rng.randint(1, 9)},"
            f"INV-{index // 2},{category},{branch}\n".encode()
        )
    return b"".join(lines)


@cache
def retail_bundle() -> ReportBundle:
    """The bundle, built under the triple this build publishes so every section states."""
    content = retail_csv()
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    package = build_fact_package(
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
    return ReportBundle.of(package)


class Recording:
    """A `PagePrinter` that keeps each document it is handed, then prints it for real."""

    def __init__(self, inner: PagePrinter) -> None:
        self._inner = inner
        self.documents: list[str] = []

    def print_to_pdf(self, page: PrintablePage) -> bytes:
        self.documents.append(page.document)
        return self._inner.print_to_pdf(page)


@cache
def printed_documents() -> dict[str, str]:
    """Each language's document exactly as the PDF renderer printed it."""
    from khepri.rra.rendering.chromium import launch_chromium
    from khepri.rra.rendering.pdf import PdfReportRenderer

    with launch_chromium() as printer:
        recording = Recording(printer)
        PdfReportRenderer(printer=recording).render_pdf(retail_bundle())
    by_language = {_language_of(document): document for document in recording.documents}
    assert set(by_language) == set(LANGUAGES), sorted(by_language)
    return by_language


@cache
def web_documents() -> dict[str, str]:
    """Each language's web report, the surface a reader opens in place."""
    return dict(HtmlReportRenderer().render_html(retail_bundle()).documents)


def a4_content_width_px() -> int:
    """The printable measure, read from the print sheet's own `@page` rule.

    Read rather than restated, so a change to the page margins moves this with it
    instead of leaving a test measuring a page the renderer no longer prints.
    """
    sheet = (
        resources.files("khepri.rra.rendering")
        .joinpath("templates", "report.print.css")
        .read_text(encoding="utf-8")
    )
    page_rule = re.search(r"@page\s*\{(?P<body>[^}]*)\}", sheet)
    assert page_rule is not None, "report.print.css states no @page rule"
    body = page_rule.group("body")
    assert re.search(r"size:\s*A4\s*;", body), "the print sheet no longer prints A4"
    margin = re.search(r"margin:\s*(?P<block>[\d.]+)mm\s+(?P<inline>[\d.]+)mm\s*;", body)
    assert margin is not None, "the @page margin is not `<block>mm <inline>mm`"
    inline_mm = float(margin.group("inline"))
    return round((_A4_WIDTH_MM - 2 * inline_mm) * _PX_PER_MM)


def _language_of(document: str) -> str:
    match = re.search(r'<html[^>]*\blang="(?P<lang>[a-z]+)"', document)
    assert match is not None, "a printed document declares no language"
    return match.group("lang")
