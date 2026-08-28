"""RRA-009: the business/audit split in the governed workbook."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

from khepri.rra.bundle import ReportBundle
from khepri.rra.narrative import LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from tests.rra003_contract_fixtures import landed_sections
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


def _cells_of_sheet(
    bundle: ReportBundle,
    directory: Path,
    *,
    sheet_number: int,
) -> list[str]:
    """The text cells one worksheet wrote, resolved through the shared string table.

    XlsxWriter writes every string cell as an index into `sharedStrings.xml`, so a
    per-sheet assertion has to resolve them; reading the shared table alone says
    what the *workbook* holds and never which sheet holds it, which is exactly the
    distinction a business/audit separation test needs.
    """
    with zipfile.ZipFile(_workbook_bytes(bundle, directory)) as archive:
        shared = re.findall(
            r"<t[^>]*>(.*?)</t>", archive.read("xl/sharedStrings.xml").decode(), re.S
        )
        sheet = archive.read(f"xl/worksheets/sheet{sheet_number}.xml").decode()
    indexes = [int(value) for value in re.findall(r"<v>(\d+)</v>", sheet)]
    return [shared[index] for index in indexes if index < len(shared)]


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


def test_the_rich_fixture_presents_every_section_that_has_landed() -> None:
    """Every analysis section publishes, once its family is admitted.

    A fixed list of five had to be edited once per family commit, and a missed
    edit reads as a regression rather than as the designed window.
    `landed_sections()` asks the gate, using the formula version this bundle was
    *built* under -- pinned to the published predecessor, so the families
    admitted against it are the ones that have not moved.
    """
    from khepri.rra.bundle import _FAMILIES, SECTION_GROWTH

    bundle = rich_bundle()
    landed = landed_sections(bundle.identity.formula_version)
    states = {section.section_id: section.state for section in bundle.sections}

    # Growth is the one landed family this fixture cannot present, and the
    # reason is the fixture's own content rather than the gate: it carries one
    # posted return so the returns metric has something to state, and
    # `RRA-008` requires growth's two aligned windows to be "return-free
    # posted-sale populations" -- a return "refuses growth". Refusing here is
    # the specification being honoured, not a family failing to land.
    for section_id in _FAMILIES:
        if section_id == SECTION_GROWTH:
            assert states[section_id] == "refused", (
                "the fixture holds a posted return, so growth must refuse"
            )
            continue
        assert states[section_id] == (
            "present" if section_id in landed else "refused"
        ), section_id
    # `overview` states the package's own figures and has no family to gate it.
    assert states["overview"] == "present"


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


def test_business_sheets_come_before_the_audit_sheets(tmp_path: Path) -> None:
    """Worksheet order *is* the information architecture: it is what a reader sees
    on opening the file."""
    from khepri.rra.rendering import wording

    names = _sheet_names(rich_bundle(), tmp_path)
    summary = names.index(
        wording.BUSINESS_SHEET_NAMES[LANGUAGE_ENGLISH]["executive_summary"]
    )

    assert summary < names.index("Audit Trail")
    assert summary < names.index("Provenance")
    assert names.index("Data Limitations") < names.index("Audit Trail")


def test_a_business_sheet_with_no_figure_is_absent(tmp_path: Path) -> None:
    """A worksheet whose only content is an apology is worse than its absence, so
    the business tab set varies by dataset. The audit sheets do not."""
    from khepri.rra.rendering import wording

    names = _sheet_names(_plain_bundle(), tmp_path)
    profitability = wording.BUSINESS_SHEET_NAMES[LANGUAGE_ENGLISH]["profitability"]

    assert profitability not in names
    assert "Audit Trail" in names


def test_a_business_sheet_appears_when_its_figures_exist(tmp_path: Path) -> None:
    from khepri.rra.rendering import wording

    names = _sheet_names(rich_bundle(), tmp_path)

    assert wording.BUSINESS_SHEET_NAMES[LANGUAGE_ENGLISH]["profitability"] in names


def test_every_business_sheet_is_written_in_both_languages(tmp_path: Path) -> None:
    from khepri.rra.rendering import wording

    names = _sheet_names(rich_bundle(), tmp_path)
    for language in REQUIRED_LANGUAGES:
        assert wording.BUSINESS_SHEET_NAMES[language]["executive_summary"] in names


def test_the_audit_trail_carries_every_identifier(tmp_path: Path) -> None:
    bundle = rich_bundle()
    strings = _shared_strings(bundle, tmp_path)

    for figure in bundle.figures:
        assert figure.figure_id in strings, figure.figure_id
        assert figure.citation_id in strings, figure.citation_id
    for section in bundle.sections:
        assert section.section_id in strings, section.section_id


def test_no_business_sheet_carries_an_identifier_value(tmp_path: Path) -> None:
    """The business figure table is two columns, and neither holds an identifier.

    Asserted on the written cells of a business sheet rather than on column header
    strings: "Figure" is the business name header *and* the audit trail's identifier
    header -- the same word naming two different things -- so comparing headers
    reports a false positive. What must be true is that no `figure_id` or
    `citation_id` value appears on a business sheet.
    """
    bundle = rich_bundle()
    business_cells = _cells_of_sheet(bundle, tmp_path, sheet_number=1)

    assert business_cells, "the first business sheet wrote no cells"
    identifiers = {figure.figure_id for figure in bundle.figures} | {
        figure.citation_id for figure in bundle.figures
    }
    assert not (set(business_cells) & identifiers), sorted(
        set(business_cells) & identifiers
    )
    # And it is genuinely the business sheet: it names a measure in business words.
    assert "Revenue" in business_cells


def test_the_section_state_reaches_no_worksheet(tmp_path: Path) -> None:
    """`state` is Internal under RRA-009, so it is not written at all -- not even to
    the audit trail. A row carrying a reason is a refused section by construction."""
    strings = _shared_strings(_plain_bundle(), tmp_path)

    for state in ("present", "refused"):
        assert f">{state}<" not in strings, state


def test_the_limitations_sheet_states_caveats_as_prose(tmp_path: Path) -> None:
    from khepri.rra.rendering.wording import caveat_prose

    bundle = _plain_bundle()
    strings = _shared_strings(bundle, tmp_path)

    assert bundle.caveats
    for caveat in bundle.caveats:
        assert caveat_prose(caveat.code, LANGUAGE_ENGLISH) in strings, caveat.code


def test_the_limitations_sheet_states_refusals_as_prose(tmp_path: Path) -> None:
    from khepri.rra.rendering.wording import section_refusal_message

    bundle = ReportBundle.of(package_for(ROWS[:2]))
    strings = _shared_strings(bundle, tmp_path)
    refused = [section for section in bundle.sections if section.reason]

    assert refused
    for section in refused:
        # `section_refusal_message`, which is what the renderer writes. One
        # reason is shared by all four families, so its prose is a template
        # naming the section it refers to -- comparing the bare `refusal_message`
        # template was only ever true of the reasons that name themselves, and
        # held until a fixture could reach the shared one.
        assert (
            section_refusal_message(
                section.section_id, section.reason, LANGUAGE_ENGLISH
            )
            in strings
        ), section.section_id


def test_every_charted_section_still_gets_a_chart(tmp_path: Path) -> None:
    """`_draw_charts` skips a block whose business sheet was omitted, and that skip
    is silent by design -- this is what keeps it from hiding a real loss."""
    bundle = rich_bundle()
    charted = [section for section in bundle.sections if section.chart is not None]

    with zipfile.ZipFile(_workbook_bytes(bundle, tmp_path)) as archive:
        parts = [
            name
            for name in archive.namelist()
            if name.startswith("xl/charts/chart") and name.endswith(".xml")
        ]

    assert charted
    assert len(parts) == len(charted) * len(REQUIRED_LANGUAGES)


def test_the_chart_data_sheet_is_still_present(tmp_path: Path) -> None:
    """`_series_range` addresses it by name and `excel.py` requires it visible on
    APP-013 grounds. Reordering the workbook is exactly the change that breaks a
    chart silently -- one pointing at a missing sheet renders empty."""
    names = _sheet_names(rich_bundle(), tmp_path)

    assert any("chartdata" in name for name in names)


def test_the_workbook_still_reconciles(tmp_path: Path) -> None:
    """The property the whole restructure rests on.

    `reconcile` compares the `SurfaceContent` claim and never opens the file, so
    every other test in this module could pass while the workbook silently stopped
    reconciling -- and equally, reconciliation could keep passing while the file
    lost a cell. Both directions are asserted, here and below.
    """
    from khepri.rra.bundle import reconcile

    for bundle in (rich_bundle(), _plain_bundle()):
        content = ExcelSurfaceRenderer(directory=tmp_path).render(bundle)
        reconcile(content, bundle=bundle)


def test_the_claim_still_states_every_figure(tmp_path: Path) -> None:
    """A surface that relocated a figure and also stopped claiming it would
    reconcile, and would have lost the figure."""
    bundle = rich_bundle()
    content = ExcelSurfaceRenderer(directory=tmp_path).render(bundle)

    expected = {figure.figure_id for figure in bundle.figures}
    for entry in content.languages:
        assert {stated.figure_id for stated in entry.stated} == expected, entry.language


def test_the_claim_still_states_every_section(tmp_path: Path) -> None:
    bundle = rich_bundle()
    content = ExcelSurfaceRenderer(directory=tmp_path).render(bundle)

    for entry in content.languages:
        assert entry.sections == bundle.section_ids, entry.language


def test_every_figure_value_is_still_in_the_file(tmp_path: Path) -> None:
    """The other direction: the claim could be complete while the workbook dropped
    a cell, and reconciliation would never notice."""
    bundle = rich_bundle()
    strings = _shared_strings(bundle, tmp_path)

    for figure in bundle.figures:
        for language in REQUIRED_LANGUAGES:
            assert figure.renderings[language] in strings, (
                figure.figure_id,
                language,
            )


def test_the_governed_disclosure_reaches_the_workbook(tmp_path: Path) -> None:
    """RRA-009 carries it verbatim on every report.

    It used to live on the index sheet, which the business sheets replaced -- so
    removing that sheet without moving the disclosure would have dropped it from the
    workbook entirely. This is the test that caught exactly that.
    """
    bundle = rich_bundle()
    strings = _shared_strings(bundle, tmp_path)

    for language in REQUIRED_LANGUAGES:
        assert bundle.disclosure(language) in strings, language


def test_regenerating_the_workbook_produces_the_same_sheets(tmp_path: Path) -> None:
    """Deterministic regeneration. A sheet order that varied per run would make the
    workbook's identity a function of something other than the data."""
    bundle = rich_bundle()
    one = tmp_path / "one"
    two = tmp_path / "two"
    one.mkdir()
    two.mkdir()

    assert _sheet_names(bundle, one) == _sheet_names(bundle, two)
