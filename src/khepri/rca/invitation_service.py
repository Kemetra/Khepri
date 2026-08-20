"""Owner-authorized issuance and revocation of invitations (`R4-04`).

**Scope.** Two operations and nothing else. The `FR-020` and purge cascades are `R4-06`, redemption
and its uniform-failure path are `R4-05`, and the uniform-failure matrix is `R4-07`. This module
decides no authorization: see below.

## Authorization lives outside this service

`R6-01` §5's critical rule and `R6-04`'s placement put the check in the gate rather than in the
verbs, so `issue` takes `actor_account_id` for **attribution** and performs no role check of its
own. `FR-015` names *invite* as an owner capability; the matrix rows in `R6-01` §3.1 and their
classes in `tests/test_rca001_authorization_matrix.py` are what make the gate the authorized route,
and a second check here would be a second authority over one fact.

Note the asymmetry with `R4-05`'s redemption, which will carry a `ResolvedActor`: `issue` and
`revoke` are reached **through** the gate, which has already resolved the actor, so
`actor_account_id` and `organization_id` here are values the gate supplies rather than a caller's
claims. A redeemer holds no membership and so has no gate, which is why that verb must derive its
account from a presented session instead.

## The two requirements that shape the signatures

**`organization_id` is the resolved scope, never a second caller-supplied value.** `issue` creates
a row rather than looking one up, so it carries no identifier-grants-authority hazard of its own --
but a service taking a resolved scope *and* a separate organization parameter would let an owner of
`A` issue into `B`. `FR-024` requires a request whose actor and whose named scope disagree to fail
closed, and two independently-supplied organization values are that disagreement made expressible.
There is one organization value in each signature for that reason.

**Revocation is scoped by `(organization_id, invitation_id)`.** `R4-01` §4.1 derives this from
`FR-023` -- "possession of an object identifier MUST confer no authority" -- and it is the same
defect class as a caller-supplied `account_id`, in a different verb: there the caller names the
account, here the caller names the object. The composite predicate lives in
`SqlInvitationStore.delete_open_invitation`, as one statement rather than a read and a write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from khepri.rca.accounts import canonical_email
from khepri.rca.errors import INVITATION_FAILURE, InvitationOperationFailed
from khepri.rca.invitations import (
    Invitation,
    InvitationOffer,
    issue_secret,
    parse_token,
    verify_secret,
)
from khepri.rca.organizations import Membership, MembershipEvent

if TYPE_CHECKING:
    from datetime import datetime

    from khepri.rca.actor_resolution import ResolvedActor
    from khepri.rca.stores import InvitationStore


class InvitationService:
    """Issue and revoke organization invitations.

    Holds only an `InvitationStore`. No `AccountStore` and no `OrganizationStore`: verifying that
    the actor may act, and that the organization exists, is the gate's work and is already done by
    the time either method is called. Taking those stores would invite a second liveness check here
    -- a copy of a fact that was live one step earlier, which is what `AuthorizationContext`'s
    docstring refuses for the same reason.
    """

    def __init__(self, store: InvitationStore) -> None:
        self._store = store

    def issue(self, offer: InvitationOffer, *, expires_at: datetime, now: datetime) -> str:
        """Mint an invitation and return its token. The token is returned **once**.

        Only the `Verifier`'s salt and digest persist -- `FR-016`'s "persisted only as a strong
        salted hash" -- so the secret cannot be recovered afterwards and the caller must transmit
        it now or reissue.

        `target_identity` is canonicalized **at rest**, not at comparison time. `R4-01` §4: an
        address stored as typed makes every later predicate miss the row -- §6.1.1's addressee
        check, §7's recipient cascade, §7.1's purge cascade -- and §7.1's miss is the worst, because
        a skipped purge leaves a stale invitation redeemable at a **released** address, the identity
        transfer that section exists to prevent. `SqlInvitationStore.add_invitation` canonicalizes
        too: a store caller bypassing this service would otherwise reintroduce the gap, the same
        argument §3's `CHECK` constraints rest on.

        `expires_at` is a parameter with no default. `FR-016` requires an explicit expiry and does
        not fix a lifetime, so a constant here would put a product decision in the domain.

        `intended_role` is validated by `Invitation.create`, which is where a caller-supplied role
        first enters the codebase; it is not re-checked here.

        **The parameters are grouped rather than listed flat**, matching `Invitation.create` and
        `ca7c572`'s fix for the same shape in `khepri.rra`: `InvitationOffer` already carries
        exactly these four values, and its own docstring says `R4-04` supplies `issued_by` "from
        what the gate resolved rather than from a caller's claim". `R4-01` §4 states the signature
        flat as prose shorthand; spelling it out cost 7 parameters and CodeScene scored the file
        9.69 on Excess Number of Function Arguments. Reusing the existing grouping is what §4's own
        argument about `create` recommends, and it keeps one organization value in the signature --
        the `FR-024` property that a caller cannot name a scope beside the one the gate resolved.
        """
        secret = issue_secret()
        invitation = Invitation.create(
            InvitationOffer(
                organization_id=offer.organization_id,
                intended_role=offer.intended_role,
                target_identity=canonical_email(offer.target_identity),
                issued_by=offer.issued_by,
            ),
            secret=secret,
            expires_at=expires_at,
            issued_at=now,
        )
        if not self._store.add_invitation(invitation):
            # The identifier is 18 CSPRNG bytes, so a collision is not the realistic cause -- a
            # storage refusal is. Failing closed rather than retrying: a silent retry would hide
            # whichever condition actually refused the write.
            raise InvitationOperationFailed(INVITATION_FAILURE)
        return secret.token

    def revoke(
        self,
        organization_id: str,
        invitation_id: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> None:
        """Revoke an open invitation reachable in this scope, or refuse uniformly.

        **One refusal for four causes** -- the invitation does not exist, it is already revoked, it
        is already redeemed, it has expired, or it belongs to another organization. `FR-025`: "a
        denial for an object the actor may not reach MUST be indistinguishable from a denial for an
        object that does not exist. Denials MUST NOT disclose existence, ownership, or the identity
        of another organization." So this never reports which occurred and never names the owning
        organization, following `resolve_scope` (`isolation.py:30-40`), where three distinct causes
        raise the identical `ScopeAccessDenied`.

        **No dummy-KDF padding, unlike `R4-05`'s redemption path.** Revocation compares no secret,
        and the composite statement is the same single statement whether it misses because the
        invitation does not exist or because it belongs to another organization -- so the two causes
        are timing-equivalent by construction rather than by added work. `R4-01` §4.1 records this
        so that "every uniform refusal needs a dummy hash" is not generalized from `R4-05`.

        `actor_account_id` is accepted and deliberately unused. `R4-01` §4.1 fixes the signature
        with it, and it is kept rather than trimmed for one reason: revocation *deletes* the row, so
        there is no record left to attribute, and a verb the gate calls should take the actor the
        gate resolved rather than reach for it later. An earlier version of this docstring justified
        it by saying `R4-06`'s cascade needs it; that is not supportable -- §7 puts the cascade in
        `revoke_membership`'s write callback, not in this verb -- so the claim is withdrawn rather
        than left for a reviewer to falsify.
        """
        del actor_account_id
        if not self._store.delete_open_invitation(organization_id, invitation_id, now=now):
            raise InvitationOperationFailed(INVITATION_FAILURE)


    def redeem(self, token: str, actor: ResolvedActor, *, now: datetime) -> None:
        """Accept an invitation, creating exactly one membership. Or refuse, uniformly.

        **The account comes from the presented session and is never named by the caller.** §6's
        correction: a caller-supplied `account_id` lets any holder of a stolen or guessed token pass
        someone else's identifier and have the membership created for them -- or for an account they
        hold no session for at all. `FR-019` requires an *authenticated* account, and a parameter is
        not authentication. `resolve_actor` (`actor_resolution.py:76`) takes only a token and a
        clock for the same reason.

        **Every refusal is one refusal.** A malformed token, an unknown invitation, a wrong secret,
        an expired or revoked invitation, an addressee mismatch, a tombstone actor, a dead session,
        a disabled account, an already-redeemed token, and an existing membership all raise
        `InvitationOperationFailed(INVITATION_FAILURE)`. §5 and `FR-025`: a caller able to
        distinguish these would learn whether a token was valid, whether an invitation exists, and
        who it was addressed to, one probe at a time.

        **The order of checks, and why the liveness pair comes last.** The secret is verified first,
        on the destroy-on-touch read path, so an expired verifier's bytes are gone whatever happens
        next. Then the addressee. Then -- immediately before the write, after the store has taken
        the account lock -- account liveness and session liveness. §6.1 requires the session check
        "**after** every other lock is acquired, immediately before the write, so nothing remains to
        wait on": a predicate evaluated before a lock wait cannot speak for the state after it.

        **`Session.is_live_at`, not `is_revoked`.** Revoking a session does not touch
        `rca_accounts`, so `can_act` still passes and the account check does not cover it; and
        expiry is the clock rather than a write, so no lock reaches it at all. The repo holds both
        conditions in one predicate (`sessions.py:113`) and reaching past it to the revocation half
        is the drift `accounts.py:68` warns about.

        **A residual, stated rather than left to be found.** `is_live_at` runs at some instant
        the transaction and the commit happens later; a session live at the check can expire before
        the commit, and no predicate evaluated before a wait speaks for the state after it. §8.5
        records the owner reading `FR-019` as the last check and accepting that. Unlike the account
        race this one is not closable: disablement is a write and two writers can be made to
        contend, but expiry has no writer to serialize with.
        """
        try:
            invitation_id, secret = parse_token(token)
        except ValueError as malformed:
            raise InvitationOperationFailed(INVITATION_FAILURE) from malformed

        # The destroy-on-touch read: an expired invitation's verifier is destroyed here, in the
        # transaction that reads it, before this method refuses.
        invitation = self._store.find_for_redemption(invitation_id, now=now)
        if invitation is None or not verify_secret(secret, invitation.verifier):
            raise InvitationOperationFailed(INVITATION_FAILURE)

        # §6.1.1: the addressee is who may redeem, which is what makes a forwarded token useless.
        # A tombstone actor has no address and cannot be shown to be the addressee, so it fails
        # closed rather than being reconstructed.
        address = actor.account.email
        if address is None or canonical_email(address) != canonical_email(
            invitation.target_identity
        ):
            raise InvitationOperationFailed(INVITATION_FAILURE)

        # The invitation's own openness is re-checked in the store's conditional statement; this
        # is the cheap pre-check. Session liveness is **not** checked here on purpose: the actor's
        # `session` is a snapshot that cannot see a revocation landing after it was read, so the
        # store re-reads the row inside the transaction that writes. Checking the snapshot here as
        # well would look like the guard and would not be one.
        if not invitation.is_open_at(now):
            raise InvitationOperationFailed(INVITATION_FAILURE)

        membership = Membership.create(
            invitation.organization_id, actor.account_id, invitation.intended_role
        )
        event = MembershipEvent.created(
            invitation.organization_id,
            actor.account_id,
            invitation.intended_role,
            # The redeemer is the actor: they accepted, and `FR-014` attributes a change to whoever
            # made it. `prior_role IS NULL` and `next_role = intended_role` carry the kind, so §6.2
            # is right that no new event kind or column is needed.
            actor_account_id=actor.account_id,
            now=now,
        )
        if not self._store.redeem_into_membership(
            invitation_id,
            account_id=actor.account_id,
            organization_id=invitation.organization_id,
            role=invitation.intended_role,
            now=now,
            membership=membership,
            event=event,
            session_id_hash=actor.session.session_id_hash,
        ):
            raise InvitationOperationFailed(INVITATION_FAILURE)


__all__ = ["InvitationService"]
