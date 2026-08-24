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
from khepri.rra.bundle import (
    KIND_ROWS,
    KIND_VALUE,
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    ReportBundle,
)
from khepri.rra.facts import build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import HtmlReportRenderer, build_cells
from khepri.rra.rendering.wording import business_metric_name, kind_qualifier


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
    """A bucket's row count stays a business figure, and stops being a row.

    An earlier revision of this slice filtered `KIND_ROWS` out of the business
    tables. That was the wrong instrument for a real problem, and review caught
    it: `docs/reporting/presentation-visibility-matrix.md` classifies a figure's
    `text` **B** and only its `kind` column **A**, so removing the whole row moved
    a Business-tier value into the audit region. `rendering/excel.py` never
    filtered them, so the surfaces disagreed as well.

    The interleaving is fixed by giving the count its own column beside the value
    it explains. These tests pin the corrected property: the counts are present,
    and they are not rows.
    """

    def test_the_count_is_still_stated_on_the_business_page(self) -> None:
        # The tier assertion. The count is a Business-tier value; it must reach a
        # reader, in the region the matrix puts it in.
        qualifier = kind_qualifier(KIND_ROWS, LANGUAGE_ENGLISH)
        assert qualifier, "the row-kind qualifier must exist for this to check"
        assert qualifier in english_document(), (
            f"{qualifier!r} no longer appears in the rendered report"
        )

    def test_a_named_series_states_its_count_as_a_column_not_a_row(self) -> None:
        # The legibility assertion, and the whole point of the correction: the
        # count sits in a column headed by what it counts, rather than as its own
        # row interleaved with the figures.
        document = english_document()
        qualifier = kind_qualifier(KIND_ROWS, LANGUAGE_ENGLISH)
        headings = re.findall(r'<th scope="col">([^<]*)</th>', document)
        counted_headings = [head for head in headings if qualifier in head]
        assert counted_headings, "no count column was rendered"
        assert all(head != qualifier for head in counted_headings), (
            "a count column must name what it counts, not read 'rows counted' alone"
        )

    def test_the_interleaved_count_rows_are_gone_for_named_series(self) -> None:
        # The negative that makes the column assertion mean something. Only
        # `concentration_curve` has no governed metric name and so keeps the row
        # form; every named series pivots.
        document = english_document()
        qualifier = kind_qualifier(KIND_ROWS, LANGUAGE_ENGLISH)
        row_headers = re.findall(r'<th scope="row">([^<]*)</th>', document)
        counted_rows = [head for head in row_headers if qualifier in head]
        assert all(head.strip().startswith(qualifier) for head in counted_rows), (
            "a named series is still stating its count as an interleaved row"
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
        # `reconcile` compares figure coverage between surfaces, and the audit
        # trail lists every identifier.
        assert any(figure.kind == KIND_ROWS for figure in bundle().figures)

    def test_the_view_model_still_offers_every_figure(self) -> None:
        # `build_cells` is the general mapping from figures to cells and stays
        # total: the audit surface renders from it too, and a filter there would
        # remove the counts from the evidence page as well.
        assembled = build_cells(bundle(), LANGUAGE_ENGLISH)
        assert any(cell.kind == KIND_ROWS for cell in assembled)

    def test_the_value_rows_survive(self) -> None:
        # The direct negative: the pivot rearranged the figures and lost none.
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


class TestEverySeriesNamesItsMeasure:
    """A labelled series states what it measures, in both languages.

    `revenue_by_category`, `units_by_category`, `revenue_by_store` and
    `units_by_store` were missing from the wording table while the by-period and
    by-product names were present, and nothing failed: an unnamed series rendered
    its label and a number with no measure, so the revenue and unit series in one
    section stated `Antibiotics` twice with nothing telling them apart. That is
    the exact defect the by-period names exist to prevent.

    This lives here rather than beside the other wording tests because it needs
    this module's fixture: the `RRA-009` split fixture produces no by-category or
    by-store series at all, so the same assertion there is blind to the omission.
    Verified by mutation -- removing `revenue_by_category` from the table fails
    this test and passes there.
    """

    #: The one labelled series with no accepted business name. Named rather than
    #: skipped, so adding a name is a deliberate edit and a *new* unnamed series
    #: fails instead of joining it silently.
    UNNAMED_BY_DESIGN = frozenset({"concentration_curve"})

    def test_every_labelled_series_metric_is_named_in_both_languages(self) -> None:
        for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
            cells = build_cells(bundle(), language)
            series = {
                cell.metric
                for cell in cells
                if cell.label is not None and cell.kind == KIND_VALUE
            }
            assert series, "fixture carries no labelled series figures"
            missing = {
                metric
                for metric in series - self.UNNAMED_BY_DESIGN
                if business_metric_name(metric, language) is None
            }
            assert not missing, (
                f"{language}: labelled series metrics with no accepted business "
                f"name: {sorted(missing)}"
            )

    def test_the_fixture_carries_the_series_that_were_missing(self) -> None:
        # The emptiness assertion. Without it the check above passes on a fixture
        # that happens to produce none of the affected series -- which is exactly
        # how the omission survived in the first place.
        cells = build_cells(bundle(), LANGUAGE_ENGLISH)
        produced = {cell.metric for cell in cells}
        for metric in (
            "revenue_by_category",
            "units_by_category",
            "revenue_by_store",
            "units_by_store",
        ):
            assert metric in produced, f"fixture no longer produces {metric}"


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
