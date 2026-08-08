# RCA-001 — Cross-artifact analysis

Analyzes `governance/specifications/RCA-001.md`, `plan.md`, `tasks.md`, and the governance
constraints together.

---

## 1. Architecture and governance compliance check

Required by the workflow's §9. Any `BLOCKED` row stops the chain.

| Constraint | Plan decision | Evidence | Result |
|---|---|---|---|
| `AGENTS.md:14` — no product code ahead of an approved spec | No code written; tasks are unexecuted | This run wrote only `.md` | **PASS** |
| `AGENTS.md:16` — small verifiable slices, fail closed | 21 slices, each with a stop condition | `tasks.md` | **PASS** |
| `AGENTS.md:19` — three validation commands | Named in spec Verification and `tasks.md` | `RCA-001.md` §Verification | **PASS** |
| `AGENTS.md:21` — CodeScene 10.00 on new files, ≤3 ctor args | Domain split across 7 small modules; frozen dataclasses | `plan.md` §2 | **PASS** (verifiable only in CI) |
| `AGENTS.md:24-28` — migration sibling collision | `down_revision` stated, re-point warned in advance | `plan.md` §3 | **PASS** |
| Constitution I — one authoritative representation | Requirements only in the governed path; `specs/.../spec.md` is a pointer | `spec.md` | **PASS** |
| Constitution II — named human authority | No approval claimed or recorded | registry `draft` | **PASS** |
| Constitution III — reference is not authority | No Seshat artifact used | — | **PASS** |
| Constitution IV — no scope smuggled | Exclusions enumerate all 20 non-goals | `RCA-001.md` §Exclusions | **PASS** |
| Constitution V — fail closed | `FR-022` deny-by-default; 11 security tasks | `tasks.md` | **PASS** |
| Constitution VII — least data, retention decision | Retention named as precondition 3, **not authored** | `clarify.md` P-1 | **PASS** |
| Constitution VIII — delegation | All delegations expired; none reused | `plan.md` §1 | **PASS** |
| `RCA.md` Owns — identity, orgs, membership, authz | Exactly this slice; nothing broader | `RCA-001.md` | **PASS** |
| `RCA.md` Excludes — no RRA reimplementation | `FR-036`; RRA consumed via `SessionScope` | `plan.md` §6 | **PASS** |
| `RCA.md` Excludes — no weakening of RRA-001/002/006 | `FR-037`, `FR-038`; `T-019` asserts `sessions.py` byte-identical | `tasks.md` T-019, T-020 | **PASS** |
| `RCA.md` Excludes — no runtime/provider selection | None chosen; no external provider adopted | `plan.md` §4 | **PASS** |
| `KHEPRI-DEC-014` §2 — opaque owner ID survives | Organization maps to it; `sessions.py` unmodified | `plan.md` §6 | **PASS** |
| `KHEPRI-DEC-014` §2 — hash-only secrets extend to credentials | `FR-002`, `FR-005`, `FR-016` | `RCA-001.md` | **PASS** |
| `KHEPRI-DEC-014` §2 — consent survives unchanged | `FR-038` | `RCA-001.md` | **PASS** |
| `KHEPRI-DEC-014` §2 — immediate deletion survives | `FR-037`; org/account deletion excluded | `RCA-001.md` §Exclusions | **PASS** |
| `KHEPRI-DEC-014` §2 — 95%/10min floor not weakened | Untouched; no latency claim made | — | **PASS** |
| `KHEPRI-DEC-014` §3 — no retention change | Excluded; precondition 3 | `RCA-001.md` | **PASS** |
| `KHEPRI-DEC-014` §3 — no deployment or spend | None proposed | `plan.md` §10 | **PASS** |
| `KHEPRI-DEC-014` §2a — four implementation conditions | All four listed; **2 and 3 unmet** | `RCA-001.md` §Preconditions | **GATE — see §5** |
| `KHEPRI-DEC-013` — Seshat boundary | Excluded | `RCA-001.md` §Exclusions | **PASS** |
| `RRA-001:21` — opaque owner ID is the attachment point | Used exactly as intended | `plan.md` §6 | **PASS** |

**No `BLOCKED` row.** The single `GATE` row is the implementation-authority gate, which is the
workflow's designed stopping point rather than a defect.

---

## 2. Traceability matrix

`Requirement → Plan decision → Task(s) → Validation`

| FR | Plan | Task(s) | Validation |
|---|---|---|---|
| FR-001 | §2 `Account` | T-001 | account exists, grants nothing |
| FR-002 | §4 scrypt reuse | T-001 | no recoverable credential |
| FR-003 | §2 `AuthSession` | T-012 | one actor resolved |
| FR-004 | §5 one refusal | T-002 | three causes, identical message |
| FR-005 | §7 recovery | T-013 | single-use, expiring |
| FR-006 | §7 enumeration | T-013 | unknown address indistinguishable |
| FR-007 | §7 revocation | T-013 | prior sessions invalidated |
| FR-008 | §5 live resolve | T-002, T-017 | disabled stops authorizing |
| FR-009 | §2 `Organization` | T-003 | org owns content |
| FR-010 | §2 atomic creation | T-003 | never ownerless |
| FR-011 | §2 `Membership` | T-005 | scopes do not merge |
| FR-012 | §3 row-targeted revoke | T-005 | non-interference both ways |
| FR-013 | §3 transactional guard | T-004, T-011 | three routes + concurrency |
| FR-014 | §2 audit | T-006 | five fields recorded |
| FR-015 | §2 `Role` | T-003, T-015 | two roles, matrix |
| FR-016 | §2 `Invitation` | T-007 | one org, one role, hashed |
| FR-017 | §7 single-use | T-008 | replay/expiry uniform |
| FR-018 | §2 acceptance | T-007 | exactly one membership |
| FR-019 | §2 email-addressed | T-009 | precedes account |
| FR-020 | §2 revocation | T-008 | invitations invalidated |
| FR-021 | §5 resolver | T-014, T-021 | actor + scope required |
| FR-022 | §5 deny-by-default | T-012, T-014, T-015 | unresolved ⇒ denied |
| FR-023 | §5 scope from membership | T-016, T-021 | guessed id denied |
| FR-024 | §5 step 4 | T-015, T-016 | conflicting scope denied |
| FR-025 | §5 one refusal | T-016 | denial == nonexistence |
| FR-026 | §5 canonical path | T-014, T-021 | unconstructable elsewhere |
| FR-027 | §2 `AuthSession` | T-018 | at most one active org |
| FR-028 | §5 step 3 | T-018 | no-org account denied |
| FR-029 | §5 validated switch | T-018 | membership required |
| FR-030 | §2 unpersisted context | T-017 | bites without session end |
| FR-031 | §6 bridge | T-019 | scope resolved |
| FR-032 | §6 opaque generation | T-019 | no identifier derivable |
| FR-033 | §6 opacity | T-019 | scope contains no identity |
| FR-034 | §6 unchanged | T-019, T-020 | uniform refusal preserved |
| FR-035 | §6 stable id | T-019 | distinct + stable |
| FR-036 | §6 one-way | T-019, T-020 | RRA learns nothing |
| FR-037 | §3, §8 | T-010, T-019, T-020 | `sessions.py` byte-identical |
| FR-038 | §8 | T-020 | consent/disclosure/parity hold |
| FR-039 | §3 separate `Base` | T-010, T-020 | RRA passes with no `rca_*` row |
| FR-040 | §7 content-free | T-006 | no secret in audit |

**All 40 requirements have task coverage. All 21 tasks trace to at least one requirement.**
Scenario coverage: all 20 scenarios map through the specification's scenario table into tasks.

---

## 3. Checks the workflow requires

| Check | Finding |
|---|---|
| Requirements with no task coverage | **None** — 40/40 covered |
| Tasks not justified by requirements | **None** — 21/21 trace back |
| Authorization path without denial tests | **None** — T-015 matrix asserts every denial cell; T-002, T-008, T-016, T-017, T-021 are dedicated denial tasks |
| Missing cross-org tests | **None** — T-016 covers read and mutation; T-019 covers scope distinctness |
| Scope creep | **None** — every task maps to an FR; all 20 non-goals excluded |
| Speculative infrastructure | **None** — no external provider, no cache, no queue, no third role |
| Duplicated sources of truth | **Resolved** — `specs/.../spec.md` is a pointer, not a second spec; `/speckit-constitution` deliberately not run |
| Hidden RRA changes | **None** — T-019 asserts `sessions.py` byte-identical; T-010 forbids altering `rra_*`; T-020 gates on an empty RRA diff |
| Migration without backward-compatibility | **Addressed** — additive only; down_revision stated; reversibility tested in T-010 |
| Product decisions buried in tasks | **None** — all 11 product decisions surfaced in `clarify.md` C-1..C-11 |

**Critical findings: 0. High findings: 0.**

---

## 4. Residual risks

- **R-1 — CodeScene is unverifiable locally.** `AGENTS.md:20-23` names a CodeScene Code Health
  gate that "local tooling does not reproduce" and calls CI the only authority. The plan's small
  modules and 2-3 argument constructors are aimed at it, but the gate cannot be confirmed until CI
  runs. *Not resolvable in this run.*
- **R-2 — Concurrency tests are backend-sensitive.** T-011's final-owner race depends on the
  database's isolation level. If tests run on SQLite and production on PostgreSQL, the test may
  pass where production would race. T-011 should run against the production engine.
- **R-3 — `A-1` (email uniqueness as a product rule) is rejectable.** If a reviewer rejects it,
  `FR-005` and `FR-019` both change. Flagged in `clarify.md` C-2 for exactly this reason.
- **R-4 — Stale prose in `governance/families/RCA.md:36`** reads "The family is proposed" while
  `families.yaml:24` records `state: active`. This is the same class of defect `KHEPRI-DEC-014` §4
  identified in `RRA.md`. **Reported, not fixed**, for two independently sufficient reasons.
  First, `RCA.md` is pinned: `governance/approvals/APP-017.yaml` carries
  `document_sha256: sha256:011d8950a297e2dd1d739d034ace60146ec49b50e909ef22e660d27b4fc23c69`
  for it (verified by reading the package, not inferred), and DEC-014 §4 establishes that "a
  pinned document admits no drive-by fix" — correcting it requires a renewal package, which is
  how `RRA.md`'s identical defect was handled in this same package. Second, editing an approved
  family charter is outside this specification's boundary regardless of pinning. Fixing it here
  would be an unauthorized governance change.

---

## 5. Implementation authority — the gate

Re-read from the authoritative registries at `HEAD = 3da504c`.

| Precondition (`KHEPRI-DEC-014` §2a) | State | Evidence |
|---|---|---|
| Decision accepted and `RCA` active | **MET** | `decisions.yaml:104` `accepted`; `families.yaml:24` `active` |
| The relevant `RCA` specification is approved | **NOT MET** | `RCA-001` is `draft`; no approval evidence exists |
| A separately approved architecture decision settled runtime and provider | **NOT MET** | `KHEPRI-DEC-008` is `proposed` (`decisions.yaml:62`) |
| The slice links its specification and reference assessments | n/a | No slice exists |

Plus, from Constitution VII and `KHEPRI-DEC-014` §2/§3:

| Additional precondition | State |
|---|---|
| Constitution VII retention decision for durable identity data | **NOT MET** — does not exist; not authored here |

And on authority itself:

| Authority route | Available? |
|---|---|
| Human approval by `AHMED-SHAABAN` | Not given in this session |
| Delegated approval by `KHEPRI-AGENT` | **No** — `DEL-001`..`DEL-005` all expired on or before `2026-08-06` (today `2026-08-08`), all session-scoped, none names `RCA-001` |

**Three independent blockers, any one of which is sufficient to stop implementation.** No product
code may be written. This is the workflow's §12 endpoint and a valid successful outcome.
