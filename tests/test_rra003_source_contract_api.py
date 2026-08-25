"""The source contract arriving over the wire, and being bound to the profile.

`khepri.rra.source_contract` proves a contract can be built and refused. This
module proves the other half: that one actually reaches the profile route, that
a malformed one is refused there rather than deeper, and that its digest is
persisted with the profile so later admission can bind against it.

**`extra="forbid"`, and why it earns its place on this body.** A misspelled key
in a permissive model is silently dropped, so an operator who wrote
`revenue_vat_inclusive` would get the *default* basis and a report computed on a
declaration they did not make. `RRA-003` refuses inference, and a silently
ignored field is inference by another name.

**The digest is persisted, not recomputed on read.** Recomputing would make the
stored profile agree with whatever the current code produces, which is exactly
the drift the binding exists to detect.
"""

from __future__ import annotations

from datetime import timedelta

from tests.test_rra003_api import GOLDEN_CSV, NOW, Harness, harness


def _contract_payload(**overrides: object) -> dict[str, object]:
    """A complete, admissible declaration of the golden CSV."""
    payload: dict[str, object] = {
        "contract_id": "sc-001",
        "evidence": "operator attestation 2026-08-25",
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
    payload.update(overrides)
    return payload


def _ready(test: Harness) -> None:
    token = test.invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    test.client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    test.client.post(
        "/api/v1/beta/consent",
        json={"consent_version": "beta-privacy-v1"},
    )
    assert test.client.post("/api/v1/beta/uploads", content=GOLDEN_CSV).status_code == (
        201
    )


def _profile(test: Harness, contract: dict[str, object] | None) -> object:
    body: dict[str, object] = {"requested_semantics": []}
    if contract is not None:
        body["source_contract"] = contract
    return test.client.post("/api/v1/beta/profile", json=body)


def test_a_profile_with_a_complete_contract_is_accepted() -> None:
    test = harness()
    _ready(test)

    response = _profile(test, _contract_payload())

    assert response.status_code == 201


def test_a_profile_without_a_contract_is_refused() -> None:
    """`RRA-003` requires the declaration; it is not optional."""
    test = harness()
    _ready(test)

    response = _profile(test, None)

    assert response.status_code == 422


def test_an_unknown_field_in_the_contract_is_refused() -> None:
    """`extra="forbid"`, so a misspelling cannot silently take a default.

    An operator writing `revenue_vat_inclusive` would otherwise receive the
    default basis and a report computed on a declaration they never made.
    """
    test = harness()
    _ready(test)

    response = _profile(
        test,
        _contract_payload(revenue_vat_inclusive=True),
    )

    assert response.status_code == 422


def test_a_contradictory_declaration_is_refused_with_its_reason() -> None:
    """A column and a constant for one semantic, refused at the boundary."""
    test = harness()
    _ready(test)

    response = _profile(
        test,
        _contract_payload(event_kind_column="kind", sale_only=True),
    )

    assert response.status_code == 400


def test_a_currency_that_is_not_an_iso_code_is_refused() -> None:
    test = harness()
    _ready(test)

    response = _profile(test, _contract_payload(currency_code="egp"))

    assert response.status_code == 400


def test_the_accepted_contract_digest_reaches_the_profile_response() -> None:
    """Persisted provenance, readable by whoever asks what was declared."""
    test = harness()
    _ready(test)

    response = _profile(test, _contract_payload())

    assert response.json()["source_contract_digest"]


def test_the_same_declaration_is_idempotent() -> None:
    """An identical re-post is the same admission, so the profile is reused."""
    test = harness()
    _ready(test)

    first = _profile(test, _contract_payload())
    second = _profile(test, _contract_payload())

    assert first.status_code == 201
    assert second.status_code == 200
    assert (
        first.json()["source_contract_digest"]
        == second.json()["source_contract_digest"]
    )


def test_a_corrected_declaration_is_refused_rather_than_silently_reused() -> None:
    """The same bytes re-declared are a different admission, not a repeat.

    One profile is stored per upload, and it records the declaration it was
    admitted under. Handing the stored profile back for a corrected contract
    would answer under a declaration the caller has just replaced, and would
    leave any coverage manifest bound to semantics nobody asserts any more.

    So the second request conflicts. That refusal is the load-bearing behaviour:
    asserting merely that the digests differ would pass even if the corrected
    declaration were ignored, because the stored digest would simply be returned
    unchanged for both.
    """
    test = harness()
    _ready(test)

    accepted = _profile(test, _contract_payload())
    corrected = _profile(test, _contract_payload(revenue_vat_exclusive=False))

    assert accepted.status_code == 201
    assert corrected.status_code == 409
