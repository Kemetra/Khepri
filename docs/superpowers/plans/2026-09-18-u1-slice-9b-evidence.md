# `U1` slice 9b / `U1-06` — Accessibility evidence, commercial shell surfaces: the evidence

**Authority:** active `RCA-010` `FR-200`, verified `active` in `governance/registry.yaml`.
**Plan:** `docs/superpowers/plans/2026-09-18-u1-slice-9b-execution-plan.md`.
**Allocation:** `docs/superpowers/plans/2026-09-17-u1-shell-allocation-plan.md` §Slice 9b.
**Base:** `aa62016` (`#485`, slice 8).

**No source file changed.** Two test files and two documents:

| File | Change |
|---|---|
| `tests/test_r811_shell_accessibility.py` | new — 276 cases |
| `tests/test_r807_shell_quality.py` | `test_every_legal_template_is_measured` added beside the shell scan |
| the plan and this evidence | new |

---

## The three findings, stated before the passes

An evidence slice that reports only what passed has hidden what it could not measure. All three
are carried to the owner. Findings 1 and 2 are not closable inside `tests/`; Finding 3 was a real
product defect, and the slice owning `shell-components.css` has since fixed it.

### Finding 1 — `FR-200`'s computed-contrast floor does not run in CI

`FR-200` §Verification requires the floors "measured in the real browser the repository already
drives, with contrast computed rather than asserted". CI runs a bare `uv run pytest`
(`.github/workflows/governance.yml`) with **no browser install step**.

Measured, not assumed:

```
$ PLAYWRIGHT_BROWSERS_PATH=/nonexistent uv run pytest tests/test_r811_shell_accessibility.py -q -m browser
44 skipped, 148 deselected in 15.64s
```

**All 44 browser-gated cases skip.** Unlike slice 8's layout half, this cannot be narrowed onto a
static guard: contrast computation is irreducibly browser-bound.

Closing it means editing `.github/workflows/governance.yml`. **`.github/` is not in `RCA-010`
§Scope** — §Scope authorizes `shell.css`, `shell-components.css`, `workspace.css`,
`shell_templates/`, `legal_templates/`, `shell_copy.py` and `tests/`, and nothing else. The
allocation block forbids widening past `tests/`.

So the slice makes the gap legible rather than closing it:
`test_the_browser_floors_are_not_silently_unmeasured` pins the marker against silent removal, so
the cases cannot be de-marked to make CI appear to cover them.

> **This slice does not discharge `FR-200` in CI.** Authorizing a browser install needs an
> amendment naming `.github/`, which only the owner can author.

### Finding 2 — the announcement clause has no reachable subject

`FR-200` requires `role="status"` for **refusals and progress**. Across all 10 shell surfaces in
both languages:

- **no surface renders any of slice 5's three refusal classes** — `.decision-refusal`,
  `.decision-unsupported`, `.compare-refusal`;
- **the shell authors no progress affordance at all** — slice 5's
  `test_no_shell_surface_carries_a_loading_affordance` already records that it cannot occur.

So `test_a_refusal_or_progress_region_announces_itself` **skips all 20 cases**. That is
NOT EXERCISED, not PASS. `test_the_announcement_clause_has_no_reachable_subject_today` pins the
antecedent so the distinction survives: it fails the day a surface renders a refusal, which is
when the floor becomes live and the pin should go.

**This is not a product defect.** Nothing is missing from the markup; the clause's subject simply
does not arise on these fixtures.

### Finding 3 — 200% text overflows three surfaces at 390px (`shell-components.css`)

> **CLOSED.** Fixed by the follow-on slice this finding called for — `overflow-wrap:
> break-word` on `.document-card`. See
> `docs/superpowers/plans/2026-09-18-shell-components-scaling-overflow-evidence.md`.
> The account below is left as written, because it is the record of what this slice found.

**This one IS a product defect**, and the only one this slice found. `FR-200` requires text to
scale "to 200% without loss of content or function". At the 390px viewport, in **English only**:

| Surface | `scrollWidth` | Over by | `h1` |
|---|---|---|---|
| `switcher` | 418 | 28px | "Choose an organization" |
| `no_membership` | 418 | 28px | "You are not in an organization yet" |
| `compare` | 411 | 21px | "Comparison" |

**Cause.** `.shell-main` (`shell-components.css:36`) and `.document-card` (`:68`) keep their
padding when the root font size doubles, leaving the `h1` a **244px box for a 345px word run**.
`white-space` is `normal` the whole way up and no ancestor is a non-shrinking flex item — the text
simply cannot wrap small enough. `"Comparison"` is a single unbreakable token, which is why the
shortest heading still overflows.

**Arabic passes on all three at the same width**, so this is English string length against that
card width, not a directional defect.

**Not fixed here.** The failing file is `shell-components.css`, and the allocation block is
explicit: a floor failure opens a follow-on slice under `RCA-010` named for the file that fails,
and an evidence slice editing a stylesheet to make its own assertion pass "has left its scope, and
the failure it hid is still in the product". So the three cases are pinned by `_SCALING_OVERFLOW`,
**case by case and two-sided**: the test fails if a fourth surface starts overflowing *and* if any
of these three is fixed without removing it from the set. A blanket `xfail` would have marked all
40 cases and hidden both directions.

**This does not contradict slice 8's `FR-198` overflow claim.** That measures at 100% text; this is
a text-scaling defect at 200%. Different floor, no conflict.

---

## What the slice got wrong first, and what the correction was

Recorded because each was a guard that passed over a defect or fired on correct markup, and the
reasoning is what a later slice needs.

### The announcement clause was applied to the wrong states

The first draft built `_ANNOUNCING` from a grep of the rendered pages and got
`("empty-state", "decision-availability")`. Four cases failed on **correct markup**.

`FR-202` separates the vocabulary: an *empty result* is one of its four states and belongs to
slice 5, and the spec's own words call `overview`'s two regions "the two governed empty rules". A
*trust state* has its own `FR-200` clause — non-colour differentiation — which
`test_a_trust_state_is_not_carried_by_colour_alone` already measures.

The corrected list comes from slice 5's state grammar (`test_r808_shell_state_grammar.py:8-17`),
where `FR-202`'s four states are already bound to classes — not from a grep. Same failure mode as
`_LANDMARKS` below: deriving a guard's input from the wrong source.

### `form` and `section` are not unconditional landmarks

The first `_LANDMARKS` set included them, and the uniqueness floor failed on `team` and
`analysis`. Both elements are landmarks **only when they carry an accessible name**: an unnamed
`<form>` is exposed as a plain grouping. The failing markup is the single-button revoke and
download forms, where the *button* names the action — correct markup the floor was reporting as a
defect.

### A `re.search` over the first match hid an emptied region

`test_a_trust_state_is_not_carried_by_colour_alone` first used `re.search`, which matches once.
`overview` renders **two** `empty-state` regions, so a mutant that emptied one passed. The floor
now uses `re.findall` **and asserts the match count equals the occurrence count**, so a region
that goes unmatched fails rather than passing silently.

---

## Mutation results

Every floor was mutated and each restore verified with `git diff` showing zero deletions. A mutant
whose target string was absent is recorded as proving nothing and was replaced.

| # | Mutant | Floor | Result |
|---|---|---|---|
| 1 | drop `refund-and-void` from `LEGAL_PUBLISHED` | legal roster extent | **FAIL** as required |
| 2 | add `_probe.html.j2` to `legal_templates/` | legal template extent | **FAIL** as required |
| 3 | `tabindex="-1"` → `tabindex="3"` on `<main>` | positive tabindex | **FAIL**, 20 shell cases |
| 4 | `aria-label="Analysis"` → `"Sections"` on `decision` | landmark uniqueness | **FAIL** as required |
| 5 | unwrap `<label class="decision-filter">` to a `<div>` | placeholder-is-not-a-label | **FAIL**, both decision cases |
| 6 | empty the rendered `pinned_empty` region | non-colour trust state | **FAIL**, both overview cases |
| 7 | force `color:#bbb` on `background:#ccc` | computed contrast | **23 of 23 nodes flagged** |

**Two malformed mutants, recorded rather than hidden:**

- *Adding* `tabindex="3"` beside the existing `tabindex="-1"` produced a duplicate attribute.
  `html.parser` keeps the first, so the floor never saw `3` and the mutant passed. Replacing the
  **value** (mutant 3) fires correctly. A malformed mutant proves nothing.
- Emptying `overview_no_work` (template line 27) changed a branch the fixture does not take, so
  nothing moved in the rendered page. Mutant 6 targets `pinned_empty`, which does render.

### The contrast measurement is falsifiable

The central deliverable, so it is checked directly rather than inferred from a green run:

```
baseline: 23 nodes measured on overview/en, worst real ratio 6.23  (floor 4.5)
under `* { color:#bbb; background-color:#ccc }`: 23 violations
[OK] the contrast measurement detects a real violation
```

A measurement reporting no violations under a forced low-contrast override would be measuring
nothing. Each case also asserts `measured` is non-empty before asserting the floors, so a run over
an empty node list fails rather than passing.

---

## The two extent assertions

`test_every_shell_template_is_measured` scans only `shell_templates/`, so `legal.html.j2` and
`legal_page.html.j2` were measured by nothing while slice 8 hardened them — the allocation block's
tree-state finding 3.

**Added as a sibling, not as a widening**, for three verified reasons:

1. The existing scan computes `measured = {f"{surface}.html.j2" for surface in SHELL_SURFACES}`,
   assuming surface key == template basename, 1:1. **Six legal pages share one template**, so
   adding six roster entries would synthesize six basenames absent from disk.
2. `legal.html.j2` is a layout — `legal_page.html.j2` opens `{% extends "legal.html.j2" %}`.
3. `_html()` structurally cannot serve a legal page: it builds
   `add_shell_routes(app, services=ShellServices(...))`, while legal registers through
   `add_legal_routes(app)`, which takes **no services argument**.

**Labelled two-sided drift detection, not independent.** `tests/` sits in the same `RCA-010`
§Scope as the templates, so a slice can edit both sides. It is stronger than a tautology and
weaker than independence, exactly as the allocation block requires it be described — the block's
heading says "from an independent source" and its body corrects that; the body governs.

Page extent is asserted separately by `test_the_legal_roster_matches_the_served_inventory`, since
template extent cannot see a page added to a shared template.

---

## The legal pages are measured as the product serves them

`legal.html.j2:7-8` links **two** sheets — `shell.css` and `shell-components.css` — and
`legal_api.py`'s `_ASSETS` allowlist serves exactly those two. The shell's browser cases inject a
**third**, `workspace.css`. `_legal_css()` injects only the two, because injecting a sheet the page
never links would measure a document the product does not serve — the error `_PRINT_TEMPLATES`
exists to prevent, and which the `r807` module's own comment records from before the component
layer existed.

**Both publication states are driven.** Only 4 of 12 legal responses are `200` (`about-us` and
`refund-and-void`); the other 8 hold a governed `503` unpublished state. All 12 render a document
with exactly one `h1`. The contrast cases drive one published and one unpublished page per
language, and `test_a_published_legal_page_carries_more_than_its_chrome` asserts the published one
carries content the unpublished lacks — so the non-null case is provably reached rather than
assumed.

---

## Gate results

| Gate | Result |
|---|---|
| `pytest` (whole suite) | **5863 passed, 97 skipped, 2 xfailed** in 9m37s |
| `pytest tests/test_r811_shell_accessibility.py` | **256 passed, 20 skipped** (the unreachable clause) |
| `ruff check .` | All checks passed |
| `khepri-gov validate` | Governance validation passed |
| CodeScene `analyze_change_set` vs `origin/main` | `quality_gates: passed`, 2 files checked |
| CodeScene score, `test_r811_shell_accessibility.py` | **10.00** |
| CodeScene score, `test_r807_shell_quality.py` | **10.00** (unchanged) |

The whole suite was run, not only the touched modules: changing a shared helper's meaning breaks
suites never opened.

---

## `FR-200` floor coverage

| Floor | Where | Runs in CI |
|---|---|---|
| Visible focus on every tab stop | existing `r807` skip-link case | no |
| Focus order, no positive `tabindex` | `test_no_surface_carries_a_positive_tabindex` + legal | **yes** |
| Semantic landmarks, meaningful unique names | `test_repeated_landmarks_carry_distinct_accessible_names` | **yes** |
| Exactly one `h1` | `test_every_legal_page_renders_one_heading…` + existing `r807` | **yes** |
| Labels associated, never a placeholder | `test_every_control_has_a_label_that_is_not_its_placeholder` | **yes** |
| ARIA only where native semantics insufficient | the sole-`main` reasoning in `_LANDMARKS` | **yes** |
| `role="status"` for refusals and progress | **Finding 2 — not exercised** | n/a |
| Non-colour differentiation per trust state | `test_a_trust_state_is_not_carried_by_colour_alone` | **yes** |
| Targets ≥ 44px on the element a pointer lands on | `test_a_pointer_target_is_measured…` (both languages, both viewports, incl. `input`) | no |
| Contrast computed rather than asserted | `test_text_contrast_is_computed…` (both viewports) — **Finding 1** | **no** |
| `prefers-reduced-motion` | existing `r807` case (`emulate_media`) | no |
| Text scales to 200% | `test_text_scales_to_two_hundred_percent…` — **Finding 3** | no |
| Errors announced, not only coloured | no error class exists on the shell (slice 5) | n/a |

Six floors run in CI. Five are browser-gated and do not (Finding 1). Two have no subject on the
shell today — the announcement clause (Finding 2) and the error clause, which slice 5 already
recorded as having no class anywhere on the shell.

---

## What this slice did not do

- **It changed no source file** — including the stylesheet carrying Finding 3. One floor **did**
  fail on the product, and the fix belongs to the slice that owns `shell-components.css`. The
  other failures encountered were defects in this slice's own guards, corrected above.
- **It did not open the follow-on slice** for Finding 3. That slice is named for
  `shell-components.css` under `RCA-010` and is the owner's to schedule.
- **It did not edit CI**, because `.github/` is outside §Scope.
- **It did not assert `FR-202`'s refusal-vs-error distinguishability**, which is slice 5's.
- **It did not touch slice 10b's visual-regression obligation** (`FR-204`–`FR-205`), which depends
  on this slice and comes next in the shell family chain.
