# Phase 0B: Charter the Commercial Family (RCA) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draft every governance artifact Phase 0B needs — a decision superseding `KHEPRI-DEC-003`'s beta boundary, a new `RCA` (Retail Commercial Analysis) family charter, a re-scope of `RRA.md`'s exclusions carried as a renewal package, and the registry entries for all of it — so the owner has one reviewable, digest-locked approval package and every phase from 1 onward stops being blocked on a family that excludes commerce.

**Architecture:** This plan produces **documents only**. Every artifact lands in a pre-approval state (`proposed` for the decision, `proposed` for the RCA family) with no `approved_by`, no `approved_at`, no `approval_ref`, and no `superseded_by`. Two independent validator rules make that mandatory rather than stylistic: `lifecycle.py:231` requires a successor decision be `accepted` before `KHEPRI-DEC-003` may name it via `superseded_by`, and `approval_transition_validation.py:206-211` requires each artifact's `approval_ref` equal the ref of the package approving it. A drafting plan has no such package. `khepri-gov validate` must pass at every commit with the new artifacts sitting unapproved, exactly as `KHEPRI-DEC-008`, `KHEPRI-DEC-013`, and (before PR #112) `KHEPRI-DEC-012` sit today.

**Tech Stack:** Markdown governance documents, YAML registries, `khepri-gov` CLI (`validate`, `document-digest`, `approval-digest`). No Python source changes, no tests, no dependencies.

## Global Constraints

- **Change no lifecycle state.** No task in this plan edits a `state:` field, adds `approved_by`/`approved_at`/`approval_ref`, or sets `superseded_by`. Those are the approving package's to write, and only after a named authority approves it. Marking `KHEPRI-DEC-003` as `superseded` here would fail `khepri-gov validate` because its named successor would not yet be `accepted`.
- **Add no `RCA-*` specification entries.** `validator.py:293-303` requires an approved specification's family be `active` and a specification id carry its family prefix. An `RCA-001` placeholder added while `RCA` is `proposed` either fails the family-state check or couples the charter to a spec that Phase 2+ owns. This plan creates zero specifications.
- **`governance/families/RRA.md` is digest-pinned and must not be edited as a plain file.** Verified empirically 2026-08-07: `uv run khepri-gov document-digest governance/families/RRA.md` returns `sha256:8a1235a0d6b9e36a6446a1e1cfd3f7ef5db52ca7d9e0ed23bcffb18eded095d2`, byte-identical to the pin in `governance/approvals/APP-002.yaml:38-41`. Any edit fails validation as `RRA changed without renewal` — the same trap `docs/khepri-commercial-roadmap.md:534-545` records for `KHEPRI-DEC-005`'s stale closing sentence. Task 4 therefore produces a **renewal package** carrying the edit, not a bare diff.
- **A renewal must preserve state.** `approval_renewals.py:140-144` raises `renewal must preserve state` unless `from_state == to_state` (or the pair is a legal lifecycle edge). The `RRA` renewal entry is `from_state: active` → `to_state: active` with `supersedes_approval_ref: governance/approvals/APP-002.yaml`, mirroring `APP-013.yaml`'s renewal of `KHEPRI-DEC-005`.
- **Every digest in a drafted package is a placeholder until computed.** `governance/templates/approval-package.yaml:1-3` states the rule: replace every symbolic zero digest with output from `uv run khepri-gov document-digest PATH` and `uv run khepri-gov approval-digest PACKAGE_PATH`. Task 6 computes them; earlier tasks leave `sha256:0000…` in place deliberately, because a digest computed before the document is final is a digest that pins the wrong bytes.
- **The proposed decision must enumerate every `KHEPRI-DEC-003` control and say whether it survives.** Silently dropping one is the single-authoritative-representation drift Constitution I forbids. `KHEPRI-DEC-003:14-27` lists them; Task 2 accounts for all of them, one line each.
- **The package this plan drafts stays `state: proposed` with no `approval:` block.** Filling in `approved_by: KHEPRI-AGENT` under a delegation is not available: `DEL-005` expired `2026-08-06` (`governance/delegations/DEL-005.yaml`, `expires_at: 2026-08-06`), it never listed any Phase 0B artifact in its `scope.artifacts`, and `APP-015.yaml:18` explicitly excludes "Any amendment of RRA.md, any specification, or any family charter." No live delegation covers this work.
- **Write full governed prose. No placeholders in a governance document.** Unlike the RRA-009 vocabulary plan, there is no bilingual-authorship gap here — governed decision and charter text is the agent's to draft and the owner's to approve.

---

## File Structure

- **Create:** `governance/decisions/KHEPRI-DEC-014-commercial-boundary.md` — the decision superseding `KHEPRI-DEC-003`'s beta boundary. Next free id: `decisions.yaml` ends at `KHEPRI-DEC-013`.
- **Create:** `governance/families/RCA.md` — the Retail Commercial Analysis family charter, `depends_on: [FND, RRA]`.
- **Create:** `governance/approvals/APP-017.yaml` — the atomic approval package covering all four artifacts, including the `RRA` renewal. Next free id: `governance/approvals/` ends at `APP-016.yaml`.
- **Modify:** `governance/registries/decisions.yaml` — append the `KHEPRI-DEC-014` entry at `state: proposed`.
- **Modify:** `governance/registries/families.yaml` — append the `RCA` entry at `state: proposed`.
- **Create:** `docs/platform/proposed-governance/rra-exclusions-rescope.md` — the exact `RRA.md` replacement text the renewal would apply, staged as a reviewable document rather than an unvalidatable edit to a pinned file.

Nothing under `src/` or `tests/` is touched.

---

## Task 1: Reserve the identifiers and confirm the drafting baseline

**Files:**
- Read only: `governance/registries/decisions.yaml`, `governance/registries/families.yaml`, `governance/approvals/`

**Interfaces:**
- Consumes: nothing.
- Produces: three confirmed identifiers used verbatim by every later task — decision id `KHEPRI-DEC-014`, family id `RCA`, package id `APP-017`. If any is already taken, later tasks use the next free one and this task records the substitution.

- [ ] **Step 1: Confirm the next free decision, family, and package identifiers**

Run:
```bash
grep -c "^  - id: KHEPRI-DEC-" governance/registries/decisions.yaml
grep "^  - id:" governance/registries/families.yaml
ls governance/approvals/ | sort | tail -3
```
Expected: 13 decisions (so `KHEPRI-DEC-014` is free); families are exactly `FND` and `RRA` (so `RCA` is free); the last approval is `APP-016.yaml` (so `APP-017` is free).

- [ ] **Step 2: Confirm `FND` and `RRA` are both `active`**

Run: `grep -A1 "^  - id: \(FND\|RRA\)$" governance/registries/families.yaml`
Expected: both show `state: active`. This matters because `approval_transition_validation.py:222-230` refuses to move a family to `active` unless every entry in its `depends_on` is already `active` — so `RCA` depending on `[FND, RRA]` is approvable later only because both already are.

- [ ] **Step 3: Confirm the baseline validates before any edit**

Run: `uv run khepri-gov validate`
Expected: exit 0, no errors. Every later task re-runs this; a failure appearing later is then unambiguously that task's doing.

- [ ] **Step 4: Commit nothing**

This task writes no files. Record the three identifiers in the working notes and proceed. (No commit step: a task that produces no artifact has nothing to commit, and an empty commit would misrepresent the history.)

---

## Task 2: Draft `KHEPRI-DEC-014`, the commercial boundary decision

**Files:**
- Create: `governance/decisions/KHEPRI-DEC-014-commercial-boundary.md`

**Interfaces:**
- Consumes: `KHEPRI-DEC-003`'s seven-part beta boundary (`governance/decisions/KHEPRI-DEC-003-rra-private-beta.md:14-31`) and its four implementation preconditions (`:33-38`); `RRA-001`/`RRA-002` control names as cited in `docs/khepri-commercial-roadmap.md:348-352`.
- Produces: the decision document later referenced by `decisions.yaml`'s `KHEPRI-DEC-014` entry (Task 5) and pinned by `APP-017`'s `document_sha256` (Task 6).

- [ ] **Step 1: Write the decision document**

Create `governance/decisions/KHEPRI-DEC-014-commercial-boundary.md` following the `governance/templates/decision.md` structure (`## Context` / `## Decision` / `## Consequences`) and imitating `KHEPRI-DEC-013`'s level of specificity — it is the closest precedent for a decision that partially supersedes a prior boundary and enumerates exactly what survives:

```markdown
# KHEPRI-DEC-014: Commercial boundary superseding the private-beta scope

## Context

`KHEPRI-DEC-003` is `accepted` and bounds Khepri to an invite-only private beta: a pseudonymous
single-use invitation, no durable customer, seven-day content expiry, and one dataset per
session. `governance/families/RRA.md` excludes, in its own words, "commercial authentication,
user profiles, persistent customer workspaces, organizations, membership roles, billing,
subscriptions, scheduling, and public signup" and "agency portfolios, client switching,
delegated access, work queues, and white labeling."

Every capability a paying customer needs is on that exclusion list. `AGENTS.md` forbids
implementing ahead of an approved specification, and a specification cannot be approved into a
family that excludes its subject, so no billing, signup, or workspace slice is authorizable
today at any level of effort. `docs/khepri-commercial-roadmap.md` records this as the gate on
every phase from 1 onward.

Two reference reviews already surveyed this ground and deferred it — `BATCH-04` (commercial
identity, persistent workspaces, report history) and `BATCH-09` (agency portfolios, delegation,
work queues, white labeling). Both are technical evidence carrying no approval.

### Why a new family rather than editing RRA

Deleting `RRA.md`'s exclusions would leave one family document asserting both "invite-only
pseudonymous beta" and "commercial multi-tenant service." Constitution I requires one
authoritative representation per governed fact, and a family claiming both is two claims in one
document. `FND.md` already shows the correct shape: it excludes "responsibilities of future
product families" and states those boundaries "require separately approved families."

`RRA` is not retired and not superseded. The private beta remains a real, governed product
boundary with approved specifications `RRA-001` through `RRA-009` under it. What changes is that
`RRA` stops being the only family, and its exclusions are re-expressed as family boundaries
rather than as prohibitions on Khepri.

## Decision

### 1. The RCA family is created

Create the proposed `RCA — Retail Commercial Analysis` family, depending on `FND` and `RRA`,
charted in `governance/families/RCA.md`. It owns durable commercial identity, organizations and
membership, persistent customer workspaces, multi-dataset accumulation, pricing and billing,
public signup and onboarding, agency tenancy, and recurring delivery.

It does not own, and its charter excludes, forecasting, customer-authored formulas, and generic
non-retail analysis. Those stay excluded from Khepri entirely rather than moving between
families.

### 2. What the private-beta boundary contributed, and what replaces it

`KHEPRI-DEC-003`'s beta boundary is superseded **in scope only**. Each of its controls is
accounted for below. A control marked *survives* is unchanged and binds `RCA` exactly as it
binds `RRA`; a control marked *replaced* is replaced only by the named successor obligation and
never by silence.

| `KHEPRI-DEC-003` control | Status under RCA |
|---|---|
| "A single-use invitation creates a pseudonymous session and opaque owner ID." | **Replaced.** Durable accounts replace single-use invitations. The opaque owner ID survives as the internal boundary key, so `assert_same_scope` and every isolation test keep working; commercial identity maps *to* it rather than replacing it. |
| "stores invitation secrets only as hashes and collects no password, profile, billing identity, or email owner key" | **Replaced in part.** Hash-only storage of secrets survives and extends to credentials. Collecting a profile, billing identity, and email owner key becomes permitted — that is what commercialization means — and each requires its own retention decision under Constitution VII. |
| "Consent is required before upload." | **Survives unchanged.** |
| "Session content expires seven days after creation and can be deleted immediately." | **Replaced in part.** Seven-day expiry is replaced by an explicit retention decision per Constitution VII, naming purpose, owner, boundary, retention period, and approval. **Immediate idempotent deletion on demand survives unchanged** and is not weakened by durable retention. |
| "One immutable retail fact package supplies narrative, charts, PDF, and Excel." | **Survives unchanged.** `FactPackage`, `NarrativeAdapter`, and `ReportBundle` remain stable contract boundaries. |
| "Reports are automatically generated and clearly disclosed as such; no human approval is represented." | **Survives unchanged.** The governed disclosure is immutable and is not reworded for commercial tone. |
| "At least 95% of valid datasets of 50 MB or less must produce a complete report bundle within ten minutes under an approved beta benchmark." | **Survives as the floor.** Commercialization may not weaken it. A lower objective requires its own decision. |
| "Privacy, isolation, validation, reconciliation, provenance, language parity, and deletion controls cannot be weakened to improve latency." | **Survives unchanged, and extends to commercial pressure.** These controls may not be weakened to improve latency, price, conversion, or onboarding friction. |

`RRA-001` and `RRA-002` are **not amended by this decision.** Their controls — opaque
identifiers, cross-session isolation failing closed, encryption in transit and at rest, isolated
object namespaces, immediate idempotent deletion, content-free logging — are the substrate of the
product's defensibility. Replacing pseudonymity with real accounts is a specification obligation
under `RCA` that must preserve every one of them, with tests, and it is not discharged by this
decision.

### 3. What this decision does not authorize

- **No product code.** No commercial identity, billing, signup, workspace, or tenancy
  implementation is authorized. Each requires an approved `RCA` specification first.
- **No specification.** This decision allocates no `RCA-*` specification and approves none.
- **No retention change.** Durable retention requires its own Constitution VII decision naming
  purpose, owner, boundary, retention, and approval. This decision permits that decision to be
  written; it does not pre-approve its content.
- **No deployment, provisioning, or spend.** `KHEPRI-DEC-008` remains `proposed` and the
  deployment gate is untouched and remains first. Nothing chartered here can be demonstrated to
  a customer until that clears.
- **No relaxation of any `RRA` control** beyond the four replacements enumerated in §2.

### 4. The RRA re-scope this decision requires

`RRA.md`'s Excludes are written as flat prohibitions. Once `RCA` is active and owns billing,
"billing is excluded" is ambiguous between excluded-from-RRA and excluded-from-Khepri, and
Constitution I requires one authoritative representation per governed fact.

This decision requires that `RRA.md`'s Excludes be re-expressed as family boundaries in the
approval package that accepts this decision, following `FND.md`'s existing phrasing. The
replacement text is staged at `docs/platform/proposed-governance/rra-exclusions-rescope.md`.

**`RRA.md` is pinned by `document_sha256` in `APP-002`**, so this is a renewal rather than an
edit — the same mechanism `APP-013` used for `KHEPRI-DEC-005`. The renewal preserves
`RRA`'s `active` state and names `APP-002` as the package it supersedes.

The re-scope also corrects `RRA.md`'s stale closing sentence, which reads "The family is
proposed" against a registry recording `state: active`. It is corrected in the same renewal
rather than as a separate edit, because a pinned document admits no drive-by fix.

**The re-scope is a consequence of acceptance, not of proposal, and is not applied here.** While
this decision is `proposed` it carries no authority, and editing an approved family charter on
the strength of an unaccepted decision is the borrowed-authority failure Constitution III
forbids.

## Consequences

- `KHEPRI-DEC-003` moves to `superseded` and names this decision as `superseded_by`, retaining
  its own approval evidence. That transition happens **in the accepting package**, not here:
  `lifecycle.py:231` requires a successor be `accepted` before it can be named, so proposing
  this decision cannot and must not touch `KHEPRI-DEC-003`'s registry entry.
- `RRA` remains `active` with every specification under it unchanged. The private beta is a
  governed product boundary that continues to exist, not a phase that ended.
- One follow-up obligation: the `RRA.md` re-scope renewal in §4, carried in the same approval
  package. It is **not** discharged by this decision being proposed.
- Every roadmap phase from 1 onward becomes specifiable once `RCA` is `active`. None becomes
  implementable until its own specification is approved.
- The deployment gate is unchanged and remains first.
- `KHEPRI-DEC-012` and `KHEPRI-DEC-013` are unaffected and not superseded.

---

Identity, lifecycle state, ownership, and approval evidence are authoritative in
`governance/registries/decisions.yaml`.
```

- [ ] **Step 2: Confirm the document accounts for every `KHEPRI-DEC-003` control**

Run: `sed -n '14,31p' governance/decisions/KHEPRI-DEC-003-rra-private-beta.md`
Expected: eight bullet controls plus the commercial-exclusion paragraph. Check each appears as a row in §2's table. A control with no row is a silent drop and must be added before committing.

- [ ] **Step 3: Validate**

Run: `uv run khepri-gov validate`
Expected: exit 0. The document exists but has no registry entry yet, which is legal — the validator judges registry entries, and an unreferenced governance document is not an error at this stage.

- [ ] **Step 4: Commit**

```bash
git add governance/decisions/KHEPRI-DEC-014-commercial-boundary.md
git commit -m "docs: draft KHEPRI-DEC-014, the commercial boundary superseding the beta scope"
```

---

## Task 3: Draft the `RCA` family charter

**Files:**
- Create: `governance/families/RCA.md`

**Interfaces:**
- Consumes: `governance/templates/family.md` structure (`## Owns` / `## Excludes` + the registry pointer line); `RRA.md` and `FND.md` as the two in-repo precedents for phrasing.
- Produces: the charter document referenced by `families.yaml`'s `RCA` entry (Task 5) and pinned by `APP-017` (Task 6).

- [ ] **Step 1: Write the charter**

Create `governance/families/RCA.md`. Note the closing line states the family is **proposed** — which is true at drafting time and matches what Task 5 writes to the registry, avoiding the exact staleness defect `RRA.md` currently carries:

```markdown
# RCA: Retail Commercial Analysis

## Owns

- Durable commercial identity: accounts, credentials, sessions, and recovery, mapped onto the
  opaque owner ID that `RRA-001` establishes as the isolation boundary key.
- Organizations, membership roles, and the authorization model over them.
- Persistent customer workspaces: durable storage of inputs and reports beyond the beta's
  seven-day expiry, under an explicit approved retention decision.
- Multi-dataset accumulation within a workspace, and comparison across datasets a single upload
  could not produce.
- Pricing, plans, entitlements, subscription lifecycle, quota enforcement, and invoicing.
- Public signup, abuse controls, self-serve onboarding, and the pre-purchase product surface.
- Agency tenancy: portfolios, client switching, delegated access, and bounded white labeling.
- Recurring scheduled delivery of reports a customer does not log in to collect.

## Excludes

- The invite-bound pseudonymous beta boundary, its intake and content lifecycle, its
  deterministic retail facts, its grounded bilingual narrative, and its report surfaces. Those
  are `RRA`'s, and `RCA` consumes them rather than reimplementing them.
- Repository governance, artifact identifiers, registries, and fail-closed validation. Those are
  `FND`'s.
- Forecasting, customer-authored formulas, and generic non-retail analysis. These are excluded
  from Khepri rather than reassigned between families, and admitting one requires a separately
  approved decision and family amendment.
- Any weakening of the privacy, isolation, validation, reconciliation, provenance, language
  parity, or deletion controls that `RRA-001`, `RRA-002`, and `RRA-006` fix. Commercialization
  does not relax them, and no `RCA` specification may propose that it does.
- Analytical capabilities owned by `Kemetra/Seshat-BI` under `KHEPRI-DEC-013`, including
  statistical inference Khepri does not implement.
- Product implementation while this family remains proposed or its specifications remain draft.
- Runtime, provider, or deployment selection, which `KHEPRI-DEC-008` governs and which remains
  a separate gate.

The family is proposed. Its authoritative lifecycle state and approval evidence are recorded in
`governance/registries/families.yaml`.
```

- [ ] **Step 2: Confirm no capability is claimed by two families**

Run: `grep -n "billing\|scheduling\|signup\|workspace\|portfolio\|white label" governance/families/RRA.md governance/families/RCA.md`
Expected: each capability appears in `RRA.md`'s Excludes (still as flat prohibitions — Task 4 stages their re-scope) and in `RCA.md`'s Owns. That overlap is precisely what the Task 4 re-scope resolves, and it is why the re-scope must ride in the same approval package: at no approved moment may both documents claim the same capability.

- [ ] **Step 3: Validate**

Run: `uv run khepri-gov validate`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add governance/families/RCA.md
git commit -m "docs: draft the RCA family charter, depending on FND and RRA"
```

---

## Task 4: Stage the `RRA.md` re-scope as reviewable replacement text

**Files:**
- Create: `docs/platform/proposed-governance/rra-exclusions-rescope.md`
- Read only, never modified: `governance/families/RRA.md`

**Interfaces:**
- Consumes: `RRA.md`'s current `## Excludes` block (`governance/families/RRA.md:10-20`) and `FND.md:11-13`'s future-families phrasing.
- Produces: the exact replacement text `APP-017`'s `RRA` renewal entry authorizes. Task 6 references this file by path from the package's scope; the renewal is what permits the edit, and the edit itself happens only after approval.

**Why this task writes a staging document rather than editing the file:** verified empirically 2026-08-07 — `uv run khepri-gov document-digest governance/families/RRA.md` returns `sha256:8a1235a0d6b9e36a6446a1e1cfd3f7ef5db52ca7d9e0ed23bcffb18eded095d2`, byte-identical to `APP-002.yaml:41`. Editing the file makes `khepri-gov validate` fail with `RRA changed without renewal`. `docs/khepri-commercial-roadmap.md:534-545` records this exact trap being hit and reverted for `KHEPRI-DEC-005`, and states the lesson: "'it's just a stale sentence' is exactly the reasoning the digest binding exists to stop."

- [ ] **Step 1: Confirm the pin still matches before relying on it**

Run:
```bash
uv run khepri-gov document-digest governance/families/RRA.md
grep -A3 "id: RRA$" governance/approvals/APP-002.yaml
```
Expected: the computed digest equals the `document_sha256` under `APP-002`'s `RRA` artifact. If they differ, `RRA.md` has already drifted from its approval and that is a pre-existing validation failure to report to the owner before continuing — not something this plan should paper over.

- [ ] **Step 2: Write the staging document**

Create `docs/platform/proposed-governance/rra-exclusions-rescope.md`:

```markdown
# Proposed re-scope of `governance/families/RRA.md`

**Status:** staged replacement text for owner approval. Applies nothing. `RRA.md` is unchanged
and remains pinned by `APP-002`.

`KHEPRI-DEC-014` §4 requires this re-scope, and requires it be carried by a renewal package
rather than an edit. `governance/families/RRA.md` is pinned at
`sha256:8a1235a0d6b9e36a6446a1e1cfd3f7ef5db52ca7d9e0ed23bcffb18eded095d2` by
`governance/approvals/APP-002.yaml`, so `khepri-gov validate` rejects any change to it that no
renewal authorizes.

## Why the current text cannot stand once RCA is active

`RRA.md`'s Excludes are flat prohibitions: billing, subscriptions, scheduling, and public signup
are *excluded*, full stop. Once `RCA` owns billing, "billing is excluded" reads two ways —
excluded from `RRA`, or excluded from Khepri — and Constitution I requires one authoritative
representation per governed fact.

`FND.md:11-13` already solves this correctly, excluding "customer features, business or domain
logic, infrastructure services, and responsibilities of future product families" and stating
those boundaries "require separately approved families and specifications." The re-scope below
adopts that phrasing.

## Two changes, and no others

1. **The Excludes block** is re-expressed as family boundaries rather than prohibitions.
2. **The closing sentence** is corrected. It currently reads "The family is proposed" while
   `governance/registries/families.yaml` records `state: active` — the same
   stale-closing-sentence defect the roadmap records for `KHEPRI-DEC-005`. A pinned document
   admits no drive-by fix, so it is corrected here or not at all.

No line in `## Owns` changes. `RRA` keeps every responsibility it has.

## Replacement text for `## Excludes` and the closing line

> ## Excludes
>
> - Responsibilities of the `RCA — Retail Commercial Analysis` family: commercial
>   authentication, user profiles, persistent customer workspaces, organizations, membership
>   roles, billing, subscriptions, scheduling, public signup, agency portfolios, client
>   switching, delegated access, work queues, and white labeling. Those boundaries require
>   separately approved specifications under that family.
> - Forecasting, generic analysis, customer-authored formulas, and unsupported metrics. These
>   are excluded from Khepri rather than allocated to another family.
> - Analytical capabilities owned by `Kemetra/Seshat-BI` under `KHEPRI-DEC-013`.
> - Runtime or provider selection before a separate architecture decision is accepted.
> - Product implementation while this family's specifications remain draft.
>
> The family's authoritative lifecycle state and approval evidence are recorded in
> `governance/registries/families.yaml`.

## What changed, line by line

| Current | Replacement | Why |
|---|---|---|
| "Commercial authentication, … and public signup." + "Agency portfolios, … and white labeling." (two bullets, flat prohibitions) | One bullet naming `RCA` as the owner and requiring separately approved specifications | Removes the excluded-from-Khepri reading; adopts `FND.md`'s phrasing |
| "Forecasting, generic analysis, customer-authored formulas, and unsupported metrics." | Same list, plus "excluded from Khepri rather than allocated to another family" | Prevents a later reader assuming `RCA` inherited them |
| (absent) | "Analytical capabilities owned by `Kemetra/Seshat-BI` under `KHEPRI-DEC-013`." | `KHEPRI-DEC-013` is `proposed`; this line is added by the same renewal only if that decision is `accepted` first. **If `KHEPRI-DEC-013` is still `proposed` when this package is approved, omit this bullet** — citing an unaccepted decision as a boundary is borrowed authority. |
| "Product implementation while this family remains proposed or its specifications remain draft." | "Product implementation while this family's specifications remain draft." | The family is active; the "remains proposed" clause is dead text |
| "The family is proposed. Its authoritative lifecycle state…" | "The family's authoritative lifecycle state…" | Corrects the stale state claim |

## Mechanism

`APP-017` carries this as a renewal entry, mirroring `APP-013.yaml`'s renewal of
`KHEPRI-DEC-005`:

```yaml
  - id: RRA
    document: governance/families/RRA.md
    document_sha256: sha256:<digest of RRA.md AFTER the replacement is applied>
    from_state: active
    to_state: active
    supersedes_approval_ref: governance/approvals/APP-002.yaml
```

`from_state` equals `to_state` because `approval_renewals.py:140-144` raises
`renewal must preserve state` otherwise. The digest is computed from the edited file, so the
sequencing at approval time is: apply the replacement, compute the digest, write it into
`APP-017`, recompute the manifest digest, then approve. That order is not optional — a digest
taken before the edit pins the wrong bytes.
```

- [ ] **Step 3: Confirm `RRA.md` is still untouched**

Run: `git status --short governance/families/RRA.md`
Expected: no output. If `RRA.md` appears as modified, revert it — this task must not edit it.

- [ ] **Step 4: Validate**

Run: `uv run khepri-gov validate`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add docs/platform/proposed-governance/rra-exclusions-rescope.md
git commit -m "docs: stage the RRA exclusions re-scope the RCA charter requires"
```

---

## Task 5: Add the registry entries, both unapproved

**Files:**
- Modify: `governance/registries/decisions.yaml`
- Modify: `governance/registries/families.yaml`

**Interfaces:**
- Consumes: the two documents from Tasks 2 and 3, by path.
- Produces: registry entries that make `KHEPRI-DEC-014` and `RCA` real artifacts the validator judges. After this task, `khepri-gov validate` is genuinely exercising the new artifacts rather than ignoring unreferenced files.

- [ ] **Step 1: Append the decision entry**

Add to the end of `governance/registries/decisions.yaml`, matching the shape of the `KHEPRI-DEC-013` entry directly above it — four fields only, no approval fields, no `superseded_by`:

```yaml
  - id: KHEPRI-DEC-014
    title: Commercial boundary superseding the private-beta scope
    state: proposed
    owner: AHMED-SHAABAN
    document: governance/decisions/KHEPRI-DEC-014-commercial-boundary.md
```

- [ ] **Step 2: Append the family entry**

Add to the end of `governance/registries/families.yaml`. `depends_on` is required for families (`validator.py:37`) and lists both active families:

```yaml
  - id: RCA
    name: Retail Commercial Analysis
    state: proposed
    owner: AHMED-SHAABAN
    document: governance/families/RCA.md
    depends_on:
      - FND
      - RRA
```

- [ ] **Step 3: Validate — this is the task's real test**

Run: `uv run khepri-gov validate`
Expected: exit 0. Three specific rules are now being exercised and each would fail loudly if this plan's constraints were violated:
- `validator.py:130-135` — `depends_on` must be a list of known ids. `FND` and `RRA` both exist.
- `validator.py:326-328` — an unknown dependency is an error. Neither is unknown.
- `lifecycle.py:213-216` — `superseded_by` is only valid on a `superseded` decision. Neither new entry carries one.

If validation fails on `RCA` needing `approved_by`: check that `state` is `proposed`, not `active`. `validator.py:31` requires approval fields only for `active` and `retired` families.

- [ ] **Step 4: Confirm no state was changed anywhere else**

Run: `git diff --stat` then `git diff governance/registries/`
Expected: exactly two files changed, additions only, no line containing `state:` modified on any pre-existing entry. In particular `KHEPRI-DEC-003` must still read `state: accepted` with no `superseded_by`.

- [ ] **Step 5: Commit**

```bash
git add governance/registries/decisions.yaml governance/registries/families.yaml
git commit -m "gov: register KHEPRI-DEC-014 and the RCA family as proposed"
```

---

## Task 6: Draft `APP-017`, the approval package, with computed digests

**Files:**
- Create: `governance/approvals/APP-017.yaml`

**Interfaces:**
- Consumes: `governance/templates/approval-package.yaml` structure; `APP-016.yaml` as the most recent package precedent and `APP-013.yaml` as the renewal precedent; the documents from Tasks 2, 3, 4.
- Produces: the package the owner reviews and approves. It is the last artifact this plan creates and the only one whose approval unblocks Phase 1's dependents.

- [ ] **Step 1: Compute the document digests**

Run:
```bash
uv run khepri-gov document-digest governance/decisions/KHEPRI-DEC-014-commercial-boundary.md
uv run khepri-gov document-digest governance/families/RCA.md
```
Record both. These pin the exact bytes the owner approves; a later edit to either document invalidates the package and requires a renewal.

- [ ] **Step 2: Write the package with `state: proposed` and no `approval:` block**

Create `governance/approvals/APP-017.yaml`. The `RRA` renewal entry deliberately carries a zero digest, because the bytes it must pin do not exist until the re-scope is applied at approval time:

```yaml
schema_version: 1
id: APP-017
title: Commercial family charter and the boundary that supersedes the private beta
state: proposed
owner: AHMED-SHAABAN
scope: >-
  Accept KHEPRI-DEC-014, activate the RCA — Retail Commercial Analysis family depending on FND
  and RRA, move KHEPRI-DEC-003 to superseded naming KHEPRI-DEC-014 while retaining its own
  approval evidence, and renew the RRA family charter to re-express its Excludes as family
  boundaries per the staged replacement text in
  docs/platform/proposed-governance/rra-exclusions-rescope.md, correcting its stale closing
  sentence in the same renewal.
exclusions:
  - Any change to governance/CONSTITUTION.md or the authorities registry
  - Any delegation record, and any widening of a delegation's scope or expiry
  - Any RCA specification, which this package neither allocates nor approves
  - Any product application code, which requires an approved RCA specification first
  - Any retention decision, which Constitution VII requires be separately approved
  - Any deployment, provisioning, or spending authorization
  - Any transition or approval of KHEPRI-DEC-008, KHEPRI-DEC-012, or KHEPRI-DEC-013
  - Any weakening of RRA-001, RRA-002, or RRA-006 controls
  - Any change to RRA.md's Owns section
  - Any claim that a human authority approved this package, absent that authority's evidence
manifest_digest: sha256:0000000000000000000000000000000000000000000000000000000000000000
artifacts:
  - id: KHEPRI-DEC-014
    document: governance/decisions/KHEPRI-DEC-014-commercial-boundary.md
    document_sha256: sha256:<from Step 1>
    from_state: proposed
    to_state: accepted
  - id: RCA
    document: governance/families/RCA.md
    document_sha256: sha256:<from Step 1>
    from_state: proposed
    to_state: active
  - id: KHEPRI-DEC-003
    document: governance/decisions/KHEPRI-DEC-003-rra-private-beta.md
    document_sha256: sha256:5df52d073bdd426832ac56e47b280e466fa122068d91577b9b3e1c376b3e4b50
    from_state: accepted
    to_state: superseded
  - id: RRA
    document: governance/families/RRA.md
    document_sha256: sha256:0000000000000000000000000000000000000000000000000000000000000000
    from_state: active
    to_state: active
    supersedes_approval_ref: governance/approvals/APP-002.yaml
```

Note on `KHEPRI-DEC-003`'s digest: it is reused verbatim from `APP-002.yaml:31` because the
document is unchanged — only its state moves. Reusing the existing pin is correct; recomputing it
would be equivalent but reusing makes the continuity checkable by eye.

- [ ] **Step 3: Compute and insert the manifest digest**

Run: `uv run khepri-gov approval-digest governance/approvals/APP-017.yaml`
Insert the result as `manifest_digest`. Re-run to confirm it is now stable — the digest covers the artifact list, so inserting it must not change it.

- [ ] **Step 4: Validate**

Run: `uv run khepri-gov validate`
Expected: exit 0. The package is `proposed` with no `approval:` block, so no transition is applied and no registry state is judged against it. If validation instead reports a transition error, confirm `state: proposed` — a package only materializes transitions once approved.

- [ ] **Step 5: Confirm the package applies nothing yet**

Run: `grep -n "state:" governance/registries/decisions.yaml | tail -4` and `grep -n "state:" governance/registries/families.yaml`
Expected: `KHEPRI-DEC-014` still `proposed`, `KHEPRI-DEC-003` still `accepted`, `RCA` still `proposed`, `RRA` still `active`. The package describes four transitions and has applied none of them.

- [ ] **Step 6: Run the full governed gate**

Run: `uv run khepri-gov validate && uv run ruff check . && uv run pytest -q`
Expected: all three pass. `pytest` and `ruff` are unaffected by a documents-only change, and running them confirms exactly that — per `[[khepri-five-ci-checks]]`, CI's `validate`/`ruff`/`pytest` remain the authority.

- [ ] **Step 7: Commit**

```bash
git add governance/approvals/APP-017.yaml
git commit -m "gov: draft APP-017, the commercial charter approval package"
```

---

## What the owner must do next, and what nobody may do for them

This plan ends with four artifacts drafted and nothing approved. Completing Phase 0B requires, in this order:

1. **The owner reviews `KHEPRI-DEC-014`, `RCA.md`, and the staged re-scope**, and decides whether the commercial boundary is the one they want. §2's control-by-control table is the part that most deserves scrutiny — it is where a control could be quietly weakened.
2. **The owner posts approval evidence as a GitHub issue comment.** Per `[[khepri-approval-evidence-mechanism]]`, a bare issue URL is rejected; the evidence must be a comment, transcribed afterwards by a PR.
3. **Apply the `RRA.md` re-scope, then recompute two digests in this order** — `document-digest governance/families/RRA.md` into the `RRA` artifact entry, then `approval-digest` for the manifest. Approving before this leaves the renewal pinning zeroes.
4. **Flip `APP-017` to `approved` with the evidence, and flip all four registry entries in one commit.** `[[khepri-approval-evidence-mechanism]]` records that the package and registry flip must be atomic.
5. **If `KHEPRI-DEC-013` is still `proposed`** at that moment, drop the Seshat bullet from the re-scope text per the note in the staging document.

**A delegated approval is not available for this package.** `DEL-005` expired 2026-08-06, never listed any Phase 0B artifact, and `APP-015.yaml:18` explicitly excludes amending `RRA.md`, any specification, or any family charter. A new delegation would be the owner's to grant, in writing, naming these artifacts.

---

## Self-Review

**Roadmap coverage** (`docs/khepri-commercial-roadmap.md:179-197`, Phase 0B steps 1–5):

- Step 1, "draft a decision superseding `KHEPRI-DEC-003`'s beta boundary, stating what commercialization authorizes and what it still refuses… say explicitly which survive unchanged and which are replaced" → Task 2, §2's eight-row table.
- Step 2, "draft `governance/families/RCA.md` with Owns and Excludes… Its Excludes should still hold a line: forecasting, customer-authored formulas, and generic non-retail analysis stay out" → Task 3.
- Step 3, "re-scope `RRA.md`'s Excludes… in the same approval package as the RCA charter" → Task 4 stages the text, Task 6 carries it as the renewal entry. The roadmap did not anticipate the digest pin; this plan does, and that is the one place it departs from the roadmap's literal instruction ("an edit") in favour of the mechanism the validator actually requires (a renewal).
- Step 4, "add both to the registries with `depends_on: [FND, RRA]` and no approval evidence" → Task 5.
- Step 5, "owner approves via the DEC-004 atomic approval package mechanism" → Task 6 drafts the package; approval is explicitly outside this plan.

**Roadmap's exit criterion** — "`RCA` is `active` in `families.yaml` with approval evidence, and the superseding decision is `accepted`" — is **not** met by this plan and cannot be. It requires the owner. This plan's own exit criterion is: four artifacts drafted, `khepri-gov validate` green, nothing approved.

**Roadmap's kill test** — "Write the pricing page copy before writing the family charter. If you cannot state in three sentences why a chain pays monthly for this, the charter is premature." This plan does **not** discharge it, and it is not an agent's to discharge: it is a judgment about willingness to pay, and Phase 0C's withdrawal means no prospect has been asked. Flagged for the owner at review time rather than silently skipped.

**Placeholder scan:** two intentional `sha256:0000…` values, both required by the mechanism — `manifest_digest` before Task 6 Step 3 computes it, and the `RRA` renewal digest which cannot exist until the re-scope is applied at approval time. Both are called out where they appear. No prose placeholders; every governed document is written in full.

**State-change audit:** no task writes `approved_by`, `approved_at`, `approval_ref`, or `superseded_by`. Task 5 Step 4 and Task 6 Step 5 both explicitly verify that pre-existing states are untouched. `KHEPRI-DEC-003` stays `accepted` throughout.

**Id consistency:** `KHEPRI-DEC-014`, `RCA`, `APP-017` are used identically in Tasks 2, 3, 5, 6 and in the file names. Task 1 verifies all three are free before anything is written.
