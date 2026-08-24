"""The shape of a repeated series in the web report's figure tables.

**The defect.** A section's cells were rendered as one row per cell, so a
five-period series carrying two metrics produced ten rows -- `Revenue — 2026-01`,
`Revenue — 2026-02`, … then `Units sold — 2026-01`, `Units sold — 2026-02`, …
each repeating the metric name and each stating one number. The 1,467-row report
put 107 rows in its Overview that way. A reader comparing revenue against units
for one month had to find two rows in different halves of the table.

**The shape instead.** One row per label, one column per metric:

    Period     Revenue        Units sold
    2026-01     58,848.18            253
    2026-02     60,432.28            261

Twenty stacked rows become five, and the comparison a reader wants is along a
row rather than across a table.

**Scalars are untouched.** A figure with no label -- `revenue`, `gross_margin`,
the eight overview totals -- is not a series and stays a name/value row. The
pivot applies only where more than one metric shares a label, which is what
makes a column heading meaningful; a lone labelled metric would gain a column
header stating what its single column already said.

Every check runs on the rendered document. The defect is one of shape, and a
test over the view model would pass while the template emitted the old rows.
"""

from __future__ import annotations

import hashlib
import random
import re

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import KIND_ROWS, LANGUAGE_ARABIC, LANGUAGE_ENGLISH, ReportBundle
from khepri.rra.facts import build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import (
    FigureCell,
    HtmlReportRenderer,
    _series_tables,
    build_cells,
)


def _content() -> bytes:
    """Five periods over four products, so the series are long enough to matter."""
    random.seed(11)
    rows = [b"transaction_date,net_sales,units_sold,invoice_no,category,branch,cogs\n"]
    products = ("Analgesics", "Antibiotics", "Vitamins", "Antacids")
    branches = ("Cairo-Maadi", "Cairo-Nasr", "Giza-Dokki")
    for index in range(240):
        rows.append(
            f"2026-{(index % 5) + 1:02d}-{(index % 27) + 1:02d},"
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


def document(language: str = LANGUAGE_ENGLISH) -> str:
    return HtmlReportRenderer().render_html(bundle()).documents[language]


def business_cells(language: str = LANGUAGE_ENGLISH):
    return [cell for cell in build_cells(bundle(), language) if cell.kind != KIND_ROWS]


def period_labels() -> set[str]:
    """The period labels the fixture produces, as the report spells them."""
    return {
        cell.label
        for cell in business_cells()
        if cell.label and re.fullmatch(r"2026-\d\d", cell.label)
    }


def shared_period_figures() -> dict[str, set[str]]:
    """Period labels carrying more than one metric, with the texts they carry.

    Extracted from the test that reads it rather than inlined: nesting the
    grouping loop inside the assertion loop is the "Bumpy Road" CodeScene flagged,
    and a helper named for what it returns reads better than the two levels did.
    """
    labels = period_labels()
    by_label: dict[str, set[str]] = {}
    for cell in business_cells():
        if cell.label in labels:
            by_label.setdefault(cell.label, set()).add(cell.text)
    return {label: texts for label, texts in by_label.items() if len(texts) > 1}


def overview_rows(html: str) -> list[str]:
    """Every `<tr>` of every figure table in the document.

    All tables rather than the first: a section renders its scalars in one table
    and each of its series in another, so scoping to the first would look only at
    the scalars and see no pivot at all.
    """
    tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.S)
    assert tables, "the report must render a figure table"
    return [row for table in tables for row in re.findall(r"<tr>(.*?)</tr>", table, re.S)]


class TestASeriesBecomesOneRowPerLabel:
    def test_a_period_appears_in_exactly_one_row(self) -> None:
        # The core assertion. Before the pivot, `2026-01` headed two rows in the
        # overview -- one for revenue and one for units.
        rows = overview_rows(document())
        periods = sorted(period_labels())
        assert len(periods) >= 4, f"the fixture must produce several periods: {periods}"

        appearances = {
            period: sum(1 for row in rows if period in row) for period in periods
        }
        assert all(count == 1 for count in appearances.values()), appearances

    def test_a_pivoted_row_carries_every_metric_for_its_label(self) -> None:
        # A row is only useful if it holds the whole period: revenue *and* units.
        rows = overview_rows(document())
        shared = shared_period_figures()
        assert shared, "the fixture must produce a label carrying several metrics"

        for label, texts in shared.items():
            row = next(row for row in rows if label in row)
            missing = [text for text in texts if text not in row]
            assert not missing, f"{label} row is missing {missing}"

    def test_the_metric_name_is_stated_as_a_column_not_per_row(self) -> None:
        # The repetition that made the table long: `Revenue` once per period.
        html = document()
        rows = overview_rows(html)
        pivoted = [row for row in rows if re.search(r"2026-\d\d", row)]
        assert pivoted, "the fixture must produce pivoted rows"
        for row in pivoted:
            assert "Revenue —" not in row, f"metric name repeated in row: {row[:120]}"

    def test_the_pivoted_series_states_more_figures_than_it_has_rows(self) -> None:
        # The measurable outcome. Scoped to the overview *section* rather than to
        # the whole document, because rows from every section would be compared
        # against one section's cells -- which is how this check first went wrong.
        # Stated as an inequality so it does not become a fixture-shape assertion.
        html = document()
        section = re.search(
            r'<section id="overview".*?</section>', html, re.S
        )
        assert section, "the report must render an overview section"
        rows = re.findall(r"<tr>(.*?)</tr>", section.group(0), re.S)
        figures = section.group(0).count('<td class="figure">')
        assert figures > len(rows), (
            f"{figures} figures in {len(rows)} rows -- nothing was pivoted"
        )


class TestScalarsAreLeftAlone:
    def test_a_figure_with_no_label_keeps_its_own_row(self) -> None:
        html = document()
        rows = overview_rows(html)
        scalars = [
            cell
            for cell in business_cells()
            if cell.section == "overview" and cell.label is None
        ]
        assert scalars, "the fixture must produce scalar overview figures"
        for cell in scalars:
            assert cell.metric_name, f"{cell.metric} has no name to state"
            carrying = [
                row for row in rows if cell.metric_name in row and cell.text in row
            ]
            assert carrying, f"{cell.metric_name} lost its row"


class TestNothingIsLost:
    def test_every_business_figure_still_reaches_the_page(self) -> None:
        # The guard that stops the pivot from being a way to drop cells. Every
        # rendered figure text must still appear somewhere in the document.
        for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
            html = document(language)
            for cell in business_cells(language):
                assert cell.text in html, (cell.metric, cell.label, language)

    def test_every_customer_label_still_reaches_the_page(self) -> None:
        # A pivot keys rows by label; a label that vanished would take the
        # customer's own product or branch name with it.
        for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
            html = document(language)
            for cell in business_cells(language):
                if cell.label:
                    assert cell.label in html, (cell.metric, cell.label, language)


def _cell(metric: str, kind: str, label: str, text: str) -> FigureCell:
    """One business cell, built directly so a sparse series can be constructed."""
    return FigureCell(
        figure_id=f"fig_{metric}_{kind}_{label}",
        citation_id=f"cit_{metric}_{label}",
        metric=metric,
        metric_name="Revenue" if metric.startswith("revenue") else "Units sold",
        kind=kind,
        unit_kind="monetary" if metric.startswith("revenue") else "count",
        section="overview",
        label=label,
        text=text,
    )


class TestASparseLabelStaysInItsSeries:
    """A label missing one figure is an empty cell, not a table of its own.

    Grouping families by the *exact* set of columns present split a series on
    missingness: a period whose revenue inputs were all null had a different
    column set from its neighbours and rendered as a one-row table beside them.
    It also made `_SeriesTable`'s empty cell unreachable -- every label in a
    family had every column by construction -- so the `None` the template renders
    as a blank could not occur, and the docstring promised behaviour the grouping
    had ruled out.
    """

    def _sparse(self) -> tuple[FigureCell, ...]:
        # Three periods carrying revenue and units; the middle one has no revenue.
        cells = []
        for period, revenue in (("2026-01", "10.00"), ("2026-02", None), ("2026-03", "30.00")):
            if revenue is not None:
                cells.append(_cell("revenue_by_period", "value", period, revenue))
            cells.append(_cell("units_by_period", "value", period, "5"))
        return tuple(cells)

    def test_the_sparse_label_is_not_split_into_its_own_table(self) -> None:
        tables = _series_tables(self._sparse())

        assert len(tables) == 1, [t.headings for t in tables]
        assert [row.label for row in tables[0].rows] == ["2026-01", "2026-02", "2026-03"]

    def test_the_missing_figure_renders_as_an_empty_cell(self) -> None:
        # The `None` that the template turns into a blank `<td>`, reachable at
        # last. Deliberately not a zero, which would be a number invented here.
        rows = {row.label: row.texts for row in _series_tables(self._sparse())[0].rows}

        assert None in rows["2026-02"], rows["2026-02"]
        assert all(text is not None for text in rows["2026-01"])

    def test_the_distinct_series_still_separate(self) -> None:
        # The separation the exact-set grouping got right, kept: a by-period and a
        # by-category series share no column, so they remain two tables.
        mixed = self._sparse() + (
            _cell("revenue_by_category", "value", "Antibiotics", "7.00"),
            _cell("units_by_category", "value", "Antibiotics", "2"),
        )

        assert len(_series_tables(mixed)) == 2
