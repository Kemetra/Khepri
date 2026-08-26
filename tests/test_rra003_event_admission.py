"""Which rows a governed calculation may use, and which it must refuse.

`RRA-003`'s normalized event contract requires every row used by a governed
calculation to carry a transaction date, an event kind of `sale` or `return`, a
status proving `posted`, and exactly one uppercase ISO 4217 currency for every
monetary measure. It then states what happens when one is missing:

> An unknown or missing event kind, status, currency, or required identity proof
> refuses every affected population rather than silently excluding rows.
> Explicitly void and cancelled events are excluded from every population.
> Missing, malformed, or mixed currency refuses monetary facts and their derived
> results but does not suppress independently proven count-only facts.

**Two different outcomes, and conflating them is the defect these cases guard.**
An *explicitly void* row is excluded — the extract said what it was and the
answer is computable without it. An *unknown* status is a refusal — the extract
did not say, so excluding the row would be a guess about what it meant, and the
population that guess feeds is no longer proven.

These are `V-mapping`'s RED cases for M3. At `739d474` none of this exists:
`mapping.py` carries no event-kind, status, or currency semantic, and `status`,
`void`, `cancel` and `currency` appear nowhere in `aggregates.py` or
`admissibility.py`. Mapping resolves columns to semantics and never filters
rows, so admission is its own module over profile plus contract.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from khepri.rra.source_contract import (
    BasisDeclaration,
    ContractAttribution,
    EventDeclaration,
    IdentityDeclaration,
    SourceContract,
    build_source_contract,
)

MIXED_CURRENCY_CSV = (
    b"date,invoice,event_kind,status,amount,qty,currency\n"
    b"2026-03-04,INV-1,sale,posted,100.00,2,EGP\n"
    b"2026-03-05,INV-2,sale,posted,200.00,4,USD\n"
)

VOID_AND_POSTED_CSV = (
    b"date,invoice,event_kind,status,amount,qty,currency\n"
    b"2026-03-04,INV-1,sale,posted,100.00,2,EGP\n"
    b"2026-03-05,INV-2,sale,void,999.00,99,EGP\n"
    b"2026-03-06,INV-3,sale,posted,50.00,1,EGP\n"
)

UNKNOWN_STATUS_CSV = (
    b"date,invoice,event_kind,status,amount,qty,currency\n"
    b"2026-03-04,INV-1,sale,posted,100.00,2,EGP\n"
    b"2026-03-05,INV-2,sale,pending,200.00,4,EGP\n"
)

RETURNS_CSV = (
    b"date,invoice,event_kind,status,amount,qty,currency\n"
    b"2026-03-04,INV-1,sale,posted,100.00,2,EGP\n"
    b"2026-03-05,INV-2,return,posted,-30.00,-1,EGP\n"
)


def mapped_contract(**overrides: object) -> SourceContract:
    """A contract mapping event kind, status and currency to real columns."""
    fields: dict[str, object] = {
        "event_kind_column": "event_kind",
        "status_column": "status",
        "currency_column": "currency",
        "sale_only": False,
        "posted_only": False,
        "currency_code": None,
    }
    fields.update(overrides)
    return build_source_contract(
        attribution=ContractAttribution(
            contract_id="src_admission",
            evidence="Declared for the admission cases in this module.",
        ),
        events=EventDeclaration(
            event_kind_column=fields["event_kind_column"],  # type: ignore[arg-type]
            sale_only=bool(fields["sale_only"]),
            status_column=fields["status_column"],  # type: ignore[arg-type]
            posted_only=bool(fields["posted_only"]),
            currency_column=fields["currency_column"],  # type: ignore[arg-type]
            currency_code=fields["currency_code"],  # type: ignore[arg-type]
        ),
        identity=IdentityDeclaration(
            event_key_columns=("invoice",),
            unique_line_grain_attested=False,
            transaction_id_column="invoice",
            transaction_key_components=(),
            transaction_id_unique_package_wide=True,
        ),
        basis=BasisDeclaration(
            revenue_vat_exclusive=True,
            revenue_is_net_of_returns=False,
            units_are_integral=True,
            cost_is_extended=True,
            discount_is_additive=True,
        ),
    )


def admit(content: bytes, contract: SourceContract):
    """The admitted events these bytes and this declaration produce."""
    from khepri.rra.admission import admit_events

    return admit_events(content=content, contract=contract)


def test_explicitly_void_rows_are_excluded_from_every_population() -> None:
    """"Explicitly void and cancelled events are excluded from every population."

    The extract said what the row was, so the answer is computable without it.
    The 999.00 must not reach revenue and the 99 must not reach units.
    """
    admitted = admit(VOID_AND_POSTED_CSV, mapped_contract())

    assert len(admitted.events) == 2
    assert admitted.revenue_total == Decimal("150.00")
    assert all(event.status == "posted" for event in admitted.events)


def test_an_unknown_status_refuses_rather_than_excluding_the_row() -> None:
    """An unknown status "refuses every affected population".

    `pending` is not `posted`, and it is not an explicit `void` or `cancelled`
    either. Dropping it would be a guess about what the extract meant, and the
    population that guess feeds would no longer be proven.
    """
    from khepri.rra.admission import EventsRefused

    with pytest.raises(EventsRefused) as refused:
        admit(UNKNOWN_STATUS_CSV, mapped_contract())

    assert "status" in str(refused.value).lower()


def test_mixed_currency_refuses_monetary_facts() -> None:
    """"Missing, malformed, or mixed currency refuses monetary facts."

    Two currencies in one package, and `RRA-003` states plainly that "Khepri
    performs no currency conversion", so there is no total to publish.

    **Refused as a field, not as an exception.** Raising here would take the
    count-only facts with it, which the same sentence forbids -- see the case
    below. The refusal is recorded on the result so the monetary half can be
    withheld while the rest of the package still answers.
    """
    admitted = admit(MIXED_CURRENCY_CSV, mapped_contract())

    assert admitted.monetary_refused is True
    assert admitted.currency is None
    assert admitted.revenue_total is None


def test_mixed_currency_leaves_count_only_facts_standing() -> None:
    """The same sentence's second half, which a blanket refusal would lose.

    "...but does not suppress independently proven count-only facts." Units and
    transaction counts do not depend on the currency being one, so refusing them
    alongside the monetary facts refuses more than the rule allows.
    """
    admitted = admit(MIXED_CURRENCY_CSV, mapped_contract(), )

    assert admitted.monetary_refused is True
    assert admitted.units_total == 6
    assert admitted.transaction_count == 2


def test_a_declared_currency_needs_no_column() -> None:
    """A package-level claim is admissible where the contract records it.

    `RRA-003` permits the declaration "that all monetary values use one named
    currency". The file carries a `currency` column here too, but the contract
    naming a code instead is a different reading and must be honoured as one.
    """
    single = (
        b"date,invoice,event_kind,status,amount,qty\n"
        b"2026-03-04,INV-1,sale,posted,100.00,2\n"
    )

    admitted = admit(
        single,
        mapped_contract(currency_column=None, currency_code="EGP"),
    )

    assert admitted.currency == "EGP"
    assert admitted.monetary_refused is False


def test_a_lowercase_currency_code_is_normalized_not_refused() -> None:
    """"Exactly one *normalized* uppercase ISO 4217 currency."

    Normalization is the specification's word, so `egp` in the data is the same
    currency as `EGP` and refusing it would refuse a package the contract
    proved. What is refused is two *different* currencies, which is the case
    above.
    """
    lowered = (
        b"date,invoice,event_kind,status,amount,qty,currency\n"
        b"2026-03-04,INV-1,sale,posted,100.00,2,egp\n"
        b"2026-03-05,INV-2,sale,posted,50.00,1,EGP\n"
    )

    admitted = admit(lowered, mapped_contract())

    assert admitted.currency == "EGP"
    assert admitted.monetary_refused is False


def test_returns_are_admitted_as_negative_revenue_not_dropped() -> None:
    """`RRA-003` derives return magnitude from admitted negative revenue.

    "No independently mapped returns" -- the return event is admitted as an
    event, and its magnitude is read from its own signed revenue rather than
    from a separate column.
    """
    admitted = admit(RETURNS_CSV, mapped_contract())

    assert len(admitted.events) == 2
    assert admitted.revenue_total == Decimal("70.00")
    assert admitted.returns_magnitude == Decimal("30.00")


def test_a_sale_only_declaration_refuses_a_return_row() -> None:
    """The package-level claim is a claim, and a false one is caught.

    `RRA-003` admits "that all rows are sales only when the extract contract
    excludes returns". A contract declaring `sale_only` over an extract that
    carries a return has made a false statement about the file, and admitting
    it would let the declaration override the data it describes.
    """
    from khepri.rra.admission import EventsRefused

    with pytest.raises(EventsRefused) as refused:
        admit(
            RETURNS_CSV,
            mapped_contract(event_kind_column=None, sale_only=True),
        )

    assert "sale" in str(refused.value).lower()
