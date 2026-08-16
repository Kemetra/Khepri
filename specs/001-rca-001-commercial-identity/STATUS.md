# RCA-001 — implementation status against `main`

**Task:** `R0-03` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.

**Baseline:** `main` @ `2fbeba0`, 2026-08-16. `uv run khepri-gov validate` passes; `uv run pytest`
reports 2075 passed, 47 skipped. Migration head `20260815_0016` (single head).

**Updated for `R6-03`.** Eight further slices merged since `95760a4`: `R3-05` … `R3-08` and `R3-10`
as `#186` … `#191`, and `R6-01` … `R6-03` as `#192` … `#194`, on top of the `R3-02` … `R3-04`
session slices (`#182` … `#185`). Four requirements changed status and ten more had their gaps
rewritten; all are re-derived from the code as it stands, not from the roadmap's claims about it.

**`R6-04` is not in this baseline.** Live membership and role resolution — step 4 of `R3-01` §4, the
chokepoint every protected action is meant to pass through — is in flight and had not merged at
`2fbeba0`. Every row below that names `R6-04` as its blocker was written without sight of it, as was
the absence table's single remaining row. A reader at a later commit should re-derive those rows
rather than trust them.

**This file records status only.** It does not restate, interpret, or amend any requirement.
`governance/specifications/RCA-001.md` is the only authoritative source of what RCA-001 requires,
and `governance/registry.yaml` is the only authoritative source of its lifecycle state. Where this
file and either of those disagree, they win and this file is the defect.

**Why it exists.** Slices of RCA-001 are merged (`#148`, `#153`, `#157`, then the `R1` account
lifecycle, the `R2` membership slice `#150`, the `R3` session slices, and the first three `R6`
slices) and `RCA-001` is `active`, but nothing recorded which requirements those slices actually
satisfied. Without that, the next slice cannot be scoped without re-deriving it, and an agent
reading the sibling planning documents in this directory would rebuild merged code. See
`SUPERSEDED.md`.

---

## Rollup

| Status | Count | Change since `95760a4` |
|---|---|---|
| Implemented | 15 | +2 (FR-008, FR-027) |
| Partial | 14 | +1 |
| Not implemented | 11 | −3 |

"Partial" is used strictly: the requirement has real code behind it that does what it says for some
paths, and a named clause or scenario it does not yet cover. It is not a synonym for "started".

Three rows moved out of **Not implemented** — FR-027 to Implemented, FR-029 and FR-030 to Partial —
and FR-008 moved from Partial to Implemented. That ratio is what a session layer without a decision
layer looks like. Eight requirements gained the artifact their gap named (a session, a switch, a
revocation of every session for an account): FR-003, FR-007, FR-008, FR-022, FR-027, FR-029, FR-030,
and FR-035. Only two of them reached Implemented, because the rest stopped short at the same place —
nothing yet *decides* anything from the artifact. `R6-04` is that decision path, and it is not in
this baseline.

FR-029 is the sharpest case and worth stating. Its first clause is closed exactly — `switch` refuses
a non-member, and refuses an unknown organization identically — and its second clause is *persisted*
rather than satisfied: `point_at_organization` writes through `save_session`, so a future reader
would see the switch, but `active_organization_id` is read by nothing outside the session record and
its store. A clause whose effect no decision consumes is not yet in effect. Marking it Implemented
because the write lands would have been the easier reading and the wrong one.

FR-015 stayed **Partial** rather than becoming Implemented, and the reason is worth stating: `R2`
closed its first clause exactly (two roles, CHECK-constrained) but the requirement also enumerates
owner capabilities, two of which — invite, and disable the organization — have no operation. Marking
it Implemented because the role *model* is finished would have been the easier reading and the wrong
one.

## The absences that explain the gap

25 requirements are not fully implemented (14 partial + 11 not implemented). **9 of them** trace to
one missing piece, an existing roadmap program:

| Absence | Verified by | Blocks | Count | Roadmap |
|---|---|---|---|---|
| No decision path — no checkpoint every protected action passes through, and no live membership/role resolution | `AuthorizationContext` is constructed nowhere in `src/`; `active_organization_id` is written and rehydrated but read by no decision | FR-021, FR-022 … FR-025 general halves, FR-026, FR-028 clause 2, FR-029 clause 2, FR-030 clause 1 | 9 | `R6-04` |

FR-035 is the tenth requirement this absence touches but is **not** blocked by it. Its remaining
clauses are testable at this baseline — both sessions and switches exist — and simply untested. That
is a task, not a dependency, and the distinction matters when scoping: the other nine cannot be
closed before `R6-04`, and FR-035 can.

**The session absence is now closed.** At `95760a4` this table had a second row reading "No session
concept — every `session` token in `src/khepri/rca/` is a docstring or SQLAlchemy's
`sessionmaker`/`Session`", blocking FR-003 clause 2, FR-007, FR-008 clause 2, FR-022's session half,
FR-027, FR-029, FR-030, and FR-035's session clause. `R3` built the record (`sessions.py`), its
store (`session_persistence.py`), its lifecycle (`session_service.py`), the account chokepoint
(`actor_resolution.py`), the transport (`session_cookie.py`), and the sweeper
(`session_retention.py`). Two of those eight are now Implemented (FR-008, FR-027). FR-029 and FR-030
moved from Not implemented to Partial. FR-003, FR-022, and FR-035 were already Partial and had their
gaps rewritten. FR-007 remains Not implemented, blocked now by recovery alone rather than doubly.

**The authorization-layer row was restated rather than retired.** It read "No authorization layer —
no `authorization.py`; no protected-action abstraction". `authorization.py` now exists, so that
evidence is stale, but the absence it named is not closed: `R6-01` catalogued the protected actions
as a document and `R6-02` built the *inputs* type a decision is made from. Neither is a checkpoint,
and `authorization.py`'s own docstring says so. The absence above is the narrower thing that
persists.

Two capability absences account for another **8**: invitations do not exist (FR-016 … FR-020, `R4`)
and recovery does not exist (FR-005, FR-006, FR-007, `R5`). None of those eight overlaps the row
above, so the running total is **17 of 25**.

The remaining **8** — FR-001, FR-003, FR-009, FR-015, FR-031, FR-034, FR-035, FR-038 — are not
blocked by a missing subsystem. They are partial for narrower reasons stated in their rows: an
unasserted clause (FR-001), an unjoined path (FR-003 — nothing connects authentication to session
creation), an
unwired service (FR-009, FR-031, FR-034, FR-038 all still trace to `IsolationService` being
instantiated nowhere outside tests, which `local/wiring.py` confirms: it now builds the session
store and the session sweeper, and still no isolation path), unbuilt owner capabilities (FR-015),
and an untested-but-testable clause (FR-035).

That the one remaining structural absence maps onto `R6-04`, and the two capability absences onto
`R4` and `R5`, is independent evidence for the roadmap's critical path — arrived at from the code
rather than from the roadmap.

## Two gaps `R2` recorded rather than closed

Both were found by probing rather than assumed, are asserted in
`tests/test_rca001_guard_evidence.py`, and each is latent, needing a change that did not belong in a
test-only slice:

| Gap | Evidence | What closing it needs |
|---|---|---|
| `rca_membership_events` has no role CHECK — a forged `next_role` is stored without complaint | `test_the_event_table_does_not_constrain_its_roles` | A migration. `FR-014` attribution naming a role that cannot exist in live state is two sources disagreeing about one fact |
| `Membership.create` and `MembershipEvent.role_changed` accept any string as a role | `test_the_domain_records_do_not_validate_roles_either` | Domain validation against `ROLES`, or a documented decision that the narrow service surface is the guard |

What prevents forgery on the membership path is the *shape of the interface*, not validation:
`promote_to_owner`/`demote_to_member` each name their destination role, so no parameter exists to
forge. `test_no_role_change_operation_accepts_a_role_from_its_caller` fails if any operation grows
one — which is the moment validation stops being optional.

**At `95760a4` this section read "not currently reachable — no service accepts a role as input". That
is no longer true.** `AuthorizationContext.create` (`authorization.py:82-102`) takes a `role` and is
the first surface here to do so; it validates against `ROLES` itself, which is why no new gap opens.
But the guard-evidence test's scope is narrower than its name suggests: it enumerates
`OrganizationService` members only, so a role-accepting surface outside that class passes it
unexamined. The two gaps below remain open on the paths they name, and the interface-shape argument
now covers the membership operations rather than the package.

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
| FR-007 | Not implemented | — | `session_service.py:130-140` `revoke_all` exists and cites this requirement | Singly blocked now: the invalidation half exists (one statement, so a session issued between read and write cannot slip through), but there is no recovery to complete (`R5`) |
| FR-008 | Implemented | Clause 1: `accounts.py:244-249`, `:157-176`; `lifecycle.py:91-106`. Clause 2: `actor_resolution.py:76-90` is the first and only production caller of `assert_account_active` | `test_rca001_disablement.py:60`, `:72`, `:130`, `:185`; `test_rca001_lifecycle.py:28`; `test_rca001_actor_resolution.py:82`, `:101`, `:117`, `:149` | — Clause 2's hard part is "with no dependence on session expiry": `test_disablement_takes_effect_on_the_very_next_resolution` holds the session live and unexpired and changes only the account. `test_the_session_itself_is_untouched_by_disablement` keeps the two mechanisms distinct, and `test_the_chokepoint_has_exactly_one_production_caller` pins the call site by AST rather than substring |

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
| FR-016 … FR-020 | Not implemented | Entirely absent. No `Invitation` type, no `rca_invitations` table (`test_rca001_migration.py:50-57` enumerates seven: accounts, organizations, memberships, isolation_scopes, membership_events, sessions, external_identities), no store method. FR-020 was doubly blocked at `ebfbe77`; `R2` supplied revocation (`organizations.py:382`), so it is now blocked by invitations alone (`R4`) |

### Authorization

| FR | Status | Code | Tests | Gap |
|---|---|---|---|---|
| FR-021 | Not implemented | — | — | A session now carries the actor, so half the old gap is closed. But no protected action resolves one: `R6-01` catalogued the actions as a document and `R6-02` built the inputs type, and `AuthorizationContext` is constructed nowhere in `src/` |
| FR-022 | Partial | `isolation.py:30-40` — three sequential guards, no permissive fallthrough; `session_service.py:78-93` — absent, unknown, expired, and revoked all raise one `AuthenticationFailed` | `test_rca001_isolation.py:141`, `:149`; `test_rca001_disablement.py:130`; `test_rca001_session_service.py:151` | Scenario 19 is now covered at session resolution — `test_every_refusal_is_indistinguishable` asserts one refusal across every stale-or-invalid cause. Deny-by-default still holds only at `resolve_scope` and `resolve`, not at a checkpoint an action without an explicit permitting rule passes through (`R6-04`) |
| FR-023 | Partial | `isolation.py:34-36` — the decision is a membership lookup, not the supplied identifier | `test_rca001_isolation.py:141` | Verified at organization-scope granularity only; no object-level authorization path exists |
| FR-024 | Partial | `isolation.py:34-36` | `test_rca001_isolation.py:141`, `:149` | Scenario 15 (cross-org mutation, no state change in either) has no test and no mutating protected action to test |
| FR-025 | Partial | `isolation.py:32`, `:36`, `:39` — all three failure modes raise one `ScopeAccessDenied` | `test_rca001_isolation.py:149` — asserts one message across non-member, nonexistent org, and both, and that neither the org name nor a probe string appears | Not proven at object granularity |
| FR-026 | Not implemented | — | — | No canonical checkpoint. `isolation.py:14` is one chokepoint for one capability, and `actor_resolution.py` is one chokepoint for account activity; neither is a checkpoint every protected action passes through. `R6-01` enumerated the actions and `R6-02` built the inputs type — a catalog and a record are not a checkpoint, and `authorization.py:50-56` says so |
| FR-027 | Implemented | `sessions.py:92-95` — one nullable `active_organization_id`; column `persistence.py:191` | `test_rca001_sessions.py`; `test_rca001_session_service.py:80`; `test_rca001_organization_switching.py:85`; `test_rca001_session_security_evidence.py:142`, `:158` | — Satisfied structurally rather than by validation: one nullable column cannot hold two organizations. `test_switching_between_two_organizations_replaces_rather_than_accumulates` asserts the switch replaces, `test_a_new_session_starts_with_no_active_organization` asserts the at-most, and `test_the_columns_are_exactly_the_six_identity_carries` fixes the shape against a second column appearing |
| FR-028 | Partial | Clause 1: `accounts.py:278-304` never consults membership; `sessions.py:92-95` makes "authenticated, in no organization" representable. Clause 2: `isolation.py:34-36` | `test_rca001_authorization_context.py:57`, `:172`; `test_rca001_organization_switching.py:218`; `test_rca001_isolation.py:141` | Clause 1 is now asserted — scenario 18 has three tests, and `switching.py:65-77` makes clearing a normal state rather than a refusal. Clause 2 ("denied **every** organization-scoped action") holds at `resolve_scope` alone; there is no set of organization-scoped actions to be denied all of (`R6-04`) |
| FR-029 | Partial | `switching.py:48-63` — the membership lookup *is* the authorization; persisted through `session_service.py:113-128` | `test_rca001_organization_switching.py` (16 tests): `:64`, `:70`, `:85`, `:111`, `:119`, `:138`, `:225` | Clause 1 closed exactly: a non-member and an unknown organization are refused identically, membership is read from the store per switch (`test_it_does_not_read_the_sessions_own_active_organization`), and a revoked membership cannot be switched into. Clause 2 ("take effect for every subsequent authorization decision") is persisted but unconsumed — `active_organization_id` is read by no decision anywhere in `src/`, so there is no subsequent decision for it to take effect for (`R6-04`) |
| FR-030 | Partial | Nothing caches authority: `sessions.py:76-86`, `actor_resolution.py:38-47` carry no role or membership; `switching.py:65-77` `clear` ends authority in one organization without ending the session | `test_rca001_organization_switching.py:138`, `:188`, `:225`; `test_rca001_session_security_evidence.py:179`, `:193` | Clause 2 has real code — the session survives while its organization pointer is cleared, which is exactly what the clause describes. Clause 1 ("take effect for authorization decisions made after it") has no authorization decision to take effect for; scenario 20 remains untestable pending `R6-04`. The absence of caching is the hard half and is asserted, not assumed |

### Isolation and the RRA boundary

| FR | Status | Code | Tests | Gap |
|---|---|---|---|---|
| FR-031 | Partial | `isolation.py:11-40` — returns `owner_id` as a bare `str` and deliberately mints no `SessionScope` (rationale `:14-17`) | `test_rca001_isolation.py:46`, `:56`, `:64` | Mapping is unit-tested but unexercised: `IsolationService` is instantiated nowhere outside tests, so no commercial actor reaches an RRA capability |
| FR-032 | Implemented | `organizations.py:98-104`, `:127-130` — `create` has no `owner_id` parameter, so a chosen key is unexpressible rather than rejected | `test_rca001_isolation.py:101` (7 adversarial names, sliding-window check), `:114`; `test_rca001_persistence.py:303` | — |
| FR-033 | Implemented | `organizations.py:107-135`; `persistence.py:88-101` | `test_rca001_isolation.py:101`, `:114` | — |
| FR-034 | Partial | `isolation.py:32`, `:36`, `:39` → uniform `SCOPE_FAILURE` | `test_rca001_isolation.py:149` | Verified at `resolve_scope`; no cross-scope access through a commercial actor exists yet |
| FR-035 | Partial | `_from_storage` preserves the stored key (`organizations.py:132-135`); `UniqueConstraint("owner_id")` `persistence.py:91` | `test_rca001_isolation.py:64`, `:100` (across a demotion), `:125` (revocation ends access), `:148`; `test_rca001_persistence.py:224`, `:639` | "Across membership changes" is asserted. "Across sessions" and "across active-organization switches" changed from *unverifiable* to **testable and untested**: both concepts now exist (`sessions.py`, `switching.py`) and no test in `test_rca001_isolation.py` resolves a scope on either side of a session boundary or a switch. The Verification section's bridge test requires exactly that |
| FR-036 | Implemented | verified by absence, re-checked across the nine modules `R3` and `R6` added: zero `khepri.rra` imports in `src/khepri/rca/` — the only occurrence of the string is a docstring cross-reference at `persistence.py:515` | `test_rca001_boundary.py:135`; `test_rca001_migration.py:262`; `test_rca001_session_security_evidence.py:258` | Still satisfied vacuously — no commercial actor reaches an RRA capability yet. The session modules are now covered by an explicit direction test (`test_no_session_module_imports_rra`), which the rest of the package still lacks; `test_rca001_boundary.py:96` tests RRA→RCA |
| FR-037 | Implemented | table namespace separation; one-directional import rule `test_rca001_boundary.py:63-105` | the three slice diffs touched zero `test_rra*` files | — |
| FR-038 | Not implemented | — | — | No commercial actor can reach an RRA capability, so these controls have nothing to hold for. Nothing in `src/khepri/rca/` touches them |
| FR-039 | Implemented | RCA declares its own `DeclarativeBase` (`persistence.py:24-25`) with no FK to any `rra_` table | `test_rca001_boundary.py:96` (AST scan, self-checked at `:108`); `test_rca001_migration.py:262` | — |
| FR-040 | Implemented, vacuously | verified by absence, re-checked at this baseline: zero `logging`, `logger`, or `print(` in `src/khepri/rca/`; `PurgeReport` carries counts only | `test_rca001_isolation.py:149`; `test_rca001_retention.py:64`; `test_rca001_session_security_evidence.py:267` | Holds because nothing logs. The session path is now guarded — `test_the_session_path_logs_nothing` fails if one of those modules grows a log statement — so the old "unguarded by any test" caveat narrows to the rest of the package. `FINAL_OWNER_FAILURE` is a deliberate content-bearing exception documented at `errors.py:8-18`, not a breach |

---

## Scenario coverage

The specification's Verification section requires a test per scenario, each **named for the scenario
it verifies**, and an authorization matrix over `{owner, member, non-member, unauthenticated}` ×
every protected action.

**Naming has started.** At `95760a4` no RCA-001 test named a scenario number; six now do — scenarios
10, 11, 17 (`test_rca001_revocation.py:88`, `:174`, `test_rca001_role_transitions.py:181`) and 18
(`test_rca001_authorization_context.py:57`, `:172`, `test_rca001_organization_switching.py:218`).
The remaining named scenarios are covered by tests that do not cite the number, which does not
satisfy the Verification bullet as written.

**There is still no matrix test.** `R6-01` delivered the matrix as a document; the Verification
section requires a test, and a catalog is not one.

Scenarios with no corresponding test: **4, 6, 7, 8, 9, 14, 15, 20**. Three moved off this list —
13 (`test_rca001_organization_switching.py`, switching in and every refusal), 18 (three tests), and
19 (`test_rca001_session_service.py:151`, one refusal across every stale-or-invalid cause). The
eight that remain are exactly what the surviving absences predict: recovery (`R5`) covers 4,
invitations (`R4`) cover 6 … 9, and the decision path (`R6-04`) covers 14, 15, and 20.

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
5. **`test_no_role_change_operation_accepts_a_role_from_its_caller` is narrower than its name.** It
   enumerates `OrganizationService` members only, so `AuthorizationContext.create` — which does take
   a caller-supplied role — passes it unexamined. That surface validates against `ROLES` itself, so
   nothing is currently unguarded, but the test no longer covers every role-accepting surface and
   the next one to appear will not trip it.
6. **Nothing joins authentication to session creation.** `AccountService.authenticate` returns an
   `Account` and `SessionService.create` takes an `account_id`; no production code calls both. Until
   something does, FR-003's "the resulting session" names an artifact no path produces, and the
   `R3` session work is reachable only from tests.
7. **`identity.py` (`R3-10`) moved no requirement, deliberately.** It is governed by
   `KHEPRI-DEC-018`; no FR in RCA-001 names an external identity provider, and `A-4` leaves the
   choice a plan-level decision. It is recorded here so a later reader does not mistake its absence
   from the table for an oversight. The same applies to `R6-01`, which is a document.
