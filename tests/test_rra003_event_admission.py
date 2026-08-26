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
from tests.rra_calculation_oracle import (
    ALLOCATED_DISCOUNT_EXPECTED,
    ALLOCATED_DISCOUNT_ROWS,
    REPEATED_INVOICE_EXPECTED,
    REPEATED_INVOICE_ROWS,
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
        "transaction_key_components": (),
        "transaction_id_unique_package_wide": True,
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
            transaction_key_components=fields["transaction_key_components"],  # type: ignore[arg-type]
            transaction_id_unique_package_wide=bool(
                fields["transaction_id_unique_package_wide"]
            ),
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


# ---------------------------------------------------------------------------
# M3 gap 1: canonical transaction key construction.
# ---------------------------------------------------------------------------

def _oracle_admission_csv(rows: tuple[object, ...]) -> bytes:
    """The oracle's own rows, rendered with the columns admission requires.

    `rra_calculation_oracle.to_csv` deliberately emits no `event_kind`,
    `status`, `currency` or `terminal` column -- see its docstring -- so it
    cannot feed `admit_events`, which requires every one of them. This renders
    the same `OracleRow` fields into a header admission does resolve. It is a
    serializer, not a calculation: every cell is read straight off the row, so
    no expectation is computed here.
    """
    header = (
        b"date,invoice,event_kind,status,amount,qty,currency,store,terminal,"
        b"discount_amount,cost\n"
    )

    def cell(value: object) -> str:
        return "" if value is None else str(value)

    body = b"".join(
        ",".join(
            (
                row.day.isoformat(),  # type: ignore[attr-defined]
                cell(row.invoice),  # type: ignore[attr-defined]
                row.event_kind,  # type: ignore[attr-defined]
                row.status,  # type: ignore[attr-defined]
                cell(row.revenue),  # type: ignore[attr-defined]
                cell(row.units),  # type: ignore[attr-defined]
                "EGP",
                cell(row.store),  # type: ignore[attr-defined]
                cell(row.terminal),  # type: ignore[attr-defined]
                cell(row.discount),  # type: ignore[attr-defined]
                cell(row.cost),  # type: ignore[attr-defined]
            )
        ).encode()
        + b"\n"
        for row in rows
    )
    return header + body


#: The oracle's `REPEATED_INVOICE_ROWS` -- two stores each numbering receipts
#: from 1 -- rendered for admission. Built from the oracle rather than retyped,
#: so the four canonical keys this file asserts are the oracle's own.
REPEATED_INVOICE_CSV = _oracle_admission_csv(REPEATED_INVOICE_ROWS)

#: `RRA-003`'s canonical composite in the oracle's own words: source
#: identifier, store, business date, and terminal.
ORACLE_KEY_COMPONENTS = ("invoice", "store", "date", "terminal")


def test_a_composite_transaction_key_distinguishes_repeated_bare_invoice_ids() -> None:
    """`RRA-003`: a bare identifier is the key only when proven package-wide
    unique. Two stores each numbering receipts from 1 must not collapse into
    one transaction just because the bare `invoice` values collide.

    The count comes from the oracle's own
    `REPEATED_INVOICE_EXPECTED["transactions"]`, over the oracle's own rows,
    under the oracle's own four-component key.
    """
    admitted = admit(
        REPEATED_INVOICE_CSV,
        mapped_contract(
            transaction_id_unique_package_wide=False,
            transaction_key_components=ORACLE_KEY_COMPONENTS,
        ),
    )

    assert admitted.transaction_count == int(
        REPEATED_INVOICE_EXPECTED["transactions"]
    )


def test_the_composite_key_format_matches_the_oracles_canonical_key() -> None:
    """Production's join format is bound to the oracle's, not merely to some
    injective join.

    `OracleRow.canonical_transaction_key` joins source identifier, store,
    business date and terminal on `"|"`, and `REPEATED_INVOICE_EXPECTED`'s
    docstring spells the four keys out. Asserting the count alone would pass
    for any injective join; this fails if production changes the delimiter, the
    component order, or the escaping.

    Compared against the oracle's `canonical_transaction_key` property rather
    than a literal retyped here, so the two cannot drift apart silently. This
    claims agreement on the oracle's recorded datasets, whose terminals are all
    populated -- not parity with the property's `terminal or ""` fallback for a
    null terminal, which admission refuses as a missing component instead.
    """
    admitted = admit(
        REPEATED_INVOICE_CSV,
        mapped_contract(
            transaction_id_unique_package_wide=False,
            transaction_key_components=ORACLE_KEY_COMPONENTS,
        ),
    )

    expected = [row.canonical_transaction_key for row in REPEATED_INVOICE_ROWS]
    assert expected[0] == "INV-1|S1|2026-03-04|T1"  # the oracle's own literal
    assert [event.transaction_key for event in admitted.events] == expected


def test_a_bare_unique_identifier_still_supplies_the_transaction_key() -> None:
    """Package-wide uniqueness proven means the bare identifier IS the key --
    `mapped_contract()`'s default -- and `transaction_count` must keep counting
    it, exactly as every already-passing test above depends on.

    The `2` here is not an oracle figure and must not be read as one: it is the
    count of distinct *bare* invoices in the oracle's rows, which is precisely
    the wrong answer the oracle's `REPEATED_INVOICE_EXPECTED` records production
    giving. It stands here only because this contract *declares* the bare
    identifier unique package-wide, which the oracle's dataset has no contract
    for. What is under test is that the declaration is honoured, not that 2 is
    the right transaction count for this data.
    """
    admitted = admit(REPEATED_INVOICE_CSV, mapped_contract())

    assert admitted.transaction_count == 2
    assert admitted.events[0].transaction_key == "INV-1"


def test_a_declared_component_column_absent_from_the_file_refuses() -> None:
    """`RRA-003`: "Missing components or collisions refuse transactions."

    A declaration naming a column the file does not carry proves nothing about
    identity, and `transaction_count` returns `int` -- so yielding `None` here
    would publish the *stated fact zero* for an unprovable identity, which is
    exactly the collapse `monetary_refused` exists in this module to prevent.
    `_column` already refuses a contract-named column the file lacks; the
    composite path must not bypass that refusal.
    """
    without_store = (
        b"date,invoice,event_kind,status,amount,qty,currency,terminal\n"
        b"2026-03-04,INV-1,sale,posted,100.00,2,EGP,T1\n"
        b"2026-03-04,INV-2,sale,posted,200.00,4,EGP,T1\n"
    )

    with pytest.raises(EventsRefused) as refused:
        admit(
            without_store,
            mapped_contract(
                transaction_id_unique_package_wide=False,
                transaction_key_components=("invoice", "store"),
            ),
        )

    assert "store" in str(refused.value)


def test_a_blank_component_cell_refuses_rather_than_counting_short() -> None:
    """A blank cell in a present component column refuses the population.

    Same reasoning as the absent column, one layer in: a composite with a hole
    is not a proven identity, and a `None` key would silently drop the row from
    `transaction_count` -- reporting 1 transaction for 2 rows as a stated fact.
    `RRA-003` refuses; it does not undercount.
    """
    blank_store = (
        b"date,invoice,event_kind,status,amount,qty,currency,store,terminal\n"
        b"2026-03-04,INV-1,sale,posted,100.00,2,EGP,S1,T1\n"
        b"2026-03-04,INV-2,sale,posted,200.00,4,EGP,,T1\n"
    )

    with pytest.raises(EventsRefused) as refused:
        admit(
            blank_store,
            mapped_contract(
                transaction_id_unique_package_wide=False,
                transaction_key_components=("invoice", "store"),
            ),
        )

    assert "store" in str(refused.value)


def test_the_composite_join_stays_injective_for_delimiter_bearing_values() -> None:
    """Declared columns constrain column *names*, never the arbitrary source
    *values* in them -- so a value carrying the delimiter must not forge a
    collision with a different row.

    Without escaping, `("INV-1", "S1|X")` and `("INV-1|S1", "X")` both join to
    `INV-1|S1|X` and two genuinely distinct transactions count as one -- the
    same magnitude of error as the repeated-invoice regression this composite
    exists to fix, and `RRA-003`'s "collisions refuse transactions" makes an
    encoding-induced collision governance-relevant rather than cosmetic.
    """
    colliding = (
        b"date,invoice,event_kind,status,amount,qty,currency,store\n"
        b'2026-03-04,INV-1,sale,posted,100.00,2,EGP,"S1|X"\n'
        b'2026-03-04,"INV-1|S1",sale,posted,200.00,4,EGP,X\n'
    )
    admitted = admit(
        colliding,
        mapped_contract(
            transaction_id_unique_package_wide=False,
            transaction_key_components=("invoice", "store"),
        ),
    )

    keys = [event.transaction_key for event in admitted.events]
    assert len(admitted.events) == 2
    assert keys[0] != keys[1], keys
    assert admitted.transaction_count == 2


def test_delimiter_free_components_join_exactly_as_the_oracle_states() -> None:
    """Escaping must be transparent for values carrying neither the delimiter
    nor the escape character.

    Otherwise the injectivity fix in the case above would silently break the
    format agreement with `OracleRow.canonical_transaction_key`, and no test
    would say so.
    """
    admitted = admit(
        REPEATED_INVOICE_CSV,
        mapped_contract(
            transaction_id_unique_package_wide=False,
            transaction_key_components=ORACLE_KEY_COMPONENTS,
        ),
    )

    assert admitted.events[0].transaction_key == "INV-1|S1|2026-03-04|T1"


# ---------------------------------------------------------------------------
# M3 gap 2: unique-key / line-grain attestation, enforced at admission time.
#
# `source_contract.build_source_contract` already refuses an unattested
# declaration at *construction* time (`_assert_identity_declared`). But
# `contract_from_document` -- the path `packages._stored_contract` uses to
# replay a stored profile -- deliberately does NOT re-validate (see its own
# docstring: re-validating "would refuse a stored contract whose rules have
# since tightened"). So a contract lacking both proofs can still reach
# `admit_events` on the replay path, and `admission.py` itself has no check.
# These cases construct the `SourceContract` the way that replay path does --
# directly, bypassing the builder -- so they actually exercise admission.
# ---------------------------------------------------------------------------


def _unattested_contract(**overrides: object) -> SourceContract:
    """A contract built by-passing `build_source_contract`'s own attestation
    check, the way `contract_from_document` replays a stored declaration
    without re-validating it. This is the only way to get an unattested
    contract in front of `admit_events` at all."""
    fields: dict[str, object] = {
        "event_kind_column": "event_kind",
        "status_column": "status",
        "currency_column": "currency",
        "event_key_columns": (),
        "unique_line_grain_attested": False,
    }
    fields.update(overrides)
    return SourceContract(
        contract_version="rra003.source-contract.v1",
        contract_id="src_admission_unattested",
        evidence="Constructed directly to bypass builder validation.",
        events=EventDeclaration(
            event_kind_column=fields["event_kind_column"],  # type: ignore[arg-type]
            sale_only=False,
            status_column=fields["status_column"],  # type: ignore[arg-type]
            posted_only=False,
            currency_column=fields["currency_column"],  # type: ignore[arg-type]
            currency_code=None,
        ),
        identity=IdentityDeclaration(
            event_key_columns=fields["event_key_columns"],  # type: ignore[arg-type]
            unique_line_grain_attested=fields["unique_line_grain_attested"],  # type: ignore[arg-type]
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


def test_admission_refuses_a_population_with_neither_key_nor_line_grain_proof() -> None:
    """`RRA-003` requires either a unique key or an explicit line-grain
    attestation. Neither is present here, so admission itself must refuse --
    it cannot rely solely on the builder, which the replay path bypasses."""
    contract = _unattested_contract(
        event_key_columns=(), unique_line_grain_attested=False
    )

    with pytest.raises(EventsRefused) as refused:
        admit(MIXED_CURRENCY_CSV, contract)

    message = str(refused.value).lower()
    assert "line grain" in message or "event key" in message or "identity" in message


def test_admission_admits_when_line_grain_is_attested_with_no_event_keys() -> None:
    """The attestation alone is sufficient -- `event_key_columns` empty is not
    itself a refusal once `unique_line_grain_attested` is `True`."""
    contract = _unattested_contract(
        event_key_columns=(), unique_line_grain_attested=True
    )

    admitted = admit(MIXED_CURRENCY_CSV, contract)

    assert len(admitted.events) == 2


def test_admission_admits_when_event_keys_are_declared_with_no_attestation() -> None:
    """The other proof alone is sufficient -- declared event keys with
    `unique_line_grain_attested=False` must not be refused."""
    contract = _unattested_contract(
        event_key_columns=("invoice",), unique_line_grain_attested=False
    )

    admitted = admit(MIXED_CURRENCY_CSV, contract)

    assert len(admitted.events) == 2


# ---------------------------------------------------------------------------
# M3 gaps 3 and 4: discount and cost normalized measures.
# ---------------------------------------------------------------------------

DISCOUNT_AND_COST_CSV = (
    b"date,invoice,event_kind,status,amount,qty,currency,discount_amount,cost\n"
    b"2026-03-04,INV-1,sale,posted,100.00,2,EGP,10.00,55.00\n"
    b"2026-03-05,INV-2,sale,posted,200.00,4,EGP,5.00,110.00\n"
)


#: The oracle's own discount case -- one invoice's three lines carrying row
#: discounts of 22.00 / 14.00 / 9.00 -- rendered for admission.
ALLOCATED_DISCOUNT_CSV = _oracle_admission_csv(ALLOCATED_DISCOUNT_ROWS)


def test_discount_is_admitted_as_a_normalized_measure_like_revenue() -> None:
    """`mapping.py` already resolves `SEMANTIC_DISCOUNT`; admission must read
    it onto each event the same way it reads revenue.

    Values come from the oracle's `ALLOCATED_DISCOUNT_ROWS` and their sum from
    its own `ALLOCATED_DISCOUNT_EXPECTED["discount"]`, so nothing here is a
    literal this file authored.
    """
    admitted = admit(ALLOCATED_DISCOUNT_CSV, mapped_contract())

    assert [event.discount for event in admitted.events] == [
        row.discount for row in ALLOCATED_DISCOUNT_ROWS
    ]
    assert sum(
        (event.discount for event in admitted.events if event.discount is not None),
        Decimal("0.00"),
    ) == ALLOCATED_DISCOUNT_EXPECTED["discount"]


def test_cost_is_admitted_as_a_normalized_measure_like_revenue() -> None:
    """`mapping.py` already resolves `SEMANTIC_COST`; admission must read it
    onto each event the same way it reads revenue."""
    admitted = admit(DISCOUNT_AND_COST_CSV, mapped_contract())

    assert [event.cost for event in admitted.events] == [
        Decimal("55.00"),
        Decimal("110.00"),
    ]


def test_discount_and_cost_are_withheld_alongside_revenue_on_currency_refusal() -> None:
    """`RRA-003`: currency refusal withholds monetary facts and their derived
    results. Discount and cost are monetary, so a mixed currency must withhold
    them exactly as it withholds revenue -- not leave them computed under an
    unproven currency."""
    mixed = (
        b"date,invoice,event_kind,status,amount,qty,currency,discount_amount,cost\n"
        b"2026-03-04,INV-1,sale,posted,100.00,2,EGP,10.00,55.00\n"
        b"2026-03-05,INV-2,sale,posted,200.00,4,USD,5.00,110.00\n"
    )

    admitted = admit(mixed, mapped_contract())

    assert admitted.monetary_refused is True
    assert all(event.discount is None for event in admitted.events)
    assert all(event.cost is None for event in admitted.events)


def test_discount_is_withheld_when_the_basis_does_not_attest_additivity() -> None:
    """`BasisDeclaration.discount_is_additive` is the operator's attestation
    that the mapped discount column is already non-overlapping, allocated
    additive currency -- `RRA-003`: "A bare discount, rate, percentage,
    repeated invoice total, or overlapping component set refuses the discount
    metric." Where the basis does not attest additivity, admission has no
    proof the column may be summed, so it is withheld the same way an
    unproven currency withholds revenue -- publishing a figure the basis
    itself disclaims would be the inference `RRA-003` forbids."""
    admitted = admit(
        DISCOUNT_AND_COST_CSV,
        mapped_contract(),
    )
    assert admitted.events[0].discount is not None  # sanity: additive by default

    non_additive_contract = build_source_contract(
        attribution=ContractAttribution(
            contract_id="src_admission_non_additive",
            evidence="Discount basis not attested additive.",
        ),
        events=EventDeclaration(
            event_kind_column="event_kind",
            sale_only=False,
            status_column="status",
            posted_only=False,
            currency_column="currency",
            currency_code=None,
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
            discount_is_additive=False,
        ),
    )

    admitted = admit(DISCOUNT_AND_COST_CSV, non_additive_contract)

    assert all(event.discount is None for event in admitted.events)
    # Revenue and cost are unaffected by the discount basis flag specifically.
    assert admitted.events[0].revenue == Decimal("100.00")


def test_cost_is_withheld_when_the_basis_does_not_attest_extended() -> None:
    """`BasisDeclaration.cost_is_extended` is the attestation that the mapped
    cost column is already row-level extended COGS, not a unit/average/list
    cost. `RRA-003`: "unit cost, average cost, standard cost, list cost, and a
    bare ambiguous cost label are not additive COGS and are refused." Where
    the basis does not attest extended cost, admission withholds it."""
    non_extended_contract = build_source_contract(
        attribution=ContractAttribution(
            contract_id="src_admission_non_extended",
            evidence="Cost basis not attested extended.",
        ),
        events=EventDeclaration(
            event_kind_column="event_kind",
            sale_only=False,
            status_column="status",
            posted_only=False,
            currency_column="currency",
            currency_code=None,
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
            cost_is_extended=False,
            discount_is_additive=True,
        ),
    )

    admitted = admit(DISCOUNT_AND_COST_CSV, non_extended_contract)

    assert all(event.cost is None for event in admitted.events)
    assert admitted.events[0].revenue == Decimal("100.00")


def test_discount_and_cost_columns_are_read_once_each_not_once_per_row() -> None:
    """Same performance discipline as the existing revenue/units/transaction-id
    proof: discount and cost must be hoisted out of the per-row loop too."""
    import polars as pl

    rows = 200
    header = (
        b"date,invoice,event_kind,status,amount,qty,currency,"
        b"discount_amount,cost\n"
    )
    body = b"".join(
        b"2026-03-%02d,INV-%d,sale,posted,100.00,2,EGP,5.00,50.00\n"
        % ((index % 28) + 1, index)
        for index in range(rows)
    )
    content = header + body
    contract = mapped_contract()

    calls = 0
    original = pl.DataFrame.get_column

    def counting_get_column(self: pl.DataFrame, name: str):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(self, name)

    pl.DataFrame.get_column = counting_get_column  # type: ignore[method-assign]
    try:
        admitted = admit(content, contract)
    finally:
        pl.DataFrame.get_column = original  # type: ignore[method-assign]

    assert len(admitted.events) == rows
    assert calls <= 40, (
        f"admission materialized columns {calls} times for {rows} rows with "
        "discount and cost columns -- reads must stay hoisted out of the loop"
    )


def _composite_key_csv(rows: int) -> bytes:
    """`rows` admissible rows carrying every declared composite component."""
    header = (
        b"date,invoice,event_kind,status,amount,qty,currency,store,terminal\n"
    )
    body = b"".join(
        b"2026-03-%02d,INV-%d,sale,posted,100.00,2,EGP,S1,T1\n"
        % ((index % 28) + 1, index)
        for index in range(rows)
    )
    return header + body


def _column_reads_for(content: bytes, contract: SourceContract) -> int:
    """How many times admission materialized a column for this input."""
    import polars as pl

    calls = 0
    original = pl.DataFrame.get_column

    def counting_get_column(self: pl.DataFrame, name: str):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return original(self, name)

    pl.DataFrame.get_column = counting_get_column  # type: ignore[method-assign]
    try:
        admit(content, contract)
    finally:
        pl.DataFrame.get_column = original  # type: ignore[method-assign]
    return calls


def test_the_composite_key_components_are_read_once_each_not_once_per_row() -> None:
    """The composite key's own loop over N declared components must be hoisted.

    The sibling test above runs on `mapped_contract()`'s default, where
    `transaction_id_unique_package_wide` is `True` -- so `_transaction_key_column`
    returns the already-read transaction ids immediately and reads *zero*
    columns. It therefore measures discount and cost, which merely reuse the
    already-proven `_measure_column`, and leaves the one genuinely new per-row
    loop entirely unmeasured. This is the variant that measures it.

    Asserted as flatness across two row counts rather than against a threshold:
    a bound can be satisfied by a loop that is merely cheap, while an equal
    count can only be satisfied by a read that does not depend on row count at
    all.
    """
    contract = mapped_contract(
        transaction_id_unique_package_wide=False,
        transaction_key_components=("invoice", "store", "terminal"),
    )

    few = _column_reads_for(_composite_key_csv(50), contract)
    many = _column_reads_for(_composite_key_csv(500), contract)

    assert few == many, (
        f"admission materialized columns {few} times for 50 rows and {many} "
        "times for 500 -- the composite key's component reads are inside the "
        "per-row loop"
    )
