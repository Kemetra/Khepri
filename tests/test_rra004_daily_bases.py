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
# --- the producer: a package retains what RRA-004:120 requires -------------

_PRODUCER_SCOPE = "all-stores"
_PRODUCER_DAYS = (date(2026, 1, 5), date(2026, 1, 6), date(2026, 1, 7))
#: Two days carrying a sale and a third the operator attested with no row on
#: it -- the "attested zero-activity day" `RRA-004` names.
_PRODUCER_CSV = (
    b"date,revenue,units,invoice_no\n"
    b"2026-01-05,100.00,4,INV-1\n"
    b"2026-01-06,200.00,6,INV-2\n"
)


def _producer_package(attested: bool):
    """A package through the real pipeline, with or without an attestation."""
    import hashlib

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.facts import AdmittedInput, build_fact_package
    from khepri.rra.intake import CSV_MEDIA_TYPE
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile
    from tests.rra003_contract_fixtures import (
        TEST_CONTRACT,
        attesting_manifest,
        published_mapping_identity,
    )

    profile = build_profile(
        content=_PRODUCER_CSV,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(_PRODUCER_CSV).hexdigest(),
    )
    manifest = (
        attesting_manifest(
            content=_PRODUCER_CSV,
            contract=TEST_CONTRACT,
            days=_PRODUCER_DAYS,
            scope=_PRODUCER_SCOPE,
        )
        if attested
        else None
    )
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                manifest=manifest,
                content=_PRODUCER_CSV,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
        )


def test_an_attested_package_retains_its_aligned_daily_bases() -> None:
    """`RRA-004:120` requires the package to retain "aligned daily revenue and
    unit bases bound to each accepted comparison window".

    The type, its serialization and its readback all existed, and
    `FactPackage.daily_bases` defaulted to `()` -- **nothing ever populated
    it**. No family read it, so no published figure was wrong; it was an unmet
    retention obligation, and the partial-window selection `RRA-004:141`
    describes cannot be built without it.

    Retained per attested scope over the window the signature covers, and
    including "attested zero-activity days", which come from the manifest and
    rather than from the data: a day with no row is covered when the operator
    attested it and simply absent when they did not.
    """
    package = _producer_package(attested=True)

    assert package.daily_bases, (
        "RRA-004 requires the aligned daily bases and the package retains none"
    )
    basis = package.daily_bases[0]
    assert basis.scope == _PRODUCER_SCOPE
    assert basis.start == _PRODUCER_DAYS[0]
    assert basis.end == _PRODUCER_DAYS[-1]
    assert [value.day for value in basis.values] == list(_PRODUCER_DAYS)

    stated = {value.day: value.revenue for value in basis.values}
    assert stated[_PRODUCER_DAYS[0]] == Decimal("100.00")
    assert stated[_PRODUCER_DAYS[1]] == Decimal("200.00")
    assert stated[_PRODUCER_DAYS[2]] == Decimal(0), (
        "an attested day carrying no row is a proven quiet day and states zero; "
        "`None` is for a measure the package does not have at all"
    )


def test_a_package_with_no_attestation_retains_no_daily_basis() -> None:
    """A daily basis is coverage evidence, so an unattested package has none.

    Pinned beside the case above so a producer that simply always emits one
    fails here: `RRA-004` says observed bounds "are evidence but are not
    coverage-manifest completeness proof", and a basis derived from the rows
    alone would be exactly that.
    """
    assert _producer_package(attested=False).daily_bases == ()
def test_no_daily_basis_is_retained_for_an_unattested_population() -> None:
    """A basis is coverage evidence, so it answers to the same gate as a signature.

    With a manifest attesting `sale` over an extract the package admitted returns
    from, `_signatures_of` correctly refused to sign -- and `_daily_bases_of`
    still stored `financial_posted` values labelled with both admitted kinds.
    That presented an unattested population as retained coverage evidence, which
    a later reconciliation or prefix projection would consume. Found in review.
    """
    import hashlib

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.coverage import (
        ManifestBinding,
        ManifestExceptions,
        ManifestWindow,
        build_coverage_manifest,
    )
    from khepri.rra.facts import AdmittedInput, build_fact_package
    from khepri.rra.intake import CSV_MEDIA_TYPE
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile
    from tests.rra003_contract_fixtures import (
        oracle_contract,
        published_mapping_identity,
    )

    days = (date(2026, 2, 1), date(2026, 2, 2), date(2026, 2, 3))
    content = (
        b"date,event_kind,revenue,units,invoice_no\n"
        b"2026-02-01,sale,400.00,10,INV-1\n"
        b"2026-02-02,sale,600.00,15,INV-2\n"
        b"2026-02-03,return,-90.00,-2,INV-3\n"
    )
    contract = oracle_contract(status_column=None)
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    manifest = build_coverage_manifest(
        binding=ManifestBinding(
            input_digest=profile.source_sha256_hex,
            source_contract_digest=contract.digest,
            timezone="Africa/Cairo",
            attested_by="Test fixture: operator attestation.",
        ),
        window=ManifestWindow(
            covered_start=days[0],
            covered_end=days[-1],
            aggregate_scope="all-stores",
            store_roster=(),
            covered_pairs=tuple(("all-stores", day) for day in days),
        ),
        exceptions=ManifestExceptions(
            closures=(),
            extraction_gaps=(),
            partial_terminal_boundary=None,
            # Sales only, while the package admits a return.
            event_kinds=("sale",),
            statuses=("posted",),
        ),
    )
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=contract)
        package = build_fact_package(
            AdmittedInput(
                manifest=manifest,
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=contract,
            ),
        )

    # The premise: the attestation really does not cover what was admitted.
    assert package.event_kind_filters == ("return", "sale")
    assert not package.coverage_signatures

    assert package.daily_bases == (), (
        'a daily basis was retained over a population the manifest does not attest'
    )
