# KHEPRI-DEC-009: Standing authorization for specification milestone transitions

## Context

Seven structured approval packages have been approved, `APP-002` through `APP-008`. Each required
the named authority to read a manifest digest and write a digest-bound sentence to a durable
location before the transition it carries could be recorded. `APP-001` predates the mechanism: it
is unstructured bootstrap evidence carrying no manifest digest, permitted by the validator as the
sole exception by name. On 2026-08-02 the pattern cost a measurable delay: the implementation of `FND-002`
merged at 15:30 UTC, the approval sentence for `APP-008` was posted at 15:52 UTC, and the
transition was recorded after that. Nothing failed. Work serialized on one human act whose
content was mechanical.

The friction is not the typing. It is that the act must occur in a specific window — after a
package's digest exists, before the transition can be recorded — so every milestone stalls until
the authority is at a keyboard. The owner asked whether that per-milestone act can be replaced by
one standing act.

Two obvious remedies fail on inspection, and both were considered before this one.

Delegating approval capability to automation contradicts Article II in words: "Only a named,
active authority can approve an artifact. Automation validates and reports; it never grants
approval." It would also make the same party author and approver of every package, which is the
substitution each package's own `exclusions` block refuses in a dedicated line. This decision does
not propose it.

A blanket pre-approval covering future work cannot be checked. Approval binds a manifest digest
computed over `schema_version`, `id`, `title`, `owner`, `scope`, `exclusions`, and `artifacts`; a
manifest that does not yet exist has no digest, so a sentence approving it in advance names
nothing and constrains nothing. This is not hypothetical: a comment reading `APPROVED 008` was
posted at 15:34 UTC on 2026-08-02 and was correctly not treated as evidence for `APP-008`,
because it bound no digest. A blanket pre-approval is that comment at larger scale.

What remains is to narrow *which acts* require an individual approval, without weakening what an
approval means. That requires distinguishing two kinds of act the current model treats
identically.

**Entry and exit are judgments.** Moving a decision from `proposed` to `accepted`, a family to
`active`, or a specification from `draft` to `approved` settles what shall be true. Moving any
artifact to `superseded` or `retired` ends authority that other artifacts may depend on. In both
cases the authority is deciding, and no gate can stand in for that.

**Progress along an approved path is a finding of fact.** Moving a specification from `approved`
to `implemented`, or `implemented` to `verified`, asserts that work the authority already
authorized has been done to a standard the authority already set. That is a question the
repository's gates answer more reliably than a human reading a digest: `khepri-gov validate`,
`pytest`, `ruff`, and the CodeScene review inspect the artifact, whereas a human approving a
milestone is largely trusting the same gates at one remove.

One datum cuts against acting on this now, and it belongs here rather than in a footnote. Those
seven packages recorded seventeen artifact transitions between them. Exactly one was a progress
transition: `FND-002` from `approved` to `implemented`, under `APP-008`. The other sixteen were
entry, eleven of them in `APP-002` alone. The class this decision would pre-authorize has occurred
once in the repository's history, so the friction measured above is a sample of one, and the ratio
is worse than the package count suggests. The case for acting is prospective: ten specifications exist,
each admitting up to two progress transitions, against an entry cost already largely paid. If the
roadmap stalls or shrinks, this instrument will have bought little, and rejecting this decision on
those grounds is reasonable.

A second gap surfaced while drafting. The constitution records `Version: 1.0.0` and a ratification
date but documents no amendment procedure. Whatever instrument amends it first will set that
precedent by default rather than by decision. This decision therefore states its own amendment
mechanics explicitly instead of leaving them implied.

## Decision

Standing authorization is adopted for specification milestone transitions only, bounded as
follows. Every clause is a limit; none is guidance.

**1. Constitutional amendment.** This decision authorizes amending the constitution to version
1.1.0 by adding one article, and no other change to any existing article:

> ## VIII. Standing authorization
>
> A named, active authority may approve, as a governed artifact in its own right, a standing
> authorization that pre-authorizes a bounded class of later transitions. A standing
> authorization is approved individually, binds its own manifest digest, enumerates the artifacts
> and transitions it covers, names the verification gates that must pass, states an expiry date,
> and may be revoked at any time by the authority. Automation may record a transition under a
> standing authorization only when the transition, the artifact, and the gates all fall inside
> what the authority enumerated. Automation still never grants approval, and no gate result is
> approval; the approval is the authority's, given in advance and bounded in writing.

Articles II and V are unchanged in text. Article VIII is drawn narrowly so that it explains their
application to a pre-authorized class rather than creating an exception to them: the approving act
remains a named human's, and a passing gate satisfies a condition the human set rather than
substituting for the human.

**2. The instrument is a governed artifact.** A standing authorization is a YAML artifact under
`governance/authorizations/`, with a schema version, an identifier, an owner, an explicit scope, an
expiry date, and a manifest digest. It is approved by the ordinary package mechanism — a named
authority, a digest-bound sentence, a durable `evidence_ref`. It is not self-authorizing.

**3. Permitted scope, exhaustively.** A standing authorization may cover only forward progress
transitions of specifications: `approved` to `implemented`, and `implemented` to `verified`. It
may cover only specification identifiers it names individually; no wildcard, prefix, family, or
"all" form is valid.

**4. Prohibited scope, exhaustively.** A standing authorization may never cover a decision
transition of any kind, a family transition of any kind, any authority-ending transition
(`superseded`, `retired`), any initial approval or entry into the graph, the creation of any new
governed artifact, any change to `governance/CONSTITUTION.md`, any change to
`governance/registries/authorities.yaml`, or any change to a standing authorization including its
own renewal.

**5. Named gates must assert something.** The instrument names the gates whose success is a
precondition. A gate that certifies nothing may not be named. The `benchmark` job is excluded by
name until an approved workload exists: it reports "NOT CERTIFIED", measures no sample, and
succeeds without asserting anything, so naming it would make the instrument weaker than it reads.

**6. Expiry, no automatic renewal.** A standing authorization states an expiry date no more than
90 days after its approval. On expiry it stops covering anything. Renewal is a new instrument with
a new approval; nothing renews by default, and clause 4 forbids automation from renewing one.

**7. Machine-enforced boundary, failing closed.** The validator rejects any package claiming a
standing authorization where the artifact is not enumerated, the transition is outside clause 3,
the instrument is expired, absent, malformed, revoked, or unapproved, or a named gate did not pass.
Ambiguity blocks progress, per Article V.

**8. Traceability is not reduced.** A package materialized under a standing authorization records
the instrument it relied on and the CI run that satisfied the named gates, in addition to the
instrument's own human `evidence_ref`. A reader can still reach a named human and a specific
sentence from any recorded transition.

## Consequences

The gates become load-bearing. Today the authority's reading is the last line of defence before a
state change; afterwards, for the covered class, CI is. That is acceptable only for the class in
clause 3, where the question is whether authorized work was done, and only with clause 5 keeping
non-asserting gates out. It is not acceptable for entry or exit, which is why clause 4 is written
as a closed list rather than a principle.

This decision was drafted by the automation that gains latitude from it. That is a conflict of
interest, and the owner should read clauses 3, 4, and 5 personally even if the rest is skimmed.
The drafting party is not a neutral judge of where its own boundary belongs.

The constitution gains an amendment procedure by precedent: an accepted decision naming the exact
article text, materialized in the same package that carries the decision's transition. A future
decision should state that procedure directly rather than inherit it from this one.

Approval cost is not eliminated. This instrument must itself be approved in writing, so the owner
pays one act now to stop paying per milestone later. If fewer than roughly three progress
transitions follow, the instrument costs more than it saves.

Follow-up obligations, none of which this decision performs: a specification defining the
instrument's schema and the validator's obligations; the validator implementation, which must fail
closed on every clause 7 condition; the constitutional amendment to version 1.1.0; and the first
standing authorization instrument, which must be approved individually.

This decision supersedes nothing. `FND-002` and its implemented lifecycle transitions are
unaffected: standing authorization changes who must act to record a transition, never which
transitions exist or what evidence a package must carry.
