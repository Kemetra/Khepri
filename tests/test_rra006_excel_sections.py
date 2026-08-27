"""A worksheet per business concept, in each language.

The workbook once ran all five governed sections together in one grid, then moved to
a worksheet per section. RRA-009 replaced that with a worksheet per *business
concept*: business sheets named by business meaning come first, and every identifier
moved onto a single audit trail after them.

The guarantees this file defends survived that move and are restated against the new
shape rather than deleted. A figure must still be readable under the right heading, a
refusal must still be visible to a reader rather than only present in the claim, and
the two languages must still publish the same sheets. What changed is where each of
those is checked.

Note that the business tab set now varies by dataset: a sheet whose figures are all
absent is omitted, because a worksheet whose only content is an apology is worse than
its absence. The audit sheets do not vary.
"""

from __future__ import annotations

import hashlib
import tempfile
from datetime import date, timedelta
from pathlib import Path

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    ORDERED_SECTIONS,
    SECTION_CONCENTRATION,
    FactPackage,
    ReportBundle,
)
from khepri.rra.facts import AdmittedInput, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile
from khepri.rra.rendering import excel
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from tests import rra_workbooks
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    published_mapping_identity,
)

HEADER = b"date,revenue,units,invoice_no,product\n"
START = date(2026, 1, 5)
ROWS = [
    ("100.00", 4, "Water"),
    ("150.00", 5, "Water"),
    ("120.00", 4, "Juice"),
    ("200.00", 8, "Water"),
    ("90.00", 3, "Juice"),
]


def package(rows: list | None = None) -> FactPackage:
    body = b"".join(
        f"{(START + timedelta(days=index)).isoformat()},{amount},{units},"
        f"INV-{index},{product}\n".encode()
        for index, (amount, units, product) in enumerate(rows or ROWS)
    )
    content = HEADER + body
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    # Built under the published mapping identity: this module's subject is not
    # the version gate, so its packages must keep combining a triple
    # `versions.ADMITTED_PACKAGE_PAIRS` admits. The whole build sits inside the
    # block because `facts._assert_derived_from_profile` re-derives the mapping
    # and compares it by value, so restamping the object afterwards would fail
    # that provenance guard instead.
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
        )


def workbook_of(rows: list | None = None) -> rra_workbooks.ReadWorkbook:
    """Render, then reopen the file that was written rather than trusting the claim."""
    bundle = ReportBundle.of(package(rows))
    renderer = ExcelSurfaceRenderer(directory=Path(tempfile.mkdtemp()))
    renderer.render(bundle)
    return rra_workbooks.read(renderer.path_for(bundle).read_bytes())


def test_one_worksheet_per_presented_business_concept_per_language() -> None:
    """Every business sheet with figures is written, in both languages."""
    from khepri.rra.rendering.excel_layout import BUSINESS_SHEETS
    from khepri.rra.rendering.wording import BUSINESS_SHEET_NAMES

    workbook = workbook_of()
    bundle = ReportBundle.of(package())
    rendered_metrics = {figure.metric for figure in bundle.figures}

    presented = [
        sheet for sheet in BUSINESS_SHEETS if rendered_metrics & set(sheet.metrics)
    ]
    assert presented, "this fixture presents no business sheet at all"
    for sheet in presented:
        for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
            name = BUSINESS_SHEET_NAMES[language][sheet.key]
            assert name in workbook.cells, (name, language)


def test_a_sheet_name_is_an_address_and_is_not_translated() -> None:
    """Both workbooks name the same sheet, so a reference resolves in either.

    The language belongs inside the sheet -- in its headings and its figures -- not in
    the name a reader or a tool has to type.
    """
    assert excel._section_sheet(SECTION_CONCENTRATION, LANGUAGE_ENGLISH) == (
        "en_concentration"
    )
    assert excel._section_sheet(SECTION_CONCENTRATION, LANGUAGE_ARABIC) == (
        "ar_concentration"
    )


def test_a_business_sheet_lists_only_the_figures_it_presents() -> None:
    """A figure on the wrong sheet is read under the wrong heading.

    That is the workbook's version of the misplacement the page's section index
    exists to prevent, and no text comparison would catch it. Checked against the
    layout table's metric list rather than a section identifier, because a business
    sheet is defined by the figures it presents.
    """
    from khepri.rra.rendering.excel import _business_name
    from khepri.rra.rendering.excel_layout import BUSINESS_SHEETS
    from khepri.rra.rendering.wording import BUSINESS_SHEET_NAMES

    workbook = workbook_of()
    bundle = ReportBundle.of(package())
    checked = 0
    for sheet in BUSINESS_SHEETS:
        name = BUSINESS_SHEET_NAMES[LANGUAGE_ENGLISH][sheet.key]
        if name not in workbook.cells:
            continue
        expected = {
            _business_name(figure, LANGUAGE_ENGLISH)
            for figure in bundle.figures
            if figure.metric in sheet.metrics
        }
        written = {row[0] for row in workbook.cells[name] if row and row[0]}
        unexplained = written - expected - {
            excel._BUSINESS_COLUMNS[LANGUAGE_ENGLISH][0],
            excel._DISCLOSURE_HEADING[LANGUAGE_ENGLISH],
        }
        assert not unexplained, (sheet.key, sorted(unexplained))
        checked += 1
    assert checked, "no business sheet was written, so the loop proved nothing"


def test_a_refused_analysis_is_stated_where_a_reader_will_find_it() -> None:
    """A refusal invisible to a reader is the one disclosure they cannot infer.

    It used to be an empty section sheet carrying a reason code. RRA-009 states it as
    customer prose on the limitations sheet, and keeps the raw code on the audit
    trail -- so both halves are asserted, in the places they now live.
    """
    from khepri.rra.rendering.wording import section_refusal_message

    # Two days settle no prior period, so the comparison and growth families refuse.
    rows = ROWS[:2]
    bundle = ReportBundle.of(package(rows))
    workbook = workbook_of(rows)
    refused = [section for section in bundle.sections if section.reason]
    assert refused

    limitations = {
        cell
        for row in workbook.cells[excel._LIMITATIONS_SHEET[LANGUAGE_ENGLISH]]
        for cell in row
        if cell
    }
    audit = {
        cell
        for row in workbook.cells[excel._AUDIT_SHEET[LANGUAGE_ENGLISH]]
        for cell in row
        if cell
    }
    for section in refused:
        message = section_refusal_message(
            section.section_id, section.reason, LANGUAGE_ENGLISH
        )
        assert message in limitations, section.section_id
        assert section.reason in audit, section.section_id


def test_the_audit_trail_states_every_section_and_every_figure() -> None:
    """The index sheet's job moved to the audit trail, which is where a reader who
    wants to address a single analysis or quote a single figure now looks."""
    workbook = workbook_of()
    bundle = ReportBundle.of(package())
    audit = {
        cell
        for row in workbook.cells[excel._AUDIT_SHEET[LANGUAGE_ENGLISH]]
        for cell in row
        if cell
    }

    for section_id in ORDERED_SECTIONS:
        assert section_id in audit, section_id
    for figure in bundle.figures:
        assert figure.figure_id in audit, figure.figure_id


def test_every_caveat_reaches_the_limitations_sheet_as_prose() -> None:
    """A scoped caveat used to be written on the sheet whose heading gave its scope.

    RRA-009 states every caveat as customer prose on one limitations sheet, and
    `_reconcile_language` compares caveat sets for equality -- so a subset is a
    refused report rather than a tidier sheet, and completeness is the assertion.
    """
    from khepri.rra.rendering.wording import caveat_prose

    workbook = workbook_of()
    bundle = ReportBundle.of(package())
    assert bundle.caveats

    for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
        written = {
            cell
            for row in workbook.cells[excel._LIMITATIONS_SHEET[language]]
            for cell in row
            if cell
        }
        for caveat in bundle.caveats:
            assert caveat_prose(caveat.code, language) in written, (
                caveat.code,
                language,
            )


def test_both_languages_publish_the_same_sheets() -> None:
    names = set(workbook_of().cells)
    english = {
        name.removeprefix("en_") for name in names if name.startswith("en_")
    }
    arabic = {name.removeprefix("ar_") for name in names if name.startswith("ar_")}
    assert english == arabic
