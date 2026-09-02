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
    KIND_VALUE,
    LANGUAGE_DIRECTION,
    ORDERED_SECTIONS,
    SECTION_REASONS,
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
from khepri.rra.rendering.wording import (
    CHART_DESCRIPTIONS,
    COMPONENT_STATE_WORDING,
    LABEL_WORDING,
    SECTION_HEADINGS,
    business_metric_name,
    caveat_prose,
    component_chrome,
    kind_qualifier,
    section_refusal_message,
)
from khepri.rra.report_artifacts import (
    HTML_MEDIA_TYPE,
    ArtifactPayload,
    MaterializedSurface,
)

# v2 restructures the business tables: a repeated series renders as one row per
# label with a column per (metric, kind) pair, where every figure was its own row.
# The version is machine-readable provenance, and a consumer that selected its
# parser from v1 would look for a row per figure and find a grid.
HTML_SURFACE_VERSION = "rra006.html.v2"

TEMPLATE_PACKAGE = "khepri.rra.rendering"
TEMPLATE_DIRECTORY = "templates"
TEMPLATE_NAME = "report.html.j2"
EVIDENCE_TEMPLATE_NAME = "report.evidence.html.j2"
STYLESHEET_NAME = "report.css"

# How much of the bundle identity the business region shows. Eight hex characters
# is short enough to read over a phone and long enough that two reports a customer
# holds at once will not collide. The full identity is in the audit region.
REPORT_REFERENCE_WIDTH = 8

# The page's own furniture, in both governed languages. Headings and column
# names are the renderer's to write — they say nothing about the data — but they
# are held here rather than in the template so that the two languages are one
# table with one key set, and a heading added to one cannot silently be missing
# from the other.
def _section_refusal_prose(language: str) -> dict[str, dict[str, str]]:
    """Refusal prose per section, already filled.

    The template used to index `REFUSAL_WORDING["section"]` by reason and print
    the value, which was fine while every section reason named its own family.
    The version pairing reason is shared by all four and carries a `{section}`
    placeholder, so the raw mapping put a literal brace on the page and in the
    PDF that extends the same template.

    Nested by section then reason rather than filled once, because the same
    reason renders differently per section -- which is the whole point of naming
    the analysis a reader has lost.
    """
    return {
        section: {
            reason: section_refusal_message(section, reason, language)
            for reason in SECTION_REASONS[section]
        }
        for section in ORDERED_SECTIONS
    }


_CHROME: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "title": "Retail report",
        "skip": "Skip to the report",
        "navigation": "On this page",
        "about": "About this report",
        "figures": "Figures",
        "figures_caption": "Every figure in this report, beside the fact it cites",
        "business_caption": "The figures in this section",
        "business_figure": "Figure",
        # The first column of a pivoted series table. Deliberately generic: the
        # labels down that column are periods in one section and branches or
        # products in another, and the alternative -- naming the dimension -- would
        # make this module decide what a customer's own labels mean.
        "series_caption": "The figures in this section by breakdown",
        "series_label": "Breakdown",
        "caveats": "Data caveats",
        "commentary": "Commentary",
        # The colophon is the one place the business report names itself. It carries
        # the short reference and says the evidence exists, because a report that
        # never mentions its own evidence cannot be forwarded to an auditor by a
        # reader who does not know there is any.
        "colophon_reference": "Report reference",
        "colophon_evidence": (
            "Full calculation evidence and data lineage are available on request."
        ),
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
        "evidence_title": "Technical evidence",
        "evidence_intro": (
            "Every figure in this report, the identifiers it is filed under, and "
            "the facts it cites. Forward this page to an auditor."
        ),
        "figure_reference": "Figure",
        "section_states": "Section states",
        "section_column": "Section",
        "state_column": "State",
        "reason_column": "Reason",
        "commentary_citations": "Commentary citations",
        "refusal_prose": _section_refusal_prose(LANGUAGE_ENGLISH),
        # Shared customer wording is read from `wording` rather than copied here.
        # Every duplicate would be a place for surfaces or languages to drift into
        # naming the same section, chart, label, or refusal differently.
        "sections": SECTION_HEADINGS[LANGUAGE_ENGLISH],
        "chart_descriptions": CHART_DESCRIPTIONS[LANGUAGE_ENGLISH],
        "labels": LABEL_WORDING[LANGUAGE_ENGLISH],
        # The data-display component layer's own chrome (`RRA-012` FR-095a), and the
        # word its status badge shows per governed section state. Registered here
        # because this table is the only path from `wording` to a template.
        "component": component_chrome(LANGUAGE_ENGLISH),
        "component_state": COMPONENT_STATE_WORDING[LANGUAGE_ENGLISH],
    },
    LANGUAGE_ARABIC: {
        "title": "تقرير التجزئة",
        "skip": "الانتقال إلى التقرير",
        "navigation": "في هذه الصفحة",
        "about": "عن هذا التقرير",
        "figures": "الأرقام",
        "figures_caption": "كل رقم في هذا التقرير، بجانب الحقيقة التي يُسند إليها",
        "business_caption": "أرقام هذا القسم",
        "business_figure": "البيان",
        "series_caption": "أرقام هذا القسم حسب التصنيف",
        "series_label": "التصنيف",
        "caveats": "تحذيرات البيانات",
        "commentary": "التعليق",
        "colophon_reference": "مرجع التقرير",
        "colophon_evidence": "تتوفر أدلة الحساب الكاملة وسلسلة مصدر البيانات عند الطلب.",
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
        "evidence_title": "الأدلة التقنية",
        "evidence_intro": (
            "كل رقم في هذا التقرير، والمعرّفات المسجّل بها، والحقائق التي يُسند "
            "إليها. أرسِل هذه الصفحة إلى المراجع."
        ),
        "figure_reference": "المعرّف",
        "section_states": "حالات الأقسام",
        "section_column": "القسم",
        "state_column": "الحالة",
        "reason_column": "السبب",
        "commentary_citations": "إسنادات التعليق",
        "refusal_prose": _section_refusal_prose(LANGUAGE_ARABIC),
        "sections": SECTION_HEADINGS[LANGUAGE_ARABIC],
        "chart_descriptions": CHART_DESCRIPTIONS[LANGUAGE_ARABIC],
        "labels": LABEL_WORDING[LANGUAGE_ARABIC],
        # The data-display component layer's own chrome (`RRA-012` FR-095a), and the
        # word its status badge shows per governed section state. Registered here
        # because this table is the only path from `wording` to a template.
        "component": component_chrome(LANGUAGE_ARABIC),
        "component_state": COMPONENT_STATE_WORDING[LANGUAGE_ARABIC],
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
    metric_name: str | None
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
    """The rendered regions, beside the claim `bundle.reconcile` will judge.

    Both are returned together because they are derived from one pass over the
    bundle. A renderer that built the claim separately from the page could
    reconcile perfectly while shipping a page that says something else.

    `evidence` is a sibling of `documents` rather than more keys inside it.
    RRA-009 requires the audit region be carried as a distinct web page, and
    `documents` publishes exactly the governed languages. Both regions are
    generated for every report; delivery decides which copy a customer receives.
    """

    content: SurfaceContent
    documents: dict[str, str]
    evidence: dict[str, str]

    def __post_init__(self) -> None:
        _require_governed_documents(self.documents, "documents")
        _require_governed_documents(self.evidence, "evidence")


def _require_governed_documents(documents: dict[str, str], name: str) -> None:
    if set(documents) != set(REQUIRED_LANGUAGES):
        message = f"An HTML surface publishes exactly the governed languages in {name}."
        raise ValueError(message)
    for language, document in documents.items():
        _require_text(document, f"{name}[{language}]")


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

    def render_materialized(self, bundle: ReportBundle) -> MaterializedSurface:
        surface = self.render_html(bundle)
        artifacts = tuple(
            ArtifactPayload.of(
                kind=f"web_business_{language}",
                media_type=HTML_MEDIA_TYPE,
                file_name="khepri-report.html",
                content=surface.documents[language].encode("utf-8"),
            )
            for language in REQUIRED_LANGUAGES
        ) + tuple(
            ArtifactPayload.of(
                kind=f"web_evidence_{language}",
                media_type=HTML_MEDIA_TYPE,
                file_name="khepri-evidence.html",
                content=surface.evidence[language].encode("utf-8"),
            )
            for language in REQUIRED_LANGUAGES
        )
        return MaterializedSurface(content=surface.content, artifacts=artifacts)

    def render_html(self, bundle: ReportBundle) -> HtmlSurface:
        """Render both regions, and the claim about what they present."""
        template = self._environment.get_template(TEMPLATE_NAME)
        evidence_template = self._environment.get_template(EVIDENCE_TEMPLATE_NAME)
        cells = {language: build_cells(bundle, language) for language in REQUIRED_LANGUAGES}
        contexts = {
            language: build_context(bundle, language, cells[language])
            for language in REQUIRED_LANGUAGES
        }
        documents = {
            language: template.render(contexts[language])
            for language in REQUIRED_LANGUAGES
        }
        evidence = {
            language: evidence_template.render(contexts[language])
            for language in REQUIRED_LANGUAGES
        }
        return HtmlSurface(
            content=build_content(
                bundle,
                cells,
                output_size_bytes=_document_bytes(documents) + _document_bytes(evidence),
            ),
            documents=documents,
            evidence=evidence,
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
        metric_name=_business_name(figure, language),
        kind=figure.kind,
        unit_kind=figure.unit_kind,
        section=figure.section,
        label=_row_label(figure.label, language),
        text=text,
    )


def _business_name(figure: CitedFigure, language: str) -> str | None:
    """A figure's customer-facing name, qualified by its kind where that matters.

    A bucket emits two figures with the same metric and the same label -- the
    value, and the count of rows it was computed from. `kind` is what separates
    them and `kind` is Audit-tier, so without a qualifier here a reader sees one
    name twice with two unrelated numbers beside it and nothing saying which is
    which.

    Only `KIND_ROWS` qualifies. A plain value needs no suffix: the value is the
    figure, and "Revenue (amount)" on every row is noise that makes the report
    harder to read rather than clearer.

    Returns `None` only for a plain value with no governed name, which is the
    signal that the row is named by its own label alone.

    **The qualifier applies whether or not a governed name exists**, and that is
    the whole point rather than a detail. The colliding rows in practice are
    `revenue_by_period` and `units_by_period`, which have *no* metric name and are
    named by their period label -- so returning early on a missing name left four
    rows all reading `2026-01-09`, which is the defect this function was added to
    fix.
    """
    name = business_metric_name(figure.metric, language)
    qualifier = kind_qualifier(figure.kind, language)
    if qualifier is None:
        return name
    if name is None:
        # A row the label names, counting rows rather than stating the value. The
        # label still appears beside this in the rendered heading, so "rows
        # counted — 2026-01-09" reads correctly and is distinct from the value row.
        return qualifier
    return f"{name} ({qualifier})"


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


def _audit_region(
    bundle: ReportBundle,
    language: str,
    cells: tuple[FigureCell, ...],
    provenance: tuple[tuple[str, str], ...],
) -> dict[str, object]:
    """Group every existing audit value without computing or filtering it.

    `section.state` is not carried. It is tier I -- Internal -- and RRA-009 renders
    an Internal field on no customer surface including the audit region, so handing
    it to the evidence template would be handing a consumer a field it must
    remember not to render. A refused section is identifiable here by carrying a
    reason, which is the Audit-tier evidence an auditor actually joins on.
    """
    return {
        "figures": list(cells),
        "sections": [
            {
                "section_id": section.section_id,
                "reason": section.reason,
            }
            for section in bundle.sections
        ],
        "caveats": [
            {"code": caveat.code, "section": caveat.section}
            for caveat in bundle.caveats
        ],
        "citations": sorted({cell.citation_id for cell in cells}),
        "passages": list(_passages(bundle.narrative, language)),
        "provenance": provenance,
    }


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
    provenance = _provenance(bundle, extra_provenance or {})
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
        "caveat_prose": {
            caveat.code: caveat_prose(caveat.code, language)
            for caveat in bundle.caveats
        },
        "sections": _section_views(bundle, language, cells),
        "refused_state": SECTION_REFUSED,
        "cells": list(cells),
        "citations": sorted({cell.citation_id for cell in cells}),
        "passages": list(_passages(bundle.narrative, language)),
        "provenance": provenance,
        # The one identifier the business region carries. Derived from the bundle
        # identity rather than invented, so a reader quoting it can be matched to
        # the report -- and short enough to read aloud, which a digest is not. The
        # full identity stays in the audit region, where an auditor needs it.
        "report_reference": _report_reference(bundle),
        "audit": _audit_region(bundle, language, cells, provenance),
    }


def _report_reference(bundle: ReportBundle) -> str:
    """The short human reference a customer quotes when asking about a report.

    A prefix of the bundle identity rather than a new identifier: a second
    identifier would be a second thing to reconcile, and this one is already
    content-addressed. Upper-cased because it is read aloud and transcribed.
    """
    return bundle.bundle_id[:REPORT_REFERENCE_WIDTH].upper()


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
    # `narrative_state` is deliberately absent, and an earlier revision of this
    # function was wrong to add it. It is tier I -- Internal -- and RRA-009 renders
    # an Internal field "on no customer surface, including the audit region", so
    # there is nowhere on either document it may go. Internal is not a quieter
    # Audit: an Audit field is relocated, an Internal one is not rendered.
    #
    # `excel.py:701` writes it to the workbook's provenance sheet. That is a
    # pre-existing divergence from this classification rather than a precedent to
    # copy, and it belongs to the Excel slice.
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
class _SeriesRow:
    """One label's figures, in the column order its group declares."""

    label: str
    texts: tuple[str | None, ...]


@dataclass(frozen=True, slots=True)
class _SeriesTable:
    """A repeated series as a table: one column per metric, one row per label.

    The shape a series wants. Rendered as one row per cell, a five-period series
    carrying revenue and units produced ten rows, each repeating a metric name and
    stating one number, with the two halves of the comparison a reader wanted in
    different parts of the table.

    `headings` is metric names and `rows` is one entry per label, so a `None` in
    `texts` is a metric that carried no figure for that label rather than a zero.
    Nothing here is computed: every string is a cell `build_cells` already made.
    """

    headings: tuple[str, ...]
    rows: tuple[_SeriesRow, ...]


@dataclass(frozen=True, slots=True)
class _SectionView:
    """One governed section as the template needs it: heading, chart, cells, caveats.

    Assembled here rather than in the template because a template choosing which
    cells belong to a section could disagree with `bundle.section_ids`, which is
    what every surface is reconciled against.

    `cells` holds the scalars -- the figures with no label -- and `series` the
    pivoted groups. The split is made here for the same reason the section
    membership is: a template deciding which figures form a series could group
    two that the bundle never related.
    """

    section_id: str
    state: str
    reason: str | None
    cells: tuple[FigureCell, ...]
    series: tuple[_SeriesTable, ...]
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
            # Every figure this section states, provenance included: a bucket's
            # row count is a Business-tier value per the visibility matrix, and
            # `_series_tables` gives it a column beside the value it explains
            # rather than a row interleaved with it.
            cells=_scalar_cells(_stated(cells, section.section_id)),
            series=_series_tables(_stated(cells, section.section_id)),
            caveats=_stated_once(bundle, section.section_id, language),
            chart=_chart_of(section, figures, language),
        )
        for section in bundle.sections
    ]


def _stated(cells: tuple[FigureCell, ...], section_id: str) -> tuple[FigureCell, ...]:
    """One section's cells, in the bundle's order.

    **`KIND_ROWS` is not filtered out here, and an earlier revision of this slice
    was wrong to do it.** The interleaving it was fixing is real -- a five-period
    series became ten rows, and a real upload put 39 `rows counted` rows among the
    findings -- but dropping the figures is the wrong instrument, for two reasons
    found in review.

    `docs/reporting/presentation-visibility-matrix.md` classifies a figure's
    `text` **B** ("the number") and only its `kind` column **A**. Removing the
    whole row moves a Business-tier value into the audit region, which is a
    governed tier change rather than a layout choice. And the earlier reasoning
    read `wording` backwards: `KIND_QUALIFIERS` exists *because* `kind` is
    Audit-tier and cannot appear, so a row count needs customer wording to be
    legible on the business page -- "the raw code stays in the audit region; this
    is its customer wording". It is the machinery that makes these figures
    presentable here, not evidence that they belong elsewhere.

    `rendering/excel.py::_write_business_sheet` never filtered them either, so the
    filter also left the surfaces disagreeing about what the business region
    contains.

    The interleaving is fixed where it actually belongs: `_series_tables` gives a
    bucket's count its own column beside the value it explains.
    """
    return tuple(cell for cell in cells if cell.section == section_id)


def _scalar_cells(cells: tuple[FigureCell, ...]) -> tuple[FigureCell, ...]:
    """The figures that are not part of a series, in the bundle's order.

    A figure with no label is a total and states itself. A labelled figure whose
    metric is the only one at that label is *also* left here: giving it a pivoted
    table would add a column heading stating what its single column already said,
    and `concentration_curve` -- four ranks, one metric, no governed name -- is
    exactly that case.
    """
    grouped = _series_columns(cells)
    return tuple(
        cell for cell in cells if cell.label is None or _column(cell) not in grouped
    )


#: How a breakdown metric names its dimension: `revenue_by_period` breaks down by
#: period, `units_by_store` by store.
_BY = "_by_"


def _dimension(cell: FigureCell) -> str:
    """The series a cell belongs to, which is its breakdown rather than its label.

    **A display label is not a series identity, and treating it as one merged two
    breakdowns.** Rows were keyed by label alone, so a product literally named
    `2026-01` shared a key with the January period. Grouping then bridged the
    by-period and by-product series into one table with `Revenue` and `Units sold`
    appearing twice, and a product row sitting under period columns.

    `CitedFigure` carries no dimension, and adding one is a governed change --
    `as_document` feeds the bundle digest -- so the dimension is read from the
    metric identifier, which already states it: everything after `_by_`. A metric
    that names no breakdown falls back to its section, which keeps the comparison
    deltas (`revenue_delta_absolute` and `revenue_delta_percent`, one row per
    mode) in one series as they were.

    The identifier is used to *group*, never to display: `RRA-009` classifies it
    Audit-tier and `_series_columns` still refuses a column whose heading would
    have to be one. `test_every_series_metric_declares_its_dimension` pins the
    convention so a metric that stops following it fails here rather than
    grouping oddly on a customer surface.
    """
    _, separator, dimension = cell.metric.partition(_BY)
    return dimension if separator else cell.section


def _column(cell: FigureCell) -> tuple[str, str]:
    """A cell's column identity: its metric *and* its kind.

    Keyed on both because a bucket emits two figures carrying the same metric and
    the same label -- the value, and the count of rows behind it. Keyed on metric
    alone they collide, and one silently overwrites the other in the grid.
    """
    return (cell.metric, cell.kind)


def _series_columns(cells: tuple[FigureCell, ...]) -> frozenset[tuple[str, str]]:
    """The columns that share a label with another column, and so form a table.

    Sharing is the test rather than "has a label", because a column heading only
    means something when there is more than one column to tell apart. A bucket's
    value and its row count are two columns by that test, which is what turns the
    interleaving into a grid: `concentration_curve`'s four ranks were eight rows
    alternating a share and a count, and become four rows with a column each.

    **A metric whose value has no governed name is excluded entirely, and that is
    a disclosure rule rather than a cosmetic one.** A column needs a heading, and
    the only string available for one that has no `metric_name` is the metric
    identifier -- `revenue_by_category`. `RRA-009` classifies the metric
    identifier Audit-tier and renders it on the evidence surface, so putting it in
    a customer-facing `<th>` would move an Audit field onto the business page to
    satisfy a layout. Those series keep the row-per-cell form, where the label
    alone names the row and no identifier is needed.

    The test is on the **value** cell's name, not on each cell's own: a row count
    always has customer wording (`kind_qualifier` supplies "rows counted" even
    with no metric name), so testing each cell would admit an unnamed metric's
    count column while its value column stayed row-form -- the count separated
    from the number it explains. `revenue_by_period` is unaffected: it carries
    `Revenue`, so both its columns are admitted.
    """
    by_label: dict[str, set[tuple[str, str]]] = {}
    named = {cell.metric for cell in cells if cell.kind == KIND_VALUE and cell.metric_name}
    for cell in cells:
        if cell.label is not None and cell.metric in named:
            by_label.setdefault(cell.label, set()).add(_column(cell))
    return frozenset(
        column
        for columns in by_label.values()
        if len(columns) > 1
        for column in columns
    )


def _series_tables(cells: tuple[FigureCell, ...]) -> tuple[_SeriesTable, ...]:
    """The section's repeated series, one table per set of co-occurring metrics.

    Grouped by the *set* of metrics sharing a label rather than by section, so a
    section carrying both a by-period series and a by-branch series renders two
    tables instead of one table with empty halves. Column order follows the order
    the metrics first appear, which is the bundle's; row order follows the order
    the labels first appear, for the same reason.

    A metric with no figure at a given label contributes `None`, which the
    template renders as an empty cell -- not a zero, which would be a number this
    module invented.
    """
    grouped = _series_columns(cells)
    if not grouped:
        return ()
    names, values = _series_index(cells, grouped)
    return tuple(
        _SeriesTable(
            headings=tuple(names[column] for column in family),
            rows=tuple(
                _SeriesRow(
                    label=row[1],
                    texts=tuple(values[row].get(column) for column in family),
                )
                for row in rows
            ),
        )
        for family, rows in _series_families(names, values).items()
    )


def _series_index(
    cells: tuple[FigureCell, ...],
    grouped: frozenset[tuple[str, str]],
) -> tuple[dict[tuple[str, str], str], dict[str, dict[tuple[str, str], str]]]:
    """The column names and the label/column grid, both in first-appearance order.

    `_series_columns` admits only columns whose metric has a governed name, so
    `metric_name` is the name here rather than a fallback: an identifier reaching a
    column heading would put an Audit-tier field on the business page. A row
    count's name already carries its qualifier -- `_business_name` composes
    "Revenue (rows counted)" -- so the count column says what it counts.
    """
    names: dict[tuple[str, str], str] = {}
    values: dict[tuple[str, str], dict[tuple[str, str], str]] = {}
    for cell in cells:
        column = _column(cell)
        if cell.label is None or column not in grouped:
            continue
        names.setdefault(column, cell.metric_name or "")
        values.setdefault((_dimension(cell), cell.label), {})[column] = cell.text
    return names, values


def _series_families(
    names: dict[tuple[str, str], str],
    values: dict[tuple[str, str], dict[tuple[str, str], str]],
) -> dict[tuple[tuple[str, str], ...], list[tuple[str, str]]]:
    """Labels grouped into series, each carrying the union of its columns.

    A section carrying both a by-period and a by-branch series renders two tables
    instead of one with empty halves, and that separation is what this does. What
    it must *not* do is separate on missingness.

    **Grouping by the exact set of columns present did both, and the second was a
    defect.** A label whose bucket lacks one figure -- a period where every
    revenue input is null -- has a different exact set from its neighbours, so it
    formed a family of its own and rendered as a one-row table beside the series
    it belongs to. Worse, the split made `_SeriesTable`'s empty cell unreachable:
    every label in a family had every column by construction, so the `None` that
    `_series_tables` looks up and the template renders as a blank could not occur.
    The docstring promised a behaviour the grouping had ruled out.

    So labels are joined when they **share any column**, and the family carries
    the union. `revenue_by_period` never appears at a branch label, so the
    by-period and by-branch series still separate; a sparse period still shares
    `units_by_period` with its neighbours and stays with them, its missing figure
    now an empty cell rather than a table.

    Column order follows `names`, which is the bundle's order, so a bucket's count
    sits beside the value it explains.
    """
    return {
        tuple(column for column in names if column in columns): rows
        for columns, rows in _merged_series(values)
    }


#: One series being accumulated: the columns it spans, and the (dimension, label)
#: rows in it.
_Series = tuple[set[tuple[str, str]], list[tuple[str, str]]]


def _merged_series(
    values: dict[tuple[str, str], dict[tuple[str, str], str]],
) -> list[_Series]:
    """Rows folded into series, each carrying the union of its columns."""
    series: list[_Series] = []
    for row, present in values.items():
        series = _absorb(series, set(present), row)
    return series


def _absorb(
    series: list[_Series],
    columns: set[tuple[str, str]],
    row: tuple[str, str],
) -> list[_Series]:
    """One row joined to every series it shares a column with, or standing alone.

    Joining rather than matching is what tolerates a sparse row: it need only
    share *one* column with its neighbours to stay among them, where an exact
    match would have set it apart. A row is `(dimension, label)`, so two
    breakdowns that happen to share a display label no longer bridge here --
    their columns never meet at one row.
    """
    joined = [entry for entry in series if entry[0] & columns]
    apart = [entry for entry in series if not entry[0] & columns]
    rows = [existing for entry in joined for existing in entry[1]]
    rows.append(row)
    return [*apart, (columns.union(*(entry[0] for entry in joined)), rows)]


def _stated_once(bundle: ReportBundle, section_id: str, language: str) -> tuple[str, ...]:
    """One section's caveat codes, with codes that read identically collapsed.

    **Deduplicated by prose rather than by code, because the codes differ and the
    sentences do not.** A single-period upload emits
    `revenue_delta_absolute.year_over_year:prior_window_absent` and
    `revenue_delta_percent.year_over_year:prior_window_absent` -- two governed
    codes, one per affected metric, which is correct: the caveat is a property of
    a figure and both figures have it. `caveat_prose` then maps both to the same
    paragraph, so the comparison section stated "comparison with an earlier
    period is not available" twice in consecutive list items.
    See `test_no_section_caveat_paragraph_is_repeated`.

    The first code wins and the bundle's order is preserved, so the surviving
    entry is the one a reader would have seen first. No code is dropped from the
    bundle: `_reconcile_language` compares the caveat *codes* both languages
    carry and would refuse a surface that had actually lost one -- this narrows
    what is *printed*, which is the same distinction `RRA-006` draws between a
    figure and its presentation.

    Collapsing is per language deliberately. Two codes sharing English prose need
    not share Arabic prose, and deduplicating on one language's text would drop a
    sentence the other language still distinguishes.
    """
    stated: dict[str, str] = {}
    for caveat in bundle.caveats:
        if caveat.section != section_id:
            continue
        stated.setdefault(caveat_prose(caveat.code, language), caveat.code)
    return tuple(stated.values())


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
