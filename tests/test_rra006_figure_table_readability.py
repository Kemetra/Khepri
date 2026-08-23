"""What the web report's figure tables show, and what belongs elsewhere.

Two defects, both visible on the first screen of a rendered report and neither
of them a formatting question.

**A row count is provenance, not a finding.** Every bucket figure emits a
`KIND_VALUE` and a `KIND_ROWS` pair, and both were rendered into the section
table -- so a five-month revenue series produced ten rows, alternating a figure
with the number of source rows behind it. On the report generated from a
1,467-row upload that put 39 `rows counted` rows in the reader's way. The counts
are not removed: `bundle.figures` still carries every one, the audit trail still
lists them, and `reconcile` still compares them. They stop being interleaved
with the findings.

**A caveat states itself once.** The section caveat list rendered one entry per
figure carrying the caveat rather than one per distinct caveat, so the
"comparison with an earlier period is not available" paragraph appeared twice in
the same block.

Both are checked on the *rendered document* rather than on the view model. A
test over `build_cells` would pass while the template printed the same cell
twice, and the defect being fixed is what the reader sees.
"""

from __future__ import annotations

import hashlib
import random
import re

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import KIND_ROWS, KIND_VALUE, LANGUAGE_ENGLISH, ReportBundle
from khepri.rra.facts import build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import HtmlReportRenderer, build_cells
from khepri.rra.rendering.wording import kind_qualifier


def _content() -> bytes:
    """A file with enough periods and buckets to produce the repeated rows.

    Generated rather than written out: the defect is one of *volume*, and a
    four-line fixture produces two `rows counted` rows, which is not a table a
    reader would complain about. Seeded so the figures are stable.
    """
    random.seed(11)
    rows = [b"transaction_date,net_sales,units_sold,invoice_no,category,branch,cogs\n"]
    products = ("Analgesics", "Antibiotics", "Vitamins", "Antacids")
    branches = ("Cairo-Maadi", "Cairo-Nasr", "Giza-Dokki")
    for index in range(240):
        month = (index % 5) + 1
        day = (index % 27) + 1
        rows.append(
            f"2026-{month:02d}-{day:02d},"
            f"{random.uniform(500, 2000):.2f},"
            f"{random.randint(1, 9)},"
            f"INV-{index // 2},"
            f"{products[index % len(products)]},"
            f"{branches[index % len(branches)]},"
            f"{random.uniform(200, 900):.2f}\n".encode()
        )
    return b"".join(rows)


CONTENT = _content()


def bundle() -> ReportBundle:
    profile = build_profile(
        content=CONTENT,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(CONTENT).hexdigest(),
    )
    mapping = build_mapping(profile)
    return ReportBundle.of(
        build_fact_package(
            content=CONTENT,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
        )
    )


def english_document() -> str:
    return HtmlReportRenderer().render_html(bundle()).documents[LANGUAGE_ENGLISH]


class TestARowCountIsNotAFinding:
    def test_the_rendered_table_shows_no_rows_counted_row(self) -> None:
        # The reader-facing assertion, on the document rather than the model.
        qualifier = kind_qualifier(KIND_ROWS, LANGUAGE_ENGLISH)
        assert qualifier, "the row-kind qualifier must exist for this to check"

        document = english_document()
        assert qualifier not in document, (
            f"{qualifier!r} still appears in the rendered report"
        )

    def test_the_fixture_would_have_produced_many_such_rows(self) -> None:
        # The emptiness assertion. Without this, the check above passes on a
        # bundle that happened to carry no row-count figures at all, and would
        # keep passing if the pair stopped being emitted upstream.
        counts = [
            figure for figure in bundle().figures if figure.kind == KIND_ROWS
        ]
        assert len(counts) > 20, (
            f"the fixture produced only {len(counts)} row-count figures, which is "
            "too few to demonstrate the defect"
        )

    def test_the_row_counts_are_still_carried_by_the_bundle(self) -> None:
        # Moved out of the table, not deleted. `reconcile` compares figure
        # coverage between surfaces, and the audit trail lists every identifier.
        assert any(figure.kind == KIND_ROWS for figure in bundle().figures)

    def test_the_view_model_still_offers_every_figure(self) -> None:
        # `build_cells` is the general mapping from figures to cells and stays
        # total: the audit surface renders from it too, and a filter there would
        # remove the counts from the evidence page as well.
        assembled = build_cells(bundle(), LANGUAGE_ENGLISH)
        assert any(cell.kind == KIND_ROWS for cell in assembled)

    def test_the_value_rows_survive(self) -> None:
        # The direct negative: the filter removed the counts and not the figures.
        document = english_document()
        values = [
            figure
            for figure in bundle().figures
            if figure.kind == KIND_VALUE and figure.section == "overview"
        ]
        assert values, "the fixture must produce overview value figures"
        shown = [
            figure
            for figure in values
            if figure.renderings[LANGUAGE_ENGLISH] in document
        ]
        assert len(shown) >= len(values) // 2, "value rows were removed with the counts"


class TestACaveatStatesItselfOnce:
    def test_no_section_caveat_paragraph_is_repeated(self) -> None:
        document = english_document()
        paragraphs = re.findall(r'<li>(.*?)</li>', document, re.S)
        caveat_text = [
            text.strip()
            for text in paragraphs
            if "not available" in text or "single period" in text
        ]
        duplicated = {
            text for text in caveat_text if caveat_text.count(text) > 1
        }
        assert not duplicated, f"caveat repeated verbatim: {duplicated}"
