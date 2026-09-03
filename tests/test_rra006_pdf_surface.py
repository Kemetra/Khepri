from __future__ import annotations

import base64
import hashlib
import re
from decimal import Decimal
from importlib import resources

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    LANGUAGE_DIRECTION,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    SURFACE_PDF,
    CitedEvidence,
    CitedFigure,
    ReportBundle,
    Section,
    reconcile,
)
from khepri.rra.facts import AdmittedInput, FactPackage, build_fact_package
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
    PdfNotPrintable,
    PdfReportRenderer,
    PrintablePage,
    SurfaceRenderFailed,
)
from khepri.rra.rendering import fonts as fonts_module
from khepri.rra.rendering.fonts import (
    FONT_DIGESTS,
    FONT_FAMILY,
    load_report_fonts,
)
from khepri.rra.rendering.pdf import (
    PDF_TEMPLATE_NAME,
    PRINT_STYLESHEET_NAME,
    PdfSurface,
)
from khepri.rra.rendering.wording import caveat_prose
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    published_mapping_identity,
)

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
    # Built under the published mapping identity: this module's subject is not
    # the version gate, so its packages must keep combining a triple
    # `versions.ADMITTED_PACKAGE_PAIRS` admits. The whole build sits inside the
    # block because `facts._assert_derived_from_profile` re-derives the mapping
    # and compares it by value, so restamping the object afterwards would fail
    # that provenance guard instead.
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
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


def figure(
    *,
    figure_id: str = "cit_test/value",
    label: str | None = None,
    renderings: dict[str, str] | None = None,
    value: str = "500.00",
) -> CitedFigure:
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


def _evidence_for(figures: tuple[CitedFigure, ...]) -> tuple[CitedEvidence, ...]:
    """A derived-shaped evidence record per distinct citation, for a hand-built bundle."""
    seen: dict[str, CitedEvidence] = {}
    for figure in figures:
        seen.setdefault(
            figure.citation_id,
            CitedEvidence(
                citation_id=figure.citation_id,
                metric=figure.metric,
                unit_kind=figure.unit_kind,
                formula_version="rra004.formula.v1",
                precision=None,
                inputs=None,
            ),
        )
    return tuple(seen.values())


def bundle_with(*figures: CitedFigure, caveats: tuple[str, ...] = ()) -> ReportBundle:
    base = ReportBundle.of(package())
    return ReportBundle(
        identity=base.identity,
        figures=figures,
        # `RRA-013` FR-102: the evidence region renders a drawer beside every figure row,
        # so a hand-built bundle carries a record per citation or the template fails closed.
        evidence=_evidence_for(figures),
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


def template_source(name: str) -> str:
    return (
        resources.files("khepri.rra.rendering")
        .joinpath("templates", name)
        .read_text(encoding="utf-8")
    )


# --- the fake browser -------------------------------------------------------


def tagged_pdf(*, tagged: bool = True, embedded: bool = True, closed: bool = True) -> bytes:
    """The smallest byte string that looks like what Chromium prints.

    Hand-built rather than captured, so a test can remove exactly one property
    -- the structure tree, the embedded font program, the trailer -- and nothing
    else, and see the renderer refuse for that one reason.
    """
    body = b"1 0 obj<</Type/Catalog"
    if tagged:
        body += b"/MarkInfo<</Marked true>>/StructTreeRoot 9 0 R/Lang(ar)"
    body += b">>endobj\n"
    if embedded:
        body += b"2 0 obj<</Type/FontDescriptor/FontName/AAAAAA+NotoSansArabic-Regular"
        body += b"/FontFile2 3 0 R>>endobj\n"
    return b"%PDF-1.4\n" + body + (b"%%EOF\n" if closed else b"")


class FakePrinter:
    """A hand-written `PagePrinter`. No browser, no mock library.

    It keeps every page it was handed, which is what makes the document
    Chromium *would* have printed available to assertions.
    """

    def __init__(self, *, blob: bytes | None = None) -> None:
        self.pages: list[PrintablePage] = []
        self._blob = tagged_pdf() if blob is None else blob

    def print_to_pdf(self, page: PrintablePage) -> bytes:
        self.pages.append(page)
        return self._blob

    @property
    def printed(self) -> dict[str, str]:
        return {page.language: page.document for page in self.pages}


def renderer_with(printer: FakePrinter | None = None) -> PdfReportRenderer:
    return PdfReportRenderer(printer=printer or FakePrinter())


# --- the surface the bundle will accept ------------------------------------


def test_the_pdf_surface_reconciles_against_the_bundle_it_was_built_from() -> None:
    # `bundle.reconcile` is the gate every surface passes, and the only judge of
    # whether this renderer presented what it was handed.
    bundle = ReportBundle.of(package(), narrative=narrative_for())
    renderer = renderer_with()

    reconcile(renderer.render(bundle), bundle=bundle)

    assert renderer.surface == SURFACE_PDF


def test_each_language_is_printed_as_its_own_document_declaring_how_it_reads() -> None:
    # One PDF has one root direction, so one file cannot be both `rtl` and
    # `ltr`. Two documents printed separately, each stating how it reads.
    printer = FakePrinter()

    surface = renderer_with(printer).render_pdf(ReportBundle.of(package()))

    assert set(surface.documents) == set(REQUIRED_LANGUAGES)
    assert {page.language for page in printer.pages} == set(REQUIRED_LANGUAGES)
    for page in printer.pages:
        assert page.direction == LANGUAGE_DIRECTION[page.language]
        assert f'lang="{page.language}"' in page.document
        assert f'dir="{page.direction}"' in page.document


def test_the_pdf_surface_reports_the_size_of_the_documents_it_printed() -> None:
    # RRA-007 records output size per stage, and `bytes` is where that number
    # comes from. Every printed document counts, not merely the first: a surface
    # reporting one language's file would report half the report.
    surface = renderer_with().render_pdf(ReportBundle.of(package()))

    printed = sum(len(blob) for blob in surface.documents.values())
    assert surface.content.output_size_bytes == printed
    assert printed > 0


# --- the renderer computes nothing ----------------------------------------


def test_the_printed_page_carries_the_supplied_rendering_never_the_value_beside_it() -> None:
    # `CitedFigure` carries a `Decimal` next to the string the bundle rendered.
    # Here the two deliberately disagree, so the page Chromium is handed can only
    # show the figure the bundle wrote -- formatting the `Decimal` would show the
    # other number. RRA-006 makes the fact package the sole source of every
    # figure, and this is what "sole" has to mean for a renderer.
    bundle = bundle_with(
        figure(renderings={LANGUAGE_ENGLISH: "999.99", LANGUAGE_ARABIC: "٩٩٩٫٩٩"})
    )
    printer = FakePrinter()

    renderer_with(printer).render_pdf(bundle)

    assert "999.99" in printer.printed[LANGUAGE_ENGLISH]
    assert "500.00" not in printer.printed[LANGUAGE_ENGLISH]
    assert "٩٩٩٫٩٩" in printer.printed[LANGUAGE_ARABIC]
    assert "٥٠٠٫٠٠" not in printer.printed[LANGUAGE_ARABIC]


def test_a_figure_with_no_rendering_for_a_language_is_refused() -> None:
    bundle = bundle_with(figure(renderings={LANGUAGE_ENGLISH: "500.00"}))

    with pytest.raises(SurfaceRenderFailed):
        renderer_with().render_pdf(bundle)


def test_no_source_column_value_reaches_the_printed_page() -> None:
    # `invoice_no` is a transaction identifier and never becomes a governed
    # bucket label. The branch names do appear, which is what stops this from
    # passing because the page is empty.
    printer = FakePrinter()

    renderer_with(printer).render_pdf(ReportBundle.of(package()))

    for document in printer.printed.values():
        assert "INV-" not in document
    assert "Cairo" in printer.printed[LANGUAGE_ENGLISH]


# --- the fonts the page carries into the browser ---------------------------


def test_the_printed_page_embeds_the_exact_font_bytes_this_package_ships() -> None:
    # The strongest claim available without a browser: the document handed to
    # Chromium carries the shipped Arabic face inline, byte for byte. Whether
    # Chromium honours it is a browser's business; whether it was *offered* is
    # this renderer's, and that is what this holds.
    printer = FakePrinter()

    renderer_with(printer).render_pdf(ReportBundle.of(package()))

    document = printer.printed[LANGUAGE_ARABIC]
    assert "@font-face" in document
    assert f'font-family: "{FONT_FAMILY}"' in document

    payloads = {
        base64.b64decode(match)
        for match in re.findall(r"data:font/woff2;base64,([A-Za-z0-9+/=]+)", document)
    }
    shipped = {font.payload for font in load_report_fonts()}
    assert payloads == shipped
    assert shipped, "the package ships at least one face"


def test_the_embedded_faces_cover_the_arabic_block_the_report_actually_uses() -> None:
    # A face embedded under a `unicode-range` that excludes Arabic is a font the
    # browser will never reach for, and the Arabic page would silently fall back
    # to whatever the host happens to have.
    printer = FakePrinter()

    renderer_with(printer).render_pdf(ReportBundle.of(package()))
    document = printer.printed[LANGUAGE_ARABIC]

    assert "unicode-range:" in document
    # The Arabic block, and the presentation forms Arabic shaping resolves to.
    assert "U+0600-06FF" in document
    assert "U+FB50-FDFF" in document


def test_the_shipped_font_files_are_the_audited_bytes() -> None:
    # Provenance for a binary, held the same way this codebase holds it for a
    # customer upload: by digest. A font swapped in the tree is a font that no
    # longer matches what was reviewed.
    assert FONT_DIGESTS
    for font in load_report_fonts():
        assert hashlib.sha256(font.payload).hexdigest() == FONT_DIGESTS[font.file_name]


def test_a_font_whose_bytes_do_not_match_the_manifest_is_refused() -> None:
    name = next(iter(FONT_DIGESTS))

    with pytest.raises(ValueError, match="digest"):
        fonts_module._require_audited(name, b"not the audited font")


def test_every_shipped_face_names_the_family_the_stylesheet_asks_for() -> None:
    # The bundled stylesheet already puts `Noto Sans Arabic` first in its stack.
    # An embedded face under any other family name would leave that first entry
    # unresolvable and the embedding pointless.
    assert "Noto Sans Arabic" in template_source("report.css")
    for font in load_report_fonts():
        assert font.family == FONT_FAMILY


# --- a PDF this surface will not publish -----------------------------------


@pytest.mark.parametrize(
    ("blob", "expected"),
    [
        # RRA-006 asks for a tagged, readable PDF. An untagged one is a picture
        # of a report, and a screen reader gets nothing at all from it.
        pytest.param(tagged_pdf(tagged=False), "tagged", id="untagged"),
        # A PDF referencing fonts it does not carry renders in whatever the
        # opening machine has -- which for Arabic is frequently nothing.
        pytest.param(tagged_pdf(embedded=False), "font", id="no-embedded-font"),
        # A printer that returned early hands back a prefix of a valid file, and
        # a prefix opens as a damaged document rather than as an error.
        pytest.param(tagged_pdf(closed=False), "truncated", id="truncated"),
        pytest.param(b"<html>not a pdf</html>", "not a PDF", id="not-a-pdf"),
        pytest.param(b"", "not a PDF", id="empty"),
    ],
)
def test_a_pdf_that_is_not_tagged_readable_and_whole_is_refused(
    blob: bytes,
    expected: str,
) -> None:
    # Neither tagging nor font embedding is visible in the object a printer
    # returns -- `bytes` is `bytes` -- so the bytes are inspected before a
    # surface exists. `BundleAssembler` turns this into an incomplete bundle,
    # which is the right outcome: no report beats an unreadable one.
    with pytest.raises(PdfNotPrintable, match=expected):
        renderer_with(FakePrinter(blob=blob)).render_pdf(ReportBundle.of(package()))


def test_a_surface_missing_a_governed_language_cannot_be_constructed() -> None:
    bundle = ReportBundle.of(package())
    content = renderer_with().render(bundle)

    with pytest.raises(ValueError):
        PdfSurface(content=content, documents={LANGUAGE_ENGLISH: tagged_pdf()})


# --- the template is extended, not forked ---------------------------------


def test_the_print_template_extends_the_web_template_rather_than_forking_it() -> None:
    # KHEPRI-DEC-005 consolidates bilingual rendering into one template. A second
    # copy of the page is a second place for Arabic parity to drift.
    source = template_source(PDF_TEMPLATE_NAME)

    assert '{% extends "report.html.j2" %}' in source
    assert "<!doctype" not in source.lower()
    assert "<body" not in source.lower()
    assert "{% block embedded_fonts %}" in source
    assert "{% block print_stylesheet %}" in source


def test_the_print_template_marks_nothing_safe() -> None:
    # Base64 uses none of the characters HTML escaping touches, so a font
    # payload needs no exemption -- and the guarantee only holds if none is
    # taken anyway.
    source = template_source(PDF_TEMPLATE_NAME)

    assert "|safe" not in source
    assert "| safe" not in source
    assert "Markup" not in source


def test_the_printed_page_fetches_nothing_from_the_network() -> None:
    # A report that reaches out while printing is a report whose content depends
    # on what a network returned, and whose rendering leaks that it was printed.
    printer = FakePrinter()

    renderer_with(printer).render_pdf(ReportBundle.of(package()))

    for document in printer.printed.values():
        assert "<link" not in document
        assert "<script" not in document
        assert "url(http" not in document
        assert "@import" not in document


# --- print layout ---------------------------------------------------------


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
def test_the_print_stylesheet_uses_logical_properties_only(physical: str) -> None:
    # The print sheet lays out the right-to-left document from the same
    # declarations as the left-to-right one, on the same terms as the screen
    # sheet. A physical inline offset is correct in one direction only.
    assert physical not in template_source(PRINT_STYLESHEET_NAME)


def test_the_print_stylesheet_governs_the_page_box_and_the_table_breaks() -> None:
    # The absence test above passes on an empty file, so the presence of the
    # rules that make a PDF readable is what makes it mean anything.
    source = template_source(PRINT_STYLESHEET_NAME)

    assert "@media print" in source
    assert "@page" in source
    # A table taller than one page needs its header repeated, or every page
    # after the first is a grid of unlabelled numbers.
    assert "table-header-group" in source
    assert "break-inside" in source
    # `overflow-x: auto` on screen becomes a clipped table on paper.
    assert "overflow: visible" in source


def test_the_print_stylesheet_overrides_the_dark_colour_scheme() -> None:
    # The screen sheet inverts its palette under `prefers-color-scheme: dark`.
    # Printing that produces white text on a black page, which is not readable
    # and is not what a reader asked to print.
    source = template_source(PRINT_STYLESHEET_NAME)
    printed = source[source.index("@media print") :]

    assert "--report-ink" in printed
    assert "--report-paper" in printed


def test_both_stylesheets_ship_inside_the_printed_page() -> None:
    # The print rules are only worth writing if they reach the document, and the
    # screen rules have to arrive too -- the print sheet layers onto them and
    # states no font stack, no table structure and no logical box of its own.
    printer = FakePrinter()

    renderer_with(printer).render_pdf(ReportBundle.of(package()))

    for document in printer.printed.values():
        assert "@page" in document
        assert "table-header-group" in document
        # From `report.css`, inherited through the parent template.
        assert "margin-inline" in document


def test_the_provenance_block_names_the_pdf_surface_version() -> None:
    # A reader holding a PDF can say which renderer produced it.
    printer = FakePrinter()

    renderer_with(printer).render_pdf(ReportBundle.of(package()))

    for document in printer.printed.values():
        assert "pdf_surface_version" in document


# --- Arabic and English parity --------------------------------------------


def test_arabic_and_english_carry_the_same_facts_caveats_and_citations() -> None:
    # Compared on the documents themselves rather than on the claim the renderer
    # built, which would only prove the renderer agrees with itself.
    bundle = ReportBundle.of(package(), narrative=narrative_for())
    printer = FakePrinter()

    renderer_with(printer).render_pdf(bundle)

    assert bundle.caveats
    for language, document in printer.printed.items():
        for entry in bundle.figures:
            assert entry.renderings[language] in document
            assert entry.citation_id in document
        for caveat in bundle.caveats:
            assert caveat_prose(caveat.code, language) in document
        assert bundle.disclosure(language) in document


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
        printer = FakePrinter()

        renderer_with(printer).render_pdf(bundle)

        assert bundle.narrative_state == state
        for language, document in printer.printed.items():
            assert bundle.disclosure(language) in document
            # Internal under RRA-009 and therefore on no customer surface at all --
            # the printed document carries the business body and the appendix
            # together, so this one assertion covers both regions.
            #
            # On the field name, not the bare value: `narrative_state` can be
            # `refused`, which is also the CSS class on a refused section's prose.
            assert "data-narrative-state" not in document, language
            assert "narrative_state" not in document, language


def test_a_hostile_label_is_escaped_rather_than_injected() -> None:
    hostile = "<script>alert(1)</script>"
    printer = FakePrinter()

    renderer_with(printer).render_pdf(bundle_with(figure(label=hostile)))

    document = printer.printed[LANGUAGE_ENGLISH]
    assert "<script>" not in document
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in document


# --- the real browser ------------------------------------------------------
#
# Everything above is proven with a hand-written fake and no browser. The two
# tests below are the only ones that can say anything about what Chromium
# actually does, and they are skipped -- not silently passed -- when the pinned
# browser is not installed.


def chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:  # pragma: no cover - depends on the environment
        return False
    try:
        import os

        with sync_playwright() as play:
            path = play.chromium.executable_path
        return bool(path) and os.path.exists(path)
    except Exception:  # pragma: no cover - depends on the environment
        return False


CHROMIUM = chromium_available()

needs_chromium = pytest.mark.skipif(
    not CHROMIUM,
    reason="the pinned Chromium is not installed; run `playwright install chromium`",
)


@pytest.mark.browser
@needs_chromium
def test_real_chromium_prints_a_tagged_pdf_carrying_the_shipped_arabic_face() -> None:
    from khepri.rra.rendering.chromium import launch_chromium

    bundle = ReportBundle.of(package(), narrative=narrative_for())

    with launch_chromium() as printer:
        surface = PdfReportRenderer(printer=printer).render_pdf(bundle)

    reconcile(surface.content, bundle=bundle)

    arabic = surface.documents[LANGUAGE_ARABIC]
    assert arabic.startswith(b"%PDF-")
    # Tagged: a structure tree, and a document element declaring Arabic.
    assert b"/StructTreeRoot" in arabic
    assert b"/Marked true" in arabic
    assert b"/Lang (ar)" in arabic
    # The face this package ships, embedded as a subsetted font program rather
    # than referenced by name and left to the host to find.
    assert b"/FontFile2" in arabic
    assert re.search(rb"/BaseFont\s*/[A-Z]{6}\+NotoSansArabic-Regular", arabic)


@pytest.mark.browser
@needs_chromium
def test_real_chromium_lays_the_arabic_page_out_right_to_left() -> None:
    # Tagging and embedding are visible in the bytes; direction is not. This
    # asks the engine that produced the PDF what it actually computed.
    from khepri.rra.rendering.chromium import launch_chromium
    from khepri.rra.rendering.pdf import PdfReportRenderer as Renderer

    printer_pages: dict[str, str] = {}

    class Capturing:
        def __init__(self, inner: object) -> None:
            self._inner = inner

        def print_to_pdf(self, page: PrintablePage) -> bytes:
            printer_pages[page.language] = page.document
            return self._inner.print_to_pdf(page)  # type: ignore[attr-defined]

    with launch_chromium() as printer:
        Renderer(printer=Capturing(printer)).render_pdf(ReportBundle.of(package()))

        page = printer.browser.new_page()
        try:
            page.set_content(printer_pages[LANGUAGE_ARABIC], wait_until="load")
            page.evaluate("() => document.fonts.ready")
            assert (
                page.evaluate("() => getComputedStyle(document.documentElement).direction")
                == "rtl"
            )
            # The Arabic face is not merely offered, it is loaded and usable.
            assert page.evaluate(
                f"() => document.fonts.check('16px \"{FONT_FAMILY}\"')"
            )
            # In a right-to-left table the first column sits furthest right.
            #
            # Asserted per table, not across the document. A flat scan of every
            # `thead th` on the page concatenates one descending run per table, and
            # the joined list is not itself descending as soon as a later table's
            # first column starts further right than an earlier table's last -- which
            # is ordinary, since the tables hold different content and size their
            # columns independently. The report now renders one table per governed
            # analysis, so the flat form failed on a correctly laid out page.
            tables = page.evaluate(
                "() => [...document.querySelectorAll('table')].map(table =>"
                " [...table.querySelectorAll('thead th')]"
                ".map(th => th.getBoundingClientRect().left))"
            )
            assert tables, "the Arabic page rendered no table to measure"
            for index, columns in enumerate(tables):
                assert len(columns) > 1, (index, columns)
                assert columns == sorted(columns, reverse=True), (index, columns)
        finally:
            page.close()
