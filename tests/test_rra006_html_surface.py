from __future__ import annotations

import hashlib
from decimal import Decimal
from importlib import resources

import pytest
from jinja2 import Environment

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    KIND_ROWS,
    LANGUAGE_DIRECTION,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    SURFACE_WEB,
    CitedFigure,
    ReportBundle,
    Section,
    reconcile,
)
from khepri.rra.facts import FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    REQUIRED_LANGUAGES,
    LanguageNarrative,
    NarrativeDraft,
    NarrativeRequest,
    NarrativeSection,
)
from khepri.rra.profiling import build_profile
from khepri.rra.rendering import (
    HtmlReportRenderer,
    SurfaceRenderFailed,
    build_environment,
)
from khepri.rra.rendering import html as html_module
from khepri.rra.rendering.html import STYLESHEET_NAME, TEMPLATE_NAME
from khepri.rra.rendering.wording import caveat_prose

ADAPTER_VERSION = "test.adapter.v1"

GOLDEN = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)


def package(content: bytes = GOLDEN) -> FactPackage:
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
    )


def narrative_for(text: str = "Revenue was 500.00.") -> NarrativeDraft:
    request = NarrativeRequest.of(package(), adapter_version=ADAPTER_VERSION)
    fact_id = next(
        str(entry["fact_id"])
        for entry in request.document["facts"]
        if entry["metric"] == "revenue"
    )
    return NarrativeDraft(
        adapter_version=ADAPTER_VERSION,
        request_digest=request.digest,
        languages=(
            LanguageNarrative(
                language=LANGUAGE_ARABIC,
                sections=(
                    NarrativeSection(
                        section_id="summary",
                        text="بلغت الإيرادات ٥٠٠٫٠٠.",
                        cited_fact_ids=(fact_id,),
                        caveats=(),
                    ),
                ),
            ),
            LanguageNarrative(
                language=LANGUAGE_ENGLISH,
                sections=(
                    NarrativeSection(
                        section_id="summary",
                        text=text,
                        cited_fact_ids=(fact_id,),
                        caveats=(),
                    ),
                ),
            ),
        ),
    )


def stylesheet() -> str:
    return (
        resources.files("khepri.rra.rendering")
        .joinpath("templates", STYLESHEET_NAME)
        .read_text(encoding="utf-8")
    )


def figure(
    *,
    figure_id: str = "cit_test/value",
    label: str | None = None,
    renderings: dict[str, str] | None = None,
    value: str = "500.00",
) -> CitedFigure:
    """One hand-built figure, so a test can say exactly what the bundle supplied."""
    return CitedFigure(
        figure_id=figure_id,
        citation_id="cit_test",
        fact_id="fct_test",
        metric="revenue",
        unit_kind="monetary",
        kind="value",
        section=SECTION_OVERVIEW,
        label=label,
        value=Decimal(value),
        renderings=renderings
        or {LANGUAGE_ENGLISH: "500.00", LANGUAGE_ARABIC: "٥٠٠٫٠٠"},
    )


def bundle_with(*figures: CitedFigure, caveats: tuple[str, ...] = ()) -> ReportBundle:
    base = ReportBundle.of(package())
    return ReportBundle(
        identity=base.identity,
        figures=figures,
        caveats=caveats,
        narrative_state=base.narrative_state,
        # The bundle has to index the figures it carries. A bundle declaring no
        # section while holding one is a bundle disagreeing with itself, and
        # every surface would copy both halves of that into its claim.
        sections=(
            Section(
                section_id=SECTION_OVERVIEW,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=tuple(figure.figure_id for figure in figures),
                chart=None,
            ),
        )
        if figures
        else (),
        narrative=None,
    )


# --- the surface the bundle will accept ------------------------------------


def test_the_web_surface_reconciles_against_the_bundle_it_was_built_from() -> None:
    # `bundle.reconcile` is the gate every surface has to pass, and it is the
    # only judge of whether this renderer presented what it was handed.
    bundle = ReportBundle.of(package(), narrative=narrative_for())
    renderer = HtmlReportRenderer()

    reconcile(renderer.render(bundle), bundle=bundle)

    assert renderer.surface == SURFACE_WEB


def test_each_language_is_its_own_document_declaring_how_it_reads() -> None:
    # One document has one root element, so one page cannot be both `rtl` and
    # `ltr`. Two documents, each stating the direction its language reads in.
    surface = HtmlReportRenderer().render_html(ReportBundle.of(package()))

    assert set(surface.documents) == set(REQUIRED_LANGUAGES)
    for language, direction in LANGUAGE_DIRECTION.items():
        document = surface.documents[language]
        assert f'lang="{language}"' in document
        assert f'dir="{direction}"' in document


def test_every_scrolling_table_is_reachable_and_no_landmark_is_ambiguous() -> None:
    # Two requirements, because they pull against each other. Every scroller is
    # focusable, or the columns past the fold need a pointer to reach. And every
    # scroller that is a *named* `region` carries its own name: a landmark list of
    # identical labels asks the reader to guess, which is worse than no landmark.
    #
    # A section carries one business table, so that one is named. It may carry
    # several breakdowns whose headings and first label can both collide -- see
    # `TestADisplayLabelIsNotASeriesIdentity._colliding` -- so those are focusable
    # and unnamed rather than several landmarks reading alike.
    #
    # Names are compared as resolved *text*, not as the `aria-labelledby` value: two
    # attributes naming two distinct ids whose captions read the same still name both
    # regions identically, and that is the defect this case exists to catch.
    import re

    surface = HtmlReportRenderer().render_html(ReportBundle.of(package()))

    for language in REQUIRED_LANGUAGES:
        document = surface.documents[language]
        scrollers = re.findall(r'<div class="scroller"([^>]*)>', document)
        assert scrollers, f"{language}: no scrolling table was rendered"
        for attributes in scrollers:
            assert 'tabindex="0"' in attributes, (
                f"{language}: a scrolling table is not keyboard reachable: {attributes!r}"
            )

        # Anchored on the `h2`/`caption` tag itself: starting from any `id="..."`
        # matches the enclosing `<section id=...>` and runs through the `</h2>` inside
        # it, so the heading's own id is never collected and every reference to it
        # looks absent.
        text_of = {
            element_id: re.sub(r"<[^>]+>", "", body).strip()
            for element_id, body in re.findall(
                r'<(?:h2|caption)[^>]*id="([^"]+)"[^>]*>(.*?)</(?:h2|caption)>',
                document,
                re.S,
            )
        }
        names = []
        for attributes in scrollers:
            reference = re.search(r'aria-labelledby="([^"]+)"', attributes)
            if reference is None:
                continue
            for token in reference.group(1).split():
                # An `aria-labelledby` naming an absent id resolves to no name at all,
                # which reads as a populated attribute and a nameless landmark.
                assert token in text_of, (
                    f"{language}: aria-labelledby names absent id {token!r}"
                )
            names.append(" ".join(text_of[t] for t in reference.group(1).split()))

        assert names, f"{language}: no scrolling table was named"
        assert len(names) == len(set(names)), (
            f"{language}: two landmarks resolve to one accessible name: {names}"
        )


def test_the_web_surface_reports_the_size_of_the_documents_it_rendered() -> None:
    # RRA-007 records output size per stage, and the size is only knowable here,
    # where the payload is. Checked against the documents themselves: a surface
    # reporting a number it did not measure is caught by this and nothing else.
    # RRA-009 makes the business and evidence regions one generated web surface,
    # so the measurement covers both document maps.
    surface = HtmlReportRenderer().render_html(ReportBundle.of(package()))

    rendered = sum(
        len(document.encode("utf-8"))
        for region in (surface.documents, surface.evidence)
        for document in region.values()
    )
    assert surface.content.output_size_bytes == rendered
    assert rendered > 0


# --- the renderer computes nothing ----------------------------------------


def test_the_page_prints_the_supplied_rendering_and_never_the_value_beside_it() -> None:
    # `CitedFigure` carries a `Decimal` next to the string the bundle rendered.
    # Here the two deliberately disagree, so the page can only show the figure
    # the bundle wrote — formatting the `Decimal` would show the other number.
    # RRA-006 makes the fact package the sole source of every figure, and this
    # is what "sole" has to mean for a renderer.
    bundle = bundle_with(
        figure(renderings={LANGUAGE_ENGLISH: "999.99", LANGUAGE_ARABIC: "٩٩٩٫٩٩"})
    )

    surface = HtmlReportRenderer().render_html(bundle)

    assert "999.99" in surface.documents[LANGUAGE_ENGLISH]
    assert "500.00" not in surface.documents[LANGUAGE_ENGLISH]
    assert "٩٩٩٫٩٩" in surface.documents[LANGUAGE_ARABIC]
    assert "٥٠٠٫٠٠" not in surface.documents[LANGUAGE_ARABIC]


def test_a_figure_with_no_rendering_for_a_language_is_refused() -> None:
    # A cell this surface would have to write for itself is a cell it will not
    # write at all.
    bundle = bundle_with(figure(renderings={LANGUAGE_ENGLISH: "500.00"}))

    with pytest.raises(SurfaceRenderFailed):
        HtmlReportRenderer().render_html(bundle)


def test_no_source_column_value_reaches_the_page() -> None:
    # `invoice_no` is a transaction identifier, so it never becomes a governed
    # bucket label and has no business being printed. The branch names do appear,
    # which is what stops this from passing because the page is empty.
    surface = HtmlReportRenderer().render_html(ReportBundle.of(package()))

    for document in surface.documents.values():
        assert "INV-" not in document
    assert "Cairo" in surface.documents[LANGUAGE_ENGLISH]


# --- escaping --------------------------------------------------------------


def test_the_report_environment_autoescapes() -> None:
    assert build_environment().autoescape is True
    assert HtmlReportRenderer().environment.autoescape is True


def test_an_environment_that_does_not_autoescape_is_refused() -> None:
    with pytest.raises(ValueError, match="autoescape"):
        HtmlReportRenderer(environment=Environment(autoescape=False))


def test_a_hostile_label_is_escaped_rather_than_injected() -> None:
    # Absence of `<script>` alone would also pass if the renderer had simply
    # dropped the label, so the escaped form has to be present too.
    hostile = "<script>alert(1)</script>"
    bundle = bundle_with(figure(label=hostile))

    document = HtmlReportRenderer().render_html(bundle).documents[LANGUAGE_ENGLISH]

    assert "<script>" not in document
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in document


def test_hostile_commentary_is_escaped_rather_than_injected() -> None:
    # Narrative prose is provider-controlled text, so it is escaped on exactly
    # the same terms as a customer label.
    hostile = '</p><img src=x onerror="alert(1)">'
    bundle = ReportBundle.of(package(), narrative=narrative_for(hostile))

    document = HtmlReportRenderer().render_html(bundle).documents[LANGUAGE_ENGLISH]

    assert "<img" not in document
    # The attribute never becomes an attribute: its quotes are escaped too.
    assert 'onerror="' not in document
    assert "&lt;img src=x onerror=&#34;alert(1)&#34;&gt;" in document


def test_the_template_marks_nothing_safe() -> None:
    # One `|safe` in the template is an escaping convention rather than an
    # escaping guarantee, and the stylesheet is included as template source
    # precisely so that none is needed.
    source = (
        resources.files("khepri.rra.rendering")
        .joinpath("templates", TEMPLATE_NAME)
        .read_text(encoding="utf-8")
    )

    assert "|safe" not in source
    assert "| safe" not in source
    assert "Markup" not in source


# --- Arabic and English parity ---------------------------------------------


def test_arabic_and_english_carry_the_same_facts_caveats_and_citations() -> None:
    # Compared on the documents themselves rather than on the two claim objects
    # the renderer built: comparing the claims would only prove the renderer
    # agrees with itself.
    bundle = ReportBundle.of(package(), narrative=narrative_for())
    surface = HtmlReportRenderer().render_html(bundle)
    documents = surface.documents

    assert bundle.caveats
    for language, document in documents.items():
        for entry in bundle.figures:
            # A row count states itself on the audit surface, so parity for one
            # is checked there. Asserting it against the business document would
            # pass only by coincidence -- a count of `1` appears in almost any
            # page -- which is a weaker check than the one it looks like.
            stated = document if entry.kind != KIND_ROWS else surface.evidence[language]
            assert entry.renderings[language] in stated
            # The citation identifier is Audit-tier under RRA-009 and reaches the
            # evidence document rather than the business page. Asserted there, in
            # the same loop, so parity still covers it: a citation present in one
            # language's evidence and missing from the other's is the failure this
            # test exists to catch, wherever the citation lives.
            assert entry.citation_id in surface.evidence[language]
        for caveat in bundle.caveats:
            assert caveat_prose(caveat.code, language) in document
        # The governed disclosure, in full. A shortened or reworded one is not
        # the disclosure, and `bundle.reconcile` refuses it for the same reason.
        assert bundle.disclosure(language) in document

    # `data-figure-id` is gone from the business page by design -- RRA-009 keeps an
    # identifier in an attribute only where a reader uses one, and that hook served
    # tooling. Parity is therefore counted on the figure rows the two languages
    # actually render, which is the property the attribute count stood in for.
    rows = {
        language: document.count('<td class="figure">')
        for language, document in documents.items()
    }
    assert rows[LANGUAGE_ARABIC] == rows[LANGUAGE_ENGLISH]
    # **The business page states every figure the bundle carries, row counts
    # included.** An earlier revision of this slice filtered `KIND_ROWS` out of the
    # business tables and this assertion was relaxed to match, counting only the
    # non-count figures. That inverted it: the visibility matrix classifies a
    # figure's `text` Business and only its `kind` column Audit, so the relaxed
    # form asserted the defect. The count is now stated in its own column beside
    # the value it explains, and the identity is whole again.
    counts = [figure for figure in bundle.figures if figure.kind == KIND_ROWS]
    assert counts, "the fixture must carry row counts for this split to mean anything"
    assert rows[LANGUAGE_ENGLISH] == len(bundle.figures)
    for document in documents.values():
        assert "data-figure-id" not in document


def test_both_readers_are_told_the_same_thing_about_the_commentary() -> None:
    for state, refused, narrative in (
        ("included", False, narrative_for()),
        ("refused", True, None),
        ("omitted", False, None),
    ):
        bundle = ReportBundle.of(
            package(),
            narrative=narrative,
            narrative_refused=refused,
        )
        surface = HtmlReportRenderer().render_html(bundle)

        assert bundle.narrative_state == state
        for language, document in surface.documents.items():
            assert bundle.disclosure(language) in document
            # `narrative_state` is tier I -- Internal -- under RRA-009, which
            # renders an Internal field "on no customer surface, including the
            # audit region". So it is absent from *both* documents rather than
            # relocated: Internal is not a quieter Audit. The governed disclosure
            # prose stays; the operational attribute beside it does not.
            #
            # Asserted on the attribute and on a provenance row rather than on the
            # bare state string. `narrative_state` takes the value `refused`, which
            # is also the CSS class on a refused section's prose -- a substring
            # search reports that legitimate class as a leak.
            assert "data-narrative-state" not in document, language
            assert "narrative_state" not in document, language
            assert "narrative_state" not in surface.evidence[language], language


def test_the_page_furniture_is_one_table_with_one_key_set() -> None:
    # A heading added to one language and forgotten in the other is a page that
    # reads differently to two readers, and no data-level check would see it.
    chrome = html_module._CHROME

    assert set(chrome) == set(REQUIRED_LANGUAGES)
    assert set(chrome[LANGUAGE_ARABIC]) == set(chrome[LANGUAGE_ENGLISH])
    for entries in chrome.values():
        for name, text in entries.items():
            _assert_filled(name, text, chrome[LANGUAGE_ENGLISH][name])


def _assert_filled(name: str, text: object, english: object) -> None:
    """One chrome entry, which may itself be a table of them.

    Nested tables -- section headings, chart descriptions, metric names -- are walked
    too. A table added to one language and forgotten in the other is the failure this
    test exists to catch, and nesting must not open a hole in it.
    """
    if not isinstance(text, dict):
        assert isinstance(text, str)
        assert text.strip(), name
        return
    assert isinstance(english, dict)
    assert set(text) == set(english), name
    for key, nested in text.items():
        _assert_filled(f"{name}.{key}", nested, english[key])


# --- layout ----------------------------------------------------------------


@pytest.mark.parametrize(
    "physical",
    [
        "margin-left",
        "margin-right",
        "padding-left",
        "padding-right",
        "border-left",
        "border-right",
        "text-align: left",
        "text-align: right",
        "float: left",
        "float: right",
    ],
)
def test_the_bundled_stylesheet_uses_logical_properties_only(physical: str) -> None:
    # KHEPRI-DEC-005 governs RTL with logical properties. A physical rule is
    # correct in one direction and wrong in the other, and the usual repair is a
    # mirrored stylesheet that drifts from the original.
    assert physical not in stylesheet()


def test_the_bundled_stylesheet_actually_uses_the_logical_properties() -> None:
    # The absence test above passes on an empty file, so the presence of the
    # logical forms is what makes it mean anything.
    source = stylesheet()

    for logical in (
        "margin-inline",
        "padding-inline",
        "border-inline-start",
        "text-align: start",
        "inset-inline-start",
    ):
        assert logical in source


def test_the_page_names_arabic_capable_fonts_and_leaves_room_to_embed_them() -> None:
    source = (
        resources.files("khepri.rra.rendering")
        .joinpath("templates", TEMPLATE_NAME)
        .read_text(encoding="utf-8")
    )

    assert "Noto Sans Arabic" in stylesheet()
    # The blocks a print stylesheet and real font binaries are layered on by,
    # so the PDF surface reuses this template instead of forking it.
    assert "{% block embedded_fonts %}" in source
    assert "{% block print_stylesheet %}" in source


def test_the_stylesheet_ships_inside_the_page_rather_than_as_a_second_request() -> None:
    document = HtmlReportRenderer().render_html(ReportBundle.of(package())).documents[
        LANGUAGE_ENGLISH
    ]

    assert "<style>" in document
    assert "margin-inline" in document
    # Bundled means bundled: nothing on this page fetches anything.
    assert "<link" not in document
    assert "<script" not in document


# --- charts ----------------------------------------------------------------

# Every class `_chart.svg.j2` puts on an element. The stylesheet carried a rule
# for none of them, so each painted at its SVG default: marks solid black,
# labels black on top of those marks, and a polyline the template already sets
# `fill="none"` on left with no stroke, which paints nothing at all whatever its
# geometry says.
CHART_CLASSES = ("chart", "chart__mark", "chart__curve", "chart__label")


def declarations_of(selector: str) -> str:
    """The declaration block of the first rule naming this selector."""
    source = stylesheet()
    start = source.index(selector)
    return source[source.index("{", start) : source.index("}", start)]


@pytest.mark.parametrize("name", CHART_CLASSES)
def test_the_stylesheet_rules_on_every_chart_class_the_template_emits(name: str) -> None:
    # No assertion about the document can catch an unstyled chart. The elements
    # are all present, correctly positioned and correctly labelled, and a reader
    # still sees black blocks -- so the contract is checked here, against the
    # stylesheet, which is the artifact that was missing.
    assert f".{name}" in stylesheet(), name


def test_the_curve_is_stroked_rather_than_left_to_paint_nothing() -> None:
    # The RRA-008 concentration curve. `fill="none"` is inline in the template,
    # so a polyline this sheet gives no stroke is invisible while every
    # assertion about its `points` attribute keeps passing.
    block = declarations_of(".chart__curve")

    assert "stroke:" in block
    assert "stroke: none" not in block


def test_a_chart_mark_is_filled_from_the_report_palette() -> None:
    # Not the SVG default black, which ignores the palette, prints as a slab of
    # ink, and renders two touching grouped bars as one solid rectangle.
    block = declarations_of(".chart__mark")

    assert "fill:" in block
    assert "var(--report-" in block


def test_a_chart_label_stays_legible_where_it_is_placed() -> None:
    # `charts.build_chart` puts every label at `y = CHART_HEIGHT`, which is
    # inside the plotting area and therefore on top of the marks. Legibility is
    # the stylesheet's problem: the label needs to be smaller than body text and
    # separated from whatever it overlaps.
    block = declarations_of(".chart__label")

    assert "font-size:" in block
    assert "paint-order:" in block
