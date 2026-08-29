"""Public legal route framework (`LEGAL1-01`, RCA-003 FR-062--FR-080).

This deliberately proves the framework's fail-closed publication state, not substantive legal
content. The later LEGAL1 slices can publish a page only after their own authority and verified
inputs are present.
"""

from __future__ import annotations

from html import unescape

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.runtime.legal_api import LEGAL_PAGES, LEGAL_PREFIX, add_legal_routes

PAGES = {
    "privacy-policy": ("Privacy Policy", "سياسة الخصوصية"),
    "data-protection": ("Data Protection", "حماية البيانات"),
    "terms-and-conditions": ("Terms and Conditions", "الشروط والأحكام"),
    "contact-us": ("Contact Us", "اتصل بنا"),
    "about-us": ("About Us", "من نحن"),
    "refund-and-void": ("Refund & Void", "حالة الاسترداد والإلغاء"),
}


def _client() -> TestClient:
    app = FastAPI()
    add_legal_routes(app)
    return TestClient(app)


def test_the_legal_inventory_is_limited_to_the_six_authorized_destinations() -> None:
    """Publishing a seventh legal destination expands RCA-003's closed public surface set."""
    assert frozenset(
        {
            "privacy-policy",
            "data-protection",
            "terms-and-conditions",
            "contact-us",
            "about-us",
            "refund-and-void",
        }
    ) == LEGAL_PAGES


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("language", ("en", "ar"))
def test_every_authorized_legal_route_is_public_and_fail_closed(
    page: str, language: str
) -> None:
    """Removing an authorized address or publishing invented legal copy breaks this test."""
    response = _client().get(f"{LEGAL_PREFIX}/{language}/{page}")

    assert response.status_code == 503
    assert (
        "This page is not currently published." in response.text
        or "هذه الصفحة غير منشورة حاليًا." in response.text
    )
    assert "khepri_session" not in response.text
    assert "organization" not in response.text.lower()


@pytest.mark.parametrize("page, titles", PAGES.items())
def test_legal_route_keeps_page_identity_and_language_switch_at_parity(
    page: str, titles: tuple[str, str]
) -> None:
    """A language-specific route, title, or switch target drifting from its peer breaks parity."""
    client = _client()
    english = client.get(f"{LEGAL_PREFIX}/en/{page}")
    arabic = client.get(f"{LEGAL_PREFIX}/ar/{page}")

    assert titles[0] in unescape(english.text)
    assert titles[1] in unescape(arabic.text)
    assert 'lang="en"' in english.text
    assert 'lang="ar" dir="rtl"' in arabic.text
    assert f'href="{LEGAL_PREFIX}/ar/{page}"' in english.text
    assert f'href="{LEGAL_PREFIX}/en/{page}"' in arabic.text


def test_legal_routes_render_without_or_with_an_authenticated_cookie() -> None:
    """Accidentally applying the commercial session gate changes this public response."""
    client = _client()
    anonymous = client.get(f"{LEGAL_PREFIX}/en/about-us")
    client.cookies.set("khepri_session", "customer-session-that-must-not-matter")
    cookie_bearing = client.get(f"{LEGAL_PREFIX}/en/about-us")

    assert anonymous.status_code == cookie_bearing.status_code == 503
    assert anonymous.text == cookie_bearing.text


@pytest.mark.parametrize(
    "path",
    (
        "/legal/en/not-a-page",
        "/legal/de/privacy-policy",
        "/legal/en/privacy-policy/extra",
    ),
)
def test_unknown_legal_paths_use_ordinary_public_not_found(path: str) -> None:
    """An authenticated-style refusal for an unknown legal path leaks boundary semantics."""
    response = _client().get(path)

    assert response.status_code == 404
    assert "organization" not in response.text.lower()
    assert "session" not in response.text.lower()


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("language", ("en", "ar"))
def test_legal_framework_preserves_browser_security_without_footer_links(
    page: str, language: str
) -> None:
    """Weakening CSP or rendering LEGAL1-05 navigation in this slice breaks the public boundary."""
    response = _client().get(f"{LEGAL_PREFIX}/{language}/{page}")

    assert response.headers["Content-Security-Policy"] == (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'"
    )
    assert response.headers["Cache-Control"] == "public, max-age=0, must-revalidate"
    assert "<script" not in response.text
    assert "style=" not in response.text
    assert "<footer" not in response.text
