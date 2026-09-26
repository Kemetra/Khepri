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
