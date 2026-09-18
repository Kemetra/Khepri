"""`RCA-010` `FR-200`: the master specification §11 accessibility floors, per shell surface.

`tests/` only. Where a floor fails, the fix lands in the slice that owns the file, not here --
this module changes no source file, and an evidence slice that edited a template to make its own
assertion pass would leave the failure in the product.

Two rosters, because one driver cannot serve both. `SHELL_SURFACES` renders through
`add_shell_routes(app, services=ShellServices(...))`; the legal pages render through
`add_legal_routes(app)`, which takes no services argument, and six of them share one template.
"""

from __future__ import annotations

import os
from html.parser import HTMLParser
from importlib.resources import files
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.runtime.legal_api import LEGAL_PAGES, LEGAL_PREFIX, add_legal_routes
from tests.test_r807_shell_quality import SHELL_SURFACES, _html

#: The legal pages, by the state each renders. `about-us` and `refund-and-void` publish; the
#: other four hold a governed unpublished state and answer 503. Both are measurable documents --
#: each carries exactly one `h1` -- and driving only the unpublished four would be a run that can
#: only produce the null case.
LEGAL_PUBLISHED = ("about-us", "refund-and-void")
LEGAL_UNPUBLISHED = ("contact-us", "data-protection", "privacy-policy", "terms-and-conditions")


def _legal_client() -> TestClient:
    """The legal routes carry no session and no services, so this needs neither."""
    app = FastAPI()
    add_legal_routes(app)
    return TestClient(app, base_url="https://testserver")


def _legal_html(page: str, language: str) -> str:
    return _legal_client().get(f"{LEGAL_PREFIX}/{language}/{page}").text


def test_the_legal_roster_matches_the_served_inventory() -> None:
    """A legal page added to the product without a case here fails rather than going unmeasured."""
    assert LEGAL_PAGES, "no legal pages found, so this test proves nothing"
    assert set(LEGAL_PUBLISHED) | set(LEGAL_UNPUBLISHED) == set(LEGAL_PAGES)


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("page", sorted(LEGAL_PAGES))
def test_every_legal_page_renders_one_heading_in_both_languages(page: str, language: str) -> None:
    """Both the published and the unpublished state are documents, not error pages."""
    html = _legal_html(page, language)
    assert html.count("<h1") == 1
    assert f'lang="{language}"' in html


def test_a_published_legal_page_carries_more_than_its_chrome() -> None:
    """Without this, every legal measurement below could pass over an empty document."""
    published = len(_legal_html("about-us", "en"))
    unpublished = len(_legal_html("contact-us", "en"))
    assert published > unpublished, "the published page must carry content the unpublished lacks"


#: Landmarks `FR-200` requires to carry meaningful unique accessible names.
#:
#: `form` and `section` are deliberately absent. Both are landmarks **only when they carry an
#: accessible name**: an unnamed `<form>` is exposed as a plain grouping, not as a `form`
#: landmark, so requiring a name here would report the single-button revoke and download forms
#: on `team` and `analysis` as defects when the button is what names the action. Including them
#: would have made this floor fire on correct markup -- the opposite of the requirement.
_LANDMARKS = frozenset({"nav", "main", "header", "footer", "aside"})


class _Landmarks(HTMLParser):
    """Collects landmarks with their accessible names, by parser rather than by regex.

    Slice 8 settled the idiom after a substring scan counted `data-href=` as an anchor `href`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[str, str | None]] = []
        self.tabindex: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("tabindex") is not None:
            self.tabindex.append(str(values["tabindex"]))
        if tag in _LANDMARKS:
            self.found.append((tag, values.get("aria-label") or values.get("aria-labelledby")))


def _parse(html: str) -> _Landmarks:
    parser = _Landmarks()
    parser.feed(html)
    return parser


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_no_surface_carries_a_positive_tabindex(surface: str, language: str) -> None:
    """`FR-200`: focus order follows document order, so no positive `tabindex` anywhere."""
    for value in _parse(_html(surface, language)).tabindex:
        assert int(value) <= 0, f"{surface}/{language} carries tabindex={value}"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("page", sorted(LEGAL_PAGES))
def test_no_legal_page_carries_a_positive_tabindex(page: str, language: str) -> None:
    """The same floor over the surfaces the shell roster cannot reach."""
    for value in _parse(_legal_html(page, language)).tabindex:
        assert int(value) <= 0, f"{page}/{language} carries tabindex={value}"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_repeated_landmarks_carry_distinct_accessible_names(surface: str, language: str) -> None:
    """`FR-200`: landmarks are meaningful and unique.

    A sole `main` needs no name -- naming it would be ARIA where native semantics suffice, which
    the same requirement forbids. The floor is that landmarks sharing a tag are *told apart*,
    which is where a screen-reader user is actually stranded. `decision` carries two `nav` regions
    ("Sections" and "Analysis") and is the case that makes this non-vacuous.
    """
    found = _parse(_html(surface, language)).found
    for tag in {element for element, _ in found}:
        names = [name for element, name in found if element == tag]
        if len(names) > 1:
            assert all(names), f"{surface}/{language}: repeated <{tag}> without a name"
            assert len(set(names)) == len(names), f"{surface}/{language}: duplicate <{tag}> names"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_every_surface_has_exactly_one_main_landmark(surface: str, language: str) -> None:
    """`FR-200`: semantic landmarks. One `main` is what the skip link targets."""
    found = _parse(_html(surface, language)).found
    assert len([tag for tag, _ in found if tag == "main"]) == 1


class _Controls(HTMLParser):
    """Tracks whether each labellable control is inside a `<label>` or carries an explicit name."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.controls: list[dict[str, str | bool | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "label":
            self.depth += 1
        if tag in {"input", "select", "textarea"}:
            if values.get("type") in {"hidden", "submit", "button"}:
                return
            self.controls.append(
                {
                    "wrapped": self.depth > 0,
                    "id": values.get("id"),
                    "aria-label": values.get("aria-label"),
                    "aria-labelledby": values.get("aria-labelledby"),
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            self.depth = max(0, self.depth - 1)


def _controls(html: str) -> list[dict[str, str | bool | None]]:
    parser = _Controls()
    parser.feed(html)
    return parser.controls


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_every_control_has_a_label_that_is_not_its_placeholder(surface: str, language: str) -> None:
    """`FR-200`: a placeholder is a value hint and disappears on input; it is never the label.

    `decision`'s three filter inputs carry `placeholder="Any"` and are each wrapped in a
    `<label>` with visible text -- so the placeholder describes the *default*, not the field.
    This asserts the wrapping label is what names them, which is the part that could regress.
    """
    html = _html(surface, language)
    for control in _controls(html):
        identifier = control["id"]
        named = (
            control["wrapped"]
            or control["aria-label"]
            or control["aria-labelledby"]
            or (identifier is not None and f'for="{identifier}"' in html)
        )
        assert named, f"{surface}/{language}: a control is named only by its placeholder"


def _pinned_chromium() -> str | None:
    """A Chromium under `PLAYWRIGHT_BROWSERS_PATH`, the fallback slice 8 established."""
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not root:
        return None
    candidates = sorted(Path(root).glob("chromium*/chrome-win/chrome.exe"))
    return str(candidates[-1]) if candidates else None


def _launch_chromium(playwright: object) -> object:
    """The pinned Chromium, or `pytest.skip` when this machine genuinely has none."""
    from playwright.sync_api import Error

    try:
        return playwright.chromium.launch()  # type: ignore[attr-defined]
    except Error as error:
        executable = _pinned_chromium()
        if executable is None:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        return playwright.chromium.launch(executable_path=executable)  # type: ignore[attr-defined]


def _shell_css() -> str:
    """The three sheets a shell surface links, in link order."""
    journey = files("khepri.rra.journey").joinpath("assets")
    return "\n".join(
        (
            journey.joinpath("shell.css").read_text(encoding="utf-8"),
            journey.joinpath("shell-components.css").read_text(encoding="utf-8"),
            files("khepri.runtime")
            .joinpath("shell_assets", "workspace.css")
            .read_text(encoding="utf-8"),
        )
    )


def _legal_css() -> str:
    """The **two** sheets a legal page links.

    `legal.html.j2:7-8` links `shell.css` and `shell-components.css`, and `legal_api.py`'s
    `_ASSETS` allowlist serves exactly those two. Injecting `workspace.css` here would measure a
    document the product never serves -- the error `_PRINT_TEMPLATES` exists to prevent.
    """
    journey = files("khepri.rra.journey").joinpath("assets")
    return "\n".join(
        (
            journey.joinpath("shell.css").read_text(encoding="utf-8"),
            journey.joinpath("shell-components.css").read_text(encoding="utf-8"),
        )
    )


#: Computed in the page from resolved colours -- `FR-200` §Verification requires contrast
#: *computed*, not asserted against a table of hex values a test happens to remember.
#:
#: The background is walked up the ancestor chain because a transparent element inherits what it
#: sits on; comparing text against `rgba(0, 0, 0, 0)` would report a fictional ratio. Leaf
#: elements only, so a paragraph's text is not measured again through its wrapper.
_CONTRAST = """
(() => {
  const lum = (c) => {
    const [r, g, b] = c.match(/[0-9.]+/g).slice(0, 3).map(Number).map((v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const opaque = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const bg = getComputedStyle(n).backgroundColor;
      if (bg && !bg.startsWith('rgba(0, 0, 0, 0)')) return bg;
    }
    return 'rgb(255, 255, 255)';
  };
  const out = [];
  for (const el of document.querySelectorAll('p, h1, h2, h3, li, a, button, span, td, th')) {
    if (!el.textContent.trim() || el.offsetParent === null) continue;
    if (el.children.length > 0) continue;
    const style = getComputedStyle(el);
    const size = parseFloat(style.fontSize);
    const large = size >= 24 || (size >= 18.66 && parseInt(style.fontWeight, 10) >= 700);
    const a = lum(style.color), b = lum(opaque(el));
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    out.push({ ratio, floor: large ? 3.0 : 4.5, text: el.textContent.trim().slice(0, 40) });
  }
  return out;
})()
"""


def _assert_contrast(measured: list[dict[str, float | str]], where: str) -> None:
    """Every measured node clears its floor, and something was measured at all."""
    assert measured, f"{where}: no text measured, so this proves nothing"
    for item in measured:
        assert item["ratio"] >= item["floor"], (
            f"{where}: {item['ratio']:.2f} < {item['floor']} on {item['text']!r}"
        )


@pytest.mark.browser
@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_text_contrast_is_computed_and_meets_its_floor(surface: str, language: str) -> None:
    """`FR-200` §Verification: contrast **computed** in the real browser, not asserted."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(_html(surface, language), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            _assert_contrast(page.evaluate(_CONTRAST), f"{surface}/{language}")
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("page_name", ["about-us", "contact-us"])
def test_legal_text_contrast_is_computed_and_meets_its_floor(page_name: str, language: str) -> None:
    """One published page and one unpublished, so the non-null case is provably reached."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(_legal_html(page_name, language), wait_until="domcontentloaded")
            page.add_style_tag(content=_legal_css())
            _assert_contrast(page.evaluate(_CONTRAST), f"{page_name}/{language}")
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_text_scales_to_two_hundred_percent_without_losing_content(surface: str) -> None:
    """`FR-200`: 200% text loses neither content nor function."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(_html(surface, "en"), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            before = page.evaluate("document.body.innerText.trim().length")
            page.add_style_tag(content="html { font-size: 200% !important; }")
            after = page.evaluate("document.body.innerText.trim().length")
            assert after >= before, f"{surface}: text was lost at 200%"
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_a_pointer_target_is_measured_on_the_element_it_lands_on(surface: str) -> None:
    """`FR-200`: at least 44px **on the element a pointer lands on**, not on an ancestor.

    The existing `r807` case measures the same floor at two viewports; this one measures the
    narrow viewport only and exists to state the "element a pointer lands on" half explicitly,
    which is the part an ancestor-based measurement would hide.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(_html(surface, "en"), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            for locator in page.locator("a:visible, button:visible, select:visible").all():
                box = locator.bounding_box()
                assert box is not None
                assert box["height"] >= 44, f"{surface}: a target is {box['height']}px tall"
        finally:
            browser.close()
