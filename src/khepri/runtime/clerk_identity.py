"""Networkless Clerk token verification behind Khepri's identity-provider seam."""

from __future__ import annotations

import base64
import json
from typing import Any

from clerk_backend_api.security import verify_token
from clerk_backend_api.security.types import TokenVerificationError, VerifyTokenOptions

from khepri.rca.identity import VerifiedIdentity
from khepri.runtime.config import ClerkIdentitySettings

_ALGORITHM = "RS256"
_MAX_TOKEN_LIFETIME_SECONDS = 60


class ClerkIdentityProvider:
    """Verify one pinned Clerk instance and expose only its stable token subject."""

    def __init__(self, settings: ClerkIdentitySettings) -> None:
        self._settings = settings
        self._options = VerifyTokenOptions(
            audience=settings.audience,
            authorized_parties=list(settings.authorized_parties),
            clock_skew_in_ms=0,
            jwt_key=settings.jwt_key,
        )

    def verify(self, credential: str) -> VerifiedIdentity | None:
        """Return the signed Clerk subject, collapsing every invalid credential to refusal."""
        if not _has_pinned_header(credential, self._settings.key_id):
            return None
        try:
            claims = verify_token(credential, self._options)
        except (TokenVerificationError, TypeError, ValueError):
            return None
        subject = _verified_subject(claims, issuer=self._settings.issuer)
        if subject is None:
            return None
        return VerifiedIdentity(provider="clerk", provider_subject=subject)


def _has_pinned_header(token: str, key_id: str) -> bool:
    try:
        encoded = token.split(".", 1)[0]
        padding = "=" * (-len(encoded) % 4)
        header = json.loads(base64.urlsafe_b64decode(encoded + padding))
    except (UnicodeDecodeError, ValueError):
        return False
    return (
        isinstance(header, dict)
        and header.get("alg") == _ALGORITHM
        and header.get("kid") == key_id
    )


def _verified_subject(claims: dict[str, Any], *, issuer: str) -> str | None:
    subject = claims.get("sub")
    issued_at = claims.get("iat")
    expires_at = claims.get("exp")
    valid_times = (
        isinstance(issued_at, int)
        and not isinstance(issued_at, bool)
        and isinstance(expires_at, int)
        and not isinstance(expires_at, bool)
        and 0 < expires_at - issued_at <= _MAX_TOKEN_LIFETIME_SECONDS
    )
    valid_identity = claims.get("iss") == issuer and isinstance(subject, str) and bool(subject)
    if not valid_identity or not valid_times:
        return None
    return subject


__all__ = ["ClerkIdentityProvider"]
