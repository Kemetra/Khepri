"""`RRA-016` `FR-227`–`FR-229`: the journey places the approved hero artwork, and only that.

Four kinds of evidence:

- **Static scope.** The journey allowlist is its six prior entries plus exactly the two names
  `hero.py` audits, so no other filename became servable and the PNG never did. No template writes
  alternative text of its own, and the steps the handoff table does not place it on carry none.
- **Computed presentation**, in a real browser from the routed page: the crop is `object-fit` and
  `object-position` only, the focal point mirrors under right-to-left while the image does not,
  and the heading stays inside the wash's solid stop, at 200% text too.
- **Failure.** With the artwork refused, every placing step is still legible and complete.
- **The wire.** On a loopback origin serving the real journey application and its real Content
  Security Policy, the derivatives arrive with a 200 and their audited digests, an unknown name
  and the PNG are refused, and a navigated page actually decodes the image.
"""

from __future__ import annotations

import hashlib
import re
from importlib.resources import files

import pytest
from fastapi import FastAPI
from playwright.sync_api import Browser, Page, sync_playwright

from khepri.rra.api import create_app
from khepri.rra.journey.copy import JOURNEY_COPY
from khepri.rra.journey.hero import HERO_DIGESTS, HERO_FILES, HERO_MEDIA_TYPES
from khepri.rra.journey.routes import JourneyServices
from tests.test_rca012_shell_hero_load import _origin
from tests.test_rra006_report_api import invitation_service
from tests.test_rra016_journey_composition import (
    _CLIPPED_SCRIPT,
    _RENDERED,
    _launch,
    _layout_failures,
    _populated_page,
)
from tests.test_rra_journey_api import NOW, Reader, client

_LANGUAGES = ("en", "ar")
_TEMPLATES = files("khepri.rra.journey").joinpath("templates")

#: The step, its handoff §6 row as the browser computes it (LTR focal point, RTL focal point),
#: the placed element, and the band's minimum height where it is a band.
_PLACEMENTS = {
    "upload": (".journey-hero-card__image", "50% 50%", "50% 50%", None),
    "review": (".journey-hero__image", "70% 40%", "30% 40%", "170px"),
    "processing": (".journey-hero__image", "66% 44%", "34% 44%", "186px"),
}
#: Steps and terminal pages the handoff table does not place the artwork on.
_UNPLACED = ("report", "expired", "expired?deletion=requested")

#: Everything the handoff forbids doing to the artwork, as the browser computes it.
_TREATMENT_SCRIPT = """
(selector) => {
  const image = document.querySelector(selector);
  const style = getComputedStyle(image);
  return {
    fit: style.objectFit, focal: style.objectPosition, transform: style.transform,
    filter: style.filter, blend: style.mixBlendMode, opacity: style.opacity,
    decoded: image.complete && image.naturalWidth > 0, alt: image.alt,
  };
}
"""

#: The heading column's inline-end edge against the wash's solid stop, in the band's own frame.
_STOP_SCRIPT = """
() => {
  const band = document.querySelector(".journey-hero");
  const copy = band.querySelector(".journey-hero__copy").getBoundingClientRect();
  const box = band.getBoundingClientRect();
  const solid = parseFloat(getComputedStyle(band).getPropertyValue("--journey-hero-solid")) / 100;
  const rtl = getComputedStyle(band).direction === "rtl";
  const end = rtl ? box.right - copy.left : copy.right - box.left;
  return { end, stop: box.width * solid };
}
"""


def _prior_asset_names() -> set[str]:
    """The allowlist before this slice: the stylesheet and the five modules."""
    return {"journey.css", "common.js", "upload.js", "review.js", "processing.js", "report.js"}


def _journey_app() -> FastAPI:
    """The shipped journey application, as `tests.test_rra_journey_api.client` builds it."""
    return create_app(
        service=invitation_service(),
        clock=lambda: NOW,
        journey_services=JourneyServices(reader=Reader()),
    )


#: The populated state each placing step is measured in.
_PLACED_STATE = {"upload": "upload", "review": "review-mapped", "processing": "processing-running"}


def _placed_page(browser: Browser, language: str, step: str, width: int) -> Page:
    return _populated_page(browser, language, _PLACED_STATE[step], width)


def _without_artwork(page: Page, step: str) -> Page:
    """The same page reloaded with every derivative refused.

    The latest page route takes precedence over the routed page's own handler, and routing
    disables the HTTP cache, so the reload cannot reuse the bytes the first load fetched."""
    page.route("**/khepri-hero*", lambda route: route.abort())
    page.reload()
    page.wait_for_selector(_RENDERED[_PLACED_STATE[step]], state="attached")
    page.evaluate("document.fonts.ready")
    return page


# --- FR-227: exactly two names became servable ----------------------------------------------------


def test_the_allowlist_gained_exactly_the_audited_derivatives() -> None:
    from khepri.rra.journey.routes import _ASSETS

    assert HERO_MEDIA_TYPES, "hero.py audits nothing, so this proves nothing"
    assert set(_ASSETS) == _prior_asset_names() | set(HERO_MEDIA_TYPES)
    for name, media_type in HERO_MEDIA_TYPES.items():
        assert _ASSETS[name] == media_type


@pytest.mark.parametrize("name", HERO_FILES)
def test_each_derivative_is_served_with_its_audited_bytes(name: str) -> None:
    response = client().get(f"/beta/assets/{name}")

    assert response.status_code == 200
    assert response.headers["content-type"] == HERO_MEDIA_TYPES[name]
    assert hashlib.sha256(response.content).hexdigest() == HERO_DIGESTS[name]


@pytest.mark.parametrize("name", ["khepri-hero.png", "khepri-hero.avif", "khepri-hero@2x.jpg"])
def test_an_unaudited_name_is_refused(name: str) -> None:
    assert client().get(f"/beta/assets/{name}").status_code == 404


# --- FR-228, FR-229: placement and alternative text ---------------------------------------------


@pytest.mark.parametrize("language", _LANGUAGES)
@pytest.mark.parametrize("step", sorted(_PLACEMENTS))
def test_each_placing_step_carries_one_image_with_the_copy_modules_alt(
    language: str, step: str
) -> None:
    body = client().get(f"/beta/{language}/{step}").text
    images = re.findall(r"<img\b[^>]*>", body)

    assert len(images) == 1, step
    assert f'alt="{JOURNEY_COPY[language]["hero_alt"]}"' in images[0]
    assert 'src="/beta/assets/khepri-hero.jpg"' in images[0]
    assert '<source srcset="/beta/assets/khepri-hero.webp" type="image/webp">' in body


@pytest.mark.parametrize("language", _LANGUAGES)
@pytest.mark.parametrize("address", _UNPLACED)
def test_no_other_page_places_the_artwork(language: str, address: str) -> None:
    response = client().get(f"/beta/{language}/{address}")

    assert response.status_code == 200
    assert "khepri-hero" not in response.text


def test_no_template_writes_alternative_text_of_its_own() -> None:
    """Every `alt` is the copy module's key: a literal in either language fails here."""
    alts = {
        entry.name: re.findall(r'alt="([^"]*)"', entry.read_text(encoding="utf-8"))
        for entry in _TEMPLATES.iterdir()
        if entry.name.endswith(".j2")
    }

    assert sum(len(found) for found in alts.values()) > 0, "no alt was found, so none was checked"
    assert {value for found in alts.values() for value in found} == {"{{ copy.hero_alt }}"}


def test_no_journey_stylesheet_names_an_app_address() -> None:
    css = files("khepri.rra.journey").joinpath("assets", "journey.css").read_text("utf-8")

    assert "/app/" not in css


# --- FR-228 in a real browser ------------------------------------------------------------------


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_crop_is_position_only_and_the_focal_point_mirrors(language: str) -> None:
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for step, (selector, ltr, rtl, band) in _PLACEMENTS.items():
                page = _placed_page(browser, language, step, 1440)
                page.wait_for_function("s => document.querySelector(s).complete", arg=selector)
                treatment = page.evaluate(_TREATMENT_SCRIPT, selector)
                assert treatment == {
                    "fit": "cover",
                    "focal": ltr if language == "en" else rtl,
                    "transform": "none",
                    "filter": "none",
                    "blend": "normal",
                    "opacity": "1",
                    "decoded": True,
                    "alt": JOURNEY_COPY[language]["hero_alt"],
                }, step
                if band is not None:
                    height = page.evaluate(
                        "getComputedStyle(document.querySelector('.journey-hero')).minHeight"
                    )
                    assert height == band, step
                page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("scale", ["100%", "200%"])
@pytest.mark.parametrize("width", [1440, 1024])
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_heading_stays_inside_the_washs_solid_stop(
    language: str, width: int, scale: str
) -> None:
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for step in ("review", "processing"):
                page = _placed_page(browser, language, step, width)
                page.add_style_tag(content=f"html {{ font-size: {scale}; }}")
                measured = page.evaluate(_STOP_SCRIPT)
                assert 0 < measured["end"] <= measured["stop"], (step, measured)
                assert page.evaluate(_CLIPPED_SCRIPT) == [], step
                page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_the_artwork_leads_the_heading_at_the_narrow_width(language: str) -> None:
    """Handoff §13: at 390 the band's image becomes a strip above the copy, not beside it."""
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for step, (selector, *_row) in _PLACEMENTS.items():
                page = _placed_page(browser, language, step, 390)
                image = page.locator(selector).bounding_box()
                heading = page.locator("h1").bounding_box()
                assert image is not None and heading is not None
                assert image["y"] + image["height"] <= heading["y"], step
                page.close()
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("width", [1440, 1024, 390])
@pytest.mark.parametrize("language", _LANGUAGES)
def test_a_step_whose_artwork_never_arrives_is_legible_and_complete(
    language: str, width: int
) -> None:
    with sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            for step, (selector, *_row) in _PLACEMENTS.items():
                page = _without_artwork(_placed_page(browser, language, step, width), step)
                assert (
                    page.evaluate("s => document.querySelector(s).naturalWidth", selector) == 0
                ), f"{step}: the artwork arrived, so its absence was not exercised"
                assert _layout_failures(page) == [], step
                page.close()
        finally:
            browser.close()


# --- FR-227 over a real socket -----------------------------------------------------------------


@pytest.mark.browser
def test_the_origin_serves_the_audited_derivatives_and_refuses_the_rest() -> None:
    with _origin(_journey_app) as origin, sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            request = browser.new_context().request
            for name in HERO_FILES:
                response = request.get(f"{origin}/beta/assets/{name}")
                assert response.status == 200, name
                assert response.headers["content-type"] == HERO_MEDIA_TYPES[name]
                assert hashlib.sha256(response.body()).hexdigest() == HERO_DIGESTS[name]
            for refused in ("khepri-hero.png", "khepri-hero.avif"):
                assert request.get(f"{origin}/beta/assets/{refused}").status == 404, refused
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("language", _LANGUAGES)
def test_a_navigated_step_decodes_the_artwork_under_the_shipped_policy(language: str) -> None:
    """The routed page answers without the response headers, so no CSP applies there. This
    navigates the real origin, whose policy the response carries, with the step's module blocked
    so its session check cannot navigate away before the image is read."""
    with _origin(_journey_app) as origin, sync_playwright() as playwright:
        browser = _launch(playwright)
        try:
            page = browser.new_page()
            page.route("**/*.js", lambda route: route.abort())
            response = page.goto(f"{origin}/beta/{language}/review")
            assert (
                response is not None
                and "img-src 'self'" in response.headers["content-security-policy"]
            )
            page.wait_for_function("document.querySelector('.journey-hero__image').complete")
            assert (
                page.evaluate("document.querySelector('.journey-hero__image').naturalWidth") == 1400
            )
        finally:
            browser.close()
