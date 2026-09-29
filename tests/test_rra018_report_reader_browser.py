"""`RRA-018` in a real browser: the report opens in place, under its wall, and reaches its evidence.

`RRA-018` §Verification asks for three things only a browser can show:

1. **FR-240.** The web report renders as a page rather than starting a download. Chromium
   decides that from `Content-Disposition`, so an in-process header assertion shows the header
   and not the behaviour.
2. **FR-241 and FR-251 together.** Following a section's evidence link under the exact policy
   reaches the evidence surface **with the beta session**. The session cookie is
   `SameSite=Strict`, and a sandboxed page without `allow-same-origin` has an opaque origin.
   Whether the browser then sends the cookie is the browser's decision, so the test asks it.
3. **The wall holds when escaping does not.** A stored document carrying a live `<script>` stands
   in for an escaping defect. The policy, not the autoescaper, is what must stop it.

**How the origin is built.** Every request to a fake HTTPS origin is answered by the real report
API through `page.route`, as `tests/journey_routed_page.py` does for the journey. The HTTPS origin
lets Chromium hold the `Secure` session cookie. The forwarder passes on **only the cookie header
the browser sent**, and the in-process client's own cookie jar is cleared after redeeming. So
"the evidence page arrived with the session" means the browser carried it, not the test client.
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

from khepri.rra.artifact_publication import ArtifactDocument
from khepri.rra.bundle import ReportBundle
from khepri.rra.narrative import LANGUAGE_ENGLISH
from khepri.rra.rendering.html import HtmlReportRenderer
from tests.test_rra006_bundle import package
from tests.test_rra006_pdf_surface import chromium_available
from tests.test_rra006_report_artifact_api import _harness, _redeem

ORIGIN = "https://report.test"
HTML = "text/html; charset=utf-8"
REPORT = f"{ORIGIN}/api/v1/beta/reports/job_alpha/surfaces/web/en"
HOSTILE = f"{ORIGIN}/api/v1/beta/reports/job_hostile/surfaces/web/en"

needs_chromium = pytest.mark.skipif(
    not chromium_available(),
    reason="the pinned Chromium is not installed; run `playwright install chromium`",
)

#: A stored page as an escaping defect would leave it: the script is live markup, not text.
_HOSTILE_PAGE = (
    '<!doctype html><html lang="en"><head><meta charset="utf-8">'
    "<title>Retail report</title></head><body><h1>Retail report</h1>"
    "<script>document.title = 'RAN'</script></body></html>"
)


def _served() -> tuple[object, str, list[tuple[str, bool]]]:
    """The report API holding the golden report, and a log of what each request carried."""
    client, invitations, artifacts = _harness()
    session = _redeem(client, invitations)
    client.cookies.clear()
    surface = HtmlReportRenderer().render_html(ReportBundle.of(package()))
    held = {
        ("job_alpha", "web_business_en"): (
            surface.documents[LANGUAGE_ENGLISH],
            "khepri-report.html",
        ),
        ("job_alpha", "web_evidence_en"): (
            surface.evidence[LANGUAGE_ENGLISH],
            "khepri-evidence.html",
        ),
        ("job_hostile", "web_business_en"): (_HOSTILE_PAGE, "khepri-report.html"),
    }
    for (job, kind), (document, file_name) in held.items():
        artifacts.held[(session, job, kind)] = ArtifactDocument(
            content=document.encode("utf-8"), media_type=HTML, file_name=file_name
        )
    return client, session, []


def _forward(client: object, log: list[tuple[str, bool]]):
    def handle(route) -> None:
        request = route.request
        cookie = request.all_headers().get("cookie", "")
        path = urlparse(request.url).path
        log.append((path, "khepri_beta_session=" in cookie))
        response = client.get(path, headers={"cookie": cookie} if cookie else {})  # type: ignore[attr-defined]
        route.fulfill(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.content,
        )

    return handle


def _open(playwright: object, session: str):
    from tests.test_r811_shell_accessibility import _launch_chromium

    browser = _launch_chromium(playwright)
    context = browser.new_context(accept_downloads=False)  # type: ignore[attr-defined]
    context.add_cookies(
        [
            {
                "name": "khepri_beta_session",
                "value": session,
                "url": ORIGIN,
                "secure": True,
                "httpOnly": True,
                "sameSite": "Strict",
            }
        ]
    )
    return browser, context


@pytest.mark.browser
@needs_chromium
def test_the_report_opens_in_place_and_its_evidence_link_keeps_the_session() -> None:
    from playwright.sync_api import sync_playwright

    client, session, log = _served()
    with sync_playwright() as playwright:
        browser, context = _open(playwright, session)
        try:
            page = context.new_page()
            refused: list[str] = []
            page.on(
                "console",
                lambda message: (
                    refused.append(message.text) if "Refused to" in message.text else None
                ),
            )
            page.route(f"{ORIGIN}/**", _forward(client, log))

            page.goto(REPORT, wait_until="load")
            assert page.locator("h1").first.inner_text() == "Retail report"
            assert page.locator('[data-component="refused-results"]').count() == 1

            with page.expect_navigation(wait_until="load"):
                page.locator('[data-component="section-evidence-link"]').first.click()

            assert page.url.endswith("/surfaces/evidence/en#evidence-section-overview")
            # The session is checked before the page's heading: without `allow-same-origin`
            # the navigation arrives with no cookie and the page is the JSON refusal, so the
            # heading never appears -- measured by mutating the policy, which fails here.
            evidence = [carried for path, carried in log if path.endswith("/evidence/en")]
            assert evidence == [True], f"the evidence request lost the session: {log}"
            assert page.locator("h1").first.inner_text() == "Technical evidence"
            assert refused == [], f"the policy refused part of the genuine report: {refused}"
        finally:
            browser.close()  # type: ignore[attr-defined]


@pytest.mark.browser
@needs_chromium
def test_a_live_script_in_a_stored_report_does_not_run() -> None:
    from playwright.sync_api import sync_playwright

    client, session, log = _served()
    with sync_playwright() as playwright:
        browser, context = _open(playwright, session)
        try:
            page = context.new_page()
            page.route(f"{ORIGIN}/**", _forward(client, log))

            page.goto(HOSTILE, wait_until="load")

            assert page.locator("h1").first.inner_text() == "Retail report", "not served"
            assert page.title() == "Retail report", "the stored script ran under the policy"
        finally:
            browser.close()  # type: ignore[attr-defined]
