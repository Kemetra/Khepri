"""What a profile request carries, and what it is refused for.

The request body and the two refusals it can raise, together. `api` keeps the
route table; the question of whether a declaration proves what `RRA-003`
requires is answered here, beside the model that carries it, so a second
surface cannot answer it differently.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict

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
    """

    model_config = ConfigDict(extra="forbid")

    requested_semantics: list[str] = []
    source_contract: SourceContractBody


def governed_semantics(payload: ProfileRequestBody) -> set[str]:
    """The requested semantics, or a refusal naming them ungoverned."""
    requested = set(payload.requested_semantics)
    if not requested <= KNOWN_SEMANTICS:
        raise HTTPException(
            status_code=400,
            detail="Requested retail semantics are not governed.",
        )
    return requested


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
