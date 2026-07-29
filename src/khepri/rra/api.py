from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import Cookie, FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from khepri.rra.sessions import (
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


def create_app(
    *,
    service: InvitationService,
    clock: Callable[[], datetime],
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

    return app


def _session_unavailable() -> HTTPException:
    return HTTPException(status_code=401, detail="Session is unavailable.")
