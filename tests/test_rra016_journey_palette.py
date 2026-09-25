"""`RRA-016` `FR-220`–`FR-222`: the journey declares the master specification §16.5 palette.

The independent source is §16.5 itself, parsed from the master specification. Comparing
`journey.css` against `shell.css` would compare one copy of the palette with another and prove
nothing (`RRA-016` §Verification), so no assertion here reads a shell stylesheet for values.

The role table pins which §16.5 row each journey property takes, by row name, so a value that is
in the palette but on the wrong role (an error ink painted as the accent) still fails. The roles
are chosen by computed contrast: `gold-500` is about 2.3:1 as text, so the accent is `gold-ink`;
`border-strong` is 1.4:1, so a text input's boundary is `ink-secondary`, over the 3:1 non-text
floor. See `docs/superpowers/plans/2026-09-25-rra016-slice-1-palette-execution-plan.md`.

`FR-221` (a refusal never carries error paint) is pinned by `test_rra_journey_accessibility.py`
and is not restated here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Error, sync_playwright

from tests.test_rra_journey_api import client

_ROOT = Path(__file__).resolve().parents[1]
_MASTER_SPEC = _ROOT / "docs" / "product" / "KHEPRI_UI_UX_MASTER_SPEC.md"
_JOURNEY_CSS = _ROOT / "src" / "khepri" / "rra" / "journey" / "assets" / "journey.css"

#: §16.5 states 24 named rows and three status triplets (nine values). The warning ink is the
#: same value as `gold-ink`, so the distinct palette is one smaller than the 33 rows. Pinned by
#: hand: a parser that silently dropped a row would otherwise shrink the palette and still pass.
_SECTION_ROWS = 33
_DISTINCT_VALUES = 32

#: Journey property -> the §16.5 row it takes. Status rows are named `<state>-ink|fill|border`.
_ROLES = {
    "--paper": "surface-canvas",
    "--surface": "surface-card",
    "--ink": "ink",
    "--muted": "ink-muted",
    "--line": "border-strong",
    "--accent": "gold-ink",
    "--accent-dark": "gold-ink",
    "--focus": "gold-ink",
    "--danger": "error-ink",
    "--journey-danger-surface": "error-fill",
    "--journey-danger-border": "error-border",
    "--journey-line-subtle": "border-inner",
    "--journey-sunken": "surface-sand",
    "--journey-accent-surface": "gold-tint",
    "--journey-ink-secondary": "ink-secondary",
}

#: Ink/ground pairs the rules draw, with the floor each must clear (4.5 text, 3.0 non-text).
_PAIRS = (
    ("--ink", "--paper", 4.5),
    ("--ink", "--surface", 4.5),
    ("--muted", "--paper", 4.5),
    ("--muted", "--surface", 4.5),
    ("--accent", "--paper", 4.5),
    ("--accent", "--surface", 4.5),
    ("--surface", "--accent-dark", 4.5),
    ("--danger", "--journey-danger-surface", 4.5),
    ("--danger", "--surface", 3.0),
    ("--focus", "--paper", 3.0),
    ("--focus", "--surface", 3.0),
    ("--journey-ink-secondary", "--surface", 3.0),
    ("--accent-dark", "--line", 3.0),
)

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_FUNCTIONAL = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", re.IGNORECASE)
_COLOUR_DECLARATION = re.compile(
    r"(?<![\w-])((?:background|border|outline|accent|caret|fill|stroke|color|box-shadow"
    r"|text-shadow|text-decoration-color)[\w-]*)\s*:\s*([^;}]+)"
)
#: Non-colour words a colour-bearing shorthand may carry, and the colour keywords that name no hue.
_ADMITTED_WORDS = frozenset(
    {
        "transparent",
        "currentcolor",
        "inherit",
        "initial",
        "unset",
        "none",
        "solid",
        "dashed",
        "dotted",
        "double",
        "collapse",
        "separate",
        "auto",
        "light",
    }
)

_STEPS = ("upload", "review", "processing", "report")
_TARGETS = "button:visible, .language-link:visible, .step-nav a:visible"


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _journey() -> str:
    return _strip_comments(_JOURNEY_CSS.read_text(encoding="utf-8"))


def _palette_section() -> str:
    text = _MASTER_SPEC.read_text(encoding="utf-8")
    start = text.index("### 16.5 The approved palette")
    return text[start : text.index("\n## 17.", start)]


def _palette_rows() -> dict[str, str]:
    section = _palette_section()
    rows = {
        name: value.lower()
        for name, value in re.findall(r"`([a-z0-9-]+) (#[0-9A-Fa-f]{6})`", section)
    }
    hexes = r"`(#[0-9A-Fa-f]{6})` /\s*`(#[0-9A-Fa-f]{6})` /\s*`(#[0-9A-Fa-f]{6})`"
    triplets = re.findall(rf"(success|warning|error) {hexes}", section)
    for state, ink, fill, border in triplets:
        rows |= {
            f"{state}-ink": ink.lower(),
            f"{state}-fill": fill.lower(),
            f"{state}-border": border.lower(),
        }
    return rows


def _root_tokens(css: str) -> dict[str, str]:
    root = css[css.index(":root") : css.index("}", css.index(":root"))]
    return {
        name: value.lower()
        for name, value in re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", root)
    }


def _below_root(css: str) -> str:
    return css[css.index("}", css.index(":root")) :]


def _unlisted_hexes(css: str, palette: set[str]) -> set[str]:
    return {value.lower() for value in _HEX.findall(css)} - palette


def _non_token_colours(css: str) -> list[str]:
    """Colour declarations below `:root` that carry anything but a `var()` or an admitted word."""
    found = []
    for prop, value in _COLOUR_DECLARATION.findall(_below_root(css)):
        bare = re.sub(r"var\([^)]*\)", "", value)
        words = set(re.findall(r"[a-zA-Z][\w-]*", bare)) - {"px", "rem", "em"}
        if (
            _HEX.search(bare)
            or _FUNCTIONAL.search(bare)
            or {w.lower() for w in words} - _ADMITTED_WORDS
        ):
            found.append(f"{prop}: {value.strip()}")
    return found


def _luminance(value: str) -> float:
    channels = (int(value[index : index + 2], 16) / 255 for index in (1, 3, 5))
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# --- the independent source ---------------------------------------------------------------------


def test_the_palette_parser_reads_every_row_of_the_section() -> None:
    rows = _palette_rows()

    assert len(rows) == _SECTION_ROWS
    assert len(set(rows.values())) == _DISTINCT_VALUES
    assert rows["warning-ink"] == rows["gold-ink"] == "#7a5a17"


# --- FR-220: values are §16.5's exactly ---------------------------------------------------------


def test_every_journey_colour_is_a_palette_value() -> None:
    unlisted = _unlisted_hexes(_journey(), set(_palette_rows().values()))

    assert not unlisted, f"journey.css declares {sorted(unlisted)}, which §16.5 does not list"


def test_an_unlisted_colour_still_fails_the_palette_check() -> None:
    injected = _journey() + "\n.probe { color: #abcdef; }"

    assert "#abcdef" in _unlisted_hexes(injected, set(_palette_rows().values()))


def test_rules_consume_tokens_and_carry_no_colour_of_their_own() -> None:
    assert _non_token_colours(_journey()) == []


def test_no_functional_colour_anywhere_in_the_stylesheet() -> None:
    """Scanned over the whole sheet, `:root` included, not a list of property names: a guard
    that names its own scope misses the `rgba()` shadow or wash the handoff writes."""
    assert _FUNCTIONAL.findall(_journey()) == []


@pytest.mark.parametrize(
    "probe",
    (
        ":root { --journey-wash: rgba(0, 0, 0, .5); }",
        ".probe { box-shadow: 0 1px 2px rgb(0 0 0); }",
    ),
)
def test_a_functional_colour_is_seen_wherever_it_is_declared(probe: str) -> None:
    assert _FUNCTIONAL.findall(f"{_journey()}\n{probe}")


@pytest.mark.parametrize(
    "probe",
    (
        "color: #7a5a17",
        "background: rgb(0 0 0)",
        "border: 1px solid navy",
        "box-shadow: 0 1px 2px black",
    ),
)
def test_a_literal_colour_below_root_is_seen(probe: str) -> None:
    assert _non_token_colours(_journey() + f"\n.probe {{ {probe}; }}")


@pytest.mark.parametrize(("token", "row"), sorted(_ROLES.items()))
def test_each_journey_property_takes_its_palette_row(token: str, row: str) -> None:
    assert _root_tokens(_journey()).get(token) == _palette_rows()[row]


def test_every_declared_colour_property_has_a_role() -> None:
    """An extent assertion: a colour token added to `:root` without a role row fails here."""
    assert set(_root_tokens(_journey())) == set(_ROLES)


def test_every_colour_property_is_consumed_by_a_rule() -> None:
    below = _below_root(_journey())

    unconsumed = {token for token in _ROLES if f"var({token})" not in below}
    assert not unconsumed, f"{sorted(unconsumed)} are declared and never consumed"


# --- contrast, computed ------------------------------------------------------------------------


@pytest.mark.parametrize(("ink", "ground", "floor"), _PAIRS)
def test_each_drawn_pair_clears_its_floor(ink: str, ground: str, floor: float) -> None:
    tokens = _root_tokens(_journey())

    assert _contrast(tokens[ink], tokens[ground]) >= floor


#: Every visible element that owns a text node, with its colour and nearest opaque background.
_TEXT_CONTRAST_SCRIPT = """
() => {
  const rgb = (value) => (value.match(/[\\d.]+/g) || []).map(Number);
  const luminance = ([r, g, b]) => {
    const lin = [r, g, b].map((c) => c / 255)
      .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
  };
  const ground = (element) => {
    for (let node = element; node; node = node.parentElement) {
      const parts = rgb(getComputedStyle(node).backgroundColor);
      if (parts.length === 3 || (parts.length === 4 && parts[3] === 1)) return parts.slice(0, 3);
    }
    return [255, 255, 255];
  };
  const failures = [];
  let measured = 0;
  for (const element of document.body.querySelectorAll("*")) {
    const owns = [...element.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!owns || element.closest(".visually-hidden, .skip-link")) continue;
    if (element.matches(":disabled")) continue;
    if (!element.getClientRects().length) continue;
    const style = getComputedStyle(element);
    const size = parseFloat(style.fontSize);
    const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700);
    const [a, b] = [luminance(rgb(style.color)), luminance(ground(element))].sort((x, y) => y - x);
    const ratio = (a + 0.05) / (b + 0.05);
    measured += 1;
    const name = `${element.tagName}.${element.getAttribute("class") || ""}`;
    if (ratio < (large ? 3 : 4.5)) failures.push(`${name}: ${ratio.toFixed(2)}`);
  }
  return { measured, failures };
}
"""


#: Tabs through the page; each stop must paint an outline that clears 3:1 on its ground.
#:
#: A native `type="date"` input is exempt, by name: Tab lands on a date segment inside its
#: shadow tree, Chromium highlights that segment, and `:focus-visible` never matches the host,
#: so no journey rule can paint it. That predates this slice and is recorded in its PR.
_FOCUS_SCRIPT = """
(stops) => {
  const rgb = (value) => (value.match(/[\d.]+/g) || []).map(Number);
  const luminance = ([r, g, b]) => {
    const lin = [r, g, b].map((c) => c / 255)
      .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
  };
  const ground = (element) => {
    for (let node = element; node; node = node.parentElement) {
      const parts = rgb(getComputedStyle(node).backgroundColor);
      if (parts.length === 3 || (parts.length === 4 && parts[3] === 1)) return parts.slice(0, 3);
    }
    return [255, 255, 255];
  };
  const element = document.activeElement;
  if (element.matches('input[type="date"]')) return "";
  const style = getComputedStyle(element);
  if (style.outlineStyle === "none" || parseFloat(style.outlineWidth) === 0) {
    return `${element.tagName}: no outline`;
  }
  const [a, b] = [luminance(rgb(style.outlineColor)), luminance(ground(element.parentElement))]
    .sort((x, y) => y - x);
  const ratio = (a + 0.05) / (b + 0.05);
  return ratio < 3 ? `${element.tagName}: ${ratio.toFixed(2)}` : "";
}
"""


def _focus_failures(page, stops: int) -> list[str]:
    failures = []
    for _ in range(stops):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement === document.body"):
            break
        failures.append(page.evaluate(_FOCUS_SCRIPT, stops))
    return [failure for failure in failures if failure]


@pytest.mark.browser
@pytest.mark.parametrize("language", ["en", "ar"])
def test_every_tab_stop_paints_a_focus_ring_that_clears_three_to_one(language: str) -> None:
    css = _JOURNEY_CSS.read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            for step in _STEPS:
                page.set_content(client().get(f"/beta/{language}/{step}").text)
                page.add_style_tag(content=css)
                assert _focus_failures(page, 40) == [], step
            page.add_style_tag(content=":focus-visible { outline-color: #e9e3da !important; }")
            page.evaluate("document.activeElement.blur()")
            assert _focus_failures(page, 3), "the focus measure cannot fail"
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("viewport", [(1440, 900), (1024, 768), (390, 844)])
@pytest.mark.parametrize("language", ["en", "ar"])
def test_journey_text_clears_contrast_and_fits_the_viewport(
    viewport: tuple[int, int], language: str
) -> None:
    css = _JOURNEY_CSS.read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            for step in _STEPS:
                page.set_content(client().get(f"/beta/{language}/{step}").text)
                page.add_style_tag(content=css)
                result = page.evaluate(_TEXT_CONTRAST_SCRIPT)
                assert result["measured"] > 0, f"{step}: no text measured, so this proves nothing"
                assert result["failures"] == [], f"{step}: {result['failures']}"
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), step
                for target in page.locator(_TARGETS).all():
                    box = target.bounding_box()
                    assert box is not None and box["height"] >= 44, step
            page.add_style_tag(content=".lede { color: #c9a45c !important; }")
            assert page.evaluate(_TEXT_CONTRAST_SCRIPT)["failures"], "the measure cannot fail"
        finally:
            browser.close()
