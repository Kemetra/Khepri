from __future__ import annotations

import io

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from khepri.rra.intake import StoragePolicyViolation
from khepri.rra.storage import S3EncryptedObjectStore

BUCKET = "khepri-beta-content"
KEY = "owners/own_alpha/sessions/ses_alpha/inputs/upl_alpha"
KMS_KEY_ARN = (
    "arn:aws:kms:me-central-1:123456789012:"
    "key/11111111-2222-3333-4444-555555555555"
)
OWNER_ACCOUNT = "123456789012"
CONTENT = b"a,b\n1,2\n"
SHA256_BASE64 = "SS1epJYFbxpqZZIkEDL6t2TDIVljF5MLT6Dh6Lw7dHA="


def store_and_stubber() -> tuple[S3EncryptedObjectStore, Stubber]:
    client = boto3.client(
        "s3",
        region_name="me-central-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return (
        S3EncryptedObjectStore(
            client=client,
            bucket=BUCKET,
            kms_key_arn=KMS_KEY_ARN,
            expected_bucket_owner=OWNER_ACCOUNT,
        ),
        Stubber(client),
    )


def get_parameters() -> dict[str, object]:
    return {
        "Bucket": BUCKET,
        "Key": KEY,
        "ExpectedBucketOwner": OWNER_ACCOUNT,
        "ChecksumMode": "ENABLED",
    }


def body(content: bytes = CONTENT) -> StreamingBody:
    return StreamingBody(io.BytesIO(content), len(content))


def test_get_returns_content_when_s3_proves_the_storage_policy() -> None:
    store, stubber = store_and_stubber()
    stubber.add_response(
        "get_object",
        {
            "Body": body(),
            "ChecksumSHA256": SHA256_BASE64,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY_ARN,
        },
        get_parameters(),
    )

    with stubber:
        assert store.get(KEY) == CONTENT


@pytest.mark.parametrize(
    "response",
    [
        {
            "Body": body(b"tampered"),
            "ChecksumSHA256": SHA256_BASE64,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY_ARN,
        },
        {
            "Body": body(),
            "ChecksumSHA256": SHA256_BASE64,
            "ServerSideEncryption": "AES256",
        },
        {
            "Body": body(),
            "ChecksumSHA256": SHA256_BASE64,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY_ARN.replace("me-central-1", "eu-west-1"),
        },
        {
            "Body": body(),
            "ChecksumSHA256": SHA256_BASE64,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY_ARN,
            "VersionId": "unexpected-version",
        },
    ],
)
def test_get_refuses_content_when_s3_does_not_prove_the_policy(
    response: dict[str, object],
) -> None:
    store, stubber = store_and_stubber()
    stubber.add_response("get_object", response, get_parameters())

    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY)
