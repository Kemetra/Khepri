# KHEPRI-DEC-011: Constitution 1.1.0, delegation articles

## Context

`KHEPRI-DEC-010` is accepted. It adopted spoken delegation and stated the amended text of the
constitution's second article, but it referred to a reserved set "defined in Article VIII" without
writing Article VIII. Applying `KHEPRI-DEC-010` therefore requires composing constitutional text
that no approved artifact contains, which is not a mechanical act and must not be performed as one.

This decision closes that gap. It states the complete final text of both articles so that amending
`governance/CONSTITUTION.md` afterwards is a transcription with nothing left to judgment, and it
states the authorities registry change in the same way.

The constitution documents no amendment procedure. `KHEPRI-DEC-010` recorded that gap; this
decision is the first instrument to amend the constitution and therefore sets the precedent in fact.
It states the procedure it follows so the precedent is deliberate: an accepted decision containing
the complete replacement text, approved by the named human authority in a package, followed by a
transcription that changes nothing the decision did not state.

## Decision

**1. Version.** `governance/CONSTITUTION.md` becomes version `1.1.0` and gains a line reading
`Amended: 2026-08-02 (KHEPRI-DEC-011)` beneath its ratification line. No other header changes.

**2. Article II is replaced in full by:**

> ## II. Named human authority
>
> Every governed artifact has a known human owner. Only a named, active authority can approve an
> artifact, and only a named, active human authority can approve a change within the reserved set
> defined in Article VIII. Automation validates and reports; it grants approval only as a named
> delegate, only within a recorded delegation, and never under a human authority's identifier.

**3. A new Article VIII is added after Article VII, before the lifecycle vocabularies, reading in
full:**

> ## VIII. Delegation
>
> A named, active human authority may delegate approval to a named, active non-human authority. A
> delegation is created by an explicit instruction from the human authority and recorded by the
> delegate as a delegation record stating the instruction verbatim, the date it was given, the
> session in which it was given, the scope granted, and an expiry date. A delegation record is the
> delegate's attestation of an instruction; it is not proof of one, and the authority's approval of
> this article is its acceptance of that attestation as sufficient.
>
> An approval performed under a delegation records the delegate's identifier as its approver, in
> the approval package and in every registry entry it materialises. It never records a human
> authority's identifier. Human and delegated approvals remain distinguishable by inspection.
>
> The reserved set is this constitution; the authorities registry, including a delegate's own
> record, role, and active flag; every delegation record, including its creation, extension, and
> renewal; and the acceptance of any decision that alters the reserved set. No delegation reaches
> the reserved set, and an authority that could widen its own authority is unbounded however
> narrowly it begins.
>
> A delegation granted without an explicit duration covers only the session in which it was given.
> A standing delegation expires no later than ninety days after it is recorded and does not renew
> itself. The human authority may revoke any delegation at any time by any means, with immediate
> effect, and a delegate may not resist, defer, or condition a revocation. Revocation does not
> invalidate transitions already recorded; it stops further ones.
>
> Validation fails closed on every condition in this article.

**4. Articles I, III, IV, V, VI, and VII are unchanged**, as are the lifecycle vocabularies and the
closing paragraph. Article V in particular keeps its full force: a passing technical check remains
not an approval, and a delegate's approval is an approval by a named authority rather than by a
gate.

**5. The authorities registry gains an explicit humanity field.** Every record in
`governance/registries/authorities.yaml` gains `human`, set `true` for `AHMED-SHAABAN`. A record is
added:

> ```yaml
>   - id: KHEPRI-AGENT
>     name: Khepri governance delegate
>     roles:
>       - delegate
>     active: true
>     human: false
>     document: governance/authorities/khepri-agent.md
> ```

Its document states what the delegate is, which credential it acts through, and that it is
software rather than a person, so that a reader encountering `approved_by: KHEPRI-AGENT` can
establish that fact from the repository alone.

**6. Registration is not authorisation.** Adding the delegate to the registry grants it nothing by
itself. It may approve only within a delegation record that does not yet exist and cannot exist
until `FND-003` is implemented and a human instruction creates one.

## Consequences

After the transcription this decision authorises, the repository will state in its constitution that
a non-human authority may hold delegated approval. That is a material change to the document's
central promise, and it is deliberate: `KHEPRI-DEC-010` established that the repository could not
already distinguish a human approval from one its automation could have produced, and mandatory
attribution under Article VIII repairs that for every future act while narrowing what a delegate may
touch.

The amendment is inert until `FND-003` is implemented. Article VIII describes delegation records and
attribution that no validator can yet enforce, so between this decision's materialisation and that
implementation the constitution will describe a capability the tooling does not provide. That
interval is a real inconsistency rather than a formality, and it is accepted because the alternative
orderings are worse: implementing enforcement for an unamended constitution would build machinery the
governing document forbids.

`KHEPRI-AGENT` is the identifier this session's automation will use. It authenticates through the
`Kemetra` GitHub credential, which is also the human authority's account, so the registry entry
records what the credential cannot: that acts attributed to the delegate were performed by software.
Restoring the human authority's signing key remains the only mechanism that would make the
distinction cryptographic rather than declared, and it stays outstanding.

This decision supersedes nothing and rejects nothing. It performs no transcription itself: the
constitution, the authorities registry, and the delegate's document are unchanged by the package
that carries this decision, and each requires the materialisation this decision authorises.
