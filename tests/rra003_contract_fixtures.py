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
#: The formula third of the triple. Pinned differently from the other two, and
#: the difference is the whole reason this helper exists: `build_fact_package`
#: takes `formula_version` as a keyword argument whose default is **bound at
#: import**, so patching the module attribute cannot reach it. The other two are
#: read at call time -- the mapping off the object it is handed, the package off
#: its own module -- so three constants need three mechanisms.
PUBLISHED_FORMULA_VERSION = "rra004.formula.v1"


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
    original_formula = facts_module.FORMULA_VERSION
    original_defaults = facts_module.build_fact_package.__kwdefaults__
    mapping_module.MAPPING_VERSION = PUBLISHED_MAPPING_VERSION
    facts_module.PACKAGE_VERSION = PUBLISHED_PACKAGE_VERSION
    # Both the constant and the bound default, because `build_fact_package`
    # captured its `formula_version` default at import while `_build` compares
    # against the module attribute at call time. Moving one without the other
    # trips the builder's own "not implemented by this package builder" guard,
    # which is right to refuse: a builder implements one formula version, and a
    # caller asking for another would get this arithmetic under that identity.
    facts_module.FORMULA_VERSION = PUBLISHED_FORMULA_VERSION
    facts_module.build_fact_package.__kwdefaults__ = {
        **(original_defaults or {}),
        "formula_version": PUBLISHED_FORMULA_VERSION,
    }
    try:
        yield
    finally:
        mapping_module.MAPPING_VERSION = original_mapping
        facts_module.PACKAGE_VERSION = original_package
        facts_module.FORMULA_VERSION = original_formula
        facts_module.build_fact_package.__kwdefaults__ = original_defaults


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


def oracle_contract(
    *,
    contract_id: str = "src_oracle",
    transaction_key_components: tuple[str, ...] = (),
    status_column: str | None = "status",
) -> SourceContract:
    """The contract that honestly describes `tests/rra_calculation_oracle.to_csv`.

    The oracle bridge emits `event_kind` and `status` columns -- `RRA-003`
    requires every row to prove both and forbids establishing either from
    observed values -- and carries no currency column, so the currency is a
    package-level declaration.

    Kept beside the other fixtures rather than in the oracle, because the oracle
    computes no expectation and states no declaration: it renders rows, and what
    those rows are declared to *mean* is the consumer's recorded reading.
    """
    return build_source_contract(
        attribution=ContractAttribution(
            contract_id=contract_id,
            evidence="Test fixture: declared for the independent calculation oracle.",
        ),
        events=EventDeclaration(
            event_kind_column="event_kind",
            sale_only=False,
            status_column=status_column,
            posted_only=status_column is None,
            currency_column=None,
            currency_code="EGP",
        ),
        identity=IdentityDeclaration(
            event_key_columns=(),
            unique_line_grain_attested=True,
            transaction_id_column=DEFAULT_TRANSACTION_COLUMN,
            transaction_key_components=transaction_key_components,
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


#: For the `RRA-009` rich fixture, which carries a mapped `event_kind` column so
#: its posted return is admitted as one. Every other declaration matches
#: `TEST_CONTRACT`; only the event kind moves from a package-level claim to a
#: column, because a claim of "all rows are sales" would be false of it.
RICH_CONTRACT = oracle_contract(
    contract_id="src_rra009_rich",
    status_column=None,
)


def attesting_manifest(
    *,
    content: bytes,
    contract: SourceContract,
    days: tuple,
    scope: str = "all-stores",
    covered: tuple | None = None,
):
    """A manifest attesting the span of `days` for one aggregate scope.

    `RRA-008` refuses completeness-dependent comparison "without an
    authoritative valid manifest", so a fixture whose subject is comparison
    arithmetic has to attest its own coverage -- otherwise every case refuses on
    coverage before reaching the arithmetic it was written to prove.

    `covered` defaults to every day from the first to the last of `days`, which
    is the ordinary case: a manifest must span its own declared window, and a
    day carrying no sale is covered rather than missing whenever the operator
    attested it. Passing `covered` explicitly produces the day-`1..k` prefix
    `RRA-008` admits for an incomplete current period.
    """
    import hashlib
    from datetime import date as _date

    from khepri.rra.coverage import (
        ManifestBinding,
        ManifestExceptions,
        ManifestWindow,
        build_coverage_manifest,
    )

    if covered is None:
        first, last = min(days), max(days)
        attested = tuple(
            _date.fromordinal(first.toordinal() + offset)
            for offset in range((last - first).days + 1)
        )
    else:
        attested = covered
    return build_coverage_manifest(
        binding=ManifestBinding(
            input_digest=hashlib.sha256(content).hexdigest(),
            source_contract_digest=contract.digest,
            timezone="Africa/Cairo",
            attested_by="Test fixture: operator attestation.",
        ),
        window=ManifestWindow(
            covered_start=min(attested),
            covered_end=max(attested),
            aggregate_scope=scope,
            store_roster=(),
            covered_pairs=tuple((scope, day) for day in attested),
        ),
        exceptions=ManifestExceptions(
            event_kinds=("sale", "return"),
            statuses=("posted",),
        ),
    )


def manifest_for_csv(content: bytes, contract: SourceContract):
    """A manifest attesting every day spanned by a CSV whose first column is a date.

    Comparison under `rra008.comparison.v2` refuses a window the manifest does
    not prove, so any fixture wanting a comparison section must attest its own
    coverage. Reading the dates back out of the rendered bytes keeps the
    attestation and the extract in step: a fixture that gains a row gains its
    coverage, and one that never carried dates gets no manifest rather than a
    fabricated one.
    """
    from datetime import date as _date

    days = []
    for line in content.decode().strip().split("\n")[1:]:
        head = line.split(",")[0].strip()
        try:
            days.append(_date.fromisoformat(head))
        except ValueError:
            continue
    if not days:
        return None
    return attesting_manifest(content=content, contract=contract, days=tuple(days))


def landed_sections(formula_version: str | None = None) -> frozenset[str]:
    """Which analysis sections publish, read from the gate itself.

    The `RRA-008` families land one commit at a time and each opens its own gate,
    so between `V-formula` and `V-concentration` the set of publishing sections
    is a moving target. A test asserting a fixed set has to be edited once per
    family commit, and a missed edit reads as a regression rather than as the
    designed window.

    **Pass the formula version the package was actually built under.** A module
    pinned to the published predecessor builds packages carrying
    `rra004.formula.v1`, and the gate asks about *that* pairing -- so a pinned
    bundle publishes the families still at `v1` and refuses the ones that have
    moved to `v2`, which is the exact inverse of the unpinned answer.

    **Deliberately not for the two gate-subject modules.** A gate test that
    consults the gate's own table passes whatever that table says, which is the
    tautology those modules exist to avoid.
    """
    from khepri.rra import bundle
    from khepri.rra.facts import FORMULA_VERSION
    from khepri.rra.versions import admits_family

    combined = FORMULA_VERSION if formula_version is None else formula_version
    return frozenset(
        section_id
        for section_id, family in bundle._FAMILIES.items()
        if admits_family(formula_version=combined, family_version=family.version())
    )


def refusal_prose(bundle, language: str) -> frozenset[str]:
    """Every governed refusal message this bundle's refused sections state.

    **Why this belongs in shared fixtures rather than in each test.** A refused
    section is not an absent one: it still renders, carrying customer prose that
    says why. So any assertion of the form "every cell is a figure value or a
    governed label" has to admit that prose too -- and which sections are
    refused moves every time a governed version moves, which under a staged
    publication sequence is every commit.

    Written once here so a version move costs one recomputation rather than one
    edit per surface. Pairs with `landed_sections`: that one answers *which*
    sections publish, this one answers *what a refused one says*.
    """
    from khepri.rra.rendering.wording import section_refusal_message

    return frozenset(
        section_refusal_message(section.section_id, section.reason, language)
        for section in bundle.sections
        if section.reason
    )


def publishing_sections(bundle) -> frozenset[str]:
    """The sections of this bundle that actually state something.

    Read off the bundle rather than from the gate, so it stays true of a section
    refused for its *own* reasons -- a single-period file has no prior window to
    compare, which is a data fact rather than a version one. A test asserting
    "every section carries metrics" means every section that publishes.
    """
    return frozenset(
        section.section_id for section in bundle.sections if not section.reason
    )
