"""A-13 (#524): every workbook cell write is checked.

XlsxWriter reports a refused write by return code and raises nothing, so an unchecked
write could drop a cell or cut its text while the surface claim still reconciled.
Split from `test_rra006_excel_surface.py`, whose subject is what the workbook presents.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering.excel import ExcelSurfaceRenderer, WorkbookUnavailable
from tests.test_rra006_excel_surface import hostile_bundle, rendered


def _long_label_bundle(length: int) -> ReportBundle:
    """One figure whose label is `length` characters: Excel holds at most 32,767."""
    base = hostile_bundle()
    figure = replace(base.figures[0], label="L" * length)
    return replace(
        base,
        figures=(figure,),
        sections=(replace(base.sections[0], figure_ids=(figure.figure_id,)),),
    )


def test_a_cell_excel_would_truncate_fails_the_workbook(tmp_path: Path) -> None:
    """A-13 (#524). XlsxWriter reports a refused write by return code -- `-2` when it
    cut a string to 32,767 characters, `-1` when the cell is past the sheet's last
    row or column -- and raises nothing. Unchecked, the cell held a label the bundle
    never carried while the claim still reconciled.
    """
    bundle = _long_label_bundle(32_768)
    renderer = ExcelSurfaceRenderer()

    with pytest.raises(WorkbookUnavailable):
        renderer.render(bundle)
    # The workbook is built in memory (`#465`), so a refused one leaves nothing on
    # disk carrying the customer's content.
    assert list(tmp_path.iterdir()) == []


def test_a_label_at_the_cell_limit_is_written_whole(tmp_path: Path) -> None:
    """The boundary: 32,767 characters is a legal cell, and is written verbatim."""
    bundle = _long_label_bundle(32_767)

    _, workbook = rendered(bundle)

    assert "L" * 32_767 in workbook.texts


def test_a_write_past_the_last_row_is_refused(tmp_path: Path) -> None:
    """`-1`: the row limit, which a long enough figure table would reach."""
    import xlsxwriter

    from khepri.rra.rendering import excel_rows

    with xlsxwriter.Workbook(str(tmp_path / "rows.xlsx")) as workbook:
        sheet = workbook.add_worksheet()
        assert excel_rows.write_row(sheet, 1_048_575, ("last",)) == 1_048_576
        with pytest.raises(WorkbookUnavailable):
            excel_rows.write_row(sheet, 1_048_576, ("past",))
        with pytest.raises(WorkbookUnavailable):
            excel_rows.write_number(sheet, 1_048_576, 0, 1.0)


def test_the_workbook_error_is_one_class() -> None:
    """Re-exported rather than redefined, so `except WorkbookUnavailable` catches
    a refused cell write wherever a caller imported it from."""
    from khepri.rra.rendering import WorkbookUnavailable as exported
    from khepri.rra.rendering import excel_rows

    assert excel_rows.WorkbookUnavailable is WorkbookUnavailable is exported
