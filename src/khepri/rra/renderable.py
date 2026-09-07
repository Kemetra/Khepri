"""Define the read-only seam shared by RRA-006 presentation siblings.

RRA-006 §Two-population bundle keeps the two-population bundle beside
``ReportBundle`` while requiring the same renderers and reconciliation. These
protocols express that common surface without making either identity govern the
other, and type-only imports keep this seam free of runtime cycles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from khepri.rra.bundle import ChartSpec, CitedEvidence, CitedFigure, StatedCaveat
    from khepri.rra.narrative import NarrativeDraft

__all__ = ["BundleIdentityDocument", "PresentationSection", "RenderableBundle"]


class BundleIdentityDocument(Protocol):
    """The provenance members shared by both RRA-006 bundle identities."""

    package_version: str
    coverage_manifest_identity: str | None
    coverage_signatures: tuple[str, ...]

    def as_document(self) -> dict[str, object]: ...


class PresentationSection(Protocol):
    """The section shape a renderer reads without choosing its governance."""

    section_id: str
    state: str
    reason: str | None
    figure_ids: tuple[str, ...]
    chart: ChartSpec | None


class RenderableBundle(Protocol):
    """The exact read-only bundle shape used by surfaces and reconciliation."""

    identity: BundleIdentityDocument
    figures: tuple[CitedFigure, ...]
    caveats: tuple[StatedCaveat, ...]
    narrative_state: str
    sections: tuple[PresentationSection, ...]
    narrative: NarrativeDraft | None
    evidence: tuple[CitedEvidence, ...]

    @property
    def bundle_version(self) -> str: ...

    @property
    def section_ids(self) -> tuple[str, ...]: ...

    @property
    def bundle_id(self) -> str: ...

    def figure(self, figure_id: str) -> CitedFigure | None: ...

    def disclosure(self, language: str) -> str: ...
