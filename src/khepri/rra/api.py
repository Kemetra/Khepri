from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import Cookie, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from khepri.rra.admissibility import ReportRequest
from khepri.rra.datasets import (
    DatasetProfileRecord,
    ProfilingService,
    UploadNotFound,
)
from khepri.rra.deletion import DeletionRetryRequired, DeletionService
from khepri.rra.intake import (
    IntakeRejected,
    IntakeService,
    StoragePolicyViolation,
    UploadAlreadyExists,
    UploadMetadata,
    UploadTooLarge,
)
from khepri.rra.mapping import KNOWN_SEMANTICS
from khepri.rra.packages import (
    FactPackageRecord,
    FactPackageService,
    PackageCorrupted,
    PackageRefused,
    ProfileNotFound,
)
from khepri.rra.profiling import ProfileRejected
from khepri.rra.sessions import (
    ConsentRequired,
    CrossSessionAccessDenied,
    InvitationRejected,
    InvitationService,
    SessionExpired,
)

SESSION_COOKIE = "khepri_beta_session"
ConsentVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class RedeemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str


class RedeemResponse(BaseModel):
    content_expires_at: datetime
    consent_required: bool


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consent_version: ConsentVersion


class UploadResponse(BaseModel):
    upload_id: str
    size_bytes: int
    sha256_hex: str
    media_type: str
    expires_at: datetime


class ProfileRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_semantics: list[str] = []


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
    row_count: int
    column_count: int
    admissible: bool
    reasons: list[str]
    findings: list[str]
    excluded_columns: list[str]
    columns: list[ProfileColumnResponse]
    mappings: list[ProfileMappingResponse]


class FactResponse(BaseModel):
    fact_id: str
    metric: str
    value: str
    precision: int
    unit_kind: str
    inputs: list[str]
    caveats: list[str]
    citation_id: str


class FactAggregateResponse(BaseModel):
    fact_id: str
    metric: str
    measure: str
    unit_kind: str
    precision: int
    scope: str
    citation_id: str
    caveats: list[str]
    buckets: list[dict[str, object]]


class FactRefusalResponse(BaseModel):
    metric: str
    reason: str


class FactPackageResponse(BaseModel):
    package_id: str
    package_version: str
    formula_version: str
    mapping_version: str
    profile_digest: str
    profile_document_digest: str
    package_digest: str
    source_sha256_hex: str
    row_count: int
    monetary_precision: int
    caveats: list[str]
    facts: list[FactResponse]
    series: list[FactAggregateResponse]
    comparisons: list[FactAggregateResponse]
    refusals: list[FactRefusalResponse]


def create_app(
    *,
    service: InvitationService,
    clock: Callable[[], datetime],
    intake_service: IntakeService | None = None,
    deletion_service: DeletionService | None = None,
    profiling_service: ProfilingService | None = None,
    package_service: FactPackageService | None = None,
) -> FastAPI:
    app = FastAPI(title="Khepri RRA", docs_url=None, redoc_url=None)

    @app.post(
        "/api/v1/beta/sessions/redeem",
        response_model=RedeemResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def redeem_invitation(payload: RedeemRequest, response: Response) -> RedeemResponse:
        try:
            session = service.redeem(payload.token, now=clock())
        except InvitationRejected as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        response.set_cookie(
            key=SESSION_COOKIE,
            value=session.session_id,
            max_age=7 * 24 * 60 * 60,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/api/v1/beta",
        )
        return RedeemResponse(
            content_expires_at=session.content_expires_at,
            consent_required=True,
        )

    @app.post(
        "/api/v1/beta/consent",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def record_consent(
        payload: ConsentRequest,
        session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    ) -> Response:
        if session_id is None:
            raise _session_unavailable()
        try:
            service.record_consent(
                session_id,
                consent_version=payload.consent_version,
                now=clock(),
            )
        except (LookupError, SessionExpired) as error:
            raise _session_unavailable() from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    if intake_service is not None:

        @app.post(
            "/api/v1/beta/uploads",
            response_model=UploadResponse,
            status_code=status.HTTP_201_CREATED,
        )
        async def upload_retail_input(
            request: Request,
            session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        ) -> UploadResponse:
            if session_id is None:
                raise _session_unavailable()
            try:
                pending = intake_service.begin(
                    session_id=session_id,
                    declared_size=_declared_size(request),
                    now=clock(),
                )
                async for chunk in request.stream():
                    pending.append(chunk)
                metadata = pending.complete(now=clock())
            except SessionExpired as error:
                raise _session_unavailable() from error
            except ConsentRequired as error:
                raise HTTPException(status_code=403, detail=str(error)) from error
            except UploadTooLarge as error:
                raise HTTPException(status_code=413, detail=str(error)) from error
            except UploadAlreadyExists as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except IntakeRejected as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            except StoragePolicyViolation as error:
                raise HTTPException(
                    status_code=503,
                    detail="Upload storage is unavailable.",
                ) from error
            return _upload_response(metadata)

    if profiling_service is not None:

        @app.post(
            "/api/v1/beta/profile",
            response_model=ProfileResponse,
            status_code=status.HTTP_201_CREATED,
        )
        def profile_retail_input(
            payload: ProfileRequestBody,
            response: Response,
            session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        ) -> ProfileResponse:
            if session_id is None:
                raise _session_unavailable()
            requested = set(payload.requested_semantics)
            if not requested <= KNOWN_SEMANTICS:
                raise HTTPException(
                    status_code=400,
                    detail="Requested retail semantics are not governed.",
                )
            try:
                record, created = profiling_service.profile_session_upload(
                    session_id=session_id,
                    now=clock(),
                    request=ReportRequest(requested_semantics=frozenset(requested)),
                )
            except SessionExpired as error:
                raise _session_unavailable() from error
            except ConsentRequired as error:
                raise HTTPException(status_code=403, detail=str(error)) from error
            except CrossSessionAccessDenied as error:
                raise _session_unavailable() from error
            except UploadNotFound as error:
                raise HTTPException(status_code=404, detail=str(error)) from error
            except ProfileRejected as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            except StoragePolicyViolation as error:
                raise HTTPException(
                    status_code=503,
                    detail="Upload storage is unavailable.",
                ) from error
            if not created:
                response.status_code = status.HTTP_200_OK
            return _profile_response(record)

        @app.get(
            "/api/v1/beta/profile",
            response_model=ProfileResponse,
        )
        def read_retail_profile(
            session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        ) -> ProfileResponse:
            if session_id is None:
                raise _session_unavailable()
            try:
                record = profiling_service.get_session_profile(
                    session_id=session_id,
                    now=clock(),
                )
            except SessionExpired as error:
                raise _session_unavailable() from error
            except ConsentRequired as error:
                raise HTTPException(status_code=403, detail=str(error)) from error
            if record is None:
                raise HTTPException(
                    status_code=404,
                    detail="No dataset profile is available for this session.",
                )
            return _profile_response(record)

    if package_service is not None:

        @app.post(
            "/api/v1/beta/facts",
            response_model=FactPackageResponse,
            status_code=status.HTTP_201_CREATED,
        )
        def build_retail_facts(
            response: Response,
            session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        ) -> FactPackageResponse:
            # The package carries no request of its own. Which semantics are
            # required was decided when the dataset was profiled, and letting
            # this endpoint ask again would let the two answers disagree.
            if session_id is None:
                raise _session_unavailable()
            try:
                record, created = package_service.build_session_package(
                    session_id=session_id,
                    now=clock(),
                )
            except SessionExpired as error:
                raise _session_unavailable() from error
            except ConsentRequired as error:
                raise HTTPException(status_code=403, detail=str(error)) from error
            except CrossSessionAccessDenied as error:
                raise _session_unavailable() from error
            except ProfileNotFound as error:
                raise HTTPException(status_code=404, detail=str(error)) from error
            except PackageRefused as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except PackageCorrupted as error:
                raise HTTPException(
                    status_code=503,
                    detail="Stored fact package is unavailable.",
                ) from error
            except StoragePolicyViolation as error:
                raise HTTPException(
                    status_code=503,
                    detail="Upload storage is unavailable.",
                ) from error
            if not created:
                response.status_code = status.HTTP_200_OK
            return _package_response(record)

        @app.get(
            "/api/v1/beta/facts",
            response_model=FactPackageResponse,
        )
        def read_retail_facts(
            session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        ) -> FactPackageResponse:
            if session_id is None:
                raise _session_unavailable()
            try:
                record = package_service.get_session_package(
                    session_id=session_id,
                    now=clock(),
                )
            except SessionExpired as error:
                raise _session_unavailable() from error
            except ConsentRequired as error:
                raise HTTPException(status_code=403, detail=str(error)) from error
            except PackageRefused as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except PackageCorrupted as error:
                raise HTTPException(
                    status_code=503,
                    detail="Stored fact package is unavailable.",
                ) from error
            if record is None:
                raise HTTPException(
                    status_code=404,
                    detail="No fact package is available for this session.",
                )
            return _package_response(record)

    if deletion_service is not None:

        @app.delete(
            "/api/v1/beta/content",
            status_code=status.HTTP_204_NO_CONTENT,
        )
        def delete_session_content(
            session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        ) -> Response:
            if session_id is None:
                raise _session_unavailable()
            try:
                deletion_service.delete_session_content(
                    session_id=session_id,
                    reason="immediate",
                    now=clock(),
                )
            except SessionExpired as error:
                raise _session_unavailable() from error
            except DeletionRetryRequired as error:
                raise HTTPException(
                    status_code=503,
                    detail="Content deletion is pending retry.",
                ) from error
            response = Response(status_code=status.HTTP_204_NO_CONTENT)
            response.delete_cookie(
                key=SESSION_COOKIE,
                secure=True,
                httponly=True,
                samesite="strict",
                path="/api/v1/beta",
            )
            return response

    return app


def _session_unavailable() -> HTTPException:
    return HTTPException(status_code=401, detail="Session is unavailable.")


def _declared_size(request: Request) -> int | None:
    value = request.headers.get("content-length")
    if value is None:
        return None
    try:
        size = int(value)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Content-Length is invalid.") from error
    if size < 0:
        raise HTTPException(status_code=400, detail="Content-Length is invalid.")
    return size


def _profile_response(record: DatasetProfileRecord) -> ProfileResponse:
    profile = record.document["profile"]
    mapping = record.document["mapping"]
    admissibility = record.document["admissibility"]
    labels = {column["position"]: column["safe_label"] for column in profile["columns"]}
    return ProfileResponse(
        profile_id=record.profile_id,
        profile_version=record.profile_version,
        mapping_version=record.mapping_version,
        profile_digest=record.profile_digest,
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


def _package_response(record: FactPackageRecord) -> FactPackageResponse:
    document = record.document
    return FactPackageResponse(
        package_id=record.package_id,
        package_version=record.package_version,
        formula_version=record.formula_version,
        mapping_version=record.mapping_version,
        profile_digest=record.profile_digest,
        profile_document_digest=record.profile_document_digest,
        package_digest=record.package_digest,
        source_sha256_hex=record.source_sha256_hex,
        row_count=record.row_count,
        monetary_precision=int(document["monetary_precision"]),
        caveats=list(document["caveats"]),
        facts=[
            FactResponse(
                fact_id=fact["fact_id"],
                metric=fact["metric"],
                value=fact["value"],
                precision=fact["precision"],
                unit_kind=fact["unit_kind"],
                inputs=list(fact["inputs"]),
                caveats=list(fact["caveats"]),
                citation_id=fact["citation_id"],
            )
            for fact in document["facts"]
        ],
        series=[_aggregate_response(entry, "granularity") for entry in document["series"]],
        comparisons=[
            _aggregate_response(entry, "dimension") for entry in document["comparisons"]
        ],
        refusals=[
            FactRefusalResponse(metric=refusal["metric"], reason=refusal["reason"])
            for refusal in document["refusals"]
        ],
    )


def _aggregate_response(entry: dict[str, object], scope_key: str) -> FactAggregateResponse:
    """Render a series or a comparison, which differ only in what scopes them."""
    buckets = entry["points"] if scope_key == "granularity" else entry["buckets"]
    return FactAggregateResponse(
        fact_id=str(entry["fact_id"]),
        metric=str(entry["metric"]),
        measure=str(entry["measure"]),
        unit_kind=str(entry["unit_kind"]),
        precision=int(entry["precision"]),
        scope=str(entry[scope_key]),
        citation_id=str(entry["citation_id"]),
        caveats=list(entry["caveats"]),
        buckets=list(buckets),
    )


def _upload_response(metadata: UploadMetadata) -> UploadResponse:
    return UploadResponse(
        upload_id=metadata.upload_id,
        size_bytes=metadata.size_bytes,
        sha256_hex=metadata.sha256_hex,
        media_type=metadata.media_type,
        expires_at=metadata.expires_at,
    )
