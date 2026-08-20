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
from khepri.rca.invitations import Invitation, InvitationOffer, issue_secret

if TYPE_CHECKING:
    from datetime import datetime

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


__all__ = ["InvitationService"]
