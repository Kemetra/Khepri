"""#519 (A-24/A-25/A-27), #531 and #530 A-30 -- fields the source states reach the row.

Authority: active `RRA-014` `FR-137` (effective dimensions are stated, so they
must also be what applied), `FR-138` (selection and governed wording only),
`FR-139` (versions equal the source records, including the package formula of a
two-population source), `FR-140` (every refusal and evidence absence survives
projection), and the consumer `RCA-008` `FR-162` reads through.

**Every assertion here reads real `project()` output.** `test_d103_metric_card`
builds S-1 and S-6 rows by hand, so no test there could see that the projector
emitted `None` for `availability` and `versions`; that is how a card that could
never read `verified` shipped with every test green. The bundles below are real
`ReportBundle`/`CrossVersionBundle` values, and the rows are the projector's.

**A limit recorded rather than hidden.** The `RRA-004` headline refusals --
`gross_margin`, `gross_profit`, `cost` and the rest -- live on
`FactPackage.refusals`, and `ReportBundle.of` never carries them onto the bundle.
`#531` forbids reaching past the bundle for them, so `MetricAvailabilityView`
states nothing about those metrics. The test asserting that is written to fail
the day the bundle starts carrying them, so the change is looked at.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

from khepri.rca.semantic_queries import ports
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision import card
from khepri.rra import definitions
from khepri.rra.analysis import basket, comparison, concentration
from khepri.rra.bundle import (
    NARRATIVE_OMITTED,
    SECTION_BASKET,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_PRESENT,
    SECTION_REASON_FAMILY_VERSION_UNADMITTED,
    SECTION_REFUSED,
    CitedEvidence,
    CitedFigure,
    ReportBundle,
    Section,
    StatedCaveat,
)
from khepri.rra.crossversion_bundle import (
    LABEL_BASELINE,
    LABEL_DIFFERENCE,
    LABEL_SUBJECT,
    CrossVersionBundle,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.semantic_views import compatibility, projection, registry
from tests.c105_support import _bundle as _crossversion_bundle
from tests.c105_support import build_comparison_request
from tests.test_rra006_bundle import package
from tests.test_sv105_propagation import _identity

_OVERVIEW = registry.define_view("ExecutiveOverviewView")
_BASKET = registry.define_view("BasketView")
_AVAILABILITY = registry.define_view("MetricAvailabilityView")
_EVIDENCE = registry.define_view("ReportEvidenceView")
_COMPARISON = registry.define_view("PeriodComparisonView")
_PRODUCT_CATEGORY = registry.define_view("ProductCategoryView")
_CONCENTRATION = registry.define_view("ConcentrationView")

_YOY_REFUSED = (
    f"{comparison.METRIC_DELTA_PERCENT}.{comparison.MODE_YEAR_OVER_YEAR}"
    f":{comparison.REASON_PRIOR_WINDOW_ABSENT}"
)


def _figure(
    metric: str,
    *,
    label: str | None = None,
    section: str = "overview",
    value: str = "500.50",
) -> CitedFigure:
    """One real cited figure, addressed by metric and label."""
    return CitedFigure(
        figure_id=f"fig_{metric}_{label or 'none'}",
        citation_id=f"cit_{metric}",
        fact_id="fct_000000000000000000000000",
        metric=metric,
        unit_kind="monetary",
        kind="value",
        section=section,
        label=label,
        value=Decimal(value),
        renderings={LANGUAGE_ENGLISH: value, LANGUAGE_ARABIC: value},
    )


def _evidence(citation_id: str, *, complete: bool) -> CitedEvidence:
    """A retained record stating everything, or stating all three absences."""
    return CitedEvidence(
        citation_id=citation_id,
        metric="revenue",
        unit_kind="monetary",
        formula_version="rra004.formula.v1",
        precision=2 if complete else None,
        inputs=("fct_a",) if complete else None,
        provenance=(("subject", "v1"),) if complete else None,
    )


def _report(
    figures: tuple[CitedFigure, ...],
    *,
    caveats: tuple[StatedCaveat, ...] = (),
    evidence: tuple[CitedEvidence, ...] = (),
) -> ReportBundle:
    """A real single-population bundle whose sections follow its figures."""
    placed: dict[str, list[str]] = {}
    for figure in figures:
        placed.setdefault(figure.section, []).append(figure.figure_id)
    return ReportBundle(
        identity=_identity(),
        figures=figures,
        caveats=caveats,
        narrative_state=NARRATIVE_OMITTED,
        sections=tuple(
            Section(
                section_id=section_id,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=tuple(ids),
                chart=None,
            )
            for section_id, ids in placed.items()
        ),
        evidence=evidence,
    )


def _request(definition, **overrides: object) -> compatibility.SemanticViewRequest:
    fields: dict[str, object] = {
        "view_id": definition.view_id,
        "view_version": definition.view_version,
    }
    return compatibility.SemanticViewRequest(**(fields | overrides))  # type: ignore[arg-type]


def _rows(definition, source: object, **overrides: object) -> tuple[dict[str, object], ...]:
    """The admitted projection's rows, each named by the published field order."""
    outcome = projection.project(_request(definition, **overrides), (source,))
    assert outcome.admitted, outcome.refusal
    assert outcome.projection is not None
    fields = outcome.projection.fields
    return tuple(dict(zip(fields, row, strict=True)) for row in outcome.projection.rows)


def _by_metric(rows: tuple[dict[str, object], ...]) -> dict[str, dict[str, object]]:
    return {str(row["metric"]): row for row in rows}


# --- read_cards over the real projector (RCA-008 FR-162) --------------------


class _ProjectingPort:
    """The port `RCA-007`'s adapter is, minus persistence: the real projector."""

    def __init__(self, bundle: object) -> None:
        self.bundle = bundle

    def project(self, request: object, sources: tuple[object, ...]) -> object:
        return projection.project(request, (self.bundle,))  # type: ignore[arg-type]


class _Isolation:
    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        return f"owner-of-{organization_id}"


class _Sources:
    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> object:
        return object()


def _cards(bundle: object) -> card.CardsReading:
    actions = SemanticQueryActions(_Isolation(), _Sources(), _ProjectingPort(bundle))
    return card.read_cards(
        actions,
        card.CardsRequest(organization_id="org-1", account_id="acct-1", source_id="run-1"),
    )


def test_a_card_reads_verified_when_the_source_states_the_figure_available() -> None:
    """`#519` -- the customer-visible defect: no production card could be verified.

    A caveat-free bundle is used on purpose. `card_status` qualifies a card with
    every caveat on the projection, so any caveat anywhere would make this read
    `caveated` for a reason that has nothing to do with availability.
    """
    reading = _cards(_report((_figure("revenue"),)))

    assert reading.status == ports.KIND_ADMITTED
    (revenue,) = reading.cards
    assert revenue.availability == definitions.AVAILABLE
    assert revenue.status == card.STATUS_VERIFIED
    assert dict(revenue.versions)["formula"] == _identity().formula_version  # type: ignore[arg-type]


def test_a_real_report_bundle_carries_availability_and_versions_to_every_card() -> None:
    """Over `ReportBundle.of(package)`, every card is affirmed and versioned.

    The real bundle states `chart_not_drawn` on its overview, so these cards read
    `caveated` rather than `verified`: `card._admitted` qualifies each card with
    the whole projection's caveats. That is the card's reading, not the
    projector's, and it is reported as an `RCA-008` follow-up rather than changed
    here.
    """
    reading = _cards(ReportBundle.of(package()))

    assert reading.cards
    for one in reading.cards:
        assert one.availability == definitions.AVAILABLE, one.metric
        assert one.status == card.STATUS_CAVEATED, one.metric
        assert dict(one.versions)["view"] == _OVERVIEW.view_version  # type: ignore[arg-type]


# --- versions on ExecutiveOverviewView, BasketView, MetricAvailabilityView ---


def test_overview_rows_carry_the_sources_versions() -> None:
    """`FR-139` -- the row's versions are the identity's, never `None`."""
    (row,) = _rows(_OVERVIEW, _report((_figure("revenue"),)))
    versions = dict(row["versions"])  # type: ignore[arg-type]
    identity = _identity()

    assert versions["package"] == identity.package_version
    assert versions["formula"] == identity.formula_version
    assert versions["mapping"] == identity.mapping_version
    assert versions["view"] == _OVERVIEW.view_version


def test_basket_rows_carry_their_own_family_version() -> None:
    """`FR-139` names *family*: a basket row carries the basket family's version."""
    figure = _figure(basket.METRIC_ITEMS_PER_TRANSACTION, section=SECTION_BASKET)
    record = replace(
        _evidence(figure.citation_id, complete=True),
        formula_version=basket.BASKET_FORMULA_VERSION,
    )
    (row,) = _rows(_BASKET, _report((figure,), evidence=(record,)))
    versions = dict(row["versions"])  # type: ignore[arg-type]

    assert versions[f"family:{SECTION_BASKET}"] == basket.BASKET_FORMULA_VERSION
    assert versions["view"] == _BASKET.view_version


def test_availability_rows_carry_versions() -> None:
    (row,) = _rows(_AVAILABILITY, _report((_figure("revenue"),)))

    assert dict(row["versions"])["view"] == _AVAILABILITY.view_version  # type: ignore[arg-type]


# --- #531: availability and reason, from what the bundle states -------------


def test_a_metric_with_a_figure_is_available_and_states_no_reason() -> None:
    rows = _by_metric(_rows(_AVAILABILITY, _report((_figure("revenue"),))))

    assert rows["revenue"]["availability"] == definitions.AVAILABLE
    assert rows["revenue"]["reason"] is None


def test_a_result_refused_inside_a_present_section_is_unavailable_with_its_reason() -> None:
    """`bundle._scoped` carries it as `<result>:<reason>`, scoped to its section."""
    present = _figure(comparison.METRIC_DELTA_ABSOLUTE, section=SECTION_COMPARISON)
    bundle = _report(
        (present,), caveats=(StatedCaveat(code=_YOY_REFUSED, section=SECTION_COMPARISON),)
    )
    rows = _by_metric(_rows(_AVAILABILITY, bundle))

    refused = rows[comparison.METRIC_DELTA_PERCENT]
    assert refused["availability"] == definitions.UNAVAILABLE
    assert refused["reason"] == comparison.REASON_PRIOR_WINDOW_ABSENT
    assert rows[comparison.METRIC_DELTA_ABSOLUTE]["availability"] == definitions.AVAILABLE


def test_a_metric_with_a_figure_stays_available_beside_another_modes_refusal() -> None:
    """One mode refused, the other stated: a figure exists, so it is available.

    The refusal still survives (`FR-140`) -- it is on the projection's caveats,
    which is also what stops the card reading `verified`.
    """
    stated = _figure(comparison.METRIC_DELTA_PERCENT, section=SECTION_COMPARISON)
    refusal = StatedCaveat(code=_YOY_REFUSED, section=SECTION_COMPARISON)
    outcome = projection.project(
        _request(_AVAILABILITY), (_report((stated,), caveats=(refusal,)),)
    )

    assert outcome.projection is not None
    (row,) = outcome.projection.rows
    assert row[1] == definitions.AVAILABLE
    assert refusal in outcome.projection.caveats


def test_every_metric_of_a_refused_section_is_unavailable_with_the_sections_reason() -> None:
    """Over a real bundle whose four families are all refused.

    `ReportBundle.of(package())` refuses every family section on the version
    pairing, and those sections carry no figures -- so nothing but the section
    states the refusal, and every metric of those families must say so.
    """
    real = ReportBundle.of(package())
    refused = {s.section_id for s in real.sections if s.reason is not None}
    assert refused >= {SECTION_BASKET, SECTION_COMPARISON, SECTION_CONCENTRATION}
    rows = _by_metric(_rows(_AVAILABILITY, real))

    for metric in (
        *basket.GOVERNED_METRICS,
        *comparison.GOVERNED_METRICS,
        *concentration.GOVERNED_METRICS,
    ):
        assert rows[metric]["availability"] == definitions.UNAVAILABLE, metric
        assert rows[metric]["reason"] == SECTION_REASON_FAMILY_VERSION_UNADMITTED, metric
    assert rows["revenue"]["availability"] == definitions.AVAILABLE


def _refused_comparison(*, own: str) -> ReportBundle:
    """A comparison section refused on a missing window, whose YoY result names `own`.

    `bundle._analysed` builds exactly this when a family refuses outright: the
    section carries the summary reason and `_scoped` carries each mode's own.
    """
    headline = _figure("revenue")
    return ReportBundle(
        identity=_identity(),
        figures=(headline,),
        caveats=(
            StatedCaveat(
                code=f"{comparison.METRIC_DELTA_PERCENT}.{comparison.MODE_YEAR_OVER_YEAR}:{own}",
                section=SECTION_COMPARISON,
            ),
        ),
        narrative_state=NARRATIVE_OMITTED,
        sections=(
            Section("overview", SECTION_PRESENT, None, (headline.figure_id,), None),
            Section(
                SECTION_COMPARISON, SECTION_REFUSED, comparison.REASON_PRIOR_WINDOW_ABSENT, (), None
            ),
        ),
        evidence=(),
    )


def test_a_results_own_refusal_outranks_its_sections_summary_reason() -> None:
    """The section states one cause; the result states its own, and that is its answer."""
    own = comparison.REASON_COVERAGE_INCOMPATIBLE
    rows = _by_metric(_rows(_AVAILABILITY, _refused_comparison(own=own)))

    assert rows[comparison.METRIC_DELTA_PERCENT]["reason"] == own
    assert rows[comparison.METRIC_DELTA_ABSOLUTE]["reason"] == comparison.REASON_PRIOR_WINDOW_ABSENT


def test_a_result_stating_only_refusals_is_not_an_empty_result() -> None:
    """`FR-142` -- emptiness is about rows: a stated refusal is a row, not nothing."""
    bundle = _refused_comparison(own=comparison.REASON_COVERAGE_INCOMPATIBLE)
    outcome = projection.project(
        _request(_AVAILABILITY, metrics=(comparison.METRIC_DELTA_PERCENT,)), (bundle,)
    )

    assert outcome.projection is not None
    assert len(outcome.projection.rows) == 1
    assert outcome.projection.is_empty is False


def test_headline_refusals_do_not_travel_on_the_bundle_so_no_row_states_them() -> None:
    """The owner escalation `#531` asked this slice to check for, pinned.

    `gross_margin` is refused on the package (`required_input_unavailable`: no
    cost column) and `ReportBundle.of` carries no `package.refusals` anywhere.
    The projection may not reach past the bundle, so it states nothing. When the
    bundle starts carrying these refusals, this fails and the row gains a reason.
    """
    source = package()
    assert source.refusal("gross_margin") is not None
    rows = _by_metric(_rows(_AVAILABILITY, ReportBundle.of(source)))

    assert "gross_margin" not in rows


# --- ReportEvidenceView: provenance and absence ------------------------------


def test_evidence_rows_carry_the_records_provenance_and_state_no_absence() -> None:
    figure = _figure("revenue")
    record = _evidence(figure.citation_id, complete=True)
    (row,) = _rows(_EVIDENCE, _report((figure,), evidence=(record,)))

    assert row["provenance"] == record.provenance
    assert row["absence"] == ()


def test_evidence_rows_name_every_governed_absence_of_their_record() -> None:
    """`FR-140` -- the absence is named on the row, not converted to a blank."""
    figure = _figure("revenue")
    record = _evidence(figure.citation_id, complete=False)
    (row,) = _rows(_EVIDENCE, _report((figure,), evidence=(record,)))

    assert row["provenance"] is None
    assert row["absence"] == (
        projection.ABSENCE_PRECISION,
        projection.ABSENCE_INPUTS,
        projection.ABSENCE_PROVENANCE,
    )


# --- CrossVersionBundle: subject/baseline/delta and the package formula -----


def _real_crossversion() -> CrossVersionBundle:
    return _crossversion_bundle(build_comparison_request())


def _labelled(bundle: object, citation: str, label: str) -> object:
    return next(
        f.value
        for f in bundle.figures  # type: ignore[attr-defined]
        if f.citation_id == citation and f.label == label
    )


def test_period_comparison_reads_one_row_per_fact_from_the_labelled_figures() -> None:
    """`#531` -- selection by governed label, the source's own `Decimal`s."""
    bundle = _real_crossversion()
    outcome = projection.project(_request(_COMPARISON), (bundle,))
    assert outcome.projection is not None
    fields = outcome.projection.fields
    rows = outcome.projection.rows
    citations = tuple(dict.fromkeys(f.citation_id for f in bundle.figures))

    assert len(rows) == len(citations)
    for citation, row in zip(citations, rows, strict=True):
        named = dict(zip(fields, row, strict=True))
        assert named["subject"] is _labelled(bundle, citation, LABEL_SUBJECT)
        assert named["baseline"] is _labelled(bundle, citation, LABEL_BASELINE)
        assert named["delta"] is _labelled(bundle, citation, LABEL_DIFFERENCE)
        assert named["versions"]


def test_an_absent_comparison_cell_projects_as_an_absence() -> None:
    """`FR-140` -- a missing baseline is `None`, never a zero or a dropped row."""
    real = _real_crossversion()
    source = SimpleNamespace(
        identity=real.identity,
        figures=tuple(f for f in real.figures if f.label != LABEL_BASELINE),
        caveats=real.caveats,
        evidence=real.evidence,
        sections=real.sections,
        bundle_version=real.bundle_version,
    )
    rows = _rows(_COMPARISON, source)

    assert rows
    for row in rows:
        assert row["baseline"] is None
        assert row["subject"] is not None


def test_availability_over_a_real_two_population_source_is_admitted_and_affirmed() -> None:
    """`MetricAvailabilityView` admits both shapes; the two-population one must not raise."""
    bundle = _real_crossversion()
    rows = _rows(_AVAILABILITY, bundle)
    stated = {f.metric for f in bundle.figures} & set(_AVAILABILITY.metric_allowlist)

    assert stated
    assert {str(row["metric"]) for row in rows} == stated
    assert {row["availability"] for row in rows} == {definitions.AVAILABLE}


def test_evidence_over_a_real_two_population_source_carries_its_pair_provenance() -> None:
    """The cross-version record is the one source stating provenance today (`FR-140`)."""
    bundle = _real_crossversion()
    records = {record.citation_id: record for record in bundle.evidence}
    outcome = projection.project(_request(_EVIDENCE), (bundle,))
    assert outcome.projection is not None
    fields = outcome.projection.fields

    assert outcome.projection.rows
    for row in outcome.projection.rows:
        named = dict(zip(fields, row, strict=True))
        record = records[str(named["evidence"])]
        assert record.provenance
        assert named["provenance"] == record.provenance


def test_two_facts_sharing_a_metric_keep_two_comparison_rows() -> None:
    """Rows are keyed by citation: keying by metric would suppress one fact (`FR-140`)."""
    real = _real_crossversion()
    first = real.figures[0].citation_id
    twin = tuple(
        replace(f, citation_id="cit_twin", figure_id=f"{f.figure_id}_twin")
        for f in real.figures
        if f.citation_id == first
    )
    source = SimpleNamespace(
        identity=real.identity,
        figures=(*real.figures, *twin),
        caveats=real.caveats,
        evidence=real.evidence,
        sections=real.sections,
        bundle_version=real.bundle_version,
    )
    rows = _rows(_COMPARISON, source)
    metric = real.figures[0].metric

    assert [row["metric"] for row in rows].count(metric) == 2


def test_a_two_population_source_carries_its_package_formula_version() -> None:
    """`A-25` / `FR-139` -- `package_formula_version`, under `formula` and only there."""
    bundle = _real_crossversion()
    identity = bundle.identity
    assert identity.package_formula_version != identity.comparison_formula_version
    outcome = projection.project(_request(_COMPARISON), (bundle,))
    assert outcome.projection is not None
    versions = outcome.projection.versions

    assert versions["formula"] == identity.package_formula_version
    assert "comparison_formula" not in versions
    assert "comparison_formula_version" not in versions


# --- A-27 / A-30: dimensions over a mixed product/category bundle -----------


def _mixed() -> ReportBundle:
    """The same customer label under product and under category."""
    return _report(
        (
            _figure("revenue_by_product", label="Drinks", value="10.00"),
            _figure("revenue_by_category", label="Drinks", value="20.00"),
        )
    )


def test_the_dimension_column_names_the_dimension_not_the_member() -> None:
    rows = _rows(_PRODUCT_CATEGORY, _mixed())

    assert [(row["dimension"], row["member"]) for row in rows] == [
        ("product", "Drinks"),
        ("category", "Drinks"),
    ]


def test_a_requested_dimension_is_the_dimension_that_applies() -> None:
    """`FR-137` -- the result states `product`, so only product may be in it."""
    outcome = projection.project(_request(_PRODUCT_CATEGORY, dimensions=("product",)), (_mixed(),))

    assert outcome.effective is not None
    assert outcome.effective.dimensions == ("product",)
    rows = _rows(_PRODUCT_CATEGORY, _mixed(), dimensions=("product",))
    assert [row["metric"] for row in rows] == ["revenue_by_product"]


def test_a_filter_matches_its_own_dimension_only() -> None:
    """`A-30` -- a product filter is not satisfied by an equal category label."""
    product = _rows(_PRODUCT_CATEGORY, _mixed(), filters=(("product", "Drinks"),))
    category = _rows(_PRODUCT_CATEGORY, _mixed(), filters=(("category", "Drinks"),))

    assert [row["metric"] for row in product] == ["revenue_by_product"]
    assert [row["metric"] for row in category] == ["revenue_by_category"]


def test_a_figure_stating_no_dimension_fails_closed_under_a_narrowing_request() -> None:
    """Concentration figures state no dimension, so `product` cannot be claimed for them."""
    figure = _figure(concentration.METRIC_TOP_DECILE_SHARE, section=SECTION_CONCENTRATION)
    bundle = _report((figure,))

    (row,) = _rows(_CONCENTRATION, bundle)
    assert row["dimension"] is None
    assert _rows(_CONCENTRATION, bundle, dimensions=("product",)) == ()
    assert len(_rows(_CONCENTRATION, bundle, dimensions=("product", "category"))) == 1
