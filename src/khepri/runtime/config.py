"""Fail-closed runtime coordinates supplied by an ECS task definition.

The database credential arrives as one Secrets Manager JSON value. It is
parsed directly into a SQLAlchemy URL object so the password is never joined
into a plain connection string or included in this settings object's repr.
"""

from __future__ import annotations

import base64
import json
import os
from binascii import Error as BinasciiError
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, TypedDict
from urllib.parse import urlsplit

from sqlalchemy import URL

from khepri.rra.envelope import EnvelopeError, MasterKey

DATABASE_NAME = "khepri"

DATABASE_SECRET_VARIABLE = "KHEPRI_DATABASE_SECRET"
# `KHEPRI-DEC-008` states the runtime as a capability contract, so the storage coordinates are the
# ones an S3-compatible client needs and nothing more. There is no region allowlist and no account
# identifier: a region is whatever the configured endpoint expects, and ownership is established by
# the credentials rather than asserted on every call.
STORAGE_ENDPOINT_VARIABLE = "KHEPRI_STORAGE_ENDPOINT"
STORAGE_REGION_VARIABLE = "KHEPRI_STORAGE_REGION"
BUCKET_VARIABLE = "KHEPRI_BUCKET"
# The envelope master key, base64-encoded 32 bytes, drawn from the secret store. The secret
# *source* is a deployment decision no artifact settles; this is only the boundary it arrives
# through.
MASTER_KEY_VARIABLE = "KHEPRI_STORAGE_MASTER_KEY"
# Inert. `KHEPRI-DEC-008` removed Amazon SQS, "its adapter, and its one-message
# driver", and job delivery is now the PostgreSQL claim query -- but the runtime went
# on *requiring* both URLs and rejecting them when equal, so every new environment had
# to invent two values nothing read. That requirement is gone: neither name reaches
# `RuntimeSettings`, `_RuntimeCoordinates`, or any `_required` call, and an environment
# still carrying them boots and ignores them.
#
# The names survive only because `src/khepri/infra/compute.py` writes them into the
# retired AWS task definition it describes, and that module is frozen reference under
# the same decision -- closed to new slices, kept green by CI, not the deployment path.
# Deleting them here would edit the frozen example by proxy.
QUEUE_URL_VARIABLE = "KHEPRI_QUEUE_URL"
DEAD_LETTER_QUEUE_URL_VARIABLE = "KHEPRI_DLQ_URL"
CLERK_MODE_VARIABLE = "KHEPRI_CLERK_MODE"
CLERK_ISSUER_VARIABLE = "KHEPRI_CLERK_ISSUER"
CLERK_JWT_KEY_VARIABLE = "KHEPRI_CLERK_JWT_KEY"
CLERK_KEY_ID_VARIABLE = "KHEPRI_CLERK_KEY_ID"
CLERK_AUTHORIZED_PARTIES_VARIABLE = "KHEPRI_CLERK_AUTHORIZED_PARTIES"
CLERK_AUDIENCE_VARIABLE = "KHEPRI_CLERK_AUDIENCE"

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
    storage_endpoint: str
    storage_region: str
    bucket: str
    master_key: MasterKey


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
    storage_endpoint: str
    storage_region: str
    bucket: str
    master_key: MasterKey
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
    return _RuntimeCoordinates(
        storage_endpoint=_storage_endpoint(environment),
        storage_region=_required(environment, STORAGE_REGION_VARIABLE),
        bucket=_required(environment, BUCKET_VARIABLE),
        master_key=_master_key(environment),
    )


def _storage_endpoint(environment: Mapping[str, str]) -> str:
    """Any HTTPS S3-compatible endpoint. No provider is recognised by name."""
    endpoint = _required(environment, STORAGE_ENDPOINT_VARIABLE)
    location = urlsplit(endpoint)
    if location.scheme != "https" or not location.netloc or location.query or location.fragment:
        raise RuntimeConfigurationError(
            f"{STORAGE_ENDPOINT_VARIABLE} must be an HTTPS endpoint URL."
        )
    return endpoint.rstrip("/")


def _master_key(environment: Mapping[str, str]) -> MasterKey:
    """Decode the envelope master key, refusing anything that is not 32 bytes.

    The error names the variable and never the value. A malformed key that was
    echoed here would be echoed into whatever log caught the startup failure.
    """
    encoded = _required(environment, MASTER_KEY_VARIABLE)
    try:
        material = base64.b64decode(encoded, validate=True)
    except (BinasciiError, ValueError) as error:
        raise RuntimeConfigurationError(
            f"{MASTER_KEY_VARIABLE} must be base64-encoded."
        ) from error
    try:
        return MasterKey(material=material)
    except EnvelopeError as error:
        raise RuntimeConfigurationError(
            f"{MASTER_KEY_VARIABLE} must decode to 32 bytes."
        ) from error


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
    "MASTER_KEY_VARIABLE",
    "QUEUE_URL_VARIABLE",
    "STORAGE_ENDPOINT_VARIABLE",
    "STORAGE_REGION_VARIABLE",
    "RuntimeConfigurationError",
    "RuntimeSettings",
]
