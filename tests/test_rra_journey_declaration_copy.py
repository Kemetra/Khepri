"""Declaration copy the owner approved for the upload page (#586, #587, #588).

Committed literals rather than a property of the wording: what is under test is
that the page says the approved sentence, in both languages, and a structural
assertion would pass against the misleading wording this replaced.
"""

from __future__ import annotations

import pytest

from khepri.rra.journey.copy import JOURNEY_COPY

#: `#588`. The claim is that a reference identifies one *sale*, so several order
#: lines may share it; "unique across the whole file" read as one row per
#: reference and sent honest declarations into the composite-key refusal.
UNIQUE_REFERENCE = {
    "en": "Each reference belongs to one sale only, even when that sale has several rows",
    "ar": "كل مرجع يخص عملية بيع واحدة فقط، حتى لو كانت لها عدة صفوف",
}


@pytest.mark.parametrize("language", ["en", "ar"])
def test_the_uniqueness_claim_names_the_sale_not_the_value(language: str) -> None:
    copy = JOURNEY_COPY[language]

    assert copy["contract_transaction_id_unique_package_wide"] == UNIQUE_REFERENCE[language]


#: `#586` and `#587`, as the owner approved them in the plan's copy table.
APPROVED = {
    "contract_transaction_key_components": {
        "en": "Columns that together identify one sale, when the reference alone does not",
        "ar": "الأعمدة التي تحدد معاً عملية بيع واحدة، إذا لم يكفِ المرجع وحده",
    },
    "contract_transaction_key_components_hint": {
        "en": (
            "Separated by commas, and including the transaction reference column — for example "
            "invoice_no, branch. Leave blank when each reference belongs to one sale only."
        ),
        "ar": (
            "افصل بينها بفواصل، وأدرج عمود مرجع المعاملة، مثل invoice_no, branch. "
            "اتركه فارغاً إذا كان كل مرجع يخص عملية بيع واحدة فقط."
        ),
    },
    "profile_rejected": {
        "en": (
            "Your file is uploaded, but it could not be analysed with this declaration. "
            "Correct the declaration and submit again — your file is kept."
        ),
        "ar": (
            "تم رفع ملفك، لكن تعذر تحليله بهذا الإقرار. صحّح الإقرار وأرسله مرة أخرى، فملفك محفوظ."
        ),
    },
    "upload_kept": {
        "en": (
            "Your uploaded file is kept for this session. To use a different file, "
            "delete this session's content."
        ),
        "ar": "ملفك المرفوع محفوظ لهذه الجلسة. لاستخدام ملف آخر، احذف محتوى هذه الجلسة.",
    },
}


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("key", sorted(APPROVED))
def test_the_page_says_the_approved_sentence(key: str, language: str) -> None:
    assert JOURNEY_COPY[language][key] == APPROVED[key][language]
