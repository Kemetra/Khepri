# Journey declaration fixes (#586, #587, #588, #589) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A beta participant can declare the transaction key their data actually has, can correct a refused declaration without a new invitation, and reads no internal code or misleading label on the way.

**Architecture:** There are four independent changes to the `/beta` upload and review pages. Each gets a test-first commit followed by its implementation commit.
- #587 and #588 change only the client and the copy.
- #589 adds governed wording that the review script reads from a server-rendered vocabulary element.
- #586 adds one declaration control whose value the request model already accepts.

No route, endpoint, request shape, status code, persistence or domain module changes.

**Tech Stack:** Jinja2 templates, ES modules (`upload.js`, `review.js`), `journey/copy.py`, pytest, and Playwright (`@pytest.mark.browser`).

**Spec:** `governance/specifications/RRA-003.md` §Event and transaction identity (lines 59-64) and `governance/specifications/RRA-010.md` §Scope and §Exclusions.

## Authority

- **Owner decision, 2026-09-26, in session:** "ok i approve for you recomndations. if can put in one pr do it", given in response to the recommendations recorded on #586-#589. The exact wording below is approved when the owner merges this PR (Constitution II). This plan claims nothing beyond that approval.
- **#586 is `RRA-003` contract content, not `RRA-010` presentation.**
  - `RRA-003`:59-64 makes the canonical key a bare identifier only when the contract proves it unique. "Otherwise the canonical key is an admitted composite containing the source identifier and every field required for uniqueness."
  - The journey is a customer's only way to make that declaration. Without the control, the "otherwise" branch cannot be reached.
  - `RRA-010` §Exclusions bars "any new data collection, field" for *presentation* slices. This control collects column names that the contract already carries (`SourceContractBody.transaction_key_components`, `list[str] = []`).
  - **The owner's merge is the approval for adding it.** The PR body says so plainly.
- **#587** calls an endpoint the runtime already serves (`POST /profile`). A probe on the SQL harness returned 400, then 201, on one session. It is capability-neutral under `RRA-010` test 2.
- **#588 and #589** are copy.
  - #588 re-words an existing key.
  - #589 adds keys for codes `mapping.py` already emits, and replaces a raw code with governed words.

## Global Constraints

- Customer strings live in `journey/copy.py`, in both `_EN` and `_AR`, and are never authored in JavaScript (`RRA-010` §Invariants).
- The client never synthesizes contract content: the transaction reference is **not** auto-added to the composite; the server refuses a composite without it.
- Don't run `ruff format` on existing files; lint only.
- Delete `.playwright-mcp/` after the live run; it is not git-ignored.

## Approved copy

| Key | English | Arabic |
|---|---|---|
| `contract_transaction_id_unique_package_wide` (changed, #588) | Each reference belongs to one sale only, even when that sale has several rows | كل مرجع يخص عملية بيع واحدة فقط، حتى لو كانت لها عدة صفوف |
| `contract_transaction_key_components` (new, #586) | Columns that together identify one sale, when the reference alone does not | الأعمدة التي تحدد معاً عملية بيع واحدة، إذا لم يكفِ المرجع وحده |
| `contract_transaction_key_components_hint` (new, #586) | Separated by commas, and including the transaction reference column — for example invoice_no, branch. Leave blank when each reference belongs to one sale only. | افصل بينها بفواصل، وأدرج عمود مرجع المعاملة، مثل invoice_no, branch. اتركه فارغاً إذا كان كل مرجع يخص عملية بيع واحدة فقط. |
| `profile_rejected` (changed, #587) | Your file is uploaded, but it could not be analysed with this declaration. Correct the declaration and submit again — your file is kept. | تم رفع ملفك، لكن تعذر تحليله بهذا الإقرار. صحّح الإقرار وأرسله مرة أخرى، فملفك محفوظ. |
| `upload_kept` (new, #587) | Your uploaded file is kept for this session. To use a different file, delete this session's content. | ملفك المرفوع محفوظ لهذه الجلسة. لاستخدام ملف آخر، احذف محتوى هذه الجلسة. |
| `evidence_label_exact` (new, #589) | Column name matches exactly | اسم العمود مطابق تماماً |
| `evidence_label_token` | Column name contains a matching word | اسم العمود يتضمن كلمة مطابقة |
| `evidence_label_substring` | Column name partly matches | اسم العمود مطابق جزئياً |
| `evidence_type_confirmed` | Values have the expected type | القيم من النوع المتوقع |
| `evidence_type_conflict` | Values do not have the expected type | القيم ليست من النوع المتوقع |
| `evidence_type_only` | Matched by value type only | مطابق حسب نوع القيم فقط |
| `evidence_declared_in_source_contract` | Named in your declaration | مذكور في إقرارك |

## Review Focus

1. A participant picks a **different file** after a refusal: it must not be silently ignored. The file control locks, and the page says the stored file is kept.
2. The page is **reloaded** after a refusal (`bootstrap` path, `file` is null): the participant can still resubmit a corrected declaration.
3. A composite that **omits the reference column**: 400 with the governed reason, never 422.
4. **"Unique" ticked and a composite also typed**: the server ignores the composite (`_assert_transaction_key` returns early). It is accepted, not refused.
5. An evidence code emitted by `mapping.py` with **no wording**: the build fails, instead of the page showing the raw code.

---

### Task 1: #588, the uniqueness label names the sale, not the value

**Files:** Modify `src/khepri/rra/journey/copy.py` (both tables). Test: `tests/test_rra_journey_declaration_copy.py` (new).

- [ ] Step 1: a test asserts the approved EN and AR literals for `contract_transaction_id_unique_package_wide`.
- [ ] Step 2: run it and see it FAIL, showing the old wording.
- [ ] Step 3: replace both strings.
- [ ] Step 4: run it and see it PASS. Commit.

### Task 2: #589, evidence codes are shown as governed words

**Files:** Modify `copy.py`, `templates/review.html.j2` (`#value-vocabulary`), `assets/review.js:43`. Test: `tests/test_rra_journey_evidence_wording.py` (new).

- [ ] Step 1: tests:
  - the emitted set is derived from `mapping.py`'s syntax tree (string constants in `evidence.append(...)` calls and `evidence=` keyword tuples). It is non-empty and equals the committed seven codes;
  - every code has an `evidence_<code>` key in both languages;
  - `review.html.j2` carries `data-evidence-<code-with-hyphens>="{{ copy.evidence_<code> }}"` for each code;
  - a browser test runs `review.js`'s row builder over a stub mapping and asserts no raw code appears in the evidence cell, in EN and AR.
- [ ] Step 2: run the tests and see them FAIL.
- [ ] Step 3: add the keys and attributes. `review.js` maps each code through `wordFor("evidence", code)` before joining with `" · "`.
- [ ] Step 4: PASS. Mutant: joining the raw codes fails the browser test. Commit.

### Task 3: #586, a composite transaction key can be declared

**Files:** Modify `copy.py`, `templates/upload.html.j2` (a new row after the transaction-reference row), `assets/upload.js` `declaration()`. Test: extend `tests/test_rra003_journey_source_contract.py`.

- [ ] Step 1: tests:
  - the shipped template carries `data-contract-field="transaction_key_components"` with `data-contract-list`;
  - `declaration()`, run in the browser over the served page, sends `["invoice_no", "branch"]` for `"invoice_no, branch"` and `[]` for blank;
  - through the real API (`test_rra003_api.harness`):
    - unique unticked with components `[id column, store column]` returns 201;
    - components without the id column return 400 with "A composite transaction key must contain the source identifier.";
    - unique ticked with components also typed returns 201.
- [ ] Step 2: run them and see them FAIL.
- [ ] Step 3: add the row (label, input, hint via `aria-describedby`). In `declaration()`, a `data-contract-list` control is split on commas, trimmed, and filtered, sharing one `listValue()` helper with `attestation()`.
- [ ] Step 4: PASS. Mutant: the list parser returning the raw string fails. Commit.

### Task 4: #587, a refused declaration can be corrected in the same session

**Files:** Modify `assets/upload.js` (submit handler, `update()`, `bootstrap`), `templates/upload.html.j2` (an `#upload-kept` note), `copy.py`. Test: `tests/test_rra_journey_browser.py` (new test).

- [ ] Step 1: a browser test serves the real `/beta/en/upload` page and assets through `page.route`, and stubs the API:
  - consent 204; uploads 201 counted; the first profile 400 with a governed detail, the second 201; journey state.
  - Submitting twice gives exactly one upload and two profiles, and the page leaves for `/beta/en/review`.
  - After the refusal, the file input is disabled and `#upload-kept` is visible.
  - A second case: after a reload with `upload_present: true` and `profile_present: false`, and no file chosen, the button is enabled.
- [ ] Step 2: run it and see it FAIL, showing uploads counted twice.
- [ ] Step 3: extract `submitDeclaration()`. It skips consent and upload when `uploaded` is true.
  - `update()` enables the button on `uploaded || (consent.checked && file)`.
  - A `lockUpload()` helper disables the file input and reveals `#upload-kept` once `uploaded` is true, on the submit path and in `bootstrap`.
  - `profile_rejected` gets its new wording.
- [ ] Step 4: PASS. Mutant: removing the skip-upload guard fails the test. Commit.

### Task 5: verification

- [ ] `uv run khepri-gov validate`, `uv run ruff check .`, the journey, `rra003` and browser test files, then the full suite.
- [ ] Live stack in a browser:
  - (a) refused, then corrected, then Review, with no new invitation;
  - (b) unique unticked with `invoice_no, branch`, then Review;
  - (c) Review shows no raw codes, in EN and AR.
- [ ] Record "Owner decision (2026-09-26)" on #586-#589. Open one PR with `Refs` only. The PR is **left unmerged**, because its merge approves the wording.
