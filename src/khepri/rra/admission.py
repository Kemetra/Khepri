"""Which rows a governed calculation may use, and which it must refuse.

`RRA-003`'s normalized event contract requires every row used by a governed
calculation to carry a transaction date, an event kind of `sale` or `return`, a
status proving `posted`, and exactly one normalized uppercase ISO 4217 currency
for every monetary measure.

**Its own module, not `mapping.py`.** Mapping resolves *columns to semantics*;
it never filters rows, and it carries no event-kind, status or currency semantic
to resolve. What happens here is a per-row read of the frame under a recorded
declaration, which is a different question from which column means what.

**Three outcomes, and collapsing any two of them is the defect this module
exists to prevent.** `RRA-003`:

> An unknown or missing event kind, status, currency, or required identity proof
> refuses every affected population rather than silently excluding rows.
> Explicitly void and cancelled events are excluded from every population.
> Missing, malformed, or mixed currency refuses monetary facts and their derived
> results but does not suppress independently proven count-only facts.

- **Excluded.** An explicitly void or cancelled row. The extract said what it
  was, so the answer is computable without it.
- **Refused entirely.** An unknown event kind or status. The extract did not
  say, so dropping the row would be a guess about what it meant and the
  population that guess feeds is no longer proven.
- **Refused in part.** Missing, malformed, or mixed currency. Monetary facts go;
  count-only facts, which never depended on the currency being one, stay.

The third is the one a blanket refusal loses, and losing it refuses more than
the specification allows.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import polars as pl

from khepri.rra.mapping import (
    SEMANTIC_COST,
    SEMANTIC_DISCOUNT,
    SEMANTIC_REVENUE,
    SEMANTIC_UNITS,
    RetailMapping,
)
from khepri.rra.profiling import materialize
from khepri.rra.source_contract import SourceContract

EVENT_SALE = "sale"
EVENT_RETURN = "return"

STATUS_POSTED = "posted"
#: Statuses that exclude their row. Named explicitly, because `RRA-003` excludes
#: only what the extract *says* is void or cancelled -- anything else unknown is
#: a refusal, not a silent drop.
STATUS_EXCLUDED = frozenset({"void", "cancelled", "canceled"})

_ISO_CURRENCY_LENGTH = 3

#: How `RRA-003`'s canonical composite is spelled. `"|"` is the delimiter the
#: calculation oracle's `canonical_transaction_key` records, so a component
#: value carrying one is escaped rather than the delimiter being changed --
#: changing it would break the recorded format agreement.
KEY_DELIMITER = "|"
KEY_ESCAPE = "\\"


class EventsRefused(ValueError):
    """A population that cannot be proven from what the extract declared."""


@dataclass(frozen=True, slots=True)
class _Reading:
    """One materialized frame and the column positions its header resolved to.

    The two always travel together -- `labels` is derived from `frame.columns`
    and is meaningless against any other frame -- so passing them as one value
    keeps a reader from having to check that a given pair belongs together.
    """

    frame: pl.DataFrame
    labels: dict[str, int]


@dataclass(frozen=True, slots=True)
class AdmittedEvent:
    """One normalized retail event, as far as this slice admits one.

    **No transaction date yet.** `RRA-003` lists one first among the fields a
    normalized event carries, and there is no refusal here for a row lacking
    one -- the date is resolved as a mapped semantic and read by the comparison
    windows downstream, so admitting it here would duplicate that resolution
    without any consumer. A field that always held `None` would read as done
    while lying to the first caller that trusted it, so it is absent instead.
    Recorded as outstanding in the `CAL1-01` ledger.
    """

    event_kind: str
    status: str
    revenue: Decimal | None
    units: int | None
    transaction_id: str | None
    cost: Decimal | None
    discount: Decimal | None
    #: The identity `transaction_count` actually counts. Equal to
    #: `transaction_id` when the contract proves it unique package-wide;
    #: otherwise the declared composite, joined in `RRA-003`'s words as "an
    #: admitted composite of the source transaction identifier and every
    #: field needed for uniqueness", with each component escaped so a value
    #: carrying the delimiter cannot forge a collision. `None` only where no
    #: identity is declared at all -- a bare identifier not proven unique and no
    #: composite declared -- which `source_contract` already refuses at
    #: declaration time, so this module only has to read the outcome, not
    #: re-derive the proof. A *declared* composite that cannot be built refuses
    #: the population instead of arriving here as `None`.
    transaction_key: str | None


@dataclass(frozen=True, slots=True)
class AdmittedEvents:
    """The events a package may calculate over, and what was refused.

    `monetary_refused` is a field rather than an exception because the
    specification refuses monetary facts *and leaves count-only facts standing*.
    Raising would take both.
    """

    events: tuple[AdmittedEvent, ...]
    currency: str | None
    monetary_refused: bool
    excluded_count: int
    #: Positions of the rows that survived admission, in frame order. Carried so
    #: a caller reading the frame directly can narrow it to the same rows rather
    #: than re-deriving the exclusion and risking a different answer.
    kept_positions: tuple[int, ...]
    #: Whether a declared event key repeats across the admitted rows. `RRA-003`
    #: proves identity "in exactly one of these ways", and a contract naming
    #: `event_key_columns` chose the first -- but declaring a key is not proof
    #: that its values are unique, and `source_contract` validates only that
    #: exactly one proof was declared. A field rather than an exception for
    #: `monetary_refused`'s reason: the sentence names the results it refuses,
    #: and raising would take the ones it does not.
    repeated_event_key: bool = False

    @property
    def revenue_total(self) -> Decimal | None:
        """Signed net revenue, or `None` when monetary facts are refused.

        Returns contribute negatively rather than being dropped: `RRA-003`
        derives return magnitude from admitted negative revenue and admits "no
        independently mapped returns".
        """
        if self.monetary_refused:
            return None
        return sum(
            (event.revenue for event in self.events if event.revenue is not None),
            Decimal("0.00"),
        )

    @property
    def returns_magnitude(self) -> Decimal | None:
        """The positive reversal magnitude: `-return revenue`, summed."""
        if self.monetary_refused:
            return None
        return -sum(
            (
                event.revenue
                for event in self.events
                if event.event_kind == EVENT_RETURN and event.revenue is not None
            ),
            Decimal("0.00"),
        )

    @property
    def units_total(self) -> int:
        """A count-only fact, so it survives a currency refusal."""
        return sum(event.units for event in self.events if event.units is not None)

    @property
    def transaction_count(self) -> int:
        """Distinct canonical transactions, also count-only.

        Counts `transaction_key`, not the bare `transaction_id` -- `RRA-003`
        requires the composite whenever a bare identifier is not proven
        package-wide unique, and counting the bare identifier instead would
        collapse two different stores' identically-numbered receipts into
        one transaction.
        """
        return len(
            {event.transaction_key for event in self.events if event.transaction_key}
        )


def admit_events(
    *,
    content: bytes,
    media_type: str,
    mapping: RetailMapping,
    contract: SourceContract,
) -> AdmittedEvents:
    """The events these bytes and this declaration admit, or a refusal.

    **Measures come from the mapping, never from a header.** `RRA-003` holds
    that headers "never establish event kind, status, currency, gross/net basis,
    VAT treatment, additivity, allocation, or coverage", so reading a column
    because it is spelled `amount` would be the inference this module exists to
    refuse. `RetailMapping` already resolved revenue and units under recorded
    evidence; this reads the positions it resolved.
    """
    _assert_identity_proven(contract)
    frame = materialize(content, media_type)
    labels = {label: index for index, label in enumerate(frame.columns)}
    kinds = _event_kinds(frame, labels, contract)
    statuses = _statuses(frame, labels, contract)
    currency, monetary_refused = _currency(frame, labels, contract)

    kept = [
        index
        for index in range(frame.height)
        if statuses[index] not in STATUS_EXCLUDED
    ]
    # Every column this loop needs, materialized once. Reading them per row made
    # admission quadratic in row count on the `POST /api/v1/beta/facts` request
    # thread: three full column materializations for every kept row, each one
    # discarding all but a single element.
    revenues = (
        [None] * frame.height
        if monetary_refused
        else _measure_column(frame, mapping, SEMANTIC_REVENUE)
    )
    units = _unit_column(frame, mapping)
    transaction_ids = _transaction_id_column(frame, labels, contract)
    reading = _Reading(frame=frame, labels=labels)
    keys = _transaction_key_column(reading, contract, transaction_ids, frozenset(kept))
    discounts = (
        [None] * frame.height
        if monetary_refused or not contract.basis.discount_is_additive
        else _measure_column(frame, mapping, SEMANTIC_DISCOUNT)
    )
    costs = (
        [None] * frame.height
        if monetary_refused or not contract.basis.cost_is_extended
        else _measure_column(frame, mapping, SEMANTIC_COST)
    )
    events = [
        AdmittedEvent(
            event_kind=kinds[index],
            status=statuses[index],
            revenue=revenues[index],
            units=units[index],
            transaction_id=transaction_ids[index],
            cost=costs[index],
            discount=discounts[index],
            transaction_key=keys[index],
        )
        for index in kept
    ]
    excluded = frame.height - len(kept)
    return AdmittedEvents(
        events=tuple(events),
        currency=currency,
        monetary_refused=monetary_refused,
        excluded_count=excluded,
        kept_positions=tuple(kept),
        repeated_event_key=_repeated_event_key(reading, contract, frozenset(kept)),
    )


def _event_kinds(
    frame: pl.DataFrame,
    labels: dict[str, int],
    contract: SourceContract,
) -> list[str]:
    """Every row's event kind, from the mapped column or the package claim."""
    declared = contract.events.event_kind_column
    if declared is None:
        _assert_sale_only_holds(frame, labels, contract)
        return [EVENT_SALE] * frame.height
    return [_one_kind(value) for value in _column(frame, labels, declared)]


def _one_kind(value: str | None) -> str:
    """A sale or a return, or a refusal naming what the extract said instead."""
    kind = (value or "").strip().lower()
    if kind not in {EVENT_SALE, EVENT_RETURN}:
        raise EventsRefused(
            f"An event kind of {value!r} is neither a sale nor a return."
        )
    return kind


def _assert_sale_only_holds(
    frame: pl.DataFrame,
    labels: dict[str, int],
    contract: SourceContract,
) -> None:
    """A package-level `sale_only` claim, checked against the extract it describes.

    `RRA-003` admits the declaration "that all rows are sales **only when the
    extract contract excludes returns**". So it is a claim about the file, not a
    permission to reinterpret it, and a claim contradicted by the file has
    established nothing -- admitting it would let the declaration override the
    data it describes, which is the inference this specification refuses.

    **Checked against a column the contract itself named**, never one found by
    spelling. `sale_only` and a mapped `event_kind_column` are mutually
    exclusive -- `source_contract` refuses a semantic declared twice -- so the
    column consulted here is the one the *identity* declaration names as an
    event key, where the operator pointed at something that also records kind.
    Where the contract names no such column there is nothing to contradict and
    the claim stands on its own attestation, which is what `RRA-003` admits it
    on. Guessing at `event_kind`/`event_type` labels would re-introduce the
    header inference this module refuses.
    """
    if not contract.events.sale_only:
        return
    for label in contract.identity.event_key_columns:
        if label not in labels:
            continue
        kinds = {
            (value or "").strip().lower() for value in _column(frame, labels, label)
        }
        if EVENT_RETURN in kinds:
            raise EventsRefused(
                "The source contract declares sale-only rows, but the extract "
                f"carries a return in {label!r}."
            )


def _statuses(
    frame: pl.DataFrame,
    labels: dict[str, int],
    contract: SourceContract,
) -> list[str]:
    """Every row's status, refusing any the extract did not account for."""
    declared = contract.events.status_column
    if declared is None:
        return [STATUS_POSTED] * frame.height
    return [_one_status(value) for value in _column(frame, labels, declared)]


def _one_status(value: str | None) -> str:
    """Posted, or explicitly excluded, or a refusal.

    The third branch is the point: an unknown status is neither proof nor an
    exclusion, and dropping its row would be a guess about what the extract
    meant.
    """
    status = (value or "").strip().lower()
    if status != STATUS_POSTED and status not in STATUS_EXCLUDED:
        raise EventsRefused(
            f"A status of {value!r} neither proves posted nor excludes the row."
        )
    return status


def _currency(
    frame: pl.DataFrame,
    labels: dict[str, int],
    contract: SourceContract,
) -> tuple[str | None, bool]:
    """The one currency, or the refusal of monetary facts alone.

    Normalized before comparison, because `RRA-003` asks for "exactly one
    *normalized* uppercase ISO 4217 currency" -- `egp` and `EGP` are the same
    currency and refusing that pairing would refuse a package the contract
    proved. What is refused is two genuinely different codes.
    """
    if contract.events.currency_code is not None:
        return contract.events.currency_code.upper(), False
    declared = contract.events.currency_column
    if declared is None:
        return None, True
    seen = {
        (value or "").strip().upper()
        for value in _column(frame, labels, declared)
        if (value or "").strip()
    }
    if len(seen) != 1:
        return None, True
    code = seen.pop()
    return (code, False) if _is_iso_currency(code) else (None, True)


def _is_iso_currency(code: str) -> bool:
    """Three letters, which is the whole of ISO 4217's shape.

    The same test `source_contract` applies to a declared code, applied here to
    an observed one, so a column carrying `EGP ` and a contract carrying `egp`
    reach the same verdict.
    """
    return len(code) == _ISO_CURRENCY_LENGTH and code.isalpha()


def _column(
    frame: pl.DataFrame,
    labels: dict[str, int],
    label: str,
) -> list[str | None]:
    """One declared column's values, refusing a column the file does not carry."""
    if label not in labels:
        raise EventsRefused(f"The source contract names no column {label!r}.")
    series = frame.get_column(frame.columns[labels[label]]).cast(pl.String)
    return [
        None if value is None or not value.strip() else value.strip()
        for value in series.to_list()
    ]


def _measure_column(
    frame: pl.DataFrame,
    mapping: RetailMapping,
    semantic: str,
) -> list[Decimal | None]:
    """Every row's value for a mapped measure, read in one pass.

    An unresolved semantic, a blank cell, and an unparsable one all yield `None`
    here rather than a refusal: whether a missing measure refuses the population
    is `facts.py`'s question, and this module answers only what the extract says.
    """
    column = mapping.for_semantic(semantic).column
    if column is None:
        return [None] * frame.height
    return [_one_measure(raw) for raw in _raw_column(frame, column.position)]


def _one_measure(raw: object) -> Decimal | None:
    """One cell as a governed decimal, or `None` where it states no number."""
    if raw is None or not str(raw).strip():
        return None
    try:
        return Decimal(str(raw).strip())
    except InvalidOperation:
        return None


def _unit_column(frame: pl.DataFrame, mapping: RetailMapping) -> list[int | None]:
    """Every row's unit count, from the same single pass as any other measure."""
    return [
        None if value is None else int(value)
        for value in _measure_column(frame, mapping, SEMANTIC_UNITS)
    ]


def _transaction_id_column(
    frame: pl.DataFrame,
    labels: dict[str, int],
    contract: SourceContract,
) -> list[str | None]:
    """Every row's declared transaction id, or `None` where none is declared.

    An undeclared or absent column is not a refusal here -- `_column` refuses a
    contract-named column the file lacks, while identity is optional at this
    boundary and `facts.py` decides what its absence costs.
    """
    declared = contract.identity.transaction_id_column
    if declared is None or declared not in labels:
        return [None] * frame.height
    return [
        None if raw is None else str(raw).strip() or None
        for raw in _raw_column(frame, labels[declared])
    ]


def _repeated_event_key(
    reading: _Reading,
    contract: SourceContract,
    kept: frozenset[int],
) -> bool:
    """Whether a declared event key repeats across the rows admission kept.

    `RRA-003`: "A repeated event key, whether identical or conflicting, refuses
    every additive or distinct-transaction result that could include it." Two
    rows sharing one key are either two events wrongly given the same identity or
    one event exported twice, and the extract does not say which -- the same
    ambiguity the canonical-row-signature test answers for contracts that took
    the other identity proof.

    Asked only of contracts that took this proof. A contract attesting unique
    line grain declares no key columns, and its own falsification is the repeated
    row signature `facts` checks.

    Excluded rows are not consulted: `RRA-003` excludes void and cancelled events
    "from every population", so a key repeated only on a row already dropped
    refuses nothing.
    """
    components = contract.identity.event_key_columns
    if not components:
        return False
    # Read through `_column`, which refuses a column the file does not carry.
    # Skipping the absent ones and answering `False` instead would report "no
    # repeats" for a contract whose declared identity was never checked at all:
    # the extract would publish facts under an identity proof that could not be
    # evaluated, which is the one outcome `RRA-003` does not allow. A contract
    # naming a column its own extract lacks is an inconsistent pair, and the
    # refusal belongs to the pair rather than to either half.
    columns = [
        _column(reading.frame, reading.labels, component) for component in components
    ]
    seen: set[tuple[str | None, ...]] = set()
    for index in sorted(kept):
        key = tuple(column[index] for column in columns)
        if key in seen:
            return True
        seen.add(key)
    return False


def _transaction_key_column(
    reading: _Reading,
    contract: SourceContract,
    transaction_ids: list[str | None],
    kept: frozenset[int],
) -> list[str | None]:
    """Every row's canonical transaction key, `RRA-003`'s composite or the
    bare identifier, whichever the contract proves.

    A bare `transaction_id` qualifies as the key only where the contract
    proves it package-wide unique. Otherwise `RRA-003` requires "an admitted
    composite of the source transaction identifier and every field needed for
    uniqueness" -- built here by joining `transaction_key_components`' own
    declared columns, so two stores numbering receipts from 1 do not collapse
    into one transaction merely because the bare identifiers collide.

    **A missing component refuses the population, and does not yield `None`.**
    `RRA-003`: "Missing components or collisions refuse transactions." Two ways
    a component can be missing, both refused here:

    - *The column is absent from the file.* A declaration naming a column the
      extract does not carry proves nothing about identity, and
      `source_contract._assert_transaction_key` already establishes that these
      components are load-bearing -- it refuses a composite omitting the source
      identifier. A composite whose columns are absent is the same defect
      discovered one layer later, so `_column`'s existing refusal is allowed to
      fire rather than being bypassed.
    - *A present column's cell is blank.* Refused rather than recorded as an
      unprovable row. `transaction_count` returns `int`, so a `None` key makes
      an unprovable identity indistinguishable from the *stated fact* that the
      row contributed no transaction -- which is the collapse `monetary_refused`
      was introduced into this module to prevent. Recording it instead would
      need a distinguishable marker of its own, and inventing one here without
      a consumer is deferred (`CAL1-01` ledger, `M1`).

    **The blank-cell refusal applies only to a row that survives exclusion.**
    `RRA-003` excludes an explicitly void or cancelled row from every
    population, and the answer is computable without it -- so a blank component
    on a row nothing counts is not a missing proof, it is a row already
    correctly dropped. Refusing over it would be exactly the blanket refusal
    this module's own docstring warns of: "the one a blanket refusal loses, and
    losing it refuses more than the specification allows". Excluded positions
    yield `None`, which no caller reads, because `admit_events` builds events
    only over `kept`.

    The *absent column* refusal stays unconditional by contrast: a declaration
    naming a column the extract does not carry is a defect in the declaration
    rather than in any one row, and `_column` settles it before a single row is
    examined.

    Column reads are hoisted the same way `_measure_column` hoists them.
    """
    if contract.identity.transaction_id_unique_package_wide:
        return transaction_ids
    components = contract.identity.transaction_key_components
    if not components:
        return [None] * reading.frame.height
    columns = [
        _column(reading.frame, reading.labels, component) for component in components
    ]
    return [
        _joined_key(columns, index) if index in kept else None
        for index in range(reading.frame.height)
    ]


def _joined_key(
    columns: list[list[str | None]],
    index: int,
) -> str | None:
    """One row's composite key, or nothing where a component is blank.

    A composite with a hole is not a proven identity -- `RRA-003`: "Missing
    components or collisions refuse transactions, AOV, items per transaction,
    and attach rate" -- so a gap yields no key rather than being joined into a
    shorter one or reported as a silent zero.

    **Absent rather than raised, and the sentence above is why.** `RRA-003` names
    the four results a missing component refuses, and revenue, units and ASP are
    not among them: they need no transaction key, and `RRA-004`:97 requires
    "every refusal leaves facts whose own semantics and population remain
    independently proven". Raising took the whole package -- `_admitted_events`
    turns `EventsRefused` into a package-wide `FactsRefused` -- so a file with one
    incomplete key published nothing at all.

    This is `AdmittedEvents.monetary_refused`'s shape, chosen there for the same
    reason: "a field rather than an exception because the specification refuses
    monetary facts *and leaves count-only facts standing*. Raising would take
    both."
    """
    values: list[str] = []
    for column in columns:
        value = column[index]
        if value is None:
            return None
        values.append(value)
    return KEY_DELIMITER.join(_escaped(value) for value in values)


def _escaped(value: str) -> str:
    """One component, encoded so the join cannot forge a collision.

    Declared columns constrain column *names*; the values in them are arbitrary
    source data and may carry the delimiter. Unescaped, `("INV-1", "S1|X")` and
    `("INV-1|S1", "X")` join to the same key and two distinct transactions count
    as one -- the same magnitude of error as the repeated-invoice regression the
    composite exists to fix, and `RRA-003` makes a collision a refusal rather
    than a rounding difference.

    The escape character is escaped *first*, so an `INV\\|1` in the source
    cannot be read back as a delimiter. Transparent for values carrying neither
    character, which is why the key still reads exactly as
    `RRA-003` states it -- `INV-1|S1|2026-03-04|T1`.
    """
    return value.replace(KEY_ESCAPE, KEY_ESCAPE * 2).replace(
        KEY_DELIMITER, KEY_ESCAPE + KEY_DELIMITER
    )


def _assert_identity_proven(contract: SourceContract) -> None:
    """`RRA-003` requires either a unique event key or an explicit line-grain
    attestation; refuse the whole population when neither holds.

    `source_contract.build_source_contract` already enforces this at
    declaration time -- but `contract_from_document` deliberately does not
    re-validate a replayed declaration (see its own docstring), and
    `packages._stored_contract` reaches `admit_events` through exactly that
    path. So this check has to live here too, or a stored profile whose
    contract predates the rule -- or was constructed without going through
    the builder -- would be admitted with no identity proof at all.
    """
    identity = contract.identity
    if not identity.event_key_columns and not identity.unique_line_grain_attested:
        raise EventsRefused(
            "The source contract supplies neither event keys nor an "
            "attested unique line grain."
        )


def _raw_column(frame: pl.DataFrame, position: int) -> list[str | None]:
    """One column's cells as strings, materialized exactly once."""
    return frame.get_column(frame.columns[position]).cast(pl.String).to_list()


__all__ = [
    "AdmittedEvent",
    "AdmittedEvents",
    "EventsRefused",
    "admit_events",
]
