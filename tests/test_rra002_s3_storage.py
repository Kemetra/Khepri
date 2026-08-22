"""The object store against any S3-compatible API, per `KHEPRI-DEC-008`.

**What these tests stopped asserting, and why.** An earlier version of this file
proved that `put` sent `ServerSideEncryption="aws:kms"`, `SSEKMSKeyId`,
`SSEKMSEncryptionContext`, `BucketKeyEnabled`, and `ExpectedBucketOwner`, and that
the constructor refused a KMS ARN outside `me-central-1` or a bucket owner that was
not twelve digits. Every one of those is now a portability violation rather than a
control: no S3-compatible store outside AWS can satisfy them, and encryption is the
application's own work. They are replaced by assertions that the request carries
*none* of them.

**A fake would not prove this.** `Stubber` matches the exact parameter set of every
call, so a request that grew an AWS-only field would fail here rather than pass
quietly -- which is the property that makes these tests a portability guard rather
than a description of the code.
"""

from __future__ import annotations

import hashlib
import io

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from khepri.rra.envelope import ALGORITHM_AES_256_GCM, ENVELOPE_VERSION, MasterKey, seal
from khepri.rra.intake import StoragePolicyViolation
from khepri.rra.storage import ObjectWrite, S3EncryptedObjectStore, StoredEnvelope

_MASTER_KEY = MasterKey(material=b"k" * 32)
_OTHER_KEY = MasterKey(material=b"j" * 32)

BUCKET = "khepri-beta-content"
KEY = "owners/own_alpha/sessions/ses_alpha/inputs/upl_alpha"
CONTENT = b"a,b\n1,2\n"
SHA256_HEX = hashlib.sha256(CONTENT).hexdigest()

# Deliberately not an AWS endpoint or region. A conforming store is a conforming
# store; if either of these had to be an AWS value, the boundary would not be
# portable and this module would say so by failing.
ENDPOINT = "https://fra1.digitaloceanspaces.example"
REGION = "fra1"

# Every AWS-only parameter the retired implementation sent.
# `test_put_writes_ciphertext_and_records_both_digests` asserts none reaches the wire.
_AWS_ONLY_PARAMETERS = (
    "ServerSideEncryption",
    "SSEKMSKeyId",
    "SSEKMSEncryptionContext",
    "BucketKeyEnabled",
    "ExpectedBucketOwner",
)


def client_for(*, endpoint: str = ENDPOINT, region: str = REGION):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )


def store_and_stubber(
    *, master_key: MasterKey = _MASTER_KEY
) -> tuple[S3EncryptedObjectStore, Stubber]:
    client = client_for()
    return (
        S3EncryptedObjectStore(client=client, bucket=BUCKET, master_key=master_key),
        Stubber(client),
    )


def sealed_body() -> tuple[bytes, str]:
    """One sealed copy of `CONTENT` and its ciphertext digest."""
    result = seal(plaintext=CONTENT, master_key=_MASTER_KEY)
    return result.envelope, result.ciphertext_sha256_hex


def envelope_for(ciphertext_digest: str) -> StoredEnvelope:
    return StoredEnvelope(
        ciphertext_sha256_hex=ciphertext_digest,
        sha256_hex=SHA256_HEX,
        encryption_algorithm=ALGORITHM_AES_256_GCM,
        envelope_version=ENVELOPE_VERSION,
    )


def streaming(body: bytes) -> StreamingBody:
    return StreamingBody(io.BytesIO(body), len(body))


# --- construction -----------------------------------------------------------


def test_a_bucket_is_the_only_required_coordinate() -> None:
    """No KMS ARN, no account identifier, no region check."""
    store = S3EncryptedObjectStore(
        client=client_for(), bucket=BUCKET, master_key=_MASTER_KEY
    )

    assert store is not None


def test_an_absent_bucket_is_refused() -> None:
    with pytest.raises(ValueError):
        S3EncryptedObjectStore(client=client_for(), bucket="", master_key=_MASTER_KEY)


@pytest.mark.parametrize(
    ("endpoint", "region"),
    [
        ("https://fra1.digitaloceanspaces.example", "fra1"),
        ("https://s3.eu-central-1.amazonaws.example", "eu-central-1"),
        ("https://nbg1.your-objectstorage.example", "nbg1"),
        ("https://minio.internal.example:9000", "us-east-1"),
        ("https://s3.me-central-1.amazonaws.example", "me-central-1"),
    ],
)
def test_any_conforming_endpoint_is_accepted(endpoint: str, region: str) -> None:
    """`me-central-1` is present as one row among five, not as a requirement."""
    store = S3EncryptedObjectStore(
        client=client_for(endpoint=endpoint, region=region),
        bucket=BUCKET,
        master_key=_MASTER_KEY,
    )

    assert store is not None


# --- writing ----------------------------------------------------------------


def test_put_writes_ciphertext_and_records_both_digests() -> None:
    """The whole write path, with a recording client rather than a stub.

    `Stubber` cannot echo back a checksum it has not yet seen, and the checksum is
    computed from randomised ciphertext, so the round trip is exercised against a
    recorder instead. That also makes the sent parameters inspectable, which is
    what the portability assertion below needs.
    """
    sent: dict[str, object] = {}

    class Recorder:
        def put_object(self, **kwargs: object) -> dict[str, object]:
            sent.update(kwargs)
            return {"ChecksumSHA256": kwargs["ChecksumSHA256"]}

    store = S3EncryptedObjectStore(
        client=Recorder(),  # type: ignore[arg-type]
        bucket=BUCKET,
        master_key=_MASTER_KEY,
    )
    stored = store.put(key=KEY, content=CONTENT, media_type="text/csv", sha256_hex=SHA256_HEX)

    # The plaintext digest stays the content address; the ciphertext digest is new.
    assert stored.sha256_hex == SHA256_HEX
    assert stored.size_bytes == len(CONTENT)
    assert stored.encryption_algorithm == ALGORITHM_AES_256_GCM
    assert stored.envelope_version == ENVELOPE_VERSION
    assert len(stored.ciphertext_sha256_hex) == 64
    assert stored.ciphertext_sha256_hex != SHA256_HEX

    # Ciphertext crossed the boundary, not the content.
    assert sent["Body"] != CONTENT
    assert CONTENT not in sent["Body"]  # type: ignore[operator]
    assert sent["IfNoneMatch"] == "*"

    # The portability assertion: not one retired AWS field was sent.
    for parameter in _AWS_ONLY_PARAMETERS:
        assert parameter not in sent


def test_put_or_verify_proves_an_identical_preexisting_object() -> None:
    """Content addressing survives randomised encryption.

    The write loses the `IfNoneMatch` race, so the existing object is read and
    decrypted to prove it holds the requested plaintext. Comparing ciphertext
    would fail here by construction: the same content sealed twice differs.
    """
    store, stubber = store_and_stubber()
    stubber.add_client_error(
        "put_object", service_error_code="PreconditionFailed", http_status_code=412
    )
    stubber.add_response(
        "get_object",
        {"Body": streaming(sealed_body()[0])},
        {"Bucket": BUCKET, "Key": KEY},
    )
    with stubber:
        result = store.put_or_verify(
            ObjectWrite(key=KEY, content=CONTENT, media_type="text/csv", sha256_hex=SHA256_HEX)
        )

    assert result.created is False
    assert result.stored.sha256_hex == SHA256_HEX
    assert result.stored.encryption_algorithm == ALGORITHM_AES_256_GCM
    assert result.stored.envelope_version == ENVELOPE_VERSION


def test_put_refuses_content_that_does_not_match_its_declared_digest() -> None:
    store, stubber = store_and_stubber()
    with stubber, pytest.raises(StoragePolicyViolation):
        store.put(key=KEY, content=b"different", media_type="text/csv", sha256_hex=SHA256_HEX)


def test_stored_ciphertext_is_never_the_plaintext() -> None:
    body, _ = sealed_body()

    assert CONTENT not in body


# --- reading ----------------------------------------------------------------


def test_get_verifies_ciphertext_then_decrypts() -> None:
    body, digest = sealed_body()
    store, stubber = store_and_stubber()
    stubber.add_response(
        "get_object", {"Body": streaming(body)}, {"Bucket": BUCKET, "Key": KEY}
    )
    with stubber:
        assert store.get(KEY, envelope=envelope_for(digest)) == CONTENT


def test_get_refuses_a_ciphertext_digest_mismatch() -> None:
    """The read-back proof `KHEPRI-DEC-008` requires, in its failing direction."""
    body, _ = sealed_body()
    store, stubber = store_and_stubber()
    stubber.add_response(
        "get_object", {"Body": streaming(body)}, {"Bucket": BUCKET, "Key": KEY}
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY, envelope=envelope_for("0" * 64))


def test_get_refuses_tampered_ciphertext() -> None:
    body, _ = sealed_body()
    edited = bytearray(body)
    edited[-1] ^= 0x01
    tampered = bytes(edited)
    store, stubber = store_and_stubber()
    stubber.add_response(
        "get_object", {"Body": streaming(tampered)}, {"Bucket": BUCKET, "Key": KEY}
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY, envelope=envelope_for(hashlib.sha256(tampered).hexdigest()))


def test_get_refuses_under_the_wrong_master_key() -> None:
    body, digest = sealed_body()
    client = client_for()
    store = S3EncryptedObjectStore(client=client, bucket=BUCKET, master_key=_OTHER_KEY)
    stubber = Stubber(client)
    stubber.add_response(
        "get_object", {"Body": streaming(body)}, {"Bucket": BUCKET, "Key": KEY}
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY, envelope=envelope_for(digest))


def test_get_refuses_a_retired_algorithm() -> None:
    """A row still claiming `aws:kms` is unreadable rather than trusted."""
    store, stubber = store_and_stubber()
    retired = StoredEnvelope(
        ciphertext_sha256_hex="c" * 64,
        sha256_hex=SHA256_HEX,
        encryption_algorithm="aws:kms",
        envelope_version=ENVELOPE_VERSION,
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY, envelope=retired)


def test_get_fails_closed_on_versioned_semantics() -> None:
    body, digest = sealed_body()
    store, stubber = store_and_stubber()
    stubber.add_response(
        "get_object",
        {"Body": streaming(body), "VersionId": "v1"},
        {"Bucket": BUCKET, "Key": KEY},
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY, envelope=envelope_for(digest))


def test_put_or_verify_refuses_an_existing_object_holding_other_content() -> None:
    other = seal(plaintext=b"not the requested content", master_key=_MASTER_KEY)
    store, stubber = store_and_stubber()
    stubber.add_client_error(
        "put_object", service_error_code="PreconditionFailed", http_status_code=412
    )
    stubber.add_response(
        "get_object", {"Body": streaming(other.envelope)}, {"Bucket": BUCKET, "Key": KEY}
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.put_or_verify(
            ObjectWrite(key=KEY, content=CONTENT, media_type="text/csv", sha256_hex=SHA256_HEX)
        )


# --- deletion and cleanup ---------------------------------------------------


def test_delete_sends_no_bucket_owner_assertion() -> None:
    store, stubber = store_and_stubber()
    stubber.add_response("delete_object", {}, {"Bucket": BUCKET, "Key": KEY})
    with stubber:
        store.delete(KEY)

    stubber.assert_no_pending_responses()


def test_delete_fails_closed_if_the_store_reports_versioned_semantics() -> None:
    store, stubber = store_and_stubber()
    stubber.add_response(
        "delete_object", {"DeleteMarker": True}, {"Bucket": BUCKET, "Key": KEY}
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.delete(KEY)


def test_prefix_cleanup_deletes_and_confirms_an_empty_scope() -> None:
    prefix = "owners/own_alpha/sessions/ses_alpha/"
    store, stubber = store_and_stubber()
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": f"{prefix}inputs/upl_alpha"}], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": prefix},
    )
    stubber.add_response(
        "delete_object", {}, {"Bucket": BUCKET, "Key": f"{prefix}inputs/upl_alpha"}
    )
    stubber.add_response(
        "list_objects_v2", {"IsTruncated": False}, {"Bucket": BUCKET, "Prefix": prefix}
    )
    with stubber:
        store.delete_prefix(prefix)

    stubber.assert_no_pending_responses()


def test_prefix_cleanup_refuses_an_object_outside_its_scope() -> None:
    prefix = "owners/own_alpha/sessions/ses_alpha/"
    store, stubber = store_and_stubber()
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": "owners/own_beta/leak"}], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": prefix},
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.delete_prefix(prefix)


def test_prefix_cleanup_fails_closed_when_objects_remain() -> None:
    prefix = "owners/own_alpha/sessions/ses_alpha/"
    store, stubber = store_and_stubber()
    stubber.add_response(
        "list_objects_v2", {"IsTruncated": False}, {"Bucket": BUCKET, "Prefix": prefix}
    )
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": f"{prefix}stubborn"}], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": prefix},
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.delete_prefix(prefix)


def test_multipart_cleanup_aborts_every_upload_under_the_prefix() -> None:
    prefix = "owners/own_alpha/sessions/ses_alpha/"
    store, stubber = store_and_stubber()
    stubber.add_response(
        "list_multipart_uploads",
        {"Uploads": [{"Key": f"{prefix}partial", "UploadId": "u1"}], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": prefix},
    )
    stubber.add_response(
        "abort_multipart_upload",
        {},
        {"Bucket": BUCKET, "Key": f"{prefix}partial", "UploadId": "u1"},
    )
    stubber.add_response(
        "list_multipart_uploads",
        {"IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": prefix},
    )
    with stubber:
        store.abort_multipart_uploads(prefix)

    stubber.assert_no_pending_responses()


def test_multipart_cleanup_refuses_an_upload_outside_its_scope() -> None:
    prefix = "owners/own_alpha/sessions/ses_alpha/"
    store, stubber = store_and_stubber()
    stubber.add_response(
        "list_multipart_uploads",
        {"Uploads": [{"Key": "owners/own_beta/leak", "UploadId": "u1"}], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": prefix},
    )
    with stubber, pytest.raises(StoragePolicyViolation):
        store.abort_multipart_uploads(prefix)
