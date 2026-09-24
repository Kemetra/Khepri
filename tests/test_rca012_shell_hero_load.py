"""`RCA-012`: a real browser, from a real origin, actually loads the shell's hero artwork.

**Why this file exists beside `test_rca012_shell_hero_artwork.py`.** That module proves the route
serves the bytes through `TestClient` and file scans. `RCA-012` §Verification asks for more,
naming the discipline `test_rca011_shell_font_load.py` established: an allowlist entry naming a
file the shipped image does not carry passes every in-process test and 404s in production. Only a
real HTTP origin can tell those two apart.

**Two kinds of evidence, both over a real socket.** The direct fetches read the response for each
derivative: the status, the `Content-Type` the browser was actually handed, and the SHA-256 of the
bytes that came over the wire against the audited manifest. They were this module's only claim
when `#514` shipped the asset with no page placing it, because a navigation then would have
watched for a request no page makes.

The placing surfaces now exist -- the overview (`U1` slice 11) and analysis detail (its
follow-on) -- so the navigation case visits each one, as the font module does for `@font-face`,
and asserts the browser requested a derivative, was answered 200, and resolved that surface's
handoff row in its computed style.
"""

from __future__ import annotations

import hashlib
import socket
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest
from fastapi import FastAPI

from khepri.rra.journey.hero import (
    HERO_DIGESTS,
    HERO_FILES,
    HERO_JPEG_FILE,
    HERO_MEDIA_TYPES,
)
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
from tests.test_r807_shell_quality import NOW as QUALITY_NOW
from tests.test_r807_shell_quality import (
    _StubBridge,
    _StubComparisons,
    _StubDecisions,
    _StubInvitations,
    _StubProvenance,
)
from tests.test_r807_shell_quality import _StubIsolation as _QualityIsolation
from tests.test_r807_shell_quality import _StubOrganizations as _QualityOrganizations
from tests.test_r807_shell_quality import _StubRecords as _QualityRecords
from tests.test_r807_shell_quality import _StubResolver as _QualityResolver
from tests.test_rra006_pdf_surface import chromium_available

needs_chromium = pytest.mark.skipif(
    not chromium_available(),
    reason="the pinned Chromium is not installed; run `playwright install chromium`",
)


def _listener() -> socket.socket:
    """A bound, listening socket, handed to uvicorn rather than a port number.

    Probing for a free port and closing the probe leaves a window in which the port is free again
    but nothing holds it, and a parallel worker in the same tree can take it. Keeping the listener
    open closes that window; `test_rca011_shell_font_load.py` records the same reasoning.
    """
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    return listener


def _app() -> FastAPI:
    """The real shell routes. The stubs stand in for the resolver and reader only.

    The asset route, the allowlist and the security headers are the shipped ones -- a fixture that
    served the artwork itself would prove nothing about the route.
    """
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(_Context("acct-1", "org-acme")),
            organizations=_StubOrganizations(
                [_organization("org-acme", ORGANIZATION_NAME)]
            ),
            records=_StubRecords(),
            isolation=_StubIsolation(),
        ),
        clock=lambda: NOW,
    )
    return app


def _detail_app() -> FastAPI:
    """The same shipped routes, wired so analysis detail renders.

    Detail needs the provenance read and the artifact handoff (`FR-049`); without them the address
    404s and a navigation would watch a page that never placed the artwork. These are the stubs
    `test_r807_shell_quality.py` measures the `analysis` surface through, so "the detail surface"
    here is the one the shell's quality matrix already renders.
    """
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_QualityResolver(),
            organizations=_QualityOrganizations(memberships=True),
            invitations=_StubInvitations(),
            records=_QualityRecords(),
            isolation=_QualityIsolation(),
            provenance=_StubProvenance(),
            bridge=_StubBridge(),
            comparisons=_StubComparisons(),
            decisions=_StubDecisions(),
        ),
        clock=lambda: QUALITY_NOW,
    )
    return app


#: Each placing surface: its address under `/app/{language}`, the app that renders it, and the
#: handoff §09 row the browser must resolve -- band height, focal point, mirrored focal point.
_PLACING_SURFACES = {
    "overview": ("/org-acme/overview", _app, ("238px", "62% 46%", "38% 46%")),
    "analysis": ("/org-acme/analyses/run-a", _detail_app, ("210px", "64% 46%", "36% 46%")),
}


@contextmanager
def _origin(build: Callable[[], FastAPI] = _app) -> Iterator[str]:
    """The application on a loopback port, torn down whatever happens."""
    import uvicorn

    listener = _listener()
    port = int(listener.getsockname()[1])
    server = uvicorn.Server(
        uvicorn.Config(build(), host="127.0.0.1", port=port, log_level="warning")
    )
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
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
        listener.close()


@needs_chromium
class TestTheShippedOriginServesTheArtwork:
    """The browser asks this origin for the artwork and is handed the audited bytes."""

    @pytest.mark.parametrize("file_name", HERO_FILES)
    def test_the_browser_fetches_the_derivative_over_the_wire(
        self, file_name: str
    ) -> None:
        """Status, media type and bytes, all read from the response the browser received.

        The digest is the assertion that cannot be faked by a route that 200s with the wrong
        file: a placeholder, a stale copy or an HTML error page all fail it.
        """
        from playwright.sync_api import sync_playwright

        from tests.test_r811_shell_accessibility import _launch_chromium

        with _origin() as origin, sync_playwright() as playwright:
            browser = _launch_chromium(playwright)
            try:
                request = browser.new_context().request
                response = request.get(f"{origin}{SHELL_ASSETS}/{file_name}")

                assert response.status == 200, (
                    f"{file_name} -> {response.status} from a real origin"
                )
                assert response.headers["content-type"].startswith(
                    HERO_MEDIA_TYPES[file_name]
                )
                assert (
                    hashlib.sha256(response.body()).hexdigest()
                    == HERO_DIGESTS[file_name]
                )
            finally:
                browser.close()

    def test_the_supplied_png_is_not_reachable_from_the_origin(self) -> None:
        """`FR-215` over the wire, not only in the allowlist dict."""
        from playwright.sync_api import sync_playwright

        from tests.test_r811_shell_accessibility import _launch_chromium

        with _origin() as origin, sync_playwright() as playwright:
            browser = _launch_chromium(playwright)
            try:
                request = browser.new_context().request

                assert (
                    request.get(f"{origin}{SHELL_ASSETS}/khepri-hero.png").status == 404
                )
            finally:
                browser.close()

    @pytest.mark.parametrize("language", ["en", "ar"])
    @pytest.mark.parametrize("surface", sorted(_PLACING_SURFACES))
    def test_the_placing_surface_makes_the_browser_fetch_the_artwork(
        self, surface: str, language: str
    ) -> None:
        """`U1` slice 11's central claim, read from the wire rather than from the markup, on
        each surface that places the artwork: the overview and analysis detail.

        The in-process tests prove the template *names* the address. They cannot prove a browser
        rendering that page issues the request and is answered -- which is the whole `#489` lesson
        the font module records: a surface can name an asset that never arrives and look fine,
        because nothing falls over when an image 404s.

        So this navigates to the real overview surface on a real origin and asserts the browser
        requested a hero derivative and got a 200. The WebP and the JPEG are both acceptable: the
        `<picture>` element exists precisely so the browser picks, and pinning which one Chromium
        chooses would assert a browser's codec support rather than this slice's work.

        It then reads the band's minimum height -- the band grows with the copy it carries since
        `U1` slice 12 -- and the image's focal point **as the browser computed them**. The
        stylesheet tests read CSS text, and a modifier that loses the cascade -- equal
        specificity, wrong source order -- passes every one of them while the page renders the
        other surface's row. Only the computed value sees that.
        """
        from playwright.sync_api import sync_playwright

        from khepri.rca.session_cookie import SESSION_COOKIE
        from tests.test_r811_shell_accessibility import _launch_chromium

        path, build, (height, focal, mirrored) = _PLACING_SURFACES[surface]
        with _origin(build) as origin, sync_playwright() as playwright:
            browser = _launch_chromium(playwright)
            try:
                context = browser.new_context()
                context.add_cookies(
                    [{"name": SESSION_COOKIE, "value": "a-session-token", "url": origin}]
                )
                page = context.new_page()
                seen: list[tuple[str, int]] = []
                page.on("response", lambda r: seen.append((r.url, r.status)))

                address = f"{origin}/app/{language}{path}"
                landed = page.goto(address, wait_until="load")
                assert landed is not None and landed.status == 200, (
                    f"{address} -> {landed.status if landed else 'no response'}"
                )

                hero = [
                    (url, status)
                    for url, status in seen
                    if any(name in url for name in HERO_FILES)
                ]

                assert hero, f"the {surface} surface requested no hero derivative: {seen}"
                assert all(status == 200 for _, status in hero), hero

                resolved = page.evaluate(
                    """() => [
                        getComputedStyle(document.querySelector('.hero-band')).minHeight,
                        getComputedStyle(
                            document.querySelector('.hero-band__image')
                        ).objectPosition,
                        getComputedStyle(
                            document.querySelector('.hero-band__image')
                        ).transform,
                    ]"""
                )
                expected = mirrored if language == "ar" else focal
                assert resolved[:2] == [height, expected], resolved
                # Crop only: the artwork itself is never mirrored, in either direction.
                assert resolved[2] == "none", resolved
            finally:
                browser.close()

    def test_an_image_element_actually_decodes_the_artwork(self) -> None:
        """Fetched is not the same as usable: a truncated or mislabelled image 200s and then
        fails to decode. This loads it as an `Image` and reads the dimensions the browser
        decoded, which is the artwork being genuinely renderable at the shell's address."""
        from playwright.sync_api import sync_playwright

        from tests.test_r811_shell_accessibility import _launch_chromium

        with _origin() as origin, sync_playwright() as playwright:
            browser = _launch_chromium(playwright)
            try:
                page = browser.new_context().new_page()
                page.goto(f"{origin}{SHELL_ASSETS}/{HERO_JPEG_FILE}", wait_until="load")
                size = page.evaluate(
                    """(url) => new Promise((resolve, reject) => {
                        const image = new Image();
                        image.onload = () => resolve(
                            [image.naturalWidth, image.naturalHeight]
                        );
                        image.onerror = () => reject(new Error('decode failed'));
                        image.src = url;
                    })""",
                    f"{origin}{SHELL_ASSETS}/{HERO_JPEG_FILE}",
                )

                assert size == [1400, 900]
            finally:
                browser.close()
