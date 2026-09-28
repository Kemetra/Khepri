"""`RRA-016` `FR-223`–`FR-226`: the journey takes the handoff's composition, and adds nothing.

The palette values are `test_rra016_journey_palette.py`'s. This module pins where they land and
what the composition may not do: the navy is the header's alone, the header carries only what the
journey already rendered, every property a rule reads is declared in the journey's own sheet, the
upload declarations sit side by side where the width allows without changing source order, and
text scales to 200% without widening the page.

The populated-state checks drive the real pages and their real modules through
`tests.journey_routed_page`, because a `set_content` page runs no module, so its review table,
refusal and failed-processing states never render and a check over them measures nothing.
"""

from __future__ import annotations

import re
from importlib.resources import files
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Error, Page, sync_playwright

from khepri.rra.journey.copy import JOURNEY_COPY
from tests.journey_routed_page import open_journey_page
from tests.test_rra016_journey_palette import _TEXT_CONTRAST_SCRIPT, _focus_failures, _palette_rows
from tests.test_rra_journey_api import client

_ROOT = Path(__file__).resolve().parents[1]
_JOURNEY = files("khepri.rra.journey")
_SHELL_SHEETS = (
    _ROOT / "src" / "khepri" / "rra" / "journey" / "assets" / "shell-components.css",
    _ROOT / "src" / "khepri" / "runtime" / "shell_assets" / "workspace.css",
)
_LANGUAGES = ("en", "ar")
_STEPS = ("upload", "review", "processing", "report")
_VIEWPORTS = ((1440, 900), (1024, 768), (390, 844))
_TARGETS = "button:visible, .language-link:visible, .step-nav a:visible"

#: Classes this slice introduced. Each must be rendered, and none may be a shell class (`FR-222`).
_SLICE_CLASSES = ("upload-form",)

_MAPPINGS = [
    {
        "semantic": "transaction_date",
        "state": "mapped",
        "requirement": "required",
        "candidates": [{"safe_label": "order_date", "evidence": ["label_exact", "type_confirmed"]}],
    },
    {
        "semantic": "revenue",
        "state": "mapped",
        "requirement": "required",
        "candidates": [{"safe_label": "net_sales_egp", "evidence": ["label_token"]}],
    },
    {
        "semantic": "units",
        "state": "ambiguous",
        "requirement": "optional",
        "candidates": [{"safe_label": "qty", "evidence": ["label_substring"]}],
    },
    {"semantic": "store", "state": "unavailable", "requirement": "optional", "candidates": []},
]


def _profile(admissible: bool) -> tuple[int, object]:
    refused = not admissible
    return 200, {
        "mappings": _MAPPINGS,
        "admissible": admissible,
        "reasons": ["no_answerable_core_measure"] if refused else [],
        "findings": ["duplicate_safe_labels"] if refused else [],
    }


_PROCESSING = {"step": "processing", "job_id": "j1", "package_present": True}
_REPORT = {
    "step": "report",
    "bundle_complete": True,
    "job_id": "j1",
    "row_count": 12480,
    "generated_at": "2026-09-28T09:00:00Z",
    "content_expires_at": "2026-10-05T09:00:00Z",
}

#: `(address, journey response, profile response)` for each state a reader can arrive at, the
#: refusal, failure, recovery and terminal states included. A response is `(status, body)`.
_STATES = {
    "upload": ("upload", (200, {"step": "upload"}), None),
    # The upload is stored and its declaration refused: the file control locks, the kept notice
    # shows, and the server's stated reason is shown with the recovery action (`#587`).
    "upload-kept-refused": (
        "upload",
        (200, {"step": "upload", "upload_present": True, "profile_present": False}),
        (400, {"detail": "A declared currency must be one uppercase ISO 4217 code."}),
    ),
    "upload-unavailable": ("upload", (503, None), None),
    "review-mapped": ("review", (200, {"step": "review"}), _profile(True)),
    "review-refused": ("review", (200, {"step": "review"}), _profile(False)),
    "processing-running": ("processing", (200, {**_PROCESSING, "job_state": "running"}), None),
    "processing-failed": (
        "processing",
        (200, {**_PROCESSING, "job_state": "dead_lettered"}),
        None,
    ),
    "report-ready": ("report", (200, _REPORT), None),
    "expired": ("expired", (401, None), None),
    "expired-deletion": ("expired?deletion=requested", (401, None), None),
}

#: The selector each state must show, so a state that never rendered cannot pass. Each one names
#: something the step's module creates or reveals, never markup present on first paint: the
#: recovery button renders visible, so the failed state waits for the bar the module hides.
_RENDERED = {
    "upload": "#upload-form",
    "upload-kept-refused": "#upload-kept:not([hidden]) ~ #upload-recovery:not([hidden])",
    "upload-unavailable": "#error-summary:not([hidden])",
    "review-mapped": "#mapping-table tbody tr",
    "review-refused": "#profile-findings:not([hidden]) li",
    "processing-running": "#processing-status:not(:empty)",
    "processing-failed": ".indeterminate[hidden] ~ #processing-recovery",
    "report-ready": "#report-links:not([hidden]) .report-card",
    "expired": "#page-title",
    "expired-deletion": "#page-title",
}

#: Every element whose computed background is one of the given colours, as `tag.class`.
_PAINTED_SCRIPT = """
(colours) => [...document.querySelectorAll("body *")]
  .filter((element) => colours.includes(getComputedStyle(element).backgroundColor))
  .map((element) => `${element.tagName.toLowerCase()}.${element.getAttribute("class") || ""}`)
"""

#: Elements that clip their own content horizontally, other than the ones built to.
_CLIPPED_SCRIPT = """
() => [...document.querySelectorAll("body *")]
  .filter((element) => !element.closest(".visually-hidden, .table-region, .indeterminate"))
  .filter((element) => ["hidden", "clip"].includes(getComputedStyle(element).overflowX))
  .filter((element) => element.scrollWidth > element.clientWidth + 1)
  .map((element) => `${element.tagName.toLowerCase()}.${element.getAttribute("class") || ""}`)
"""

#: Elements whose content runs past their own box while nothing clips it. The page-level width
#: check only fails once a spill also clears the page's inline padding, which is a margin of a few
#: pixels that font metrics decide: at 200% text on 390 the stepper and two date rows spilled 30px
#: on Windows unseen and overflowed the page on Linux CI. This fails on either.
_SPILL_SCRIPT = """
() => [...document.querySelectorAll("body *")]
  .filter((element) => !element.closest(".visually-hidden, .table-region"))
  .filter((element) => getComputedStyle(element).overflowX === "visible")
  .filter((element) => element.clientWidth > 0 && element.scrollWidth > element.clientWidth + 1)
  .map((element) => `${element.tagName.toLowerCase()}#${element.id}`
    + `.${element.getAttribute("class") || ""}`
    + ` ${element.scrollWidth}/${element.clientWidth}`)
"""


def _css() -> str:
    text = _JOURNEY.joinpath("assets", "journey.css").read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _rgb(hex_value: str) -> str:
    red, green, blue = (int(hex_value[index : index + 2], 16) for index in (1, 3, 5))
    return f"rgb({red}, {green}, {blue})"


def _consumed(css: str) -> set[str]:
    return set(re.findall(r"var\((--[\w-]+)", css))


def _declared(css: str) -> set[str]:
    return set(re.findall(r"(--[\w-]+)\s*:", css))


def _controls(header: str) -> list[str]:
    """Every interactive element's opening, with its class when it carries one."""
    return re.findall(r'<(?:a|button|input|select|textarea)\b(?:\s+class="[^"]*")?', header)


def _asymmetric_shorthands(css: str) -> list[str]:
    found = []
    for prop, value in re.findall(r"(?<![\w-])(padding|margin)\s*:\s*([^;}]+)", css):
        parts = re.findall(r"[\w.%-]+\([^)]*\)|\S+", value.strip())
        if len(parts) == 4 and parts[1] != parts[3]:
            found.append(f"{prop}: {value.strip()}")
    return found


def _shell_classes() -> set[str]:
    return {
        name
        for sheet in _SHELL_SHEETS
        for name in re.findall(r"\.([a-zA-Z][\w-]*)", sheet.read_text(encoding="utf-8"))
    }


def _launch(playwright) -> Browser:
    try:
        return playwright.chromium.launch()
    except Error as error:  # pragma: no cover - depends on the environment
        pytest.skip(f"Pinned Chromium is unavailable: {error}")


def _served_page(browser: Browser, language: str, step: str, viewport: tuple[int, int]) -> Page:
    """The served page on an HTTP origin, so the vendored typeface loads and metrics are real."""
    page, _ = open_journey_page(
        browser, language=language, step=step, api=_stub((200, {"step": step}))
    )
    page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
    page.evaluate("document.fonts.ready")
    return page


def _stub(journey: tuple[int, object], profile: tuple[int, object] | None = None):
    def api(method: str, path: str) -> tuple[int, object]:
        if path == "/api/v1/beta/journey":
            return journey
        if path == "/api/v1/beta/profile" and profile is not None:
            return profile
        return 200, {}

    return api


def _populated_page(browser: Browser, language: str, name: str, width: int) -> Page:
    step, journey, profile = _STATES[name]
    page, _ = open_journey_page(browser, language=language, step=step, api=_stub(journey, profile))
    page.set_viewport_size({"width": width, "height": 900})
    page.wait_for_selector(_RENDERED[name], state="attached")
    page.evaluate("document.fonts.ready")
    return page


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_deletion_variant_of_the_terminal_page_is_the_one_rendered(language: str) -> None:
    """The matrix's `expired-deletion` row measures the deletion page, not the expiry page."""
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            copy = JOURNEY_COPY[language]
            for name, title in (
                ("expired", copy["expired_title"]),
                ("expired-deletion", copy["deletion_requested_title"]),
            ):
                page = _populated_page(browser, language, name, 1440)
                assert page.inner_text("#page-title") == title, name
                page.close()
        finally:
            browser.close()


def test_the_typeface_is_served_to_the_routed_pages() -> None:
    """The browser checks below read real metrics only if the face they name is served."""
    for face in ("NotoSansArabic-Regular-arabic.woff2", "NotoSansArabic-Regular-latin.woff2"):
        response = client().get(f"/beta/assets/{face}")
        assert response.status_code == 200 and response.headers["content-type"] == "font/woff2"


def _layout_failures(page: Page) -> list[str]:
    failures = []
    if not page.evaluate("[...document.fonts].some((face) => face.status === 'loaded')"):
        failures.append("the vendored typeface did not load, so metrics are a fallback's")
    contrast = page.evaluate(_TEXT_CONTRAST_SCRIPT)
    if not contrast["measured"]:
        failures.append("no text measured")
    failures += contrast["failures"]
    if not page.evaluate("document.documentElement.scrollWidth <= innerWidth"):
        failures.append("page overflows horizontally")
    for target in page.locator(_TARGETS).all():
        box = target.bounding_box()
        if box is None or box["height"] < 44:
            failures.append(f"target under 44px: {target.inner_text()!r}")
    return failures


# --- FR-222: nothing the shell owns ---------------------------------------------------------------


def test_every_property_a_rule_reads_is_declared_in_the_journey_sheet() -> None:
    """No `var()` can resolve to a shell declaration, because every one resolves here."""
    css = _css()

    assert _consumed(css), "no custom property is consumed, so this proves nothing"
    assert _consumed(css) <= _declared(css), sorted(_consumed(css) - _declared(css))


def test_an_undeclared_property_is_seen() -> None:
    probe = _css() + "\n.probe { color: var(--gold-500); }"

    assert "--gold-500" in _consumed(probe) - _declared(probe)


@pytest.mark.parametrize("name", _SLICE_CLASSES)
def test_the_slice_classes_are_rendered_and_none_is_a_shell_class(name: str) -> None:
    shell = _shell_classes()

    assert {"app-frame", "app-rail", "page-head"} <= shell, "the shell class census read nothing"
    assert name not in shell
    assert re.search(rf'class="[^"]*\b{name}\b', client().get("/beta/en/upload").text)


# --- FR-223: the header adds nothing ---------------------------------------------------------


@pytest.mark.parametrize("language", _LANGUAGES)
@pytest.mark.parametrize("step", _STEPS)
def test_the_header_holds_only_the_wordmark_and_the_language_control(
    language: str, step: str
) -> None:
    body = client().get(f"/beta/{language}/{step}").text
    header = re.search(r'<header class="site-header">.*?</header>', body, re.DOTALL).group(0)

    assert _controls(header) == ['<a class="brand"', '<a class="language-link"']


def test_a_control_without_a_class_is_still_seen_in_the_header() -> None:
    assert _controls('<header><a class="brand"><button type="button">') == [
        '<a class="brand"',
        "<button",
    ]


# --- FR-226: right-to-left needs logical properties, shorthands included ------------------------


def test_no_four_value_box_shorthand_is_asymmetric_across_the_inline_axis() -> None:
    """`padding: a b c d` is physical: `b` is the right and `d` the left in either direction.

    `RRA-010`'s physical-property scan names longhands such as `padding-left`, so it cannot see
    a shorthand that sets the two sides differently and mirrors wrongly under right-to-left."""
    assert _asymmetric_shorthands(_css()) == []


def test_an_asymmetric_shorthand_is_seen() -> None:
    probe = _css() + "\n.probe { padding: .35rem 1.5rem .35rem 3rem; }"

    assert _asymmetric_shorthands(probe) == ["padding: .35rem 1.5rem .35rem 3rem"]


# --- FR-220, FR-223, FR-226: in a real browser ----------------------------------------------


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_navy_paints_the_header_and_nothing_else(language: str) -> None:
    rows = _palette_rows()
    navy = [_rgb(rows["navy-900"]), _rgb(rows["navy-950"])]
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for step in _STEPS:
                page = _served_page(browser, language, step, (1440, 900))
                assert page.evaluate(_PAINTED_SCRIPT, navy) == ["header.site-header"], step
                page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_declarations_share_a_row_only_where_the_width_allows(language: str) -> None:
    """Side by side from 900px, the contract first on the reading side; stacked below it.

    Both sides of the `max-width: 899px` breakpoint are measured, not only the supported widths
    either side of it, so a breakpoint that moved would fail here."""
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for viewport in (*_VIEWPORTS, (900, 800), (899, 800)):
                page = _served_page(browser, language, "upload", viewport)
                contract = page.locator("#source-contract").bounding_box()
                manifest = page.locator("#coverage-manifest").bounding_box()
                assert contract is not None and manifest is not None
                if viewport[0] >= 900:
                    assert contract["y"] == manifest["y"], viewport
                    first = contract["x"] < manifest["x"]
                    assert first == (language == "en"), viewport
                else:
                    assert manifest["y"] >= contract["y"] + contract["height"], viewport
                page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", [viewport[0] for viewport in _VIEWPORTS])
@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_populated_state_clears_contrast_targets_and_width(language: str, width: int) -> None:
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for name in _STATES:
                page = _populated_page(browser, language, name, width)
                assert _layout_failures(page) == [], name
                page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("viewport", _VIEWPORTS)
@pytest.mark.parametrize("language", _LANGUAGES)
def test_text_scales_to_two_hundred_percent_without_loss(
    language: str, viewport: tuple[int, int]
) -> None:
    """Every size is `rem`, so doubling the root doubles the text; nothing may widen or clip."""
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for step in _STATES:
                page = _populated_page(browser, language, step, viewport[0])
                base = page.evaluate(
                    "parseFloat(getComputedStyle(document.querySelector('h1')).fontSize)"
                )
                page.add_style_tag(content="html { font-size: 200%; }")
                scaled = page.evaluate(
                    "parseFloat(getComputedStyle(document.querySelector('h1')).fontSize)"
                )
                assert scaled > base * 1.5, f"{step}: the heading did not scale"
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), step
                assert page.evaluate(_CLIPPED_SCRIPT) == [], step
                assert page.evaluate(_SPILL_SCRIPT) == [], step
                page.close()
        finally:
            browser.close()


# --- FR-225, FR-226: motion and focus in every populated state -----------------------------------

#: The indeterminate bar's fill: its animation and how much of the track it covers.
_BAR_SCRIPT = """
() => {
  const fill = document.querySelector(".indeterminate span");
  const track = fill.parentElement.getBoundingClientRect().width;
  const share = fill.getBoundingClientRect().width / track;
  return { animation: getComputedStyle(fill).animationName, share };
}
"""


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_reduced_motion_fills_the_progress_track_rather_than_freezing_it(language: str) -> None:
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            moving = _populated_page(browser, language, "processing-running", 1440)
            assert moving.evaluate(_BAR_SCRIPT)["animation"].startswith("journey-progress"), (
                "the bar does not animate by default, so the reduced case proves nothing"
            )
            moving.close()
            page = _populated_page(browser, language, "processing-running", 1440)
            page.emulate_media(reduced_motion="reduce")
            assert page.evaluate(_BAR_SCRIPT) == {"animation": "none", "share": 1}
            page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", [viewport[0] for viewport in _VIEWPORTS])
@pytest.mark.parametrize("language", _LANGUAGES)
def test_every_tab_stop_in_every_state_shows_its_focus(language: str, width: int) -> None:
    """The palette module measures the four steps at 1440; this covers every state and width."""
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for name in _STATES:
                page = _populated_page(browser, language, name, width)
                assert _focus_failures(page, 60) == [], name
                page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_narrow_stepper_is_one_row_at_normal_text_size(language: str) -> None:
    """The stepper may wrap at 200% text (above); at 100% on 390 its four steps share one row."""
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for step in _STEPS:
                page = _served_page(browser, language, step, (390, 844))
                tops = page.evaluate(
                    "[...document.querySelectorAll('.step-nav li')]"
                    ".map((item) => Math.round(item.getBoundingClientRect().top))"
                )
                assert len(tops) == 4 and len(set(tops)) == 1, (step, tops)
                page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("scale", ["250%", "300%"])
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_header_wraps_rather_than_widening_the_page(language: str, scale: str) -> None:
    """Past the 200% floor the header's two controls take a second row, never the viewport.

    At 220% on 390 the Arabic header ran 9px wide under Linux Chromium while 200% passed, so the
    200% test alone leaves the header's margin to font metrics."""
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            page = _served_page(browser, language, "upload", (390, 844))
            page.add_style_tag(content=f"html {{ font-size: {scale}; }}")
            header = page.evaluate(
                "(() => { const h = document.querySelector('.site-header');"
                " return { right: h.getBoundingClientRect().right,"
                " scroll: h.scrollWidth, box: h.clientWidth }; })()"
            )
            assert header["scroll"] <= header["box"] + 1, header
            assert header["right"] <= 390, header
            page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_header_is_one_row_at_normal_text_size(language: str) -> None:
    """Allowing the header to wrap must not move it at 100%: one row, at the heights `main` had
    before it could wrap (64px, and 60px at 390, both measured)."""
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for width, height in ((1440, 64), (390, 60)):
                page = _served_page(browser, language, "upload", (width, 844))
                brand = page.locator(".site-header .brand").bounding_box()
                switch = page.locator(".site-header .language-link").bounding_box()
                box = page.locator(".site-header").bounding_box()
                assert brand is not None and switch is not None and box is not None
                assert (
                    abs(brand["y"] + brand["height"] / 2 - (switch["y"] + switch["height"] / 2)) < 2
                )
                assert round(box["height"]) == height, (width, box["height"])
                page.close()
        finally:
            browser.close()
