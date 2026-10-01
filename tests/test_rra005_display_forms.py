"""`RRA-005`: prose states every figure in the tables' display form for its language (A9(b)).

SCRUM-26 A9(b), the owner's reading recorded in `#637`. The commentary restated `23520.06`
beside a table printing `23,520.06`, and in Arabic quoted Latin digits beside a table printing
`٢٣٬٥٢٠٫٠٦`. The amendment has the request supply each figure's display form in each language,
as it already supplies a proportion's percentage form, and the narrator quote it rather than
convert. Grounding normalizes digits, separators and the percent sign, so a changed significant
digit is still refused.

The fixture is the SCRUM-21 file shape (`retail_csv`) through the real pipeline. The expected
forms are read from the bundle's own figures, which are what the tables print, rather than
rebuilt here.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from decimal import Decimal
from functools import cache

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import ReportBundle
from khepri.rra.deterministic_narrative import ADAPTER_VERSION, DeterministicNarrator
from khepri.rra.facts import AdmittedInput, FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    REASON_UNGROUNDED_NUMBER,
    NarrativeGround,
    NarrativeRefused,
    NarrativeRequest,
    validate,
)
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import TEST_CONTRACT, manifest_for_csv
from tests.rra_printed_support import retail_csv

LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)
_TIMEOUT = Decimal(5)


@cache
def _package() -> FactPackage:
    content = retail_csv()
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    return build_fact_package(
        AdmittedInput(
            manifest=manifest_for_csv(content, TEST_CONTRACT),
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=TEST_CONTRACT,
        )
    )


@cache
def _request() -> NarrativeRequest:
    return NarrativeRequest.of(_package(), adapter_version=ADAPTER_VERSION)


def _table_forms() -> dict[str, dict[str, str]]:
    """Each whole-file fact's table rendering, by citation: what the report prints."""
    bundle = ReportBundle.of(_package())
    return {
        figure.citation_id: figure.renderings
        for figure in bundle.figures
        if figure.label is None and figure.kind == "value"
    }


def _draft():
    return DeterministicNarrator().draft(_request(), timeout_seconds=_TIMEOUT)


def test_every_fact_carries_the_tables_form_in_each_language() -> None:
    tables = _table_forms()
    facts = _request().document["facts"]
    assert facts

    for fact in facts:
        assert fact["display"] == {
            language: tables[fact["citation_id"]][language] for language in LANGUAGES
        }, fact["metric"]


def test_every_bucket_and_point_carries_its_display_form() -> None:
    document = _request().document
    entries = [*document["series"], *document["comparisons"]]
    assert entries

    for entry in entries:
        for item in (*entry.get("points", ()), *entry.get("buckets", ())):
            assert set(item["display"]) == set(LANGUAGES), entry["metric"]
            assert set(item["rows_display"]) == set(LANGUAGES), entry["metric"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_commentary_quotes_the_tables_form_byte_for_byte(language: str) -> None:
    tables = _table_forms()
    narrative = next(entry for entry in _draft().languages if entry.language == language)
    assert narrative.sections

    for section in narrative.sections:
        form = tables[section.cited_fact_ids[0]][language]
        assert form in section.text, (form, section.text)


def test_the_arabic_commentary_states_no_latin_digit() -> None:
    narrative = next(entry for entry in _draft().languages if entry.language == LANGUAGE_ARABIC)

    for section in narrative.sections:
        assert not any(character.isascii() and character.isdigit() for character in section.text)


def test_the_display_forms_ground() -> None:
    validate(_draft(), request=_request())


def _changed_last_digit(form: str, language: str) -> str:
    """The form with its last digit replaced in place, any trailing sign kept."""
    digits = "0123456789" if language == LANGUAGE_ENGLISH else "٠١٢٣٤٥٦٧٨٩"
    position = max(index for index, character in enumerate(form) if character in digits)
    current = digits.index(form[position])
    return form[:position] + digits[(current + 1) % 10] + form[position + 1 :]


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_changed_significant_digit_is_still_refused(language: str) -> None:
    """Normalizing the form does not admit a different number."""
    draft = _draft()
    tables = _table_forms()
    mutated = []
    for entry in draft.languages:
        if entry.language != language:
            mutated.append(entry)
            continue
        first, *rest = entry.sections
        form = tables[first.cited_fact_ids[0]][language]
        changed = _changed_last_digit(form, language)
        assert changed != form and changed in first.text.replace(form, changed)
        mutated.append(
            replace(entry, sections=(replace(first, text=first.text.replace(form, changed)), *rest))
        )

    with pytest.raises(NarrativeRefused) as refused:
        validate(replace(draft, languages=tuple(mutated)), request=_request())
    assert str(refused.value) == REASON_UNGROUNDED_NUMBER


def test_every_bucket_and_point_form_is_its_table_cell() -> None:
    """Values, not only keys: each supplied form is the bundle's rendering of that cell."""
    bundle = ReportBundle.of(_package())
    cells = {
        (figure.citation_id, figure.label, figure.kind): figure.renderings
        for figure in bundle.figures
        if figure.label is not None
    }
    document = _request().document
    checked = 0
    for entry in (*document["series"], *document["comparisons"]):
        for item in (*entry.get("points", ()), *entry.get("buckets", ())):
            key = (entry["citation_id"], str(item["label"]))
            assert item["rows_display"] == cells[(*key, "rows")]
            if "display" in item:
                assert item["display"] == cells[(*key, "value")]
            checked += 1
    assert checked


def test_a_supplied_percentage_form_on_a_bucket_grounds() -> None:
    """A bucket of a proportion is supplied as `12.50%`, so quoting it must ground."""
    request = NarrativeRequest(
        document={
            "facts": [],
            "series": [],
            "comparisons": [
                {
                    "fact_id": "f",
                    "citation_id": "c",
                    "buckets": [
                        {
                            "label": "A",
                            "value": "0.1250",
                            "rows": 3,
                            "display": {LANGUAGE_ENGLISH: "12.50%", LANGUAGE_ARABIC: "١٢٫٥٠٪"},
                        }
                    ],
                }
            ],
            "caveats": [],
        }
    )

    assert Decimal("12.50") in NarrativeGround.of(request).stateable(("c",)).percents


def test_the_adapter_version_names_the_new_convention() -> None:
    assert ADAPTER_VERSION == "rra005.deterministic.v4"
