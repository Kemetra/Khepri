"""The two-population bundle's one worksheet.

`RRA-006` §Two-population bundle: a surface never shows a delta without both operands
beside it, and a cell has to say which population it belongs to. `excel.py`'s business
sheets are keyed by metric and cannot say that, so the sibling's cells are written
here, under the section's governed heading, through the same row primitives every
business sheet uses. For a report bundle this writes nothing.
"""

from __future__ import annotations

from xlsxwriter.workbook import Workbook

from khepri.rra.bundle import SECTION_CROSSVERSION
from khepri.rra.renderable import RenderableBundle
from khepri.rra.rendering.excel_rows import (
    BUSINESS_COLUMNS,
    DISCLOSURE_HEADING,
    LABEL_WIDTH,
    VALUE_WIDTH,
    business_cells,
    sheet,
    write_row,
)
from khepri.rra.rendering.wording import SECTION_HEADINGS

__all__ = ["write_crossversion_sheet"]


def write_crossversion_sheet(workbook: Workbook, bundle: RenderableBundle, language: str) -> None:
    """The two-population bundle's one sheet, or nothing for a report bundle.

    `RRA-006` §Two-population bundle: a surface never shows a delta without both
    operands beside it, and a cell has to say which population it belongs to. The
    business sheets are keyed by metric and cannot say that, so the sibling's cells
    are written here under the section's governed heading, named the way every
    business row is named -- measure, then role -- and the `RRA-009` disclosure
    opens the sheet because this bundle has no executive summary to carry it.
    """
    figures = [figure for figure in bundle.figures if figure.section == SECTION_CROSSVERSION]
    if not figures:
        return
    worksheet = sheet(workbook, SECTION_HEADINGS[language][SECTION_CROSSVERSION], language)
    worksheet.set_column(0, 0, LABEL_WIDTH * 2)
    worksheet.set_column(1, 1, VALUE_WIDTH)
    row = write_row(worksheet, 0, (DISCLOSURE_HEADING[language], bundle.disclosure(language)))
    row = write_row(worksheet, row + 1, BUSINESS_COLUMNS[language])
    for figure in figures:
        row = write_row(worksheet, row, business_cells(figure, language))
