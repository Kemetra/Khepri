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
    GOVERNED_FIGURE_LABELS,
    LANGUAGE_DIRECTION,
    SECTION_REFUSED,
    SURFACE_WEB,
    CitedFigure,
    ReportBundle,
    Section,
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
from khepri.rra.rendering.charts import ChartView, build_chart

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
        "chart_not_drawn": "No chart",
        "sections": {
            "overview": "Overview",
            "comparison": "Period comparison",
            "concentration": "Concentration",
            "growth": "Growth decomposition",
            "basket": "Basket structure",
        },
        "chart_descriptions": {
            "chart_description.bar": "Bar chart of the figures in this section",
            "chart_description.grouped_bar": (
                "Grouped bar chart of the figures in this section"
            ),
            "chart_description.line": "Cumulative share curve over the ranked values",
        },
        # One table for every governed code a chart label can carry: metric names,
        # and mode names. One lookup path in the macro, so a new kind of code cannot
        # arrive with nowhere to be translated.
        "labels": {
            "metric.growth_revenue_change": "Revenue change",
            "metric.growth_price_effect": "Price effect",
            "metric.growth_volume_effect": "Volume effect",
            "label.period_over_period": "Against the previous period",
            "label.year_over_year": "Against the same period last year",
        },
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
        "chart_not_drawn": "لا يوجد رسم",
        "sections": {
            "overview": "نظرة عامة",
            "comparison": "مقارنة الفترات",
            "concentration": "التركّز",
            "growth": "تحليل النمو",
            "basket": "بنية السلة",
        },
        "chart_descriptions": {
            "chart_description.bar": "رسم بالأعمدة للأرقام في هذا القسم",
            "chart_description.grouped_bar": "رسم بأعمدة مجمّعة للأرقام في هذا القسم",
            "chart_description.line": "منحنى النصيب التراكمي عبر القيم المرتّبة",
        },
        "labels": {
            "metric.growth_revenue_change": "التغيّر في الإيرادات",
            "metric.growth_price_effect": "أثر السعر",
            "metric.growth_volume_effect": "أثر الحجم",
            "label.period_over_period": "مقابل الفترة السابقة",
            "label.year_over_year": "مقابل الفترة نفسها من العام الماضي",
        },
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
        label=_row_label(figure.label, language),
        text=text,
    )


def _row_label(label: str | None, language: str) -> str | None:
    """A row's own name, translated when it is a governed code rather than a value.

    A bucket label is a product or branch name and is reproduced exactly. A comparison
    mode is an internal identifier, and `period_over_period` in a table cell is the
    same failure as `period_over_period` on an axis -- the chart path was fixed first
    and this is the same code reaching the reader one column over.

    Nothing reconciled changes: `reconcile` compares a figure's *text*, never its
    label.
    """
    if label is None or label not in GOVERNED_FIGURE_LABELS:
        return label
    return _CHROME[language]["labels"][f"label.{label}"]


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
        # Report-level caveats only. A section-scoped one qualifies one analysis and
        # is rendered inside that section: listing it here would tell a reader the
        # whole dataset is qualified, and dropping it would leave `build_content`
        # claiming a caveat the page never showed.
        "caveats": [caveat for caveat in bundle.caveats if caveat.section is None],
        "sections": _section_views(bundle, language, cells),
        "refused_state": SECTION_REFUSED,
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


@dataclass(frozen=True, slots=True)
class _SectionView:
    """One governed section as the template needs it: heading, chart, cells, caveats.

    Assembled here rather than in the template because a template choosing which
    cells belong to a section could disagree with `bundle.section_ids`, which is
    what every surface is reconciled against.
    """

    section_id: str
    state: str
    reason: str | None
    cells: tuple[FigureCell, ...]
    caveats: tuple[str, ...]
    chart: ChartView | None


def _section_views(
    bundle: ReportBundle,
    language: str,
    cells: tuple[FigureCell, ...],
) -> list[_SectionView]:
    """Every section the bundle declares, in its order, with what it renders.

    The geometry is computed per language because the category axis mirrors for a
    right-to-left page. Whether a chart is drawable at all is not a per-language
    question and was already decided by the bundle, which is why a section without
    a `ChartSpec` gets no chart here and carries `chart_not_drawn` instead.
    """
    figures = {figure.figure_id: figure for figure in bundle.figures}
    return [
        _SectionView(
            section_id=section.section_id,
            state=section.state,
            reason=section.reason,
            cells=tuple(
                cell for cell in cells if cell.section == section.section_id
            ),
            caveats=tuple(
                caveat.code
                for caveat in bundle.caveats
                if caveat.section == section.section_id
            ),
            chart=_chart_of(section, figures, language),
        )
        for section in bundle.sections
    ]


def _chart_of(
    section: Section,
    figures: dict[str, CitedFigure],
    language: str,
) -> ChartView | None:
    """The geometry for one section's chart, if the bundle declared one."""
    if section.chart is None:
        return None
    return build_chart(
        section.chart,
        tuple(figures[figure_id] for figure_id in section.figure_ids),
        direction=LANGUAGE_DIRECTION[language],
    )


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required.")
