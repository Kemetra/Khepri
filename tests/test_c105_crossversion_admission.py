"""What a two-population bundle refuses, and the invariants a directly built one must hold.

RRA-008 §Admission and §Refusals and caveats: every cause refuses with bilingual wording and
no figure; RRA-006 §Two-population bundle: a refused pair is no bundle at all. The invariant
tests reconstruct bundles with `dataclasses.replace` to reach states assembly never produces."""

from __future__ import annotations

from dataclasses import replace

import pytest

from khepri.rra import crossversion_assembly as assembly_module
from khepri.rra.analysis.comparison_narrative import CROSSVERSION_REFUSALS
from khepri.rra.analysis.dataset_period import (
    CAUSE_INCOMPLETE,
)
from khepri.rra.crossversion_bundle import (
    LABEL_DIFFERENCE,
    LABEL_SUBJECT,
    CrossVersionBundle,
    CrossVersionRefusal,
    CrossVersionRequest,
    build_crossversion_bundle,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from tests.c105_support import (
    _bundle,
    _compatibility_cases,
    _period_cases,
    _refusal,
    build_comparison_request,
)


@pytest.fixture(scope="module")
def comparison_request() -> CrossVersionRequest:
    return build_comparison_request()


def test_every_refusal_cause_returns_wording_and_no_bundle(
    comparison_request: CrossVersionRequest,
) -> None:
    request = comparison_request
    cases = (*_compatibility_cases(request), *_period_cases(request))
    assert {cause for cause, _ in cases} == set(CROSSVERSION_REFUSALS)
    for expected, changed in cases:
        refused = _refusal(build_crossversion_bundle(changed))
        assert refused.cause == expected
        assert refused.wording == CROSSVERSION_REFUSALS[expected]


def test_scope_projection_does_not_read_retained_evidence(
    comparison_request: CrossVersionRequest,
) -> None:
    """Emptying one package's daily bases must not turn its scope into a mismatch.

    Review of #408 (debate-review): the projection inferred manifest shape from
    `daily_bases`, which `facts` also empties for a repeated row signature, so two
    datasets of one organization refused as `cross-organization or scope mismatch`.
    The projection now compares the attested scope sets directly.
    """
    request = comparison_request
    stripped = replace(request, subject=replace(request.subject, daily_bases=()))

    result = build_crossversion_bundle(stripped)

    assert isinstance(result, CrossVersionBundle)


def test_pair_sharing_no_metric_refuses_rather_than_raising(
    comparison_request: CrossVersionRequest,
) -> None:
    """Admission reads provenance, not columns; the empty comparison is a refusal.

    Review of #408 (debate-review): two admitted packages gapped in each other's
    columns passed every predicate, produced no facts, and the bundle's own rules
    then raised -- neither a bundle nor governed wording. It is now a refusal under
    `incomplete coverage`, with wording in both languages and no figure.
    """
    request = comparison_request
    disjoint = replace(request, baseline=replace(request.baseline, facts=()))

    result = build_crossversion_bundle(disjoint)

    assert isinstance(result, CrossVersionRefusal)
    assert result.cause == CAUSE_INCOMPLETE
    assert set(result.wording) == {LANGUAGE_ARABIC, LANGUAGE_ENGLISH}
    assert result.figures == ()
    assert result.bundle is None


def test_matched_metric_without_a_retained_basis_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    """A basis the cited metric needs but the package does not retain is a refusal.

    Review of #408: admission checked only that each package retained *some* basis,
    so a package missing the one a matched metric cites raised from the basis
    lookup after the pair was admitted. Admission now checks every shared metric on
    both sides and refuses under `incomplete coverage`.
    """
    request = comparison_request
    without_revenue_basis = tuple(
        basis
        for basis in request.baseline.retained_bases
        if basis.name != "financial_revenue_basis"
    )
    assert len(without_revenue_basis) == len(request.baseline.retained_bases) - 1
    thinned = replace(
        request, baseline=replace(request.baseline, retained_bases=without_revenue_basis)
    )

    result = build_crossversion_bundle(thinned)

    assert isinstance(result, CrossVersionRefusal)
    assert result.cause == CAUSE_INCOMPLETE
    assert result.bundle is None


def test_basis_map_covers_every_governed_metric_and_nothing_else(
    comparison_request: CrossVersionRequest,
) -> None:
    """The import-time guard, asserted against the emitted set and exercised.

    Review of #408 (debate-review): without this a metric added to GOVERNED_METRICS
    later would refuse every pair under `incomplete coverage` instead of failing
    once at import. The guard is called with a broken table so the test proves it
    can fail, not only that the shipped table passes it.
    """
    from khepri.rra.facts import GOVERNED_METRICS

    table = assembly_module._BASIS_BY_METRIC
    assert set(table) == GOVERNED_METRICS
    assert {figure.metric for figure in _bundle(comparison_request).figures} <= set(table)

    missing_one = {metric: basis for metric, basis in table.items() if metric != "revenue"}
    with pytest.raises(ValueError, match="missing \\['revenue'\\]"):
        assembly_module._assert_basis_map_complete(missing_one)
    with pytest.raises(ValueError, match="unknown \\['invented'\\]"):
        assembly_module._assert_basis_map_complete({**table, "invented": "some_basis"})


def test_package_stating_a_metric_twice_fails_named_not_as_a_repeated_figure(
    comparison_request: CrossVersionRequest,
) -> None:
    """A malformed population fails closed at the door, with its own name.

    Review of #408 (debate-review): a hand-built subject package with a duplicated
    metric produced two facts under one identity and surfaced as "section repeats
    a figure". It is not a governed refusal -- RRA-008 §Frozen contracts puts an
    input RRA-004 would not admit upstream of this family, and every frozen cause
    would misdescribe it -- so it is an explicit invariant instead.
    """
    request = comparison_request
    doubled = replace(request.subject, facts=(*request.subject.facts, request.subject.facts[0]))

    with pytest.raises(ValueError, match="states a metric twice"):
        build_crossversion_bundle(replace(request, subject=doubled))


def test_same_name_basis_bound_to_another_input_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    """A basis is the package's own only if it binds to the package's input and mapping.

    Review of #408 (CodeRabbit): the lookup matched by name alone, so a hand-built
    package carrying a foreign basis under the right name would have published that
    basis identity as provenance. It is now not found, and the pair refuses.
    """
    request = comparison_request
    rebound = tuple(
        replace(basis, input_digest="0" * 64) if basis.name == "financial_revenue_basis" else basis
        for basis in request.baseline.retained_bases
    )
    foreign = replace(request, baseline=replace(request.baseline, retained_bases=rebound))

    result = build_crossversion_bundle(foreign)

    assert isinstance(result, CrossVersionRefusal)
    assert result.cause == CAUSE_INCOMPLETE


def test_citation_naming_a_different_pair_than_its_identity_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    """Every identity citation is bound to the identity's own ordered pair."""
    identity = _bundle(comparison_request).identity
    first, *rest = identity.citations
    swapped_pair = replace(
        first.pair,
        subject_version_id=first.pair.baseline_version_id,
        baseline_version_id=first.pair.subject_version_id,
    )

    with pytest.raises(ValueError, match="different pair"):
        replace(identity, citations=(replace(first, pair=swapped_pair), *rest))


def test_identity_repeating_a_citation_refuses(comparison_request: CrossVersionRequest) -> None:
    """Keyed by identifier downstream, a repeated citation would silently collapse."""
    identity = _bundle(comparison_request).identity
    first, *rest = identity.citations

    with pytest.raises(ValueError, match="repeats a citation"):
        replace(identity, citations=(first, first, *rest))


def test_group_with_a_repeated_operand_refuses(comparison_request: CrossVersionRequest) -> None:
    """Two subject cells are not one subject; a set of labels would not notice."""
    bundle = _bundle(comparison_request)
    subject = next(figure for figure in bundle.figures if figure.label == LABEL_SUBJECT)
    duplicate = replace(subject, figure_id=f"{subject.figure_id}-again")
    figures = (*bundle.figures, duplicate)
    section = replace(bundle.sections[0], figure_ids=tuple(figure.figure_id for figure in figures))

    with pytest.raises(ValueError, match="repeats"):
        replace(bundle, figures=figures, sections=(section,))


def test_group_without_an_absolute_difference_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    """Subject and baseline alone are two numbers, not a comparison."""
    bundle = _bundle(comparison_request)
    kept = tuple(figure for figure in bundle.figures if figure.label != LABEL_DIFFERENCE)
    section = replace(bundle.sections[0], figure_ids=tuple(figure.figure_id for figure in kept))

    with pytest.raises(ValueError, match="difference"):
        replace(bundle, figures=kept, sections=(section,))


def test_duplicate_evidence_record_refuses(comparison_request: CrossVersionRequest) -> None:
    bundle = _bundle(comparison_request)

    with pytest.raises(ValueError, match="repeats"):
        replace(bundle, evidence=(*bundle.evidence, bundle.evidence[0]))


def test_evidence_with_a_different_metric_than_its_figure_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    bundle = _bundle(comparison_request)
    first, *rest = bundle.evidence

    with pytest.raises(ValueError, match="disagrees"):
        replace(bundle, evidence=(replace(first, metric="another_metric"), *rest))


def test_forged_provenance_under_a_real_citation_refuses(
    comparison_request: CrossVersionRequest,
) -> None:
    """A real citation identifier does not launder a different pair."""
    bundle = _bundle(comparison_request)
    first, *rest = bundle.evidence
    assert first.provenance is not None
    forged = tuple(
        (key, {"subject_version_id": "dsv_forged"}.get(key, value))
        for key, value in first.provenance
    )

    with pytest.raises(ValueError, match="different pair"):
        replace(bundle, evidence=(replace(first, provenance=forged), *rest))
