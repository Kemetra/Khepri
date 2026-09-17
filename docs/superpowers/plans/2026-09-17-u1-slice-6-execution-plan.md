# `U1` slice 6 / `U1-03` — Chart grammar: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:test-driven-development`, then
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. **Do not skip a RED step, and
> prove by mutation any test that passes on arrival.**

**Goal:** Give the shipped chart kinds the approved grammar `RRA-015` `FR-181`–`FR-188` fixes — a
visible zero baseline, an axis stating its unit, governed chrome words in both languages, and the
refusals `FR-185`/`FR-186` require — over the three kinds that already exist and no others.

**Architecture:** `charts.py` keeps returning geometry and never markup; `_chart.svg.j2` renders
what it returns; `report.css` and `report.print.css` carry the chart's screen and print rules;
`html.py` binds the view and registers chart chrome; `wording.py` gains chart chrome codes beside
its existing tables. **`ChartView` gains fields, never `build_chart` parameters** — see the
CodeScene note below.

**Tech Stack:** Python 3.13, frozen dataclasses with `slots=True`, `Decimal` throughout
`charts.py`, Jinja2 with `StrictUndefined` and unconditional autoescaping, pytest.

**Spec:** active `RRA-015` (`FR-181`–`FR-192`), merged 2026-09-17 at `e915af8` (`#477`).
Allocation plan: `docs/superpowers/plans/2026-09-17-u1-rra-surfaces-allocation-plan.md` (§Slice 6).
Design: master specification §8 (§8.1–§8.5).
**Baseline:** `main` at `d2a01fc`. Re-verify every line number before editing.

---

## Four findings that set this slice's scope

Established against the tree **before** writing this plan, because three of them shrink what
`FR-183` can ask for. Each is a fact about the repository, not a reading of the specification.

### 1. No governed period is reachable — the axis-period half is REFUSED, not synthesized

`FR-183` asks for an axis "labelled with its unit and its period." **The unit is reachable; the
period is not.**

- `ChartSpec` (`bundle.py:616-625`) carries `kind` and `figure_ids` only.
- `CitedFigure` (`bundle.py:822-842`) has ten fields and none is a period.
- `PresentationSection` declares no period.
- `bundle.py`'s "period" matches are all prose comments.

`build_chart` receives a `ChartSpec`, a `tuple[CitedFigure, ...]` and a `direction`. **Nothing in
that input names a period.** Composing one would be a chart-derived fact — precisely what `FR-182`
forbids — and reaching for one would require a new parameter sourced from `bundle.py`, which is
`RRA-006`'s and **outside `RRA-015` §Scope**.

**So the axis states its unit, and the period half is deferred with its owner named.** A later
artifact that puts a governed period on the bundle, or an `RRA-006` slice that adds one, is what
unblocks it. This plan records the gap rather than papering it: **an axis that stated an invented
period would be worse than an axis that states none.**

### 2. There is no series concept, so legend eligibility as stated is unimplementable

`FR-183`: a legend "renders only where two or more series exist."

- `_Plot` (`charts.py:185-195`) carries `values: tuple[Decimal, ...]` — **flat, no grouping.**
- `_bars` and `_grouped_bars` (`charts.py:290-298`) differ **only by a fill constant**
  (`BAR_FILL` vs `GROUPED_FILL`). Neither groups anything.
- `_resolve` already refuses fewer than **two values** (`charts.py:279`), so "two or more" is
  always true of values and cannot be the test.

**A legend needs a series concept `charts.py` does not have**, and inventing one is a geometry
change well beyond presentation. **Deferred, owner named:** a slice that gives `_Plot` series
grouping — which needs `ChartSpec` to say which figures belong to which series, and `ChartSpec` is
`RRA-006`'s. Until then, **no chart renders a legend**, and this slice asserts that: a legend
element must not appear, so a later slice cannot ship a decorative one that names nothing.

### 3. The truncated-axis refusal is structurally unreachable — assert the invariant instead

`FR-183`: "An axis truncated on a comparison is refused."

`_Domain` is built `low=min(*values, Decimal(0)), high=max(*values, Decimal(0))`
(`charts.py:284`), so **zero is always inside the domain** and the axis is never truncated. A test
driving a "truncated axis" input would be a run that can only produce the null case — a surface
correctly rendering nothing is NOT EXERCISED, not PASS.

**So assert the construction invariant, and mutate it:** replace `min(*values, Decimal(0))` with
`min(values)` and the test must fail. That proves the property `FR-183` wants rather than
exercising a refusal path no input can reach.

### 4. `unit_kind` has a closed set in a file this slice cannot edit — a genuine independent source

`facts.py:102-104` declares exactly three: `UNIT_MONETARY = "monetary"`, `UNIT_COUNT = "count"`,
`UNIT_RATIO = "ratio"`. **`facts.py` is `RRA-004`'s and outside `RRA-015` §Scope**, so a slice here
cannot widen it to match a mistake — the same property that makes `GOVERNED_CHART_KINDS` a valid
expectation.

**The precedent to copy is already in the repository.** `shell_decisions.py:150`'s `UNIT_WORDING`
keys a bilingual table off those imported constants, and its comment states the reason: "a unit
kind renamed there is an import error and not a silently missing line." The chart's axis-unit table
does the same.

**The duplication with that table is forced by the scope split, and the code must say so.**
`UNIT_WORDING` lives in `src/khepri/runtime/`, which is `RCA`'s and **outside `RRA-015` §Scope** —
this slice cannot import it. A second bilingual unit table in `wording.py` is therefore required,
not drift. **Record the reason in a comment beside it**, or a reviewer reads two identical tables
as an accident and a later slice "fixes" it with a cross-family import that `FR-201`'s sibling
boundary forbids.

### Three traps verified before GREEN

| Trap | State at `d2a01fc` |
|---|---|
| `ChartView` construction sites | **One** — `charts.py:217`, all keyword arguments. Adding a field breaks nothing; the `slots=True` frozen dataclass and its nine existing fields are not a barrier |
| The new chrome key must reach **both** `_CHROME` branches | `html.py:178` is English, `:226` Arabic. The macro resolves chrome under `StrictUndefined`, so a key in one branch only raises on the Arabic render alone — Task 4's bilingual assertion must drive a **real render**, not just compare key sets |
| A new completeness assertion must be **called** | `wording.py:1215` invokes `_assert_chart_descriptions_complete()` at import. A sibling defined and never called is the defined-but-never-attached defect and passes every test. Verify the call, then mutate the table without touching `facts.py` and confirm the **import** fails |

---

## Global Constraints

Copied from the allocation plan; every task's requirements implicitly include this section.

- **A chart computes no figure** (`FR-182`). No sum, average, difference, rank, score,
  normalization, threshold, percentage, interpolation, re-rounding, or reformatting. **The existing
  `_rank` and `_Domain.offset` are geometry over given values, not derivation** — they scale, they
  do not compute a new fact. A slice must not add anything that turns a value into a different
  value.
- **Only the shipped kinds** (`FR-181`): `CHART_BAR`, `CHART_GROUPED_BAR`, `CHART_LINE`.
- **Every customer-visible word is a governed code** (`FR-184`) resolved in `wording.py`, in both
  languages, under the same import-time completeness assertion the surrounding tables use. **A
  chart composes no sentence.**
- **A chart chrome label names a part of the chart** and never a metric, refusal, caveat,
  population or version (`FR-184`). Where it would, the word is `RRA-009`'s or `RRA-011`'s.
- **Logical CSS properties only** (`FR-188`); no physical directional property on a chart rule.
- **No `|safe`, no `Markup`** in `_chart.svg.j2` (§Scope). The macro is source, so its elements are
  markup while every label inside still escapes — that is the property that makes a product named
  `<script>` inert, and it must not be weakened.
- **`FR-192` asset policy**, unrelaxed. **The chart's own SVG geometry is the one admitted
  programmatic drawing**; decoration is not. Scope the scan to the chart rules in
  `report.css`/`report.print.css`, **not** the macro — a scan that cannot tell governed geometry
  from decoration is the useless one.
- **Scope is the seven paths in `RRA-015` §Scope and nothing else.** `bundle.py`, `facts.py`,
  `wording.py`'s refusal and metric tables, and every route are outside.

### CodeScene: `ChartView` gains fields, not parameters

`ChartView` already carries nine fields and `build_chart` takes three arguments plus a
keyword-only. **CodeScene gates on arguments > 4**, so adding baseline/axis/legend as parameters
fails the gate. They are computed inside `build_chart` from what it already receives and carried as
`ChartView` fields. `build_chart`'s own docstring sets the precedent: a `language` parameter the
module did not use was **removed** rather than kept.

CodeScene also gates cyclomatic > 9 and module mean > 4, and **extracting helpers raises the
mean** — so prefer adding to an existing helper over minting a new one, and pre-flight with
`analyze_change_set` before opening the PR.

---

## Tasks

### Task 1 — RED: the dispatch table has no extent assertion

- [ ] Add `test_the_geometry_table_covers_exactly_the_governed_kinds` to
      `tests/test_rra006_charts.py`: `set(_GEOMETRY) == GOVERNED_CHART_KINDS`.
- [ ] **This is slice 6's one genuinely new chart-kind assertion.** The frozenset identity already
      ships at `tests/test_rra006_bundle_sections.py:197` and the `"stacked_bar"` sentinel mutation
      at `tests/test_rra009_wording.py:730-733`. Do **not** re-add either; cite them.
- [ ] `_GEOMETRY` (`charts.py:398`) is referenced only by `charts.py:216` and asserted by no test —
      it is the table that decides whether a kind renders.
- [ ] **Independent source:** `GOVERNED_CHART_KINDS` lives in `bundle.py`, outside §Scope.
- [ ] Mutate: delete a row from `_GEOMETRY` → must fail. Add a bogus row → must fail. Revert each
      with `git diff` showing zero deletions.
- [ ] Commit: `test(u1-03): assert the geometry table's extent`

### Task 2 — RED: zero is always in the domain (the truncated-axis invariant)

- [ ] Add `test_the_domain_always_includes_zero`, driving `build_chart` with an all-positive series
      and an all-negative one, asserting `plot.domain.low <= 0 <= plot.domain.high` through the
      rendered view's baseline position rather than by reaching into a private type where possible.
- [ ] **Mutate `min(*values, Decimal(0))` → `min(values)` and `max(*values, Decimal(0))` →
      `max(values)`, separately.** Each must fail; a single mutant leaves the other bound unproven.
- [ ] Per finding 3, do **not** write a test driving a "truncated axis" input — no input can reach
      that state, and such a test would be scaffolding.
- [ ] Commit: `test(u1-03): hold the zero baseline in the domain`

### Task 3 — RED: no visible baseline element exists

- [ ] Add `test_a_chart_draws_a_visible_zero_baseline`: the rendered SVG carries a baseline element
      positioned at `domain.zero`, for a series with negative values and one without.
- [ ] Assert the baseline's position **equals** the value the domain computes — not merely that an
      element exists. An element at the wrong offset is worse than none.
- [ ] Genuinely RED: no baseline element exists today (verified — `_chart.svg.j2` renders marks,
      polyline and labels only).
- [ ] Commit: `test(u1-03): require a visible zero baseline`

### Task 4 — RED: the axis states its unit, in both languages

- [ ] Add a bilingual axis-unit table to `wording.py`, keyed off `UNIT_MONETARY`, `UNIT_COUNT` and
      `UNIT_RATIO` **imported from `facts.py`**, following `shell_decisions.py:150`'s precedent
      exactly: a renamed unit kind becomes an import error, not a silently missing line.
- [ ] Extend the import-time completeness assertion to it, deriving the expected key set from the
      three imported constants — **the independent source of finding 4**.
- [ ] `ChartView` gains an axis-unit **field**, resolved from the figures' single `unit_kind`, which
      `_resolve` (`charts.py:281`) already guarantees is one value per chart.
- [ ] Assert the axis label renders in both languages, and that an unknown unit kind **fails closed**
      rather than rendering the code string, an empty element, or a blank.
- [ ] Assert **no period** is rendered on the axis, per finding 1 — a slice that later invents one
      must fail here.
- [ ] Mutate: add a fourth key to the axis table without touching `facts.py` → the completeness
      assertion must fail. Remove a language → must fail.
- [ ] Commit: `test(u1-03): state the axis unit from a governed code`

### Task 5 — RED: no legend may render

- [ ] Add `test_a_chart_renders_no_legend`, per finding 2: no legend element appears for any of the
      three kinds, because no series concept exists for one to describe.
- [ ] State the deferral in the test's docstring with its owner: a slice giving `_Plot` series
      grouping, which needs `ChartSpec` to name series membership, and `ChartSpec` is `RRA-006`'s.
- [ ] Mutate: add a legend element to the macro → must fail. This is what stops a later slice
      shipping a decorative legend that names nothing.
- [ ] Commit: `test(u1-03): refuse a legend until a series concept exists`

### Task 6 — RED: refusal, and the evidence entry point

**`FR-185`'s per-point gap is a fourth deferral, not a task here.** `_resolve` returns `None` when
**any** value is missing (`charts.py:278`), so the whole chart refuses and there is no per-point
gap to carry a reason. Giving one a gap means per-point geometry — a `charts.py` change of a
different shape. Assert what ships; the deferral is in the table below.

**`FR-186` is already satisfied, and the reason is worth asserting so it stays.**
`report.html.j2:91` renders the chart only `{% if section.chart %}`, so a refused chart draws
**nothing at all** — not an empty chart, not error paint — and the table beside it remains the
authoritative presentation, exactly as `FR-182` requires. Verified at `d2a01fc`. The task is to
pin that behaviour, not to build it.

- [ ] A missing value refuses the chart, and nothing draws it as zero (`FR-185`, as it ships).
- [ ] A refused chart renders **no chart element**, asserted through the real template path rather
      than by checking `build_chart` returned `None` (`FR-186`). **Assert the effect on the code
      path.**
- [ ] `FR-186`: a refused figure renders the governed refusal presentation, not an empty chart; a
      zero denominator is that refusal rather than `0%` or `NaN`. **Assert the effect on the real
      code path**, not that an exception type is raised.
- [ ] `FR-186`: a refusal and an error never share an element or a class, and a refusal carries no
      error paint.
- [ ] `FR-187`: every chart carries an evidence entry point reached **from the chart**, not from a
      global destination.
- [ ] Commit: `test(u1-03): hold the missing-data and refusal presentation`

### Task 7 — RED: Arabic, and the no-arithmetic scan

- [ ] `FR-188`: in Arabic the category axis runs right to left through the existing `mirrored` flag
      (`charts.py:190`, `:213`, `:264`, `:287`, `:367`) — **extend that seam, do not mint another**.
- [ ] Numbers use Arabic-Indic digits, Arabic month names and the Arabic percent mark; every label,
      axis, legend-absence, caveat and refusal present in one language is present in the other.
- [ ] A static scan over `charts.py` and `_chart.svg.j2` asserting **no sum, difference, ratio,
      ranking or percentage is derived there** (§Verification). **Anchor to `__file__`, never a
      CWD-relative `Path("src")`**, and assert the scan is non-empty so it cannot pass vacuously.
      Note `_rank` and `_Domain.offset` are geometry over given values — the scan must admit them
      and reject derivation of a new fact, or it is unusable.
- [ ] A value whose precision differs from any default survives `build_chart` unchanged — the
      value-preservation test, distinct from the static scan.
- [ ] A chart rule in `report.css`/`report.print.css` introduces no physical directional property;
      `FR-192` scan over the chart rules only, **not** the macro.
- [ ] Commit: `test(u1-03): hold RTL, no-arithmetic and the asset policy`

### Task 8 — GREEN

- [ ] Implement the baseline geometry, the axis-unit field and its governed table, and the refusal
      presentation, in that order — each making one task's RED green without weakening another's.
- [ ] `ChartView` gains fields; `build_chart`'s signature does not grow.
- [ ] Run every earlier task's tests after each step.

### Task 9 — Verify, and record

- [ ] `./.venv/Scripts/python.exe -m pytest tests/test_rra006_charts.py tests/test_rra009_wording.py tests/test_rra006_bundle_sections.py -q`
- [ ] `./.venv/Scripts/python.exe -m pytest -q` — **the full suite.** A chart field changes the
      rendered report, and the PDF and Excel suites read it.
- [ ] `uv run khepri-gov validate`; `uv run ruff check .` (**never `ruff format`**);
      `git diff --check`.
- [ ] Write `docs/superpowers/plans/2026-09-17-u1-slice-6-evidence.md`: per-mutant results, full
      stdout including failures, and the three deferrals with their owners.

### Task 10 — Pre-flight and one PR

- [ ] `git fetch origin --prune` **first**, then CodeScene `analyze_change_set`. `charts.py` is
      code-health eligible and near the module-mean gate; read any finding rather than guessing.
- [ ] **Self-mutate every guard before requesting review.** On slice 2b the gaps found locally cost
      minutes and the ones that reached CI cost a full cycle each.
- [ ] One PR: plan+RED commits then the implementation commit. Branch off `main`, never stacked.
- [ ] **Batch every review fix and push once per round.** Five mid-flight pushes on slice 2b reset
      a ten-minute pipeline five times.

---

## Deferred, each with its owner named

| Item | Why | Owner |
|---|---|---|
| The axis's **period** | No governed period is reachable from `build_chart`'s input; composing one violates `FR-182`, and reaching for one needs `bundle.py`, outside §Scope | An `RRA-006` slice, or an artifact putting a governed period on the bundle |
| A **legend** | No series concept exists; `_bars` and `_grouped_bars` differ only by fill | A slice giving `_Plot` series grouping, which needs `ChartSpec` to name membership — `RRA-006`'s |
| A **per-point data gap** (`FR-185`) | `_resolve` returns `None` when any value is missing, so the whole chart refuses. **`FR-185`'s "visible gap carrying its stated reason" is satisfied by that refusal**: `CAVEAT_CHART_NOT_DRAWN` (`bundle.py:179`) is attached at `bundle.py:1036`, carries governed bilingual prose in `wording.py`, and renders as a chrome label ("No chart" / "لا يوجد رسم"). So the requirement is MET, not deferred — what is deferred is only a *per-point* gap inside a drawn chart | Recorded for the owner; per-point geometry is a different shape of change |

**Each is a deferral with a named owner, not a silent narrowing** — and each is asserted negatively
(no period rendered, no legend rendered) so a later slice cannot quietly ship the thing this one
declined to invent.

## What this slice does not do

- No new chart kind, forecast, trend line, or refusal cause (`FR-181`, §Exclusions).
- No change to `bundle.py`, `facts.py`, the fact families, the catalog, the component layer, the
  Excel renderer, or any route.
- No telemetry event of any kind; `KHEPRI-DEC-015` §3 stands unamended.
- No `journey.css`, no shell stylesheet — those are the companion plan's.
- No shared token layer across families (`FR-201`).
