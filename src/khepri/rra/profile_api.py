"""The HTTP surface for profiling an upload under a declared source contract.

**Why these routes are not in `api`.** `create_app` is a tracked CodeScene
hotspot, and its gate refuses any change that lets a hotspot decline. Adding the
source-contract admission to it made a measurably worse file, and extracting
helpers could not fix that -- a whole-module measure moves the wrong way when
you add functions to it. `report_api` already set the precedent for exactly this
reason, so this module follows it: `create_app` ends up smaller than it was
before this slice rather than larger.

**The conditional lives here, not in `create_app`.** `add_profile_routes`
returns without declaring anything when no profiling service was supplied, so
the group is still registered conditionally on an optional keyword-only
parameter -- the same contract every other group has, one function deeper.

**Why a contract is built before the upload is read.** `RRA-003` will not let
admission infer what a column means, so a declaration that leaves a semantic
unproven is refused here, with its own reason. Refusing later would surface the
same defect as an unexplained admissibility failure, and the operator would have
no way to tell a bad file from a bad declaration.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import Cookie, FastAPI, HTTPException, Response, status

from khepri.rra.admissibility import ReportRequest
from khepri.rra.datasets import (
    DatasetProfileRecord,
    ProfileCorrupted,
    ProfileRequestConflict,
    ProfilingService,
    UploadNotFound,
)
from khepri.rra.intake import StoragePolicyViolation
from khepri.rra.mapping import KNOWN_SEMANTICS
from khepri.rra.profiles import (
    ProfileRequestBody,
    ProfileResponse,
    profile_response,
)
from khepri.rra.profiling import ProfileRejected
from khepri.rra.session_cookie import SESSION_COOKIE, SESSION_UNAVAILABLE
from khepri.rra.sessions import (
    ConsentRequired,
    CrossSessionAccessDenied,
    SessionExpired,
)
from khepri.rra.source_contract import ContractRefused, SourceContract


def _session_unavailable() -> HTTPException:
    return HTTPException(status_code=401, detail=SESSION_UNAVAILABLE)


def _governed_semantics(payload: ProfileRequestBody) -> set[str]:
    """The requested semantics, or a refusal naming them as ungoverned."""
    requested = set(payload.requested_semantics)
    if not requested <= KNOWN_SEMANTICS:
        raise HTTPException(
            status_code=400,
            detail="Requested retail semantics are not governed.",
        )
    return requested


def _admitted_contract(payload: ProfileRequestBody) -> SourceContract:
    """The declared reading of this file, refused if it proves nothing."""
    try:
        return payload.source_contract.to_contract()
    except ContractRefused as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


def _profile_response(record: DatasetProfileRecord) -> ProfileResponse:
    return profile_response(record)


def add_profile_routes(
    app: FastAPI,
    *,
    service: ProfilingService | None,
    clock: Callable[[], datetime],
) -> None:
    """Declare the profile route group, or declare nothing at all."""
    if service is None:
        return


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
        requested = _governed_semantics(payload)
        contract = _admitted_contract(payload)
        try:
            record, created = service.profile_session_upload(
                session_id=session_id,
                now=clock(),
                request=ReportRequest(requested_semantics=frozenset(requested)),
                source_contract_digest=contract.digest,
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
            record = service.get_session_profile(
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
