"""Point the real `S3EncryptedObjectStore` at a local S3-compatible endpoint.

**There is no local object store class here, and that is still the point.** A
`FilesystemObjectStore` over a directory would have to report an encryption
algorithm it did not perform, and a durable claim that plaintext bytes on disk are
encrypted is fabricated evidence rather than a test double. Local development uses
the production class against a real endpoint instead, so the code exercised here is
the code that runs in the runtime.

**What `KHEPRI-DEC-028` changed about this module.** It used to provision a
LocalStack KMS key and pass its ARN and account to the store, because the store
proved its policy by reading `ServerSideEncryption`, `SSEKMSKeyId`, and
`BucketKeyEnabled` off the response. Encryption is now the application's own work,
so none of that is needed: no KMS client, no key, no account identifier. What
remains is an endpoint, a bucket, and the same envelope master key the runtime
uses.

**MinIO now works, and so does any conforming store.** The earlier note recorded
that MinIO could not be used because it rewrites `SSEKMSKeyId` to a form carrying
neither region nor account and never returns `BucketKeyEnabled=True`. Both facts
are still true and neither matters any more: the store no longer reads those
fields. The required surface is put, get, delete, list, abort multipart, and
`IfNoneMatch`.

**Local and runtime share one correctness model.** The local master key is a fixed
non-secret value from `khepri.local.config`, which is safe precisely because the
local stack holds no real content -- and important because a plaintext local path
would mean the encryption path were never exercised until deployment.

The bucket is created **unversioned** deliberately: the store rejects any response
carrying a `VersionId`, because `RRA-002` requires deletion to actually delete
rather than leave a recoverable prior version behind.
"""

from __future__ import annotations

import base64
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from khepri.local.config import LocalSettings
from khepri.rra.envelope import MasterKey
from khepri.rra.storage import S3EncryptedObjectStore


def local_client(settings: LocalSettings, service: str) -> Any:
    """A boto3 client aimed at the local endpoint rather than at AWS.

    Path addressing because a local endpoint has no per-bucket DNS, and explicit
    SigV4 so the request is signed the way the real service expects.
    """
    return boto3.client(
        service,
        endpoint_url=settings.s3_endpoint,
        region_name=settings.region,
        aws_access_key_id=settings.access_key,
        aws_secret_access_key=settings.secret_key,
        config=Config(
            s3={"addressing_style": "path"},
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def local_master_key(settings: LocalSettings) -> MasterKey:
    """The local envelope master key, decoded the same way the runtime decodes it."""
    return MasterKey(material=base64.b64decode(settings.master_key_base64, validate=True))


def ensure_local_bucket(s3: Any, settings: LocalSettings) -> None:
    """Create the content bucket if it is absent, and never enable versioning."""
    try:
        s3.head_bucket(Bucket=settings.bucket)
        return
    except ClientError:
        pass
    s3.create_bucket(
        Bucket=settings.bucket,
        CreateBucketConfiguration={"LocationConstraint": settings.region},
    )


def build_local_object_store(settings: LocalSettings) -> S3EncryptedObjectStore:
    """The production store class, unmodified, over a local endpoint."""
    s3 = local_client(settings, "s3")
    ensure_local_bucket(s3, settings)
    return S3EncryptedObjectStore(
        client=s3,
        bucket=settings.bucket,
        master_key=local_master_key(settings),
    )


__all__ = [
    "build_local_object_store",
    "ensure_local_bucket",
    "local_client",
    "local_master_key",
]
