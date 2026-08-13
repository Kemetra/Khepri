"""Credential material: derivation, storage shape, and destruction (FR-002).

This module exists so that "make a verifier" and "destroy a verifier" are each **one trusted
operation** rather than a set of field assignments any layer can perform. #151 recorded the
finding this closes: `SqlAccountStore.add_account` accepted an `Account` carrying
`credential_digest=credential.encode()` with an empty salt, and committed it — a recoverable
credential at rest, in violation of FR-002.

The fix is not to validate the digest at the store. A digest cannot be distinguished from an
arbitrary 32-byte string by inspection, so shape checking cannot establish that a real KDF
produced it — the same reason #148's round 2 failed to close the isolation-key hole by
validating the key's shape. Instead there is no path that accepts a caller-supplied digest for
a *new* account: `Verifier.derive` allocates the salt and runs the KDF itself.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

KDF_N = 2**15
KDF_R = 8
KDF_P = 1
KDF_DKLEN = 32
SALT_BYTES = 16
# A fixed dummy salt used to pay the same scrypt cost for a missing account as for a
# wrong-credential rejection, so account existence is not revealed through timing (FR-004).
DUMMY_SALT = b"\x00" * SALT_BYTES


@dataclass(frozen=True, slots=True)
class KdfParams:
    """The scrypt cost parameters a digest was produced with.

    Stored alongside each digest so the work factor can be raised later without
    invalidating existing records.
    """

    n: int = KDF_N
    r: int = KDF_R
    p: int = KDF_P


DEFAULT_KDF = KdfParams()


# scrypt needs 128 * n * r bytes = 64 MiB at n=2**15, r=8, which exceeds OpenSSL's 32 MiB
# default. Without an explicit maxmem, hashlib.scrypt raises
# ValueError("[digital envelope routines] memory limit exceeded"). Verified on this machine.
def hash_credential(credential: str, salt: bytes, kdf: KdfParams = DEFAULT_KDF) -> bytes:
    """Derive a digest from a credential and salt at the given work factor.

    Public because it carries no invariant of its own: it is a pure function of its inputs,
    and the property that matters — that a *stored* verifier was produced by it rather than
    supplied by a caller — is owned by `Verifier.derive`, not by this function. Tests call it
    directly to construct legacy-factor records and to assert salt participation.
    """
    return hashlib.scrypt(
        credential.encode(),
        salt=salt,
        n=kdf.n,
        r=kdf.r,
        p=kdf.p,
        dklen=KDF_DKLEN,
        maxmem=128 * kdf.n * kdf.r * 2,
    )


@dataclass(frozen=True, slots=True)
class Verifier:
    """A salted credential verifier: everything needed to check a credential, and nothing more.

    The credential itself is never held. `KHEPRI-DEC-015` requires the verifier to be destroyed
    immediately and non-recoverably on disablement or replacement, which is why an account holds
    this as an optional whole rather than three independently-nullable columns: destruction is
    then "set the verifier to None", one assignment that cannot be done by halves.
    """

    salt: bytes
    digest: bytes
    kdf: KdfParams

    @classmethod
    def derive(cls, credential: str) -> Verifier:
        """Produce a verifier for a new or replacement credential, at the current default factor.

        Allocates the salt from a CSPRNG. There is deliberately no parameter for the salt or the
        digest: this is the only supported way to obtain a verifier for a credential, so a
        caller cannot substitute credential-derived material for a real derivation.
        """
        salt = secrets.token_bytes(SALT_BYTES)
        return cls(
            salt=salt,
            digest=hash_credential(credential, salt, DEFAULT_KDF),
            kdf=DEFAULT_KDF,
        )

    @classmethod
    def from_storage(cls, salt: bytes, digest: bytes, kdf: KdfParams) -> Verifier:
        """Rebuild a verifier from stored columns, preserving them verbatim.

        Reading must not re-derive: the stored digest is the only thing a candidate can be
        compared against. Asserts nothing about the values, because they came from the database
        and the guarantee is that nothing but `derive` could have put them there.
        """
        return cls(salt=salt, digest=digest, kdf=kdf)
