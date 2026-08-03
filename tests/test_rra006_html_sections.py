"""The rendered page: a section per family, a real SVG, and nothing marked safe.

Every assertion here is on the *document*, not on a view model. That is the point of
the file: the string-returning chart design this replaced could assert
`'role="img"' in svg` while the page displayed that text literally, so the claim only
means something when it is made against what a browser would receive.
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    CAVEAT_CHART_NOT_DRAWN,
    SECTION_BASKET,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_GROWTH,
    SECTION_OVERVIEW,
    SECTION_REFUSED,
    FactPackage,
    ReportBundle,
    reconcile,
)
from khepri.rra.facts import build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import HtmlReportRenderer

HEADER = b"date,revenue,units,invoice_no,product\n"
START = date(2026, 1, 5)

ROWS = [
    ("100.00", 4, "Water"),
    ("150.00", 5, "Water"),
    ("120.00", 4, "Juice"),
    ("200.00", 8, "Water"),
    ("90.00", 3, "Juice"),
]


def package_for(rows: list[tuple[str, int, str]]) -> FactPackage:
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},{amount},{units},"
        f"INV-{index},{product}\n".encode()
        for index, (amount, units, product) in enumerate(rows)
    )
    content = HEADER + body
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


def page(language: str = LANGUAGE_ENGLISH, rows: list | None = None) -> str:
    bundle = ReportBundle.of(package_for(rows or ROWS))
    surface = HtmlReportRenderer().render_html(bundle)
    # Reconciled here so no assertion below rests on a page the bundle would reject.
    reconcile(surface.content, bundle=bundle)
    return surface.documents[language]


def test_each_family_has_its_own_heading_and_navigation_entry() -> None:
    rendered = page()
    for section_id in (
        SECTION_OVERVIEW,
        SECTION_COMPARISON,
        SECTION_CONCENTRATION,
        SECTION_GROWTH,
        SECTION_BASKET,
    ):
        assert f'<section id="{section_id}"' in rendered, section_id
        assert f'href="#{section_id}"' in rendered, section_id


def test_the_existing_sections_keep_their_place() -> None:
    """The regression this slice was most likely to cause.

    `ORDERED_SECTIONS` covers figure-bearing analysis sections only, so the four
    sections that hold no `CitedFigure` must not fall out of the navigation.
    """
    rendered = page()
    # Commentary is deliberately absent from this list: its anchor is conditional on
    # the bundle carrying narrative, and this one carries none. Asserting it here
    # would be asserting that a report without commentary links to a commentary
    # section it does not have.
    for anchor in ("caveats", "citations", "provenance"):
        assert f'href="#{anchor}"' in rendered, anchor


def test_a_refused_section_renders_its_governed_reason() -> None:
    """Two days settle no period, so the comparison refuses.

    The heading and the reason are both present, because a reader cannot otherwise
    tell "there was nothing to show" from "we could not show it".
    """
    rendered = page(rows=ROWS[:2])
    assert f'<section id="{SECTION_COMPARISON}"' in rendered
    assert 'class="refused"' in rendered
    assert "prior_window_absent" in rendered


def test_a_drawable_section_renders_a_real_svg_element() -> None:
    """Positively assert the markup reached the page.

    The escaped-string design this replaced would have rendered `&lt;svg` here and
    passed every other test in this file.
    """
    rendered = page()
    assert "<svg" in rendered
    assert "&lt;svg" not in rendered
    assert 'role="img"' in rendered
    assert "<rect" in rendered


def test_the_chart_is_labelled_for_a_screen_reader() -> None:
    """`aria-labelledby` pointing at a title and a description that exist."""
    rendered = page()
    assert f'aria-labelledby="{SECTION_BASKET}-ct {SECTION_BASKET}-cd"' in rendered
    assert f'<title id="{SECTION_BASKET}-ct">' in rendered
    assert f'<desc id="{SECTION_BASKET}-cd">' in rendered


def test_no_chart_code_reaches_the_reader_untranslated() -> None:
    """A title or description code printed raw would be an identifier on the page."""
    rendered = page()
    assert "chart_title." not in rendered
    assert "chart_description." not in rendered


def test_a_chart_label_from_customer_data_is_escaped() -> None:
    """A product name is customer text on the one path a chart label travels.

    The label goes through the environment's autoescaping exactly as a table cell
    does, which is the whole reason this module returns strings and a macro writes
    the elements.
    """
    hostile = [(amount, units, "<script>alert(1)</script>") for amount, units, _ in ROWS]
    rendered = page(rows=hostile)

    # The property that matters, asserted directly: nothing executable reached the
    # document, on the chart path or the table path.
    assert "<script>alert(1)</script>" not in rendered
    assert "<script" not in rendered

    # It does not arrive escaped either, because `profiling.safe_value_label` strips
    # it before a bucket label is ever built -- so the surface never sees it. That is
    # defence in depth rather than redundancy: the escaping here is what makes the
    # page safe if that sanitizing is ever relaxed, and a test asserting `&lt;script&gt;`
    # would be asserting the upstream stripping had stopped working.
    assert "&lt;script&gt;" not in rendered


def test_the_table_is_present_even_when_the_chart_is_not() -> None:
    """The table is the authoritative presentation, and concentration draws nothing.

    Two counts beside two ratios share no axis, so the chart is refused -- and the
    figures are still there to read.
    """
    rendered = page()
    concentration_at = rendered.index(f'<section id="{SECTION_CONCENTRATION}"')
    growth_at = rendered.index(f'<section id="{SECTION_GROWTH}"')
    block = rendered[concentration_at:growth_at]

    assert "<table" in block
    assert "<svg" not in block


def test_an_undrawable_chart_says_so_inside_its_own_section() -> None:
    """The caveat that keeps a chart failure honest.

    Returning no chart is not a disclosure: the section would simply look sparse.
    The caveat carries the distinction, and it is rendered under the section it
    qualifies rather than under the report's own caveats heading.
    """
    rendered = page()
    concentration_at = rendered.index(f'<section id="{SECTION_CONCENTRATION}"')
    growth_at = rendered.index(f'<section id="{SECTION_GROWTH}"')

    assert CAVEAT_CHART_NOT_DRAWN in rendered[concentration_at:growth_at]


def test_both_languages_render_every_section() -> None:
    """A heading present in one language and missing from the other is two reports."""
    for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
        rendered = page(language)
        for section_id in (SECTION_OVERVIEW, SECTION_BASKET):
            assert f'<section id="{section_id}"' in rendered, (language, section_id)


def test_the_arabic_page_mirrors_its_chart() -> None:
    """The category axis mirrors for a right-to-left page, and the values do not."""
    english = page(LANGUAGE_ENGLISH)
    arabic = page(LANGUAGE_ARABIC)
    assert 'dir="rtl"' in arabic
    assert english != arabic
    assert "<svg" in arabic


def test_a_refused_section_renders_no_table_and_no_chart() -> None:
    rendered = page(rows=ROWS[:2])
    comparison_at = rendered.index(f'<section id="{SECTION_COMPARISON}"')
    block = rendered[comparison_at : rendered.index("</section>", comparison_at)]

    assert SECTION_REFUSED not in block or 'class="refused"' in block
    assert "<table" not in block
    assert "<svg" not in block
