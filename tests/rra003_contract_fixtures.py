"""The source contract a test needs to build a mapping under `mapping.v3`.

`rra003.mapping.v3` makes the declaration required: `build_mapping` takes a
`SourceContract` because `RRA-003` refuses to establish event kind, status,
currency, basis, or identity from headers. Every test that builds a mapping
therefore needs one, and hand-rolling 26 of them would spread the same
declaration across the suite with 26 chances to drift.

**What this fixture is for, and what it is not.** It supplies a *complete,
unremarkable* declaration for tests whose subject is something else -- a chart, a
worksheet, a narrative, a growth decomposition. Those tests were written against
`mapping.v2`'s header inference and their subject has not changed, so the
contract they get should be the one that leaves their behaviour as it was.

Tests whose subject **is** the contract -- refusals, digest binding, admission --
build their own declarations inline and must not use this. A shared fixture that
grew a special case for each of them would stop being unremarkable, and the
admission tests would start proving properties of this file.
"""

from __future__ import annotations

from khepri.rra.source_contract import (
    BasisDeclaration,
    ContractAttribution,
    EventDeclaration,
    IdentityDeclaration,
    SourceContract,
    SourceContractBody,
    build_source_contract,
)

#: The transaction column the retail fixtures across this suite actually carry.
#: `mapping.py` resolves several spellings -- `invoice`, `invoice_no`,
#: `transaction_id` -- and a contract naming one the file lacks leaves the
#: inferred resolution standing rather than fabricating a column, so this is a
#: default rather than an assertion about any particular fixture.
DEFAULT_TRANSACTION_COLUMN = "invoice_no"


def sale_only_contract(
    *,
    contract_id: str = "src_test_contract",
    transaction_id_column: str | None = DEFAULT_TRANSACTION_COLUMN,
    currency_code: str = "EGP",
) -> SourceContract:
    """A package-level declaration: all rows are posted sales in one currency.

    `RRA-003` permits the package-level form as a claim about the extract --
    "all rows are sales" when the contract excludes returns, "all rows are
    posted" when it excludes void and cancelled events. That is what the retail
    fixtures in this suite are, so the claim is true of them and recorded rather
    than inferred.

    `unique_line_grain_attested` rather than named event-key columns, for the
    same reason: these fixtures are one row per line with no explicit event key,
    which is exactly the attestation `RRA-003` admits in place of one.
    """
    return build_source_contract(
        attribution=ContractAttribution(
            contract_id=contract_id,
            evidence="Test fixture: declared for a synthetic retail extract.",
        ),
        events=EventDeclaration(
            event_kind_column=None,
            sale_only=True,
            status_column=None,
            posted_only=True,
            currency_column=None,
            currency_code=currency_code,
        ),
        identity=IdentityDeclaration(
            event_key_columns=(),
            unique_line_grain_attested=True,
            transaction_id_column=transaction_id_column,
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


#: One shared instance for the common case. Frozen and slotted, so sharing it is
#: safe and keeps every unremarkable caller digesting identically.
TEST_CONTRACT = sale_only_contract()


def contract_payload(**overrides: object) -> dict[str, object]:
    """The same declaration, in the flat shape the profile route accepts.

    `SourceContractBody` is flat over the wire and grouped in the domain, so a
    test driving the HTTP route needs the flat form. Built from the model rather
    than hand-written so the two cannot drift, and validated on the way out so a
    malformed override fails here rather than as an indistinguishable 4xx.
    """
    contract = sale_only_contract()
    body = SourceContractBody(
        contract_id=contract.contract_id,
        evidence=contract.evidence,
        sale_only=contract.events.sale_only,
        posted_only=contract.events.posted_only,
        currency_code=contract.events.currency_code,
        unique_line_grain_attested=contract.identity.unique_line_grain_attested,
        transaction_id_column=contract.identity.transaction_id_column,
        transaction_id_unique_package_wide=(
            contract.identity.transaction_id_unique_package_wide
        ),
    )
    payload = {**body.model_dump(), **overrides}
    SourceContractBody(**payload).to_contract()
    return payload


def profile_payload(**overrides: object) -> dict[str, object]:
    """A complete `POST /api/v1/beta/profile` body.

    The route requires a declaration under `rra003.mapping.v3`, so `json={}` --
    what these tests posted under v2 -- is now a 422. This keeps the request
    minimal and the contract unremarkable, so a test about profiling stays about
    profiling.
    """
    return {
        "requested_semantics": [],
        "source_contract": contract_payload(),
        **overrides,
    }
