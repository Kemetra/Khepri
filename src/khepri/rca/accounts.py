"""Durable commercial identity: accounts and credential verification (`RCA-001` slice 1).

Covers FR-001 (durable account), FR-002 (verifier stored only as a salted hash), FR-004
(uniform, content-free refusals), and A-1 (one identity per email address).

**Account lifecycle is deliberately NOT in this slice.** Disablement sits at the
intersection of three requirements this slice does not implement — `KHEPRI-DEC-015`'s
24-month retention horizon and opaque tombstone, `FR-008`'s session revocation, and
`FR-013`'s final-owner guard — and implementing it without them produced a disabled account
that stranded its organization and retained its login identity indefinitely. It gets its own
slice, with a design first. The verifier columns are already nullable so that slice needs no
migration to destroy a verifier.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from khepri.rca.errors import AUTHENTICATION_FAILURE, AuthenticationFailed

if TYPE_CHECKING:
    from khepri.rca.stores import AccountStore

KDF_N = 2**15
KDF_R = 8
KDF_P = 1
KDF_DKLEN = 32
SALT_BYTES = 16
# A fixed dummy salt used to pay the same scrypt cost for a missing account as for a
# wrong-credential rejection, so account existence is not revealed through timing (FR-004).
_DUMMY_SALT = b"\x00" * SALT_BYTES


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


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    email: str
    # Nullable so the schema can represent an account with no verifier. KHEPRI-DEC-015
    # retains the credential verifier only "while the account is enabled" and requires
    # immediate, non-recoverable destruction on disablement or replacement. Disablement
    # itself is not in this slice (see the module docstring), but the shape it requires is,
    # so the lifecycle slice does not need a migration to introduce it.
    credential_salt: bytes | None
    credential_digest: bytes | None
    kdf: KdfParams | None

    @property
    def has_verifier(self) -> bool:
        return (
            self.credential_salt is not None
            and self.credential_digest is not None
            and self.kdf is not None
        )


# scrypt needs 128 * n * r bytes = 64 MiB at n=2**15, r=8, which exceeds OpenSSL's 32 MiB
# default. Without an explicit maxmem, hashlib.scrypt raises
# ValueError("[digital envelope routines] memory limit exceeded"). Verified on this machine.
def canonical_email(email: str) -> str:
    """Canonical form used for both storage and lookup, so uniqueness is meaningful.

    `RCA-001` A-1 requires one durable identity per email address. The domain is
    case-insensitive per RFC 1035, so `owner@example.test` and `owner@EXAMPLE.TEST` are the
    same mailbox; storing both verbatim under a case-sensitive unique constraint would admit
    two accounts for one address and make recovery and invitation addressing ambiguous.

    The local part is lowercased too. RFC 5321 permits it to be case-sensitive, but no
    mainstream provider treats it that way, and admitting `Owner@` beside `owner@` as
    distinct identities would be a footgun rather than a feature. Surrounding whitespace is
    stripped; nothing else is normalised, so provider-specific rules such as Gmail's dots
    and `+` tags are deliberately out of scope.
    """
    return email.strip().lower()


def _is_verifiable(account: Account | None) -> bool:
    """True only for a record this slice can verify: present, complete, at the default factor."""
    return account is not None and account.has_verifier and account.kdf == DEFAULT_KDF


def _verifiable_salt(account: Account | None) -> bytes:
    """The record's salt, or a fixed dummy so an unverifiable record costs the same."""
    if _is_verifiable(account):
        assert account is not None and account.credential_salt is not None
        return account.credential_salt
    return _DUMMY_SALT


def _verifiable_digest(account: Account | None) -> bytes | None:
    """The digest to compare against, or None when the record cannot be verified here."""
    if _is_verifiable(account):
        assert account is not None
        return account.credential_digest
    return None


def hash_credential(credential: str, salt: bytes, kdf: KdfParams = DEFAULT_KDF) -> bytes:
    return hashlib.scrypt(
        credential.encode(),
        salt=salt,
        n=kdf.n,
        r=kdf.r,
        p=kdf.p,
        dklen=KDF_DKLEN,
        maxmem=128 * kdf.n * kdf.r * 2,
    )


class AccountService:
    def __init__(self, store: AccountStore) -> None:
        self._store = store

    def create_account(self, email: str, credential: str) -> Account:
        salt = secrets.token_bytes(SALT_BYTES)
        account = Account(
            account_id=f"acc_{secrets.token_urlsafe(18)}",
            email=canonical_email(email),
            credential_salt=salt,
            credential_digest=hash_credential(credential, salt, DEFAULT_KDF),
            kdf=DEFAULT_KDF,
        )
        if not self._store.add_account(account):
            raise AuthenticationFailed(AUTHENTICATION_FAILURE)
        return account

    def authenticate(self, email: str, credential: str) -> Account:
        """Verify a credential with exactly one scrypt call at `DEFAULT_KDF`, on every path.

        Missing account, verifier-less row, wrong credential, success — all four perform the
        identical operation, so none is distinguishable from another by cost (FR-004).

        **This slice supports exactly one work factor**, and that is what makes the property
        hold rather than merely be approximated. Three earlier attempts to support
        per-record factors all leaked: padding the nominal `n*r*p` shortfall ignored that
        scrypt is memory-hard (two calls at `n=2**14` versus one at `n=2**15` measured
        within 0.4% on one CPU and 0.14s versus 0.23s on another); padding a full default
        cost overshot to 1.49x; verifying at the stored factor plus one default hash still
        cost about 1.5x. Each was a workaround for the real gap — a legacy record can only
        be made uniform by re-hashing it to the current default on successful login, and
        that needs a write path.

        So `KdfParams` is stored per record but only `DEFAULT_KDF` is ever used to verify.
        A record at any other factor is refused, uniformly, rather than verified cheaply.
        The upgrade path lands with the write path in the lifecycle slice.
        """
        account = self._store.get_account_by_email(canonical_email(email))
        expected = _verifiable_digest(account)
        candidate = hash_credential(credential, _verifiable_salt(account), DEFAULT_KDF)
        if expected is None or not hmac.compare_digest(candidate, expected):
            self._reject()
        assert account is not None  # a digest was recovered, so the account exists
        return account

    @staticmethod
    def _reject() -> None:
        raise AuthenticationFailed(AUTHENTICATION_FAILURE)
