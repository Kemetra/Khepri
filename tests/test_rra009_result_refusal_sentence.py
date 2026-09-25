"""A refused result states its own sentence, not its section's (`#575`).

`RRA-009` §Refusals part 1: a refusal names "which business analysis was unavailable". Five reasons
are governed at both the section and the result tier, and `wording.caveat_prose` used to send a
joined `<result>:<reason>` code carrying any of them to the section sentence. A refused
`basket_items_per_transaction` therefore read "Basket size -- not available", and a refused revenue
change read "Comparison with an earlier period -- not available". The result was never named.

`required_input_unavailable` is the one shared reason held on the section sentence, failing
closed: its result sentence fills `{column}` with the refused metric's own name and would tell a
customer the file "does not contain Revenue percentage change", which is false. It moves with
`#560` item 2, which carries the refusing input; `test_an_unavailable_input_...` pins the hold.

The cases are built from real CSV bytes through the real pipeline and `ReportBundle.of`, under the
triple this build publishes, so every family is derived rather than refused on its version. The
expected sentences are written out rather than rebuilt from `REFUSAL_WORDING`, because rebuilding
them would restate the table being tested.
"""

from __future__ import annotations

from functools import cache

import pytest

from khepri.rra.bundle import GOVERNED_SECTION_REASONS, ReportBundle
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.wording import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    REFUSAL_WORDING,
    SECTION_HEADINGS,
    business_metric_name,
    caveat_prose,
)
from khepri.rra.report_api import _quality_response
from tests.test_rra008_assembly import HEADER, package_for

LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)

#: Four days and no manifest: a pair of periods exists but its coverage is unproven.
_UNPROVEN_COVERAGE = HEADER + (
    b"2026-01-05,100.00,1,INV-0,A\n"
    b"2026-01-06,110.00,2,INV-1,B\n"
    b"2026-01-07,120.00,3,INV-2,A\n"
    b"2026-01-08,130.00,4,INV-3,B\n"
)
#: One row carries a receipt number and one does not.
_GAPPED_RECEIPTS = HEADER + b"2026-01-05,100.00,2,INV-1,A\n2026-01-06,50.00,1,,B\n"
#: Two rows identical in every column.
_REPEATED_ROWS = HEADER + (
    b"2026-01-05,100.00,2,INV-1,A\n2026-01-05,100.00,2,INV-1,A\n2026-01-06,50.00,1,INV-2,B\n"
)
_FIXTURES = {
    "coverage": _UNPROVEN_COVERAGE,
    "gapped": _GAPPED_RECEIPTS,
    "repeated": _REPEATED_ROWS,
}

_GAPPED_EN = "is not shown — receipt numbers are missing from some rows"
_GAPPED_AR = "غير معروض — أرقام الإيصالات مفقودة من بعض الصفوف"
_REPEATED_EN = "is not shown — the file contains sale lines that cannot be told apart"
_REPEATED_AR = "غير معروض — يحتوي الملف على سطور بيع لا يمكن التمييز بينها"
_COVERAGE_EN = "is not shown — the two periods being compared are not covered the same way"
_COVERAGE_AR = "غير معروض — الفترتان المقارنتان غير مغطاتين بالطريقة نفسها"
_INPUT_EN = "is not shown — the file does not contain"
_INPUT_AR = "غير معروض — لا يحتوي الملف على"
_HELD = "required_input_unavailable"
_HELD_SECTION = {
    LANGUAGE_ENGLISH: "This analysis — not available. The figures this analysis needs",
    LANGUAGE_ARABIC: "هذا التحليل — غير متاح. الأرقام التي يحتاجها هذا التحليل",
}

#: (fixture, joined code, English sentence opening, Arabic sentence opening). Each opening follows
#: the refused metric's business name.
_CASES = (
    (
        "gapped",
        "basket_items_per_transaction:incomplete_transaction_identifiers",
        _GAPPED_EN,
        _GAPPED_AR,
    ),
    ("gapped", "basket_attach_rate:incomplete_transaction_identifiers", _GAPPED_EN, _GAPPED_AR),
    ("repeated", "basket_items_per_transaction:repeated_row_signature", _REPEATED_EN, _REPEATED_AR),
    ("repeated", "basket_attach_rate:repeated_row_signature", _REPEATED_EN, _REPEATED_AR),
    (
        "coverage",
        "revenue_delta_absolute.period_over_period:coverage_structurally_incompatible",
        _COVERAGE_EN,
        _COVERAGE_AR,
    ),
)

#: The routed shared codes a real bundle emits at the result tier. The held code is pinned apart,
#: and the fifth routed code,
#: `family_version_pairing_unadmitted`, refuses a whole section before any family derives, so it
#: reaches the result tier only through a direct call (`test_a_version_refusal_...`).
_EMITTED_SHARED = frozenset(
    {
        "coverage_structurally_incompatible",
        "incomplete_transaction_identifiers",
        "repeated_row_signature",
    }
)


@cache
def _bundle(fixture: str) -> ReportBundle:
    return ReportBundle.of(package_for(_FIXTURES[fixture], published=True))


def _joined_codes(fixture: str) -> tuple[str, ...]:
    return tuple(caveat.code for caveat in _bundle(fixture).caveats if ":" in caveat.code)


def _reason(code: str) -> str:
    return code.rpartition(":")[2]


def _routed(code: str) -> bool:
    return _shared(code) and _reason(code) != _HELD


def _shared(code: str) -> bool:
    reason = _reason(code)
    return (
        reason in GOVERNED_SECTION_REASONS and reason in REFUSAL_WORDING["result"][LANGUAGE_ENGLISH]
    )


def _name(code: str, language: str) -> str:
    metric = code.rpartition(":")[0].split(".", maxsplit=1)[0]
    name = business_metric_name(metric, language)
    assert name is not None, metric
    return name


def _section_sentences(language: str) -> frozenset[str]:
    """Every section sentence as a reader could see it, placeholder filled or not."""
    return frozenset(
        message.split(" — ", maxsplit=1)[0]
        for message in REFUSAL_WORDING["section"][language].values()
    )


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("case", _CASES, ids=[case[1] for case in _CASES])
def test_a_refused_result_opens_with_its_own_name(
    case: tuple[str, str, str, str], language: str
) -> None:
    fixture, code, english, arabic = case
    assert code in _joined_codes(fixture), "the real bundle no longer emits this case"
    opening = english if language == LANGUAGE_ENGLISH else arabic

    prose = caveat_prose(code, language)

    assert prose.startswith(f"{_name(code, language)} {opening}"), prose


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("fixture", sorted(_FIXTURES))
def test_no_shared_code_result_reads_as_a_section_sentence(fixture: str, language: str) -> None:
    """Swept over every joined code the bundle carries, not only the pinned ones."""
    headings = set(SECTION_HEADINGS[language].values())
    for code in filter(_routed, _joined_codes(fixture)):
        prose = caveat_prose(code, language)
        assert prose.split(" — ", maxsplit=1)[0] not in _section_sentences(language), code
        assert not any(heading in prose for heading in headings), code
        assert "{" not in prose, code


def test_the_sweep_reaches_every_shared_code_a_bundle_emits() -> None:
    """Extent: a sweep over fixtures that stopped emitting a code would pass having checked it."""
    emitted = {
        _reason(code) for fixture in _FIXTURES for code in _joined_codes(fixture) if _shared(code)
    }

    assert emitted == _EMITTED_SHARED | {_HELD}


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_names_the_refused_result_inside_its_section(language: str) -> None:
    """The HTML surface prints a refused section's scoped caveats beneath its refusal panel."""
    page = HtmlReportRenderer().render_html(_bundle("gapped")).documents[language]
    start = page.index('<section id="basket"')
    end = page.find('<section id="', start + 1)
    block = page[start:] if end == -1 else page[start:end]
    code = "basket_items_per_transaction:incomplete_transaction_identifiers"
    opening = _GAPPED_EN if language == LANGUAGE_ENGLISH else _GAPPED_AR

    assert f"{_name(code, language)} {opening}" in block


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_quality_response_names_the_refused_result(language: str) -> None:
    """The `report_api` surface words a refused result with the same governed sentence."""
    stated = {
        f"{entry.result}:{entry.reason}": entry.wording
        for entry in _quality_response(_bundle("gapped"), language).refused_results
    }
    code = "basket_items_per_transaction:incomplete_transaction_identifiers"
    opening = _GAPPED_EN if language == LANGUAGE_ENGLISH else _GAPPED_AR

    assert stated[code].startswith(f"{_name(code, language)} {opening}"), stated[code]


@pytest.mark.parametrize(
    ("language", "expected"),
    (
        (LANGUAGE_ENGLISH, "Gross margin is not shown — this analysis is being released in stages"),
        (LANGUAGE_ARABIC, "هامش الربح الإجمالي غير معروض — يصدر هذا التحليل على مراحل"),
    ),
    ids=LANGUAGES,
)
def test_a_version_refusal_of_a_result_names_the_result(language: str, expected: str) -> None:
    prose = caveat_prose("gross_margin:family_version_pairing_unadmitted", language)

    assert prose.startswith(expected), prose


@pytest.mark.parametrize(
    ("language", "expected"),
    (
        (LANGUAGE_ENGLISH, "This analysis is not shown — this analysis is being released"),
        (LANGUAGE_ARABIC, "هذا التحليل غير معروض — يصدر هذا التحليل على مراحل"),
    ),
    ids=LANGUAGES,
)
def test_a_section_id_left_half_keeps_the_section_sentence(language: str, expected: str) -> None:
    """`growth` is a section, not a result, so there is no result to name."""
    prose = caveat_prose("growth:family_version_pairing_unadmitted", language)

    assert prose.startswith(expected), prose


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_unavailable_input_keeps_the_section_sentence_until_its_input_is_known(
    language: str,
) -> None:
    """Held, failing closed, until `#560` item 2: the result sentence would state a falsehood."""
    held = [code for code in _joined_codes("repeated") if _reason(code) == _HELD]
    assert held, "the real bundle no longer emits the held reason"
    false_claim = _INPUT_EN if language == LANGUAGE_ENGLISH else _INPUT_AR

    for code in held:
        prose = caveat_prose(code, language)
        assert prose.startswith(_HELD_SECTION[language]), prose
        assert f"{_name(code, language)} {false_claim}" not in prose, prose
