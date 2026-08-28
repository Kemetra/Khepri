from __future__ import annotations

from decimal import Decimal

import pytest

from khepri.rra.bundle import (
    BUNDLE_VERSION,
    CHART_BAR,
    CHART_GROUPED_BAR,
    CHART_LINE,
    GOVERNED_CHART_KINDS,
    GOVERNED_SECTION_REASONS,
    GOVERNED_SECTION_STATES,
    KIND_VALUE,
    NARRATIVE_OMITTED,
    ORDERED_SECTIONS,
    SECTION_BASKET,
    SECTION_CHART_KINDS,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_GROWTH,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    SECTION_REASONS,
    SECTION_REFUSED,
    BundleIdentity,
    ChartSpec,
    CitedFigure,
    ReportBundle,
    Section,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH


def _present(section_id: str) -> Section:
    return Section(
        section_id=section_id,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=(f"F-{section_id}",),
        chart=None,
    )


def _identity() -> BundleIdentity:
    """A provenance record with no data behind it.

    Every field is a version string, a digest, or a count, so a bundle can be
    assembled here without building a fact package. These tests are about the
    section sequence a bundle declares and nothing downstream of it.
    """
    return BundleIdentity(
        package_version="rra004.package.v1",
        formula_version="rra004.formula.v1",
        mapping_version="rra004.mapping.v1",
        narrative_version="rra005.narrative.v1",
        profile_digest="0" * 64,
        source_sha256_hex="1" * 64,
        monetary_precision=2,
        row_count=0,
    )


def _figure(figure_id: str, section: str) -> CitedFigure:
    """A figure with no data behind it, placed in one section."""
    return CitedFigure(
        figure_id=figure_id,
        citation_id="cit_000000000000",
        fact_id="fct_000000000000000000000000",
        metric="revenue",
        unit_kind="monetary",
        kind=KIND_VALUE,
        section=section,
        label=None,
        value=Decimal("500.00"),
        renderings={LANGUAGE_ENGLISH: "500.00", LANGUAGE_ARABIC: "٥٠٠٫٠٠"},
    )


def _bundle(sections: tuple[Section, ...]) -> ReportBundle:
    """A bundle carrying exactly the figures its sections index.

    The figures are derived from the index rather than supplied beside it,
    because a bundle whose sections and figures disagree about placement is
    rejected -- these tests are about the section sequence, not about that.
    """
    return ReportBundle(
        identity=_identity(),
        figures=tuple(
            _figure(figure_id, section.section_id)
            for section in sections
            for figure_id in section.figure_ids
        ),
        caveats=(),
        narrative_state=NARRATIVE_OMITTED,
        sections=sections,
    )


def test_ordered_sections_starts_with_overview() -> None:
    assert ORDERED_SECTIONS[0] == SECTION_OVERVIEW
    assert SECTION_COMPARISON in ORDERED_SECTIONS


def test_ordered_sections_is_the_governed_order_of_the_five_families() -> None:
    # Order is governed data, not a renderer's choice. A renderer permitted to
    # choose it would let the PDF and the workbook disagree about what a reader
    # sees first, and both would still reconcile.
    assert ORDERED_SECTIONS == (
        SECTION_OVERVIEW,
        SECTION_COMPARISON,
        SECTION_CONCENTRATION,
        SECTION_GROWTH,
        SECTION_BASKET,
    )


def test_present_section_carries_no_reason() -> None:
    section = Section(
        section_id=SECTION_OVERVIEW,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=("F-1",),
        chart=None,
    )
    assert section.reason is None


def test_refused_section_requires_a_reason() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_REFUSED,
            reason=None,
            figure_ids=(),
            chart=None,
        )


def test_present_section_may_not_carry_a_reason() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_PRESENT,
            reason="prior_window_absent",
            figure_ids=("F-1",),
            chart=None,
        )


def test_a_state_outside_the_governed_set_is_rejected() -> None:
    # A state the governed set does not contain must fail construction, not be
    # judged by the reason rules. `pending` with no reason satisfies both of
    # those rules by matching neither, and a renderer testing
    # `state == SECTION_REFUSED` then draws an invented state as a present one.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state="pending",
            reason=None,
            figure_ids=(),
            chart=None,
        )


def test_the_governed_state_set_is_exactly_present_and_refused() -> None:
    assert frozenset({SECTION_PRESENT, SECTION_REFUSED}) == GOVERNED_SECTION_STATES


def test_an_unknown_section_id_is_rejected() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id="invented",
            state=SECTION_PRESENT,
            reason=None,
            figure_ids=("F-1",),
            chart=None,
        )


def test_chart_must_plot_at_least_one_figure() -> None:
    with pytest.raises(ValueError):
        ChartSpec(kind=CHART_BAR, figure_ids=())


def test_chart_kind_must_be_governed() -> None:
    with pytest.raises(ValueError):
        ChartSpec(kind="waterfall", figure_ids=("F-1",))


def test_the_governed_chart_kinds_are_the_three_the_design_fixes() -> None:
    assert frozenset({CHART_BAR, CHART_GROUPED_BAR, CHART_LINE}) == GOVERNED_CHART_KINDS


def test_a_chart_may_not_plot_a_figure_outside_its_section() -> None:
    # Structural rather than validated: a chart can only reference figures the
    # section already declared, and those are already reconciled by exact
    # string comparison. There is no parallel mechanism to keep in step.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_PRESENT,
            reason=None,
            figure_ids=("F-1",),
            chart=ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        )


def test_a_chart_plotting_a_subset_of_its_section_is_accepted() -> None:
    section = Section(
        section_id=SECTION_CONCENTRATION,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=("F-1", "F-2", "F-3"),
        chart=ChartSpec(kind=CHART_LINE, figure_ids=("F-1", "F-2")),
    )
    assert section.chart is not None
    assert section.chart.kind == CHART_LINE


def test_a_refused_section_carries_no_figures_and_still_constructs() -> None:
    # The shape the refusal path depends on. A refused family renders its
    # heading and its reason, so it must be representable with no figures at
    # all -- which is also why section coverage can never be inferred from
    # figure rows.
    section = Section(
        section_id=SECTION_GROWTH,
        state=SECTION_REFUSED,
        reason="units_absent",
        figure_ids=(),
        chart=None,
    )
    assert section.figure_ids == ()
    assert section.chart is None


def test_a_refused_section_may_not_authorize_figures() -> None:
    # The class invariant has to be enforced, not just documented. A refused
    # section carrying figures declares content the refusal branch never
    # renders, so the bundle would authorize figures no surface presents.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_COMPARISON,
            state=SECTION_REFUSED,
            reason="prior_window_absent",
            figure_ids=("F-1",),
            chart=None,
        )


def test_a_refused_section_may_not_authorize_a_chart() -> None:
    # Worse than unused: chart reconciliation requires every plotted figure to
    # appear in what the surface stated, and a refused section states none, so
    # this would refuse the whole bundle for a chart that should not exist.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_COMPARISON,
            state=SECTION_REFUSED,
            reason="prior_window_absent",
            figure_ids=("F-1",),
            chart=ChartSpec(kind=CHART_GROUPED_BAR, figure_ids=("F-1",)),
        )


def test_a_present_section_must_present_something() -> None:
    # The state model has two members, so a present section holding no figures
    # is a third state wearing the first one's name: it claims the analysis
    # succeeded, shows nothing, and carries no reason because present sections
    # may not. An analysis that produced nothing refuses instead.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_PRESENT,
            reason=None,
            figure_ids=(),
            chart=None,
        )


def test_a_refused_section_may_not_invent_a_reason_code() -> None:
    # Every surface renders a refusal by looking the code up in a per-language
    # table, so an ungoverned one arrives as a blank refusal in front of a
    # reader while the bundle stays valid.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_COMPARISON,
            state=SECTION_REFUSED,
            reason="prior_window_absnet",
            figure_ids=(),
            chart=None,
        )


def test_a_refusal_reason_may_not_carry_arbitrary_text() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_COMPARISON,
            state=SECTION_REFUSED,
            reason="no data for Acme Retail Ltd",
            figure_ids=(),
            chart=None,
        )


def test_every_governed_reason_constructs_under_its_own_section() -> None:
    for section_id, reasons in SECTION_REASONS.items():
        for reason in reasons:
            section = Section(
                section_id=section_id,
                state=SECTION_REFUSED,
                reason=reason,
                figure_ids=(),
                chart=None,
            )
            assert section.reason == reason


def test_a_section_may_not_borrow_another_analysis_reason() -> None:
    # Growth analysis cannot fail for want of a transaction identifier. A
    # globally governed code is not a licence to use it anywhere, and this
    # explanation would be hashed into the bundle and rendered as authoritative.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_GROWTH,
            state=SECTION_REFUSED,
            reason="transaction_identifier_absent",
            figure_ids=(),
            chart=None,
        )


def test_the_overview_states_no_governed_refusal_reason() -> None:
    # It carries RRA-004 headline figures rather than an RRA-008 family, and
    # RRA-004 refuses individual metrics inside the package instead.
    assert SECTION_REASONS[SECTION_OVERVIEW] == frozenset()
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_REFUSED,
            reason="units_absent",
            figure_ids=(),
            chart=None,
        )


def test_each_family_carries_the_reasons_rra008_assigns_it() -> None:
    # Taken from RRA-008's per-family requirements, not composed here. The rows
    # that are *not* from RRA-008 all have the same authority: the family can
    # reach them. A section restricted to the specification's wording would have
    # to raise on a valid package, or explain a refusal with a cause that is not
    # the one that occurred.
    #
    # `aggregate_unavailable` was introduced by the merged plan for the RRA-004
    # amendment. APP-014 has since recorded it, and `concentration.derive` now
    # uses the reason for a dimension that exists while no curve over it does.
    #
    # Comparison's `required_input_unavailable` comes from RRA-004: `derive`
    # refuses with the reason its modes actually gave, and a compared period
    # holding only null revenue gives the fact package's.
    #
    # Growth carries four because it decomposes the window the comparison states
    # and therefore fails the same two ways as well as its own: a dataset short
    # of two settled periods has no change to split, and an absent revenue trend
    # has nothing to split at all. Neither is "units absent".
    #
    # `coverage_structurally_incompatible` comes from RRA-008's requirement that
    # completeness and alignment come only from the authoritative coverage
    # manifest and the retained structural signatures. `rra008.comparison.v2`
    # refuses a window those cannot prove comparable, and that is a different
    # finding from `prior_window_absent`: the earlier period is present, and
    # re-exporting more history does not help. Growth carries it for the reason
    # it carries the other two -- it consumes the window comparison accepted.
    #
    # Every family also carries `family_version_pairing_unadmitted`, which RRA-008
    # does not assign to any one of them because it is not about their inputs. It
    # is the version compatibility gate's family seam: any of the four may be the
    # one whose successor has not landed while the core formula has moved, and
    # RRA-008 requires that failure to refuse "only dependent results, leaving
    # independently answerable facts and the rest of the report intact". A reason
    # only one family could state would make that promise false for the other
    # three.
    assert SECTION_REASONS[SECTION_COMPARISON] == frozenset(
        {
            "prior_window_absent",
            "required_input_unavailable",
            "family_version_pairing_unadmitted",
            "coverage_structurally_incompatible",
        }
    )
    assert SECTION_REASONS[SECTION_CONCENTRATION] == frozenset(
        {"distinct_set_uncomputable", "aggregate_unavailable", "family_version_pairing_unadmitted"}
    )
    assert SECTION_REASONS[SECTION_GROWTH] == frozenset(
        {
            "units_absent",
            "decomposition_not_additive",
            "prior_window_absent",
            "required_input_unavailable",
            "family_version_pairing_unadmitted",
            "coverage_structurally_incompatible",
            # Growth alone refuses on returns: `RRA-008` admits only
            # return-free aligned windows for this family.
            "returns_present",
        }
    )
    # Basket carries three. RRA-008 requires a transaction identifier for both its
    # metrics, so an absent column and one with gaps each take the whole family --
    # the fact package distinguishes those two causes already. The third is
    # reachable as a whole-family refusal only: a dataset with an identifier and
    # neither units nor a product dimension states nothing at all.
    assert SECTION_REASONS[SECTION_BASKET] == frozenset(
        {
            "transaction_identifier_absent",
            "incomplete_transaction_identifiers",
            # The fourth is the same failure with a third cause: rows repeated
            # byte for byte, which `RRA-003` refuses outright rather than
            # leaving the count partial. `basket._identifier_reason` reports the
            # package's reason verbatim, so the family refuses with it and the
            # section has to be able to say it.
            "repeated_row_signature",
            "required_input_unavailable",
            "family_version_pairing_unadmitted",
        }
    )


def test_basket_survives_the_loss_of_attach_rate_alone() -> None:
    # RRA-008 requires a transaction identifier for *both* basket metrics but an
    # admissible dimension for attach rate only, so losing the dimension -- or
    # the pending membership aggregate -- kills attach rate while items per
    # transaction survives. The section stays present and carries it.
    section = Section(
        section_id=SECTION_BASKET,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=("F-items-per-transaction",),
        chart=None,
    )
    assert section.state == SECTION_PRESENT


def test_a_reason_that_kills_one_metric_may_not_refuse_the_whole_section() -> None:
    # A refused section carries no figures, so admitting these as section states
    # would suppress the figure that survived. They belong on the attach-rate
    # result, beside the figures, not on the section.
    for reason in ("dimension_absent", "aggregate_unavailable"):
        with pytest.raises(ValueError):
            Section(
                section_id=SECTION_BASKET,
                state=SECTION_REFUSED,
                reason=reason,
                figure_ids=(),
                chart=None,
            )


def test_basket_refuses_wholly_only_without_a_transaction_identifier() -> None:
    # RRA-008 requires it for both metrics, so its absence is the one basket
    # failure that takes the whole family.
    section = Section(
        section_id=SECTION_BASKET,
        state=SECTION_REFUSED,
        reason="transaction_identifier_absent",
        figure_ids=(),
        chart=None,
    )
    assert section.reason == "transaction_identifier_absent"


def test_concentration_still_refuses_wholly_on_the_pending_aggregate() -> None:
    # The same code is a whole-family refusal here, because the plan gates
    # concentration entirely on the RRA-004 amendment rather than one metric.
    section = Section(
        section_id=SECTION_CONCENTRATION,
        state=SECTION_REFUSED,
        reason="aggregate_unavailable",
        figure_ids=(),
        chart=None,
    )
    assert section.reason == "aggregate_unavailable"


def test_the_governed_vocabulary_is_the_union_of_the_families() -> None:
    # Derived rather than maintained beside the table, so the two cannot
    # disagree about what a governed reason is.
    assert frozenset().union(*SECTION_REASONS.values()) == GOVERNED_SECTION_REASONS


def test_the_governed_reasons_cover_every_family_the_plan_names() -> None:
    # Each code is named by the merged design or plan for a specific family.
    # Adding one is a deliberate act in the slice that introduces it, rather
    # than a string passed through from an analysis module.
    assert frozenset(
        {
            "prior_window_absent",
            # Added by `V-concentration`, which found the code defined by the
            # comparison slice and attached to nothing. `rra008.comparison.v2`
            # refuses a window the manifest cannot prove comparable, and that
            # is not `prior_window_absent`: the earlier period is present, so
            # re-exporting more history does not help. Growth carries it too,
            # because it consumes the window comparison accepted.
            "coverage_structurally_incompatible",
            # Added by the comparison slice, which proved it reachable: a
            # compared period holding only null revenue refuses the family with
            # the fact package's own required_input_unavailable, and a section
            # that cannot state its family's reason relabels it instead.
            "required_input_unavailable",
            "aggregate_unavailable",
            "distinct_set_uncomputable",
            "units_absent",
            "decomposition_not_additive",
            "transaction_identifier_absent",
            # Added by the duplicate-row slice: `RRA-003` refuses every additive
            # or distinct-transaction result over a repeated canonical row
            # signature, so the basket family loses its transaction count and
            # names that cause rather than borrowing "identifier absent", which
            # did not occur.
            "repeated_row_signature",
            # Added by the basket slice, which proved it reachable: an identifier
            # column with gaps takes both basket metrics, and the fact package
            # already refuses its transaction count with this rather than with
            # "absent". Relabelling it would name a cause that did not occur.
            "incomplete_transaction_identifiers",
            # Added by the version compatibility gate's family seam, and the one
            # code here that belongs to every family rather than to one. Any of
            # the four may be the family whose successor has not landed while the
            # core formula has moved, and RRA-008 requires that failure to refuse
            # only its own section.
            "family_version_pairing_unadmitted",
            # Added by the #309 growth-population slice, and belonging to
            # growth alone: `RRA-008` requires both aligned windows to be
            # "return-free posted-sale populations" and says a return
            # "refuses growth", so a package recording returns refuses the
            # decomposition rather than netting them out. The comparison
            # beside it is unaffected, which the customer wording states.
            "returns_present",
        }
    ) == GOVERNED_SECTION_REASONS


def test_section_document_is_serializable_for_the_bundle_digest() -> None:
    section = Section(
        section_id=SECTION_BASKET,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=("F-9",),
        chart=ChartSpec(kind=CHART_BAR, figure_ids=("F-9",)),
    )
    assert section.as_document() == {
        "section_id": SECTION_BASKET,
        "state": SECTION_PRESENT,
        "reason": None,
        "figure_ids": ["F-9"],
        "chart": {"kind": CHART_BAR, "figure_ids": ["F-9"]},
    }


def test_a_chart_may_not_repeat_a_figure() -> None:
    # `_require_chart_within` compares frozensets, and a set comparison cannot
    # see multiplicity: ("F-1", "F-1") is a subset of ("F-1",). A renderer
    # iterating the tuple would draw one governed value as two marks, stating a
    # second data point that does not exist.
    with pytest.raises(ValueError):
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-1"))


def test_a_section_may_not_repeat_a_figure() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_PRESENT,
            reason=None,
            figure_ids=("F-1", "F-1"),
            chart=None,
        )


def test_each_section_is_drawn_as_its_own_kind() -> None:
    for section_id, kind in SECTION_CHART_KINDS.items():
        section = Section(
            section_id=section_id,
            state=SECTION_PRESENT,
            reason=None,
            figure_ids=("F-1", "F-2"),
            chart=ChartSpec(kind=kind, figure_ids=("F-1", "F-2")),
        )
        assert section.chart is not None
        assert section.chart.kind == kind


def test_a_governed_kind_is_not_usable_on_any_section() -> None:
    # Reconciliation compares the text beside a chart and never the chart, so a
    # section handed the wrong kind renders faithfully and reconciles perfectly
    # while showing the reader the wrong visualization.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_PRESENT,
            reason=None,
            figure_ids=("F-1", "F-2"),
            chart=ChartSpec(kind=CHART_LINE, figure_ids=("F-1", "F-2")),
        )


def test_concentration_is_a_curve_because_rra008_says_curve() -> None:
    # The one row of the mapping fixed by specification rather than by design:
    # RRA-008 requires the "cumulative share curve", and bars drawn over
    # cumulative shares misstate a governed requirement.
    assert SECTION_CHART_KINDS[SECTION_CONCENTRATION] == CHART_LINE
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_CONCENTRATION,
            state=SECTION_PRESENT,
            reason=None,
            figure_ids=("F-1", "F-2"),
            chart=ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        )


def test_every_section_has_exactly_one_governed_chart_kind() -> None:
    assert set(SECTION_CHART_KINDS) == set(ORDERED_SECTIONS)
    assert set(SECTION_CHART_KINDS.values()) <= GOVERNED_CHART_KINDS


def test_a_bundle_declaring_the_governed_order_is_accepted() -> None:
    bundle = _bundle(tuple(_present(section_id) for section_id in ORDERED_SECTIONS))
    assert bundle.section_ids == ORDERED_SECTIONS


def test_a_bundle_declaring_a_subset_in_governed_order_is_accepted() -> None:
    bundle = _bundle((_present(SECTION_OVERVIEW), _present(SECTION_GROWTH)))
    assert bundle.section_ids == (SECTION_OVERVIEW, SECTION_GROWTH)


def test_a_bundle_with_no_sections_is_accepted() -> None:
    assert _bundle(()).section_ids == ()


def test_a_bundle_may_not_reorder_the_governed_sections() -> None:
    # `section_ids` is the authority every surface's section claim reconciles
    # against, so an order the bundle got wrong is an order every surface
    # follows and reconciles against perfectly. Order is governed data; a
    # caller assembling it is not entitled to choose.
    with pytest.raises(ValueError):
        _bundle((_present(SECTION_GROWTH), _present(SECTION_OVERVIEW)))


def test_a_bundle_may_not_repeat_a_section() -> None:
    with pytest.raises(ValueError):
        _bundle((_present(SECTION_OVERVIEW), _present(SECTION_OVERVIEW)))


def test_the_bundle_version_names_the_document_shape_that_carries_sections() -> None:
    # `sections` joined the hashed document, so every bundle id changed. Two
    # bundles built from identical inputs on either side of that change must
    # not claim the same schema version while having different identities.
    #
    # v5 for the same reason one step on: `figures` is now ordered by governed
    # section rather than by derivation, which reorders the canonical document and
    # moves every bundle id again. Stored evidence has to be able to tell the two
    # ordering contracts apart.
    #
    # v6 changes a field rather than an order: a series or comparison bucket figure
    # records its fact's `metric` where it used to record the `measure` behind it, so
    # `revenue_by_period` appears where `revenue` did. Every affected figure's document
    # changes and every bundle id with it, and a consumer comparing a stored figure's
    # metric across the two shapes would read a rename as a different measurement.
    #
    # v7 moves the document without touching a fact: `renderings` now carry
    # presentation -- `726,919.57` for a bare `726919.57`, `86.65%` for `0.8665`,
    # `٪` for `%` in Arabic. `renderings` is inside `CitedFigure.as_document`, so
    # every figure's document and every bundle id changes while the fact package
    # behind them is byte-identical. That is exactly the case the first paragraph
    # of this test names: two bundles from identical inputs must not claim one
    # schema version while having different identities.
    assert BUNDLE_VERSION == "rra006.bundle.v7"
    assert _identity().as_document()["bundle_version"] == BUNDLE_VERSION
