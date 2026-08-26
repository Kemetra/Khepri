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
from datetime import date
from decimal import Decimal, InvalidOperation

import polars as pl

from khepri.rra.mapping import (
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


class EventsRefused(ValueError):
    """A population that cannot be proven from what the extract declared."""


@dataclass(frozen=True, slots=True)
class AdmittedEvent:
    """One normalized retail event, as `RRA-003` defines one."""

    day: date | None
    event_kind: str
    status: str
    revenue: Decimal | None
    units: int | None
    transaction_id: str | None


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
        """Distinct canonical transactions, also count-only."""
        return len({event.transaction_id for event in self.events if event.transaction_id})


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
    events = [
        AdmittedEvent(
            day=None,
            event_kind=kinds[index],
            status=statuses[index],
            revenue=(
                None
                if monetary_refused
                else _measure(frame, mapping, SEMANTIC_REVENUE, index)
            ),
            units=_unit_count(frame, mapping, index),
            transaction_id=_transaction_id(frame, labels, contract, index),
        )
        for index in kept
    ]
    excluded = frame.height - len(kept)
    return AdmittedEvents(
        events=tuple(events),
        currency=currency,
        monetary_refused=monetary_refused,
        excluded_count=excluded,
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


def _measure(
    frame: pl.DataFrame,
    mapping: RetailMapping,
    semantic: str,
    index: int,
) -> Decimal | None:
    """One row's value for a mapped measure, or `None` where none is resolved."""
    column = mapping.for_semantic(semantic).column
    if column is None:
        return None
    raw = frame.get_column(frame.columns[column.position]).cast(pl.String).to_list()[index]
    if raw is None or not str(raw).strip():
        return None
    try:
        return Decimal(str(raw).strip())
    except InvalidOperation:
        return None


def _unit_count(frame: pl.DataFrame, mapping: RetailMapping, index: int) -> int | None:
    value = _measure(frame, mapping, SEMANTIC_UNITS, index)
    return None if value is None else int(value)


def _transaction_id(
    frame: pl.DataFrame,
    labels: dict[str, int],
    contract: SourceContract,
    index: int,
) -> str | None:
    declared = contract.identity.transaction_id_column
    if declared is None or declared not in labels:
        return None
    raw = (
        frame.get_column(frame.columns[labels[declared]]).cast(pl.String).to_list()[index]
    )
    return None if raw is None else str(raw).strip() or None


__all__ = [
    "AdmittedEvent",
    "AdmittedEvents",
    "EventsRefused",
    "admit_events",
]
