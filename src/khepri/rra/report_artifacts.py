"""Worker-local payloads for one reconciled RRA report bundle.

The report domain describes what each surface presents with ``SurfaceContent``.
That claim stays content-free because it is also operational evidence.  The
types here carry the bytes only inside the report worker, between a renderer
and the encrypted publication boundary.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from khepri.rra.bundle import ReportBundle, SurfaceContent

HTML_MEDIA_TYPE = "text/html; charset=utf-8"
PDF_MEDIA_TYPE = "application/pdf"
XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

REQUIRED_ARTIFACT_KINDS = (
    "web_business_ar",
    "web_business_en",
    "web_evidence_ar",
    "web_evidence_en",
    "pdf_ar",
    "pdf_en",
    "excel",
)

ARTIFACT_METADATA = {
    "web_business_ar": (HTML_MEDIA_TYPE, "khepri-report.html"),
    "web_business_en": (HTML_MEDIA_TYPE, "khepri-report.html"),
    "web_evidence_ar": (HTML_MEDIA_TYPE, "khepri-evidence.html"),
    "web_evidence_en": (HTML_MEDIA_TYPE, "khepri-evidence.html"),
    "pdf_ar": (PDF_MEDIA_TYPE, "khepri-report.pdf"),
    "pdf_en": (PDF_MEDIA_TYPE, "khepri-report.pdf"),
    "excel": (XLSX_MEDIA_TYPE, "khepri-report.xlsx"),
}

SURFACE_ARTIFACT_KINDS = {
    "web": REQUIRED_ARTIFACT_KINDS[:4],
    "pdf": REQUIRED_ARTIFACT_KINDS[4:6],
    "excel": REQUIRED_ARTIFACT_KINDS[6:],
}


@dataclass(frozen=True, slots=True)
class ArtifactPayload:
    """One rendered artifact before it crosses the storage boundary."""

    kind: str
    media_type: str
    file_name: str
    content: bytes
    sha256_hex: str

    def __post_init__(self) -> None:
        _validate_artifact_identity(self)
        _validate_artifact_content(self)

    @classmethod
    def of(
        cls,
        *,
        kind: str,
        media_type: str,
        file_name: str,
        content: bytes,
    ) -> ArtifactPayload:
        return cls(
            kind=kind,
            media_type=media_type,
            file_name=file_name,
            content=content,
            sha256_hex=hashlib.sha256(content).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class MaterializedSurface:
    """A content-free surface claim beside its worker-local payloads."""

    content: SurfaceContent
    artifacts: tuple[ArtifactPayload, ...]

    def __post_init__(self) -> None:
        _validate_surface_identity(self)
        _validate_surface_size(self)


def _validate_artifact_identity(artifact: ArtifactPayload) -> None:
    expected = ARTIFACT_METADATA.get(artifact.kind)
    if expected is None:
        raise ValueError("Artifact kind is not governed.")
    _require_equal(
        artifact.media_type,
        expected[0],
        "Artifact media type does not match its kind.",
    )
    _require_equal(
        artifact.file_name,
        expected[1],
        "Artifact file name does not match its kind.",
    )


def _require_equal(actual: str, expected: str, message: str) -> None:
    if actual != expected:
        raise ValueError(message)


def _validate_artifact_content(artifact: ArtifactPayload) -> None:
    if not artifact.content:
        raise ValueError("Artifact content is required.")
    if artifact.sha256_hex != hashlib.sha256(artifact.content).hexdigest():
        raise ValueError("Artifact digest does not address its content.")


def _validate_surface_identity(surface: MaterializedSurface) -> None:
    expected = SURFACE_ARTIFACT_KINDS.get(surface.content.surface)
    if expected is None:
        raise ValueError("Materialized surface is not governed.")
    actual = tuple(artifact.kind for artifact in surface.artifacts)
    if actual != expected:
        raise ValueError("Materialized surface does not carry its exact artifacts.")


def _validate_surface_size(surface: MaterializedSurface) -> None:
    size = sum(len(artifact.content) for artifact in surface.artifacts)
    if surface.content.output_size_bytes != size:
        raise ValueError("Surface output size does not match its artifacts.")


class MaterializedRenderer(Protocol):
    """A renderer that keeps bytes off the operational-evidence contract."""

    @property
    def surface(self) -> str: ...

    def render_materialized(self, bundle: ReportBundle) -> MaterializedSurface: ...


__all__ = [
    "HTML_MEDIA_TYPE",
    "PDF_MEDIA_TYPE",
    "XLSX_MEDIA_TYPE",
    "ArtifactPayload",
    "ARTIFACT_METADATA",
    "MaterializedRenderer",
    "MaterializedSurface",
    "REQUIRED_ARTIFACT_KINDS",
    "SURFACE_ARTIFACT_KINDS",
]
