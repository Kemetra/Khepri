"""A real journey page in a real browser, with only the API stubbed.

The `set_content` tests lift a function out of a served module and run it in
isolation, which cannot show what a page *does* across requests -- how many
uploads a second submit sends, or what `load()` renders from a profile. This
serves the actual page and its actual modules from the journey app through
`page.route`, on one origin so the modules' relative `fetch` and XHR resolve,
and answers `/api/` from a caller-supplied handler that also records each call.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

from playwright.sync_api import Browser, Page, Route

from tests.test_rra_journey_api import client

ORIGIN = "http://journey.test"

#: `(method, path) -> (status, JSON body or None)`.
ApiHandler = Callable[[str, str], tuple[int, object]]


@dataclass
class ApiCalls:
    """Every API request the page made, in order, as `(method, path)`."""

    made: list[tuple[str, str]] = field(default_factory=list)
    #: The JSON body of each call that sent one, keyed by `(method, path)`, in order.
    bodies: dict[tuple[str, str], list[object]] = field(default_factory=dict)

    def count(self, method: str, path: str) -> int:
        return self.made.count((method, path))


def open_journey_page(
    browser: Browser,
    *,
    language: str,
    step: str,
    api: ApiHandler,
) -> tuple[Page, ApiCalls]:
    """Load `/beta/{language}/{step}` with its real assets and a stubbed API."""
    journey = client()
    calls = ApiCalls()

    def handle(route: Route) -> None:
        path = urlparse(route.request.url).path
        if path.startswith("/api/"):
            method = route.request.method
            calls.made.append((method, path))
            if route.request.headers.get("content-type", "").startswith("application/json"):
                sent = json.loads(route.request.post_data or "null")
                calls.bodies.setdefault((method, path), []).append(sent)
            status, body = api(method, path)
            route.fulfill(
                status=status,
                content_type="application/json",
                body="" if body is None else json.dumps(body),
            )
            return
        served = journey.get(path)
        route.fulfill(
            status=served.status_code,
            content_type=served.headers["content-type"],
            body=served.content,
        )

    page = browser.new_page()
    page.route(f"{ORIGIN}/**", handle)
    page.goto(f"{ORIGIN}/beta/{language}/{step}")
    return page, calls
