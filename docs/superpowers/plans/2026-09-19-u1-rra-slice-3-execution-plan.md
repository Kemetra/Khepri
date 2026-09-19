# `U1` RRA slice 3 — Collapse the raw journey font sizes onto the type scale: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Checkboxes in this
> repository are **never ticked after the fact** — read the newest dated status block, not the
> boxes.

**Goal:** Remove every raw numeric type size from `journey.css`, mapping each onto the journey's
existing scale without changing that scale.

**Architecture:** Nine substitutions in one stylesheet, plus one new test module,
`tests/test_rra010_journey_type_scale.py`. The tokens themselves are **not** touched.

**Tech Stack:** Jinja2, pytest, Playwright (Chromium), FastAPI `TestClient`.

**Spec:** `governance/specifications/RRA-010.md`.
**Allocation:** `docs/superpowers/plans/2026-09-17-u1-rra-surfaces-allocation-plan.md` §Slice 3.
**Design:** master specification §G.1.

---

## Global Constraints

- **Authority is `RRA-010`**, `active`, verified at `08e734d`.
- **`journey.css` and `tests/` only.** `shell-components.css:135,141` hold two raw sizes and are the
  companion plan's slice 2b (`FR-201`).
- **Do not merge the tokens.** `journey.css:57-58` records that `--journey-text-xs` and
  `--journey-text-sm` are "a separate decision, not a rounding of the same one; collapsing them
  would restyle every paragraph in the journey, which this slice has no mandate for." Two rows go
  to `xs`, seven to `sm`.
- **All nine, or a stated deferral.** The four `font-size` rows are the floor; the five `font`
  shorthand rows are in the same mandate. Silently excluding part of the population is the defect
  this repository keeps rediscovering.

---

## Decision 1 — `var()` inside the shorthand, not longhand splitting

The allocation plan recommends keeping the shorthand with a `var()` in the size slot, because
splitting to longhand changes the cascade for any property the shorthand was resetting. Taken.

**One form was worth proving rather than assuming.** An invalid `font` shorthand is dropped whole,
taking the family and line-height with it — silently. `.intake-facts dt:101` has **no weight
token**, so its substitution puts `var()` in the leading position. Measured in Chromium before
writing any substitution:

| Form | Computed |
|---|---|
| `font: var(--xs)/1.2 ui-monospace, monospace` | `11.2px`, family `ui-monospace, monospace`, lh `13.44px` |
| `font: 700 var(--sm)/1 ui-monospace, monospace` | `13.12px`, family preserved, weight `700` |

Both parse. Family, line-height and weight survive in each.

## Decision 2 — A raw-size scan must match shorthands, and must not match `font: inherit`

A scan worded for `font-size` alone passes green over all five shorthand sizes and would certify a
false claim. The scan matches typographic declarations generally:

```
font-size:\s*[0-9.]   |   font:\s*[^;]*[0-9]+(\.[0-9]+)?rem
```

`font: inherit` (`:72`, `:116`) carries no size and must **not** be flagged; the second alternative
requires a numeric `rem`, so it does not match. Task 3 mutates both directions.

## Decision 3 — The delta roster must render, or it measures nothing

A selector matching no element returns `None` and asserts nothing while reporting PASS
(`khepri-a-run-that-can-only-produce-the-null-case`).

A first roster put `.contract-row label` and `.meta` on `review`; both render on **`upload`**
(`upload.html.j2:21,35,37`). They returned `None` for all four language/viewport combinations. The
corrected roster reaches all nine. The shipped test asserts each selector is present before
measuring it.

---

## Task 0 — Capture the before-state

- [ ] Computed `fontSize`, `fontFamily`, `lineHeight`, `fontWeight` for all nine selectors, in both
      languages, at 1180x900 and 390x844.
- [ ] Assert no selector returns `None`.

**Captured at `08e734d`** (en, 1180px): `.brand` 13.44, `.contract-row label` 13.76,
`.intake-facts dt` 10.88, `.meta` 12.16, `.report-group h2` 12.48, `.report-meta` 13.28,
`.report-meta dt` 12.16, `.step-nav a` 12, `th` 12.48.

## Task 1 — The nine substitutions

- [ ] Apply each, asserting the old fragment occurs **exactly once** before replacing it, so a
      selector that moved is a hard failure rather than a silent no-op.

| # | Selector | Line | Form | Raw | Token |
|---|---|---|---|---|---|
| 1 | `.brand` | 78 | shorthand | `.84rem` | `--journey-text-sm` |
| 2 | `.step-nav a` | 82 | `font-size` | `.75rem` | `--journey-text-xs` |
| 3 | `.intake-facts dt` | 101 | shorthand | `.68rem` | `--journey-text-xs` |
| 4 | `.contract-row label` | 115 | `font-size` | `.86rem` | `--journey-text-sm` |
| 5 | `.meta` | 145 | shorthand | `.76rem` | `--journey-text-sm` |
| 6 | `th` | 165 | `font-size` | `.78rem` | `--journey-text-sm` |
| 7 | `.report-meta` | 169 | shorthand | `.83rem` | `--journey-text-sm` |
| 8 | `.report-meta dt` | 171 | `font-size` | `.76rem` | `--journey-text-sm` |
| 9 | `.report-group h2` | 179 | shorthand | `.78rem` | `--journey-text-sm` |

## Task 2 — RED: the three shapes

- [ ] **No raw numeric type size remains**, scanning `font-size` **and** `font` shorthands, with an
      emptiness assertion so it cannot pass by scanning nothing.
- [ ] **Computed size unchanged beyond the stated delta**, measured in a real browser at both
      viewports in both languages, with family, line-height and weight preserved.
- [ ] **§G.1 computed contrast re-measured**, per master specification §22 — "the 0.22 margin has
      no room."

## Task 3 — Mutation-test every guard

- [ ] Add a raw `font-size: .9rem` to `journey.css` → the scan must **fail**.
- [ ] Add a `font: inherit` → the scan must **pass** (a correct tree is not refused).
- [ ] Point a token at a different value → the delta test must **fail**.
- [ ] Restore each by `git checkout`, never `str.replace`.

## Task 4 — Evidence file and gates

- [ ] `docs/superpowers/plans/2026-09-19-u1-rra-slice-3-evidence.md` with the delta table and the
      mutation results.
- [ ] `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest` — **run serially**; two
      pytest runs in one tree collide on `.pytest-tmp` and report phantom errors.
- [ ] CodeScene: the new module scores 10.00.
