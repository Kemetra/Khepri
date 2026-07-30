from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import Cookie, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from khepri.rra.admissibility import ReportRequest
from khepri.rra.datasets import (
    DatasetProfileRecord,
    ProfileCorrupted,
    ProfileRequestConflict,
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
from khepri.rra.reports import (
    DeliveredBundle,
    DeliveryWithheld,
    JobEvidenceContradicted,
    ReportJobView,
    ReportPackageMissing,
    ReportServices,
    job_outcome,
    reconcile_delivery,
)
from khepri.rra.sessions import (
    ConsentRequired,
    CrossSessionAccessDenied,
    InvitationRejected,
    InvitationService,
    SessionExpired,
)

SESSION_COOKIE = "khepri_beta_session"
_SESSION_UNAVAILABLE = "Session is unavailable."
ConsentVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
# An opaque job identifier, bounded so an unbounded path segment never reaches a
# store as a lookup key.
JobIdentifier = Annotated[
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


class FactPackageResponse(BaseModel):
    """The published package, served as the document its digest addresses.

    The canonical document is nested verbatim rather than reshaped into
    per-entry models. A consumer given `package_digest` can only check it
    against the bytes it was computed over, and renaming or dropping fields on
    the way out -- as an earlier revision did with the truncation and redaction
    counts -- makes the digest unverifiable and hides how much a comparison
    left out.
    """

    package_id: str
    package_digest: str
    profile_document_digest: str
    document: dict[str, object]


class ReportRequestBody(BaseModel):
    """A report request carries no request of its own.

    Which figures a report contains was decided when the dataset was profiled
    and fixed when the fact package was published. A field here -- a template, a
    title, a set of semantics -- would be a second decision able to disagree
    with the first, so the model exists to refuse one rather than to carry one.
    """

    model_config = ConfigDict(extra="forbid")


class ReportJobResponse(BaseModel):
    """One job's governed state, and for a finished job what it produced.

    Content-free by construction: an opaque job identifier, a state from the
    governed vocabulary, two timestamps, a bundle content address, and a
    governed reason code. There is no field a label, a figure, a filename, or a
    provider sentence could occupy.
    """

    job_id: str
    state: str
    queued_at: datetime
    completed_at: datetime | None
    bundle_id: str | None
    reason: str | None


class ReportBundleResponse(BaseModel):
    """The delivered report as a manifest of what was published, not as content.

    Deliberately no figures, no caveats, no narrative, no filenames, and no
    download location or credential of any kind. What a caller is owed here is
    that one whole report exists and what it is bound to: the bundle's content
    address, the fact-package version behind every surface of it, whether
    commentary was included, and which surfaces were delivered.
    """

    job_id: str
    bundle_id: str
    package_version: str
    narrative_state: str
    surfaces: list[str]


def create_app(
    *,
    service: InvitationService,
    clock: Callable[[], datetime],
    intake_service: IntakeService | None = None,
    deletion_service: DeletionService | None = None,
    profiling_service: ProfilingService | None = None,
    package_service: FactPackageService | None = None,
    report_services: ReportServices | None = None,
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
            except ProfileRequestConflict as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            except ProfileRejected as error:
                raise HTTPException(status_code=400, detail=str(error)) from error
            except ProfileCorrupted as error:
                raise HTTPException(
                    status_code=503,
                    detail="Stored dataset profile is unavailable.",
                ) from error
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
            except ProfileCorrupted as error:
                raise HTTPException(
                    status_code=503,
                    detail="Stored dataset profile is unavailable.",
                ) from error
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
            except (PackageCorrupted, ProfileCorrupted) as error:
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
            except (PackageCorrupted, ProfileCorrupted) as error:
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

    if report_services is not None:

        @app.post(
            "/api/v1/beta/reports",
            response_model=ReportJobResponse,
            status_code=status.HTTP_201_CREATED,
        )
        def request_retail_report(
            payload: ReportRequestBody,
            response: Response,
            session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        ) -> ReportJobResponse:
            # `payload` is declared and unused on purpose: it is the guard that
            # refuses a caller who invents a field. See `ReportRequestBody`.
            return _requested_report(
                report_services,
                response=response,
                session_id=_require_session(session_id),
                now=clock(),
            )

        @app.get(
            "/api/v1/beta/reports/{job_id}",
            response_model=ReportJobResponse,
        )
        def read_retail_report_job(
            job_id: JobIdentifier,
            session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        ) -> ReportJobResponse:
            return _report_job(
                report_services,
                session_id=_require_session(session_id),
                job_id=job_id,
                now=clock(),
            )

        @app.get(
            "/api/v1/beta/reports/{job_id}/bundle",
            response_model=ReportBundleResponse,
        )
        def read_retail_report_bundle(
            job_id: JobIdentifier,
            session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
        ) -> ReportBundleResponse:
            return _report_bundle(
                report_services,
                session_id=_require_session(session_id),
                job_id=job_id,
                now=clock(),
            )

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
    return HTTPException(status_code=401, detail=_SESSION_UNAVAILABLE)


# How a governed refusal reaches a caller. A table rather than a chain of
# `except` clauses inside each route: the report routes refuse for the same
# reasons, and three copies of one mapping is three places for them to drift.
# `None` for the detail means the exception's own message is already governed
# text -- every one of those is a fixed sentence written in this package.
_REPORT_REFUSALS: tuple[tuple[type[Exception], int, str | None], ...] = (
    (SessionExpired, 401, _SESSION_UNAVAILABLE),
    (CrossSessionAccessDenied, 401, _SESSION_UNAVAILABLE),
    (ConsentRequired, 403, None),
    (ReportPackageMissing, 404, None),
    (PackageRefused, 409, None),
    (PackageCorrupted, 503, "Stored fact package is unavailable."),
    (ProfileCorrupted, 503, "Stored fact package is unavailable."),
)


def _refusal_for(error: Exception) -> HTTPException:
    """The status one governed refusal reaches a caller as.

    An error this table does not recognize is re-raised rather than reported as
    a refusal, so an unmapped failure fails closed as a server error instead of
    being described to a caller in words nothing here governs.
    """
    for kind, code, detail in _REPORT_REFUSALS:
        if isinstance(error, kind):
            return HTTPException(status_code=code, detail=detail or str(error))
    raise error


def _require_session(session_id: str | None) -> str:
    if session_id is None:
        raise _session_unavailable()
    return session_id


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


def _requested_report(
    services: ReportServices,
    *,
    response: Response,
    session_id: str,
    now: datetime,
) -> ReportJobResponse:
    """Ask for this caller's report, and say whether this call is what asked.

    Held outside `create_app` rather than written into the route, so the branches
    a refusal needs do not accumulate in the one function every route group in
    this module already shares.
    """
    try:
        view, created = services.jobs.request_session_report(
            session_id=session_id,
            now=now,
        )
    except Exception as error:
        raise _refusal_for(error) from error
    if not created:
        # The same request, so the same job. A second identifier here would be a
        # second report built from one package, and RRA-007 requires the
        # background job be idempotent rather than merely repeatable.
        response.status_code = status.HTTP_200_OK
    return _job_response(view)


def _report_job(
    services: ReportServices,
    *,
    session_id: str,
    job_id: str,
    now: datetime,
) -> ReportJobResponse:
    try:
        view = services.jobs.get_session_job(
            session_id=session_id,
            job_id=job_id,
            now=now,
        )
    except Exception as error:
        raise _refusal_for(error) from error
    if view is None:
        # Identical to the answer another caller's job gets, because the store is
        # asked for this caller's job and nothing else. A distinguishable
        # refusal would confirm that another caller's job exists.
        raise HTTPException(
            status_code=404,
            detail="No report job is available for this session.",
        )
    return _job_response(view)


def _report_bundle(
    services: ReportServices,
    *,
    session_id: str,
    job_id: str,
    now: datetime,
) -> ReportBundleResponse:
    try:
        bundle = services.bundles.get_session_bundle(
            session_id=session_id,
            job_id=job_id,
            now=now,
        )
    except Exception as error:
        raise _refusal_for(error) from error
    if bundle is None:
        raise HTTPException(
            status_code=404,
            detail="No delivered report is available for this session.",
        )
    return _bundle_response(bundle, job_id=job_id)


def _job_response(view: ReportJobView) -> ReportJobResponse:
    """One job as a caller sees it, or a refusal to describe it at all.

    What may be said is decided in `reports.job_outcome`, which owns the
    governed vocabularies. All that happens here is the mapping onto a status.
    """
    try:
        outcome = job_outcome(view)
    except JobEvidenceContradicted as error:
        # Deliberately indistinguishable between an ungoverned state, a missing
        # delivery record, and a record naming another job. Which invariant a
        # store broke is an operator's question, and answering it here would
        # describe stored state to a caller who cannot act on it.
        raise HTTPException(
            status_code=503,
            detail="Report job state is unavailable.",
        ) from error
    return ReportJobResponse(
        job_id=view.job.job_id,
        state=outcome.state,
        queued_at=view.job.queued_at,
        completed_at=view.job.completed_at,
        bundle_id=outcome.bundle_id,
        reason=outcome.reason,
    )


def _bundle_response(bundle: DeliveredBundle, *, job_id: str) -> ReportBundleResponse:
    """The manifest of one whole report, or nothing.

    Every field is taken from the delivery record rather than from the stored
    surfaces, and the record has already refused to name fewer than every
    required surface. The surfaces are what the record is checked against.
    """
    try:
        reconcile_delivery(bundle, job_id=job_id)
    except DeliveryWithheld as withheld:
        # The governed reason stays on the exception. Which invariant a store
        # broke is an operator's question; a caller is told only that no whole
        # report can be served, which is the answer RRA-006 requires.
        raise HTTPException(
            status_code=503,
            detail="Report bundle is unavailable.",
        ) from withheld
    record = bundle.record
    return ReportBundleResponse(
        job_id=record.job_id,
        bundle_id=record.bundle_id,
        package_version=record.package_version,
        narrative_state=record.narrative_state,
        surfaces=list(record.surfaces),
    )


def _package_response(record: FactPackageRecord) -> FactPackageResponse:
    return FactPackageResponse(
        package_id=record.package_id,
        package_digest=record.package_digest,
        profile_document_digest=record.profile_document_digest,
        document=record.document,
    )


def _upload_response(metadata: UploadMetadata) -> UploadResponse:
    return UploadResponse(
        upload_id=metadata.upload_id,
        size_bytes=metadata.size_bytes,
        sha256_hex=metadata.sha256_hex,
        media_type=metadata.media_type,
        expires_at=metadata.expires_at,
    )
