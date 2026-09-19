"""`RRA-015` `FR-189` — the accessibility floors on the report and evidence surfaces.

`FR-189` names ten floors and requires them "asserted per surface as tests, in both
languages". This module is that assertion. **It changes no source file**: where a floor
fails, the fix belongs to the slice that owns the failing file.

**The roster is a reviewed literal, because no independent source exists.** The allocation
plan rules out `SECTION_CHART_KINDS`, which maps five *sections* and knows nothing about the
evidence drawer. `html.py`'s `TEMPLATE_NAME`/`EVIDENCE_TEMPLATE_NAME` were considered and
rejected for the same reason one level down: those are template file NAMES, not surfaces.
The roster below is `HtmlSurface`'s two mappings, confirmed against `FR-189`'s wording.

**The PDF surface is out on two independent grounds.** `RRA-015:140` excludes the PDF
renderer from this specification's scope, and `report.pdf.html.j2` carries zero focusable
elements against `report.html.j2`'s six -- so "visible focus on every tab stop" has no
subject there. Either ground alone would be arguable.

**Two floors are recorded absences, pinned two-sided.** `role="status"` and
labels-associated-with-controls have no subject on a read-only report: zero status regions
and zero form controls. Each is asserted as an implication plus a record that the antecedent
is false today, so the pin fails the day a subject ships rather than passing over nothing.
"""

from __future__ import annotations

import re

import pytest

from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering.html import HtmlReportRenderer
from tests.test_rra006_html_sections import ROWS, package_for

#: Both languages `FR-189` requires. Arabic is an equal surface, not a translation.
_LANGUAGES = ("ar", "en")

#: The reviewed literal. `HtmlSurface` exposes exactly these two mappings, and `FR-189`
#: names "the report and evidence surfaces". Reviewed against that wording; see the module
#: docstring for the two rejected derivations.
_SURFACES = ("documents", "evidence")

#: `dir` per language, the pairing a server computes from the language alone.
_DIRECTION = {"ar": "rtl", "en": "ltr"}

#: The supported viewports. `RRA-015` §Verification requires no page-level horizontal
#: overflow "at any width", which a single width cannot establish: a responsive layout
#: passes at 1180px and fails at 390px, where doubled text has a quarter of the room.
_VIEWPORTS = ((1180, 900), (390, 844))

#: `FR-189` target-floor failures, recorded not fixed, keyed by the exact case that fails.
#: Both live in stylesheets a follow-on slice under `RRA-015` owns. An evidence slice that
#: edited them to go green would hide the defect rather than record it.
_TARGET_FLOOR_FAILURES = {
    ("documents", "en"): (
        "FR-189 floor failure in report.css. The report surface's 'On this page' nav "
        "anchors render at 21px against the 44px floor; report.css declares no minimum "
        "target size at all."
    ),
    ("documents", "ar"): (
        "FR-189 floor failure in report.css, the Arabic report surface. Same cause as the "
        "English one: no minimum target size is declared."
    ),
    ("evidence", "ar"): (
        "FR-189 floor failure on the ARABIC evidence surface only: a tab stop measures "
        "135x21px against the 44x44 floor. `evidence/en` PASSES at 47px, so this is a "
        "language-specific layout failure, not a missing rule -- which is why the marker "
        "is keyed by (surface, language) and not by surface."
    ),
}

#: `FR-189` reflow failures at 200% text, keyed the same way. Both languages fail on the
#: evidence surface at the narrow viewport; the wide viewport passes.
_REFLOW_FAILURES = {
    ("evidence", "ar", 390),
    ("evidence", "en", 390),
}


def _surfaces(*, published: bool = True) -> dict[tuple[str, str], str]:
    """Every governed surface, keyed by (surface, language).

    Published by default: a chart belongs to an `RRA-008` family and only the published
    triple admits one. Under the default fixture both surfaces render zero `<svg>`, so a
    chart assertion would pass over nothing -- the trap this module's plan names.
    """
    rendered = HtmlReportRenderer().render_html(
        ReportBundle.of(package_for(ROWS, published=published))
    )
    out: dict[tuple[str, str], str] = {}
    for surface in _SURFACES:
        mapping = getattr(rendered, surface)
        for language in _LANGUAGES:
            out[(surface, language)] = mapping[language]
    return out


def _refusal_bearing_surfaces() -> dict[tuple[str, str], str]:
    """The surfaces on the fixture that actually renders refusals.

    A chart needs `published=True`; a refusal panel needs the opposite. `V-concentration`
    closed the refusal window, so the published triple admits a family and draws a chart,
    while the unpublished one refuses sections instead. Measured: unpublished renders 4
    refusal panels on the report surface, published renders 0. Two clauses of `FR-189`
    therefore need two fixtures, and asserting both against one would leave one unmeasured.
    """
    return _surfaces(published=False)


def test_the_roster_reaches_every_governed_surface_in_both_languages() -> None:
    """Equality plus non-empty over the roster, so one added later cannot ship unmeasured.

    A subset assertion hides a forgotten entry. This does not derive the expectation from
    the list the tests drive -- that would be the tautology the allocation plan rules out --
    it asserts the renderer exposes exactly the surfaces this module claims to cover.
    """
    rendered = HtmlReportRenderer().render_html(ReportBundle.of(package_for(ROWS)))
    exposed = {
        name
        for name in ("documents", "evidence")
        if isinstance(getattr(rendered, name, None), dict)
    }
    assert exposed == set(_SURFACES), (
        f"the renderer exposes {sorted(exposed)}, this module measures {sorted(_SURFACES)}"
    )
    for (surface, language), document in _surfaces().items():
        assert document.strip(), f"{surface}/{language} rendered nothing"


def test_every_surface_carries_exactly_one_h1_and_skips_no_heading_level() -> None:
    """`FR-189`: "exactly one `h1` with no skipped heading level"."""
    for (surface, language), document in _surfaces().items():
        levels = [int(level) for level in re.findall(r"<h([1-6])\b", document)]
        assert levels, f"{surface}/{language} renders no heading, so this proves nothing"
        assert levels.count(1) == 1, (
            f"{surface}/{language} renders {levels.count(1)} h1 elements, expected 1"
        )
        for previous, current in zip(levels, levels[1:], strict=False):
            assert current - previous <= 1, (
                f"{surface}/{language} skips from h{previous} to h{current}"
            )


def test_no_surface_declares_a_positive_tabindex() -> None:
    """`FR-189`: "focus order following document order with no positive `tabindex`".

    A positive value lifts an element out of document order for every keyboard user on the
    page, not only that element. `-1` and `0` are both in document order and allowed.
    """
    for (surface, language), document in _surfaces().items():
        values = re.findall(r'tabindex="(-?\d+)"', document)
        positive = [value for value in values if int(value) > 0]
        assert not positive, (
            f"{surface}/{language} declares positive tabindex {positive}, which reorders "
            "focus away from document order"
        )


def test_lang_and_dir_are_present_and_paired_on_every_surface() -> None:
    """`FR-189`: "`lang` and `dir` server-computed".

    This asserts the *output*. Provenance is a separate claim and a separate test: correct
    and template-inferred markup are identical here, so this test alone cannot distinguish
    them. See `test_no_template_infers_direction_from_anything_but_the_passed_value`.
    """
    for (surface, language), document in _surfaces().items():
        langs = re.findall(r"<html[^>]*\blang=\"([^\"]+)\"", document)
        dirs = re.findall(r"<html[^>]*\bdir=\"([^\"]+)\"", document)
        assert langs == [language], f"{surface}/{language} declares lang={langs}"
        assert dirs == [_DIRECTION[language]], f"{surface}/{language} declares dir={dirs}"


def test_no_template_infers_direction_from_anything_but_the_passed_value() -> None:
    """`FR-189`'s "server-computed" half, which reading the output cannot establish.

    A template that wrote `dir="{{ 'rtl' if language == 'ar' else 'ltr' }}"` would render
    byte-identical markup while moving the computation into the presentation layer. This
    reads the templates instead and refuses a conditional in the `dir` attribute.
    """
    from importlib.resources import files

    templates = files("khepri.rra.rendering").joinpath("templates")
    checked = 0
    found = 0
    for name in ("report.html.j2", "report.evidence.html.j2"):
        source = templates.joinpath(name).read_text(encoding="utf-8")
        checked += 1
        for match in re.findall(r'dir="\{\{([^}]*)\}\}"', source):
            found += 1
            # An allowlist, not a denylist. Rejecting `if` and `rtl` would admit
            # `directions[language]` and `direction_for(language)` -- both template-side
            # computations, both violating the same requirement. Requiring the expression
            # to BE the passed name admits exactly one form and refuses every other.
            assert match.strip() == "direction", (
                f"{name} sets dir from {match.strip()!r}; `FR-189` requires the value "
                "server-computed and passed in, so the expression must be `direction` "
                "alone -- an index, a call, or a conditional all move the computation "
                "into the presentation layer"
            )
    assert checked == 2, "the template roster changed; this scan measured the wrong set"
    assert found, "no dir attribute found in either template, so this scan proves nothing"


def test_every_chart_exposes_an_image_role_with_a_title_and_a_description() -> None:
    """`FR-189`: a chart exposes `role="img"` with a `<title>` and a `<desc>`.

    **The count assertion is the load-bearing half.** Under the default fixture both
    surfaces render zero `<svg>`, because a chart belongs to an `RRA-008` family and only
    the published triple admits one. Without the count, this test would assert "no chart
    lacks a description" over nothing and certify the clause while measuring nothing.
    """
    charts = 0
    for (surface, language), document in _surfaces().items():
        svgs = re.findall(r"<svg\b[^>]*>.*?</svg>", document, flags=re.S)
        charts += len(svgs)
        for svg in svgs:
            assert 'role="img"' in svg, f"{surface}/{language}: a chart declares no img role"
            # Presence is not the requirement: `FR-189` says the title and description are
            # "resolved from governed codes", and an empty `<title></title>` satisfies a
            # presence check while telling a screen reader nothing. Extract the text and
            # require it to be non-empty.
            for element in ("title", "desc"):
                match = re.search(rf"<{element}\b[^>]*>(.*?)</{element}>", svg, flags=re.S)
                assert match, f"{surface}/{language}: a chart carries no <{element}>"
                assert match.group(1).strip(), (
                    f"{surface}/{language}: a chart's <{element}> is empty, so it resolves "
                    "no governed wording for a reader who cannot see the chart"
                )

    assert charts > 0, (
        "no chart rendered on any surface, so this test proves nothing about FR-189's "
        "chart clause. The fixture must publish: only the published triple admits a family."
    )


def test_trust_states_are_differentiated_by_more_than_colour() -> None:
    """`FR-189`: "non-color differentiation for every trust state".

    A state signalled by colour alone is invisible to a reader who cannot distinguish it.
    Each badge carries text, which is the non-colour affordance.

    **Only the report surface renders trust badges.** The evidence surface's two `badge`
    substrings sit in its embedded stylesheet, not its markup -- a substring count says
    `2`, a class-attribute match says `0`. Measuring the substring is how a surface with no
    subject gets reported as covered. The companion test records which surfaces are absent.
    """
    measured = 0
    for (surface, language), document in _surfaces().items():
        badges = re.findall(r'class="[^"]*\bbadge\b[^"]*"[^>]*>([^<]*)', document)
        if not badges:
            continue
        measured += 1
        unlabelled = [badge for badge in badges if not badge.strip()]
        assert not unlabelled, (
            f"{surface}/{language} renders {len(unlabelled)} trust badge(s) with no text; "
            "colour would be their only differentiator"
        )
    assert measured, "no surface rendered a trust badge, so this test proves nothing"


def test_only_the_report_surface_renders_trust_badges_today() -> None:
    """The antecedent of the pin above, recorded so the absence stays visible.

    This fails the day the evidence surface grows a trust badge, which is the point: the
    conditional above would silently begin covering it, and the pair must be revisited.
    """
    bearing = {
        surface
        for (surface, _), document in _surfaces().items()
        if re.findall(r'class="[^"]*\bbadge\b[^"]*"', document)
    }
    assert bearing == {"documents"}, (
        f"trust badges now render on {sorted(bearing)}; FR-189's non-colour clause has a "
        "subject on a surface this module treats as absent"
    )


# --- recorded absences -----------------------------------------------------
#
# Two of `FR-189`'s floors have no reachable subject on a read-only report. Each is pinned
# as an implication plus a record that the antecedent is false today, so the pin fails the
# day a subject ships rather than passing over nothing. This is the shape `#486` established.


@pytest.mark.xfail(
    reason=(
        "FR-189 floor failure in _components.html.j2, recorded not fixed. A refusal panel "
        "renders with role='note', not role='status'. Measured on the unpublished fixture: "
        "4 refusal panels on the report surface, 0 status roles. The fix belongs to a "
        "follow-on slice under RRA-015 that owns that template."
    ),
    strict=True,
)
def test_every_refusal_panel_announces_itself_with_a_status_role() -> None:
    """`FR-189`: `role="status"` for refusals and progress.

    **The subject is located by its own markup, not by the role the clause requires.** An
    earlier form of this test asked "does any `role=status|progressbar|alert` region
    exist?" and, finding none, recorded the clause as having no subject. That was wrong in
    the way `khepri-a-refused-section-still-renders` describes: a refusal panel is
    `data-component="refusal-panel"` with `role="note"`, so a search keyed on the
    *conclusion* could never see the subject and the pin passed over a real failure.

    Measured at `154348e`: the unpublished fixture renders **4** refusal panels on the
    report surface and **0** status roles.
    """
    panels = 0
    for (surface, language), document in _refusal_bearing_surfaces().items():
        for panel in re.findall(
            r'<[^>]*data-component="refusal-panel"[^>]*>', document
        ):
            panels += 1
            assert 'role="status"' in panel, (
                f"{surface}/{language} renders a refusal panel without a status role: "
                f"{panel}"
            )
    assert panels, "no refusal panel rendered, so this test proves nothing"


def test_a_refusal_panel_is_reachable_on_some_fixture() -> None:
    """The subject of the pin above is real, asserted separately from its compliance.

    Without this, the xfail could start passing because refusal panels stopped rendering
    rather than because they gained a status role -- two very different facts that a single
    assertion cannot distinguish.
    """
    panels = sum(
        document.count('data-component="refusal-panel"')
        for document in _refusal_bearing_surfaces().values()
    )
    assert panels, (
        "no fixture renders a refusal panel any more; FR-189's refusal clause has lost its "
        "subject and the pin above must be revisited rather than left to pass"
    )


def test_any_form_control_is_associated_with_a_label() -> None:
    """`FR-189`: "labels associated with controls".

    Conditional for the same reason: a report is a read-only presentation and renders no
    `<input>`, `<select>` or `<textarea>`. The implication holds vacuously today and is
    asserted so it binds the moment a control appears.
    """
    for (surface, language), document in _surfaces().items():
        controls = re.findall(r"<(?:input|select|textarea)\b[^>]*>", document)
        for control in controls:
            identifier = re.search(r'\bid="([^"]+)"', control)
            labelled = re.search(r"\baria-label(?:ledby)?=", control)
            assert labelled or (
                identifier and f'for="{identifier.group(1)}"' in document
            ), f"{surface}/{language} renders an unlabelled control: {control}"


def test_the_report_surfaces_render_no_form_control_today() -> None:
    """The antecedent of the labels pin, recorded for the same reason."""
    for (surface, language), document in _surfaces().items():
        controls = re.findall(r"<(?:input|select|textarea)\b", document)
        assert not controls, (
            f"{surface}/{language} now renders {len(controls)} form control(s); FR-189's "
            "label clause has a subject and its test must stop being conditional"
        )


# --- the real browser ------------------------------------------------------
#
# Focus visibility, target size and 200% reflow are computed, not declared: no reading of
# the markup can say whether an outline paints or a layout overflows.


def _launch_chromium(playwright: object) -> object:
    """The pinned Chromium, or `pytest.skip` when this machine genuinely has none."""
    from playwright.sync_api import Error

    try:
        return playwright.chromium.launch()  # type: ignore[attr-defined]
    except Error as error:  # pragma: no cover - depends on the environment
        pytest.skip(f"Pinned Chromium is unavailable: {error}")


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_tab_stop_shows_focus(language: str) -> None:
    """`FR-189`: a visible focus on every tab stop.

    Split from the target-size floor deliberately: that floor currently FAILS on the report
    surface and is recorded as a strict xfail below. Two floors sharing one test would let
    one failure mask the other's result, so each carries its own evidence
    (`khepri-redundant-guards-need-separate-evidence`).
    """
    from playwright.sync_api import sync_playwright

    surfaces = _surfaces()
    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})  # type: ignore[attr-defined]
            for surface in _SURFACES:
                page.set_content(surfaces[(surface, language)], wait_until="domcontentloaded")
                stops = page.locator(
                    "a[href]:visible, button:visible, [tabindex='0']:visible"
                ).all()
                if not stops:
                    continue
                for stop in stops:
                    stop.focus()
                    outline = page.evaluate(
                        "() => { const c = getComputedStyle(document.activeElement);"
                        " return {style: c.outlineStyle, width: c.outlineWidth}; }"
                    )
                    assert outline["style"] != "none" and outline["width"] != "0px", (
                        f"{surface}/{language}: a tab stop paints no visible focus "
                        f"(style={outline['style']}, width={outline['width']})"
                    )
        finally:
            browser.close()  # type: ignore[attr-defined]


@pytest.mark.browser
@pytest.mark.parametrize("surface", _SURFACES)
@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_tab_stop_meets_the_target_floor(
    request: pytest.FixtureRequest, language: str, surface: str
) -> None:
    """`FR-189`: "targets of at least 44px on the element a pointer lands on".

    **Measured on the element itself, not an ancestor.** That wording is deliberate: a 44px
    wrapper around a 21px link is a target a pointer misses, and asserting the wrapper's box
    would report it as passing.

    **Both dimensions.** A target 10px wide and 44px tall is not a 44px target; checking
    height alone admits it.

    **Parametrized per surface, and the xfail applied to `documents` only.** A
    function-level xfail with the report surface measured first meant the evidence
    surface -- which passes at 47px -- was never reached, so this module claimed evidence
    it had not produced.
    """
    from playwright.sync_api import sync_playwright

    # Two distinct recorded failures, marked per (surface, language) rather than per
    # function. A function-level xfail stopped at the report surface and never measured the
    # evidence one; a surface-level xfail would have hidden that `evidence/en` PASSES while
    # `evidence/ar` does not. Marking the exact failing cases is what keeps the ledger able
    # to say which subjects are broken and which are sound.
    if (surface, language) in _TARGET_FLOOR_FAILURES:
        request.node.add_marker(
            pytest.mark.xfail(reason=_TARGET_FLOOR_FAILURES[(surface, language)], strict=True)
        )

    document = _surfaces()[(surface, language)]
    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})  # type: ignore[attr-defined]
            page.set_content(document, wait_until="domcontentloaded")
            stops = page.locator(
                "a[href]:visible, button:visible, [tabindex='0']:visible"
            ).all()
            assert stops, f"{surface}/{language} has no tab stop, so this proves nothing"
            for stop in stops:
                box = stop.bounding_box()
                assert box is not None, f"{surface}/{language}: a tab stop has no box"
                assert box["height"] >= 44 and box["width"] >= 44, (
                    f"{surface}/{language}: a tab stop is "
                    f"{box['width']}x{box['height']}px, below the 44x44 floor"
                )
        finally:
            browser.close()  # type: ignore[attr-defined]


@pytest.mark.browser
@pytest.mark.parametrize("surface", _SURFACES)
@pytest.mark.parametrize("viewport", _VIEWPORTS)
@pytest.mark.parametrize("language", _LANGUAGES)
def test_text_scales_to_200_percent_without_horizontal_overflow(
    request: pytest.FixtureRequest,
    language: str,
    viewport: tuple[int, int],
    surface: str,
) -> None:
    """`FR-189`: text scales to 200% without loss of content or function.

    `RRA-015` §Verification adds "no page-level horizontal overflow at **any** width".
    Doubling the root font size is the reflow test: a layout built on fixed pixel widths
    pushes the page wider instead of wrapping, and the content a reader needs moves
    off-screen.

    **Every supported viewport, not just the widest.** A responsive layout passes at 1180px
    and fails at 390px, where the doubled text has a quarter of the horizontal room; a
    single-width test cannot establish "at any width" and a first form of this one claimed
    it from 1180px alone.
    """
    from playwright.sync_api import sync_playwright

    if (surface, language, viewport[0]) in _REFLOW_FAILURES:
        request.node.add_marker(
            pytest.mark.xfail(
                reason=(
                    f"FR-189 reflow failure: {surface}/{language} overflows by ~184px at "
                    f"{viewport[0]}px with 200% text. The wide viewport passes, so this is "
                    "a narrow-width layout failure in the evidence surface's stylesheet, "
                    "owned by a follow-on slice under RRA-015."
                ),
                strict=True,
            )
        )

    document = _surfaces()[(surface, language)]
    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(  # type: ignore[attr-defined]
                viewport={"width": viewport[0], "height": viewport[1]}
            )
            page.set_content(document, wait_until="domcontentloaded")
            page.add_style_tag(content="html { font-size: 200% !important; }")
            overflow = page.evaluate(
                "() => document.documentElement.scrollWidth - window.innerWidth"
            )
            assert overflow <= 0, (
                f"{surface}/{language} at {viewport[0]}px overflows by {overflow}px at "
                "200% text; content moves off-screen rather than reflowing"
            )
        finally:
            browser.close()  # type: ignore[attr-defined]
