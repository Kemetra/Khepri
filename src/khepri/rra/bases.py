"""The reconciliation bases a package retains as audit evidence.

`RRA-004`'s "Retained audit-only reconciliation bases" names twelve, and is
explicit about what they are for: "never as additional customer KPIs". A basis
is the evidence that a published figure was computed over the population it
claims, so that a reader auditing the package can reconcile the figure against
the rows rather than take the number on trust.

**Every basis records the same eight things**, per the same section: "population
code, event count, canonical transaction count when applicable, input digest,
mapping version, currency when applicable, precision, and a stable basis
identity". Grouped into one type rather than eight parallel arguments, because a
basis missing any of them cannot be reconciled and would be evidence in name
only.

**The identity is derived, not supplied.** `RRA-004` requires "a stable basis
identity" and says "every derived fact cites exactly one compatible basis or a
documented set of bases with the same population identity". An identity a caller
chose could differ between two bases that are in fact the same population, which
would make that citation rule unenforceable. So it is a digest over the fields
that define the basis, and two bases over the same population of the same input
under the same mapping necessarily share it.

**`None` is not zero.** A canonical transaction count is absent when no
transaction identity is mapped, and a currency is absent for a count-only basis.
`RRA-004` writes both as "when applicable". Recording zero instead would state
that the basis counted transactions and found none, which is a different and
false claim.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from khepri.rra.populations import is_governed_population
from khepri.rra.profiling import canonical_json

#: The twelve basis names `RRA-004` retains. A name is a role -- what the basis
#: is evidence *for* -- and is distinct from the population code, which says
#: which rows it covers. `financial_revenue_basis` and `financial_units_basis`
#: share the population `financial_posted` and are two different bases.
BASIS_FINANCIAL_REVENUE = "financial_revenue_basis"
BASIS_FINANCIAL_UNITS = "financial_units_basis"
BASIS_SALES_REVENUE = "sales_revenue_basis"
BASIS_SALES_UNITS = "sales_units_basis"
BASIS_SALES_TRANSACTION = "sales_transaction_basis"
BASIS_SALES_REVENUE_UNITS = "sales_revenue_units_basis"
BASIS_SALES_REVENUE_TRANSACTION = "sales_revenue_transaction_basis"
BASIS_SALES_UNITS_TRANSACTION = "sales_units_transaction_basis"
BASIS_FINANCIAL_REVENUE_COST = "financial_revenue_cost_basis"

#: Two of the twelve are families over a dimension rather than constants,
#: written `dimension_sales_revenue_basis:<dimension>` and
#: `dimension_transaction_basis:<dimension>`.
BASIS_DIMENSION_SALES_REVENUE = "dimension_sales_revenue_basis"
BASIS_DIMENSION_TRANSACTION = "dimension_transaction_basis"

#: The separator the specification uses in both family names.
BASIS_DIMENSION_SEPARATOR = ":"

#: Every basis name that is a constant. The two dimension families and the
#: aligned daily bases are admitted by their own rules.
GOVERNED_BASES: frozenset[str] = frozenset(
    {
        BASIS_FINANCIAL_REVENUE,
        BASIS_FINANCIAL_UNITS,
        BASIS_SALES_REVENUE,
        BASIS_SALES_UNITS,
        BASIS_SALES_TRANSACTION,
        BASIS_SALES_REVENUE_UNITS,
        BASIS_SALES_REVENUE_TRANSACTION,
        BASIS_SALES_UNITS_TRANSACTION,
        BASIS_FINANCIAL_REVENUE_COST,
    }
)


class BasisRefused(ValueError):
    """A basis that could not be retained completely.

    `RRA-004`: "Failure to retain one basis completely refuses only dependent
    facts." So this refuses the basis, and the caller refuses the facts citing
    it -- never the package.
    """


def dimension_basis(name: str, dimension: str) -> str:
    """One member of a dimension basis family, spelled once."""
    return f"{name}{BASIS_DIMENSION_SEPARATOR}{dimension}"


@dataclass(frozen=True, slots=True)
class RetainedBasis:
    """One reconciliation basis and everything needed to reconcile against it.

    Frozen because a basis is evidence about a package that is itself immutable:
    a basis a later step could edit would prove nothing about the figures that
    already cited it.
    """

    name: str
    population: str
    event_count: int
    input_digest: str
    mapping_version: str
    precision: int
    #: `None` where no transaction identity is mapped -- see the module note on
    #: why this is not zero.
    transaction_count: int | None = None
    #: `None` for a count-only basis, which never depended on one currency.
    currency: str | None = None

    def __post_init__(self) -> None:
        if not is_governed_population(self.population):
            raise BasisRefused(
                f"A retained basis cannot cite {self.population!r}, "
                "which names no governed population."
            )
        if self.event_count < 0:
            raise BasisRefused("A retained basis cannot count fewer than no events.")
        if self.transaction_count is not None and self.transaction_count < 0:
            raise BasisRefused(
                "A retained basis cannot count fewer than no transactions."
            )

    @property
    def identity(self) -> str:
        """The stable identity `RRA-004` requires, derived from the basis itself.

        Over the *defining* fields only. Two bases retained from one input under
        one mapping over one population, counting the same events, are the same
        basis and must share an identity -- that is the property the "cites
        exactly one compatible basis" rule is checked against.
        """
        return hashlib.sha256(
            canonical_json(
                {
                    "name": self.name,
                    "population": self.population,
                    "event_count": self.event_count,
                    "transaction_count": self.transaction_count,
                    "input_digest": self.input_digest,
                    "mapping_version": self.mapping_version,
                    "currency": self.currency,
                    "precision": self.precision,
                }
            ).encode()
        ).hexdigest()

    def as_document(self) -> dict[str, object]:
        """The canonical shape a stored package records this basis in."""
        return {
            "name": self.name,
            "population": self.population,
            "event_count": self.event_count,
            "transaction_count": self.transaction_count,
            "input_digest": self.input_digest,
            "mapping_version": self.mapping_version,
            "currency": self.currency,
            "precision": self.precision,
            "identity": self.identity,
        }


def compatible(left: RetainedBasis, right: RetainedBasis) -> bool:
    """Whether two bases share one population identity.

    `RRA-004` lets a derived fact cite "a documented set of bases with the same
    population identity", so this is the check that admits such a set. Compared
    on the population and its binding rather than on `identity`, because two
    bases of *different roles* over the same population -- revenue and units
    over `sales_posted` -- are exactly the compatible pair a ratio needs, and
    their identities differ by name.
    """
    return (
        left.population == right.population
        and left.input_digest == right.input_digest
        and left.mapping_version == right.mapping_version
        and left.event_count == right.event_count
    )


def retain_bases(
    *,
    events: tuple[object, ...],
    input_digest: str,
    mapping_version: str,
    currency: str | None,
    precision: int,
) -> tuple[RetainedBasis, ...]:
    """The reconciliation bases derivable from one admitted event set.

    `RRA-004` requires the package to retain these as audit evidence, and
    requires every derived fact to cite "exactly one compatible basis or a
    documented set of bases with the same population identity". A package
    retaining none would leave every derived fact citing nothing, so these are
    produced wherever the events allow rather than being optional.

    **Counts, not values.** A basis records "population code, event count,
    canonical transaction count when applicable" and the bindings -- it is the
    evidence a figure can be reconciled *against*, not a second copy of the
    figure. The totals themselves stay on the facts.

    **The nine constant bases only.** The two `dimension_*` families need the
    per-value transaction membership sets that `aggregates` collapses to a
    count, and the aligned daily bases are retained separately by
    `daily_bases`. Both are recorded on the package by their own producers.
    """
    from khepri.rra.populations import (
        POPULATION_FINANCIAL_COMPLETE_REVENUE_COST,
        POPULATION_FINANCIAL_POSTED,
        POPULATION_SALES_COMPLETE_REVENUE_TRANSACTIONS,
        POPULATION_SALES_COMPLETE_REVENUE_UNITS,
        POPULATION_SALES_COMPLETE_TRANSACTIONS,
        POPULATION_SALES_COMPLETE_UNITS_TRANSACTIONS,
        POPULATION_SALES_POSTED,
    )

    sales = tuple(event for event in events if getattr(event, "event_kind", "") == "sale")
    keys = {
        getattr(event, "transaction_key", None)
        for event in sales
        if getattr(event, "transaction_key", None) is not None
    }
    sale_keys = len(keys) if keys else None

    def _basis(
        name: str,
        population: str,
        count: int,
        *,
        transactions: int | None = None,
        monetary: bool = True,
    ) -> RetainedBasis:
        return RetainedBasis(
            name=name,
            population=population,
            event_count=count,
            input_digest=input_digest,
            mapping_version=mapping_version,
            precision=precision,
            transaction_count=transactions,
            currency=currency if monetary else None,
        )

    return (
        _basis(BASIS_FINANCIAL_REVENUE, POPULATION_FINANCIAL_POSTED, len(events)),
        _basis(
            BASIS_FINANCIAL_UNITS,
            POPULATION_FINANCIAL_POSTED,
            len(events),
            monetary=False,
        ),
        _basis(BASIS_SALES_REVENUE, POPULATION_SALES_POSTED, len(sales)),
        _basis(
            BASIS_SALES_UNITS, POPULATION_SALES_POSTED, len(sales), monetary=False
        ),
        _basis(
            BASIS_SALES_TRANSACTION,
            POPULATION_SALES_COMPLETE_TRANSACTIONS,
            len(sales),
            transactions=sale_keys,
            monetary=False,
        ),
        _basis(
            BASIS_SALES_REVENUE_UNITS,
            POPULATION_SALES_COMPLETE_REVENUE_UNITS,
            len(sales),
        ),
        _basis(
            BASIS_SALES_REVENUE_TRANSACTION,
            POPULATION_SALES_COMPLETE_REVENUE_TRANSACTIONS,
            len(sales),
            transactions=sale_keys,
        ),
        _basis(
            BASIS_SALES_UNITS_TRANSACTION,
            POPULATION_SALES_COMPLETE_UNITS_TRANSACTIONS,
            len(sales),
            transactions=sale_keys,
            monetary=False,
        ),
        _basis(
            BASIS_FINANCIAL_REVENUE_COST,
            POPULATION_FINANCIAL_COMPLETE_REVENUE_COST,
            len(events),
        ),
    )
