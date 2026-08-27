"""The readable population codes `rra004.package.v3` records in provenance.

`RRA-004` lists ten population codes and says an identity hash alone is
insufficient, which is a requirement about *readability*: a figure must say
which rows it was computed over in words a reader can check against the
specification, not a digest they can only compare for equality.

These cases are `V-package`'s RED for the vocabulary itself. The bases that
cite these codes, and the facts that cite those bases, are proven separately --
a code nothing records would pass every test here while provenance stayed empty.
"""

from __future__ import annotations

import pytest

from khepri.rra.populations import (
    GOVERNED_POPULATIONS,
    POPULATION_FINANCIAL_POSTED,
    POPULATION_SALES_COMPLETE_REVENUE_TRANSACTIONS,
    POPULATION_SALES_POSTED,
    dimension_population,
    is_governed_population,
)

#: Every code `RRA-004`'s population contract names as a constant, transcribed
#: from the specification rather than imported, so a rename in the module fails
#: here instead of silently redefining the vocabulary.
_SPECIFIED = {
    "financial_posted",
    "sales_posted",
    "sales_complete_revenue",
    "sales_complete_units",
    "sales_complete_revenue_units",
    "sales_complete_transactions",
    "sales_complete_revenue_transactions",
    "sales_complete_units_transactions",
    "financial_complete_revenue_cost",
}


def test_the_vocabulary_is_exactly_what_the_specification_names() -> None:
    """Set equality, so neither a missing code nor an invented one passes."""
    assert GOVERNED_POPULATIONS == _SPECIFIED


def test_a_dimension_population_carries_the_dimension_it_is_complete_in() -> None:
    """`RRA-004` writes it `dimension_complete_sales:<dimension>`."""
    assert dimension_population("product") == "dimension_complete_sales:product"
    assert dimension_population("category") == "dimension_complete_sales:category"


def test_two_dimensions_are_two_populations() -> None:
    """The property the compatibility rule rests on.

    Facts over product and over category are not comparable, and they are only
    distinguishable later if the code said which dimension it meant.
    """
    assert dimension_population("product") != dimension_population("category")


def test_the_bare_family_prefix_names_no_population() -> None:
    """A dimension population without its dimension identifies nothing.

    Admitting it would let a fact claim completeness in *some* dimension, which
    is not a claim a reader can check.
    """
    assert not is_governed_population("dimension_complete_sales")
    assert not is_governed_population("dimension_complete_sales:")


@pytest.mark.parametrize("code", sorted(_SPECIFIED))
def test_every_specified_code_is_recognised(code: str) -> None:
    assert is_governed_population(code)


def test_a_dimension_population_is_recognised() -> None:
    assert is_governed_population(dimension_population("store"))


@pytest.mark.parametrize(
    "code",
    [
        "sales_complete",
        "financial",
        "sales_complete_revenue_unit",
        "SALES_POSTED",
        "",
    ],
)
def test_a_code_the_specification_does_not_name_is_refused(code: str) -> None:
    """Fail closed: an unrecognised code is not a population.

    A typo recorded as provenance would travel with the figure and read as a
    population nobody defined, which is worse than no code at all -- it looks
    like an answer.
    """
    assert not is_governed_population(code)


def test_the_two_base_populations_are_distinct() -> None:
    """`financial_posted` includes returns; `sales_posted` does not.

    This is the distinction every ratio in `RRA-004` turns on, so a module that
    collapsed them would make AOV and headline revenue claim one population.
    """
    assert POPULATION_FINANCIAL_POSTED != POPULATION_SALES_POSTED
    assert POPULATION_SALES_COMPLETE_REVENUE_TRANSACTIONS != POPULATION_SALES_POSTED


def test_a_dimension_population_needs_a_dimension_not_whitespace() -> None:
    """`"dimension_complete_sales: "` is truthy and names nothing.

    Found in review. The family is admitted by its prefix plus a non-empty
    member, and a whitespace member satisfied that while leaving a
    `RetainedBasis` citing a population that reconciles against nothing.
    """
    from khepri.rra.populations import (
        POPULATION_DIMENSION_COMPLETE_SALES,
        POPULATION_DIMENSION_SEPARATOR,
        is_governed_population,
    )

    prefix = f"{POPULATION_DIMENSION_COMPLETE_SALES}{POPULATION_DIMENSION_SEPARATOR}"
    assert is_governed_population(f"{prefix}product")
    for blank in ("", " ", "   "):
        assert not is_governed_population(prefix + blank), repr(blank)
