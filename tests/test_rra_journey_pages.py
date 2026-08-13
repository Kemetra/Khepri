from __future__ import annotations

from tests.test_rra_journey_api import client


def test_every_journey_page_has_a_secure_bilingual_document_shell() -> None:
    test = client()
    for language, direction in (("en", "ltr"), ("ar", "rtl")):
        for step in ("upload", "review", "processing", "report"):
            response = test.get(f"/beta/{language}/{step}")
            assert response.status_code == 200
            assert f'<html lang="{language}" dir="{direction}">' in response.text
            assert response.text.count("<h1") == 1
            assert '<main id="main-content"' in response.text
            assert 'href="#main-content"' in response.text
            assert "/beta/assets/journey.css" in response.text
            assert "http://" not in response.text
            assert "https://" not in response.text
            assert "onclick=" not in response.text
            assert response.headers["cache-control"] == "private, no-store"
            assert response.headers["content-security-policy"].startswith("default-src 'none'")


def test_entry_route_is_the_upload_bootstrap_and_unknown_language_is_absent() -> None:
    test = client()
    assert test.get("/beta/en").status_code == 200
    assert 'data-step="upload"' in test.get("/beta/en").text
    assert test.get("/beta/fr/upload").status_code == 404


def test_only_allowlisted_local_assets_are_served() -> None:
    test = client()
    css = test.get("/beta/assets/journey.css")
    assert css.status_code == 200
    assert "immutable" in css.headers["cache-control"]
    typeface = test.get("/beta/assets/NotoSansArabic-Regular-arabic.woff2")
    assert typeface.status_code == 200
    assert typeface.headers["content-type"] == "font/woff2"
    assert test.get("/beta/assets/../routes.py").status_code == 404
