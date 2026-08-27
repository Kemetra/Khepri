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
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import (
    _BY,
    FigureCell,
    HtmlReportRenderer,
    _series_columns,
    _series_tables,
    _stated,
    build_cells,
)
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    manifest_for_csv,
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
    # Built unpinned, unlike its sibling rendering modules, because this
    # module's subject *is* the comparison section: its cases assert how
    # comparison's deltas share one series table. Pinning to the published
    # predecessor asks the family gate about `formula.v1`, which refuses
    # comparison now that it has reached `rra008.comparison.v2` -- leaving
    # every case here asserting over a section that states nothing.
    #
    # The rule this follows: pin to whichever triple admits the family the
    # module is about. Modules about all four are served by the predecessor
    # pin; this one is about comparison, so it takes the published triple.
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    return ReportBundle.of(
        build_fact_package(
            AdmittedInput(
                manifest=manifest_for_csv(CONTENT, TEST_CONTRACT),
                content=CONTENT,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
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


class TestADisplayLabelIsNotASeriesIdentity:
    """Two breakdowns sharing a label stay two tables.

    Rows were keyed by display label alone, so a product literally named
    `2026-01` shared a key with the January period. Once labels were joined on
    shared columns, that collision bridged the by-period and by-product series
    into one table with `Revenue` and `Units sold` twice over, and a product row
    sitting under period columns. The row key is now `(dimension, label)`, read
    from the metric identifier rather than from a customer-supplied string.
    """

    def _colliding(self) -> tuple[FigureCell, ...]:
        return (
            _cell("revenue_by_period", "value", "2026-01", "10.00"),
            _cell("units_by_period", "value", "2026-01", "5"),
            _cell("revenue_by_period", "value", "2026-02", "20.00"),
            _cell("units_by_period", "value", "2026-02", "6"),
            # A product whose name happens to read as a period.
            _cell("revenue_by_product", "value", "2026-01", "99.00"),
            _cell("units_by_product", "value", "2026-01", "1"),
            _cell("revenue_by_product", "value", "Vitamins", "7.00"),
            _cell("units_by_product", "value", "Vitamins", "2"),
        )

    def test_the_two_breakdowns_render_as_two_tables(self) -> None:
        tables = _series_tables(self._colliding())

        assert len(tables) == 2, [table.headings for table in tables]

    def test_neither_table_repeats_a_heading(self) -> None:
        # The visible symptom of the bridge: `Revenue` and `Units sold` appearing
        # twice in one header row, naming columns from unrelated breakdowns.
        for table in _series_tables(self._colliding()):
            assert len(set(table.headings)) == len(table.headings), table.headings

    def test_no_row_carries_a_figure_from_the_other_breakdown(self) -> None:
        # The bridge put `Vitamins` under period columns with `None` beside it.
        # Every row here is complete, because each table holds one series.
        for table in _series_tables(self._colliding()):
            for row in table.rows:
                assert all(text is not None for text in row.texts), (
                    table.headings,
                    row,
                )

    def test_the_colliding_labels_land_in_different_tables(self) -> None:
        # Both series carry a `2026-01` row, and they are not the same row.
        tables = _series_tables(self._colliding())
        carrying = [
            table for table in tables if any(row.label == "2026-01" for row in table.rows)
        ]

        assert len(carrying) == 2
        assert {
            row.texts for table in carrying for row in table.rows if row.label == "2026-01"
        } == {("10.00", "5"), ("99.00", "1")}


def _pivoting_metrics() -> dict[str, set[str]]:
    """Per section, the metrics whose columns `_series_columns` actually admits.

    Read from the admitted columns rather than from every labelled cell, because
    only an admitted column is grouped by `_dimension`. `concentration_curve` is
    labelled and dimensionless but carries no governed name, so it never reaches
    the pivot and its identifier is not a grouping key -- asserting over it would
    demand a convention it is not held to.
    """
    cells = build_cells(bundle(), LANGUAGE_ENGLISH)
    admitted: dict[str, set[str]] = {}
    for section in {cell.section for cell in cells}:
        stated = _stated(cells, section)
        columns = _series_columns(stated)
        if columns:
            admitted[section] = {metric for metric, _ in columns}
    return admitted


def test_every_series_metric_declares_its_dimension() -> None:
    """The naming convention `_dimension` reads, pinned so it cannot drift.

    `_dimension` takes everything after `_by_` in the metric identifier and falls
    back to the section for a metric that names no breakdown. The fallback is
    correct only while the section's dimensionless metrics are genuinely one
    series -- true for the comparison deltas, which are one row per mode. A new
    dimensionless metric joining such a section would silently merge into it, so
    each exception is named here rather than discovered on a customer surface.
    """
    section_grouped = {"revenue_delta_absolute", "revenue_delta_percent"}
    metrics = {
        metric for section in _pivoting_metrics().values() for metric in section
    }

    assert metrics, "fixture pivots no series at all"
    undeclared = {
        metric
        for metric in metrics - section_grouped
        if _BY not in metric
    }
    assert not undeclared, (
        f"pivoted metrics that declare no dimension: {sorted(undeclared)}"
    )


def test_each_named_exception_is_one_still_taken() -> None:
    """The allowlist above cannot quietly outlive the metrics it excuses.

    An exception set that no longer matches anything is an exception set that
    stops being read: the next dimensionless metric would be waved through by a
    name left behind from a metric that had since been renamed or dropped.
    """
    from khepri.rra.analysis.comparison import (
        METRIC_DELTA_ABSOLUTE,
        METRIC_DELTA_PERCENT,
    )

    # Checked against the metrics the comparison family *names*, not against
    # the ones a bundle happens to publish today. Both are excused because they
    # are section-grouped, which is a property of the metric rather than of
    # whether its family has reached its successor version -- and while that
    # family is refused mid-sequence it publishes nothing, which would read as
    # "these metrics no longer pivot" and invite deleting an allowlist entry
    # that commit 7 needs back.
    section_grouped = {"revenue_delta_absolute", "revenue_delta_percent"}

    assert section_grouped == {METRIC_DELTA_ABSOLUTE, METRIC_DELTA_PERCENT}, (
        f"excused metrics no longer exist: {sorted(section_grouped)}"
    )


def test_a_dimensionless_metric_shares_its_section_series() -> None:
    """Why the fallback is safe *here*, stated as behaviour rather than as prose.

    The comparison deltas name no breakdown, so both fall back to `comparison`
    and their labels key one series. The section renders one table, which is the
    property the exception above is granted for.
    """
    cells = build_cells(bundle(), LANGUAGE_ENGLISH)
    comparison = _stated(cells, "comparison")

    tables = _series_tables(comparison)
    assert len(tables) == 1, [table.headings for table in tables]
    assert len(tables[0].headings) == 2, tables[0].headings
