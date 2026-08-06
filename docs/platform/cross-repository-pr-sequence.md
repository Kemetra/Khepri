# Cross-repository coordination: PR split, gates, and stop conditions

**Planning-only. Creates no authority. Authorizes no pull request, no branch, and no
identifier.** This is the coordination document roadmap §14 rule 9 requires: base commits,
dependency order, expected PR sequence, compatibility commands, rollback point, and ownership of
follow-up fixes.

Everything below describes work that is **ready for owner review and possible approval
initiation**. Nothing here has been approved, and this document cannot approve it.

Artifacts are named by placeholder. **No identifier is allocated or reserved.** The survey of what
the registries currently hold, and what a next value *would* be if derived, is
[`proposed-governance/identifier-survey.md`](proposed-governance/identifier-survey.md), merged as
R1b. It records provisional candidates and reserves nothing.

---

## 0. Status, 2026-08-05

### The review PRs have landed; no governance PR has been opened

| PR | Repository | State |
|---|---|---|
| **R1a** | `Kemetra/Khepri` | merged `db98f4b` (#97) |
| **R2** | `Kemetra/Seshat-BI` | merged `3875aca` (#579) |
| **R3** | `Kemetra/Khepri` | merged `7dd3c31` (#98) |
| **R1b** | `Kemetra/Khepri` | merged `b2c032c` (#99) |

**No registry has been edited and no artifact has changed state.** `KHEPRI-DEC-008` is still
`proposed`; `KHEPRI-DEC-012` is still `proposed`; no identifier has been allocated. Every package
in §4 remains unopened.

### G5 is withdrawn. G4 remains.

**Owner election, 2026-08-06: the prospect interviews will not be conducted.** G5 — three retail
interviews, two agency interviews, and an explicit go / revise / stop — is **withdrawn**, not
deferred. It no longer gates anything.

**This is the override §2 G5 always contemplated, and it is legitimate.** That section states the
election is the owner's to make, on one condition: it must be **recorded**, naming what was
skipped, rather than left silent. This section is that record, and the text below is retained
rather than deleted for the reason §2 gives — *"a gate bypassed without a record is
indistinguishable later from a gate that never existed."*

**What was skipped, named as §2 requires.** No prospect in either named segment was spoken to. The
premise that auditability is a purchase driver rather than a hygiene factor is therefore
permanently an assumption. The whole sequencing argument in both roadmaps rests on it, and it now
rests on the owner's judgment rather than on evidence. **Any approval package that approves
`[SPEC-REPORT]` must carry this override by reference.**

**G4 is unaffected and still gates `[SPEC-REPORT]`.** It is the golden-sample approval, including
the Arabic copy review — a review of `docs/reporting/golden-sample/`, which already exists. It is
not an interview, it costs nothing but the owner's reading, and it is now the **only** gate between
the owner and `G-g → I1`, the sole chain here that produces something a customer can see.

> **This section is the single statement of that fact.** §2, §3, §6 and §7 point here rather than
> restate it. A gate status repeated in five places is a contradiction waiting for one of them to
> be updated alone — which has already happened twice in this package.

---

## 1. Base commits

| Repository | Branch | Base commit | Date |
|---|---|---|---|
| `Kemetra/Khepri` | `main` | `c7d78b223e24b655c53309266cfac4688c4d8ce8` | 2026-08-04 |
| `Kemetra/Seshat-BI` | `main` | `157ef43e0449a68d1488db0fc967f55b77e77ad5` | 2026-08-04 |

Both clean at inspection. Every PR below branches from its repository's base or from the PR
named as its parent.

---

## 2. Gates — and what each one actually blocks

The most common planning error here is treating the deployment gate as a global blocker. It is
not. Each gate is scoped to what an approved artifact actually makes conditional.

### G1 — Governed environment and benchmark

`KHEPRI-DEC-005` is accepted and names an environment `KHEPRI-DEC-008` prices at ~675 USD/month
and records the owner cannot fund. `KHEPRI-DEC-008`, the provider-neutral replacement, is
`proposed`. No accepted DEC-008 → no approved target-selection artifact → no environment → no
`KHEPRI-DEC-006` benchmark evidence.

**G1 blocks:**

- processing **real customer data**;
- **beta launch** — `KHEPRI-DEC-003` additionally requires an explicit authorization artifact
  from the owner defining client count and observation period;
- any **production claim**, including performance or availability statements;
- any **external demonstration on a governed environment**.

**G1 does not block:**

- documentation and design artifacts;
- the golden sample;
- drafting and approving `[SPEC-REPORT]` — **G5 gates its approval, not G1**;
- **implementing the report layer against local synthetic fixtures**;
- prospect conversations using the existing static golden sample.

**The evidence for that split, because it is not obvious.** `KHEPRI-DEC-003` (accepted) states
that application implementation "may begin only after: (1) this decision is accepted and `RRA` is
active; (2) the relevant RRA specification is approved; (3) **a separate architecture decision
approves final runtime and provider selections**; and (4) the implementation slice links its
specification and relevant reference assessments."

Condition 3 requires an **accepted architecture decision** — not a provisioned environment and
not a passing benchmark. `KHEPRI-DEC-005` is accepted, so condition 3 is satisfied today.
Conditions 1 and 4 are satisfied or procedural. **Condition 2 is the live one:** the relevant
specification must be approved.

So the real gate on report-layer implementation is `[SPEC-REPORT]`, not G1. No approved artifact
orders environment before implementation, and reading G1 that way would stall the only
buyer-visible work behind a spending decision it does not depend on.

> **One caveat to carry.** If `KHEPRI-DEC-008` is accepted and `KHEPRI-DEC-005` moves to
> `superseded`, DEC-003 condition 3 must be satisfied by DEC-008 instead. DEC-008 is an
> architecture decision approving runtime and provider selection as a capability contract, so it
> should satisfy the condition — **but confirm that explicitly in the supersession**, because a
> supersession that silently invalidates a condition another accepted decision depends on is
> exactly the fail-closed case Constitution V covers.

### G2 — Boundary

No Khepri artifact governs any relationship with `Kemetra/Seshat-BI`.

**Blocks:** any integration work, in either repository.
**Does not block:** the boundary artifacts themselves, or anything Khepri-only.

### G3 — Seshat implementation capacity

`Seshat-BI/CLAUDE.md`: spec 138 is RATIFIED and in implementation, spec 137 awaits ratification,
and "At most ONE of the two may be in implementation at a time (spec 138 FR-026)."

**Blocks:** Seshat *implementation*.
**Does not block:** Seshat authorship, ratification, or `[SESHAT-ADR-BOUNDARY]`.
**Currently uncontended** — the integration is deferred, so this package requests no Seshat
implementation capacity at all.

### G4 — Golden-sample approval

Roadmap §10 Phase 1 stop condition, plus the Arabic copy review.

**Blocks:** `[SPEC-REPORT]` proceeding to approval, and therefore implementation.
**Does not block:** the design package, or the sample itself.

> **Unaffected by the 2026-08-06 withdrawal of G5 — §0.** G4 still blocks exactly what it blocked
> before, and with G5 withdrawn it is now the **only** gate on `[SPEC-REPORT]`.

### G5 — Commercial validation (Phase 0C)

`docs/khepri-commercial-roadmap.md` Phase 0C. Every sequencing argument in both roadmaps rests
on auditability being a purchase driver rather than a hygiene factor, and **no prospect in either
named segment has been spoken to.** That is an assumption, not a finding.

**G5 requires all four:**

1. the static golden sample exists and is approved (G4);
2. **three retail chain or mid-market prospect interviews**;
3. **two agency interviews**;
4. an explicit owner decision recorded as **go / revise / stop**.

**G5 blocks:** approval of `[SPEC-REPORT]` (G-g) and implementation I1.

**G5 does not block:** R3, the static golden sample itself, the Arabic copy review, or the
prospect conversations — those *are* the gate being cleared, and they need no code, charter,
environment, or approval to start.

**Sequencing, stated precisely.** The mock is what tests the thesis, so it comes before the code
rather than beside it. Learning that auditability is hygiene rather than a driver costs a few
conversations here; learning it after I1 costs the report layer's information architecture.

**Override.** If the owner elects to approve `[SPEC-REPORT]` without the interview evidence, that
is a legitimate call — but it must be **recorded as an explicit override**, naming what was
skipped and why, in the approval package that approves the specification. Silence is not an
override. A gate bypassed without a record is indistinguishable later from a gate that never
existed, and the whole point of G5 is that its absence is currently invisible.

> **WITHDRAWN by owner election, 2026-08-06 — §0.** The override contemplated in the paragraph
> above has now been exercised and recorded: no interview happened, none will, and §0 names what
> was skipped. **G5 no longer blocks `G-g` or `I1`.** The requirement text is retained as the
> record of what was set aside, not as a live gate.

---

## 3. Proposed PR split

**Governance transitions are never mixed with architecture review.** A reviewer assessing
whether an architecture read is *correct* is doing different work from an owner deciding whether
to *accept a decision*, and combining them means the second borrows assent from the first.

### Review PRs — no governance transition, no registry, no approval package

| PR | Repo | Contents | Depends on | Outcome |
|---|---|---|---|---|
| **R1a** | Khepri | **Khepri architecture planning.** `docs/platform/README.md`, `current-state-delta.md`, `khepri-seshat-target-architecture.md`, `cross-repository-ownership-matrix.md`, this file. | base | **merged** `db98f4b` (#97) |
| **R1b** | Khepri | **Proposed governance drafts.** `docs/platform/proposed-governance/{README, identifier-survey, KHEPRI-DEC-012-amendment, decision-draft-seshat-boundary, family-charter-draft-commercial}.md`. | R1a merged | **merged** `b2c032c` (#99) |
| **R2** | Seshat-BI | **Seshat headless-engine boundary planning.** `docs/architecture/{headless-analysis-engine, khepri-consumer-boundary, analysis-evidence-contracts}.md`. | R1a merged; cites its **actual merged commit SHA** | **merged** `3875aca` (#579), citing `db98f4b` |
| **R3** | Khepri | **Business-report and golden-sample planning.** `docs/reporting/golden-sample-plan.md`. | base — independent of R1a, R1b, R2 | **merged** `7dd3c31` (#98) |

The split held: **no governance transition rode in on any of them**, and every dependency was
satisfied before its dependent opened.

**Why R1a and R1b are separate.** Reviewing whether an architecture read is *correct* is
different work from reviewing whether a governance draft is *the right thing to propose*. Mixing
them means the second borrows assent from the first: a reviewer who agrees the delta report is
accurate has not thereby agreed that a boundary decision should exist. R1b also lands after R1a
so its drafts cite merged architecture rather than a pending branch.

**R3 shares no file with any of them** and is the one that matters commercially.

### Governance PRs — one atomic governance purpose per PR

> **One atomic governance purpose per PR, containing every transition required to leave the
> registries and approval graph valid.**

Not "one transition each." A single purpose frequently requires several transitions that are only
valid together: accepting a replacement decision without superseding what it replaces leaves two
accepted decisions describing incompatible environments, and Constitution I forbids that. The
atom is the *purpose*; the transitions are however many that purpose needs.

**None is authorized.** Each becomes possible only after its review PR merges and the owner
directs it. Every one is listed with the exact artifact state transitions it is expected to
contain, so the package's size is visible before it is drafted.

#### G-a — Deployment capability contract

*Purpose: replace an unfundable provider-specific stack with an approvable capability contract.*

| Artifact | From | To | Note |
|---|---|---|---|
| `KHEPRI-DEC-008` | `proposed` | `accepted` | Records `approved_by`, `approved_at`, `approval_ref` |
| `KHEPRI-DEC-005` | `accepted` | `superseded` | `superseded_by: KHEPRI-DEC-008`; retains its own approval evidence |
| `KHEPRI-DEC-007` | `accepted` | `superseded` | `superseded_by: KHEPRI-DEC-008` |

Plus one new approval package pinning DEC-008's document digest and recording all three
transitions. `(accepted, superseded)` is a valid transition (`lifecycle.py:14`), and
`superseded_by` is supported by both the lifecycle validator (`lifecycle.py:43,151`) and the
package schema (`approval_packages.py:68`) — **so DEC-008's own obligation to "add a
`superseded_by` field to the decisions registry and validator support" is already discharged.**
`KHEPRI-DEC-008` records that discharge itself as of `e27d0bb` (PR #95).

**Why the three transitions cannot travel separately — verified, not argued.** PR #95 (`e27d0bb`)
established this by dry run against the validator, and it is the reason this package is atomic
rather than merely convenient to combine. `APP-013.yaml` pins `KHEPRI-DEC-005` and `APP-005.yaml`
pins `KHEPRI-DEC-007`, each with `to_state: accepted`. Moving either decision to `superseded`
without transition records in the *new* package invalidates those *prior* packages:

```text
ERROR approval-packages:APP-013: KHEPRI-DEC-005 must be at to_state 'accepted'
ERROR approval-packages:APP-005: KHEPRI-DEC-007 must be at to_state 'accepted'
ERROR approval-packages:APP-013: renewal must preserve state 'superseded'
```

A repository state in which the successor is accepted and its predecessors are not yet superseded
is one Constitution I forbids and the validator rejects. All three transitions land in one commit.

**Do not fix `KHEPRI-DEC-005`'s stale closing sentence in this package, or any other.** Once
DEC-005 is `superseded`, editing its body would rewrite prior authority, which Constitution VI
forbids: "supersession is explicit and never rewrites prior authority." The stale sentence
becomes a historical artifact of a superseded decision, which is correct. **This removes the
renewal that earlier drafts of this document placed here.**

#### G-a2 — Target selection

*Purpose: name the provider, region, and residency commitment DEC-008 deliberately declines to
name.*

Separate from G-a because it is a **different purpose with a different gate** — G-a is gated by
authority, G-a2 by a residency and spend commitment. DEC-008 fixes the artifact's required
content: provider and region; residency justification; the concrete product satisfying each
capability with exact versions; confirmation that object-store expiry, deletion, and
multipart-abort semantics satisfy `RRA-002`; recorded RTO and RPO; and the sizing values DEC-008's
rules require.

**Its artifact class is unsettled** — decision, or a sizing-style artifact alongside
`KHEPRI-BMK-001-sizing.yaml` — and must be decided at drafting. Transitions cannot be listed until
it is.

#### G-b — `KHEPRI-DEC-012` revision

**No lifecycle transition. No registry change. No approval package.**

`KHEPRI-DEC-012` is `proposed` and stays `proposed`. This PR revises the *text* of a document that
carries no authority — its own closing line: "While it remains `proposed` it is reasoning on the
record, not authority." No approval package pins it, because packages pin artifacts they
transition and nothing has ever transitioned this one.

| Artifact | From | To |
|---|---|---|
| `KHEPRI-DEC-012` | `proposed` | `proposed` — **unchanged** |

Listing it among the governance PRs is a courtesy to the reader, not a claim that it is one.

#### G-b2 — `KHEPRI-DEC-012` acceptance

*Purpose: accept the revised transformation and orchestration boundary.*

| Artifact | From | To |
|---|---|---|
| `KHEPRI-DEC-012` | `proposed` | `accepted` |

Plus one new approval package pinning the **revised** document digest.

**Separate from G-b by necessity, not preference.** An approval package binds
`document_sha256`. If the revision and the acceptance shared a PR, the digest pinned would be text
the owner approved in the same breath as reading it. Splitting them means the pinned digest is the
*reviewed* text.

#### G-c — Boundary decision proposed

*Purpose: put the Khepri/Seshat-BI boundary on the record as a proposal.*

| Artifact | From | To |
|---|---|---|
| `[DEC-BOUNDARY]` | — (new) | `proposed` |

**No approval package.** Constitution VI requires `approved_by`, `approved_at`, and
`approval_ref` only at `accepted`; a `proposed` decision records none, so there is nothing to
approve and nothing to pin.

**The `AGENTS.md` qualification does not belong here.** Earlier drafts of this document placed it
in G-c. That was wrong: narrowing the copy prohibition to Seshat-Platform is a *consequence of the
boundary being accepted*, not of it being proposed. It moves to G-e.

#### G-d — Seshat boundary decision

*Purpose: record the mirrored boundary under Seshat's own governance.*

Seshat has no YAML registry, so there is no state transition to list. A new ADR is authored with
`Status: Accepted` per that repository's convention, ratified by a named human, citing G-c by
**Khepri commit SHA**. Ratification is a human action; the agent transcribes and never
self-ratifies.

#### G-e — Boundary decision accepted

*Purpose: accept the boundary and discharge its one follow-up obligation.*

| Artifact | From | To |
|---|---|---|
| `[DEC-BOUNDARY]` | `proposed` | `accepted` |

Plus one new approval package pinning the decision document digest, citing G-d by **Seshat commit
SHA**, and carrying the `AGENTS.md` Seshat-Platform qualification. `AGENTS.md` is not pinned by any
approval package, so that edit is plain.

**Why G-c / G-d / G-e are three PRs.** Neither governance system can approve an artifact in the
other repository. A simultaneous merge would have each citing an unmerged commit in the other —
what §14 rule 10 forbids. The handshake gives every citation a real SHA: G-c lands the proposal,
G-d cites it, G-e accepts citing G-d back.

#### G-f — Commercial family charter

*Purpose: charter the commercial family and remove the ambiguity its existence creates in
`RRA.md`.*

**Deliberately an atomic multi-artifact package.** Four transitions that are only valid together:

| Artifact | From | To | Note |
|---|---|---|---|
| `[FAM-COMMERCIAL]` | `proposed` | `active` | Created and activated in one package, as `APP-002` did for `RRA` |
| `RRA` | `active` | `active` | **Renewal** — re-attests `APP-002`'s pin against the new `RRA.md` digest. State unchanged. |
| `[DEC-COMMERCIAL]` | `proposed` | `accepted` | |
| `KHEPRI-DEC-003` | `accepted` | `superseded` | `superseded_by: [DEC-COMMERCIAL]`. **Registry only** — its document is pinned by `APP-002`. |

Plus one new approval package covering all four.

**Why atomic.** Splitting leaves a window in which both `RRA.md` and the new charter claim
billing, which Constitution I forbids; and a window in which `KHEPRI-DEC-003`'s beta boundary
stands `accepted` beside a chartered commercial family, which is two accepted artifacts describing
incompatible products. Neither window may exist, so neither transition may travel alone.

**The renewal is verified, not assumed.** `APP-002.yaml` binds `RRA.md` as
`sha256:8a1235a0d6b9e36a6446a1e1cfd3f7ef5db52ca7d9e0ed23bcffb18eded095d2`, and the file hashes to
exactly that today. `src/khepri_gov/approval_renewals.py` applies; a plain edit fails
`khepri-gov validate` closed, as the `KHEPRI-DEC-005` attempt did. `APP-002` also pins
`KHEPRI-DEC-002`, `-003`, `-004`, and `RRA-001` through `RRA-007`.

#### G-g — Report specification

*Purpose: approve the business-first report and separated audit evidence.*

| Artifact | From | To |
|---|---|---|
| `[SPEC-REPORT]` | `draft` | `approved` |

Plus one new approval package pinning the specification document digest. Created at `draft` and
approved in the same package, as `APP-002` did for `RRA-001` through `RRA-007`.

**Gated by G4 alone.** G5 is withdrawn (§0). The package must carry the **explicit override** that
withdrawal requires, naming what was skipped — no prospect interviews, and the differentiator
premise left untested — by reference to §0.

### Implementation PRs — after their specification is approved

| PR | Repo | Contents | Gate |
|---|---|---|---|
| **I1** | Khepri | Report layer against **local synthetic fixtures**. Includes the ~170-reference test migration across 19 files. | G-g. **Not G1.** |
| **I2** | Khepri | Portability slices `KHEPRI-DEC-008` obliges: PostgreSQL claim-and-redrive, envelope encryption, unlock `runtime/config.py`, re-issue `BMK-001` | G-a. No environment needed; these cost nothing to run. |
| **I3** | Khepri | Provision, benchmark, beta authorization | **G1**, and a separate spending decision |

**I1 carries two exit criteria** beyond the usual checks: promote
`docs/reporting/golden-sample/verify_separation.py` to a required test, and add a coverage test
asserting the business and audit regions *together* still cover every `bundle.figures`,
`bundle.caveats`, and section. Reconcile will not catch a relocation that loses content — both
surfaces claim `sections=bundle.section_ids` unconditionally (`html.py:284`, `excel.py:764`), so
`_reconcile_sections_against_bundle` compares an asserted claim against its own source.

### Deferred — recorded, not proposed

Owner direction 2026-08-05: boundary now, integration deferred past Milestones A and B. **None
of these is proposed, and no identifier is derived for any of them.**

| Ref | Repo | Contents | Would be gated by |
|---|---|---|---|
| **D1** | Seshat-BI | `[SESHAT-SPEC-CONTRACTS]` — schemas, committed fixtures, versioning, compatibility manifest | G2 |
| **D2** | Seshat-BI | `[SESHAT-SPEC-ENGINE]` — repo-root-free `run_analysis`, injected governance context | G2; the §9 metric-authority precondition |
| **D3** | Seshat-BI | Implementation of D2 | **G3** |
| **D4** | Seshat-BI | `[SESHAT-SPEC-CONSUMER]` — producer fixtures, consumer suite | D3 |
| **D5** | Khepri | Consumer specification | D1, and a new decision authorizing it |
| **D6** | Khepri | Request adapter + evidence consumer, one **statistical** analysis Khepri does not already compute | D4, D5 |

Three notes worth keeping:

- **D1 is the cheapest and the one to pull forward first** if the integration is ever revived.
  Committed fixtures need no package, no distribution decision, and no implementation capacity,
  and they satisfy roadmap §2's acceptance criterion in full.
- **D3 carries a required adversarial test:** a request whose context *claims* readiness with no
  supporting evidence must be `refused`. `ADR-0008` gives grant-approval to Core Authority alone;
  roadmap §19.9 requires it survive.
- **D6 must not start with a deterministic retail metric.** `[DEC-BOUNDARY]` §1 keeps those
  Khepri-authoritative, and roadmap Phase 4's "start with existing deterministic retail metrics"
  would mean building them in Seshat first (delta §G.1).

---

## 4. Dependency graph

```text
REVIEW (docs only, no transition, no approval package)
  R1a Khepri architecture ──┬──► R1b governance drafts
                            └──► R2  Seshat boundary  (cites R1a's merged SHA)
  R3  report + golden sample                          (independent of all three)

GOVERNANCE (one atomic purpose per PR; owner-initiated only)
  G-a  DEC-008 accepted + DEC-005/DEC-007 superseded ─┬─► I2 portability slices
                                                      └─► G-a2 target selection
                                                             └─► I3 provision + benchmark
                                                                    └─► G1 cleared
  G-b  DEC-012 revised (NO transition) ──► G-b2 DEC-012 accepted
  G-c  [DEC-BOUNDARY] proposed ──► G-d [SESHAT-ADR] ──► G-e accepted + AGENTS.md
  G-f  [FAM-COMMERCIAL] active + RRA renewal + [DEC-COMMERCIAL] accepted
                                         + DEC-003 superseded   (atomic, 4 transitions)
  G-g  [SPEC-REPORT] approved ──► I1 report layer (synthetic fixtures)

PHASE 0C - WITHDRAWN by owner election 2026-08-06 (see §0)
  3 retail interviews + 2 agency interviews + go/revise/stop  -- will not happen
        └─► G5 no longer gates anything; the override is recorded in §0
  G-g now waits on G4 alone - the golden-sample approval, which is a read not an interview

GATE SCOPE
  G1 blocks : real customer data - beta launch - production claims -
              external demonstration on a governed environment
  G1 NOT    : R1a R1b R2 R3 - G-b G-b2 G-c G-d G-e G-f G-g - I1 - I2
  G4 blocks : G-g - I1          (golden-sample approval; the only remaining gate on them)
  G5 blocks : nothing - WITHDRAWN 2026-08-06

DEFERRED (not proposed, no identifiers derived)
  D1 ──► D2 ──► D3 ──► D4 ──► D5 ──► D6
```

Five independent chains. Only `G-c → G-e` crosses repositories, and it ends at a settled
boundary rather than at running code.

**Two things this graph is drawn to make visible.** `G-g → I1` produces the only thing a customer
can see, and **G1 does not sit on it** — G5 does, and G5 is cleared by conversations rather than
by spend. And `G-b` sits alone with no arrow into a registry, because revising an unaccepted
draft changes no state at all.

---

## 5. Validation — what each check actually proves

### On the current untracked files

`uv run khepri-gov validate` passes at this commit. **That proves the currently governed state
remains valid — that no registry, approval package, or governed document was disturbed. It says
nothing about whether these planning documents are correct, complete, or well-formed.** The
validator reads the registries and the artifacts they name; it performs no scan of the governance
tree (`src/khepri_gov/validator.py` has no `rglob`) and has no knowledge of `docs/`.

Nothing in this package has been validated as *content*. It has been checked for the absence of
side effects, which is a different claim.

### Khepri — required on any review branch

`.github/workflows/governance.yml` defines **five** jobs. All five, in the order the workflow
declares them:

```bash
uv run khepri-gov validate                       # job: validate
uv run ruff check .                              # job: ruff
git diff --name-only origin/main...HEAD \
  | uv run khepri-gov delegation-guard           # job: delegation-guard
uv run pytest                                    # job: pytest
uv run python -m khepri.rra.benchmark_gate       # job: benchmark
```

Plus a **sixth check that appears in no workflow file**: a CodeScene Code Health Review, a GitHub
App, gates every pull request. Every new file must score 10.00 and no tracked hotspot may
decline. Local CodeScene tooling does not reproduce server thresholds — **CI is the only
authority.**

**Three of these are worth understanding before reading a green result as reassurance:**

- **`delegation-guard`** enforces FND-003 at the *file* level: a delegated approval may never ride
  in the same commit as a change to a reserved file, because the package validator sees artifact
  transitions and never the diff. A docs-only PR carrying no approval passes trivially — which is
  a fact about the PR, not a property of the guard.
- **`benchmark`** "certifies nothing without an approved workload." With
  `KHEPRI_BENCHMARK_*` unset — every run today, locally and in CI — it reports NOT CERTIFIED,
  measures no sample, tests no objective, and succeeds without asserting anything. **A green
  benchmark job is not evidence that any objective holds.**
- **CodeScene** scores code files. A docs-only PR introduces no new scoreable file, so the gate
  should be satisfied without a health finding — but CI decides that, not this document.

For a docs-only PR every local result should be **identical to base**, and that is the assertion
worth putting in the PR body: not "checks pass" but "checks are unchanged from base, and here is
each one."

**Two additional checks these PRs should carry, and neither exists today:**

- **Relative-link resolution.** This package is heavily cross-linked, and three files were
  renamed during correction. A broken link in a governance-adjacent document is a real defect.
  No link checker is configured in the repository; one would need adding, or the links verified
  by hand and the method stated.
- **The `APP-002` digest assertion.** Before any PR that touches `RRA.md`, re-hash it and compare
  against `sha256:8a1235a0d6…`. `khepri-gov validate` will catch a mismatch, but catching it
  before the push is cheaper than catching it in CI.

### Seshat-BI — required on any review branch

```bash
seshat check    # static governance gate (src/seshat/cli/__init__.py:191)
pytest          # full suite
```

Plus the SPECKIT fence: `test_active_spec_kit_markers_agree_and_resolve` asserts exactly one
active plan path. **Do not add a second.** R2 is docs-only and adds no plan path, so the fence
should be untouched — assert that rather than assume it.

### Cross-repository

**There is no shared CI.** From D1 onward, both repositories would run the *same committed
fixture set* through their own validators, and each would assert its schema copy matches the
recorded digest (`[DEC-BOUNDARY]` §2a rule 4). That is the only cross-repository check that would
exist, and it does not exist yet.

---

## 6. Known collisions

From `AGENTS.md`, applying to any parallel work:

- Two slices each adding an Alembic migration become **siblings off one parent**; the second to
  merge re-points its `down_revision`.
- **Squash-merging a base branch detaches anything stacked on it.** Replay with
  `git rebase --onto origin/main <old-base>` rather than merging.
- State both in the pull request *before* they happen.

From project memory, bearing on this split specifically:

- Branch protection forces **serial merges**. R1, R2, R3 are independent but still merge one at a
  time.
- Approval evidence must be a **GitHub issue comment first**, then a PR transcribing it. Bare
  issue URLs are rejected. The approval package and the registry flip land in **one commit**.

---

## 7. Stop conditions

Each halts its own chain. None halts all of them — that is the point of the split.

| # | Condition | Halts | Does not halt |
|---|---|---|---|
| 1 | `KHEPRI-DEC-008` not accepted | G-a2, I2, I3, and therefore G1 | R1a–R3, G-b–G-g, **I1** |
| 2 | Golden sample not approved (incl. Arabic copy review) — **G4**. Now the **only** gate on G-g, §0 | G-g, I1 | Everything else |
| 2b | ~~**G5** — interviews and an owner go/revise/stop~~ — **WITHDRAWN 2026-08-06, §0.** Overridden in writing, as this row always required | **nothing** | — |
| 3 | `[DEC-BOUNDARY]` not accepted | G-e, all deferred work | R1a–R3, G-a, G-f, G-g, I1, I2 |
| 4 | The `APP-002` renewal not approved | G-f in its entirety — all four transitions, since the package is atomic | Everything else |
| 5 | Prospect validation negative | **Re-sequence, not halt** — see below | — |
| 6 | Parity gap in a transferred calculation | D6. Dormant while deferred; **re-arm before D6** | — |
| 7 | Spec 138 still open in Seshat | D3. Dormant while deferred | R2, G-d |
| 8 | `KHEPRI-DEC-012` revision not reviewed | G-b2 — the digest pinned must be the reviewed text | G-c, which needs no acceptance of DEC-012 |

**On conditions 2b and 5 — both are now closed by the same election.** Phase 0C was always
*ungated*: no code, no charter, no environment, no approval stood between the owner and starting
it. As **G5** it gated `[SPEC-REPORT]` approval; as **stop condition 5** a negative result would
have re-sequenced rather than halted. The owner has elected not to run it at all (§0), so neither
reading can ever resolve.

**State the residue precisely, because it does not disappear with the gate.** The differentiator
the whole sequence is built on is now permanently unverified. That is not a blocked dependency and
it halts nothing — it is a standing exposure, and the first place it can surface is a paid sale
attempt rather than a conversation. Recorded here so no later reader mistakes a withdrawn gate for
a cleared one.

---

## 8. Ownership of follow-up fixes

| Failure | Owner | Why |
|---|---|---|
| Contract schema disagreement | **Seshat** | §5.2 — Seshat owns contract definitions and the canonical schemas |
| Schema copy drifts from canonical | **Khepri** | It consumes a pinned copy; the digest assertion is its obligation |
| Consumer misreads a valid bundle | **Khepri** | The consumer is Khepri's |
| Version negotiation failure | **Khepri** | §14 rule 7 — Khepri must fail closed |
| Precision loss in round-trip | **Seshat**, Khepri verifies | §7.1 — decimal strings are a producer obligation |
| Reason code with no customer wording | **Khepri** | §7.1 — customer wording is not part of the evidence contract |
| Renderer divergence | **Neither** — recorded as intentional | `[DEC-BOUNDARY]` §4 |
| A number differing between engines | **Halt.** Not a fix, a stop condition | §17 risk 1 |

---

## 9. Preconditions — status, and how each is (or is not) evidenced

**No checkboxes here, deliberately.** An earlier revision rendered these as a ticked list, and a
ticked box reads as a cleared gate whatever the surrounding prose says. Most of these are not
cleared. They are split below by **what kind of thing would make them true.**

### Evidenced — any reader can re-derive these from the repository

| Precondition | Evidence |
|---|---|
| `RRA.md` is digest-pinned, so the commercial re-scope is a renewal | `APP-002.yaml` binds `sha256:8a1235a0d6…`; the file hashes to exactly that |
| `APP-009`'s absence is intentional | Created `c00c098` (#65), withdrawn `f38ee8f` (#66) when `KHEPRI-DEC-009` was rejected |
| The deployment gate does not order environment before implementation | `KHEPRI-DEC-003` condition 3 requires an **accepted architecture decision**; `KHEPRI-DEC-005` is accepted |
| `superseded_by` is already supported | `lifecycle.py:43,151`; `approval_packages.py:68` |

### Recorded as owner direction — **not** traceable evidence

The owner selected each of these in a working session on 2026-08-05. **No issue comment, approval
package, registry entry, or approval reference records any of them**, and `AGENTS.md:17-18`
forbids treating that as human approval. They shape the reasoning in this package; they clear
nothing.

- Distribution — committed files, no package, with the five source-of-truth rules
  (`[DEC-BOUNDARY]` §2a).
- Integration scope — boundary now, integration deferred.
- Renderer question — two renderers, two products, closed.
- `AGENTS.md` ambiguity — qualify to Seshat-Platform.
- Report layer under `RRA` as `[SPEC-REPORT]`.
- `KHEPRI-DEC-012` amended while `proposed`, then accepted.
- Deployment gate as Phase 0 item 0.

**Each becomes a cleared gate only when its own governed artifact is approved with traceable
evidence.** Until then a downstream document must obtain its own approval and must not cite this
section.

### Analysed and closed within this package

- Metric authority for consumer requests — a **precondition**, not an open question
  (`[DEC-BOUNDARY]` §9). Mechanism parked to the integration specification.

### Open

- Whether `KHEPRI-DEC-008`'s supersession of `KHEPRI-DEC-005` preserves `KHEPRI-DEC-003`
  condition 3 (§2 caveat). A drafting obligation for G-a, not a blocker for review.
- **G4 — golden-sample approval, including the Arabic copy review.** The sample exists at
  `docs/reporting/golden-sample/`. This is a read, not an interview, and it is the only thing left
  gating `G-g → I1`.

**Closed by election rather than by evidence**

- **G5 in its entirety.** Three retail interviews, two agency interviews, and an explicit owner
  go/revise/stop. **None happened and none will (§0).** This is closed as a *gate* while remaining
  unresolved as a *question* — the distinction matters, and §7 records the residue.
