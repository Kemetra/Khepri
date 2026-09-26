"""A same-origin shell form is admitted when Chromium sends `Origin: null` (#598).

Shell pages carry `Referrer-Policy: no-referrer` (`SECURITY_HEADERS`). Under that policy Chromium
serializes the `Origin` of a form-navigation POST as `null`, while still sending
`Sec-Fetch-Site: same-origin`. `require_same_origin` admitted only an absent or exact origin, so
every shell form a real browser submitted -- starting an analysis, deleting a version, pins,
invitations, and the #594 organization switch -- answered 403. The journey never hit it: it posts
with `fetch()`, whose CORS-mode requests always carry the real origin. The route tests never hit it
either, because their clients set `Origin` by hand.

**The fix admits `null` only beside `Sec-Fetch-Site: same-origin`.** That header is set by the
browser and cannot be written by a page, so a cross-site form still carries `cross-site` and is
refused, and an unmarked `null` with a cookie is still refused.

**One case runs a real browser against a real server** on a loopback port, clicking a chooser row
and following the redirect. It is the only kind of test that can see what Chromium actually sends.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
import uvicorn
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlOrganizationStore
from khepri.rra.journey.security import require_same_origin
from khepri.runtime.wiring import build_web_app
from tests.i594_support import RCA_COOKIE, Deployed, deployed_fixture  # noqa: F401
from tests.w104_support import NOW

HOST = "127.0.0.1"


def _request(headers: dict[str, str]) -> Request:
    raw = [(name.lower().encode(), value.encode()) for name, value in headers.items()]
    scope = {
        "type": "http",
        "method": "POST",
        "scheme": "https",
        "server": ("shell.example", 443),
        "path": "/app/en/org/switch",
        "headers": [(b"host", b"shell.example"), (b"cookie", b"khepri_session=t"), *raw],
    }
    return Request(scope)


class TestTheSameOriginCheck:
    def test_a_null_origin_marked_same_origin_is_admitted(self) -> None:
        require_same_origin(_request({"Origin": "null", "Sec-Fetch-Site": "same-origin"}))

    @pytest.mark.parametrize(
        "headers",
        [
            {"Origin": "null", "Sec-Fetch-Site": "cross-site"},
            {"Origin": "null", "Sec-Fetch-Site": "same-site"},
            {"Origin": "null", "Sec-Fetch-Site": "none"},
            {"Origin": "null"},
            {"Origin": "https://evil.example", "Sec-Fetch-Site": "same-origin"},
        ],
        ids=["null cross-site", "null same-site", "null none", "null unmarked", "foreign origin"],
    )
    def test_every_other_null_or_foreign_origin_is_refused(self, headers: dict) -> None:
        with pytest.raises(HTTPException) as refused:
            require_same_origin(_request(headers))

        assert refused.value.status_code == 403


@contextmanager
def _serving(app: FastAPI) -> Iterator[str]:
    sock = socket.socket()
    sock.bind((HOST, 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    try:
        yield f"http://{HOST}:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)


@pytest.mark.browser
def test_a_real_browser_switches_organization_from_the_chooser(deployed: Deployed) -> None:
    """Chromium, the deployed app, a revoked membership, one click on the remaining row."""
    from playwright.sync_api import Error, sync_playwright

    other = (
        OrganizationService(SqlOrganizationStore(deployed.stack.factory))
        .create_organization("Globex", deployed.member_account, now=NOW)
        .organization_id
    )
    token = deployed.rca_token(deployed.member_account)
    deployed.revoke_member()

    with _serving(build_web_app(deployed.stack)) as base, sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            context = browser.new_context()
            context.add_cookies([{"name": RCA_COOKIE, "value": token, "url": base}])
            page = context.new_page()
            page.goto(f"{base}/app/en/")
            with page.expect_navigation():
                page.click(f'form[action="/app/en/{other}/switch"] button')
            landed = page.url
            body = page.content()
        finally:
            browser.close()

    assert landed == f"{base}/app/en/{other}/overview", body[:300]
