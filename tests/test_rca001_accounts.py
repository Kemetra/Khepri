from __future__ import annotations

import secrets

import pytest

from khepri.rca import accounts as accounts_module
from khepri.rca.accounts import (
    DEFAULT_KDF,
    Account,
    AccountService,
    KdfParams,
    hash_credential,
)
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

    messages = []
    exception_types = []
    for email, credential in (
        ("missing@example.test", CREDENTIAL),
        (EMAIL, "wrong credential"),
    ):
        with pytest.raises(AuthenticationFailed) as caught:
            service.authenticate(email, credential)
        messages.append(str(caught.value))
        exception_types.append(type(caught.value))

    assert len(set(messages)) == 1
    assert len(set(exception_types)) == 1


def _rejection_work(
    service: AccountService,
    monkeypatch: pytest.MonkeyPatch,
    cases: tuple[tuple[str, str, str], ...],
) -> dict[str, int]:
    """The DEFAULT_KDF hash calls each rejection path issues, keyed by label.

    Records which parameters each path hashes at, rather than measuring wall-clock (flaky on
    shared CI runners) or summing nominal n*r*p (which cannot see that scrypt is memory-hard,
    so 2 calls at n=2**14 and 1 at n=2**15 have equal nominal cost but different real cost —
    measured within 0.4% on one CPU and 0.14s vs 0.23s on another).
    """
    calls: dict[str, list[KdfParams]] = {}
    real_hash = accounts_module.hash_credential
    current = ""

    def _recording(credential: str, salt: bytes, kdf: KdfParams = DEFAULT_KDF) -> bytes:
        calls[current].append(kdf)
        return real_hash(credential, salt, kdf)

    monkeypatch.setattr(accounts_module, "hash_credential", _recording)
    for label, email, credential in cases:
        current = label
        calls[current] = []
        with pytest.raises(AuthenticationFailed):
            service.authenticate(email, credential)
    return {label: [k for k in issued if k == DEFAULT_KDF] for label, issued in calls.items()}


def test_every_rejection_path_spends_the_same_work(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-004: a refusal must not reveal which check failed, including via cost.

    The missing-account path returns before any verifier exists and the wrong-credential
    path hashes for real. Both must cost the same, or the difference is an
    account-enumeration oracle.
    """
    service = _service()
    service.create_account(EMAIL, CREDENTIAL)

    totals = _rejection_work(
        service,
        monkeypatch,
        (
            ("missing", "missing@example.test", CREDENTIAL),
            ("wrong_credential", EMAIL, "wrong credential"),
        ),
    )

    assert {label: len(issued) for label, issued in totals.items()} == dict.fromkeys(totals, 1)


def test_duplicate_email_is_refused_uniformly() -> None:
    service = _service()
    service.create_account(EMAIL, CREDENTIAL)
    with pytest.raises(AuthenticationFailed):
        service.create_account(EMAIL, "another credential")


@pytest.mark.parametrize(
    "variant",
    [
        "owner@EXAMPLE.TEST",
        "OWNER@example.test",
        "Owner@Example.Test",
        "  owner@example.test  ",
    ],
)
def test_the_same_mailbox_cannot_hold_two_accounts(variant: str) -> None:
    """A-1: one durable identity per email address.

    The domain is case-insensitive, so storing variants verbatim under a case-sensitive
    unique constraint would admit two accounts for one mailbox and make recovery and
    invitation addressing ambiguous.
    """
    service = _service()
    service.create_account(EMAIL, CREDENTIAL)
    with pytest.raises(AuthenticationFailed):
        service.create_account(variant, "another credential")


@pytest.mark.parametrize(
    "variant",
    ["owner@EXAMPLE.TEST", "OWNER@example.test", "  Owner@Example.Test  "],
)
def test_authentication_accepts_any_casing_of_the_registered_address(variant: str) -> None:
    service = _service()
    created = service.create_account(EMAIL, CREDENTIAL)
    assert service.authenticate(variant, CREDENTIAL).account_id == created.account_id


def test_the_stored_address_is_canonical() -> None:
    service = _service()
    account = service.create_account("  Owner@EXAMPLE.Test  ", CREDENTIAL)
    assert account.email == EMAIL


def test_a_legacy_record_still_issues_exactly_one_default_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The invariant is the SHAPE of the work, not its nominal sum.

    Summing `n*r*p` treats two hashes at n=2**14 as equal to one at n=2**15. scrypt is
    memory-hard, so they are not: 2x16 MiB behaves differently from 1x32 MiB, measured
    within 0.4% on one CPU and 0.14s vs 0.23s on another. Asserting that every path issues
    exactly one DEFAULT_KDF call closes that gap by construction.

    The legacy path additionally issues one cheaper stored-factor call, so it runs SLOWER
    than a missing account (measured 200ms vs 128ms), never faster. Only a faster response
    would reveal that an account is absent, so the residual is in the safe direction.
    Eliminating it needs re-hashing legacy records on successful login, which requires a
    write path and is deferred with the rest of the account-mutation surface.
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

    issued: list[KdfParams] = []
    real_hash = accounts_module.hash_credential

    def _recording(credential: str, salt: bytes, kdf: KdfParams = DEFAULT_KDF) -> bytes:
        issued.append(kdf)
        return real_hash(credential, salt, kdf)

    monkeypatch.setattr(accounts_module, "hash_credential", _recording)
    with pytest.raises(AuthenticationFailed):
        service.authenticate("legacy@example.test", "wrong credential")

    assert issued.count(DEFAULT_KDF) == 1, f"expected one default-parameter hash: {issued}"
    assert all(k.n <= DEFAULT_KDF.n for k in issued), "no path may exceed the default factor"


def test_a_legacy_work_factor_does_not_reveal_account_existence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    # Uniformity is TWO-SIDED, which an earlier one-sided bound missed: paying a whole
    # default-cost hash on top of the legacy hash made the legacy path 1.49x the
    # missing-account path — still an oracle, just inverted, and 1/1.49 cleared a 0.6 floor.
    # Comparing exact work totals catches both the undershoot and the overshoot.
    totals = _rejection_work(
        service,
        monkeypatch,
        (
            ("missing", "missing@example.test", CREDENTIAL),
            ("legacy", "legacy@example.test", "wrong credential"),
            ("current", EMAIL, "wrong credential"),
        ),
    )

    assert {label: len(issued) for label, issued in totals.items()} == dict.fromkeys(totals, 1)
