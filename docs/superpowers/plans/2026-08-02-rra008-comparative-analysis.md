# RRA-008 Comparative and Concentration Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add period comparison, concentration, growth decomposition, and basket structure to the
governed fact package as deterministic derived facts over the `RRA-004` aggregates.

**Blocked until approved.** `RRA-008` is `draft`. `APP-006` carries it at manifest digest
`sha256:21e5423212912bbb3658a0304a5d7f5221b417bf3b1b3d5557f27d067d66cfd6` and is `proposed` with no
`approval` block. **No task below may begin until that package records approval evidence from the
named active authority and the registry entry reads `approved`.** Implementing ahead of that is the
failure `AGENTS.md` forbids, and a passing gate is not approval.

## Where the files actually landed

**This plan is complete. The module and test names in the steps below were not the ones used.** The
four analyses became a package rather than four sibling modules, and two were renamed for what they
compute. The steps are left as authored; follow this table instead.

| Named in the steps below | Actual file |
|---|---|
| `src/khepri/rra/analysis_periods.py` | `src/khepri/rra/analysis/comparison.py` |
| `src/khepri/rra/analysis_concentration.py` | `src/khepri/rra/analysis/concentration.py` |
| `src/khepri/rra/analysis_decomposition.py` | `src/khepri/rra/analysis/growth.py` |
| `src/khepri/rra/analysis_basket.py` | `src/khepri/rra/analysis/basket.py` |
| `tests/test_rra008_periods.py` | `tests/test_rra008_comparison.py` |
| `tests/test_rra008_decomposition.py` | `tests/test_rra008_growth.py` |
| `tests/test_rra008_package_integration.py` | `tests/test_rra008_assembly.py` |

`src/khepri/rra/analysis/windows.py` is a fifth module this plan does not name: comparison and growth
both read it, so the two families split the same delta rather than each deciding what a period is.

**Architecture:** One module per analysis, each exporting immutable result types with an
`as_document(precision)` method in the style of `Bucket`, `Series`, and `Comparison` in
`aggregates.py`. Nothing is added to `facts.py`, which is already 948 lines against the 800-line
guidance; the fact package composes the new modules rather than absorbing them.

**Tech Stack:** Python 3.13, Polars, exact `Decimal` arithmetic, pytest, Ruff.

**Governance boundary:** This implements `RRA-008` only. It does not amend `RRA-003` or `RRA-004`,
introduces no mapping semantics, and adds no forecasting, customer-defined metric, cohort analysis,
or two-dimension breakdown. Monetary values remain integer minor units or exact decimals; no binary
float is ever an authoritative financial fact.

**Read before starting:** `src/khepri/rra/aggregates.py` for the bucket, series, and comparison
shapes and the reserved-label handling; `src/khepri/rra/facts.py` for how a fact family records its
provenance, formula version, and caveats; `src/khepri/rra/packages.py` for how a fact package is
assembled and digested.

---

### Task 1: Period comparison

**Files:**

- Add: `src/khepri/rra/analysis_periods.py`
- Add: `tests/test_rra008_periods.py`

**Step 1: Write the failing tests**

Prove that:

- two complete equal-length windows produce absolute and percentage deltas;
- an incomplete current window truncates **both** windows to the same day count, and the result
  carries a caveat naming the truncated window;
- a prior window with no coverage refuses that comparison and does not raise for the report;
- a zero base refuses the percentage delta while still emitting the absolute delta;
- a negative base refuses the percentage delta;
- granularity follows the existing 92-day day/month rule rather than a new one;
- the same inputs produce byte-identical documents.

**Step 2: Run and verify RED**

Run: `uv run pytest tests/test_rra008_periods.py -q`

Expected: FAIL, `ModuleNotFoundError`.

**Step 3: Implement**

Immutable `PeriodComparison` carrying the two windows, the measure, absolute delta, optional
percentage delta, and caveats. Truncation is computed from coverage, never from a caller argument,
so a caller cannot ask for an untruncated misleading comparison.

**Step 4: Run and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 2: Concentration

**Files:**

- Add: `src/khepri/rra/analysis_concentration.py`
- Add: `tests/test_rra008_concentration.py`

**Step 1: Write the failing tests**

Prove that:

- the cumulative share curve is computed over the **full** admissible distinct-value set, not the
  20-bucket display set — construct a case with more than 20 distinct values where a
  bucket-truncated curve would differ, and assert the full-set answer;
- the result records `distinct_values` and the count actually ranked;
- top-decile and top-quartile shares are emitted, and no fixed classification band appears
  anywhere in the output;
- a distinct set too large to compute within admissibility limits refuses;
- reserved labels (`other`, `unlabelled`, `redacted`) are handled as `aggregates.py` handles them
  and never enter the ranking as if they were products.

**Step 2: Run and verify RED**

Run: `uv run pytest tests/test_rra008_concentration.py -q`

Expected: FAIL.

**Step 3: Implement**

Rank by revenue over the full distinct set; truncate only what is displayed. The refusal path is
required, not optional: a concentration curve that silently ranked 20 of 5,000 products would be
wrong in a way no surface reveals.

**Step 4: Run and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 3: Growth decomposition

**Files:**

- Add: `src/khepri/rra/analysis_decomposition.py`
- Add: `tests/test_rra008_decomposition.py`

**Step 1: Write the failing tests**

Prove that:

- `(asp_prior * units_change) + (units_current * asp_change)` equals the revenue change **exactly**,
  asserted as equality on `Decimal` and not within a tolerance, across a table of cases including
  price-only, volume-only, opposing-sign, and both-negative changes;
- zero units in either period refuses, because average selling price is undefined;
- the recorded formula version is present and pinned;
- the output states that the interaction term is assigned to price.

**Step 2: Run and verify RED**

Run: `uv run pytest tests/test_rra008_decomposition.py -q`

Expected: FAIL.

**Step 3: Implement**

Use exact `Decimal` throughout. If a rounding step is needed for display, round only at the
document boundary and assert the unrounded parts sum exactly, so the reconciliation property is a
property of the computation rather than of the formatting.

**Step 4: Run and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 4: Basket structure

**Files:**

- Add: `src/khepri/rra/analysis_basket.py`
- Add: `tests/test_rra008_basket.py`

**Step 1: Write the failing tests**

Prove that:

- items per transaction is units over transactions;
- attach rate is transactions containing a dimension value over all transactions;
- an absent `transaction_id` mapping refuses both, with a stated reason;
- line-item-grain input is never counted as one transaction per row — construct a dataset where the
  wrong denominator yields exactly 1.0 items per transaction and assert the refusal or the correct
  value, never the plausible wrong one;
- attach rate without an admissible product or category dimension refuses.

**Step 2: Run and verify RED**

Run: `uv run pytest tests/test_rra008_basket.py -q`

Expected: FAIL.

**Step 3: Implement**

Take the transaction count from distinct mapped transaction identifiers, never from row count.

**Step 4: Run and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 5: Compose into the fact package

**Files:**

- Modify: `src/khepri/rra/packages.py`
- Modify: `tests/test_rra004_packages.py`
- Add: `tests/test_rra008_package_integration.py`

**Step 1: Write the failing tests**

Prove that:

- each new fact family carries stable fact and citation identifiers, input digest, mapping version,
  formula version, dimensions, filters, units, precision, and caveats;
- every derived fact reconciles to the `RRA-004` aggregate it derives from, and a forced
  reconciliation failure produces a caveat or a refusal rather than a value;
- reruns with identical input and governed versions are byte-equivalent;
- a refusal in one analysis does not suppress the others.

**Step 2: Run and verify RED**

Run: `uv run pytest tests/test_rra008_package_integration.py tests/test_rra004_packages.py -q`

Expected: FAIL.

**Step 3: Implement**

Compose the four modules into the package. Do not widen `facts.py`.

**Step 4: Run and verify GREEN**

Run the command from Step 2. Expected: PASS.

### Task 6: Bilingual surfaces

**Files:**

- Modify: `src/khepri/rra/bundle.py` and the report template
- Modify: `tests/test_rra006_html_surface.py`, `tests/test_rra006_pdf_surface.py`,
  `tests/test_rra006_excel_surface.py`

**Step 1: Write the failing tests**

Prove that every new fact and every caveat appears with equal content in Arabic and English across
web, PDF, and Excel, that truncation caveats are never dropped on any surface, and that Excel output
remains literal values and safe labels with formula interpretation disabled.

**Step 2: Run and verify RED**

Run: `uv run pytest tests/test_rra006_html_surface.py tests/test_rra006_excel_surface.py -q`

Expected: FAIL.

**Step 3: Implement**

Render from the fact package only. No surface recomputes a figure.

**Step 4: Run and verify GREEN**

Run the command from Step 2, plus `-m browser` for the PDF surface where Chromium is installed.

### Task 7: Verify the slice

**Step 1: Run the focused suite**

Run: `uv run pytest tests/test_rra008_periods.py tests/test_rra008_concentration.py
tests/test_rra008_decomposition.py tests/test_rra008_basket.py
tests/test_rra008_package_integration.py -q`

Expected: PASS.

**Step 2: Run the required gates**

Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest`. Expected: all PASS.

**Step 3: Inspect the diff**

Run `git diff --check` and `git status --short`. Expected: no whitespace errors, and only the files
this plan names.

**Step 4: Report the CI-only gate honestly**

State that CodeScene Code Health remains CI-authoritative. Do not claim its 10.00 new-file score
locally. Keep constructors to two or three arguments rather than sitting at a limit.
