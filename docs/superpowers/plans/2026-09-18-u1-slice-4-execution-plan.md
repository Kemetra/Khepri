# `U1` slice 4 / `U1-05` — Navigation and filter presentation: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:test-driven-development`, then
> `superpowers:executing-plans`. Steps use `- [ ]` checkboxes. **Commit GREEN before mutating** — a
> `git checkout --` of a dirty file destroys uncommitted work, which cost slice 6 a recovery.

**Goal:** Give the commercial shell's navigation and filter presentation the guards `RCA-010`
`FR-193`–`FR-197` require. The behaviour is largely correct already; **what does not exist is
anything that fails when it stops being correct.**

**Architecture:** Presentation and tests only. `shell_templates/` changes as presentation markup and
ARIA state, `shell_copy.py` gains chrome labels if a region needs naming, `workspace.css` and
`shell-components.css` carry presentation rules. No route, handler, destination, read, or
capability.

**Tech Stack:** Python 3.13, Jinja2, pytest, and the Playwright/Chromium already shipped.

**Spec:** active `RCA-010` (`FR-193`–`FR-197`), merged 2026-09-17 at `e915af8` (`#477`).
Presenting `RCA-008` `FR-166` and `RCA-002` `FR-047`/`FR-049`/`FR-055` without redefining any.
Allocation plan: `docs/superpowers/plans/2026-09-17-u1-shell-allocation-plan.md` (§Slice 4).
Design: master specification §D.3–§D.5.
**Baseline:** `main` at `b26de23`.

---

## Findings that set this slice's scope

Established against the tree before writing. Two correct the allocation plan.

### 1. The navigation is correct and **completely unguarded** — that is the slice

`grep` for `aria-current`, `frame-surfaces` and `destinations` across `tests/` returns **nothing**.
No test asserts the navigation's extent, its `aria-current`, or that a destination the shell does
not serve stays out of it. The markup at `shell.html.j2:73-77` is right; nothing holds it there.

**So this slice is almost entirely RED.** Expect very little GREEN, and do not manufacture some.

### 2. The allocation plan is wrong that no independent source exists — `shell_frame.py` is one

The allocation plan states slice 4 "has **no** independent source" and prescribes a reviewed
literal. **That is not true**, and the correction matters because a reviewed literal is weaker
evidence than a registry.

`shell_frame.py:45-53` holds the destination roster, with its own comment saying it is decided
"here and nowhere else":

| Constant | Destinations |
|---|---|
| `_WORKSPACE_DESTINATIONS` | `("overview_title", "overview")`, `("data_title", "data")` |
| `_ANALYSES_DESTINATION` | `("analyses_title", "analyses")` |
| `_TEAM_DESTINATION` | `("team_title", "team")` |

**`RCA-010` §Scope never names `shell_frame.py`** — verified: `grep shell_frame` over
`RCA-010.md` returns nothing. It belongs to `RCA-002`/`RCA-005`, so a slice under this
specification can **read** it and cannot **edit** it. That is exactly the property that made
`GOVERNED_CHART_KINDS` a valid expectation for slice 6, and it is the same shape here.

**Use it — and be exact about what it proves.** The flow is registry-driven in one direction:
`shell_frame.py` *decides* the roster, `shell_api.py` hands it to the frame, and `shell.html.j2`
renders whatever it is given. The expectation and the subject therefore sit on the **same** side of
that flow, so equality between them is **two-sided drift detection, not independence**. It catches a
template that stops rendering what the roster names, which is real drift. It cannot catch the roster
itself shrinking: drop a destination and both sides move together, and the equality still holds.

**The independent evidence is the destination-template inventory.** A destination the navigation
names must have a `shell_templates/*.html.j2` that renders it, and that directory derives from no
roster — so a roster shrunk by one leaves a template with no entry pointing at it. The reverse
direction holds too: a destination-shaped template in no navigation is a defect, with the exemptions
(the frame, the two partials, the print surface, the `POST`-only result, the surfaces reachable
without a resolved organization, and the detail surfaces reached *through* a destination) stated
rather than inferred.

### 3. `FR-194` is already satisfied, and a naive guard would break it

There are **two** `<nav>` elements on the decision surface, and that is correct:

| Element | `aria-label` | `aria-current` |
|---|---|---|
| `shell.html.j2:73` `.frame-surfaces` | `frame_surfaces_label` | `"page"` |
| `decision.html.j2:34` `.decision-sources` | `period_label` | `"true"` |

`FR-194` asks for "one navigation per surface, with `aria-current="page"` on exactly one entry."
Both hold: the *surface* navigation is one element, and `aria-current="page"` appears **once**. The
source selector is a landmark for a different purpose, distinctly labelled, and its
`aria-current="true"` is the correct value for a non-page selection.

**A guard counting `<nav>` elements would fire on correct markup** and send an implementer to
remove a labelled landmark. **Count `aria-current="page"`, not `<nav>`**, and assert each `<nav>`
carries a distinct accessible name.

### 4. The two arrow glyphs are `FR-194`-compliant and must survive the glyph scan

`analysis.html.j2:59` and `:82` render `<span class="change-arrow" aria-hidden="true">→</span>`.
These are change separators inside a transition row, **not navigation affordances**; they are
`aria-hidden`; and they are the documented reason `.change-transition` pins `direction: ltr`
(`workspace.css:301`, review on `#377`). **Scope the glyph scan to navigation regions**, or it
breaks reviewed behaviour.

### 5. `SURFACE_VIEWS` is the wrong granularity — the allocation plan is right about this

`shell_controls.py:73` holds **seven semantic views**, while the navigation names **four shell
surfaces**. Asserting one as the other is a real signal at the wrong granularity. Do not use it
for navigation extent. (It remains readable for anything genuinely about views.)

### 6. Another agent is working in this repository concurrently

`git worktree list` shows worktrees on `codex/fnd-004-ui-contract-reference-index` and a detached
`d2a01fc`, neither created by this slice. **Do not remove them.** But:

- **Verify the interpreter before trusting any test run.**
  `./.venv/Scripts/python.exe -c "import khepri; print(khepri.__file__)"` must print a path under
  this repository's `src`. It printed a stray worktree's path at the start of this slice, and
  `uv sync` repointed it. Slice 6 lost real time to exactly this.
- Re-verify `shell_frame.py`'s roster before asserting against it — a concurrent branch touching
  `RCA-002` surfaces could change it.

---

## Global Constraints

Copied from the allocation plan; every task's requirements implicitly include this section.

- **The interface never invents capability** (`FR-193`): no "coming soon" entry, no disabled control
  standing in for a future surface, no result count the governed set does not fix. **No slice here
  adds a route, address, capability, authorization path, or product destination.**
- **Scope is `RCA-010` §Scope only**: `shell.css` (tokens-only, and must stay so),
  `shell-components.css`, `workspace.css`, `shell_templates/`, `legal_templates/`,
  `shell_copy.py` (chrome labels only), and `tests/`. **Not `shell_api.py`, not `shell_frame.py`,
  not `shell_controls.py`, not any other `src/khepri/runtime/*.py`, not `src/khepri/rca/`.**
- **Filters stay what `RCA-008` `FR-166` models them as** (`FR-197`): the period is a source
  selector, the workspace is the resolved organization scope, and only view filters whose
  definitions admit them are filters. No slice adds a filter, sends a parameter a view's allowlist
  does not name, or retains filter/layout/sort/dismissal state.
- **`FR-199` logical properties only**, with the carve-outs slice 2b established:
  `workspace.css:310` and `:372` carry deliberate `direction: ltr` (review `#377`), and
  **`min-height` is not a directional property** — a block size has no direction to mirror. Any
  scan must exclude both by name or it reports defects that are not defects.
- **`FR-201` and `FR-206` already have instruments** from slice 2b in
  `tests/test_r807_shell_quality.py`. **Extend them; do not duplicate** — a near-duplicate guard
  trips CodeScene's Low Cohesion on the test module itself.
- **No inline script or style, and the CSP is never weakened.**
- **A chrome label names a region of the interface.** The moment a word would describe a metric,
  refusal, caveat, population, version or governed state, it is `RRA-009`'s, `RRA-011`'s,
  `RRA-014`'s or `RCA-008`'s.

### CodeScene

The gate fails at **600 lines** and **four responsibilities** per module.
`tests/test_r807_shell_quality.py` is already large — measure it before adding, and if these tests
would push it over, they belong in a new `tests/test_u1_05_navigation_and_filters.py`. Slice 6 had
to split a module *after* CodeScene failed; measuring first is cheaper. Shared fixtures are
imported, never copied.

---

## Tasks

### Task 1 — RED: the navigation's extent, against an independent source

- [ ] New test: the destinations `shell.html.j2` renders equal the roster `shell_frame.py` decides,
      for an organization whose `Offers` admit everything.
- [ ] **Read the expectation from `shell_frame.py`** — `_WORKSPACE_DESTINATIONS`,
      `_ANALYSES_DESTINATION`, `_TEAM_DESTINATION`. It is outside `RCA-010` §Scope, so this slice
      cannot widen it to match a mistake. Assert **equality plus non-empty**, never `>=`.
- [ ] Compare the destinations as an **ordered sequence**, not a set. `FR-121` fixes the order and
      `shell_frame.py:110-114` renders it from an ordered tuple, so a set comparison would admit a
      shuffled navigation, a destination named twice, or a dropped duplicate.
- [ ] **Build the independent half: the destination-template inventory** (rationale 2). Equality
      against the roster is drift detection only, because the roster determines what the template
      renders. So also assert that every destination named has a template of its own under
      `shell_templates/`, and that every destination-shaped template is named by the navigation,
      with the exemptions listed explicitly. That directory derives from no roster, which is the
      whole of what makes this half independent.
- [ ] Mutate **three** ways, separately — each mutant leaves the others unproven:
      drop a destination from the rendered nav → must fail; add an entry the roster does not name
      → must fail; **drop a destination from `shell_frame.py`'s roster** → must fail **on the
      inventory half**, and is the mutant the equality alone cannot catch.
- [ ] Commit: `test(u1-05): assert the navigation's extent against the frame's roster`

### Task 2 — RED: exactly one `aria-current="page"`, and distinctly named landmarks

- [ ] Count `aria-current="page"` across each rendered surface and assert it is **exactly one**
      where the surface is a navigation destination.
- [ ] **Do not count `<nav>` elements** (finding 3). Instead assert every `<nav>` carries a
      **distinct, non-empty** `aria-label`, so a second landmark is admitted only when it says what
      it is for.
- [ ] Mutate: make `aria-current` unconditional → must fail with two. Remove the condition entirely
      → must fail with zero. Give two `<nav>`s the same label → must fail.
- [ ] Commit: `test(u1-05): hold one current page and distinctly named landmarks`

### Task 3 — RED: no navigation entry for a surface the shell does not serve

- [ ] Drive a shell whose `Offers` withhold `records` and `analyses`, and assert the navigation
      names **only** what remains — no "coming soon", no disabled control (`FR-193`).
- [ ] Assert the withheld destinations are **absent from the markup**, not merely unstyled.
- [ ] Mutate: render a withheld destination anyway → must fail.
- [ ] Commit: `test(u1-05): refuse a navigation entry for an unserved surface`

### Task 4 — RED: no directional glyph in a navigation region

- [ ] Scan the **navigation regions only** — the `<nav>` subtrees of a rendered surface — for a
      literal directional glyph (`←→↑↓⇐⇒‹›«»`).
- [ ] **Assert the two `aria-hidden` arrows in `analysis.html.j2` still pass** (finding 4), so the
      guard's scope is itself pinned. A template-wide scan would break reviewed behaviour.
- [ ] Mutate: put `→` inside a `<nav>` → must fail. Confirm the change-arrows still pass.
- [ ] Commit: `test(u1-05): forbid a directional glyph in a navigation region`

### Task 5 — RED: the language switch preserves surface and position

- [ ] `FR-195`: the switch swaps the language segment and keeps the rest of the address, **query
      string included** — `decision.html.j2`'s comment records that the applied filter state
      survives the switch precisely because it is in `surface_path`.
- [ ] Assert on a surface **carrying a query string**, or the test cannot see the property it claims.
- [ ] Note `invitation_issued` renders no switch by design (`shell.html.j2`'s comment): a POST
      result has no address to re-request. Assert that exemption rather than failing on it.
- [ ] Mutate: build the switch from a path without the query string → must fail.
- [ ] Commit: `test(u1-05): the language switch keeps the surface and its applied state`

### Task 6 — RED: every effective filter is visible and announced

- [ ] `FR-196`: on the surface carrying the figures they qualify, the applied filter set is
      **visible** and **announced to assistive technology**.
- [ ] Measured in the real browser at the supported viewports, following
      `test_r807_shell_quality.py`'s three-sheet link-order harness — a stylesheet read cannot see
      visibility. **Slice 2b's lesson: a guard that reads the model cannot see the surface.**
- [ ] A narrow viewport may collapse the controls into a disclosure, **and the applied filters stay
      visible when it does** (`FR-196`).
- [ ] Mutate: hide the applied-filter region at the narrow viewport → must fail.
- [ ] Commit: `test(u1-05): applied filters stay visible and announced`

### Task 7 — RED: no route, handler, destination or capability changed

- [ ] Static scope evidence over the authorized paths (§Verification): assert `shell_api.py`,
      `shell_frame.py` and `shell_controls.py` are **unmodified** by this slice, e.g. by comparing
      against `git show origin/main:<path>` or asserting no route table entry changed.
- [ ] `FR-197`: no filter added, no parameter outside a view's allowlist, no retained state.
- [ ] Commit: `test(u1-05): pin the scope boundary`

### Task 8 — GREEN, only where a RED demands it

- [ ] Fix only what the RED tests fail on. **Finding 1 says most of this behaviour is already
      correct**, so a large GREEN diff means a test is asserting something the specification does
      not require — re-read `FR-193`–`FR-197` before writing it.
- [ ] If a chrome label is needed to name a region, add it to `shell_copy.py` under the existing
      import-time parity discipline.

### Task 9 — Verify

- [ ] `./.venv/Scripts/python.exe -c "import khepri; print(khepri.__file__)"` — **must** be this
      tree (finding 6).
- [ ] The targeted modules, then `./.venv/Scripts/python.exe -m pytest -q` — **the full suite.**
      Template and ARIA changes break suites nobody opened.
- [ ] `uv run khepri-gov validate`; `uv run ruff check .` (**never `ruff format`**);
      `git diff --check`.
- [ ] Write `docs/superpowers/plans/2026-09-18-u1-slice-4-evidence.md`: per-mutant results, full
      stdout including failures, and any deferral with a named owner.

### Task 10 — Pre-flight and one PR

- [ ] `git fetch origin --prune` **first**, then CodeScene `analyze_change_set`. Measure the test
      module's size before it fails the gate.
- [ ] **Self-mutate every guard before requesting review.** On slices 2b and 6, gaps found locally
      cost minutes and gaps that reached CI cost a full pipeline cycle each.
- [ ] One PR: plan+RED commits then the implementation commit. Branch off `main`, never stacked.
- [ ] **Batch every review fix into one push per round.**

---

## What this slice does not do

- **No `shell_api.py`, `shell_frame.py` or `shell_controls.py` change.** The destination roster and
  the view list are read, never edited — that is what makes them independent sources.
- **No new `<nav>` removed for being second.** Finding 3: a distinctly labelled landmark is correct.
- **No change to the two `aria-hidden` change arrows.** Finding 4.
- **No filter added, no parameter widened, no state retained** (`FR-197`).
- No route, capability, governed word, or telemetry event; `KHEPRI-DEC-015` §3 stands unamended.
- No `journey.css` or report stylesheet — those are the companion plan's.
- No shared token layer across families (`FR-201`).
