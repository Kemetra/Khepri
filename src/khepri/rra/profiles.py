"""The request and response shapes of the profile surface.

Separated from `api` because `create_app` is a tracked CodeScene hotspot whose
gate refuses any change that lets it decline, and separated from `profile_api`
because these shapes are the surface's vocabulary rather than its routing: a
caller reading what a profile response contains should not have to read the
route that returns it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from khepri.rra.datasets import DatasetProfileRecord
from khepri.rra.source_contract import SourceContractBody


class ProfileRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_semantics: list[str] = []
    # Required, because `RRA-003` will not let admission infer what a column
    # means. A body without it is refused by validation rather than defaulted.
    source_contract: SourceContractBody


class ProfileColumnResponse(BaseModel):
    position: int
    safe_label: str
    inferred_type: str
    non_null_count: int
    null_count: int
    null_rate: str
    distinct_count: int
    minimum: str | None
    maximum: str | None
    date_format: str | None
    personal_data_risk: bool
    personal_data_signals: list[str]
    findings: list[str]


class ProfileMappingCandidateResponse(BaseModel):
    safe_label: str
    confidence: str
    evidence: list[str]


class ProfileMappingResponse(BaseModel):
    semantic: str
    requirement: str
    state: str
    candidates: list[ProfileMappingCandidateResponse]


class ProfileResponse(BaseModel):
    profile_id: str
    profile_version: str
    mapping_version: str
    profile_digest: str
    # The reading this profile was admitted under. Carried so a later coverage
    # manifest can be bound to it, and so a reader can ask what was declared.
    source_contract_digest: str
    row_count: int
    column_count: int
    admissible: bool
    reasons: list[str]
    findings: list[str]
    excluded_columns: list[str]
    columns: list[ProfileColumnResponse]
    mappings: list[ProfileMappingResponse]



def profile_response(record: DatasetProfileRecord) -> ProfileResponse:
    profile = record.document["profile"]
    mapping = record.document["mapping"]
    admissibility = record.document["admissibility"]
    labels = {column["position"]: column["safe_label"] for column in profile["columns"]}
    return ProfileResponse(
        profile_id=record.profile_id,
        profile_version=record.profile_version,
        mapping_version=record.mapping_version,
        profile_digest=record.profile_digest,
        source_contract_digest=str(record.document.get("source_contract_digest", "")),
        row_count=record.row_count,
        column_count=record.column_count,
        admissible=record.admissible,
        reasons=list(admissibility["reasons"]),
        findings=list(profile["findings"]),
        excluded_columns=[
            labels[position] for position in mapping["excluded_positions"]
        ],
        columns=[
            ProfileColumnResponse(
                position=column["position"],
                safe_label=column["safe_label"],
                inferred_type=column["inferred_type"],
                non_null_count=column["non_null_count"],
                null_count=column["null_count"],
                null_rate=column["null_rate"],
                distinct_count=column["distinct_count"],
                minimum=column["minimum"],
                maximum=column["maximum"],
                date_format=column["date_format"],
                personal_data_risk=column["personal_data_risk"],
                personal_data_signals=list(column["personal_data_signals"]),
                findings=list(column["findings"]),
            )
            for column in profile["columns"]
        ],
        mappings=[
            ProfileMappingResponse(
                semantic=entry["semantic"],
                requirement=entry["requirement"],
                state=entry["state"],
                candidates=[
                    ProfileMappingCandidateResponse(
                        safe_label=candidate["safe_label"],
                        confidence=candidate["confidence"],
                        evidence=list(candidate["evidence"]),
                    )
                    for candidate in entry["candidates"]
                ],
            )
            for entry in mapping["mappings"]
        ],
    )
