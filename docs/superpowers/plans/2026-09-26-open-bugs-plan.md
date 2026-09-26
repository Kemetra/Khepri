# Plan: fix the remaining open bugs (#560, #431, #465, #525, #432) in one PR

## Context

Five issues labelled `bug` remain open. Each was blocked on an owner decision. The owner
approved the decisions in session on 2026-09-26, after the research agents reported and the
advisor reviewed them:

| Item | Decision |
|---|---|
| #465 | Build the workbook in memory. With no workbook directory, the race has nothing to act on. Authorized by `RRA-006` (outputs "retained nowhere", same expiry boundary) and `RRA-002` ("temporary materializations"). |
| #560 · 1 | Card status (`RCA-008` FR-162) ignores the display-only caveat codes `chart_not_drawn` and `curve_points_sampled`. The card's caveat count uses the same rule. Recorded as an `RCA-008` addition beside FR-162. |
| #560 · 5 | `record_consent` re-reads the stored row and returns it. No refusal and no Protocol change. |
| #560 · 7 | Claude drafts EN/AR refusal wording to RRA-009 parts 1-5: part 1 for all ten cross-version causes, part 5 for `STORE_SET`/`GRANULARITY`, and part 4 for `SCOPE` naming the store column. The owner approves the wording by merging. |
| #431 § 3 | Amend `RRA-004` (:11, :124, :158-159) so population is disclosed at package level through the retained bases, matching `RRA-011` and `RRA-013` FR-104. Fix `projection.py:42`'s false comment. No stored-format change. |
| #431 § 6 | A real collision. Fix under `rra004.package.v5`: `coverage_manifest_identity = document_digest(manifest.as_document())`. |
| #525 | Only the `DEC-029` amendment goes in this PR. The gate rework is its own slice later, and #525 stays open. |
| #432 | No code. Close it after giving each deferred sub-item a home. |

**Merging is the owner's.** This PR carries governed text (`RCA-008`, `RRA-004`, `DEC-029`, EN/AR
copy and a package version move), and merging is what approves it. Open the PR and stop. No merge
delegation applies.

## Setup

- `git fetch`, then create a worktree `../Khepri-bugs` on the new branch `fix/open-bugs-560-431-465` from `origin/main`
  (`15d93e4`). Local `main` is behind.
- Run tests with `PYTHONPATH="$(cygpath -w $PWD)\src;$(cygpath -w $PWD)"` and
  `../Khepri/.venv/Scripts/python.exe -m pytest`. Confirm `khepri.__file__` resolves to the worktree.
- Skills:
  - `superpowers:test-driven-development` for every code item (RED observed before GREEN, then a mutation check);
  - `superpowers:systematic-debugging` on any failure;
  - `clearing-codescene-gate` before pushing;
  - `.grok/skills/khepri-adversarial-review/SKILL.md` before opening the PR;
  - `safe-git-pr-workflow` for commits (`git commit -F`).
- First commit: the plan document `docs/superpowers/plans/2026-09-26-open-bugs-plan.md`.

## Commits (one per item; each spec edit sits in the same commit as the code it authorizes)

### 1. #465: render the workbook in memory
- `src/khepri/rra/rendering/excel.py`:
  - Add `_build(bundle) -> bytes` using `xlsxwriter.Workbook(io.BytesIO(), {**WORKBOOK_OPTIONS, "in_memory": True})`.
  - `render_materialized` returns those bytes, and `render()` returns `_content(bundle, len(...))`. Both Protocols stay unchanged.
  - Delete `path_for`, `_attempt_path`, `payload_for`, the attempt/replace/unlink logic and the torn-read check.
  - Make `directory` go away, or optional if a caller still needs it.
- Remove the workbook directories:
  - `runtime/wiring.py` (:345-348, :783-793);
  - `local/wiring.py` (:230, :297-304);
  - `runtime/worker.py` (:42, :157);
  - `COMPARISON_DIRECTORY`, plus `_scratch_under`/`mkdtemp`/`rmtree` in `comparison_assembly.py` (:128-182).
- `local/cli.py`: keep `--workbooks` as a documented no-op flag, so the CLI keeps working.
- Keep `own_private_directory` and its `mkdir` sweep as the guard for any future directory.
- Tests:
  - Rewrite the AST tests in `tests/test_s1_04_private_directories.py` to pin the new invariant: no wiring builds a workbook directory. Don't delete them.
  - New: a render leaves no file in `tmp_path`.
  - New: `xlsxwriter.Workbook` receives a `BytesIO` with `in_memory: True`.
  - Move about 10 tests from `path_for(...).read_bytes()` to `render_materialized(...).artifacts[0].content`: `test_rra006_excel_*`, `test_c105_crossversion_bundle.py`, `test_rra009_excel_*`, `test_c106_comparison_orchestration.py`.
- Mutant: restore a disk write, and the no-file test fails.

### 2. #560 · 1: display-only caveats do not block `verified`
- `RCA-008.md`: add a clause after FR-162, keeping FR-162's wording. It names the display-only codes excluded from card status and the card's caveat count, and says they still show on the S-6 exceptions surface (FR-161).
- `src/khepri/rca/workspace/decision/card.py`:
  - Add a named constant set of the two codes, sourced from the RRA caveat constants through the existing projection vocabulary, not imported across the R7-01 boundary. Check the imports.
  - `card_status` and the count filter them out.
  - Don't grow `_admitted`; add a helper.
- Tests:
  - A real `project()` bundle whose only caveats are display-only gives `verified` with count 0.
  - The same bundle plus a data caveat gives `caveated`.
  - The S-6 surface still lists `chart_not_drawn`.
- Mutant: an empty exclusion set turns the first test red.

### 3. #560 · 5: `record_consent` returns what was stored
- `src/khepri/rra/sessions.py:207-230`: after `update_session`, `return self._store.get_session(session_id)`, raising the existing expired or lookup refusal on `None`.
- Test in `tests/test_rra001_sessions.py`: the fake store records a deletion between the read and the write. The returned session carries `deletion_requested_at`, and passing it to `require_upload_consent` refuses. That is the observable hazard.
- Mutant: return `consented` again, and the test fails.

### 4. #560 · 7: cross-version refusals in five parts
- `src/khepri/rra/analysis/comparison_narrative.py`: all ten causes open with a part-1 capability sentence. `CAUSE_STORE_SET` and `CAUSE_GRANULARITY` get part-5 remedies, building on #573's English candidates. `CAUSE_SCOPE` names the store column for part 4.
- `tests/test_c104_comparison_narrative.py`: remove `_ENDS_WITHOUT_REMEDY` (:102, :129) and assert every cause has a remedy. Add a new test pinning each approved string as a literal, in EN and AR.
- The PR body carries the copy table for approval.

### 5. #431 § 3: population disclosed at package level
- `RRA-004.md`:
  - :11: codes are recorded in package provenance through the retained bases.
  - :124: derived facts rest on package bases of one population identity.
  - :158-159: per-fact disclosure is formula, mapping, fact and citation identity; population is disclosed at package level.
  - Cite `RRA-011`:24-28 and `RRA-013` FR-104 as the reason.
- `semantic_views/projection.py:42`: correct the comment. Population codes live on `RetainedBasis`.
- No code-path change. `khepri-gov validate`.

### 6. #431 § 6: coverage identity names the attestation (package v5)
- **First, audit every consumer** of `coverage_manifest_identity` for code that treats it as the upload digest:
  - `crossversion_rules.py:61, 135-137`;
  - `crossversion_assembly.py:373-375, 506`;
  - `report_api.py:1021`;
  - `rendering/html.py:574`;
  - `coverage_signature.py:57`.

  Fix any comparison against `input_digest`. If a consumer needs the upload binding, it reads `input_digest` directly.
- RED: a test that builds two **real** `CoverageManifest` attestations of the same bytes, differing only in `attested_by` (and a second case on `timezone`). Today they share `coverage_manifest_identity` and `bundle_id`. Also replace the fabricated `"<id>-other"` test in `test_rra013_evidence_supply.py:243-248`.
- `facts.py`:
  - Compute the value in a helper outside `_build` (a hotspot; add no lines inside it), reusing `document_digest` as `runtime/workspace_recording.py:295` does.
  - Set `PACKAGE_VERSION = "rra004.package.v5"`.
  - Widen `VERSIONS_RECORDING_REFUSAL_INPUTS` to `{v4, v5}`.
- `versions.py`: add the `ADMITTED_PACKAGE_PAIRS` row `(mapping.v3, package.v5, formula.v2)`. Update `tests/test_rra004_version_compatibility.py` (pin the whole triple; gate tests use a `.v99` sentinel).
- `package_source.py`: the reader accepts v3/v4 documents unchanged, where the old value is read as the upload digest.
- `RRA-004.md`: add a v5 paragraph modelled on #583's v4 paragraph (:196-200). It authorizes this one value change and nothing else. `BUNDLE_VERSION` stays at v8.
- Mutant: revert to `input_digest`, and the two-attestation test fails.

### 7. #525: DEC-029 amendment only
- `KHEPRI-DEC-029` (`governance/decisions/...-029-...md`):
  - Add `rows_per_transaction: 3` to the dataset shape (:121-137), stating that a transaction's lines share date, store and channel.
  - Enumerate the workload descriptor's top-level key order, which :301 references but never lists.
  - State that `master_seed`, per-dataset sizes and `generator_version` are recorded by the descriptor slice.
- `khepri-gov validate`. #525 stays open, and the PR says so.

## After opening the PR (outward actions; the owner approved them in session)

- **#432:** open three issues (`rra_dataset_profiles.upload_id` FK; composite membership key on `rca_sessions`; Postgres RLS with a non-owner role). Comment on #152 about the unscoped lookups. Then close #432 with the owner's decision and links.
- **PR body:** `Refs` only, never `Closes`. Include the copy table, the decisions table and the per-commit test evidence.
- **After the owner merges:** close #465, #560 and #431 by hand. #525 stays open.

## Verification

- Per commit: the targeted tests are RED before and GREEN after, plus the mutant named above.
- Before pushing:
  - `uv run khepri-gov validate`;
  - `uv run ruff check .`;
  - the **full** `pytest` locally (items 1 and 6 reach suites the targeted runs don't open). Read the counts line, not just the exit code.
- CodeScene: `code_health_review` on every changed or new file. New files must score 10.00, and `facts.py`, `excel.py` and `card.py` must not decline.
- A browser or visual check is not needed; no template changes.
- Push, then watch CI (validate, ruff, pytest, CodeScene) until it is green. Then stop for the owner's merge.
