"""The audit-only reconciliation bases `rra004.package.v3` retains.

`RRA-004` names twelve and says each records "population code, event count,
canonical transaction count when applicable, input digest, mapping version,
currency when applicable, precision, and a stable basis identity". These are
`V-package`'s RED cases for the basis type; the wiring that actually retains one
per package is proven against the builder separately.

**The identity rule is the one worth reading twice.** "Every derived fact cites
exactly one compatible basis or a documented set of bases with the same
population identity" is only enforceable if two bases over the same population
of the same input necessarily agree -- so the identity is derived, never
supplied, and these cases prove both halves: same inputs agree, any changed
defining field disagrees.
"""

from __future__ import annotations

import pytest

from khepri.rra.bases import (
    BASIS_DIMENSION_SALES_REVENUE,
    BASIS_FINANCIAL_REVENUE,
    BASIS_SALES_REVENUE,
    BASIS_SALES_UNITS,
    GOVERNED_BASES,
    BasisRefused,
    RetainedBasis,
    compatible,
    dimension_basis,
)
from khepri.rra.populations import (
    POPULATION_FINANCIAL_POSTED,
    POPULATION_SALES_POSTED,
)

_DIGEST = "a" * 64
_MAPPING = "rra003.mapping.v3"


def _basis(**overrides: object) -> RetainedBasis:
    fields: dict[str, object] = {
        "name": BASIS_SALES_REVENUE,
        "population": POPULATION_SALES_POSTED,
        "event_count": 12,
        "input_digest": _DIGEST,
        "mapping_version": _MAPPING,
        "precision": 2,
        "transaction_count": 8,
        "currency": "EGP",
    }
    fields.update(overrides)
    return RetainedBasis(**fields)  # type: ignore[arg-type]


#: The nine constant basis names, transcribed from `RRA-004`'s retained-bases
#: section rather than imported, so a rename in the module fails here instead of
#: silently redefining the vocabulary.
_SPECIFIED_BASES = {
    "financial_revenue_basis",
    "financial_units_basis",
    "sales_revenue_basis",
    "sales_units_basis",
    "sales_transaction_basis",
    "sales_revenue_units_basis",
    "sales_revenue_transaction_basis",
    "sales_units_transaction_basis",
    "financial_revenue_cost_basis",
}


def test_the_nine_constant_bases_are_exactly_what_the_specification_names() -> None:
    """Set equality, so neither a missing name nor an invented one passes."""
    assert GOVERNED_BASES == _SPECIFIED_BASES


def test_a_dimension_basis_carries_its_dimension() -> None:
    """`RRA-004` writes it `dimension_sales_revenue_basis:<dimension>`."""
    assert (
        dimension_basis(BASIS_DIMENSION_SALES_REVENUE, "product")
        == "dimension_sales_revenue_basis:product"
    )


def test_a_basis_records_every_field_the_specification_lists() -> None:
    document = _basis().as_document()

    assert set(document) == {
        "name",
        "population",
        "event_count",
        "transaction_count",
        "input_digest",
        "mapping_version",
        "currency",
        "precision",
        "identity",
    }


def test_two_bases_over_the_same_population_share_an_identity() -> None:
    """The property the citation rule rests on."""
    assert _basis().identity == _basis().identity


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("population", POPULATION_FINANCIAL_POSTED),
        ("event_count", 13),
        ("transaction_count", 9),
        ("input_digest", "b" * 64),
        ("mapping_version", "rra003.mapping.v2"),
        ("currency", "SAR"),
        ("precision", 4),
        ("name", BASIS_FINANCIAL_REVENUE),
    ],
)
def test_changing_any_defining_field_changes_the_identity(
    field: str,
    value: object,
) -> None:
    """Otherwise two different bases could be cited interchangeably."""
    assert _basis(**{field: value}).identity != _basis().identity


def test_a_basis_citing_no_governed_population_is_refused() -> None:
    """Fail closed. A basis is evidence, and evidence about an unnamed
    population is not checkable against the specification."""
    with pytest.raises(BasisRefused):
        _basis(population="whatever_rows_were_lying_around")


def test_an_absent_transaction_count_is_not_zero() -> None:
    """`RRA-004` says "when applicable".

    Zero would state that the basis counted transactions and found none, which
    is a different claim from having no transaction identity to count.
    """
    absent = _basis(transaction_count=None)
    counted_none = _basis(transaction_count=0)

    assert absent.transaction_count is None
    assert counted_none.transaction_count == 0
    assert absent.identity != counted_none.identity


def test_an_absent_currency_is_not_a_currency() -> None:
    """A count-only basis never depended on one currency being proven."""
    assert _basis(currency=None).currency is None
    assert _basis(currency=None).identity != _basis().identity


def test_a_negative_count_is_refused() -> None:
    with pytest.raises(BasisRefused):
        _basis(event_count=-1)
    with pytest.raises(BasisRefused):
        _basis(transaction_count=-1)


def test_two_bases_of_different_roles_over_one_population_are_compatible() -> None:
    """The pair a ratio needs.

    Revenue and units over `sales_posted` have different identities -- they are
    different bases -- but a fact dividing one by the other is computed over one
    population, which is what `compatible` has to admit.
    """
    revenue = _basis(name=BASIS_SALES_REVENUE)
    units = _basis(name=BASIS_SALES_UNITS, currency=None)

    assert revenue.identity != units.identity
    assert compatible(revenue, units)


def test_bases_over_different_populations_are_not_compatible() -> None:
    """The defect the whole population contract exists to prevent: a ratio whose
    numerator and denominator came from different sets of rows."""
    assert not compatible(
        _basis(population=POPULATION_SALES_POSTED),
        _basis(population=POPULATION_FINANCIAL_POSTED),
    )


def test_bases_from_different_inputs_are_not_compatible() -> None:
    assert not compatible(_basis(), _basis(input_digest="c" * 64))


def test_bases_under_different_mappings_are_not_compatible() -> None:
    """A corrected reading of the same bytes is a different admission."""
    assert not compatible(_basis(), _basis(mapping_version="rra003.mapping.v2"))


def test_bases_counting_different_events_are_not_compatible() -> None:
    """Same population name over a different number of rows is not one
    population; one of them is incomplete."""
    assert not compatible(_basis(), _basis(event_count=11))


# --- the shape `rra004.package.v3` stores -----------------------------------


def test_a_stored_package_missing_a_v3_field_is_refused_not_defaulted() -> None:
    """`rebuild_fact_package` promises this in its own docstring: "a governed
    field that is absent is refused instead of defaulted".

    The fields carry dataclass defaults so the shape could land before every
    producer filled it. A default is a convenience for *construction*; on
    *read* it would silently turn a truncated document into a package claiming
    no currency, no coverage and no bases -- which is a different package that
    would digest differently from the one that was stored.

    Driven through the real reader over a real document, so it fails if the
    enumeration in `package_source` stops listing a field.
    """
    from khepri.rra.package_source import PackageCorrupted, rebuild_fact_package

    complete = _package().as_document()
    assert rebuild_fact_package(complete).digest == _package().digest

    for field in (
        "currency",
        "event_kind_filters",
        "status_filters",
        "coverage_manifest_identity",
        "coverage_signatures",
        "daily_bases",
        "retained_bases",
    ):
        truncated = {name: value for name, value in complete.items() if name != field}
        with pytest.raises(PackageCorrupted):
            rebuild_fact_package(truncated)


def test_a_retained_basis_survives_the_package_round_trip() -> None:
    """The basis a fact cites must come back identical, or the citation names
    evidence that no longer exists."""
    from khepri.rra.package_source import rebuild_fact_package

    package = _package(retained_bases=(_basis(),))

    rebuilt = rebuild_fact_package(package.as_document())

    assert rebuilt.retained_bases == package.retained_bases
    assert rebuilt.retained_bases[0].identity == _basis().identity
    assert rebuilt.digest == package.digest


def _package(**overrides: object):
    """One minimal package carrying the v3 provenance fields."""
    from khepri.rra.facts import FactPackage

    fields: dict[str, object] = {
        "package_version": "rra004.package.v2",
        "formula_version": "rra004.formula.v1",
        "mapping_version": _MAPPING,
        "profile_digest": "d" * 64,
        "source_sha256_hex": _DIGEST,
        "row_count": 3,
        "monetary_precision": 2,
        "facts": (),
        "series": (),
        "comparisons": (),
        "refusals": (),
        "caveats": (),
        "currency": "EGP",
        "event_kind_filters": ("sale",),
        "status_filters": ("posted",),
    }
    fields.update(overrides)
    return FactPackage(**fields)  # type: ignore[arg-type]
