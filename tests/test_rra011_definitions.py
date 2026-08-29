"""`definitions.py`: one catalog, derived from the sets that already govern.

`RRA-011` requires the catalog to be assembled from existing governed constants
and forbids it declaring a code of its own. It also requires a slice to *reduce*
the repository's count of hand-maintained code lists rather than add one, and
requires this proof to state its expectation independently — a test that read the
registry to check the registry would pass against any content, including nothing.

So every expectation below is written out. That makes the tests a second place
the vocabulary appears, which is deliberate and is the opposite of the defect:
a test that must be updated when a code lands is the guard, while a *module* that
must be updated is the duplicate truth.
"""

from __future__ import annotations

import dataclasses

import pytest

from khepri.rra import definitions, facts, populations
from khepri.rra.analysis import basket, comparison, concentration, growth


def test_each_analysis_family_states_the_metrics_it_publishes() -> None:
    """A family's published metrics are that family's to declare.

    `comparison` and `growth` already exported `GOVERNED_METRICS`; `basket` and
    `concentration` did not, and a catalog wanting "every published metric" had
    nowhere to read theirs from. Scanning their `METRIC_*` attributes is not the
    answer: `basket` re-exports `revenue`, `transactions` and `units` from
    `facts`, so a scan would attribute three core metrics to the basket family.
    """
    assert {"basket_items_per_transaction", "basket_attach_rate"} == set(
        basket.GOVERNED_METRICS
    )
    assert {
        "concentration_curve",
        "concentration_distinct_values",
        "concentration_ranked_values",
        "concentration_top_decile_share",
        "concentration_top_quartile_share",
    } == set(concentration.GOVERNED_METRICS)


def test_the_catalog_holds_every_governed_metric_and_no_others() -> None:
    """The union of five sources, and nothing invented on top of them."""
    expected = (
        set(facts.GOVERNED_METRICS)
        | set(comparison.GOVERNED_METRICS)
        | set(growth.GOVERNED_METRICS)
        | set(basket.GOVERNED_METRICS)
        | set(concentration.GOVERNED_METRICS)
    )

    assert expected == set(definitions.METRIC_CODES)


def test_the_catalog_holds_every_governed_population() -> None:
    assert set(populations.GOVERNED_POPULATIONS) == set(definitions.POPULATION_CODES)


def test_a_dimension_population_is_admitted_as_a_family_member() -> None:
    """`RRA-011`: admit a code the way its governing module admits it.

    `dimension_complete_sales:<dimension>` is a family whose members are whichever
    dimensions the mapping resolved, so `GOVERNED_POPULATIONS` excludes them and
    `is_governed_population` admits them by prefix. A catalog testing membership
    of the constants set would reject a population a real package carries.
    """
    concrete = populations.dimension_population("category")

    assert concrete not in definitions.POPULATION_CODES
    assert definitions.admits_population(concrete)
    assert not definitions.admits_population("dimension_complete_sales:")


def test_an_unknown_code_refuses_rather_than_returning_a_definition() -> None:
    """`RRA-011` fail-closed: no fabricated definition, no code-as-name."""
    assert definitions.define_metric("revenue").code == "revenue"

    with pytest.raises(definitions.UnknownCode):
        definitions.define_metric("revenues")


def test_a_definition_carries_only_catalog_scope_attributes() -> None:
    """Precision and population are properties of a run, not of a metric.

    `facts.py` reads monetary precision from the admitted data, and no record
    ties a metric to a population, so `RRA-011` forbids either appearing on the
    import-time catalog where it would be a guess dressed as a definition.
    """
    fields = {field.name for field in dataclasses.fields(definitions.MetricDefinition)}

    assert {"code", "family"} == fields
