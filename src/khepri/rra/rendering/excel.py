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

**Charts, and why this paragraph changed.** It used to argue charts out, on the grounds
that an XlsxWriter chart series addresses numeric cells and Excel stores every numeric
cell as an IEEE 754 double -- which `KHEPRI-DEC-005` forbids as an authoritative
financial fact. That reasoning was sound and is why the prohibition still holds for
every cell this module writes today.

`APP-013` has since amended `KHEPRI-DEC-005` to permit a numeric cell *solely* as a
chart series address, on a dedicated worksheet holding no authoritative figure and no
citation identifier, excluded from the surface content a bundle reconciles. The
authoritative figure remains the decimal string on the section worksheet. That
amendment narrows the prohibition; it does not relax it.

The native chart path is the remaining half of this slice and is deliberately not here
yet: the per-section worksheets need no amendment and merge on their own, and parking
them behind the chart work would have held reviewable work behind a numeric write. Until
that lands, every cell in this module still goes through `write_string`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import xlsxwriter
from xlsxwriter.workbook import Workbook
from xlsxwriter.worksheet import Worksheet

from khepri.rra.bundle import (
    DIRECTION_RTL,
    GOVERNED_SECTION_STATES,
    LANGUAGE_DIRECTION,
    SURFACE_EXCEL,
    CitedFigure,
    ReportBundle,
    Section,
    StatedCaveat,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
    SurfaceUnavailable,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH

# v2 moves the figures off the two report sheets and onto a sheet per section. The
# version is machine-readable provenance a consumer selects its parser from, so a
# workbook with the new layout claiming v1 sends that consumer looking for a grid that
# is no longer there.
EXCEL_SURFACE_VERSION = "rra006.excel.v2"
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

# A worksheet per section per language. The name is built from the section identifier
# rather than translated, because a sheet name is an address: a reader following a
# reference, and any tooling reading the file, needs the same name in both workbooks.
# The heading inside the sheet is where the language belongs, and `_SECTION_COLUMNS`
# carries it.
_SECTION_SHEET_PREFIX = {LANGUAGE_ENGLISH: "en", LANGUAGE_ARABIC: "ar"}


def _section_sheet(section_id: str, language: str) -> str:
    return f"{_SECTION_SHEET_PREFIX[language]}_{section_id}"

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
        for mapping in (_FIGURE_COLUMNS, _CITATION_COLUMNS, _SECTION_COLUMNS)
        for headers in mapping.values()
        for header in headers
    }
    | set(_SECTIONS_HEADING.values())
    | set(GOVERNED_SECTION_STATES)
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
        """Write the workbook, then report what it presents and how large it is.

        The size is read from the closed file rather than accumulated while
        writing. A workbook is a compressed archive, so the bytes a caller ends
        up holding are only knowable once the archive has been finished, and any
        figure taken earlier would describe something that never existed.
        """
        path = self.path_for(bundle)
        try:
            with xlsxwriter.Workbook(str(path), dict(WORKBOOK_OPTIONS)) as workbook:
                _write_workbook(workbook, bundle)
            written = path.stat().st_size
        except OSError as error:
            raise WorkbookUnavailable("The Excel surface could not be written.") from error
        return _content(bundle, written)


def _write_workbook(workbook: Workbook, bundle: ReportBundle) -> None:
    for language in LANGUAGES:
        _write_report(workbook, bundle, language)
        for section in bundle.sections:
            _write_section(workbook, bundle, language, section)
        _write_citations(workbook, bundle, language)
    _write_provenance(workbook, bundle)


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


def _write_section(
    workbook: Workbook,
    bundle: ReportBundle,
    language: str,
    section: Section,
) -> None:
    """One analysis: its state, its figures, and the caveats that qualify it.

    A refused section still gets a worksheet. `RRA-008` refuses the affected analysis
    rather than the report, and a missing sheet is the one disclosure a reader cannot
    distinguish from an analysis nobody ran -- the same reason the page renders a
    heading and a reason rather than nothing.
    """
    sheet = _sheet(workbook, _section_sheet(section.section_id, language), language)
    sheet.set_column(0, 0, _LABEL_WIDTH)
    sheet.set_column(1, len(_FIGURE_COLUMNS[language]) - 1, _VALUE_WIDTH)

    row = _write_row(sheet, 0, _SECTION_COLUMNS[language])
    row = _write_row(sheet, row, (section.section_id, section.state, section.reason))
    row = _write_section_figures(sheet, row, bundle, language, section.section_id)
    _write_section_caveats(sheet, row, bundle, language, section.section_id)


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
