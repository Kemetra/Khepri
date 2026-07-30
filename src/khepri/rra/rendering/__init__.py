"""Concrete surfaces for one report bundle.

`khepri.rra.bundle` decides what a report says. The modules here decide only
how one surface presents it, and each of them satisfies `SurfaceRenderer` so
the assembler can refuse a surface that presents anything else.

The Chromium adapter is deliberately absent from these exports. It is the one
module that needs a browser binary, and importing this package must not.
Reach for `khepri.rra.rendering.chromium` explicitly when a real browser is
wanted.
"""

from __future__ import annotations

from khepri.rra.rendering.excel import (
    ExcelSurfaceRenderer,
    WorkbookUnavailable,
)
from khepri.rra.rendering.fonts import EmbeddedFont, load_report_fonts
from khepri.rra.rendering.html import (
    HtmlReportRenderer,
    HtmlSurface,
    SurfaceRenderFailed,
    build_environment,
)
from khepri.rra.rendering.pdf import (
    PagePrinter,
    PdfNotPrintable,
    PdfReportRenderer,
    PdfSurface,
    PrintablePage,
)

__all__ = [
    "EmbeddedFont",
    "ExcelSurfaceRenderer",
    "HtmlReportRenderer",
    "HtmlSurface",
    "PagePrinter",
    "PdfNotPrintable",
    "PdfReportRenderer",
    "PdfSurface",
    "PrintablePage",
    "SurfaceRenderFailed",
    "WorkbookUnavailable",
    "build_environment",
    "load_report_fonts",
]
