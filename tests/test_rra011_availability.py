"""`T1-04`'s pre-analysis capability availability, derived from the mapping alone.

The `Analysis Impact Preview` shows, **before the analysis step runs**, which
analyses the admitted data can support -- `KHEPRI_PRODUCT_UX_BLUEPRINT.md`:201
places it `Review -> Impact Preview -> Analyze`, and :309 states it as
availability drawn from the `T1` vocabulary. No `ReportBundle` exists at that
point, so this contract reads the `RetailMapping` and nothing else.

Two boundaries this suite exists to hold:

- **Availability, never certainty.** `RRA-011`:188-192 excludes a confidence
  score, a quality score, a likelihood, and a completeness percentage by name.
  This answers set membership -- are a family's declared inputs resolved -- and
  performs no arithmetic, so it has no shape a score could hide in.
- **Derived, never restated.** Each family declares the semantics it needs. A
  second table here naming those inputs would be exactly the hand-maintained
  parallel truth `RRA-011` forbids and requires each slice to reduce.
"""

from __future__ import annotations

import dataclasses

import pytest

from khepri.rra import definitions
from khepri.rra.analysis import basket, comparison, concentration, growth
from khepri.rra.bundle import (
    SECTION_BASKET,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_GROWTH,
)
from khepri.rra.mapping import (
    REQUIREMENT_CORE_MEASURE,
    SEMANTIC_CATEGORY,
    SEMANTIC_PRODUCT,
    SEMANTIC_REVENUE,
    SEMANTIC_TRANSACTION_DATE,
    SEMANTIC_TRANSACTION_ID,
    SEMANTIC_UNITS,
    STATE_AMBIGUOUS,
    STATE_MAPPED,
    STATE_UNAVAILABLE,
    RetailMapping,
    SemanticMapping,
)

_ALL_SEMANTICS = (
    SEMANTIC_TRANSACTION_DATE,
    SEMANTIC_REVENUE,
    SEMANTIC_UNITS,
    SEMANTIC_TRANSACTION_ID,
    SEMANTIC_PRODUCT,
    SEMANTIC_CATEGORY,
)


def _mapping(**states: str) -> RetailMapping:
    """A mapping whose every semantic is `STATE_UNAVAILABLE` unless named.

    Built here rather than from a file so a test states exactly the mapping
    state it is about. Availability reads `state_of`, so the candidates a real
    mapper would attach are not what this contract consults.
    """
    return RetailMapping(
        mapping_version="rra003.mapping.v1",
        mappings=tuple(
            SemanticMapping(
                semantic=semantic,
                requirement=REQUIREMENT_CORE_MEASURE,
                state=states.get(semantic, STATE_UNAVAILABLE),
                candidates=(),
            )
            for semantic in _ALL_SEMANTICS
        ),
        excluded_positions=(),
    )


def _for(report, section: str):
    return next(entry for entry in report if entry.section == section)


def test_a_family_with_every_input_resolved_is_available() -> None:
    """`growth` needs a date, revenue and units; resolve all three."""
    mapping = _mapping(
        **{
            SEMANTIC_TRANSACTION_DATE: STATE_MAPPED,
            SEMANTIC_REVENUE: STATE_MAPPED,
            SEMANTIC_UNITS: STATE_MAPPED,
        }
    )

    entry = _for(definitions.availability(mapping), SECTION_GROWTH)

    assert entry.state == definitions.AVAILABLE
    assert entry.missing == ()


def test_a_family_with_no_input_resolved_is_unavailable() -> None:
    """Nothing mapped, so nothing this family needs is present."""
    entry = _for(definitions.availability(_mapping()), SECTION_GROWTH)

    assert entry.state == definitions.UNAVAILABLE
    required, _ = growth.RESULT_REQUIREMENTS[growth.GOVERNED_METRICS[0]]
    assert set(entry.missing) == set(required)


def test_a_family_missing_one_conjunctive_input_publishes_nothing() -> None:
    """Every growth metric decomposes from the same three inputs.

    Two of three resolved is not two thirds of an analysis: `_periods` returns
    `None` without the units trend and the whole section refuses. `missing`
    still names the gap, which is what a customer acts on.
    """
    mapping = _mapping(
        **{SEMANTIC_TRANSACTION_DATE: STATE_MAPPED, SEMANTIC_REVENUE: STATE_MAPPED}
    )

    entry = _for(definitions.availability(mapping), SECTION_GROWTH)

    assert entry.state == definitions.UNAVAILABLE
    assert entry.missing == (SEMANTIC_UNITS,)


def test_an_ambiguous_column_does_not_resolve_an_input() -> None:
    """`RRA-003` leaves a column stating no measure kind ambiguous.

    `facts._unavailable_reason` already draws this distinction: the data is
    present and its *label* falls short. Treating ambiguous as resolved would
    promise an analysis that refuses the moment it runs, which is the false
    promise an availability contract exists to prevent.
    """
    mapping = _mapping(
        **{
            SEMANTIC_TRANSACTION_DATE: STATE_MAPPED,
            SEMANTIC_REVENUE: STATE_MAPPED,
            SEMANTIC_UNITS: STATE_AMBIGUOUS,
        }
    )

    entry = _for(definitions.availability(mapping), SECTION_GROWTH)

    # `unavailable`, not `partial`: every growth metric decomposes from the same
    # three inputs, so an unresolved units column leaves the family publishing
    # nothing. What this test fixes is that the column is *not counted as
    # resolved* -- the state follows from that.
    assert entry.state == definitions.UNAVAILABLE
    assert entry.missing == (SEMANTIC_UNITS,)


def test_availability_covers_every_governed_family() -> None:
    """One entry per analysis, so a surface can render them without a second list."""
    report = definitions.availability(_mapping())

    assert {entry.section for entry in report} == {
        SECTION_COMPARISON,
        SECTION_CONCENTRATION,
        SECTION_GROWTH,
        SECTION_BASKET,
    }


def test_a_family_needing_one_of_two_dimensions_resolves_on_either() -> None:
    """`concentration` distributes over products *or* categories.

    Either dimension supports it, so requiring both would report an analysis
    unavailable that the calculation would in fact publish.
    """
    products = _mapping(
        **{SEMANTIC_REVENUE: STATE_MAPPED, SEMANTIC_PRODUCT: STATE_MAPPED}
    )
    categories = _mapping(
        **{SEMANTIC_REVENUE: STATE_MAPPED, SEMANTIC_CATEGORY: STATE_MAPPED}
    )

    assert _for(definitions.availability(products), SECTION_CONCENTRATION).state == (
        definitions.AVAILABLE
    )
    assert _for(definitions.availability(categories), SECTION_CONCENTRATION).state == (
        definitions.AVAILABLE
    )


def test_the_contract_states_no_score() -> None:
    """`RRA-011`:188-192 excludes an invented measure of how good a result is."""
    fields = {f.name for f in dataclasses.fields(definitions.CapabilityAvailability)}
    forbidden = {
        "score",
        "confidence",
        "quality",
        "completeness",
        "percentage",
        "ratio",
        "likelihood",
    }

    assert not (fields & forbidden)


def test_each_family_declares_the_inputs_availability_reads() -> None:
    """No second truth: the requirement is read from the family that has it.

    `RRA-011` requires a slice to *reduce* the repository's hand-maintained code
    lists. Restating each family's inputs here would add one, and it would go
    stale the first time a family changed what it needs -- silently, because a
    list agreeing with itself always passes.
    """
    for family in (comparison, growth, basket, concentration):
        assert family.RESULT_REQUIREMENTS
        assert set(family.RESULT_REQUIREMENTS) == set(family.GOVERNED_METRICS)
        for required, alternatives in family.RESULT_REQUIREMENTS.values():
            assert set(required) | set(alternatives) <= set(_ALL_SEMANTICS)


def test_an_unknown_section_has_no_availability_to_report() -> None:
    """Fail closed, as every other catalog lookup does."""
    with pytest.raises(definitions.UnknownCode):
        definitions.availability_for(_mapping(), "sectionn")


def test_a_family_needing_a_dimension_is_not_available_without_one() -> None:
    """Revenue alone does not support a distribution.

    The positive case above -- either dimension resolves it -- passes just as
    well when the dimension requirement is dropped altogether, because removing
    a constraint never breaks a case that met it. This is the case that fails
    when it is dropped, and it is the one a customer feels: a curve reported
    available with nothing to distribute over.
    """
    entry = _for(
        definitions.availability(_mapping(**{SEMANTIC_REVENUE: STATE_MAPPED})),
        SECTION_CONCENTRATION,
    )

    assert entry.state != definitions.AVAILABLE
    # The whole group, not one of them chosen by tuple order: a customer who
    # could satisfy this with either needs to be told both, and naming only
    # `product` would conceal that a category alone would do.
    assert set(entry.missing) == set(concentration.GOVERNED_DIMENSIONS)


def test_basket_without_a_dimension_is_partial_rather_than_available() -> None:
    """Items per transaction publishes; the attach rate does not.

    `basket` states two metrics over different requirements. Items per
    transaction needs units and a transaction identifier. The attach rate needs
    a governed dimension, and `_refusals` emits `dimension_absent` without one --
    its comment: *"no governed dimension was mapped at all -- there is nothing to
    state a rate over"*.

    So a mapping carrying units and a transaction id but no product or category
    supports half this family. Reporting it available would promise the customer
    an attach rate the analysis is already committed to refusing, which is the
    false promise this contract exists to prevent.
    """
    mapping = _mapping(
        **{SEMANTIC_UNITS: STATE_MAPPED, SEMANTIC_TRANSACTION_ID: STATE_MAPPED}
    )

    entry = _for(definitions.availability(mapping), SECTION_BASKET)

    assert entry.state == definitions.PARTIAL
    assert set(entry.missing) == set(basket.GOVERNED_DIMENSIONS)


def test_basket_with_a_dimension_is_available() -> None:
    """Either governed dimension supports the attach rate, as `_found` selects."""
    for dimension in (SEMANTIC_PRODUCT, SEMANTIC_CATEGORY):
        mapping = _mapping(
            **{
                SEMANTIC_UNITS: STATE_MAPPED,
                SEMANTIC_TRANSACTION_ID: STATE_MAPPED,
                dimension: STATE_MAPPED,
            }
        )

        entry = _for(definitions.availability(mapping), SECTION_BASKET)

        assert entry.state == definitions.AVAILABLE, dimension
        assert entry.missing == ()


def test_a_family_with_governed_dimensions_declares_them_as_an_alternative() -> None:
    """The property that would have caught the basket gap before review.

    `basket` and `concentration` each state a metric over a governed dimension
    and refuse without one. Modelling that for concentration and not for basket
    is what made the preview promise an attach rate the analysis was already
    committed to refusing -- and no test noticed, because each family was only
    ever checked on its own terms.

    Asserted over the families rather than per family, so a fifth one declaring
    `GOVERNED_DIMENSIONS` fails here rather than shipping the same defect.
    """
    for family in (comparison, growth, basket, concentration):
        dimensions = getattr(family, "GOVERNED_DIMENSIONS", None)
        if dimensions is None:
            continue
        stated = {
            alternatives
            for _, alternatives in family.RESULT_REQUIREMENTS.values()
            if alternatives
        }
        assert stated == {dimensions}, family.__name__


def test_partial_means_a_result_is_publishable_not_an_input_is_present() -> None:
    """`growth` needs all three inputs for every metric it states.

    `_periods` returns `None` without the units trend, and all three growth
    metrics decompose from that pair, so a mapping with a date and revenue but
    no units publishes *nothing* -- the whole section refuses. Counting resolved
    inputs called that `partial`, which tells a customer some of the analysis
    survives when none of it does.

    `partial` is a claim about outcomes, not about inputs.
    """
    mapping = _mapping(
        **{SEMANTIC_TRANSACTION_DATE: STATE_MAPPED, SEMANTIC_REVENUE: STATE_MAPPED}
    )

    entry = _for(definitions.availability(mapping), SECTION_GROWTH)

    assert entry.state == definitions.UNAVAILABLE
    assert entry.missing == (SEMANTIC_UNITS,)


def test_a_family_publishing_nothing_is_unavailable_however_much_is_mapped() -> None:
    """`basket` on a transaction id alone states neither of its metrics.

    Items per transaction needs units beside the identifier; the attach rate
    needs a dimension as well. One input of four resolved is not a partial
    result, it is no result.
    """
    entry = _for(
        definitions.availability(_mapping(**{SEMANTIC_TRANSACTION_ID: STATE_MAPPED})),
        SECTION_BASKET,
    )

    assert entry.state == definitions.UNAVAILABLE


def test_partial_survives_where_one_metric_of_two_can_publish() -> None:
    """The case that is genuinely partial, kept distinct from the two above.

    `basket` states two metrics over *different* requirements: items per
    transaction on units and an identifier, the attach rate on those plus a
    dimension. Units and an identifier without a dimension publishes the first
    and refuses the second, which is what `partial` means.
    """
    mapping = _mapping(
        **{SEMANTIC_UNITS: STATE_MAPPED, SEMANTIC_TRANSACTION_ID: STATE_MAPPED}
    )

    entry = _for(definitions.availability(mapping), SECTION_BASKET)

    assert entry.state == definitions.PARTIAL
