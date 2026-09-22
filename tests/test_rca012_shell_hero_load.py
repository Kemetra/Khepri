"""`RCA-012`: a real browser, from a real origin, actually loads the shell's hero artwork.

**Why this file exists beside `test_rca012_shell_hero_artwork.py`.** That module proves the route
serves the bytes through `TestClient` and file scans. `RCA-012` §Verification asks for more,
naming the discipline `test_rca011_shell_font_load.py` established: an allowlist entry naming a
file the shipped image does not carry passes every in-process test and 404s in production. Only a
real HTTP origin can tell those two apart.

**Why this is a direct fetch and not a page navigation.** The font module could navigate to a
surface and watch the wire, because a stylesheet `@font-face` links the file and the browser goes
and gets it. Nothing links the artwork yet -- this is the asset slice, and placing the hero is
`RCA-010`'s presentation slice, which `test_rca012_shell_hero_artwork.py` asserts has not happened.
A navigation test here would therefore watch for a request no page makes, and pass whether or not
the route worked.

So the browser fetches the shell's own address directly and the assertions read the response: the
status, the `Content-Type` the browser was actually handed, and the SHA-256 of the bytes that came
over the wire against the audited manifest. That is the claim this file can honestly make -- the
shipped application, on a real socket, serves the audited artwork at the address a stylesheet will
name -- and it is exactly the claim the in-process module cannot.
"""

from __future__ import annotations

import hashlib
import socket
import threading
import time
from collections.abc import Iterator
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


@contextmanager
def _origin() -> Iterator[str]:
    """The application on a loopback port, torn down whatever happens."""
    import uvicorn

    listener = _listener()
    port = int(listener.getsockname()[1])
    server = uvicorn.Server(
        uvicorn.Config(_app(), host="127.0.0.1", port=port, log_level="warning")
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
