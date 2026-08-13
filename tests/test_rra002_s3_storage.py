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
SHA256_HEX = "492d5ea496056f1a6a6592241032fab764c321596317930b4fa0e1e8bc3b7470"
SHA256_BASE64 = "SS1epJYFbxpqZZIkEDL6t2TDIVljF5MLT6Dh6Lw7dHA="
CONTEXT_BASE64 = (
    "eyJvd25lcl9pZCI6Im93bl9hbHBoYSIsInNlc3Npb25faWQiOiJzZXNfYWxwaGEi"
    "LCJ1cGxvYWRfaWQiOiJ1cGxfYWxwaGEifQ=="
)


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


def test_store_rejects_a_kms_key_outside_the_approved_region() -> None:
    client = boto3.client(
        "s3",
        region_name="me-central-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    with pytest.raises(ValueError):
        S3EncryptedObjectStore(
            client=client,
            bucket=BUCKET,
            kms_key_arn=KMS_KEY_ARN.replace("me-central-1", "eu-west-1"),
            expected_bucket_owner=OWNER_ACCOUNT,
        )


def test_store_rejects_an_invalid_expected_bucket_owner() -> None:
    client = boto3.client(
        "s3",
        region_name="me-central-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    with pytest.raises(ValueError):
        S3EncryptedObjectStore(
            client=client,
            bucket=BUCKET,
            kms_key_arn=KMS_KEY_ARN,
            expected_bucket_owner="not-an-account",
        )


def test_store_rejects_an_empty_bucket_name() -> None:
    client = boto3.client(
        "s3",
        region_name="me-central-1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )

    with pytest.raises(ValueError):
        S3EncryptedObjectStore(
            client=client,
            bucket="",
            kms_key_arn=KMS_KEY_ARN,
            expected_bucket_owner=OWNER_ACCOUNT,
        )


def put_parameters() -> dict[str, object]:
    return {
        "Bucket": BUCKET,
        "Key": KEY,
        "Body": CONTENT,
        "ContentLength": len(CONTENT),
        "ContentType": "text/csv",
        "ChecksumSHA256": SHA256_BASE64,
        "ServerSideEncryption": "aws:kms",
        "SSEKMSKeyId": KMS_KEY_ARN,
        "SSEKMSEncryptionContext": CONTEXT_BASE64,
        "BucketKeyEnabled": True,
        "ExpectedBucketOwner": OWNER_ACCOUNT,
        "IfNoneMatch": "*",
    }


def test_put_sends_and_verifies_checksum_kms_context_and_owner_guard() -> None:
    store, stubber = store_and_stubber()
    stubber.add_response(
        "put_object",
        {
            "ChecksumSHA256": SHA256_BASE64,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY_ARN,
            "BucketKeyEnabled": True,
        },
        put_parameters(),
    )

    with stubber:
        stored = store.put(
            key=KEY,
            content=CONTENT,
            media_type="text/csv",
            sha256_hex=SHA256_HEX,
            encryption_context={
                "session_id": "ses_alpha",
                "upload_id": "upl_alpha",
                "owner_id": "own_alpha",
            },
        )

    assert stored.key == KEY
    assert stored.size_bytes == 8
    assert stored.sha256_hex == SHA256_HEX
    assert stored.media_type == "text/csv"
    assert stored.encryption_algorithm == "aws:kms"
    assert stored.kms_key_id == KMS_KEY_ARN


def test_put_or_verify_accepts_identical_preexisting_encrypted_content() -> None:
    store, stubber = store_and_stubber()
    stubber.add_client_error(
        "put_object",
        service_error_code="PreconditionFailed",
        http_status_code=412,
        expected_params=put_parameters(),
    )
    stubber.add_response(
        "get_object",
        {
            "Body": StreamingBody(io.BytesIO(CONTENT), len(CONTENT)),
            "ChecksumSHA256": SHA256_BASE64,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY_ARN,
        },
        {
            "Bucket": BUCKET,
            "Key": KEY,
            "ExpectedBucketOwner": OWNER_ACCOUNT,
            "ChecksumMode": "ENABLED",
        },
    )

    with stubber:
        result = store.put_or_verify(
            key=KEY,
            content=CONTENT,
            media_type="text/csv",
            sha256_hex=SHA256_HEX,
            encryption_context={
                "session_id": "ses_alpha",
                "upload_id": "upl_alpha",
                "owner_id": "own_alpha",
            },
        )

    assert result.created is False
    assert result.stored.sha256_hex == SHA256_HEX


@pytest.mark.parametrize(
    "response",
    [
        {
            "ChecksumSHA256": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY_ARN,
            "BucketKeyEnabled": True,
        },
        {
            "ChecksumSHA256": SHA256_BASE64,
            "ServerSideEncryption": "AES256",
            "BucketKeyEnabled": False,
        },
        {
            "ChecksumSHA256": SHA256_BASE64,
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": KMS_KEY_ARN,
            "BucketKeyEnabled": True,
            "VersionId": "unexpected-version",
        },
    ],
)
def test_put_removes_object_when_s3_does_not_prove_storage_policy(
    response: dict[str, object],
) -> None:
    store, stubber = store_and_stubber()
    stubber.add_response("put_object", response, put_parameters())
    stubber.add_response(
        "delete_object",
        {},
        {
            "Bucket": BUCKET,
            "Key": KEY,
            "ExpectedBucketOwner": OWNER_ACCOUNT,
        },
    )

    with stubber, pytest.raises(StoragePolicyViolation):
        store.put(
            key=KEY,
            content=CONTENT,
            media_type="text/csv",
            sha256_hex=SHA256_HEX,
            encryption_context={
                "owner_id": "own_alpha",
                "session_id": "ses_alpha",
                "upload_id": "upl_alpha",
            },
        )


def test_delete_is_idempotent_for_an_unversioned_bucket() -> None:
    store, stubber = store_and_stubber()
    expected = {
        "Bucket": BUCKET,
        "Key": KEY,
        "ExpectedBucketOwner": OWNER_ACCOUNT,
    }
    stubber.add_response("delete_object", {}, expected)
    stubber.add_response("delete_object", {}, expected)

    with stubber:
        store.delete(KEY)
        store.delete(KEY)


def test_delete_fails_closed_if_s3_reports_versioned_delete_semantics() -> None:
    store, stubber = store_and_stubber()
    stubber.add_response(
        "delete_object",
        {"DeleteMarker": True, "VersionId": "delete-marker-version"},
        {
            "Bucket": BUCKET,
            "Key": KEY,
            "ExpectedBucketOwner": OWNER_ACCOUNT,
        },
    )

    with stubber, pytest.raises(StoragePolicyViolation):
        store.delete(KEY)


def test_multipart_cleanup_aborts_and_confirms_every_upload_under_prefix() -> None:
    store, stubber = store_and_stubber()
    prefix = "owners/own_alpha/sessions/ses_alpha/"
    list_parameters = {
        "Bucket": BUCKET,
        "Prefix": prefix,
        "ExpectedBucketOwner": OWNER_ACCOUNT,
    }
    stubber.add_response(
        "list_multipart_uploads",
        {
            "IsTruncated": False,
            "Uploads": [{"Key": KEY, "UploadId": "multipart-alpha"}],
        },
        list_parameters,
    )
    stubber.add_response(
        "abort_multipart_upload",
        {},
        {
            "Bucket": BUCKET,
            "Key": KEY,
            "UploadId": "multipart-alpha",
            "ExpectedBucketOwner": OWNER_ACCOUNT,
        },
    )
    stubber.add_response(
        "list_multipart_uploads",
        {"IsTruncated": False, "Uploads": []},
        list_parameters,
    )

    with stubber:
        store.abort_multipart_uploads(prefix)


def test_multipart_cleanup_follows_both_s3_pagination_markers() -> None:
    store, stubber = store_and_stubber()
    prefix = "owners/own_alpha/sessions/ses_alpha/"
    base = {
        "Bucket": BUCKET,
        "Prefix": prefix,
        "ExpectedBucketOwner": OWNER_ACCOUNT,
    }
    second_key = f"{prefix}inputs/upl_beta"
    stubber.add_response(
        "list_multipart_uploads",
        {
            "IsTruncated": True,
            "NextKeyMarker": KEY,
            "NextUploadIdMarker": "multipart-alpha",
            "Uploads": [{"Key": KEY, "UploadId": "multipart-alpha"}],
        },
        base,
    )
    stubber.add_response(
        "abort_multipart_upload",
        {},
        {
            "Bucket": BUCKET,
            "Key": KEY,
            "UploadId": "multipart-alpha",
            "ExpectedBucketOwner": OWNER_ACCOUNT,
        },
    )
    stubber.add_response(
        "list_multipart_uploads",
        {
            "IsTruncated": False,
            "Uploads": [{"Key": second_key, "UploadId": "multipart-beta"}],
        },
        {
            **base,
            "KeyMarker": KEY,
            "UploadIdMarker": "multipart-alpha",
        },
    )
    stubber.add_response(
        "abort_multipart_upload",
        {},
        {
            "Bucket": BUCKET,
            "Key": second_key,
            "UploadId": "multipart-beta",
            "ExpectedBucketOwner": OWNER_ACCOUNT,
        },
    )
    stubber.add_response(
        "list_multipart_uploads",
        {"IsTruncated": False, "Uploads": []},
        base,
    )

    with stubber:
        store.abort_multipart_uploads(prefix)
