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
    # All three are None once the verifier has been destroyed. KHEPRI-DEC-015 retains the
    # credential verifier only "while the account is enabled" and requires immediate,
    # non-recoverable destruction on disablement or replacement.
    credential_salt: bytes | None
    credential_digest: bytes | None
    kdf: KdfParams | None
    disabled: bool = False

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
def _scrypt_cost(kdf: KdfParams) -> int:
    """Relative cost of one scrypt call. Work scales with ``n * r * p``."""
    return kdf.n * kdf.r * kdf.p


def _shortfall_params(kdf: KdfParams) -> KdfParams | None:
    """Parameters costing the difference between ``kdf`` and the default, or None.

    Returns None when the stored parameters already cost at least the default, so no
    padding is needed. Otherwise returns a `KdfParams` whose cost is the remainder, keeping
    the total spent on a legacy verification equal to one default-cost hash.

    The remainder is carried on ``n`` because scrypt requires ``n`` to be a power of two
    greater than one. Rounding down to a power of two makes the padding slightly cheap
    rather than slightly expensive, and the residual is far below the measurement noise a
    remote attacker can resolve.
    """
    deficit = _scrypt_cost(DEFAULT_KDF) - _scrypt_cost(kdf)
    if deficit <= 0:
        return None
    n = 1 << max(1, (deficit // (DEFAULT_KDF.r * DEFAULT_KDF.p)).bit_length() - 1)
    return KdfParams(n=n, r=DEFAULT_KDF.r, p=DEFAULT_KDF.p)


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
        if not account.has_verifier:
            # The verifier was destroyed at disablement (KHEPRI-DEC-015). Pay the default
            # cost anyway so this is indistinguishable from a wrong credential (FR-004).
            hash_credential(credential, _DUMMY_SALT, DEFAULT_KDF)
            self._reject()
        assert account.credential_salt is not None  # narrowed by has_verifier
        assert account.credential_digest is not None
        assert account.kdf is not None
        self._pad_legacy_verification(account.kdf)
        candidate = hash_credential(credential, account.credential_salt, account.kdf)
        if not hmac.compare_digest(candidate, account.credential_digest):
            self._reject()
        if account.disabled:
            self._reject()
        return account

    def disable_account(self, account_id: str) -> None:
        """Disable the account and destroy its credential verifier in one write.

        KHEPRI-DEC-015 retains the verifier only while the account is enabled, and requires
        destruction to be immediate and non-recoverable at disablement. Clearing it in the
        same update as the flag means no window exists where a disabled account still holds
        a guessable verifier.
        """
        account = self._store.get_account(account_id)
        if account is None:
            return
        self._store.update_account(
            replace(
                account,
                disabled=True,
                credential_salt=None,
                credential_digest=None,
                kdf=None,
            )
        )

    @staticmethod
    def _pad_legacy_verification(kdf: KdfParams) -> None:
        """Spend only the SHORTFALL between a record's stored cost and the default.

        Every rejection path must cost the same total. A record stored at an older, cheaper
        work factor verifies for less than the default that the missing-account path always
        pays, so the difference has to be made up — otherwise raising `DEFAULT_KDF`, the
        upgrade `KdfParams` exists to support, would make a legacy account's rejection
        observably cheaper than a nonexistent one.

        Adding a *whole* default-cost hash overshoots and leaks in the other direction: the
        legacy path would then cost the stored hash plus a full default, measured at 1.49x
        the missing-account path. Uniformity is two-sided, so this pays the remainder only.
        """
        shortfall = _shortfall_params(kdf)
        if shortfall is None:
            return
        hash_credential("", _DUMMY_SALT, shortfall)

    @staticmethod
    def _reject() -> None:
        raise AuthenticationFailed(AUTHENTICATION_FAILURE)
