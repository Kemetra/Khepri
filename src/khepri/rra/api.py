from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import Cookie, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from khepri.rra.intake import (
    IntakeRejected,
    IntakeService,
    StoragePolicyViolation,
    UploadAlreadyExists,
    UploadMetadata,
    UploadTooLarge,
)
from khepri.rra.sessions import (
    ConsentRequired,
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


def create_app(
    *,
    service: InvitationService,
    clock: Callable[[], datetime],
    intake_service: IntakeService | None = None,
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


def _upload_response(metadata: UploadMetadata) -> UploadResponse:
    return UploadResponse(
        upload_id=metadata.upload_id,
        size_bytes=metadata.size_bytes,
        sha256_hex=metadata.sha256_hex,
        media_type=metadata.media_type,
        expires_at=metadata.expires_at,
    )
