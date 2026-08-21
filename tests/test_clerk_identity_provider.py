"""R3-11: Clerk proves identity; it never supplies Khepri authority."""

from __future__ import annotations

from datetime import UTC, datetime

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from khepri.rca.identity import VerifiedIdentity
from khepri.runtime.clerk_identity import ClerkIdentityProvider
from khepri.runtime.config import ClerkIdentitySettings

ISSUER = "https://private-beta.clerk.accounts.example"
AUDIENCE = "khepri-private-beta"
AUTHORIZED_PARTY = "https://beta.khepri.example"
KEY_ID = "ins_private_beta"


def _key_pair() -> tuple[rsa.RSAPrivateKey, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_key.decode("ascii")


PRIVATE_KEY, PUBLIC_KEY = _key_pair()
FOREIGN_PRIVATE_KEY, _ = _key_pair()


def _settings(**overrides: object) -> ClerkIdentitySettings:
    values: dict[str, object] = {
        "mode": "private_beta",
        "issuer": ISSUER,
        "jwt_key": PUBLIC_KEY,
        "key_id": KEY_ID,
        "authorized_parties": (AUTHORIZED_PARTY,),
        "audience": AUDIENCE,
    }
    values.update(overrides)
    return ClerkIdentitySettings(**values)  # type: ignore[arg-type]


def _token(
    *,
    claims: dict[str, object] | None = None,
    headers: dict[str, object] | None = None,
    key: rsa.RSAPrivateKey = PRIVATE_KEY,
    algorithm: str = "RS256",
) -> str:
    issued_at = int(datetime.now(UTC).timestamp())
    payload: dict[str, object] = {
        "iss": ISSUER,
        "sub": "user_private_beta_123",
        "iat": issued_at,
        "exp": issued_at + 60,
        "azp": AUTHORIZED_PARTY,
        "aud": AUDIENCE,
    }
    payload.update(claims or {})
    protected = {"kid": KEY_ID, **(headers or {})}
    return jwt.encode(payload, key, algorithm=algorithm, headers=protected)


def test_a_valid_token_exposes_only_clerk_and_its_verified_subject() -> None:
    token = _token(
        claims={
            "email": "mutable@example.com",
            "org_role": "admin",
            "permissions": ["everything"],
            "plan": "enterprise",
            "metadata": {"can_act": True},
        }
    )

    identity = ClerkIdentityProvider(_settings()).verify(token)

    assert identity == VerifiedIdentity(
        provider="clerk",
        provider_subject="user_private_beta_123",
    )


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        _token(headers={"kid": "foreign_key"}),
        _token(key=FOREIGN_PRIVATE_KEY),
        jwt.encode(
            {
                "iss": ISSUER,
                "sub": "user_private_beta_123",
                "iat": int(datetime.now(UTC).timestamp()),
                "exp": int(datetime.now(UTC).timestamp()) + 60,
                "azp": AUTHORIZED_PARTY,
                "aud": AUDIENCE,
            },
            "symmetric-test-secret-that-is-not-an-rsa-key",
            algorithm="HS256",
            headers={"kid": KEY_ID},
        ),
    ],
    ids=["malformed", "foreign-kid", "bad-signature", "wrong-algorithm"],
)
def test_untrusted_or_malformed_tokens_are_uniformly_refused(token: str) -> None:
    assert ClerkIdentityProvider(_settings()).verify(token) is None


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://development.clerk.accounts.example"},
        {"azp": "https://attacker.example"},
        {"aud": "another-service"},
        {"sub": ""},
        {"sub": None},
        {"iat": None},
        {"exp": None},
    ],
    ids=[
        "foreign-issuer",
        "foreign-authorized-party",
        "foreign-audience",
        "empty-subject",
        "non-text-subject",
        "missing-issued-at",
        "missing-expiry",
    ],
)
def test_a_token_outside_the_pinned_identity_contract_is_refused(
    claims: dict[str, object],
) -> None:
    assert ClerkIdentityProvider(_settings()).verify(_token(claims=claims)) is None


def test_a_token_longer_than_the_admitted_sixty_seconds_is_refused() -> None:
    issued_at = int(datetime.now(UTC).timestamp())
    token = _token(claims={"iat": issued_at, "exp": issued_at + 61})

    assert ClerkIdentityProvider(_settings()).verify(token) is None


def test_an_expired_token_is_refused() -> None:
    expired_at = int(datetime.now(UTC).timestamp()) - 1
    token = _token(claims={"iat": expired_at - 60, "exp": expired_at})

    assert ClerkIdentityProvider(_settings()).verify(token) is None


def test_audience_can_be_deliberately_unused() -> None:
    token = _token(claims={"aud": None})

    assert ClerkIdentityProvider(_settings(audience=None)).verify(token) == VerifiedIdentity(
        provider="clerk",
        provider_subject="user_private_beta_123",
    )


def test_verification_remains_networkless_when_clerk_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("token verification attempted a Clerk API call")

    monkeypatch.setattr("clerk_backend_api.security.verifytoken.httpx.Client", refuse_network)

    assert ClerkIdentityProvider(_settings()).verify(_token()) is not None
