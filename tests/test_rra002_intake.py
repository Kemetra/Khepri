from __future__ import annotations

import io
import zipfile

import pytest

from khepri.rra.intake import (
    CSV_MEDIA_TYPE,
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
