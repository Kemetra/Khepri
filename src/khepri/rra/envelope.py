"""Application-side envelope encryption for stored objects.

`KHEPRI-DEC-028` replaces the five provider-header proofs with encryption the
application performs itself: "a per-object AES-256-GCM data key, wrapped by a
master key drawn from the secret store, with the ciphertext digest verified on
read-back". This module is the whole of that construction. Nothing else in the
codebase touches a cipher, a nonce, or a key.

**Why one module.** Scattering nonce handling across the storage adapter and its
callers would make "is the nonce unique?" a question about several files. Here it
is a question about `seal`, which draws every nonce from `os.urandom` and never
accepts one from a caller.

**Why AES-256-GCM wraps the data key too.** `KHEPRI-DEC-028` names exactly one
primitive, AES-256-GCM, and says the data key is "wrapped by a master key". It
does not name a wrapping primitive. Using the primitive it *does* name introduces
no second algorithm, no second library, and no security property the decision has
not already accepted; choosing AES-KW instead would be selecting a primitive no
authority settles, which is the choice this slice is not entitled to make. The
consequence is recorded rather than assumed: wrapping is authenticated, so a
wrong master key or an edited wrapped key fails the GCM tag check rather than
producing a plausible-looking data key.

**Two nonces, never one.** GCM is catastrophically broken by nonce reuse under the
same key. The wrap nonce is used once per object under the long-lived master key,
and the content nonce once per object under a data key that exists for one object,
so a single nonce field shared between them would reuse a nonce under the master
key on the second object ever written. They are separate fields for that reason.

**What the envelope is not.** It carries no customer content, no filename, no
label, and no plaintext digest. A reader who obtains the envelope without the
master key learns the version, the algorithm, and the ciphertext length.

**Digest semantics.** `seal` returns the ciphertext digest, and the caller stores
it to satisfy the read-back proof `KHEPRI-DEC-028` requires. The plaintext digest
stays the content address and is verified by `open_envelope` against the decrypted
bytes. Both are checked; they answer different questions. Encryption is
randomised, so the same plaintext sealed twice yields different ciphertext and a
different ciphertext digest -- which is why the ciphertext digest can never be the
content address.

**Format `v2` binds the object key (#535).** The digests refuse a ciphertext moved
between rows, but not a row and its object moved *together* to another scope's key:
both digests travel with them. `v2` passes additional authenticated data to both
GCM calls -- the format version and the object key, domain-separated per call as
``b"khepri.envelope\\x00" + purpose + b"\\x00" + version + key`` with purpose
``wrap`` or ``content``. Every key is built under its scope
(``owners/{owner_id}/sessions/{session_id}/...``) and names one object, so the key
is the object/scope identity. The caller supplies it from the row it read; it is
never read from the envelope, which would let the bytes vouch for themselves.

A `v2` header rewritten to `1` fails because `v1` opens with *no* AAD while the
object was sealed with some -- not because the version is inside the AAD. The
version is bound for the versions after `v2`: an envelope sealed as `v2` must not
open under a later format's reading of the same bytes, and that holds only because
each version's AAD differs. `test_i535_envelope_aad` pins it with a forge whose AAD
names another version.

**Scope is checked by the reader, not here.** The envelope proves the bytes belong
to the key they were sealed for. It cannot prove the key belongs to the caller: a
row whose scope columns were edited still names the first scope's key, and the tag
verifies. Every reader holds the key to the caller's own namespace with
`khepri.rra.sessions.assert_object_in_scope` before it reads.

**Version compatibility.** New writes are `WRITE_ENVELOPE_VERSION` (`2`). A reader
accepts exactly `READABLE_ENVELOPE_VERSIONS`: `v1`, which binds no AAD and stays
readable because stored objects predate `v2`, and `v2`. Rewriting stored `v1`
objects as `v2` is not done here: `khepri.rra.envelope_migration` does it for
report artifacts, and `v1` leaves the readable set only once no `v1` row remains.
Any later format version must bind at least what `v2` binds.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Bumped only when a field is added, removed, or reinterpreted. A reader that does
# not recognise the version refuses rather than guessing which fields it has.
# There is deliberately no single `ENVELOPE_VERSION`: a pin has to say whether it
# means "what this build writes" or "what this build can read".
WRITE_ENVELOPE_VERSION = 2
READABLE_ENVELOPE_VERSIONS = frozenset({1, 2})
# The format sealed with no AAD. Public because the migration that retires it has to
# name it, and a second literal `1` elsewhere would be a pin nothing ties to this one.
LEGACY_ENVELOPE_VERSION = 1

_AAD_DOMAIN = b"khepri.envelope\x00"
_WRAP = b"wrap"
_CONTENT = b"content"

# The one algorithm `KHEPRI-DEC-028` names. Recorded in the envelope and in the
# database so a stored object says how it was encrypted rather than relying on the
# reader's assumption.
ALGORITHM_AES_256_GCM = "AES-256-GCM"

MASTER_KEY_BYTES = 32
DATA_KEY_BYTES = 32
NONCE_BYTES = 12
_GCM_TAG_BYTES = 16

# A sealed data key is the 32-byte key plus GCM's authentication tag.
_WRAPPED_KEY_BYTES = DATA_KEY_BYTES + _GCM_TAG_BYTES

# The header is fixed width so a truncated envelope is detected by length rather
# than by a parser that happens to read past the end of the buffer.
_VERSION_BYTES = 1
_HEADER_BYTES = _VERSION_BYTES + NONCE_BYTES + NONCE_BYTES + _WRAPPED_KEY_BYTES


class EnvelopeError(ValueError):
    """The envelope could not be produced, parsed, or trusted.

    Carries no key material, no nonce, and no ciphertext, so the message is safe
    to log. Every failure -- wrong master key, edited ciphertext, truncated
    buffer, unknown version -- surfaces as this one type, because distinguishing
    them for a caller would tell an attacker which part of a forgery was wrong.
    """


@dataclass(frozen=True, slots=True)
class MasterKey:
    """A 256-bit envelope master key drawn from the secret store.

    `field(repr=False)` is the point of the type. A bare `bytes` passed through
    the wiring would appear in any dataclass repr, exception, or log line that
    happened to include the object holding it.
    """

    material: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.material, bytes) or len(self.material) != MASTER_KEY_BYTES:
            raise EnvelopeError("Envelope master key must be 32 bytes.")


@dataclass(frozen=True, slots=True)
class SealedObject:
    """Ciphertext that crosses the storage boundary, and the proof of what it is."""

    envelope: bytes
    ciphertext_sha256_hex: str
    algorithm: str
    envelope_version: int


def seal(*, plaintext: bytes, master_key: MasterKey, object_key: str) -> SealedObject:
    """Encrypt one object under a fresh data key and wrap that key.

    Every nonce comes from `os.urandom` here. No caller supplies one, so no
    caller can reuse one. `object_key` is required for the same reason: an
    optional binding is one a caller can leave out.
    """
    version = WRITE_ENVELOPE_VERSION
    data_key = os.urandom(DATA_KEY_BYTES)
    content_nonce = os.urandom(NONCE_BYTES)
    wrap_nonce = os.urandom(NONCE_BYTES)

    ciphertext = AESGCM(data_key).encrypt(
        content_nonce, plaintext, _aad(_CONTENT, version, object_key)
    )
    wrapped_key = AESGCM(master_key.material).encrypt(
        wrap_nonce, data_key, _aad(_WRAP, version, object_key)
    )

    envelope = b"".join(
        (
            version.to_bytes(_VERSION_BYTES, "big"),
            wrap_nonce,
            content_nonce,
            wrapped_key,
            ciphertext,
        )
    )
    return SealedObject(
        envelope=envelope,
        ciphertext_sha256_hex=hashlib.sha256(envelope).hexdigest(),
        algorithm=ALGORITHM_AES_256_GCM,
        envelope_version=version,
    )


def envelope_version_of(envelope: bytes) -> int:
    """The format version stored bytes carry, refusing a short or unknown one."""
    return _parse(envelope).version


@dataclass(frozen=True, slots=True)
class ExpectedObject:
    """What the reader's own record says the stored object is.

    Every field is required. `envelope_version` is `None` only where no record
    exists yet -- `put_or_verify`'s race loser, proving an object it did not write
    -- and a caller has to write that `None` out, so it cannot be omitted by
    accident.
    """

    object_key: str
    ciphertext_sha256_hex: str
    plaintext_sha256_hex: str
    envelope_version: int | None


def open_envelope(*, envelope: bytes, master_key: MasterKey, expected: ExpectedObject) -> bytes:
    """Verify the ciphertext, decrypt it, and verify the plaintext.

    Both digests and the object key are required rather than optional checks. An
    optional verification is one a caller can omit, and the read-back proof
    `KHEPRI-DEC-028` requires is worth nothing if the storage adapter can skip it.

    The ciphertext digest is checked *before* the cipher runs, so bytes that were
    not the bytes written are rejected without being decrypted.
    """
    _assert_ciphertext_unchanged(envelope, expected.ciphertext_sha256_hex)
    parts = _parse(envelope)
    _assert_version_recorded(parts.version, expected.envelope_version)
    data_key = _unwrap(
        parts.wrapped_key,
        nonce=parts.wrap_nonce,
        master_key=master_key,
        aad=_aad(_WRAP, parts.version, expected.object_key),
    )
    plaintext = _decrypt(
        parts.ciphertext,
        nonce=parts.content_nonce,
        data_key=data_key,
        aad=_aad(_CONTENT, parts.version, expected.object_key),
    )
    _assert_plaintext_expected(plaintext, expected.plaintext_sha256_hex)
    return plaintext


def _assert_version_recorded(stored: int, recorded: int | None) -> None:
    """The row and the object must name one format.

    The ciphertext digest already binds them, so this refuses a row that was
    recorded wrongly rather than a forgery.
    """
    if recorded is not None and stored != recorded:
        raise EnvelopeError("Stored object and its record name different versions.")


def _aad(purpose: bytes, version: int, object_key: str) -> bytes | None:
    """The additional authenticated data for one GCM call of one format version.

    `v1` binds nothing, which is exactly how every `v1` object was sealed. The key
    is validated for both versions so a caller that lost it fails the same way
    whichever format it happens to read.
    """
    if not isinstance(object_key, str) or not object_key:
        raise EnvelopeError("An envelope is bound to a non-empty object key.")
    if version == LEGACY_ENVELOPE_VERSION:
        return None
    return b"".join(
        (
            _AAD_DOMAIN,
            purpose,
            b"\x00",
            version.to_bytes(_VERSION_BYTES, "big"),
            object_key.encode("utf-8"),
        )
    )


@dataclass(frozen=True, slots=True)
class _Parts:
    """One envelope's fields, after its length and version were accepted."""

    version: int
    wrap_nonce: bytes
    content_nonce: bytes
    wrapped_key: bytes
    ciphertext: bytes


def _assert_ciphertext_unchanged(envelope: bytes, expected_hex: str) -> None:
    """The read-back proof, checked before the cipher runs.

    Bytes that were not the bytes written are rejected without being decrypted.
    """
    if hashlib.sha256(envelope).hexdigest() != expected_hex:
        raise EnvelopeError("Stored ciphertext does not match the recorded digest.")


def _parse(envelope: bytes) -> _Parts:
    """Split an envelope into its fields, refusing a short or unknown one."""
    if len(envelope) < _HEADER_BYTES:
        raise EnvelopeError("Envelope is shorter than its header.")
    if envelope[0] not in READABLE_ENVELOPE_VERSIONS:
        raise EnvelopeError("Unsupported envelope version.")
    return _Parts(
        version=envelope[0],
        wrap_nonce=envelope[_VERSION_BYTES : _VERSION_BYTES + NONCE_BYTES],
        content_nonce=envelope[_VERSION_BYTES + NONCE_BYTES : _VERSION_BYTES + 2 * NONCE_BYTES],
        wrapped_key=envelope[_VERSION_BYTES + 2 * NONCE_BYTES : _HEADER_BYTES],
        ciphertext=envelope[_HEADER_BYTES:],
    )


def _unwrap(
    wrapped_key: bytes, *, nonce: bytes, master_key: MasterKey, aad: bytes | None
) -> bytes:
    """Recover the data key, or refuse without saying which part was wrong."""
    try:
        data_key = AESGCM(master_key.material).decrypt(nonce, wrapped_key, aad)
    except InvalidTag as error:
        # The master key is wrong, the wrapped key or its nonce was edited, or the
        # object was read under another key or version than it was sealed for.
        # Which one is not reported: the distinction is only useful to a forger.
        raise EnvelopeError("The wrapped data key could not be authenticated.") from error
    if len(data_key) != DATA_KEY_BYTES:
        raise EnvelopeError("The wrapped data key is the wrong length.")
    return data_key


def _decrypt(ciphertext: bytes, *, nonce: bytes, data_key: bytes, aad: bytes | None) -> bytes:
    try:
        return AESGCM(data_key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as error:
        raise EnvelopeError("The object content could not be authenticated.") from error


def _assert_plaintext_expected(plaintext: bytes, expected_hex: str) -> None:
    """Reachable only when the row and the object no longer describe each other.

    The content authenticated, so it is the content somebody encrypted -- but not
    the content this row says it is. Fail rather than return either answer.
    """
    if hashlib.sha256(plaintext).hexdigest() != expected_hex:
        raise EnvelopeError("Decrypted content does not match the recorded digest.")


def assert_supported(*, algorithm: str, envelope_version: int) -> None:
    """Refuse persisted metadata this build cannot honour.

    Called before a read is attempted so an unreadable row is rejected as a
    storage-policy failure rather than as a decryption failure deep in the cipher.
    """
    if algorithm != ALGORITHM_AES_256_GCM:
        raise EnvelopeError("Unsupported object encryption algorithm.")
    if envelope_version not in READABLE_ENVELOPE_VERSIONS:
        raise EnvelopeError("Unsupported envelope version.")


__all__ = [
    "ALGORITHM_AES_256_GCM",
    "DATA_KEY_BYTES",
    "LEGACY_ENVELOPE_VERSION",
    "MASTER_KEY_BYTES",
    "NONCE_BYTES",
    "READABLE_ENVELOPE_VERSIONS",
    "WRITE_ENVELOPE_VERSION",
    "EnvelopeError",
    "ExpectedObject",
    "MasterKey",
    "SealedObject",
    "assert_supported",
    "envelope_version_of",
    "open_envelope",
    "seal",
]
