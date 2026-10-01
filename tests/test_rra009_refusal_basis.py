"""`RRA-009` §Refusals: a refusal whose cause belongs to one comparison basis names it (A4(b)).

SCRUM-26 A4(b), the owner's reading recorded in `#637`. The Period comparison section of the
SCRUM-21 file printed a coverage refusal as its headline and, beneath it, a `prior_window_absent`
sentence. Each was true of one basis, and neither said which, so the headline read as true of
both. The amendment names the basis in the first part, at the result and the section tier, in
both languages, from the governed basis labels.

The two fixtures are real CSV bytes through the real pipeline and `ReportBundle.of`:

- `split` is four days with no coverage manifest. Previous-period coverage is unproven
  (`coverage_structurally_incompatible`) and there is no year-earlier period
  (`prior_window_absent`), so each basis is refused for its own cause. Growth consumes the
  previous-period window and is refused for that window's cause.
- `single` is one day. Both bases are refused for the same cause, so the section's cause belongs
  to neither basis alone and its headline names none, while the two result refusals, which differ
  only in basis, are both printed.

The expected openings are written out rather than rebuilt from `LABEL_WORDING`, because
rebuilding them would restate the composition under test.
"""

from __future__ import annotations

import io
import re
import zipfile
from functools import cache

import pytest

from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.wording import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    business_metric_name,
    caveat_prose,
)
from tests.test_rra008_assembly import HEADER, package_for

LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)

_FIXTURES = {
    "split": HEADER
    + (
        b"2026-01-05,100.00,1,INV-0,A\n"
        b"2026-01-06,110.00,2,INV-1,B\n"
        b"2026-01-07,120.00,3,INV-2,A\n"
        b"2026-01-08,130.00,4,INV-3,B\n"
    ),
    "single": HEADER + b"2026-01-05,100.00,1,INV-0,A\n2026-01-05,110.00,2,INV-1,B\n",
}

_PREVIOUS = {
    LANGUAGE_ENGLISH: "Against the previous period: ",
    LANGUAGE_ARABIC: "مقابل الفترة السابقة: ",
}
_LAST_YEAR = {
    LANGUAGE_ENGLISH: "Against the same period last year: ",
    LANGUAGE_ARABIC: "مقابل الفترة نفسها من العام الماضي: ",
}
#: The section sentence's own opening, and the opening of each cause's second part.
_HEAD = {
    LANGUAGE_ENGLISH: "Comparison with an earlier period — not available.",
    LANGUAGE_ARABIC: "المقارنة بفترة سابقة — غير متاحة.",
}
_COVERAGE = {
    LANGUAGE_ENGLISH: " Your file covers both periods, but not in the same way",
    LANGUAGE_ARABIC: " يغطي ملفك الفترتين، لكن ليس بالطريقة نفسها",
}
_ABSENT = {
    LANGUAGE_ENGLISH: " Your file does not include the earlier period",
    LANGUAGE_ARABIC: " لا يتضمن ملفك الفترة السابقة",
}
_COVERAGE_RESULT = {
    LANGUAGE_ENGLISH: " is not shown — the two periods being compared are not covered",
    LANGUAGE_ARABIC: " غير معروض — الفترتان المقارنتان غير مغطاتين بالطريقة نفسها",
}

_POP_COVERAGE = "revenue_delta_absolute.period_over_period:coverage_structurally_incompatible"
_YOY_ABSENT = "revenue_delta_absolute.year_over_year:prior_window_absent"
_POP_ABSENT = "revenue_delta_absolute.period_over_period:prior_window_absent"


@cache
def _bundle(fixture: str) -> ReportBundle:
    return ReportBundle.of(package_for(_FIXTURES[fixture], published=True))


@cache
def _page(fixture: str, language: str) -> str:
    return HtmlReportRenderer().render_html(_bundle(fixture)).documents[language]


def _section_block(page: str, section_id: str) -> str:
    start = page.index(f'<section id="{section_id}"')
    end = page.find('<section id="', start + 1)
    return page[start:] if end == -1 else page[start:end]


def _panel(fixture: str, section_id: str, language: str) -> str:
    """The refusal panel's prose: what a reader takes as the section's headline."""
    block = _section_block(_page(fixture, language), section_id)
    match = re.search(r'data-component="refusal-panel".*?</span>(.*?)</p>', block, re.S)
    assert match, f"{section_id} prints no refusal panel"
    return " ".join(match.group(1).split())


def _metric(code: str, language: str) -> str:
    name = business_metric_name(code.split(".", maxsplit=1)[0], language)
    assert name is not None, code
    return name


def _limitations(fixture: str) -> str:
    content = ExcelSurfaceRenderer().render_materialized(_bundle(fixture)).artifacts[0].content
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return archive.read("xl/sharedStrings.xml").decode()


def _reasons(fixture: str) -> dict[str, str | None]:
    return {section.section_id: section.reason for section in _bundle(fixture).sections}


def _codes(fixture: str) -> frozenset[str]:
    return frozenset(caveat.code for caveat in _bundle(fixture).caveats)


def test_the_fixtures_refuse_the_bases_as_declared() -> None:
    """Extent: each fixture still produces the case it is named for."""
    assert _reasons("split")["comparison"] == "coverage_structurally_incompatible"
    assert _reasons("split")["growth"] == "coverage_structurally_incompatible"
    assert {_POP_COVERAGE, _YOY_ABSENT} <= _codes("split")
    assert _reasons("single")["comparison"] == "prior_window_absent"
    assert {_POP_ABSENT, _YOY_ABSENT} <= _codes("single")


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_result_refusal_names_the_basis_it_was_computed_against(language: str) -> None:
    coverage = caveat_prose(_POP_COVERAGE, language)
    absent = caveat_prose(_YOY_ABSENT, language)

    assert coverage.startswith(
        f"{_PREVIOUS[language]}{_metric(_POP_COVERAGE, language)}{_COVERAGE_RESULT[language]}"
    ), coverage
    assert absent.startswith(f"{_LAST_YEAR[language]}{_HEAD[language]}{_ABSENT[language]}"), absent


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_section_refused_per_basis_for_different_causes_names_each(language: str) -> None:
    """The headline is never true of one basis while presented as true of both."""
    panel = _panel("split", "comparison", language)

    previous = f"{_PREVIOUS[language]}{_HEAD[language]}{_COVERAGE[language]}"
    last_year = f"{_LAST_YEAR[language]}{_HEAD[language]}{_ABSENT[language]}"
    assert panel.startswith(previous), panel
    assert last_year in panel, panel
    assert panel.index(previous) < panel.index(last_year)


@pytest.mark.parametrize("language", LANGUAGES)
def test_growth_names_the_basis_whose_window_it_was_refused_for(language: str) -> None:
    panel = _panel("split", "growth", language)

    assert panel.startswith(f"{_PREVIOUS[language]}{_HEAD[language]}{_COVERAGE[language]}"), panel
    assert _LAST_YEAR[language] not in panel


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_cause_shared_by_every_basis_is_stated_once_and_unnamed(language: str) -> None:
    """Both bases refused alike: the cause belongs to neither alone, so the headline names none."""
    panel = _panel("single", "comparison", language)

    assert panel.startswith(f"{_HEAD[language]}{_ABSENT[language]}"), panel
    assert panel.count(_HEAD[language]) == 1, panel


@pytest.mark.parametrize("language", LANGUAGES)
def test_two_refusals_differing_only_in_basis_are_both_printed(language: str) -> None:
    block = _section_block(_page("single", language), "comparison")
    text = " ".join(re.sub(r"<[^>]+>", " ", block).split())

    assert f"{_PREVIOUS[language]}{_HEAD[language]}{_ABSENT[language]}" in text
    assert f"{_LAST_YEAR[language]}{_HEAD[language]}{_ABSENT[language]}" in text


def test_the_workbook_states_each_basis_with_its_own_cause() -> None:
    strings = _limitations("split")

    for language in LANGUAGES:
        assert f"{_PREVIOUS[language]}{_HEAD[language]}{_COVERAGE[language]}" in strings
        assert f"{_LAST_YEAR[language]}{_HEAD[language]}{_ABSENT[language]}" in strings


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_refusal_with_no_basis_is_unchanged(language: str) -> None:
    """A cause that belongs to no basis keeps its sentence: nothing is prefixed."""
    prose = caveat_prose("basket_attach_rate:incomplete_transaction_identifiers", language)

    assert not prose.startswith((_PREVIOUS[language], _LAST_YEAR[language])), prose


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_quality_response_words_a_section_as_its_panel_does(language: str) -> None:
    """The `report_api` analysis-quality surface names each basis exactly as the page does."""
    from khepri.rra.report_api import _quality_response

    stated = {
        entry.section_id: entry.wording
        for entry in _quality_response(_bundle("split"), language).refusals
    }

    assert stated["comparison"] == _panel("split", "comparison", language)
    assert stated["growth"] == _panel("split", "growth", language)


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_basis_recorded_alone_names_itself(language: str) -> None:
    """One basis's record and no other: its cause belongs to that basis, so it is named."""
    from khepri.rra.bundle import StatedCaveat
    from khepri.rra.rendering.refusal_basis import section_refusal_prose

    caveats = (StatedCaveat(code=_YOY_ABSENT, section="comparison"),)

    prose = section_refusal_prose("comparison", "prior_window_absent", caveats, language)

    assert prose.startswith(f"{_LAST_YEAR[language]}{_HEAD[language]}{_ABSENT[language]}"), prose
