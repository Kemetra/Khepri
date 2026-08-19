# RCA-001 — implementation status against `main`

**Task:** `R0-03` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.

**Baseline:** `main` @ `00e0f47`, 2026-08-17. `uv run khepri-gov validate` passes; `uv run pytest`
reports 2154 passed, 45 skipped. Migration head `20260815_0016` (single head).

**Updated through `R7-01`.** This pass reconciles two independent derivations: the `R6-03`-era
status work proposed in `#196`, and the row edits the `R6-05` … `R6-08` evidence slices made in
`#197` … `#200`. `#196` was cut before those four merged, so its rows are re-derived here against
the current tree rather than replayed.

Four rows changed status, each verified against the code and not taken from either document:

| FR | Was | Now | Why |
|---|---|---|---|
| `FR-003` | Partial | Partial | Status unchanged; its gap said "No session exists" after `R3` shipped them. Clause 2 is now *asserted* rather than structural |
| `FR-026` | Not implemented | **Partial** | The checkpoint exists and is correct in isolation. Its gap previously said `R6-08` would close it; `R6-08` is merged and **asserts the absence** instead |
| `FR-027` | Not implemented | **Implemented** | One nullable `active_organization_id` makes "at most one" structural rather than validated |
| `FR-029` | Not implemented | **Implemented** | `switching.py:61` — the live membership lookup *is* the authorization; `R6-06` adds the dual-member case that catches accumulation |

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

| Status | Count | Change since `R2-10` |
|---|---|---|
| Implemented | 16 | — |
| Partial | 15 | +1 (FR-016, by `R4-02`) |
| Not implemented | 9 | −1 |

**16 + 15 + 9 = 40**, matching `FR-001` … `FR-040`. The change since `R2-10`/`R6-07` was
+3 Implemented (FR-027, FR-029, FR-030), +1 net Partial (FR-026 in, FR-027/FR-029 out), −3 Not
implemented; `R4-02` (`d50ffe6`) then moved **FR-016** from Not implemented to Partial — the domain
and hashed secret exist, the table and store do not. The previous rollup read 13/13/14 = 40 with
the right total but the wrong split: it excluded the one `Implemented, vacuously` row (FR-040) from
"Implemented". `R6-07` promotes exactly one row, `FR-030`; `FR-008` gains evidence but stays
`Partial` (see its row).

**A correction to this correction, recorded because the method matters more than the number.** An
earlier revision of this slice published 15/12/8 = 35, "counted from the requirement tables" — and
was wrong. The script that produced it matched rows shaped `| FR-0NN |` and silently skipped
`| FR-016 … FR-020 |`, the one collapsed row, so five invitation requirements vanished from the
total and were then described as `Implemented` when their own row says `Not implemented`. The
output looked clean and 35 ≠ 40 was visible on its face. A derived number is not verified until it
is checked against something independent of the tool that derived it. Found in review on `#199`.

"Partial" is used strictly: the requirement has real code behind it that does what it says for some
paths, and a named clause or scenario it does not yet cover. It is not a synonym for "started".

FR-015 stayed **Partial** rather than becoming Implemented, and the reason is worth stating: `R2`
closed its first clause exactly (two roles, CHECK-constrained) but the requirement also enumerates
owner capabilities, two of which — invite, and disable the organization — have no operation. Marking
it Implemented because the role *model* is finished would have been the easier reading and the wrong
one.

## The absences that explain the gap

24 requirements are not fully implemented (15 partial + 9 not implemented).

**Both structural absences this section was built around are now closed.** They are kept as history
rather than deleted, because the roadmap's critical path was derived from them:

| Absence | Status | Was blocking | Closed by |
|---|---|---|---|
| No session concept | **closed** | FR-003 clause 2, FR-007, FR-008 clause 2, FR-022 session half, FR-027, FR-029, FR-030, FR-035 session clause | `R3` — `sessions.py`, `session_service.py`, `actor_resolution.py` |
| No authorization layer | **closed** | FR-021, FR-022 … FR-025 general halves, FR-026, FR-028 | `R6` — `authorization.py` (`#193`), `authorization_resolution.py` (`#195`) |

The rows they blocked did not all become Implemented: several are `Partial` for reasons of their
own now (no object-level authorization path, no production consumer of `IsolationService`), which
is why closing two absences moved fewer rows than their counts suggest. FR-007 and FR-021 remain
`Not implemented` because they need `R5` recovery and a protected-action *abstraction* respectively,
neither of which `R3` or `R6` delivered.

**A third absence closed earlier.** At `ebfbe77` this table had a row reading "No membership write
operations — `OrganizationStore` exposes exactly one write, `create_organization`", blocking FR-012,
FR-013's remove/downgrade clauses, FR-014's second clause, FR-020, and FR-035's membership clause.
`R2` added promotion, demotion, and revocation, so four of those five are no longer blocked by it.
FR-020 remains blocked, but by invitations rather than by revocation.

**What now explains the remaining 20.** With all three structural absences closed, the gap is no
longer dominated by missing subsystems:

| Cause | Requirements | Count | Roadmap |
|---|---|---|---|
| Invitations have a domain but no service or table | FR-017, FR-018, FR-019, FR-020 | 4 | `R4-03` … `R4-06` |
| Invitations have no table or store | FR-016 | 1 | `R4-03` |
| Recovery does not exist | FR-005, FR-006, FR-007 | 3 | `R5` |
| **No production path routes through the canonical checkpoint** | FR-008, FR-009, FR-021, FR-022, FR-023, FR-024, FR-025, FR-026, FR-028, FR-031, FR-034, FR-038 | 12 | `R7-05` |
| Narrower single-clause reasons stated in their own rows | FR-001, FR-003, FR-015, FR-035 | 4 | various |

4 + 1 + 3 + 12 + 4 = **24**, matching the rollup. `R4-02` split the invitations cause in two rather than reducing it: `FR-016` is now `Partial` for a narrower reason than the other four, and collapsing them would hide that its remaining gap is a table rather than a subsystem. The set was checked against the requirement tables
directly, not assembled by hand: every row above appears in the tables as `Partial` or
`Not implemented`, and every such row appears above.

**One cause now dominates.** With all three structural absences closed, twelve of the twenty-four
trace to a single fact: `AuthorizationResolver` exists, is correct in isolation, and **nothing in
`src/` calls it** — `R6-08`'s `test_the_resolver_has_no_production_consumer_yet` asserts exactly
that absence, and its docstring says the tripwire "currently guards an empty room". `IsolationService`
is likewise instantiated nowhere outside tests. `R7-05` routes the first endpoint through the
resolver, and `KHEPRI-DEC-019` (`00e0f47`) unblocked that path. Those twelve rows move together or
not at all, which is why `R7` is the critical path rather than `R4` or `R5`.

**The `FR-027`/`FR-029` divergence flagged by `R6-07` is closed here.** Both read
`Not implemented` while `R6-03` (`#194`) had shipped `switching.py`; both are now `Implemented`
against the code. `FR-003`'s gap said "No session exists" after `R3` shipped sessions, and
`FR-026`'s said `R6-08` would close it when `R6-08` in fact asserts the absence rather than
removing it. Every count above is derived from the requirement tables below; if they disagree, the
tables win and this section is the defect.

That the two structural absences mapped one-to-one onto `R3` and `R6`, and the capability absences
onto `R4` and `R5`, was independent evidence for the roadmap's critical path — arrived at from the
code rather than from the roadmap. Both structural predictions have now been borne out by merge.

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
| FR-003 | Partial | `accounts.py:278-304` resolves exactly one `Account`; `sessions.py:89-101` carries one `account_id`; `actor_resolution.py:52-60` names the account row authoritative | `test_rca001_accounts.py:58`; `test_rca001_session_security_evidence.py:135`, `:142` | Clause 2 is now **asserted**, not merely structural: the identity record's columns are enumerated and no column names retail content. Clause 1's "resulting session" has no production path — nothing joins `AccountService.authenticate` to `SessionService.create`, and every caller of `create` is a test |
| FR-004 | Implemented | `accounts.py:230-249`, `:252-265`, `:298-304`; `DUMMY_SALT` at `credentials.py:31` | `test_rca001_accounts.py:64`, `:126`, `:148`, `:193`; `test_rca001_disablement.py:95` | — |
| FR-005 | Not implemented | — | — | No recovery secret, store method, or service |
| FR-006 | Not implemented | — | — | No recovery initiation to be uniform about |
| FR-007 | Not implemented | — | — | Doubly blocked: no recovery, and no sessions to invalidate |
| FR-008 | Partial | Clause 1: `accounts.py:244-249`, `:157-176`; `lifecycle.py:91-106`. Clause 2: `isolation.py:31-33` **and** `actor_resolution.py`, which calls `assert_account_active` at step 3 of every resolution | `test_rca001_disablement.py:60`, `:72`, `:130`, `:185`; `test_rca001_lifecycle.py:28`; `test_rca001_stale_session_authorization.py` (scenario 16) | The stale "no production caller" text predating `R3` is closed — `ActorResolver` is one, and "no dependence on session expiry" is asserted where it can fail. **Still Partial**, because clause 2 says *every* pre-existing session must cease to authorize **any** action: `promote_to_owner`, `demote_to_member`, and `revoke_membership` (`organizations.py:343-432`) take `actor_account_id` and perform no session or account check, and no production path gates them through `AuthorizationResolver`. The tests enter the resolver by hand, so they prove the selected paths only. Making bypass unreachable is `R6-08`'s subject; this row promotes when a production path exists. Found in review on `#199` |

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
| FR-016 | **Partial — domain only** | `R4-02` (`d50ffe6`, #215) supplies the record and its hashed secret in `invitations.py`: a sealed `Invitation`, the four states discriminated by nullability, `is_expired_at` as the single expression of the boundary, the `kci1.` token, scrypt at RRA's parameters, and a sealed `InvitationSecret` whose only door is `issue_secret` — provenance rather than a shape check, which is what establishes "persisted only as a strong salted hash". **No table and no store method**: `RCA_TABLES` in `test_rca001_migration.py` enumerates seven and `rca_invitations` is not among them, and `R4-03` owes it plus the two `CHECK`s and the sweeper. (An earlier draft of this row said *five*, carried over from the text it replaced — accurate before `R3-03` added `rca_sessions` and `rca_external_identities`, stale after. A number quoted from the prose being rewritten still needs checking against source.) |
| FR-017 … FR-019 | Not implemented | No service. Issuance and revocation are `R4-04`; redemption and the uniform-failure path are `R4-05`. **`FR-017`'s timing half is deliberately not in the domain** — `invitations.py`'s docstring records that `parse_token` and `verify_secret` cannot establish it alone, because the dummy lookup and dummy scrypt belong to the path that sequences them |
| FR-020 | Not implemented | Blocked by invitations alone since `R2` supplied revocation (`organizations.py:382`); it was doubly blocked at `ebfbe77`. The cascade is `R4-06`, reordered before `R4-05` |

### Authorization

| FR | Status | Code | Tests | Gap |
|---|---|---|---|---|
| FR-021 | Not implemented | — | — | No protected-action abstraction, and no session carrying the actor |
| FR-022 | Partial | `isolation.py:30-40` — three sequential guards, no permissive fallthrough | `test_rca001_isolation.py:141`, `:149`; `test_rca001_disablement.py:130` | Deny-by-default holds at `resolve_scope` only. Scenario 19 unverifiable without sessions |
| FR-023 | Partial | `isolation.py:34-36` — the decision is a membership lookup, not the supplied identifier | `test_rca001_isolation.py:141`; `test_rca001_cross_organization.py` (scenario 14) | Verified at organization-scope granularity only; no object-level authorization path exists. **`R6-06`'s carried gap** — the critical rule's object half ("object identifiers never grant authority") stays untestable until an object-level path is built |
| FR-024 | Partial | `isolation.py:34-36` | `test_rca001_isolation.py:141`, `:149`; `test_rca001_cross_organization.py` (scenarios 14, 15) | Scenario 15 is **partial**, not covered: the mutation runs behind the gate but the test enters the gate by hand, since no production path does. Cannot catch wiring that omits the gate. Still organization-granular |
| FR-025 | Partial | `isolation.py:32`, `:36`, `:39` — all three failure modes raise one `ScopeAccessDenied` | `test_rca001_isolation.py:149` — asserts one message across non-member, nonexistent org, and both, and that neither the org name nor a probe string appears | Not proven at object granularity |
| FR-026 | Partial | `authorization_resolution.py:60-131` — the resolver exists and composes `ActorResolver`, so steps 2, 3 and 4 of `R3-01` §4 run on one path | `test_rca001_authorization_resolution.py` (29 tests), notably `TestStepsTwoAndThreeStillRun` | The checkpoint now exists and is correct in isolation; **nothing routes through it**. A repo-wide search finds no use of `AuthorizationResolver` outside its own module, so `IsolationService.resolve_scope(account_id, organization_id)` remains publicly reachable with a caller-named organization. A checkpoint no production path passes through authorizes nothing. `R6-08` is **merged and does not close this**: `test_the_resolver_has_no_production_consumer_yet` asserts the absence rather than removing it, and its own docstring says the tripwire "currently guards an empty room". `R7-05` is what closes it, by routing an endpoint through the resolver — `KHEPRI-DEC-019` unblocked that path |
| FR-027 | Implemented | `sessions.py:92-95` — one nullable `active_organization_id`; column `persistence.py:191` | `test_rca001_sessions.py`; `test_rca001_session_service.py:80`; `test_rca001_organization_switching.py:85`; `test_rca001_session_security_evidence.py:142`, `:158` | — Satisfied structurally rather than by validation: one nullable column cannot hold two organizations. `test_switching_between_two_organizations_replaces_rather_than_accumulates` asserts the switch replaces, `test_a_new_session_starts_with_no_active_organization` asserts the at-most, and `test_the_columns_are_exactly_the_six_identity_carries` fixes the shape against a second column appearing |
| FR-028 | Partial | Clause 1: `accounts.py:278-304` never consults membership. Clause 2: `isolation.py:34-36` | Clause 2: `test_rca001_isolation.py:141` | Clause 1 holds incidentally and is unasserted; scenario 18 has no test |
| FR-029 | Implemented | `switching.py:48-63` — the membership lookup *is* the authorization; persisted through `session_service.py:113-128`; consumed by `authorization_resolution.py:145-163` | `test_rca001_organization_switching.py` (16 tests): `:64`, `:70`, `:85`, `:111`, `:119`, `:138`, `:225`; `test_rca001_authorization_resolution.py` `test_a_reused_resolver_observes_a_switch` | — Clause 1 closed exactly: a non-member and an unknown organization are refused identically, membership is read from the store per switch, and a revoked membership cannot be switched into. Clause 2 closed by `R6-04`: `active_organization_id` is read by `_context_for` on every resolution, and a switch through a *held* resolver changes the next decision, which is what "every subsequent authorization decision" names. `R6-06` adds the dual-member case — an actor in both A and B, active in A, is refused B — which is the only arrangement that catches an implementation accumulating access instead of replacing it |
| FR-030 | Implemented | `authorization_resolution.py:_context_for` reads the membership per call; `AuthorizationContext` carries no `resolved_at` that would invite reuse | `test_rca001_authorization_resolution.py` (`TestOneResolverHeldAcrossAChange`); `test_rca001_stale_session_authorization.py` (scenario 20) | Scenario 20 **now tested**. Both clauses asserted: the change takes effect with no clock movement between the two resolutions, and the session is separately asserted to still resolve afterwards — "without requiring the affected session to end" is invisible at the refused call |

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
over `{owner, member, non-member, unauthenticated}` × every protected action.

**`R6-05` supplies a *partial* matrix for `R6-01` §3.1** — **19 of 20 cells**, in
`tests/test_rca001_authorization_matrix.py`. Five organization-scoped actions × four actor kinds,
each `DENY` cell driving the verb through the gate and asserting the membership is unchanged rather
than only that an exception was raised.

**The missing cell is scope resolution × `unauthenticated`**, for the reason in carried gap 0
below: `resolve_scope` authenticates nobody, so the cell is not expressible at that surface. The
matrix is **not** complete and `RCA-001`'s Verification requirement is **not** satisfied by this
slice — recorded explicitly because a "matrix supplied" line is exactly what a later reader would
cite to call verification done. Found in review on `#197`.

**Scenario 13 is tested.** `TestSwitchActiveOrganization` covers the permitted owner/member
switches and the denied non-member/unauthenticated ones, and
`test_rca001_organization_switching.py:70-107` verifies persistence and replacement across two
organizations — together that is scenario 13's governed outcome ("switch succeeds only into a
current membership"). It was listed as untested here; found in review on `#197`.

**Scenario 18 is tested. Scenario 19 is partial.** Scenario 19 requires a stale or invalid session
to be denied for *every* protected action, and `TestScenarioNineteen` exercises only the resolver
methods: the six §3.2 account-scoped actions are uncovered (carried gap 1), as is the isolation
cell above. Scenarios **4, 6, 7, 8, and 9** remain untested; 14 and 15 are `R6-06`'s, and 16 and
20 are `R6-07`'s below.

### Carried gaps from `R6-05`

0. **The matrix is exhaustive by construction** (`tasks.md:191`), not by convention:
   `test_every_protected_action_in_the_design_has_a_matrix_class` parses `R6-01` §3.1's own table
   and fails when an action there has no test class. `R4` and `R5` extend that table by design, so
   this is what makes those slices notice they owe the matrix a row. Verified by adding an
   invitation row to the design note and watching it fail.

1. **Scope resolution's `unauthenticated` cell is uncovered.** `IsolationService.resolve_scope`
   takes an `account_id` and no token, so it authenticates nobody — a caller who merely knows a
   member's identifier resolves that member's scope, which is the identifier doing a credential's
   work that `R6-01` §5's critical rule forbids. Passing an unknown identifier exercises the
   nonexistent-account branch, **not** the unauthenticated column, and the first version of this
   slice named such a test `test_an_unauthenticated_caller_is_refused` — the name asserted a cell
   the test never reached. Found in review on `#197`. The exposure is latent (`FR-031`:
   `IsolationService` has no production caller) and the authenticated boundary is `R7`'s;
   `test_the_unauthenticated_cell_is_unreachable_at_this_surface` asserts the signature so the gap
   fails loudly the moment that boundary arrives.
2. **`R6-01` §3.2 is not covered, and cannot be at this shape.** The six account-scoped actions turn
   on self-versus-another-account, and `AuthorizationContext` carries the acting `account_id` with
   no target. `authorization_resolution.py`'s docstring defers this to an `R6-02` change. Covering
   §3.2 requires that change first; it is not a test-only slice.
3. **The three owner-only verbs check no authority of their own.** `promote_to_owner`,
   `demote_to_member`, and `revoke_membership` take `actor_account_id` for *attribution* only, so a
   direct call from a member succeeds. `R6-04` placed the check in the gate rather than in the
   verbs; the matrix therefore drives each action through `require_owner`, which is the authorized
   route. **That the gate is the *only* route is unproven until `R6-08`** — this is precisely the
   hole that slice exists to close, and `R6-04`'s docstring records four deliberate exclusions
   without recording this one.

**`R6-06` supplies scenarios 12 and 14, and takes 15 from untested to *partial***, in `tests/test_rca001_cross_organization.py`.
Scenario 15's "no state change in **either** organization" is asserted on both sides: the target
organization *and* the actor's own, since a gate that authorized against the active organization
while refusing the named one would leave the target untouched and still be the defect.

**Why 15 is partial and not covered.** The mutation now runs behind the gate, but the test enters
the gate by hand -- `require_owner` has no caller under `src/` besides its own definition, and the
membership verbs remain callable without it. So these cells cannot catch production wiring that
omits or reorders the gate, which is the failure mode scenario 15 ultimately guards. The row
promotes when a production protected-mutation path exists (`R7`). Found in review on `#198`.

Scenarios still untested here: **4, 6, 7, 8, 9, 13, 20**. (`18` and `19` are `R6-05`'s; `20` is
`R6-07`'s.)

### Carried gap from `R6-06`

**Indistinguishability is proven at organization granularity only.** `FR-023`'s object half — the
critical rule's "object identifiers never grant authority" — has no test because no object-level
authorization path exists to test. Building one is `R7`/`W1` work, not a test-only slice.

One note for whoever extends these tests: scenario 14's message-comparison holds *structurally*,
because a nonexistent organization has no membership row and is refused by the same guard as a
foreign one. A mutant that rewords that guard therefore leaves the comparison green without
reintroducing the oracle — correctly, since such a mutant does not reintroduce the enumeration
oracle either. A test pinning the *call order* was written and removed (`#198`): its only unique
kill-set was implementations that check existence first and still return one refusal shape, which
this document's own type-plus-message definition calls compliant.

---

## `R6-08` — what the chokepoint evidence does and does not establish

`tests/test_rca001_resolver_chokepoint.py`. The task title says "making bypassing the resolver
unreachable"; **unreachable is not claimed and is not achievable**, and the file says so in the
register `authorization.py` set — the boundary is *unmistakable*, never *unbypassable*.

What is asserted, each verified by introducing the defect and watching the test fail:

| Claim | Fires on |
|---|---|
| No module in **any production package** calls the three owner-only verbs | a probe calling `promote_to_owner` directly, planted in `khepri/runtime` |
| No module in **any** production package calls `object.__new__`/`object.__setattr__` | a probe forging a record, planted in `khepri/runtime` |
| No `khepri.rca` module calls `dataclasses.replace` on a sealed record | a probe calling it on a context |
| No module constructs an `AuthorizationContext` outside `create`, **aliases resolved** | a probe spelling the class directly, and one using `import ... as auth` |
| `AuthorizationResolver` still has no production consumer | a probe importing it |

The verb and construction scans cover every production package — `runtime`, `local`, `infra`, and
`rra`, not just `rca` — because `runtime`/`local` are exactly where wiring that calls a membership
verb will live, and a scan confined to `rca/` would miss the bypass it exists to catch (`#200` P1).
The escape scan is split by what it looks for rather than by package: `object.__new__` and
`object.__setattr__` have no legitimate use anywhere and are scanned repo-wide, while only
`dataclasses.replace` stays `rca`-scoped, because that call *does* have ordinary uses — six of them
in `khepri.rra`.

Each scanner is additionally self-tested against known-bad and known-good sources, following
`test_rca001_boundary.py::test_rca_import_checker_flags_and_clears_expected_cases`. Without that, a
scanner broken into returning `[]` would pass every assertion above it.

### Two gaps `R6-08` records rather than closes

1. **The three owner-only verbs check no authority of their own.** They take `actor_account_id` for
   *attribution* only, so a direct call from any caller succeeds. `R6-04` placed the check in the
   gate, which is coherent — but `R6-04`'s docstring enumerates four things deliberately left out
   of the resolver and does not mention this fifth one, so the decision `R6-01` §7 flagged
   ("where that check lives") was made in code without being recorded in prose. Closing it means
   giving the verbs a context parameter: an `R6-02` change, not a test-only slice.
2. **The tripwire currently guards an empty room.** No production module consumes
   `AuthorizationResolver`, because the HTTP surface that would is `R7`/`R8`. The inventory is
   therefore *preventative* — it will catch the first bypass and has caught none because none has
   been possible. A green run must not be read as "every handler is gated"; there are no handlers.
   `test_the_resolver_has_no_production_consumer_yet` asserts this explicitly so the caveat cannot
   be lost, and instructs its own replacement when the first consumer arrives.

**`R6-07` supplies scenarios 16 and 20**, in `tests/test_rca001_stale_session_authorization.py`.


### A note on what `R6-07` adds beyond `R6-04`

Demotion is the load-bearing case, because it is the only change of the three where the actor keeps
*some* authority — revocation and disablement are total, so "lost something" and "lost everything"
are indistinguishable for them. The new claim is the **consequence** of a demotion: the demoted
actor's member-permitted actions still work and resolve the *same* isolation key. Verified by
mutating `demote_to_member` into `revoke_membership`; `R6-04` catches that with one test, `R6-07`
with three.

One mutant to not repeat: caching the role on the `Session` object appears to introduce `FR-030`
staleness and does not, because `Session` is `slots=True` and the write silently fails. A mutant
that genuinely caches must hold state on the resolver; that one is killed by three tests here.

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
