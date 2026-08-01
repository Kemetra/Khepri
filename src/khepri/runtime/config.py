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
from dataclasses import dataclass

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

_ACCOUNT_ID = re.compile(r"^\d{12}$")
_KMS_KEY_ARN = re.compile(
    r"^arn:aws:kms:me-central-1:\d{12}:"
    r"key/[0-9a-fA-F-]{36}$"
)
_SECRET_FIELDS = frozenset({"username", "password", "engine", "host", "port", "dbname"})


class RuntimeConfigurationError(ValueError):
    """A required runtime coordinate is absent or outside the approved boundary."""


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    database_url: URL
    region: str
    bucket: str
    kms_key_arn: str
    expected_bucket_owner: str
    queue_url: str
    dead_letter_queue_url: str

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> RuntimeSettings:
        source = os.environ if environment is None else environment
        region = _required(source, REGION_VARIABLE)
        if region != REGION:
            raise RuntimeConfigurationError(f"{REGION_VARIABLE} must be {REGION}.")
        kms_key_arn = _required(source, KMS_KEY_ARN_VARIABLE)
        if _KMS_KEY_ARN.fullmatch(kms_key_arn) is None:
            raise RuntimeConfigurationError(
                f"{KMS_KEY_ARN_VARIABLE} must be a KMS key ARN in {REGION}."
            )
        owner = _required(source, BUCKET_OWNER_VARIABLE)
        if _ACCOUNT_ID.fullmatch(owner) is None:
            raise RuntimeConfigurationError(
                f"{BUCKET_OWNER_VARIABLE} must be a 12-digit account ID."
            )
        queue_url = _required(source, QUEUE_URL_VARIABLE)
        dead_letter_url = _required(source, DEAD_LETTER_QUEUE_URL_VARIABLE)
        if dead_letter_url == queue_url:
            raise RuntimeConfigurationError(
                f"{DEAD_LETTER_QUEUE_URL_VARIABLE} must differ from {QUEUE_URL_VARIABLE}."
            )
        return cls(
            database_url=_database_url(_required(source, DATABASE_SECRET_VARIABLE)),
            region=region,
            bucket=_required(source, BUCKET_VARIABLE),
            kms_key_arn=kms_key_arn,
            expected_bucket_owner=owner,
            queue_url=queue_url,
            dead_letter_queue_url=dead_letter_url,
        )


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RuntimeConfigurationError(f"{name} is required.")
    return value


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


def _database_secret(encoded: str) -> dict[str, object]:
    try:
        value = json.loads(encoded)
    except (TypeError, ValueError) as error:
        raise _invalid_database_secret() from error
    if not isinstance(value, dict) or not set(value) >= _SECRET_FIELDS:
        raise _invalid_database_secret()
    for name in ("username", "password", "engine", "host", "dbname"):
        if not isinstance(value[name], str) or not value[name].strip():
            raise _invalid_database_secret()
    port = value["port"]
    if isinstance(port, bool) or not isinstance(port, int) or not 0 < port <= 65535:
        raise _invalid_database_secret()
    if value["engine"] != "postgres" or value["dbname"] != DATABASE_NAME:
        raise _invalid_database_secret()
    return value


def _invalid_database_secret() -> RuntimeConfigurationError:
    return RuntimeConfigurationError(
        f"{DATABASE_SECRET_VARIABLE} database secret is invalid."
    )


__all__ = [
    "BUCKET_OWNER_VARIABLE",
    "BUCKET_VARIABLE",
    "DATABASE_SECRET_VARIABLE",
    "DEAD_LETTER_QUEUE_URL_VARIABLE",
    "KMS_KEY_ARN_VARIABLE",
    "QUEUE_URL_VARIABLE",
    "REGION",
    "REGION_VARIABLE",
    "RuntimeConfigurationError",
    "RuntimeSettings",
]
