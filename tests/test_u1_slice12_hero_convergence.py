"""`U1` slice 12: the shell converges on the approved Product UI composition (`RCA-010` §Scope).

Slice 11 placed the approved artwork as a picture above the page, with the heading and lede in a
card that rose into it, and deferred the handoff's own composition -- copy on the band over an
ivory wash -- to "the slice that makes that change" (`test_u1_slice11_hero_placement.py`). This is
that slice, together with three layout corrections the §17 critique found at the handoff's own
verification widths (1440, 1024, 390):

- **The copy sits on the band, inside the opaque part of the wash.** A contrast probe that reads
  the nearest `background-color` would see the ivory ground and pass even with the text over the
  photograph, so the evidence here is geometric: the text column's inline-end edge stays inside
  the solid stop the browser actually computed for the wash, in both directions.
- **At 390 the image is a 140px band above the copy**, not behind it (handoff §13).
- **At 1024 the analysis side rail drops below the passport** (handoff §13, "rail drops below"),
  where it previously kept a two-column label grid in a third of the width and split words.
- **At 1024 no overview module sits alone beside an empty cell**, and
  **at 1440 the frame keeps a symmetric inline margin** on the sand ground (handoff §10).

Every browser case runs the shipped routes on a loopback origin, so the stylesheets, the typeface
and the artwork arrive over the wire and the metrics are the ones a reader gets. Nothing here reads
a reference image: the references are the target, never the source of an assertion (`FR-205`).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from html.parser import HTMLParser
from typing import Any

import pytest
from fastapi import FastAPI

from tests.test_rca012_shell_hero_load import _app, _detail_app, _origin, needs_chromium
from tests.test_u1_slice11_hero_placement import _render

#: Each placing surface: its address under `/app/{language}` and the app that renders it.
_PLACING = {
    "overview": ("/org-acme/overview", _app),
    "analysis": ("/org-acme/analyses/run-a", _detail_app),
}
_LANGUAGES = ("en", "ar")
_CASES = [(surface, language) for surface in _PLACING for language in _LANGUAGES]

#: The handoff's verification widths (§13), with the two the wash must hold at.
_WIDE, _TABLET, _NARROW = 1440, 1024, 390


class _Ancestry(HTMLParser):
    """Records the class list of every open element when a target element starts."""

    def __init__(self, predicate: Callable[[str, dict[str, str]], bool]) -> None:
        super().__init__()
        self._predicate = predicate
        self._stack: list[tuple[str, str]] = []
        self.found: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value or "" for name, value in attrs}
        if self._predicate(tag, values):
            self.found.append([classes for _, classes in self._stack])
        if tag not in {"img", "source", "br", "hr", "input", "meta", "link"}:
            self._stack.append((tag, values.get("class", "")))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index][0] == tag:
                del self._stack[index:]
                return


def _ancestors_of(html: str, predicate: Callable[[str, dict[str, str]], bool]) -> list[list[str]]:
    parser = _Ancestry(predicate)
    parser.feed(html)
    return parser.found


def _inside_band(chain: list[str]) -> bool:
    return any("hero-band" in classes.split() for classes in chain)


class TestTheCopySitsOnTheBand:
    """The composition the handoff pairs with its wash: heading and lede on the band."""

    @pytest.mark.parametrize(("surface", "language"), _CASES)
    def test_the_page_title_is_inside_the_band(self, surface: str, language: str) -> None:
        html = _render(surface, language)
        chains = _ancestors_of(html, lambda _t, a: a.get("id") == "page-title")

        assert len(chains) == 1, f"{surface}/{language}: expected one #page-title, got {chains}"
        assert _inside_band(chains[0]), f"{surface}/{language}: the title is not on the band"

    @pytest.mark.parametrize(("surface", "language"), _CASES)
    def test_a_decorative_scrim_ships_with_the_copy(self, surface: str, language: str) -> None:
        """The wash is presentation only: hidden from assistive technology, inside the band."""
        html = _render(surface, language)
        chains = _ancestors_of(html, lambda _t, a: "hero-band__scrim" in a.get("class", "").split())

        assert len(chains) == 1, f"{surface}/{language}: expected one scrim, got {len(chains)}"
        assert _inside_band(chains[0])
        assert re.search(r'class="hero-band__scrim"[^>]*aria-hidden="true"', html)

    @pytest.mark.parametrize(("surface", "language"), _CASES)
    def test_the_labelled_region_still_contains_its_title(
        self, surface: str, language: str
    ) -> None:
        """`FR-200`: moving the band inside the page keeps `aria-labelledby` resolving within it."""
        html = _render(surface, language)
        chains = _ancestors_of(html, lambda _t, a: a.get("id") == "page-title")

        region = r'<section[^>]*class="workspace-page"[^>]*aria-labelledby="page-title"'
        assert re.search(region, html), f"{surface}/{language}: no labelled workspace-page region"
        assert any("workspace-page" in classes.split() for classes in chains[0]), chains[0]


@contextmanager
def _page(build: Callable[[], FastAPI], width: int, height: int = 900) -> Iterator[Any]:
    """A logged-in page at one viewport width, on a real origin."""
    from playwright.sync_api import sync_playwright

    from khepri.rca.session_cookie import SESSION_COOKIE
    from tests.test_r811_shell_accessibility import _launch_chromium

    with _origin(build) as origin, sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            context = browser.new_context(viewport={"width": width, "height": height})
            context.add_cookies(
                [{"name": SESSION_COOKIE, "value": "a-session-token", "url": origin}]
            )
            page = context.new_page()
            page.set_default_timeout(30_000)
            yield page, origin
        finally:
            browser.close()


_WASH_PROBE = """() => {
  const band = document.querySelector('.hero-band');
  const scrim = band.querySelector('.hero-band__scrim');
  const text = band.querySelector('.page-head__text');
  const box = (el) => { const r = el.getBoundingClientRect();
    return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width}; };
  return {
    band: box(band), text: box(text),
    image: getComputedStyle(scrim).backgroundImage,
    dir: document.documentElement.getAttribute('dir'),
  };
}"""

#: The wash's direction and its solid stop, read from the gradient the browser computed rather
#: than from the stylesheet that declares it -- so the assertion and the rule have two sources.
_GRADIENT = re.compile(r"linear-gradient\((?P<angle>\d+)deg,\s*rgb\([^)]*\)\s+(?P<solid>[\d.]+)%")


@pytest.mark.browser
@needs_chromium
class TestTheCopyStaysOnTheOpaqueWash:
    """Legibility is geometric: the text column ends before the wash begins to fade."""

    @pytest.mark.parametrize("width", [_WIDE, _TABLET])
    @pytest.mark.parametrize(("surface", "language"), _CASES)
    def test_the_text_column_ends_inside_the_solid_stop(
        self, surface: str, language: str, width: int
    ) -> None:
        path, build = _PLACING[surface]
        with _page(build, width) as (page, origin):
            page.goto(f"{origin}/app/{language}{path}", wait_until="load")
            measured = page.evaluate(_WASH_PROBE)

        gradient = _GRADIENT.search(measured["image"])
        assert gradient is not None, f"no wash is painted: {measured['image']!r}"
        band, text = measured["band"], measured["text"]
        solid = band["width"] * float(gradient["solid"]) / 100
        assert text["width"] > 0, "no text column measured, so this proves nothing"
        if measured["dir"] == "rtl":
            assert gradient["angle"] == "270", measured["image"]
            assert text["left"] >= band["right"] - solid - 0.5, (measured, gradient["solid"])
        else:
            assert gradient["angle"] == "90", measured["image"]
            assert text["right"] <= band["left"] + solid + 0.5, (measured, gradient["solid"])


_NARROW_PROBE = """() => {
  const band = document.querySelector('.hero-band');
  const image = band.querySelector('.hero-band__image').getBoundingClientRect();
  const text = band.querySelector('.page-head__text').getBoundingClientRect();
  return {imageHeight: image.height, imageBottom: image.bottom, textTop: text.top};
}"""


@pytest.mark.browser
@needs_chromium
class TestTheNarrowBandSitsAboveTheCopy:
    """Handoff §13 mobile: "image becomes a 140px band above copy"."""

    @pytest.mark.parametrize(("surface", "language"), _CASES)
    def test_the_image_is_a_140px_band_above_the_text(self, surface: str, language: str) -> None:
        path, build = _PLACING[surface]
        with _page(build, _NARROW, 844) as (page, origin):
            page.goto(f"{origin}/app/{language}{path}", wait_until="load")
            measured = page.evaluate(_NARROW_PROBE)

        assert round(measured["imageHeight"]) == 140, measured
        assert measured["textTop"] >= measured["imageBottom"] - 0.5, measured


@pytest.mark.browser
@needs_chromium
class TestTheTabletLayoutDropsTheRail:
    """Handoff §13 tablet: the side rail drops below, and no module is left beside an empty cell."""

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_the_analysis_side_rail_sits_below_the_passport(self, language: str) -> None:
        path, build = _PLACING["analysis"]
        with _page(build, _TABLET) as (page, origin):
            page.goto(f"{origin}/app/{language}{path}", wait_until="load")
            measured = page.evaluate(
                """() => {
                  const grid = document.querySelector('.detail-grid').getBoundingClientRect();
                  const side = document.querySelector('.detail-side').getBoundingClientRect();
                  const main = document.querySelector('.passport').getBoundingClientRect();
                  return {grid: grid.width, side: side.width, sideTop: side.top,
                          mainBottom: main.bottom};
                }"""
            )

        assert measured["sideTop"] >= measured["mainBottom"], measured
        assert measured["side"] >= measured["grid"] - 1, measured

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_no_module_sits_alone_beside_an_empty_cell(self, language: str) -> None:
        """Every module either spans the row or shares it. Measured through
        `test_r807_shell_quality.py`'s overview wiring, which renders the arrangement the critique
        found orphaned: three half-width modules, then `Recent` spanning the row."""
        from tests.test_r807_shell_quality import _client

        path = _PLACING["overview"][0]
        with _page(lambda: _client("overview").app, _TABLET) as (page, origin):
            page.goto(f"{origin}/app/{language}{path}", wait_until="load")
            rows = page.evaluate(
                """() => {
                  const grid = document.querySelector('.module-grid');
                  const full = grid.getBoundingClientRect().width;
                  const rows = {};
                  for (const child of grid.children) {
                    const r = child.getBoundingClientRect();
                    const key = Math.round(r.top);
                    (rows[key] ||= []).push(r.width >= full - 1 ? 'full' : 'part');
                  }
                  return Object.values(rows);
                }"""
            )

        partial = [row for row in rows if "part" in row]
        assert partial, f"no module shares a row, so this proves nothing: {rows}"
        assert all(len(row) > 1 for row in partial), f"a module sits alone: {rows}"


@pytest.mark.browser
@needs_chromium
class TestTheFrameSitsOnTheGround:
    """Handoff §10: the frame keeps the sand ground around it on every side at desktop."""

    @pytest.mark.parametrize("language", _LANGUAGES)
    def test_the_inline_margins_are_symmetric_and_present(self, language: str) -> None:
        path, build = _PLACING["overview"]
        with _page(build, _WIDE) as (page, origin):
            page.goto(f"{origin}/app/{language}{path}", wait_until="load")
            measured = page.evaluate(
                """() => {
                  const frame = document.querySelector('.app-frame').getBoundingClientRect();
                  const top = parseFloat(getComputedStyle(
                    document.querySelector('.app-frame')).marginBlockStart);
                  return {start: frame.left, end: document.documentElement.clientWidth
                          - frame.right, top};
                }"""
            )

        assert measured["top"] > 0, measured
        assert measured["start"] >= measured["top"] - 0.5, measured
        assert abs(measured["start"] - measured["end"]) <= 1, measured
