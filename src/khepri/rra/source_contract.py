"""What the operator declared their file to mean.

`RRA-003` holds one line everywhere: "Generic headers and observed values never
establish event kind, status, currency, gross/net basis, VAT treatment,
additivity, allocation, or coverage." Each of those is a statement *about* the
data that the data cannot make about itself. A column called `amount` holding
`120.00` is equally consistent with VAT-inclusive gross, VAT-exclusive net, a
per-unit price, and a running total, and no amount of inspection separates them.

So they are declared once, in a recorded contract, and later admission reads the
contract rather than the headers.

**Declared or refused, with no third branch.** Every semantic here is either an
explicitly mapped column or a package-level constant. Nothing defaults, because
a default is an inference wearing a configuration's clothes -- and the defaulted
value would be indistinguishable, downstream, from one an operator chose.

**Both at once is a contradiction, not a preference.** A column *and* a constant
for the same semantic is refused rather than resolved by precedence: silently
preferring one makes the other invisible, and an operator who set it would
reasonably believe it applied.

**The digest identifies a reading, not a file.** Two contracts differing in any
declaration digest differently. That is precisely the property
`khepri.rra.coverage` relies on when it refuses a manifest whose source-contract
identity does not match the contract the events were admitted under: the same
bytes, re-declared, are a different admission and an old attestation says
nothing about it.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from khepri.rra.profiling import canonical_json

SOURCE_CONTRACT_VERSION = "rra003.source-contract.v1"

_ISO_CURRENCY_LENGTH = 3


class ContractRefused(ValueError):
    """A declaration that leaves a governed semantic unproven."""


@dataclass(frozen=True, slots=True)
class EventDeclaration:
    """Event kind, status, and currency: mapped, or declared for the package.

    `RRA-003` permits the package-level form only as a claim about the extract
    -- "all rows are sales" when the contract excludes returns, "all rows are
    posted" when it excludes void and cancelled events. The claim is recorded so
    it is attributable, not so it is convenient.
    """

    event_kind_column: str | None
    sale_only: bool
    status_column: str | None
    posted_only: bool
    currency_column: str | None
    currency_code: str | None


@dataclass(frozen=True, slots=True)
class IdentityDeclaration:
    """How one event, and one transaction, are told apart from another."""

    event_key_columns: tuple[str, ...]
    unique_line_grain_attested: bool
    transaction_id_column: str | None
    transaction_key_components: tuple[str, ...]
    transaction_id_unique_package_wide: bool


@dataclass(frozen=True, slots=True)
class BasisDeclaration:
    """What the measures are measured on. None of it is visible in a value."""

    revenue_vat_exclusive: bool
    revenue_is_net_of_returns: bool
    units_are_integral: bool
    cost_is_extended: bool
    discount_is_additive: bool


@dataclass(frozen=True, slots=True)
class SourceContract:
    """One recorded reading of one file."""

    contract_version: str
    contract_id: str
    evidence: str
    events: EventDeclaration
    identity: IdentityDeclaration
    basis: BasisDeclaration

    def as_document(self) -> dict[str, object]:
        """The canonical shape the digest is taken over."""
        return {
            "contract_version": self.contract_version,
            "contract_id": self.contract_id,
            "evidence": self.evidence,
            "events": {
                "event_kind_column": self.events.event_kind_column,
                "sale_only": self.events.sale_only,
                "status_column": self.events.status_column,
                "posted_only": self.events.posted_only,
                "currency_column": self.events.currency_column,
                "currency_code": self.events.currency_code,
            },
            "identity": {
                "event_key_columns": list(self.identity.event_key_columns),
                "unique_line_grain_attested": (
                    self.identity.unique_line_grain_attested
                ),
                "transaction_id_column": self.identity.transaction_id_column,
                "transaction_key_components": list(
                    self.identity.transaction_key_components
                ),
                "transaction_id_unique_package_wide": (
                    self.identity.transaction_id_unique_package_wide
                ),
            },
            "basis": {
                "revenue_vat_exclusive": self.basis.revenue_vat_exclusive,
                "revenue_is_net_of_returns": self.basis.revenue_is_net_of_returns,
                "units_are_integral": self.basis.units_are_integral,
                "cost_is_extended": self.basis.cost_is_extended,
                "discount_is_additive": self.basis.discount_is_additive,
            },
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.as_document()).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ContractAttribution:
    """Who declared this reading, and on what authority.

    Grouped with the identifier because an identifier without evidence names an
    attestation nobody signed, which `RRA-003` treats as no attestation at all.
    """

    contract_id: str
    evidence: str


def build_source_contract(
    *,
    attribution: ContractAttribution,
    events: EventDeclaration,
    identity: IdentityDeclaration,
    basis: BasisDeclaration,
) -> SourceContract:
    """One contract, or a refusal naming the semantic left unproven."""
    contract_id = attribution.contract_id
    evidence = attribution.evidence
    if not contract_id.strip():
        # The identifier a coverage manifest binds against. Left blank, every
        # unsigned contract shares one identity, and `coverage`'s refusal of a
        # manifest declared against a different reading stops discriminating.
        raise ContractRefused("A source contract must record its identifier.")
    if not evidence.strip():
        raise ContractRefused("A source contract must record its evidence.")
    _assert_events_declared(events)
    _assert_identity_declared(identity)
    return SourceContract(
        contract_version=SOURCE_CONTRACT_VERSION,
        contract_id=contract_id,
        evidence=evidence,
        events=events,
        identity=identity,
        basis=basis,
    )


def _is_mapped(column: str | None) -> bool:
    """Whether a declaration names a column a reader could actually resolve.

    `None` is the absence of a mapping and `" "` is the same absence wearing a
    mapping's shape: `RRA-003` requires each semantic to be "supplied by an
    explicitly mapped source column", and a blank string names none. Treating it
    as mapped would satisfy the declare-exactly-once rule while leaving the
    semantic inferred, which is the outcome that rule exists to prevent.
    """
    return column is not None and bool(column.strip())


def _assert_events_declared(events: EventDeclaration) -> None:
    """Event kind, status, and currency each proven exactly once."""
    _assert_exactly_one(
        _is_mapped(events.event_kind_column),
        events.sale_only,
        "event kind",
    )
    _assert_exactly_one(
        _is_mapped(events.status_column),
        events.posted_only,
        "status",
    )
    _assert_exactly_one(
        _is_mapped(events.currency_column),
        events.currency_code is not None,
        "currency",
    )
    if events.currency_code is not None:
        _assert_iso_currency(events.currency_code)


def _assert_exactly_one(mapped: bool, declared: bool, semantic: str) -> None:
    """Neither leaves it inferred; both leaves it contradictory."""
    if not mapped and not declared:
        raise ContractRefused(
            f"A source contract must map or declare {semantic}; it is never inferred."
        )
    if mapped and declared:
        raise ContractRefused(
            f"A source contract declares {semantic} by column or constant, not both."
        )


def _is_iso_currency(code: str) -> bool:
    """Three uppercase letters, which is the whole of ISO 4217's shape.

    Split from its refusal so the three conditions read as one named question
    rather than a compound conditional at the raise site.
    """
    if len(code) != _ISO_CURRENCY_LENGTH:
        return False
    if not code.isalpha():
        return False
    return code.isupper()


def _assert_iso_currency(code: str) -> None:
    """Exactly one normalized uppercase ISO 4217 code, per `RRA-003`."""
    if not _is_iso_currency(code):
        raise ContractRefused(
            "A declared currency must be one uppercase ISO 4217 code."
        )


def _assert_identity_declared(identity: IdentityDeclaration) -> None:
    """Event identity proven one of two ways, and a usable transaction key.

    `RRA-003` proves source-event identity "in exactly one of these ways", and
    both halves of that phrase bind. Neither leaves identity inferred. Both
    leaves it unrecorded which proof admission relied on, and the two fail
    differently -- a repeated event key refuses the affected populations, while a
    line-grain attestation is falsified by a repeated canonical row signature --
    so a contract carrying both answers no question a later reader can ask.
    """
    if not identity.event_key_columns and not identity.unique_line_grain_attested:
        raise ContractRefused(
            "A source contract must supply event keys or attest unique line grain."
        )
    if identity.event_key_columns and identity.unique_line_grain_attested:
        raise ContractRefused(
            "A source contract proves event identity by keys or by attested "
            "line grain, not both."
        )
    _assert_transaction_key(identity)


def _assert_transaction_key(identity: IdentityDeclaration) -> None:
    """A bare identifier only when proven unique; otherwise a composite.

    `RRA-003` requires the composite to contain the source identifier itself.
    A composite of store and date alone identifies a day's trading, not a
    transaction, and would collapse every sale in that day into one.
    """
    if identity.transaction_id_unique_package_wide:
        if not _is_mapped(identity.transaction_id_column):
            # Uniqueness asserted of a value that does not exist. The flag is
            # what lets a bare identifier serve as the canonical transaction
            # key, so accepting it without one returns early past the composite
            # requirement and leaves admission no transaction identity at all.
            raise ContractRefused(
                "A source contract cannot prove a transaction identifier unique "
                "without naming one."
            )
        return
    if not identity.transaction_key_components:
        raise ContractRefused(
            "A transaction identifier not proven unique needs a composite key."
        )
    if identity.transaction_id_column not in identity.transaction_key_components:
        raise ContractRefused(
            "A composite transaction key must contain the source identifier."
        )


def contract_from_document(document: dict[str, object]) -> SourceContract:
    """The contract a stored profile was admitted under, read back verbatim.

    **Rebuilt rather than re-declared.** `packages.py` re-derives the profile
    document and compares its digest to the stored one, refusing a package whose
    profile the current bytes and rules no longer produce. The contract is
    inside that document, so the rebuild has to reproduce *the same reading* --
    constructing a fresh one from defaults would change the digest and refuse
    every package, and re-validating the declaration here would refuse a stored
    contract whose rules have since tightened rather than reporting the
    mismatch the digest is there to report.

    So this is a faithful read of what was recorded, not a second admission.
    The declaration was validated when it was accepted; what is checked at
    rebuild time is the digest.
    """
    events = _mapping_at(document, "events")
    identity = _mapping_at(document, "identity")
    basis = _mapping_at(document, "basis")
    return SourceContract(
        contract_version=str(document["contract_version"]),
        contract_id=str(document["contract_id"]),
        evidence=str(document["evidence"]),
        events=EventDeclaration(
            event_kind_column=_optional_str(events["event_kind_column"]),
            sale_only=bool(events["sale_only"]),
            status_column=_optional_str(events["status_column"]),
            posted_only=bool(events["posted_only"]),
            currency_column=_optional_str(events["currency_column"]),
            currency_code=_optional_str(events["currency_code"]),
        ),
        identity=IdentityDeclaration(
            event_key_columns=tuple(identity["event_key_columns"]),
            unique_line_grain_attested=bool(identity["unique_line_grain_attested"]),
            transaction_id_column=_optional_str(identity["transaction_id_column"]),
            transaction_key_components=tuple(identity["transaction_key_components"]),
            transaction_id_unique_package_wide=bool(
                identity["transaction_id_unique_package_wide"]
            ),
        ),
        basis=BasisDeclaration(
            revenue_vat_exclusive=bool(basis["revenue_vat_exclusive"]),
            revenue_is_net_of_returns=bool(basis["revenue_is_net_of_returns"]),
            units_are_integral=bool(basis["units_are_integral"]),
            cost_is_extended=bool(basis["cost_is_extended"]),
            discount_is_additive=bool(basis["discount_is_additive"]),
        ),
    )


def _mapping_at(document: dict[str, object], key: str) -> dict[str, Any]:
    section = document[key]
    if not isinstance(section, dict):
        raise ContractRefused(f"A stored source contract is missing its {key}.")
    return section


def _optional_str(value: object) -> str | None:
    return None if value is None else str(value)


class SourceContractBody(BaseModel):
    """What the operator declares their file to mean, over the wire.

    `extra="forbid"` earns its place here rather than being a habit. A
    misspelled key in a permissive model is dropped silently, so an operator
    writing `revenue_vat_inclusive` would receive the *default* basis and a
    report computed on a declaration they never made. `RRA-003` refuses
    inference, and a silently ignored field is inference by another name.

    Flat over the wire and grouped in the domain: a JSON body is easier to post
    flat, while `khepri.rra.source_contract` groups the same declarations by
    what they mean. This model is the translation between the two.
    """

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    evidence: str
    event_kind_column: str | None = None
    sale_only: bool = False
    status_column: str | None = None
    posted_only: bool = False
    currency_column: str | None = None
    currency_code: str | None = None
    event_key_columns: list[str] = []
    unique_line_grain_attested: bool = False
    transaction_id_column: str | None = None
    transaction_key_components: list[str] = []
    transaction_id_unique_package_wide: bool = False
    revenue_vat_exclusive: bool = True
    revenue_is_net_of_returns: bool = False
    units_are_integral: bool = True
    cost_is_extended: bool = True
    discount_is_additive: bool = True

    def to_contract(self) -> SourceContract:
        """The governed contract, or `ContractRefused` naming what is unproven."""
        return build_source_contract(
            attribution=ContractAttribution(
                contract_id=self.contract_id,
                evidence=self.evidence,
            ),
            events=EventDeclaration(
                event_kind_column=self.event_kind_column,
                sale_only=self.sale_only,
                status_column=self.status_column,
                posted_only=self.posted_only,
                currency_column=self.currency_column,
                currency_code=self.currency_code,
            ),
            identity=IdentityDeclaration(
                event_key_columns=tuple(self.event_key_columns),
                unique_line_grain_attested=self.unique_line_grain_attested,
                transaction_id_column=self.transaction_id_column,
                transaction_key_components=tuple(self.transaction_key_components),
                transaction_id_unique_package_wide=(
                    self.transaction_id_unique_package_wide
                ),
            ),
            basis=BasisDeclaration(
                revenue_vat_exclusive=self.revenue_vat_exclusive,
                revenue_is_net_of_returns=self.revenue_is_net_of_returns,
                units_are_integral=self.units_are_integral,
                cost_is_extended=self.cost_is_extended,
                discount_is_additive=self.discount_is_additive,
            ),
        )
