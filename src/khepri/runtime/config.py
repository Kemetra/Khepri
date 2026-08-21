"""Fail-closed runtime coordinates supplied by an ECS task definition.

The database credential arrives as one Secrets Manager JSON value. It is
parsed directly into a SQLAlchemy URL object so the password is never joined
into a plain connection string or included in this settings object's repr.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, TypedDict
from urllib.parse import urlsplit

from sqlalchemy import URL

REGION = "me-central-1"
DATABASE_NAME = "khepri"

DATABASE_SECRET_VARIABLE = "KHEPRI_DATABASE_SECRET"
REGION_VARIABLE = "KHEPRI_AWS_REGION"
BUCKET_VARIABLE = "KHEPRI_BUCKET"
KMS_KEY_ARN_VARIABLE = "KHEPRI_KMS_KEY_ARN"
BUCKET_OWNER_VARIABLE = "KHEPRI_EXPECTED_BUCKET_OWNER"
QUEUE_URL_VARIABLE = "KHEPRI_QUEUE_URL"
DEAD_LETTER_QUEUE_URL_VARIABLE = "KHEPRI_DLQ_URL"
CLERK_MODE_VARIABLE = "KHEPRI_CLERK_MODE"
CLERK_ISSUER_VARIABLE = "KHEPRI_CLERK_ISSUER"
CLERK_JWT_KEY_VARIABLE = "KHEPRI_CLERK_JWT_KEY"
CLERK_KEY_ID_VARIABLE = "KHEPRI_CLERK_KEY_ID"
CLERK_AUTHORIZED_PARTIES_VARIABLE = "KHEPRI_CLERK_AUTHORIZED_PARTIES"
CLERK_AUDIENCE_VARIABLE = "KHEPRI_CLERK_AUDIENCE"

_ACCOUNT_ID = re.compile(r"^\d{12}$")
_KMS_KEY_ARN = re.compile(
    r"^arn:aws:kms:me-central-1:\d{12}:"
    r"key/[0-9a-fA-F-]{36}$"
)
_SECRET_FIELDS = frozenset({"username", "password", "engine", "host", "port", "dbname"})


class RuntimeConfigurationError(ValueError):
    """A required runtime coordinate is absent or outside the approved boundary."""


class _DatabaseSecret(TypedDict):
    username: str
    password: str
    engine: str
    host: str
    port: int
    dbname: str


class _RuntimeCoordinates(TypedDict):
    region: str
    bucket: str
    kms_key_arn: str
    expected_bucket_owner: str
    queue_url: str
    dead_letter_queue_url: str


ClerkMode = Literal["development", "test", "private_beta"]
_CLERK_MODES = frozenset({"development", "test", "private_beta"})


@dataclass(frozen=True, slots=True)
class ClerkIdentitySettings:
    """Pinned, networkless trust coordinates for one Clerk instance."""

    mode: ClerkMode
    issuer: str
    jwt_key: str = field(repr=False)
    key_id: str
    authorized_parties: tuple[str, ...]
    audience: str | None


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    database_url: URL
    region: str
    bucket: str
    kms_key_arn: str
    expected_bucket_owner: str
    queue_url: str
    dead_letter_queue_url: str
    clerk: ClerkIdentitySettings | None

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> RuntimeSettings:
        source = _environment_source(environment)
        return cls(
            database_url=_database_url(_required(source, DATABASE_SECRET_VARIABLE)),
            **_runtime_coordinates(source),
            clerk=_clerk_settings(source),
        )


def _environment_source(
    environment: Mapping[str, str] | None,
) -> Mapping[str, str]:
    return os.environ if environment is None else environment


def _runtime_coordinates(environment: Mapping[str, str]) -> _RuntimeCoordinates:
    queue_url, dead_letter_url = _queue_urls(environment)
    return _RuntimeCoordinates(
        region=_region(environment),
        bucket=_required(environment, BUCKET_VARIABLE),
        kms_key_arn=_kms_key_arn(environment),
        expected_bucket_owner=_bucket_owner(environment),
        queue_url=queue_url,
        dead_letter_queue_url=dead_letter_url,
    )


def _region(environment: Mapping[str, str]) -> str:
    region = _required(environment, REGION_VARIABLE)
    if region != REGION:
        raise RuntimeConfigurationError(f"{REGION_VARIABLE} must be {REGION}.")
    return region


def _kms_key_arn(environment: Mapping[str, str]) -> str:
    key_arn = _required(environment, KMS_KEY_ARN_VARIABLE)
    if _KMS_KEY_ARN.fullmatch(key_arn) is None:
        raise RuntimeConfigurationError(
            f"{KMS_KEY_ARN_VARIABLE} must be a KMS key ARN in {REGION}."
        )
    return key_arn


def _bucket_owner(environment: Mapping[str, str]) -> str:
    owner = _required(environment, BUCKET_OWNER_VARIABLE)
    if _ACCOUNT_ID.fullmatch(owner) is None:
        raise RuntimeConfigurationError(
            f"{BUCKET_OWNER_VARIABLE} must be a 12-digit account ID."
        )
    return owner


def _queue_urls(environment: Mapping[str, str]) -> tuple[str, str]:
    queue_url = _required(environment, QUEUE_URL_VARIABLE)
    dead_letter_url = _required(environment, DEAD_LETTER_QUEUE_URL_VARIABLE)
    if dead_letter_url == queue_url:
        raise RuntimeConfigurationError(
            f"{DEAD_LETTER_QUEUE_URL_VARIABLE} must differ from {QUEUE_URL_VARIABLE}."
        )
    return queue_url, dead_letter_url


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeConfigurationError(f"{name} is required.")
    return value


def _clerk_settings(environment: Mapping[str, str]) -> ClerkIdentitySettings | None:
    mode = environment.get(CLERK_MODE_VARIABLE, "disabled")
    if mode == "disabled":
        return None
    if mode not in _CLERK_MODES:
        raise RuntimeConfigurationError(
            f"{CLERK_MODE_VARIABLE} must be disabled, development, test, or private_beta."
        )
    return ClerkIdentitySettings(
        mode=mode,  # type: ignore[arg-type]
        issuer=_clerk_issuer(environment),
        jwt_key=_clerk_public_key(environment),
        key_id=_required(environment, CLERK_KEY_ID_VARIABLE),
        authorized_parties=_clerk_authorized_parties(environment),
        audience=_optional(environment, CLERK_AUDIENCE_VARIABLE),
    )


def _clerk_issuer(environment: Mapping[str, str]) -> str:
    issuer = _required(environment, CLERK_ISSUER_VARIABLE)
    location = urlsplit(issuer)
    if location.scheme != "https" or not location.netloc or location.query or location.fragment:
        raise RuntimeConfigurationError(f"{CLERK_ISSUER_VARIABLE} must be an HTTPS issuer URL.")
    return issuer.rstrip("/")


def _clerk_public_key(environment: Mapping[str, str]) -> str:
    key = _required(environment, CLERK_JWT_KEY_VARIABLE)
    if not key.startswith("-----BEGIN PUBLIC KEY-----") or not key.rstrip().endswith(
        "-----END PUBLIC KEY-----"
    ):
        raise RuntimeConfigurationError(
            f"{CLERK_JWT_KEY_VARIABLE} must be a PEM public key."
        )
    return key


def _clerk_authorized_parties(environment: Mapping[str, str]) -> tuple[str, ...]:
    name = CLERK_AUTHORIZED_PARTIES_VARIABLE
    encoded = _required(environment, name)
    try:
        parties = json.loads(encoded)
    except ValueError as error:
        raise RuntimeConfigurationError(f"{name} must be a JSON string array.") from error
    valid = (
        isinstance(parties, list)
        and bool(parties)
        and all(isinstance(party, str) and party.strip() for party in parties)
        and len(parties) == len(set(parties))
    )
    if not valid:
        raise RuntimeConfigurationError(f"{name} must be a non-empty JSON string array.")
    return tuple(parties)


def _optional(environment: Mapping[str, str], name: str) -> str | None:
    return None if name not in environment else _required(environment, name)


def _database_url(encoded: str) -> URL:
    document = _database_secret(encoded)
    return URL.create(
        "postgresql+psycopg",
        username=document["username"],
        password=document["password"],
        host=document["host"],
        port=document["port"],
        database=document["dbname"],
        query={"sslmode": "require"},
    )


def _database_secret(encoded: str) -> _DatabaseSecret:
    document = _decoded_database_secret(encoded)
    if not set(document) >= _SECRET_FIELDS:
        raise _invalid_database_secret()
    return _DatabaseSecret(
        username=_secret_text(document, "username"),
        password=_secret_text(document, "password"),
        engine=_exact_secret_text(document, "engine", "postgres"),
        host=_secret_text(document, "host"),
        port=_secret_port(document),
        dbname=_exact_secret_text(document, "dbname", DATABASE_NAME),
    )


def _decoded_database_secret(encoded: str) -> dict[str, object]:
    try:
        value = json.loads(encoded)
    except (TypeError, ValueError) as error:
        raise _invalid_database_secret() from error
    if not isinstance(value, dict):
        raise _invalid_database_secret()
    return value


def _secret_text(document: Mapping[str, object], name: str) -> str:
    value = document[name]
    if not isinstance(value, str) or not value.strip():
        raise _invalid_database_secret()
    return value


def _exact_secret_text(
    document: Mapping[str, object],
    name: str,
    expected: str,
) -> str:
    value = _secret_text(document, name)
    if value != expected:
        raise _invalid_database_secret()
    return value


def _secret_port(document: Mapping[str, object]) -> int:
    port = document["port"]
    if isinstance(port, bool):
        raise _invalid_database_secret()
    if not isinstance(port, int):
        raise _invalid_database_secret()
    if port not in range(1, 65536):
        raise _invalid_database_secret()
    return port


def _invalid_database_secret() -> RuntimeConfigurationError:
    return RuntimeConfigurationError(
        f"{DATABASE_SECRET_VARIABLE} database secret is invalid."
    )


__all__ = [
    "BUCKET_OWNER_VARIABLE",
    "BUCKET_VARIABLE",
    "CLERK_AUDIENCE_VARIABLE",
    "CLERK_AUTHORIZED_PARTIES_VARIABLE",
    "CLERK_ISSUER_VARIABLE",
    "CLERK_JWT_KEY_VARIABLE",
    "CLERK_KEY_ID_VARIABLE",
    "CLERK_MODE_VARIABLE",
    "ClerkIdentitySettings",
    "DATABASE_SECRET_VARIABLE",
    "DEAD_LETTER_QUEUE_URL_VARIABLE",
    "KMS_KEY_ARN_VARIABLE",
    "QUEUE_URL_VARIABLE",
    "REGION",
    "REGION_VARIABLE",
    "RuntimeConfigurationError",
    "RuntimeSettings",
]
