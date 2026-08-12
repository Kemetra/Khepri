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
# scrypt needs 128 * n * r bytes = 64 MiB at n=2**15, r=8, which exceeds OpenSSL's 32 MiB
# default. Without an explicit maxmem, hashlib.scrypt raises
# ValueError("[digital envelope routines] memory limit exceeded"). Verified on this machine.
KDF_MAXMEM = 128 * KDF_N * KDF_R * 2


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    email: str
    credential_salt: bytes
    credential_digest: bytes
    kdf_n: int
    kdf_r: int
    kdf_p: int
    disabled: bool = False


def hash_credential(credential: str, salt: bytes, *, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        credential.encode(),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=KDF_DKLEN,
        maxmem=128 * n * r * 2,
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
            credential_digest=hash_credential(credential, salt, n=KDF_N, r=KDF_R, p=KDF_P),
            kdf_n=KDF_N,
            kdf_r=KDF_R,
            kdf_p=KDF_P,
        )
        if not self._store.add_account(account):
            raise AuthenticationFailed(AUTHENTICATION_FAILURE)
        return account

    def authenticate(self, email: str, credential: str) -> Account:
        account = self._store.get_account_by_email(email)
        if account is None:
            self._reject()
        candidate = hash_credential(
            credential,
            account.credential_salt,
            n=account.kdf_n,
            r=account.kdf_r,
            p=account.kdf_p,
        )
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
    def _reject() -> None:
        raise AuthenticationFailed(AUTHENTICATION_FAILURE)
