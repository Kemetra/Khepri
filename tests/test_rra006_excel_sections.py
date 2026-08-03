"""A worksheet per governed analysis, in each language.

The workbook used to run all five sections together in one grid per language. That was
the surface disagreeing with the other two about what a section is: the page gives each
one a heading and the printed report gives each one a page, so a reader moving between
them found five analyses in one sheet and no way to address a single analysis.

A refused section still gets a worksheet. A missing sheet is the one disclosure a reader
cannot distinguish from an analysis nobody ran.
"""

from __future__ import annotations

import hashlib
import tempfile
from datetime import date, timedelta
from pathlib import Path

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    ORDERED_SECTIONS,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_PRESENT,
    SECTION_REFUSED,
    FactPackage,
    ReportBundle,
)
from khepri.rra.facts import build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.profiling import build_profile
from khepri.rra.rendering import excel
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from tests import rra_workbooks

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
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
    )


def workbook_of(rows: list | None = None) -> rra_workbooks.ReadWorkbook:
    """Render, then reopen the file that was written rather than trusting the claim."""
    bundle = ReportBundle.of(package(rows))
    renderer = ExcelSurfaceRenderer(directory=Path(tempfile.mkdtemp()))
    renderer.render(bundle)
    return rra_workbooks.read(renderer.path_for(bundle).read_bytes())


def test_one_worksheet_per_section_per_language() -> None:
    names = set(workbook_of().cells)
    for section_id in ORDERED_SECTIONS:
        for language in REQUIRED_LANGUAGES:
            assert excel._section_sheet(section_id, language) in names, (
                section_id,
                language,
            )
    assert excel._PROVENANCE_SHEET in names


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


def test_a_section_sheet_carries_only_its_own_figures() -> None:
    """A figure on the wrong sheet is cited correctly and read under the wrong heading.

    That is the workbook's version of the misplacement the page's section index and the
    figure `section` field exist to prevent, and no text comparison would catch it.
    """
    workbook = workbook_of()
    for section_id in ORDERED_SECTIONS:
        stated = _sections_named_on(workbook, section_id)
        assert stated <= {section_id}, (section_id, stated)

    # And at least one sheet actually carried figures, so the loop above is not
    # vacuously true over five empty sheets.
    assert any(_sections_named_on(workbook, section_id) for section_id in ORDERED_SECTIONS)


def _sections_named_on(
    workbook: rra_workbooks.ReadWorkbook,
    section_id: str,
) -> set[str]:
    """Every section named in the Section column of one section's sheet."""
    headers = list(excel._FIGURE_COLUMNS[LANGUAGE_ENGLISH])
    section_at = headers.index(excel._FIGURE_COLUMNS[LANGUAGE_ENGLISH][2])
    rows = workbook.cells[excel._section_sheet(section_id, LANGUAGE_ENGLISH)]
    if headers not in rows:
        return set()
    return {
        row[section_at]
        for row in rows[rows.index(headers) + 1 :]
        if len(row) > section_at
    }


def test_a_refused_section_still_gets_its_worksheet() -> None:
    """Two days settle no period, so the comparison refuses.

    The sheet exists, states the reason, and carries no figure table -- which is the
    shape that lets a reader tell a refused analysis from an absent one.
    """
    workbook = workbook_of(ROWS[:2])
    bundle = ReportBundle.of(package(ROWS[:2]))
    refused = next(
        section for section in bundle.sections if section.section_id == SECTION_COMPARISON
    )
    assert refused.state == SECTION_REFUSED

    for language in REQUIRED_LANGUAGES:
        rows = workbook.cells[excel._section_sheet(SECTION_COMPARISON, language)]
        flattened = [cell for row in rows for cell in row]
        assert SECTION_REFUSED in flattened
        assert refused.reason in flattened
        assert list(excel._FIGURE_COLUMNS[language]) not in rows


def test_the_index_sheet_states_every_section_and_carries_no_figures() -> None:
    """A reader lands on what the report says about itself, then chooses an analysis."""
    workbook = workbook_of()
    for language in REQUIRED_LANGUAGES:
        rows = workbook.cells[excel._REPORT_SHEET[language]]
        flattened = [cell for row in rows for cell in row]
        for section_id in ORDERED_SECTIONS:
            assert section_id in flattened, (language, section_id)
        assert SECTION_PRESENT in flattened
        # The figure table moved to the section sheets.
        assert list(excel._FIGURE_COLUMNS[language]) not in rows


def test_a_sections_own_caveats_are_written_on_its_sheet() -> None:
    """A scoped caveat under the report's heading says the whole dataset is qualified.

    On the index it is written beside the section it names, because that is where a
    reader sees every caveat at once. On the section sheet the heading already supplies
    the scope.
    """
    workbook = workbook_of()
    bundle = ReportBundle.of(package())
    scoped = [caveat for caveat in bundle.caveats if caveat.section is not None]
    assert scoped

    for caveat in scoped:
        rows = workbook.cells[excel._section_sheet(caveat.section, LANGUAGE_ENGLISH)]
        assert [caveat.code] in rows, caveat


def test_both_languages_publish_the_same_sheets() -> None:
    names = set(workbook_of().cells)
    english = {
        name.removeprefix("en_") for name in names if name.startswith("en_")
    }
    arabic = {name.removeprefix("ar_") for name in names if name.startswith("ar_")}
    assert english == arabic
