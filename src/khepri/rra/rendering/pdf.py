"""The tagged PDF surface of one report bundle.

**One template, two surfaces.** This module renders no page of its own. It calls
the same `build_cells`, `build_context` and `build_content` the web surface calls,
adds a print stylesheet and font payloads to that context, and renders a template
that *extends* the web template rather than replacing it. KHEPRI-DEC-005
consolidated bilingual rendering into one engine for a specific reason: Arabic
and English parity, the governed disclosure, and the figure table are each
correct in one place, and a forked print template would be a second place for
them to drift. What this module owns is everything a *page* needs and a viewport
does not -- a page box, break behaviour, embedded faces -- and nothing else.

**It presents figures; it never produces one.** Inherited from the web surface
and true for the same reason: the view model carries `text`, the arithmetic
happened once in `bundle`, and a `Decimal` this renderer could format is never
in reach. A test holds it by making the string and the `Decimal` disagree.

**The browser is a port, not an import.** Chromium is a large external binary
that a build, a container, or an air-gapped checkout may not have. Rendering is
therefore expressed against `PagePrinter` -- one method, HTML in, PDF bytes out
-- so the whole surface is verifiable with a hand-written fake and no browser at
all. `chromium.py` holds the one adapter that needs Playwright, and this module
does not import it.

**What a PDF has to be before it is published.** RRA-006 asks for a *tagged,
readable* PDF, and neither property is visible in the object a renderer returns:
`bytes` is `bytes`. So the bytes are inspected before a `PdfSurface` can exist.
An untagged PDF carries no structure tree and is unreadable to a screen reader; a
PDF with no embedded font program renders in whatever the opening machine happens
to have, which for Arabic is frequently nothing. Both are refused here rather
than discovered by a customer. `BundleAssembler` turns that refusal into an
incomplete bundle, which is the correct outcome: no report is better than an
unreadable one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jinja2 import Environment

from khepri.rra.bundle import (
    LANGUAGE_DIRECTION,
    SURFACE_PDF,
    ReportBundle,
    SurfaceContent,
)
from khepri.rra.narrative import REQUIRED_LANGUAGES
from khepri.rra.rendering.fonts import EmbeddedFont, load_report_fonts
from khepri.rra.rendering.html import (
    FigureCell,
    build_cells,
    build_content,
    build_context,
    build_environment,
)
from khepri.rra.report_artifacts import (
    PDF_MEDIA_TYPE,
    ArtifactPayload,
    MaterializedSurface,
)

PDF_SURFACE_VERSION = "rra006.pdf.v1"

PDF_TEMPLATE_NAME = "report.pdf.html.j2"
PRINT_STYLESHEET_NAME = "report.print.css"

# What Chromium's PDF writer puts in a file it tagged, and what it puts in a file
# carrying an embedded font program. Named here, in one place, because they are
# the only evidence available from the bytes and a wrong marker would refuse
# every report rather than a bad one.
PDF_HEADER = b"%PDF-"
PDF_TRAILER = b"%%EOF"
TAGGED_MARKERS = (b"/StructTreeRoot", b"/MarkInfo", b"/Marked true")
# `/FontFile`, `/FontFile2` and `/FontFile3` all begin with this, and any of them
# is an embedded program rather than a reference to an installed face.
EMBEDDED_FONT_MARKER = b"/FontFile"


class PdfNotPrintable(ValueError):
    """The bytes a printer returned are not a PDF this surface will publish."""


@dataclass(frozen=True, slots=True)
class PrintablePage:
    """One document, ready to print, and how it reads.

    The direction travels beside the HTML rather than being parsed back out of
    it, so an adapter can act on it -- and so a fake can assert on it -- without
    either of them reading the markup.
    """

    language: str
    direction: str
    document: str

    def __post_init__(self) -> None:
        _require_text(self.language, "language")
        _require_text(self.direction, "direction")
        _require_text(self.document, "document")


class PagePrinter(Protocol):
    """The single thing a browser does for this surface.

    One method, deliberately. Everything else a browser can do -- navigate,
    execute script, fetch a subresource -- is something this surface has no use
    for and would rather not have available.
    """

    def print_to_pdf(self, page: PrintablePage) -> bytes: ...


@dataclass(frozen=True, slots=True)
class PdfSurface:
    """The printed files, beside the claim `bundle.reconcile` will judge.

    A `PdfSurface` cannot hold a PDF that is untagged, unclosed, or carrying no
    embedded font: the guards run here, so the invalid object never exists to be
    passed on by a caller that forgot to check.
    """

    content: SurfaceContent
    documents: dict[str, bytes]

    def __post_init__(self) -> None:
        _require_governed_languages(self.documents)
        for language, blob in self.documents.items():
            _require_printable_pdf(blob, language)


class PdfReportRenderer:
    """The PDF surface of `bundle.SurfaceRenderer`."""

    def __init__(
        self,
        *,
        printer: PagePrinter,
        environment: Environment | None = None,
        fonts: tuple[EmbeddedFont, ...] | None = None,
    ) -> None:
        self._printer = printer
        self._environment = build_environment() if environment is None else environment
        if not self._environment.autoescape:
            # Inherited from the web surface for the same reason: a label reading
            # `<script>` is customer text either way, and whether the reader sees
            # it or a browser runs it is decided entirely here.
            raise ValueError("The report environment must autoescape.")
        self._fonts = load_report_fonts() if fonts is None else fonts
        _require_fonts(self._fonts)

    @property
    def surface(self) -> str:
        return SURFACE_PDF

    @property
    def environment(self) -> Environment:
        return self._environment

    @property
    def fonts(self) -> tuple[EmbeddedFont, ...]:
        return self._fonts

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        return self.render_pdf(bundle).content

    def render_materialized(self, bundle: ReportBundle) -> MaterializedSurface:
        surface = self.render_pdf(bundle)
        return MaterializedSurface(
            content=surface.content,
            artifacts=tuple(
                ArtifactPayload.of(
                    kind=f"pdf_{language}",
                    media_type=PDF_MEDIA_TYPE,
                    file_name="khepri-report.pdf",
                    content=surface.documents[language],
                )
                for language in REQUIRED_LANGUAGES
            ),
        )

    def render_pdf(self, bundle: ReportBundle) -> PdfSurface:
        """Print one document per governed language, and claim what they present."""
        template = self._environment.get_template(PDF_TEMPLATE_NAME)
        cells = {language: build_cells(bundle, language) for language in REQUIRED_LANGUAGES}
        documents = {
            language: self._printer.print_to_pdf(
                PrintablePage(
                    language=language,
                    direction=LANGUAGE_DIRECTION[language],
                    document=template.render(self._context(bundle, language, cells[language])),
                )
            )
            for language in REQUIRED_LANGUAGES
        }
        return PdfSurface(
            content=build_content(
                bundle,
                cells,
                surface=SURFACE_PDF,
                output_size_bytes=_printed_bytes(documents),
            ),
            documents=documents,
        )

    def _context(
        self,
        bundle: ReportBundle,
        language: str,
        cells: tuple[FigureCell, ...],
    ) -> dict[str, object]:
        context = build_context(
            bundle,
            language,
            cells,
            extra_provenance={"pdf_surface_version": PDF_SURFACE_VERSION},
        )
        context["print_stylesheet_name"] = PRINT_STYLESHEET_NAME
        context["fonts"] = list(self._fonts)
        return context


def _printed_bytes(documents: dict[str, bytes]) -> int:
    """How large this surface turned out to be: every file it printed, together.

    Both documents, because the surface is both of them. A number covering the
    English file alone would report half a report and look like a measurement.
    """
    return sum(len(blob) for blob in documents.values())


def _require_governed_languages(documents: dict[str, bytes]) -> None:
    if set(documents) != set(REQUIRED_LANGUAGES):
        raise ValueError("A PDF surface publishes exactly the governed languages.")


def _require_printable_pdf(blob: bytes, language: str) -> None:
    """Refuse bytes that are not a tagged, closed, self-contained PDF."""
    _require_pdf_container(blob, language)
    _require_tagged(blob, language)
    _require_embedded_font(blob, language)


def _require_pdf_container(blob: bytes, language: str) -> None:
    if not blob.startswith(PDF_HEADER):
        raise PdfNotPrintable(f"documents[{language}] is not a PDF.")
    if PDF_TRAILER not in blob:
        # A printer that returned early hands back a prefix of a valid file, and
        # a prefix opens as a damaged document rather than as an error.
        raise PdfNotPrintable(f"documents[{language}] is a truncated PDF.")


def _require_tagged(blob: bytes, language: str) -> None:
    missing = [marker for marker in TAGGED_MARKERS if marker not in blob]
    if missing:
        raise PdfNotPrintable(f"documents[{language}] is not a tagged PDF.")


def _require_embedded_font(blob: bytes, language: str) -> None:
    if EMBEDDED_FONT_MARKER not in blob:
        raise PdfNotPrintable(f"documents[{language}] embeds no font program.")


def _require_fonts(fonts: tuple[EmbeddedFont, ...]) -> None:
    if not fonts:
        # A print surface with no embedded face is a print surface that depends
        # on the reader's machine having an Arabic font, which is the thing this
        # slice exists to stop depending on.
        raise ValueError("The PDF surface requires at least one embedded face.")


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required.")
