"""The row and sheet primitives every worksheet of the workbook is written with.

Extracted from `excel.py` so that the report bundle's writer and the two-population
bundle's writer (`excel_crossversion.py`) share one definition of a text row, a
right-to-left sheet, and a business row's name -- and so `excel.py` stays under the
module size CodeScene tracks for it.
"""

from __future__ import annotations

from xlsxwriter.workbook import Workbook
from xlsxwriter.worksheet import Worksheet

from khepri.rra.bundle import (
    DIRECTION_RTL,
    LANGUAGE_DIRECTION,
    CitedFigure,
    SurfaceUnavailable,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering.wording import (
    business_metric_name,
    category_of,
    kind_qualifier,
    worded,
)

__all__ = [
    "BUSINESS_COLUMNS",
    "DISCLOSURE_HEADING",
    "LABEL_WIDTH",
    "VALUE_WIDTH",
    "WorkbookUnavailable",
    "business_cells",
    "business_name",
    "sheet",
    "write_number",
    "write_row",
    "write_text",
]

LABEL_WIDTH = 34
VALUE_WIDTH = 22

BUSINESS_COLUMNS = {
    LANGUAGE_ENGLISH: ("Figure", "Value"),
    LANGUAGE_ARABIC: ("البيان", "القيمة"),
}
DISCLOSURE_HEADING = {
    LANGUAGE_ENGLISH: "About this report",
    LANGUAGE_ARABIC: "عن هذا التقرير",
}


class WorkbookUnavailable(SurfaceUnavailable, RuntimeError):
    """The workbook could not be written, so this surface does not exist.

    Subclasses `SurfaceUnavailable` so the assembler treats it as a failed
    surface, and `RuntimeError` because it is operational rather than a
    statement about the bundle. Defined here rather than in `excel.py`, which
    re-exports it, because the checked writes below raise it and `excel.py`
    imports this module.
    """


def sheet(workbook: Workbook, name: str, language: str) -> Worksheet:
    sheet = workbook.add_worksheet(name)
    if LANGUAGE_DIRECTION[language] == DIRECTION_RTL:
        # The only place direction is real rather than declared: this sets
        # `rightToLeft` on the sheet view, so Arabic columns run the way Arabic
        # reads instead of merely being labelled that way.
        sheet.right_to_left()
    return sheet


def write_row(sheet: Worksheet, row: int, values: tuple[str | None, ...]) -> int:
    """Write one row of literal text and return the next row.

    `write_string` rather than `write`: it has no coercion path at all, so a
    label beginning `=` is a string here even if a future caller constructs the
    workbook without `WORKBOOK_OPTIONS`.
    """
    for column, value in enumerate(values):
        if value is not None:
            write_text(sheet, row, column, value)
    return row + 1


def write_text(sheet: Worksheet, row: int, column: int, value: str) -> None:
    """One text cell, refused rather than altered.

    XlsxWriter reports a refused write by return code and raises nothing: `-1`
    when the cell lies past the sheet's last row or column, which drops it, and
    `-2` when the string exceeds 32,767 characters, which stores it cut short. A
    dropped figure and a truncated label both leave a workbook that says something
    other than the bundle while the claim -- built from the bundle -- still
    reconciles. So a non-zero code fails the surface, the way `insert_chart`'s does.
    """
    _checked(sheet.write_string(row, column, value))


def write_number(sheet: Worksheet, row: int, column: int, number: float) -> None:
    """One numeric cell, checked on the same terms as `write_text`.

    Only the chart data sheet writes numbers (`excel._write_chart_value`), and a
    dropped one would draw a series short of the figures it was built from.
    """
    _checked(sheet.write_number(row, column, number))


def _checked(result: int) -> None:
    if result != 0:
        raise WorkbookUnavailable("A governed cell could not be written.")


def business_cells(figure: CitedFigure, language: str) -> tuple[str, ...]:
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
    return (business_name(figure, language), figure.renderings[language])


def business_name(figure: CitedFigure, language: str) -> str:
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
