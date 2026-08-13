from __future__ import annotations

import secrets

import pytest

from khepri.rca import accounts as accounts_module
from khepri.rca.accounts import Account, AccountService
from khepri.rca.credentials import DEFAULT_KDF, KdfParams, Verifier, hash_credential
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

    assert account.verifier is not None
    assert secret not in account.verifier.digest
    assert CREDENTIAL not in repr(account)
    # The salt must participate: the same credential under a different salt differs.
    assert account.verifier.digest != hash_credential(CREDENTIAL, b"0" * 16)


def test_credential_digest_records_its_work_factor() -> None:
    service = _service()
    account = service.create_account(EMAIL, CREDENTIAL)
    assert account.verifier is not None
    kdf = account.verifier.kdf
    assert (kdf.n, kdf.r, kdf.p) == (2**15, 8, 1)
    assert len(account.verifier.salt) == 16
    assert len(account.verifier.digest) == 32


def test_same_credential_yields_distinct_digests_across_accounts() -> None:
    service = _service()
    first = service.create_account("a@example.test", CREDENTIAL)
    second = service.create_account("b@example.test", CREDENTIAL)
    assert first.verifier is not None and second.verifier is not None
    assert first.verifier.digest != second.verifier.digest


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

    `hash_credential` lives in `khepri.rca.credentials` but is imported by name into
    `khepri.rca.accounts`, so `accounts.authenticate` resolves it through the *accounts*
    module namespace. Patching `credentials.hash_credential` would therefore record nothing
    while every assertion below still passed: `dict.fromkeys({}, ...)` compares `{} == {}`.
    The patch target must be the module that calls it, and the recorder must be proven to
    have fired, which is what the assertion at the end of this helper is for.
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

    # Without this, a stale patch target makes every caller's uniformity assertion vacuous:
    # no path records anything, and comparing an empty dict to itself passes.
    assert calls and all(calls[label] for label in calls), (
        f"the recorder never fired: {calls!r} -- hash_credential is no longer resolved "
        "through khepri.rca.accounts, so this test proves nothing"
    )
    return calls


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

    assert totals == dict.fromkeys(totals, [DEFAULT_KDF])


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


def test_a_record_at_a_non_default_work_factor_is_refused_uniformly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This slice verifies at exactly one work factor, which is what makes FR-004 hold.

    Three earlier attempts to support per-record factors all leaked, because a cheaper
    stored factor cannot be made to cost the same as the default without re-hashing the
    record — and that needs a write path this slice does not have. Padding the nominal
    `n*r*p` shortfall ignored that scrypt is memory-hard (two calls at n=2**14 versus one at
    n=2**15 measured within 0.4% on one CPU and 0.14s versus 0.23s on another); padding a
    full default cost overshot to 1.49x; verifying at the stored factor plus one default
    hash still cost about 1.5x.

    So a non-default record is refused — even with the correct credential — and the refusal
    performs the identical single hash every other path performs. The upgrade path lands
    with the write path in the lifecycle slice.
    """
    store = MemoryAccountStore()
    service = AccountService(store)
    legacy_kdf = KdfParams(n=2**14)
    salt = secrets.token_bytes(16)
    # Both records stand in for rows a *previous* release wrote, so they are built through the
    # reconstruction door rather than `create` — which is exactly what that door is for, and
    # which `create` could not express anyway (it always derives at DEFAULT_KDF).
    store.add_account(
        Account._from_storage(
            account_id="acc_legacy",
            email="legacy@example.test",
            verifier=Verifier.from_storage(
                salt=salt,
                digest=hash_credential(CREDENTIAL, salt, legacy_kdf),
                kdf=legacy_kdf,
            ),
        )
    )
    store.add_account(
        Account._from_storage(
            account_id="acc_bare",
            email="bare@example.test",
            verifier=None,
        )
    )
    service.create_account(EMAIL, CREDENTIAL)

    # The load-bearing assertion: a non-default record does not authenticate, even with the
    # right credential. Without this, relaxing the work-factor check would keep the call
    # shape uniform (so the assertion below still passes) while silently reintroducing the
    # cheap-verification timing leak.
    with pytest.raises(AuthenticationFailed):
        service.authenticate("legacy@example.test", CREDENTIAL)

    issued = _rejection_work(
        service,
        monkeypatch,
        (
            ("missing", "missing@example.test", CREDENTIAL),
            ("legacy_correct_credential", "legacy@example.test", CREDENTIAL),
            ("no_verifier", "bare@example.test", CREDENTIAL),
            ("wrong_credential", EMAIL, "wrong credential"),
        ),
    )

    # The same operation on every path, not merely the same total cost.
    assert issued == dict.fromkeys(issued, [DEFAULT_KDF])
