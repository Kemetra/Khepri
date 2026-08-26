"""What a profile request carries, and what it is refused for.

The request body and the two refusals it can raise, together. `api` keeps the
route table; the question of whether a declaration proves what `RRA-003`
requires is answered here, beside the model that carries it, so a second
surface cannot answer it differently.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

from khepri.rra.coverage import ManifestBinding, ManifestRefused
from khepri.rra.coverage_request import CoverageManifestBody
from khepri.rra.mapping import KNOWN_SEMANTICS
from khepri.rra.source_contract import (
    ContractRefused,
    SourceContract,
    SourceContractBody,
)


class ProfileRequestBody(BaseModel):
    """What a caller asks for, and what they declare their file to mean.

    **The contract is required, not defaulted.** `RRA-003` holds that "generic
    headers and observed values never establish event kind, status, currency,
    gross/net basis, VAT treatment, additivity, allocation, or coverage", and
    `rra003.mapping.v3` is the version that makes that binding on the ingestion
    path. A default contract would be indistinguishable downstream from one the
    operator chose, so there is no default: a request without a declaration is
    refused rather than profiled on inferred semantics.

    **The coverage manifest is optional, and the asymmetry is deliberate.**
    `RRA-003` requires an attestation for completeness-*dependent* comparisons
    and refuses those comparisons without one -- it does not refuse the profile.
    A dataset profiled to see what it contains needs no attestation; the same
    dataset compared period over period does. So an absent manifest is an
    ordinary profile whose completeness questions refuse, which is exactly what
    the clause says, rather than a rejected upload.

    It arrives here, with the declaration, because the stored profile document is
    content-addressed and an attestation added later would have to rewrite the
    digest every published package cites. See `datasets.build_document`.
    """

    model_config = ConfigDict(extra="forbid")

    requested_semantics: list[str] = []
    source_contract: SourceContractBody
    coverage_manifest: CoverageManifestBody | None = None


def governed_semantics(payload: ProfileRequestBody) -> set[str]:
    """The requested semantics, or a refusal naming them ungoverned."""
    requested = set(payload.requested_semantics)
    if not requested <= KNOWN_SEMANTICS:
        raise HTTPException(
            status_code=400,
            detail="Requested retail semantics are not governed.",
        )
    return requested


def declared_attestation(payload: ProfileRequestBody) -> CoverageManifestBody | None:
    """The attested manifest, checked for structural usability before it is used.

    **Refused here rather than at the route**, for the reason this module exists:
    `api` keeps the route table, and whether a declaration proves what `RRA-003`
    requires is answered beside the model that carries it. Adding a fourth
    `except` clause to the profile route would also have made `create_app` --
    already every complexity threshold this project measures -- measurably worse.

    **400 rather than 422**, exactly as `declared_contract` below. The body is
    well-formed and every field is the right type, so this is not a schema
    violation. What is wrong is the *attestation* -- a window it does not span, a
    day claimed both shut and missing, no scope at all -- and `RRA-003` gives
    that its own refusal naming what to fix.

    The manifest is validated against a placeholder binding, because the real
    binding is not known until the file has been read: `input_digest` comes from
    the upload and `source_contract_digest` from the accepted declaration. Only
    the structural rules are asked here, and they are independent of the binding.
    The binding itself is applied in `datasets`, and checked at use time in
    `session_completeness` -- which is the check that matters and the one a
    write-time-only validation would leave unproven.
    """
    attestation = payload.coverage_manifest
    if attestation is None:
        return None
    try:
        attestation.to_manifest(binding=_UNBOUND)
    except ManifestRefused as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return attestation


#: A placeholder binding, used only to ask the structural questions. Never
#: stored: `datasets.manifest_binding` builds the real one from the admission,
#: which is what makes the use-time identity check able to fail at all.
_UNBOUND = ManifestBinding(
    input_digest="",
    source_contract_digest="",
    timezone="UTC",
)


def declared_contract(payload: ProfileRequestBody) -> SourceContract:
    """The governed contract, or a refusal naming the semantic left unproven.

    **400 rather than 422**, and the distinction is the point: the body is
    well-formed and every field is the right type, so this is not a schema
    violation. What is wrong is the *declaration* -- a semantic left unproven,
    or proven twice -- and `RRA-003` gives that its own refusal naming what to
    fix. A 422 would tell an operator their JSON was malformed when it was not.
    """
    try:
        return payload.source_contract.to_contract()
    except ContractRefused as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
