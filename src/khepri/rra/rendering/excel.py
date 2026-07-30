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
change later. So every cell here is written through `write_string`, which never
interprets, and the workbook additionally disables formula, URL, and number
coercion for the generic write path. A hostile label reaches the cell verbatim
and inert -- verbatim because editing it would make this module a thing that
decides content, and `bundle.py` exists to keep that decision in one place.

The second is arithmetic. RRA-006 excludes independent surface calculations, and
a workbook is where that exclusion is easiest to break: a `SUM` in a totals row
would look like diligence. There is no arithmetic in this module. Every figure
is the exact string the fact package produced, and the only strings a cell may
hold besides bundle content are the governed labels in `GOVERNED_LABELS`.

**Why no cell is a number.** Excel stores every numeric cell as an IEEE 754
double, and DEC-005 forbids binary floating point as an authoritative financial
fact. Writing a governed total as a number would therefore round-trip money
through exactly the representation the decision rules out. The figures are
written as the decimal strings the package computed them to, which is also what
`bundle.reconcile` compares: `500.0` and `500.00` are the same number and a
different statement about precision.

**What this module does not do.** It draws no charts. An XlsxWriter chart series
addresses numeric cells, so charting a governed monetary series would reintroduce
the floating-point representation above; and RRA-006's Excel requirement is
accessible tables, units, formats, citation sheets, and machine-readable
provenance, none of which is a chart.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import xlsxwriter
from xlsxwriter.workbook import Workbook
from xlsxwriter.worksheet import Worksheet

from khepri.rra.bundle import (
    DIRECTION_RTL,
    LANGUAGE_DIRECTION,
    SURFACE_EXCEL,
    CitedFigure,
    ReportBundle,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
    SurfaceUnavailable,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH

EXCEL_SURFACE_VERSION = "rra006.excel.v1"
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
_FIGURE_COLUMNS = {
    LANGUAGE_ENGLISH: ("Figure", "Citation", "Metric", "Unit", "Label", "Value"),
    LANGUAGE_ARABIC: ("المعرّف", "الإسناد", "المقياس", "الوحدة", "التسمية", "القيمة"),
}
_CITATION_COLUMNS = {
    LANGUAGE_ENGLISH: ("Citation", "Fact", "Metric", "Unit"),
    LANGUAGE_ARABIC: ("الإسناد", "الحقيقة", "المقياس", "الوحدة"),
}

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
        for mapping in (_FIGURE_COLUMNS, _CITATION_COLUMNS)
        for headers in mapping.values()
        for header in headers
    }
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

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        path = self.path_for(bundle)
        try:
            with xlsxwriter.Workbook(str(path), dict(WORKBOOK_OPTIONS)) as workbook:
                _write_workbook(workbook, bundle)
        except OSError as error:
            raise WorkbookUnavailable("The Excel surface could not be written.") from error
        return _content(bundle)


def _write_workbook(workbook: Workbook, bundle: ReportBundle) -> None:
    for language in LANGUAGES:
        _write_report(workbook, bundle, language)
        _write_citations(workbook, bundle, language)
    _write_provenance(workbook, bundle)


def _write_report(workbook: Workbook, bundle: ReportBundle, language: str) -> None:
    """Disclosure, then the figure table, then the caveats every reader gets."""
    sheet = _sheet(workbook, _REPORT_SHEET[language], language)
    sheet.set_column(0, 0, _LABEL_WIDTH)
    sheet.set_column(1, len(_FIGURE_COLUMNS[language]) - 1, _VALUE_WIDTH)

    row = _write_row(sheet, 0, (_DISCLOSURE_HEADING[language], bundle.disclosure(language)))
    row = _write_row(sheet, row + 1, (_FIGURES_HEADING[language],))
    row = _write_row(sheet, row, _FIGURE_COLUMNS[language])
    for figure in bundle.figures:
        row = _write_row(sheet, row, _figure_cells(figure, language))

    row = _write_row(sheet, row + 1, (_CAVEATS_HEADING[language],))
    for caveat in bundle.caveats:
        row = _write_row(sheet, row, (caveat,))


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


def _content(bundle: ReportBundle) -> SurfaceContent:
    return SurfaceContent(
        surface=SURFACE_EXCEL,
        bundle_id=bundle.bundle_id,
        languages=tuple(_content_language(bundle, language) for language in LANGUAGES),
    )


def _content_language(bundle: ReportBundle, language: str) -> SurfaceLanguage:
    return SurfaceLanguage(
        language=language,
        direction=LANGUAGE_DIRECTION[language],
        stated=tuple(
            StatedFigure(figure_id=figure.figure_id, text=figure.renderings[language])
            for figure in bundle.figures
        ),
        caveats=bundle.caveats,
        disclosure=bundle.disclosure(language),
    )


def _require_directory(value: Path, name: str) -> None:
    if not value.is_dir():
        raise ValueError(f"{name} must be an existing directory.")
