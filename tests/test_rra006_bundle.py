from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from khepri.rra import bundle as bundle_module
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    BUNDLE_VERSION,
    GOVERNED_REASONS,
    LANGUAGE_DIRECTION,
    NARRATIVE_INCLUDED,
    NARRATIVE_OMITTED,
    NARRATIVE_REFUSED,
    OUTCOME_DELIVERED,
    OUTCOME_INCOMPLETE,
    REASON_BUNDLE_MISMATCH,
    REASON_CAVEAT_COVERAGE_DIFFERS,
    REASON_DISCLOSURE_ALTERED,
    REASON_DUPLICATE_SURFACE,
    REASON_FIGURE_COVERAGE_DIFFERS,
    REASON_FIGURE_NOT_RECONCILED,
    REASON_MISSING_LANGUAGE,
    REASON_MISSING_SURFACE,
    REASON_NARRATIVE_STATE_CONFLICT,
    REASON_SURFACE_FAILED,
    REASON_UNKNOWN_FIGURE,
    REASON_UNKNOWN_LANGUAGE,
    REASON_UNKNOWN_SURFACE,
    REASON_WRONG_DIRECTION,
    REQUIRED_SURFACES,
    SECTION_OVERVIEW,
    SURFACE_EXCEL,
    SURFACE_PDF,
    SURFACE_WEB,
    BundleAssembler,
    BundleRefused,
    ReportBundle,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
    SurfaceUnavailable,
    reconcile,
)
from khepri.rra.facts import FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    LanguageNarrative,
    NarrativeDraft,
    NarrativeRequest,
    NarrativeSection,
)
from khepri.rra.profiling import build_profile, canonical_json
from tests.rra003_contract_fixtures import TEST_CONTRACT

ADAPTER_VERSION = "test.adapter.v1"

# The size a stand-in renderer reports for a payload no test here holds. This
# module renders nothing, so the number is arbitrary; that it survives assembly
# unchanged is not.
SURFACE_SIZE = 4096

GOLDEN = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)

OTHER = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-02-01,10.00,1,INV-9,Beverages,Luxor\n"
    b"2026-02-02,20.00,2,INV-8,Snacks,Aswan\n"
)

# A category value carrying the separator a figure identifier is built from,
# which is what a label put into an identifier would be free to do.
COLLIDING = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,10.00,1,INV-1,Beverages/value,Cairo\n"
    b"2026-01-06,20.00,2,INV-2,Beverages,Cairo\n"
)


def package(content: bytes = GOLDEN) -> FactPackage:
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
        contract=TEST_CONTRACT,
    )


def narrative_for(text: str = "Revenue was 500.00.") -> NarrativeDraft:
    request = NarrativeRequest.of(package(), adapter_version=ADAPTER_VERSION)
    fact_id = next(
        str(entry["fact_id"])
        for entry in request.document["facts"]
        if entry["metric"] == "revenue"
    )
    return NarrativeDraft(
        adapter_version=ADAPTER_VERSION,
        request_digest=request.digest,
        languages=(
            LanguageNarrative(
                language=LANGUAGE_ARABIC,
                sections=(
                    NarrativeSection(
                        section_id="summary",
                        text="بلغت الإيرادات ٥٠٠٫٠٠.",
                        cited_fact_ids=(fact_id,),
                        caveats=(),
                    ),
                ),
            ),
            LanguageNarrative(
                language=LANGUAGE_ENGLISH,
                sections=(
                    NarrativeSection(
                        section_id="summary",
                        text=text,
                        cited_fact_ids=(fact_id,),
                        caveats=(),
                    ),
                ),
            ),
        ),
    )


def language_of(
    bundle: ReportBundle,
    language: str,
    *,
    direction: str | None = None,
    disclosure: str | None = None,
    stated: tuple[StatedFigure, ...] | None = None,
    caveats: tuple[str, ...] | None = None,
    sections: tuple[str, ...] | None = None,
) -> SurfaceLanguage:
    """A faithful presentation of the bundle, unless a test bends one field."""
    return SurfaceLanguage(
        language=language,
        direction=LANGUAGE_DIRECTION[language] if direction is None else direction,
        sections=bundle.section_ids if sections is None else sections,
        stated=(
            tuple(
                StatedFigure(
                    figure_id=entry.figure_id,
                    text=entry.renderings[language],
                    section=entry.section,
                )
                for entry in bundle.figures
            )
            if stated is None
            else stated
        ),
        caveats=bundle.caveats if caveats is None else caveats,
        disclosure=bundle.disclosure(language) if disclosure is None else disclosure,
    )


def surface_of(
    bundle: ReportBundle,
    surface: str = SURFACE_WEB,
    *,
    bundle_id: str | None = None,
    languages: tuple[SurfaceLanguage, ...] | None = None,
) -> SurfaceContent:
    return SurfaceContent(
        surface=surface,
        bundle_id=bundle.bundle_id if bundle_id is None else bundle_id,
        languages=(
            tuple(language_of(bundle, language) for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH))
            if languages is None
            else languages
        ),
        output_size_bytes=SURFACE_SIZE,
    )


class FaithfulRenderer:
    def __init__(self, surface: str) -> None:
        self._surface = surface

    @property
    def surface(self) -> str:
        return self._surface

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        return surface_of(bundle, self._surface)


def assembler(*renderers: object) -> BundleAssembler:
    return BundleAssembler(
        renderers=list(renderers) or [FaithfulRenderer(name) for name in REQUIRED_SURFACES]
    )


# --- identity -------------------------------------------------------------


def test_the_same_inputs_rebuild_the_same_bundle_identity() -> None:
    # RRA-006 asks for deterministic regeneration, which is only possible
    # because nothing about when the bundle ran reaches its name.
    assert ReportBundle.of(package()).bundle_id == ReportBundle.of(package()).bundle_id


def test_a_different_dataset_is_a_different_bundle() -> None:
    # Fact identifiers derive from metric, scope and formula version, so two
    # datasets share them. Only the content digest tells these reports apart.
    assert ReportBundle.of(package()).bundle_id != ReportBundle.of(package(OTHER)).bundle_id


def test_commentary_that_changed_does_not_keep_the_old_bundle_name() -> None:
    # The narrative is inside the digest for this reason alone: a report whose
    # prose was rewritten is a different report, and a surface built for the
    # old one must not reconcile against the new one.
    first = ReportBundle.of(package(), narrative=narrative_for("Revenue was 500.00."))
    second = ReportBundle.of(package(), narrative=narrative_for("Revenue reached 500.00."))

    assert first.bundle_id != second.bundle_id


def test_a_refused_narrative_and_an_omitted_one_are_different_reports() -> None:
    refused = ReportBundle.of(package(), narrative_refused=True)
    omitted = ReportBundle.of(package())

    assert refused.narrative_state == NARRATIVE_REFUSED
    assert omitted.narrative_state == NARRATIVE_OMITTED
    assert refused.bundle_id != omitted.bundle_id
    assert refused.disclosure(LANGUAGE_ENGLISH) != omitted.disclosure(LANGUAGE_ENGLISH)


def test_a_narrative_that_both_arrived_and_was_refused_is_a_conflict() -> None:
    with pytest.raises(BundleRefused) as refusal:
        ReportBundle.of(package(), narrative=narrative_for(), narrative_refused=True)

    assert refusal.value.reason == REASON_NARRATIVE_STATE_CONFLICT


def test_the_identity_names_both_the_code_and_the_data() -> None:
    identity = ReportBundle.of(package()).identity.as_document()

    assert identity["bundle_version"] == BUNDLE_VERSION
    assert identity["source_sha256_hex"] == hashlib.sha256(GOLDEN).hexdigest()
    assert identity["profile_digest"]
    assert identity["package_version"]


# --- figures --------------------------------------------------------------


def test_every_printed_number_in_the_package_is_rendered_once() -> None:
    # A series point and a comparison bucket are figures as much as a total is:
    # they are the numbers a table prints, and a surface that had to derive
    # them would be calculating.
    bundle = ReportBundle.of(package())
    kinds = {entry.figure_id for entry in bundle.figures}

    assert len(kinds) == len(bundle.figures)
    assert any(entry.label == "2026-01-05" for entry in bundle.figures)
    assert any(entry.label == "Beverages" for entry in bundle.figures)


def test_the_arabic_rendering_is_a_transliteration_and_not_a_recalculation() -> None:
    bundle = ReportBundle.of(package())
    revenue = next(entry for entry in bundle.figures if entry.metric == "revenue")

    assert revenue.renderings[LANGUAGE_ENGLISH] == "500.00"
    assert revenue.renderings[LANGUAGE_ARABIC] == "٥٠٠٫٠٠"
    # Same figure, same precision, different script — the digit count is the
    # check that no rounding happened on the way.
    assert len(revenue.renderings[LANGUAGE_ARABIC]) == len(revenue.renderings[LANGUAGE_ENGLISH])


def test_no_customer_text_reaches_a_figure_identifier() -> None:
    # A figure identifier travels further than the figure does — into logs, into
    # a workbook's defined names, into whatever a renderer keys its cells by. A
    # store's name does not belong in one, even though it is right there on the
    # figure as `label`.
    bundle = ReportBundle.of(package(COLLIDING))
    identifiers = " ".join(entry.figure_id for entry in bundle.figures)

    assert "Beverages" not in identifiers
    assert "Cairo" not in identifiers
    assert any(entry.label == "Beverages/value" for entry in bundle.figures)


def test_every_figure_is_addressable_on_its_own() -> None:
    # Uniqueness by construction rather than by digest. A digest of the label
    # would be probabilistic, which is the assumption `aggregates` already
    # found it could not make.
    bundle = ReportBundle.of(package(COLLIDING))

    assert len({entry.figure_id for entry in bundle.figures}) == len(bundle.figures)


# --- the payload behind a surface -----------------------------------------


def test_the_size_a_surface_reports_reaches_the_delivered_report() -> None:
    # RRA-007 records the size of what a stage produced, and only a renderer
    # holds the payload. The port carries the number back so the pipeline can
    # record it; nothing carries the bytes.
    result = assembler().assemble(ReportBundle.of(package()))

    assert result.surfaces is not None
    assert [entry.output_size_bytes for entry in result.surfaces] == [SURFACE_SIZE] * 3


def test_a_surface_cannot_report_a_size_no_payload_could_have() -> None:
    # A negative size is a broken measurement rather than a small report, and
    # `OperationalEvent` would refuse it long after the stage it was measured
    # at had finished.
    faithful = surface_of(ReportBundle.of(package()))

    with pytest.raises(ValueError):
        replace(faithful, output_size_bytes=-1)


# --- reconciliation -------------------------------------------------------


def test_a_surface_that_shows_what_it_was_given_reconciles() -> None:
    bundle = ReportBundle.of(package())

    reconcile(surface_of(bundle), bundle=bundle)


def test_a_surface_built_for_another_bundle_is_refused() -> None:
    # The whole defence against a retry delivering one run's PDF beside
    # another run's workbook.
    bundle = ReportBundle.of(package())
    stale = ReportBundle.of(package(OTHER))

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, bundle_id=stale.bundle_id), bundle=bundle)

    assert refusal.value.reason == REASON_BUNDLE_MISMATCH


def test_a_surface_nobody_asked_for_is_refused() -> None:
    bundle = ReportBundle.of(package())

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, "csv"), bundle=bundle)

    assert refusal.value.reason == REASON_UNKNOWN_SURFACE


def test_a_second_copy_of_a_language_is_refused() -> None:
    # Collapsing duplicates into a mapping would reconcile the last entry and
    # hand back a surface still carrying the others.
    bundle = ReportBundle.of(package())
    duplicated = (
        language_of(bundle, LANGUAGE_ARABIC),
        language_of(bundle, LANGUAGE_ENGLISH),
        language_of(bundle, LANGUAGE_ENGLISH),
    )

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=duplicated), bundle=bundle)

    assert refusal.value.reason == REASON_BUNDLE_MISMATCH


def test_a_surface_in_one_language_only_is_refused() -> None:
    bundle = ReportBundle.of(package())
    single = (language_of(bundle, LANGUAGE_ENGLISH),)

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=single), bundle=bundle)

    assert refusal.value.reason == REASON_MISSING_LANGUAGE


def test_a_language_the_report_does_not_publish_is_refused() -> None:
    bundle = ReportBundle.of(package())
    extra = (
        language_of(bundle, LANGUAGE_ARABIC),
        language_of(bundle, LANGUAGE_ENGLISH),
        SurfaceLanguage(
            language="fr",
            direction="ltr",
            sections=bundle.section_ids,
            stated=(),
            caveats=bundle.caveats,
            disclosure="",
        ),
    )

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=extra), bundle=bundle)

    assert refusal.value.reason == REASON_UNKNOWN_LANGUAGE


def test_arabic_laid_out_left_to_right_is_refused() -> None:
    # The layout is invisible from here; the declaration is not, and a surface
    # that thinks Arabic reads left to right has not laid it out correctly by
    # accident.
    bundle = ReportBundle.of(package())
    wrong = (
        language_of(bundle, LANGUAGE_ARABIC, direction="ltr"),
        language_of(bundle, LANGUAGE_ENGLISH),
    )

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=wrong), bundle=bundle)

    assert refusal.value.reason == REASON_WRONG_DIRECTION


@pytest.mark.parametrize(
    ("altered", "name"),
    [
        ("This analysis was generated automatically.", "shortened"),
        ("", "dropped"),
        (
            "This analysis was generated automatically from the data you supplied. "
            "Every figure is cited to the fact package named in this report. "
            "The written commentary was generated automatically and checked against "
            "those figures!",
            "one character changed",
        ),
    ],
)
def test_a_disclosure_that_is_not_the_governed_one_is_refused(altered: str, name: str) -> None:
    # Compared in full rather than searched for a phrase. A disclosure that has
    # been shortened, dropped or quietly reworded is not the governed one, and
    # a keyword search would accept the first and third of these.
    bundle = ReportBundle.of(package(), narrative=narrative_for())
    weakened = (
        language_of(bundle, LANGUAGE_ARABIC),
        language_of(bundle, LANGUAGE_ENGLISH, disclosure=altered),
    )

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=weakened), bundle=bundle)

    assert refusal.value.reason == REASON_DISCLOSURE_ALTERED, name


def test_a_surface_that_reformats_a_figure_is_refused() -> None:
    # `500.0` and `500.00` are the same number and a different statement about
    # precision. A surface does not get to choose which one a reader sees.
    bundle = ReportBundle.of(package())
    revenue = next(entry for entry in bundle.figures if entry.metric == "revenue")
    reformatted = (
        language_of(bundle, LANGUAGE_ARABIC),
        language_of(
            bundle,
            LANGUAGE_ENGLISH,
            stated=(
                StatedFigure(
                    figure_id=revenue.figure_id,
                    text="500.0",
                    section=revenue.section,
                ),
            ),
        ),
    )

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=reformatted), bundle=bundle)

    assert refusal.value.reason == REASON_FIGURE_NOT_RECONCILED


def test_an_english_page_showing_the_arabic_rendering_is_refused() -> None:
    bundle = ReportBundle.of(package())
    revenue = next(entry for entry in bundle.figures if entry.metric == "revenue")
    swapped = (
        language_of(bundle, LANGUAGE_ARABIC),
        language_of(
            bundle,
            LANGUAGE_ENGLISH,
            stated=(
                StatedFigure(
                    figure_id=revenue.figure_id,
                    text=revenue.renderings[LANGUAGE_ARABIC],
                    section=revenue.section,
                ),
            ),
        ),
    )

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=swapped), bundle=bundle)

    assert refusal.value.reason == REASON_FIGURE_NOT_RECONCILED


def test_a_figure_the_bundle_never_carried_is_refused() -> None:
    bundle = ReportBundle.of(package())
    invented = (
        language_of(bundle, LANGUAGE_ARABIC),
        language_of(
            bundle,
            LANGUAGE_ENGLISH,
            stated=(
                StatedFigure(
                    figure_id="cit_nothing/value",
                    text="500.00",
                    section=SECTION_OVERVIEW,
                ),
            ),
        ),
    )

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=invented), bundle=bundle)

    assert refusal.value.reason == REASON_UNKNOWN_FIGURE


def test_a_surface_that_drops_a_caveat_is_refused() -> None:
    bundle = ReportBundle.of(package())
    silent = (
        language_of(bundle, LANGUAGE_ARABIC),
        language_of(bundle, LANGUAGE_ENGLISH, caveats=()),
    )

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=silent), bundle=bundle)

    assert refusal.value.reason == REASON_CAVEAT_COVERAGE_DIFFERS


def test_a_row_missing_from_one_language_only_is_refused() -> None:
    # Each language reconciles perfectly on its own here. What differs is which
    # rows the two readers are shown, which no per-language check can see.
    bundle = ReportBundle.of(package())
    # The dropped figure must be one no chart plots. A charted figure missing from a
    # language earns `chart_figure_not_stated` first -- also correct, and a different
    # finding: the chart would be drawing something that reader was never shown.
    # This test is about coverage between the two languages, so it drops a row that
    # only the table carries.
    charted = {
        figure_id
        for section in bundle.sections
        if section.chart is not None
        for figure_id in section.chart.figure_ids
    }
    dropped = next(
        figure
        for figure in reversed(bundle.figures)
        if figure.figure_id not in charted
    )
    shortened = tuple(
        StatedFigure(
            figure_id=entry.figure_id,
            text=entry.renderings[LANGUAGE_ARABIC],
            section=entry.section,
        )
        for entry in bundle.figures
        if entry.figure_id != dropped.figure_id
    )
    uneven = (
        language_of(bundle, LANGUAGE_ARABIC, stated=shortened),
        language_of(bundle, LANGUAGE_ENGLISH),
    )

    with pytest.raises(BundleRefused) as refusal:
        reconcile(surface_of(bundle, languages=uneven), bundle=bundle)

    assert refusal.value.reason == REASON_FIGURE_COVERAGE_DIFFERS


# --- assembly -------------------------------------------------------------


def test_three_faithful_surfaces_are_delivered_together() -> None:
    bundle = ReportBundle.of(package(), narrative=narrative_for())

    result = assembler().assemble(bundle)

    assert result.incomplete is False
    assert result.attempt.outcome == OUTCOME_DELIVERED
    assert result.attempt.reason is None
    assert result.attempt.narrative_state == NARRATIVE_INCLUDED
    assert [entry.surface for entry in result.surfaces or ()] == list(REQUIRED_SURFACES)


def test_one_failed_surface_withholds_the_other_two() -> None:
    # A customer holding a PDF from one run beside a workbook from the next
    # holds two reports that disagree, with nothing on either to say so.
    class BrokenRenderer:
        surface = SURFACE_EXCEL

        def render(self, bundle: ReportBundle) -> SurfaceContent:
            raise SurfaceUnavailable

    bundle = ReportBundle.of(package())
    result = assembler(
        FaithfulRenderer(SURFACE_WEB),
        FaithfulRenderer(SURFACE_PDF),
        BrokenRenderer(),
    ).assemble(bundle)

    assert result.incomplete is True
    assert result.surfaces is None
    assert result.attempt.outcome == OUTCOME_INCOMPLETE
    assert result.attempt.reason == REASON_SURFACE_FAILED
    # The surfaces that did render are named so a retry can be reasoned about.
    assert result.attempt.surfaces == (SURFACE_PDF, SURFACE_WEB)


def test_a_surface_from_an_earlier_run_makes_the_bundle_incomplete() -> None:
    stale = ReportBundle.of(package(OTHER))

    class StaleRenderer:
        surface = SURFACE_PDF

        def render(self, bundle: ReportBundle) -> SurfaceContent:
            return surface_of(stale, SURFACE_PDF)

    result = assembler(
        FaithfulRenderer(SURFACE_WEB),
        StaleRenderer(),
        FaithfulRenderer(SURFACE_EXCEL),
    ).assemble(ReportBundle.of(package()))

    assert result.incomplete is True
    assert result.attempt.reason == REASON_BUNDLE_MISMATCH


def test_a_missing_renderer_makes_the_bundle_incomplete() -> None:
    result = assembler(
        FaithfulRenderer(SURFACE_WEB),
        FaithfulRenderer(SURFACE_PDF),
    ).assemble(ReportBundle.of(package()))

    assert result.incomplete is True
    assert result.attempt.reason == REASON_MISSING_SURFACE


def test_two_renderers_claiming_one_surface_make_the_bundle_incomplete() -> None:
    # Otherwise which of them was delivered would be decided by iteration order.
    result = assembler(
        FaithfulRenderer(SURFACE_WEB),
        FaithfulRenderer(SURFACE_WEB),
        FaithfulRenderer(SURFACE_PDF),
        FaithfulRenderer(SURFACE_EXCEL),
    ).assemble(ReportBundle.of(package()))

    assert result.incomplete is True
    assert result.attempt.reason == REASON_DUPLICATE_SURFACE


def test_assembling_twice_produces_the_same_bundle_identity() -> None:
    # Idempotent retry: nothing here depends on when it ran, so a second
    # attempt either produces the same bundle or a visibly different one.
    first = assembler().assemble(ReportBundle.of(package()))
    second = assembler().assemble(ReportBundle.of(package()))

    assert first.attempt.bundle_id == second.attempt.bundle_id
    assert first.attempt.as_document() == second.attempt.as_document()


# --- what the record may carry --------------------------------------------


def test_a_renderer_sentence_offered_as_a_reason_is_not_recorded() -> None:
    # `BundleRefused` is public, so a renderer can raise it carrying anything.
    class LeakyRenderer:
        surface = SURFACE_PDF

        def render(self, bundle: ReportBundle) -> SurfaceContent:
            raise BundleRefused("customer Cairo record 12345")

    result = assembler(
        FaithfulRenderer(SURFACE_WEB),
        LeakyRenderer(),
        FaithfulRenderer(SURFACE_EXCEL),
    ).assemble(ReportBundle.of(package()))

    assert result.attempt.reason == REASON_SURFACE_FAILED
    assert "Cairo" not in canonical_json(result.attempt.as_document())


def test_the_governed_reasons_are_the_reasons_the_module_defines() -> None:
    defined = {
        value
        for name, value in vars(bundle_module).items()
        if name.startswith("REASON_") and isinstance(value, str)
    }

    assert defined == set(GOVERNED_REASONS)


def test_a_delivered_record_names_versions_and_nothing_from_the_data() -> None:
    bundle = ReportBundle.of(package(), narrative=narrative_for())

    document = assembler().assemble(bundle).attempt.as_document()

    assert set(document) == {
        "bundle_version",
        "bundle_id",
        "package_version",
        "narrative_state",
        "surfaces",
        "outcome",
        "reason",
    }
    serialized = canonical_json(document)
    for leaked in ("Cairo", "Beverages", "500.00", "currency_not_declared"):
        assert leaked not in serialized


# --- what a surface is still free to do -----------------------------------


def test_a_surface_may_show_a_subset_so_long_as_both_readers_see_it() -> None:
    # A summary page printing only the totals is a legitimate surface, not a
    # defect. What is refused is showing one subset to one reader and another
    # to the other, which the cross-language comparison already catches.
    bundle = ReportBundle.of(package())
    # A subset must still include everything its charts plot. A page showing fewer
    # rows is legitimate; a page whose chart draws a figure that reader was never
    # shown is `chart_figure_not_stated`, and that is a different and correct
    # refusal. Analysis figures now carry the scope they were derived under as a
    # label, so "the totals" no longer happens to include them.
    charted = {
        figure_id
        for section in bundle.sections
        if section.chart is not None
        for figure_id in section.chart.figure_ids
    }
    totals = tuple(
        entry
        for entry in bundle.figures
        if entry.label is None or entry.figure_id in charted
    )
    partial = tuple(
        language_of(
            bundle,
            language,
            stated=tuple(
                StatedFigure(
                    figure_id=entry.figure_id,
                    text=entry.renderings[language],
                    section=entry.section,
                )
                for entry in totals
            ),
        )
        for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
    )

    reconcile(surface_of(bundle, languages=partial), bundle=bundle)


def test_a_withheld_bucket_value_is_rendered_as_nothing_at_all() -> None:
    # A surface cannot print what was not supplied, and giving it an empty
    # rendering would hand it something to print.
    #
    # `metric` and `measure` are deliberately different here: a bucket figure carries
    # the metric, because a figure's metric is its fact's metric everywhere in this
    # module. Carrying the measure instead is what left the concentration curve
    # claiming to be `revenue` and therefore chartable by nobody.
    owner = {
        "citation_id": "cit_x",
        "fact_id": "fct_x",
        "metric": "revenue_by_branch",
        "measure": "revenue",
        "unit_kind": "money",
    }
    withheld = bundle_module._bucket(owner, {"label": "Cairo", "value": None, "rows": 4}, 0)

    assert [entry.kind for entry in withheld] == ["rows"]
    assert withheld[0].renderings[LANGUAGE_ENGLISH] == "4"
    assert withheld[0].metric == "revenue_by_branch"
