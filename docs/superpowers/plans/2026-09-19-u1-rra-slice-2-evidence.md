# `U1` RRA slice 2 — evidence

**Slice:** One skip-link mechanism on the journey.
**Authority:** `RRA-010` §73, `active`, verified at `79a0557`.
**Plan:** `docs/superpowers/plans/2026-09-19-u1-rra-slice-2-execution-plan.md`.
**Module:** `tests/test_rra010_journey_focus.py` — 24 tests, 16 static and 8 browser-marked.

**This slice changed no production file.** All four §73 clauses were compliant before it was
written. What it adds is the measurement, two-sided, so a later regression fails rather than
passing quietly.

---

## Finding 1 — The allocation plan's premise was false

Slice 2 was written as "unifies the **journey** half" of a two-mechanism skip-link split across
`journey.css:75-76` and `shell-components.css:45,56`.

**There is no split on the journey.** Measured at `79a0557`:

| Fact | Evidence |
|---|---|
| Journey templates linking a stylesheet | one: `base.html.j2:7` to `/beta/assets/journey.css` |
| Journey pages extending that base | all five: `expired`, `processing`, `report`, `review`, `upload` |
| `@import` in `journey.css` | none |
| Who links `shell-components.css` | `shell_templates/shell.html.j2:8`, `legal_templates/legal.html.j2:8` |
| `.skip-link` base selectors delivered to a journey page | **1** |

The two definitions share a directory and are never delivered to the same page. §73's
"consolidating two journey-internal mechanisms" therefore had **no subject**, and its "adopting a
shell-owned mechanism as the target is not [authorized]" is what keeps it that way.

The allocation plan was corrected in place, as its own Global Constraints require.

**This also settles the journey-adoption gate for slice 2.** `RRA-010` §73 answers the question
restrictively and in advance, so the slice did not wait on the owner's untaken reading. That
reading still gates any slice that would put a shell-owned component **on** a journey surface.

## Finding 2 — A measurement that answered a different question

A first attempt at the tab-order measurement called `link.focus()` and *then* pressed `Tab`, and
reported the first tab stop as `.brand`. That looked like a defect. It was not: focus had already
moved past the skip link, so `Tab` reported the **second** stop.

Re-measured from a clean page load, the order is `skip-link, brand, language-link` — correct.

The shipped test presses `Tab` from a clean load with no prior `focus()` call, and its docstring
records why. See `khepri-a-guard-can-answer-a-different-question`.

---

## Pre-slice measurements

`/beta/{en,ar}/{upload,review,processing,report}`, viewports 390x844 and 1180x900.

| §73 clause | Subject | Result |
|---|---|---|
| One skip-link mechanism | 1 delivered base selector | **PASS** |
| Correct tab order | first tab stop from clean load is `.skip-link` | **PASS** |
| Visible focus — skip link | focused box **46.375px**, floor 44 | **PASS** |
| Visible focus — scroll container | `.table-region` `tabindex="0"`, outline `3px solid rgb(31, 95, 168)` | **PASS** |

`RRA-010`:133 (no physical directional property) also holds over the delivered sheet.

**A gap this slice closes.** `test_rra_journey_browser.py:155` enforces the same 44px floor over
`button`, `.language-link` and `.step-nav a`. Its selector list excludes `.skip-link` — so the one
target that exists purely for keyboard users was the one never measured. The new test closes that
without editing the existing one.

---

## Mutation results

Every guard was mutated and restored by `git checkout`, never by `str.replace`
(`khepri-restore-a-mutant-by-diff-not-by-replace`). Final `git diff --stat` over `src/` is empty.

| # | Mutant | Expected | Result |
|---|---|---|---|
| M1 | `.skip-nav` added to **`journey.css`** | guard fails | **8 failed** |
| M2 | `.skip-nav` added to **`shell-components.css`** | guard **passes** | **8 passed** |
| M3 | skip link moved below `.brand` in `base.html.j2` | tab order fails | **2 failed** |
| M4 | skip link `padding` zeroed | target floor fails | **4 failed** |
| M5 | `:focus-visible` outline set to `none` | scroll container fails | **2 failed** |

**M2 is the load-bearing one.** It proves the guard measures the *binding* rather than the
directory: a second mechanism in the companion surface's file, which shares
`src/khepri/rra/journey/assets/`, does **not** fail a correct journey tree. A directory-scoped
guard fails there — the `#486` defect, where three guards built from rendered output fired on
correct markup.

**M4 recorded an RTL-specific margin.** Only the two **Arabic** parametrizations failed. With
padding zeroed, the English skip link's rendered text still forced a line box clearing 44px at one
viewport; the shorter Arabic string did not. A single-language test would have called this mutant
survivable, which is why `RRA-010`:134 requires the floor "in both languages".

---

## Gates

| Gate | Result |
|---|---|
| `uv run pytest tests/test_rra010_journey_focus.py` | **24 passed** |
| `uv run ruff check .` | passed |
| `uv run khepri-gov validate` | passed |
| `uv run pytest` (full suite) | see the pull request |
| CodeScene, new module | see the pull request |
