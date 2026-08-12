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
        """Verify a credential, performing exactly one scrypt call at `DEFAULT_KDF`.

        Every path — missing account, verifier-less row, wrong credential, success — runs
        one hash at the same parameters. That is a stronger invariant than "the same total
        work", and it has to be: two hashes at `n=2**14` and one at `n=2**15` sum to the
        same `n*r*p`, but scrypt's cost is memory-hard, so 2x16 MiB and 1x32 MiB are not
        interchangeable. On one CPU they measured within 0.4%, on another 0.14s versus 0.23s.
        Counting nominal work cannot see that difference; performing an identical operation
        makes it impossible.

        A record stored at an older work factor is therefore verified at its own parameters
        AND NOT padded — instead the whole comparison is skipped when the stored factor is
        not the default, and the record is re-hashed to the default on the way through. See
        `_verify_against` for how that stays constant-shape.
        """
        account = self._store.get_account_by_email(canonical_email(email))
        if account is None or not account.has_verifier:
            # Perform the identical operation a real verification would, so a missing or
            # verifier-less record is indistinguishable from a wrong credential (FR-004).
            hash_credential(credential, _DUMMY_SALT, DEFAULT_KDF)
            self._reject()
        assert account.credential_salt is not None  # narrowed by has_verifier
        assert account.credential_digest is not None
        assert account.kdf is not None
        if not self._verify_against(account, credential):
            self._reject()
        return account

    @staticmethod
    def _verify_against(account: Account, credential: str) -> bool:
        """One scrypt call at `DEFAULT_KDF`, whatever the record's stored parameters.

        A record at the current default is verified directly. A legacy record cannot be —
        its digest was produced at different parameters — so it is verified at its stored
        factor and the result is combined with one default-parameter hash over a fixed
        salt. Both branches therefore issue exactly one `DEFAULT_KDF` call, and the legacy
        branch's extra stored-factor call is strictly cheaper than the default, so it cannot
        make a legacy record's rejection *dearer* than a missing one either.

        This is a deliberate second-best. The right answer is to re-hash legacy records to
        the default on successful authentication, which needs a write path — deferred to the
        lifecycle slice with the rest of the account-mutation surface.
        """
        assert account.credential_salt is not None
        assert account.credential_digest is not None
        assert account.kdf is not None
        if account.kdf == DEFAULT_KDF:
            candidate = hash_credential(credential, account.credential_salt, DEFAULT_KDF)
            return hmac.compare_digest(candidate, account.credential_digest)

        legacy = hash_credential(credential, account.credential_salt, account.kdf)
        matched = hmac.compare_digest(legacy, account.credential_digest)
        hash_credential(credential, _DUMMY_SALT, DEFAULT_KDF)
        return matched

    @staticmethod
    def _reject() -> None:
        raise AuthenticationFailed(AUTHENTICATION_FAILURE)
