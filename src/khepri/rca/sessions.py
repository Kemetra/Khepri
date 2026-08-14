"""Commercial authentication sessions: the domain and its state vocabulary (`R3-02`).

**Scope.** Domain types only. Persistence is `R3-03`, the service is `R3-04`, the cookie boundary is
`R3-06`. Nothing here touches a database or a request.

Records follow the two-door rule in `records.py`.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from khepri.rca.records import Sealed, register_sealed, through_door

#: `RRA` mints `ses_` for its beta sessions and `own_` for isolation keys, and `R3-01` §2.1 records
#: that `rra/sessions.py` and `rca/organizations.py` already produce byte-identical `own_` values
#: distinguishable only by which table holds them. A distinct prefix keeps commercial sessions
#: legible in evidence rather than reproducing that ambiguity one layer up.
SESSION_ID_PREFIX = "cse_"

#: 18 bytes of CSPRNG output, matching every other opaque identifier in this package.
_TOKEN_BYTES = 18


def hash_session_id(token: str) -> str:
    """The stored form of a session identifier.

    **SHA-256, not the scrypt KDF `credentials.py` uses, and the difference is deliberate.** A KDF's
    cost exists to make guessing a *low-entropy* secret expensive. A session token is 18 bytes of
    CSPRNG output, so there is nothing to guess -- and `credentials.DEFAULT_KDF` allocates 64 MiB
    per call, which on a per-request authorization path would be a denial-of-service surface rather
    than a protection. A single hash of a high-entropy value is the right primitive.

    Returns hex rather than bytes so the stored column is a plain string, matching `account_id` and
    the other opaque identifiers.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class StoredSession:
    """The columns a persisted session consists of, for rehydration through `_from_storage`.

    Not a `Sealed` record and not a domain type -- it carries no invariant and exists so the
    rehydration door takes one named value instead of six positional ones. `R3-03` builds it from a
    row; nothing else should construct it.
    """

    session_id_hash: str
    account_id: str
    active_organization_id: str | None
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """A new session and the one-time raw token that reaches it.

    The two travel together exactly once, at issuance. `token` belongs in the cookie and nowhere
    else; `session` is what gets stored. Pairing them in one return value means a caller cannot
    accidentally store the raw token, because the record it stores does not contain it.
    """

    session: Session
    token: str


@register_sealed
@dataclass(frozen=True, slots=True)
class Session(Sealed):
    """One authenticated actor's session. Carries identity, never authority.

    **What is deliberately absent, and this is the load-bearing part.** No role, no membership, no
    `owner_id`, no `can_act` flag, no retail content. `FR-030` requires a membership or role change
    to take effect for decisions made *after* it without the session ending, and `FR-008` requires
    disablement to stop authorization without waiting for expiry. Any of those values cached here
    goes stale exactly when it matters most. `R3-05` resolves them live on every protected action.

    `KHEPRI-DEC-018` §4 extends the same rule to external identity: where a provider authenticates
    the actor, no provider organization, role, or permission claim may be copied into this record.
    """

    #: The stored hash, never the raw token. Owner decision 1 (`R3-01` §9).
    session_id_hash: str
    #: The one authenticated actor (`FR-003`).
    account_id: str
    #: Nullable because `FR-028` requires an account with no membership to authenticate. One
    #: nullable column cannot hold two organizations, which is how `FR-027` is satisfied
    #: structurally rather than by validation.
    active_organization_id: str | None
    created_at: datetime
    #: A single absolute instant. Owner decision 2 (`R3-01` §9): no sliding renewal, so the answer
    #: to "when does this session end" never moves.
    expires_at: datetime
    #: NULL means live. Derived state is never duplicated into a boolean, following `Account`.
    revoked_at: datetime | None

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def is_expired_at(self, moment: datetime) -> bool:
        """True once the absolute horizon has elapsed. The expiry instant itself counts as expired,
        matching `MembershipEvent.is_purgeable_at`: a horizon that excluded its own boundary would
        leave a one-instant window where a session is neither live nor expired."""
        return self.expires_at <= moment

    def is_live_at(self, moment: datetime) -> bool:
        """Neither expired nor revoked.

        **Not sufficient for authorization on its own.** A live session says only that this actor
        presented a valid identifier. `FR-008` and `FR-030` require account status, membership, and
        role to be read live per request, which is `R3-05`'s chokepoint. Nothing here may be
        memoized into the record.
        """
        return not self.is_expired_at(moment) and not self.is_revoked

    def switched_to(self, organization_id: str | None) -> Session:
        """Point this session at one organization, or at none (`FR-027`, `FR-029`, `FR-030`).

        **This does not check that the actor holds a membership, and that is correct rather than an
        omission.** `FR-029` requires a switch to succeed only into a current membership, and that
        answer lives in the store and must be read live. A record cannot read a store, so validating
        here would require handing this type a store and would put the check in two places once
        `R3-04` also performs it -- the same drift `_apply_membership_change` was built to avoid in
        `R2`. The service authorizes the switch; the record only holds the result.

        Passing `None` clears it, which is how `FR-030` is satisfied without ending the session: a
        session whose active-organization membership was revoked must cease to authorize *there*
        while remaining a valid session, which `FR-030` states explicitly.
        """
        if self.is_revoked:
            raise ValueError("a revoked session cannot switch organization")
        with through_door():
            return Session(
                session_id_hash=self.session_id_hash,
                account_id=self.account_id,
                active_organization_id=organization_id,
                created_at=self.created_at,
                expires_at=self.expires_at,
                revoked_at=self.revoked_at,
            )

    def revoked(self, *, now: datetime) -> Session:
        """End this session immediately, without waiting for expiry (`FR-008`).

        Refuses a second revocation rather than silently re-dating the first. `revoked_at` is when
        authority actually ended, and moving it would misreport that -- the same reason
        `Membership.promoted` refuses a no-op instead of returning an equivalent record.
        """
        if self.is_revoked:
            raise ValueError("session is already revoked")
        with through_door():
            return Session(
                session_id_hash=self.session_id_hash,
                account_id=self.account_id,
                active_organization_id=self.active_organization_id,
                created_at=self.created_at,
                expires_at=self.expires_at,
                revoked_at=now,
            )

    @classmethod
    def issue(
        cls, account_id: str, *, now: datetime, lifetime: timedelta
    ) -> IssuedSession:
        """Mint a session and its one-time token.

        The token is allocated before the door opens, following `Account.create`: a door authorizes
        the whole thread while open, so its body holds the constructor call alone.
        """
        token = f"{SESSION_ID_PREFIX}{secrets.token_urlsafe(_TOKEN_BYTES)}"
        digest = hash_session_id(token)
        with through_door():
            session = Session(
                session_id_hash=digest,
                account_id=account_id,
                active_organization_id=None,
                created_at=now,
                expires_at=now + lifetime,
                revoked_at=None,
            )
        return IssuedSession(session=session, token=token)

    @classmethod
    def _from_storage(cls, row: StoredSession) -> Session:
        """Rebuild a stored row exactly, minting nothing.

        The second door in `records.py`'s two-door rule. It must preserve `session_id_hash` rather
        than deriving a new one -- a door that re-minted would orphan every stored session while
        looking correct in isolation.

        **Takes one grouped value rather than six parameters.** `Account._from_storage` has four and
        reads fine; six is where the signature stops being safe, because `created_at` and
        `expires_at` are both `datetime` and transposing them type-checks while producing a session
        that expired before it began. A named field cannot be passed in the wrong position.
        CodeScene flagged the arity, and the fix it prompted is the better interface.
        """
        with through_door():
            return Session(
                session_id_hash=row.session_id_hash,
                account_id=row.account_id,
                active_organization_id=row.active_organization_id,
                created_at=row.created_at,
                expires_at=row.expires_at,
                revoked_at=row.revoked_at,
            )


__all__ = [
    "SESSION_ID_PREFIX",
    "IssuedSession",
    "Session",
    "StoredSession",
    "hash_session_id",
]
