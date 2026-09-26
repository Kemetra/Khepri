"""The local pipeline renders its surfaces in the order a publication requires.

`ReportPublication` refuses any artifact sequence other than
`REQUIRED_ARTIFACT_KINDS`, and the pipeline concatenates artifacts in renderer
order. The local wiring once appended the PDF renderer after Excel, so every
local report job settled `retryable` with every artifact present — a defect only
`test_local_journey` could see, and that test skips wherever the local stack is
not running, which includes CI.

No stack is needed here: the order is a property of the wiring, not of
PostgreSQL or the object store.
"""

from __future__ import annotations

from pathlib import Path

from khepri.local.wiring import local_renderers
from khepri.rra.bundle import REQUIRED_SURFACES
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS


class UnusedPrinter:
    """Constructs the PDF renderer; ordering never asks it to print."""

    def print_pdf(self, html: str, *, language: str) -> bytes:  # pragma: no cover
        raise AssertionError("ordering must not render")


def test_local_renderers_follow_the_required_surface_order(tmp_path: Path) -> None:
    renderers = local_renderers(workbooks=tmp_path, printer=UnusedPrinter())

    assert tuple(renderer.surface for renderer in renderers) == REQUIRED_SURFACES


def test_required_surface_order_is_the_artifact_order() -> None:
    """Surface order is only the right proxy while artifacts group by surface in it."""
    surfaces_in_artifact_order = tuple(
        dict.fromkeys(kind.split("_", 1)[0] for kind in REQUIRED_ARTIFACT_KINDS)
    )

    assert surfaces_in_artifact_order == REQUIRED_SURFACES
