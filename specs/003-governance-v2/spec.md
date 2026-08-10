# Feature Specification: Governance v2 — Gate by Consequence, Not by Artifact Class

**Feature Branch**: `003-governance-v2` (directory only; no git branch created)

**Created**: 2026-08-10

**Status**: Draft — not approved, not implementation-authorized

**Supersedes**: `specs/002-governance-friction-reduction/` — which recorded OOS-001..005 excluding
constitutional amendment on the grounds that the agent may not author its own release. The owner
has since instructed the opposite ("we need a new or diff gov sys… I authorize you"). Article VIII
line 55 is the precedent: a governed instrument may be *created by explicit instruction and
recorded by the delegate*. Drafting is instructed; ratification remains reserved. Per Constitution
VI supersession is explicit and never rewrites prior authority, so 002 stands as written.

**Input**: User description: "you can say that we need a new or diff gov sys / think about it and
do the full speckit chain / i authorize you you take captin chair now"

## Scope boundary

This directory is Spec Kit working material. Constitution I permits one authoritative
representation per governed fact, so **nothing here governs anything**. The governed instruments
this feature proposes are `KHEPRI-DEC-016` (the decision, carrying complete replacement text) and
`APP-023` (the package the owner ratifies). Both are authored at `proposed` with **no approval
block**.

## The diagnosis

Governance was not measured before it was amended. It is now.

**Corrected 2026-08-10 after review.** Two figures in the original table were wrong, and both
overstated the case for this redesign. They are restated below with the erroneous values shown,
because a diagnosis that quietly improves its own evidence is worth less than one that does not.

| Signal | Value | Reading |
|---|---|---|
| Commits touching `governance/` on `main` | **53** *(first stated 72)* | — |
| Commits touching `src/khepri/` on `main` | **57** *(first stated 58)* | **Product commits outnumber governance commits.** The original figures came from `git log --all`, which counts abandoned branches; on the reviewed history the ratio reverses |
| Specifications approved | 13 | — |
| Specifications implemented or verified | 3 | 10 approved specs authorize no shipped behaviour |
| Approval packages | 20 | — |
| Packages that are pure drift repair | **2** — `APP-019`, `APP-021` *(first stated 4)* | `APP-018` (`proposed`→`accepted`) and `APP-020` (`draft`→`approved`) are genuine state advances that would exist without any drift. Only state-preserving renewals count |
| Enforcement code | 2,488 lines | For 20 packages: ~124 lines per package approved |

**What survives the correction.** The claim "governance costs more than the product it governs" does
**not** survive, and is withdrawn. What does survive: 10 of 13 approved specifications authorize no
shipped behaviour, and 2,488 lines of enforcement serve 20 packages. The drift-repair burden is
real but half what was claimed — 2 of 20, not 4 of 20 — which weakens the urgency of W3 without
touching W1, whose value was never the count.

### The three distinct problems, which have three different costs

**Problem 1 — drift remediation cost.** `APP-018` through `APP-021` share one root cause: a
governed document is edited after its approval package was approved, so the digest that package
pinned no longer matches the file.

**Corrected 2026-08-10 — the original claim here was false.** This section first asserted drift was
"a missing pre-commit check." It is not missing. `approval_renewals.py::_document_changed` already
detects it, follows `approval_ref`, and `validate` already runs in CI on every pull request. Tested
directly: appending one line to `governance/families/RCA.md` produces

```
ERROR approval-packages:APP-021: governed document for RCA changed without renewal
```

and the same for `RRA-009`/`APP-019`. Detection is complete and general.

So `APP-018`..`APP-021` are **not** evidence of a missing guardrail. They are evidence the
guardrail works and that its **remedy** is a full approval package. The real question is not *how
is drift detected* but *must every detected drift cost a package*, which is a consequence-gating
question and belongs to W3, not to a hook.

What genuinely remains here is narrower: a rule whose normative force is conditioned on a lifecycle
state silently disarms when that state flips. `APP-021` is the pure case — an exclusion reading
*"while this family remains proposed"* stopped excluding anything the moment the family went
active. **No check detects this**, and it is not the same defect as digest drift: the bytes never
changed, so no digest could have caught it.

**Problem 2 — harness blocks.** Every hard stop in the 2026-08-10 session came from the Claude Code
permission classifier, never from `khepri-gov`. Allowlist fix. No amendment. Carried from spec 002
unchanged.

**Problem 3 — package ceremony per artifact.** This is the only one requiring Article VIII to move.

### Why the current shape produces problem 3 structurally

Today a typo fix in a family charter and an authorization to spend money traverse **identical
machinery**: a package, a manifest digest, an approval block, a registry flip. The gate is keyed to
**artifact class**, and artifact classes do not correlate with consequence.

`DEL-006` demonstrated the failure mode. It enumerated eleven artifact identifiers, so every class
invented afterwards fell outside the grant *by default rather than by decision*. `DEL-007` widened
it to `'*'`. But an allowlist that must be re-widened whenever governance grows is a grant that
decays into an obstacle on a timer — and the next stale enumeration rebuilds the same wall.

### The argument from Constitution I, not against it

Constitution I: *one authoritative representation per governed fact.*

Git already records who committed what, when, and against which tree. Approval packages
**re-represent that same fact** with worse ergonomics. And per `KHEPRI-DEC-010`, they do not buy
better attribution: the automation authenticates through the `Kemetra` credential, so the
repository *"cannot distinguish an approval the owner typed from one the automation could have
typed."* The owner has now declined signing keys, closing the only route that would have changed
this.

So for low-consequence artifacts the package layer is a second representation of a fact git already
holds, purchasing a guarantee the repository cannot honour. **Removing it is a simplification
argument derived from Constitution I, not a relaxation argued against it.**

## The design principle

> **Gate by reversibility and cost, not by artifact class.**

An artifact requires owner ratification when getting it wrong is expensive or hard to undo.
Everything else is agent-approved, CI-validated, git-attributed, and revertible by `git revert`.

### What stays reserved — and why each member earns it

| Reserved | Why |
|---|---|
| Deployment (`KHEPRI-DEC-008`) | Irreversible; exposes real systems |
| Spend, provider selection, runtime choice | Real money; contractual lock-in |
| Privacy, retention, and data-boundary decisions | Constitution VII; affects real people; not revertible once data moves |
| `governance/CONSTITUTION.md` | The amendment mechanism itself |
| The authorities registry | Defines who may act at all |
| Every delegation record, including renewals | **Bootstrap containment — non-negotiable** |
| Any decision altering the reserved set | Closes the loop above |

Privacy is **added** to the reserved set by this feature. It was previously reachable by
delegation, and it fails the reversibility test as hard as deployment does.

### What leaves package-based approval

Family charters and renewals, specifications, non-reserved decisions, reference assessments,
lifecycle transitions that do not authorize product behaviour, and every correction of governance's
own drift. These become: agent commits → CI validates → digest hook proves consistency → merged.

## User scenarios

### Scenario 1 — Long plan, executed uninterrupted (primary)

**Given** a multi-step plan touching only non-reserved artifacts, **when** the agent executes it,
**then** it branches, commits, pushes, opens PRs, merges on green CI, and reports **once** at the
end — with no permission prompts and no approval requests.

### Scenario 2 — Plan reaches a reserved step

**Given** an executing plan whose next step deploys, spends, selects a provider, or moves a
privacy boundary, **when** the agent reaches it, **then** every non-reserved step completes, the
reserved step **halts**, and the report names precisely what remains and under which reserved
category.

### Scenario 3 — Digest drift is caught before it lands

**Given** an edit to a document pinned by a registry entry, **when** the agent attempts to commit
without updating the pin, **then** the pre-commit hook fails with the artifact, the expected
digest, and the actual digest — and no `APP-021`-class repair package is ever needed.

### Scenario 4 — Self-disarming rule is rejected at authoring time

**Given** a governance document containing an exclusion conditioned on a lifecycle state
(*"while this family remains proposed"*), **when** validation runs, **then** it fails and names the
passage, because such a rule silently disarms when the state flips.

### Scenario 5 — Delegation lapse and revocation

**Given** `DEL-007` has expired, **when** a delegated approval is attempted, **then** validation
fails closed naming the record. **And given** the owner revokes at any time by any means, **then**
the agent stops immediately, does not resist or defer, and prior transitions stand as recorded.

## Functional requirements

### Must have — drift enforcement (no amendment)

- **FR-001** ~~Pre-commit digest check~~ **ALREADY SATISFIED.**
  `approval_renewals.py::_document_changed` detects drift against `approval_ref`. Verified by
  direct test on `RCA`/`APP-021` and `RRA-009`/`APP-019`. No work required.
- **FR-002** ~~Same check in CI~~ **ALREADY SATISFIED.** `validate` runs as its own CI job
  (`.github/workflows/governance.yml:29`) on every pull request. No work required.
- **FR-003** Validation MUST reject governance prose whose normative force is conditioned on a
  lifecycle state that can flip beneath it (the `APP-021` defect class). **This is the only
  unbuilt item in W1.** It is distinct from digest drift: the document bytes never change, so no
  digest check can detect it.
- **FR-004** ~~Pin updated in same commit~~ **ALREADY SATISFIED** by the same mechanism as FR-001.

### Must have — harness autonomy (no amendment)

- **FR-005** Commit, push, branch, PR-create, and PR-merge MUST run without per-invocation prompts,
  via a repository-scoped allowlist.
- **FR-006** Read-only verification (`validate`, `delegation-guard`, `document-digest`,
  `approval-digest`, `ruff`, `pytest`) MUST run without prompting.
- **FR-007** Force-push, hard reset of shared refs, history rewriting, and remote branch deletion
  MUST remain gated.
- **FR-008** PR merge MUST require every check green, and MUST stay blocked while any check is
  pending or failing.

### Must have — the amendment (owner ratification required)

- **FR-009** Article VIII's reserved set MUST be restated by consequence: deployment, spend,
  provider and runtime selection, privacy/retention/data-boundary decisions, the constitution, the
  authorities registry, every delegation record, and any decision altering the reserved set.
- **FR-010** Artifacts outside the reserved set MUST NOT require an approval package. Agent commit
  plus green CI is sufficient authority.
- **FR-011** Attribution MUST survive verbatim. `approved_by: KHEPRI-AGENT` never records a human
  identifier; human and delegated acts stay distinguishable by inspection. **Non-negotiable.**
- **FR-012** Bootstrap containment MUST survive verbatim: no delegation reaches the reserved set,
  and no authority may widen its own authority.
- **FR-013** Revocation MUST remain immediate, unilateral, by any means, and non-resistable.
- **FR-014** The ninety-day standing maximum MUST continue to apply to delegation records.
- **FR-015** Existing approved artifacts MUST remain valid. The amendment is prospective; no
  historical package is invalidated or rewritten.

### Should have

- **FR-016** The system SHOULD warn ahead of `DEL-007`'s 2026-11-08 expiry rather than failing
  silently on the day.
- **FR-017** Enforcement code SHOULD shrink materially, since package validation applies to a much
  smaller artifact set. 2,488 lines for a reserved-set-only gate is disproportionate.

### Out of scope

- **OOS-001** Removing attribution, bootstrap containment, revocation, or the 90-day cap
  (FR-011..014 protect these).
- **OOS-002** Any agent approval of the amendment package itself.
- **OOS-003** Retroactive invalidation of existing approvals.
- **OOS-004** Product feature work; `RCA-001` implementation preconditions remain unmet.

## Success criteria

- **SC-001** A plan touching only non-reserved artifacts completes with **zero** prompts and
  **zero** owner approval requests.
- **SC-002** Owner touchpoints drop from **one per artifact** to **reserved-set decisions only**,
  plus one delegation renewal per 90 days.
- **SC-003** A plan reaching a reserved step halts there in **100%** of cases.
- **SC-004** Digest drift is caught before commit in **100%** of cases; **zero** future packages
  exist solely to repair a stale pin.
- **SC-005** Every act remains attributable by inspection to owner or agent, with **no**
  indistinguishable case.
- **SC-006** All delegated authority is revocable in **one** action, effective immediately.
- **SC-007** ~~Governance commits fall below product commits~~ **WITHDRAWN.** The measurement that
  motivated it was wrong: on `main` the ratio is already 53:57 in product's favour, so the
  criterion was satisfied before the feature began and measures nothing. Replaced by **SC-007a**:
  the number of state-preserving renewal packages (`APP-019`, `APP-021` class) over the next 30
  days is **zero**, since `lifecycle-guard` and the existing drift check now catch both causes
  before a package is needed.

## Assumptions

- **A-001** The owner's instruction authorizes *drafting* the amendment, not enacting it. `APP-023`
  carries no approval block.
- **A-002** Attribution is worth keeping even though it cannot prove personhood — it is the one
  guarantee still true, and `KHEPRI-DEC-010` already conceded the rest.
- **A-003** The owner has declined signing keys ("no sign is approved"). The design therefore stops
  producing evidence that is not evidence, rather than pretending otherwise.
- **A-004** `DEL-007` remains in force until 2026-11-08.
- **A-005** Spec Kit is not initialized (`.specify/` absent); this follows the layout of
  `specs/001-rca-001-commercial-identity/`.

## Key entities

- **Reserved set** — restated by consequence rather than artifact class; enforced independently of
  delegation scope.
- **Digest pin** — a registry entry's `document_sha256`; the drift source this feature closes.
- **Approval package** — retained, but only for the reserved set.
- **Delegation record** — the agent's attestation of an owner instruction; not proof of one.
- **Permission allowlist** — Claude Code harness config; not a governed artifact.

## Dependencies

- `KHEPRI-DEC-011` — the amendment precedent this feature follows: an accepted decision carrying
  complete replacement text, approved in a package, then a mechanical transcription.
- `KHEPRI-DEC-010` — attribution and bootstrap containment rationale.
- `DEL-007` (#137), `APP-021` (#138).
- Claude Code settings for FR-005..008; no repository dependency.

## The one thing that remains the owner's

`APP-023` must be authored at `proposed` with **no approval block**. An agent-approved amendment
shrinking the agent's own reserved set is precisely the artifact bootstrap containment exists to
prevent — and it would be indistinguishable, in the record, from an agent that decided this alone.
The owner's ratification is the single act that makes the whole design legitimate rather than
self-granted.
