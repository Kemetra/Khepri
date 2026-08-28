"""What the operator declared their file to mean.

`RRA-003` draws one line and holds it everywhere: "Generic headers and observed
values never establish event kind, status, currency, gross/net basis, VAT
treatment, additivity, allocation, or coverage." Every one of those is a
statement *about* the data that the data cannot make about itself. A column
called `amount` holding `120.00` is equally consistent with VAT-inclusive gross,
VAT-exclusive net, a per-unit price, and a running total, and no amount of
inspection separates them.

So they are declared, once, in a recorded contract -- and the contract is what
later admission reads, never the headers.

**Declared or refused, never inferred.** Each declaration here is either an
explicitly mapped source column or a package-level constant. There is no third
option that guesses, which is why the constructor refuses rather than defaulting:
a default would be an inference wearing a configuration's clothes.

**A package-level declaration is a claim about the extract, not a convenience.**
`RRA-003` permits "all rows are sales" only when the extract contract excludes
returns, and "all rows are posted" only when it excludes void and cancelled
events. Declaring sale-only over a file that contains returns is a false
attestation, and the digest is what makes such a claim attributable later.

**The digest identifies a reading, not a file.** Two contracts differing in any
declaration must digest differently, because that is what lets a coverage
manifest refuse reuse against corrected semantics -- the same bytes, re-declared,
are a different admission.
"""

from __future__ import annotations

import pytest

from khepri.rra.source_contract import (
    SOURCE_CONTRACT_VERSION,
    BasisDeclaration,
    ContractAttribution,
    ContractRefused,
    EventDeclaration,
    IdentityDeclaration,
    SourceContract,
    build_source_contract,
)


def _event(**overrides: object) -> EventDeclaration:
    defaults: dict[str, object] = {
        "event_kind_column": None,
        "sale_only": True,
        "status_column": None,
        "posted_only": True,
        "currency_column": None,
        "currency_code": "EGP",
    }
    defaults.update(overrides)
    return EventDeclaration(**defaults)  # type: ignore[arg-type]


def _identity(**overrides: object) -> IdentityDeclaration:
    defaults: dict[str, object] = {
        "event_key_columns": ("line_id",),
        "unique_line_grain_attested": False,
        "transaction_id_column": "invoice_no",
        "transaction_key_components": (),
        "transaction_id_unique_package_wide": True,
    }
    defaults.update(overrides)
    return IdentityDeclaration(**defaults)  # type: ignore[arg-type]


def _basis(**overrides: object) -> BasisDeclaration:
    defaults: dict[str, object] = {
        "revenue_vat_exclusive": True,
        "revenue_is_net_of_returns": False,
        "units_are_integral": True,
        "cost_is_extended": True,
        "discount_is_additive": True,
    }
    defaults.update(overrides)
    return BasisDeclaration(**defaults)  # type: ignore[arg-type]


def _contract(
    *,
    contract_id: str = "sc-001",
    evidence: str = "operator attestation 2026-08-25",
    **overrides: object,
) -> SourceContract:
    defaults: dict[str, object] = {
        "attribution": ContractAttribution(contract_id=contract_id, evidence=evidence),
        "events": _event(),
        "identity": _identity(),
        "basis": _basis(),
    }
    defaults.update(overrides)
    return build_source_contract(**defaults)  # type: ignore[arg-type]


def test_a_contract_records_its_governed_version() -> None:
    assert _contract().contract_version == SOURCE_CONTRACT_VERSION


def test_two_identical_contracts_digest_identically() -> None:
    """Determinism, without which reuse checks would be noise."""
    assert _contract().digest == _contract().digest


def test_changing_any_declaration_changes_the_digest() -> None:
    """The property a coverage manifest's source-contract binding relies on.

    If a corrected declaration digested the same, an old manifest would still
    match and would admit completeness it never attested.
    """
    baseline = _contract().digest

    assert _contract(basis=_basis(revenue_vat_exclusive=False)).digest != baseline
    assert _contract(events=_event(currency_code="SAR")).digest != baseline
    assert (
        _contract(identity=_identity(transaction_id_column="receipt")).digest != baseline
    )


def test_event_kind_may_be_a_column_instead_of_a_declaration() -> None:
    contract = _contract(events=_event(event_kind_column="kind", sale_only=False))

    assert contract.events.event_kind_column == "kind"


def test_event_kind_neither_mapped_nor_declared_is_refused() -> None:
    """`RRA-003`: never inferred from generic headers or observed values."""
    with pytest.raises(ContractRefused):
        _contract(events=_event(event_kind_column=None, sale_only=False))


def test_status_neither_mapped_nor_declared_is_refused() -> None:
    with pytest.raises(ContractRefused):
        _contract(events=_event(status_column=None, posted_only=False))


def test_currency_neither_mapped_nor_declared_is_refused() -> None:
    with pytest.raises(ContractRefused):
        _contract(events=_event(currency_column=None, currency_code=None))


def test_declaring_both_a_column_and_a_constant_is_refused() -> None:
    """Two sources for one semantic is an unresolved contradiction.

    Silently preferring one would make the ignored declaration invisible, and
    an operator who set it would reasonably believe it applied.
    """
    with pytest.raises(ContractRefused):
        _contract(events=_event(event_kind_column="kind", sale_only=True))


@pytest.mark.parametrize("code", ["egp", "Egp", "EG", "EGPP", "", "12EGP"])
def test_a_currency_that_is_not_an_uppercase_iso_code_is_refused(code: str) -> None:
    """`RRA-003` requires exactly one normalized uppercase ISO 4217 code."""
    with pytest.raises(ContractRefused):
        _contract(events=_event(currency_column=None, currency_code=code))


def test_event_identity_may_be_an_attested_unique_line_grain() -> None:
    """`RRA-003`'s second proof: no key, but an explicit attestation."""
    contract = _contract(
        identity=_identity(event_key_columns=(), unique_line_grain_attested=True)
    )

    assert contract.identity.unique_line_grain_attested


def test_event_identity_neither_keyed_nor_attested_is_refused() -> None:
    with pytest.raises(ContractRefused):
        _contract(
            identity=_identity(event_key_columns=(), unique_line_grain_attested=False)
        )


def test_a_bare_transaction_id_without_proven_uniqueness_is_refused() -> None:
    """`RRA-003`: a bare identifier qualifies only when proven package-unique.

    Otherwise the canonical key must be an admitted composite. Accepting the
    bare column would let one identifier reused across stores or days collapse
    distinct transactions into one.
    """
    with pytest.raises(ContractRefused):
        _contract(
            identity=_identity(
                transaction_id_unique_package_wide=False,
                transaction_key_components=(),
            )
        )


def test_a_composite_transaction_key_admits_a_non_unique_identifier() -> None:
    """The same identifier, made unique by the fields that disambiguate it."""
    contract = _contract(
        identity=_identity(
            transaction_id_unique_package_wide=False,
            transaction_key_components=("invoice_no", "store", "business_date"),
        )
    )

    assert contract.identity.transaction_key_components == (
        "invoice_no",
        "store",
        "business_date",
    )


def test_a_composite_key_that_omits_the_source_identifier_is_refused() -> None:
    """`RRA-003`: the composite contains the source identifier and the rest."""
    with pytest.raises(ContractRefused):
        _contract(
            identity=_identity(
                transaction_id_unique_package_wide=False,
                transaction_key_components=("store", "business_date"),
            )
        )


def test_a_contract_without_evidence_is_refused() -> None:
    """An attestation nobody signed is not an attestation."""
    with pytest.raises(ContractRefused):
        _contract(evidence="   ")


def test_a_contract_without_an_identifier_is_refused() -> None:
    """`RRA-003` requires the attestation's own identity, not only its evidence.

    `build_source_contract` checks both halves of `ContractAttribution`, and the
    identifier is the half nothing here could reach: this module's `_contract`
    helper accepted an `evidence` override and hardcoded `contract_id`, so the
    guard at `source_contract.py:164` was proven only through the HTTP and
    profile layers. A contract attributed to `""` cannot be cited by anything
    downstream, which is what makes it a refusal rather than a blank field.
    """
    with pytest.raises(ContractRefused):
        _contract(contract_id="   ")


def test_a_blank_mapped_column_name_is_refused() -> None:
    """A whitespace column name reads as mapped and establishes nothing.

    `_assert_exactly_one` asks whether a column is `not None`, so `" "` satisfies
    the declare-exactly-once rule while naming no column any reader could
    resolve. `RRA-003` requires event kind to be "supplied by an explicitly
    mapped source column", and a blank string is not one -- it is the absence of
    a declaration wearing a declaration's shape, which is the inference this
    contract exists to refuse.
    """
    with pytest.raises(ContractRefused):
        _contract(events=_event(event_kind_column=" ", sale_only=False))


def test_a_blank_mapped_status_column_is_refused() -> None:
    """The same hole, proven on a second semantic so a one-field fix cannot pass."""
    with pytest.raises(ContractRefused):
        _contract(events=_event(status_column="", posted_only=False))


def test_supplying_both_event_identity_proofs_is_refused() -> None:
    """`RRA-003` offers two ways to prove event identity, "in exactly one of these ways".

    Supplying event keys *and* attesting unique line grain leaves it unrecorded
    which one admission relied on. That matters because the two fail differently:
    a repeated event key refuses the affected populations, while a line-grain
    attestation is falsified by a repeated canonical row signature. A contract
    admitting both records no answer to "what was relied on here?".
    """
    with pytest.raises(ContractRefused):
        _contract(
            identity=_identity(
                event_key_columns=("line_id",),
                unique_line_grain_attested=True,
            )
        )


def test_package_wide_uniqueness_without_a_transaction_identifier_is_refused() -> None:
    """Uniqueness asserted of nothing.

    `transaction_id_unique_package_wide=True` is the claim that lets a bare
    identifier serve as the canonical transaction key. With no identifier column
    it asserts the uniqueness of a value that does not exist, and
    `_assert_transaction_key` returns early on the flag alone -- so the composite
    requirement never runs and admission is left with no transaction identity at
    all.
    """
    with pytest.raises(ContractRefused):
        _contract(
            identity=_identity(
                transaction_id_column=None,
                transaction_id_unique_package_wide=True,
            )
        )
