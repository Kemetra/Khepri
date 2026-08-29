"""Bilingual page-status copy for the public legal framework (`LEGAL1-01`)."""

from __future__ import annotations

_EN = {
    "product": "Khepri",
    "skip": "Skip to main content",
    "language": "العربية",
    "language_code": "ar",
    "language_navigation": "Language",
    "unpublished_title": "This page is not currently published.",
    "unpublished_intro": (
        "This legal information is not currently available for public publication."
    ),
}

_AR = {
    "product": "خِبري",
    "skip": "تخطَّ إلى المحتوى الرئيسي",
    "language": "English",
    "language_code": "en",
    "language_navigation": "اللغة",
    "unpublished_title": "هذه الصفحة غير منشورة حاليًا.",
    "unpublished_intro": "هذه المعلومات القانونية غير متاحة حاليًا للنشر العام.",
}

if set(_EN) != set(_AR):  # pragma: no cover -- import-time parity guard
    missing = set(_EN).symmetric_difference(_AR)
    raise RuntimeError(f"LEGAL_COPY is not at language parity: {sorted(missing)}")

LEGAL_COPY = {"en": _EN, "ar": _AR}

LEGAL_PAGE_TITLES = {
    "en": {
        "privacy-policy": "Privacy Policy",
        "data-protection": "Data Protection",
        "terms-and-conditions": "Terms and Conditions",
        "contact-us": "Contact Us",
        "about-us": "About Us",
        "refund-and-void": "Refund & Void",
    },
    "ar": {
        "privacy-policy": "سياسة الخصوصية",
        "data-protection": "حماية البيانات",
        "terms-and-conditions": "الشروط والأحكام",
        "contact-us": "اتصل بنا",
        "about-us": "من نحن",
        "refund-and-void": "حالة الاسترداد والإلغاء",
    },
}

if set(LEGAL_PAGE_TITLES["en"]) != set(LEGAL_PAGE_TITLES["ar"]):  # pragma: no cover
    missing = set(LEGAL_PAGE_TITLES["en"]).symmetric_difference(LEGAL_PAGE_TITLES["ar"])
    raise RuntimeError(f"LEGAL_PAGE_TITLES is not at language parity: {sorted(missing)}")

DIRECTIONS = {"en": "ltr", "ar": "rtl"}

__all__ = ["DIRECTIONS", "LEGAL_COPY", "LEGAL_PAGE_TITLES"]
