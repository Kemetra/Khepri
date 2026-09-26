"""The review step shows mapping evidence as governed words, never as codes (#589).

`RRA-003` requires every mapping to carry evidence, so the review step is right
to show it; it printed the codes themselves (`label_exact · type_confirmed`).
The other cells of the same row already go through `wordFor`, reading wording
the server renders into `#value-vocabulary`. `wordFor` falls back to the raw
code when an attribute is missing, so a code with no wording fails *silently*
on the page -- which is why the emitted set is derived from `mapping.py`'s own
source and checked against the copy tables *and* the template.
"""

from __future__ import annotations

import ast
from importlib.resources import files

import pytest
from playwright.sync_api import Error, sync_playwright

from khepri.rra.journey.copy import JOURNEY_COPY
from tests.journey_routed_page import open_journey_page

#: The codes `mapping.py` emits today, committed so a new code is a visible diff.
EVIDENCE_CODES = frozenset(
    {
        "label_exact",
        "label_token",
        "label_substring",
        "type_confirmed",
        "type_conflict",
        "type_only",
        "declared_in_source_contract",
    }
)


def _emitted_evidence_codes() -> frozenset[str]:
    """String constants passed to `evidence.append(...)` or an `evidence=` argument."""
    tree = ast.parse(files("khepri.rra").joinpath("mapping.py").read_text(encoding="utf-8"))
    codes: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "append":
            if isinstance(func.value, ast.Name) and func.value.id == "evidence":
                codes.update(_constants(node.args))
        for keyword in node.keywords:
            if keyword.arg == "evidence":
                codes.update(_constants([keyword.value]))
    return frozenset(codes)


def _constants(nodes: list[ast.expr]) -> set[str]:
    return {
        leaf.value
        for node in nodes
        for leaf in ast.walk(node)
        if isinstance(leaf, ast.Constant) and isinstance(leaf.value, str)
    }


def test_the_committed_codes_are_exactly_what_mapping_emits() -> None:
    emitted = _emitted_evidence_codes()

    assert emitted, "the derivation found no evidence codes, so it checks nothing"
    assert emitted == EVIDENCE_CODES


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("code", sorted(EVIDENCE_CODES))
def test_every_evidence_code_has_wording(language: str, code: str) -> None:
    wording = JOURNEY_COPY[language].get(f"evidence_{code}")

    assert wording, f"{code} has no {language} wording"
    assert "_" not in wording


@pytest.mark.parametrize("code", sorted(EVIDENCE_CODES))
def test_the_review_vocabulary_carries_every_evidence_code(code: str) -> None:
    template = (
        files("khepri.rra.journey").joinpath("templates/review.html.j2").read_text(encoding="utf-8")
    )
    attribute = f'data-evidence-{code.replace("_", "-")}="{{{{ copy.evidence_{code} }}}}"'

    assert attribute in template


def _review_api(method: str, path: str) -> tuple[int, object]:
    if path == "/api/v1/beta/journey":
        return 200, {"step": "review"}
    if path == "/api/v1/beta/profile":
        return 200, {
            "admissible": True,
            "reasons": [],
            "findings": [],
            "mappings": [
                {
                    "semantic": "revenue",
                    "state": "mapped",
                    "requirement": "required",
                    "candidates": [
                        {"safe_label": "revenue", "evidence": sorted(EVIDENCE_CODES)}
                    ],
                }
            ],
        }
    return 404, {"detail": "not stubbed"}


@pytest.mark.browser
@pytest.mark.parametrize("language", ["en", "ar"])
def test_the_evidence_cell_shows_words_not_codes(language: str) -> None:
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Error as error:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        try:
            page, _ = open_journey_page(browser, language=language, step="review", api=_review_api)
            evidence = page.locator("#mapping-table tbody tr td").nth(3)
            evidence.wait_for()
            shown = evidence.text_content()
        finally:
            browser.close()

    words = [JOURNEY_COPY[language][f"evidence_{code}"] for code in sorted(EVIDENCE_CODES)]
    assert shown == " · ".join(words)
