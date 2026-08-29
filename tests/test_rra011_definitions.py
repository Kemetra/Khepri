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
from khepri.rra.rendering import wording


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

    assert {"code", "formula_version"} == fields


def test_a_definition_names_a_governed_version_rather_than_an_invented_label() -> None:
    """Scope test 1 binds what the catalog *returns*, not only what it admits.

    An earlier form grouped metrics under labels this module coined -- "core",
    "basket" -- and the route published them. A label is a code the catalog
    returns, and "core" corresponded to no constant anywhere, so the catalog was
    stating vocabulary of its own through the one field nobody was checking.

    Every value is now a version constant its own module declares.
    """
    governed = {
        facts.FORMULA_VERSION,
        comparison.COMPARISON_FORMULA_VERSION,
        growth.GROWTH_FORMULA_VERSION,
        basket.BASKET_FORMULA_VERSION,
        concentration.CONCENTRATION_FORMULA_VERSION,
    }

    published = {
        definitions.define_metric(code).formula_version
        for code in definitions.METRIC_CODES
    }

    assert published <= governed
    assert definitions.define_metric("revenue").formula_version == facts.FORMULA_VERSION
    assert (
        definitions.define_metric("basket_attach_rate").formula_version
        == basket.BASKET_FORMULA_VERSION
    )


# --- T1-03: the vocabulary RRA-011 authors -------------------------------
#
# `RRA-009` governs what a metric is *called*. `RRA-011` governs what it
# *means*: a description, safe synonyms a reader may recognize it by, and the
# interpretations it explicitly does not support. No existing artifact declared
# any of those, which is why the specification grants this one exception to its
# own derivation rule — and bounds it: vocabulary attaches only to a code some
# other module already governs, and never admits one.


def test_every_metric_the_catalog_admits_has_a_description_in_both_languages() -> None:
    """Parity asserted at import, so a one-language description cannot ship."""
    for language in ("en", "ar"):
        described = {
            code
            for code in definitions.METRIC_CODES
            if definitions.describe_metric(code, language)
        }
        assert described == set(definitions.METRIC_CODES)


def test_vocabulary_attaches_only_to_codes_a_governed_module_admits() -> None:
    """The bound that keeps authored wording from becoming a second truth.

    `RRA-011` grants the authority to *describe* a code and withholds the
    authority to *introduce* one. A description keyed to a code no family
    publishes would be exactly the invented vocabulary the derivation test
    forbids, arriving through the one door the specification left open.
    """
    # The tables live in `wording`, which `RRA-011`'s Scope names as their home:
    # a description sits beside the business name `RRA-009` governs because they
    # are one rendering surface. The bound is unchanged by where they live.
    for table in (wording.METRIC_DESCRIPTIONS, wording.METRIC_NOT_MEANT):
        for entries in table.values():
            assert set(entries) <= set(definitions.METRIC_CODES)


def test_a_metric_states_what_it_does_not_mean() -> None:
    """The half of T1 that stops a reader misreading a figure.

    An unsupported interpretation is not a hedge; it is the specific wrong
    reading the metric invites. `average_order_value` divides by *sale
    transactions*, so a reader taking it as revenue per customer is wrong in a
    way no caveat on the figure would tell them.
    """
    english = definitions.not_meant("average_order_value", "en")
    arabic = definitions.not_meant("average_order_value", "ar")

    assert "customer" in english.lower()
    assert english and arabic


def test_an_unknown_code_has_no_vocabulary_and_refuses() -> None:
    with pytest.raises(definitions.UnknownCode):
        definitions.describe_metric("revenues", "en")

    with pytest.raises(definitions.UnknownCode):
        definitions.not_meant("revenues", "en")


def test_an_unknown_language_refuses_rather_than_falling_back() -> None:
    """No silent English fallback: an Arabic reader gets Arabic or an error."""
    with pytest.raises(KeyError):
        definitions.describe_metric("revenue", "fr")
