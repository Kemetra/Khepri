# Khepri Master Product Roadmap

**Status:** Proposed planning artifact. It is not a governing specification and grants no implementation authority.

**Recommended repository path after owner review:** `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.
**Baseline:** `Kemetra/Khepri` `main` at `cfca25490639b69d9db26b4ba0904977cfadad15` on 2026-08-13.

**Audience:** Ahmed Shaaban (owner and merge authority), Claude Code (planner and adversarial reviewer), and Codex (bounded-slice implementer).

**Supersedes for planning purposes:** `docs/khepri-commercial-roadmap.md`, the earlier advisory
plan. That document remains as a historical snapshot and should not be used to sequence work; its
gating claim about `KHEPRI-DEC-008` is stale, because that decision is now `active`.

## Verification record

This document was reviewed against `main` at `cfca25490639b69d9db26b4ba0904977cfadad15` before it
was added. Confirmed at that commit:

- the baseline SHA matches `origin/main`, and `migrations/versions/` has exactly one head
  (`20260813_0012`);
- `#150`, `#152`, and `#155` are open and match their descriptions here;
- `RCA-001` is `active` in `governance/registry.yaml`, and excludes persistent workspaces, report
  history, retention changes, multi-dataset storage, and billing;
- `KHEPRI-DEC-008` is `active`; it requires a target-selection artifact and deliberately selects no
  provider, region, or residency;
- the `#155` race is real: `LifecycleService` reads accounts, counts owners, and writes through
  three stores that each open their own session;
- the handoff gates and the CodeScene requirement match `AGENTS.md`.

Corrections applied as a result of that review are marked in place: the R1 predicate correction and
divergence note, the R4/R5 routing in the dependency graph, the migration-serialization note, the M1
scope note, the status convention in section 15, and the R2, R5, and OPS1 status rows.

Known drift **not** fixed here, because this program is docs-only:

- the `count_owners` docstring in `src/khepri/rca/persistence.py` describes only the enabled and
  not-purged conditions and omits the `credential_digest` clause the query actually applies. Code
  is correct; the docstring is incomplete. Record as an issue, fix alongside R1.
- `specs/001-rca-001-commercial-identity/` is still stale and still instructs agents not to execute.
  It also cites `governance/registries/decisions.yaml`, a path that no longer exists. That is the
  subject of `R0-02` and `R0-03` and is not addressed by this file alone.

**Update, 2026-08-13 (`R0-02`/`R0-03`/`R0-05`).** The second item is now addressed. Each stale
document carries a supersession banner, and three new files sit beside them: `SUPERSEDED.md` (the
delta), `STATUS.md` (per-requirement implementation status), and `NEXT-SLICES.md` (the issue-to-task
map). The originals were **not** rewritten, for the reason this document already gives about dated
advisories — and because they reason from a Constitution and an approval framework that commit
`2fc6c70` deleted, so a line-by-line patch would cite artifacts that no longer exist.

That reconciliation also corrected an assumption in this roadmap. Section 3 lists
`LifecycleService.assert_account_active` as the FR-008 chokepoint shipping unused, which is
accurate — but `src/khepri/rca/isolation.py:30-40` independently enforces account liveness,
membership, and uniform refusal at scope resolution. So FR-022, FR-023, FR-024, FR-025, and FR-028
are **partially implemented**, not absent, and `R6` extends an existing guard rather than
introducing the first one. `STATUS.md` records the evidence, and counts the gap: of the 30
requirements not fully implemented, 18 trace to three structural absences (no sessions, no
membership writes, no authorization layer — `R3`, `R2`, `R6`), 6 more to invitations and recovery
not existing (`R4`, `R5`), and the remaining 6 to narrower causes, four of which are the same one —
`IsolationService` is instantiated nowhere outside tests.

The first item stands, and `NEXT-SLICES.md` carries it forward as an `R1` follow-up.

**Update, 2026-08-13 (`R1` complete, `#155` closed at `c8c6edb`).** Four things this program
established that later programs inherit, recorded here because each was decided during R1 rather
than planned in this document:

1. **`OrganizationStore.apply_owner_reducing_change` is the seam `R2-06` reuses.** It opens one
   transaction, locks the account's owner-role memberships with `SELECT … FOR UPDATE`, counts
   effective owners on the locked rows, and either writes or refuses. `R2`'s revoke and demote
   must route through it rather than adding a second guard.
2. **CI now runs PostgreSQL, and a skipped concurrency test fails the build.** This resolves the
   open decision in `R1-01` §8 and `R1-02` §9 — option (a) was taken, as its own change
   (`8ed6e24`). `.github/scripts/require_concurrency_tests.py` refuses both a skip and a marker
   that matches nothing.
3. **A two-thread test is not a reliable proof here.** The two-owner concurrency test passed
   against the *broken* code; only the three-owner case failed. Under `READ COMMITTED` two
   contenders usually do not interleave badly enough. Any later concurrency proof — `R2-06`
   included — needs at least three contenders, or it can report green against a live defect.
4. **The effective-owner rule now has one SQL expression** (`_effective_owner_conditions`), and a
   parametrized test asserts it agrees with `Account.can_authenticate` across the four states
   that matter. The divergence `R1-01` was asked to resolve is now enforced rather than reviewed.

**North star:** Move Khepri from a secure bilingual single-assessment private-beta journey into a sellable enterprise retail analytics platform with durable organization workspaces, analysis history, period comparison, evidence-backed dashboards and reports, team administration, onboarding, billing, agency tenancy, recurring delivery, and a governed evidence-backed AI assistant.

---

## 1. Authority and operating rules

Before any agent changes code or governed artifacts, it must read:

1. `AGENTS.md`
2. `governance/CONSTITUTION.md`
3. `governance/registry.yaml`
4. The active governed specification for the requested slice
5. The relevant design, plan, issue, and prior merged PRs

Repository rules that control this roadmap:

- `governance/registry.yaml` is the source of truth for artifact identity, state, dependencies, and supersession.
- A branch or pull request is only a proposal. Ahmed Shaaban merging to `main` is the approval event.
- Product code must be linked to an active specification and delivered as a small, independently verifiable slice.
- Ambiguous identity, scope, privacy, data, runtime, and authorization boundaries fail closed.
- The required local handoff gates are:
  - `uv run khepri-gov validate`
  - `uv run ruff check .`
  - `uv run pytest`
- CodeScene is a required server-side PR gate. Every new file must score 10.00 and no tracked hotspot may decline.
- Parallel Alembic branches must not leave multiple heads. The later branch to merge must re-point its `down_revision`.
- Do not introduce a separate SPA or Node.js runtime under the current private-beta architecture. FastAPI, Jinja2, bundled CSS, and minimal bundled JavaScript remain the default until an active architecture decision says otherwise.
- RCA may orchestrate commercial identity and workspace behavior, but authoritative retail calculations must continue to originate in RRA fact contracts.
- Do not copy application code, catalogs, specifications, or governance records from Seshat-Platform.

---

## 2. Agent responsibility model

### Ahmed Shaaban

- Chooses product direction and unresolved owner decisions.
- Approves scope before implementation.
- Approves commit, push, PR, and merge actions.
- Is the only merge authority for governing changes.

### Claude Code

Primary role: planner and adversarial reviewer.

Claude Code should:

- inspect current repository truth before planning;
- reconcile the requested slice against active governance and merged code;
- identify missing decisions, unsafe assumptions, stale tests, race conditions, and scope creep;
- produce or review `spec.md`, `clarify.md`, `plan.md`, `tasks.md`, and test matrices;
- review Codex diffs and PRs adversarially;
- propose mutation tests or deliberate breakage checks for load-bearing guards;
- stop before implementation unless Ahmed explicitly assigns implementation.

### Codex

Primary role: bounded implementation.

Codex should:

- implement exactly one approved task or tightly coupled task group;
- start with repository state checks;
- write the expected failing test before implementation where practical;
- avoid unrelated refactors and framework changes;
- run all required validation;
- report changed files, task completion, tests, risks, and forbidden-scope confirmation;
- stop before commit, push, PR, or merge unless Ahmed explicitly authorizes those actions.

### Standard slice loop

1. Claude Code performs pre-flight and produces an implementation-ready plan.
2. Ahmed approves the bounded slice.
3. Codex implements and validates only that slice.
4. Claude Code reviews the diff, tests, scope, and security assumptions.
5. Codex addresses only approved review findings.
6. Ahmed decides whether to commit, push, open a PR, and merge.
7. The roadmap and task status are updated only after merge to `main`.

---

## 3. Current product baseline

Khepri already has:

- the governed RRA analysis engine;
- deterministic mapping, facts, narrative, and bilingual report contracts;
- encrypted report artifact publication;
- English and Arabic HTML, PDF, and Excel delivery;
- a responsive, accessible private-beta browser journey:
  - Upload
  - Review
  - Processing
  - Report
- durable RCA accounts, organizations, owner memberships, and opaque isolation scopes;
- sealed RCA record construction boundaries;
- account disablement, re-enablement, retention, purge, and sequential final-owner protection;
- `LifecycleService.assert_account_active`, which ships unused as the chokepoint `FR-008` requires.

Because that chokepoint already exists, `R3-05` wires an existing guard into session resolution
rather than designing a new one, and R3 is correspondingly cheaper than its task count suggests.

The baseline is not yet a complete enterprise product because it does not yet provide:

- complete RCA authentication sessions and recovery;
- complete membership role changes, revocation, and expiring audit events;
- organization invitations;
- the canonical commercial authorization checkpoint and active-organization context;
- a commercial application shell around the beta journey;
- durable customer workspaces or report history;
- multi-dataset comparison;
- an executive dashboard;
- public onboarding, billing, agency tenancy, recurring delivery, or an AI assistant.

Open repository issues at this baseline:

- `#150` - membership roles, revocation, final-owner protection, and 12-month membership audit events;
- `#155` - the final-owner guard and its write are not in one transaction;
- `#152` - selective RRA construction-boundary hardening.

---

## 4. Product end state

Khepri is considered enterprise-complete when an authorized customer can:

1. create or access a durable account;
2. enter one organization at a time under live authorization;
3. invite and administer team members safely;
4. create a durable workspace owned by the organization;
5. upload multiple governed datasets over time;
6. review mapping and provenance before analysis;
7. generate and retain complete bilingual reports under an approved retention policy;
8. compare periods, branches, categories, and other governed dimensions;
9. view an executive dashboard whose values originate only from governed RRA facts;
10. open evidence for every material claim;
11. manage plan, quota, subscription, and invoices;
12. optionally operate an agency portfolio with strict client isolation;
13. schedule recurring delivery through approved channels;
14. ask an AI assistant questions that can answer only from governed facts and must cite evidence;
15. use the service in a production environment with tested backup, restore, observability, incident response, security, and release controls.

---

## 5. Milestones and release gates

| Milestone | Product state | Exit gate |
| --- | --- | --- |
| M0 | Current private-beta baseline | Already on `main` |
| M1 | RCA-001 complete and concurrency-safe | All RCA-001 scenarios pass; `#150` and `#155` closed; canonical authorization exists |
| M2 | Commercial design-partner alpha | Account/org sign-in shell embeds the current analysis journey; team and org switching work |
| M3 | Durable workspace beta | Approved retention decision and workspace specification; history and deletion lifecycle work |
| M4 | Sellable analytics core | Multi-dataset comparison, executive dashboard, and evidence-backed report workspace work |
| M5 | Paid self-serve candidate | Public onboarding, entitlements, billing, quotas, and supportable operations work |
| M6 | Multi-tenant growth product | Agency portfolios and recurring delivery work without weakening isolation |
| M7 | Evidence-backed intelligence | Governed AI assistant passes grounding, privacy, refusal, and bilingual evaluation gates |
| M8 | Enterprise GA | Security review, restore exercises, capacity evidence, release controls, support procedures, and enterprise identity options are complete |

M1 is a milestone, not a slice. Its exit gate spans R1 through R6 — effectively the whole of
`RCA-001` — so the immediate actions in section 12 are the first steps of M1, not all of it. Do not
read "M1" as a single bounded piece of work.

The first genuinely sellable milestone is M4. M2 can support design partners, but it is still a single-assessment experience. M3 creates repeat use. M4 creates decision value.

---

## 6. Master dependency graph

```text
M0 CURRENT BASELINE
 |
 +--> R0 Roadmap and Spec Kit truth reconciliation
 |
 +--> R1 Transaction boundary and concurrent final-owner safety (#155)
       |
       +--> R2 Membership lifecycle and audit retention (#150)
       |     |
       |     +--> R4 Organization invitations    [side branch; not a gate on R6]
       |
       +--> R3 Authentication sessions
             |
             +--> R5 Account recovery            [side branch; not a gate on R6]

R2 and R3 together gate the authorization chain:

R6 Canonical authorization and active organization
 |
 +--> R7 RCA-to-RRA commercial bridge
       |
       +--> R8 Commercial application shell
             |
             M2 DESIGN-PARTNER ALPHA

Parallel after M1 safety:
  O1 Target selection and production operations track
  S1 Selective RRA construction-boundary triage (#152)
  U1 Design system and bilingual accessibility track

M2
 |
 +--> G2 New retention decision for durable retail content
 +--> G3 Active workspace/history specification
       |
       +--> W1 Workspace and durable analysis history
             |
             M3 DURABLE WORKSPACE BETA
             |
             +--> G4 Comparison specification split between RCA and RRA
                   |
                   +--> C1 Multi-dataset comparison facts and delivery
                         |
                         +--> D1 Executive dashboard and evidence workspace
                               |
                               M4 SELLABLE ANALYTICS CORE
                               |
                               +--> G5 Public onboarding and abuse-control specification
                               +--> G6 Billing and entitlement specification
                                     |
                                     +--> B1 Self-serve onboarding and billing
                                           |
                                           M5 PAID SELF-SERVE CANDIDATE
                                           |
                                           +--> G7 Agency tenancy specification
                                           +--> G8 Recurring delivery specification/runtime decision
                                                 |
                                                 +--> A1 Agency and scheduled delivery
                                                       |
                                                       M6 MULTI-TENANT GROWTH PRODUCT
                                                       |
                                                       +--> G9 AI assistant specification and provider/privacy decision
                                                             |
                                                             +--> AI1 Evidence-backed assistant
                                                                   |
                                                                   M7 EVIDENCE-BACKED INTELLIGENCE
                                                                   |
                                                                   +--> E1 Enterprise GA hardening
                                                                         |
                                                                         M8 ENTERPRISE GA
```

---

# PROGRAM R0 - Roadmap and truth reconciliation

## Goal

Make the repository's working plans accurately describe current `main` before another agent implements from them.

The existing Spec Kit working directory for RCA-001 predates the current active registry and merged slices. It must not remain an instruction source that says implementation is blocked or asks agents to rebuild code already on `main`.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| R0-01 | Snapshot current `main`, open issues, merged PRs, active governance, and implemented RCA-001 requirements | none | R0-02 | Current-state matrix |
| R0-02 | Reconcile `specs/001-rca-001-commercial-identity/` with current registry and merged code | none | R0-01 | Updated pointer, plan, tasks, analyze, checklist |
| R0-03 | Mark completed, partially complete, and unimplemented RCA-001 requirements without restating governed requirements | R0-01 | no | Requirement-to-code status matrix |
| R0-04 | Add this master roadmap as a non-governing planning artifact | R0-01 | R0-02 | Roadmap file with baseline SHA |
| R0-05 | Create issue/task mapping for the next three bounded slices only | R0-02, R0-03 | no | `#155`, `#150`, sessions plan mapped to task IDs |

## Required acceptance criteria

- `governance/specifications/RCA-001.md` remains the only authoritative RCA-001 requirement source.
- Working docs do not claim RCA-001 is draft or implementation-blocked when the registry says active.
- Merged work is not recreated under old task instructions.
- No product code, migration, or runtime behavior changes in this program.
- Governance validation, Ruff, and the relevant documentation checks pass.

## Parallelism

R0-01 and R0-02 may start in parallel, but R0-03 and R0-05 must use the same baseline commit and should merge as one docs-only proposal to avoid two competing task maps.

---

# PROGRAM R1 - Concurrent final-owner safety (#155)

## Goal

Make the FR-013 guard and the owner-reducing write one atomic decision before membership revocation and role demotion are implemented.

## Why it is first

The current sequential path is protected, but two concurrent calls can both pass the guard before either write commits. Membership revocation and role demotion will inherit the same race. Building membership behavior first would duplicate a known defect.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| R1-01 | Design probe: compare a shared transaction/unit-of-work, row locking, and database-enforced alternatives; state where the effective-owner predicate lives afterwards | R0 | S1 triage, U1 design audit | Approved design note; no code |
| R1-02 | Define the transaction-scoped service/store contract and fake semantics | R1-01 | test design | Interface and invariants |
| R1-03 | Add deterministic concurrent final-owner tests against PostgreSQL behavior | R1-02 | implementation skeleton | RED concurrency test |
| R1-04 | Implement one atomic guard-and-write boundary for account disablement | R1-03 | no | SQL and memory implementations agree |
| R1-05 | Prove non-owner-reducing operations do not acquire unnecessary locks | R1-04 | no | Focused regression/performance tests |
| R1-06 | Update lifecycle documentation and close `#155` after merge | R1-04, R1-05 | no | Issue closeout evidence |

## Design requirements

The selected mechanism must:

- keep the final-owner check and write in one database transaction;
- serialize competing owner-reducing operations for the same organization;
- leave unrelated organizations independent;
- preserve testability without allowing memory fakes to model weaker semantics than SQL;
- support account disablement, membership revocation, and owner-to-member demotion through one invariant;
- reconcile the two effective-owner definitions that already exist on `main` rather than adding a third;
- keep `Account.can_authenticate` as the FR-013 owner-counting predicate and `Account.can_act` as the
  liveness predicate for the lifecycle chokepoint and scope resolution, without collapsing the two;
- fail closed when the transaction or lock cannot establish the required state.

### Predicate correction (verified against `cfca254`)

An earlier draft of this roadmap told the implementer to use `Account.can_act` as the single
definition of a live account. That is the wrong predicate for FR-013 and following it would
reintroduce a defect already found and fixed:

- `src/khepri/rca/accounts.py` defines `can_act` as enabled-and-not-purged, and `can_authenticate`
  as `can_act and has_verifier`. Its docstring states that `can_act` "is deliberately weaker and
  stays that way" and that "only ownership needs the stronger question".
- `SqlOrganizationStore.count_owners` in `src/khepri/rca/persistence.py` filters on
  `credential_digest IS NOT NULL` for exactly that reason. Re-enablement leaves the verifier
  destroyed under `KHEPRI-DEC-015` §5, so disabling owner A, re-enabling A, then disabling owner B
  once left an organization whose only remaining owner could not authenticate.

R1 must preserve that distinction. Swapping the owner count onto `can_act` is a regression, not a
simplification.

### The divergence R1-01 must resolve

The effective-owner rule is already expressed twice on `main`: once as Python properties in
`accounts.py`, and once as a replicated SQL predicate in `count_owners`. A `SELECT ... FOR UPDATE`
design keeps it in SQL; a shared-session design may move it. R1-01 is therefore a reconciliation of
an existing divergence, not the preservation of a clean single definition. Plan the probe
accordingly.

## Stop conditions

Stop and return to design if implementation requires:

- broad changes across unrelated RRA stores;
- two independent final-owner guards;
- a check committed separately from the write;
- a SQLite-only proof for a PostgreSQL concurrency contract;
- weakening the exact owner/member role model.

---

# PROGRAM R2 - Membership lifecycle and expiring audit events (#150)

## Goal

Complete the two-role membership model, revocation, role changes, final-owner protection, attributable events, and 12-month audit retention.

## Required design decisions before code

1. The membership state row should not retain event attribution beyond the approved horizon.
2. Decide how existing `changed_by` and `changed_at` data is migrated into event history.
3. Decide whether organization creation emits an explicit membership-created event.
4. Use the sweeper pattern for bounded retention; lazy purge is not sufficient.
5. Keep initial organization creation atomic with its owner membership and required event.
6. Reuse R1's transaction boundary for revoke and demote operations.

## Recommended slice sequence

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| R2-01 | Finalize membership event model, migration semantics, and retention behavior | R1 design | R3 session design | Design and plan |
| R2-02 | Add `rca_membership_events` schema and migration; preserve one Alembic head | R2-01, R1 merged | no other migration branch | Schema only or schema plus safe backfill |
| R2-03 | Remove durable event attribution from `rca_memberships` after safe migration | R2-02 | no | State row contains only live membership state |
| R2-04 | Implement exact `owner` and `member` transitions through explicit operations | R2-03 | R3 domain-only work | Role-change service and tests |
| R2-05 | Implement membership revocation with non-interference tests | R2-04 | no | One membership changes; all others remain intact |
| R2-06 | Apply the shared final-owner transaction invariant to revoke and demote | R2-04, R1 | no | Concurrent protection tests |
| R2-07 | Emit content-free append-only events for create, role change, and revoke | R2-04, R2-05 | no | FR-014 event coverage |
| R2-08 | Implement 12-month membership-event sweeper and local/runtime wiring | R2-07 | U1 UI design | Retention enforcement |
| R2-09 | Add mutation/adversarial tests for role forgery, stale fakes, and event omission | R2-08 | no | Guard evidence |
| R2-10 | Close `#150` after merge and update RCA-001 status matrix | R2-09 | no | Closeout |

## Acceptance criteria

- Exactly two roles exist: `owner` and `member`.
- An organization cannot be created with a non-owner initial membership.
- A role change is an operation, never a field replacement.
- Revoking one membership changes no other membership.
- Revoke, demote, and disable all use the same effective-owner invariant.
- Every change records actor, target, prior role, next role, and timestamp in a content-free event.
- Event data is purged at the approved 12-month horizon without corrupting live membership state.
- Concurrent final-owner attempts leave at least one effective owner.

---

# PROGRAM R3 - Authentication sessions

## Goal

Create opaque, server-side commercial authentication sessions that resolve one actor, support revocation, and do not cache authorization facts that must remain live.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| R3-01 | Specify session identity, expiry, revocation, cookie boundary, and relation to existing RRA beta sessions | R0, active RCA-001 | R2 design | Session design |
| R3-02 | Add session domain types and exact state vocabulary | R3-01 | R4 invitation design | Domain tests |
| R3-03 | Add persistence and migration | R3-02, R3-09, R2 migration merged or coordinated Alembic re-point | no other migration merge | Session table/store |
| R3-04 | Implement create, resolve, expire, and revoke | R3-03 | R4 domain work | Session service |
| R3-05 | Enforce account activity on every actor resolution | R3-04 | no | Disabled accounts stop authorizing immediately |
| R3-06 | Add secure HttpOnly cookie handling and uniform invalid-session denial | R3-04 | U1 shell design | HTTP boundary |
| R3-07 | Add session cleanup and retention behavior under active decisions | R3-04 | no | Sweeper or lifecycle cleanup |
| R3-08 | Add tests proving no retail content, role, or stale membership authority is stored in session identity | R3-05 | no | Security evidence |
| R3-09 | Specify how external identity composes with R3's session model, resolving the FR-027 seam below | R3-01, KHEPRI-DEC-018 merged | R3-02 | Design addendum |
| R3-10 | Add the `IdentityProvider` seam and its verified-identity type | R3-09, R3-02 | no adapter work | Port + domain tests |
| R3-11 | Add the admitted-provider adapter behind the seam | R3-10, a provider admitted under the governing successor to KHEPRI-DEC-018 | no | Provider adapter |

### Task disposition — external identity (recorded 2026-08-14)

`KHEPRI-DEC-018` merged at `dcb63da`, **after** `R3-01` was designed and merged. `R3-01` therefore
describes Khepri authenticating its own credentials and minting its own session, and contains no
`IdentityProvider` concept. Three tasks are appended rather than existing ones being renumbered or
rewritten, because `R3-01` is merged and referenced from `NEXT-SLICES.md`, `STATUS.md`,
`docs/superpowers/specs/2026-08-14-r3-provider-evaluation-clerk.md`, and `KHEPRI-DEC-018`'s own
Consequences.

**No `R3` task is `SUPERSEDED`, and this is not an `R3` rewrite.** `KHEPRI-DEC-018` §11 admits no
provider and supersedes nothing; until a provider is admitted under §5, `FR-002` remains the only
authentication path, so `R3-01` … `R3-08` are exactly what Khepri needs. `R3-09` … `R3-11` are
additive and become relevant only on admission. `R3-11` cannot start before a provider is admitted;
`R3-09` and `R3-10` are provider-neutral and can.

**The seam `R3-10` builds** is fixed by `KHEPRI-DEC-018` §6: it exposes only whether a request
carries a verified identity, and the stable provider subject with its issuing provider. Vendor SDK
types stay behind the adapter and no module outside it imports them. Per the merged Clerk evaluation,
the authenticated subject is the verified token's `sub`, resolved locally through
`(provider, provider_subject) -> account_id`; a provider's `external_id`-equivalent is a portability
anchor, never the per-request subject.

**The open seam `R3-09` must resolve, stated rather than deferred silently.** `KHEPRI-DEC-018` §2
lets an admitted provider own "session or token issuance, refresh, and expiry" and says "Khepri
implements none of these for accounts authenticated through an admitted provider." But `FR-027`
requires "an authenticated session MUST carry at most one active organization", `FR-029` requires a
switch to "take effect for every subsequent authorization decision in that session", and
`KHEPRI-DEC-018` §3 makes the active organization (`FR-027`) Khepri-authoritative — a provider
assertion may not substitute for it.

Those hold together only if Khepri keeps **its own server-side state keyed to the verified provider
identity**, carrying the active organization and nothing a provider owns. What that state is called,
whether it reuses `R3-03`'s table, and how its lifetime relates to a provider token's are exactly
what `R3-09` settles. It is a design question, not a contradiction in either artifact: §2 assigns
*authentication mechanics* to the provider, and an active-organization pointer is not an
authentication mechanic. Recording it here prevents `R3-03` from writing schema that assumes one
answer, and `R3-03`'s `Depends on` cell now names `R3-09` so that ordering is encoded in the table
rather than only in this prose.

**Shape-affected if `R3-09` concludes Khepri holds no session row of its own:** `R3-02`, `R3-03`,
`R3-04`, and `R3-06` — `R3-06` most, since the cookie boundary is a different artifact when a
provider issues the token. None is blocked today, and `R3-02`'s domain types are needed under either
answer.

## Key constraints

- A session may identify one account and at most one active organization.
- Role and membership validity are resolved live at authorization time.
- Account disablement and membership revocation take effect without waiting for session expiry.
- Session error responses do not reveal whether a token once existed.
- RCA authentication sessions and RRA private-beta sessions must not be silently conflated.
- Where an admitted external identity provider authenticates the actor, the same constraints hold
  unchanged, and no provider organization, role, permission, or membership claim participates in any
  authorization decision (`KHEPRI-DEC-024` §4, carried forward unchanged by `KHEPRI-DEC-025` §1).
  Provider identity replaces credential verification, never authority.

### Task disposition — staged Clerk admission (recorded 2026-08-21)

`KHEPRI-DEC-024` superseded `KHEPRI-DEC-018` without rewriting the historical `R3-09` design, and
**`KHEPRI-DEC-025` now supersedes `-024`** — carrying every one of its sections forward unchanged and
additionally authorizing the implementation that `#240` merged. Clerk is admitted provisionally only
for an invite-only, non-paying private beta, and all sixteen evidence gates stand as a hard
commercial stop. The identity seam and session composition remain as merged: Clerk proves the
subject, the local link resolves a Khepri `account_id`, and Khepri holds the revocable
active-organization session used by the live authorization chain.

The admission did **not** make `R3-11` the next safe code change by itself. The Clerk private-beta
milestone, **merged at `15a8175` (`#240`)**, first resolved that prerequisite provider-neutrally:
account and link pre-provisioning share one transaction, and final-owner capability is a local
verifier or an external identity link. The persistence probe found the existing nullable verifier
columns and external-identity table sufficient, so that capability needs no schema change —
`KHEPRI-DEC-025` §2.4 adopts that finding as a decision, since `-024` §14 forbade concluding it.
**`-024` authorized none of that code**, which `-025` records rather than glosses: a
risk-acceptance record admitting a vendor is not a mandate to implement, and the two instruments
were conflated until the `#240` post-merge audit separated them. The companion
`docs/superpowers/specs/2026-08-21-clerk-first-identity-and-r5-disposition.md` defines its readiness
boundary. It assigns no task ID and settles neither whether a migration is required nor the
persistence schema. Private-beta provisioning is operator-controlled and creates the Khepri account
and external identity link before authentication; an unknown or unlinked provider subject fails
closed and no public self-service bootstrap is authorized.

---

# PROGRAM R4 - Organization invitations

## Goal

Issue, revoke, and redeem organization invitations with one role, one organization, one expiry, one-use semantics, and uniform failure behavior.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| R4-01 | Specify invitation state, expiry, revocation, intended role, and authenticated redemption | R2 design | R3 implementation | Invitation design |
| R4-02 | Add invitation domain and hashed secret handling | R4-01 | R3 domain work | Domain tests |
| R4-03 | Add persistence and migration after the current migration head is known | R4-02 | no parallel migration merge | Store and schema |
| R4-04 | Implement owner-authorized issuance and revocation | R4-03, R6-01 authorization matrix draft | R5 recovery design | Service tests |
| R4-05 | Implement one-time authenticated redemption into exactly one membership | R4-03, R2 merged, R3 actor resolution, R4-06 | no | Membership creation |
| R4-06 | Invalidate relevant unredeemed invitations when a membership is revoked, and on identity purge | R4-04 | no | FR-020 behavior |
| R4-07 | Add uniform expired, replayed, revoked, malformed, and foreign-scope tests | R4-05 | no | Security matrix |

---

# PROGRAM R5 - Account recovery

## Goal

Provide single-use, expiring, hash-only recovery that is externally uniform and revokes every pre-existing authentication session after success.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| R5-01 | Specify recovery lifecycle, delivery abstraction, expiry, and uniform initiation response | R3 design | R4 implementation | Recovery design |
| R5-02 | Add recovery secret domain and persistence | R5-01, migration head known | no migration conflict | Store and schema |
| R5-03 | Implement uniform recovery initiation for existing and unknown accounts | R5-02 | no | Anti-enumeration tests |
| R5-04 | Implement one-use credential replacement | R5-02 | no | Recovery completion |
| R5-05 | Revoke every existing session in the same successful recovery transaction | R5-04, R3 | no | Session invalidation tests |
| R5-06 | Add replay, expiry, concurrent use, and logging tests | R5-05 | no | Security evidence |

### Task disposition — Clerk-owned credentials (recorded 2026-08-21)

The table above records the Khepri-credential sequence designed by merged `R5-01`; it remains useful
if credential ownership returns to Khepri. Under provisional Clerk admission, recovery follows the
credential owner:

- **`R5-02` DEFER** — no Khepri recovery-secret domain, table, or migration while Clerk owns the
  credential;
- **`R5-03` DEFER** — Clerk owns initiation, delivery, and its anti-enumeration behavior;
- **`R5-04` DEFER** — Clerk owns one-use credential replacement;
- **`R5-05` REFRAME** — Khepri revalidates account state, revokes every Khepri session, and records
  content-free security evidence after provider recovery; and
- **`R5-06` REFRAME** — prove those local consequences, idempotency, disabled/purged refusal, and
  identity-link integrity rather than reproducing Clerk recovery internals.

The Clerk credential change and Khepri consequence cannot share the transaction `R5-01` designed
for local credentials. `KHEPRI-DEC-024` §7 accepts that cross-system residual only for non-paying
private beta and keeps it open for commercial admission; `KHEPRI-DEC-025` §1 carries that acceptance
forward unchanged. Details and the evidence boundary are in
`docs/superpowers/specs/2026-08-21-clerk-first-identity-and-r5-disposition.md`. **The reframed
consequence is merged but not composed** — see the `R5` row in §16 and `KHEPRI-DEC-025` §4.

---

# PROGRAM R6 - Canonical authorization and active organization

## Goal

Make one canonical authorization checkpoint resolve the actor, active organization, live membership, live role, requested object scope, and permitted action.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| R6-01 | Define the protected-action catalog and authorization matrix | R2 role model, R3 session design | R4/R5 work | Matrix and contract |
| R6-02 | Define an authorization context that cannot be constructed by handlers | R6-01 | static test design | Context boundary |
| R6-03 | Implement active-organization selection and switching | R3, R2 | U1 shell implementation contract | Session/context behavior |
| R6-04 | Implement live membership and role resolution at every protected action | R6-02, R6-03 | no | Canonical resolver |
| R6-05 | Add owner/member/non-member/unauthenticated exhaustive action matrix | R6-04 | no | Matrix tests |
| R6-06 | Add cross-organization read and mutation indistinguishability tests | R6-04 | no | Isolation evidence |
| R6-07 | Add stale-session tests for revocation, demotion, and disablement | R6-04 | no | Immediate authorization change |
| R6-08 | Add static or architectural tests making bypassing the resolver unreachable | R6-04 | no | Chokepoint evidence |

## Critical rule

Object identifiers never grant authority. Every object lookup must be scoped from the authorization result, not trusted from a route parameter.

---

# PROGRAM R7 - Commercial bridge to the existing RRA journey

## Goal

Map an authenticated RCA actor and active organization to the existing opaque RRA isolation scope without moving authoritative retail behavior into RCA.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| R7-01 | Define how a commercial authorization context opens or resumes an RRA analysis session | R6, current RRA contracts | U1 UI work | Bridge contract |
| R7-02 | Resolve organization to its stable opaque owner scope | R6 | no | Bridge service |
| R7-03 | Ensure disabled/revoked actors cannot use an existing analysis session | R3, R6 | no | Live auth tests |
| R7-04 | Preserve RRA independence and existing beta mode | R7-01 | no | Regression tests |
| R7-05 | Add commercial API endpoints only through the canonical resolver | R7-02, R6 | U1 templates | HTTP integration |
| R7-06 | Add end-to-end cross-org and nonexistence-indistinguishability tests | R7-05 | no | Security E2E |
| R7-07 | Implement the RRA scoped-session entry point and the RCA bridge that calls it | R7-02 merged, KHEPRI-DEC-020 §3 lifted or a successor authorizing product code | no | Bridge service |

### Task disposition — the schema conflict and its migration (recorded 2026-08-17)

`R7-02`'s row above describes the slice as it was designed: one task producing a "Bridge service".
It shipped as **two**, and the row is left as written rather than edited, because `R7-02` is merged
and cited from `STATUS.md`, `KHEPRI-DEC-019`, `KHEPRI-DEC-020`, and
`docs/superpowers/specs/2026-08-17-r7-02-schema-cardinality-finding.md`.

What actually happened:

1. `R7-02` probed before implementing and found that `KHEPRI-DEC-019` contradicted itself — its §2
   admitted an entry point taking a caller-supplied `owner_id`, while its §5 forbade any schema
   change, and `rra_beta_sessions.UNIQUE (owner_id)` made those incompatible. It recorded the
   finding (`9bfae82`) instead of shipping an entry point whose second call raises `IntegrityError`.
2. `KHEPRI-DEC-020` (`2c9e0c1`) superseded `KHEPRI-DEC-019` and authorized **the migration and its
   ORM change, explicitly and only** — its §3 reads "No product code beyond the migration and its
   ORM change. No bridge service and no entry-point implementation are authorized here."
3. `R7-02` therefore delivers the migration (`20260817_0017`) and stops there.

**`R7-07` is appended for the bridge itself.** It was blocked on governance rather than on code —
`KHEPRI-DEC-020` §1 re-enacted the *admitted shape*, so the design was settled, but §3 withheld
authorization for the code. **`KHEPRI-DEC-021` lifts exactly that bullet** and is the governing
record for the slice.

`KHEPRI-DEC-021` settles three things this disposition previously left open, and they change what
`R7-07` builds:

1. **The bridge lives in `khepri.runtime`**, per its §3 — rejecting *both* options the merged
   documents offered. `R7-01` §3 recommended `khepri.local`; `pyproject.toml:66` excludes that
   package from the wheel the OCI image installs, its own `__init__` says "none of it is deployed",
   and `Dockerfile:72` validates `khepri.runtime` instead — so a bridge there is unreachable from the
   role that will serve `R7-05`. `khepri.runtime` is the packaged composition root. It is the first
   `khepri.rca` import into that package, admitted deliberately: a composition root exists to know
   both sides. The RCA-side option `R7-01` §3 warned about stays rejected.
2. **The scope is four parts, not one.** `rra/sessions.py` has no invitation-free session insert —
   `BetaSessionRow` is written only inside `redeem_invitation` — so the entry point admitted by
   `KHEPRI-DEC-019` §2 had nowhere to persist. `KHEPRI-DEC-021` §2 authorizes the entry point, an
   additive `SessionStore` Protocol method with its `SqlSessionStore` implementation, a resume
   lookup scoped by **`(owner_id, session_id)`** — never `owner_id` alone, which is non-unique after
   `20260817_0017` and would select an arbitrary or stale analysis — and the bridge.
3. **The boundary assertion is a flat prohibition, not an allowlist**, which follows from (1).

The note this paragraph replaces said the bridge's discipline was "no `rra_` import inside
`src/khepri/rca/`". That framing is superseded by `KHEPRI-DEC-021` §3: with the bridge in
`khepri.runtime`, `khepri.rca` imports **no** `khepri.rra` module at all, mirroring the existing
prohibition rather than carving an exception from it. What remains correct is the *gap* it named:
`test_rca001_boundary.py` asserts the **RRA→RCA** direction only
(`test_no_rra_module_imports_rca`), `STATUS.md`'s `FR-036` row records that no test asserts
RCA→RRA, and adding the missing direction belongs in `R7-07`.

**Closed by `R7-07` at `d93b844`, with one departure.** Both directions are now asserted and
mutation-verified, but in `test_r707_commercial_bridge.py` with an independent AST scan rather than
as the mirror of `find_rca_import_offenses` that `KHEPRI-DEC-021` §3's consequences ask for. The
prohibition holds either way; what it costs is a second boundary scanner where the record expected
one parameterised helper reused, which is a consolidation candidate rather than a gap in coverage.
`find_rca_import_offenses(source, package)` is already parameterised on `package`, so the mirror is
small. `isolation.py:3-8`'s `TYPE_CHECKING` pattern remains the idiom for needing a type without a
runtime import, though a `khepri.runtime` bridge should not need it.

## Non-goals

- No durable report history.
- No changed retail-content retention.
- No new authoritative calculation in RCA.
- No public signup.
- No billing.

---

# PROGRAM R8 - Commercial application shell v1

## Goal

Wrap the existing production journey in an authenticated, organization-aware product shell without pretending that history, billing, or dashboard data exists yet.

## Product surfaces

- Sign in
- Recovery
- Organization selection/switching
- Team and invitation management
- Account settings
- Organization settings within RCA-001 scope
- New analysis entry
- Existing Upload -> Review -> Processing -> Report journey
- Current-session unavailable, expired, deleted, and unauthorized states

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| R8-01 | Produce shell information architecture and design tokens | R3/R6 contracts drafted | R2-R7 backend work | UI design only |
| R8-02 | Build shared authenticated layout, navigation, RTL/LTR behavior, and language parity | R8-01, R3 HTTP | R7 API | Templates/assets |
| R8-03 | Build sign-in, recovery, and invalid-session surfaces | R3, R5 | R8-04 | Auth UI |
| R8-04 | Build organization switcher and no-membership state | R6 | R8-03 | Org context UI |
| R8-05 | Build team/invitation management surfaces | R2, R4, R6 | R8-03 | Team UI |
| R8-06 | Embed or route into the existing journey from New Analysis | R7 | R8-05 | Integrated flow |
| R8-07 | Add responsive, accessibility, keyboard, bilingual, and visual regression tests | R8-02 through R8-06 | no | UI quality evidence |
| R8-08 | Add content-free product activation telemetry | approved telemetry scope | R8-07 | Funnel metrics without customer content |

**`R8-03` under Clerk.** It must not recreate Khepri password or recovery forms for Clerk-backed
accounts. Its provider-stage responsibility is the authentication handoff, uniform unavailable
state, and return to the Khepri shell only after the local session or recovery consequence succeeds.
Organization selection and every authorized product surface continue to read Khepri state.

## UI guardrails

- Preserve the current server-rendered architecture.
- Do not build empty dashboard widgets, fake history, fake charts, or inactive enterprise controls.
- Reuse the current four-step journey as a workflow, not as the full product shell.
- Keep Arabic and English state/action coverage equal.
- No external fonts, analytics scripts, CDNs, or runtime assets.

## M2 exit gate

A design partner can sign in, select an organization, manage basic membership/invitations, start one assessment, complete the current journey, and access the complete report under live authorization.

---

# CROSS-CUTTING TRACK OPS1 - Production target and operations

This track begins after R1 closes concurrent final-owner risk and continues through every milestone.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| OPS1-01 | Re-price and select provider, region, residency, and products in the required target-selection artifact | owner decision (`KHEPRI-DEC-008` is active and requires this artifact; it deliberately selects no provider, region, or residency) | R2-R8 | Approved environment descriptor |
| OPS1-02 | Provision a non-production environment through CI only | OPS1-01 | late R7/R8 | Staging environment |
| OPS1-03 | Configure PostgreSQL, private object storage, secret store, TLS ingress, image registry, and OTLP/log destinations | OPS1-02 | R8 | Environment contract evidence |
| OPS1-04 | Run migration, backup, restore, deletion, and envelope-encryption read-back exercises | OPS1-03 | no | Recovery evidence |
| OPS1-05 | Run the governed benchmark and capacity tests | OPS1-03 | no | Target performance evidence |
| OPS1-06 | Add content-free alerts, dashboards, runbooks, and break-glass evidence | OPS1-03 | R8 | Operability |
| OPS1-07 | Define release, rollback, database migration, and incident procedures | OPS1-04 | R8 | Pilot runbook |

## Deployment stop gate

Do not serve concurrent external users before R1 is merged and its concurrency tests pass.

---

# CROSS-CUTTING TRACK S1 - Selective RRA construction hardening (#152)

## Goal

Harden only RRA records that carry security or integrity invariants a direct store caller could violate.

## Sequence

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| S1-01 | Inventory RRA records and classify security-invariant records vs plain data carriers | none | R0/R1 | Triage report only |
| S1-02 | Identify store seams that accept caller-controlled opaque identifiers or derived security material | S1-01 | R2/R3 | Risk-ranked list |
| S1-03 | Select the smallest independently verifiable hardening slice | S1-02 | no | Approved plan |
| S1-04 | Implement one record family at a time with accidental-bypass tests | S1-03 | avoid active RRA feature branches | Bounded PRs |
| S1-05 | Close `#152` only after every classified high-risk record is addressed or explicitly accepted | S1-04 | no | Closeout |

## Non-goal

Do not seal every dataclass. Ceremony without a protected invariant is not value.

---

# PROGRAM G2/G3 - Governance for durable workspaces and history

No workspace/history implementation may begin under RCA-001 because that specification explicitly excludes persistent customer workspaces, report history, retention changes, and multi-dataset storage.

## Governance tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| G2-01 | Define the product purpose and data classes for durable retail inputs, derived facts, reports, metadata, and deletion evidence | M2 learnings | workspace UX research | Data inventory |
| G2-02 | Decide retention defaults, customer deletion, organization closure, backup behavior, export, and legal/operational ownership | G2-01 | no | Owner decisions |
| G2-03 | Draft and activate a retention decision for durable commercial retail content | G2-02 | workspace spec drafting | Active decision |
| G3-01 | Draft the next RCA workspace/history specification | G2-01 | G2-03 | Governed spec proposal |
| G3-02 | Clarify workspace ownership, analysis identity, dataset versions, immutability, history visibility, and deletion semantics | G3-01 | UI IA | Clarification record |
| G3-03 | Produce plan, tasks, analysis, checklist, and approval-ready registry change | G3-02, G2-03 | no | Implementation-ready active spec |

## Required product decisions

- Is retention fixed, plan-based, or organization-configurable?
- What is deleted when a user deletes an analysis, a workspace, or an organization?
- Are original uploads retained, or only governed derived artifacts?
- What is the customer export contract?
- How are historical analyses made immutable and reproducible?
- What is the relationship between a workspace, dataset period, analysis run, fact package, and report bundle?
- What happens when mapping semantics change between periods?

---

# PROGRAM W1 - Durable workspaces and analysis history

## Goal

Turn a one-time assessment into a repeat-use organization workspace while preserving isolation, provenance, reconciliation, and approved retention.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| W1-01 | Define workspace, dataset version, analysis run, and retained artifact domain contracts | active G3 spec | UI contract design | Domain model |
| W1-02 | Add persistence and one-head migrations | W1-01 | no parallel schema merge | Database model |
| W1-03 | Extend encrypted object namespaces and metadata under the approved retention decision | W1-01, G2 active | W1-02 tests | Storage lifecycle |
| W1-04 | Implement organization-scoped create, read, list, delete, and resume operations through R6 authorization | W1-02, R6 | W1-05 UI skeleton | Workspace service/API |
| W1-05 | Build Overview, Workspaces, Analysis History, and New Analysis product pages | stable W1 API contract | W1-04 | UI |
| W1-06 | Preserve immutable provenance and fact/report bindings across history | W1-03, W1-04 | no | Reproducibility evidence |
| W1-07 | Implement immediate deletion, retention sweep, backup-aware lifecycle, and deletion evidence | W1-03, G2 | no | Lifecycle enforcement |
| W1-08 | Add cross-org, expired, deleted, partial, corrupt, and restore-path tests | W1-04 through W1-07 | no | Security/recovery evidence |
| W1-09 | Add history-specific content-free metrics | W1-05 | no | Repeat-use measurement |

## M3 exit gate

An organization can retain multiple completed analyses under an active retention decision, view history, reopen a complete report, and delete content with correct evidence. No comparison is required yet.

---

# PROGRAM G4/C1 - Multi-dataset comparison

## Governance split

Comparison crosses family responsibilities:

- RCA owns workspace accumulation, period selection, and commercial user flow.
- RRA must own authoritative comparison facts, calculations, cited narrative, and report surfaces.

Do not put comparison arithmetic into RCA controllers, UI code, SQL read models, or client JavaScript.

## Governance tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| G4-01 | Specify comparison actors, compatible period semantics, user scenarios, and success criteria | M3 | UI research | Product scope |
| G4-02 | Draft/activate the required RRA comparison fact specification or approved extension | G4-01 | RCA orchestration spec | RRA authority |
| G4-03 | Draft/activate the RCA comparison orchestration specification | G4-01 | G4-02 | RCA authority |
| G4-04 | Freeze versioned comparison input/output contracts before parallel implementation | G4-02, G4-03 | no | Contract baseline |

## Implementation tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| C1-01 | Add period and dataset-version semantics in the workspace domain | G4-04, W1 | RRA test fixture design | Period model |
| C1-02 | Detect compatibility, missing dimensions, mapping drift, and incomparable inputs | C1-01 | no | Fail-closed compatibility contract |
| C1-03 | Build versioned immutable RRA comparison fact package | G4-04, C1-02 | RCA API work after contract freeze | Comparison facts |
| C1-04 | Build deterministic bilingual comparison narrative with citations/refusals | C1-03 | report renderer work | Narrative |
| C1-05 | Add comparison HTML/PDF/Excel surfaces and reconciliation | C1-03 | C1-04 | Deliverables |
| C1-06 | Add authorized comparison orchestration API in RCA | C1-01, stable C1-03 contract | C1-04/C1-05 | API |
| C1-07 | Build Compare flow and results UI | C1-06, stable surface contracts | accessibility tests | UI |
| C1-08 | Add exactness, provenance, cross-org, mixed-version, and unsupported-comparison tests | all above | no | Evidence |

## M4 prerequisite

No executive dashboard work should begin until the comparison fact contract is stable and versioned.

---

# PROGRAM D1 - Executive dashboard and evidence-backed report workspace

## Goal

Expose repeatable decision value without duplicating calculations outside governed RRA facts.

## Product surfaces

- Executive overview
- Period-over-period change summary
- Branch performance
- Category/product performance where governed
- Exceptions and limitations
- Recent analyses and comparisons
- Interactive report navigation
- Evidence panel for each material claim
- Download and expiry/retention status

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| D1-01 | Define dashboard information architecture and exact fact-source map | C1 stable | design system work | No-calculation UI contract |
| D1-02 | Add versioned dashboard read model assembled only from governed fact packages | D1-01 | evidence API | Read model |
| D1-03 | Build Executive Overview and change summary | D1-02 | D1-04 | UI module |
| D1-04 | Build Branch, Category, and Exception modules only where governed facts exist | D1-02 | D1-03 | UI modules |
| D1-05 | Build evidence API and evidence drawer linking claims to facts, citations, provenance, and caveats | C1 facts | D1-03/D1-04 | Evidence experience |
| D1-06 | Refactor the report page into a navigable report workspace without changing fact authority | D1-05 | no | Report UX |
| D1-07 | Add cache and performance behavior scoped by organization and fact-package version | D1-02 | no | Performance |
| D1-08 | Add Arabic/English parity, RTL, accessibility, visual regression, and narrow-layout tests | D1-03 through D1-06 | no | Quality evidence |
| D1-09 | Add dashboard activation and repeat-use telemetry without content | D1-03 | no | Product measurement |

## M4 exit gate

A paying design partner can return to a workspace, compare periods, view an executive dashboard, inspect evidence for material claims, and download reconciled reports.

---

# PROGRAM G5/ON1 - Public onboarding and team administration

Public signup is excluded from RCA-001 and needs its own active specification.

## Governance tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| G5-01 | Define self-serve vs assisted onboarding, verification, organization bootstrap, abuse controls, and support boundaries | M4 product evidence | billing research | Product decisions |
| G5-02 | Specify public signup, account verification, organization creation, invitation acceptance, and failure behavior | G5-01 | G6 pricing spec | Active specification |
| G5-03 | Decide email delivery, anti-abuse, rate-limit, domain, and operational provider boundaries | G5-01 | no | Architecture/operations decision if needed |

## Implementation tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| ON1-01 | Build public account verification and signup | active G5, R3/R5 | organization bootstrap | Auth flow |
| ON1-02 | Build first-organization bootstrap and first-owner guarantee | ON1-01, R1/R2 | team UI polish | Org onboarding |
| ON1-03 | Build guided first-analysis onboarding | ON1-02, R8/W1 | billing integration later | Activation flow |
| ON1-04 | Complete team, invitation, role, and membership administration UI | R2/R4/R6 | ON1-03 | Admin UX |
| ON1-05 | Add account and organization audit views using approved content-free events | active retention authority | no | Audit UX |
| ON1-06 | Add abuse, throttling, enumeration, replay, and accessibility tests | ON1-01 through ON1-05 | no | Security evidence |

---

# PROGRAM G6/B1 - Billing, entitlements, quotas, and invoicing

Billing begins only after M4 proves repeat value. Do not monetize a product whose core repeat-use loop is incomplete.

## Governance and product decisions

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| G6-01 | Define plans, entitlement vocabulary, billable units, free/trial behavior, and overage policy | M4 evidence | G5 onboarding | Product catalog |
| G6-02 | Define cancellation, downgrade, payment failure, refunds, invoices, tax responsibility, and data-retention consequences | G6-01 | provider evaluation | Lifecycle rules |
| G6-03 | Select billing provider behind an adapter and approve required data flow | G6-01, G6-02 | no | Architecture/provider decision |
| G6-04 | Activate billing/entitlement specification | G6-01 through G6-03 | no | Implementation authority |

## Implementation tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| B1-01 | Implement plan catalog and versioned entitlement model | active G6 | usage meter design | Domain |
| B1-02 | Implement content-free usage metering with idempotent events | B1-01 | billing adapter | Metering |
| B1-03 | Implement canonical entitlement checkpoint separate from authorization but required by protected paid actions | B1-01, R6 | billing adapter | Entitlement service |
| B1-04 | Implement billing-provider adapter and idempotent webhook ingestion | B1-01, G6 provider decision | B1-02/B1-03 | Billing integration |
| B1-05 | Implement quota enforcement at job creation and retained-resource boundaries | B1-02, B1-03 | UI | Enforcement |
| B1-06 | Build plan, usage, checkout, payment status, invoice, and cancellation UI | B1-04, B1-05 | no | Billing UX |
| B1-07 | Add replay, out-of-order webhook, downgrade, payment-failure, quota-race, and cross-org billing tests | all above | no | Reliability evidence |

## M5 exit gate

A new customer can sign up, create an organization, complete a first analysis, select a plan, pay, see usage, receive invoices, and be constrained by correct entitlements and quotas.

---

# PROGRAM G7/A1 - Agency tenancy

## Goal

Let an agency serve multiple client organizations without creating a second path around organization isolation.

## Governance decisions

- Is an agency itself an organization, a portfolio over client organizations, or a distinct tenant type?
- Which actor can create, attach, detach, and delegate a client?
- What can a client owner see about the agency?
- Which branding elements may be customized without weakening provenance or disclosures?
- How does billing allocate between agency and client?

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| G7-01 | Activate agency tenancy and delegated-access specification | M5, owner decisions | recurring-delivery spec | Authority |
| A1-01 | Implement portfolio and client-association domain | active G7 | UI design | Domain |
| A1-02 | Extend canonical authorization with explicit delegated-access rules | A1-01, R6 | no other auth refactor | Authorization |
| A1-03 | Build client switcher and portfolio overview | A1-02 | billing allocation | UI |
| A1-04 | Implement bounded white-label configuration that cannot remove governed disclosures/evidence | G7 | A1-03 | Branding |
| A1-05 | Add exhaustive cross-client read/mutation/nonexistence tests | A1-02 through A1-04 | no | Isolation evidence |

---

# PROGRAM G8/S2 - Recurring scheduled delivery

## Goal

Schedule and deliver reports through approved channels without weakening job reliability, authorization, retention, or evidence.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| G8-01 | Define schedule ownership, trigger inputs, time zones, pause/cancel, recipient authorization, and delivery channels | M5 | G7 agency spec | Product rules |
| G8-02 | Activate scheduling specification and any required runtime/provider decision | G8-01 | no | Authority |
| S2-01 | Add schedule domain, persistence, and one-head migration | active G8 | delivery adapter design | Schedule store |
| S2-02 | Add scheduler/claim worker using durable state and bounded retries | S2-01 | UI | Runtime |
| S2-03 | Add secure delivery-channel adapters and recipient checks | S2-01, G8 | S2-02 | Delivery |
| S2-04 | Add schedule management UI | S2-01 | S2-02/S2-03 | UX |
| S2-05 | Add DST, time-zone, duplicate-trigger, revoked-recipient, retry, deletion, and audit tests | all above | no | Reliability evidence |

## Parallelism with agency

Agency and recurring-delivery specifications may be drafted in parallel. Code may proceed in parallel only if one branch does not modify the same authorization, migration, or job-state hotspot. Otherwise serialize the implementations.

---

# PROGRAM G9/AI1 - Evidence-backed AI assistant

## Goal

Allow a user to ask business questions while ensuring every answer is grounded in governed facts, cites evidence, and refuses unsupported claims.

## Preconditions

- M4 evidence graph and comparison contracts are stable.
- The AI product scope is governed.
- Provider, data handling, retention, and model allowlist decisions are active.
- No raw rows, filenames, secrets, opaque owner/session identifiers, or storage locations leave approved boundaries.

## Governance tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| G9-01 | Define supported question classes, excluded actions, answer contract, citations, and refusal behavior | M4/M6 evidence | provider evaluation | Product spec |
| G9-02 | Decide provider/model/data-processing/ZDR/retention and adapter constraints | G9-01 | evaluation design | Active architecture decision |
| G9-03 | Activate AI assistant specification | G9-01, G9-02 | no | Implementation authority |

## Implementation tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| AI1-01 | Build a read-only query context from governed facts, safe labels, caveats, and citation identifiers only | active G9 | evaluation fixtures | Context contract |
| AI1-02 | Build provider-neutral adapter and pinned request/response schema | G9-02, AI1-01 | validator | Adapter |
| AI1-03 | Validate every numeric, categorical, temporal, and causal claim against supplied facts | AI1-01 | AI1-02 | Claim validator |
| AI1-04 | Require citations/evidence for every material claim and refuse unsupported questions | AI1-03 | UI | Grounding |
| AI1-05 | Add English/Arabic answer parity and direction-safe rendering | AI1-04 | evals | Bilingual assistant |
| AI1-06 | Build adversarial evaluation suite for unsupported numbers, prompt injection, cross-org leakage, unsafe labels, missing evidence, and refusal quality | AI1-01 through AI1-05 | no | Evaluation gate |
| AI1-07 | Build Ask Khepri UI with evidence navigation and explicit limitations | AI1-04, AI1-05 | no | Product UX |

## Non-goals for the first AI slice

- No autonomous actions.
- No write access.
- No customer-authored formulas.
- No forecasting.
- No provider-hosted files, vector stores, threads, or hidden state.
- No answer that cannot be reconstructed from cited governed facts.

---

# PROGRAM E1 - Enterprise GA hardening

## Goal

Make the product supportable, recoverable, secure, and reviewable for enterprise customers.

## Tasks

| ID | Task | Depends on | Parallel | Output |
| --- | --- | --- | --- | --- |
| E1-01 | Decide enterprise identity roadmap: MFA baseline, SSO/SAML, SCIM, domain controls, and provider abstraction | M5 product needs | agency/scheduling | Identity decision |
| E1-02 | Implement approved enterprise identity slice behind existing authentication/authorization boundaries | E1-01 | ops | Identity controls |
| E1-03 | Complete account/org export, closure, retention, and deletion workflows under active decisions | workspace/billing/agency specs | no | Lifecycle completeness |
| E1-04 | Run external or independent security review and resolve approved findings | feature complete | capacity work | Security evidence |
| E1-05 | Run load, soak, concurrency, failover, restore, and deletion-under-failure exercises | production target | security review | Capacity/recovery evidence |
| E1-06 | Define SLA/SLO, on-call, incident severity, support escalation, and customer communication | observability stable | E1-04/E1-05 | Operating model |
| E1-07 | Finalize release channels, migration rehearsal, rollback, feature flags, and emergency disablement | E1-05 | documentation | Release safety |
| E1-08 | Produce enterprise security, privacy, data-flow, retention, and operational documentation | all above | no | Customer readiness |

## M8 exit gate

Enterprise GA requires proof, not only code:

- current security review;
- successful backup and restore exercises;
- verified deletion after restore;
- capacity and concurrency evidence;
- runbooks and incident procedures;
- release/rollback rehearsal;
- support ownership;
- accurate security and privacy documentation;
- no unresolved critical or high-risk authorization, isolation, retention, or recovery finding.

---

## 7. Parallel work policy

### Work that may run in parallel

1. Governance/specification work for the next milestone may run while the current milestone's implementation is stabilizing. Implementation must wait until the required artifact is active.
2. UI information architecture and visual design may run while backend contracts are being implemented, but UI code should wait until API and state vocabularies are stable.
3. RRA comparison facts and RCA comparison orchestration may be implemented in parallel after one versioned contract is frozen.
4. Production operations may run in parallel with product work after R1 closes the deployment-blocking concurrency risk.
5. Selective RRA hardening triage may run at any time; implementation should avoid overlapping active RRA feature hotspots.
6. Test fixture design, adversarial cases, and accessibility plans may run in parallel with implementation.

### Work that must be serialized

1. Two branches that both change the RCA transaction/store seam.
2. `#155` and membership owner-reducing behavior as independent implementations.
3. Two migrations that both assume they are the current Alembic head without a re-point plan.
4. Two branches that both modify `src/khepri/rca/records.py`, `persistence.py`, the same central template/CSS file, or `authorization.py` once R6 creates it (it does not exist at this baseline).
5. Comparison calculation code and the fact contract it depends on.
6. Billing enforcement and an unsettled entitlement vocabulary.
7. Agency authorization and another broad authorization refactor.
8. AI answer generation and an unsettled evidence/citation contract.
9. Public signup code before anti-abuse and recovery behavior are governed.
10. Durable content code before the retention decision is active.

### Migrations are strictly serial

`R2-02`, `R3-03`, and `R4-03` add migrations; the original Khepri-credential shape of `R5-02`
would add one too, but that task is deferred while Clerk owns credentials. Any future R5 recovery
migration remains subject to the same serial rule. Combined with the one-persistence-branch limit
below, schema work is strictly sequential regardless of what the per-program "Parallel" columns
suggest. Those columns describe design, domain, and test work that may overlap — not schema merges.
The later branch to merge re-points its `down_revision`. No migration need or absence is inferred
for the future external-identity account slice; its persistence probe must decide that separately.

### Recommended concurrency limit

For this repository and one owner, keep at most:

- one high-risk persistence/authorization implementation branch;
- one independent UI or domain branch;
- one docs/governance planning branch.

More parallel branches create migration, spec, and review collisions faster than they create throughput.

---

## 8. Critical path

The minimum critical path to a sellable Khepri product is:

```text
R0 truth reconciliation
-> R1 concurrent final-owner safety
-> R2 membership lifecycle
-> R3 sessions
-> R6 canonical authorization
-> R7 commercial RRA bridge
-> R8 commercial shell
-> G2/G3 retention and workspace authority
-> W1 history
-> G4 comparison authority
-> C1 comparison facts
-> D1 dashboard and evidence workspace
-> M4 sellable analytics core
```

Invitations and recovery are required for a complete RCA-001 experience but may run on side branches after their dependencies stabilize:

```text
R2 -> R4 invitations
R3 -> R5 recovery
```

Billing, agency, recurring delivery, and AI are not on the shortest path to first sellable value.

---

## 9. Pull request packaging rules

Every implementation PR should contain:

1. One bounded product outcome.
2. The active specification and exact requirements/scenarios it implements.
3. Explicit non-goals.
4. The design decision or plan it follows.
5. Test-first evidence and mutation/adversarial evidence for load-bearing guards.
6. Migration chain status when applicable.
7. Parallel-branch collision notes.
8. Validation results:
   - governance validation;
   - Ruff;
   - full pytest;
   - focused tests;
   - server-side CodeScene after PR creation.
9. Review focus naming the highest-risk code, not only a generic test plan.
10. Known limitations recorded as issues rather than hidden in prose.

Do not combine:

- governance authority and unrelated product implementation;
- membership, sessions, invitations, and authorization in one PR;
- a new frontend framework with a product feature;
- a broad RRA refactor with a new comparison engine;
- billing provider integration with unrelated workspace changes;
- AI integration with dashboard refactoring.

---

## 10. Definition of Ready for one implementation slice

A task is ready for Codex only when all are true:

- the repository baseline and branch are known;
- the governing specification is active;
- every required owner decision for the slice is settled;
- the scope and non-goals are explicit;
- dependencies have merged or a reviewed stacking strategy exists;
- expected failing tests are named;
- allowed and forbidden files are named;
- migration-head strategy is named if relevant;
- validation commands are named;
- the stop point is explicit;
- Ahmed has approved implementation of that task ID.

---

## 11. Definition of Done for one implementation slice

A task is done only when:

- the requested behavior and negative cases pass;
- no unrelated behavior is added;
- content-free logging and privacy boundaries are preserved;
- cross-org and nonexistence behavior is tested where relevant;
- fakes and production stores enforce the same invariant;
- migration upgrade/downgrade and single-head checks pass where relevant;
- focused tests, full pytest, Ruff, and governance validation pass;
- CodeScene PR gate passes;
- Claude Code review has no unresolved approved finding;
- the owner merges the proposal to `main`;
- issue and roadmap status are updated against the merged SHA.

A green local test suite is necessary but not sufficient.

---

## 12. Immediate execution order

Do not start with the full roadmap. Start with these bounded actions:

### Immediate Slice A - Docs-only truth reconciliation

Task IDs: `R0-01` through `R0-05`.

Purpose: prevent Claude Code or Codex from following stale RCA-001 Spec Kit instructions.

### Immediate Slice B - Transaction-boundary design

Task ID: `R1-01` only.

Purpose: settle the design for `#155` before implementation.

### Immediate Slice C - Concurrent final-owner implementation

Task IDs: `R1-02` through `R1-05` after Slice B review and owner approval.

### Immediate Slice D - Membership design and migration plan

Task ID: `R2-01` only after R1's contract is settled.

The first membership implementation PR begins only after the R1 transaction boundary is merged.

---

# 13. Claude Code master planning/review prompt

```text
You are working in Kemetra/Khepri as the planning and adversarial review agent.

Operating role:
- Do not implement code unless the owner explicitly assigns implementation.
- Treat Ahmed Shaaban as the only merge authority.
- Treat branches and PRs as proposals until merged to main.

Start with repository truth:
1. git status --short
2. git branch --show-current
3. git fetch origin
4. git checkout main
5. git pull --ff-only origin main
6. git log -1 --oneline
7. inspect open PRs and issues relevant to the requested task

Read first:
- AGENTS.md
- governance/CONSTITUTION.md
- governance/registry.yaml
- governance/families/RCA.md
- the active governed specification for the task
- KHEPRI_MASTER_PRODUCT_ROADMAP.md
- the relevant issue, design, plan, prior merged PR, and current tests

Requested roadmap task:
[TASK_ID AND TITLE]

Your job:
- verify that the task is still correct against current main;
- identify completed, stale, conflicting, or missing assumptions;
- list only blocking owner decisions;
- produce or review a small implementation-ready plan;
- name exact requirements, scenarios, expected RED tests, files, dependencies, non-goals, migration strategy, validation, and stop conditions;
- identify what may run in parallel and what must be serialized;
- test for scope creep, duplicate sources of truth, authorization bypass, data-retention drift, race conditions, weak fakes, and tests that could pass for the wrong reason;
- recommend deliberate mutation or adversarial probes for load-bearing guards.

Do not:
- widen the requested task;
- implement another roadmap phase;
- invent authority not present in governance/registry.yaml;
- propose a new framework or broad refactor without an explicit requirement;
- commit, push, open a PR, or merge.

Final response:
1. Repo state and baseline SHA
2. Readiness verdict: READY / NOT READY
3. Governing requirements and dependencies
4. Blocking decisions, if any
5. Implementation plan and task order
6. Parallelism and collision analysis
7. Test and mutation plan
8. Allowed and forbidden scope
9. Risks and follow-ups
10. Exact stop point

Stop after planning/review and wait for owner approval.
```

---

# 14. Codex master implementation prompt

```text
You are working in Kemetra/Khepri as the bounded implementation agent.

Start with repository truth:
1. git status --short
2. git branch --show-current
3. git fetch origin
4. git checkout main
5. git pull --ff-only origin main
6. git log -1 --oneline

Read first:
- AGENTS.md
- governance/CONSTITUTION.md
- governance/registry.yaml
- the active governed specification for this slice
- KHEPRI_MASTER_PRODUCT_ROADMAP.md
- the approved Claude Code plan for this task
- the relevant issue, design, tests, and prior merged PRs

Implement only:
[TASK_ID OR TIGHTLY COUPLED TASK IDS]

Target outcome:
[ONE BOUNDED OUTCOME]

Governing requirements/scenarios:
[EXACT IDS]

Dependencies that must already be on main:
[MERGED SHAS OR PRS]

Allowed files:
[EXACT FILES OR DIRECTORIES]

Forbidden scope:
- any later roadmap phase;
- unrelated refactors;
- package-manager, lockfile, framework, runtime, CI, or deployment changes unless explicitly listed;
- new governance authority;
- broad RRA changes;
- commit, push, PR creation, or merge.

Implementation rules:
- confirm the expected RED test fails for the intended reason;
- implement the smallest production change that turns it green;
- preserve fail-closed behavior;
- keep production stores and memory fakes semantically aligned;
- preserve one Alembic head;
- do not trust route/object identifiers as authorization;
- keep retail calculations in governed RRA facts;
- keep logs and telemetry content-free;
- add adversarial or mutation-style tests for every load-bearing guard.

Required validation:
- focused tests for the slice;
- uv run khepri-gov validate
- uv run ruff check .
- uv run pytest
- migration upgrade/downgrade and single-head checks when relevant

Final report:
1. Branch and baseline SHA
2. Task IDs completed
3. Files changed
4. Behavior implemented
5. Tests added and why they fail against the broken behavior
6. Validation commands and results
7. Migration-head status
8. Risks or follow-up issues
9. Confirmation that forbidden scope was untouched
10. git status --short

Stop after implementation and validation. Do not commit.
```

---

## 15. Roadmap status convention

Use the following statuses only:

- `PROPOSED` - roadmap or spec work exists but is not approved/active.
- `READY_FOR_PLAN` - governing authority exists; design questions remain.
- `READY_FOR_IMPLEMENTATION` - approved bounded plan and tests exist.
- `IN_IMPLEMENTATION` - one approved branch is implementing the task.
- `IN_REVIEW` - implementation is complete and under adversarial review.
- `MERGED` - owner merged to `main`.
- `BLOCKED` - a named dependency or owner decision prevents progress.
- `SUPERSEDED` - a later roadmap or artifact replaces this task.

A program's status is the status of its **next actionable task**. Where design may proceed but
implementation cannot, the program is `READY_FOR_PLAN` and the blocking implementation dependency is
named in the reason. `BLOCKED` is reserved for programs whose next task — design included — cannot
start.

Never mark a task complete because it exists on a branch. Use `MERGED` only with a `main` SHA.

---

## 16. Recommended current status

### How this table drifted, recorded 2026-08-19 (`R0-03` follow-up)

Four rows — `R0`, `R3`, `R6`, `R7` — described a repository state that twenty-one merged commits had
already left behind. `R6` read `BLOCKED` while all eight of `R6-01`…`R6-08` were merged, and `R7`
still cited R6 as its blocker after that dependency was met.

**The cause is structural, not clerical.** A slice's Definition of Done requires its own artifacts and
tests; nothing in it requires updating this table, so the table is the one document a merged slice
never touches. Programs whose slices land in a burst — R3 shipped nine, R6 eight — drift furthest.

**What a reader should trust.** This table and `STATUS.md` are maintained; verify a status claim
against the merged commits and the files a slice was supposed to produce before building on it, exactly
as `R1`'s cleared-then-reopened stop gate teaches. A green CI run and a merged PR title prove a slice
landed, never that its requirements closed — the `R6` row above lists three of its own gaps for that
reason.

**A correction this reconciliation itself needed, recorded because it is the same class of error.**
The first version of these rows called `R7-03` unblocked, reading its `Depends on: R3, R6` cell and
observing that both had merged. That is wrong: `KHEPRI-DEC-020`'s Consequences state that "`R7-03`,
`R7-05`, and `R7-06` remain blocked on `R7-02`" and that the table's dependency cell **understates**
it, because `R7-03` tests the resume path and needs persistence that `R7-02` did not ship. An active
governance decision governs over a roadmap dependency cell, and the first pass read the cell. It also
invented two statuses — `MERGED_EXCEPT_R3-11` and `PARTIAL` — where §15 says to use its eight only,
and where §15's own next-actionable-task rule already answered the question. Both found in review on
`#214`. **Fixing a stale row means reading what governs the dependency, not only what the table says
about it.**

**What to do at the end of a slice.** If a slice completes the last open task in its program, update
that program's row in the same PR. This is cheaper than a reconciliation pass and keeps the drift
bounded to programs still in flight.

| Program | Status | Reason |
| --- | --- | --- |
| R0 Roadmap/spec reconciliation | MERGED | `R0-04` merged at `ebfbe77`. `R0-01`/`R0-02`/`R0-03`/`R0-05` merged as one docs-only slice — `specs/001-rca-001-commercial-identity/{SUPERSEDED,STATUS,NEXT-SLICES}.md` — last reconciled by `R0-03` at `2b271a3` (`#202`). `R0-01` has no separate artifact by design; its current-state matrix is the shared baseline block at the top of those three files. **`NEXT-SLICES.md` is pinned to `95760a4` and is stale for R3/R4/R6/R7** — it stops at Slice 3 (`R3`) and predates every R4/R6/R7 merge. Read this table and `STATUS.md` for current state, not that file's "Recommended order" |
| R1 Concurrent final-owner safety | MERGED | `R1-01`…`R1-06` complete at `c8c6edb`; `#155` closed. **The stop gate was re-cleared by `ac7143b` (#175), not by `R1`** — `R1`'s lock covered one row per organization, so three callers disabling three different owners of one organization locked disjoint sets and `FOR UPDATE` serialized nothing. Measured at 4 failures in 12 against real PostgreSQL; it had read as a flake. See the note under `R2` |
| R2 Membership lifecycle | MERGED | `R2-01`…`R2-10` complete at `95760a4` (`#150`); PRs `#165`…`#178`. Roles CHECK-constrained, promotion/demotion/revocation through explicit operations, one shared FR-013 guard for remove/downgrade/disable, append-only FR-014 events on a 12-month horizon with a wired sweeper. Two latent gaps recorded rather than closed — see `specs/001-rca-001-commercial-identity/STATUS.md` |
| R3 Authentication sessions | MERGED | `R3-01`…`R3-10` merged earlier; **`R3-11` merged at `15a8175` (`#240`)**, so the program is complete. `KHEPRI-DEC-024` provisionally admitted Clerk for non-paying private beta and `KHEPRI-DEC-025` authorizes the implementation that closed it. Delivered: atomic provider-neutral external account/link pre-provisioning (`persistence.py:621`, one transaction, `IntegrityError → False`), external-capable final-owner protection (`_effective_owner_conditions`, `persistence.py:797`, `or_(credential_digest IS NOT NULL, external_identity_exists)` defined once and used at all three owner-counting sites), the contained Clerk adapter returning only two `str` fields across the seam, production session handoff, hard-stop revocation, and signed-token RCA→RRA evidence through the real `build_stack`/`build_web_app` graph. The persistence probe found no external-account migration necessary; the existing nullable verifier columns and `rca_external_identities` express the model, and `KHEPRI-DEC-025` §2.4 adopts that finding as a decision rather than leaving it an assumption `-024` §14 forbade. **The two gaps the `#240` post-merge audit recorded are closed** under `KHEPRI-DEC-025` §4: the recovery consequence is constructed by `build_recovery_security_service` and its sweeper is the fifth `RetentionPasses` entry, and `khepri-clerk-hard-stop` is registered in `[project.scripts]` pointing at `khepri.runtime.clerk_hard_stop:main` — `khepri.runtime` and not `khepri.local`, because the wheel excludes `src/khepri/local` and a command declared there would be absent from the image that has to run it. **CodeScene failed on `#240`** and the merge proceeded: `_verified_subject` and `_bearer` each scored 9.69 against `AGENTS.md`'s 10.00 requirement. Both are restructured into named predicates with the decision unchanged, and the behaviour was locked first — four cases pinning the `bool`-is-an-`int` exclusion and the strict lower bound on token lifetime, and eighteen pinning bearer parsing, which had **no** coverage before. CodeScene must re-evaluate both files server-side |
| R4 Invitations | MERGED | `R4-01` design merged (#209, #210, #212, #213, #220), **`R4-02` merged at `d50ffe6` (#215)**, **`R4-03` merged at `fc74f8e` (#217)** **`R4-04` merged at `d19e4f4` (#221)**, **`R4-06` merged at `b76579b` (#222)**, **`R4-05` merged at `f6e06c0` (#223)** and **`R4-07` proposed** — the program's last task — `invitations.py` carries the sealed record, `persistence.py` the `InvitationRow` with four `CHECK`s, `invitation_persistence.py` the store and its destroy-on-touch read, `invitation_retention.py` the sweeper, and migration `20260818_0018` the table. **`R4-07` closes the program** — `invitation_service.py` carries `issue` and `revoke`, `delete_open_invitation` the composite conditional statement §4.1 requires, and `R6-01` §3.1 the two invitation rows §6.3 assigns to this slice. `R4-04` widened `InvitationStore` rather than composing revocation from `get_invitation` and `save_invitation`: those two are a read-then-write, which is the stale-snapshot defect §4.1 forbids, and the read is keyed by identifier alone, which is `FR-023`. **The reads were deliberately left unscoped** — `find_for_redemption` must stay identifier-only because a redeemer holds no membership and cannot supply a scope. **`R4-06` adds the three cascades** — `FR-020`'s recipient predicate and `KHEPRI-DEC-015` §2's issuer trigger in `revoke_membership`'s `write` callback, and §7.1's unscoped purge cascade inside `purge_if_still_eligible`. The callback rather than the shared `_apply_membership_change` body is load-bearing: `demote_membership` delegates to the same helper, and a valid helper-body placement passes 10 of the slice's 11 tests. **It also lands the §8.2 advisory lock §4/§4.1 never asked for**, so `R4-04` shipped without it; the issuance-first ordering is now closed and the purge-first residual is carried as `xfail(strict=True)`. Two spec contradictions were corrected in `R4-01` rather than decided in code: §7 said to mark `revoked_at` where §4.1 says the cascades delete, and §4.1's claim that §7's cascades inherit its `expires_at > :now` clause is too broad for the purge trigger. The two owner decisions it also waited on were answered 2026-08-18 — `R4-01` §8.2 accepts the issuance-versus-purge residual, and §8.5 reads `FR-019` as the last check. **One gap `R4-03` records rather than closes**: no scheduler exists, so `RetentionPasses` runs only from the manual `sweep` command and every governed horizon — accounts, events, sessions, invitations — is unenforced without one. `R4-01` §8.1 assigns that elsewhere |
| R5 Recovery | READY_FOR_PLAN | `R5-01` remains the design for a future Khepri-credential path. Under `KHEPRI-DEC-025`, carrying `-024`'s disposition forward, `R5-02`, `R5-03`, and `R5-04` stay **deferred** while Clerk owns credentials. The reframed `R5-05`/`R5-06` consequence **merged at `15a8175` (`#240`)**: verified-link resolution, live account revalidation, all-Khepri-session revocation with a re-check after it, idempotent content-free evidence keyed by digest with cross-account fail-closed, disabled/purged refusal, identity-link integrity, and twelve-month evidence retention. Migration `20260821_0019` adds only that evidence table. **The composition gap the `#240` audit found is closed** under `KHEPRI-DEC-025` §4: `build_recovery_security_service` in `runtime/wiring.py` constructs the service over the real `SqlRecoverySecurityEventStore`, sharing the one `SessionService` lifetime and `LifecycleService` the authentication route uses so revocation and account state keep a single definition, and returning `None` with no provider configured because the consequence follows provider-owned recovery. The sweeper is the fifth `RetentionPasses` entry at the governed twelve-month horizon with no override, so the evidence no longer accumulates indefinitely. That work also found `#240`'s migration `20260821_0019` was never registered in `RCA_REVISIONS`, so the schema-drift guard had stopped one revision short of head and could not see the new table — registered, and the guard covers head again. The accepted cross-system recovery window between Clerk credential replacement and Khepri revocation remains a non-paying private-beta residual and a commercial hard stop (`-024` §7, carried forward). **`READY_FOR_PLAN` rather than `MERGED` or `READY_FOR_IMPLEMENTATION`:** every implementable task in the program is now either merged or deferred, so no bounded plan is outstanding — `R5-02`/`-03`/`-04` are the Khepri-credential path, and the event that reopens them is a decision returning credential ownership to Khepri (`-024` §13's fourth exit path), not an engineering dependency. `MERGED` is unavailable because §15 permits it only with a `main` SHA for every task, and three have none by design |
| R6 Canonical authorization | MERGED | All eight tasks `R6-01`…`R6-08` are merged: PRs `#192`…`#200`. Delivers `authorization.py` (the single door), `switching.py` (`R6-03`), `authorization_resolution.py` (the canonical resolver), and four evidence suites — `test_rca001_authorization_matrix.py`, `test_rca001_cross_organization.py`, `test_rca001_stale_session_authorization.py`, `test_rca001_resolver_chokepoint.py`. **This is what unblocks R7.** Read `STATUS.md` before building on it: `R6-01` §3.2 is uncovered and needs an `R6-02` change (self-versus-another-account has no target in `AuthorizationContext`); the three owner-only verbs check no authority of their own, so the gate is the authorized route but not a proven-exclusive one; and `R6-08`'s tripwire guards an empty room until a production consumer exists |
| R7 Commercial RRA bridge | MERGED | **`R7-07` merged at `d93b844` (`#226`), and `KHEPRI-DEC-021` is `active`** — the header device this row previously carried ("written for the state this row holds once `KHEPRI-DEC-021` merges") has served its purpose and is removed rather than left to read as a pending condition. `R7-01` (`#201`), `R7-02` (`#203` finding + `#205` migration `20260817_0017`), `R7-04` (`#207`) and `R7-07` are merged; **`R7-02` shipped as the migration only**, because `KHEPRI-DEC-020` §3 withheld the bridge service, and `KHEPRI-DEC-021` lifted exactly that bullet. **`R7-07` delivered §2's four parts and no more**: `open_commercial_session` in `khepri.rra` (accepting an opaque `owner_id` rather than minting one — `allocate_owner_id` stays the single definition, and a second minting site is how `FR-035`'s stability breaks), `open_commercial_session_row` closing the gap that `BetaSessionRow` had exactly one write site behind the invitation guard, `get_session_for_owner` keyed `(owner_id, session_id)` = `uq_session_owner_scope` and failing closed so a foreign session is indistinguishable from an absent one (`FR-023`, `FR-025`), and `CommercialBridge` in **`khepri.runtime`** — §3's location, chosen over `R7-01` §3's `khepri.local` recommendation for a packaging reason: the wheel excludes `src/khepri/local`, so a bridge there is unreachable from the deployed web role. **No migration was needed**, as §4 had already verified. Two mutants confirm the guards can fail: dropping `owner_id` from the resume `WHERE` clause is killed by 4 tests, a bridge skipping `resolve_scope` by 8. **`R7-03` merged at `4999cc1` (`#229`)** — `tests/test_r703_live_authorization_on_resume.py`, evidence only: no production code and no migration. It is **the join the two adjacent suites could not make**, and that is why it exists rather than more cases being added to either: `R6-07`'s `test_rca001_stale_session_authorization.py` proves revocation, demotion and disablement take effect immediately but stops at `resolve_scope` with **no RRA analysis anywhere in it**, while `R7-07`'s `test_r707_commercial_bridge.py` proves re-resolution on resume but passes `account_id` directly and **mints no session at all** — and a test that never mints a session cannot show a *session-bearing* actor losing access, which is the whole of the claim. Five journeys carry it: a revoked member and a disabled account are both refused, a **demoted owner still resumes** and reads live as `member` (the negative case that keeps the guard from being a blanket refusal), a revoked authentication session is refused and **re-authenticating restores access**, and each refusal asserts **the analysis still exists** so the outcome is authorization rather than absence, with `test_no_time_passed` and `test_it_does_not_wait_for_session_expiry` pinning `FR-008`'s “no dependence on session expiry” and `FR-030`'s “without requiring the affected session to end”. Because the composition puts **two** gates in the path — `ActorResolver`'s `assert_account_active` at step 3 (`R3-05`) before the bridge is reached, and `resolve_scope` inside it — `TestBothLayersRefuseIndependently` isolates each, so neither passes on the strength of the other. **Its `Depends on: R3, R6` cell understated the real dependency**: it needed the persistence `R7-07` added, because it resumes an analysis that already exists; `R7-01` §4 with `KHEPRI-DEC-021` governs instead of the table, and the same understatement stands for `R7-05` and `R7-06`. **No mutation evidence is recorded in the file**, unlike `R7-07`'s two mutants — stated rather than assumed, since a green evidence suite is not proof its guards can fail. **`R7-05` merged at `9802586` (`#234`)** — `khepri/runtime/commercial_api.py` adds `POST /api/v1/commercial/analyses` and `GET /api/v1/commercial/analyses/{session_id}`, wired in `wiring.py` via `build_commercial_services`, which constructs the RCA half of the graph in the production composition root **for the first time** (`build_stack` had built only RRA and S3). It honors `KHEPRI-DEC-022` §2's four bounds: `for_request` and never `resolve`, the cookie as the only token source, `R6-08`'s tripwire replaced rather than relaxed, and **no new `R6-01` §3.1 row** — opening an analysis *is* `resolve_scope` plus a mint that authorizes nothing, and “Resolve an isolation scope” is already `PERMIT`/`PERMIT` there. **No organization is accepted in any request**: `for_request` is called with `organization_id=None`, so the comparison the record requires cannot be skipped because there is no parameter to skip it on. **Every refusal is one empty-body `404`** — both exception types derive from `PermissionError`, so one handler covers them, and refusals return a bare `Response` rather than raising `HTTPException`, whose `{"detail": …}` body is exactly what must not vary between causes. **Three mutants verified**: `for_request`→`resolve` killed by `test_the_resolver_is_called_with_no_organization` (failing on the recorded call name, not `AttributeError` — the stub defines both methods so the mutant cannot die for the wrong reason), `404`→`403` killed by all four matrix rows plus two live journeys, and dropping the null-services guard killed by the unwired-app test. `R6-08`'s `test_the_resolver_has_no_production_consumer_yet` is **deleted**, replaced by one naming both legitimate consumers with an emptiness assertion — verified by stubbing the scan to return `[]` and confirming the failure lands on that assertion. `R6-05`'s matrix tripwire needed **no change**, confirming §2's fourth bullet. `R7-04`'s ten beta regressions pass **unmodified**, which is how §3's no-beta-change requirement is evidenced; the null-services guard means an unwired deployment has no commercial surface at all. **Of the twelve `RCA-001` requirements `KHEPRI-DEC-022` moves with this slice, four carry evidence here** — `FR-008` (`test_a_disabled_account_cannot_resume_through_the_route`, no time passes), `FR-022` and `FR-025` (the uniform matrix and the response-to-response comparison), `FR-023` (`session_id` stays an identifier) — plus `FR-030`, which is not on that list but is what the revoked-member journey proves. **The remaining eight — `FR-009`, `FR-021`, `FR-024`, `FR-026`, `FR-028`, `FR-031`, `FR-034`, `FR-038` — are reached but not closed here**, and are `R7-06`'s to evidence end-to-end; stating that rather than claiming twelve is the difference between a slice reaching a requirement and proving it. **`R7-06` merged at `2747670` (`#237`), and `R7` is complete.** It was scoped as a test-only slice and is not one: probing the seam found `FR-038` **false**, because consent is enforced at the service layer (`IntakeService.begin` → `require_upload_consent`) so it already bound a commercial actor, while the only route recording consent read the beta cookie a commercial actor never holds — so every commercial upload failed closed forever. `KHEPRI-DEC-023` (`43fcd72`) authorized the fix; `POST /api/v1/commercial/analyses/{session_id}/consent` reuses `record_consent` and adds no consent logic, with **`bridge.resume` before the write as the scope check** so one organization cannot write consent onto another's analysis. **Eleven tests close seven requirements** — `FR-009`, `FR-021`, `FR-026`, `FR-028`, `FR-031`, `FR-034` and `FR-038` — while `FR-008`, `FR-022`, `FR-023` and `FR-025` closed in `R7-05`, not here. **`FR-024` is satisfied by absence, not by test**: no commercial route accepts an organization, so an actor/named-scope disagreement cannot be constructed, and the suite asserts that absence rather than a comparison it never made. `FR-038`'s four clauses are evidenced separately — consent by both halves (refused before, accepted after, because the refusal alone would pass against the very defect just fixed), and disclosure, provenance and Arabic/English parity by a structural scan proving no module on the named report path distinguishes a commercial actor. **Four mutants verified, and one initially survived**: a `409`-on-already-consented mutant lived because every case consented once on a fresh journey, so §2's "consenting twice is not an error" was unverified — the missing case was added and the mutant now dies. Both structural scans carry emptiness assertions, and the report-path scan also asserts every named module exists, so a renamed pipeline module fails loudly rather than being skipped. `R7-04`'s beta regressions pass unmodified throughout. **Three things `R7-07` deliberately did not fire**, recorded so a green run is not mistaken for coverage: `R6-08`'s `test_the_resolver_has_no_production_consumer_yet` and `R6-05`'s matrix tripwire both wait on `R7-05`'s endpoint, not on a bridge no handler reaches, and twelve `RCA-001` requirements (`FR-008`, `FR-009`, `FR-021`…`FR-026`, `FR-028`, `FR-031`, `FR-034`, `FR-038`) still move with `R7-05`. **One departure from `KHEPRI-DEC-021`, recorded rather than glossed:** §3's consequences ask for the boundary assertion as a mirror of `find_rca_import_offenses` inside `test_rca001_boundary.py` (whose `_TARGET` is hard-coded to `khepri.rca`); `R7-07` asserted the same flat prohibition in both directions with an independent scan in `test_r707_commercial_bridge.py` instead, carrying its own emptiness assertion. The property holds and is mutation-verified, but there are now two boundary scanners where the record expected one reused helper — consolidating them is a candidate for `#211`'s deferred ledger |
| R8 Commercial shell | READY_FOR_IMPLEMENTATION | **`R8-01` merged at `d95d34b` (`#219`)** — `docs/superpowers/specs/2026-08-19-r8-01-shell-ia-and-tokens.md` carries the shell information architecture, and `src/khepri/rra/journey/assets/shell.css` the token set, with `tests/test_r801_shell_tokens.py` holding four consistency claims the note makes. Design output only: no template links the stylesheet and it is deliberately **not** in `routes.py`'s asset allowlist. **This row read `READY_FOR_PLAN` and "`R8-01` proposed" for three status passes after `d95d34b` merged** — the §16 drift this section documents about itself, caught in the `#240` post-merge audit. `R8-02` is the next task and nothing gates it: its `R8-01` and R3-HTTP dependencies are merged, and the R7 API it consumes closed at `2747670`. Three things the note settles rather than defers: the shell takes `/app/{language}/…` because `/beta/{language}/{step}` is a catch-all; expired, deleted, and session-unavailable stay collapsed into one surface because distinguishing them is the disclosure **`FR-025`** forbids — "denials MUST NOT disclose existence, ownership, or the identity of another organization", which is the invariant a UI breaks most easily since naming the organization is the natural thing for an error page to do — while *no membership* gets its own because it is the only one with a next step; and `docs/ui/design_handoff_khepri/` is reusable as IA reference but **not** as an asset plan — it specifies Google Fonts and a unpkg CDN, which the UI guardrails forbid. Two questions are left to `R8-02`: how the shell attaches its response headers -- **not** whether it shares `endpoints.security`, which carries none: that middleware only enforces same-origin mutations, while CSP and `Cache-Control: private, no-store` are `SECURITY_HEADERS` attached per response, and the middleware is registered app-globally either way (corrected in review on `#219`; the open part is whether the commercial session wants the same policy as the beta one, which is `R3-06`), and whether `account` stays nested under the organization path. `R8-02` is then the next task; implementation of the surfaces still depends on R3/R4/R6/R7 |
| OPS1 Production operations | READY_FOR_PLAN | `KHEPRI-DEC-008` is active and leaves target selection open by design; spend is an owner decision; deployment waits for R1 |
| S1 RRA hardening | READY_FOR_PLAN | Triage only may begin in parallel |
| G2/G3 Workspace authority | PROPOSED | Needs product decisions, retention decision, and active spec |
| W1 Workspace/history | BLOCKED | No active authority yet |
| G4/C1 Comparison | BLOCKED | Depends on durable history and new RCA/RRA authority |
| D1 Dashboard/evidence workspace | BLOCKED | Depends on stable comparison facts |
| G5/ON1 Public onboarding | PROPOSED | Separate spec required; not on first critical path |
| G6/B1 Billing | PROPOSED | Begin after M4 proves repeat value |
| G7/A1 Agency | PROPOSED | Begin after billing and stable authorization |
| G8/S2 Recurring delivery | PROPOSED | Separate spec/runtime decision required |
| G9/AI1 AI assistant | PROPOSED | Requires stable evidence contracts and provider/privacy authority |
| E1 Enterprise GA | PROPOSED | Final hardening program built on all prior milestones |

---

## 17. Final sequencing rule

Khepri should not be developed as one long feature branch or one giant specification.

The correct sequence is:

1. close known invariants and races;
2. finish one active specification;
3. expose it through a truthful product shell;
4. create the next retention and product authority;
5. add persistent repeat value;
6. add comparison and evidence-backed decision value;
7. monetize only after repeat value exists;
8. add complex tenancy and scheduling only after authorization and billing are stable;
9. add AI only after facts and evidence are mature;
10. prove operations, security, recovery, and support before enterprise GA.

That sequence preserves Khepri's strongest differentiator: every customer-visible result is reproducible, scoped, governed, cited, and safe under failure.
