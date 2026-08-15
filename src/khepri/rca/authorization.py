"""The authorization context: what a decision is made from (`R6-02`).

**What this type is.** The resolved answer to "who is acting, where, and as what" — the three
inputs `R6-01` §3 needs to decide any cell of the authorization matrix. `R6-04` builds one per
protected action from live state; a handler receives it and never assembles it.

**The guarantee, stated exactly.** `R6-02`'s task title says the context "cannot be constructed by
handlers". Python offers no private construction, so that claim is not achievable and this module
does not make it. `records.py` enumerates what remains open — `object.__new__` allocates without a
constructor, `object.__setattr__` mutates a frozen instance, and any module may call
`through_door()` itself — and none is closable, because a guard against `object.__setattr__` is
removable by `object.__setattr__`.

What *is* guaranteed: bypassing the door is **deliberate and conspicuous**. Nobody writes
`object.__new__(AuthorizationContext)` while trying to do the right thing, whereas
`dataclasses.replace(context, role=OWNER_ROLE)` is exactly what a careful engineer writes — and
that one is refused. The distinction is the boundary's real content.

This wording is deliberate rather than cautious. `IsolationScope` once carried a docstring claiming
"no layer can construct a scope carrying an untrusted key"; it was untrue when written, and
reviewers trusting it is part of why `#148` ran four review rounds. Docstrings in this package say
"unmistakable", never "unbypassable".

**One door, unlike every other sealed record here.** Creation and reconstruction exist because
records are persisted and read back. An authorization context is never stored — it is derived from
live state for one decision and discarded. A `_from_storage` would be a way to rebuild a *past*
authorization, which is the staleness `FR-008` and `FR-030` exist to forbid.

**No liveness marker, and the absence is the design.** There is no `resolved_at` or `expires_at`,
because a context is valid for exactly one decision. A timestamp invites "is this still fresh?",
and any answer other than "build a new one" is the caching `R6-01` §5 forbids: `FR-030` requires a
membership or role change to take effect for decisions made after it, and a context reused across
two decisions is wrong for the second one exactly when it matters.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rca.organizations import OWNER_ROLE, ROLES
from khepri.rca.records import Sealed, register_sealed, through_door


@register_sealed
@dataclass(frozen=True, slots=True)
class AuthorizationContext(Sealed):
    """One actor's authority for one decision. Never stored, never reused.

    **What is deliberately absent.** No permission list, no action catalog, no resolved verdict:
    this carries the *inputs* to `R6-01`'s matrix, not its output. A context holding "may promote"
    would be an authorization decided somewhere other than the resolver, which is the single
    chokepoint `R6-04` exists to be.

    No account object either — only its identifier. `R3-05` already resolved account status through
    `assert_account_active` before this type is built, so carrying the record would invite a second
    consultation of a value that was live one step earlier and is now a copy.
    """

    #: The one authenticated actor (`FR-003`), as resolved by `R3-05`.
    account_id: str
    #: The organization this decision is about, or `None` when the actor is in none.
    #:
    #: `None` is not an error state: `FR-028` and scenario 18 require an account with no membership
    #: to authenticate successfully, with every organization-scoped cell denied. It is also how a
    #: non-member is represented -- naming an organization the actor holds no role in would give
    #: one matrix cell two spellings.
    organization_id: str | None
    #: The actor's role in `organization_id`, read live, or `None` when there is no organization.
    role: str | None

    @property
    def is_owner(self) -> bool:
        """Whether the owner column of `R6-01` §3.1 applies.

        A property rather than a field, following `Account.can_act`: derived state duplicated into
        a stored boolean is how the two drift apart. There is deliberately no `is_member` — that is
        `organization_id is not None`, and a second spelling of one fact is the same defect.
        """
        return self.role == OWNER_ROLE

    @classmethod
    def create(
        cls, *, account_id: str, organization_id: str | None, role: str | None
    ) -> AuthorizationContext:
        """Build a context from live state. The only door.

        **Validates the pair, not just the parts.** An organization with no role and a role with no
        organization are both refused: a role is a role *in* an organization, and either half alone
        would let a context claim `owner` with nothing to be an owner of, or represent a non-member
        in a second way.

        **Checks the role against `ROLES`.** `R2` left the domain accepting any string as a role,
        safe only because no service took one as input. This one does, so the check moves here
        rather than staying absent — and `R2`'s findings record that the domain's own guard is
        still missing, so this is the first place a forged role would be caught.
        """
        if (organization_id is None) != (role is None):
            raise ValueError("an organization and a role are given together or not at all")
        if role is not None and role not in ROLES:
            raise ValueError("unknown role")
        with through_door():
            return cls(account_id=account_id, organization_id=organization_id, role=role)


__all__ = ["AuthorizationContext"]
