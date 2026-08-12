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
    shortfall_schedule,
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
    """Total scrypt work each rejection path performs, keyed by label.

    Counts work instead of measuring wall-clock: "every path spends the same" is a
    deterministic property, and timing it is flaky on shared CI runners where neighbouring
    jobs contend for CPU. A wall-clock version of this measured 1.001x locally and 1.37x in
    CI — a false failure, since the work performed was identical both times.
    """
    work: dict[str, list[int]] = {}
    real_hash = accounts_module.hash_credential
    current = ""

    def _recording(credential: str, salt: bytes, kdf: KdfParams = DEFAULT_KDF) -> bytes:
        work[current].append(kdf.n * kdf.r * kdf.p)
        return real_hash(credential, salt, kdf)

    monkeypatch.setattr(accounts_module, "hash_credential", _recording)
    for label, email, credential in cases:
        current = label
        work[current] = []
        with pytest.raises(AuthenticationFailed):
            service.authenticate(email, credential)
    return {label: sum(costs) for label, costs in work.items()}


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

    assert len(set(totals.values())) == 1, f"rejection cost is not uniform: {totals}"
    assert totals["missing"] == DEFAULT_KDF.n * DEFAULT_KDF.r * DEFAULT_KDF.p


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


@pytest.mark.parametrize("stored_n", [2**14, 2**13, 2**12, 2**11])
def test_padding_covers_the_full_deficit_for_every_older_work_factor(stored_n: int) -> None:
    """A single rounded step only pays a power-of-two share of the deficit.

    At a stored n=2**13 against a default of 2**15 that covered 75% of the required work,
    and at 2**12 only 62% — an existence oracle in exactly the range this padding exists to
    close. Decomposing the deficit into one hash per set bit covers it exactly.
    """
    stored = KdfParams(n=stored_n)
    stored_cost = stored.n * stored.r * stored.p
    padding_cost = sum(step.n * step.r * step.p for step in shortfall_schedule(stored))
    default_cost = DEFAULT_KDF.n * DEFAULT_KDF.r * DEFAULT_KDF.p

    assert stored_cost + padding_cost == default_cost


def test_a_current_factor_record_needs_no_padding() -> None:
    assert shortfall_schedule(DEFAULT_KDF) == ()
    assert shortfall_schedule(KdfParams(n=DEFAULT_KDF.n * 2)) == ()


def test_hash_credential_is_deterministic_for_a_fixed_salt() -> None:
    salt = b"0123456789abcdef"
    first = hash_credential(CREDENTIAL, salt, KdfParams(n=2**14))
    second = hash_credential(CREDENTIAL, salt, KdfParams(n=2**14))
    assert first == second
    assert hash_credential("other", salt, KdfParams(n=2**14)) != first


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

    assert len(set(totals.values())) == 1, f"rejection cost is not uniform: {totals}"
    assert totals["missing"] == DEFAULT_KDF.n * DEFAULT_KDF.r * DEFAULT_KDF.p
