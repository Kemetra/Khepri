from __future__ import annotations

import base64
import json
import re
from typing import Any, Protocol

from khepri.rra.intake import StoragePolicyViolation, StoredObject

_KMS_KEY_ARN = re.compile(
    r"^arn:aws:kms:me-central-1:\d{12}:"
    r"key/[0-9a-fA-F-]{36}$"
)
_ACCOUNT_ID = re.compile(r"^\d{12}$")


class S3Client(Protocol):
    def put_object(self, **kwargs: object) -> dict[str, Any]: ...

    def delete_object(self, **kwargs: object) -> dict[str, Any]: ...

    def list_multipart_uploads(self, **kwargs: object) -> dict[str, Any]: ...

    def abort_multipart_upload(self, **kwargs: object) -> dict[str, Any]: ...


class S3EncryptedObjectStore:
    def __init__(
        self,
        *,
        client: S3Client,
        bucket: str,
        kms_key_arn: str,
        expected_bucket_owner: str,
    ) -> None:
        if not bucket:
            raise ValueError("S3 bucket is required.")
        if _KMS_KEY_ARN.fullmatch(kms_key_arn) is None:
            raise ValueError("KMS key must be a key ARN in me-central-1.")
        if _ACCOUNT_ID.fullmatch(expected_bucket_owner) is None:
            raise ValueError("Expected bucket owner must be a 12-digit account ID.")
        self._client = client
        self._bucket = bucket
        self._kms_key_arn = kms_key_arn
        self._expected_bucket_owner = expected_bucket_owner

    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
        encryption_context: dict[str, str],
    ) -> StoredObject:
        checksum = base64.b64encode(bytes.fromhex(sha256_hex)).decode("ascii")
        context = base64.b64encode(
            json.dumps(
                encryption_context,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).decode("ascii")
        response = self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=content,
            ContentLength=len(content),
            ContentType=media_type,
            ChecksumSHA256=checksum,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=self._kms_key_arn,
            SSEKMSEncryptionContext=context,
            BucketKeyEnabled=True,
            ExpectedBucketOwner=self._expected_bucket_owner,
            IfNoneMatch="*",
        )
        if not self._response_proves_policy(response, checksum):
            self._delete_unversioned(key)
            raise StoragePolicyViolation("S3 did not prove the required storage policy.")
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256_hex=sha256_hex,
            media_type=media_type,
            encryption_algorithm="aws:kms",
            kms_key_id=self._kms_key_arn,
        )

    def delete(self, key: str) -> None:
        self._delete_unversioned(key)

    def abort_multipart_uploads(self, prefix: str) -> None:
        base_parameters = {
            "Bucket": self._bucket,
            "Prefix": prefix,
            "ExpectedBucketOwner": self._expected_bucket_owner,
        }
        parameters: dict[str, object] = dict(base_parameters)
        while True:
            response = self._client.list_multipart_uploads(**parameters)
            for upload in response.get("Uploads") or []:
                key = upload["Key"]
                upload_id = upload["UploadId"]
                if not isinstance(key, str) or not key.startswith(prefix):
                    raise StoragePolicyViolation(
                        "S3 returned a multipart upload outside the deletion scope."
                    )
                self._client.abort_multipart_upload(
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id,
                    ExpectedBucketOwner=self._expected_bucket_owner,
                )
            if response.get("IsTruncated") is not True:
                break
            key_marker = response.get("NextKeyMarker")
            upload_marker = response.get("NextUploadIdMarker")
            if not isinstance(key_marker, str) or not isinstance(upload_marker, str):
                raise StoragePolicyViolation("S3 multipart pagination is incomplete.")
            parameters = {
                **base_parameters,
                "KeyMarker": key_marker,
                "UploadIdMarker": upload_marker,
            }
        confirmation = self._client.list_multipart_uploads(**base_parameters)
        if confirmation.get("Uploads") or confirmation.get("IsTruncated") is True:
            raise StoragePolicyViolation("S3 multipart uploads remain after cleanup.")

    def _delete_unversioned(self, key: str) -> None:
        response = self._client.delete_object(
            Bucket=self._bucket,
            Key=key,
            ExpectedBucketOwner=self._expected_bucket_owner,
        )
        if response.get("DeleteMarker") is True or "VersionId" in response:
            raise StoragePolicyViolation(
                "S3 reported versioned deletion semantics for ephemeral content."
            )

    def _response_proves_policy(
        self,
        response: dict[str, Any],
        checksum: str,
    ) -> bool:
        return (
            response.get("ChecksumSHA256") == checksum
            and response.get("ServerSideEncryption") == "aws:kms"
            and response.get("SSEKMSKeyId") == self._kms_key_arn
            and response.get("BucketKeyEnabled") is True
            and "VersionId" not in response
        )
