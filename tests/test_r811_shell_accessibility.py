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
import re
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
    """Resolves each labellable control's accessible NAME, not merely its association.

    Association is not a name. A control inside an **empty** `<label>` is associated with nothing
    a person can read, and an `aria-labelledby` naming a missing or empty element resolves to no
    name at all. So this records the text of every open `<label>` and of every element carrying an
    `id`, and the floor below requires the resolved name to be non-empty.
    """

    _LABELLABLE = frozenset({"input", "select", "textarea"})
    _UNLABELLED_TYPES = frozenset({"hidden", "submit", "button"})

    def __init__(self) -> None:
        super().__init__()
        self._labels: list[list[str]] = []
        self._ids: list[tuple[str, list[str]]] = []
        self.controls: list[dict[str, object]] = []
        #: Text by element `id`, so an `aria-labelledby` reference can be resolved.
        self.text_by_id: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if (identifier := values.get("id")) is not None:
            self._ids.append((identifier, []))
        if tag == "label":
            self._labels.append([])
        if tag in self._LABELLABLE and values.get("type") not in self._UNLABELLED_TYPES:
            self.controls.append(
                {
                    # The list object itself, so text appended after this tag still counts.
                    "label_texts": list(self._labels),
                    "aria-label": (values.get("aria-label") or "").strip(),
                    "aria-labelledby": (values.get("aria-labelledby") or "").strip(),
                    "id": values.get("id"),
                }
            )

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        if not (text := data.strip()):
            return
        for bucket in self._labels:
            bucket.append(text)
        for _, bucket in self._ids:
            bucket.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "label" and self._labels:
            self._labels.pop()
        if self._ids:
            identifier, bucket = self._ids.pop()
            self.text_by_id.setdefault(identifier, " ".join(bucket).strip())


def _controls(html: str) -> tuple[list[dict[str, object]], dict[str, str]]:
    parser = _Controls()
    parser.feed(html)
    return parser.controls, parser.text_by_id


def _from_aria_labelledby(control: dict[str, object], text_by_id: dict[str, str], _: str) -> str:
    """Each referenced element's own text. A reference to a missing or empty node names nothing."""
    tokens = str(control["aria-labelledby"]).split()
    return " ".join(text_by_id.get(token, "") for token in tokens).strip()


def _from_wrapping_label(control: dict[str, object], _: dict[str, str], __: str) -> str:
    """The text of every `<label>` open around the control."""
    texts: list[list[str]] = control["label_texts"]  # type: ignore[assignment]
    return " ".join(" ".join(part) for part in texts).strip()


def _from_label_for(control: dict[str, object], _: dict[str, str], html: str) -> str:
    """The text inside `<label for="...">`, which is a sibling rather than an ancestor."""
    if (identifier := control["id"]) is None:
        return ""
    pattern = rf'<label[^>]*for="{re.escape(str(identifier))}"[^>]*>(.*?)</label>'
    match = re.search(pattern, html, re.S)
    return re.sub(r"<[^>]+>", "", match.group(1)).strip() if match else ""


#: The naming mechanisms in ARIA precedence. Each returns the **resolved text**, so a mechanism
#: that is present but resolves to nothing falls through to the next rather than counting as a
#: name -- which is the whole point of the floor.
_NAME_SOURCES = (
    lambda control, _, __: str(control["aria-label"]),
    _from_aria_labelledby,
    _from_wrapping_label,
    _from_label_for,
)


def _accessible_name(control: dict[str, object], text_by_id: dict[str, str], html: str) -> str:
    """The name a screen reader would announce, or `""` when every mechanism resolves empty."""
    for source in _NAME_SOURCES:
        if name := source(control, text_by_id, html):
            return name
    return ""


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_every_control_has_a_label_that_is_not_its_placeholder(surface: str, language: str) -> None:
    """`FR-200`: a placeholder is a value hint and disappears on input; it is never the label.

    `decision`'s three filter inputs carry `placeholder="Any"` and are each wrapped in a
    `<label>` with visible text -- so the placeholder describes the *default*, not the field.

    The floor is the resolved **name**, not the association: a control inside an empty `<label>`,
    or carrying an `aria-labelledby` that resolves to nothing, is named by its placeholder alone
    even though every association check passes.
    """
    html = _html(surface, language)
    controls, text_by_id = _controls(html)
    for control in controls:
        name = _accessible_name(control, text_by_id, html)
        assert name, f"{surface}/{language}: a control resolves to no accessible name"


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


#: The three cases where 200% text overflows the 390px viewport today -- an OPEN `FR-200` finding
#: against `shell-components.css`, recorded rather than fixed.
#:
#: `.shell-main` (`:36`) and `.document-card` (`:68`) keep their padding at 200%, leaving the `h1`
#: a 244px box for a 345px word run. English only: `"Comparison"` is a single unbreakable token,
#: while every Arabic heading has shorter words and passes at the same width. The fix belongs to
#: the slice that owns that sheet -- an evidence slice editing a stylesheet to make its own
#: assertion pass would leave the defect in the product.
#:
#: Listed case by case, so this fails BOTH if a fourth surface starts overflowing and if one of
#: these three is fixed. A blanket `xfail` would mark all 40 cases and hide both directions.
_SCALING_OVERFLOW = frozenset({("compare", "en", 390), ("no_membership", "en", 390),
                               ("switcher", "en", 390)})


#: The two supported viewports, the pair the pre-existing `r807` browser case already measures.
#: `FR-200` requires its floors "at the supported viewports", plural, so every browser floor below
#: runs across this matrix rather than picking one width per floor.
_VIEWPORTS = ((1180, 900), (390, 844))


def _assert_contrast(measured: list[dict[str, float | str]], where: str) -> None:
    """Every measured node clears its floor, and something was measured at all."""
    assert measured, f"{where}: no text measured, so this proves nothing"
    for item in measured:
        assert item["ratio"] >= item["floor"], (
            f"{where}: {item['ratio']:.2f} < {item['floor']} on {item['text']!r}"
        )


@pytest.mark.browser
@pytest.mark.parametrize("viewport", _VIEWPORTS)
@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_text_contrast_is_computed_and_meets_its_floor(
    surface: str, language: str, viewport: tuple[int, int]
) -> None:
    """`FR-200` §Verification: contrast **computed** in the real browser, not asserted.

    Across both viewports: a narrow layout can reflow text onto a different background, so a
    ratio measured only at 1180 does not establish the floor at 390.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            page.set_content(_html(surface, language), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            _assert_contrast(page.evaluate(_CONTRAST), f"{surface}/{language}@{viewport[0]}")
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("viewport", _VIEWPORTS)
@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("page_name", ["about-us", "contact-us"])
def test_legal_text_contrast_is_computed_and_meets_its_floor(
    page_name: str, language: str, viewport: tuple[int, int]
) -> None:
    """One published page and one unpublished, so the non-null case is provably reached."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            page.set_content(_legal_html(page_name, language), wait_until="domcontentloaded")
            page.add_style_tag(content=_legal_css())
            _assert_contrast(page.evaluate(_CONTRAST), f"{page_name}/{language}@{viewport[0]}")
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("viewport", _VIEWPORTS)
@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_text_scales_to_two_hundred_percent_without_losing_content(
    surface: str, language: str, viewport: tuple[int, int]
) -> None:
    """`FR-200`: 200% text loses neither content nor function.

    Text length alone is not enough: CSS can clip content or push it off-screen while
    `innerText` is unchanged. So this also asserts no page-level horizontal overflow appears,
    which is how lost *function* actually presents.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            page.set_content(_html(surface, language), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            before = page.evaluate("document.body.innerText.trim().length")
            page.add_style_tag(content="html { font-size: 200% !important; }")
            after = page.evaluate("document.body.innerText.trim().length")
            assert after >= before, f"{surface}/{language}@{viewport[0]}: text was lost at 200%"
            fits = page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            if (surface, language, viewport[0]) in _SCALING_OVERFLOW:
                assert not fits, (
                    f"{surface}/{language}@{viewport[0]} now fits at 200%: the "
                    "`shell-components.css` finding is fixed, so remove it from _SCALING_OVERFLOW"
                )
            else:
                assert fits, (
                    f"{surface}/{language}@{viewport[0]}: 200% text introduced horizontal overflow"
                )
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("viewport", _VIEWPORTS)
@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_a_pointer_target_is_measured_on_the_element_it_lands_on(
    surface: str, language: str, viewport: tuple[int, int]
) -> None:
    """`FR-200`: at least 44px **on the element a pointer lands on**, not on an ancestor.

    States the "element a pointer lands on" half explicitly, which an ancestor-based measurement
    would hide, and includes `input` -- a text field is a pointer target like any other.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            page.set_content(_html(surface, language), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            controls = "a:visible, button:visible, select:visible, input:visible"
            for locator in page.locator(controls).all():
                box = locator.bounding_box()
                assert box is not None
                assert box["height"] >= 44, (
                    f"{surface}/{language}@{viewport[0]}: a target is {box['height']}px tall"
                )
        finally:
            browser.close()


#: The classes `FR-200`'s `role="status"` clause governs: **refusal and progress**.
#:
#: Taken from slice 5's state grammar (`test_r808_shell_state_grammar.py:8-17`), which bound
#: `FR-202`'s four states to classes, rather than from a grep of the rendered pages. The first
#: draft here used `empty-state` and `decision-availability` and failed on correct markup: an
#: empty result is `FR-202`'s state and slice 5's, not a refusal, and a trust state is measured
#: by the non-colour floor below under its own `FR-200` clause. Applying the announcement clause
#: to either is a guard answering a different question.
#:
#: The shell authors no progress affordance at all -- slice 5's
#: `test_no_shell_surface_carries_a_loading_affordance` records that it cannot occur -- so this
#: tuple carries refusals only.
_ANNOUNCING = ("decision-refusal", "decision-unsupported", "compare-refusal")

#: Regions carrying a trust state, which `FR-200` governs under its non-colour clause rather
#: than its announcement clause. `empty-state` is a governed empty rule (`FR-202`, slice 5's).
_TRUST_STATES = ("empty-state", "decision-availability")


def _regions(html: str, classes: tuple[str, ...]) -> list[str]:
    return [fragment for fragment in classes if f'class="{fragment}' in html]


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_a_refusal_or_progress_region_announces_itself(surface: str, language: str) -> None:
    """`FR-200`: `role="status"` for refusals and progress.

    Conditional because the clause has no reachable subject on these fixtures, not because the
    product omits something. No surface in `SHELL_SURFACES` renders any of slice 5's three
    refusal classes, and the shell authors no progress affordance at all. So this asserts the
    implication -- a surface that *does* carry a refusal announces it -- and the test below
    records that the antecedent is never true today, which is NOT EXERCISED rather than PASS.
    """
    html = _html(surface, language)
    regions = _regions(html, _ANNOUNCING)
    if not regions:
        pytest.skip(f"{surface}/{language} renders no refusal or progress region")
    assert 'role="status"' in html, f"{surface}/{language} renders {regions} without role=status"


def test_the_announcement_clause_has_no_reachable_subject_today() -> None:
    """Pinned so "not exercised" cannot be read later as "passed".

    `FR-200`'s announcement clause governs refusals and progress. These fixtures reach neither,
    so the floor above skips every case -- and a skipped floor proves nothing about the product.
    The day a surface renders a refusal, this fails, and that is the signal that the floor above
    has become live and this pin should go.
    """
    carrying = sorted(
        f"{surface}/{language}"
        for surface in SHELL_SURFACES
        for language in ("en", "ar")
        if _regions(_html(surface, language), _ANNOUNCING)
    )
    assert carrying == [], (
        f"{carrying} now render a refusal: the floor above is live, so delete this pin and "
        "record the result rather than the absence"
    )


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_a_trust_state_is_not_carried_by_colour_alone(surface: str, language: str) -> None:
    """`FR-200`: non-colour differentiation for every trust state.

    A state carried only by a class that paints it is invisible to a person who cannot see the
    paint. The floor is that the region carries text of its own -- the thing a screen reader
    announces and a monochrome display still shows.
    """
    html = _html(surface, language)
    for fragment in _regions(html, _TRUST_STATES):
        # EVERY occurrence, not the first: `overview` renders two `empty-state` regions, and a
        # `re.search` over the first passed a mutant that emptied one of them.
        pattern = rf'<(\w+)[^>]*class="{fragment}[^"]*"[^>]*>(.*?)</\1>'
        matches = re.findall(pattern, html, re.S)
        assert len(matches) == html.count(f'class="{fragment}'), (
            f"{surface}/{language}: a {fragment} region went unmatched, so this proves nothing"
        )
        for _, inner in matches:
            text = re.sub(r"<[^>]+>", "", inner).strip()
            assert text, f"{surface}/{language}: {fragment} carries colour but no text"


def test_the_browser_floors_are_not_silently_unmeasured() -> None:
    """The browser-gated floors skip in CI, and a skip is not a pass.

    CI runs a bare `uv run pytest` with no browser install step
    (`.github/workflows/governance.yml`), so every `@pytest.mark.browser` case -- including the
    computed-contrast floor `FR-200` §Verification requires to run in a real browser -- reports
    `skipped` there. Closing that needs a workflow edit, and `.github/` is not in `RCA-010`
    §Scope, so this slice records the gap rather than hiding it.

    What this pins: the marker still gates a non-zero number of cases. Removing the marker to
    make CI appear to cover them, or deleting the cases, fails here.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    marked = source.count("@pytest.mark.browser")
    assert marked >= 4, (
        f"only {marked} browser-gated cases remain; the computed-contrast floor may have been "
        "removed or silently de-marked"
    )
