"""U1-04's placement RED tests: the drawer is not yet beside any figure.

Every RED test here fails on this tree, and each docstring says what it is waiting for.
They are the deliverable §15 requires before `U1`'s row may read
`READY_FOR_IMPLEMENTATION`. Strict `xfail`, as every U1 plan before this one.

**Assertions are on the rendered documents** -- the evidence page, the business page,
and the printed page -- because placement is a claim about what a reader receives.

Plan: `docs/superpowers/plans/2026-09-03-u1-04-drawer-placement-plan.md`.
Authority: active `RRA-012` FR-096, FR-096a, FR-097, FR-098, FR-099; `RRA-013` FR-107.
"""

from __future__ import annotations

import re

import pytest
from jinja2 import StrictUndefined
from jinja2.sandbox import ImmutableSandboxedEnvironment

from khepri.rra.bundle import ReportBundle
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering.html import HtmlReportRenderer, HtmlSurface
from khepri.rra.rendering.pdf import PdfReportRenderer
from khepri.rra.rendering.wording import component_chrome
from tests.test_rra006_pdf_surface import FakePrinter
from tests.test_rra013_evidence_supply import ROWS, package_for

RED = pytest.mark.xfail(strict=True, reason="U1-04 RED: the drawer is placed on no page yet.")

DRAWER = re.compile(r'<details[^>]*data-component="evidence-drawer"[^>]*>.*?</details>', re.S)
#: Every `<tr>` of the evidence figures table, in document order, so sibling structure
#: can be asserted rather than inferred from two independently collected lists.
TABLE_ROW = re.compile(r"<tr[^>]*>.*?</tr>", re.S)
ARABIC_SCRIPT = re.compile(r"[\u0600-\u06ff]")


@pytest.fixture(scope="module")
def bundle() -> ReportBundle:
    return ReportBundle.of(package_for(ROWS))


@pytest.fixture(scope="module")
def surface(bundle: ReportBundle) -> HtmlSurface:
    return HtmlReportRenderer().render_html(bundle)


def printed(bundle: ReportBundle, language: str) -> str:
    """The document Chromium would have printed, as the fake printer keeps it.

    `PdfSurface.documents` holds the printer's *bytes*; the HTML page it was handed is
    what `FakePrinter.printed` retains, and that is what the drawer assertions read.
    """
    printer = FakePrinter()
    PdfReportRenderer(printer=printer).render_pdf(bundle)
    return printer.printed[language]


# --------------------------------------------------------------------------
# FR-096 -- beside that figure
# --------------------------------------------------------------------------


@RED
@pytest.mark.parametrize("language", sorted(REQUIRED_LANGUAGES))
def test_every_evidence_figure_row_is_followed_by_its_drawer(
    surface: HtmlSurface, language: str
) -> None:
    """FR-096: the row after every figure row is that figure's drawer, and nothing else.

    Asserted on the table's sibling structure rather than on two lists paired by order
    (`#356` review): the body rows are walked in document order and must alternate
    figure row, drawer row, with each drawer citing the figure directly above it. An
    implementation rendering every drawer after the table would match counts and order
    and still fail here.
    """
    document = surface.evidence[language]
    table = document.split('id="evidence-figures"')[1].split("</table>")[0]
    rows = TABLE_ROW.findall(table.split("<tbody>")[1])
    assert rows, "no figure rows -- the fixture proves nothing"
    assert len(rows) % 2 == 0, "the body does not pair every figure row with a drawer row"
    for figure_row, drawer_row in zip(rows[0::2], rows[1::2], strict=True):
        assert '<th scope="row">' in figure_row and not DRAWER.search(figure_row)
        assert drawer_row.startswith('<tr class="evidence-drawer-row">'), (
            "the row after a figure row is not its drawer"
        )
        citation = re.search(r'href="#citation-([^"]+)"', figure_row)
        assert citation, "a figure row carries no evidence link"
        drawer = DRAWER.search(drawer_row)
        assert drawer, "a drawer row carries no drawer"
        assert f'href="#citation-{citation.group(1)}"' in drawer.group(0), (
            "a drawer does not cite the figure directly above it"
        )


@RED
def test_the_business_page_carries_no_drawer(surface: HtmlSurface) -> None:
    """Citation identifiers, versions and coverage are tier A; the business page has none."""
    for language in REQUIRED_LANGUAGES:
        assert not DRAWER.search(surface.documents[language]), "a drawer reached the business page"
    assert DRAWER.search(surface.evidence[LANGUAGE_ENGLISH]), "RED: no drawer anywhere yet"


# --------------------------------------------------------------------------
# FR-097, FR-104, FR-096a -- what each drawer states
# --------------------------------------------------------------------------


@RED
def test_the_drawer_reads_coverage_once_from_the_bundle(
    surface: HtmlSurface, bundle: ReportBundle
) -> None:
    """FR-104 upstream, FR-097 on the page: every drawer's coverage is the identity's."""
    identity = bundle.identity.coverage_manifest_identity
    assert identity, "the fixture carries no coverage manifest -- the test proves nothing"
    drawers = DRAWER.findall(surface.evidence[LANGUAGE_ENGLISH])
    assert drawers
    for drawer in drawers:
        assert identity in drawer, "a drawer states a coverage other than the bundle's"
        # Case-insensitive (`#356` review): a capitalised heading is still a population.
        assert not re.search(r"population|basis", drawer, re.IGNORECASE), (
            "a drawer names a per-figure population or basis"
        )


@RED
def test_a_derived_figure_drawer_states_absent_inputs(
    surface: HtmlSurface, bundle: ReportBundle
) -> None:
    """FR-096a on the page: a derived figure's drawer states its inputs are not stated."""
    unavailable = component_chrome(LANGUAGE_ENGLISH)["unavailable"]
    derived = {
        record.citation_id
        for record in bundle.evidence
        if record.inputs is None and record.precision is None
    }
    assert derived, "no derived record -- the fixture proves nothing"
    drawers = [
        drawer
        for drawer in DRAWER.findall(surface.evidence[LANGUAGE_ENGLISH])
        if any(f'href="#citation-{citation}"' in drawer for citation in derived)
    ]
    assert drawers
    for drawer in drawers:
        assert 'data-state="unavailable">' + unavailable in drawer


# --------------------------------------------------------------------------
# FR-099, FR-107 -- both languages, and open on paper only
# --------------------------------------------------------------------------


@RED
def test_drawers_render_in_arabic_with_arabic_labels(surface: HtmlSurface) -> None:
    """FR-099: every drawer label on the Arabic evidence page is Arabic."""
    drawers = DRAWER.findall(surface.evidence[LANGUAGE_ARABIC])
    assert drawers
    for drawer in drawers:
        labels = re.findall(r"<summary[^>]*>([^<]*)</summary>|<dt>([^<]*)</dt>", drawer)
        words = [opener or label for opener, label in labels]
        assert words and all(ARABIC_SCRIPT.search(word) for word in words), (
            f"drawer labels not in Arabic: {words}"
        )


@RED
def test_print_drawers_are_open_and_web_drawers_are_closed(
    surface: HtmlSurface, bundle: ReportBundle
) -> None:
    """`RRA-013` FR-107 meets FR-098: a closed `<details>` prints collapsed, so paper opens it."""
    web = DRAWER.findall(surface.evidence[LANGUAGE_ENGLISH])
    paper = DRAWER.findall(printed(bundle, LANGUAGE_ENGLISH))
    assert web and paper
    assert not any(re.match(r"<details[^>]*\sopen[\s>]", drawer) for drawer in web), (
        "a web drawer is open by default"
    )
    assert all(re.match(r"<details[^>]*\sopen[\s>]", drawer) for drawer in paper), (
        "a printed drawer is collapsed"
    )


def test_the_default_filter_survives_strict_undefined() -> None:
    """Check 3's premise, proven before the template depends on it. Not RED: holds today."""
    environment = ImmutableSandboxedEnvironment(undefined=StrictUndefined)
    rendered = environment.from_string("{{ evidence_open | default(false) }}").render()
    assert rendered == "False"
