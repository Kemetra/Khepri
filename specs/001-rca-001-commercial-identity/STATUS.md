# RCA-001 — implementation status against `main`

**Task:** `R0-03` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.

**Baseline:** `main` @ `ebfbe77`, 2026-08-13. `uv run khepri-gov validate` passes; `uv run pytest`
reports 1794 passed, 10 skipped. Migration head `20260813_0012` (single head).

**This file records status only.** It does not restate, interpret, or amend any requirement.
`governance/specifications/RCA-001.md` is the only authoritative source of what RCA-001 requires,
and `governance/registry.yaml` is the only authoritative source of its lifecycle state. Where this
file and either of those disagree, they win and this file is the defect.

**Why it exists.** Three slices of RCA-001 are merged (`#148`, `#153`, `#157`) and `RCA-001` is
`active`, but nothing recorded which requirements those slices actually satisfied. Without that,
the next slice cannot be scoped without re-deriving it, and an agent reading the sibling planning
documents in this directory would rebuild merged code. See `SUPERSEDED.md`.

---

## Rollup

| Status | Count |
|---|---|
| Implemented | 10 |
| Partial | 15 |
| Not implemented | 15 |

"Partial" is used strictly: the requirement has real code behind it that does what it says for some
paths, and a named clause or scenario it does not yet cover. It is not a synonym for "started".

## The absences that explain the gap

30 requirements are not fully implemented (15 partial + 15 not implemented). **18 of them** trace to
exactly three missing pieces, each an existing roadmap program:

| Absence | Verified by | Blocks | Count | Roadmap |
|---|---|---|---|---|
| No session concept | every `session` token in `src/khepri/rca/` is a docstring or SQLAlchemy's `sessionmaker`/`Session` | FR-003 clause 2, FR-007, FR-008 clause 2 generally, FR-022 session half, FR-027, FR-029, FR-030, FR-035 session clause | 8 | `R3` |
| No membership write operations | `stores.py` `OrganizationStore` exposes exactly one write, `create_organization` | FR-012, FR-013 remove/downgrade clauses, FR-014 second clause, FR-020, FR-035 membership clause | 5 | `R2` |
| No authorization layer | no `authorization.py`; no protected-action abstraction | FR-021, FR-022 … FR-025 general halves, FR-026, FR-028 | 7 | `R6` |

The three sets overlap (FR-022 and FR-035 each appear twice), so the union is **18**, not 20.

Two further capability absences account for another **6**: invitations do not exist (FR-016 … FR-020,
`R4`) and recovery does not exist (FR-005, FR-006, FR-007, `R5`) — FR-007 and FR-020 are already
counted above, so these add 6 distinct rows for a running total of **24 of 30**.

The remaining **6** — FR-001, FR-009, FR-015, FR-031, FR-034, FR-038 — are not blocked by a missing
subsystem. They are partial for narrower reasons stated in their rows: an unasserted clause
(FR-001), an unwired service (FR-009, FR-031, FR-034, FR-038 all trace to `IsolationService` being
instantiated nowhere outside tests), and an unconstrained `role` column (FR-015).

That the three structural absences map one-to-one onto `R2`, `R3`, and `R6`, and the two capability
absences onto `R4` and `R5`, is independent evidence for the roadmap's critical path — arrived at
from the code rather than from the roadmap.

---

## Requirement status

### Identity and credentials

| FR | Status | Code | Tests | Gap |
|---|---|---|---|---|
| FR-001 | Partial | `accounts.py:114-138`, `:272-276`; `persistence.py:177-196` | `test_rca001_accounts.py:21`; `test_rca001_persistence.py:80`, `:93` | Clause 1 done. Clause 2 (creation grants no organization access) holds structurally — `create_account` writes no membership row — but is never asserted |
| FR-002 | Implemented | `credentials.py:94-109`, `:53-69`; `persistence.py:117-129`; sealed at `records.py:164-237` | `test_rca001_accounts.py:28`, `:40`, `:50`; `test_rca001_persistence.py:120`, `:334` | — |
| FR-003 | Partial | `accounts.py:278-304` resolves exactly one `Account` | `test_rca001_accounts.py:58` | No session exists, so "the resulting session" and "that session's identity record" have no artifact. Clause 2 unverifiable |
| FR-004 | Implemented | `accounts.py:230-249`, `:252-265`, `:298-304`; `DUMMY_SALT` at `credentials.py:31` | `test_rca001_accounts.py:64`, `:126`, `:148`, `:193`; `test_rca001_disablement.py:95` | — |
| FR-005 | Not implemented | — | — | No recovery secret, store method, or service |
| FR-006 | Not implemented | — | — | No recovery initiation to be uniform about |
| FR-007 | Not implemented | — | — | Doubly blocked: no recovery, and no sessions to invalidate |
| FR-008 | Partial | Clause 1: `accounts.py:244-249`, `:157-176`; `lifecycle.py:91-106`. Clause 2: `isolation.py:31-33` | `test_rca001_disablement.py:60`, `:72`, `:130`, `:185`; `test_rca001_lifecycle.py:28` | Clause 2 is enforced at scope resolution only. `assert_account_active` (`lifecycle.py:132`) has no production caller and awaits `R3` |

### Organizations and membership

| FR | Status | Code | Tests | Gap |
|---|---|---|---|---|
| FR-009 | Partial | `organizations.py:17-36`; `persistence.py:56-61`, `:88-101` | `test_rca001_organizations.py:69`; `test_rca001_persistence.py:211` | "Owns retail content" not demonstrated end to end: `IsolationService` is wired into no application path — `local/wiring.py` imports only the sweeper and account store |
| FR-010 | Implemented | `organizations.py:142-160`; atomic write `persistence.py:297-348`, identity checks `:312-315`, ordering flush `:330` | `test_rca001_organizations.py:48`, `:79`; `test_rca001_persistence.py:211`, `:267` | — |
| FR-011 | Implemented | composite PK `persistence.py:81-82`; `memberships_for_account` `:364-369`; per-org scope `:88-101` | `test_rca001_isolation.py:74`, `:124` | — |
| FR-012 | Not implemented | — | — | Revocation does not exist as an operation. `OrganizationStore` has no remove or role-change method |
| FR-013 | Partial | `lifecycle.py:152-166`; effective-owner count `persistence.py:371-413`; `errors.py:8-18`, `:37` | `test_rca001_final_owner.py:36`, `:53`, `:98`, `:146`, `:196` | Two gaps: (1) the requirement names remove, downgrade, and disable — only disable exists to guard; (2) the cross-store race at `lifecycle.py:66-84`, which is issue `#155` and roadmap `R1` |
| FR-014 | Partial | `organizations.py:51-55`, `:150-156`; `persistence.py:84-85` | `test_rca001_organizations.py:58` (creation attribution only) | Two gaps: the current-state row cannot represent a transition (stated at `organizations.py:44-49`), and there is no role-change or revocation operation to record. `changed_by` is a caller-supplied string, not a validated actor |
| FR-015 | Partial | `organizations.py:14` (`OWNER_ROLE`); `persistence.py:83` `role: Mapped[str]`, unconstrained | indirect only | No `member` constant; `role` has no CHECK constraint or validation, so a third role is writable. No owner-only capability exists |

### Invitations

| FR | Status | Gap |
|---|---|---|
| FR-016 … FR-020 | Not implemented | Entirely absent. No `Invitation` type, no `rca_invitations` table (`test_rca001_migration.py:202` enumerates four tables: accounts, organizations, memberships, isolation_scopes), no store method. FR-020 is doubly blocked — no invitations and no revocation |

### Authorization

| FR | Status | Code | Tests | Gap |
|---|---|---|---|---|
| FR-021 | Not implemented | — | — | No protected-action abstraction, and no session carrying the actor |
| FR-022 | Partial | `isolation.py:30-40` — three sequential guards, no permissive fallthrough | `test_rca001_isolation.py:141`, `:149`; `test_rca001_disablement.py:130` | Deny-by-default holds at `resolve_scope` only. Scenario 19 unverifiable without sessions |
| FR-023 | Partial | `isolation.py:34-36` — the decision is a membership lookup, not the supplied identifier | `test_rca001_isolation.py:141` | Verified at organization-scope granularity only; no object-level authorization path exists |
| FR-024 | Partial | `isolation.py:34-36` | `test_rca001_isolation.py:141`, `:149` | Scenario 15 (cross-org mutation, no state change in either) has no test and no mutating protected action to test |
| FR-025 | Partial | `isolation.py:32`, `:36`, `:39` — all three failure modes raise one `ScopeAccessDenied` | `test_rca001_isolation.py:149` — asserts one message across non-member, nonexistent org, and both, and that neither the org name nor a probe string appears | Not proven at object granularity |
| FR-026 | Not implemented | — | — | No canonical checkpoint. `isolation.py:14` is one chokepoint for one capability, which is not a checkpoint every protected action passes through |
| FR-027 | Not implemented | — | — | No session, so no active-organization state; `resolve_scope` takes the organization per call |
| FR-028 | Partial | Clause 1: `accounts.py:278-304` never consults membership. Clause 2: `isolation.py:34-36` | Clause 2: `test_rca001_isolation.py:141` | Clause 1 holds incidentally and is unasserted; scenario 18 has no test |
| FR-029 | Not implemented | — | — | No switch operation and no active-org state |
| FR-030 | Not implemented | — | — | No sessions, and no membership-change operation whose effect could be observed. `isolation.py` reads membership live per call, which is the right shape for this |

### Isolation and the RRA boundary

| FR | Status | Code | Tests | Gap |
|---|---|---|---|---|
| FR-031 | Partial | `isolation.py:11-40` — returns `owner_id` as a bare `str` and deliberately mints no `SessionScope` (rationale `:14-17`) | `test_rca001_isolation.py:46`, `:56`, `:64` | Mapping is unit-tested but unexercised: `IsolationService` is instantiated nowhere outside tests, so no commercial actor reaches an RRA capability |
| FR-032 | Implemented | `organizations.py:98-104`, `:127-130` — `create` has no `owner_id` parameter, so a chosen key is unexpressible rather than rejected | `test_rca001_isolation.py:101` (7 adversarial names, sliding-window check), `:114`; `test_rca001_persistence.py:303` | — |
| FR-033 | Implemented | `organizations.py:107-135`; `persistence.py:88-101` | `test_rca001_isolation.py:101`, `:114` | — |
| FR-034 | Partial | `isolation.py:32`, `:36`, `:39` → uniform `SCOPE_FAILURE` | `test_rca001_isolation.py:149` | Verified at `resolve_scope`; no cross-scope access through a commercial actor exists yet |
| FR-035 | Partial | `_from_storage` preserves the stored key (`organizations.py:132-135`); `UniqueConstraint("owner_id")` `persistence.py:91` | `test_rca001_isolation.py:74`, `:64`; `test_rca001_persistence.py:224`, `:639` | "Across sessions" and "across active-organization switches" are unverifiable — neither concept exists. "Across membership changes" untestable — no such operation |
| FR-036 | Implemented | verified by absence: zero `khepri.rra` imports in `src/khepri/rca/` | `test_rca001_boundary.py:135`; `test_rca001_migration.py:262` | Satisfied vacuously — no commercial actor reaches an RRA capability yet. No test asserts the RCA→RRA import direction; `test_rca001_boundary.py:96` tests RRA→RCA |
| FR-037 | Implemented | table namespace separation; one-directional import rule `test_rca001_boundary.py:63-105` | the three slice diffs touched zero `test_rra*` files | — |
| FR-038 | Not implemented | — | — | No commercial actor can reach an RRA capability, so these controls have nothing to hold for. Nothing in `src/khepri/rca/` touches them |
| FR-039 | Implemented | RCA declares its own `DeclarativeBase` (`persistence.py:24-25`) with no FK to any `rra_` table | `test_rca001_boundary.py:96` (AST scan, self-checked at `:108`); `test_rca001_migration.py:262` | — |
| FR-040 | Implemented, vacuously | verified by absence: zero `logging`, `logger`, or `print(` in `src/khepri/rca/`; `PurgeReport` carries counts only | `test_rca001_isolation.py:149`; `test_rca001_retention.py:64` | Holds because nothing logs. A future log statement is unguarded by any test. `FINAL_OWNER_FAILURE` is a deliberate content-bearing exception documented at `errors.py:8-18`, not a breach |

---

## Scenario coverage

The specification's Verification section requires a test per scenario and an authorization matrix
over `{owner, member, non-member, unauthenticated}` × every protected action. **Neither exists
yet.** No RCA-001 test names a scenario number, and there is no matrix test.

Scenarios with no corresponding test: **4, 6, 7, 8, 9, 13, 14, 15, 18, 19, 20** — the same set the
three structural absences predict.

---

## Notes for whoever writes the next slice

1. **The code's own FR annotations were checked against behavior, not trusted.** All were accurate,
   including the self-critical ones (`organizations.py:44-49`, `lifecycle.py:66-84`,
   `lifecycle.py:135`, `accounts.py:236-242`). One place is *stronger* than its annotation:
   `isolation.py:30-40` is annotated for FR-031 and FR-008 but also delivers partial FR-022, FR-023,
   FR-024, FR-025, and FR-028. Do not rebuild those guards; extend them.
2. **`lifecycle.py:66-84` documents the `#155` race but does not cite the issue.** Worth adding when
   `R1` touches the file.
3. **`count_owners`' docstring is incomplete.** `persistence.py:388-390` describes only the enabled
   and not-purged conditions; the query also filters `credential_digest IS NOT NULL` (`:409`), which
   is the clause that matters most. The code is correct and the omission is in the prose. Recorded as
   an issue to fix alongside `R1`.
4. **`MemoryOrganizationStore` can model weaker semantics than SQL.** Its `accounts` argument
   defaults to `None`, and owner counting then treats every membership holder as live. See
   `docs/superpowers/specs/2026-08-13-r1-01-transaction-boundary-design.md` §5.2.
