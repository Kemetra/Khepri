"""Minimal XLSX builder and reader for RRA workbook tests.

The builder makes inputs for intake and profiling. The reader opens a produced
workbook without a spreadsheet library, so a test can assert on the archive
itself: which cells carry text, and whether any part declares a formula or a
hyperlink.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ElementTree
import zipfile
from dataclasses import dataclass

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Override PartName="/xl/workbook.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/sheet1.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.'
    'spreadsheetml.worksheet+xml"/>'
    "</Types>"
)
_WORKBOOK = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets><sheet name="Sales" sheetId="1" r:id="rId1"/></sheets></workbook>'
)
_WORKBOOK_RELS = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
    'Target="worksheets/sheet1.xml"/></Relationships>'
)


def workbook(rows: list[list[str]]) -> bytes:
    """Build a single-worksheet XLSX carrying `rows` as inline strings."""
    body = "".join(
        f'<row r="{number}">{_cells(number, values)}</row>'
        for number, values in enumerate(rows, start=1)
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{body}</sheetData></worksheet>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _CONTENT_TYPES)
        archive.writestr("xl/workbook.xml", _WORKBOOK)
        archive.writestr("xl/_rels/workbook.xml.rels", _WORKBOOK_RELS)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


def _cells(row: int, values: list[str]) -> str:
    return "".join(
        f'<c r="{chr(64 + index)}{row}" t="inlineStr"><is><t>{value}</t></is></c>'
        for index, value in enumerate(values, start=1)
        if value != ""
    )


_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_DOCUMENT_RELATIONSHIP = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PACKAGE_RELATIONSHIP = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@dataclass(frozen=True, slots=True)
class ReadWorkbook:
    """A produced workbook as its archive presents it.

    `parts` is every archive member decoded, so a test can look for a formula
    or a hyperlink relationship anywhere in the package rather than only where
    it expected one. `sheets` and `cells` are keyed by the visible sheet name.
    """

    parts: dict[str, str]
    sheets: dict[str, str]
    cells: dict[str, list[list[str]]]

    @property
    def texts(self) -> list[str]:
        """Every populated cell of every sheet, as text."""
        return [
            value
            for rows in self.cells.values()
            for row in rows
            for value in row
            if value != ""
        ]


def read(data: bytes) -> ReadWorkbook:
    """Open an XLSX archive and resolve its worksheets to text."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        parts = {
            name: archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.endswith((".xml", ".rels"))
        }
    shared = _shared_strings(parts.get("xl/sharedStrings.xml"))
    sheets = {
        name: parts[member]
        for name, member in _sheet_members(parts).items()
        if member in parts
    }
    return ReadWorkbook(
        parts=parts,
        sheets=sheets,
        cells={name: _rows(xml, shared) for name, xml in sheets.items()},
    )


def _sheet_members(parts: dict[str, str]) -> dict[str, str]:
    targets = {
        element.get("Id"): element.get("Target", "")
        for element in ElementTree.fromstring(
            parts["xl/_rels/workbook.xml.rels"]
        ).iter(f"{_PACKAGE_RELATIONSHIP}Relationship")
    }
    return {
        str(element.get("name")): f"xl/{targets[element.get(f'{_DOCUMENT_RELATIONSHIP}id')]}"
        for element in ElementTree.fromstring(parts["xl/workbook.xml"]).iter(f"{_MAIN}sheet")
    }


def _shared_strings(xml: str | None) -> list[str]:
    if xml is None:
        return []
    return [
        "".join(entry.itertext())
        for entry in ElementTree.fromstring(xml).iter(f"{_MAIN}si")
    ]


def _rows(xml: str, shared: list[str]) -> list[list[str]]:
    return [
        _row(element, shared)
        for element in ElementTree.fromstring(xml).iter(f"{_MAIN}row")
    ]


def _row(element: ElementTree.Element, shared: list[str]) -> list[str]:
    values: list[str] = []
    for cell in element.iter(f"{_MAIN}c"):
        index = _column_index(str(cell.get("r", "A1")))
        values.extend([""] * (index + 1 - len(values)))
        values[index] = _cell_text(cell, shared)
    return values


def _cell_text(cell: ElementTree.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(cell.itertext())
    value = cell.find(f"{_MAIN}v")
    if value is None or value.text is None:
        return ""
    if kind == "s":
        return shared[int(value.text)]
    return value.text


def _column_index(reference: str) -> int:
    letters = "".join(character for character in reference if character.isalpha())
    index = 0
    for character in letters:
        index = index * 26 + (ord(character) - ord("A") + 1)
    return index - 1
