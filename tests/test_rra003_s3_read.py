"""The read path's proofs, after `KHEPRI-DEC-008` moved encryption into the application.

**What this file used to assert.** That `get` sent `ExpectedBucketOwner` and
`ChecksumMode=ENABLED`, and refused a response unless it carried
`ServerSideEncryption == "aws:kms"`, the exact configured `SSEKMSKeyId`, and no
`VersionId`. Four of those five are AWS-only and no conforming S3-compatible store
can produce them, so they are retired rather than relaxed.

**What replaces them.** The read is proved by the recorded ciphertext digest and by
authenticated decryption, so the questions are: were these the bytes that were
written, do they authenticate under the master key, and is the plaintext the content
the row describes. A provider header answers none of those, and the store no longer
reads one.

`VersionId` survives as the one portable check: `RRA-002` requires deletion to
actually delete, and a versioned read means a prior copy is recoverable.
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
from khepri.rra.storage import S3EncryptedObjectStore, StoredEnvelope

_MASTER_KEY = MasterKey(material=b"k" * 32)
_WRONG_KEY = MasterKey(material=b"j" * 32)

BUCKET = "khepri-beta-content"
KEY = "owners/own_alpha/sessions/ses_alpha/inputs/upl_alpha"
CONTENT = b"a,b\n1,2\n"
SHA256_HEX = hashlib.sha256(CONTENT).hexdigest()

# A non-AWS endpoint on purpose: the read path must not care whose store it is.
ENDPOINT = "https://fra1.digitaloceanspaces.example"


def store_and_stubber(
    *, master_key: MasterKey = _MASTER_KEY
) -> tuple[S3EncryptedObjectStore, Stubber]:
    client = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        region_name="fra1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return (
        S3EncryptedObjectStore(client=client, bucket=BUCKET, master_key=master_key),
        Stubber(client),
    )


def get_parameters() -> dict[str, object]:
    """The whole of what a read sends. No owner assertion, no checksum mode."""
    return {"Bucket": BUCKET, "Key": KEY}


def sealed() -> tuple[bytes, str]:
    result = seal(plaintext=CONTENT, master_key=_MASTER_KEY)
    return result.envelope, result.ciphertext_sha256_hex


def body(content: bytes) -> StreamingBody:
    return StreamingBody(io.BytesIO(content), len(content))


def envelope(
    ciphertext_digest: str,
    *,
    plaintext_digest: str = SHA256_HEX,
    algorithm: str = ALGORITHM_AES_256_GCM,
    version: int = ENVELOPE_VERSION,
) -> StoredEnvelope:
    return StoredEnvelope(
        ciphertext_sha256_hex=ciphertext_digest,
        sha256_hex=plaintext_digest,
        encryption_algorithm=algorithm,
        envelope_version=version,
    )


def test_get_returns_content_when_both_digests_hold() -> None:
    envelope_bytes, digest = sealed()
    store, stubber = store_and_stubber()
    stubber.add_response(
        "get_object", {"Body": body(envelope_bytes)}, get_parameters()
    )

    with stubber:
        assert store.get(KEY, envelope=envelope(digest)) == CONTENT


def test_get_sends_no_aws_only_parameter() -> None:
    """`Stubber` matches the exact parameter set, so an added field fails here.

    That is what makes this a portability guard: `ExpectedBucketOwner` or
    `ChecksumMode` creeping back into the read would break this test rather than
    pass unnoticed.
    """
    envelope_bytes, digest = sealed()
    store, stubber = store_and_stubber()
    stubber.add_response(
        "get_object", {"Body": body(envelope_bytes)}, get_parameters()
    )

    with stubber:
        store.get(KEY, envelope=envelope(digest))

    stubber.assert_no_pending_responses()


def test_a_provider_encryption_header_is_neither_required_nor_read() -> None:
    """A store that reports nothing about encryption is still trusted, correctly.

    The bytes were ciphertext before they left the application, so the provider's
    opinion about encryption is not evidence either way.
    """
    envelope_bytes, digest = sealed()
    store, stubber = store_and_stubber()
    stubber.add_response(
        "get_object",
        {"Body": body(envelope_bytes), "ServerSideEncryption": "AES256"},
        get_parameters(),
    )

    with stubber:
        assert store.get(KEY, envelope=envelope(digest)) == CONTENT


@pytest.mark.parametrize(
    "reason",
    ["tampered_body", "wrong_ciphertext_digest", "wrong_plaintext_digest", "versioned"],
)
def test_get_refuses_content_it_cannot_prove(reason: str) -> None:
    envelope_bytes, digest = sealed()
    response: dict[str, object] = {"Body": body(envelope_bytes)}
    recorded = envelope(digest)

    if reason == "tampered_body":
        edited = bytearray(envelope_bytes)
        edited[-1] ^= 0x01
        response = {"Body": body(bytes(edited))}
        # Digest recomputed over the edited bytes, so the *cipher* must refuse.
        recorded = envelope(hashlib.sha256(bytes(edited)).hexdigest())
    elif reason == "wrong_ciphertext_digest":
        recorded = envelope("0" * 64)
    elif reason == "wrong_plaintext_digest":
        recorded = envelope(digest, plaintext_digest="f" * 64)
    else:
        response = {"Body": body(envelope_bytes), "VersionId": "unexpected-version"}

    store, stubber = store_and_stubber()
    stubber.add_response("get_object", response, get_parameters())

    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY, envelope=recorded)


def test_get_refuses_under_the_wrong_master_key() -> None:
    envelope_bytes, digest = sealed()
    store, stubber = store_and_stubber(master_key=_WRONG_KEY)
    stubber.add_response(
        "get_object", {"Body": body(envelope_bytes)}, get_parameters()
    )

    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY, envelope=envelope(digest))


@pytest.mark.parametrize(
    ("algorithm", "version"),
    [("aws:kms", ENVELOPE_VERSION), (ALGORITHM_AES_256_GCM, ENVELOPE_VERSION + 1)],
)
def test_get_refuses_metadata_this_build_cannot_honour(algorithm: str, version: int) -> None:
    """A row still claiming `aws:kms` is unreadable rather than quietly trusted."""
    _, digest = sealed()
    store, stubber = store_and_stubber()

    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY, envelope=envelope(digest, algorithm=algorithm, version=version))
