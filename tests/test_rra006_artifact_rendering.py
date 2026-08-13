from __future__ import annotations

import hashlib
import importlib
import importlib.util

import pytest

from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.pdf import PdfReportRenderer
from tests.test_rra006_html_surface import package
from tests.test_rra006_pdf_surface import FakePrinter


def artifact_module():
    spec = importlib.util.find_spec("khepri.rra.report_artifacts")
    assert spec is not None, "the report artifact model is not implemented"
    return importlib.import_module("khepri.rra.report_artifacts")


def test_required_artifact_matrix_is_exact() -> None:
    artifacts = artifact_module()

    assert artifacts.REQUIRED_ARTIFACT_KINDS == (
        "web_business_ar",
        "web_business_en",
        "web_evidence_ar",
        "web_evidence_en",
        "pdf_ar",
        "pdf_en",
        "excel",
    )


def test_artifact_payload_builds_its_content_address() -> None:
    artifacts = artifact_module()
    content = b"governed report bytes"

    payload = artifacts.ArtifactPayload.of(
        kind="excel",
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        file_name="khepri-report.xlsx",
        content=content,
    )

    assert payload.sha256_hex == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("kind", "csv", "kind"),
        ("media_type", "text/plain", "media type"),
        ("file_name", "../../report.xlsx", "file name"),
        ("content", b"", "content"),
        ("sha256_hex", "0" * 64, "digest"),
    ],
)
def test_artifact_payload_rejects_untrusted_metadata(
    field: str,
    value: str | bytes,
    message: str,
) -> None:
    artifacts = artifact_module()
    content = b"xlsx"
    values: dict[str, str | bytes] = {
        "kind": "excel",
        "media_type": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        "file_name": "khepri-report.xlsx",
        "content": content,
        "sha256_hex": hashlib.sha256(content).hexdigest(),
    }
    values[field] = value

    with pytest.raises(ValueError, match=message):
        artifacts.ArtifactPayload(**values)


def test_html_renderer_materializes_business_and_evidence_documents() -> None:
    materialized = HtmlReportRenderer().render_materialized(ReportBundle.of(package()))

    assert tuple(item.kind for item in materialized.artifacts) == (
        "web_business_ar",
        "web_business_en",
        "web_evidence_ar",
        "web_evidence_en",
    )
    assert materialized.content.output_size_bytes == sum(
        len(item.content) for item in materialized.artifacts
    )
    assert all(item.content.startswith(b"<!doctype html>") for item in materialized.artifacts)


def test_pdf_renderer_materializes_one_document_per_language() -> None:
    materialized = PdfReportRenderer(printer=FakePrinter()).render_materialized(
        ReportBundle.of(package())
    )

    assert tuple(item.kind for item in materialized.artifacts) == ("pdf_ar", "pdf_en")
    assert all(item.content.startswith(b"%PDF-") for item in materialized.artifacts)


def test_excel_renderer_materializes_the_closed_workbook(tmp_path) -> None:
    materialized = ExcelSurfaceRenderer(directory=tmp_path).render_materialized(
        ReportBundle.of(package())
    )

    assert tuple(item.kind for item in materialized.artifacts) == ("excel",)
    assert materialized.artifacts[0].content.startswith(b"PK")
    assert materialized.content.output_size_bytes == len(materialized.artifacts[0].content)
