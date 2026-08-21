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


def _timestamp(claim: Any) -> int | None:
    """One integer-seconds claim, or `None`.

    `bool` is a subclass of `int`, so `isinstance(True, int)` is `True` and the explicit exclusion
    is load-bearing rather than defensive: without it `iat=True` reads as second 1 and the lifetime
    check below silently becomes `exp - 1`.
    """
    if isinstance(claim, bool) or not isinstance(claim, int):
        return None
    return claim


def _within_admitted_lifetime(claims: dict[str, Any]) -> bool:
    """Both timestamps present as integers, and the window strictly positive and capped.

    The lower bound is strict: a token expiring in the instant it was issued carries no valid
    window, and `KHEPRI-DEC-025` §2 pins the maximum lifetime rather than only a maximum.
    """
    issued_at = _timestamp(claims.get("iat"))
    expires_at = _timestamp(claims.get("exp"))
    if issued_at is None or expires_at is None:
        return False
    return 0 < expires_at - issued_at <= _MAX_TOKEN_LIFETIME_SECONDS


def _pinned_subject(claims: dict[str, Any], *, issuer: str) -> str | None:
    """The non-empty string subject of a token from the pinned issuer, or `None`."""
    if claims.get("iss") != issuer:
        return None
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        return None
    return subject


def _verified_subject(claims: dict[str, Any], *, issuer: str) -> str | None:
    """The request-time subject, refusing on issuer, subject shape, or token window.

    Split into two predicates because the identity contract and the token window are independent
    checks over disjoint claims; they were one boolean expression, which `#240`'s CodeScene review
    flagged as a Complex Method. Every clause is preserved exactly — this restructures the
    grouping, never the decision.
    """
    if not _within_admitted_lifetime(claims):
        return None
    return _pinned_subject(claims, issuer=issuer)


__all__ = ["ClerkIdentityProvider"]
