from __future__ import annotations

from importlib.resources import files

import pytest
from playwright.sync_api import Error, sync_playwright

from khepri.rra.journey.copy import JOURNEY_COPY
from khepri.rra.mapping import (
    KNOWN_SEMANTICS,
    STATE_AMBIGUOUS,
    STATE_CONFLICTING,
    STATE_MAPPED,
    STATE_UNAVAILABLE,
)
from tests.test_rra_journey_api import client

# Derived from the mapping module's own constants rather than restated, so a twelfth
# semantic or a fifth state fails these tests instead of reaching a customer as a raw
# machine identifier.
_GOVERNED_STATES = (
    STATE_MAPPED,
    STATE_AMBIGUOUS,
    STATE_CONFLICTING,
    STATE_UNAVAILABLE,
)
_VALUE_KEYS = tuple(f"semantic_{name}" for name in sorted(KNOWN_SEMANTICS)) + tuple(
    f"state_{name}" for name in _GOVERNED_STATES
)


def test_review_page_uses_a_captioned_scoped_table_and_no_editable_mapping() -> None:
    body = client().get("/beta/en/review").text
    assert "<caption" in body
    assert body.count('scope="col"') == 4
    assert '<select' not in body
    assert 'id="confirm-mapping"' in body and " disabled" in body


def test_review_renders_server_values_as_text_and_requires_mapped_fields() -> None:
    script = files("khepri.rra.journey").joinpath("assets", "review.js").read_text(
        encoding="utf-8"
    )
    assert "textContent = value" in script
    assert "innerHTML" not in script
    assert 'item.state === "mapped"' in script
    assert "profile.reasons" in script
    assert "profile.findings" in script
    assert "findings.getAttribute" in script
    assert script.index("/api/v1/beta/facts") < script.index("/api/v1/beta/reports")


def test_arabic_journey_localizes_fixed_review_processing_and_report_labels() -> None:
    test = client()
    review = test.get("/beta/ar/review").text
    processing = test.get("/beta/ar/processing").text
    report = test.get("/beta/ar/report").text
    assert "المعنى التجاري" in review
    assert "الرفع والمراجعة" in processing
    assert "جاري إعداد التقرير" in processing
    assert "مجموعة البيانات" in report
    assert "تاريخ الإنشاء" in report


def test_every_governed_semantic_and_state_has_wording_in_both_languages() -> None:
    for language in ("en", "ar"):
        for key in _VALUE_KEYS:
            wording = JOURNEY_COPY[language].get(key)
            assert wording, f"{language} is missing wording for {key}"
            # A label that is still the machine identifier is not wording.
            assert wording != key.split("_", 1)[1]


def test_review_page_publishes_every_value_label_for_the_table_to_read() -> None:
    """The page, not the script, carries both languages of the value vocabulary."""
    for language in ("en", "ar"):
        body = client().get(f"/beta/{language}/review").text
        assert 'id="value-vocabulary"' in body
        for key in _VALUE_KEYS:
            kind, code = key.split("_", 1)
            attribute = f'data-{kind}-{code.replace("_", "-")}'
            assert attribute in body, f"{language} page omits {attribute}"
            assert JOURNEY_COPY[language][key] in body


def test_review_script_renders_governed_wording_and_never_invents_a_meaning() -> None:
    script = files("khepri.rra.journey").joinpath("assets", "review.js").read_text(
        encoding="utf-8"
    )
    # The raw identifiers must no longer reach a table cell.
    assert "cell(mapping.semantic)" not in script
    assert "cell(mapping.state)" not in script
    assert 'wordFor("semantic", mapping.semantic)' in script
    assert 'wordFor("state", mapping.state)' in script
    # Server-owned copy: the script reads attributes and hardcodes no Arabic.
    assert "vocabulary?.getAttribute" in script
    for language in ("en", "ar"):
        for key in _VALUE_KEYS:
            assert JOURNEY_COPY[language][key] not in script
    # An unknown code falls back to itself, not to invented text.
    assert "?? code" in script


@pytest.mark.browser
@pytest.mark.parametrize("language", ["en", "ar"])
def test_browser_resolves_every_governed_code_to_its_wording(language: str) -> None:
    """Execute the lookup rather than assert its source text.

    The string assertions above cannot tell a working lookup from one whose key
    derivation is subtly wrong -- `transaction_date` has to reach
    `data-semantic-transaction-date`, and an off-by-one in that transform reads
    identically in source. So the real page is loaded into a real DOM and the
    lookup is run against every governed code, plus one that does not exist.
    """
    html = client().get(f"/beta/{language}/review").text
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="domcontentloaded")
            resolved = page.evaluate(
                """(codes) => {
                    const node = document.querySelector("#value-vocabulary");
                    const word = (kind, code) =>
                        node?.getAttribute(`data-${kind}-${code.replaceAll("_", "-")}`) ?? code;
                    return codes.map(([kind, code]) => word(kind, code));
                }""",
                [["semantic", name] for name in sorted(KNOWN_SEMANTICS)]
                + [["state", name] for name in _GOVERNED_STATES]
                + [["semantic", "not_a_governed_semantic"]],
            )
        finally:
            browser.close()
    expected = [JOURNEY_COPY[language][key] for key in _VALUE_KEYS]
    # An unknown code is shown as itself: no wording is invented for it.
    assert resolved == [*expected, "not_a_governed_semantic"]
    assert not any(word.startswith("data-") or word == "undefined" for word in resolved)
