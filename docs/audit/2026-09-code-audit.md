# Khepri Code Audit — 2026-09-22 (Revision 2)

Read-only deep audit of `src/khepri` and `src/khepri_gov` (218 modules, ~64k lines) and of the
test suite (311 files, 4,283 test functions). No product code was changed. This register is a
proposal input: every fix lands only as its own spec-linked slice. Items marked **OWNER** need
a decision before any slice is admissible.

- **Audited commit:** `5de5376` (`main`).
- **Revision 2** applies both adversarial verdicts (both REVISE; see §9 and
  `2026-09-adversarial-verdicts.md`). The captain re-verified every applied change against the
  code. Revision 1 is kept outside the repo for comparison.
- **Method:** nine expert passes (domain ×3, application ×2, security ×2, database, test
  quality), then CodeScene on the hotspots (§2), then the captain verifying every HIGH, then two
  independent adversarial judges under `.grok/skills/khepri-adversarial-review`. One expert HIGH
  was **refuted by reproduction** (§6).
- **Verdicts:**
  - **REPRODUCED:** run and observed.
  - **CONFIRMED:** traced by the captain.
  - **CONFIRMED (expert):** traced by one expert only.
  - **PLAUSIBLE:** code shape present, trigger not reproduced.
- **Severity:**
  - HIGH: a reachable wrong result, broken security or privacy guarantee, or outage.
  - MEDIUM: wrong customer text, a robustness gap, a test that cannot catch a real defect, or a
    HIGH-class defect whose trigger no shipped path reaches.
  - LOW: hygiene or defence in depth.

**Governing artifacts cited:** KHEPRI-DEC-015, KHEPRI-DEC-029, KHEPRI-DEC-033, RCA-001, RCA-008,
RRA-003, RRA-004, RRA-006, RRA-007, RRA-009 and RRA-014. All are `active` in
`governance/registry.yaml`.

## 1. Baseline gates

| Gate | Result |
|---|---|
| `uv run khepri-gov validate` | pass |
| `uv run ruff check .` | pass |
| `uv run pytest` (isolated worktree at `5de5376`, `dirty=0`) | **pass**: 6,173 passed, 0 failed, 97 skipped, 2 xfailed (12m51s) |

Two earlier live-checkout runs failed, and neither failure belongs to `main`:

1. **A `git pull` landed mid-run** at 23:38:03. The process had imported the old `shell_copy.py`
   and then read #515's new template, producing `UndefinedError: overview_hero_alt`.
2. **Another session's uncommitted hero edits** caused 37 failures across `u1_05`, `w106`,
   `w108`, `w110` and `rca012`. That session has since moved the shared checkout to branch
   `feat/u1-analysis-hero-placement`.

**For the fix phase:** run every slice in its own worktree. The shared checkout is not a stable
baseline.

## 2. Code Health and structure

**CodeScene, the repo's required PR gate:**

| Score | Files |
|---|---|
| **5.95** | `rra/facts.py` |
| **6.06** | `rra/narrative.py` |
| 7.52 | `rra/api.py` |
| 7.78 | `rra/bundle.py` |
| 9.09 | `rca/persistence.py` |
| 9.21 | `runtime/shell_api.py` |
| 9.38 | `rra/rendering/excel.py` |
| 10.00 | `runtime/wiring.py`, `runtime/shell_decisions.py`, `runtime/workspace_recording.py`, `rra/semantic_views/projection.py` |

Several HIGH defects sit in files that score 10.00. Code Health measures maintainability, not
correctness.

**Static structure (AST, `src/`):**

- 2,403 functions: 64 over 50 lines, 10 over 100, none nested deeper than 4, 12 with more than
  6 arguments, 3 with more than 15 branches.
- Worst: `rra/facts.py:1021` `_build` (414 lines, 38 branches) and `rra/api.py:147` `create_app`
  (301 lines).
- Extended ruff families produce 98 hits, all triaged, none a bug (§6).

## 3. Findings register

### HIGH

| ID | Location | Defect and failure scenario | Verdict | Fix direction |
|---|---|---|---|---|
| **A-02** | `rca/session_persistence.py:99-108` `save_session`, reached through `session_service.py:120` `point_at_organization` and `:115` `revoke` | **A session revoked by account recovery can come back to life.** `save_session` writes `row.revoked_at = session.revoked_at` from the caller's snapshot. **Shipped path:** `external_auth_api.py:123` mints a session from a verified provider credential, then `:124` switches it. If recovery's `revoke_all` (FR-007) commits between those two lines, the switch writes `revoked_at = NULL` and the new session survives recovery. That breaks DEC-015:76 and RCA-001 FR-007. The window is narrow. FR-008 disablement still holds because `assert_account_active` runs on every request. | **REPRODUCED** (SQLite, real store and service; see §8) | A column-scoped `UPDATE … SET active_organization_id=:x WHERE session_id_hash=:h AND revoked_at IS NULL` that returns False when no row matches. Route `revoke`'s write through a single-statement update too. Never write `revoked_at` from a snapshot. |
| **A-03** | `rra/claim_queue.py:170` `_next_claimable` vs `rra/job_persistence.py:179` `lease` | **One stuck job can stall the report queue for every tenant.** The pick query omits the `session_id IN _live_content_sessions()` filter that `lease` applies. The oldest due job in a deletion-requested session is picked on every poll and never leased, and the worker runs one job at a time. **Triggers:** (1) a crash between deletion's `begin` (sets `deletion_requested_at`) and `defer_for_publication` (dead-letters the jobs), which run in two transactions (`deletion.py:195-208`); (2) *plausibly, with no crash*, `get_session_package` checks `deletion_requested_at` (`sessions.py:205`) outside the locked transaction in `_insert_or_get` (`job_persistence.py:305-318`), which does not re-check it. **Healing:** `recover_orphans` does **not** heal this, because it matches only `content_deleted_at IS NOT NULL` (`job_persistence.py:439-442`). Only a re-run of `delete_session_content` settles the job: a user retry, or the sweep at `retention_sweep.py:253` once `content_expires_at` passes. No schedule for that sweep was found (`infra/`, `ops/`, compose files and `pyproject` scripts were searched). | CONFIRMED (mechanism); trigger (2) PLAUSIBLE | One shared claimable predicate for `lease`, `_next_claimable` and `local/worker.py`. Re-check `deletion_requested_at` inside `enqueue`'s locked transaction, or dead-letter the job on a lease miss. |
| **A-05** | `rra/facts.py:1267-1283`, `:1303-1311`, `:1167-1192` | **Refused metrics state the wrong cause.** This is one root cause at three sites; RRA-009 §Refusals (parts 2 and 4) requires the true cause. (1) Gross profit and margin use `headline_reason(SEMANTIC_COST)`, so a gapped *revenue* column reports `required_input_unavailable`, i.e. "the file does not contain cost". (2) The units series has no `reason=`. (3) Discount and returns never read `additive_reason`, so a duplicated row reads as a missing column. #431 and #503 each fixed one call site. | (1) **REPRODUCED** (judge 1); (2) and (3) CONFIRMED | One `_reason_for(inputs)` resolver, plus a test that iterates every emitted metric. **OWNER:** RRA-003, RRA-004 and RRA-009 define the causes but never say which wins when two apply at once (e.g. a gapped column plus a repeated signature). That ordering must be decided before slice 4. Cases where only one cause applies can be fixed now. |
| **A-24** | `rra/semantic_views/projection.py:279-296` `_FIELD_READERS`; `registry.py:112-201`; consumer `rca/workspace/decision/card.py:193,225,231` via `shell_decisions.py:766` `read_cards` | **No production decision card can ever read as "verified".** Several declared view fields have no reader and always project `None`. The live consumer `read_cards` reads `availability` from `MetricAvailabilityView`, but `card_status` returns verified only when `availability == "available"`. So every card is shown as caveated or unavailable, and card `versions` is always empty. Affected fields: `MetricAvailabilityView` `availability`, `reason`, `versions`; `ExecutiveOverviewView` and `BasketView` `versions`; `ReportEvidenceView` `provenance`, `absence`; `PeriodComparisonView` `subject`, `baseline`, `delta`. `tests/test_d103_metric_card.py:104-111` builds rows by hand, so no test can catch the `None`. | CONFIRMED (consumer and status rule traced by the captain) | **Split by source.** Fields the bundle already states (`versions`, `provenance`, `absence`) get readers in slice 5a. `availability`, `reason`, `subject`, `baseline` and `delta` are **not** stated by `RenderableBundle`/`CitedFigure`, and the module docstring (`projection.py:36-37`) calls widening that source "an RRA-006/RRA-014 question and not a slice's to decide". That makes it **OWNER**. A per-row `delta` also sits close to FR-138's "grouping into a new fact". Add a test that drives `read_cards` over real `project()` output. |
| **A-25** | `rra/semantic_views/projection.py:197-217` `_versions_of` | **The package formula version is dropped for cross-version sources (FR-139).** `CrossVersionIdentity` has no `formula_version`, only `package_formula_version` (`crossversion_assembly.py:486`), so it is lost. The comparison formula version is already carried as `family:<section>` from evidence (`:469`). | CONFIRMED (expert, and judge 1) | Project `package_formula_version` under the existing `formula` key only. Do not add a second key for the comparison version, which would define it twice. |
| **A-06** | `runtime/shell_invitations.py:165` `issue_invitation` | **A storage refusal while issuing an invitation becomes a bare 500.** There is no `except` and no global handler. `InvitationOperationFailed` is raised whenever `add_invitation` returns False (CHECK or FK constraints). The sibling `revoke_invitation` returns FR-025's uniform refusal. | CONFIRMED | Route through **one** named shell refusal mapping (backlog item 7). Do not add another broad `except`, which would create a second routing definition beside A-17. |
| **T-01** | `tests/test_w107b_unenforced_flag.py:55-66`, guarding `runtime/wiring.py:732-770` | **The deployed retention sweep is guarded by a grep naming 7 of its 8 passes.** `RawUploadRetentionSweeper` is missing, every `RetentionPasses` field defaults to `None`, and no test calls `build_retention_sweep()`. Deleting the raw-upload pass keeps CI green while DEC-033's upload horizon silently goes unenforced. Production is correct today. | CONFIRMED (test gap) | Call `build_retention_sweep(runtime_stack())` and assert every `dataclasses.fields(RetentionPasses)` entry is non-`None` and correctly typed. |

### MEDIUM

| ID | Location | Defect | Verdict | Fix direction |
|---|---|---|---|---|
| A-01 | `rca/persistence.py:662` `purge_if_still_eligible`; `rca/lifecycle.py:127` `enable_account`; `rca/persistence.py:767` `_apply_account` | **Purge and re-enable race; latent, HIGH once lifecycle is wired.** The re-check is a plain `get` with no `FOR UPDATE`, and enable writes its whole snapshot back. (a) An enabled account can lose its email. (b) A purged identity can be revived, which breaks DEC-015:74 ("**Purged.** Nothing remains"). `tests/test_rca001_lock_scope.py:640` asserts that purge takes no lock. **No shipped path reaches it:** `enable_account` and `disable_account` have no caller in `src/` and no CLI entry point, so no production account is ever disabled and the purge sweep has nothing to act on. The owner's 2026-08-18 acceptance recorded at `identity_advisory_lock` (`persistence.py:428-453`) covers only the invitation-issuance-vs-purge race, **not** this one. | CONFIRMED; (b) reproduced at library level by judge 1 | Slice 2 must land **before** any slice that wires lifecycle. Lock through `account_for_update` in purge. Lock and re-check `is_purged` in enable. Deliberately remove purge from the lock-scope allowlist. Add a two-connection `concurrency` test. |
| A-04 | `runtime/workspace_recording.py:431-438` `complete_run`; `:249` `_perform_once` | **A refusal after `record_completion` still commits.** `_provenance_of` can raise `WorkspaceRefused` after `record_completion` has written, and `_perform_once` catches it inside the unit of work, which then commits. The run is left `completed` with no provenance, audited as `refused`, and cannot be retried. This fires only if the session's profile *at completion* has lost the manifest that `_retain` (`:332`) required at creation. **HIGH if that is reachable.** | CONFIRMED path; trigger PLAUSIBLE | Build `_provenance_of(...)` before `record_completion`. |
| A-07 | `runtime/worker.py:111`; `runtime/pipeline_recording.py:246` | `recover()` runs unguarded, and `reconcile` has no per-link isolation. One deterministic fault crash-loops the worker. | CONFIRMED (no isolation); trigger PLAUSIBLE | Per-link catch, log and skip. |
| A-08 | `runtime/shell_decisions.py:999-1017` `_respond` | A membership revocation between `_member_or_none` and `read_surface → resolve_scope` escapes as a 500 (FR-146/FR-165). | CONFIRMED path; race PLAUSIBLE | The same named refusal mapping as A-06. |
| A-09 | `rra/facts.py:1649-1695`; `:1419-1433` | A return row with positive revenue (RRA-003:93) refuses the headline, but is still summed into the daily and retained bases. | CONFIRMED (expert) | Gate the daily bases on `returns_violated`. Grouped with A-05, under the same spec and module. |
| A-10 | `rra/rendering/wording.py:694-698`, `:764-767`; `facts.py:2374` | `negative_base` text about a "percentage change… absolute revenue change" is shown for AOV, ASP and margin when the denominator is negative. | CONFIRMED | **OWNER:** the reason vocabulary is closed (a new code "would be an amendment"). |
| A-11 | `rra/rendering/excel.py:637-671` | The workbook prints the same limitation paragraph twice; HTML dedupes it (`html.py:1032`). | CONFIRMED (expert) | A shared dedupe helper. |
| A-12 | `rra/rendering/excel.py:1053` `_write_provenance` | Writes RRA-009-Internal `narrative_state`. `html.py:682-690` calls it "a pre-existing divergence… it belongs to the Excel slice". That is a hand-off, not an owner acceptance. | CONFIRMED | Remove it from the workbook. |
| A-13 | `rra/rendering/excel_rows.py:57-67` | XlsxWriter write return codes are unchecked. | CONFIRMED (expert); trigger PLAUSIBLE | A checked-write wrapper. |
| A-14 | `runtime/workspace_deletion.py:77-132` | An unlocked already-deleted guard lets two concurrent deletes both record `completed` (FR-123). | PLAUSIBLE (PostgreSQL) | Decide the outcome under the lock. |
| A-15 | `rra/persistence.py:469-477` `update_session` | A snapshot overwrite can clear the deletion fields; this is the pattern #217 fixed. | PLAUSIBLE | Write-once or monotonic fields. |
| A-16 | `runtime/retention_sweep.py:143-196`, `:242-262` | No per-pass isolation. One deterministic fault skips the DEC-015 purge and every later pass. | CONFIRMED (expert) | Per-pass isolation; exit non-zero at the end. |
| A-17 | `rra/report_api.py:419-423` | A broad `except → 503` sits beside `_REPORT_REFUSALS`. | PLAUSIBLE (drift) | Route through `_refusal_for`. |
| A-26 | `rra/benchmark_workload.py:46`; `benchmark_trial.py:159-200`; `benchmark_population.py`, `benchmark_rows.py` | **The benchmark gate does not run the workload DEC-029 pins.** DEC-029:120-121 fixes the Core profile (`transaction_id, transaction_date, product, category, store, channel, units, net_sales`). The gate generates `date,revenue,units,invoice_no,category,branch`, and its contract names a `transaction_id` column that does not exist, so the transaction and basket families are refused on every run. The generator that does follow the governed profile (565 lines) has no caller and cites retired DEC-006. The earlier finding A-29 is merged here. | CONFIRMED (expert, and judge 1) | Run the DEC-029 governed profile through the gate. **No either/or.** DEC-029 settles this. Re-cite DEC-029. |
| A-27 | `rra/semantic_views/projection.py:291-293`, `:322-346` vs `:399-407` | `dimension` shares the `member` reader, so it holds the member label. `EffectiveRequest.dimensions` is echoed but never used to constrain selection. | CONFIRMED (expert) | Give `dimension` its own reader, and **enforce** the dimensions (FR-137 requires stating them, so "stop reporting them" is not an option). |
| A-28 | `rra/analysis/comparison_narrative.py:53-169` | Cross-version refusal texts lack RRA-009 §Refusals parts 3 and 4. | CONFIRMED (expert) | **OWNER:** new text, or clarify RRA-009's scope. |
| S-01 | `rca/session_cookie.py:88` (no caller) | There is no logout route, and a provider sign-out does not end Khepri's 12-hour session. DEC-018 and DEC-024 are retired, and DEC-025 is silent. | CONFIRMED | **OWNER** |
| S-04 | `rra/envelope.py:121,201,213` | AES-GCM has no AAD binding. Digest checks block splicing today. Adding AAD changes how stored ciphertexts authenticate, so it needs format versioning or a migration. | CONFIRMED | **OWNER:** not hygiene. |
| A-21 | `khepri_gov/validator.py:48-61` | `yaml.safe_load` keeps the last duplicate key or block, so a registry with two `artifacts:` blocks validates only the second. | CONFIRMED (expert, reproduced) | **OWNER / governance tooling:** no product spec covers it. Use a duplicate-rejecting loader. |
| A-22 | `rca/organizations.py:330`, `rca/accounts.py:280`, `rca/lifecycle.py:107,127` | FR-008 disablement, FR-012–015 organization management and account enable/disable have **no production surface**. Their `ValueError` refusals would escape the shell's `except PermissionError` once wired. | CONFIRMED | **OWNER:** is this a phase gap or a defect? A-01 must land before any wiring. |
| T-02 | `tests/test_rra009_excel_split.py:417,432,443` | The reconcile tests compare the bundle with itself. | CONFIRMED (expert) | Compare against `presented(workbook)`. |
| T-03 | `tests/test_rra009_excel_split.py:451`; `test_rra006_excel_sections.py:130` | Figure membership is checked in the global shared strings. | CONFIRMED (expert) | Assert `expected ⊆ written` per sheet and language. |
| T-04 | `tests/test_rra006_excel_surface.py:659` | Arabic RTL is never asserted on the business sheets. | CONFIRMED (expert) | Iterate every Arabic sheet. |
| T-05 | `tests/test_rra006_html_sections.py:337` | Two of five sections are checked for Arabic. | PLAUSIBLE | `ORDERED_SECTIONS × REQUIRED_LANGUAGES`. |
| T-06 | `tests/test_runtime_wiring.py:296`; `tests/w104b_support.py:200-231` | Substring guards, plus a hand-copied app. | PLAUSIBLE | Drive `build_web_app(runtime_stack())`. |
| T-07 | `tests/test_w102_workspace_locks.py:124-213` | Locks are "proven" by grep. | PLAUSIBLE | A `FOR UPDATE NOWAIT` two-connection test. |
| T-08 | `tests/test_clerk_private_beta_e2e.py:159` | Cannot fail on Linux CI. | CONFIRMED (expert) | Assert `pool.checkedout() == 0`. |
| T-09 | `tests/test_u1_02_component_layer.py:196` | The FR-092 test skips when its precondition is missing. | PLAUSIBLE | Guarantee the precondition. |
| T-13 | `tests/test_sv105_propagation.py`; `tests/test_d103_metric_card.py:104-111` | No semantic-view test runs over a cross-version source or through `read_cards` on real output. | CONFIRMED | Part of the A-24 and A-25 slices. |

### LOW

| ID | Location | Item | Fix direction |
|---|---|---|---|
| S-02 | `rra/api.py:158` | `/openapi.json` is served unauthenticated. | Pass `openapi_url=None`. |
| S-03 | `rra/rendering/chromium.py:92` | Chromium runs with `--no-sandbox`, mitigated by `route(abort)`. | **OWNER:** enable the sandbox (container support) or accept the risk. |
| S-05 | `rra/intake.py:378-382` | The byte-level DOCTYPE guard misses UTF-16 input (PLAUSIBLE). | Decode first, or use `defusedxml`. |
| S-06 | `rra/coverage_api.py:86-133` | No `Cache-Control: private, no-store` (PLAUSIBLE). | Match `journey/routes.py:78`. |
| D-01 | `rca_memberships.account_id`, `rra_fact_packages.package_digest`, `rra_deletion_evidence.attempted_at` | Missing indexes (PLAUSIBLE). | Run `EXPLAIN` on PostgreSQL first. |
| D-02 | `rca/workspace/profile_store.py:65-78` | No parent lock or liveness check (PLAUSIBLE). | `_refuse_tombstoned_parent`. |
| D-03 | `rca/persistence.py:993-1038` | `StaleDataError` escapes, and a double promote writes two events (PLAUSIBLE). | Catch it; predicate the update. |
| D-04 | `rca/workspace/store.py:674-690` | `SERIALIZABLE` has no `40001` retry (PLAUSIBLE, PostgreSQL). | Retry, or assert non-nested. |
| D-05 | `rca/session_persistence.py:70-86` | `add_session` does not catch `IntegrityError`. | Mirror its sibling. |
| A-18 | `rra/rendering/excel.py:576-732` | Dead section writers, one writing a raw `caveat.code`. | Delete them. |
| A-19 | `runtime/comparison_assembly.py:234` | Unreachable `datetime.min` branch. | Delete it. |
| A-20 | `local/worker.py:50-91` | Same predicate gap as A-03 (local only). | Fixed by A-03's shared predicate. |
| A-23 | `rca/invitation_persistence.py:211-214` | Correct (§6), but inconsistent with the repo's pattern. | Optional. |
| A-30 | `rra/semantic_views/projection.py:306-319` | Filters ignore the dimension name (PLAUSIBLE). | Match on dimension and label. |
| T-10 | 8× `raises(Exception)`, 6× `raises((A, B))` | These hide which exception fired. | Name one type. |
| T-11 | `tests/rca_fakes.py:303-323` | The fake's NULL ordering differs from PostgreSQL's. | Use `nulls_last()` and mirror it in the fake. |
| T-12 | `tests/test_d109_…:69-70`, `test_sv108_…:463-464` | Assertions that cannot fail. | Drop them, or label them as evidence. |
| DOC | `runtime/bridge.py:3`; `analysis/comparison.py:88-92`; `excel.py:377`; `infra/compute.py:40-45` | Stale comments. | Correct them. |
| INFO | `tests/test_r808_shell_state_grammar.py:305` | A strict xfail records a live FR-163 defect (`shell_decisions.py:494`). | **OWNER** (RCA-008). |

## 4. Simplification backlog (ranked by defect leverage)

1. **One claimable-job predicate** shared by `lease`, `_next_claimable` and the local poller.
   Closes A-03 and A-20.
2. **Single-statement, precondition-checked writes** instead of snapshot write-back, in
   `save_session`/`revoke`, `enable_account`/`_apply_account` and `rra.update_session`.
   Closes A-02, A-01(b) and A-15.
3. **One refusal-reason resolver in `facts.py`**, and split `_build` (414 lines, CodeScene 5.95).
   Closes A-05 once the owner fixes the precedence.
4. **One named shell refusal mapping** (a decorator or table). Closes A-06 and A-08, and prevents
   the A-22 class.
5. **Readers for every field the source states.** This covers A-24's source-stated part, A-25
   and A-27.
6. **Shared Excel helpers:** checked writes, a prose dedupe shared with HTML, and removal of dead
   writers. Closes A-11, A-13 and A-18.
7. **Per-unit fault isolation** in `reconcile` and `RetentionPasses.run`. Closes A-07 and A-16.
8. Collapse the six `try/with begin()/except IntegrityError` methods in `rca/persistence.py`.
9. Before cutting `narrative.py` (6.06) or `rra/api.py:create_app` (301 lines), run a CodeScene
   review to pick the cut points.

## 5. Proposed fix slices (in order)

Every slice needs:

- a single concern and a single governing spec;
- its own worktree;
- TDD, with a failing test first, then a mutation check (restore the defect and confirm the test
  fails);
- the gates: `validate`, `ruff check`, `pytest`, and CodeScene (10.00 for new files, no hotspot
  decline);
- an active spec confirmed before the slice opens.

| # | Slice | Findings | Governing spec | PG test | Owner first? |
|---|---|---|---|---|---|
| 1 | A revoked session stays revoked | A-02 | RCA-001 FR-007; DEC-015:76 | no | no |
| 2 | Purge and re-enable serialize on the account row | A-01 | DEC-015:74 | yes | no, but it must precede any lifecycle wiring (A-22) |
| 3 | The queue cannot be wedged by one session | A-03, A-20 | RRA-007 | trigger (2) | no; sweep cadence is an ops item |
| 4a | Refusal causes that are unambiguous (one cause only) | A-05 single-cause cases, A-09 | RRA-009 §Refusals; RRA-003 | no | no |
| 4b | Precedence between concurrent refusal causes | A-05 multi-cause cases | RRA-009 | no | **yes** |
| 5a | Views project every field the source states | A-24 (`versions`, `provenance`, `absence`), A-25, A-27, T-13 | RRA-014 FR-137/139/140 | no | no |
| 5b | Sourcing `availability`, `reason`, `subject`, `baseline`, `delta` | A-24 (the rest) | RRA-006 / RRA-014 | no | **yes** |
| 6a | Governed refusals on shell routes | A-06, A-08 | RCA-001 FR-025; RCA-008 | no | no |
| 6b | One refusal table for report routes | A-17 | RRA-007/RRA-009 | no | no |
| 7 | `complete_run` refuses before it writes | A-04 | RCA workspace spec, to confirm | no | no |
| 8 | Worker and sweep fault isolation | A-07, A-16 | RRA-007; DEC-015/DEC-033 | no | no |
| 9 | Excel surface parity | A-11, A-12, A-13, A-18, T-02, T-03, T-04 | RRA-009 | no | no |
| 10 | Benchmark runs the DEC-029 workload | A-26 | DEC-029 | no | no (DEC-029 settles it) |
| 11a | RCA persistence robustness | A-14, D-02, D-03, D-05 | RCA workspace/identity specs | A-14, D-03 | no |
| 11b | RRA session persistence | A-15 | RRA session spec, to confirm | no | no |
| 12 | Test hardening | T-01, T-05 to T-12 | per the test's own spec | T-07 | no |
| 13 | Hygiene | S-02, S-05, S-06, A-19, A-23, A-30, DOC, D-01 | per item | D-01 | no |

**Owner decisions:**

1. The precedence between concurrent refusal causes (4b).
2. Whether RRA-006/RRA-014 require widening `RenderableBundle` for the 5b fields, or whether those
   view fields were mis-scoped.
3. A-10 and A-28 (reason vocabulary and refusal text).
4. S-01 (logout, and ending the session on provider sign-out).
5. S-03 (Chromium sandbox).
6. S-04 (AAD format change).
7. A-21 (validator duplicate keys).
8. A-22 (the organization and lifecycle surface).
9. The FR-163 strict xfail.
10. A retention-sweep schedule for the chosen deploy target.

## 6. Refuted or cleared

- **`add_invitation` "raises on PostgreSQL"**, reported HIGH: refuted by reproduction. SQLAlchemy
  2's ORM rolls back on a flush failure, and leaving `begin()` afterwards is a no-op. Now A-23.
- **Purge race**, reported CRITICAL: regraded to HIGH in Revision 1, then to MEDIUM/latent in
  Revision 2, because it has no production trigger.
- **`_completion_key` naive/aware comparison**: the branch is unreachable (A-19).
- **XLSX intake XXE and zip bombs**: rejected or bounded.
- **Local and staging credentials, `ops/staging/certs/*.key`**: documented fixtures; the keys are
  gitignored and generated.
- **Security, cleared by trace:**
  - `require_owner` cannot be escalated.
  - There is no pin oracle.
  - Private directories refuse symlinks.
  - Autoescape is on everywhere and nothing uses `|safe`.
  - Excel formula injection is blocked.
  - Chromium's network access is aborted.
  - Assets are allowlisted.
  - All SQL is Core-built or bound.
  - All 40 routes are scoped.
- **Exception boundaries**: every *wired* RCA refusal subclasses `PermissionError`.
  `EventsRefused` is translated before the sole catch.
- **Database**:
  - One linear chain, `0001 → 0030`.
  - No model/migration drift across 25 tables.
  - The irreversible downgrades are deliberate.
- **Infrastructure**: isolated subnets, CMK encryption, blocked public access, and digest-pinned
  images.
- **Cross-version siblings of A-10 to A-13**: absent locally. A-12 and A-13 reach cross-version
  workbooks only through shared `excel.py` helpers.
- **A-12, "owner-accepted?"** (judge 2 raised this as unverified): the `html.py` comment is a
  hand-off to the Excel slice, not an acceptance.

## 7. Coverage log

| Area | Deep-traced | Swept | Not reviewed |
|---|---|---|---|
| `rra/` | every module named in the §3 rows, plus `crossversion_*`, `excel_crossversion`, `pdf`, `semantic_views/*`, `coverage*`, `journey/*`, `benchmark*`, `chromium`, `fonts`, `excel_layout`, `report_services`, `profile_request`, `narrative`, `wording`, `html`, `excel`, `bundle`, the job and artifact persistence, `claim_queue`, `worker`, `pipeline` | `intake`, `profiling`, `admission`, `admissibility`, `mapping`, `datasets`, `versions`, `package_source`, `source_contract`, `populations`, `daily_bases`, `performance`, `telemetry*`, `storage`, `envelope`, `sessions`, `session_cookie` | none |
| `rca/`, `runtime/`, `local/`, `infra/`, `khepri_gov/` | all route modules, the identity/session/authorization core, workspace store and recording, `wiring`, `local/*`, `infra/*`, `khepri_gov/*`, decision and semantic queries, `clerk_*`, pipeline recording, `retention_sweep`, `worker` | remaining persistence | `__init__.py` files |
| Security | 40 routes, envelope, cookies, templates, Chromium, Excel, every SQL site | — | `decision/controls.py` dimension allowlist; artifact response headers |
| Database | 30 migrations; 25 tables; 28 write paths | — | row diffs for job/delivery/telemetry/report-artifact tables |
| Tests | hotspot mutant analysis | all 311 files | — |
| Adversarial judges | A-01, A-02, A-03, A-05, A-24, A-25, the §5 plan | — | A-04, A-06 to A-30 beyond those claims; A-01(a) and A-03(2) on PostgreSQL; cards over HTTP through the real adapter |

## 8. Reproduction (A-02)

This runs against the real `SqlSessionStore` and `SessionService` on in-memory SQLite. Its
output: `revoked: 1`, then `after revoke: refused`, then
`after switch: RESOLVES -> DEFECT CONFIRMED; revoked_at = None`.

```python
from datetime import UTC, datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from khepri.rca.accounts import AccountService
from khepri.rca.errors import AuthenticationFailed
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import Base as RcaBase, SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService

NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
engine = create_engine("sqlite+pysqlite://")
RcaBase.metadata.create_all(engine)
factory = sessionmaker(bind=engine, future=True)
accounts = AccountService(SqlAccountStore(factory))
organizations = OrganizationService(SqlOrganizationStore(factory))
sessions = SessionService(SqlSessionStore(factory), lifetime=timedelta(hours=12))

account = accounts.create_account("victim@example.test", "correct horse battery staple")
organization = organizations.create_organization("Acme", account.account_id, now=NOW)
organization_id = getattr(organization, "organization_id", organization)
token = sessions.create(account.account_id, now=NOW)

stale = sessions.resolve(token, now=NOW)                                  # 1. live snapshot
print("revoked:", sessions.revoke_all(account.account_id, now=NOW + timedelta(seconds=1)))
try:
    sessions.resolve(token, now=NOW + timedelta(seconds=2))
    print("after revoke: RESOLVES (unexpected)")
except AuthenticationFailed:
    print("after revoke: refused")                                        # 2. revoked
sessions.point_at_organization(stale, organization_id)                    # 3. stale write-back
try:
    live = sessions.resolve(token, now=NOW + timedelta(seconds=3))
    print("after switch: RESOLVES -> DEFECT CONFIRMED; revoked_at =", live.revoked_at)
except AuthenticationFailed:
    print("after switch: refused -> no defect")
```

The A-23 refutation (a flush `IntegrityError` caught inside `begin()` returns False cleanly) and
the §2 AST metrics script are kept in the session scratchpad.

## 9. Adversarial product-layer verdict

Two fresh-context judges reviewed Revision 1 under `.grok/skills/khepri-adversarial-review`.
Both returned **REVISE**. The verdicts are reproduced in full in
`docs/audit/2026-09-adversarial-verdicts.md`.

| Gap raised | Raised by | Disposition in Revision 2 |
|---|---|---|
| Slice 5 hid an owner decision (a source-type widening) | judge 2 (CRITICAL), judge 1 | **Applied.** Split into 5a (source-stated fields) and 5b (**OWNER**, RRA-006/RRA-014). |
| A-01 unreachable in the shipped runtime; wrong DEC-015 row cited | judge 1 | **Applied.** Captain verified there is no caller. Regraded to MEDIUM/latent, cited DEC-015:74, and ordered slice 2 before any wiring. A-22 widened. |
| A-01's fix should say the 2026-08-18 acceptance does not extend to it | judge 2 | **Applied**, in A-01. |
| A-03's heal statement was false; a crash-free trigger was missed | judge 1 | **Applied.** Captain verified `recover_orphans` matches `content_deleted_at IS NOT NULL` only. Fix direction changed. The enqueue race is recorded as PLAUSIBLE. |
| A-03's scheduler search was limited to `infra/` | judge 2 | **Applied.** `ops/` and the compose files were also searched: no scheduler. |
| A-05 cited the wrong spec; the precedence is not in spec text | both | **Applied.** The grant is RRA-009 §Refusals. Precedence is **OWNER** (slice 4b). |
| A-24's consumer was misnamed and the affected views under-scoped | judge 1 | **Applied.** Captain verified `read_cards` and `card_status`. `ExecutiveOverviewView` and `BasketView` `versions` added. |
| A-25's fix would define the comparison version twice | judge 1 | **Applied.** Project `package_formula_version` only. |
| A-26 and A-29 are one fact; their options contradicted DEC-029 | judge 1 | **Applied.** Merged, and the fix is the DEC-029 profile. |
| A-27 offered an option FR-137 forbids | judge 1 | **Applied.** "Stop reporting" struck. |
| S-04 and A-21 are not hygiene | judge 1 | **Applied.** Moved to OWNER. |
| Slices 6, 11 and 13 mixed specs | both | **Applied.** Split into 6a/6b and 11a/11b; A-09 moved to 4a. |
| A-06's fix would add a second refusal-routing definition | judge 1 | **Applied.** One named mapping. |
| A-02's scenario did not match the shipped path; `revoke` also writes through `save_session` | judge 1 | **Applied.** Captain verified the only switch caller (`external_auth_api.py:124`). |
| LOW rows had no fix direction | judge 1 | **Applied.** |
| The register was unfinished (pytest pending, repro only in the scratchpad) | judge 1 | **Applied.** §1 is complete and the repro is in §8. |

Revision 2 has **not** been re-judged. Under the skill, the owner decides whether a second judge
round is needed before the register drives any slice.
