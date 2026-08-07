"""RRA-009: the business/audit split in the governed workbook."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from khepri.rra.bundle import ReportBundle
from khepri.rra.narrative import LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from tests.rra009_fixtures import rich_bundle
from tests.test_rra006_html_sections import ROWS, package_for

LEAKAGE_METRICS = frozenset(
    {"cost", "gross_profit", "gross_margin", "discount", "returns"}
)


def _plain_bundle() -> ReportBundle:
    """The five-row fixture, which produces none of the leakage metrics."""
    return ReportBundle.of(package_for(ROWS))


def _workbook_bytes(bundle: ReportBundle, directory: Path) -> Path:
    renderer = ExcelSurfaceRenderer(directory=directory)
    renderer.render(bundle)
    return renderer.path_for(bundle)


def _sheet_names(bundle: ReportBundle, directory: Path) -> list[str]:
    with zipfile.ZipFile(_workbook_bytes(bundle, directory)) as archive:
        workbook = archive.read("xl/workbook.xml").decode()
    return re.findall(r'name="([^"]+)" sheetId', workbook)


def _shared_strings(bundle: ReportBundle, directory: Path) -> str:
    with zipfile.ZipFile(_workbook_bytes(bundle, directory)) as archive:
        return archive.read("xl/sharedStrings.xml").decode()


def test_the_rich_fixture_carries_every_leakage_metric() -> None:
    """Two business worksheets present exactly these, and the five-row fixture
    produces none of them. A bare `discount` column is not enough: `mapping.py`
    requires the measure kind be declared, so the column is `discount_amount`.
    """
    metrics = {figure.metric for figure in rich_bundle().figures}

    assert not (LEAKAGE_METRICS - metrics), sorted(LEAKAGE_METRICS - metrics)


def test_the_plain_fixture_carries_none_of_them() -> None:
    """The contrast this fixture exists for, asserted rather than assumed: a
    business sheet set that varies by dataset is only testable against both."""
    metrics = {figure.metric for figure in _plain_bundle().figures}

    assert not (LEAKAGE_METRICS & metrics)


def test_the_rich_fixture_presents_every_section() -> None:
    assert [section.state for section in rich_bundle().sections] == ["present"] * 5


def test_the_rich_fixture_renders_in_both_languages(tmp_path: Path) -> None:
    bundle = rich_bundle()
    for language in REQUIRED_LANGUAGES:
        assert all(language in figure.renderings for figure in bundle.figures)
    assert _sheet_names(bundle, tmp_path)


def test_every_rendered_metric_is_named_or_labelled() -> None:
    """The workbook's business sheets need a name for every row they list, on the
    same terms the web surface does. `concentration_curve` is the one metric with
    no business name, and every one of its figures carries a label.
    """
    from khepri.rra.rendering.wording import business_metric_name

    for figure in rich_bundle().figures:
        named = business_metric_name(figure.metric, LANGUAGE_ENGLISH)
        assert named or figure.label, figure.metric


def test_every_business_sheet_names_a_governed_section() -> None:
    from khepri.rra.bundle import ORDERED_SECTIONS
    from khepri.rra.rendering import excel_layout

    for sheet in excel_layout.BUSINESS_SHEETS:
        assert sheet.section in ORDERED_SECTIONS, sheet.key


def test_business_sheets_cover_every_rendered_metric() -> None:
    """A metric on no business sheet is a figure the customer never sees.

    Asserted against the rich fixture rather than against the governed metric
    vocabulary, because that vocabulary is 13 while the rendered set is 26 -- the
    series and bucket variants are what a business sheet actually lists.
    """
    from khepri.rra.rendering import excel_layout

    covered = {
        metric for sheet in excel_layout.BUSINESS_SHEETS for metric in sheet.metrics
    }
    rendered = {figure.metric for figure in rich_bundle().figures}

    assert not (rendered - covered), sorted(rendered - covered)


def test_no_metric_appears_on_two_business_sheets() -> None:
    """Two sheets showing one figure is two places for it to be read differently,
    and `reconcile` would catch neither -- it compares the claim, not the file."""
    from khepri.rra.rendering import excel_layout

    seen: dict[str, str] = {}
    for sheet in excel_layout.BUSINESS_SHEETS:
        for metric in sheet.metrics:
            assert metric not in seen, (metric, sheet.key, seen.get(metric))
            seen[metric] = sheet.key


def test_the_overview_fan_out_is_real_and_known() -> None:
    """Four business sheets present `overview`, which is why `excel.py` resolves a
    chart's target from an ordered list and not from a section-keyed mapping. A
    dict would silently keep only the last of the four.
    """
    from collections import Counter

    from khepri.rra.rendering import excel_layout

    per_section = Counter(sheet.section for sheet in excel_layout.BUSINESS_SHEETS)

    assert per_section["overview"] == 4
    assert {section: count for section, count in per_section.items() if count > 1} == {
        "overview": 4
    }


def test_every_business_sheet_is_named_in_every_language() -> None:
    from khepri.rra.rendering import excel_layout, wording

    keys = {sheet.key for sheet in excel_layout.BUSINESS_SHEETS}
    for language in REQUIRED_LANGUAGES:
        assert set(wording.BUSINESS_SHEET_NAMES[language]) == keys, language


def test_every_sheet_name_fits_the_bilingual_budget() -> None:
    """A 22-character name passes every review and raises `InvalidWorksheetName`
    during a customer's render. Measured threshold: 31 accepted, 32 raises, and
    both language suffixes are 10 characters -- so the budget is 21.
    """
    from khepri.rra.rendering import excel_layout, wording

    for language in REQUIRED_LANGUAGES:
        for key, name in wording.BUSINESS_SHEET_NAMES[language].items():
            assert len(name) <= excel_layout.MAX_SHEET_NAME_BUDGET, (
                key,
                language,
                len(name),
            )


def test_the_budget_matches_what_xlsxwriter_actually_refuses(tmp_path: Path) -> None:
    """The budget is derived from a measured limit, so the measurement is pinned.

    If XlsxWriter ever accepts 32, this test says so rather than leaving the
    constant describing a limit that moved.
    """
    import xlsxwriter
    from xlsxwriter.exceptions import InvalidWorksheetName

    from khepri.rra.rendering import excel_layout

    with xlsxwriter.Workbook(str(tmp_path / "at.xlsx")) as workbook:
        workbook.add_worksheet("X" * excel_layout.EXCEL_SHEET_NAME_LIMIT)

    try:
        with xlsxwriter.Workbook(str(tmp_path / "over.xlsx")) as workbook:
            workbook.add_worksheet("X" * (excel_layout.EXCEL_SHEET_NAME_LIMIT + 1))
    except InvalidWorksheetName:
        pass
    else:  # pragma: no cover - only runs if the limit moved
        raise AssertionError("XlsxWriter accepted a name over the recorded limit")


def test_sheet_names_are_distinct_within_a_language() -> None:
    from khepri.rra.rendering import wording

    for language in REQUIRED_LANGUAGES:
        names = list(wording.BUSINESS_SHEET_NAMES[language].values())
        assert len(set(names)) == len(names), language


def test_the_name_guard_refuses_an_incomplete_table(monkeypatch) -> None:
    """The guard runs at import, so a later edit needs it callable to be tested."""
    from khepri.rra.rendering import wording

    broken = {
        language: dict(names)
        for language, names in wording.BUSINESS_SHEET_NAMES.items()
    }
    del broken[LANGUAGE_ENGLISH]["profitability"]
    monkeypatch.setattr(wording, "BUSINESS_SHEET_NAMES", broken)

    import pytest

    with pytest.raises(RuntimeError, match="every business worksheet needs a name"):
        wording._assert_business_sheet_names_complete()


def test_the_name_guard_refuses_a_name_over_budget(monkeypatch) -> None:
    from khepri.rra.rendering import wording

    broken = {
        language: dict(names)
        for language, names in wording.BUSINESS_SHEET_NAMES.items()
    }
    broken[LANGUAGE_ENGLISH]["profitability"] = "P" * 22
    monkeypatch.setattr(wording, "BUSINESS_SHEET_NAMES", broken)

    import pytest

    with pytest.raises(RuntimeError, match="exceeds the bilingual budget"):
        wording._assert_business_sheet_names_complete()
