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

from collections.abc import Iterator
from contextlib import contextmanager

from khepri.rra import facts as facts_module
from khepri.rra import mapping as mapping_module
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
    transaction_key_components: tuple[str, ...] = (),
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
            transaction_key_components=transaction_key_components,
            # A composite is declared exactly when one is supplied. `RRA-003`
            # admits the bare identifier "only when its recorded source contract
            # proves package-wide uniqueness", so a fixture whose file reuses an
            # invoice number across stores must not make that claim -- the
            # declaration would be false of the extract it describes.
            transaction_id_unique_package_wide=not transaction_key_components,
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

#: For an extract where one invoice number is reused across stores, which is the
#: ordinary case rather than a corruption: each POS numbers its own receipts from
#: one. `RRA-003` requires the canonical key to be "an admitted composite
#: containing the source identifier and every field required for uniqueness,
#: normally store, business date, and terminal or register".
REPEATED_INVOICE_CONTRACT = sale_only_contract(
    contract_id="src_test_repeated_invoice",
    # Invoice, store and business date: the three this extract actually
    # carries. `RRA-003` says the composite holds "every field required for
    # uniqueness, **normally** store, business date, and terminal or register"
    # -- normally, not invariably, and a component naming a column the file
    # lacks is refused at admission rather than silently skipped.
    transaction_key_components=(DEFAULT_TRANSACTION_COLUMN, "store", "date"),
)


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


#: The one package triple `versions.ADMITTED_PACKAGE_PAIRS` has always admitted.
#: Named here so a test pins to a governed combination rather than to a literal
#: it invented, and so the identifiers appear once instead of in thirty files.
PUBLISHED_MAPPING_VERSION = "rra003.mapping.v2"
#: The package half of that same triple. **Both are pinned together**, because
#: the admitted identity is a triple and `facts._build` reads `PACKAGE_VERSION`
#: from its own module rather than taking it from the mapping. Pinning the
#: mapping alone left these modules combining `(mapping.v2, package.v3,
#: formula.v1)` the moment `V-package` moved the package constant -- a pairing
#: nothing ever admitted, and rightly so.
PUBLISHED_PACKAGE_VERSION = "rra004.package.v2"


@contextmanager
def published_mapping_identity() -> Iterator[None]:
    """Build mappings under the published identity for the duration of a block.

    **Why patching the constant, and not restamping the object.** `facts._build`
    proves provenance by re-deriving the mapping -- `build_mapping(profile,
    contract=...) != mapping` refuses -- so a mapping restamped after
    construction fails that check as "not derived from the supplied profile".
    That guard is correct and worth keeping, which leaves exactly one honest way
    to build under an older identity: stamp it at the source, so the object and
    its re-derivation agree.

    **Why a test pins at all.** `build_mapping` stamps `MAPPING_VERSION`, so when
    a publication commit moves that constant every package built from a fresh
    mapping meets an unlisted `(mapping, package, formula)` triple and refuses --
    correctly, because the successor package and formula are not published yet. A
    module whose subject is comparison, basket, rendering or narrative was never
    about that gate, and rewriting it to assert the refusal would delete the only
    proof of the behaviour it was written for. `RRA-004` keeps historical
    packages valid under their recorded versions, so building under the admitted
    triple is the governed reading of an old identity rather than a way around
    the gate.

    A module whose subject *is* the gate must not use this. Those assert the
    refusal directly, against hardcoded triples, in
    `test_rra004_version_gate_wiring.py` and `test_rra004_version_compatibility.py`.
    """
    original_mapping = mapping_module.MAPPING_VERSION
    original_package = facts_module.PACKAGE_VERSION
    mapping_module.MAPPING_VERSION = PUBLISHED_MAPPING_VERSION
    facts_module.PACKAGE_VERSION = PUBLISHED_PACKAGE_VERSION
    try:
        yield
    finally:
        mapping_module.MAPPING_VERSION = original_mapping
        facts_module.PACKAGE_VERSION = original_package


#: Marks an assertion that states the *refusal window* rather than the outcome
#: the test was written for. Grep this name to find every one of them.
#:
#: **`V-concentration` must flip each back.** These tests drive a path that
#: builds its package through the real route or a production helper, where no
#: pin can reach -- `packages.py` and `benchmark_trial.py` call `build_mapping`
#: themselves. While the window is open the honest outcome is the governed
#: refusal, and the ledger's §6.1 criterion says so: a browser upload reaches
#: "the governed bilingual refusal stating which version pairing was refused",
#: not a report. The last family commit empties the refusing set, at which point
#: each of these states its original claim again.
REFUSAL_WINDOW = "CAL1 refusal window: V-concentration restores this assertion"


def mixed_currency_contract(
    *,
    contract_id: str = "src_mixed_currency",
) -> SourceContract:
    """A contract mapping currency to a column rather than declaring one.

    `RRA-003` admits a package-level currency declaration as a claim about the
    extract, so declaring `EGP` over a file carrying two currencies would be a
    false attestation. Mapping the column instead lets admission read what is
    really there and refuse the monetary facts, which is the state
    `currency_not_declared` exists to disclose.
    """
    return build_source_contract(
        attribution=ContractAttribution(
            contract_id=contract_id,
            evidence="Test fixture: an extract carrying more than one currency.",
        ),
        events=EventDeclaration(
            event_kind_column=None,
            sale_only=True,
            status_column=None,
            posted_only=True,
            currency_column="currency",
            currency_code=None,
        ),
        identity=IdentityDeclaration(
            event_key_columns=(),
            unique_line_grain_attested=True,
            transaction_id_column=DEFAULT_TRANSACTION_COLUMN,
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
