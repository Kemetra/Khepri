"""Bilingual copy for the commercial shell (`R8-02`).

Separate from `khepri.rra.journey.copy` rather than an extension of it. The shell is `RCA`'s and
the journey is `RRA`'s, and `RCA-002` excludes any change to the beta journey's templates or
assets. Sharing one dictionary would make a shell key an `RRA` change.

**Parity is asserted at import, not left to a test.** `RCA-002` `FR-054` requires equivalent state,
actions, and error text in both languages. A key present in one language and missing in the other
raises `StrictUndefined` at render time -- in whichever language happens to be requested -- which
is a defect discovered by a visitor rather than by the build.

**No cause is named in the unavailable copy.** `FR-050` collapses five states into this surface and
`FR-052` forbids disclosing which one occurred, so the text says what the reader can do next and
nothing about what went wrong.
"""

from __future__ import annotations

_EN = {
    "product": "Khepri",
    "skip": "Skip to main content",
    "unavailable_title": "This page is unavailable",
    "unavailable_intro": (
        "We cannot show this page. Check the address, or return to your organization's home page."
    ),
    "no_membership_title": "You are not in an organization yet",
    "no_membership_intro": (
        "Your account is active, but it does not belong to an organization."
    ),
    "no_membership_action": "Ask an organization owner to invite you.",
    "switcher_title": "Choose an organization",
    "switcher_intro": "You belong to these organizations.",
}

_AR = {
    "product": "خِبري",
    "skip": "تخطَّ إلى المحتوى الرئيسي",
    "unavailable_title": "هذه الصفحة غير متاحة",
    "unavailable_intro": (
        "لا يمكننا عرض هذه الصفحة. تحقق من العنوان، أو عد إلى الصفحة الرئيسية لمؤسستك."
    ),
    "no_membership_title": "لست ضمن أي مؤسسة بعد",
    "no_membership_intro": "حسابك نشط، لكنه لا ينتمي إلى أي مؤسسة.",
    "no_membership_action": "اطلب من مالك المؤسسة دعوتك.",
    "switcher_title": "اختر مؤسسة",
    "switcher_intro": "أنت عضو في هذه المؤسسات.",
}

if set(_EN) != set(_AR):  # pragma: no cover -- structural guard, not a branch under test
    missing = set(_EN).symmetric_difference(_AR)
    raise RuntimeError(f"SHELL_COPY is not at language parity: {sorted(missing)}")

SHELL_COPY = {"en": _EN, "ar": _AR}

#: Text direction per language, so a template never infers it from the language code.
DIRECTIONS = {"en": "ltr", "ar": "rtl"}

__all__ = ["DIRECTIONS", "SHELL_COPY"]
