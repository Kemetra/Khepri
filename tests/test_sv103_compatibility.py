"""`SV1-03` — early refusal, cause ordering, and bilingual wording.

Authority: active `RRA-014` `FR-137` (every effective dimension and filter is
visible; an undeclared, hidden, missing-required or unsupported parameter
refuses **before projection**) and `FR-141` (the closed cause set, bilingual
wording, no partial result).

Two disciplines shape these tests.

**Each cause is triggered alone.** A fixture that trips two predicates and
passes only because the wanted one sorts first proves nothing about the other,
and would keep passing if the other were deleted. Every cause below is asserted
to be the *only* predicate matching its fixture, and first-match ordering is
then asserted separately by an input that deliberately trips two.

**Every set is derived, never retyped** -- except `FR-141`'s cause set itself,
which is spelled out here because the specification spells it out. A test that
read the cause set from the module it is checking would be a tautology passing
every mutant.
"""

from __future__ import annotations

import dataclasses

import pytest

from khepri.rra import facts
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.semantic_views import compatibility, contracts, refusals, registry

#: `FR-141`'s enumeration, in the order that sentence lists them. Both the extent
#: and the order are the specification's, which is why this is the one literal
#: the file is allowed.
FR141_CAUSES = (
    "unknown view",
    "unknown version",
    "unknown metric",
    "unknown dimension",
    "unknown filter",
    "incompatible source shape",
    "missing required evidence",
)

_OVERVIEW = registry.define_view("ExecutiveOverviewView")
_COMPARISON = registry.define_view("PeriodComparisonView")
_BRANCH = registry.define_view("BranchPerformanceView")
_EVIDENCE_VIEW = registry.define_view("ReportEvidenceView")

_SINGLE = compatibility.SourceCandidate(source_shape=contracts.SHAPE_SINGLE_POPULATION)
_TWO = compatibility.SourceCandidate(source_shape=contracts.SHAPE_TWO_POPULATION)


def _request(definition: contracts.SemanticViewDefinition, **overrides: object):
    """A request that is valid for `definition`, so a test can spoil one field."""
    fields: dict[str, object] = {
        "view_id": definition.view_id,
        "view_version": definition.view_version,
        "metrics": (),
        "dimensions": (),
        "filters": (),
    }
    return compatibility.SemanticViewRequest(**(fields | overrides))  # type: ignore[arg-type]


def _matching_causes(admission: compatibility.Admission) -> tuple[str, ...]:
    """Every cause whose predicate matches, not merely the first one returned."""
    return tuple(
        cause
        for cause, holds in compatibility._PREDICATES  # noqa: SLF001
        if holds(admission)  # type: ignore[operator]
    )


#: One fixture per cause, each built to trip exactly that predicate.
#: `missing required evidence` is the one cause no *published* view can raise --
#: all eight publish `required_evidence=()` -- so it is exercised through a
#: definition constructed here. The cause is `FR-141`'s and must exist before a
#: view version requires evidence, not after.
_EVIDENCE_REQUIRED = contracts.SemanticViewDefinition(
    view_id="EvidenceRequiringProbeView",
    view_version="sv1.evidence_requiring_probe.v1",
    accepted_source_shape=contracts.SHAPE_SINGLE_POPULATION,
    metric_allowlist=("revenue",),
    dimension_allowlist=(facts.PERIOD_DIMENSION,),
    request_filter_allowlist=(),
    fixed_filters=(),
    required_evidence=("figure_provenance",),
    output_field_order=("metric", "value"),
    empty_result_rule=contracts.EMPTY_STATED_ABSENCE,
)

_CASES: tuple[tuple[str, compatibility.Admission], ...] = (
    (
        refusals.CAUSE_UNKNOWN_VIEW,
        compatibility.Admission(
            request=_request(_OVERVIEW, view_id="NoSuchView"),
            definition=None,
            candidate=_SINGLE,
        ),
    ),
    (
        refusals.CAUSE_UNKNOWN_VERSION,
        compatibility.Admission(
            request=_request(_OVERVIEW, view_version="sv1.executive_overview.v99"),
            definition=_OVERVIEW,
            candidate=_SINGLE,
        ),
    ),
    (
        refusals.CAUSE_UNKNOWN_METRIC,
        compatibility.Admission(
            request=_request(_OVERVIEW, metrics=("no_such_metric",)),
            definition=_OVERVIEW,
            candidate=_SINGLE,
        ),
    ),
    (
        refusals.CAUSE_UNKNOWN_DIMENSION,
        compatibility.Admission(
            request=_request(_OVERVIEW, dimensions=(facts.SEMANTIC_CHANNEL,)),
            definition=_OVERVIEW,
            candidate=_SINGLE,
        ),
    ),
    (
        refusals.CAUSE_UNKNOWN_FILTER,
        compatibility.Admission(
            request=_request(_BRANCH, filters=((facts.SEMANTIC_CHANNEL, "web"),)),
            definition=_BRANCH,
            candidate=_SINGLE,
        ),
    ),
    (
        refusals.CAUSE_INCOMPATIBLE_SOURCE_SHAPE,
        compatibility.Admission(
            request=_request(_COMPARISON),
            definition=_COMPARISON,
            candidate=_SINGLE,
        ),
    ),
    (
        refusals.CAUSE_MISSING_REQUIRED_EVIDENCE,
        compatibility.Admission(
            request=_request(_EVIDENCE_REQUIRED),
            definition=_EVIDENCE_REQUIRED,
            candidate=_SINGLE,
        ),
    ),
)


def test_the_cause_set_is_exactly_the_seven_fr141_names() -> None:
    """`FR-141` closes the set; an eighth cause is an `RRA-014` amendment."""
    assert frozenset(FR141_CAUSES) == refusals.REFUSAL_CAUSES


def test_the_cause_set_is_derived_from_the_wording_table() -> None:
    """A list beside the table is a second truth that goes stale when one moves."""
    assert frozenset(refusals.VIEW_REFUSALS) == refusals.REFUSAL_CAUSES


def test_every_cause_carries_non_empty_wording_in_both_languages() -> None:
    """`FR-141` -- bilingual. Wording added to one language must reach the other."""
    for cause in sorted(refusals.REFUSAL_CAUSES):
        wording = refusals.refusal_wording(cause)
        assert set(wording) == {LANGUAGE_ENGLISH, LANGUAGE_ARABIC}, cause
        for language, text in wording.items():
            assert text.strip(), f"{cause} has empty {language} wording"


def test_refusal_wording_refuses_a_cause_the_specification_does_not_name() -> None:
    """Failing closed beats inventing wording for a cause `FR-141` never named."""
    with pytest.raises(KeyError):
        refusals.refusal_wording("filter mismatch")


def test_the_predicate_table_is_in_the_order_fr141_enumerates() -> None:
    """Order decides which cause a caller sees, so a reordering must fail here."""
    ordered = tuple(cause for cause, _ in compatibility._PREDICATES)  # noqa: SLF001
    assert ordered == FR141_CAUSES


def test_the_predicate_table_covers_every_cause_exactly_once() -> None:
    """A cause with no predicate is unreachable; a repeat makes its order unclear."""
    ordered = [cause for cause, _ in compatibility._PREDICATES]  # noqa: SLF001
    assert sorted(ordered) == sorted(refusals.REFUSAL_CAUSES)
    assert len(ordered) == len(set(ordered))


@pytest.mark.parametrize(("cause", "admission"), _CASES, ids=[c for c, _ in _CASES])
def test_each_cause_is_returned_by_an_input_that_triggers_only_it(
    cause: str, admission: compatibility.Admission
) -> None:
    """Every cause is reachable, and by a fixture no other predicate matches.

    The second half is the load-bearing one: a fixture tripping two predicates
    would pass on ordering alone and keep passing if its own predicate were
    deleted.
    """
    assert _matching_causes(admission) == (cause,)
    refusal = compatibility.validate(admission.request, admission.definition, admission.candidate)
    assert refusal is not None
    assert refusal.cause == cause


def test_the_first_matching_cause_is_the_one_returned() -> None:
    """Two causes at once must report the earlier, not an arbitrary one.

    An unknown version *and* an unknown metric: the metric is checked against a
    version that was never published, so the version is the one to fix first.
    """
    admission = compatibility.Admission(
        request=_request(
            _OVERVIEW,
            view_version="sv1.executive_overview.v99",
            metrics=("no_such_metric",),
        ),
        definition=_OVERVIEW,
        candidate=_SINGLE,
    )
    assert _matching_causes(admission) == (
        refusals.CAUSE_UNKNOWN_VERSION,
        refusals.CAUSE_UNKNOWN_METRIC,
    )
    refusal = compatibility.validate(admission.request, admission.definition, admission.candidate)
    assert refusal is not None
    assert refusal.cause == refusals.CAUSE_UNKNOWN_VERSION


def test_a_wholly_valid_request_is_admitted() -> None:
    """The refusals must not be a blanket one: a good request returns `None`."""
    request = _request(
        _BRANCH,
        metrics=_BRANCH.metric_allowlist,
        dimensions=_BRANCH.dimension_allowlist,
        filters=((facts.SEMANTIC_STORE, "riyadh-01"),),
    )
    assert compatibility.validate(request, _BRANCH, _SINGLE) is None


def test_an_admitted_filter_parameter_passes_whatever_its_value() -> None:
    """The allowlist admits parameters; values are customer data, not vocabulary."""
    for value in ("riyadh-01", "", "'; drop table --"):
        request = _request(_BRANCH, filters=((facts.SEMANTIC_STORE, value),))
        assert compatibility.validate(request, _BRANCH, _SINGLE) is None, value


def test_an_undeclared_filter_refuses_rather_than_being_silently_dropped() -> None:
    """`FR-137` -- a dropped filter returns more data than was asked for, silently."""
    request = _request(_BRANCH, filters=((facts.SEMANTIC_CHANNEL, "web"),))
    refusal = compatibility.validate(request, _BRANCH, _SINGLE)
    assert refusal is not None
    assert refusal.cause == refusals.CAUSE_UNKNOWN_FILTER


def test_a_view_admitting_either_bundle_accepts_both_concrete_shapes() -> None:
    """`SHAPE_EITHER_BUNDLE` means both are admitted, so it raises no shape cause."""
    request = _request(_EVIDENCE_VIEW)
    assert _EVIDENCE_VIEW.accepted_source_shape == contracts.SHAPE_EITHER_BUNDLE
    for candidate in (_SINGLE, _TWO):
        assert compatibility.validate(request, _EVIDENCE_VIEW, candidate) is None


def test_a_definition_resolved_for_another_view_refuses_as_unknown() -> None:
    """A caller that looked up the wrong record has named a view this cannot answer."""
    request = _request(_OVERVIEW)
    refusal = compatibility.validate(request, _BRANCH, _SINGLE)
    assert refusal is not None
    assert refusal.cause == refusals.CAUSE_UNKNOWN_VIEW


def test_a_refusal_carries_wording_and_nothing_a_result_could_travel_in() -> None:
    """`FR-141` -- no partial result. A field for one is a place one can appear."""
    names = {field.name for field in dataclasses.fields(refusals.ViewRefusal)}
    assert names == {"cause", "wording"}
    refusal = refusals.refuse(refusals.CAUSE_UNKNOWN_VIEW)
    assert refusal.wording == refusals.refusal_wording(refusals.CAUSE_UNKNOWN_VIEW)


def test_a_refusal_cannot_be_built_for_a_cause_fr141_does_not_name() -> None:
    """`#408`'s lesson: `C1-02` emitted a cause its specification did not contain."""
    with pytest.raises(ValueError, match="filter mismatch"):
        refusals.ViewRefusal(cause="filter mismatch")


def test_validate_reads_no_row_because_it_is_handed_none() -> None:
    """`FR-137` refuses *before* projection; a validator given a value could return one."""
    names = {field.name for field in dataclasses.fields(compatibility.SourceCandidate)}
    assert names == {"source_shape", "evidence_codes"}
