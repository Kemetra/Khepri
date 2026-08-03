"""Native workbook charts, and the single numeric write `APP-013` permits.

**The boundary this file exists to hold.** `KHEPRI-DEC-005` forbids binary floating
point as an authoritative financial fact, and every numeric cell in a spreadsheet is
an IEEE 754 double. `APP-013` narrows that prohibition: a numeric cell is permitted
*solely* as a chart series address, on a dedicated worksheet carrying no authoritative
figure and no citation identifier. It does not relax it. So the tests here are mostly
negative -- where a number may not appear, what the chart sheet may not carry -- and
the one positive test checks the round trip that makes "a faithful copy of the
governed string" a fact rather than a claim.

**Why the axis test is not redundant with the SVG one.** A spreadsheet category axis
runs left to right whatever the sheet declares, so an Arabic chart plots its first
category on the wrong side while every text cell on the sheet reconciles perfectly.
`bundle.reconcile` compares the text beside a chart and never the chart, which is the
same gap Task 10 closed for SVG and the same reason this is asserted on the produced
file rather than on the renderer's claim.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    CHART_LINE,
    KIND_VALUE,
    NARRATIVE_OMITTED,
    ORDERED_SECTIONS,
    SECTION_CONCENTRATION,
    SECTION_PRESENT,
    BundleIdentity,
    ChartSpec,
    CitedFigure,
    FactPackage,
    ReportBundle,
    Section,
)
from khepri.rra.facts import build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.profiling import build_profile
from khepri.rra.rendering import excel
from khepri.rra.rendering.chart_labels import category_of, worded
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from tests import rra_workbooks

HEADER = b"date,revenue,units,invoice_no,product\n"
START = date(2026, 1, 5)
# Twelve days over two products, so the comparison settles a period, growth
# decomposes it, and concentration ranks more than one value. A dataset that
# refused every family would make every assertion below vacuous.
ROWS = [
    ("100.00", 4, "Water"),
    ("150.00", 5, "Water"),
    ("120.00", 4, "Juice"),
    ("200.00", 8, "Water"),
    ("90.00", 3, "Juice"),
    ("175.00", 6, "Water"),
    ("135.00", 5, "Juice"),
    ("210.00", 7, "Water"),
    ("115.00", 4, "Juice"),
    ("160.00", 6, "Water"),
    ("145.00", 5, "Juice"),
    ("190.00", 7, "Water"),
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


def rendered(bundle: ReportBundle | None = None) -> tuple[
    ReportBundle,
    rra_workbooks.ReadWorkbook,
]:
    """Render, then reopen the file rather than trusting what the renderer claimed."""
    resolved = bundle if bundle is not None else ReportBundle.of(package())
    renderer = ExcelSurfaceRenderer(directory=Path(tempfile.mkdtemp()))
    renderer.render(resolved)
    return resolved, rra_workbooks.read(renderer.path_for(resolved).read_bytes())


# Three ranked cumulative shares, as the concentration curve states them.
CURVE = (("1", "0.6000", "٠٫٦٠٠٠"), ("2", "0.8500", "٠٫٨٥٠٠"), ("3", "1.0000", "١٫٠٠٠٠"))


def curve_bundle() -> ReportBundle:
    """A bundle carrying the one chart `RRA-008` requires: a cumulative share curve.

    Constructed here rather than derived from a dataset, and that is a finding rather
    than a convenience. `bundle._bucket` records a series figure's metric as the
    series' *measure* -- `revenue` -- while `_FAMILIES` asks the concentration section
    to plot `concentration_curve`, so `_plottable` matches nothing and no dataset
    produces a curve chart on any surface. That defect predates this file and is not
    the workbook's to fix; what it would otherwise do is leave the `CHART_LINE` branch
    of `_CHART_TYPES` shipped and unexercised.
    """
    figures = tuple(
        CitedFigure(
            figure_id=f"cit_curve/{KIND_VALUE}/{position}",
            citation_id="cit_curve",
            fact_id="fct_curve",
            metric="concentration_curve",
            unit_kind="ratio",
            kind=KIND_VALUE,
            section=SECTION_CONCENTRATION,
            label=rank,
            value=Decimal(english),
            renderings={LANGUAGE_ENGLISH: english, LANGUAGE_ARABIC: arabic},
        )
        for position, (rank, english, arabic) in enumerate(CURVE)
    )
    figure_ids = tuple(figure.figure_id for figure in figures)
    return ReportBundle(
        identity=BundleIdentity.of(package()),
        figures=figures,
        caveats=(),
        narrative_state=NARRATIVE_OMITTED,
        sections=(
            Section(
                section_id=SECTION_CONCENTRATION,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=figure_ids,
                chart=ChartSpec(kind=CHART_LINE, figure_ids=figure_ids),
            ),
        ),
    )


def charted(bundle: ReportBundle) -> tuple[Section, ...]:
    return tuple(section for section in bundle.sections if section.chart is not None)


def plotted(bundle: ReportBundle, section: Section) -> tuple[CitedFigure, ...]:
    """The figures one section's chart draws, in the order its spec named them."""
    known = {figure.figure_id: figure for figure in bundle.figures}
    assert section.chart is not None
    return tuple(known[figure_id] for figure_id in section.chart.figure_ids)


def chartdata_sheets() -> set[str]:
    return {excel._chartdata_sheet(language) for language in REQUIRED_LANGUAGES}


def test_at_least_one_section_is_charted_so_nothing_below_is_vacuous() -> None:
    bundle, _ = rendered()
    assert charted(bundle)


def test_each_language_gets_one_chart_data_sheet() -> None:
    """One per language, because the categories are text and the text is translated.

    The numbers on the two sheets are identical: a number is not a rendering, so it
    has no script and nothing to translate.
    """
    _, workbook = rendered()
    assert chartdata_sheets() <= set(workbook.cells)


def test_only_the_chart_data_sheets_carry_a_numeric_cell() -> None:
    """The narrowed prohibition, asserted as a boundary rather than as an absence.

    The predecessor of this test asserted no cell anywhere was a number. `APP-013`
    permits exactly one place, so the test that matters now is that the permission
    did not leak: a governed figure on a section sheet is still a decimal string.
    """
    _, workbook = rendered()

    allowed = chartdata_sheets()
    for name, numbers in workbook.numbers.items():
        if name in allowed:
            assert numbers, name
        else:
            assert numbers == [], (name, numbers)


def test_every_numeric_chart_cell_is_the_double_nearest_its_authoritative_string() -> None:
    """The round trip that makes "a faithful copy at write time" checkable.

    Positional, not a set membership check. Asking whether each number appears
    somewhere among the figures would pass a sheet whose values were shuffled, and a
    shuffled series is a chart that plots the right numbers against the wrong
    categories.
    """
    bundle, workbook = rendered()

    expected = [
        float(figure.renderings[LANGUAGE_ENGLISH])
        for section in charted(bundle)
        for figure in plotted(bundle, section)
    ]
    for language in REQUIRED_LANGUAGES:
        written = workbook.numbers[excel._chartdata_sheet(language)]
        assert [float(value) for value in written] == expected, language


def test_the_chart_data_sheet_carries_no_citation_and_no_figure_identifier() -> None:
    """What makes the sheet non-authoritative, in the terms `APP-013` uses.

    A cell a reader can cite is a cell a reader can quote as the figure. The
    authoritative figure is the decimal string on the section sheet, and the way to
    keep that true is to leave the chart sheet nothing addressable on it.
    """
    bundle, workbook = rendered()

    addressable = {figure.figure_id for figure in bundle.figures}
    addressable |= {figure.citation_id for figure in bundle.figures}
    addressable |= {figure.fact_id for figure in bundle.figures}
    for language in REQUIRED_LANGUAGES:
        rows = workbook.cells[excel._chartdata_sheet(language)]
        present = {cell for row in rows for cell in row if cell}
        assert not present & addressable, (language, present & addressable)


def test_a_chart_is_drawn_on_every_charted_section_sheet_and_nowhere_else() -> None:
    bundle, workbook = rendered()

    names = {section.section_id for section in charted(bundle)}
    for section_id in ORDERED_SECTIONS:
        for language in REQUIRED_LANGUAGES:
            sheet = excel._section_sheet(section_id, language)
            if sheet not in workbook.cells:
                continue
            drawn = workbook.charts(sheet)
            assert len(drawn) == (1 if section_id in names else 0), (sheet, len(drawn))


def test_each_chart_is_the_kind_its_section_declares() -> None:
    """A faithful chart of the wrong kind reconciles perfectly.

    `RRA-008` requires concentration drawn as a cumulative *curve*; a curve drawn as
    bars misstates a governed requirement rather than merely looking wrong.
    """
    bundle, workbook = rendered()

    for section in charted(bundle):
        assert section.chart is not None
        for language in REQUIRED_LANGUAGES:
            xml = workbook.charts(excel._section_sheet(section.section_id, language))[0]
            if section.chart.kind == CHART_LINE:
                assert "<c:lineChart>" in xml, section.section_id
            else:
                assert "<c:barChart>" in xml, section.section_id
                assert '<c:barDir val="col"/>' in xml, section.section_id


def test_the_arabic_category_axis_is_reversed_and_the_english_one_is_not() -> None:
    """A category axis runs left to right whatever the sheet declares.

    So the Arabic chart plots its first category on the wrong side while every text
    cell beside it reconciles. Only the category axis reverses: flipping the value
    axis would render every proportion upside down with every number beside it still
    correct, which is the rule `charts._mirror` states for SVG.
    """
    bundle, workbook = rendered()

    for section in charted(bundle):
        arabic = workbook.charts(excel._section_sheet(section.section_id, LANGUAGE_ARABIC))
        english = workbook.charts(excel._section_sheet(section.section_id, LANGUAGE_ENGLISH))
        assert 'val="maxMin"' in arabic[0], section.section_id
        assert 'val="maxMin"' not in english[0], section.section_id


def test_each_series_addresses_the_rows_its_section_declared() -> None:
    """The series range, read out of the chart part and counted.

    A chart whose range is one row short drops a governed figure from the picture
    while the table beside it still lists every one, and no text comparison sees it.

    Both halves of the series, and the same rows for each: a category range offset
    from its value range by one row labels every bar with its neighbour's name, which
    is a chart that is wrong about every figure while plotting all of them.
    """
    bundle, workbook = rendered()

    for section in charted(bundle):
        for language in REQUIRED_LANGUAGES:
            xml = workbook.charts(excel._section_sheet(section.section_id, language))[0]
            values = _series_range(xml, "val", "B")
            categories = _series_range(xml, "cat", "A")
            assert values[0] == excel._chartdata_sheet(language), section.section_id
            assert categories[1:] == values[1:], section.section_id
            assert values[2] - values[1] + 1 == len(plotted(bundle, section))


def test_each_category_is_the_wording_that_language_shows() -> None:
    """A governed code on an axis is the failure `ChartCategory.localize` exists for.

    A bucket label is the customer's own product name and is final. A metric name is
    governed wording, and `metric.growth_price_effect` on an Arabic axis is the same
    defect as an untranslated table heading.

    Asserted over the whole column in order, section headings included, because that
    is what says the blocks are laid out where the series ranges above claim they are.
    """
    bundle, workbook = rendered()

    for language in REQUIRED_LANGUAGES:
        expected: list[str] = []
        for section in charted(bundle):
            expected.append(section.section_id)
            expected.extend(
                worded(category_of(figure), language)
                for figure in plotted(bundle, section)
            )
        rows = workbook.cells[excel._chartdata_sheet(language)]
        shown = [row[0] for row in rows if row and row[0]]
        assert shown == expected, language


def test_a_cumulative_share_curve_is_drawn_as_a_line() -> None:
    """The one chart kind `RRA-008` fixes by specification rather than by design.

    A curve drawn as bars misstates a governed requirement; every other kind here is a
    design decision a later revision may move.
    """
    bundle, workbook = rendered(curve_bundle())

    for language in REQUIRED_LANGUAGES:
        xml = workbook.charts(excel._section_sheet(SECTION_CONCENTRATION, language))[0]
        assert "<c:lineChart>" in xml
        assert "<c:barChart>" not in xml

    numbers = workbook.numbers[excel._chartdata_sheet(LANGUAGE_ENGLISH)]
    assert [float(value) for value in numbers] == [float(english) for _, english, _ in CURVE]
    # Rank ordinals, not value labels: the display truncation exists so a report
    # cannot name every distinct value, and a labelled curve would hand the axis the
    # list that truncation withheld.
    rows = workbook.cells[excel._chartdata_sheet(LANGUAGE_ENGLISH)]
    shown = [row[0] for row in rows if row and row[0]]
    assert shown == [SECTION_CONCENTRATION, *(rank for rank, _, _ in CURVE)]


def test_regenerating_the_workbook_writes_the_same_numbers() -> None:
    """`RRA-008` requires a deterministic rerun, and a float is where that breaks."""
    _, first = rendered()
    _, second = rendered()

    assert first.numbers == second.numbers


def _series_range(xml: str, part: str, column: str) -> tuple[str, int, int]:
    """The sheet and the first and last row one half of a series addresses."""
    pattern = (
        rf"<c:{part}>.*?<c:f>(?P<sheet>[^!]+)!"
        rf"\${column}\$(?P<first>\d+):\${column}\$(?P<last>\d+)</c:f>"
    )
    found = re.search(pattern, xml, re.DOTALL)
    assert found is not None, (part, column, xml[:400])
    return found["sheet"], int(found["first"]), int(found["last"])
