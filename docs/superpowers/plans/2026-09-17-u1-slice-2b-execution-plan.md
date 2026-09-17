# `U1` slice 2b — One skip-link mechanism on the shell, and two raw font sizes: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:test-driven-development`, then
> `superpowers:executing-plans` (or `superpowers:subagent-driven-development`) to implement this
> plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Do not skip a RED step.**

**Goal:** Give the commercial shell one skip-link mechanism, asserted rather than assumed; remove
the last two raw type literals from `shell-components.css`; and stand up the two guards the
allocation plan assigns this slice — the `FR-201` cross-family token boundary and the `FR-206`
asset policy, neither of which has any instrument today. Discharges master specification §19 slice
2b, the last non-owner item in §18.3.

**Architecture:** Presentation only, in one stylesheet plus `tests/`. The shell's `.skip-link`
rules already exist and already work; what does not exist is anything that **fails** when a second
skip-link mechanism is added or the first is moved. Two `font-size: 0.875rem` declarations are
replaced by the token the repository's own scale comment already assigns them. **No template, no
route, no Python source file is changed.**

**Tech Stack:** Python 3.13, pytest, Playwright/Chromium as already shipped
(`pyproject.toml:31`), CSS custom properties. No new dependency, no new production module.

**Spec:** active `RCA-010` (`FR-193`–`FR-206`), merged 2026-09-17 at `e915af8` (`#477`).
Allocation plan: `docs/superpowers/plans/2026-09-17-u1-shell-allocation-plan.md` (§Slice 2b).
Start authorization: `RCA-010` §"What is now authorized, stated plainly" — "the shell presentation
files named in §Scope may be changed to realize the approved design language, which includes the
master specification §19 slice 2b".
Design: master specification §G.1 (type scale), §G.2 (components), §18.3, §19.

**Baseline:** `main` at `30b4848`. Re-verify every line number below against the tree before
editing; they are hints, and the selectors are the real anchors.

---

## Global Constraints

Copied from the allocation plan's Global Constraints; every task's requirements implicitly include
this section.

- **Scope is one stylesheet and `tests/`.** `RCA-010` §Scope admits
  `src/khepri/rra/journey/assets/shell-components.css`. **This slice writes there and in `tests/`
  and nowhere else.** No `shell.css`, no `workspace.css`, no template, no `shell_copy.py`.
- **`shell.css` stays tokens-only.** `tests/test_r801_shell_tokens.py`'s assertion that it declares
  no rules must still pass. This slice **reads** its tokens and adds none.
- **`FR-201`: a shell presentation value is the shell's.** No slice names a custom property whose
  authority sits with the journey or the report surfaces, and **no shared token layer is
  introduced**. The journey's `--journey-text-*` scale and the shell's `--text-*` scale stay
  separate; this slice touches only the shell's.
- **The journey half is not this slice's.** `journey.css:75-76` also defines `.skip-link` and
  belongs to `RRA-010` (slice 2 of the companion plan). **Unifying *across* the two surfaces is
  authorized by neither plan.**
- **`FR-199`: logical properties only**, under the allocation plan's reading — which **excludes
  `min-height`** (not a directional property; a block size has no direction to mirror) and carves
  out the two approved `direction: ltr` declarations in `workspace.css`, a file this slice does not
  touch. **Do not "fix" the six `min-height: 44px` declarations**; they are correct.
- **No inline script or style, and the CSP is never weakened.**
- **`FR-206`: the §7 asset policy is binding.** No artwork rule, emoji icon, Unicode glyph standing
  in for an icon, pseudo-element used as artwork, `@import`, or external `url(...)`.
- **No route, handler, destination, read, or capability changes** (`FR-193`).

---

## Tree state — verified at `30b4848`

| Fact | Evidence |
|---|---|
| The shell's `.skip-link` rules | `shell-components.css:45` (`.skip-link`) and `:56` (`.skip-link:focus`) |
| Its mechanism | `position: absolute; inset-inline-start: -9999px` off-screen, moved to `var(--space-3, 0.75rem)` on focus, `z-index: 1`, `min-height: 44px` |
| The journey's rival definition | `journey.css:75-76` — **out of scope**, `RRA-010`'s |
| The two raw type literals | `shell-components.css:135` on `.member-state`, `:141` on `.member-role, .invitation-role`; both `font-size: 0.875rem` |
| The token that replaces them | `--text-sm: 0.82rem` (`shell.css:111`) — see the mapping note below |
| The existing skip-link test | `tests/test_r807_shell_quality.py:465-471`, `test_the_skip_link_is_first_in_the_document` — asserts `body.index("skip-link") < body.index("<main")` for each surface in `SHELL_SURFACES`, English only, **no count and no focus-visibility assertion** |
| How a browser test loads the sheets | `tests/test_r807_shell_quality.py:404-416` joins `shell.css`, `shell-components.css` and `workspace.css` in link order — follow this exactly, or the measurement runs against an unstyled document |
| Surfaces affected by the type change | Team and invitation-issued (`.member-*`, `.invitation-role`) |

**The mapping, stated rather than assumed.** `0.875rem` → `--text-sm` (`0.82rem`), a delta of
**0.88px** at a 16px root. Record that computed figure in the evidence rather than asserting "no
visible change".

`shell.css:107`'s comment lists the run it collapsed — "`.68/.7rem` -> `--text-xs`.
`.82/.83/.84/.86rem` -> `--text-sm`" — and **`0.875rem` is not in it**, so this slice is *extending*
that mapping by one value, not applying a pre-assigned one. The extension is sound: `0.875rem` sits
0.055rem above `--text-sm` and 0.175rem above `--text-xs`, so `--text-sm` is unambiguously nearer,
and the sheet's stated posture is that "four rules do not need four sizes one hundredth apart".
**State this in the PR body** — a reviewer who checks `shell.css:107` will not find `0.875rem`
there, and an unexplained gap between the plan and the comment reads as an error.

**Note the shell and journey scales carry opposite postures, and do not carry one across.**
`shell.css:106` is headed "the near-duplicate runs collapsed" and endorses collapsing; by contrast
`journey.css:57-58` warns that its two small tokens are "a separate decision, not a rounding of the
same one; collapsing them would restyle every paragraph in the journey." This slice touches only
the shell, so the shell's posture governs — but a later slice reading this plan must not apply it
to `journey.css`.

---

## The scan logic is pre-validated

Run against the tree at `c2e2e9a` before this plan was committed, so the execution does not
discover a broken approach at RED. Five cases, using `importlib.resources`, comment-stripping, and
a regex matching `font` **and** `font-size` while excluding `font: inherit`:

| Case | Result | What it proves |
|---|---|---|
| Baseline | 1 base `.skip-link` rule, one `:focus` variant, 2 raw sizes | matches the tree-state table above |
| A second `.skip-link { … }` appended | base count → **2** | the count assertion catches the defect it exists for |
| A commented-out `.skip-link` appended | base count stays **1** | comment-stripping works; a commented rule is not a mechanism |
| The GREEN fix applied | raw sizes → **[]** | the intended fix actually satisfies the scan |
| `font: 600 .9rem/1 monospace` appended | **caught** | the shorthand form is seen — the failure a `font-size`-only scan would miss |

**The fourth and fifth rows are the load-bearing ones.** The fourth shows the fix and the guard
agree, so Task 4 cannot pass by weakening Task 3. The fifth is the defect the allocation plan's
original wording carried: a scan worded for `font-size` alone passes over a size inside the `font`
shorthand, and `journey.css` has five such sizes on the companion plan's side.

**Comment-stripping is required, not optional.** Without it, a rule inside a `/* … */` block counts
as a live mechanism and the count assertion reports a defect that does not exist.

## Tasks

### Task 1 — RED: the skip-link mechanism is not counted

- [ ] Add `test_the_shell_declares_exactly_one_skip_link_mechanism` to
      `tests/test_r807_shell_quality.py`, beside the existing skip-link test.
- [ ] It must assert **on the stylesheet**, not the DOM: parse `shell-components.css` and assert
      the number of rules whose selector is exactly `.skip-link` (ignoring `:focus` and other
      pseudo-class variants) is **exactly 1**, with a non-emptiness guard so a renamed file cannot
      satisfy it vacuously:

      assert declarations, "no rules found in shell-components.css, so this test proves nothing"
      assert base_rules == 1

- [ ] **Confirm it is genuinely RED before writing any fix.** The count is 1 today, so this test
      passes on arrival — that is *not* a RED step, and an unevaluated proof reports as a passed
      one. Make it RED by **mutation**: add a second `.skip-link { … }` rule to
      `shell-components.css`, run the test, confirm it fails naming the count, then `git diff` to
      prove the mutant is reverted with **zero** deletions before continuing. Record both outputs.
- [ ] Commit: `test(u1-2b): count the shell's skip-link mechanism`

**Why a count and not a presence check.** The existing test proves a skip link is reachable. It
cannot see a *second* one added, which is exactly what §19 slice 2b exists to prevent — and
`RCA-010` §Verification asks for "exactly one navigation per surface" reasoning applied here.

### Task 2 — RED: focus visibility is not asserted

- [ ] Add `test_the_shell_skip_link_is_visible_only_when_focused`, parametrized over `"en"` and
      `"ar"`, driving the real browser the way `:395-416` already does — loading **all three**
      sheets in link order.
- [ ] Assert the element is **off-screen when unfocused** and **inside the viewport when focused**,
      by measuring its bounding box rather than reading the stylesheet. A stylesheet assertion
      would restate the CSS; a measurement observes the behaviour.
- [ ] Assert its focused target is **at least 44px** on the element the pointer lands on.
- [ ] `pytest.skip` on `Error` from `playwright.chromium.launch()`, matching the existing pattern at
      `:419-422`, so a machine without the pinned Chromium reports a skip rather than a failure.
- [ ] Make it RED by mutation: delete the `.skip-link:focus` rule, confirm failure, revert, prove
      the revert with `git diff` showing zero deletions.
- [ ] Commit: `test(u1-2b): measure the shell skip link's focus behaviour`

### Task 3 — RED: raw type literals are not forbidden

- [ ] Add `test_shell_components_declares_no_raw_type_size`.
- [ ] Scan `shell-components.css` for **typographic declarations carrying a raw numeric literal** —
      both `font-size:` **and** the `font:` shorthand, because a scan worded for `font-size` alone
      passes over a size hidden in the shorthand. Exclude `font: inherit`, which carries no size.
- [ ] **Anchor the scan to the package via `importlib.resources`**, exactly as the existing tests
      do — never a CWD-relative `Path(...)`, which scans nothing when pytest runs from `tests/`.
- [ ] Assert the file is non-empty *and* the set of offending declarations is empty:

      assert text.strip(), "shell-components.css is empty, so this test proves nothing"
      assert offenders == [], f"raw type sizes: {offenders}"

- [ ] Confirm RED on arrival: it should fail **now**, naming `:135` and `:141`. This one is
      genuinely RED without mutation — record the failure output.
- [ ] Commit: `test(u1-2b): forbid raw type sizes in the shell component layer`

### Task 3b — RED: no cross-family token leak (`FR-201`)

- [ ] Add `test_the_shell_and_journey_type_scales_stay_separate`.
- [ ] Assert **both directions**, since a leak either way breaks `FR-201`: the shell sheets
      (`shell.css`, `shell-components.css`) declare no `--journey-*` custom property, **and**
      `journey.css` declares no `--text-*` property. Read all three via `importlib.resources`.
- [ ] Non-emptiness guard on each file read, so a rename cannot satisfy it vacuously.
- [ ] Make it RED by mutation, **one direction at a time** — a single mutant leaves the other half
      unproven: declare `--journey-text-sm` in `shell-components.css`, confirm failure, revert and
      prove it with `git diff`; then declare `--text-sm` in `journey.css`, confirm failure, revert
      and prove it. Record both.
- [ ] Commit: `test(u1-2b): hold the shell and journey type scales apart`

**Why this belongs here.** Both allocation plans assert the two scales must stay separate, and
nothing tests it — a slice could declare `--text-sm` in `journey.css` and no test would notice.
This is the instrument for the boundary the plans rely on everywhere.

### Task 3c — RED: the §7 asset policy has an instrument (`FR-206`)

- [ ] Add `test_the_shell_component_layer_draws_no_artwork`.
- [ ] Scan `shell-components.css` for: a `background-image` or `content` rule drawing artwork, an
      `@import`, an external `url(...)` host, a pseudo-element used as artwork, and any emoji or
      non-ASCII glyph standing in for an icon. Non-emptiness guard plus an empty-offenders
      assertion.
- [ ] **The shell has no admitted programmatic-drawing exception**, unlike the `RRA` side's charts,
      so this scan needs no carve-out for drawn figures. It must, however, **not** flag the two
      `aria-hidden` `→` change separators at `analysis.html.j2:59,82`, which are template content
      and `FR-194`-compliant — scoping this scan to the stylesheet avoids them by construction.
- [ ] Make it RED by mutation: add `background-image: url(https://example.invalid/x.png)`, confirm
      failure, revert, prove with `git diff`.
- [ ] Commit: `test(u1-2b): forbid drawn artwork in the shell component layer`

### Task 4 — GREEN: replace the two literals

- [ ] In `shell-components.css`, replace `font-size: 0.875rem` with `font-size: var(--text-sm)` on
      `.member-state` (`:135`) and on `.member-role, .invitation-role` (`:141`).
- [ ] Use the bare `var(--text-sm)` — **no fallback literal**. A fallback would reintroduce the raw
      number the scan forbids, and `shell.css` is always linked before this sheet on every surface
      that uses it (verified: the test harness at `:404-416` joins them in that order because the
      pages do).
- [ ] Run Task 3's test: it must now pass.
- [ ] Run Tasks 1, 2, 3b and 3c: all must still pass. **3b matters most here** — the fix introduces
      a `var(--text-sm)` reference in `shell-components.css`, and 3b is the test that would catch a
      slip that reached for `--journey-text-sm` instead.
- [ ] Commit: `feat(u1-2b): put the shell component layer on the type scale`

### Task 5 — Verify the whole suite, not the targeted one

- [ ] `./.venv/Scripts/python.exe -m pytest tests/test_r807_shell_quality.py tests/test_r801_shell_tokens.py -q`
- [ ] `./.venv/Scripts/python.exe -m pytest -q` — **the full suite.** Changing a presentation value
      breaks suites nobody opened; a targeted run cannot see it.
- [ ] `uv run khepri-gov validate`
- [ ] `uv run ruff check .` — **do not run `ruff format`**; there is no CI format gate.
- [ ] `git diff --check`
- [ ] Confirm `test_r801_shell_tokens.py`'s tokens-only assertion on `shell.css` still passes —
      this slice added no rule there.
- [ ] Record every command's full stdout in the evidence file, not a summary.

### Task 6 — Pre-flight and open the PR

- [ ] `git fetch origin --prune` **first** — a stale `origin/main` makes CodeScene's
      `analyze_change_set` return empty results and a meaningless pass.
- [ ] CodeScene `analyze_change_set` against `origin/main`. Expect the CSS file to be
      code-health-eligible; if it reports a finding, read the finding rather than guessing — the
      check-run names the file, rule, score and method.
- [ ] Write the evidence file beside this plan:
      `docs/superpowers/plans/2026-09-17-u1-slice-2b-evidence.md`.
- [ ] Open the PR with the plan+RED commits and the implementation commit **in one PR**, branched
      off `main`, never stacked.
- [ ] State in the PR body: the computed 0.88px delta, that `shell.css` is unchanged, that the
      journey's `.skip-link` is untouched and why, and that no template or Python file changed.

---

## What this slice does not do

- **Does not touch `journey.css`.** The journey's `.skip-link` (`:75-76`) is `RRA-010`'s, and
  unifying across the two surfaces is authorized by neither plan (`FR-201`).
- **Does not unify the two type scales.** `--journey-text-*` and `--text-*` stay separate; the
  shared-token question "needs its own artifact naming both families' paths".
- **Does not harmonize `min-height` with `min-block-size`.** A style question, not an `FR-199` one,
  and outside this slice's goal.
- **Does not change `workspace.css`,** so the two approved `direction: ltr` declarations are not in
  reach and their carve-out is not exercised here.
- **Adds no template, route, capability, filter, retained state, governed word, or telemetry
  event.**
**The `FR-201` and `FR-206` scans stay in this slice.** The allocation plan assigns slice 2b the
cross-family token-leak scan (`FR-201`) and the shell asset-policy scan (`FR-206`), and an
execution plan **takes its scope from the allocation plan rather than reassigning it** — moving an
obligation to a later slice is exactly how a requirement goes missing while each slice points at
another. Both are test-only, need no source change, and are Tasks 3b and 3c below.

## Execution discipline

- One PR for this slice: plan+RED commits, then the implementation commit.
- Tests run with `./.venv/Scripts/python.exe`.
- **On any test or CI failure, invoke `superpowers:systematic-debugging` before proposing a fix.**
- Restore every mutant by `git diff`, never by `str.replace` — require the diff to show **zero**
  deletions.
- The merge to `main` is the owner's.
