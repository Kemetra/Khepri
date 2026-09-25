from __future__ import annotations

import io
import re
import struct
import zipfile
import zlib

import pytest

from khepri.rra.intake import (
    CSV_MEDIA_TYPE,
    MAX_XLSX_EXPANDED_BYTES,
    XLSX_MEDIA_TYPE,
    IntakeRejected,
    UploadAccumulator,
    UploadTooLarge,
)


def test_declared_size_above_50_mb_is_rejected_before_streaming() -> None:
    with pytest.raises(UploadTooLarge):
        UploadAccumulator(declared_size=50 * 1024 * 1024 + 1)


def test_streaming_limit_rejects_the_first_excess_byte() -> None:
    upload = UploadAccumulator(declared_size=None, max_bytes=4)

    upload.append(b"1234")

    with pytest.raises(UploadTooLarge):
        upload.append(b"5")


def test_declared_size_must_match_the_completed_stream() -> None:
    upload = UploadAccumulator(declared_size=10)
    upload.append(b"a,b\n1,2\n")

    with pytest.raises(IntakeRejected):
        upload.finish()


def test_csv_is_detected_from_content_across_chunk_boundaries() -> None:
    upload = UploadAccumulator(declared_size=None)
    upload.append(b"date,reve")
    upload.append(b"nue\n2026-07-29,125.50\n")

    validated = upload.finish()

    assert validated.media_type == CSV_MEDIA_TYPE
    assert validated.size_bytes == 31
    assert validated.sha256_hex == (
        "9281d56e1cd7936815ac01501b6437cfc40663f3a5e6e6cdefcee51c5e7cc68c"
    )


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b" \r\n\t",
        b'header,value\n"unterminated,1\n',
        b"header,\x00value\none,two\n",
        b'{"revenue": 125}',
        b"date,revenue\n",
    ],
)
def test_empty_or_malformed_csv_is_rejected(content: bytes) -> None:
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)

    with pytest.raises(IntakeRejected):
        upload.finish()


def test_one_populated_xlsx_worksheet_is_accepted() -> None:
    content = _xlsx({"Sales": ["date", "revenue"]})
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)

    validated = upload.finish()

    assert validated.media_type == XLSX_MEDIA_TYPE
    assert validated.size_bytes == len(content)


def test_two_populated_xlsx_worksheets_are_rejected() -> None:
    content = _xlsx(
        {
            "Sales": ["date", "revenue"],
            "Stores": ["store", "region"],
        }
    )
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)

    with pytest.raises(IntakeRejected):
        upload.finish()


def test_empty_xlsx_workbook_is_rejected() -> None:
    content = _xlsx({"Sales": []})
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)

    with pytest.raises(IntakeRejected):
        upload.finish()


def test_xlsx_sheet_must_use_a_worksheet_relationship() -> None:
    content = _xlsx(
        {"Sales": ["revenue"]},
        worksheet_relationship=False,
    )
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)

    with pytest.raises(IntakeRejected):
        upload.finish()


def test_encrypted_or_macro_enabled_workbooks_are_rejected() -> None:
    encrypted = UploadAccumulator(declared_size=8)
    encrypted.append(bytes.fromhex("d0cf11e0a1b11ae1"))

    with pytest.raises(IntakeRejected):
        encrypted.finish()

    macro_content = _xlsx({"Sales": ["revenue"]}, macro_enabled=True)
    macro = UploadAccumulator(declared_size=len(macro_content))
    macro.append(macro_content)

    with pytest.raises(IntakeRejected):
        macro.finish()


def test_xlsx_expansion_limit_is_checked_before_xml_parsing() -> None:
    content = _xlsx({"Sales": ["x" * 5_000]})
    upload = UploadAccumulator(
        declared_size=len(content),
        max_expanded_bytes=1_000,
    )
    upload.append(content)

    with pytest.raises(IntakeRejected):
        upload.finish()


def test_xml_part_read_is_bounded_by_actual_inflated_bytes() -> None:
    """A part read must stop at the byte budget even if archive metadata understates it."""
    from khepri.rra.intake import _read_xml_part

    class LyingArchive:
        def open(self, path: str) -> io.BytesIO:
            assert path == "xl/worksheets/sheet1.xml"
            return io.BytesIO(b"<worksheet>" + b"x" * 2_000 + b"</worksheet>")

    with pytest.raises(IntakeRejected):
        _read_xml_part(LyingArchive(), "xl/worksheets/sheet1.xml", max_bytes=1_000)


def _xlsx(
    sheets: dict[str, list[str]],
    *,
    macro_enabled: bool = False,
    worksheet_relationship: bool = True,
) -> bytes:
    workbook_sheets: list[str] = []
    relationships: list[str] = []
    content_type_overrides: list[str] = []
    worksheet_parts: dict[str, str] = {}
    for index, (name, values) in enumerate(sheets.items(), start=1):
        workbook_sheets.append(
            f'<sheet name="{name}" sheetId="{index}" r:id="rId{index}"/>'
        )
        relationships.append(
            '<Relationship '
            f'Id="rId{index}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            f"relationships/{'worksheet' if worksheet_relationship else 'styles'}\" "
            f'Target="worksheets/sheet{index}.xml"/>'
        )
        content_type_overrides.append(
            '<Override '
            f'PartName="/xl/worksheets/sheet{index}.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.worksheet+xml"/>'
        )
        cells = "".join(
            f'<c r="{chr(64 + cell_index)}1" t="inlineStr"><is><t>{value}</t></is></c>'
            for cell_index, value in enumerate(values, start=1)
        )
        row = f'<row r="1">{cells}</row>' if cells else ""
        worksheet_parts[f"xl/worksheets/sheet{index}.xml"] = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/'
            f'spreadsheetml/2006/main"><sheetData>{row}</sheetData></worksheet>'
        )

    workbook_content_type = (
        "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
        if macro_enabled
        else "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet.main+xml"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        f'<Override PartName="/xl/workbook.xml" ContentType="{workbook_content_type}"/>'
        f"{''.join(content_type_overrides)}"
        "</Types>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{''.join(workbook_sheets)}</sheets></workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{''.join(relationships)}</Relationships>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        for path, xml in worksheet_parts.items():
            archive.writestr(path, xml)
        if macro_enabled:
            archive.writestr("xl/vbaProject.bin", b"macro")
    return buffer.getvalue()


_WORKSHEET_PART = "xl/worksheets/sheet1.xml"
_UTF16_WORKSHEET = (
    '<?xml version="1.0" encoding="UTF-16"?>'
    "{doctype}"
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
    '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>revenue</t></is></c>'
    "</row></sheetData></worksheet>"
)


def _with_part(content: bytes, path: str, replacement: bytes) -> bytes:
    """The same workbook with one part's bytes replaced verbatim."""
    source = zipfile.ZipFile(io.BytesIO(content))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in source.namelist():
            archive.writestr(name, replacement if name == path else source.read(name))
    return buffer.getvalue()


def _utf16_worksheet_upload(doctype: str) -> UploadAccumulator:
    part = _UTF16_WORKSHEET.format(doctype=doctype).encode("utf-16")
    content = _with_part(_xlsx({"Sales": ["revenue"]}), _WORKSHEET_PART, part)
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)
    return upload


def test_a_utf16_worksheet_without_a_document_type_is_accepted() -> None:
    """The control for the test below: UTF-16 alone is a legal XML encoding.

    Without it, a guard that refused every UTF-16 part would pass the DTD test
    for the wrong reason.
    """
    validated = _utf16_worksheet_upload("").finish()

    assert validated.media_type == XLSX_MEDIA_TYPE


@pytest.mark.parametrize(
    "doctype",
    [
        '<!DOCTYPE worksheet [<!ENTITY cell "revenue">]>',
        "<!DOCTYPE worksheet>",
    ],
)
def test_a_document_type_in_a_utf16_part_is_rejected(doctype: str) -> None:
    """`#530` S-05: the DTD guard compared raw bytes against ASCII markers.

    `<!DOCTYPE` encoded as UTF-16 interleaves a zero byte after every character,
    so it never contains the byte string `<!DOCTYPE`, while `ElementTree` decodes
    the part per its BOM and parses the declaration anyway. The guard must see
    what the parser sees.
    """
    with pytest.raises(IntakeRejected):
        _utf16_worksheet_upload(doctype).finish()


def test_a_malformed_xml_part_is_rejected_not_raised() -> None:
    """The DTD guard parses before `ElementTree` does, so it meets malformed XML first.

    Its parser raises `ExpatError`, which is not the `ElementTree.ParseError` the
    caller maps to a refusal; escaping, it would be a server error instead.
    """
    content = _with_part(_xlsx({"Sales": ["revenue"]}), _WORKSHEET_PART, b"<worksheet")
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)

    with pytest.raises(IntakeRejected):
        upload.finish()


def test_a_macro_content_type_in_a_utf16_content_types_part_is_rejected() -> None:
    """The macro guard's sibling of S-05: `[Content_Types].xml` re-encoded as UTF-16.

    No `vbaProject` part is present, so the part-name check cannot catch it; only the
    content type says the workbook is macro-enabled, and the byte check cannot read it.
    """
    plain = _xlsx({"Sales": ["revenue"]})
    types = zipfile.ZipFile(io.BytesIO(plain)).read("[Content_Types].xml").decode("utf-8")
    macro_types = types.replace('encoding="UTF-8"', 'encoding="UTF-16"').replace(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        "application/vnd.ms-excel.sheet.macroEnabled.main+xml",
    )
    assert "macroEnabled" in macro_types
    content = _with_part(plain, "[Content_Types].xml", macro_types.encode("utf-16"))
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)

    with pytest.raises(IntakeRejected):
        upload.finish()


def _recompressed(content: bytes, method: int) -> bytes:
    """The same workbook with every part stored under one compression method."""
    source = zipfile.ZipFile(io.BytesIO(content))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=method) as archive:
        for name in source.namelist():
            archive.writestr(name, source.read(name))
    return buffer.getvalue()


@pytest.mark.parametrize(
    "method",
    [
        pytest.param(zipfile.ZIP_BZIP2, id="bzip2"),
        pytest.param(zipfile.ZIP_LZMA, id="lzma"),
    ],
)
def test_a_workbook_member_outside_stored_or_deflated_is_rejected(method: int) -> None:
    """CWE-400: `read(max_bytes + 1)` clips the output, not the decompressor's allocation.

    For BZIP2 and LZMA the decompressor can allocate far more than the budget before a single
    byte comes back, so a member under either method is refused before it is opened. Excel writes
    STORED and DEFLATED only; the accepted control below is DEFLATED.
    """
    content = _recompressed(_xlsx({"Sales": ["revenue"]}), method)
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)

    with pytest.raises(IntakeRejected):
        upload.finish()


def test_a_stored_workbook_is_still_accepted() -> None:
    """The control: refusing exotic methods must not refuse an uncompressed workbook."""
    content = _recompressed(_xlsx({"Sales": ["revenue"]}), zipfile.ZIP_STORED)
    upload = UploadAccumulator(declared_size=len(content))
    upload.append(content)

    assert upload.finish().media_type == XLSX_MEDIA_TYPE


# --- #434 §1: a member's recorded size must be its actual inflated size ----------------------

_SHARED_STRINGS_PART = "xl/sharedStrings.xml"
_SHARED_STRINGS = b"<sst>" + b"x" * 20_000 + b"</sst>"


def _with_member(content: bytes, path: str, data: bytes) -> bytes:
    """The same workbook with one more member, a part intake itself never parses."""
    buffer = io.BytesIO(content)
    with zipfile.ZipFile(buffer, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(path, data)
    return buffer.getvalue()


def _honest_with_shared_strings() -> bytes:
    return _with_member(_xlsx({"Sales": ["revenue"]}), _SHARED_STRINGS_PART, _SHARED_STRINGS)


def _misrecorded(content: bytes, path: str, *, size: int, forge_crc: bool) -> bytes:
    """The workbook with `path`'s recorded size -- and optionally its CRC -- describing a prefix.

    Both the local header (CRC at +14, size at +22) and the central directory record (CRC at +16,
    size at +24) are rewritten, so neither header tells the truth about the deflate stream.
    """
    data = bytearray(content)
    name = path.encode()
    local = zipfile.ZipFile(io.BytesIO(content)).getinfo(path).header_offset
    central = next(
        match.start()
        for match in re.finditer(b"PK\x01\x02", data)
        if data[match.start() + 46 : match.start() + 46 + len(name)] == name
    )
    prefix_crc = zlib.crc32(_SHARED_STRINGS[:size])
    for crc_at, size_at in ((local + 14, local + 22), (central + 16, central + 24)):
        struct.pack_into("<I", data, size_at, size)
        if forge_crc:
            struct.pack_into("<I", data, crc_at, prefix_crc)
    return bytes(data)


def _finished(content: bytes, *, max_expanded_bytes: int = MAX_XLSX_EXPANDED_BYTES) -> str:
    upload = UploadAccumulator(
        declared_size=len(content), max_expanded_bytes=max_expanded_bytes
    )
    upload.append(content)
    return upload.finish().media_type


def test_an_unparsed_member_with_a_true_recorded_size_is_accepted() -> None:
    """The control: inflating every member must not refuse an honest one intake never parses."""
    assert _finished(_honest_with_shared_strings()) == XLSX_MEDIA_TYPE


@pytest.mark.parametrize(
    "forge_crc",
    [pytest.param(False, id="size_only"), pytest.param(True, id="size_and_prefix_crc")],
)
def test_a_member_whose_recorded_size_understates_its_stream_is_rejected(forge_crc: bool) -> None:
    """`#434` §1: the expansion cap must bound what a member inflates to, not what it declares.

    Intake parses four kinds of part. calamine later reads the whole archive, shared strings
    included, so a member intake never opens is still inflated in the web process. Its declared
    size says 10 bytes; its deflate stream holds 20 KB. With the CRC forged to match the 10-byte
    prefix, even a reader that stops at the declared size and checks the CRC would pass it.
    """
    content = _misrecorded(
        _honest_with_shared_strings(), _SHARED_STRINGS_PART, size=10, forge_crc=forge_crc
    )

    with pytest.raises(IntakeRejected):
        _finished(content)


def test_actual_inflate_is_bounded_by_the_expansion_budget() -> None:
    """The budget counts every member's bytes, the unparsed ones included."""
    content = _honest_with_shared_strings()

    with pytest.raises(IntakeRejected):
        _finished(content, max_expanded_bytes=len(_SHARED_STRINGS))
