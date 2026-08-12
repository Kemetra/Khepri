from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass, replace
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
    credential_salt: bytes
    credential_digest: bytes
    kdf: KdfParams
    disabled: bool = False


# scrypt needs 128 * n * r bytes = 64 MiB at n=2**15, r=8, which exceeds OpenSSL's 32 MiB
# default. Without an explicit maxmem, hashlib.scrypt raises
# ValueError("[digital envelope routines] memory limit exceeded"). Verified on this machine.
def _is_cheaper_than_default(kdf: KdfParams) -> bool:
    """True when verifying against ``kdf`` costs less than the current default would."""
    stored = (kdf.n, kdf.r, kdf.p)
    default = (DEFAULT_KDF.n, DEFAULT_KDF.r, DEFAULT_KDF.p)
    return any(value < baseline for value, baseline in zip(stored, default, strict=True))


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
            email=email,
            credential_salt=salt,
            credential_digest=hash_credential(credential, salt, DEFAULT_KDF),
            kdf=DEFAULT_KDF,
        )
        if not self._store.add_account(account):
            raise AuthenticationFailed(AUTHENTICATION_FAILURE)
        return account

    def authenticate(self, email: str, credential: str) -> Account:
        account = self._store.get_account_by_email(email)
        if account is None:
            # Pay the same scrypt cost as a real rejection so a missing account cannot be
            # distinguished from a wrong credential by wall-clock timing (FR-004).
            hash_credential(credential, _DUMMY_SALT, DEFAULT_KDF)
            self._reject()
        self._pad_legacy_verification(account.kdf)
        candidate = hash_credential(credential, account.credential_salt, account.kdf)
        if not hmac.compare_digest(candidate, account.credential_digest):
            self._reject()
        if account.disabled:
            self._reject()
        return account

    def disable_account(self, account_id: str) -> None:
        account = self._store.get_account(account_id)
        if account is None:
            return
        self._store.update_account(replace(account, disabled=True))

    @staticmethod
    def _pad_legacy_verification(kdf: KdfParams) -> None:
        """Spend the shortfall when a record's stored work factor is below the default.

        Verifying a legacy record costs less than the current default, and the
        missing-account path always pays the default. Without this padding, raising
        `DEFAULT_KDF` would make an old account's rejection observably cheaper than a
        nonexistent one and reveal which is which — the exact oracle FR-004 forbids, and a
        live risk because `KdfParams` exists precisely to support that upgrade.
        """
        if not _is_cheaper_than_default(kdf):
            return
        hash_credential("", _DUMMY_SALT, DEFAULT_KDF)

    @staticmethod
    def _reject() -> None:
        raise AuthenticationFailed(AUTHENTICATION_FAILURE)
