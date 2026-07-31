"""The pinned-Chromium adapter of `pdf.PagePrinter`.

**The only module here that needs a browser.** It is imported by nothing else in
this package -- not by `rendering/__init__.py` -- so importing the rendering
package, or testing the PDF surface, never requires a Chromium download. That is
not merely a convenience for a constrained checkout: it is what makes the surface
verifiable at all. Everything about the printed page that can be asserted without
a browser is asserted against a fake, and what is left over is exactly this file.

**Why `set_content` and not a URL.** The document is already complete: the
stylesheet is inlined, the fonts are inlined, and there is no script. Serving it
over a loopback HTTP server to hand Chromium a URL would add a listening socket
and an ordering problem, and buy nothing. Every request the page could still
attempt is aborted outright, so a template that grew an external reference fails
loudly here instead of silently making the report depend on a network.

**Why the caller owns the browser.** A bounded worker prints many reports and
should launch Chromium once; a test wants one browser for a handful of pages.
Neither is served by a renderer that launches per call, so the adapter takes a
running browser and `launch_chromium` is the convenience that supplies one.

**Why `launch_chromium` is not merely a convenience.** It is also the one place
`KHEPRI-DEC-007`'s required launch flag is applied, so a caller that builds its own
browser owns `LAUNCH_ARGS` itself. On Fargate a browser launched without them
crashes while printing instead of reporting a memory limit, which is why the flag
lives beside the print options rather than at a call site.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Browser, sync_playwright

from khepri.rra.rendering.pdf import PrintablePage

# The print settings this surface is defined by. `tagged` is the requirement
# RRA-006 states outright; the rest make the PDF match the print stylesheet
# instead of Chromium's defaults.
PDF_OPTIONS: dict[str, bool] = {
    "tagged": True,
    "outline": True,
    "prefer_css_page_size": True,
    "print_background": True,
}

# `KHEPRI-DEC-007` requires this flag and calls it a correctness requirement rather
# than a tuning flag. Fargate fixes `/dev/shm` at 64 MiB and does not support
# `linuxParameters.sharedMemorySize`, which is an EC2-launch-type parameter.
# Chromium's default shared-memory use exceeds 64 MiB while rendering a paginated
# document and fails as a renderer crash rather than as a memory limit, so the
# failure would be diagnosed as anything but the limit it is. The flag moves those
# allocations onto the task's ephemeral storage, which is why the worker's 40 GiB and
# this line are one decision: the storage is sized to absorb what the flag displaces.
LAUNCH_ARGS: tuple[str, ...] = ("--disable-dev-shm-usage",)


class ChromiumPagePrinter:
    """Print one prepared document to a tagged PDF with a running Chromium."""

    def __init__(self, *, browser: Browser) -> None:
        self._browser = browser

    @property
    def browser(self) -> Browser:
        return self._browser

    def print_to_pdf(self, page: PrintablePage) -> bytes:
        tab = self._browser.new_page()
        try:
            # Nothing on this page is meant to be fetched. Aborting every request
            # turns a template that grew an external reference into a visible
            # failure rather than a quiet dependency on a network.
            tab.route("**/*", lambda route: route.abort())
            tab.set_content(page.document, wait_until="load")
            # The faces are `data:` URIs and load without a network, but they
            # still load *asynchronously*. Printing before they are ready
            # rasterises the first paint, which used a fallback face -- and for
            # the Arabic page a fallback face is the failure this slice exists to
            # prevent.
            tab.evaluate("() => document.fonts.ready")
            return tab.pdf(**PDF_OPTIONS)
        finally:
            tab.close()


@contextmanager
def launch_chromium(*, headless: bool = True) -> Iterator[ChromiumPagePrinter]:
    """One Chromium, launched and closed around a batch of printing."""
    with sync_playwright() as play:
        browser = play.chromium.launch(headless=headless, args=list(LAUNCH_ARGS))
        try:
            yield ChromiumPagePrinter(browser=browser)
        finally:
            browser.close()
