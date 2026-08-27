from __future__ import annotations

import hashlib
import itertools
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    KIND_VALUE,
    LANGUAGE_DIRECTION,
    NARRATIVE_OMITTED,
    OUTCOME_DELIVERED,
    REQUIRED_SURFACES,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    SURFACE_EXCEL,
    SURFACE_PDF,
    SURFACE_WEB,
    BundleAssembler,
    BundleIdentity,
    CitedFigure,
    ReportBundle,
    Section,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
    reconcile,
)
from khepri.rra.facts import AdmittedInput, FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile
from khepri.rra.rendering import excel
from khepri.rra.rendering.excel import (
    EXCEL_SURFACE_VERSION,
    GOVERNED_LABELS,
    ExcelSurfaceRenderer,
    WorkbookUnavailable,
    _business_name,
)
from khepri.rra.rendering.wording import caveat_prose
from tests import rra_workbooks
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    published_mapping_identity,
)

# The size the stand-in web and PDF renderers report. They write no file, so
# the number is arbitrary; only the workbook's own size is measured here.
STAND_IN_SIZE = 2048

GOLDEN = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)

# Every prefix Excel treats as the start of a formula, and a value Excel would
# otherwise turn into a clickable link. A governed label cannot legitimately
# look like any of these, which is exactly why the renderer must not trust that
# it never will.
HOSTILE_LABELS = (
    "=1+1",
    '=HYPERLINK("http://evil.example","click")',
    "+1+1",
    "-1+1",
    "@SUM(A1:A9)",
    "http://evil.example/x",
    "www.evil.example",
)


def package(content: bytes = GOLDEN) -> FactPackage:
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


def hostile_bundle() -> ReportBundle:
    """A bundle whose labels are everything upstream sanitizing would remove.

    Built directly rather than from a dataset on purpose. `profiling._sanitize`
    already strips these prefixes, so a package can never carry them, and a
    renderer that relied on that would be one upstream change away from writing
    a live formula into a customer's workbook.
    """
    figures = tuple(
        CitedFigure(
            figure_id=f"cit_hostile/{KIND_VALUE}/{position}",
            citation_id="cit_hostile",
            fact_id="fct_hostile",
            metric="revenue_by_category",
            unit_kind="monetary",
            kind=KIND_VALUE,
            section=SECTION_OVERVIEW,
            label=label,
            value=Decimal("1.00"),
            renderings={LANGUAGE_ENGLISH: "1.00", LANGUAGE_ARABIC: "١٫٠٠"},
        )
        for position, label in enumerate(HOSTILE_LABELS)
    )
    return ReportBundle(
        identity=BundleIdentity.of(package()),
        figures=figures,
        caveats=(),
        narrative_state=NARRATIVE_OMITTED,
        # The bundle indexes the figures it carries. Declaring no section while
        # holding figures is a bundle disagreeing with itself, which every
        # surface would copy both halves of into its claim.
        sections=(
            Section(
                section_id=SECTION_OVERVIEW,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=tuple(figure.figure_id for figure in figures),
                chart=None,
            ),
        ),
    )


def rendered(
    bundle: ReportBundle,
    directory: Path,
) -> tuple[SurfaceContent, rra_workbooks.ReadWorkbook]:
    """Render the workbook, then reopen the file that was actually written."""
    renderer = ExcelSurfaceRenderer(directory=directory)
    content = renderer.render(bundle)
    return content, rra_workbooks.read(renderer.path_for(bundle).read_bytes())


def presented(workbook: rra_workbooks.ReadWorkbook) -> SurfaceContent:
    """Rebuild, from the sheets alone, what the workbook presents.

    This is the whole point of opening the file. `reconcile` only inspects the
    object a renderer returns, so a renderer that returned a flawless claim and
    wrote an empty workbook would reconcile perfectly.

    The size comes from the archive that was opened, never from the claim being
    checked. Taking it from the claim would make every comparison with one
    self-fulfilling.
    """
    return SurfaceContent(
        surface=SURFACE_EXCEL,
        bundle_id=_provenance(workbook)["bundle_id"],
        languages=tuple(
            _presented_language(workbook, language)
            for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)
        ),
        output_size_bytes=workbook.size_bytes,
    )


def _presented_language(
    workbook: rra_workbooks.ReadWorkbook,
    language: str,
) -> SurfaceLanguage:
    """Read one language's sheet as a table, not as a bag of strings.

    Row by row on purpose. A reconstruction that asked "does this figure's text
    appear anywhere on the sheet?" would answer yes for a dropped row whenever
    some other cell happened to carry the same number.
    """
    # The audit trail, which is where RRA-009 put the identifier table this helper
    # reads. It is the same table under the same headers, moved off the business
    # sheets rather than rebuilt, so this reader is repointed and not rewritten.
    name = excel._AUDIT_SHEET[language]
    rows = workbook.cells[name]
    headers = list(excel._FIGURE_COLUMNS[language])
    # The section comes from its own cell, never from a constant. Hardcoding the
    # overview here would have made every figure the four RRA-008 families place
    # read back as an overview figure, and this helper exists precisely so that a
    # workbook which says something other than the claim is caught.
    section_at = headers.index(excel._FIGURE_COLUMNS[language][2])
    # One table now, not one per section. RRA-009 moved every identifier onto the
    # audit trail, so the figures are read from that single block in the order it
    # writes them -- which is `bundle.figures` order, the same order the claim
    # states them in.
    figures_at = rows.index(headers)
    stated = tuple(
        StatedFigure(figure_id=row[0], text=row[-1], section=row[section_at])
        for row in rows[figures_at + 1 :]
        if row
    )
    return SurfaceLanguage(
        language=language,
        direction="rtl" if 'rightToLeft="1"' in workbook.sheets[name] else "ltr",
        # Read from the audit trail's sections block, not derived from the figure
        # rows. A refused section has no figure to derive from, so deriving would
        # silently drop it -- and the workbook would then present four sections
        # while claiming five, which reconciliation cannot see because it never
        # opens the file.
        sections=_declared_sections(workbook, language),
        stated=stated,
        # Empty, and deliberately so: this helper reads the sheets alone, and after
        # RRA-009 the sheets no longer carry caveat *codes*. They carry customer
        # prose on the limitations sheet, and prose cannot be parsed back into a
        # code -- the mapping is one-way by design, and a result-tier refusal's
        # message is composed from a figure's own identity.
        #
        # So the caller compares everything the file can still prove and asserts the
        # caveats separately. `test_rra009_excel_split.py`'s
        # `test_the_limitations_sheet_states_caveats_as_prose` is what holds that
        # every caveat reaches the workbook.
        caveats=(),
        disclosure=_presented_disclosure(workbook, language),
    )


def _presented_disclosure(
    workbook: rra_workbooks.ReadWorkbook,
    language: str,
) -> str:
    """The governed disclosure, read off the sheet that carries it."""
    for rows in workbook.cells.values():
        for row in rows:
            if row[:1] == [excel._DISCLOSURE_HEADING[language]] and len(row) > 1:
                return row[1]
    return ""


def _declared_sections(
    workbook: rra_workbooks.ReadWorkbook,
    language: str,
) -> tuple[str, ...]:
    """The sections the audit trail names, in the order it names them.

    The section table moved to the audit trail with RRA-009 and lost its `state`
    column there -- `state` is Internal and reaches no customer surface -- so the
    columns are `_AUDIT_SECTION_COLUMNS` and the block ends at the figures heading
    rather than at the caveats one.
    """
    rows = workbook.cells[excel._AUDIT_SHEET[language]]
    start = rows.index(list(excel._AUDIT_SECTION_COLUMNS[language])) + 1
    end = rows.index([excel._FIGURES_HEADING[language]])
    return tuple(row[0] for row in rows[start:end])


def _section_figure_rows(
    workbook: rra_workbooks.ReadWorkbook,
    language: str,
    section_id: str,
    headers: list[str],
) -> list[list[str]]:
    """The figure rows on one section's sheet, and none if it has no table.

    A refused section has a sheet and no figures, which is the shape that makes the
    refusal visible in the workbook rather than only in the claim.
    """
    rows = workbook.cells[excel._section_sheet(section_id, language)]
    if headers not in rows:
        return []
    start = rows.index(headers) + 1
    end = len(rows)
    if [excel._CAVEATS_HEADING[language]] in rows:
        end = rows.index([excel._CAVEATS_HEADING[language]])
    return [row for row in rows[start:end] if row]


def _provenance(workbook: rra_workbooks.ReadWorkbook) -> dict[str, str]:
    rows = next(
        rows
        for rows in workbook.cells.values()
        if any(row[:1] == ["bundle_id"] for row in rows)
    )
    return {row[0]: row[1] for row in rows if len(row) > 1}


class FaithfulRenderer:
    """A stand-in for the web and PDF surfaces, which are separate slices."""

    def __init__(self, surface: str) -> None:
        self._surface = surface

    @property
    def surface(self) -> str:
        return self._surface

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        return SurfaceContent(
            surface=self._surface,
            bundle_id=bundle.bundle_id,
            languages=tuple(
                SurfaceLanguage(
                    language=language,
                    direction=LANGUAGE_DIRECTION[language],
                    sections=bundle.section_ids,
                    stated=tuple(
                        StatedFigure(
                            figure_id=figure.figure_id,
                            text=figure.renderings[language],
                            section=figure.section,
                        )
                        for figure in bundle.figures
                    ),
                    caveats=bundle.caveats,
                    disclosure=bundle.disclosure(language),
                )
                for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
            ),
            output_size_bytes=STAND_IN_SIZE,
        )


# --- the workbook presents what the renderer claims ------------------------


def test_the_workbook_surface_reports_the_size_of_the_file_it_wrote(tmp_path: Path) -> None:
    # RRA-007 records output size per stage. This surface's payload is a file, so
    # the size is the file's, read back from disk rather than predicted.
    bundle = ReportBundle.of(package())
    renderer = ExcelSurfaceRenderer(directory=tmp_path)

    content = renderer.render(bundle)

    assert content.output_size_bytes == len(renderer.path_for(bundle).read_bytes())
    assert content.output_size_bytes > 0


def test_the_workbook_on_disk_presents_exactly_what_the_renderer_claims(tmp_path: Path) -> None:
    bundle = ReportBundle.of(package())

    content, workbook = rendered(bundle, tmp_path)
    surface = presented(workbook)

    # Compared field by field rather than whole. This test's purpose is unchanged --
    # a renderer that returned a flawless claim and wrote an empty workbook must
    # fail here -- but RRA-009 moved caveats onto the limitations sheet as customer
    # prose, and prose cannot be parsed back into the codes a claim carries. Every
    # other field is still compared exactly, and the caveats are asserted as prose
    # by `test_both_languages_carry_the_same_figures_and_caveats`.
    assert surface.bundle_id == content.bundle_id
    assert surface.output_size_bytes == content.output_size_bytes
    for read, claimed in zip(surface.languages, content.languages, strict=True):
        assert read.language == claimed.language
        assert read.direction == claimed.direction
        assert read.sections == claimed.sections
        assert read.stated == claimed.stated
        assert read.disclosure == claimed.disclosure

    reconcile(content, bundle=bundle)


def test_the_claimed_surface_reconciles_and_completes_a_bundle(tmp_path: Path) -> None:
    # The renderer satisfies `SurfaceRenderer` in the only way that matters:
    # the assembler accepts it beside the other two surfaces.
    bundle = ReportBundle.of(package())
    assembler = BundleAssembler(
        renderers=[
            FaithfulRenderer(SURFACE_WEB),
            FaithfulRenderer(SURFACE_PDF),
            ExcelSurfaceRenderer(directory=tmp_path),
        ]
    )

    result = assembler.assemble(bundle)

    assert result.incomplete is False
    assert result.attempt.outcome == OUTCOME_DELIVERED
    assert [entry.surface for entry in result.surfaces or ()] == list(REQUIRED_SURFACES)


# --- formula and URL injection --------------------------------------------


def test_a_hostile_label_is_written_as_an_inert_literal(tmp_path: Path) -> None:
    # The headline risk. A label beginning `=`, `+`, `-` or `@` must reach the
    # cell as text, and a label shaped like an address must not become a link.
    bundle = hostile_bundle()

    _, workbook = rendered(bundle, tmp_path)

    for label in HOSTILE_LABELS:
        # Verbatim, leading character included: inert is not the same as
        # stripped, and a renderer that edits a label is deciding content.
        assert label in workbook.texts, label
    for name, xml in workbook.sheets.items():
        # A formula cell carries an `<f>` element and a linked cell is listed in
        # a `<hyperlinks>` element. Neither may exist, however the text reads --
        # note that `=HYPERLINK(...)` survives above *as a string*, which is the
        # distinction being drawn.
        assert "<f>" not in xml and "<f " not in xml, name
        assert "<hyperlinks" not in xml, name
    for name, part in workbook.parts.items():
        if name.endswith(".rels"):
            assert "/hyperlink" not in part, name
    assert not [name for name in workbook.parts if name.startswith("xl/worksheets/_rels")]


def test_the_workbook_disables_formula_and_url_interpretation() -> None:
    # DEC-005, verbatim: "Formula and automatic URL interpretation are disabled
    # for customer-derived strings." Every cell goes through `write_string`,
    # which never interprets, so these options are the second line rather than
    # the first -- but the decision names them, so they are asserted.
    assert excel.WORKBOOK_OPTIONS["strings_to_formulas"] is False
    assert excel.WORKBOOK_OPTIONS["strings_to_urls"] is False
    assert excel.WORKBOOK_OPTIONS["strings_to_numbers"] is False


def test_no_worksheet_cell_is_written_as_a_number(tmp_path: Path) -> None:
    # A numeric cell in Excel is an IEEE 754 double, and DEC-005 forbids binary
    # floating point as an authoritative financial fact. Every governed figure
    # is therefore the exact decimal string the fact package produced.
    #
    # `APP-013` permits one exception: a chart series address, on the chart data sheet
    # and nowhere else. So the assertion is a boundary rather than an absence -- the
    # permission holds for that sheet and must not have leaked anywhere a reader could
    # quote a cell as the figure. `test_rra006_excel_charts` holds the other side of
    # it, that the numbers on that sheet are faithful copies of the governed strings.
    _, workbook = rendered(ReportBundle.of(package()), tmp_path)

    permitted = {
        excel._chartdata_sheet(language)
        for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)
    }
    for name, xml in workbook.sheets.items():
        if name in permitted:
            continue
        for cell in xml.split("<c ")[1:]:
            declaration = cell.split(">", 1)[0]
            assert '<v>' not in cell or 't="s"' in declaration or 't="inlineStr"' in declaration, (
                f"{name}: {declaration}"
            )


# --- the renderer never calculates ----------------------------------------


def test_every_cell_is_a_bundle_value_or_a_governed_label(tmp_path: Path) -> None:
    # RRA-006 excludes independent surface calculations. A cell holding text
    # that is neither in the bundle nor in the renderer's governed vocabulary is
    # by definition something the renderer made up.
    bundle = ReportBundle.of(package())

    _, workbook = rendered(bundle, tmp_path)

    allowed = _allowed_text(bundle)
    for text in workbook.texts:
        assert text in allowed, text


def test_a_total_the_bundle_never_published_appears_nowhere(tmp_path: Path) -> None:
    # The direct negative beside the subset check: the renderer had every
    # addend in front of it and did not add them.
    bundle = ReportBundle.of(package())
    published = {figure.renderings[LANGUAGE_ENGLISH] for figure in bundle.figures}
    values = [
        figure
        for figure in bundle.figures
        if figure.kind == KIND_VALUE and figure.value is not None
    ]
    unpublished = next(
        text
        for left, right in itertools.combinations(values, 2)
        if (text := str(left.value + right.value)) not in published
    )

    _, workbook = rendered(bundle, tmp_path)

    assert unpublished not in workbook.texts


def _allowed_identity_text(bundle: ReportBundle) -> set[str]:
    """Report-level vocabulary: identity, governed labels, and the disclosure."""
    identity = bundle.identity.as_document()
    allowed = set(GOVERNED_LABELS)
    allowed |= set(identity)
    allowed |= {str(value) for value in identity.values()}
    allowed |= {bundle.bundle_id, bundle.narrative_state, EXCEL_SURFACE_VERSION}
    allowed |= {caveat.code for caveat in bundle.caveats}
    # A section identifier is governed vocabulary, like a caveat code. The caveats
    # block names the section a scoped caveat qualifies, because one caveats heading
    # per language cannot otherwise tell a report-level warning from an analysis one.
    allowed |= set(bundle.section_ids)
    # A refusal reason is bundle content, and the sections block states it so a
    # workbook reader learns why an analysis is missing rather than just that it is.
    allowed |= {
        section.reason for section in bundle.sections if section.reason is not None
    }
    allowed |= {
        bundle.disclosure(language) for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
    }
    return allowed


def _allowed_figure_text(bundle: ReportBundle) -> set[str]:
    """Every figure's own identifiers, unit, renderings, and label."""
    allowed: set[str] = set()
    for figure in bundle.figures:
        allowed |= {figure.figure_id, figure.citation_id, figure.fact_id, figure.metric}
        allowed.add(figure.unit_kind)
        allowed |= set(figure.renderings.values())
        if figure.label is not None:
            allowed.add(figure.label)
    return allowed


def _allowed_business_names(bundle: ReportBundle) -> set[str]:
    """The composed business row names, enumerated rather than admitted wholesale.

    A business row's name is *composed* rather than looked up: governed wording for
    the measure and its kind, joined to the row's own label, which is bundle
    content. RRA-009 requires that composition -- a bucket emits a value and a
    row-count figure carrying the same metric and label, so a name that dropped
    either half would list two rows a reader cannot tell apart.

    Enumerating the composed forms here rather than widening the check keeps the
    guard's teeth: every part still has to come from the bundle or from governed
    wording, and a name assembled from anything else still fails.
    """
    return {
        _business_name(figure, language)
        for figure in bundle.figures
        for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
    }


def _allowed_chart_series(bundle: ReportBundle) -> set[str]:
    """The chart series values, which are numbers rather than presented strings.

    `_write_chart_number` writes the plotted double, and it must be the *value*
    rather than the presented string: a percentage cannot be plotted as `67.15%`
    on an axis of ratios, and grouping separators are not parseable at all. The
    section sheet still carries the authoritative presented figure, and
    `APP-013` permits this one numeric write precisely because the chartdata
    sheet holds no citation.

    Derived through the renderer's own helper rather than restated here. Writing
    `str(figure.value)` would pass while the two agreed and go stale the moment
    presentation changed again -- which is exactly what happened to this test.
    """
    return {
        _chart_number_text(figure)
        for section in bundle.sections
        if section.chart is not None
        for figure in (excel._plotted(bundle, section.chart) or ())
    }


def _chart_number_text(figure: CitedFigure) -> str:
    """One chart series value as the workbook reader reports it.

    **Formatted the way `xlsxwriter` serializes a double, not the way Python
    reprs one.** It writes `%.16g`, so the plotted `67.15` reaches the sheet as
    `67.15000000000001` -- the same number, spelled to the last bit the double
    actually holds. `str()` would say `67.15` and this guard would fail on a
    provenance question it is not asking.

    That artifact is visible in the chart-data sheet and is the cost of plotting
    the percentage rather than the ratio: `0.6715` happened to round-trip
    cleanly, `67.15` does not. The trade was taken deliberately -- the ratio
    could only be recovered by dividing in the renderer, which `RRA-009` forbids
    -- and the authoritative figure the reader is shown remains the presented
    string on the section sheet, which is unaffected.
    """
    number = excel._chart_number(figure)
    return str(int(number)) if number == int(number) else f"{number:.16g}"


def _allowed_text(bundle: ReportBundle) -> set[str]:
    return (
        _allowed_identity_text(bundle)
        | _allowed_figure_text(bundle)
        | _allowed_business_names(bundle)
        | _allowed_chart_series(bundle)
    )


# --- language parity and layout -------------------------------------------


def test_both_languages_carry_the_same_figures_and_caveats(tmp_path: Path) -> None:
    bundle = ReportBundle.of(package())

    content, workbook = rendered(bundle, tmp_path)
    surface = presented(workbook)

    english, arabic = surface.languages
    assert english.shown == arabic.shown
    assert english.disclosure == bundle.disclosure(LANGUAGE_ENGLISH)
    assert arabic.disclosure == bundle.disclosure(LANGUAGE_ARABIC)

    # Caveat *parity* is still asserted, on the prose the workbook now carries
    # instead of on the codes it used to. RRA-009 moved caveats to the limitations
    # sheet as customer prose, so a code cannot be read back out of the file -- but
    # the property this test defends is that neither language is missing one, and
    # prose proves that just as well.
    assert bundle.caveats
    strings = _workbook_strings(workbook)
    for caveat in bundle.caveats:
        for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
            assert caveat_prose(caveat.code, language) in strings, (
                caveat.code,
                language,
            )

    # The claim carries the codes; the reconstruction from the file cannot. Compared
    # field by field so the parts the file *does* prove are still compared exactly.
    assert content.bundle_id == surface.bundle_id
    assert content.output_size_bytes == surface.output_size_bytes
    for claimed, read in zip(content.languages, surface.languages, strict=True):
        assert claimed.language == read.language
        assert claimed.direction == read.direction
        assert claimed.sections == read.sections
        assert claimed.stated == read.stated
        assert claimed.disclosure == read.disclosure


def _workbook_strings(workbook: rra_workbooks.ReadWorkbook) -> set[str]:
    """Every text cell in the workbook, whichever sheet holds it."""
    return {
        cell
        for rows in workbook.cells.values()
        for row in rows
        for cell in row
        if cell
    }


def test_the_arabic_sheets_are_declared_right_to_left(tmp_path: Path) -> None:
    bundle = ReportBundle.of(package())

    _, workbook = rendered(bundle, tmp_path)

    for sheet in (excel._AUDIT_SHEET, excel._LIMITATIONS_SHEET, excel._CITATION_SHEET):
        assert 'rightToLeft="1"' in workbook.sheets[sheet[LANGUAGE_ARABIC]]
        assert 'rightToLeft="1"' not in workbook.sheets[sheet[LANGUAGE_ENGLISH]]


# --- provenance and determinism -------------------------------------------


def test_the_workbook_carries_machine_readable_provenance(tmp_path: Path) -> None:
    bundle = ReportBundle.of(package())

    _, workbook = rendered(bundle, tmp_path)

    provenance = _provenance(workbook)
    assert provenance["bundle_id"] == bundle.bundle_id
    assert provenance["source_sha256_hex"] == hashlib.sha256(GOLDEN).hexdigest()
    assert provenance["profile_digest"] == bundle.identity.profile_digest
    assert provenance["package_version"] == bundle.identity.package_version
    assert provenance["narrative_state"] == bundle.narrative_state
    assert provenance["excel_surface_version"] == EXCEL_SURFACE_VERSION


def test_regenerating_the_workbook_reproduces_the_same_cells(tmp_path: Path) -> None:
    # Not byte identity: XlsxWriter stamps a creation time into the package.
    # What determinism requires is that the same bundle yields the same cells.
    #
    # The size is compared out rather than compared, because it is the one field of the
    # claim that legitimately differs. A workbook is a deflate archive and the stamped
    # timestamp is part of what it compresses, so two renders a second apart can differ
    # by a byte in *length* while every cell is identical -- which this test asserted
    # for months and which finally failed on 2026-08-03 at 29007 against 29006. Its own
    # comment already said byte identity is not the claim; the assertion overshot it.
    #
    # Nothing is lost by excluding it: `test_the_workbook_surface_reports_the_size_of
    # _the_file_it_wrote` holds each render's size against the file that render actually
    # produced, which is the claim worth making about a size.
    first = tmp_path / "first"
    second = tmp_path / "second"
    for directory in (first, second):
        directory.mkdir()

    left, left_workbook = rendered(ReportBundle.of(package()), first)
    right, right_workbook = rendered(ReportBundle.of(package()), second)

    assert replace(left, output_size_bytes=right.output_size_bytes) == right
    assert left_workbook.cells == right_workbook.cells
    # Including the chart series values: a float is exactly where a deterministic rerun
    # would break, and `cells` resolves a numeric cell and a text cell to the same thing.
    assert left_workbook.numbers == right_workbook.numbers


def test_the_workbook_is_named_by_the_bundle_it_was_built_for(tmp_path: Path) -> None:
    # A digest carries no customer content, and naming the file by it is what
    # keeps one run's workbook from overwriting another's.
    bundle = ReportBundle.of(package())

    path = ExcelSurfaceRenderer(directory=tmp_path).path_for(bundle)

    assert path.name == f"{bundle.bundle_id}.xlsx"
    assert path.parent == tmp_path


def test_a_destination_that_is_not_a_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        ExcelSurfaceRenderer(directory=tmp_path / "absent")


def test_a_concurrent_render_of_the_same_bundle_cannot_truncate_the_payload(
    tmp_path: Path,
) -> None:
    # Two workers may hold the same bundle at once -- an expired lease is reclaimed
    # while the first worker is still writing. Both derive the same destination from
    # the bundle id, so a payload read from that shared name may be the other
    # worker's half-written archive. A digest taken afterwards would be computed
    # from those same bytes and so would verify the corruption against itself;
    # refusing the read is what keeps a corrupt workbook from being published.
    bundle = ReportBundle.of(package())
    renderer = ExcelSurfaceRenderer(directory=tmp_path)

    content = renderer.render(bundle)
    renderer.path_for(bundle).write_bytes(b"PK truncated")

    with pytest.raises(WorkbookUnavailable):
        renderer.payload_for(bundle, content)


def test_a_render_never_writes_directly_to_the_shared_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The shared name is what a concurrent worker may be reading. If a render
    # streamed the archive there directly, that worker could observe a partial
    # file; the name must only ever be claimed by an already-closed archive.
    bundle = ReportBundle.of(package())
    renderer = ExcelSurfaceRenderer(directory=tmp_path)
    shared = renderer.path_for(bundle)
    opened: list[str] = []

    original = excel.xlsxwriter.Workbook

    def record(path, options):
        opened.append(str(path))
        return original(path, options)

    monkeypatch.setattr(excel.xlsxwriter, "Workbook", record)

    content = renderer.render(bundle)

    assert opened, "the renderer never opened a workbook"
    assert str(shared) not in opened
    # The finished archive still arrives under the name callers resolve.
    assert shared.stat().st_size == content.output_size_bytes
    assert list(tmp_path.iterdir()) == [shared]


def test_a_materialized_workbook_carries_the_bytes_it_measured(
    tmp_path: Path,
) -> None:
    materialized = ExcelSurfaceRenderer(directory=tmp_path).render_materialized(
        ReportBundle.of(package())
    )

    payload = materialized.artifacts[0].content
    assert len(payload) == materialized.content.output_size_bytes
    assert payload.startswith(b"PK")
