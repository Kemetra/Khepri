"""Durable commercial identity: accounts and credential verification (`RCA-001` slice 1).

Covers FR-001 (durable account), FR-002 (verifier stored only as a salted hash), FR-004
(uniform, content-free refusals), and A-1 (one identity per email address).

**Account lifecycle is deliberately NOT in this slice.** Disablement sits at the
intersection of three requirements this slice does not implement — `KHEPRI-DEC-015`'s
24-month retention horizon and opaque tombstone, `FR-008`'s session revocation, and
`FR-013`'s final-owner guard — and implementing it without them produced a disabled account
that stranded its organization and retained its login identity indefinitely. It gets its own
slice, with a design first (#149). `Account.verifier` is already optional and
`khepri.rca.credentials` already owns derivation, so that slice needs no migration and no new
home for destruction.

Records here follow the two-door rule decided in #151: see `records.py`.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING

from khepri.rca.credentials import DEFAULT_KDF, DUMMY_SALT, Verifier, hash_credential
from khepri.rca.errors import AUTHENTICATION_FAILURE, AuthenticationFailed
from khepri.rca.records import Sealed, register_sealed, through_door

if TYPE_CHECKING:
    from khepri.rca.stores import AccountStore


@register_sealed
@dataclass(frozen=True, slots=True)
class Account(Sealed):
    account_id: str
    email: str
    # Optional as a whole, never by halves. KHEPRI-DEC-015 retains the credential verifier only
    # "while the account is enabled" and requires immediate, non-recoverable destruction on
    # disablement or replacement. Holding salt/digest/kdf as one optional value means
    # destruction is a single assignment and a partially-destroyed verifier is unrepresentable.
    # Disablement itself is #149; the shape it needs is here, so it needs no migration.
    verifier: Verifier | None

    @property
    def has_verifier(self) -> bool:
        return self.verifier is not None

    @classmethod
    def create(cls, email: str, credential: str) -> Account:
        """Establish a durable identity with a freshly derived verifier (FR-001, FR-002).

        Takes the credential, not a verifier: there is no parameter through which
        caller-supplied digest material can become a new account's stored verifier.
        """
        # EVERYTHING is computed before the door opens, not just the expensive part. A door
        # authorizes the whole thread while it is open, so any caller-reachable code running
        # inside it can construct any sealed record. `canonical_email` calls `.strip()` and
        # `.lower()` on its argument, and a `str` subclass overriding either runs attacker code
        # — verified: an overridden `strip` built an `IsolationScope` carrying a chosen
        # `owner_id` from inside this door, and it passed `assert_sealed`.
        #
        # The rule this enforces: a door's body contains the constructor call and nothing else.
        account_id = f"acc_{secrets.token_urlsafe(18)}"
        canonical = canonical_email(email)
        verifier = Verifier.derive(credential)
        with through_door():
            return cls(
                account_id=account_id,
                email=canonical,
                verifier=verifier,
            )

    @classmethod
    def _from_storage(cls, account_id: str, email: str, verifier: Verifier | None) -> Account:
        """Rebuild an account from stored columns, preserving them verbatim."""
        with through_door():
            return cls(account_id=account_id, email=email, verifier=verifier)


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


def _is_verifiable(account: Account | None) -> bool:
    """True only for a record this slice can verify: present, complete, at the default factor."""
    return (
        account is not None
        and account.verifier is not None
        and account.verifier.kdf == DEFAULT_KDF
    )


def _verifiable_salt(account: Account | None) -> bytes:
    """The record's salt, or a fixed dummy so an unverifiable record costs the same."""
    if _is_verifiable(account):
        assert account is not None and account.verifier is not None
        return account.verifier.salt
    return DUMMY_SALT


def _verifiable_digest(account: Account | None) -> bytes | None:
    """The digest to compare against, or None when the record cannot be verified here."""
    if _is_verifiable(account):
        assert account is not None and account.verifier is not None
        return account.verifier.digest
    return None


class AccountService:
    def __init__(self, store: AccountStore) -> None:
        self._store = store

    def create_account(self, email: str, credential: str) -> Account:
        account = Account.create(email, credential)
        if not self._store.add_account(account):
            raise AuthenticationFailed(AUTHENTICATION_FAILURE)
        return account

    def authenticate(self, email: str, credential: str) -> Account:
        """Verify a credential with exactly one scrypt call at `DEFAULT_KDF`, on every path.

        Missing account, verifier-less row, wrong credential, success — all four perform the
        identical operation, so none is distinguishable from another by cost (FR-004).

        **This slice supports exactly one work factor**, and that is what makes the property
        hold rather than merely be approximated. Three earlier attempts to support
        per-record factors all leaked: padding the nominal `n*r*p` shortfall ignored that
        scrypt is memory-hard (two calls at `n=2**14` versus one at `n=2**15` measured
        within 0.4% on one CPU and 0.14s versus 0.23s on another); padding a full default
        cost overshot to 1.49x; verifying at the stored factor plus one default hash still
        cost about 1.5x. Each was a workaround for the real gap — a legacy record can only
        be made uniform by re-hashing it to the current default on successful login, and
        that needs a write path.

        So `KdfParams` is stored per record but only `DEFAULT_KDF` is ever used to verify.
        A record at any other factor is refused, uniformly, rather than verified cheaply.
        The upgrade path lands with the write path in the lifecycle slice (#149).
        """
        account = self._store.get_account_by_email(canonical_email(email))
        expected = _verifiable_digest(account)
        candidate = hash_credential(credential, _verifiable_salt(account), DEFAULT_KDF)
        if expected is None or not hmac.compare_digest(candidate, expected):
            self._reject()
        assert account is not None  # a digest was recovered, so the account exists
        return account

    @staticmethod
    def _reject() -> None:
        raise AuthenticationFailed(AUTHENTICATION_FAILURE)
