"""Public legal route framework (`LEGAL1-01`, RCA-003 FR-062--FR-080).

This deliberately proves the framework's fail-closed publication state, not substantive legal
content. The later LEGAL1 slices can publish a page only after their own authority and verified
inputs are present.
"""

from __future__ import annotations

import re
from html import unescape
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.local import wiring as local_wiring
from khepri.runtime.legal_api import (
    LEGAL_PAGES,
    LEGAL_PREFIX,
    LEGAL_PUBLICATIONS,
    LegalPublication,
    add_legal_routes,
)

PAGES = {
    "privacy-policy": ("Privacy Policy", "سياسة الخصوصية"),
    "data-protection": ("Data Protection", "حماية البيانات"),
    "terms-and-conditions": ("Terms and Conditions", "الشروط والأحكام"),
    "contact-us": ("Contact Us", "اتصل بنا"),
    "about-us": ("About Us", "من نحن"),
    "refund-and-void": ("Refund & Void", "حالة الاسترداد والإلغاء"),
}
PUBLICATION_STATUS = {
    "privacy-policy": 503,
    "data-protection": 503,
    "terms-and-conditions": 503,
    "contact-us": 503,
    "about-us": 200,
    "refund-and-void": 200,
}


def _client() -> TestClient:
    app = FastAPI()
    add_legal_routes(app)
    return TestClient(app)


def test_local_web_app_registers_the_public_legal_framework(monkeypatch) -> None:
    """Omitting the public registrar from local wiring leaves browser development at a 404."""
    monkeypatch.setattr(local_wiring, "create_app", lambda **_: FastAPI())
    monkeypatch.setattr(local_wiring, "build_report_services", lambda _: object())
    stack = SimpleNamespace(
        invitations=object(),
        clock=lambda: None,
        factory=object(),
        services=SimpleNamespace(
            intake=object(), deletion=object(), profiling=object(), packages=object()
        ),
    )

    response = TestClient(local_wiring.build_web_app(stack)).get(
        f"{LEGAL_PREFIX}/en/about-us"
    )

    assert response.status_code == 200


def test_unresolved_publication_content_is_not_rendered(monkeypatch) -> None:
    """Publishing a placeholder without verified inputs must fail closed at the route boundary."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "privacy-policy",
        LegalPublication(
            content={
                "en": ("[PLACEHOLDER] privacy policy",),
                "ar": ("سياسة خصوصية",),
            },
            verified_inputs=frozenset(),
        ),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/privacy-policy")

    assert response.status_code == 503
    assert "[PLACEHOLDER]" not in response.text


def test_legally_operative_content_without_verified_inputs_is_not_rendered(
    monkeypatch,
) -> None:
    """A plain-looking document cannot bypass the verified-input publication gate."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "privacy-policy",
        LegalPublication(
            content={"en": ("Unverified legal content",), "ar": ("محتوى غير موثق",)}
        ),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/privacy-policy")

    assert response.status_code == 503
    assert "Unverified legal content" not in response.text


def test_publication_requires_both_language_variants(monkeypatch) -> None:
    """A single-language document cannot cause bilingual routes to drift."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "privacy-policy",
        LegalPublication(
            content={"en": ("English policy",)},
            verified_inputs=frozenset(
                {"operator_identity", "privacy_contact", "effective_date"}
            ),
        ),
    )

    english = _client().get(f"{LEGAL_PREFIX}/en/privacy-policy")
    arabic = _client().get(f"{LEGAL_PREFIX}/ar/privacy-policy")

    assert english.status_code == arabic.status_code == 503
    assert "English policy" not in english.text


def test_data_protection_requires_verified_operator_and_privacy_inputs(monkeypatch) -> None:
    """Bilingual data-protection copy must not bypass its operative publication inputs."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "data-protection",
        LegalPublication(content={"en": ("Safeguards",), "ar": ("ضمانات",)}),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/data-protection")

    assert response.status_code == 503
    assert "Safeguards" not in response.text


def test_required_input_flags_do_not_publish_copy_without_the_verified_values(
    monkeypatch,
) -> None:
    """Privacy cannot publish when asserted input names are absent from both documents."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "privacy-policy",
        LegalPublication(
            content={"en": ("Approved",), "ar": ("معتمد",)},
            verified_inputs=frozenset(
                {"operator_identity", "privacy_contact", "effective_date"}
            ),
        ),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/privacy-policy")

    assert response.status_code == 503
    assert "Approved" not in response.text


def test_verified_required_values_must_appear_in_each_language_variant(monkeypatch) -> None:
    """A complete operative publication renders only values bound into both documents."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "privacy-policy",
        LegalPublication(
            content={
                "en": ("Operator Example; privacy@example.test; effective 2026-01-01",),
                "ar": ("مشغل المثال؛ privacy@example.test؛ تاريخ السريان 2026-01-01",),
            },
            verified_inputs=frozenset(
                {"operator_identity", "privacy_contact", "effective_date"}
            ),
            verified_values={
                "operator_identity": {"en": "Operator Example", "ar": "مشغل المثال"},
                "privacy_contact": {
                    "en": "privacy@example.test",
                    "ar": "privacy@example.test",
                },
                "effective_date": {"en": "2026-01-01", "ar": "2026-01-01"},
            },
        ),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/privacy-policy")

    assert response.status_code == 200
    assert "Operator Example" in response.text


@pytest.mark.parametrize(
    "claim",
    ("ISO 27001", "SOC 2", "PCI DSS", "GDPR compliant", "PDPL compliant"),
)
def test_unverified_certification_or_compliance_claim_is_not_rendered(
    monkeypatch, claim: str
) -> None:
    """A claimed certification without repository evidence must keep the page unavailable."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "privacy-policy",
        LegalPublication(
            content={
                "en": (f"Khepri is {claim}.",),
                "ar": (f"خِبري {claim}.",),
            },
            verified_inputs=frozenset(
                {"operator_identity", "privacy_contact", "effective_date"}
            ),
        ),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/privacy-policy")

    assert response.status_code == 503
    assert claim not in response.text


@pytest.mark.parametrize(
    ("english_claim", "arabic_claim"),
    (
        ("Khepri is HIPAA compliant.", "نسخة عربية مطابقة للمعنى."),
        ("Khepri is certified.", "نسخة عربية مطابقة للمعنى."),
        ("Approved informational copy.", "خِبري متوافق مع HIPAA."),
        ("Approved informational copy.", "خِبري حاصل على شهادة."),
    ),
)
def test_unknown_certification_or_compliance_claim_is_not_rendered(
    monkeypatch, english_claim: str, arabic_claim: str
) -> None:
    """A claim outside the named examples must also require repository evidence."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "about-us",
        LegalPublication(content={"en": (english_claim,), "ar": (arabic_claim,)}),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/about-us")

    assert response.status_code == 503
    assert english_claim not in response.text


def test_neutral_reference_to_an_applicable_legal_framework_is_allowed(monkeypatch) -> None:
    """Naming a framework without claiming compliance must not be treated as certification."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "about-us",
        LegalPublication(
            content={
                "en": ("GDPR may be an applicable legal framework.",),
                "ar": ("قد يكون النظام العام لحماية البيانات إطارًا قانونيًا منطبقًا.",),
            }
        ),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/about-us")

    assert response.status_code == 200
    assert "GDPR may be an applicable legal framework" in response.text


@pytest.mark.parametrize(
    "claim",
    (
        "We provide a 99.9% uptime SLA.",
        "We retain customer data for 30 days.",
        "Khepri is hosted in Egypt.",
        "Khepri is hosted in the United States.",
        "Self-service deletion is available.",
        "We use customer-uploaded data for training.",
        "A public refund window is available.",
    ),
)
def test_unsupported_operational_or_billing_claim_is_not_rendered(
    monkeypatch, claim: str
) -> None:
    """Legal copy cannot introduce unsupported operational or billing commitments."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "about-us",
        LegalPublication(
            content={
                "en": (claim,),
                "ar": ("نسخة عربية مطابقة للمعنى.",),
            }
        ),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/about-us")

    assert response.status_code == 503
    assert claim not in response.text


def test_about_copy_cannot_narrow_khepri_to_a_pharmacy_only_service(monkeypatch) -> None:
    """A pharmacy-only position violates RCA-003's retail-platform requirement."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "about-us",
        LegalPublication(
            content={
                "en": ("Khepri is a pharmacy-only service.",),
                "ar": ("خِبري خدمة صيدليات فقط.",),
            }
        ),
    )

    response = _client().get(f"{LEGAL_PREFIX}/en/about-us")

    assert response.status_code == 503
    assert "pharmacy-only" not in response.text


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


@pytest.mark.parametrize("page, expected_status", PUBLICATION_STATUS.items())
@pytest.mark.parametrize("language", ("en", "ar"))
def test_every_authorized_legal_route_has_its_authorized_publication_state(
    page: str, expected_status: int, language: str
) -> None:
    """A page may publish only when its RCA-003 state is complete and truthful."""
    response = _client().get(f"{LEGAL_PREFIX}/{language}/{page}")

    assert response.status_code == expected_status
    if expected_status == 503:
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


@pytest.mark.parametrize(
    ("page", "english_copy", "arabic_copy"),
    (
        (
            "about-us",
            "Khepri is a governed retail decision platform.",
            "خِبري منصة محكومة لاتخاذ القرارات في قطاع التجزئة.",
        ),
        (
            "refund-and-void",
            "No general public self-service refund policy currently applies.",
            "لا تسري حاليًا سياسة عامة للاسترداد الذاتي للجمهور.",
        ),
    ),
)
def test_published_pages_have_equivalent_bilingual_content(
    page: str, english_copy: str, arabic_copy: str
) -> None:
    """A published language variant must carry its own approved substantive copy."""
    client = _client()
    english = client.get(f"{LEGAL_PREFIX}/en/{page}")
    arabic = client.get(f"{LEGAL_PREFIX}/ar/{page}")

    assert english.status_code == arabic.status_code == 200
    assert english_copy in english.text
    assert arabic_copy in arabic.text


def test_refund_status_does_not_introduce_future_billing_mechanics() -> None:
    """The status page may not publish a third billing assertion before billing authority exists."""
    response = _client().get(f"{LEGAL_PREFIX}/en/refund-and-void")

    assert "Detailed refund or void mechanics" not in response.text


def test_refund_status_requires_both_authorized_bilingual_statements(monkeypatch) -> None:
    """A partial refund status cannot publish without the private-fees statement."""
    monkeypatch.setitem(
        LEGAL_PUBLICATIONS,
        "refund-and-void",
        LegalPublication(
            content={
                "en": ("No general public self-service refund policy currently applies.",),
                "ar": ("لا تسري حاليًا سياسة عامة للاسترداد الذاتي للجمهور.",),
            }
        ),
    )

    english = _client().get(f"{LEGAL_PREFIX}/en/refund-and-void")
    arabic = _client().get(f"{LEGAL_PREFIX}/ar/refund-and-void")

    assert english.status_code == arabic.status_code == 503
    assert "No general public self-service refund policy" not in english.text
    assert "لا تسري حاليًا سياسة عامة للاسترداد الذاتي للجمهور." not in arabic.text


@pytest.mark.parametrize("language", ("en", "ar"))
def test_footer_links_only_to_destinations_that_answer_successfully(language: str) -> None:
    """A visible legal navigation link must not lead to an unavailable page."""
    client = _client()
    response = client.get(f"{LEGAL_PREFIX}/{language}/about-us")
    destinations = re.findall(rf'href="({LEGAL_PREFIX}/{language}/[^"]+)"', response.text)

    assert destinations
    assert all(client.get(destination).status_code == 200 for destination in destinations)


def test_legal_routes_render_without_or_with_an_authenticated_cookie() -> None:
    """Accidentally applying the commercial session gate changes this public response."""
    client = _client()
    anonymous = client.get(f"{LEGAL_PREFIX}/en/about-us")
    client.cookies.set("khepri_session", "customer-session-that-must-not-matter")
    cookie_bearing = client.get(f"{LEGAL_PREFIX}/en/about-us")

    assert anonymous.status_code == cookie_bearing.status_code == 200
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
def test_legal_framework_preserves_browser_security_and_links_only_to_live_pages(
    page: str, language: str
) -> None:
    """The public footer must preserve CSP and exclude unavailable destinations."""
    response = _client().get(f"{LEGAL_PREFIX}/{language}/{page}")

    assert response.headers["Content-Security-Policy"] == (
        "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
        "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'"
    )
    assert response.headers["Cache-Control"] == "public, max-age=0, must-revalidate"
    assert "<script" not in response.text
    assert "style=" not in response.text
    assert "<footer" in response.text
    assert f'href="{LEGAL_PREFIX}/{language}/about-us"' in response.text
    assert f'href="{LEGAL_PREFIX}/{language}/refund-and-void"' in response.text
    for unavailable in (
        "privacy-policy",
        "data-protection",
        "terms-and-conditions",
        "contact-us",
    ):
        assert f'href="{LEGAL_PREFIX}/{language}/{unavailable}"' not in response.text
