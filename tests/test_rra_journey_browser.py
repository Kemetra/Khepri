from __future__ import annotations

from importlib.resources import files

import pytest
from playwright.sync_api import Error, sync_playwright

from tests.test_rra_journey_api import client


@pytest.mark.browser
@pytest.mark.parametrize("viewport", [(1180, 900), (390, 844)])
@pytest.mark.parametrize("language", ["en", "ar"])
def test_journey_pages_fit_viewport_and_keep_operable_targets(
    viewport: tuple[int, int], language: str
) -> None:
    css = files("khepri.rra.journey").joinpath("assets", "journey.css").read_text(
        encoding="utf-8"
    )
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            page.emulate_media(reduced_motion="reduce")
            for step in ("upload", "review", "processing", "report"):
                html = client().get(f"/beta/{language}/{step}").text
                page.set_content(html, wait_until="domcontentloaded")
                page.add_style_tag(content=css)
                assert page.locator("html").get_attribute("dir") == (
                    "rtl" if language == "ar" else "ltr"
                )
                assert page.locator("h1").count() == 1
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                for locator in page.locator(
                    "button:visible, .language-link:visible, .step-nav a:visible"
                ).all():
                    box = locator.bounding_box()
                    assert box is not None and box["height"] >= 44
        finally:
            browser.close()
