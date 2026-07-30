from __future__ import annotations

import hashlib
import itertools
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
    SURFACE_EXCEL,
    SURFACE_PDF,
    SURFACE_WEB,
    BundleAssembler,
    BundleIdentity,
    CitedFigure,
    ReportBundle,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
    reconcile,
)
from khepri.rra.facts import FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.profiling import build_profile
from khepri.rra.rendering import excel
from khepri.rra.rendering.excel import (
    EXCEL_SURFACE_VERSION,
    GOVERNED_LABELS,
    ExcelSurfaceRenderer,
)
from tests import rra_workbooks

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
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
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
    name = excel._REPORT_SHEET[language]
    rows = workbook.cells[name]
    headers = list(excel._FIGURE_COLUMNS[language])
    caveats_at = rows.index([excel._CAVEATS_HEADING[language]])
    return SurfaceLanguage(
        language=language,
        direction="rtl" if 'rightToLeft="1"' in workbook.sheets[name] else "ltr",
        stated=tuple(
            StatedFigure(figure_id=row[0], text=row[-1])
            for row in rows[rows.index(headers) + 1 : caveats_at]
        ),
        caveats=tuple(row[0] for row in rows[caveats_at + 1 :]),
        disclosure=next(
            row[1] for row in rows if row[:1] == [excel._DISCLOSURE_HEADING[language]]
        ),
    )


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
                    stated=tuple(
                        StatedFigure(
                            figure_id=figure.figure_id,
                            text=figure.renderings[language],
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

    assert presented(workbook) == content
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
    _, workbook = rendered(ReportBundle.of(package()), tmp_path)

    for name, xml in workbook.sheets.items():
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


def _allowed_text(bundle: ReportBundle) -> set[str]:
    identity = bundle.identity.as_document()
    allowed = set(GOVERNED_LABELS)
    allowed |= set(identity)
    allowed |= {str(value) for value in identity.values()}
    allowed |= {bundle.bundle_id, bundle.narrative_state, EXCEL_SURFACE_VERSION}
    allowed |= set(bundle.caveats)
    allowed |= {bundle.disclosure(language) for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)}
    for figure in bundle.figures:
        allowed |= {figure.figure_id, figure.citation_id, figure.fact_id, figure.metric}
        allowed.add(figure.unit_kind)
        allowed |= set(figure.renderings.values())
        if figure.label is not None:
            allowed.add(figure.label)
    return allowed


# --- language parity and layout -------------------------------------------


def test_both_languages_carry_the_same_figures_and_caveats(tmp_path: Path) -> None:
    bundle = ReportBundle.of(package())

    content, workbook = rendered(bundle, tmp_path)
    surface = presented(workbook)

    english, arabic = surface.languages
    assert english.shown == arabic.shown
    assert set(english.caveats) == set(arabic.caveats) == set(bundle.caveats)
    assert bundle.caveats
    assert english.disclosure == bundle.disclosure(LANGUAGE_ENGLISH)
    assert arabic.disclosure == bundle.disclosure(LANGUAGE_ARABIC)
    assert content == surface


def test_the_arabic_sheets_are_declared_right_to_left(tmp_path: Path) -> None:
    bundle = ReportBundle.of(package())

    _, workbook = rendered(bundle, tmp_path)

    for sheet in (excel._REPORT_SHEET, excel._CITATION_SHEET):
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
    first = tmp_path / "first"
    second = tmp_path / "second"
    for directory in (first, second):
        directory.mkdir()

    left, left_workbook = rendered(ReportBundle.of(package()), first)
    right, right_workbook = rendered(ReportBundle.of(package()), second)

    assert left == right
    assert left_workbook.cells == right_workbook.cells


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
