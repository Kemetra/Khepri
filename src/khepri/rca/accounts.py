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
from datetime import datetime
from typing import TYPE_CHECKING

from khepri.rca.credentials import DEFAULT_KDF, DUMMY_SALT, Verifier, hash_credential
from khepri.rca.errors import AUTHENTICATION_FAILURE, AuthenticationFailed
from khepri.rca.records import Sealed, through_door

if TYPE_CHECKING:
    from khepri.rca.stores import AccountStore


@dataclass(frozen=True, slots=True)
class Account(Sealed):
    account_id: str
    # Nullable so the post-horizon tombstone is representable. KHEPRI-DEC-015 §2b purges the
    # login identity 24 months after disablement, leaving "an opaque account identifier and the
    # disablement timestamp -- no email address, no credential verifier, no profile data". A
    # non-nullable email would make that state unrepresentable and would hold the A-1 uniqueness
    # reservation forever, which §2b explicitly releases.
    email: str | None
    # Optional as a whole, never by halves. KHEPRI-DEC-015 retains the credential verifier only
    # "while the account is enabled" and requires immediate, non-recoverable destruction on
    # disablement or replacement. Holding salt/digest/kdf as one optional value means
    # destruction is a single assignment and a partially-destroyed verifier is unrepresentable.
    verifier: Verifier | None
    # NULL means enabled. The state is derived from this column and never duplicated into a
    # boolean, because two representations of one fact can disagree -- and the horizon in §2b is
    # computed from this timestamp, so it has to exist regardless.
    disabled_at: datetime | None

    @property
    def has_verifier(self) -> bool:
        return self.verifier is not None

    @property
    def is_enabled(self) -> bool:
        return self.disabled_at is None

    @property
    def is_purged(self) -> bool:
        """True once §2b has minimized this record to a tombstone."""
        return self.email is None

    @classmethod
    def create(cls, email: str, credential: str) -> Account:
        """Establish a durable identity with a freshly derived verifier (FR-001, FR-002).

        Takes the credential, not a verifier: there is no parameter through which
        caller-supplied digest material can become a new account's stored verifier.
        """
        # Derive before opening this record's door rather than inside it, so the window in
        # which construction is authorized on this thread stays one constructor call wide.
        verifier = Verifier.derive(credential)
        with through_door():
            return cls(
                account_id=f"acc_{secrets.token_urlsafe(18)}",
                email=canonical_email(email),
                verifier=verifier,
                disabled_at=None,
            )

    @classmethod
    def _from_storage(
        cls,
        account_id: str,
        email: str | None,
        verifier: Verifier | None,
        disabled_at: datetime | None,
    ) -> Account:
        """Rebuild an account from stored columns, preserving them verbatim."""
        with through_door():
            return cls(
                account_id=account_id,
                email=email,
                verifier=verifier,
                disabled_at=disabled_at,
            )

    def disabled(self, *, now: datetime) -> Account:
        """The disabled form of this account: verifier destroyed, timestamp recorded.

        A door, not a field assignment. `dataclasses.replace(account, verifier=None)` is the
        obvious way to write this and is refused by #151's construction rule — deliberately, because
        that call was the shape of the forgery that slice was opened to close. Going through a
        door also means destruction and the timestamp are set together, so a disabled account with
        a surviving verifier is not expressible.

        Destroying the verifier here is what KHEPRI-DEC-015 requires ("immediate,
        non-recoverable" on disablement). Re-enablement therefore cannot restore the old
        credential; see `enabled`.
        """
        with through_door():
            return type(self)(
                account_id=self.account_id,
                email=self.email,
                verifier=None,
                disabled_at=now,
            )

    def enabled(self) -> Account:
        """The re-enabled form of this account.

        KHEPRI-DEC-015 §2b justifies the 24-month horizon partly so an account "can be re-enabled
        after a dispute, an erroneous disablement, or a lapsed commercial relationship", so a
        horizon justified by re-enablement while offering no way to re-enable would be incoherent.

        The verifier stays destroyed — §5 gives it no path back — so a re-enabled account fails
        authentication uniformly until a new credential is set.
        """
        with through_door():
            return type(self)(
                account_id=self.account_id,
                email=self.email,
                verifier=self.verifier,
                disabled_at=None,
            )

    def purged(self) -> Account:
        """The tombstone form: identity fields gone, `account_id` and `disabled_at` retained.

        KHEPRI-DEC-015 §2b, applied 24 months after disablement. The two surviving fields are
        exactly what the decision names, and they exist to keep `FR-014` audit events
        referentially meaningful for the remainder of their own 12-month horizon and to satisfy
        §8 item 5.
        """
        with through_door():
            return type(self)(
                account_id=self.account_id,
                email=None,
                verifier=None,
                disabled_at=self.disabled_at,
            )


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
    """True only for a record this slice can verify: enabled, complete, at the default factor.

    The disabled check belongs here rather than in `authenticate`, and that placement is
    load-bearing for FR-004. Every unverifiable record — missing, verifier-less, off-factor,
    **disabled** — flows through the same dummy-salt path and pays the same single scrypt cost,
    so a disabled account is not distinguishable from a nonexistent one by timing. An early
    `if account.disabled_at is not None: raise` in `authenticate` would satisfy FR-008 while
    reintroducing the enumeration oracle FR-004 forbids: it would skip the hash entirely.

    In practice disablement destroys the verifier (KHEPRI-DEC-015 §5), so a disabled account is
    already unverifiable through `verifier is None`. This check is deliberately redundant with
    that: FR-008 must not depend on destruction having succeeded.
    """
    return (
        account is not None
        and account.is_enabled
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
