"""Resolve a presented session to an actor permitted to act (`R3-05`).

**Step 3 of `R3-01` §4, and the first production caller of `assert_account_active`.** That
chokepoint has shipped since `R1` deliberately unused: `FR-008` requires a disabled account's
pre-existing sessions to cease authorizing "with no dependence on session expiry", which is only
satisfiable by consulting account state at every authorization decision. This module is where that
consultation happens.

**What makes the requirement hard to satisfy accidentally.** An implementation that copies
`can_act` into the session row at login type-checks, passes a naive test, and fails `FR-008` — the
copy goes stale the instant the account is disabled, and authority survives until expiry. Nothing
here caches account state; `resolve_actor` reads it per call, by construction.

**Deliberately not here:** live membership and role (step 4, `R6-04`), the cookie (`R3-06`), and
organization switching (`R6-03`). `ResolvedActor` carries identity and permission-to-act-at-all,
never permission-to-act-here.

**Two services rather than one.** Session liveness and account activity are separate questions
owned by separate stores, and `R3-04` proves the session half on its own. Composing them here keeps
`SessionService` unaware of accounts, so a session can still be resolved — for revocation, for the
sweeper — without an account store in hand.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from khepri.rca.accounts import Account
from khepri.rca.errors import AUTHENTICATION_FAILURE, AuthenticationFailed
from khepri.rca.lifecycle import AccountOperationFailed, LifecycleService
from khepri.rca.session_service import SessionService
from khepri.rca.sessions import Session


@dataclass(frozen=True, slots=True)
class ResolvedActor:
    """One authenticated actor, permitted to act at all. Not permitted to act *anywhere*.

    **No role, no membership, no `owner_id`.** `FR-030` requires a membership or role change to
    take effect for decisions made after it without the session ending, so those are resolved live
    per protected action (`R6-04`) rather than carried here. This record is what a handler receives
    *before* asking any organization-scoped question.

    Holds both halves because both are needed downstream: the session carries the active
    organization (`FR-027`), and the account is what membership resolution keys against.
    """

    session: Session
    account: Account

    @property
    def account_id(self) -> str:
        """The one authenticated actor (`FR-003`), read from the account rather than the session.

        The two agree — the session was looked up and the account resolved from its `account_id` —
        so this is a choice about which is authoritative. The account row is, because it is the
        record that was just checked for permission to act.
        """
        return self.account.account_id


class ActorResolver:
    """Session liveness, then account activity, then an actor — or one uniform refusal.

    **Order is load-bearing rather than incidental.** Session state is checked first, so a dead
    session costs no account read: an account lookup attributable to an unauthenticated caller is
    a denial-of-service surface on a path that refuses anyway. `TestOrderOfChecks` asserts it with
    a lifecycle that raises if consulted.
    """

    def __init__(self, sessions: SessionService, lifecycle: LifecycleService) -> None:
        self._sessions = sessions
        self._lifecycle = lifecycle

    def resolve_actor(self, token: str, *, now: datetime) -> ResolvedActor:
        """The actor behind a presented token, or a uniform refusal.

        **Translates `AccountOperationFailed` into `AuthenticationFailed`** rather than letting it
        escape. Both are content-free, but they are different vocabularies: a caller who could
        distinguish "this session is dead" from "this account may not act" would learn account
        state without holding a valid credential, which is what `FR-004` and `FR-022` forbid. The
        session slice's refusal is the one that reaches the boundary.
        """
        session = self._sessions.resolve(token, now=now)
        try:
            account = self._lifecycle.assert_account_active(session.account_id)
        except AccountOperationFailed as refusal:
            raise AuthenticationFailed(AUTHENTICATION_FAILURE) from refusal
        return ResolvedActor(session=session, account=account)


__all__ = ["ActorResolver", "ResolvedActor"]
