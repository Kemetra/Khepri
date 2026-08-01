"""Point the real `S3EncryptedObjectStore` at a local S3-compatible endpoint.

**There is no local object store class here, and that is the point.** An earlier
plan for this slice was a `FilesystemObjectStore` implementing
`EncryptedObjectStore` over a directory. It cannot be written honestly:
`intake._storage_response_is_valid` requires `encryption_algorithm == "aws:kms"`
with a non-empty key id, and `rra_uploads` carries a CHECK constraint
(`ck_upload_kms_encryption`) enforcing the same string. A filesystem store
returning it would persist a durable claim that plaintext bytes on disk are
KMS-encrypted. That is fabricated evidence, not a test double, and the fact that
it would satisfy every assertion is exactly what makes it dangerous.

So this module supplies a real endpoint instead. LocalStack provides genuine KMS:
`create_key` returns an actual `me-central-1` ARN over a 12-digit account, the
object really is encrypted with it, and `put_object` echoes back the same ARN. The
unmodified store's five policy proofs then pass because they are true, not because
something agreed to say so.

**MinIO does not work here**, and the reason is worth recording. Its SSE-KMS
encryption is real, but it rewrites `SSEKMSKeyId` to the fixed form
`arn:aws:kms:<keyname>`, which can express neither region nor account, and it never
returns `BucketKeyEnabled=True`. Three of the five proofs pass and two cannot.

The bucket is created **unversioned** deliberately: `_response_proves_policy`
rejects any response carrying a `VersionId`, because RRA-002 requires deletion to
actually delete rather than leave a recoverable prior version behind.
"""

from __future__ import annotations

from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from khepri.local.config import LocalSettings
from khepri.rra.storage import S3EncryptedObjectStore

_KEY_DESCRIPTION = "khepri local beta content key"


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


def ensure_local_key(kms: Any) -> tuple[str, str]:
    """Find or create the local content key, and return its ARN and account.

    Reused across restarts by description rather than recreated, so a bucket
    written before a restart is still readable after one.
    """
    for entry in kms.list_keys().get("Keys", []):
        described = kms.describe_key(KeyId=entry["KeyId"])["KeyMetadata"]
        if described.get("Description") == _KEY_DESCRIPTION:
            return described["Arn"], described["AWSAccountId"]
    created = kms.create_key(Description=_KEY_DESCRIPTION)["KeyMetadata"]
    return created["Arn"], created["AWSAccountId"]


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
    kms = local_client(settings, "kms")
    s3 = local_client(settings, "s3")
    key_arn, account_id = ensure_local_key(kms)
    ensure_local_bucket(s3, settings)
    return S3EncryptedObjectStore(
        client=s3,
        bucket=settings.bucket,
        kms_key_arn=key_arn,
        expected_bucket_owner=account_id,
    )


__all__ = [
    "build_local_object_store",
    "ensure_local_bucket",
    "ensure_local_key",
    "local_client",
]
