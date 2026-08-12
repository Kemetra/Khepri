from __future__ import annotations

import secrets
import time

import pytest

from khepri.rca.accounts import Account, AccountService, KdfParams, hash_credential
from khepri.rca.errors import AuthenticationFailed

EMAIL = "owner@example.test"
CREDENTIAL = "correct horse battery staple"


class MemoryAccountStore:
    def __init__(self) -> None:
        self.accounts: dict[str, Account] = {}

    def add_account(self, account: Account) -> bool:
        if any(existing.email == account.email for existing in self.accounts.values()):
            return False
        self.accounts[account.account_id] = account
        return True

    def get_account_by_email(self, email: str) -> Account | None:
        for account in self.accounts.values():
            if account.email == email:
                return account
        return None

    def get_account(self, account_id: str) -> Account | None:
        return self.accounts.get(account_id)

    def update_account(self, account: Account) -> None:
        self.accounts[account.account_id] = account


def _service() -> AccountService:
    return AccountService(MemoryAccountStore())


def test_create_account_establishes_durable_identity() -> None:
    service = _service()
    account = service.create_account(EMAIL, CREDENTIAL)
    assert account.account_id.startswith("acc_")
    assert account.email == EMAIL
    assert account.disabled is False


def test_credential_is_never_stored_in_recoverable_form() -> None:
    service = _service()
    account = service.create_account(EMAIL, CREDENTIAL)
    secret = CREDENTIAL.encode()

    assert secret not in account.credential_digest
    assert CREDENTIAL not in repr(account)
    # The salt must participate: the same credential under a different salt differs.
    assert account.credential_digest != hash_credential(CREDENTIAL, b"0" * 16)


def test_credential_digest_records_its_work_factor() -> None:
    service = _service()
    account = service.create_account(EMAIL, CREDENTIAL)
    assert (account.kdf.n, account.kdf.r, account.kdf.p) == (2**15, 8, 1)
    assert len(account.credential_salt) == 16
    assert len(account.credential_digest) == 32


def test_same_credential_yields_distinct_digests_across_accounts() -> None:
    service = _service()
    first = service.create_account("a@example.test", CREDENTIAL)
    second = service.create_account("b@example.test", CREDENTIAL)
    assert first.credential_digest != second.credential_digest


def test_authenticate_succeeds_with_correct_credential() -> None:
    service = _service()
    created = service.create_account(EMAIL, CREDENTIAL)
    assert service.authenticate(EMAIL, CREDENTIAL).account_id == created.account_id


def test_authentication_failures_are_uniform() -> None:
    service = _service()
    service.create_account(EMAIL, CREDENTIAL)
    disabled = service.create_account("off@example.test", CREDENTIAL)
    service.disable_account(disabled.account_id)

    messages = []
    exception_types = []
    for email, credential in (
        ("missing@example.test", CREDENTIAL),
        (EMAIL, "wrong credential"),
        ("off@example.test", CREDENTIAL),
    ):
        with pytest.raises(AuthenticationFailed) as caught:
            service.authenticate(email, credential)
        messages.append(str(caught.value))
        exception_types.append(type(caught.value))

    assert len(set(messages)) == 1
    assert len(set(exception_types)) == 1


def test_authentication_timing_does_not_reveal_account_existence() -> None:
    service = _service()
    service.create_account(EMAIL, CREDENTIAL)
    disabled = service.create_account("off@example.test", CREDENTIAL)
    service.disable_account(disabled.account_id)

    def _best_of_3(email: str, credential: str) -> float:
        best = float("inf")
        for _ in range(3):
            start = time.perf_counter()
            with pytest.raises(AuthenticationFailed):
                service.authenticate(email, credential)
            elapsed = time.perf_counter() - start
            best = min(best, elapsed)
        return best

    missing_time = _best_of_3("missing@example.test", CREDENTIAL)
    wrong_credential_time = _best_of_3(EMAIL, "wrong credential")
    disabled_time = _best_of_3("off@example.test", CREDENTIAL)

    timings = (missing_time, wrong_credential_time, disabled_time)
    assert min(timings) > max(timings) * 0.5


def test_duplicate_email_is_refused_uniformly() -> None:
    service = _service()
    service.create_account(EMAIL, CREDENTIAL)
    with pytest.raises(AuthenticationFailed):
        service.create_account(EMAIL, "another credential")


def test_hash_credential_is_deterministic_for_a_fixed_salt() -> None:
    salt = b"0123456789abcdef"
    first = hash_credential(CREDENTIAL, salt, KdfParams(n=2**14))
    second = hash_credential(CREDENTIAL, salt, KdfParams(n=2**14))
    assert first == second
    assert hash_credential("other", salt, KdfParams(n=2**14)) != first


def test_a_legacy_work_factor_does_not_reveal_account_existence() -> None:
    """FR-004 must survive a KDF upgrade, which is what KdfParams exists to support.

    A record stored at an older, cheaper work factor verifies faster than the default the
    missing-account path pays. Without padding, raising DEFAULT_KDF would make a legacy
    account's rejection observably cheaper than a nonexistent one.
    """
    store = MemoryAccountStore()
    service = AccountService(store)
    legacy_kdf = KdfParams(n=2**14)
    salt = secrets.token_bytes(16)
    store.add_account(
        Account(
            account_id="acc_legacy",
            email="legacy@example.test",
            credential_salt=salt,
            credential_digest=hash_credential(CREDENTIAL, salt, legacy_kdf),
            kdf=legacy_kdf,
        )
    )
    service.create_account(EMAIL, CREDENTIAL)

    def _best_of_3(email: str, credential: str) -> float:
        best = float("inf")
        for _ in range(3):
            start = time.perf_counter()
            with pytest.raises(AuthenticationFailed):
                service.authenticate(email, credential)
            best = min(best, time.perf_counter() - start)
        return best

    timings = (
        _best_of_3("missing@example.test", CREDENTIAL),
        _best_of_3("legacy@example.test", "wrong credential"),
        _best_of_3(EMAIL, "wrong credential"),
    )
    # Uniformity is TWO-SIDED, so bound the spread rather than just the floor. A one-sided
    # `min > max * 0.6` accepted an earlier fix that overshot: paying a whole default-cost
    # hash on top of the legacy hash made the legacy path 1.49x the missing-account path —
    # still an oracle, just inverted (1/1.49 = 0.67, which cleared a 0.6 floor).
    #
    # Unpadded the spread is ~2.0x; overshooting it was ~1.5x; paying only the shortfall
    # measures ~1.00x. A 1.3x ceiling rejects both failure modes with margin for noise.
    assert max(timings) / min(timings) < 1.3
