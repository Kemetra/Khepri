# `U1` RRA slice 3 — evidence

**Slice:** Collapse the raw journey font sizes onto the type scale.
**Authority:** `RRA-010`, `active`, verified at `08e734d`. Design: master specification §G.1.
**Plan:** `docs/superpowers/plans/2026-09-19-u1-rra-slice-3-execution-plan.md`.
**Module:** `tests/test_rra010_journey_type_scale.py` — 10 tests, 4 browser-marked.

Nine substitutions in `journey.css`: four `font-size` declarations and five `font` shorthands.
**Zero raw type sizes remain.** The tokens themselves are unchanged.

---

## Computed deltas

All nine selectors, both languages, both viewports, measured in Chromium before and after.

| Selector | Delta (px) | Token |
|---|---|---|
| `.brand` | −0.32 | `sm` |
| `.contract-row label` | −0.64 | `sm` |
| `.intake-facts dt` | +0.32 | `xs` |
| `.meta` | +0.96 | `sm` |
| `.report-group h2` | +0.64 | `sm` |
| `.report-meta` | −0.16 | `sm` |
| `.report-meta dt` | +0.96 | `sm` |
| `.step-nav a` | −0.8 / 0.0 | `xs` |
| `th` | +0.64 | `sm` |

**Worst |delta| = 0.96px**, exactly the allocation plan's stated maximum. No family, weight or
null regression.

**`.step-nav a` shows two values, and that is correct.** `journey.css:198` already set it to
`--journey-text-xs` inside a narrow-viewport media query, so 390px was tokenised before this slice
and only 1180px moved. A single-viewport measurement would have reported one number and hidden the
other.

## Contrast, re-measured per master specification §22

§22 requires re-measurement "whenever type or color changes. The 0.22 margin has no room." The
spec names the thinnest text as step-nav `#667381` **at 12px**, and this slice takes that to
11.2px at 1180px.

| | |
|---|---|
| step-nav `#667381` on `#fbfcfd` | **4.7169:1** |
| AA threshold, normal text | 4.5 |
| Margin | **+0.2169** — the spec's "0.22" |

**Unchanged, and the size move does not affect it.** No colour was touched, and WCAG's reduced
3:1 threshold applies only to large text — ≥18.66px bold or ≥24px. Both 12px and 11.2px are
normal text, so the 4.5 requirement holds at both and the computed ratio is size-independent.

Master specification §484's prose still says "at 12px". That sentence is now imprecise for the
1180px viewport. It is **not** edited here: it is the master specification's, not `RRA-010`'s, and
the ratio it asserts remains correct.

---

## Mutation results

Every mutant restored by `git checkout`. Final `git diff` over `src/` is empty.

| # | Mutant | Expected | Result |
|---|---|---|---|
| M1 | raw `font-size: .9rem` added | scan fails | **1 failed** |
| M2 | `font: inherit` added | scan **passes** | **1 passed** |
| M3 | `--journey-text-sm` repointed to `0.95rem` | delta test fails | **4 failed** |
| M4 | `--journey-text-xs` deleted | scale test fails | **1 failed** |
| M5 | `/1.3` dropped from a shorthand | shorthand guard fails | **survived, then fixed** |

### M5 was a malformed mutant that found a real defect anyway

Dropping `/1.3` from `font: 600 var(--sm)/1.3 ui-monospace` was intended to produce an invalid
shorthand. **It is valid CSS** — the line-height component is optional — so the declaration parsed,
and the mutant tested nothing about parse failure
(`khepri-malformed-mutants-prove-nothing`).

It nonetheless exposed a hole. Measured directly:

| Form | size | family | weight | line-height |
|---|---|---|---|---|
| `font: 600 var(--sm)/1.3 …` | 13.12px | preserved | 600 | **17.056px** |
| `font: 600 var(--sm) …` | 13.12px | preserved | 600 | **`normal`** |

The guard asserted family and weight — both survive — and said nothing about line-height, the one
property that changed. Line-height is now asserted against each shorthand's declared ratio, and M5
re-run **fails** (2 failed) where it previously passed.

### A worktree loss, recorded because it nearly produced a false finding

The first M2 run reported a failure. The regex was correct; the *tree* was not. The nine
substitutions were uncommitted, so restoring M1 with `git checkout -- src/` discarded them too, and
M2 then ran against a file that once again held nine raw sizes — the scan was right to fail.

Re-applied, committed **before** mutating, and M2 passes.
See `khepri-verify-a-fix-against-head-not-the-worktree`.

---

## Decisions recorded

**`var()` in the shorthand size slot was proven, not assumed.** An invalid `font` shorthand is
dropped whole and takes the family and line-height with it, silently. Measured in Chromium before
any substitution was written: `font: var(--xs)/1.2 ui-monospace` — the `.intake-facts dt` case,
with **no weight token**, so the `var()` leads — and `font: 700 var(--sm)/1 ui-monospace` both
parse with family, line-height and weight intact.

**The tokens are not merged.** `journey.css:57-58` forbids collapsing `xs` and `sm`. Two rows to
`xs`, seven to `sm`, and a test fails the day either token disappears.

**A roster that renders nothing measures nothing.** A first roster put `.contract-row label` and
`.meta` on `review`; both render on `upload`, and they returned null for all four
language/viewport combinations. The shipped module asserts every selector is present in a separate
test, so a selector that stops rendering fails loudly rather than silently emptying the
measurement.

---

## Gates

| Gate | Result |
|---|---|
| `uv run pytest tests/test_rra010_journey_type_scale.py` | **10 passed** |
| `uv run ruff check .` | passed |
| `uv run khepri-gov validate` | passed |
| `uv run pytest` (full suite) | see the pull request |
| CodeScene, new module | see the pull request |
