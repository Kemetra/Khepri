"""The aligned daily bases `rra004.package.v3` retains.

`RRA-004` requires them "separately from the structural signature", recording
"exact start and end dates, store or aggregate scope, event and status filters,
population identity, currency and precision where applicable, and daily revenue
and unit values, including attested zero-activity days".

The separation is the design: a structural signature carries no measure and no
absolute date, so two windows can be compared for shape without their values
entering that question; a daily basis carries both, so a published figure can be
reconciled against the days behind it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from khepri.rra.daily_bases import (
    AlignedDailyBasis,
    DailyBasisRefused,
    DailyValue,
)
from khepri.rra.populations import (
    POPULATION_FINANCIAL_POSTED,
    POPULATION_SALES_POSTED,
)

_START = date(2026, 4, 1)
_END = date(2026, 4, 3)


def _values(*amounts: str | None) -> tuple[DailyValue, ...]:
    return tuple(
        DailyValue(
            day=date.fromordinal(_START.toordinal() + offset),
            revenue=None if amount is None else Decimal(amount),
            units=None if amount is None else int(Decimal(amount) // 10),
        )
        for offset, amount in enumerate(amounts)
    )


def _basis(**overrides: object) -> AlignedDailyBasis:
    fields: dict[str, object] = {
        "scope": "all-stores",
        "start": _START,
        "end": _END,
        "population": POPULATION_FINANCIAL_POSTED,
        "event_kinds": ("sale", "return"),
        "statuses": ("posted",),
        "values": _values("100.00", "200.00", "300.00"),
        "precision": 2,
        "currency": "EGP",
    }
    fields.update(overrides)
    return AlignedDailyBasis(**fields)  # type: ignore[arg-type]


def test_a_basis_records_every_field_the_specification_lists() -> None:
    document = _basis().as_document()

    assert set(document) == {
        "scope",
        "start",
        "end",
        "population",
        "event_kinds",
        "statuses",
        "currency",
        "precision",
        "values",
    }


def test_the_basis_carries_its_absolute_dates() -> None:
    """The deliberate difference from a structural signature, which excludes
    them: this basis exists to be reconciled against real days."""
    document = _basis().as_document()

    assert document["start"] == "2026-04-01"
    assert document["values"][0]["day"] == "2026-04-01"  # type: ignore[index]


def test_an_attested_zero_activity_day_is_a_value_and_not_a_hole() -> None:
    """`RRA-003`: a closure "proves complete zero activity"; a gap does not.

    A closed day carries zero. A day nobody attested is simply absent. Collapsing
    the two would let missing data read as a quiet day, which is the error the
    whole coverage contract exists to prevent.
    """
    closed = _basis(values=_values("100.00", "0.00", "300.00"))
    unattested = _basis(values=(_values("100.00")[0], _values(None, None, "300.00")[2]))

    assert closed.values[1].revenue == Decimal("0.00")
    assert len(unattested.values) == 2
    assert closed.identity != unattested.identity


def test_two_bases_with_different_daily_values_are_different_evidence() -> None:
    """Unlike a structural signature, the values are inside the identity: this
    basis is what a figure reconciles against."""
    assert _basis().identity != _basis(values=_values("100.00", "200.00", "301.00")).identity


def test_two_identical_bases_share_an_identity() -> None:
    assert _basis().identity == _basis().identity


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("scope", "one-store"),
        ("population", POPULATION_SALES_POSTED),
        ("currency", "SAR"),
        ("precision", 4),
        ("event_kinds", ("sale",)),
        ("statuses", ("posted", "settled")),
    ],
)
def test_changing_any_defining_field_changes_the_identity(
    field: str,
    value: object,
) -> None:
    assert _basis(**{field: value}).identity != _basis().identity


def test_a_basis_citing_no_governed_population_is_refused() -> None:
    with pytest.raises(DailyBasisRefused):
        _basis(population="whatever_rows_were_lying_around")


def test_an_inverted_window_is_refused() -> None:
    with pytest.raises(DailyBasisRefused):
        _basis(start=_END, end=_START, values=())


def test_a_day_stated_twice_is_refused() -> None:
    """Two values for one day is not a basis anyone can reconcile against: it
    states two answers to the same question."""
    repeated = (*_values("100.00"), *_values("150.00"))

    with pytest.raises(DailyBasisRefused):
        _basis(values=repeated)


def test_a_day_outside_the_window_is_refused() -> None:
    """A basis bound to a window cannot carry evidence from outside it, or the
    figures citing it would reconcile against days the window never covered."""
    outside = (
        *_values("100.00"),
        DailyValue(day=date(2026, 5, 9), revenue=Decimal("50.00"), units=5),
    )

    with pytest.raises(DailyBasisRefused):
        _basis(values=outside)


# --- restriction, for prefix projections ------------------------------------


def test_a_restriction_selects_from_the_parent_rather_than_recomputing() -> None:
    """`RRA-004`: a projection "restricts the parent daily bases to that prefix"
    and "never ... changes a parent measure value"."""
    restricted = _basis().restricted_to(days=2)

    assert [value.revenue for value in restricted.values] == [
        Decimal("100.00"),
        Decimal("200.00"),
    ]
    assert restricted.end == date(2026, 4, 2)
    assert restricted.start == _START


def test_a_restriction_keeps_every_binding_of_its_parent() -> None:
    parent = _basis()

    restricted = parent.restricted_to(days=2)

    assert restricted.scope == parent.scope
    assert restricted.population == parent.population
    assert restricted.event_kinds == parent.event_kinds
    assert restricted.statuses == parent.statuses
    assert restricted.currency == parent.currency


def test_a_restriction_may_not_reach_past_its_parent() -> None:
    with pytest.raises(DailyBasisRefused):
        _basis().restricted_to(days=4)


def test_a_restriction_covers_at_least_one_day() -> None:
    """Isolated by its reason, because a downstream guard catches it too.

    With `days=0` the restricted end lands a day before the start, so
    `__post_init__`'s inverted-window check refuses it anyway -- and the whole
    zero-day guard could be deleted with this suite green. The two refusals are
    not interchangeable: an operator told a basis "ends before it starts" when
    they asked for zero days is told something about the data, not about the
    request.
    """
    with pytest.raises(DailyBasisRefused) as refused:
        _basis().restricted_to(days=0)

    assert "at least its first day" in str(refused.value).lower()


def test_a_restriction_is_different_evidence_from_its_parent() -> None:
    """It answers for a shorter window, so a figure citing one must not be
    reconcilable against the other."""
    parent = _basis()

    assert parent.restricted_to(days=2).identity != parent.identity
