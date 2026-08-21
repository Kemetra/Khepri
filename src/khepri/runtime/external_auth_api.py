"""Private-beta external authentication handoff into Khepri's own session boundary."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import FastAPI, Header, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from khepri.rca.identity import IdentityProvider
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.session_cookie import issue_session_cookie
from khepri.rca.session_service import SessionService
from khepri.rca.switching import OrganizationSwitcher
from khepri.runtime.commercial_api import COMMERCIAL_PREFIX

EXTERNAL_SESSION_PATH = f"{COMMERCIAL_PREFIX}/auth/session"
KHEPRI_SESSION_LIFETIME = timedelta(hours=12)

OrganizationId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class ExternalSessionRequest(BaseModel):
    """The Khepri organization requested for this Khepri session."""

    model_config = ConfigDict(extra="forbid")

    organization_id: OrganizationId


@dataclass(frozen=True, slots=True)
class ExternalAuthenticationServices:
    identity_provider: IdentityProvider
    sessions: SessionService
    lifecycle: LifecycleService
    switcher: OrganizationSwitcher


def _refusal() -> Response:
    """One empty answer for invalid, unlinked, inactive, and wrongly scoped identities."""
    return Response(status_code=status.HTTP_404_NOT_FOUND)


def _bearer(authorization: str | None) -> str | None:
    if authorization is None or not authorization.startswith("Bearer "):
        return None
    credential = authorization.removeprefix("Bearer ")
    if not credential or credential.strip() != credential or any(c.isspace() for c in credential):
        return None
    return credential


def add_external_authentication_routes(
    app: FastAPI,
    *,
    services: ExternalAuthenticationServices | None,
    clock: Callable[[], datetime],
) -> None:
    """Register the handoff only when a provider is admitted and configured."""
    if services is None:
        return

    @app.post(EXTERNAL_SESSION_PATH, status_code=status.HTTP_204_NO_CONTENT)
    def create_external_session(
        payload: ExternalSessionRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> Response:
        credential = _bearer(authorization)
        if credential is None:
            return _refusal()
        try:
            identity = services.identity_provider.verify(credential)
        except Exception:  # noqa: BLE001 - provider failure must fail closed at this boundary
            return _refusal()
        if identity is None:
            return _refusal()

        account_id = services.sessions.account_for_identity(
            identity.provider, identity.provider_subject
        )
        if account_id is None:
            return _refusal()

        now = clock()
        token: str | None = None
        try:
            services.lifecycle.assert_account_active(account_id)
            token = services.sessions.create(account_id, now=now)
            services.switcher.switch(token, payload.organization_id, now=now)
        except PermissionError:
            if token is not None:
                # A concurrent security action may already have ended it. Cleanup remains
                # successful and the caller still receives the one refusal shape.
                with suppress(PermissionError):
                    services.sessions.revoke(token, now=now)
            return _refusal()

        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        response.set_cookie(**issue_session_cookie(token, lifetime=KHEPRI_SESSION_LIFETIME))
        return response


__all__ = [
    "EXTERNAL_SESSION_PATH",
    "KHEPRI_SESSION_LIFETIME",
    "ExternalAuthenticationServices",
    "ExternalSessionRequest",
    "add_external_authentication_routes",
]
