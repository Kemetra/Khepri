"""The HTTP surface that asks whether a window is proven completely covered.

**Why this route exists at all.** `RRA-003` requires completeness to be attested
rather than observed, and `khepri.rra.coverage` has held the rules for that since
before this slice. What it lacked was a caller. A manifest validated only as it
was written proves nothing at the moment it matters, so this surface asks the
question at use time -- against the stored attestation, bound to the admission it
was recorded under.

**Why it is not in `api`.** `create_app` declares its route groups inline and is
already past every complexity threshold this project measures, so each group
added there makes a tracked file measurably worse. This module registers its own,
conditionally on an optional collaborator, which is the contract every other
group has -- see `report_api.add_report_routes`.

**A read, not a write.** The attestation arrives with the declaration it is bound
to, on the profile route, because the stored profile document is content-addressed
and an attestation attached later would have to rewrite the digest every published
package cites. `datasets.build_document` records that reasoning. So there is no
POST here: what this surface offers is the question, and the refusal.

**Responses carry no customer content.** A governed reason code, a window, a
scope, and the manifest's own version. Not a figure, not a label, not a filename.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from khepri.rra.datasets import (
    CoverageUnproven,
    DatasetProfileRecord,
    ProfileCorrupted,
    ProfilingService,
    session_completeness,
)
from khepri.rra.session_cookie import SESSION_UNAVAILABLE, BetaSessionCookie
from khepri.rra.sessions import ConsentRequired, SessionExpired

_NO_PROFILE = "No dataset profile is available for this session."


class CompletenessResponse(BaseModel):
    """What an admitted window reports, and nothing more.

    `complete` is always `True` here: an unproven window is a refusal with a
    governed reason, not a 200 carrying `false`. Serving `false` would make "no
    attestation exists", "the attestation covers another reading", and "this
    window is short" the same answer, and `RRA-003` requires the caller to be
    able to act on which.
    """

    complete: bool
    manifest_version: str
    scope: str
    start: date
    end: date


class CoverageRefusalDetail(BaseModel):
    """A governed refusal, in the shape a client can branch on.

    The reason code travels beside the sentence rather than inside it, because a
    surface that has to parse prose to tell an absent attestation from a
    mismatched one will eventually parse it wrong.
    """

    reason: str
    message: str


def add_coverage_routes(
    app: FastAPI,
    *,
    profiling_service: ProfilingService | None,
    clock: Callable[[], datetime],
) -> None:
    """Declare the coverage route group, or declare nothing at all."""
    if profiling_service is None:
        return

    @app.get(
        "/api/v1/beta/coverage/completeness",
        response_model=CompletenessResponse,
    )
    def read_window_completeness(
        scope: str,
        start: date,
        end: date,
        session_id: BetaSessionCookie = None,
    ) -> CompletenessResponse:
        if session_id is None:
            raise _session_unavailable()
        if end < start:
            # 400, not 409: an inverted range is a caller error, not a dataset
            # in a state that cannot answer -- and `admits_completeness` would
            # otherwise see an empty day range and prove it vacuously.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end must not be before start.",
            )
        record = _session_profile(profiling_service, session_id, clock)
        try:
            manifest = session_completeness(
                record,
                scope=scope,
                start=start,
                end=end,
            )
        except CoverageUnproven as error:
            # 409 rather than 400 or 404, matching `ProfileRequestConflict` on
            # the profile route: the request is well-formed and the resource
            # exists, but the state it is in cannot answer the question asked.
            # A 404 would say the window does not exist; a 400 would blame the
            # caller for a dataset nobody attested.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=CoverageRefusalDetail(
                    reason=error.reason,
                    message=str(error),
                ).model_dump(),
            ) from error
        return CompletenessResponse(
            complete=True,
            manifest_version=manifest.manifest_version,
            scope=scope,
            start=start,
            end=end,
        )


def _session_profile(
    profiling_service: ProfilingService,
    session_id: str,
    clock: Callable[[], datetime],
) -> DatasetProfileRecord:
    """The session's stored profile, or the refusal its absence warrants."""
    record = _read_profile(profiling_service, session_id, clock)
    if record is None:
        raise HTTPException(status_code=404, detail=_NO_PROFILE)
    return record


def _read_profile(
    profiling_service: ProfilingService,
    session_id: str,
    clock: Callable[[], datetime],
) -> DatasetProfileRecord | None:
    """The stored read, with the profile route's own status mapping.

    Split from the not-found decision above so each function answers one
    question: this one translates the store's refusals, that one decides what an
    absent profile means. The same mapping the profile route's own GET uses, so a
    session that has expired, withheld consent, or stored a corrupted profile
    reports identically whichever surface asked.
    """
    try:
        return profiling_service.get_session_profile(
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


def _session_unavailable() -> HTTPException:
    return HTTPException(status_code=401, detail=SESSION_UNAVAILABLE)
