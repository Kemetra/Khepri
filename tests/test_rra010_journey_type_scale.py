"""`RRA-010`, master specification §G.1 — the journey carries no raw type size.

Slice 3 replaced nine raw sizes in `journey.css` with the journey's own scale tokens: four
`font-size` declarations and five `font` shorthands. The shorthands are the half a careless
scan misses -- a check worded for `font-size` alone passes green over all five and certifies
a false claim, which is why `_TYPE_SIZE` matches typographic declarations generally.

**The tokens are not merged.** `journey.css:57-58` records that `--journey-text-xs` and
`--journey-text-sm` are "a separate decision, not a rounding of the same one". Two rows map
to `xs` and seven to `sm`; this module asserts the scale still declares both.

**Every selector is asserted present before it is measured.** A selector matching no element
returns nothing and proves nothing while reporting PASS. Two of these nine render only on
`upload`, and a first roster that looked for them on `review` measured four null cases per
selector -- see `khepri-a-run-that-can-only-produce-the-null-case`.
"""

from __future__ import annotations

import re
from importlib.resources import files

import pytest

from tests.test_rra_journey_api import client

#: Each selector and a step that actually renders it. `.contract-row label` and `.meta` are
#: `upload`'s -- `upload.html.j2:21,35,37` -- not `review`'s.
_TYPED_SELECTORS = {
    ".brand": "report",
    ".step-nav a": "report",
    ".intake-facts dt": "upload",
    ".contract-row label": "upload",
    ".meta": "upload",
    "th": "review",
    ".report-meta": "report",
    ".report-meta dt": "report",
    ".report-group h2": "report",
}

_LANGUAGES = ("en", "ar")
_VIEWPORTS = ((1180, 900), (390, 844))

#: A raw numeric type size in either form. The second alternative requires a numeric `rem`, so
#: `font: inherit` (`:72`, `:116`) carries no size and is correctly not matched.
_TYPE_SIZE = re.compile(
    r"font-size:\s*[0-9.]|font:\s*[^;]*[0-9]+(?:\.[0-9]+)?rem", re.IGNORECASE
)

#: The two tokens the journey's scale declares. `RRA-010` keeps them distinct.
_SCALE_TOKENS = ("--journey-text-xs", "--journey-text-sm")


def _journey_css() -> str:
    return (
        files("khepri.rra.journey")
        .joinpath("assets", "journey.css")
        .read_text(encoding="utf-8")
    )


def _without_comments(css: str) -> str:
    """The stylesheet with block comments removed.

    Load-bearing here: `journey.css` documents the raw values it replaced, in prose, right
    beside the declarations that replaced them. A scan reading comments would report every
    one of them as still declared and this module's central claim would be unfalsifiable in
    the wrong direction.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_the_journey_declares_no_raw_type_size() -> None:
    """Master specification §G.1, over both declaration forms.

    The emptiness assertion is not ceremony: a scan that matched nothing would pass, and
    "the sheet has no raw sizes" and "the scan read no declarations" are indistinguishable
    from a green result.
    """
    declarations = _without_comments(_journey_css())
    assert "font" in declarations, (
        "no typographic declaration found in journey.css, so this scan proves nothing"
    )

    raw = _TYPE_SIZE.findall(declarations)
    assert not raw, f"journey.css still declares {len(raw)} raw type size(s): {raw}"


def test_the_journey_scale_still_declares_both_tokens() -> None:
    """`journey.css:57-58` -- the two tokens are a separate decision, not one rounded twice.

    Slice 3 maps nine raw sizes onto the nearer token. A slice that instead collapsed the
    scale to a single token would restyle every paragraph in the journey, which it has no
    mandate for. This fails the day one token disappears.
    """
    declarations = _without_comments(_journey_css())
    for token in _SCALE_TOKENS:
        assert f"{token}:" in declarations, f"the journey scale no longer declares {token}"


@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_typed_selector_renders_where_this_module_measures_it(language: str) -> None:
    """The roster is reachable, asserted separately from what it measures.

    Without this, a selector that stopped rendering would silently reduce the browser tests
    below to no-ops, and they would keep reporting PASS.
    """
    for selector, step in _TYPED_SELECTORS.items():
        body = client().get(f"/beta/{language}/{step}").text
        token = selector.split()[-1].lstrip(".")
        assert token in body, (
            f"{language}/{step} renders nothing matching {selector!r}; the delta "
            "measurement for it would prove nothing"
        )


# --- the real browser ------------------------------------------------------
#
# A stylesheet reading cannot say what size a glyph is painted at: `var()` resolution, the
# cascade, and a narrow-viewport media query all sit between the declaration and the result.
# `.step-nav a` is the worked example -- `journey.css:198` already tokenised it inside a
# media query, so at 390px it was tokenised before this slice and only 1180px changed.


def _launch_chromium(playwright: object) -> object:
    """The pinned Chromium, or `pytest.skip` when this machine genuinely has none."""
    from playwright.sync_api import Error

    try:
        return playwright.chromium.launch()  # type: ignore[attr-defined]
    except Error as error:  # pragma: no cover - depends on the environment
        pytest.skip(f"Pinned Chromium is unavailable: {error}")


@pytest.mark.browser
@pytest.mark.parametrize("viewport", _VIEWPORTS)
@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_typed_selector_resolves_to_a_scale_token(
    language: str, viewport: tuple[int, int]
) -> None:
    """Every measured selector paints at one of the scale's two computed sizes.

    This is the assertion the raw-size scan cannot make. The scan proves the *source* names
    no literal; this proves the *result* is one of the two values the scale declares, so a
    token pointed at a new value fails here rather than passing a text search.

    `--journey-text-xs` is `0.7rem` and `-sm` is `0.82rem`; at the 16px root both journey
    viewports use, that is 11.2px and 13.12px.
    """
    from playwright.sync_api import sync_playwright

    expected = {"11.2px", "13.12px"}
    css = _journey_css()

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(  # type: ignore[attr-defined]
                viewport={"width": viewport[0], "height": viewport[1]}
            )
            for selector, step in _TYPED_SELECTORS.items():
                page.set_content(
                    client().get(f"/beta/{language}/{step}").text,
                    wait_until="domcontentloaded",
                )
                page.add_style_tag(content=css)
                locator = page.locator(selector)
                assert locator.count() > 0, (
                    f"{language}/{step}: {selector!r} matched nothing, so this "
                    "measurement would prove nothing"
                )
                size = page.evaluate(
                    "s => getComputedStyle(document.querySelector(s)).fontSize", selector
                )
                assert size in expected, (
                    f"{language}/{step} at {viewport}: {selector} paints at {size}, "
                    f"which is not one of the scale's sizes {sorted(expected)}"
                )
        finally:
            browser.close()  # type: ignore[attr-defined]


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_shorthand_substitutions_kept_family_and_weight(language: str) -> None:
    """Five of the nine rows are `font` shorthands, and an invalid one is dropped whole.

    A `var()` in the size slot of a shorthand is valid, but a malformed shorthand takes the
    family and line-height down with it -- silently, because the cascade simply falls
    through to an inherited value that often looks plausible. `.intake-facts dt` is the
    sharpest case: its shorthand carries no weight token, so the `var()` leads.
    """
    from playwright.sync_api import sync_playwright

    shorthands = {
        ".brand": ("report", "700"),
        ".intake-facts dt": ("upload", "400"),
        ".meta": ("upload", "400"),
        ".report-meta": ("report", "400"),
        ".report-group h2": ("report", "600"),
    }
    css = _journey_css()

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})  # type: ignore[attr-defined]
            for selector, (step, weight) in shorthands.items():
                page.set_content(
                    client().get(f"/beta/{language}/{step}").text,
                    wait_until="domcontentloaded",
                )
                page.add_style_tag(content=css)
                assert page.locator(selector).count() > 0, f"{selector!r} matched nothing"
                computed = page.evaluate(
                    "s => { const c = getComputedStyle(document.querySelector(s));"
                    " return {family: c.fontFamily, weight: c.fontWeight}; }",
                    selector,
                )
                assert "monospace" in computed["family"], (
                    f"{language}: {selector} lost its family ({computed['family']}); the "
                    "shorthand was dropped rather than parsed"
                )
                assert computed["weight"] == weight, (
                    f"{language}: {selector} weight is {computed['weight']}, expected {weight}"
                )
        finally:
            browser.close()  # type: ignore[attr-defined]
