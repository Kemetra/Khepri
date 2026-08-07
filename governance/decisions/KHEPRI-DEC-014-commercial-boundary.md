# KHEPRI-DEC-014: Commercial boundary superseding the private-beta scope

## Context

`KHEPRI-DEC-003` is `accepted` and bounds Khepri to an invite-only private beta: a pseudonymous
single-use invitation, no durable customer, seven-day content expiry, and one dataset per session.
`governance/families/RRA.md` excludes, in its own words, "commercial authentication, user profiles,
persistent customer workspaces, organizations, membership roles, billing, subscriptions,
scheduling, and public signup" and "agency portfolios, client switching, delegated access, work
queues, and white labeling."

Every capability a paying customer needs is on that exclusion list. `AGENTS.md` forbids
implementing ahead of an approved specification, and a specification cannot be approved into a
family that excludes its subject, so no billing, signup, or workspace slice is authorizable today
at any level of effort. `docs/khepri-commercial-roadmap.md` records this as the gate on every phase
from 1 onward.

Two reference reviews already surveyed this ground and deferred it — `BATCH-04` (commercial
identity, persistent workspaces, report history) and `BATCH-09` (agency portfolios, delegation,
work queues, white labeling). Both are technical evidence carrying no approval.

### Why a new family rather than editing RRA

Deleting `RRA.md`'s exclusions would leave one family document asserting both "invite-only
pseudonymous beta" and "commercial multi-tenant service." Constitution I requires one authoritative
representation per governed fact, and a family claiming both is two claims in one document.
`FND.md` already shows the correct shape: it excludes "responsibilities of future product families"
and states those boundaries "require separately approved families and specifications."

`RRA` is not retired and not superseded. The private beta remains a real, governed product boundary
with approved specifications `RRA-001` through `RRA-009` under it. What changes is that `RRA` stops
being the only product family, and its exclusions are re-expressed as family boundaries rather than
as prohibitions on Khepri.

### What this decision does not rest on

No prospect in either named buyer segment has been spoken to. `docs/khepri-commercial-roadmap.md`
records the commercial-validation gate as **withdrawn by owner election on 2026-08-06**, and the
same document names the consequence: the premise that auditable analysis is a purchase driver
rather than a hygiene factor is "permanently an assumption rather than a finding."

That premise is what orders the commercial phases. This decision charters the family those phases
need; it does not convert the assumption into evidence, and a later reader must not mistake the
existence of this decision for validation of the thesis behind it.

## Decision

### 1. The RCA family is created

Create the proposed `RCA — Retail Commercial Analysis` family, depending on `FND` and `RRA`,
charted in `governance/families/RCA.md`. It owns durable commercial identity, organizations and
membership, persistent customer workspaces, multi-dataset accumulation, pricing and billing,
public signup and onboarding, agency tenancy, and recurring delivery.

It does not own, and its charter excludes, forecasting, customer-authored formulas, and generic
non-retail analysis. Those stay excluded from Khepri entirely rather than moving between families.

### 2. What the private-beta boundary contributed, and what replaces it

`KHEPRI-DEC-003`'s beta boundary is superseded **in scope only**. Each of its controls is accounted
for below. A control marked *survives* is unchanged and binds `RCA` exactly as it binds `RRA`; a
control marked *replaced* is replaced only by the named successor obligation and never by silence.

| `KHEPRI-DEC-003` control | Status under RCA |
|---|---|
| "A single-use invitation creates a pseudonymous session and opaque owner ID." | **Replaced.** Durable accounts replace single-use invitations. The opaque owner ID survives as the internal boundary key, so `assert_same_scope` and every isolation test keep working; commercial identity maps *to* it rather than replacing it. |
| "stores invitation secrets only as hashes and collects no password, profile, billing identity, or email owner key" | **Replaced in part.** Hash-only storage of secrets survives and extends to credentials. Collecting a profile, billing identity, and email owner key becomes permitted — that is what commercialization means — and each requires its own retention decision under Constitution VII. |
| "Consent is required before upload." | **Survives unchanged.** |
| "Session content expires seven days after creation and can be deleted immediately." | **Replaced in part.** Seven-day expiry is replaced by an explicit retention decision per Constitution VII, naming purpose, owner, boundary, retention period, and approval. **Immediate idempotent deletion on demand survives unchanged** and is not weakened by durable retention. |
| "One immutable retail fact package supplies narrative, charts, PDF, and Excel." | **Survives unchanged.** `FactPackage`, `NarrativeAdapter`, and `ReportBundle` remain stable contract boundaries. |
| "Reports are automatically generated and clearly disclosed as such; no human approval is represented." | **Survives unchanged.** The governed disclosure is immutable — `bundle.py` compares it in full — and is not reworded for commercial tone. |
| "At least 95% of valid datasets of 50 MB or less must produce a complete report bundle within ten minutes under an approved beta benchmark." | **Survives as the floor.** Commercialization may not weaken it. A lower objective requires its own decision. |
| "Privacy, isolation, validation, reconciliation, provenance, language parity, and deletion controls cannot be weakened to improve latency." | **Survives unchanged, and extends.** These controls may not be weakened to improve latency, price, conversion, or onboarding friction. |

`RRA-001` and `RRA-002` are **not amended by this decision.** Their controls — opaque identifiers,
cross-session isolation failing closed, encryption in transit and at rest, isolated object
namespaces, immediate idempotent deletion, content-free logging — are the substrate of the
product's defensibility. Replacing pseudonymity with real accounts is a specification obligation
under `RCA` that must preserve every one of them, with tests, and it is not discharged by this
decision.

### 2a. The implementation-evidence requirement is carried forward, not dropped

`KHEPRI-DEC-003` gates application implementation on four conditions, the fourth of which is that
"the implementation slice links its specification and relevant reference assessments." A
repository-wide search finds that requirement stated in `KHEPRI-DEC-003` and in `RRA-007` and
nowhere else, so superseding `KHEPRI-DEC-003` without restating it would silently remove it for
every future slice — which §3 claims this decision does not do.

**The requirement is therefore restated here, binding `RCA` as it bound `RRA`:**

An implementation slice under `RCA` may begin only after this decision is accepted and `RCA` is
`active`; the relevant `RCA` specification is approved; a separately approved architecture decision
has settled runtime and provider selection; and **the slice links its specification and the
reference assessments relevant to it.**

The registry has no mechanism for superseding a decision "in scope only" — a `superseded` decision
is superseded whole. That is precisely why every obligation worth keeping has to be restated in the
successor rather than left to be inherited, and it is why §2's table enumerates each control instead
of describing the boundary in prose.

### 3. What this decision does not authorize

- **No product code.** No commercial identity, billing, signup, workspace, or tenancy
  implementation is authorized. Each requires an approved `RCA` specification first.
- **No specification.** This decision allocates no `RCA-*` specification and approves none.
- **No retention change.** Durable retention requires its own Constitution VII decision naming
  purpose, owner, boundary, retention, and approval. This decision permits that decision to be
  written; it does not pre-approve its content.
- **No deployment, provisioning, or spend.** `KHEPRI-DEC-008` remains `proposed` and the deployment
  gate is untouched and remains first. Nothing chartered here can be demonstrated to a customer
  until that clears.
- **No relaxation of any `RRA` control** beyond the four replacements enumerated in §2.

### 4. The RRA re-scope this decision requires

`RRA.md`'s Excludes are written as flat prohibitions. Once `RCA` is active and owns billing,
"billing is excluded" is ambiguous between excluded-from-RRA and excluded-from-Khepri, and
Constitution I requires one authoritative representation per governed fact.

This decision requires that `RRA.md`'s Excludes be re-expressed as family boundaries in the
approval package that accepts this decision, following `FND.md`'s existing phrasing. The
replacement text is staged at `docs/platform/proposed-governance/rra-exclusions-rescope.md`.

**`RRA.md` is pinned by `document_sha256` in `APP-002`**, so this is a renewal rather than an edit —
the same mechanism `APP-013` used for `KHEPRI-DEC-005`. The renewal preserves `RRA`'s `active` state
and names `APP-002` as the package it supersedes.

The re-scope also corrects `RRA.md`'s stale closing sentence, which reads "The family is proposed"
against a registry recording `state: active`. It is corrected in the same renewal rather than as a
separate edit, because a pinned document admits no drive-by fix.

**The re-scope is a consequence of acceptance, not of proposal, and is not applied here.** While
this decision is `proposed` it carries no authority, and editing an approved family charter on the
strength of an unaccepted decision is the borrowed-authority failure Constitution III forbids.

## Consequences

- `KHEPRI-DEC-003` moves to `superseded` and names this decision as `superseded_by`, retaining its
  own approval evidence. That transition happens **in the accepting package**, not here: the
  governance validator requires a successor be `accepted` before it can be named, so proposing this
  decision cannot and must not touch `KHEPRI-DEC-003`'s registry entry.
- `RRA` remains `active` with every specification under it unchanged. The private beta is a governed
  product boundary that continues to exist, not a phase that ended.
- One follow-up obligation: the `RRA.md` re-scope renewal in §4, carried in the same approval
  package. It is **not** discharged by this decision being proposed.
- Every roadmap phase from 1 onward becomes specifiable once `RCA` is `active`. None becomes
  implementable until its own specification is approved.
- The deployment gate is untouched and remains first.
- `KHEPRI-DEC-012` and `KHEPRI-DEC-013` are unaffected and not superseded.
- The commercial thesis behind the phase ordering remains an untested assumption, as recorded in
  Context. This decision does not change that and must not be cited as evidence for it.

---

Identity, lifecycle state, ownership, and approval evidence are authoritative in
`governance/registries/decisions.yaml`.
