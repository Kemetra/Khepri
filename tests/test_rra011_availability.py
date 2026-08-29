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
    assert set(entry.missing) == set(growth.REQUIRED_INPUTS)


def test_a_family_missing_one_input_is_partial_and_names_it() -> None:
    """"Margin: Unavailable -- cost basis not established" needs the *which*.

    A bare state tells a customer an analysis will not run and not what to fix.
    `missing` names the unresolved semantics, which is the actionable half.
    """
    mapping = _mapping(
        **{SEMANTIC_TRANSACTION_DATE: STATE_MAPPED, SEMANTIC_REVENUE: STATE_MAPPED}
    )

    entry = _for(definitions.availability(mapping), SECTION_GROWTH)

    assert entry.state == definitions.PARTIAL
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

    assert entry.state == definitions.PARTIAL
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
        assert family.REQUIRED_INPUTS
        assert set(family.REQUIRED_INPUTS) <= set(_ALL_SEMANTICS)


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
    assert entry.missing
    # One name, not every dimension the customer could have supplied: listing
    # both reads as though both were required.
    assert set(entry.missing) <= set(concentration.ALTERNATIVE_INPUTS)
    assert len(entry.missing) == 1
