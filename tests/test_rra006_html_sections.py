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
    SECTION_PRESENT,
    SECTION_REFUSED,
    FactPackage,
    ReportBundle,
    reconcile,
)
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.wording import caveat_prose, refusal_message
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    published_mapping_identity,
)

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


def page(language: str = LANGUAGE_ENGLISH, rows: list | None = None) -> str:
    bundle = ReportBundle.of(package_for(rows or ROWS))
    surface = HtmlReportRenderer().render_html(bundle)
    # Reconciled here so no assertion below rests on a page the bundle would reject.
    reconcile(surface.content, bundle=bundle)
    return surface.documents[language]


def undrawable_section(rows: list | None = None) -> str:
    """The first present section this dataset draws no chart for.

    Derived rather than named. Both tests below used to name concentration, whose curve
    was unchartable for an unrelated defect; fixing that broke two tests whose subject
    -- what a section looks like when its figures cannot be drawn -- had not changed.
    """
    bundle = ReportBundle.of(package_for(rows or ROWS))
    return next(
        section.section_id
        for section in bundle.sections
        if section.state == SECTION_PRESENT and section.chart is None
    )


def section_block(rendered: str, section_id: str) -> str:
    """One section's markup, up to wherever the next section begins."""
    start = rendered.index(f'<section id="{section_id}"')
    following = rendered.find('<section id="', start + 1)
    return rendered[start:] if following == -1 else rendered[start:following]


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
    #
    # `citations` and `provenance` left this list under RRA-009, which moved both
    # sections to the audit region. Their anchors are gone from the business page
    # because the sections are -- a navigation link to an absent anchor is a dead
    # link, not a preserved guarantee. The colophon is what now tells a reader the
    # evidence exists, and `test_rra009_business_audit_split.py` asserts the
    # evidence document carries both sections.
    for anchor in ("caveats",):
        assert f'href="#{anchor}"' in rendered, anchor
    for moved in ("citations", "provenance"):
        assert f'href="#{moved}"' not in rendered, moved
    assert "colophon" in rendered


def test_a_refused_section_renders_its_governed_reason() -> None:
    """Two days settle no period, so the comparison refuses.

    The heading and the reason are both present, because a reader cannot otherwise
    tell "there was nothing to show" from "we could not show it".
    """
    rendered = page(rows=ROWS[:2])
    assert f'<section id="{SECTION_COMPARISON}"' in rendered
    assert 'class="refused"' in rendered
    assert "prior_window_absent" not in rendered
    assert refusal_message(
        "prior_window_absent",
        context="section",
        language=LANGUAGE_ENGLISH,
    ) in rendered


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
    """A code printed raw is an identifier on the page, in either language.

    All three kinds are checked, because all three travel the same way: the title and
    description codes, and a label whose `localize` flag is set. `StrictUndefined`
    turns a missing chrome entry into a render failure rather than a blank, so this
    also proves every code the families produce has an entry.
    """
    for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
        rendered = page(language)
        assert "chart_title." not in rendered, language
        assert "chart_description." not in rendered, language
        assert "metric." not in rendered, language
        # A mode is an internal identifier too, and treating it as customer text put
        # `period_over_period` on both axes and in both tables.
        #
        # Checked as element *text* rather than as a substring, because a mode is also
        # part of a refused result's identity -- `revenue_delta_percent.year_over_year:
        # prior_window_absent` -- and that is a governed code rendered in `<code>`,
        # which is what this template does with every governed code. The failure being
        # guarded is an identifier standing alone where a name belongs.
        for mode in ("period_over_period", "year_over_year"):
            assert f">{mode}<" not in rendered, (language, mode)


def test_a_scalar_chart_names_each_bar_in_the_readers_language() -> None:
    """Growth compares three effects, so each bar has to say which effect it is.

    Their metrics are what distinguishes them -- the mode is common to all three --
    and a metric name is governed wording, so it is looked up rather than printed.
    """
    english = page(LANGUAGE_ENGLISH)
    arabic = page(LANGUAGE_ARABIC)

    assert "Price effect" in english
    assert "Volume effect" in english
    assert "أثر السعر" in arabic


def test_a_comparison_bar_names_the_window_it_compares() -> None:
    """A mode is governed wording, so it is translated rather than printed."""
    english = page(LANGUAGE_ENGLISH)
    arabic = page(LANGUAGE_ARABIC)
    assert "Against the previous period" in english
    assert "مقابل الفترة السابقة" in arabic


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
    """The table is the authoritative presentation, and a chart may never suppress it."""
    block = section_block(page(), undrawable_section())

    assert "<table" in block
    assert "<svg" not in block


def test_an_undrawable_chart_says_so_inside_its_own_section() -> None:
    """The caveat that keeps a chart failure honest.

    Returning no chart is not a disclosure: the section would simply look sparse.
    The caveat carries the distinction, and it is rendered under the section it
    qualifies rather than under the report's own caveats heading.
    """
    assert caveat_prose(CAVEAT_CHART_NOT_DRAWN, LANGUAGE_ENGLISH) in section_block(
        page(), undrawable_section()
    )


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
