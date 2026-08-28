from __future__ import annotations

import json
from importlib.resources import files

import pytest
from playwright.sync_api import Error, sync_playwright

from khepri.rra.coverage_request import CoverageManifestBody
from tests.test_rra_journey_api import client

_ATTESTED = {
    "timezone": "Africa/Cairo",
    "attested_by": "Mona Farouk, branch manager",
    "covered_start": "2026-01-01",
    "covered_end": "2026-01-02",
    "aggregate_scope": "All stores",
    "covered_days": "2026-01-01, 2026-01-02",
    "event_kinds": "sale",
    "statuses": "posted",
    "closed_days": "2026-01-02",
    "extraction_gap_days": "",
}


@pytest.mark.browser
@pytest.mark.parametrize("language", ["en", "ar"])
def test_the_upload_page_sends_a_manifest_only_when_one_is_attested(
    language: str,
) -> None:
    """`profileRequest()` itself, run in a browser over the served module.

    Executed rather than grepped: a source assertion that the omission text is
    present passes against a body that always returns the object, and an
    always-present manifest names no scope, which `build_coverage_manifest`
    refuses -- so every operator who declined to attest would be refused.
    """
    module = client().get("/beta/assets/upload.js").text
    body = client().get(f"/beta/{language}/upload").text
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page = browser.new_page()
            page.set_content(body, wait_until="domcontentloaded")
            # The module's own `attestation`/`profileRequest`, lifted out of the
            # served file and evaluated against the served page's real controls.
            harness = (
                module[module.index("const attestation") : module.index("// The stated reason")]
                + "\nreturn profileRequest();"
            )
            blank = page.evaluate(
                "() => { const manifestFields ="
                " document.querySelectorAll('[data-manifest-field]');"
                " const declaration = () => ({});"
                f" {harness} }}"
            )
            assert "coverage_manifest" not in blank

            for name, value in _ATTESTED.items():
                page.fill(f"[data-manifest-field='{name}']", value)
            attested = page.evaluate(
                "() => { const manifestFields ="
                " document.querySelectorAll('[data-manifest-field]');"
                " const declaration = () => ({});"
                f" {harness} }}"
            )
            sent = json.loads(attested)["coverage_manifest"]
            assert sent["timezone"] == "Africa/Cairo"
            assert sent["attested_by"] == "Mona Farouk, branch manager", (
                "the page collects an attester the request does not carry"
            )
            assert sent["covered_days"] == ["2026-01-01", "2026-01-02"]
            assert sent["event_kinds"] == ["sale"]
            assert sent["closed_days"] == ["2026-01-02"]
            assert sent["extraction_gap_days"] == []
            # An untouched checkbox rides along as its own default, not as an
            # attestation: the manifest was already attested by the text above.
            assert sent["partial_terminal_boundary"] is False
            assert CoverageManifestBody(**sent)._scopes() == ("All stores",)
        finally:
            browser.close()


@pytest.mark.browser
def test_ticking_only_the_terminal_boundary_still_sends_an_attestation() -> None:
    """The one control that attests without any text being typed.

    An unticked box is not an attestation -- `false` is the field's default and
    rides on every manifest -- but a ticked one is a claim the operator made,
    and dropping it would silently discard the only thing they said.
    """
    module = client().get("/beta/assets/upload.js").text
    body = client().get("/beta/en/upload").text
    harness = (
        module[module.index("const attestation") : module.index("// The stated reason")]
        + "\nreturn profileRequest();"
    )
    evaluate = (
        "() => { const manifestFields ="
        " document.querySelectorAll('[data-manifest-field]');"
        " const declaration = () => ({});"
        f" {harness} }}"
    )
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page = browser.new_page()
            page.set_content(body, wait_until="domcontentloaded")
            assert "coverage_manifest" not in page.evaluate(evaluate)

            page.check("[data-manifest-field='partial_terminal_boundary']")

            sent = json.loads(page.evaluate(evaluate))["coverage_manifest"]
            assert sent["partial_terminal_boundary"] is True
        finally:
            browser.close()


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
