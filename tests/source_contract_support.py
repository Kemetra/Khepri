"""One admissible source contract, for every test that must post a profile.

`RRA-003` makes the declaration required, so every caller of
`POST /api/v1/beta/profile` now supplies one. Most of those tests are about
something else entirely -- idempotence, races, byte-equivalent reruns -- and
would be made unreadable by eighteen inline keys that never vary.

Kept in a support module rather than a fixture so a test can vary one field
against the same baseline, which is how the contract's own refusals are proven.
"""

from __future__ import annotations

GOLDEN_SOURCE_CONTRACT: dict[str, object] = {
    "contract_id": "sc-golden",
    "evidence": "test attestation",
    "event_kind_column": None,
    "sale_only": True,
    "status_column": None,
    "posted_only": True,
    "currency_column": None,
    "currency_code": "EGP",
    "event_key_columns": ["invoice_no"],
    "unique_line_grain_attested": False,
    "transaction_id_column": "invoice_no",
    "transaction_key_components": [],
    "transaction_id_unique_package_wide": True,
    "revenue_vat_exclusive": True,
    "revenue_is_net_of_returns": False,
    "units_are_integral": True,
    "cost_is_extended": True,
    "discount_is_additive": True,
}


def source_contract(**overrides: object) -> dict[str, object]:
    """The golden declaration, with any field replaced."""
    payload = dict(GOLDEN_SOURCE_CONTRACT)
    payload.update(overrides)
    return payload


def profile_body(
    *,
    requested_semantics: list[str] | None = None,
    **overrides: object,
) -> dict[str, object]:
    """A complete profile request body."""
    return {
        "requested_semantics": requested_semantics or [],
        "source_contract": source_contract(**overrides),
    }


def golden_contract_digest() -> str:
    """The digest of `GOLDEN_SOURCE_CONTRACT`, as the route computes it.

    Derived through the production builder rather than pinned as a literal, so
    a change to the contract's canonical shape moves this with it instead of
    leaving a stale constant that silently stops matching.
    """
    from khepri.rra.api import SourceContractBody

    return SourceContractBody(**GOLDEN_SOURCE_CONTRACT).to_contract().digest
