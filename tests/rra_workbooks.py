"""Minimal XLSX builder and reader for RRA workbook tests.

The builder makes inputs for intake and profiling. The reader opens a produced
workbook without a spreadsheet library, so a test can assert on the archive
itself: which cells carry text, which carry a number, whether any part declares a
formula or a hyperlink, and which chart parts a given worksheet draws.
"""

from __future__ import annotations

import io
import posixpath
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

    `size_bytes` is the size of the archive that was opened. It is read from the
    bytes rather than taken from whoever produced them, so a test can compare a
    renderer's claim about how large its output was against the file itself.

    `numbers` is kept apart from `cells` because the distinction is the whole point
    of `KHEPRI-DEC-005`: a numeric cell is an IEEE 754 double and a text cell is the
    decimal string the fact package produced. Resolved to text it is impossible to
    tell them apart, so a reader that only had `cells` could not see a governed
    figure quietly becoming a float.
    """

    parts: dict[str, str]
    members: dict[str, str]
    sheets: dict[str, str]
    cells: dict[str, list[list[str]]]
    numbers: dict[str, list[str]]
    size_bytes: int

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

    def charts(self, sheet: str) -> list[str]:
        """Every chart part drawn on one worksheet, as XML.

        Followed through the package relationships -- worksheet to drawing to chart
        -- rather than by collecting `xl/charts/*`. Which sheet a chart is drawn on
        is the claim being checked, and a workbook that put the Arabic chart on the
        English sheet would satisfy any assertion made over all charts at once.
        """
        return [
            self.parts[chart]
            for drawing in self._drawing_members(sheet)
            for chart in _targets(self.parts, drawing)
            if "/charts/" in chart and chart in self.parts
        ]

    def drawings(self, sheet: str) -> list[str]:
        """Every drawing part on one worksheet, as XML.

        Where an embedded object's alternative text lives: a chart's `descr` is an
        attribute of the drawing that anchors it, not of the chart itself.
        """
        return [
            self.parts[drawing]
            for drawing in self._drawing_members(sheet)
            if drawing in self.parts
        ]

    def _drawing_members(self, sheet: str) -> list[str]:
        return [
            target
            for target in _targets(self.parts, self.members[sheet])
            if "/drawings/" in target
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
    members = {
        name: member
        for name, member in _sheet_members(parts).items()
        if member in parts
    }
    sheets = {name: parts[member] for name, member in members.items()}
    return ReadWorkbook(
        parts=parts,
        members=members,
        sheets=sheets,
        cells={name: _rows(xml, shared) for name, xml in sheets.items()},
        numbers={name: _numbers(xml) for name, xml in sheets.items()},
        size_bytes=len(data),
    )


def _rels_member(member: str) -> str:
    directory, base = posixpath.split(member)
    return f"{directory}/_rels/{base}.rels"


def _targets(parts: dict[str, str], member: str) -> list[str]:
    """Every part one part points at, resolved to an archive member name.

    Targets are relative to the referring part's own directory, so `../charts/chart1.xml`
    from `xl/drawings/drawing1.xml` is `xl/charts/chart1.xml`.
    """
    rels = parts.get(_rels_member(member))
    if rels is None:
        return []
    directory = posixpath.dirname(member)
    return [
        posixpath.normpath(posixpath.join(directory, str(element.get("Target"))))
        for element in ElementTree.fromstring(rels).iter(
            f"{_PACKAGE_RELATIONSHIP}Relationship"
        )
    ]


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


def _numbers(xml: str) -> list[str]:
    """Every cell written as a number, as the digits the archive holds.

    A numeric cell carries no `t` attribute; every text form declares one. Returned
    as the raw string rather than a float so a test can see the digits that were
    written and not a re-formatting of them.
    """
    found: list[str] = []
    for cell in ElementTree.fromstring(xml).iter(f"{_MAIN}c"):
        value = cell.find(f"{_MAIN}v")
        if cell.get("t") is None and value is not None and value.text is not None:
            found.append(value.text)
    return found


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
