"""Selecting and switching the active organization (`R6-03`).

**`FR-029` has two clauses, and the second makes this a persistence operation.** A switch must
succeed only into an organization where the actor holds a *current* membership, **and** must "take
effect for every subsequent authorization decision in that session". A service that computes an
updated record and returns it satisfies the first clause and fails the second — and passes every
test that inspects only the return value. So each verb here writes through `save_session`.

**Its own module rather than a method on `SessionService`.** That service deliberately holds no
account or organization store: `R3-05` put the account chokepoint in `ActorResolver` for the same
reason, and `R3-08` asserts the absence. Keeping it store-free is what lets a session be resolved
for revocation or sweeping without an organization store in hand. Switching needs one, so it
composes the two rather than widening either.

**Membership is read from the store, never from the session.** The session already carries an
`active_organization_id`, and consulting it to decide whether a switch is permitted would be
circular — the session would authorize its own continued authority, and an actor revoked from an
organization would remain in it. `FR-030` requires a revocation to take effect for decisions made
after it without the session ending.

**Session liveness is checked before the organization**, so `Session.switched_to`'s `ValueError`
for a revoked session is unreachable from here. A `ValueError` escaping where
`AuthenticationFailed` is expected would break the uniform refusal `R3-04` and `R3-05` both hold.
"""

from __future__ import annotations

from datetime import datetime

from khepri.rca.errors import SCOPE_FAILURE, ScopeAccessDenied
from khepri.rca.session_service import SessionService
from khepri.rca.sessions import Session
from khepri.rca.stores import OrganizationStore


class OrganizationSwitcher:
    """Points a live session at one organization the actor currently belongs to, or at none.

    **Not the authorization resolver.** `R6-04` decides what an actor may *do* in the active
    organization, per protected action. This decides only which organization the session names,
    which is `FR-027`'s at-most-one and `FR-029`'s membership requirement.
    """

    def __init__(self, sessions: SessionService, organizations: OrganizationStore) -> None:
        self._sessions = sessions
        self._organizations = organizations

    def switch(self, token: str, organization_id: str, *, now: datetime) -> Session:
        """Make one organization active for this session (`FR-027`, `FR-029`).

        **Refuses a non-member and an unknown organization identically.** `get_membership` returns
        `None` for both, and the refusal does not distinguish them: a caller able to tell "no such
        organization" from "you are not in it" enumerates organizations one probe at a time, which
        `FR-004` and `FR-022` forbid.

        The membership lookup is the authorization. `Session.switched_to` deliberately validates
        nothing — its docstring records that a record cannot read a store, and that putting the
        check in two places is the drift `_apply_membership_change` was built to avoid.
        """
        session = self._sessions.resolve(token, now=now)
        if self._organizations.get_membership(organization_id, session.account_id) is None:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        return self._sessions.point_at_organization(session, organization_id)

    def clear(self, token: str, *, now: datetime) -> Session:
        """Leave the session authenticated but active in no organization (`FR-028`, `FR-030`).

        **No membership check, because there is no organization to be a member of.** This is how
        `FR-030` is satisfied without ending a session: an actor whose active-organization
        membership was revoked must cease to authorize *there* while remaining a valid session.

        Clearing an already-clear session is not an error. `FR-028` makes "authenticated, in no
        organization" a normal state rather than a failure, so refusing would make scenario 18's
        actor unable to perform a no-op.
        """
        session = self._sessions.resolve(token, now=now)
        return self._sessions.point_at_organization(session, None)


__all__ = ["OrganizationSwitcher"]
