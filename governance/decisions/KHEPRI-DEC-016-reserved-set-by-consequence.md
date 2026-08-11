# KHEPRI-DEC-016: Reserved set by consequence

> Retired by KHEPRI-DEC-017. This document records the former delegation boundary and is historical.

## Context

Article VIII defines the reserved set by artifact class: this constitution, the authorities
registry, delegation records, and decisions altering the reserved set. Everything else is
delegable, and `DEL-007` delegates all of it.

That boundary does not track what a mistake costs. A family charter typo and an authorization to
move customer data across a boundary are both outside the reserved set, so both may be approved by
`KHEPRI-AGENT` under a standing delegation. The first is revertible by `git revert`. The second is
not revertible at all once the data has moved, and Article VII commits Khepri to collecting,
retaining, and exposing the least data necessary.

This decision moves one category into the reserved set and gives the reserved set a
machine-checkable representation. It does not remove anything from it.

**What this decision does not do, and why.** The specification that motivated it
(`specs/003-governance-v2/`) proposed a second change: that artifacts outside the reserved set
require no approval package at all, with an agent commit and a green CI run as sufficient
authority. That proposal is **withdrawn on constitutional grounds and is not part of this
decision.**

Article II's third sentence enumerates automation's modes exhaustively — "Automation validates and
reports; it grants approval only as a named delegate, only within a recorded delegation, and never
under a human authority's identifier." Two `only`s, and no third mode in which an artifact
transitions with no approval act. The proposal required inventing one. The defence considered was
that a passing check would be evidence rather than approver, but that does not survive Article V:
where no approval act occurs, the transition's sole warrant is the passing check, which is exactly
what "Silence or a passing technical check is not approval" rejects.

The prohibition is not the only reason to decline it. A delegated approval is a five-line block
written in the same pass as the artifact it approves, and under `DEL-007` it costs the human
authority nothing — `APP-021` and `APP-022` were both approved without the owner's involvement.
Removing it would have purchased no reduction in owner effort, at the price of the repository's
ability to state who authorized a transition.

## Decision

**1. Version.** `governance/CONSTITUTION.md` becomes version `1.2.0` and its `Amended:` line becomes
`Amended: 2026-08-10 (KHEPRI-DEC-016)`. No other header changes.

**2. Article VIII's third paragraph is replaced in full by:**

> The reserved set is this constitution; the authorities registry, including a delegate's own
> record, role, and active flag; every delegation record, including its creation, extension, and
> renewal; the acceptance of any decision that alters the reserved set; and any artifact whose
> recorded consequence is deployment, spending, provider or runtime selection, or a change to a
> privacy, retention, or data boundary. An artifact's consequence is recorded in its authoritative
> registry entry and is not inferred from its prose. An artifact that records no consequence is
> reserved. No delegation reaches the reserved set, and an authority that could widen its own
> authority is unbounded however narrowly it begins.

**3. Article VIII's remaining paragraphs are unchanged in full**, and are restated here so the
transcription is mechanical and nothing is left to judgment:

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
> A delegation granted without an explicit duration covers only the session in which it was given.
> A standing delegation expires no later than ninety days after it is recorded and does not renew
> itself. The human authority may revoke any delegation at any time by any means, with immediate
> effect, and a delegate may not resist, defer, or condition a revocation. Revocation does not
> invalidate transitions already recorded; it stops further ones.
>
> Validation fails closed on every condition in this article.

Attribution, bootstrap containment, the ninety-day standing maximum, and immediate unilateral
revocation are therefore preserved word for word. This decision narrows what a delegate may reach;
it relaxes nothing.

**4. Articles I through VII are unchanged**, as are the lifecycle vocabularies and the closing
paragraph. Article II in particular keeps its full force, and this decision is bounded by it:
automation continues to grant approval only as a named delegate within a recorded delegation.

**5. The decision and specification registries gain a `consequence` field.** Every entry in
`governance/registries/decisions.yaml` and `governance/registries/specifications.yaml` records
`consequence`, drawn from this closed vocabulary:

> ```
> deployment          provisioning, runtime exposure, or release to real systems
> spend               financial commitment, subscription, or contractual obligation
> provider-selection  choice of vendor, runtime, or hosting arrangement
> privacy             a privacy, retention, or data-boundary change under Article VII
> none                no consequence in the categories above
> ```

A missing, empty, or unrecognised value is reserved, not exempt. Validation fails closed on it,
which is Article V applied to this field specifically: an unclassified artifact is an unknown
state, and unknown states block progress.

**6. Classification is not a judgment call the delegate makes alone.** Recording `consequence:
none` on an artifact that in fact authorizes deployment, spend, provider selection, or a privacy
change is a defect of the same class as a self-disarming exclusion, and the human authority may
correct any entry at any time. Where classification is genuinely ambiguous, the ambiguity is
resolved toward the reserved category, per Article V.

**7. Prospective only.** No approval already recorded is invalidated, reopened, or rewritten by
this decision. Existing artifacts are classified in the same commit that materialises this
amendment so that validation does not break on merge, and that classification records what each
artifact already authorizes rather than changing it.

## Consequences

The delegate's reach narrows. `DEL-007` remains a wildcard grant, but the wildcard now stops at any
artifact recording a consequence, so a standing delegation can no longer approve a retention change
or a provider selection merely because no one enumerated them. The category most likely to matter
is `privacy`: it was delegable before this decision, it is not after, and it is the category whose
mistakes cannot be reverted at all.

The cost is 28 classifications — 15 decisions and 13 specifications — plus a field on every future
entry. That is real work, and it is the price of a boundary that a validator can check rather than
one a reader must infer. Article VIII's prose already named deployment and spend as consequences
that matter; nothing in the tooling could act on that until now, because `is_reserved_file()`
classifies paths and no code classified consequence.

A fail-closed default on a missing field means this amendment cannot be materialised
half-way. Either every existing entry carries a consequence when the constitution changes, or
`validate` fails on the merge commit. That coupling is deliberate: an amendment whose enforcement
lags its text is the inversion `KHEPRI-DEC-011` warned against, and the alternative — defaulting
unclassified artifacts to `none` — would make the fail-closed rule decorative.

This decision does not reduce the number of approvals the human authority performs. It was drafted
in response to an instruction to reduce that number, and it does not deliver that, because the
mechanism which would have — removing the approval act for low-consequence artifacts — is forbidden
by Article II and was withdrawn. What actually reduced owner effort was `DEL-007`, which is already
in force. This decision moves in the opposite direction on one narrow category, and does so
deliberately.
