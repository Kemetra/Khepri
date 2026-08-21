"""The commercial HTTP surface: an authorized RCA actor to an RRA analysis (`R7-05`).

**Authorized by `KHEPRI-DEC-022` §2**, which lifted `KHEPRI-DEC-021` §5's "No endpoint" bullet and
fixed four things this module may not depart from: `for_request` rather than `resolve`, the cookie
as the only token source, `R6-08`'s tripwire replaced rather than relaxed, and no new `R6-01` §3.1
row.

## Why this module is in `khepri.runtime`

`R7-07` asserts a flat prohibition in both directions -- `khepri.rca` imports no `khepri.rra`
module and `khepri.rra` imports no `khepri.rca` module. A route module needs `AuthorizationResolver`
(RCA) and `CommercialBridge` (which holds both), so an RRA-side module would pull `khepri.rca` into
that package and fail that test. The composition root is the one layer allowed to know both sides,
and it is what the built wheel ships.

## Every refusal is one `404`

`AuthenticationFailed` and `ScopeAccessDenied` both derive from `PermissionError`
(`rca/errors.py:33`, `:37`), so a single handler covers both and the uniformity is structural rather
than a convention two branches must remember. A missing analysis returns the same thing, because
`resume` returning `None` and a refusal must be indistinguishable (`FR-025`).

**No organization is named in a request.** `for_request` is called with `organization_id=None`, so
the session's active organization is used. `KHEPRI-DEC-022` §2 requires any request-named
organization be compared; this satisfies it by admitting no such parameter, so there is no path on
which the comparison could be skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from khepri.rca.authorization_resolution import AuthorizationResolver
from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.rra.sessions import InvitationService
from khepri.runtime.bridge import CommercialBridge

COMMERCIAL_PREFIX = "/api/v1/commercial"


@dataclass(frozen=True, slots=True)
class CommercialServices:
    """The two collaborators, one from each side, paired only here."""

    resolver: AuthorizationResolver
    bridge: CommercialBridge
    consent: InvitationService


class AnalysisResponse(BaseModel):
    session_id: str


ConsentVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class ConsentRequest(BaseModel):
    """Mirrors `rra/api.py:65`'s model deliberately.

    `min_length=1` after stripping is what keeps `record_consent`'s `ValueError` unreachable: that
    exception is not a `PermissionError`, so it would escape this module's `except PermissionError`
    as a `500`. Pydantic refuses an empty version with a `422` before the service is called.
    """

    model_config = ConfigDict(extra="forbid")

    consent_version: ConsentVersion


def _not_found() -> Response:
    """The single refusal. Empty body, no detail, no distinguishing header.

    Returned for a missing cookie, an expired or revoked session, a non-member, a disabled account,
    an unknown organization, an absent analysis, and another scope's analysis. A caller able to tell
    these apart enumerates organizations one probe at a time, which `FR-004` and `FR-022` forbid and
    `R6-03` already closed on the switch path.

    A `Response` is returned rather than an `HTTPException` raised because `HTTPException`
    serializes a `{"detail": ...}` body, and a body is exactly what must not vary between causes.
    """
    return Response(status_code=status.HTTP_404_NOT_FOUND)


def add_commercial_routes(
    app: FastAPI,
    *,
    services: CommercialServices | None,
    clock: Callable[[], datetime],
) -> None:
    """Declare the commercial route group, or declare nothing at all.

    The null guard is load-bearing: unwired, the routes do not exist, so `KHEPRI-DEC-022` §3's
    no-beta-change requirement is met structurally rather than by a test asserting nothing moved.
    """
    if services is None:
        return

    @app.post(f"{COMMERCIAL_PREFIX}/analyses", status_code=status.HTTP_201_CREATED)
    def open_analysis(session: CommercialSessionCookie = None) -> Response:
        """Authorize the caller, then open an analysis in their active organization's scope."""
        if session is None:
            return _not_found()
        now = clock()
        try:
            context = services.resolver.for_request(session, organization_id=None, now=now)
            opened = services.bridge.open(
                account_id=context.account_id,
                organization_id=context.organization_id,
                now=now,
            )
        except PermissionError:
            return _not_found()
        return _analysis(opened.session_id, status.HTTP_201_CREATED)

    @app.get(f"{COMMERCIAL_PREFIX}/analyses/{{session_id}}")
    def resume_analysis(session_id: str, session: CommercialSessionCookie = None) -> Response:
        """Re-authorize, then read one analysis within the resolved scope.

        `session_id` is an object identifier and confers nothing (`FR-023`). The bridge re-resolves
        before it reads and keeps the owner predicate in the store's statement, so this handler adds
        no check of its own.
        """
        if session is None:
            return _not_found()
        now = clock()
        try:
            context = services.resolver.for_request(session, organization_id=None, now=now)
            resumed = services.bridge.resume(
                account_id=context.account_id,
                organization_id=context.organization_id,
                session_id=session_id,
                now=now,
            )
        except PermissionError:
            return _not_found()
        if resumed is None:
            return _not_found()
        return _analysis(resumed.session_id, status.HTTP_200_OK)

    @app.post(
        f"{COMMERCIAL_PREFIX}/analyses/{{session_id}}/consent",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def record_analysis_consent(
        session_id: str,
        payload: ConsentRequest,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """Authorize, confirm the analysis is in scope, then record consent.

        **The `resume` call is the scope check, not a redundant read.** Recording consent against a
        caller-supplied `session_id` without it would let one organization write to another
        organization's analysis, which is the `FR-023` violation the resume path exists to prevent.
        `KHEPRI-DEC-023` §2 names it for that reason, and `record_consent` receives the session the
        bridge returned rather than the raw path parameter so the dependency is explicit.

        **Consenting twice is deliberately not an error.** Refusing it would require distinguishing
        "already consented" from "not yours", and a caller able to tell those apart learns that an
        analysis exists in a scope they cannot reach.

        `SessionExpired` and `ConsentRequired` both derive from `PermissionError`
        (`rra/sessions.py:17`, `:21`), so the same `except` that covers authorization covers expiry
        and no second branch is needed.
        """
        if session is None:
            return _not_found()
        now = clock()
        try:
            context = services.resolver.for_request(session, organization_id=None, now=now)
            scoped = services.bridge.resume(
                account_id=context.account_id,
                organization_id=context.organization_id,
                session_id=session_id,
                now=now,
            )
            if scoped is None:
                return _not_found()
            services.consent.record_consent(
                scoped.session_id,
                consent_version=payload.consent_version,
                now=now,
            )
        except PermissionError:
            return _not_found()
        return Response(status_code=status.HTTP_204_NO_CONTENT)


def _analysis(session_id: str, code: int) -> Response:
    """Serialize one analysis identifier, so both routes answer in one shape."""
    return Response(
        content=AnalysisResponse(session_id=session_id).model_dump_json(),
        status_code=code,
        media_type="application/json",
    )


__all__ = [
    "COMMERCIAL_PREFIX",
    "AnalysisResponse",
    "CommercialServices",
    "ConsentRequest",
    "ConsentVersion",
    "add_commercial_routes",
]
