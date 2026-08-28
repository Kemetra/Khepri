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
# Any string the S3 client will accept. `us-east-1` is the conventional default
# for S3-compatible emulators; the retired `me-central-1` was carried over from the
# AWS-specific model `KHEPRI-DEC-028` replaced and named a region nothing uses.
DEFAULT_REGION = "us-east-1"
DEFAULT_BUCKET = "khepri-local-content"
DEFAULT_DATABASE_URL = "postgresql+psycopg://khepri:khepri@127.0.0.1:15432/khepri"
DEFAULT_OBJECT_ROOT = "khepri-local"
# These must match `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD` in
# `docker-compose.local.yml`. MinIO, unlike the LocalStack it replaced, rejects any
# credential but its configured root user, and requires a secret of at least eight
# characters -- which is why the secret is not simply `test`. Neither value is a
# secret: the local stack holds no real content.
DEFAULT_ACCESS_KEY = "test"
DEFAULT_SECRET_KEY = "testtest"
# 32 zero bytes, base64. Deliberately not a secret and deliberately not generated:
# a random local key would make an object written by one process unreadable by the
# next, and this key protects nothing.
DEFAULT_MASTER_KEY_BASE64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


@dataclass(frozen=True, slots=True)
class LocalSettings:
    """Every endpoint and name the local stack needs, resolved once."""

    s3_endpoint: str = DEFAULT_S3_ENDPOINT
    region: str = DEFAULT_REGION
    bucket: str = DEFAULT_BUCKET
    database_url: str = DEFAULT_DATABASE_URL
    access_key: str = DEFAULT_ACCESS_KEY
    secret_key: str = DEFAULT_SECRET_KEY
    # Local development runs the same envelope encryption as the runtime rather
    # than a plaintext shortcut: two correctness models would mean local runs
    # never exercise the path that matters. A fixed non-secret key is right here
    # precisely because the local stack holds no real content.
    master_key_base64: str = DEFAULT_MASTER_KEY_BASE64

    @classmethod
    def from_environment(cls) -> LocalSettings:
        return cls(
            s3_endpoint=os.environ.get("KHEPRI_LOCAL_S3_ENDPOINT", DEFAULT_S3_ENDPOINT),
            region=os.environ.get("KHEPRI_LOCAL_REGION", DEFAULT_REGION),
            bucket=os.environ.get("KHEPRI_LOCAL_BUCKET", DEFAULT_BUCKET),
            database_url=os.environ.get("KHEPRI_LOCAL_DATABASE_URL", DEFAULT_DATABASE_URL),
            access_key=os.environ.get("KHEPRI_LOCAL_ACCESS_KEY", DEFAULT_ACCESS_KEY),
            secret_key=os.environ.get("KHEPRI_LOCAL_SECRET_KEY", DEFAULT_SECRET_KEY),
            master_key_base64=os.environ.get(
                "KHEPRI_LOCAL_MASTER_KEY", DEFAULT_MASTER_KEY_BASE64
            ),
        )


__all__ = [
    "DEFAULT_ACCESS_KEY",
    "DEFAULT_BUCKET",
    "DEFAULT_DATABASE_URL",
    "DEFAULT_SECRET_KEY",
    "DEFAULT_MASTER_KEY_BASE64",
    "DEFAULT_OBJECT_ROOT",
    "DEFAULT_REGION",
    "DEFAULT_S3_ENDPOINT",
    "LocalSettings",
]
