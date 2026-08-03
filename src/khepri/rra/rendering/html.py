"""The canonical bilingual web surface of one report bundle.

**This module presents figures. It never produces one.** Every number on the
page is a string the bundle already rendered, copied into a cell; `CitedFigure`
carries a `Decimal` beside that string and this renderer never reads it.
RRA-006 excludes independent surface calculations, and the way to exclude them
is to leave the renderer nothing to calculate with — a total it could sum, a
value it could format, a precision it could choose. So the view model built here
holds `text`, and the arithmetic that produced it happened once, in `bundle`.

**Two documents, not one bilingual page.** A document has one root element and
therefore one `dir`, so a single page cannot declare both that Arabic reads
right to left and that English reads left to right. The surface is a pair of
documents keyed by language, each stating its own `lang` and `dir`, and the
stylesheet uses logical properties throughout — `margin-inline-start` rather
than `margin-left` — so one stylesheet lays out both directions without a
mirrored copy that could drift from the original.

**Escaping is a property of the environment, not of a habit.** Autoescaping is
on, and nothing reachable from the bundle is ever marked safe. Labels, caveats
and narrative prose are customer- or provider-derived text; a label reading
`<script>` has to arrive at the reader as the four characters somebody typed.
The stylesheet is included as *template source* rather than passed in as a
variable, which is what keeps `|safe` out of this template entirely: a page with
one `|safe` in it has an escaping convention, not an escaping guarantee.

**What is not here.** No PDF, no workbook, no browser. The template carries two
empty extension blocks so a print stylesheet and embedded font faces can be
layered on by the slice that owns them, and no JavaScript is bundled at all —
navigation is ordinary anchors, which is the smallest amount of script that can
satisfy a navigable report.
"""

from __future__ import annotations

from dataclasses import dataclass

from jinja2 import Environment, PackageLoader, StrictUndefined

from khepri.rra.bundle import (
    LANGUAGE_DIRECTION,
    SURFACE_WEB,
    CitedFigure,
    ReportBundle,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
)
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    REQUIRED_LANGUAGES,
    NarrativeDraft,
)

HTML_SURFACE_VERSION = "rra006.html.v1"

TEMPLATE_PACKAGE = "khepri.rra.rendering"
TEMPLATE_DIRECTORY = "templates"
TEMPLATE_NAME = "report.html.j2"
STYLESHEET_NAME = "report.css"

# The page's own furniture, in both governed languages. Headings and column
# names are the renderer's to write — they say nothing about the data — but they
# are held here rather than in the template so that the two languages are one
# table with one key set, and a heading added to one cannot silently be missing
# from the other.
_CHROME: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "title": "Retail report",
        "skip": "Skip to the report",
        "navigation": "On this page",
        "about": "About this report",
        "figures": "Figures",
        "figures_caption": "Every figure in this report, beside the fact it cites",
        "caveats": "Data caveats",
        "commentary": "Commentary",
        "citations": "Citations",
        "provenance": "Provenance and versions",
        "label": "Label",
        "metric": "Metric",
        "kind": "Kind",
        "unit": "Unit",
        "value": "Value",
        "citation": "Citation",
        "total": "Total",
        "none": "None",
        "cites": "Cites",
    },
    LANGUAGE_ARABIC: {
        "title": "تقرير التجزئة",
        "skip": "الانتقال إلى التقرير",
        "navigation": "في هذه الصفحة",
        "about": "عن هذا التقرير",
        "figures": "الأرقام",
        "figures_caption": "كل رقم في هذا التقرير، بجانب الحقيقة التي يُسند إليها",
        "caveats": "تحذيرات البيانات",
        "commentary": "التعليق",
        "citations": "الإسنادات",
        "provenance": "المصدر والإصدارات",
        "label": "التسمية",
        "metric": "المقياس",
        "kind": "النوع",
        "unit": "الوحدة",
        "value": "القيمة",
        "citation": "الإسناد",
        "total": "الإجمالي",
        "none": "لا يوجد",
        "cites": "يُسند إلى",
    },
}


class SurfaceRenderFailed(RuntimeError):
    """A surface could not be produced from the bundle as supplied."""


@dataclass(frozen=True, slots=True)
class FigureCell:
    """One figure as one document prints it: the supplied text, and nothing else.

    There is no `value` field on purpose. A renderer holding the `Decimal` beside
    the string is a renderer that can format the number itself, and the whole
    guarantee of this surface is that it cannot.
    """

    figure_id: str
    citation_id: str
    metric: str
    kind: str
    unit_kind: str
    section: str
    label: str | None
    text: str

    def __post_init__(self) -> None:
        _require_text(self.figure_id, "figure_id")
        _require_text(self.citation_id, "citation_id")
        _require_text(self.text, "text")


@dataclass(frozen=True, slots=True)
class NarrativePassage:
    """One passage of commentary, and the facts it says it is citing."""

    section_id: str
    text: str
    cited_fact_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_text(self.section_id, "section_id")
        _require_text(self.text, "text")


@dataclass(frozen=True, slots=True)
class HtmlSurface:
    """The rendered pages, beside the claim `bundle.reconcile` will judge.

    Both are returned together because they are derived from one pass over the
    bundle. A renderer that built the claim separately from the page could
    reconcile perfectly while shipping a page that says something else.
    """

    content: SurfaceContent
    documents: dict[str, str]

    def __post_init__(self) -> None:
        if set(self.documents) != set(REQUIRED_LANGUAGES):
            raise ValueError("An HTML surface publishes exactly the governed languages.")
        for language, document in self.documents.items():
            _require_text(document, f"documents[{language}]")


class HtmlReportRenderer:
    """The web surface of `bundle.SurfaceRenderer`."""

    def __init__(self, *, environment: Environment | None = None) -> None:
        self._environment = build_environment() if environment is None else environment
        if not self._environment.autoescape:
            # A label reading `<script>` is customer text either way; whether the
            # reader sees it or runs it is decided entirely here.
            raise ValueError("The report environment must autoescape.")

    @property
    def surface(self) -> str:
        return SURFACE_WEB

    @property
    def environment(self) -> Environment:
        return self._environment

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        return self.render_html(bundle).content

    def render_html(self, bundle: ReportBundle) -> HtmlSurface:
        """Render both documents, and the claim about what they present."""
        template = self._environment.get_template(TEMPLATE_NAME)
        cells = {language: build_cells(bundle, language) for language in REQUIRED_LANGUAGES}
        documents = {
            language: template.render(build_context(bundle, language, cells[language]))
            for language in REQUIRED_LANGUAGES
        }
        return HtmlSurface(
            content=build_content(bundle, cells, output_size_bytes=_document_bytes(documents)),
            documents=documents,
        )


def build_environment() -> Environment:
    """The one environment these templates are rendered in.

    `autoescape` is unconditional rather than selected by file extension: the
    templates here are named for what they are, and an extension test is a
    guarantee that depends on somebody naming the next one correctly.

    `StrictUndefined` fails closed. A context key the template asks for and the
    renderer did not supply is a hole in the page, and a hole that renders as an
    empty string is a figure, caveat, or disclosure quietly missing.
    """
    return Environment(
        loader=PackageLoader(TEMPLATE_PACKAGE, TEMPLATE_DIRECTORY),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def build_content(
    bundle: ReportBundle,
    cells: dict[str, tuple[FigureCell, ...]],
    *,
    surface: str = SURFACE_WEB,
    output_size_bytes: int,
) -> SurfaceContent:
    """The claim `bundle.reconcile` will judge, for whichever surface made it.

    Public, and parameterised by surface name, because the print surface is the
    *same* pass over the bundle rendered through the same template. A second
    implementation of this would be a second chance to disagree about what the
    report says, which is the failure `bundle` exists to prevent.

    The size is supplied rather than measured here, because the payload it
    describes differs per surface — a string for the screen, a printed file for
    the page — and this function sees neither.
    """
    return SurfaceContent(
        surface=surface,
        bundle_id=bundle.bundle_id,
        output_size_bytes=output_size_bytes,
        languages=tuple(
            SurfaceLanguage(
                language=language,
                direction=LANGUAGE_DIRECTION[language],
                # The sections the bundle declares, in its order. Deriving this
                # from the cells just built would make the surface agree with
                # itself by construction, and a refused section has no cell to
                # derive from at all -- so a dropped refusal heading would
                # reconcile. What this claims is what the template must render.
                sections=bundle.section_ids,
                stated=tuple(
                    StatedFigure(
                        figure_id=cell.figure_id,
                        text=cell.text,
                        section=cell.section,
                    )
                    for cell in cells[language]
                ),
                caveats=bundle.caveats,
                disclosure=bundle.disclosure(language),
            )
            for language in REQUIRED_LANGUAGES
        ),
    )


def build_cells(bundle: ReportBundle, language: str) -> tuple[FigureCell, ...]:
    """Every figure of one language as the supplied text, and nothing else."""
    return tuple(_cell(figure, language) for figure in bundle.figures)


def _cell(figure: CitedFigure, language: str) -> FigureCell:
    text = figure.renderings.get(language)
    if text is None:
        # A figure the bundle did not render in this language is a cell this
        # surface would have to write for itself. It refuses instead.
        raise SurfaceRenderFailed("A figure carries no rendering for a governed language.")
    return FigureCell(
        figure_id=figure.figure_id,
        citation_id=figure.citation_id,
        metric=figure.metric,
        kind=figure.kind,
        unit_kind=figure.unit_kind,
        section=figure.section,
        label=figure.label,
        text=text,
    )


def build_context(
    bundle: ReportBundle,
    language: str,
    cells: tuple[FigureCell, ...],
    *,
    extra_provenance: dict[str, str] | None = None,
) -> dict[str, object]:
    """The one context both the screen and the print template are rendered from.

    A surface that needs more than this -- the print surface needs font payloads
    and a print stylesheet name -- adds keys to what this returns rather than
    building its own, so neither surface can quietly disagree with the other
    about a figure, a caveat, or the disclosure.

    `extra_provenance` is how a surface names *itself* in the provenance table a
    reader checks the report against. It is restricted to strings for the same
    reason the table is: everything in it has to be a governed version, a digest,
    or a count, and never anything derived from customer data.
    """
    return {
        "language": language,
        "direction": LANGUAGE_DIRECTION[language],
        "stylesheet": STYLESHEET_NAME,
        "chrome": _CHROME[language],
        "disclosure": bundle.disclosure(language),
        "narrative_state": bundle.narrative_state,
        # Report-level caveats only. A section-scoped caveat qualifies one
        # analysis and belongs inside that section, which is the per-section
        # rendering a later slice adds -- listing it here would state it twice
        # once that lands, and under the wrong heading until then.
        "caveats": [entry for entry in bundle.caveats if entry.section is None],
        "cells": list(cells),
        "citations": sorted({cell.citation_id for cell in cells}),
        "passages": list(_passages(bundle.narrative, language)),
        "provenance": _provenance(bundle, extra_provenance or {}),
    }


def _passages(
    narrative: NarrativeDraft | None,
    language: str,
) -> tuple[NarrativePassage, ...]:
    if narrative is None:
        return ()
    entry = next(
        (item for item in narrative.languages if item.language == language),
        None,
    )
    if entry is None:
        # A narrative missing one language would publish commentary to one
        # reader and silence to the other, which is the parity failure the
        # bundle exists to prevent.
        raise SurfaceRenderFailed("The narrative carries no passage for a governed language.")
    return tuple(
        NarrativePassage(
            section_id=section.section_id,
            text=section.text,
            cited_fact_ids=tuple(section.cited_fact_ids),
        )
        for section in entry.sections
    )


def _provenance(
    bundle: ReportBundle,
    extra: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    """The version strings and digests a reader can check this report against.

    Machine-readable, identical in both languages, and content-free by
    construction: every entry comes from `BundleIdentity`, whose fields are all
    governed versions, digests, or counts.
    """
    document = bundle.identity.as_document()
    entries = {**{name: str(value) for name, value in document.items()}}
    entries["bundle_id"] = bundle.bundle_id
    entries["html_surface_version"] = HTML_SURFACE_VERSION
    entries.update(extra)
    return tuple(sorted(entries.items()))


def _document_bytes(documents: dict[str, str]) -> int:
    """How large the rendered documents are, in the encoding they are served in.

    Measured on the encoded form rather than counted in characters: an Arabic
    page is roughly twice the bytes of its character count, and the number
    RRA-007 records is a number of bytes.
    """
    return sum(len(document.encode("utf-8")) for document in documents.values())


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required.")
