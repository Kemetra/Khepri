"""The security properties `KHEPRI-DEC-008` requires of the object envelope.

Every test here asserts an *outcome* of the real primitive. None mocks `AESGCM`,
because a mocked cipher would prove the code calls something rather than that a
forgery is refused.
"""

from __future__ import annotations

import hashlib

import pytest

from khepri.rra.envelope import (
    ALGORITHM_AES_256_GCM,
    DATA_KEY_BYTES,
    ENVELOPE_VERSION,
    MASTER_KEY_BYTES,
    NONCE_BYTES,
    EnvelopeError,
    MasterKey,
    assert_supported,
    open_envelope,
    seal,
)

PLAINTEXT = b"store,revenue\nRiyadh,1200.50\nJeddah,980.00\n"
_HEADER_BYTES = 1 + NONCE_BYTES + NONCE_BYTES + DATA_KEY_BYTES + 16


def master_key(fill: int = 7) -> MasterKey:
    return MasterKey(material=bytes([fill]) * MASTER_KEY_BYTES)


def sealed(key: MasterKey | None = None):
    return seal(plaintext=PLAINTEXT, master_key=key or master_key())


def opened(envelope: bytes, *, key: MasterKey, ciphertext_digest: str) -> bytes:
    return open_envelope(
        envelope=envelope,
        master_key=key,
        expected_ciphertext_sha256_hex=ciphertext_digest,
        expected_plaintext_sha256_hex=hashlib.sha256(PLAINTEXT).hexdigest(),
    )


def tampered(envelope: bytes, index: int) -> bytes:
    """Flip one bit, keeping the length identical."""
    edited = bytearray(envelope)
    edited[index] ^= 0x01
    return bytes(edited)


# --- key material -----------------------------------------------------------


@pytest.mark.parametrize("length", [0, 16, 31, 33, 64])
def test_master_key_must_be_256_bits(length: int) -> None:
    with pytest.raises(EnvelopeError):
        MasterKey(material=b"k" * length)


def test_master_key_is_absent_from_repr() -> None:
    """A key that appears in a repr appears in every log line quoting the object."""
    secret = bytes(range(MASTER_KEY_BYTES))
    text = repr(MasterKey(material=secret))
    assert "material" not in text
    assert secret.hex() not in text
    assert str(secret) not in text


# --- encryption -------------------------------------------------------------


def test_ciphertext_is_not_plaintext() -> None:
    result = sealed()
    assert PLAINTEXT not in result.envelope
    assert result.envelope != PLAINTEXT


def test_round_trip_returns_the_original_bytes() -> None:
    key = master_key()
    result = seal(plaintext=PLAINTEXT, master_key=key)
    assert opened(result.envelope, key=key, ciphertext_digest=result.ciphertext_sha256_hex) == (
        PLAINTEXT
    )


def test_empty_plaintext_round_trips() -> None:
    key = master_key()
    result = seal(plaintext=b"", master_key=key)
    assert (
        open_envelope(
            envelope=result.envelope,
            master_key=key,
            expected_ciphertext_sha256_hex=result.ciphertext_sha256_hex,
            expected_plaintext_sha256_hex=hashlib.sha256(b"").hexdigest(),
        )
        == b""
    )


def test_sealing_twice_reuses_no_nonce_and_no_ciphertext() -> None:
    """Randomised encryption is why the ciphertext digest cannot be an identity."""
    key = master_key()
    first = seal(plaintext=PLAINTEXT, master_key=key)
    second = seal(plaintext=PLAINTEXT, master_key=key)

    assert first.envelope != second.envelope
    assert first.ciphertext_sha256_hex != second.ciphertext_sha256_hex
    # Both nonces must differ: a shared wrap nonce would repeat under the
    # long-lived master key, which is the catastrophic case for GCM.
    assert first.envelope[1 : 1 + NONCE_BYTES] != second.envelope[1 : 1 + NONCE_BYTES]
    assert (
        first.envelope[1 + NONCE_BYTES : 1 + 2 * NONCE_BYTES]
        != second.envelope[1 + NONCE_BYTES : 1 + 2 * NONCE_BYTES]
    )


def test_the_two_nonces_differ_within_one_envelope() -> None:
    result = sealed()
    assert result.envelope[1 : 1 + NONCE_BYTES] != (
        result.envelope[1 + NONCE_BYTES : 1 + 2 * NONCE_BYTES]
    )


def test_seal_records_the_governed_algorithm_and_version() -> None:
    result = sealed()
    assert result.algorithm == ALGORITHM_AES_256_GCM
    assert result.envelope_version == ENVELOPE_VERSION
    assert result.ciphertext_sha256_hex == hashlib.sha256(result.envelope).hexdigest()


# --- refusals ---------------------------------------------------------------


def test_wrong_master_key_refuses() -> None:
    result = sealed(master_key(7))
    with pytest.raises(EnvelopeError):
        opened(result.envelope, key=master_key(8), ciphertext_digest=result.ciphertext_sha256_hex)


@pytest.mark.parametrize(
    ("name", "index"),
    [
        ("wrap nonce", 1),
        ("content nonce", 1 + NONCE_BYTES),
        ("wrapped key", 1 + 2 * NONCE_BYTES),
        ("ciphertext", _HEADER_BYTES),
    ],
)
def test_editing_any_envelope_field_refuses(name: str, index: int) -> None:
    """One flipped bit anywhere authenticated must fail closed."""
    result = sealed()
    edited = tampered(result.envelope, index)
    # The digest is recomputed over the edited bytes, so this proves the *cipher*
    # refuses rather than merely that the digest check caught it.
    with pytest.raises(EnvelopeError):
        opened(
            edited,
            key=master_key(),
            ciphertext_digest=hashlib.sha256(edited).hexdigest(),
        )


def test_truncated_envelope_refuses() -> None:
    result = sealed()
    for cut in (0, 1, _HEADER_BYTES - 1, _HEADER_BYTES, len(result.envelope) - 1):
        body = result.envelope[:cut]
        with pytest.raises(EnvelopeError):
            opened(
                body,
                key=master_key(),
                ciphertext_digest=hashlib.sha256(body).hexdigest(),
            )


def test_unknown_envelope_version_refuses() -> None:
    result = sealed()
    body = bytes([ENVELOPE_VERSION + 1]) + result.envelope[1:]
    with pytest.raises(EnvelopeError):
        opened(body, key=master_key(), ciphertext_digest=hashlib.sha256(body).hexdigest())


def test_ciphertext_digest_mismatch_refuses_before_decrypting() -> None:
    result = sealed()
    with pytest.raises(EnvelopeError):
        opened(result.envelope, key=master_key(), ciphertext_digest="0" * 64)


def test_plaintext_digest_mismatch_refuses() -> None:
    """A database and object store that no longer describe the same object."""
    key = master_key()
    result = seal(plaintext=PLAINTEXT, master_key=key)
    with pytest.raises(EnvelopeError):
        open_envelope(
            envelope=result.envelope,
            master_key=key,
            expected_ciphertext_sha256_hex=result.ciphertext_sha256_hex,
            expected_plaintext_sha256_hex=hashlib.sha256(b"different").hexdigest(),
        )


def test_errors_carry_no_key_material() -> None:
    result = sealed(master_key(7))
    with pytest.raises(EnvelopeError) as caught:
        opened(result.envelope, key=master_key(8), ciphertext_digest=result.ciphertext_sha256_hex)
    message = str(caught.value)
    assert (bytes([8]) * MASTER_KEY_BYTES).hex() not in message
    assert result.envelope.hex() not in message


# --- persisted metadata -----------------------------------------------------


def test_assert_supported_accepts_the_governed_pair() -> None:
    assert_supported(algorithm=ALGORITHM_AES_256_GCM, envelope_version=ENVELOPE_VERSION)


@pytest.mark.parametrize(
    ("algorithm", "version"),
    [
        ("aws:kms", ENVELOPE_VERSION),
        ("AES-128-GCM", ENVELOPE_VERSION),
        ("", ENVELOPE_VERSION),
        (ALGORITHM_AES_256_GCM, ENVELOPE_VERSION + 1),
        (ALGORITHM_AES_256_GCM, 0),
    ],
)
def test_assert_supported_refuses_anything_else(algorithm: str, version: int) -> None:
    """`aws:kms` is named explicitly: the retired value must not be readable."""
    with pytest.raises(EnvelopeError):
        assert_supported(algorithm=algorithm, envelope_version=version)
