"""Live membership and role resolution at every protected action (`R6-04`).

**Step 4 of `R3-01` §4, and the step `R3-05` deliberately left out.** `actor_resolution.py`
resolves an actor "permitted to act at all, not permitted to act *anywhere*", and its docstring
reserves live membership and role for this module. This is where permission-to-act-*here* is
decided, and it is the only place that decides it.

**Every lookup is live, by construction rather than by discipline.** `R6-01` §5 states the
ordering contract and forbids skipping, caching, or reordering any step. `FR-030` requires a
membership or role change to take effect for decisions made after it *without the session ending*,
so a role read once and reused is wrong exactly when it matters -- the revocation case. Nothing
here holds a membership between calls, and `AuthorizationContext` deliberately carries no
`resolved_at` that would invite reuse.

**The anti-pattern this module exists to prevent, named because it type-checks.** `R3-05` records
that copying `can_act` into the session row passes a naive test and fails `FR-008`. The identical
defect lives one level up: copying `role` into the session at switch time would satisfy every test
that inspects a returned context and would fail `FR-030` the moment an owner is demoted. The role
is read from the organization store per call, never from the session, for the same reason `R6-03`
reads membership from the store when authorizing a switch.

**The organization comes from the session, never from the caller.** `R6-01` §5's critical rule:
"Object identifiers never grant authority. Every object lookup must be scoped from the
authorization result, not trusted from a route parameter." `resolve_scope` takes a bare
`organization_id` and would happily resolve any organization the caller names -- its own membership
check makes that safe today, but it means a handler holding a route parameter can reach a scope
without this resolver ever running. `for_request` closes that by *comparing* a request-named
organization against the session's active one and refusing on mismatch, rather than trusting it.

**Deliberately not here: the account-scoped half of `R6-01` §3.2.** Those six actions turn on
self-versus-another-account, and `AuthorizationContext` carries only the acting `account_id` with
no target. Deciding them would require either a second context shape or a target parameter this
type does not have, which is an `R6-02` change rather than an `R6-04` one. `R6-05`'s exhaustive
matrix therefore covers §3.1 here; §3.2 needs that decision first. Re-enablement in particular is
`R6-01` §6's open question for the owner -- it has no authorized caller in the matrix at all, and
gating it here would make a disabled account permanently unrestorable.

**Deliberately not here: `FR-013`'s final-owner guard.** `R6-01` §4 is explicit that it is an
invariant, not a permission -- it constrains the resulting state regardless of who asks.
`apply_owner_reducing_change` holds it inside the transaction that writes. Re-checking ownership
before calling a membership verb would put one rule in two places, which is the drift `R2` built
that function to avoid. An owner demoting themselves as the final owner is `PERMIT` here and still
fails downstream with `FINAL_OWNER_FAILURE`; scenario 17 requires exactly that sequence.

**Deliberately not here: a second scope check.** `R6-01` §6 resolves this: `isolation.py` already
refuses a non-member uniformly, and `R6-04` treats that existing refusal as the enforcement rather
than adding a duplicate.
"""

from __future__ import annotations

from datetime import datetime

from khepri.rca.actor_resolution import ActorResolver, ResolvedActor
from khepri.rca.authorization import AuthorizationContext
from khepri.rca.errors import SCOPE_FAILURE, ScopeAccessDenied
from khepri.rca.stores import OrganizationStore


class AuthorizationResolver:
    """The canonical resolver: one actor, one organization, one live role, per action.

    **Composes `ActorResolver` rather than reimplementing it.** Session liveness and account
    activity are steps 2 and 3 and are already a chokepoint; widening this class to repeat them
    would create the second guard that `R6-03` and `R3-05` both took care not to build. A caller
    reaches step 4 only by passing through steps 2 and 3 first, because the only way in runs them.
    """

    def __init__(self, actors: ActorResolver, organizations: OrganizationStore) -> None:
        self._actors = actors
        self._organizations = organizations

    def resolve(self, token: str, *, now: datetime) -> AuthorizationContext:
        """Build one context from live state, for exactly one decision (`FR-030`).

        **A non-member resolves successfully with no organization.** `FR-028` requires an account
        with no membership to authenticate and be denied every organization-scoped action, so a
        refusal here would be wrong: it would deny the *authentication*, not the action. The
        actor arrives with `organization_id=None`, which `R6-01` §3.3 makes every §3.1 cell `DENY`
        for, and which `R6-02` fixed as the single spelling of "not a member here".

        **A revoked membership resolves the same way**, which is what `FR-030` and scenario 20
        require: the session stays valid and stops authorizing in that organization. The session
        still names the organization; the store no longer records the membership; the store wins.
        """
        actor = self._actors.resolve_actor(token, now=now)
        return self._context_for(actor)

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: datetime
    ) -> AuthorizationContext:
        """Resolve for a request that names an organization, refusing if it is not the active one.

        **The comparison is the point, and it is not the membership check.** A caller who passes
        an organization they *are* a member of but which is not this session's active organization
        is still refused: `FR-027` allows at most one active organization, and honoring a named
        one would make the session's active organization advisory. Two organizations an actor
        belongs to would otherwise both be reachable at once, which is the accumulation `R6-03`
        refused at switch time and would reappear here.

        **Refuses a mismatch and a non-member identically**, with the same content-free
        `ScopeAccessDenied` the switch path uses. A caller able to distinguish "that is not your
        active organization" from "no such organization" enumerates organizations one probe at a
        time, which `FR-004` and `FR-022` forbid -- and `R6-03` closed exactly this oracle on the
        switch path, so re-opening it here would undo merged work.

        Passing no organization is the same question as `resolve`: the session's active
        organization is used, because there is nothing to compare it against.
        """
        context = self.resolve(token, now=now)
        if organization_id is not None and organization_id != context.organization_id:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        return context

    def require_owner(
        self, token: str, *, organization_id: str, now: datetime
    ) -> AuthorizationContext:
        """Resolve, then refuse unless the actor owns the organization they named.

        The three `R6-01` §3.1 owner-only cells -- promote, demote, revoke a membership -- share
        this shape, and expressing it once is what keeps them from drifting apart. It returns the
        context rather than a boolean so the caller cannot ask the question and ignore the answer.

        **The target organization is required here, unlike on `for_request`, and the asymmetry is
        the point.** Every owner-only verb takes an `organization_id` of its own and checks no
        role, so a gate that defaulted to the session's active organization would authorize
        against A while the caller went on to mutate B -- each line reading correctly in
        isolation. Requiring it forces the target to be named *at the gate*, so the organization
        that was authorized is the one in the caller's hand. A default that is safe only when the
        caller remembers to pass the same value twice is not a default worth having.

        **Refuses a member exactly as it refuses a non-member.** `R6-01` §3.1 gives both `DENY`,
        and a distinguishable refusal would tell a member which organizations they are merely a
        member of -- membership state disclosed to a caller who has not been granted it.
        """
        context = self.for_request(token, organization_id=organization_id, now=now)
        if not context.is_owner:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        return context

    def _context_for(self, actor: ResolvedActor) -> AuthorizationContext:
        """Read the role live, and let the store's silence mean "not a member".

        **Reads through `get_membership` rather than any cached or session-carried value.** This
        one call is the whole of `FR-030`'s enforcement: the store is consulted after the change,
        so the change is observed. `R6-03` established the same read for switching, deliberately
        not consulting the session's own `active_organization_id` because that would be circular.

        A session naming an organization the actor no longer belongs to yields `None` here, and
        the context is built with no organization at all rather than with the organization and no
        role -- `AuthorizationContext.create` refuses that pair, and `R6-02` records why: a role
        is a role *in* an organization, and either half alone gives one matrix cell two spellings.
        """
        active = actor.session.active_organization_id
        if active is None:
            return AuthorizationContext.create(
                account_id=actor.account_id, organization_id=None, role=None
            )
        membership = self._organizations.get_membership(active, actor.account_id)
        if membership is None:
            return AuthorizationContext.create(
                account_id=actor.account_id, organization_id=None, role=None
            )
        return AuthorizationContext.create(
            account_id=actor.account_id,
            organization_id=active,
            role=membership.role,
        )


__all__ = ["AuthorizationResolver"]
