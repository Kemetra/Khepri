"""Which rows a figure was computed over, said in a name a reader can check.

`RRA-004` requires every fact to record "one of these readable population codes
in provenance" and states plainly that "an identity hash alone is insufficient".
Before `rra004.package.v3` the package recorded neither: `facts._matched` built
the AOV, ASP and gross-margin row-intersections and returned only their values
and a `partial` flag, so the population each figure was computed over existed
for the length of one call and was then unrecoverable.

**Codes, not predicates.** A population is named by the specification, and this
module spells those names once so a caller cites one rather than describing it.
Two figures claiming the same population must be comparable, and that is only
checkable if both say which population they mean in the same words.

**A dimension population carries its dimension.** `RRA-004` writes the last one
as `dimension_complete_sales:<dimension>`, so the code is a family rather than a
constant, and `dimension_complete_sales` alone names no population.
"""

from __future__ import annotations

#: Posted sale and return events, excluding void and cancelled rows.
POPULATION_FINANCIAL_POSTED = "financial_posted"
#: Posted sale events only.
POPULATION_SALES_POSTED = "sales_posted"
#: `sales_posted` with complete revenue.
POPULATION_SALES_COMPLETE_REVENUE = "sales_complete_revenue"
#: `sales_posted` with complete strictly positive units.
POPULATION_SALES_COMPLETE_UNITS = "sales_complete_units"
#: `sales_posted` with complete revenue, strictly positive units, and no
#: unmatched eligible row.
POPULATION_SALES_COMPLETE_REVENUE_UNITS = "sales_complete_revenue_units"
#: `sales_posted` with complete canonical transaction keys.
POPULATION_SALES_COMPLETE_TRANSACTIONS = "sales_complete_transactions"
#: `sales_posted` with complete revenue and canonical transaction keys.
POPULATION_SALES_COMPLETE_REVENUE_TRANSACTIONS = "sales_complete_revenue_transactions"
#: `sales_posted` with complete strictly positive units and canonical
#: transaction keys.
POPULATION_SALES_COMPLETE_UNITS_TRANSACTIONS = "sales_complete_units_transactions"
#: Financial rows with complete revenue and extended cost.
POPULATION_FINANCIAL_COMPLETE_REVENUE_COST = "financial_complete_revenue_cost"

#: The prefix of the dimension population family. Never a population by itself.
POPULATION_DIMENSION_COMPLETE_SALES = "dimension_complete_sales"

#: How a dimension is joined to its population family. The same separator the
#: specification uses when it writes `dimension_complete_sales:<dimension>`.
POPULATION_DIMENSION_SEPARATOR = ":"


def dimension_population(dimension: str) -> str:
    """The population code for sale rows complete in one governed dimension.

    Spelled here rather than at each call site so every caller produces the same
    string: a code assembled two ways is two codes, and the compatibility rule
    that two figures share a population would silently stop holding.
    """
    return f"{POPULATION_DIMENSION_COMPLETE_SALES}{POPULATION_DIMENSION_SEPARATOR}{dimension}"


#: Every population code that is a constant rather than a family. Used to prove
#: a recorded code is one the specification names, so a typo refuses instead of
#: travelling into provenance as an unrecognized population.
GOVERNED_POPULATIONS: frozenset[str] = frozenset(
    {
        POPULATION_FINANCIAL_POSTED,
        POPULATION_SALES_POSTED,
        POPULATION_SALES_COMPLETE_REVENUE,
        POPULATION_SALES_COMPLETE_UNITS,
        POPULATION_SALES_COMPLETE_REVENUE_UNITS,
        POPULATION_SALES_COMPLETE_TRANSACTIONS,
        POPULATION_SALES_COMPLETE_REVENUE_TRANSACTIONS,
        POPULATION_SALES_COMPLETE_UNITS_TRANSACTIONS,
        POPULATION_FINANCIAL_COMPLETE_REVENUE_COST,
    }
)


def is_governed_population(code: str) -> bool:
    """Whether this code names a population `RRA-004` defines.

    A dimension population is admitted by its family prefix and a non-empty
    dimension, because the specification defines the family rather than each
    member: the admissible dimensions are whichever the mapping resolved.
    """
    if code in GOVERNED_POPULATIONS:
        return True
    prefix = f"{POPULATION_DIMENSION_COMPLETE_SALES}{POPULATION_DIMENSION_SEPARATOR}"
    # `.strip()` because `"dimension_complete_sales: "` is truthy while naming
    # no dimension: a `RetainedBasis` could then cite a population whose member
    # is whitespace, which reconciles against nothing.
    return code.startswith(prefix) and bool(code[len(prefix) :].strip())
