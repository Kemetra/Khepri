# `U1` slice 6 / `U1-03` — evidence ledger

Companion to `docs/superpowers/plans/2026-09-17-u1-slice-6-execution-plan.md`.
Baseline: `main` at `d2a01fc`. Branch `claude/u1-03-chart-grammar`.

---

## What `FR-183` asked for, and what the tree allowed

Established **before** the plan was written, because three of the five elements turned out to be
unbuildable as stated. This is most of the slice's work.

| `FR-183` element | Verdict | Evidence |
|---|---|---|
| Visible zero baseline | **Built** | `_Domain.zero` existed; nothing drew it |
| Axis states its unit | **Built** | `CitedFigure.unit_kind`; three closed values in `facts.py:102-104` |
| Axis states its **period** | **Deferred** | No period on `ChartSpec` (`bundle.py:616-625`), `CitedFigure` (`:822-842`), or `PresentationSection` |
| **Legend** on two or more series | **Deferred** | `_Plot.values` is flat; `_bars`/`_grouped_bars` differ only by a fill constant (`charts.py:290-298`) |
| Truncated axis refused | **Unreachable** | `_Domain` puts `Decimal(0)` in both bounds (`charts.py:284`) |

**The period.** `build_chart` receives a `ChartSpec`, a `tuple[CitedFigure, ...]` and a
`direction`. None carries a period. Composing one would be a chart-derived fact — `FR-182` — and
reaching for one needs `bundle.py`, which is `RRA-006`'s and outside `RRA-015` §Scope. **An axis
stating an invented period would be worse than an axis stating none.**

**The legend.** `_resolve` already refuses fewer than two *values* (`charts.py:279`), so "two or
more" is always true of values and cannot be the test `FR-183` describes. A legend needs a series
concept `charts.py` does not have.

**The truncated axis.** Zero is always inside the domain, so no input reaches a truncated axis. A
test driving one would be a run that can only produce the null case — NOT EXERCISED, not PASS. The
**construction invariant** is asserted instead, with each bound mutated separately.

## What was built

`ChartView` gains two **fields**, not `build_chart` parameters. The signature stays at four, which
the code-health gate on argument count requires; `build_chart`'s own docstring set that precedent
when an unused `language` parameter was *removed* rather than kept. One construction site exists
(`charts.py:217`), all keyword arguments, so the addition breaks nothing.

- **`baseline`** — `plot.domain.zero` as a coordinate string. The macro draws the line **before**
  the marks, so a bar sits on top of it rather than being cut by it. The view carries the position
  because deriving the offset again in a template is a second chance to disagree about where zero
  sits.
- **`axis_unit_kind`** — the governed *kind*, never a word. The surface resolves it through
  `AXIS_UNITS` like every other chrome label. `_resolve` already refuses a series mixing units, so
  one chart states one dimension and the kind is unambiguous by construction.

`AXIS_UNITS` is keyed off `facts.UNIT_MONETARY`/`UNIT_COUNT`/`UNIT_RATIO`, following
`shell_decisions.py:150`'s stated reason: a unit kind renamed in `khepri.rra.facts` becomes an
**import error**, not a silently missing line. `_assert_axis_units_complete()` is **called** at
import beside its sibling — an assertion defined and never called is the defined-but-never-attached
defect and passes every test.

**The duplication with `shell_decisions.UNIT_WORDING` is forced, and a comment says so.** That
table is in `src/khepri/runtime/`, which is `RCA`'s and outside `RRA-015` §Scope, so this slice
cannot import it. Without the note a reviewer reads two identical tables as drift and a later slice
"fixes" it with a cross-family import.

`axis_units` is registered in **both** `_CHROME` branches (`html.py:180`, `:229`). The macro
resolves chrome under `StrictUndefined`, so a key in one branch only raises on the Arabic render
alone — and a test comparing key sets would never drive it.

## Print inherits the new rules, and needs no rules of its own

`report.print.css` is **layered onto** `report.css` rather than replacing it — its header states
"everything about how the report reads … is inherited unchanged" — and it redefines
`--report-rule` (`#b9c0c9`) and `--report-muted` (`#4a5560`) for paper. Those are exactly the two
tokens the new rules use, so both print in the paper palette with no second declaration.

**A literal hex value would have printed the screen colour on paper, silently**, because no
stylesheet test renders a chart. `test_the_new_chart_rules_carry_no_hardcoded_colour` asserts the
mechanism rather than the value, scoped to the two selectors this slice added — a whole-sheet scan
would fail on `RRA-012`'s and `RRA-009`'s existing rules, which this specification does not govern.

`report.css` already carries `test_the_bundled_stylesheet_uses_logical_properties_only`, and the
new rules pass it: `text-anchor: start` and `dominant-baseline` name no side, which is why the axis
label follows the reading order under `direction: rtl` without the sheet naming one.

## Eleven mutants, every one caught

Each reverted with `git diff` showing zero deletions and `git status --short src/` empty after.

| Guard | Mutant | Result |
|---|---|---|
| `_GEOMETRY` extent | delete the `CHART_LINE` row | FAILS |
| | add a bogus `"treemap"` row | FAILS |
| Zero domain | `low=min(values)` — drop zero from the low bound | FAILS |
| | `high=max(values)` — drop zero from the high bound | FAILS |
| Baseline | derive from `offset(Decimal(1))` instead of `zero` | FAILS |
| Axis unit | read `.metric` instead of `.unit_kind` | FAILS |
| `AXIS_UNITS` extent | add a fourth key without touching `facts.py` | **IMPORT FAILS** |
| No-arithmetic scan | `_total = sum(values)` in `_plot` | FAILS |
| Bilingual chrome | drop `axis_units` from the Arabic branch only | FAILS |
| Value preservation | `COORDINATE_PRECISION` 4 → 2 | **passed → fixed → FAILS** |
| Print palette | hardcode `stroke: #d5dae1` on `.chart__baseline` | FAILS |

**Each domain bound was mutated separately.** A single mutant would have left the other unproven —
the same reason the `FR-201` boundary in slice 2b needed two.

### The one that caught me writing a tautology

`test_a_value_survives_the_chart_with_its_precision_intact` first derived its expected coordinate
from `COORDINATE_PRECISION` — **the same constant the geometry uses** — so halving that constant
moved both sides together and the mutant passed. The expectation is now the literal `188.3128`,
checked by hand as the four-place quantization of `320 × (300 − 123.456789) / 300 = 188.3127584`.

This is the defect shape that recurred all session: the `_CHROME` pairing, the allocation plans'
"derive the set from its own definition", slice 2b's extent gap — and now my own test. **The test
is always ownership: can the thing under test move the expectation with it?**

### What a label is for, learned by a failing assertion

My first preservation test looked for the figure's value in a chart label and failed. Labels carry
the **category** (`V1`, `V2`), never the value, because the table beside the chart is where a number
is stated. The assertion now checks the *geometry* preserves the value exactly, and additionally
that the value appears **nowhere** in the view — a chart carrying the number would be a second
place a figure is stated.

## Commands, with their output

```text
$ ./.venv/Scripts/python.exe -m pytest tests/test_rra006_charts.py -q
37 passed in 0.62s

$ ./.venv/Scripts/python.exe -m pytest tests/test_rra006_charts.py tests/test_rra009_wording.py tests/test_rra006_html_surface.py -q
109 passed in 2.53s

$ ./.venv/Scripts/python.exe -m pytest -q          # the FULL suite
5596 passed, 77 skipped, 1 xfailed, 65 warnings in 497.56s (0:08:17)
# 5585 on main; +11 here

$ uv run khepri-gov validate
Governance validation passed.                        (exit 0)

$ uv run ruff check .
All checks passed!                                   (exit 0)

$ git diff --check
                                                     (exit 0, clean)

$ CodeScene analyze_change_set (base origin/main @ d2a01fc, fetched first)
quality_gates: passed   status: no-issues-found
checked-file-count: 4, code-health-eligible-file-count: 4
```

**CI on `92533db`:** validate, ruff, pytest, benchmark, CodeScene, CodeRabbit all pass, plus
**`build and verify the pinned image`** — which is what proves the chart changes ship in the
deployed image rather than only in the test harness. `publish` skips: no registry configured.

## Two process failures, recorded rather than omitted

**1. `git checkout --` during mutation testing destroyed uncommitted GREEN.** With the
implementation uncommitted, reverting a mutant restored the file from `HEAD` and discarded every
edit in it. Three files lost their implementation while `git status` showed clean; a collection
error on an import the tests needed was the confirmation. Recovered by reapplying.

**The rule this establishes:** RED → commit → GREEN → **commit** → mutate → revert. Never mutate
across uncommitted implementation, and where a mutant must live outside the slice's scope, use a
`git worktree`. Logged to `~/.claude/global-lessons.md`.

**2. A false alarm that cost more than the real one.** After opening the PR, a grep for the macro
edits returned zero and I concluded they had been lost again. The working tree had switched to
`main`, where slice 6 does not exist. `git branch --show-current` settled it in one command, and
all four commits were intact.

**Status disagreeing with grep has two causes needing opposite responses** — a destructive revert
(real loss; reapply) and a branch switch (no loss; look elsewhere). Both present identically:
clean status, missing content. Check the branch **first**.

## Deferred, each with its owner named

| Item | Why | Owner |
|---|---|---|
| The axis's **period** (`FR-183`) | No governed period is reachable from `build_chart`'s input | An `RRA-006` slice, or an artifact putting a governed period on the bundle |
| A **legend** (`FR-183`) | No series concept; `_bars`/`_grouped_bars` differ only by fill | A slice giving `_Plot` series grouping, which needs `ChartSpec` to name membership — `RRA-006`'s |
| A **per-point data gap** (`FR-185`) | `_resolve` returns `None` when any value is missing, so the whole chart refuses | Recorded for the owner; per-point geometry is a different shape of change |

**Both `FR-183` deferrals are asserted negatively** — no `axis_period` field, no `legend` field — so
a later slice cannot quietly ship what this one declined to invent. A deferral that is only prose
is an invitation.

**`FR-186` was found already satisfied, and pinning it was the work.** `report.html.j2:91` renders
the chart only `{% if section.chart %}`, so a refused chart draws **nothing** — not an empty chart,
not error paint — and the table beside it stays authoritative, exactly as `FR-182` requires.
