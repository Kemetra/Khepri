"""The governed Excel surface: a workbook that only transcribes a bundle.

**The failure this exists to prevent.** A spreadsheet is the one surface a
customer can edit, re-sort, and hand to somebody else, and it is the only
surface whose cells can *execute*. Two things follow, and this module exists for
both.

The first is formula injection. Excel treats a cell whose text begins `=`, `+`,
`-`, or `@` as a formula, and a cell that looks like an address as a link. A
label is customer-derived; `profiling._sanitize` already removes those prefixes,
so a fact package cannot carry one. That is not a defence a renderer may lean
on: it would put a live `=HYPERLINK(...)` in a customer's workbook one upstream
change later. So every cell holding text is written through `write_string`, which
never interprets, and the workbook additionally disables formula, URL, and number
coercion for the generic write path. A hostile label reaches the cell verbatim
and inert -- verbatim because editing it would make this module a thing that
decides content, and `bundle.py` exists to keep that decision in one place.

The second is arithmetic. RRA-006 excludes independent surface calculations, and
a workbook is where that exclusion is easiest to break: a `SUM` in a totals row
would look like diligence. There is no arithmetic in this module. Every figure
is the exact string the fact package produced, and the only strings a cell may
hold besides bundle content are the governed labels in `GOVERNED_LABELS`.

**Why no figure is a number.** Excel stores every numeric cell as an IEEE 754
double, and DEC-005 forbids binary floating point as an authoritative financial
fact. Writing a governed total as a number would therefore round-trip money
through exactly the representation the decision rules out. The figures are
written as the decimal strings the package computed them to, which is also what
`bundle.reconcile` compares: `500.0` and `500.00` are the same number and a
different statement about precision.

No *figure* is a number, and the numeric cells that do exist are not figures. There
are as many of them as there are plotted values, in both languages, and exactly one
write path puts them there: see the charts paragraph below and `_write_chart_value`.

**One worksheet per governed analysis, per language.** The workbook used to run all
five sections together in one grid. That was this surface disagreeing with the other
two about what a section is -- the page gives each analysis a heading and the printed
report gives each one a page -- and it left a reader no way to address a single
analysis. A refused section still gets a sheet, stating its reason and carrying no
figure table, because a missing sheet is the one disclosure a reader cannot tell apart
from an analysis nobody ran.

A sheet's *name* is not translated. It is an address: a reader following a reference,
or any tool reading the file, needs the same name in both workbooks. The language lives
inside the sheet.

**Charts, and the one numeric write path in this module.** This paragraph used to argue
charts out, on the grounds that an XlsxWriter chart series addresses numeric cells and
Excel stores every numeric cell as an IEEE 754 double -- which `KHEPRI-DEC-005` forbids
as an authoritative financial fact. That reasoning was sound and it is why the
prohibition still holds for every other cell here.

`APP-013` amended `KHEPRI-DEC-005` to permit a numeric cell *solely* as a chart series
address, on a dedicated worksheet holding no authoritative figure and no citation
identifier, excluded from the surface content a bundle reconciles. The authoritative
figure remains the decimal string on the section worksheet. That amendment narrows the
prohibition; it does not relax it, and `_write_chart_value` is the single place in this
module that may write one.

Three things follow from "narrows, not relaxes", and each is built rather than
promised. The number is parsed from the figure's *own authoritative string*, so the
double is by construction the nearest representation of what a reader is shown, not of
some longer `Decimal` the string never claimed. The chart sheet carries no
`figure_id`, `citation_id` or `fact_id`, so there is nothing on it a reader could quote
as the figure. And it is not read back into the surface claim -- `_content_language`
states the figures the bundle carries and nothing about this sheet -- so a numeric cell
can never become a figure the report published.

It is a visible worksheet, not a hidden one. Hiding numbers that a decision permits
only conditionally is the wrong direction: an auditor opening the workbook is owed
every cell in it, and the disclosure that these are chart machinery is the section
identifier written above each block, not their absence from the tab bar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import xlsxwriter
from xlsxwriter.chart import Chart
from xlsxwriter.workbook import Workbook
from xlsxwriter.worksheet import Worksheet

from khepri.rra.bundle import (
    CHART_BAR,
    CHART_GROUPED_BAR,
    CHART_LINE,
    DIRECTION_RTL,
    GOVERNED_SECTION_STATES,
    LANGUAGE_DIRECTION,
    SURFACE_EXCEL,
    ChartSpec,
    CitedFigure,
    ReportBundle,
    Section,
    StatedCaveat,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
    SurfaceUnavailable,
    is_drawable,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering.excel_layout import (
    BUSINESS_SHEETS,
    BusinessSheet,
)
from khepri.rra.rendering.wording import (
    BUSINESS_SHEET_NAMES,
    CAVEAT_WORDING,
    CHART_DESCRIPTIONS,
    DERIVED_METRIC_WORDING,
    KIND_QUALIFIERS,
    LABEL_WORDING,
    METRIC_WORDING,
    REFUSAL_WORDING,
    SECTION_HEADINGS,
    business_metric_name,
    category_of,
    caveat_prose,
    kind_qualifier,
    section_refusal_message,
    worded,
)
from khepri.rra.report_artifacts import (
    XLSX_MEDIA_TYPE,
    ArtifactPayload,
    MaterializedSurface,
)

# v2 moved the figures off the two report sheets and onto a sheet per section; v3 adds
# the chart data sheets and the native charts drawn from them. The version is
# machine-readable provenance a consumer selects its parser from, so a workbook with a
# new layout claiming an old version sends that consumer looking for a grid that is no
# longer there -- and, at v3, leaves it unprepared for a sheet whose cells are numbers.
#
# v4 changes what those numbers *mean*: a percentage series plots `86.65` where it
# plotted `0.8665`, because the renderer no longer divides to recover the ratio.
# A consumer parsing v3 chart data and applying its own percent formatting would
# report `8665%`. The section-sheet strings are formatted too -- `726,919.57` for a
# bare `726919.57` -- so a consumer parsing those cells as numbers now meets a
# grouping separator that was never there at v3.
EXCEL_SURFACE_VERSION = "rra006.excel.v4"
WORKBOOK_SUFFIX = ".xlsx"

# Every coercion XlsxWriter would otherwise apply to a string, switched off.
# `strings_to_numbers` is not named by DEC-005 and is disabled for the same
# reason as the other two: a governed decimal that became a number would become
# a float.
WORKBOOK_OPTIONS = {
    "strings_to_formulas": False,
    "strings_to_urls": False,
    "strings_to_numbers": False,
}

# Written in this order so the workbook is deterministic.
LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)

# Which business sheet carries the governed disclosure. Read from the layout rather
# than named here, so reordering the sheets moves the disclosure with the first one.
FIRST_BUSINESS_SHEET = BUSINESS_SHEETS[0].key

_PROVENANCE_SHEET = "Provenance"
_PROVENANCE_FIELD = "field"
_PROVENANCE_VALUE = "value"
_PROVENANCE_BUNDLE_ID = "bundle_id"
_PROVENANCE_NARRATIVE_STATE = "narrative_state"
_PROVENANCE_EXCEL_VERSION = "excel_surface_version"

# Bilingual by construction. A sheet name, a heading, and a column header are
# labels a reader sees, so each governed language gets its own sheets rather
# than one sheet with English chrome and Arabic values in it.
_REPORT_SHEET = {LANGUAGE_ENGLISH: "Report (English)", LANGUAGE_ARABIC: "التقرير (العربية)"}
_CITATION_SHEET = {LANGUAGE_ENGLISH: "Citations (English)", LANGUAGE_ARABIC: "الإسنادات (العربية)"}

# A worksheet per section per language. The name is built from the section identifier
# rather than translated, because a sheet name is an address: a reader following a
# reference, and any tooling reading the file, needs the same name in both workbooks.
# The heading inside the sheet is where the language belongs, and `_SECTION_COLUMNS`
# carries it.
_SECTION_SHEET_PREFIX = {LANGUAGE_ENGLISH: "en", LANGUAGE_ARABIC: "ar"}


def _section_sheet(section_id: str, language: str) -> str:
    return f"{_SECTION_SHEET_PREFIX[language]}_{section_id}"


# One chart data sheet per language, named on the same terms as a section sheet: an
# address rather than a translation. Two of them and not one, because the categories
# are text and text is translated. The *numbers* on the two sheets are identical -- a
# number is not a rendering, so it has no script and nothing to translate.
_CHARTDATA_SECTION = "chartdata"

def _chartdata_sheet(language: str) -> str:
    return _section_sheet(_CHARTDATA_SECTION, language)

_DISCLOSURE_HEADING = {
    LANGUAGE_ENGLISH: "About this report",
    LANGUAGE_ARABIC: "عن هذا التقرير",
}
_FIGURES_HEADING = {LANGUAGE_ENGLISH: "Figures", LANGUAGE_ARABIC: "الأرقام"}
_CAVEATS_HEADING = {LANGUAGE_ENGLISH: "Caveats", LANGUAGE_ARABIC: "التحذيرات"}

# The figure identifier leads the row. It is what makes a cell addressable
# without customer text -- `bundle._figure_id` keeps labels out of it precisely
# so a workbook can key its rows by one -- and it is what lets a reader, or a
# reconciliation check, say which cell a figure was presented in.
# The section column is what backs the workbook's claim about sections. Without it
# a reader cannot tell which analysis a row belongs to, and `_content_language`
# would be claiming a section index the sheet does not show -- which reconciliation
# would never catch, because it compares the claim against the bundle and never
# against the file.
_FIGURE_COLUMNS = {
    LANGUAGE_ENGLISH: (
        "Figure",
        "Citation",
        "Section",
        "Metric",
        "Unit",
        "Label",
        "Value",
    ),
    LANGUAGE_ARABIC: (
        "المعرّف",
        "الإسناد",
        "القسم",
        "المقياس",
        "الوحدة",
        "التسمية",
        "القيمة",
    ),
}
# The business figure table: what the row is called, and what it is. Two columns,
# because every other column on the old section sheet was an identifier.
_BUSINESS_COLUMNS = {
    LANGUAGE_ENGLISH: ("Figure", "Value"),
    LANGUAGE_ARABIC: ("البيان", "القيمة"),
}

# The audit sheets, ordered after every business sheet. Their names are addresses
# rather than translations for the reason a section sheet's was: a reader following
# a reference, or a tool reading the file, needs the same name in both workbooks.
_AUDIT_SHEET = {LANGUAGE_ENGLISH: "Audit Trail", LANGUAGE_ARABIC: "سجل المراجعة"}
_LIMITATIONS_SHEET = {
    LANGUAGE_ENGLISH: "Data Limitations",
    LANGUAGE_ARABIC: "حدود البيانات",
}
_LIMITATIONS_HEADING = {
    LANGUAGE_ENGLISH: "What this review does not cover",
    LANGUAGE_ARABIC: "ما لا يشمله هذا التقرير",
}

# A section per row, refused ones included. The figure table can only show the
# sections that have figures, so a refused analysis would be invisible in the
# workbook while `_content_language` still claimed it -- and reconciliation compares
# the claim against the bundle, never against the file. A reader of the workbook is
# owed the same disclosure as a reader of the page: the heading, and the reason.
_SECTIONS_HEADING = {LANGUAGE_ENGLISH: "Sections", LANGUAGE_ARABIC: "الأقسام"}
_SECTION_COLUMNS = {
    LANGUAGE_ENGLISH: ("Section", "State", "Reason"),
    LANGUAGE_ARABIC: ("القسم", "الحالة", "السبب"),
}
# The audit trail's section table. Two columns, not three: `state` is Internal
# under RRA-009's classification and reaches no customer surface including this
# one, and a row carrying a reason is a refused section by construction.
_AUDIT_SECTION_COLUMNS = {
    LANGUAGE_ENGLISH: ("Section", "Reason"),
    LANGUAGE_ARABIC: ("القسم", "السبب"),
}
_CITATION_COLUMNS = {
    LANGUAGE_ENGLISH: ("Citation", "Fact", "Metric", "Unit"),
    LANGUAGE_ARABIC: ("الإسناد", "الحقيقة", "المقياس", "الوحدة"),
}

# Category left, value right. Held as constants because the series addresses are built
# from them: a chart pointing at the column beside the one that was written plots the
# categories as values, silently, and nothing in the text reconciles differently.
_CHART_CATEGORY_COLUMN = 0
_CHART_VALUE_COLUMN = 1

# Where a chart sits on its section sheet: clear of the figure table, so the
# authoritative figures stay readable beside the picture drawn from them.
_CHART_ANCHOR_ROW = 1
_CHART_ANCHOR_COLUMN = len(_FIGURE_COLUMNS[LANGUAGE_ENGLISH]) + 1

# The chart kind each governed kind is drawn as. `column` rather than `bar`:
# XlsxWriter's `bar` is horizontal, and every other surface draws these rising from a
# baseline.
_CHART_TYPES = {
    CHART_BAR: {"type": "column"},
    CHART_GROUPED_BAR: {"type": "column", "subtype": "clustered"},
    CHART_LINE: {"type": "line"},
}

# The rendering a chart value is parsed from. English because it is the ASCII decimal
# form: the Arabic rendering is the same number in Arabic-Indic digits, which is a
# script and not something `Decimal` parses. Naming it keeps that from reading like a
# surface preferring one language's figures.
_CHART_NUMBER_LANGUAGE = LANGUAGE_ENGLISH

# Every literal this module may put in a cell that did not come from the bundle.
# Held as one frozen set so "did the renderer invent this text?" is decidable:
# a cell is either bundle content or a member of this.
GOVERNED_LABELS = frozenset(
    {
        EXCEL_SURFACE_VERSION,
        _PROVENANCE_SHEET,
        _PROVENANCE_FIELD,
        _PROVENANCE_VALUE,
        _PROVENANCE_BUNDLE_ID,
        _PROVENANCE_NARRATIVE_STATE,
        _PROVENANCE_EXCEL_VERSION,
    }
    | {
        text
        for mapping in (
            _REPORT_SHEET,
            _CITATION_SHEET,
            _DISCLOSURE_HEADING,
            _FIGURES_HEADING,
            _CAVEATS_HEADING,
        )
        for text in mapping.values()
    }
    | {
        header
        for mapping in (_FIGURE_COLUMNS, _CITATION_COLUMNS, _SECTION_COLUMNS)
        for headers in mapping.values()
        for header in headers
    }
    | set(_SECTIONS_HEADING.values())
    | set(GOVERNED_SECTION_STATES)
    # The business and audit sheet names, their column headers, and the limitations
    # heading. Every literal a cell may hold that did not come from the bundle
    # belongs here, so "did the renderer invent this text?" stays decidable.
    | {name for names in BUSINESS_SHEET_NAMES.values() for name in names.values()}
    | {
        text
        for mapping in (_AUDIT_SHEET, _LIMITATIONS_SHEET, _LIMITATIONS_HEADING)
        for text in mapping.values()
    }
    | {
        header
        for mapping in (_BUSINESS_COLUMNS, _AUDIT_SECTION_COLUMNS)
        for headers in mapping.values()
        for header in headers
    }
    # Business metric names, the derived-label names, and the row-count qualifier.
    # These are governed wording this module puts in a cell, exactly as the chart
    # categories below are, so they belong in this set for the same reason: a cell
    # is either bundle content or a member of this.
    | {
        text
        for table in (METRIC_WORDING, DERIVED_METRIC_WORDING, KIND_QUALIFIERS)
        for names in table.values()
        for text in names.values()
    }
    # Refusal and caveat prose is governed wording too. Resolved per bundle rather
    # than enumerable at import -- a composite `<result>:<reason>` caveat code is
    # built from a figure's own identity -- so the limitations sheet's prose is
    # admitted by `_governed_prose` at write time instead.
    | {
        message
        for tier in REFUSAL_WORDING.values()
        for messages in tier.values()
        for message in messages.values()
    }
    | {
        message
        for messages in CAVEAT_WORDING.values()
        for message in messages.values()
    }
    # Chart categories. A bucket's category is the customer's own value and is bundle
    # content; a scalar's is a governed metric or mode name, which is this renderer
    # putting text in a cell and therefore belongs in this set. The wording is the one
    # `wording` also gives the page, so the axis of the native chart and the axis of
    # the SVG cannot read differently.
    | {text for wording in LABEL_WORDING.values() for text in wording.values()}
)

_LABEL_WIDTH = 34
_VALUE_WIDTH = 22


class WorkbookUnavailable(SurfaceUnavailable, RuntimeError):
    """The workbook could not be written, so this surface does not exist.

    Subclasses `SurfaceUnavailable` so the assembler treats it as a failed
    surface, and `RuntimeError` because it is operational rather than a
    statement about the bundle.
    """


@dataclass(frozen=True, slots=True)
class ExcelSurfaceRenderer:
    """Writes one workbook per bundle into a caller-supplied directory.

    The destination is a constructor argument because `SurfaceRenderer.render`
    takes only a bundle. The file is named by `bundle_id`, which is a digest and
    so carries no customer content, and which keeps one run's workbook from
    overwriting another's.
    """

    directory: Path

    def __post_init__(self) -> None:
        _require_directory(self.directory, "directory")

    @property
    def surface(self) -> str:
        return SURFACE_EXCEL

    def path_for(self, bundle: ReportBundle) -> Path:
        return self.directory / f"{bundle.bundle_id}{WORKBOOK_SUFFIX}"

    def _attempt_path(self, bundle: ReportBundle) -> Path:
        """A destination no concurrent render of this bundle can be holding.

        `path_for` is derived from `bundle_id` alone, so two workers rendering the
        same bundle -- which is what happens when an expired lease is reclaimed --
        resolve to the same file. Each attempt therefore writes somewhere unique
        and only afterwards claims the shared name.
        """
        return self.directory / f"{bundle.bundle_id}.{_new_attempt_id()}{WORKBOOK_SUFFIX}"

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        """Write the workbook, then report what it presents and how large it is.

        The size is read from the closed file rather than accumulated while
        writing. A workbook is a compressed archive, so the bytes a caller ends
        up holding are only knowable once the archive has been finished, and any
        figure taken earlier would describe something that never existed.

        The size is taken from this attempt's own file, before the shared name is
        claimed, so it describes the archive this call wrote and not one a
        concurrent worker happened to leave there.
        """
        attempt = self._attempt_path(bundle)
        try:
            with xlsxwriter.Workbook(str(attempt), dict(WORKBOOK_OPTIONS)) as workbook:
                _write_workbook(workbook, bundle)
            written = attempt.stat().st_size
            attempt.replace(self.path_for(bundle))
        except OSError as error:
            raise WorkbookUnavailable("The Excel surface could not be written.") from error
        return _content(bundle, written)

    def payload_for(self, bundle: ReportBundle, content: SurfaceContent) -> bytes:
        """The archive bytes this renderer wrote, verified against what it reported.

        Reading the shared path can observe a concurrent worker's half-written
        archive, and the digest a caller derives afterwards would be taken from
        those same bytes -- so a corrupt workbook would verify against itself. The
        recorded size is the one independent check available, and a mismatch means
        the file was replaced under us.
        """
        payload = self.path_for(bundle).read_bytes()
        if len(payload) != content.output_size_bytes:
            raise WorkbookUnavailable("The Excel surface could not be read.")
        return payload

    def render_materialized(self, bundle: ReportBundle) -> MaterializedSurface:
        content = self.render(bundle)
        payload = self.payload_for(bundle, content)
        return MaterializedSurface(
            content=content,
            artifacts=(
                ArtifactPayload.of(
                    kind="excel",
                    media_type=XLSX_MEDIA_TYPE,
                    file_name="khepri-report.xlsx",
                    content=payload,
                ),
            ),
        )


def _new_attempt_id() -> str:
    return uuid4().hex


def _write_workbook(workbook: Workbook, bundle: ReportBundle) -> None:
    """Business worksheets first, then the limitations, then the audit region.

    Order *is* the information architecture in a workbook: it is what a reader sees
    on opening the file. A customer lands on the executive summary rather than on a
    grid of identifiers, and an auditor finds every identifier on the sheets after
    them.

    The chart data sheet keeps its position at the end of each language's run, for
    the reason it always had: a chart is inserted into a worksheet object, so the
    sheets it draws onto have to exist first, and `_series_range` addresses the data
    sheet by name.
    """
    for language in LANGUAGES:
        written: list[tuple[BusinessSheet, Worksheet]] = []
        for sheet in BUSINESS_SHEETS:
            worksheet = _write_business_sheet(workbook, bundle, language, sheet)
            if worksheet is not None:
                written.append((sheet, worksheet))
        _write_limitations(workbook, bundle, language)
        _write_audit_trail(workbook, bundle, language)
        _write_citations(workbook, bundle, language)
        _draw_charts(workbook, bundle, language, written)
    _write_provenance(workbook, bundle)


def _write_business_sheet(
    workbook: Workbook,
    bundle: ReportBundle,
    language: str,
    sheet: BusinessSheet,
) -> Worksheet | None:
    """One business worksheet, or nothing when it has no figure to present.

    Returning `None` rather than an empty sheet is deliberate: a worksheet whose
    only content is an apology is worse than its absence, and a customer whose
    export carries no cost column is owed a workbook without a Profitability tab
    rather than one with an empty one. The refusal is not lost -- it reaches the
    customer as prose on the limitations sheet.

    The consequence, stated because it surprises a reader of the file: the business
    tab count varies by dataset. The audit sheets do not.
    """
    figures = [figure for figure in bundle.figures if figure.metric in sheet.metrics]
    if not figures:
        return None
    worksheet = _sheet(workbook, BUSINESS_SHEET_NAMES[language][sheet.key], language)
    worksheet.set_column(0, 0, _LABEL_WIDTH * 2)
    worksheet.set_column(1, 1, _VALUE_WIDTH)

    row = 0
    if sheet.key == FIRST_BUSINESS_SHEET:
        # The governed disclosure, on the sheet a reader opens first.
        #
        # RRA-009 requires it carried verbatim on every report, and the old index
        # sheet is where it used to live -- so removing that sheet without moving the
        # disclosure would have dropped it from the workbook entirely. It is written
        # once rather than on all eight sheets: repeating it would be this module
        # deciding a governed text is decoration.
        row = _write_row(
            worksheet,
            row,
            (_DISCLOSURE_HEADING[language], bundle.disclosure(language)),
        )
        row += 1

    row = _write_row(worksheet, row, _BUSINESS_COLUMNS[language])
    for figure in figures:
        row = _write_row(worksheet, row, _business_cells(figure, language))
    return worksheet


def _business_cells(figure: CitedFigure, language: str) -> tuple[str, ...]:
    """One figure as a business row: what it is called, and what it is.

    No identifier column, no metric code, no kind and no unit -- RRA-009 puts each
    of those in the audit region, and a business sheet carrying one would be the
    identifier ledger with a friendlier tab name.

    The name is composed the same way the web surface composes it, and for the same
    reason: a bucket emits a value figure and a row-count figure carrying the same
    metric and the same label, so a name that ignored `kind` would list two rows a
    reader cannot tell apart. `business_metric_name` returns `None` for a metric no
    table names, and those rows are named by their own label.
    """
    return (_business_name(figure, language), figure.renderings[language])


def _business_name(figure: CitedFigure, language: str) -> str:
    """A figure's business row name: its measure, its kind, and its label."""
    name = business_metric_name(figure.metric, language)
    qualifier = kind_qualifier(figure.kind, language)
    if qualifier is not None:
        name = f"{name} ({qualifier})" if name else qualifier
    if figure.label is None:
        # A scalar. Every scalar the bundle renders has a governed or derived name,
        # which `test_every_rendered_metric_is_named_or_labelled` holds.
        return name or figure.metric
    label = worded(category_of(figure), language) if figure.label else figure.label
    return f"{name} — {label}" if name else label


def _write_report(workbook: Workbook, bundle: ReportBundle, language: str) -> None:
    """The index sheet: the disclosure, the sections, and the report-level caveats.

    It carries no figures. Each analysis has its own worksheet, so a reader opening
    the workbook lands on what the report says about itself and then chooses an
    analysis by name -- which is how the sections read on the page and on paper, and
    a workbook that ran all five together in one grid was the surface disagreeing
    with the other two about what a section is.
    """
    sheet = _sheet(workbook, _REPORT_SHEET[language], language)
    sheet.set_column(0, 0, _LABEL_WIDTH)
    sheet.set_column(1, len(_SECTION_COLUMNS[language]) - 1, _VALUE_WIDTH)

    row = _write_row(sheet, 0, (_DISCLOSURE_HEADING[language], bundle.disclosure(language)))
    row = _write_row(sheet, row + 1, (_SECTIONS_HEADING[language],))
    row = _write_row(sheet, row, _SECTION_COLUMNS[language])
    for section in bundle.sections:
        row = _write_row(sheet, row, (section.section_id, section.state, section.reason))

    row = _write_row(sheet, row + 1, (_CAVEATS_HEADING[language],))
    for caveat in bundle.caveats:
        # Report-level here; a section's own caveats are written on its sheet. The
        # section is still named beside the code, because the index is where a reader
        # sees every caveat at once and a bare code there cannot say what it qualifies.
        row = _write_row(sheet, row, _caveat_cells(caveat))


def _write_audit_trail(workbook: Workbook, bundle: ReportBundle, language: str) -> None:
    """Every identifier the business sheets do not carry, on one sheet.

    This is the ledger the section sheets used to be, moved rather than rebuilt:
    the columns are `_FIGURE_COLUMNS` and the section columns unchanged, so a figure
    a reader could quote before is a figure they can quote now, under the same
    headers.

    Ordered after every business sheet. A refused section keeps its row here for the
    reason it kept its sheet before -- a missing row is the one disclosure a reader
    cannot tell apart from an analysis nobody ran -- and it is identifiable by
    carrying a reason. The section's `state` is not written: the visibility matrix
    classifies it Internal, and RRA-009 renders an Internal field on no customer
    surface, including this one.
    """
    sheet = _sheet(workbook, _AUDIT_SHEET[language], language)
    sheet.set_column(0, 0, _LABEL_WIDTH)
    sheet.set_column(1, len(_FIGURE_COLUMNS[language]) - 1, _VALUE_WIDTH)

    row = _write_row(sheet, 0, (_SECTIONS_HEADING[language],))
    row = _write_row(sheet, row, _AUDIT_SECTION_COLUMNS[language])
    for section in bundle.sections:
        row = _write_row(sheet, row, (section.section_id, section.reason))

    row = _write_row(sheet, row + 1, (_FIGURES_HEADING[language],))
    row = _write_row(sheet, row, _FIGURE_COLUMNS[language])
    for figure in bundle.figures:
        row = _write_row(sheet, row, _figure_cells(figure, language))


def _write_limitations(workbook: Workbook, bundle: ReportBundle, language: str) -> None:
    """Every refusal and every caveat, in the customer's language, as prose.

    Ordered last among the business sheets and before the audit sheets: it is
    business content -- a customer needs to know what the report does not cover --
    but it is what a reader consults after the findings rather than before them.

    Every caveat is present, not a curated subset. `_reconcile_language` compares
    caveat sets for equality, so a friendlier subset is a refused report rather than
    a tidier sheet.
    """
    sheet = _sheet(workbook, _LIMITATIONS_SHEET[language], language)
    sheet.set_column(0, 0, _LABEL_WIDTH * 4)

    row = _write_row(sheet, 0, (_LIMITATIONS_HEADING[language],))
    for section in bundle.sections:
        if section.reason is None:
            continue
        row = _write_row(
            sheet,
            row + 1,
            (
                section_refusal_message(
                    section.section_id,
                    section.reason,
                    language,
                ),
            ),
        )
    for caveat in bundle.caveats:
        row = _write_row(sheet, row + 1, (caveat_prose(caveat.code, language),))


def _write_section(
    workbook: Workbook,
    bundle: ReportBundle,
    language: str,
    section: Section,
) -> Worksheet:
    """One analysis: its state, its figures, and the caveats that qualify it.

    A refused section still gets a worksheet. `RRA-008` refuses the affected analysis
    rather than the report, and a missing sheet is the one disclosure a reader cannot
    distinguish from an analysis nobody ran -- the same reason the page renders a
    heading and a reason rather than nothing.

    Returns the sheet so a chart can be drawn onto it once the data it plots exists.
    """
    sheet = _sheet(workbook, _section_sheet(section.section_id, language), language)
    sheet.set_column(0, 0, _LABEL_WIDTH)
    sheet.set_column(1, len(_FIGURE_COLUMNS[language]) - 1, _VALUE_WIDTH)

    row = _write_row(sheet, 0, _SECTION_COLUMNS[language])
    row = _write_row(sheet, row, (section.section_id, section.state, section.reason))
    row = _write_section_figures(sheet, row, bundle, language, section.section_id)
    _write_section_caveats(sheet, row, bundle, language, section.section_id)
    return sheet


def _write_section_figures(
    sheet: Worksheet,
    row: int,
    bundle: ReportBundle,
    language: str,
    section_id: str,
) -> int:
    """The section's figure table, or nothing at all when it refused."""
    figures = [figure for figure in bundle.figures if figure.section == section_id]
    if not figures:
        return row
    row = _write_row(sheet, row + 1, (_FIGURES_HEADING[language],))
    row = _write_row(sheet, row, _FIGURE_COLUMNS[language])
    for figure in figures:
        row = _write_row(sheet, row, _figure_cells(figure, language))
    return row


def _write_section_caveats(
    sheet: Worksheet,
    row: int,
    bundle: ReportBundle,
    language: str,
    section_id: str,
) -> int:
    """The caveats qualifying this analysis. The heading supplies their scope."""
    scoped = [caveat for caveat in bundle.caveats if caveat.section == section_id]
    if not scoped:
        return row
    row = _write_row(sheet, row + 1, (_CAVEATS_HEADING[language],))
    for caveat in scoped:
        row = _write_row(sheet, row, (caveat.code,))
    return row


@dataclass(frozen=True, slots=True)
class _ChartBlock:
    """One section's series on the chart data sheet: where it sits, and what it plots.

    The layout is a value object rather than something each writer works out for
    itself, because two things read it: the sheet writer places the cells, and the
    series builder addresses them. Two independent derivations of the same rows is how
    a chart comes to plot the row above the one that was written.
    """

    section_id: str
    kind: str
    first_row: int
    categories: tuple[str, ...]
    figures: tuple[CitedFigure, ...]

    @property
    def last_row(self) -> int:
        return self.first_row + len(self.figures) - 1


def _draw_charts(
    workbook: Workbook,
    bundle: ReportBundle,
    language: str,
    written: list[tuple[BusinessSheet, Worksheet]],
) -> None:
    """Write one language's chart data, then draw each series onto its sheet.

    Takes an ordered list of the business sheets actually written rather than a
    section-keyed mapping. Four business sheets present the `overview` section, so a
    dict keyed by section would keep only the last of them and a chart for that
    section would land on whichever sheet was written last. The list preserves
    reading order, and a block draws onto the first sheet presenting its section --
    the one a reader reaches first.

    The insertion result is checked rather than discarded. `insert_chart` reports a
    refusal by return value, and a dropped chart would leave the sheet looking like a
    section that has none -- indistinguishable, to a reader, from one whose figures
    could not be drawn.
    """
    for block in _write_chartdata(workbook, bundle, language):
        target = next(
            (
                worksheet
                for sheet, worksheet in written
                if sheet.section == block.section_id
            ),
            None,
        )
        if target is None:
            # A charted section whose business sheet was omitted has no figures to
            # plot, so no chart is being lost. `_chart_blocks` already declines to
            # yield a block for an unresolvable chart; this is the second line of
            # the same rule, and a KeyError here would fail the whole workbook over
            # a picture.
            continue
        placed = target.insert_chart(
            _CHART_ANCHOR_ROW,
            _CHART_ANCHOR_COLUMN,
            _chart_for(workbook, block, language),
            {"description": _described(block, language)},
        )
        if placed != 0:
            raise WorkbookUnavailable("A governed chart could not be placed.")


def _described(block: _ChartBlock, language: str) -> str:
    """The chart's alternative text: what a reader who cannot see it is told instead.

    `RRA-006` requires an accessible workbook, and an embedded chart is the one object
    on a sheet that carries no cell text of its own. Without this a screen reader
    announces a picture and nothing about it.
    """
    return CHART_DESCRIPTIONS[language][f"chart_description.{block.kind}"]


def _write_chartdata(
    workbook: Workbook,
    bundle: ReportBundle,
    language: str,
) -> tuple[_ChartBlock, ...]:
    """The one sheet in this workbook whose cells are numbers.

    Created only when there is a chart to feed, because an empty sheet is a tab a
    reader has to open to discover it says nothing. Each block is headed by the
    section identifier it belongs to: that is what makes the sheet auditable -- a
    reader can see which analysis a run of numbers was drawn for -- while carrying
    nothing citable, which is what `APP-013` requires of it.
    """
    blocks = _chart_blocks(bundle, language)
    if not blocks:
        return blocks
    sheet = _sheet(workbook, _chartdata_sheet(language), language)
    sheet.set_column(_CHART_CATEGORY_COLUMN, _CHART_CATEGORY_COLUMN, _LABEL_WIDTH)
    sheet.set_column(_CHART_VALUE_COLUMN, _CHART_VALUE_COLUMN, _VALUE_WIDTH)
    for block in blocks:
        _write_chart_block(sheet, block)
    return blocks


def _chart_blocks(bundle: ReportBundle, language: str) -> tuple[_ChartBlock, ...]:
    """The layout: one block per charted section, in the bundle's section order.

    A section whose chart cannot be resolved contributes no block and no chart, rather
    than a block missing a row. `bundle._require_chart_within` already refuses a spec
    naming a figure its section does not carry, so this is the second line -- and it
    fails closed for the same reason `charts._resolve` does: a series drawn from the
    figures it happened to find plots something the section never authorized.
    """
    blocks: list[_ChartBlock] = []
    row = 0
    for section in bundle.sections:
        if section.chart is None:
            continue
        figures = _plotted(bundle, section.chart)
        if figures is None:
            continue
        blocks.append(
            _ChartBlock(
                section_id=section.section_id,
                kind=section.chart.kind,
                first_row=row + 1,
                categories=tuple(
                    worded(category_of(figure), language) for figure in figures
                ),
                figures=figures,
            )
        )
        # The block's own heading row, its pairs, and one blank row before the next.
        row += len(figures) + 2
    return tuple(blocks)


def _plotted(bundle: ReportBundle, spec: ChartSpec) -> tuple[CitedFigure, ...] | None:
    """The figures a spec names, in its order, or nothing if the series is undrawable.

    Two checks, and the second is `bundle.is_drawable` rather than a rule of this
    module's own. `Section` validates a chart's membership and its kind and not its
    drawability, so a directly constructed bundle can carry a spec naming one point,
    or figures in mixed units, or a domain of no width. `charts.build_chart` refuses
    all three, so the page and the printed report would show no chart while this
    surface drew one -- and mixed units in particular would give the workbook a value
    axis scaling a ratio of 0.1818 against a count of 25. `is_drawable` lives in
    `bundle` precisely so every surface answers that question the same way.

    The first check is this module's, because it is about this module's write: a figure
    without a value or without the ASCII rendering the number is parsed from has
    nothing to write, and a chart may not render a governed gap as a zero.
    """
    known = {figure.figure_id: figure for figure in bundle.figures}
    found = [known.get(figure_id) for figure_id in spec.figure_ids]
    if any(figure is None or not _has_number(figure) for figure in found):
        return None
    figures = tuple(figure for figure in found if figure is not None)
    if not is_drawable(figures):
        return None
    return figures


def _has_number(figure: CitedFigure) -> bool:
    return figure.value is not None and _CHART_NUMBER_LANGUAGE in figure.renderings


def _write_chart_block(sheet: Worksheet, block: _ChartBlock) -> None:
    """One section's block: the section identifier, then a category and a value a row."""
    _write_row(sheet, block.first_row - 1, (block.section_id,))
    for offset, figure in enumerate(block.figures):
        row = block.first_row + offset
        sheet.write_string(row, _CHART_CATEGORY_COLUMN, block.categories[offset])
        _write_chart_value(sheet, row, _CHART_VALUE_COLUMN, figure)


def _write_chart_value(
    sheet: Worksheet,
    row: int,
    column: int,
    figure: CitedFigure,
) -> None:
    """The single numeric write in this module.

    `APP-013` permits it solely as a chart series address, on a worksheet holding no
    authoritative figure and no citation. The authoritative figure is the string on the
    section sheet.

    Parsed from that authoritative string rather than narrowed from the figure's own
    `Decimal`. The two are the same number today -- `bundle._figure` builds both from
    one string -- but "the same" is an invariant held in another module, and this is
    the write the decision narrows. Parsing the string makes the double the nearest
    representation of exactly what a reader is shown, whatever that invariant does
    later; `float(figure.value)` would have quietly written more precision than the
    report ever claimed, which is the relaxation `APP-013` refuses.

    **The presentation is removed before parsing, not looked past.** The rendering now
    carries grouping separators, and a ratio carries a percent sign, because `RRA-006`
    requires formats. `Decimal` accepts neither, so this parsed cleanly only while the
    string happened to be bare -- the coupling this docstring already warned was held
    elsewhere. Undoing exactly the two transforms `bundle._presented` applies keeps
    this write addressing what the reader is shown rather than reaching for the
    `Decimal` the decision refuses: a percentage is divided back by one hundred, so
    the series plots the ratio the section sheet states.
    """
    sheet.write_number(row, column, _chart_number(figure))


def _chart_number(figure: CitedFigure) -> float:
    """The authoritative string as a double, with its presentation removed.

    **Nothing is recomputed here, and that is a governed requirement rather than
    a preference.** `RRA-009`'s preservation rules say: "Recompute no figure in a
    renderer, and hold no decimal value there." An earlier revision divided a
    percentage by a hundred to recover the stored ratio, which is arithmetic on a
    `Decimal` inside a renderer -- exactly what that rule forbids, and a second
    place where the value could drift from the one the reader is shown.

    So the separators and the sign are stripped and nothing else happens: a
    figure shown as `86.65%` plots `86.65`. The series is then in the same units
    as the business cell beside it, which is the consistency the workbook was
    missing while the sheet said `86.65%` and the chart plotted `0.8665`.

    Supplying the chart value from the bundle would be better still, and is not
    available here: `CitedFigure.as_document` feeds the bundle digest, so adding
    a field is a governed serialized-shape change under `RRA-004` and needs its
    own authority rather than a presentation slice.
    """
    shown = figure.renderings[_CHART_NUMBER_LANGUAGE]
    return float(shown.replace(",", "").rstrip("%"))


def _chart_for(workbook: Workbook, block: _ChartBlock, language: str) -> Chart:
    """One native chart over one block's rows, titled with its section's heading.

    The title is the accessibility requirement, not decoration: an embedded chart
    carries no cell text, so without one a screen reader announces a picture and
    nothing about which analysis it belongs to. It is governed wording read from
    `wording.SECTION_HEADINGS`, the same heading the page and the printed report show
    above the same analysis -- an earlier version omitted it on the grounds that prose
    composed here would be ungoverned, which was the right rule applied to the wrong
    case: this wording already exists and is already translated.

    No axis titles. The category axis is named by its own categories and the value axis
    would need a unit name no table governs.

    No legend. A single unnamed series is captioned `Series 1`, which is a label this
    surface did not write and cannot translate.
    """
    chart = workbook.add_chart(dict(_CHART_TYPES[block.kind]))
    chart.set_title({"name": SECTION_HEADINGS[language][block.section_id]})
    chart.add_series(
        {
            "categories": _series_range(block, language, _CHART_CATEGORY_COLUMN),
            "values": _series_range(block, language, _CHART_VALUE_COLUMN),
        }
    )
    chart.set_legend({"none": True})
    if LANGUAGE_DIRECTION[language] == DIRECTION_RTL:
        # The only place a chart's direction is real rather than declared. A category
        # axis runs left to right whatever the sheet declares, so without this the
        # Arabic chart plots its first category on the wrong side while every text cell
        # beside it reconciles perfectly. Only the category axis: reversing the value
        # axis would render every proportion upside down with every number beside it
        # still correct.
        chart.set_x_axis({"reverse": True})
    return chart


def _series_range(block: _ChartBlock, language: str, column: int) -> list[object]:
    """One column of a block, as the sheet-and-cells address a series takes."""
    return [
        _chartdata_sheet(language),
        block.first_row,
        column,
        block.last_row,
        column,
    ]


def _write_citations(workbook: Workbook, bundle: ReportBundle, language: str) -> None:
    """One row per cited fact, so a figure's citation is followable in-workbook."""
    sheet = _sheet(workbook, _CITATION_SHEET[language], language)
    sheet.set_column(0, len(_CITATION_COLUMNS[language]) - 1, _VALUE_WIDTH)

    row = _write_row(sheet, 0, _CITATION_COLUMNS[language])
    for figure in _cited(bundle):
        row = _write_row(
            sheet,
            row,
            (figure.citation_id, figure.fact_id, figure.metric, figure.unit_kind),
        )


def _write_provenance(workbook: Workbook, bundle: ReportBundle) -> None:
    """The provenance record, as field/value rows a machine can read.

    Governed field names rather than translated ones: this sheet is the
    machine-readable one, and every value on it is a version, a digest, a count,
    or a state.
    """
    sheet = _sheet(workbook, _PROVENANCE_SHEET, LANGUAGE_ENGLISH)
    sheet.set_column(0, 0, _LABEL_WIDTH)
    sheet.set_column(1, 1, _LABEL_WIDTH * 2)

    row = _write_row(sheet, 0, (_PROVENANCE_FIELD, _PROVENANCE_VALUE))
    for field, value in _provenance(bundle):
        row = _write_row(sheet, row, (field, value))


def _provenance(bundle: ReportBundle) -> tuple[tuple[str, str], ...]:
    entries = {
        **{field: str(value) for field, value in bundle.identity.as_document().items()},
        _PROVENANCE_BUNDLE_ID: bundle.bundle_id,
        _PROVENANCE_NARRATIVE_STATE: bundle.narrative_state,
        _PROVENANCE_EXCEL_VERSION: EXCEL_SURFACE_VERSION,
    }
    return tuple(sorted(entries.items()))


def _cited(bundle: ReportBundle) -> tuple[CitedFigure, ...]:
    """The first figure of each citation, in the order the bundle carries them."""
    seen: dict[str, CitedFigure] = {}
    for figure in bundle.figures:
        seen.setdefault(figure.citation_id, figure)
    return tuple(seen.values())


def _figure_cells(figure: CitedFigure, language: str) -> tuple[str | None, ...]:
    """One figure as its row. A figure without a label leaves the cell empty."""
    return (
        figure.figure_id,
        figure.citation_id,
        figure.section,
        figure.metric,
        figure.unit_kind,
        figure.label,
        figure.renderings[language],
    )


def _sheet(workbook: Workbook, name: str, language: str) -> Worksheet:
    sheet = workbook.add_worksheet(name)
    if LANGUAGE_DIRECTION[language] == DIRECTION_RTL:
        # The only place direction is real rather than declared: this sets
        # `rightToLeft` on the sheet view, so Arabic columns run the way Arabic
        # reads instead of merely being labelled that way.
        sheet.right_to_left()
    return sheet


def _write_row(sheet: Worksheet, row: int, values: tuple[str | None, ...]) -> int:
    """Write one row of literal text and return the next row.

    `write_string` rather than `write`: it has no coercion path at all, so a
    label beginning `=` is a string here even if a future caller constructs the
    workbook without `WORKBOOK_OPTIONS`.
    """
    for column, value in enumerate(values):
        if value is not None:
            sheet.write_string(row, column, value)
    return row + 1


def _content(bundle: ReportBundle, output_size_bytes: int) -> SurfaceContent:
    return SurfaceContent(
        surface=SURFACE_EXCEL,
        bundle_id=bundle.bundle_id,
        languages=tuple(_content_language(bundle, language) for language in LANGUAGES),
        output_size_bytes=output_size_bytes,
    )


def _content_language(bundle: ReportBundle, language: str) -> SurfaceLanguage:
    return SurfaceLanguage(
        language=language,
        direction=LANGUAGE_DIRECTION[language],
        sections=bundle.section_ids,
        stated=tuple(
            StatedFigure(
                figure_id=figure.figure_id,
                text=figure.renderings[language],
                section=figure.section,
            )
            for figure in bundle.figures
        ),
        caveats=bundle.caveats,
        disclosure=bundle.disclosure(language),
    )


def _caveat_cells(caveat: StatedCaveat) -> tuple[str, ...]:
    """A caveat code, and the section it qualifies when it qualifies only one."""
    if caveat.section is None:
        return (caveat.code,)
    return (caveat.code, caveat.section)


def _require_directory(value: Path, name: str) -> None:
    if not value.is_dir():
        raise ValueError(f"{name} must be an existing directory.")
