"""A refusal says which input refused it (`#326` item 4, `#560` item 2, `#575`).

Two defects with one root: the refusal did not carry what caused it.

- A repeated event key and a repeated canonical row signature both refused as
  `repeated_row_signature`, so a keyed extract whose line reference collided -- or was left
  blank -- was told the same thing as one exported twice. `RRA-003` proves identity in
  exactly one of two ways, so the two causes never co-occur and each gets its own code.
- A refused result's customer sentence names "which missing field or evidence caused it,
  named as a column the customer would recognise" (`RRA-009` §Refusals, part 4).
  `RefusedResult` recorded no input, so the sentence either named the refused metric as its
  own missing column or fell back to the vague section sentence.

Every case is built from real CSV bytes through the real pipeline and `ReportBundle.of`,
under the triple this build publishes. Expected labels are written out rather than read
from the journey copy, because reading them would restate the table being tested.
"""

from __future__ import annotations

import hashlib
from functools import cache

import pytest

from khepri.rra import facts as facts_module
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import SECTION_BASKET, ReportBundle
from khepri.rra.facts import AdmittedInput, FactPackage, FactsRefused, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.package_source import rebuild_fact_package
from khepri.rra.packages import PackageCorrupted
from khepri.rra.profiling import build_profile
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.wording import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    business_metric_name,
    refusal_message,
    section_refusal_message,
)
from khepri.rra.report_api import _quality_response
from khepri.rra.source_contract import (
    BasisDeclaration,
    ContractAttribution,
    EventDeclaration,
    IdentityDeclaration,
    build_source_contract,
)
from tests.rra003_contract_fixtures import TEST_CONTRACT

LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)
REPEATED_EVENT_KEY = "repeated_event_key"
REPEATED_ROW_SIGNATURE = "repeated_row_signature"

#: A keyed extract: `line_id` is the declared event key, the first identity proof.
KEYED_CONTRACT = build_source_contract(
    attribution=ContractAttribution(
        contract_id="src_keyed_refusal_inputs",
        evidence="Test fixture: a keyed synthetic retail extract.",
    ),
    events=EventDeclaration(
        event_kind_column=None,
        sale_only=True,
        status_column=None,
        posted_only=True,
        currency_column=None,
        currency_code="EGP",
    ),
    identity=IdentityDeclaration(
        event_key_columns=("line_id",),
        unique_line_grain_attested=False,
        transaction_id_column="invoice_no",
        transaction_key_components=(),
        transaction_id_unique_package_wide=True,
    ),
    basis=BasisDeclaration(
        revenue_vat_exclusive=True,
        revenue_is_net_of_returns=False,
        units_are_integral=True,
        cost_is_extended=True,
        discount_is_additive=True,
    ),
)

_KEYED_HEADER = b"date,revenue,units,invoice_no,line_id,product\n"
_UNKEYED_HEADER = b"date,revenue,units,invoice_no,product\n"
_FIXTURES = {
    # Two different sales given the same line reference.
    "collided_key": (
        _KEYED_HEADER + b"2026-01-05,100.00,2,INV-1,L1,A\n2026-01-06,50.00,1,INV-2,L1,B\n",
        KEYED_CONTRACT,
    ),
    # A sale line whose reference was left blank.
    "blank_key": (
        _KEYED_HEADER + b"2026-01-05,100.00,2,INV-1,L1,A\n2026-01-06,50.00,1,INV-2,,B\n",
        KEYED_CONTRACT,
    ),
    # Two rows identical in every column, under the unique-line-grain attestation.
    "identical_rows": (
        _UNKEYED_HEADER
        + b"2026-01-05,100.00,2,INV-1,A\n2026-01-05,100.00,2,INV-1,A\n"
        + b"2026-01-06,50.00,1,INV-2,B\n",
        TEST_CONTRACT,
    ),
    # No quantity column: items per sale refuses while attach rate stands.
    "no_units": (
        b"date,revenue,invoice_no,product\n2026-01-05,100.00,INV-1,A\n2026-01-06,50.00,INV-2,B\n",
        TEST_CONTRACT,
    ),
    # A column named only `discount` states no measure kind.
    "ambiguous_discount": (
        b"date,revenue,units,invoice_no,product,discount\n"
        b"2026-01-05,100.00,2,INV-1,A,5\n2026-01-06,50.00,1,INV-2,B,1\n",
        TEST_CONTRACT,
    ),
    # One sale carries no revenue.
    "gapped_revenue": (
        _UNKEYED_HEADER + b"2026-01-05,100.00,2,INV-1,A\n2026-01-06,,1,INV-2,B\n",
        TEST_CONTRACT,
    ),
}

_UNITS_LABEL = {LANGUAGE_ENGLISH: "Units", LANGUAGE_ARABIC: "الكمية"}
_MISSING = {
    LANGUAGE_ENGLISH: "is not shown — the file does not contain Units.",
    LANGUAGE_ARABIC: "غير معروض — لا يحتوي الملف على الكمية.",
}
_ITEMS = "basket_items_per_transaction"
_ITEMS_UNAVAILABLE = f"{_ITEMS}:required_input_unavailable"


@cache
def _package(fixture: str) -> FactPackage:
    content, contract = _FIXTURES[fixture]
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=contract)
    return build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
        )
    )


@cache
def _bundle(fixture: str) -> ReportBundle:
    return ReportBundle.of(_package(fixture))


def _reason(fixture: str, metric: str) -> str:
    refused = _package(fixture).refusal(metric)
    assert refused is not None, metric
    return refused.reason


def _input(fixture: str, metric: str) -> str | None:
    refused = _package(fixture).refusal(metric)
    assert refused is not None, metric
    return getattr(refused, "input", None)


# --- 1. `repeated_event_key` is its own code ---------------------------------------


def test_a_collided_key_and_identical_rows_refuse_with_different_codes() -> None:
    """Asserted by code, not only by refusal: both refuse, and they say different things."""
    collided = _reason("collided_key", "revenue")
    identical = _reason("identical_rows", "revenue")

    assert collided == REPEATED_EVENT_KEY
    assert identical == REPEATED_ROW_SIGNATURE
    assert collided != identical


@pytest.mark.parametrize("fixture", ("collided_key", "blank_key"))
@pytest.mark.parametrize("metric", ("revenue", "units", "transactions", "revenue_by_period"))
def test_every_result_a_keyed_repeat_refuses_names_the_key(fixture: str, metric: str) -> None:
    """A blank reference is no key at all, and `admission` refuses it as a repeat."""
    assert _reason(fixture, metric) == REPEATED_EVENT_KEY


@pytest.mark.parametrize("fixture", ("collided_key", "blank_key"))
def test_the_basket_section_refuses_on_the_key_it_copied(fixture: str) -> None:
    """`basket._identifier_reason` hands the package's cause straight to the section."""
    reasons = {section.section_id: section.reason for section in _bundle(fixture).sections}
    codes = {caveat.code for caveat in _bundle(fixture).caveats}

    assert reasons[SECTION_BASKET] == REPEATED_EVENT_KEY
    assert f"{_ITEMS}:{REPEATED_EVENT_KEY}" in codes


@pytest.mark.parametrize(
    ("language", "opening", "reference"),
    (
        (
            LANGUAGE_ENGLISH,
            "Basket size — not available.",
            "sharing the reference that identifies them or leaving it empty",
        ),
        (
            LANGUAGE_ARABIC,
            "حجم سلة الشراء — غير متاح.",
            "لاشتراكها في المرجع الذي يُعرِّفها أو لخلوّها منه",
        ),
    ),
    ids=LANGUAGES,
)
def test_the_key_section_sentence_names_the_reference(
    language: str, opening: str, reference: str
) -> None:
    prose = section_refusal_message(SECTION_BASKET, REPEATED_EVENT_KEY, language)

    assert prose.startswith(opening), prose
    assert reference in prose, prose
    assert "{" not in prose


@pytest.mark.parametrize(
    ("language", "expected"),
    (
        (
            LANGUAGE_ENGLISH,
            "Revenue is not shown — the file contains sale lines that cannot be told apart, "
            "sharing the reference that identifies them or leaving it empty,",
        ),
        (
            LANGUAGE_ARABIC,
            "الإيرادات غير معروض — يحتوي الملف على سطور بيع لا يمكن التمييز بينها، "
            "لاشتراكها في المرجع الذي يُعرِّفها أو لخلوّها منه،",
        ),
    ),
    ids=LANGUAGES,
)
def test_the_key_result_sentence_names_the_reference(language: str, expected: str) -> None:
    metric = business_metric_name("revenue", language)
    prose = refusal_message(REPEATED_EVENT_KEY, context="result", language=language)

    assert prose.format(metric=metric).startswith(expected), prose


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_key_sentence_does_not_claim_identical_rows(language: str) -> None:
    """The collision is not a duplicated extract, so the either/or is gone from its sentence."""
    identical = {LANGUAGE_ENGLISH: "identical in every column", LANGUAGE_ARABIC: "كل الأعمدة"}
    for context in ("section", "result"):
        prose = refusal_message(REPEATED_EVENT_KEY, context=context, language=language)
        assert identical[language] not in prose, context


# --- 2. A refused result records, and names, the input that refused it -------------


@pytest.mark.parametrize(
    ("fixture", "metric", "reason", "semantic"),
    (
        ("no_units", "units", "required_input_unavailable", "units"),
        ("no_units", "units_by_channel", "required_input_unavailable", "channel"),
        ("no_units", "gross_margin", "required_input_unavailable", "cost"),
        ("ambiguous_discount", "discount", "ambiguous_mapping", "discount"),
        ("gapped_revenue", "revenue", "incomplete_column_coverage", "revenue"),
        ("gapped_revenue", "gross_profit", "incomplete_column_coverage", "revenue"),
    ),
)
def test_a_refused_result_records_the_input_that_refused_it(
    fixture: str, metric: str, reason: str, semantic: str
) -> None:
    assert _reason(fixture, metric) == reason
    assert _input(fixture, metric) == semantic


@pytest.mark.parametrize("fixture", ("collided_key", "identical_rows"))
def test_a_cause_no_column_explains_records_no_input(fixture: str) -> None:
    """A repeat is not a column the customer can fill, so it names none."""
    assert _input(fixture, "revenue") is None


def test_the_family_refusal_carries_the_package_input_onto_its_caveat() -> None:
    scoped = {caveat.code: caveat for caveat in _bundle("no_units").caveats}

    assert getattr(scoped[_ITEMS_UNAVAILABLE], "refusing_input", None) == "units"


def _basket_block(language: str) -> str:
    page = HtmlReportRenderer().render_html(_bundle("no_units")).documents[language]
    start = page.index('<section id="basket"')
    end = page.find('<section id="', start + 1)
    return page[start:] if end == -1 else page[start:end]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_names_the_metric_and_the_missing_column(language: str) -> None:
    name = business_metric_name(_ITEMS, language)
    block = _basket_block(language)

    assert f"{name} {_MISSING[language]}" in block
    assert name != _UNITS_LABEL[language]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_quality_response_names_the_metric_and_the_missing_column(language: str) -> None:
    stated = {
        f"{entry.result}:{entry.reason}": entry.wording
        for entry in _quality_response(_bundle("no_units"), language).refused_results
    }
    name = business_metric_name(_ITEMS, language)
    prose = stated[_ITEMS_UNAVAILABLE]

    assert prose.startswith(f"{name} {_MISSING[language]}"), prose
    assert prose.count(name) == 1, prose


# --- 3. The package document: a lenient reader, a lenient writer, a moved version ----


def _document_with_inputs() -> dict[str, object]:
    return _package("no_units").as_document()


def test_a_refusal_with_an_input_round_trips() -> None:
    document = _document_with_inputs()
    refusals = document["refusals"]
    assert any("input" in entry for entry in refusals)  # type: ignore[union-attr]

    assert rebuild_fact_package(document).as_document() == document


def test_a_document_without_the_input_still_loads_and_reserializes_identically() -> None:
    """`rra004.package.v3` documents carry no `input`; absent must stay absent."""
    document = _document_with_inputs()
    legacy = {
        **document,
        "refusals": [
            {key: value for key, value in entry.items() if key != "input"}
            for entry in document["refusals"]  # type: ignore[union-attr]
        ],
    }

    rebuilt = rebuild_fact_package(legacy)

    assert rebuilt.as_document() == legacy
    assert all(getattr(refusal, "input", None) is None for refusal in rebuilt.refusals)


def test_a_document_naming_an_ungoverned_input_is_refused() -> None:
    """An input reaches customer prose as a label, so an unknown one must not load."""
    document = _document_with_inputs()
    forged = {
        **document,
        "refusals": [
            {**entry, "input": "a customer header"} if "input" in entry else entry
            for entry in document["refusals"]  # type: ignore[union-attr]
        ],
    }

    with pytest.raises(PackageCorrupted):
        rebuild_fact_package(forged)


def test_this_build_publishes_the_package_version_that_carries_inputs() -> None:
    assert facts_module.PACKAGE_VERSION == "rra004.package.v4"
    assert _package("no_units").package_version == "rra004.package.v4"


def test_an_unadmitted_package_version_refuses_to_build(monkeypatch) -> None:
    """A sentinel the gate refuses by construction, never the next real version."""
    monkeypatch.setattr(facts_module, "PACKAGE_VERSION", "rra004.package.v99")
    _package.cache_clear()
    try:
        with pytest.raises(FactsRefused):
            _package("no_units")
    finally:
        _package.cache_clear()
