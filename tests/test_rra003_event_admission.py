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

from khepri.rra.admission import EventsRefused
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
        "event_key_columns": ("invoice",),
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
            event_key_columns=fields["event_key_columns"],  # type: ignore[arg-type]
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
    """The admitted events these bytes and this declaration produce.

    Built through the real `build_profile`/`build_mapping` pair, so the measure
    columns come from the mapping's recorded evidence rather than from a label
    this module happened to choose. Renaming a fixture's columns to any other
    spelling `mapping.py` resolves must leave every assertion here standing.
    """
    import hashlib

    from khepri.rra.admission import admit_events
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile

    profile = build_profile(
        content=content,
        media_type="text/csv",
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    return admit_events(
        content=content,
        media_type="text/csv",
        mapping=build_mapping(profile, contract=contract),
        contract=contract,
    )


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
    # The contract names `event_kind` as an event key, so it is a column the
    # *declaration* points at rather than one found by spelling. That is the
    # only kind of column this check may consult.
    with pytest.raises(EventsRefused) as refused:
        admit(
            RETURNS_CSV,
            mapped_contract(
                event_kind_column=None,
                sale_only=True,
                event_key_columns=("invoice", "event_kind"),
            ),
        )

    assert "sale" in str(refused.value).lower()


def test_admission_runs_inside_the_package_builder() -> None:
    """The rule this whole module exists for, proved where it must hold.

    Calling `admit_events` directly proves only that admission works. It cannot
    fail when the builder stops calling it -- and a module with no caller passes
    every one of its own tests while excluding no row and refusing no
    population. `test_rra004_version_gate_wiring` makes the same argument about
    the version gate, and for the same reason this drives `build_fact_package`.

    An unknown status must refuse the package, not be silently dropped.
    """
    import hashlib

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.facts import AdmittedInput, FactsRefused, build_fact_package
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile

    contract = mapped_contract()
    profile = build_profile(
        content=UNKNOWN_STATUS_CSV,
        media_type="text/csv",
        source_sha256_hex=hashlib.sha256(UNKNOWN_STATUS_CSV).hexdigest(),
    )
    mapping = build_mapping(profile, contract=contract)

    with pytest.raises(FactsRefused) as refused:
        build_fact_package(
            AdmittedInput(
                content=UNKNOWN_STATUS_CSV,
                media_type="text/csv",
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=contract,
            )
        )

    assert "status" in str(refused.value).lower()


def package_from(content: bytes, contract: SourceContract):
    """One governed package over these bytes, through the real builder."""
    import hashlib

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.facts import AdmittedInput, build_fact_package
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile

    profile = build_profile(
        content=content,
        media_type="text/csv",
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=contract)
    return build_fact_package(
        AdmittedInput(
            content=content,
            media_type="text/csv",
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
        )
    )


def test_a_void_row_reaches_no_published_figure() -> None:
    """"Explicitly void and cancelled events are excluded from every population."

    *Every* population, which is the published package and not only the
    intermediate admitted set. `admit_events` filtering the row while
    `_measures` still reads the whole frame would leave the exclusion true of an
    object nobody publishes and false of every figure anybody sees.

    The void row carries 999.00 and 99 precisely so that a package computed over
    it is unmistakable.
    """
    package = package_from(VOID_AND_POSTED_CSV, mapped_contract())

    assert package.value("revenue") == "150.00"
    assert package.value("units") == "3"


def test_mixed_currency_withholds_every_monetary_fact() -> None:
    """Monetary facts, plural -- not revenue alone.

    `RRA-003` refuses "monetary facts and their derived results". The package
    publishes revenue, AOV, ASP, cost, gross profit, margin, discount and
    returns from monetary inputs; withholding one of them and publishing seven
    under an unproven currency refuses far less than the rule requires.
    """
    monetary = (
        b"date,invoice,event_kind,status,net_sales,units,cogs,currency\n"
        b"2026-03-04,INV-1,sale,posted,100.00,2,60.00,EGP\n"
        b"2026-03-05,INV-2,sale,posted,200.00,4,120.00,USD\n"
    )

    package = package_from(monetary, mapped_contract())

    # Every metric the package derives from a monetary input, enumerated rather
    # than sampled: a gate applied to some of them and not others publishes
    # figures under a currency the package refused to prove.
    for metric in (
        "revenue",
        "cost",
        "gross_profit",
        "gross_margin",
        "discount",
        "returns",
        "average_order_value",
        "average_selling_price",
    ):
        assert package.value(metric) is None, metric


def test_mixed_currency_still_publishes_the_counts() -> None:
    """The other half of the same sentence, on the published package."""
    monetary = (
        b"date,invoice,event_kind,status,net_sales,units,cogs,currency\n"
        b"2026-03-04,INV-1,sale,posted,100.00,2,60.00,EGP\n"
        b"2026-03-05,INV-2,sale,posted,200.00,4,120.00,USD\n"
    )

    package = package_from(monetary, mapped_contract())

    assert package.value("units") == "6"


def test_an_unknown_status_refuses_as_a_governed_refusal_not_a_crash() -> None:
    """`EventsRefused` must not escape the package builder as itself.

    `EventsRefused` and `FactsRefused` are sibling `ValueError` subclasses, so
    `except FactsRefused` does not catch the former. `packages.build_session_package`
    wraps only `FactsRefused` into `PackageRefused`, and `api.build_retail_facts`
    handles only `PackageRefused` -- so an `EventsRefused` crossing this boundary
    reaches the client as HTTP 500 rather than the governed 409 refusal.

    That misreports a correctly-detected bad declaration as a server defect and
    discards the refusal reason `RRA-003` requires be stated. The trigger is
    ordinary stored data: a declared status column carrying a value the contract
    does not admit.

    `test_admission_runs_inside_the_package_builder` above cannot catch this --
    it accepts either exception type, so it passes whether or not the boundary
    translates. This asserts the governed type specifically.
    """
    import hashlib

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.facts import AdmittedInput, FactsRefused, build_fact_package
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile

    contract = mapped_contract()
    profile = build_profile(
        content=UNKNOWN_STATUS_CSV,
        media_type="text/csv",
        source_sha256_hex=hashlib.sha256(UNKNOWN_STATUS_CSV).hexdigest(),
    )
    mapping = build_mapping(profile, contract=contract)

    with pytest.raises(FactsRefused) as refused:
        build_fact_package(
            AdmittedInput(
                content=UNKNOWN_STATUS_CSV,
                media_type="text/csv",
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=contract,
            )
        )

    # The reason survives translation; a refusal that loses it states nothing.
    assert "status" in str(refused.value).lower()


def test_a_contract_naming_an_absent_column_refuses_as_a_governed_refusal() -> None:
    """The same boundary, reached by the other `EventsRefused` path.

    `_column` raises `EventsRefused` when the contract names a column the file
    does not carry. That is a declaration defect the operator can correct, so it
    must arrive as a governed refusal too, not as a 500.
    """
    import hashlib

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.facts import AdmittedInput, FactsRefused, build_fact_package
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile

    contract = mapped_contract(status_column="settlement_state")
    profile = build_profile(
        content=UNKNOWN_STATUS_CSV,
        media_type="text/csv",
        source_sha256_hex=hashlib.sha256(UNKNOWN_STATUS_CSV).hexdigest(),
    )
    mapping = build_mapping(profile, contract=contract)

    with pytest.raises(FactsRefused) as refused:
        build_fact_package(
            AdmittedInput(
                content=UNKNOWN_STATUS_CSV,
                media_type="text/csv",
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=contract,
            )
        )

    assert "settlement_state" in str(refused.value)


def test_admission_reads_each_column_once_not_once_per_row() -> None:
    """Column reads must scale with columns, not with rows times columns.

    `_measure` and `_transaction_id` materialized a whole column per row --
    `frame.get_column(...).cast(pl.String).to_list()` then indexed one element.
    The comprehension calls `_measure` for revenue, `_unit_count` -> `_measure`
    for units, and `_transaction_id` once each, so admission performed roughly
    `3 * kept` full column materializations: quadratic in row count, on the
    `POST /api/v1/beta/facts` request thread.

    This asserts the mechanism rather than elapsed time, which would be flaky on
    a shared runner and would not say what regressed. A per-row implementation
    exceeds this bound on the first extra row; a hoisted one is unaffected by
    row count, which is the property under test.
    """
    import hashlib

    import polars as pl

    from khepri.rra.admission import admit_events
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile

    rows = 200
    header = b"date,invoice,event_kind,status,amount,qty,currency\n"
    body = b"".join(
        b"2026-03-%02d,INV-%d,sale,posted,100.00,2,EGP\n" % ((index % 28) + 1, index)
        for index in range(rows)
    )
    content = header + body
    contract = mapped_contract()
    profile = build_profile(
        content=content,
        media_type="text/csv",
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=contract)

    calls = 0
    original = pl.DataFrame.get_column

    def counting_get_column(self: pl.DataFrame, name: str):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(self, name)

    pl.DataFrame.get_column = counting_get_column  # type: ignore[method-assign]
    try:
        admitted = admit_events(
            content=content,
            media_type="text/csv",
            mapping=mapping,
            contract=contract,
        )
    finally:
        pl.DataFrame.get_column = original  # type: ignore[method-assign]

    assert len(admitted.events) == rows
    # Seven columns exist; a handful of reads per column leaves generous room for
    # implementation detail while still failing hard on anything per-row.
    assert calls <= 32, (
        f"admission materialized columns {calls} times for {rows} rows -- "
        "column reads must be hoisted out of the per-row loop"
    )
