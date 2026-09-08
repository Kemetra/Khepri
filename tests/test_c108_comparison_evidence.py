"""C1-08: the evidence a two-population comparison owes, end to end.

The C1 slices each proved their own unit. This module proves the seven properties the
roadmap row names -- exactness, provenance, cross-organization, mixed-version,
unsupported-filter, deletion, and rerun -- against the assembled bundle and, where the
property is about a reader rather than a value, against the shipped surface.

Three of the seven had no coverage anywhere in the suite before this module: exactness
(that the published delta and ratio are the arithmetic `RRA-008` §Comparative states,
not merely some number), mixed-version (that drift in any one of the three governed
versions refuses under its own cause), and unsupported filters (that a filter difference
refuses as `incomparable basis` rather than comparing across incomparable populations).
The other four existed as unit assertions and are proven here through the door a
customer actually reaches.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from khepri.rca.workspace.audit import ACTION_RUN_FAILED
from khepri.rra.analysis.compatibility import (
    CAUSE_BASIS,
    CAUSE_FORMULA_DRIFT,
    CAUSE_MAPPING_DRIFT,
    CAUSE_PACKAGE_DRIFT,
    CAUSE_SCOPE,
)
from khepri.rra.crossversion_bundle import CrossVersionBundle, CrossVersionRefusal
from khepri.rra.facts import METRIC_REVENUE
from tests.c105_support import build_comparison_request
from tests.c106_support import (
    compare_address,
    comparison_actions,
    completed_pair,
    shell_with_comparisons,
)
from tests.test_c106_comparison_orchestration import _request
from tests.w104_support import member
from tests.w104b_support import journey

#: The fixture pair: three days at 120.00 against three days at 100.00.
SUBJECT_REVENUE = Decimal("360.00")
BASELINE_REVENUE = Decimal("300.00")


@pytest.fixture
def comparison_request():
    return build_comparison_request()


def _assembled(request) -> CrossVersionBundle:
    from khepri.rra.crossversion_assembly import assemble_crossversion

    result = assemble_crossversion(request)
    assert isinstance(result, CrossVersionBundle), result
    return result


def _refusal(request) -> CrossVersionRefusal:
    from khepri.rra.crossversion_assembly import assemble_crossversion

    result = assemble_crossversion(request)
    assert isinstance(result, CrossVersionRefusal), result
    return result


def _figures_for(bundle: CrossVersionBundle, metric: str) -> dict[str | None, object]:
    """The metric's cells by label: `subject`, `baseline`, `difference`, and the ratio."""
    found = {figure.label: figure for figure in bundle.figures if figure.metric == metric}
    assert found, sorted({figure.metric for figure in bundle.figures})
    return found


def _value(bundle: CrossVersionBundle, metric: str, label: str) -> Decimal:
    figure = _figures_for(bundle, metric)[label]
    value = figure.value
    assert value is not None, (metric, label)
    return value


#: The four cells `RRA-006` §Two-population states for every compared metric.
CELLS = ("subject", "baseline", "difference", "percentage_difference")


def _pair_provenance_of(request):
    """The pair provenance the assembly builds, reused so this module states no digest."""
    from khepri.rra.crossversion_assembly import _pair_provenance

    return _pair_provenance(METRIC_REVENUE, request)


# --- exactness ------------------------------------------------------------------


def test_the_absolute_delta_is_the_exact_difference(comparison_request) -> None:
    """`RRA-008` §Comparative: the delta is `current - prior`, stated exactly.

    Hand-computed from the fixture rather than recomputed from the operands: three
    days at 120.00 against three at 100.00 is 360.00 against 300.00, so the delta is
    60.00 and nothing about the arithmetic is taken on the implementation's word.
    """
    bundle = _assembled(comparison_request)

    assert _value(bundle, METRIC_REVENUE, "subject") == SUBJECT_REVENUE
    assert _value(bundle, METRIC_REVENUE, "baseline") == BASELINE_REVENUE
    assert _value(bundle, METRIC_REVENUE, "difference") == Decimal("60.00")


def test_the_published_ratio_is_the_exact_four_place_fraction(comparison_request) -> None:
    """60.00 over 300.00 is exactly one fifth, so the published ratio is 0.2000.

    A four-place fraction, not a percent: review of `#408` found a pre-formatted
    percent string bypassed the shared formatter. The figure carries the fraction and
    the surface scales it.
    """
    bundle = _assembled(comparison_request)

    ratio = _figures_for(bundle, METRIC_REVENUE)["percentage_difference"]

    assert ratio.value == Decimal("0.2000")
    assert ratio.unit_kind == "ratio"
    # The stored value is the fraction; the surface scales it. Both are asserted so a
    # change that published the fraction raw, or the percent as the value, fails here.
    assert ratio.renderings["en"] == "20.00%"


def test_every_delta_reconciles_against_its_own_operands(comparison_request) -> None:
    """Not one metric but all of them: no fact may state a delta its operands deny.

    A per-metric loop rather than a spot check, so a metric whose delta is assembled
    on a different path cannot pass by being absent from a single assertion.
    """
    bundle = _assembled(comparison_request)
    metrics = {figure.metric for figure in bundle.figures}

    assert metrics
    for metric in sorted(metrics):
        cells = _figures_for(bundle, metric)
        assert set(cells) == set(CELLS), metric
        difference = _value(bundle, metric, "difference")
        assert difference == _value(bundle, metric, "subject") - _value(
            bundle, metric, "baseline"
        ), metric
        ratio = _value(bundle, metric, "percentage_difference")
        assert ratio == (difference / _value(bundle, metric, "baseline")).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_EVEN
        ), metric


def test_the_ratio_keeps_four_places_where_two_would_lose_the_difference() -> None:
    """The published quantum is four decimal places, and that is load-bearing.

    Every ratio the shared fixture produces is exact at two places (0.2000, 0.0000), so
    a mutant that quantized to two survived the assertions above -- a real gap the
    fixture cannot close. This drives the ratio directly with a pair whose quotient
    needs the fourth place: 1.00 over 300.00 is 0.003333..., which two places would
    publish as 0.00, erasing a real difference into "no change".
    """
    from khepri.rra.analysis.comparison_package import MeasuredPair, build_cross_version_fact
    from khepri.rra.crossversion_assembly import _percentage_ratio

    measured = MeasuredPair(
        metric=METRIC_REVENUE,
        subject_value=Decimal("301.00"),
        baseline_value=Decimal("300.00"),
        precision=2,
        unit_kind="monetary",
    )
    fact = build_cross_version_fact(measured, _pair_provenance_of(build_comparison_request()))

    ratio = _percentage_ratio(fact)

    assert ratio == Decimal("0.0033")
    assert ratio != Decimal("0.00")


def test_the_ratio_rounds_half_to_even_at_a_tie() -> None:
    """`RRA-008` publishes round-half-even, and only a tie can tell the modes apart.

    Self-review caught this gap: swapping the mode to `ROUND_HALF_UP` left every other
    test in this module passing, because each fixture quotient is exact and never
    reaches a tie. A subject of 1.000250 over a baseline of 1.00 is exactly 0.00025 at
    the fifth place -- half-even keeps 0.0002, half-up would publish 0.0003.
    """
    from khepri.rra.analysis.comparison_package import MeasuredPair, build_cross_version_fact
    from khepri.rra.crossversion_assembly import _percentage_ratio

    measured = MeasuredPair(
        metric=METRIC_REVENUE,
        subject_value=Decimal("1.000250"),
        baseline_value=Decimal("1.00"),
        precision=6,
        unit_kind="monetary",
    )
    fact = build_cross_version_fact(measured, _pair_provenance_of(build_comparison_request()))

    ratio = _percentage_ratio(fact)

    assert ratio == Decimal("0.0002")
    assert ratio != Decimal("0.0003")


# --- mixed version --------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "cause"),
    [
        ("mapping_version", CAUSE_MAPPING_DRIFT),
        ("formula_version", CAUSE_FORMULA_DRIFT),
        ("package_version", CAUSE_PACKAGE_DRIFT),
    ],
)
def test_a_mixed_version_pair_refuses_under_its_own_cause(
    comparison_request, field: str, cause: str
) -> None:
    """`RRA-008` `D-2`/`D-3`/`D-4`: each governed version must match, and each states
    its own cause. A single "drift" cause for all three would tell a reader nothing
    about which version moved, so the three are asserted apart."""
    drifted = replace(
        comparison_request,
        subject=replace(comparison_request.subject, **{field: "v-moved"}),
    )

    refused = _refusal(drifted)

    assert refused.cause == cause
    assert set(refused.wording) == {"en", "ar"}
    assert all(refused.wording[language].strip() for language in ("en", "ar"))


def test_the_three_drifts_are_told_apart_through_the_assembly(comparison_request) -> None:
    """Three different drifts, three different answers -- asserted through the door.

    Self-review caught the first version of this test asserting that three imported
    constants differ, which no change to the comparison could ever break. What matters
    is that the assembly distinguishes them: a reader told "formula drift" when the
    mapping moved has been told the wrong thing, and a single collapsed cause would
    pass a per-cause test that never compares the three against each other.
    """
    causes = {
        field: _refusal(
            replace(
                comparison_request,
                subject=replace(comparison_request.subject, **{field: "v-moved"}),
            )
        ).cause
        for field in ("mapping_version", "formula_version", "package_version")
    }
    wordings = {
        cause: _refusal(
            replace(
                comparison_request,
                subject=replace(comparison_request.subject, **{field: "v-moved"}),
            )
        ).wording["en"]
        for field, cause in causes.items()
    }

    assert len(set(causes.values())) == 3, causes
    assert len(set(wordings.values())) == 3, wordings


# --- unsupported filter ---------------------------------------------------------


@pytest.mark.parametrize("field", ["event_kind_filters", "status_filters"])
def test_a_filter_difference_refuses_as_an_incomparable_basis(
    comparison_request, field: str
) -> None:
    """`RRA-008` `D-5`: identical event-kind and status filters, or the pair is not
    comparable. The cause is the frozen `incomparable basis` -- `#408` corrected an
    earlier slice that had invented `filter mismatch`, which the frozen set does not
    contain."""
    filtered = replace(
        comparison_request,
        subject=replace(comparison_request.subject, **{field: ("returns-only",)}),
    )

    refused = _refusal(filtered)

    assert refused.cause == CAUSE_BASIS


def test_a_filter_difference_states_no_figure(comparison_request) -> None:
    """A refusal carries wording and nothing else: `RRA-008` §Refusals forbids a
    figure beside a refusal, so a reader cannot mistake a partial for a result."""
    filtered = replace(
        comparison_request,
        subject=replace(comparison_request.subject, event_kind_filters=("returns-only",)),
    )

    refused = _refusal(filtered)

    assert refused.figures == ()
    assert refused.bundle is None
    assert refused.wording["en"]


# --- cross organization ---------------------------------------------------------


def test_a_cross_scope_pair_refuses_before_any_figure(comparison_request) -> None:
    """`D-1`: two organizations' packages never compare, whatever else matches."""
    crossed = replace(comparison_request, subject_organization_scope="org_other")

    refused = _refusal(crossed)

    assert refused.cause == CAUSE_SCOPE


def test_a_foreign_pair_is_indistinguishable_from_a_missing_one(tmp_path) -> None:
    """`FR-050` through the shipped door: a member asking for another organization's
    version must not learn it exists. The two responses are compared byte for byte,
    which is the only assertion that can catch a difference in wording, length or
    ordering between the two paths."""
    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    mine = completed_pair(j, owner)
    theirs = completed_pair(j, stranger)
    client = shell_with_comparisons(j, owner, tmp_path)

    foreign = client.get(
        compare_address(owner, theirs.subject.version_id, mine.baseline.version_id)
    )
    missing = client.get(compare_address(owner, "dsv_no_such_version", mine.baseline.version_id))

    assert foreign.status_code == missing.status_code == 404
    assert foreign.text == missing.text


# --- deletion -------------------------------------------------------------------


def test_a_deleted_version_leaves_the_pair_unavailable_and_audited(tmp_path) -> None:
    """`KHEPRI-DEC-033`: a deleted version's comparison is the uniform unavailable
    surface, and the attempt is still audited exactly once.

    `test_deleted_version_refuses_uniformly` in the C1-06 module already proves the
    surface is uniform; it asserts nothing about the audit trail. This adds the half
    that matters for evidence: deletion removes the content, not the record that
    someone asked, and the record is still exactly one event under `FR-133`.
    """
    from tests.w107_support import deletion_service

    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j, tmp_path)
    deletion_service(j).delete_version(
        who.owner_id, pair.subject.version_id, actor_account_id=who.account_id, now=j.clock()
    )
    j.clock.advance(timedelta(minutes=1))
    before = len(j.w.audit.events_for_scope(who.owner_id))

    outcome = actions.request(
        _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
    )

    added = j.w.audit.events_for_scope(who.owner_id)[before:]
    assert outcome.unavailable
    assert [event.action for event in added] == [ACTION_RUN_FAILED]


# --- rerun ----------------------------------------------------------------------


def test_the_same_pair_assembles_the_same_bundle_twice(comparison_request) -> None:
    """`RRA-006`: a bundle is derived, not stored, so asking twice must give the same
    answer. The identity is compared, not the object, since a fresh assembly is a
    different instance by construction."""
    first = _assembled(comparison_request)
    second = _assembled(comparison_request)

    assert first.bundle_id == second.bundle_id
    assert first.identity.as_document() == second.identity.as_document()


def test_the_reversed_pair_is_a_different_bundle(comparison_request) -> None:
    """The ordered pair is the identity: subject against baseline is not the same
    comparison as baseline against subject, and the digest must say so."""
    forward = _assembled(comparison_request)
    reversed_pair = replace(
        comparison_request,
        subject=comparison_request.baseline,
        baseline=comparison_request.subject,
        subject_period=comparison_request.baseline_period,
        baseline_period=comparison_request.subject_period,
    )

    backward = _assembled(reversed_pair)

    assert forward.bundle_id != backward.bundle_id
    assert _value(backward, METRIC_REVENUE, "difference") == Decimal("-60.00")


# --- provenance -----------------------------------------------------------------


def test_every_figure_cites_evidence_naming_both_operands(comparison_request) -> None:
    """`RRA-008` §Two-population: a figure without its pair's provenance is a number
    with no stated origin. Every figure must carry evidence, and that evidence must
    name both versions rather than only the subject."""
    bundle = _assembled(comparison_request)
    by_citation = {record.citation_id: record for record in bundle.evidence}

    assert bundle.figures and by_citation
    for figure in bundle.figures:
        record = by_citation.get(figure.citation_id)
        assert record is not None, figure.metric
        stated = dict(record.provenance or ())
        # Both operands, and the order they were compared in: a composite provenance
        # naming only the subject would leave a reader unable to say what it was
        # compared against.
        assert stated.get("subject_version_id") == "dsv_subject", figure.metric
        assert stated.get("baseline_version_id") == "dsv_baseline", figure.metric
        assert stated.get("operand_order") == "subject,baseline", figure.metric
