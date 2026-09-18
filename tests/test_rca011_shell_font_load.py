"""`RCA-011`: a real browser, from a real origin, actually loads the shell's typeface.

**Why this file exists beside `test_rca011_shell_typeface.py`.** That module proves the route
serves the bytes and the stylesheet names the right address, through `TestClient` and file scans.
The shell's browser matrix (`test_r810`/`r811`/`r812`) builds pages with `page.set_content` plus
`page.add_style_tag` -- there is **no HTTP origin** in those tests, so a relative `url()` in an
`@font-face` resolves against nothing and the face is never fetched. Both are real evidence, and
neither can say the shipped browser requests and loads the file.

So those suites are **regression evidence**: they prove this slice moved no metric. They are not
font-load evidence, and `#489` is the reason the difference matters -- a token can name a family
that never arrives, and everything still looks fine because the cascade falls through.

This module closes exactly that gap. It runs the real application under `uvicorn` on a loopback
port, points the pinned Chromium at it, and watches the wire.

**The network layer is the primary proof, not `document.fonts.check()`.** That call answers "does
this family resolve at all", which a **system-installed** Noto Sans Arabic satisfies on a machine
that happens to have one -- a false positive that would survive deleting the whole slice. What
cannot be faked by a system font is the browser issuing `GET /app/assets/<face>.woff2` against this
origin and receiving a 200. `document.fonts` is then layered on top to show the face was not merely
fetched but parsed and usable.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi import FastAPI

from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rra.rendering.fonts import ARABIC_FILE, FONT_FAMILY, FONT_MEDIA_TYPE, LATIN_FILE
from khepri.runtime.shell_api import SHELL_ASSETS, ShellServices, add_shell_routes
from tests.test_m2_persistent_frame import (
    NOW,
    ORGANIZATION_NAME,
    _Context,
    _organization,
    _StubIsolation,
    _StubOrganizations,
    _StubRecords,
    _StubResolver,
)
from tests.test_rra006_pdf_surface import chromium_available

#: The session the shell reads. A browser without it lands on the unavailable surface, which links
#: the same stylesheets and would make every assertion below measure a refusal.
_SESSION = "a-session-token"

#: A surface that renders 200 and links the shell's three stylesheets, in both languages.
_SURFACE = "/app/{language}/org-acme/overview"

needs_chromium = pytest.mark.skipif(
    not chromium_available(),
    reason="the pinned Chromium is not installed; run `playwright install chromium`",
)


def _free_port() -> int:
    """A port the OS just confirmed is free, so two runs in one tree do not collide."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _app() -> FastAPI:
    """The real shell routes, wired the way `test_m2_persistent_frame.py` wires them.

    The stubs stand in for the resolver and the organization reader only. The asset route, the
    templates, the allowlist and the security headers are the shipped ones -- which is the whole
    point: a hand-wired fixture that served the fonts itself would prove nothing about the route.
    """
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(_Context("acct-1", "org-acme")),
            organizations=_StubOrganizations([_organization("org-acme", ORGANIZATION_NAME)]),
            records=_StubRecords(),
            isolation=_StubIsolation(),
        ),
        clock=lambda: NOW,
    )
    return app


def _served(app: FastAPI, path: str) -> object:
    """A `TestClient` read of a surface, carrying the session the shell requires."""
    from fastapi.testclient import TestClient

    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, _SESSION)
    return client.get(path)


@contextmanager
def _origin() -> Iterator[str]:
    """The application on a loopback port, torn down whatever happens.

    `install_signal_handlers` is disabled because uvicorn installs them on the main thread only and
    raises off it. The server is polled rather than slept at, so a slow machine waits longer rather
    than flaking.
    """
    import uvicorn

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(_app(), host="127.0.0.1", port=port, log_level="warning")
    )
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 30
        while not server.started:
            if time.monotonic() > deadline:  # pragma: no cover - a hung server
                raise RuntimeError("the test origin did not start")
            if not thread.is_alive():  # pragma: no cover - a crashed server
                raise RuntimeError("the test origin died before it started")
            time.sleep(0.05)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=30)


@contextmanager
def _page_on(origin: str, language: str) -> Iterator[tuple[object, list[tuple[str, int]]]]:
    """A Chromium page loaded from the real origin, with every response recorded.

    The recording is what makes this file's central claim falsifiable: the assertions below read
    the wire, not the renderer.
    """
    from playwright.sync_api import sync_playwright

    from tests.test_r811_shell_accessibility import _launch_chromium

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            context = browser.new_context()
            context.add_cookies(
                [{"name": SESSION_COOKIE, "value": _SESSION, "url": origin}]
            )
            page = context.new_page()
            responses: list[tuple[str, int]] = []
            page.on("response", lambda r: responses.append((r.url, r.status)))
            address = f"{origin}{_SURFACE.format(language=language)}"
            landed = page.goto(address, wait_until="load")
            # A refusal links the same stylesheets, so every assertion below would still pass on a
            # page that never rendered the surface. Fail here instead.
            assert landed is not None and landed.status == 200, (
                f"{address} -> {landed.status if landed else 'no response'}"
            )
            page.evaluate("() => document.fonts.ready")
            yield page, responses
        finally:
            browser.close()


def _fonts(responses: list[tuple[str, int]]) -> list[tuple[str, int]]:
    return [(url, status) for url, status in responses if url.endswith(".woff2")]


class TestTheSurfaceLinksTheStylesheet:
    """Requirement B, asserted before any browser runs.

    Without this, every font assertion below could pass vacuously on a page that linked nothing:
    no link, no request, no failure.
    """

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_rendered_page_links_the_shells_own_stylesheet(self, language: str) -> None:
        response = _served(_app(), _SURFACE.format(language=language))

        assert response.status_code == 200
        assert f'href="{SHELL_ASSETS}/shell-components.css"' in response.text

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_page_carries_text_in_both_scripts(self, language: str) -> None:
        """Both subsets are exercised on either page because the language control names the other
        language in its own script. A page of one script only would request one subset, and
        asserting both there would fail on correct code."""
        text = _served(_app(), _SURFACE.format(language=language)).text

        assert any("؀" <= character <= "ۿ" for character in text), "no Arabic text"
        assert any("a" <= character.lower() <= "z" for character in text), "no Latin text"


@pytest.mark.browser
@needs_chromium
class TestARealBrowserLoadsTheFaceFromTheShellsOrigin:
    """Requirements A, C and D, measured on the wire rather than in the renderer."""

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_browser_requests_both_subsets_from_the_shell_and_gets_them(
        self, language: str
    ) -> None:
        """`FR-207`: served from the shell's own address, to a real browser.

        A system-installed Noto could satisfy `document.fonts.check`; it cannot make Chromium issue
        this request against this origin.
        """
        with _origin() as origin, _page_on(origin, language) as (_page, responses):
            served = dict(_fonts(responses))

            for file_name in (ARABIC_FILE, LATIN_FILE):
                address = f"{origin}{SHELL_ASSETS}/{file_name}"
                assert address in served, (
                    f"{file_name} was never requested from the shell; font requests: {served}"
                )
                assert served[address] == 200, f"{file_name} -> {served[address]}"

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_no_font_request_fails_and_none_reaches_the_journey(self, language: str) -> None:
        """`FR-208`: the shell depends on no `/beta` address, asserted against real traffic."""
        with _origin() as origin, _page_on(origin, language) as (_page, responses):
            assert not [url for url, _ in responses if "/beta/" in url], (
                f"the shell requested a journey address: {responses}"
            )

            failures = [(url, status) for url, status in _fonts(responses) if status >= 400]
            assert not failures, f"a font request failed: {failures}"

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_face_is_served_with_the_font_media_type(self, language: str) -> None:
        """`nosniff` ships in `SECURITY_HEADERS`, so a `.woff2` labelled `text/css` is refused by
        the browser rather than quietly accepted. The header is read from the real response."""
        with _origin() as origin, _page_on(origin, language) as (page, _responses):
            checked = page.request.get(f"{origin}{SHELL_ASSETS}/{ARABIC_FILE}")

            assert checked.status == 200
            assert checked.headers["content-type"].startswith(FONT_MEDIA_TYPE)
            assert checked.headers.get("x-content-type-options") == "nosniff"

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_stylesheet_parsed_into_two_font_faces(self, language: str) -> None:
        """`document.fonts` carrying both entries proves the browser parsed the `@font-face` rules
        the slice added -- not merely that some font of that family exists somewhere."""
        with _origin() as origin, _page_on(origin, language) as (page, _responses):
            families = page.evaluate(
                "() => [...document.fonts].map(face => face.family)"
            )

            assert families.count(FONT_FAMILY) == 2, (
                f"expected two @font-face entries for {FONT_FAMILY}, saw {families}"
            )

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_face_loads_rather_than_merely_being_declared(self, language: str) -> None:
        """`FR-207`/`FR-210`: the intended face is available, and the chain is still declared.

        `document.fonts.load` is awaited for text in each script, then every entry for the family
        is required to report `loaded` and none to report `error`. A declared-but-unfetched face
        reports `unloaded`; a face whose bytes failed reports `error`. Both would pass a
        `getComputedStyle(...).fontFamily` check, which is why that is not the assertion here.
        """
        with _origin() as origin, _page_on(origin, language) as (page, _responses):
            statuses = page.evaluate(
                """async () => {
                    await document.fonts.load('16px "Noto Sans Arabic"', 'Khepri');
                    await document.fonts.load(
                        '16px "Noto Sans Arabic"', '\\u0645\\u0631\\u062d\\u0628\\u0627');
                    await document.fonts.ready;
                    return [...document.fonts]
                        .filter(face => face.family === 'Noto Sans Arabic')
                        .map(face => face.status);
                }"""
            )

            assert statuses, "no FontFace entry for the family the stylesheet declares"
            assert set(statuses) == {"loaded"}, f"font statuses: {statuses}"

    @pytest.mark.parametrize("language", ["en", "ar"])
    def test_the_body_still_declares_the_whole_fallback_chain(self, language: str) -> None:
        """`FR-210`: the face became available; the fallback did not become unnecessary.

        This is the `#489` assertion, re-made from a real origin. It is deliberately *not* the
        proof that the face loaded -- the test above is -- because this string reads the same
        whether the file arrived or 404'd.
        """
        with _origin() as origin, _page_on(origin, language) as (page, _responses):
            declared = page.evaluate("() => getComputedStyle(document.body).fontFamily")

            for family in (FONT_FAMILY, "Segoe UI", "Tahoma", "sans-serif"):
                assert family in declared, f"{family} missing from {declared!r}"
@pytest.mark.browser
@needs_chromium
class TestTheRealFaceChangesNoLayout:
    """`RCA-010` `FR-200`, re-measured with the face actually loaded.

    **Why this belongs here and not in the `r810`/`r812` matrix.** Those suites inject CSS with no
    HTTP origin, so they measure the *fallback's* metrics however many times they are re-run --
    they prove this slice regressed nothing, which is a different claim from "the shipped face
    fits". A typeface change moves text metrics, and `#487` found a real 200%-zoom overflow
    exactly this way, so the question is asked of the real face from the real origin.

    `body.style.zoom` is used rather than a device scale factor because `FR-200` is about text
    scaling, and it is the mechanism `#487`'s fix was measured against.
    """

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize(
        ("width", "height", "zoom"),
        [(1180, 900, None), (390, 844, None), (1180, 900, "200%")],
        ids=["desktop", "mobile", "desktop-200pc"],
    )
    def test_the_loaded_face_causes_no_horizontal_overflow(
        self, language: str, width: int, height: int, zoom: str | None
    ) -> None:
        from playwright.sync_api import sync_playwright

        from tests.test_r811_shell_accessibility import _launch_chromium

        with _origin() as origin, sync_playwright() as playwright:
            browser = _launch_chromium(playwright)
            try:
                context = browser.new_context(viewport={"width": width, "height": height})
                context.add_cookies(
                    [{"name": SESSION_COOKIE, "value": _SESSION, "url": origin}]
                )
                page = context.new_page()
                page.goto(
                    f"{origin}{_SURFACE.format(language=language)}", wait_until="load"
                )
                page.evaluate("() => document.fonts.ready")

                # The measurement is meaningless if the face never arrived: the fallback would be
                # measured and reported as a pass, which is the defect this whole module exists to
                # rule out.
                statuses = page.evaluate(
                    "() => [...document.fonts]"
                    ".filter(face => face.family === 'Noto Sans Arabic')"
                    ".map(face => face.status)"
                )
                assert statuses and set(statuses) == {"loaded"}, (
                    f"the face was not loaded when layout was measured: {statuses}"
                )

                if zoom is not None:
                    page.evaluate(f"() => {{ document.body.style.zoom = '{zoom}'; }}")
                    page.wait_for_timeout(200)

                overflow = page.evaluate(
                    "() => document.documentElement.scrollWidth"
                    " - document.documentElement.clientWidth"
                )

                assert overflow <= 0, (
                    f"{language} at {width}x{height} zoom={zoom}: {overflow}px of horizontal "
                    "overflow with the real face loaded"
                )
            finally:
                browser.close()
