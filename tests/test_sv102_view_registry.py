"""`SV1-02` — the closed, versioned semantic-view definition registry.

Authority: active `RRA-014` `FR-134` (immutable identity; any field change is a
new version), `FR-135` (the registry is closed to exactly eight views and every
allowlist member derives from its governing declaration), `FR-136` (each
definition admits an exact source shape).

The tests here are extent tests on purpose. `FR-135` says "closed", which is a
claim about the whole set, and a subset assertion cannot see a ninth view added
-- the defect `RCA_TABLES` shipped three times. Every membership assertion below
is an equality against a set derived from the governing module, never against a
list of codes retyped here: a literal copied into this file would be the "second
truth" `FR-135` forbids, and it would pass while the governing declaration moved
underneath it.
"""

from __future__ import annotations

import dataclasses

import pytest

from khepri.rra import definitions, facts
from khepri.rra.semantic_views import contracts, registry

#: The eight views `RRA-014` publishes, spelled out because the specification
#: spells them out. This is the one place a literal is correct: it is the
#: closed set the specification names, and a test deriving it from the registry
#: it is checking would be a tautology that passes every mutant.
PUBLISHED_VIEW_IDS = frozenset(
    {
        "ExecutiveOverviewView",
        "PeriodComparisonView",
        "BranchPerformanceView",
        "ProductCategoryView",
        "BasketView",
        "ConcentrationView",
        "ReportEvidenceView",
        "MetricAvailabilityView",
    }
)


def test_registry_extent_equals_the_eight_published_views() -> None:
    """`FR-135` -- closed. Equality, never `>=`: a ninth view must fail here."""
    assert registry.view_ids() == PUBLISHED_VIEW_IDS


def test_registry_is_not_empty() -> None:
    """A registry that fails to load must not pass the extent test by being empty.

    Without this, `view_ids()` returning `frozenset()` would fail the equality
    above -- but a future refactor that makes both sides derive from the same
    empty source would pass both. Assert non-emptiness separately.
    """
    assert len(registry.view_ids()) == 8


def test_every_metric_in_every_allowlist_is_a_governed_metric() -> None:
    """`FR-135` -- derived, never retyped.

    Iterates the registry rather than checking named views, so a view added
    with an invented metric code cannot pass by not being in this test's list.
    """
    for view_id in sorted(registry.view_ids()):
        definition = registry.define_view(view_id)
        assert definition.metric_allowlist, f"{view_id} allows no metric"
        for code in definition.metric_allowlist:
            assert definitions.admits_metric(code), f"{view_id} invented {code!r}"


def test_every_dimension_in_every_allowlist_is_a_governed_dimension() -> None:
    """`FR-135` -- the dimension axis is `facts.SERIES_DIMENSIONS`, not a copy."""
    governed = frozenset(facts.SERIES_DIMENSIONS)
    for view_id in sorted(registry.view_ids()):
        definition = registry.define_view(view_id)
        for dimension in definition.dimension_allowlist:
            assert dimension in governed, f"{view_id} invented {dimension!r}"


def test_no_allowlist_admits_a_metric_no_builder_can_emit() -> None:
    """`FR-135`, reading `SERIES_METRICS`' own rule.

    `definitions.SERIES_METRICS` composes `<measure>_by_<dimension>` over
    `SERIES_MEASURES` -- revenue and units -- precisely because composing over
    all ten core metrics admits `gross_margin_by_channel`, which no builder
    emits. A view allowlist that reintroduces such a code defines an
    unproducible metric, which is not fail-closed.
    """
    unproducible = frozenset(
        f"{measure}_by_{dimension}"
        for measure in sorted(set(facts.GOVERNED_METRICS) - set(facts.SERIES_MEASURES))
        for dimension in facts.SERIES_DIMENSIONS
    )
    assert unproducible, "the fixture must name codes no builder emits"
    for view_id in sorted(registry.view_ids()):
        allowed = frozenset(registry.define_view(view_id).metric_allowlist)
        assert not (allowed & unproducible), f"{view_id} admits an unproducible code"


def test_an_unknown_view_refuses_rather_than_returning_none() -> None:
    """`FR-141` fails closed; a `None` would be indistinguishable from a real miss."""
    with pytest.raises(registry.UnknownView):
        registry.define_view("NoSuchView")


def test_a_ninth_view_cannot_be_registered() -> None:
    """`FR-135` -- the published set is closed, not a default."""
    with pytest.raises(registry.UnknownView):
        registry.define_view("ExecutiveOverviewViewV2")


def test_a_definition_is_frozen() -> None:
    """`FR-134` -- immutable after publication."""
    definition = registry.define_view("ExecutiveOverviewView")
    with pytest.raises(dataclasses.FrozenInstanceError):
        definition.view_version = "sv1.executive.v99"  # type: ignore[misc]


def test_every_definition_carries_the_ten_contract_fields() -> None:
    """`RRA-014` names exactly ten contract fields; a missing one is a gap."""
    expected = {
        "view_id",
        "view_version",
        "accepted_source_shape",
        "metric_allowlist",
        "dimension_allowlist",
        "request_filter_allowlist",
        "fixed_filters",
        "required_evidence",
        "output_field_order",
        "empty_result_rule",
    }
    actual = {field.name for field in dataclasses.fields(contracts.SemanticViewDefinition)}
    assert actual == expected


def test_every_definition_names_an_admitted_source_shape() -> None:
    """`FR-136` -- single-population bundle, two-population bundle, or both."""
    for view_id in sorted(registry.view_ids()):
        shape = registry.define_view(view_id).accepted_source_shape
        assert shape in contracts.ADMITTED_SOURCE_SHAPES, f"{view_id}: {shape!r}"


def test_output_field_order_is_an_ordered_tuple_with_no_repeat() -> None:
    """`FR-134` makes output order part of identity, so it must be a sequence."""
    for view_id in sorted(registry.view_ids()):
        order = registry.define_view(view_id).output_field_order
        assert isinstance(order, tuple), f"{view_id} order is not a tuple"
        assert len(order) == len(set(order)), f"{view_id} repeats a field"
        assert order, f"{view_id} publishes no field"


def test_every_definition_states_an_empty_rule() -> None:
    """`FR-142`'s rule is per-definition; a view without one has no empty behaviour."""
    for view_id in sorted(registry.view_ids()):
        rule = registry.define_view(view_id).empty_result_rule
        assert rule in contracts.EMPTY_RULES, f"{view_id}: {rule!r}"


def test_view_versions_are_unique_across_the_registry() -> None:
    """Two views sharing a version make `FR-143`'s exact-version request ambiguous."""
    versions = [registry.define_view(v).view_version for v in sorted(registry.view_ids())]
    assert len(versions) == len(set(versions))


def _definition(view_id: str, **overrides: object) -> contracts.SemanticViewDefinition:
    """A minimal admissible definition, so each test varies one field only.

    Each caller passes its own `view_id`: `FR-134`'s identity invariant is
    process-wide by construction, so a shared identity would make one test's
    record the cause of another test's refusal.
    """
    fields: dict[str, object] = {
        "view_id": view_id,
        "view_version": f"sv1.{view_id}.v1",
        "accepted_source_shape": contracts.SHAPE_SINGLE_POPULATION,
        "metric_allowlist": ("revenue",),
        "dimension_allowlist": (facts.PERIOD_DIMENSION,),
        "request_filter_allowlist": (),
        "fixed_filters": (),
        "required_evidence": (),
        "output_field_order": ("metric", "value"),
        "empty_result_rule": contracts.EMPTY_STATED_ABSENCE,
    }
    return contracts.SemanticViewDefinition(**(fields | overrides))  # type: ignore[arg-type]


def test_an_unadmitted_source_shape_refuses_at_construction() -> None:
    """`FR-136` admits exactly three shapes; `frozen=True` cannot see a fourth.

    The constant existed before this test and nothing read it, which is a
    vocabulary that documents rather than governs.
    """
    with pytest.raises(contracts.ViewDefinitionRefused):
        _definition("ShapeProbeView", accepted_source_shape="invalid")


def test_an_unknown_empty_rule_refuses_at_construction() -> None:
    """`FR-142`'s rule is per-definition, so a definition may not invent one."""
    with pytest.raises(contracts.ViewDefinitionRefused):
        _definition("EmptyRuleProbeView", empty_result_rule="widen_to_unfiltered")


def test_every_admitted_shape_and_rule_constructs() -> None:
    """The refusal must not be a blanket one: each published value is admitted."""
    for index, shape in enumerate(sorted(contracts.ADMITTED_SOURCE_SHAPES)):
        for rule in sorted(contracts.EMPTY_RULES):
            definition = _definition(
                f"AdmittedProbeView{index}{rule}",
                accepted_source_shape=shape,
                empty_result_rule=rule,
            )
            assert definition.accepted_source_shape == shape
            assert definition.empty_result_rule == rule


def test_replacing_a_semantic_field_without_moving_the_version_refuses() -> None:
    """`FR-134` -- a changed field is a new version, and `replace` bypasses `frozen`.

    `frozen=True` blocks assignment to an existing record; it does not stop
    `dataclasses.replace` producing a second record that keeps `view_id` and
    `view_version` while changing what they mean.
    """
    published = registry.define_view("ExecutiveOverviewView")
    with pytest.raises(contracts.ViewDefinitionRefused):
        dataclasses.replace(published, output_field_order=("value", "metric"))


def test_every_version_moving_field_is_covered_by_the_identity_check() -> None:
    """`FR-134` names eight fields; a ninth added to the record joins them.

    Iterates the record's own fields rather than a list retyped here, so a
    contract field added without joining the comparison fails this test.
    """
    published = registry.define_view("BranchPerformanceView")
    changed: dict[str, object] = {
        "accepted_source_shape": contracts.SHAPE_TWO_POPULATION,
        "metric_allowlist": ("revenue",),
        "dimension_allowlist": (facts.SEMANTIC_PRODUCT,),
        "request_filter_allowlist": (facts.SEMANTIC_PRODUCT,),
        "fixed_filters": (("channel", "web"),),
        "required_evidence": ("figure_provenance",),
        "output_field_order": ("metric",),
        "empty_result_rule": contracts.EMPTY_STATED_ABSENCE,
    }
    version_moving = {
        field.name
        for field in dataclasses.fields(contracts.SemanticViewDefinition)
        if field.name not in {"view_id", "view_version"}
    }
    assert set(changed) == version_moving, "a contract field is not exercised here"
    for name, value in changed.items():
        with pytest.raises(contracts.ViewDefinitionRefused, match="new version"):
            dataclasses.replace(published, **{name: value})


def test_moving_the_version_admits_the_changed_definition() -> None:
    """The refusal is about reusing a version, not about changing a definition."""
    published = registry.define_view("ConcentrationView")
    successor = dataclasses.replace(
        published,
        view_version="sv1.concentration.v2",
        output_field_order=("metric", "dimension", "value", "population"),
    )
    assert successor.view_version != published.view_version


def test_reconstructing_an_identical_definition_is_admitted() -> None:
    """An import is not an edit: the check compares content, not repetition."""
    published = registry.define_view("BasketView")
    assert dataclasses.replace(published) == published
