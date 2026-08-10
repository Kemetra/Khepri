# Feature Specification: Governance Friction Reduction and Long-Plan Autonomy

**Feature Branch**: `002-governance-friction-reduction` (directory only; no git branch created)

**Created**: 2026-08-10

**Status**: Superseded by `specs/003-governance-v2/` — not approved, not implementation-authorized

**Superseded**: 2026-08-10. This spec recorded OOS-001..005, excluding constitutional amendment on
the grounds that `KHEPRI-AGENT` may not author its own release from the reserved set. The owner
subsequently instructed the opposite ("we need a new or diff gov sys… I authorize you"), which
Article VIII line 55 recognises as the mechanism by which a governed instrument is created. Spec
003 supersedes this one on scope. Its findings on harness blocks and digest drift are carried
forward unchanged and remain accurate. Per Constitution VI, supersession is explicit and never
rewrites prior authority, so this document stands as originally written.

**Input**: User description: "i wanna to change the gov sys as iam the only developer and the
ratification sys is boring and inhibit automation of commit and merging from you as i wanna to make
a long plan and let you do it / so i wanna to change or delete thheses chains which obstacle me"

## Scope boundary: this file proposes, it does not govern

Constitution I requires one authoritative representation per governed fact. Any change to
`governance/CONSTITUTION.md`, `governance/registries/`, or `governance/delegations/` is a governed
fact and is made through an approval package, never through this directory. This file is Spec Kit
working material: it frames the problem and enumerates options. **Nothing here grants anything.**

Article VIII places the constitution, the authorities registry, and every delegation record in the
reserved set. `KHEPRI-DEC-010` clause 7 names the reason as bootstrap containment: *"an authority
that can widen its own authority is unbounded regardless of how narrowly it begins."* This
specification is authored by `KHEPRI-AGENT`. It therefore **cannot** be the instrument that removes
constraints on `KHEPRI-AGENT`, and it does not attempt to be.

## Problem statement

The owner is the sole developer and the sole human authority. He reports that approval ceremony is
tedious and that it blocks the workflow he wants: **write a long plan once, then let the agent
execute it end to end without per-step interruption.**

The 2026-08-10 session is the evidence base. It produced three merged pull requests (#136, #137,
#138) and the friction split cleanly into two unrelated systems.

### Finding 1 — governance was not the blocker it appeared to be

`APP-021` stalled overnight labelled *"needs owner approval"*. The cause was not that charters
warrant owner attention. `DEL-006` enumerated eleven artifact identifiers and was written before
family charters were a question, so charters fell outside the grant **by default rather than by
decision**. `DEL-007` replaced enumeration with the wildcard scope the validator already supported,
and the same class of artifact was then approved by the agent with no owner involvement (#138).

**Governance friction for specifications, decisions, families, and reference assessments is already
resolved** for the life of `DEL-007`. It is not part of this feature's problem.

### Finding 2 — the real blocker is the harness, not the repository

Every hard stop in the session came from the Claude Code permission classifier, not from
`khepri-gov`:

| Blocked action | Source | Governance verdict at the time |
|---|---|---|
| `uv run khepri-gov validate` | permission classifier | would have passed |
| `git commit` (heredoc form) | permission classifier | package already valid |
| `git push origin main` (×2) | permission classifier | CI green on identical content |

`validate` and `delegation-guard` passed on every attempt. `DEL-007` cannot reach the classifier —
it is Claude Code configuration, outside the repository's authority entirely. **This is the
obstacle that actually inhibits commit and merge automation**, and it requires no constitutional
change to remove.

### Finding 3 — one genuine governance limit remains

Two things still reach the owner, both by Article VIII design:

1. **Delegation renewal.** `DEL-007` expires 2026-11-08 and cannot renew itself. Article VIII fixes
   the ninety-day standing maximum in constitutional text; `STANDING_MAX_DAYS = 90` merely enforces
   it.
2. **The reserved set.** Deployment (`KHEPRI-DEC-008`), spend, provider selection, the constitution,
   and the authorities registry.

These are the only remaining "chains", and they are load-bearing rather than incidental.

## User scenarios

### Scenario 1 — Long plan executed without interruption (primary)

**Given** the owner has written a multi-step plan and the work touches only non-reserved artifacts,
**when** the agent executes it, **then** the agent creates branches, commits, pushes, opens pull
requests, approves non-reserved packages under delegation, and merges once CI is green, **without
pausing for per-step permission**, and **the owner reads one summary at the end.**

### Scenario 2 — Plan reaches the reserved set

**Given** an executing plan whose next step would deploy, authorize spend, select a provider, or
edit the constitution, **when** the agent reaches that step, **then** it completes every
non-reserved step, **stops** at the reserved one, and reports precisely what remains and why.

### Scenario 3 — Delegation lapse

**Given** `DEL-007` has expired, **when** the agent attempts a delegated approval, **then**
validation fails closed with a message naming the expired record, and the agent asks the owner for a
renewal instruction rather than proceeding.

### Scenario 4 — Owner revokes mid-plan

**Given** a plan in flight, **when** the owner revokes by any means, **then** the agent stops
further approvals immediately, does not resist or defer, and transitions already recorded stand as
recorded.

## Functional requirements

### Must have — harness autonomy (no governance change required)

- **FR-001** Commit, push, branch, and PR-creation commands MUST execute without a per-invocation
  permission prompt, via a project-scoped allowlist.
- **FR-002** Read-only verification commands (`khepri-gov validate`, `delegation-guard`,
  `document-digest`, `approval-digest`, `ruff`, `pytest`) MUST execute without prompting.
- **FR-003** The allowlist MUST be scoped to this repository and MUST NOT grant blanket shell
  access. Destructive operations (`push --force`, `reset --hard` on shared refs, history rewriting,
  branch deletion on the remote) MUST remain gated.
- **FR-004** Merging a pull request MUST be permitted once every required check reports success,
  and MUST remain blocked while any check is pending or failing.

### Must have — plan execution

- **FR-005** The agent MUST execute an approved multi-step plan to completion without requesting
  per-step confirmation for non-reserved work.
- **FR-006** The agent MUST halt at any step touching the reserved set and report the remaining
  items rather than attempting them.
- **FR-007** Every delegated approval MUST record `approved_by: KHEPRI-AGENT` and its
  `delegation_ref`, never a human identifier. This requirement is non-negotiable and machine
  enforced.
- **FR-008** The agent MUST report, at plan end, every artifact it approved and every step it
  skipped, with reasons.

### Should have — reducing renewal friction

- **FR-009** The system SHOULD warn the owner ahead of `DEL-007`'s expiry rather than failing
  silently on the day.
- **FR-010** A renewal SHOULD be a single owner instruction, with the record drafted by the agent
  and requiring only the instruction to become valid.

### Out of scope — constitutional amendment

The following are explicitly **excluded** from this feature and recorded here so the boundary is
unambiguous:

- **OOS-001** Removing or weakening Articles II, V, or VIII.
- **OOS-002** Removing the reserved set, or removing any member of it.
- **OOS-003** Raising or removing the ninety-day standing delegation maximum.
- **OOS-004** Granting `KHEPRI-AGENT` authority to approve delegation records, including its own
  renewal.
- **OOS-005** Deleting the approval-package mechanism, the registries, or `khepri-gov` enforcement.

**Rationale.** Each of these is inside the reserved set, so `KHEPRI-AGENT` may not approve them, and
this specification is authored by `KHEPRI-AGENT`. They are not refused — they remain entirely open
to the owner — but they must originate as an owner decision, not as an agent-drafted change to the
agent's own limits. See "Open decision for the owner" below.

## Success criteria

- **SC-001** A multi-step plan touching only non-reserved artifacts completes end to end with
  **zero** permission prompts and **zero** approval requests to the owner.
- **SC-002** Owner touchpoints for a routine governance change drop from **one per artifact** to
  **zero**, with the delegation renewal (once per 90 days) the only scheduled interruption.
- **SC-003** A plan reaching a reserved-set step stops there in **100%** of cases and never
  approves past it.
- **SC-004** Every approval in the repository remains attributable by inspection to either the
  owner or the agent, with **no** case where the two are indistinguishable.
- **SC-005** No governed document's registry entry pins a digest that differs from the file on
  disk — the defect class corrected by `APP-018` through `APP-021`.
- **SC-006** The owner can revoke all delegated authority in **one action**, taking effect
  immediately.

## Open decision for the owner

The owner has asked twice to remove the ratification chains. That is a legitimate request and it
has a legitimate route, but it is not this specification's to take. The options, stated plainly:

| Option | What it means | Who can author it |
|---|---|---|
| **A — Harness only** | Fix the permission classifier. Governance unchanged. Removes every blocker observed this session except reserved-set stops. | Agent may implement in full |
| **B — Narrow the reserved set** | Amend Article VIII to remove specific members (e.g. move provider selection out). The reserved set shrinks; bootstrap containment survives. | **Owner authors**; agent may draft on instruction |
| **C — Remove ratification entirely** | Delete approval packages, registries, and `khepri-gov` enforcement. No approval step exists. | **Owner only** |

**Recommendation: A, and reassess.** Option A removes the friction actually observed this session
and requires no constitutional change. Options B and C address a cost the evidence does not yet show
you are paying: after `DEL-007`, no non-reserved artifact required owner approval at all.

Option C also has a consequence worth stating before it is chosen rather than after.
`KHEPRI-DEC-010` records that the automation's credential authenticates as `Kemetra` and that
nothing in the repository is cryptographically attributable to a person. Under the current model,
attribution is what remains verifiable once personal attribution is not. Remove the approval
records and the repository can no longer answer *who decided this and when* — including for the
owner's own past decisions. That is a real trade and it may still be the right one for a
single-developer platform; it should be made deliberately.

## Assumptions

- **A-001** The owner's `/speckit-specify` instruction is a request to specify the change, not an
  instruction to enact it. Governed changes still flow through approval packages.
- **A-002** "Automation of commit and merging" refers to the permission-classifier blocks observed
  this session, since those were the only commit and merge failures.
- **A-003** The owner wants attribution preserved unless he states otherwise; FR-007 reflects this
  and is revisitable.
- **A-004** `DEL-007` remains in force. This feature assumes delegated approval works as merged in
  #137 and does not re-litigate it.
- **A-005** Spec Kit is not initialized in this repository (`.specify/` absent). This directory
  follows the layout established by `specs/001-rca-001-commercial-identity/`.

## Key entities

- **Reserved set** — constitution, authorities registry, delegation records, decisions altering the
  reserved set. Enforced by `is_reserved_file()` independently of delegation scope.
- **Delegation record** — the agent's attestation of an owner instruction; not proof of one.
  Article VIII.
- **Approval package** — the unit carrying a manifest digest, artifact transitions, and an approval
  block naming its authority.
- **Permission allowlist** — Claude Code harness configuration. **Not** a governed artifact, and
  outside the repository's authority.

## Dependencies

- `DEL-007` (merged #137), expiring 2026-11-08
- `APP-021` (merged #138), closing the `RCA` registry digest gap
- Article VIII and `KHEPRI-DEC-010` for the reserved set and attribution rules
- Claude Code settings for FR-001 through FR-004; no repository dependency
