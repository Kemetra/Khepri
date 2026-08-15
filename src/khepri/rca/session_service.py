"""Create, resolve, expire, and revoke commercial sessions (`R3-04`).

**This is steps 1 and 2 of `R3-01` §4, and no more.** That section describes a five-step resolution
path per protected action. Here: read the presented identifier, and decide whether the session is
live. Step 3 is `assert_account_active` (`R3-05`), step 4 is live membership and role (`R6-04`), the
cookie is `R3-06`, and organization switching is `R6-03`.

**Why the boundary is drawn there rather than "while we are here".** The chokepoint
`lifecycle.assert_account_active` ships with no production caller, deliberately: being its first
caller is the whole of `R3-05`, and that
slice's tests cover disablement, which this one's do not. Wiring it here would move the `FR-008`
chokepoint into a service that cannot prove it works.

**Expiry is decided here, not swept here.** `R3-01` §4 names RRA as the counter-example: its expiry
predicate is repeated at four call sites because `get_session` does not filter on expiry, so every
caller carries the obligation and one of them will eventually forget. `resolve` is the single
predicate for commercial sessions. Deleting expired rows is `R3-07`; an expired row that still
exists is already inert because nothing but `resolve` reads one.

**Every refusal is one refusal.** `FR-004` and `FR-022` require an absent, unknown, expired, and
revoked session to be indistinguishable, so all four raise `AuthenticationFailed` with
`AUTHENTICATION_FAILURE`. A caller able to tell "expired" from "never existed" could enumerate valid
identifiers one probe at a time.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from khepri.rca.errors import AUTHENTICATION_FAILURE, AuthenticationFailed
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.sessions import Session, hash_session_id


def _require_aware(moment: datetime) -> datetime:
    """Refuse a naive instant at the boundary rather than deep inside a comparison.

    SQLite drops `tzinfo`, so `SqlSessionStore` normalizes stored timestamps to UTC on read. A
    naive `now` would then raise `TypeError` from inside `is_expired_at` — the one decision the
    column exists to make — with a message naming neither the caller nor the cause. Failing closed
    here makes it a caller error, stated once.
    """
    if moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None:
        raise ValueError("a session moment must be timezone-aware")
    return moment


class SessionService:
    """The commercial session lifecycle: create, resolve, expire, revoke (`R3-04`).

    **Holds no account store, and that absence is load-bearing.** See the module docstring: the
    account-activity chokepoint belongs to `R3-05`. This service answers only "does this identifier
    name a live session", which is a question about the session table alone.

    `lifetime` is fixed per service rather than per call. `R3-01` §9 settled a single absolute
    horizon with no sliding renewal, so the answer to "when does this session end" is decided once,
    at issuance, and never moves.
    """

    def __init__(self, sessions: SqlSessionStore, *, lifetime: timedelta) -> None:
        self._sessions = sessions
        self._lifetime = lifetime

    def create(self, account_id: str, *, now: datetime) -> str:
        """Issue a session for one account and return its raw token, exactly once.

        **Returns the token, not the record.** The raw secret belongs in the cookie (`R3-06`) and
        nowhere else; the record it names does not contain it. Returning only the token means a
        caller cannot accidentally persist the secret, because it never receives an object holding
        both. `Session.issue` pairs them internally and this method unpairs them in the safe
        direction.
        """
        issued = Session.issue(account_id, now=_require_aware(now), lifetime=self._lifetime)
        if not self._sessions.add_session(issued.session):
            raise AuthenticationFailed(AUTHENTICATION_FAILURE)
        return issued.token

    def resolve(self, token: str, *, now: datetime) -> Session:
        """The session behind a presented token, or a uniform refusal.

        **Hashes before looking up**, so the stored form is never a usable credential: a database
        disclosure hands over hashes, and a hash presented as a token hashes again into nothing.
        That is what makes `R3-01` §9's hashing-at-rest decision worth having.

        Returns the record and nothing derived from it. A live session says only that this actor
        presented a valid identifier — `FR-008` and `FR-030` require account status, membership, and
        role to be read live per request, and none of them may be memoized here.
        """
        moment = _require_aware(now)
        session = self._sessions.get_session(hash_session_id(token))
        if session is None or not session.is_live_at(moment):
            raise AuthenticationFailed(AUTHENTICATION_FAILURE)
        return session

    def revoke(self, token: str, *, now: datetime) -> Session:
        """End one session immediately — logout, and `R5-05`'s per-session case.

        Refuses an already-revoked session rather than re-dating it, matching `Session.revoked`:
        `revoked_at` is when authority actually ended, and moving it would misreport that.

        **Does not consult expiry.** Revoking an expired session is a no-op in effect but not in
        record, and refusing it would leak the distinction `resolve` is careful to hide.
        """
        moment = _require_aware(now)
        session = self._sessions.get_session(hash_session_id(token))
        if session is None or session.is_revoked:
            raise AuthenticationFailed(AUTHENTICATION_FAILURE)
        revoked = session.revoked(now=moment)
        if not self._sessions.save_session(revoked):
            raise AuthenticationFailed(AUTHENTICATION_FAILURE)
        return revoked

    def point_at_organization(self, session: Session, organization_id: str | None) -> Session:
        """Persist a session's active organization (`FR-029`'s second clause).

        **Takes an already-resolved session and authorizes nothing.** Whether the actor may be in
        that organization is a membership question this service cannot answer -- it holds no
        organization store, deliberately (`R3-05`, `R3-08`). `R6-03`'s `OrganizationSwitcher`
        makes that decision and calls this to record it.

        **A narrow verb rather than a general `save_session`.** Exposing "write this record" would
        let any caller persist an arbitrary session, including one with a revoked-at cleared or an
        expiry moved. This writes one field's worth of intent and nothing else.
        """
        pointed = session.switched_to(organization_id)
        if not self._sessions.save_session(pointed):
            raise AuthenticationFailed(AUTHENTICATION_FAILURE)
        return pointed

    def revoke_all(self, account_id: str, *, now: datetime) -> int:
        """Revoke every live session for one account (`FR-007`, `FR-008`).

        Returns the number of sessions actually ended, which is zero for an account holding none.
        That is a truthful count rather than a refusal: nothing to revoke is not a failure, and
        raising would tell a caller that the account has no live sessions.

        The store does this in one statement, so a session issued between a read and a write cannot
        slip through.
        """
        return self._sessions.revoke_all_for_account(account_id, now=_require_aware(now))

    def link_identity(
        self, provider: str, provider_subject: str, account_id: str, *, now: datetime
    ) -> bool:
        """Link a verified provider subject to one account (`KHEPRI-DEC-018` §7).

        **Takes an already-verified subject.** Verifying a provider assertion is the seam's job
        (`R3-10`) and the adapter's (`R3-11`); this records the result. Reports False for an
        already-linked subject rather than re-pointing it, because re-pointing a link is account
        takeover.
        """
        return self._sessions.link_external_identity(
            provider, provider_subject, account_id, now=_require_aware(now)
        )

    def account_for_identity(self, provider: str, provider_subject: str) -> str | None:
        """Which account a provider subject names, by local lookup and no provider call.

        `R3-09` §2.1 depends on this being local: the composed path verifies an assertion once and
        then resolves the actor from Khepri's own table, so a provider outage cannot make an
        already-authenticated request unresolvable.
        """
        return self._sessions.account_for_external_identity(provider, provider_subject)

    def unlink_identity(self, provider: str, provider_subject: str) -> bool:
        """Remove a link, leaving every other record standing (`R3-09` §5).

        The account, its memberships, its audit events, and the final-owner invariant survive. The
        account becomes unauthenticatable through that provider until relinked, which does not
        change `can_act` — so an owner remains an effective owner and no `FR-013` reasoning applies.

        **Does not revoke the account's sessions**, and that is deliberate rather than an omission.
        Unlinking removes a way to authenticate in future; it does not disable the account, and
        `FR-008` ties session revocation to disablement. Ending live sessions here would over-apply,
        logging out an account that may still hold a password credential.
        """
        return self._sessions.unlink_external_identity(provider, provider_subject)


__all__ = ["SessionService"]
