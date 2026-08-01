"""Where the local stack lives, read from the environment with local defaults.

Defaults are supplied here, unlike `khepri.infra.sizing`, and the difference is
deliberate. Sizing refuses a default because a governed value guessed by code is
indistinguishable from an approved one once deployed. A local endpoint URL is not
a governed value at all: nothing downstream records it, no digest covers it, and
being wrong about it fails loudly on the next call rather than quietly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_S3_ENDPOINT = "http://127.0.0.1:14566"
DEFAULT_REGION = "me-central-1"
DEFAULT_BUCKET = "khepri-local-content"
DEFAULT_DATABASE_URL = "postgresql+psycopg://khepri:khepri@127.0.0.1:15432/khepri"
DEFAULT_OBJECT_ROOT = "khepri-local"


@dataclass(frozen=True, slots=True)
class LocalSettings:
    """Every endpoint and name the local stack needs, resolved once."""

    s3_endpoint: str = DEFAULT_S3_ENDPOINT
    region: str = DEFAULT_REGION
    bucket: str = DEFAULT_BUCKET
    database_url: str = DEFAULT_DATABASE_URL
    access_key: str = "test"
    secret_key: str = "test"

    @classmethod
    def from_environment(cls) -> LocalSettings:
        return cls(
            s3_endpoint=os.environ.get("KHEPRI_LOCAL_S3_ENDPOINT", DEFAULT_S3_ENDPOINT),
            region=os.environ.get("KHEPRI_LOCAL_REGION", DEFAULT_REGION),
            bucket=os.environ.get("KHEPRI_LOCAL_BUCKET", DEFAULT_BUCKET),
            database_url=os.environ.get("KHEPRI_LOCAL_DATABASE_URL", DEFAULT_DATABASE_URL),
            access_key=os.environ.get("KHEPRI_LOCAL_ACCESS_KEY", "test"),
            secret_key=os.environ.get("KHEPRI_LOCAL_SECRET_KEY", "test"),
        )


__all__ = [
    "DEFAULT_BUCKET",
    "DEFAULT_DATABASE_URL",
    "DEFAULT_OBJECT_ROOT",
    "DEFAULT_REGION",
    "DEFAULT_S3_ENDPOINT",
    "LocalSettings",
]
