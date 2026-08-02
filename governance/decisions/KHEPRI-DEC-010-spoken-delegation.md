# KHEPRI-DEC-010: Spoken delegation to a named non-human authority

## Context

The owner has asked four times, in increasingly plain terms, for the ability to delegate approval
by saying `authorize` or `delegate` in a working session, and finally: "i bored of this". That is a
requirement, not a preference, and this decision treats it as one. `KHEPRI-DEC-009` answered a
narrower question the owner did not ask — pre-authorizing two milestone transitions — and is
withdrawn by the same package that carries this decision.

The friction is now measured rather than asserted. Seven structured packages have been approved,
recording seventeen artifact transitions, and every one of them required the owner to leave the
work, read a digest, and compose a sentence in a browser. On 2026-08-02 alone that happened twice.
The cost is not the sentence; it is the context switch, and it lands at the moment work is ready to
proceed.

One finding from this session reframes what a new model must do. The automation's GitHub
credential authenticates as `Kemetra`, user id 206601658 — the same account that authored every
approval comment on issue 43, including the owner's `APP-008` approval. Both `Kemetra` and
`ahmed-shaaban-94` are present in the machine's credential store. `required_signatures` is `false`
on the default branch and local commit signing is inoperative, so nothing in the repository is
cryptographically attributable to any person.

The consequence is uncomfortable and belongs in the record: under the current model the repository
cannot distinguish an approval the owner typed from one the automation could have typed. No claim
is made that any existing approval was fabricated; the defect is unverifiability, not forgery. But
it means the present model does not deliver the guarantee its ceremony implies. A model that
records machine approvals *as machine approvals* is therefore more honest than the status quo, not
less — which is the central argument of this decision.

What must not be built is machine approval wearing the owner's name. That is the one form of this
change that degrades the record, because it would make a false statement about who acted, in an
artifact whose entire purpose is to answer that question.

## Decision

Spoken delegation is adopted on the following terms.

**1. A non-human authority is named.** `governance/registries/authorities.yaml` gains an authority
with identifier `KHEPRI-AGENT`, a role of `delegate`, and an explicit `human: false` field. Every
authority record gains `human`, set `true` for existing entries. A delegate is an authority for the
purposes of Article II and is never a substitute for the human authority.

**2. Article II is amended.** Its second sentence becomes:

> Only a named, active authority can approve an artifact, and only a named, active **human**
> authority can approve entry into or exit from the reserved set defined in Article VIII.
> Automation validates and reports; it grants approval only as a named delegate, only within a
> recorded delegation, and never under a human authority's identifier.

Article V is unchanged: a passing gate remains not-approval, and a delegate's approval is an
approval by a named authority rather than by a gate.

**3. Attribution is mandatory and non-negotiable.** An approval performed under delegation records
`approved_by: KHEPRI-AGENT`. It never records the human's identifier. The registry entry it
materializes records the same. A reader can therefore separate, forever and by inspection, what the
owner approved from what his automation approved. Any implementation that allows a delegated
approval to carry a human identifier is defective and must fail closed.

**4. The trigger is a spoken instruction.** When the human authority says `authorize`, `delegate`,
or an unambiguous equivalent in a working session, the delegate writes a delegation record under
`governance/delegations/` capturing the verbatim instruction, the date, the session identifier, the
scope granted, and the expiry. The record is committed with the work it authorizes.

**5. A delegation record is an attestation, not proof.** It is the delegate's sworn account of an
instruction that exists only in a session transcript. The repository cannot verify it. Approving
this decision is the owner's acceptance of that attestation as sufficient. This is stated plainly
because a trust decision recorded ambiguously is worse than one recorded honestly, and because the
owner is entitled to know exactly what he is trading.

**6. Default scope is the session; standing grants are explicit.** A bare `authorize` grants the
delegate approval authority for the work in progress in that session, expiring when the session
ends. A standing grant requires the owner to say so — "delegate until revoked" or equivalent — and
expires 90 days after it is recorded unless renewed by a further instruction. For a standing grant
the owner is encouraged, and not required, to post one durable comment naming the delegation record
so that the grant has an attributable trace independent of the delegate.

**7. The reserved set, which no delegation may reach.** A delegate may never approve: any change to
`governance/CONSTITUTION.md`; any change to `governance/registries/authorities.yaml`, including its
own record, role, or `active` flag; any delegation record, including its own creation, scope
extension, or renewal; or the acceptance of any decision that alters this reserved set. The reason
is bootstrap containment: an authority that can widen its own authority is unbounded regardless of
how narrowly it begins. Everything outside this set is delegable, including decision acceptance,
family and specification transitions, authority-ending transitions, and initial approvals.

**8. Revocation is immediate and unilateral.** The human authority revokes by saying so, by
deleting or expiring the delegation record, or by setting `active: false` on the delegate. Clause 7
forbids the delegate from resisting any of these. Revocation does not invalidate transitions
already recorded; it stops further ones.

**9. The validator fails closed.** It rejects a delegated approval that names a human identifier,
falls outside the delegation's recorded scope, relies on an absent, malformed, expired, or revoked
delegation record, or touches the reserved set. Ambiguity blocks progress.

## Consequences

The owner pays one written, digest-bound approval for this decision and then stops paying per
package. A delegation regime cannot authorize itself into existence, so this specific approval
cannot be delegated; that is a property of bootstrapping, not a ceremony this decision could remove.

The guarantee the repository offers changes shape rather than weakening uniformly. It gives up "a
human personally approved every transition", which this session showed it could not actually
verify. It gains "every transition names the authority that approved it, and human and machine
approvals are permanently distinguishable" — which it can verify, because clause 3 is machine
enforced. For the reserved set the old guarantee is kept in full.

The residual risk is concentrated and worth naming. A delegate that fabricates a delegation record
can approve anything outside the reserved set, and the repository cannot detect it. The mitigations
are that the reserved set contains the powers needed to escalate, that every delegated approval is
visibly attributed and therefore auditable after the fact, and that revocation is immediate. The
mitigation that does not exist is prevention. An owner unwilling to accept that should reject this
decision and instead pursue attributable evidence — signed commits with a key the automation does
not hold — which this decision does not do and does not obstruct.

Restoring the owner's signing key remains outstanding and becomes more valuable under this
decision, not less: it is the only mechanism that would let the owner's own approvals be
distinguished from a delegate impersonating him, and the reserved set is exactly where that matters.

`KHEPRI-DEC-009` is withdrawn as `rejected` by the package carrying this decision. It proposed a
narrower instrument for a question the owner did not ask, and its standing-authorization mechanism
would have recorded milestone approvals under the human's identifier, which clause 3 forbids.

Follow-up obligations, none performed here: the constitutional amendment to version 1.1.0; the
`human` field and the `KHEPRI-AGENT` record in the authorities registry; a specification defining
the delegation record schema and the validator's obligations; and the validator implementation,
which must fail closed on every clause 9 condition. Until all of them exist and are approved, no
delegation is operative and the current model stands unchanged.
