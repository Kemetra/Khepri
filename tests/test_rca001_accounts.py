from __future__ import annotations

import pytest

from khepri.rca.accounts import Account, AccountService, hash_credential
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
    assert secret not in account.credential_salt
    assert CREDENTIAL not in repr(account)
    for field in (account.account_id, account.email):
        assert CREDENTIAL not in field
    # The salt must participate: the same credential under a different salt differs.
    assert account.credential_digest != hash_credential(
        CREDENTIAL, b"0" * 16, n=2**15, r=8, p=1
    )


def test_credential_digest_records_its_work_factor() -> None:
    service = _service()
    account = service.create_account(EMAIL, CREDENTIAL)
    assert (account.kdf_n, account.kdf_r, account.kdf_p) == (2**15, 8, 1)
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
    for email, credential in (
        ("missing@example.test", CREDENTIAL),
        (EMAIL, "wrong credential"),
        ("off@example.test", CREDENTIAL),
    ):
        with pytest.raises(AuthenticationFailed) as caught:
            service.authenticate(email, credential)
        messages.append(str(caught.value))

    assert len(set(messages)) == 1


def test_duplicate_email_is_refused_uniformly() -> None:
    service = _service()
    service.create_account(EMAIL, CREDENTIAL)
    with pytest.raises(AuthenticationFailed):
        service.create_account(EMAIL, "another credential")


def test_hash_credential_is_deterministic_for_a_fixed_salt() -> None:
    salt = b"0123456789abcdef"
    first = hash_credential(CREDENTIAL, salt, n=2**14, r=8, p=1)
    second = hash_credential(CREDENTIAL, salt, n=2**14, r=8, p=1)
    assert first == second
    assert hash_credential("other", salt, n=2**14, r=8, p=1) != first
