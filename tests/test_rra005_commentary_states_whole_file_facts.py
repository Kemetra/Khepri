"""`RRA-005`: the deterministic commentary states whole-file facts, by their names.

SCRUM-21 A9, on the SCRUM-21 file:

- **A series or comparison was quoted as if it were a total.** A breakdown section
  quoted its last bucket under the breakdown's name: "The recorded revenue by
  category is 6584.93" is Snacks alone, and "revenue by store is 10681.09" is one
  branch. Nothing in the sentence says so. That changes the meaning, which
  `RRA-005` does not allow ("wording may differ without changing meaning"). Every
  breakdown is stated in full in the report's tables.
- **Arabic prose named every measure by its English code** ("القيمة المسجلة لـ
  revenue"), and English read "The recorded units is 836".

Formatted figures and Arabic-Indic digits are not asserted here. The narrator's
recorded rule is to quote a supplied figure verbatim, and changing that is an owner
reading, not this slice.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal

import pytest

from khepri.rra.deterministic_narrative import ADAPTER_VERSION, DeterministicNarrator
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    NarrativeDraft,
    NarrativeRequest,
    validate,
)
from khepri.rra.rendering.wording import business_metric_name
from tests import rra_printed_support as support

_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")


@pytest.fixture(scope="module")
def request_and_draft() -> tuple[NarrativeRequest, NarrativeDraft]:
    content = support.retail_csv()
    profile = support.build_profile(
        content=content,
        media_type=support.CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = support.build_mapping(profile, contract=support.TEST_CONTRACT)
    package = support.build_fact_package(
        support.AdmittedInput(
            manifest=support.manifest_for_csv(content, support.TEST_CONTRACT),
            content=content,
            media_type=support.CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=support.assess_admissibility(profile, mapping),
            contract=support.TEST_CONTRACT,
        )
    )
    request = NarrativeRequest.of(package, adapter_version=ADAPTER_VERSION)
    return request, DeterministicNarrator().draft(request, timeout_seconds=Decimal("30"))


def _texts(draft: NarrativeDraft, language: str) -> list[str]:
    entry = next(entry for entry in draft.languages if entry.language == language)
    return [section.text for section in entry.sections]


def test_the_draft_survives_validation(request_and_draft) -> None:
    request, draft = request_and_draft
    validate(draft, request=request)


def test_no_breakdown_is_quoted_as_a_whole(request_and_draft) -> None:
    """Every section cites a whole-file fact, never one bucket of a breakdown."""
    request, draft = request_and_draft
    whole_file = {entry["citation_id"] for entry in request.document["facts"]}
    breakdowns = [*request.document["series"], *request.document["comparisons"]]
    # The file carries breakdowns, so leaving them out is a choice this test sees.
    assert breakdowns, "the fixture publishes no breakdown"

    for entry in draft.languages:
        cited = {fact for section in entry.sections for fact in section.cited_fact_ids}
        assert cited, entry.language
        assert cited <= whole_file, f"{entry.language}: {sorted(cited - whole_file)}"


def test_each_language_names_the_measure_as_the_report_does(request_and_draft) -> None:
    request, draft = request_and_draft
    names = {
        language: [
            business_metric_name(entry["metric"], language) for entry in request.document["facts"]
        ]
        for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)
    }

    for language, expected in names.items():
        texts = _texts(draft, language)
        assert len(texts) == len(expected), language
        for name, text in zip(expected, texts, strict=True):
            assert name is not None and name in text, f"{language}: {text}"

    arabic = " ".join(_texts(draft, LANGUAGE_ARABIC))
    assert _LATIN_WORD.findall(arabic) == [], arabic


def test_no_english_sentence_misagrees(request_and_draft) -> None:
    _, draft = request_and_draft
    english = " ".join(_texts(draft, LANGUAGE_ENGLISH))
    assert " is " not in english, english


def test_the_prose_change_is_a_new_adapter_version() -> None:
    """A stored run records which prose it was written in."""
    assert ADAPTER_VERSION == "rra005.deterministic.v3"
