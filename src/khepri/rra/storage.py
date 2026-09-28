"""Object storage over any S3-compatible API, with encryption Khepri performs itself.

**What changed and why.** This adapter used to prove its storage policy by reading
five fields off the `PutObject` response: the checksum, `ServerSideEncryption ==
"aws:kms"`, the exact customer managed key ARN, `BucketKeyEnabled`, and the
absence of a `VersionId`. `KHEPRI-DEC-028` retires that arrangement, because no
S3-compatible store outside AWS can satisfy it -- DigitalOcean Spaces has no
customer managed key and never returns `BucketKeyEnabled`, and MinIO rewrites the
key identifier to a form carrying neither region nor account. Asking a provider to
attest that it encrypted the bytes is also a weaker claim than encrypting them.

So the application encrypts. What crosses this boundary is ciphertext produced by
`khepri.rra.envelope`, and the remaining proof obligation is that the exact bytes
written are the bytes read back, which a digest settles without trusting any
provider header.

**What is still required of the store**, and it is deliberately little: put, get,
delete, list, and abort multipart uploads; `IfNoneMatch` for content-addressed
creation; and unversioned delete semantics. No encryption header, no key
identifier, no bucket-owner assertion, and no region is read from a response.

**No provider branches.** There is no `if provider == ...` here and there must
never be one. AWS, Spaces, Hetzner, and MinIO differ in endpoint and credentials,
which are deployment coordinates the client is constructed with, not application
behaviour.

**Digest semantics, which are two things.** `sha256_hex` on a request and on
`StoredObject` is the *plaintext* digest: it is the content address, it survives
encryption, and idempotent writes still key on it. `ciphertext_sha256_hex` is the
read-back proof and is different every time the same plaintext is stored, because
encryption is randomised. Conflating them would make content addressing
non-deterministic, so they never mix: one identifies content, the other identifies
one stored copy of it.

**Why `get` needs the record.** Verifying the read-back digest means knowing which
digest to expect, and only the caller's persisted row knows. `get` therefore takes
the recorded envelope metadata rather than discovering it, which also means a row
and an object that have drifted apart fail closed instead of returning whichever
one the reader happened to reach.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

from botocore.exceptions import ClientError

from khepri.rra.envelope import (
    ALGORITHM_AES_256_GCM,
    LEGACY_ENVELOPE_VERSION,
    WRITE_ENVELOPE_VERSION,
    EnvelopeError,
    ExpectedObject,
    MasterKey,
    assert_supported,
    envelope_version_of,
    open_envelope,
    seal,
)
from khepri.rra.intake import StoragePolicyViolation, StoredObject


class S3Client(Protocol):
    def put_object(self, **kwargs: object) -> dict[str, Any]: ...

    def get_object(self, **kwargs: object) -> dict[str, Any]: ...

    def delete_object(self, **kwargs: object) -> dict[str, Any]: ...

    def list_multipart_uploads(self, **kwargs: object) -> dict[str, Any]: ...

    def list_objects_v2(self, **kwargs: object) -> dict[str, Any]: ...

    def abort_multipart_upload(self, **kwargs: object) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class PutResult:
    """A stored object and whether this call created it."""

    stored: StoredObject
    created: bool


@dataclass(frozen=True, slots=True)
class ObjectWrite:
    key: str
    content: bytes
    media_type: str
    sha256_hex: str


@dataclass(frozen=True, slots=True)
class StoredEnvelope:
    """The recorded facts a read needs in order to verify what it fetched."""

    ciphertext_sha256_hex: str
    sha256_hex: str
    encryption_algorithm: str
    envelope_version: int


@dataclass(frozen=True, slots=True)
class Resealed:
    """What a stored `v1` object is now, and so what its row must record (#535)."""

    envelope_version: int
    ciphertext_sha256_hex: str
    #: `False` when a previous run had already written the object and this call only proved it.
    rewritten: bool


class S3EncryptedObjectStore:
    """Encrypts before writing, verifies before returning."""

    def __init__(
        self,
        *,
        client: S3Client,
        bucket: str,
        master_key: MasterKey,
    ) -> None:
        if not bucket:
            raise ValueError("Object storage bucket is required.")
        self._client = client
        self._bucket = bucket
        self._master_key = master_key

    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
    ) -> StoredObject:
        """Seal the content and write the ciphertext.

        The declared plaintext digest is checked against the bytes before
        anything is encrypted. A caller that mislabels its own content would
        otherwise produce an object whose recorded address does not describe it,
        and the mismatch would only surface on a later read.
        """
        if hashlib.sha256(content).hexdigest() != sha256_hex:
            raise StoragePolicyViolation("Content does not match its declared digest.")

        sealed = seal(plaintext=content, master_key=self._master_key, object_key=key)
        checksum = base64.b64encode(bytes.fromhex(sealed.ciphertext_sha256_hex)).decode("ascii")
        response = self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=sealed.envelope,
            ContentLength=len(sealed.envelope),
            ContentType=media_type,
            ChecksumSHA256=checksum,
            IfNoneMatch="*",
        )
        if not _write_is_unversioned(response, checksum):
            self._delete_unversioned(key)
            raise StoragePolicyViolation("Object storage did not confirm the written bytes.")
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256_hex=sha256_hex,
            media_type=media_type,
            encryption_algorithm=sealed.algorithm,
            envelope_version=sealed.envelope_version,
            ciphertext_sha256_hex=sealed.ciphertext_sha256_hex,
        )

    def put_or_verify(self, request: ObjectWrite) -> PutResult:
        """Create a content-addressed object, or prove the existing one matches.

        `IfNoneMatch="*"` makes creation conditional, so two writers racing on one
        content address cannot both believe they created it. The loser reads what
        is there and proves it represents the same plaintext -- which requires
        decrypting it, because randomised encryption means the stored ciphertext of
        identical content differs from what this call would have produced.
        """
        try:
            stored = self.put(
                key=request.key,
                content=request.content,
                media_type=request.media_type,
                sha256_hex=request.sha256_hex,
            )
        except ClientError as error:
            if not _is_precondition_failure(error):
                raise
            existing = self._read_and_verify_existing(request)
            return PutResult(stored=existing, created=False)
        return PutResult(stored=stored, created=True)

    def get(self, key: str, *, envelope: StoredEnvelope) -> bytes:
        """Fetch, verify the ciphertext, decrypt, and verify the plaintext."""
        try:
            # Inside the guard, not in front of it: an unreadable row must reach a
            # caller as the storage-policy failure every caller already handles,
            # not as a crypto-module exception nothing upstream catches.
            assert_supported(
                algorithm=envelope.encryption_algorithm,
                envelope_version=envelope.envelope_version,
            )
        except EnvelopeError as error:
            raise StoragePolicyViolation(str(error)) from error
        body = self._fetch(key)
        try:
            # The key comes from the caller's row, never from the object, so an
            # object moved with its row to another scope's key fails the tag.
            return open_envelope(
                envelope=body,
                master_key=self._master_key,
                expected=ExpectedObject(
                    object_key=key,
                    ciphertext_sha256_hex=envelope.ciphertext_sha256_hex,
                    plaintext_sha256_hex=envelope.sha256_hex,
                    envelope_version=envelope.envelope_version,
                ),
            )
        except EnvelopeError as error:
            # The envelope module's messages carry no key material and no content,
            # so the reason is safe to keep. It becomes a storage-policy failure
            # because that is what every caller already handles.
            raise StoragePolicyViolation(str(error)) from error

    def reseal(self, key: str, *, envelope: StoredEnvelope, media_type: str) -> Resealed:
        """Rewrite a stored `v1` object as the write version, bound to its key (#535).

        `envelope` is the row's record, and it must record `v1`: this verb retires one
        format and does nothing else. The fetched object is then one of two things.

        - **`v1`:** opened under both of the row's digests, re-sealed, and overwritten
          in place.
        - **The write version:** a previous run overwrote it and stopped before its row
          committed. It is proved by the tag under this key and by the row's plaintext
          digest, then reported as it stands, without a second write.

        Anything else is refused. The key comes from the caller's row, as it does for
        `get`, so an object sealed for another key cannot be adopted here.
        """
        try:
            assert_supported(
                algorithm=envelope.encryption_algorithm,
                envelope_version=envelope.envelope_version,
            )
            if envelope.envelope_version != LEGACY_ENVELOPE_VERSION:
                raise EnvelopeError("Only a v1 record is resealed.")
            body = self._fetch(key)
            if envelope_version_of(body) == WRITE_ENVELOPE_VERSION:
                return self._adopt(key, body, plaintext_sha256_hex=envelope.sha256_hex)
            plaintext = open_envelope(
                envelope=body,
                master_key=self._master_key,
                expected=ExpectedObject(
                    object_key=key,
                    ciphertext_sha256_hex=envelope.ciphertext_sha256_hex,
                    plaintext_sha256_hex=envelope.sha256_hex,
                    envelope_version=LEGACY_ENVELOPE_VERSION,
                ),
            )
        except EnvelopeError as error:
            raise StoragePolicyViolation(str(error)) from error
        return self._overwrite(key, plaintext, media_type=media_type)

    def _adopt(self, key: str, body: bytes, *, plaintext_sha256_hex: str) -> Resealed:
        """Prove an object an earlier run already rewrote. The row has no digest for it yet."""
        digest = hashlib.sha256(body).hexdigest()
        open_envelope(
            envelope=body,
            master_key=self._master_key,
            expected=ExpectedObject(
                object_key=key,
                ciphertext_sha256_hex=digest,
                plaintext_sha256_hex=plaintext_sha256_hex,
                envelope_version=WRITE_ENVELOPE_VERSION,
            ),
        )
        return Resealed(
            envelope_version=WRITE_ENVELOPE_VERSION,
            ciphertext_sha256_hex=digest,
            rewritten=False,
        )

    def _overwrite(self, key: str, plaintext: bytes, *, media_type: str) -> Resealed:
        """Replace an object in place. Unconditional, and never followed by a delete.

        `put` sends `IfNoneMatch` because it creates; this replaces an object a row
        already names, so the condition would refuse the one write it exists to make.
        `put` also deletes what it could not confirm, which is right for an object it
        just created and wrong here: the key holds the only copy, and S3 writes are
        atomic, so what is there is either the old envelope or the new one. The next
        run reseals the first and adopts the second.
        """
        sealed = seal(plaintext=plaintext, master_key=self._master_key, object_key=key)
        checksum = base64.b64encode(bytes.fromhex(sealed.ciphertext_sha256_hex)).decode("ascii")
        response = self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=sealed.envelope,
            ContentLength=len(sealed.envelope),
            ContentType=media_type,
            ChecksumSHA256=checksum,
        )
        if not _write_is_unversioned(response, checksum):
            raise StoragePolicyViolation("Object storage did not confirm the rewritten bytes.")
        return Resealed(
            envelope_version=sealed.envelope_version,
            ciphertext_sha256_hex=sealed.ciphertext_sha256_hex,
            rewritten=True,
        )

    def delete(self, key: str) -> None:
        self._delete_unversioned(key)

    def delete_prefix(self, prefix: str) -> None:
        base = {"Bucket": self._bucket, "Prefix": prefix}
        parameters: dict[str, object] = dict(base)
        while True:
            response = self._client.list_objects_v2(**parameters)
            for item in response.get("Contents") or []:
                key = item.get("Key")
                if not isinstance(key, str) or not key.startswith(prefix):
                    raise StoragePolicyViolation(
                        "Object storage returned an object outside the deletion scope."
                    )
                self._delete_unversioned(key)
            if response.get("IsTruncated") is not True:
                break
            token = response.get("NextContinuationToken")
            if not isinstance(token, str):
                raise StoragePolicyViolation("Object pagination is incomplete.")
            parameters = {**base, "ContinuationToken": token}
        confirmation = self._client.list_objects_v2(**base)
        if confirmation.get("Contents") or confirmation.get("IsTruncated") is True:
            raise StoragePolicyViolation("Objects remain after prefix cleanup.")

    def abort_multipart_uploads(self, prefix: str) -> None:
        base_parameters = {"Bucket": self._bucket, "Prefix": prefix}
        parameters: dict[str, object] = dict(base_parameters)
        while True:
            response = self._client.list_multipart_uploads(**parameters)
            for upload in response.get("Uploads") or []:
                key = upload["Key"]
                upload_id = upload["UploadId"]
                if not isinstance(key, str) or not key.startswith(prefix):
                    raise StoragePolicyViolation(
                        "Object storage returned a multipart upload outside the deletion scope."
                    )
                self._client.abort_multipart_upload(
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id,
                )
            if response.get("IsTruncated") is not True:
                break
            key_marker = response.get("NextKeyMarker")
            upload_marker = response.get("NextUploadIdMarker")
            if not isinstance(key_marker, str) or not isinstance(upload_marker, str):
                raise StoragePolicyViolation("Multipart pagination is incomplete.")
            parameters = {
                **base_parameters,
                "KeyMarker": key_marker,
                "UploadIdMarker": upload_marker,
            }
        confirmation = self._client.list_multipart_uploads(**base_parameters)
        if confirmation.get("Uploads") or confirmation.get("IsTruncated") is True:
            raise StoragePolicyViolation("Multipart uploads remain after cleanup.")

    def _read_and_verify_existing(self, request: ObjectWrite) -> StoredObject:
        """Prove an object that already exists holds the requested content.

        The ciphertext digest is computed from what was fetched rather than
        compared against a recorded one: there is no record yet, since this is the
        path where the write lost the race. Authentication still comes from GCM
        and from the plaintext digest, so tampered bytes cannot pass.
        """
        body = self._fetch(request.key)
        try:
            plaintext = open_envelope(
                envelope=body,
                master_key=self._master_key,
                expected=ExpectedObject(
                    object_key=request.key,
                    ciphertext_sha256_hex=hashlib.sha256(body).hexdigest(),
                    plaintext_sha256_hex=request.sha256_hex,
                    # No record exists on this path, so there is no version to hold
                    # the object to; the one it carries is reported below.
                    envelope_version=None,
                ),
            )
        except EnvelopeError as error:
            raise StoragePolicyViolation(
                "An existing object conflicts with the requested content."
            ) from error
        if len(plaintext) != len(request.content) or plaintext != request.content:
            raise StoragePolicyViolation(
                "An existing object conflicts with the requested content."
            )
        return StoredObject(
            key=request.key,
            size_bytes=len(plaintext),
            sha256_hex=request.sha256_hex,
            media_type=request.media_type,
            encryption_algorithm=ALGORITHM_AES_256_GCM,
            # What is there, not what this build would write: an existing `v1`
            # object is proved as `v1` and recorded as such.
            envelope_version=envelope_version_of(body),
            ciphertext_sha256_hex=hashlib.sha256(body).hexdigest(),
        )

    def _fetch(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body = response.get("Body")
        if body is None:
            raise StoragePolicyViolation("Object storage returned no object body.")
        if "VersionId" in response:
            raise StoragePolicyViolation(
                "Object storage reported versioned semantics for ephemeral content."
            )
        content = body.read()
        if not isinstance(content, bytes):
            raise StoragePolicyViolation("Object storage returned a non-binary body.")
        return content

    def _delete_unversioned(self, key: str) -> None:
        response = self._client.delete_object(Bucket=self._bucket, Key=key)
        if response.get("DeleteMarker") is True or "VersionId" in response:
            raise StoragePolicyViolation(
                "Object storage reported versioned deletion semantics for ephemeral content."
            )



def _is_precondition_failure(error: ClientError) -> bool:
    response = error.response
    status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
    code = response.get("Error", {}).get("Code")
    return status == 412 and code in {"PreconditionFailed", "412"}


def _write_is_unversioned(response: dict[str, Any], checksum: str) -> bool:
    """The whole of what a write response must show.

    Two properties, both portable: the store echoed the checksum of the bytes it
    accepted, and it is not versioning them. Every AWS-only assertion this
    replaced -- `ServerSideEncryption`, `SSEKMSKeyId`, `BucketKeyEnabled` -- is
    gone, because the bytes were already ciphertext when they left this process.
    """
    return response.get("ChecksumSHA256") == checksum and "VersionId" not in response


__all__ = [
    "ObjectWrite",
    "PutResult",
    "Resealed",
    "S3Client",
    "S3EncryptedObjectStore",
    "StoredEnvelope",
]
