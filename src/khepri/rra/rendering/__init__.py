"""Concrete surfaces for one report bundle.

`khepri.rra.bundle` decides what a report says. The modules here decide only
how one surface presents it, and each of them satisfies `SurfaceRenderer` so
the assembler can refuse a surface that presents anything else.
"""

from __future__ import annotations

from khepri.rra.rendering.excel import (
    ExcelSurfaceRenderer,
    WorkbookUnavailable,
)
from khepri.rra.rendering.html import (
    HtmlReportRenderer,
    HtmlSurface,
    SurfaceRenderFailed,
    build_environment,
)

__all__ = [
    "ExcelSurfaceRenderer",
    "HtmlReportRenderer",
    "HtmlSurface",
    "SurfaceRenderFailed",
    "WorkbookUnavailable",
    "build_environment",
]
