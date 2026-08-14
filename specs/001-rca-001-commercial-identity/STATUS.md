# RCA-001 — implementation status against `main`

**Task:** `R0-03` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.

**Baseline:** `main` @ `95760a4`, 2026-08-14. `uv run khepri-gov validate` passes; `uv run pytest`
reports 1883 passed, 47 skipped. Migration head `20260814_0015` (single head).

**Updated for `R2-10`.** The `R2` membership slice (`#150`) is merged: `R2-01` … `R2-09` landed as
`#165` … `#178`. The rows below were last accurate at `ebfbe77`, before that slice; four membership
requirements changed status and are re-derived from the code as it stands, not from the roadmap's
claims about it.

**This file records status only.** It does not restate, interpret, or amend any requirement.
`governance/specifications/RCA-001.md` is the only authoritative source of what RCA-001 requires,
and `governance/registry.yaml` is the only authoritative source of its lifecycle state. Where this
file and either of those disagree, they win and this file is the defect.

**Why it exists.** Slices of RCA-001 are merged (`#148`, `#153`, `#157`, then the `R1` account
lifecycle and the `R2` membership slice `#150`) and `RCA-001` is `active`, but nothing recorded which
requirements those slices actually satisfied. Without that, the next slice cannot be scoped without
re-deriving it, and an agent reading the sibling planning documents in this directory would rebuild
merged code. See `SUPERSEDED.md`.

---

## Rollup

| Status | Count | Change since `ebfbe77` |
|---|---|---|
| Implemented | 13 | +3 (FR-012, FR-013, FR-014) |
| Partial | 13 | −2 |
| Not implemented | 14 | −1 |

"Partial" is used strictly: the requirement has real code behind it that does what it says for some
paths, and a named clause or scenario it does not yet cover. It is not a synonym for "started".

FR-015 stayed **Partial** rather than becoming Implemented, and the reason is worth stating: `R2`
closed its first clause exactly (two roles, CHECK-constrained) but the requirement also enumerates
owner capabilities, two of which — invite, and disable the organization — have no operation. Marking
it Implemented because the role *model* is finished would have been the easier reading and the wrong
one.

## The absences that explain the gap

27 requirements are not fully implemented (13 partial + 14 not implemented). **15 of them** trace to
exactly two missing pieces, each an existing roadmap program:

| Absence | Verified by | Blocks | Count | Roadmap |
|---|---|---|---|---|
| No session concept | every `session` token in `src/khepri/rca/` is a docstring or SQLAlchemy's `sessionmaker`/`Session` | FR-003 clause 2, FR-007, FR-008 clause 2 generally, FR-022 session half, FR-027, FR-029, FR-030, FR-035 session clause | 8 | `R3` |
| No authorization layer | no `authorization.py`; no protected-action abstraction | FR-021, FR-022 … FR-025 general halves, FR-026, FR-028 | 7 | `R6` |

FR-022 appears in both, so the union is **14**, not 15.

**The third absence is now closed.** At `ebfbe77` this table had a row reading "No membership write
operations — `OrganizationStore` exposes exactly one write, `create_organization`", blocking FR-012,
FR-013's remove/downgrade clauses, FR-014's second clause, FR-020, and FR-035's membership clause.
`R2` added promotion, demotion, and revocation, so four of those five are no longer blocked by it.
FR-020 remains blocked, but by invitations rather than by revocation.

Two capability absences account for another **6**: invitations do not exist (FR-016 … FR-020, `R4`)
and recovery does not exist (FR-005, FR-006, FR-007, `R5`) — FR-007 and FR-020 are already counted
above, so these add 6 distinct rows for a running total of **20 of 27**.

The remaining **7** — FR-001, FR-009, FR-015, FR-031, FR-034, FR-035, FR-038 — are not blocked by a
missing subsystem. They are partial for narrower reasons stated in their rows: an unasserted clause
(FR-001), an unwired service (FR-009, FR-031, FR-034, FR-038 all trace to `IsolationService` being
instantiated nowhere outside tests), and unbuilt owner capabilities (FR-015).

That the remaining structural absences map one-to-one onto `R3` and `R6`, and the two capability
absences onto `R4` and `R5`, is independent evidence for the roadmap's critical path — arrived at
from the code rather than from the roadmap.

## Two gaps `R2` recorded rather than closed

Both were found by probing rather than assumed, are asserted in
`tests/test_rca001_guard_evidence.py`, and are **not currently reachable** — no service accepts a
role as input, so there is no caller-supplied value to forge. Each is latent, and each needs a
change that did not belong in a test-only slice:

| Gap | Evidence | What closing it needs |
|---|---|---|
| `rca_membership_events` has no role CHECK — a forged `next_role` is stored without complaint | `test_the_event_table_does_not_constrain_its_roles` | A migration. `FR-014` attribution naming a role that cannot exist in live state is two sources disagreeing about one fact |
| `Membership.create` and `MembershipEvent.role_changed` accept any string as a role | `test_the_domain_records_do_not_validate_roles_either` | Domain validation against `ROLES`, or a documented decision that the narrow service surface is the guard |

What prevents forgery today is the *shape of the interface*, not validation:
`promote_to_owner`/`demote_to_member` each name their destination role, so no parameter exists to
forge. `test_no_role_change_operation_accepts_a_role_from_its_caller` fails if any operation grows
one — which is the moment validation stops being optional.

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
| FR-012 | Implemented | `organizations.py:382` `revoke_membership`; store `persistence.py:749` | `test_rca001_revocation.py` (13 tests); non-interference asserted per clause | — Both clauses tested separately, because they fail separately: one asserts the account's *other* memberships survive, the other asserts the organization's *other* members do |
| FR-013 | Implemented | shared guard `persistence.py:831` `_apply_membership_change`; disable path `apply_owner_reducing_change` `:442`; `errors.py:8-18` | `test_rca001_final_owner.py`; `test_rca001_concurrent_final_owner.py` (6 contention tests × `ATTEMPTS = 10`, PostgreSQL); `test_rca001_guard_evidence.py` (one-guard AST assertion) | — All three verbs guarded: remove and downgrade share `_apply_membership_change`, disable uses the R1 sibling. `#155` closed by `ac7143b` (see the note below — its residual was a live defect, not a flake) |
| FR-014 | Implemented | `MembershipEvent` `organizations.py:156`; `MembershipEventRow` `persistence.py:129`; attribution emitted inside every write transaction | `test_rca001_membership_events.py`; `test_rca001_event_coverage.py` (4 tests incl. AST deleter audit); `test_rca001_event_retention.py` | — Attribution moved off the state row onto an append-only expiring table (`20260814_0014` dropped `changed_by`/`changed_at`). `prior_role` is read from the stored row under lock, not taken from the caller |
| FR-015 | Partial | `ROLES` `organizations.py:28`; CHECK `ck_rca_membership_role` `persistence.py:105`, migration `20260814_0015`; `promote_to_owner` `:343`, `demote_to_member` `:411`, `revoke_membership` `:382` | `test_rca001_role_transitions.py` (19 tests); `test_rca001_guard_evidence.py` (forgery surface) | Clause 1 (exactly two roles) implemented and constrained. Clause 2 is partial: of the owner capabilities the requirement names, change-roles and revoke-memberships exist; **invite** is `R4`, and **disable the organization** has no operation. See the two recorded gaps below |

### Invitations

| FR | Status | Gap |
|---|---|---|
| FR-016 … FR-020 | Not implemented | Entirely absent. No `Invitation` type, no `rca_invitations` table (`test_rca001_migration.py` enumerates five: accounts, organizations, memberships, isolation_scopes, membership_events), no store method. FR-020 was doubly blocked at `ebfbe77`; `R2` supplied revocation (`organizations.py:382`), so it is now blocked by invitations alone (`R4`) |

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
| FR-030 | Not implemented | — | — | Blocked by sessions alone now (`R3`). `R2` supplied the membership-change operations whose effect this requires observing, and `isolation.py` reads membership live per call — the right shape for "takes effect for decisions made after the change". Scenario 20 becomes testable once a session exists |

### Isolation and the RRA boundary

| FR | Status | Code | Tests | Gap |
|---|---|---|---|---|
| FR-031 | Partial | `isolation.py:11-40` — returns `owner_id` as a bare `str` and deliberately mints no `SessionScope` (rationale `:14-17`) | `test_rca001_isolation.py:46`, `:56`, `:64` | Mapping is unit-tested but unexercised: `IsolationService` is instantiated nowhere outside tests, so no commercial actor reaches an RRA capability |
| FR-032 | Implemented | `organizations.py:98-104`, `:127-130` — `create` has no `owner_id` parameter, so a chosen key is unexpressible rather than rejected | `test_rca001_isolation.py:101` (7 adversarial names, sliding-window check), `:114`; `test_rca001_persistence.py:303` | — |
| FR-033 | Implemented | `organizations.py:107-135`; `persistence.py:88-101` | `test_rca001_isolation.py:101`, `:114` | — |
| FR-034 | Partial | `isolation.py:32`, `:36`, `:39` → uniform `SCOPE_FAILURE` | `test_rca001_isolation.py:149` | Verified at `resolve_scope`; no cross-scope access through a commercial actor exists yet |
| FR-035 | Partial | `_from_storage` preserves the stored key (`organizations.py:132-135`); `UniqueConstraint("owner_id")` `persistence.py:91` | `test_rca001_isolation.py:64`, `:100` (across a demotion), `:125` (revocation ends access), `:148`; `test_rca001_persistence.py:224`, `:639` | "Across membership changes" now **asserted** — it was untestable before `R2` because the clause named a change no code could make. Remaining: "across sessions" and "across active-organization switches" are still unverifiable, since neither concept exists (`R3`) |
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
