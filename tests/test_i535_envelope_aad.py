"""#535: envelope format `v2` binds its version and object key as AAD.

The ciphertext and plaintext digests already refuse a ciphertext moved between rows. What they
cannot refuse is a row and its object moved *together* to another scope's key. `v2` closes that by
authenticating the object key, and the format version, inside both GCM calls. `v1` objects stay
readable because stored data predates this slice.

The AAD layout is restated here rather than imported: it is a stored format, so a change to it in
the module must fail a test that describes it independently.
"""

from __future__ import annotations

import hashlib
import io
import os

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from khepri.rra import envelope as env
from khepri.rra.intake import StoragePolicyViolation
from khepri.rra.storage import ObjectWrite, S3EncryptedObjectStore, StoredEnvelope

# Removed with the implementation. The three `v1` adapter tests below carry no marker: they hold
# before and after, and guard that `v2` does not cost stored data its readability.
RED = pytest.mark.xfail(strict=True, reason="#535 RED: envelope v2 is not implemented")

MASTER = env.MasterKey(material=bytes([7]) * 32)
PLAINTEXT = b"store,revenue\nRiyadh,1200.50\n"
PLAINTEXT_SHA = hashlib.sha256(PLAINTEXT).hexdigest()
KEY_A = "owners/own_alpha/sessions/ses_alpha/inputs/upl_alpha"
KEY_B = "owners/own_bravo/sessions/ses_bravo/inputs/upl_alpha"
BUCKET = "khepri-content"

# Sealed by the pre-#535 code (`main` @ 4276814) under `MASTER`, with no AAD on either call.
GOLDEN_V1 = bytes.fromhex(
    "0111a9ad6f57a301692bef5a58516c4ecf655d81a72109f6628de6dea1b25c8021a0454c"
    "cdf0136dd7422aef4563c182c063ed6549480ea7938fc587a70a80a2ae5c4f3eac1c1991"
    "27c47cebe2e0b4ce2c1089260ce21de53f26c2a451b74734de0dd816c76a3366a341c53e"
    "39f3460c68f912a6f8bd"
)
GOLDEN_V1_SHA = "5547118e8c421962446d70bf9815b86821a3fbb55b8f71a3261f2c3efe686ac8"


def _aad(purpose: bytes, object_key: str) -> bytes:
    return b"khepri.envelope\x00" + purpose + b"\x00" + bytes([2]) + object_key.encode("utf-8")


def _forge(*, wrap_aad: bytes | None, content_aad: bytes | None) -> bytes:
    """A `v2` envelope built from the documented layout, one AAD at a time."""
    data_key = os.urandom(32)
    wrap_nonce, content_nonce = os.urandom(12), os.urandom(12)
    wrapped = AESGCM(MASTER.material).encrypt(wrap_nonce, data_key, wrap_aad)
    ciphertext = AESGCM(data_key).encrypt(content_nonce, PLAINTEXT, content_aad)
    return bytes([2]) + wrap_nonce + content_nonce + wrapped + ciphertext


def _open(body: bytes, object_key: str = KEY_A) -> bytes:
    return env.open_envelope(
        envelope=body,
        master_key=MASTER,
        object_key=object_key,
        expected_ciphertext_sha256_hex=hashlib.sha256(body).hexdigest(),
        expected_plaintext_sha256_hex=PLAINTEXT_SHA,
    )


def _seal(object_key: str = KEY_A) -> env.SealedObject:
    return env.seal(plaintext=PLAINTEXT, master_key=MASTER, object_key=object_key)


@RED
def test_a_stored_v1_envelope_still_opens() -> None:
    assert hashlib.sha256(GOLDEN_V1).hexdigest() == GOLDEN_V1_SHA
    assert _open(GOLDEN_V1) == PLAINTEXT


@RED
def test_new_writes_are_v2() -> None:
    sealed = _seal()
    assert sealed.envelope_version == env.WRITE_ENVELOPE_VERSION == 2
    assert sealed.envelope[0] == 2
    assert env.envelope_version_of(sealed.envelope) == 2


@RED
def test_both_versions_are_readable_and_no_other() -> None:
    assert sorted(env.READABLE_ENVELOPE_VERSIONS) == [1, 2]
    for version in (1, 2):
        env.assert_supported(algorithm=env.ALGORITHM_AES_256_GCM, envelope_version=version)
    with pytest.raises(env.EnvelopeError):
        env.assert_supported(algorithm=env.ALGORITHM_AES_256_GCM, envelope_version=3)


@RED
def test_v2_opens_only_under_its_own_object_key() -> None:
    body = _seal(KEY_A).envelope
    assert _open(body, KEY_A) == PLAINTEXT
    with pytest.raises(env.EnvelopeError):
        _open(body, KEY_B)


@RED
def test_rewriting_a_v2_header_to_v1_refuses() -> None:
    body = bytes([1]) + _seal().envelope[1:]
    with pytest.raises(env.EnvelopeError):
        _open(body)


@RED
def test_the_documented_layout_opens() -> None:
    body = _forge(wrap_aad=_aad(b"wrap", KEY_A), content_aad=_aad(b"content", KEY_A))
    assert _open(body) == PLAINTEXT


@RED
def test_the_wrap_call_must_carry_its_aad() -> None:
    body = _forge(wrap_aad=None, content_aad=_aad(b"content", KEY_A))
    with pytest.raises(env.EnvelopeError):
        _open(body)


@RED
def test_the_content_call_must_carry_its_aad() -> None:
    body = _forge(wrap_aad=_aad(b"wrap", KEY_A), content_aad=None)
    with pytest.raises(env.EnvelopeError):
        _open(body)


@RED
def test_the_two_calls_are_domain_separated() -> None:
    body = _forge(wrap_aad=_aad(b"content", KEY_A), content_aad=_aad(b"wrap", KEY_A))
    with pytest.raises(env.EnvelopeError):
        _open(body)


@RED
def test_an_empty_object_key_cannot_be_sealed() -> None:
    with pytest.raises(env.EnvelopeError):
        _seal("")


# --- through the storage adapter ------------------------------------------------


def _store() -> tuple[S3EncryptedObjectStore, Stubber]:
    client = boto3.client(
        "s3",
        endpoint_url="https://objects.example",
        region_name="fra1",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    return S3EncryptedObjectStore(client=client, bucket=BUCKET, master_key=MASTER), Stubber(client)


def _row(body: bytes, version: int) -> StoredEnvelope:
    return StoredEnvelope(
        ciphertext_sha256_hex=hashlib.sha256(body).hexdigest(),
        sha256_hex=PLAINTEXT_SHA,
        encryption_algorithm=env.ALGORITHM_AES_256_GCM,
        envelope_version=version,
    )


def _serving(stubber: Stubber, body: bytes, key: str) -> None:
    stubber.add_response(
        "get_object",
        {"Body": StreamingBody(io.BytesIO(body), len(body))},
        {"Bucket": BUCKET, "Key": key},
    )


@RED
def test_an_object_moved_with_its_row_to_another_scope_refuses() -> None:
    """Both digests hold, so only the bound key can refuse this splice."""
    body = _seal(KEY_A).envelope
    store, stubber = _store()
    _serving(stubber, body, KEY_B)
    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY_B, envelope=_row(body, 2))


def test_a_row_must_name_the_version_its_object_carries() -> None:
    store, stubber = _store()
    _serving(stubber, GOLDEN_V1, KEY_A)
    with stubber, pytest.raises(StoragePolicyViolation):
        store.get(KEY_A, envelope=_row(GOLDEN_V1, 2))


def test_a_stored_v1_object_reads_through_the_adapter() -> None:
    store, stubber = _store()
    _serving(stubber, GOLDEN_V1, KEY_A)
    with stubber:
        assert store.get(KEY_A, envelope=_row(GOLDEN_V1, 1)) == PLAINTEXT


def test_put_or_verify_proves_an_existing_v1_object_as_v1() -> None:
    store, stubber = _store()
    stubber.add_client_error(
        "put_object", service_error_code="PreconditionFailed", http_status_code=412
    )
    _serving(stubber, GOLDEN_V1, KEY_A)
    request = ObjectWrite(
        key=KEY_A, content=PLAINTEXT, media_type="text/csv", sha256_hex=PLAINTEXT_SHA
    )
    with stubber:
        result = store.put_or_verify(request)
    assert result.created is False
    assert result.stored.envelope_version == 1
    assert result.stored.ciphertext_sha256_hex == GOLDEN_V1_SHA
