"""`RRA-010` §73 — focus and navigation semantics on the journey surfaces.

The clause: "one skip-link mechanism, correct tab order, and visible focus on every tab
stop including scroll containers. Consolidating two journey-internal mechanisms is
authorized; adopting a shell-owned mechanism as the target is not."

**The consolidation half has no subject, and that is this module's first finding.** The
allocation plan assigned slice 2 the "journey half" of a two-mechanism split across
`journey.css` and `shell-components.css`. Those two files share a directory and are never
delivered to the same page: `base.html.j2` links `journey.css` alone, all five journey
templates extend it, there is no `@import`, and `shell-components.css` reaches only the
shell and legal templates. One mechanism is delivered, so there is nothing to consolidate
and §73's "adopting a shell-owned mechanism as the target is not [authorized]" is what
keeps it that way.

**Every assertion here derives its input from what a rendered page LINKS, never from a
directory scan.** A guard globbing `journey/assets/*.css` finds two `.skip-link` blocks
and fails a correct tree -- the `#486` defect, where three guards built from rendered
output fired on correct markup. `_delivered_css` is that discipline in one place.

This module changes no production file. All four clauses measured compliant before it was
written; the pins are two-sided so a later regression fails rather than passing quietly.
"""

from __future__ import annotations

import re
from importlib.resources import files

import pytest

from tests.test_rra_journey_api import client

#: The four journey steps and both languages, the roster the existing journey evidence uses.
_STEPS = ("upload", "review", "processing", "report")
_LANGUAGES = ("en", "ar")

#: `RRA-010`:134 -- "Interactive targets meet the minimum target size the existing journey
#: tests enforce". That floor is 44, asserted at `test_rra_journey_browser.py:155`. Its
#: selector list excludes `.skip-link`, which is the gap this module closes; it does not
#: edit that test.
_TARGET_FLOOR = 44

#: Physical properties with a logical counterpart. `RRA-010`:133 -- "Stylesheets contain no
#: physical directional CSS properties." Restated here rather than imported from
#: `test_r801_shell_tokens.py`: `FR-201` keeps the two surfaces' evidence separate, and a
#: cross-import would make a shell edit able to weaken the journey's pin.
_PHYSICAL = (
    "margin-left",
    "margin-right",
    "padding-left",
    "padding-right",
    "border-left",
    "border-right",
    "text-align: left",
    "text-align: right",
)


def _without_comments(css: str) -> str:
    """The stylesheet with block comments removed.

    Load-bearing: `journey.css` documents rules in prose, and a scan reading comments would
    report documented properties as declared.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _linked_stylesheets(html: str) -> list[str]:
    """Every stylesheet href the page carries, in link order."""
    return re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)


def _delivered_css(language: str, step: str) -> str:
    """The CSS a journey page actually delivers, resolved from its own `<link>` tags.

    This is the whole anti-`#486` discipline: the input is what the page links, so a sheet
    sitting in the same directory and reaching no journey page cannot make a correct tree
    fail, and a sheet newly linked cannot slip past unmeasured.
    """
    html = client().get(f"/beta/{language}/{step}").text
    hrefs = _linked_stylesheets(html)
    assert hrefs == ["/beta/assets/journey.css"], (
        f"{language}/{step} links {hrefs}; this module's assertions are scoped to the "
        "journey's own sheet, so a new link must be reviewed rather than silently measured"
    )
    return (
        files("khepri.rra.journey")
        .joinpath("assets", "journey.css")
        .read_text(encoding="utf-8")
    )


def _selector_parts(css: str) -> list[str]:
    """Every comma-separated selector part, with `:is()`/`:where()` unwrapped.

    Equality on a whole captured selector string misses a second mechanism three ways: a
    grouped selector (`.skip-link, .alt`), an `:is(.skip-link, .alt)` wrapper, and a
    pseudo-class variant. Counting *parts* is what the assertion means.
    """
    unwrapped = re.sub(r":(?:is|where)\(([^)]*)\)", r"\1", css, flags=re.IGNORECASE)
    parts: list[str] = []
    for selector in re.findall(r"([^{}]+)\{", unwrapped):
        parts.extend(part.strip() for part in selector.split(",") if part.strip())
    return parts


def _base(selector: str) -> str:
    """The selector with its pseudo-class or pseudo-element suffix removed."""
    return re.split(r"::?", selector, maxsplit=1)[0]


@pytest.mark.parametrize("language", _LANGUAGES)
@pytest.mark.parametrize("step", _STEPS)
def test_the_journey_delivers_exactly_one_skip_link_mechanism(
    language: str, step: str
) -> None:
    """`RRA-010` §73, the count rather than the presence.

    Presence is already covered by `test_rra_journey_accessibility.py`. What nothing saw
    was a *second* mechanism added beside the first, which is the drift this closes.
    """
    parts = _selector_parts(_without_comments(_delivered_css(language, step)))
    assert parts, "no rules found in the delivered CSS, so this test proves nothing"

    skip_like = {base for part in parts if "skip" in (base := _base(part)).lower()}
    assert skip_like == {".skip-link"}, (
        f"expected one skip-link mechanism on {language}/{step}, "
        f"found {len(skip_like)}: {sorted(skip_like)}"
    )


@pytest.mark.parametrize("language", _LANGUAGES)
@pytest.mark.parametrize("step", _STEPS)
def test_the_journey_declares_no_physical_directional_property(
    language: str, step: str
) -> None:
    """`RRA-010`:133, over the sheet the page actually delivers.

    An RTL layout that mirrors correctly cannot be built from physical properties, and
    Arabic is an equal surface rather than a translation of the English one.
    """
    declarations = _without_comments(_delivered_css(language, step)).lower()
    found = [physical for physical in _PHYSICAL if physical in declarations]
    assert not found, (
        f"{found} have logical counterparts; {language}/{step} delivers a sheet that "
        "cannot mirror correctly"
    )


# --- the real browser ------------------------------------------------------
#
# Tab order and focus visibility are computed, not declared: no static reading of the
# stylesheet can say which element a Tab press reaches or whether an outline paints. The
# tests below are the only ones here that can answer that, and they are skipped -- never
# silently passed -- when the pinned browser is absent. `FND-005` makes CI fail rather
# than report green when that happens.


def _launch_chromium(playwright: object) -> object:
    """The pinned Chromium, or `pytest.skip` when this machine genuinely has none."""
    from playwright.sync_api import Error

    try:
        return playwright.chromium.launch()  # type: ignore[attr-defined]
    except Error as error:  # pragma: no cover - depends on the environment
        pytest.skip(f"Pinned Chromium is unavailable: {error}")


def _page_with_journey_css(browser: object, language: str, step: str, viewport: tuple[int, int]):
    """A rendered journey page carrying the sheet it links, at a supported viewport."""
    page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})  # type: ignore[attr-defined]
    page.set_content(
        client().get(f"/beta/{language}/{step}").text, wait_until="domcontentloaded"
    )
    page.add_style_tag(content=_delivered_css(language, step))
    return page


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_journey_skip_link_is_the_first_tab_stop(language: str) -> None:
    """`RRA-010` §73, "correct tab order".

    Pressed from a CLEAN page load with no prior `focus()` call. A first measurement of
    this focused the link and *then* pressed Tab, and reported `.brand` -- a real
    measurement answering a different question, because focus had already moved past the
    link. A skip link that is not the first tab stop is one nobody reaches.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            for step in _STEPS:
                page = _page_with_journey_css(browser, language, step, (390, 844))
                page.keyboard.press("Tab")
                first = page.evaluate("document.activeElement.className")
                assert "skip-link" in first, (
                    f"{language}/{step}: first tab stop is {first!r}, not the skip link"
                )
        finally:
            browser.close()  # type: ignore[attr-defined]


@pytest.mark.browser
@pytest.mark.parametrize("viewport", [(1180, 900), (390, 844)])
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_journey_skip_link_meets_the_target_floor_when_focused(
    language: str, viewport: tuple[int, int]
) -> None:
    """`RRA-010`:134, applied to the skip link itself.

    `test_rra_journey_browser.py:155` enforces the same floor over buttons, language links
    and step-nav anchors. Its selector list does not include `.skip-link`, so the one
    target that exists purely for keyboard users was the one never measured. Measured
    while focused, because that is the only state in which it is on screen.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            for step in _STEPS:
                page = _page_with_journey_css(browser, language, step, viewport)
                link = page.locator(".skip-link")
                link.focus()
                box = link.bounding_box()
                assert box is not None, f"{language}/{step}: skip link has no box when focused"
                assert box["height"] >= _TARGET_FLOOR, (
                    f"{language}/{step} at {viewport}: focused skip link is "
                    f"{box['height']}px, below the {_TARGET_FLOOR}px floor"
                )
        finally:
            browser.close()  # type: ignore[attr-defined]


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_journey_scroll_container_shows_focus(language: str) -> None:
    """`RRA-010` §73, "visible focus on every tab stop including scroll containers".

    `.table-region` is the journey's one scroll container -- `overflow-x: auto` at
    `journey.css:160`, reached by keyboard through `tabindex="0"` on `review.html.j2:45`.
    A scroll container a keyboard user can enter but cannot see they have entered fails
    this clause, so the outline is the assertion.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = _page_with_journey_css(browser, language, "review", (390, 844))
            region = page.locator(".table-region")
            assert region.count() == 1, f"{language}: expected one scroll container"
            region.first.focus()
            assert "table-region" in page.evaluate("document.activeElement.className"), (
                f"{language}: the scroll container did not take focus"
            )
            outline = page.evaluate(
                "(() => { const s = getComputedStyle(document.activeElement);"
                " return {style: s.outlineStyle, width: s.outlineWidth}; })()"
            )
            # Both halves are load-bearing, and the width half was missing until a review
            # found it: `outline-width: 0` keeps `outlineStyle == "solid"`, so a style-only
            # assertion passes on a container that paints nothing. Mutation M6 confirmed the
            # hole -- the style check alone survived a zero-width outline.
            assert outline["style"] != "none" and outline["width"] != "0px", (
                f"{language}: the focused scroll container paints no visible outline "
                f"(style={outline['style']}, width={outline['width']})"
            )
        finally:
            browser.close()  # type: ignore[attr-defined]
