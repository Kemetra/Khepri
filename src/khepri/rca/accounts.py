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


def _scrypt_cost(kdf: KdfParams) -> int:
    """Relative cost of one scrypt call. Work scales with ``n * r * p``."""
    return kdf.n * kdf.r * kdf.p


def shortfall_schedule(kdf: KdfParams) -> tuple[KdfParams, ...]:
    """Padding hashes whose combined cost exactly covers the deficit against the default.

    Empty when the stored parameters already cost at least the default.

    A single rounded-down step is not enough. scrypt requires ``n`` to be a power of two, so
    one step can only ever pay a power-of-two share of the deficit: at a stored ``n=2**13``
    against a default of ``2**15`` that covered 75% of the required work, and at ``2**12``
    only 62% — an existence oracle in exactly the range this padding exists to close. Since
    every deficit is a sum of distinct powers of two, decomposing it into one hash per set
    bit covers it exactly, with no residual.
    """
    deficit = _scrypt_cost(DEFAULT_KDF) - _scrypt_cost(kdf)
    if deficit <= 0:
        return ()
    unit = DEFAULT_KDF.r * DEFAULT_KDF.p
    steps = deficit // unit
    return tuple(
        KdfParams(n=1 << bit, r=DEFAULT_KDF.r, p=DEFAULT_KDF.p)
        for bit in range(steps.bit_length())
        if steps >> bit & 1 and bit >= 1
    )


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
        account = self._store.get_account_by_email(canonical_email(email))
        if account is None:
            # Pay the same scrypt cost as a real rejection so a missing account cannot be
            # distinguished from a wrong credential by wall-clock timing (FR-004).
            hash_credential(credential, _DUMMY_SALT, DEFAULT_KDF)
            self._reject()
        if not account.has_verifier:
            # No verifier stored. Pay the default cost anyway so this is indistinguishable
            # from a wrong credential (FR-004).
            hash_credential(credential, _DUMMY_SALT, DEFAULT_KDF)
            self._reject()
        assert account.credential_salt is not None  # narrowed by has_verifier
        assert account.credential_digest is not None
        assert account.kdf is not None
        self._pad_legacy_verification(account.kdf)
        candidate = hash_credential(credential, account.credential_salt, account.kdf)
        if not hmac.compare_digest(candidate, account.credential_digest):
            self._reject()
        return account

    @staticmethod
    def _pad_legacy_verification(kdf: KdfParams) -> None:
        """Spend exactly the SHORTFALL between a record's stored cost and the default.

        Every rejection path must cost the same total. A record stored at an older, cheaper
        work factor verifies for less than the default that the missing-account path always
        pays, so the difference has to be made up — otherwise raising `DEFAULT_KDF`, the
        upgrade `KdfParams` exists to support, would make a legacy account's rejection
        observably cheaper than a nonexistent one.

        Adding a *whole* default-cost hash overshoots and leaks in the other direction: the
        legacy path would then cost the stored hash plus a full default, measured at 1.49x
        the missing-account path. Uniformity is two-sided, so this pays the remainder only,
        and pays all of it — see `shortfall_schedule` for why one step is not enough.
        """
        for step in shortfall_schedule(kdf):
            hash_credential("", _DUMMY_SALT, step)

    @staticmethod
    def _reject() -> None:
        raise AuthenticationFailed(AUTHENTICATION_FAILURE)
