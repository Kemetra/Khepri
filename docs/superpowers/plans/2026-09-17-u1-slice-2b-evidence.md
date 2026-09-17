# `U1` slice 2b — evidence ledger

Companion to `docs/superpowers/plans/2026-09-17-u1-slice-2b-execution-plan.md`.
Baseline: `main` at `c296704`. Branch `claude/u1-2b-shell-skip-link-and-type-scale`.

---

## The change

Two declarations in `src/khepri/rra/journey/assets/shell-components.css`:

```diff
-  font-size: 0.875rem;
+  font-size: var(--text-sm);
```

on `.member-state` and on the `.member-role, .invitation-role` pair.

**Affected surface: the Team destination only.** All three classes live in
`shell_templates/team.html.j2` and nowhere else — `.member-role` at `:22`, `.member-state` at
`:25`, `.invitation-role` at `:83`. `invitation_issued.html.j2` uses
`invitation-recipient`/`-token`/`-warning` and never `.invitation-role`, so an earlier claim in the
plan and in commit `4b4d856` that two surfaces are affected was **wrong and is corrected here**.
`.member-state` renders only on the `member.disabled` branch.

**The token mapping.** `0.875rem` → `--text-sm` (`0.82rem`) = **0.88px** at a 16px root
(`0.055rem × 16`). `shell.css:107`'s comment lists the run it collapsed —
"`.82/.83/.84/.86rem` -> `--text-sm`" — and `0.875rem` is **not** in it, so this extends that
mapping by one value. `--text-sm` is nearest: `0.055rem` away, against `0.175rem` to `--text-xs`
and `0.125rem` to `--text-base`.

**The bare `var()` resolves everywhere it is used.** `shell.css` precedes
`shell-components.css` in `shell_templates/shell.html.j2:7-8` and in
`legal_templates/legal.html.j2:7-8`, and no template links the component sheet without the token
sheet. A fallback literal would reintroduce the raw number the new scan forbids.

## §G.1 contrast recomputation

Master specification §G.1 requires a recomputation on any type or colour change; recorded rather
than reasoned, per that obligation.

| Element | Colour on surface | Ratio | Threshold | Verdict |
|---|---|---|---|---|
| `.member-state`, `.member-role`, `.invitation-role` | `--muted` on `--surface` | 6.23:1 | 4.5:1 (normal text) | passes |

The size change crosses no threshold: both `14px` (`0.875rem`) and `13.12px` (`0.82rem`) are below
the `18.66px` large-text boundary, so the normal-text 4.5:1 requirement applied before and after.
Colour is unchanged by this slice.

## Guards added, and the mutation that proves each

Seven tests in `tests/test_r807_shell_quality.py`. **Every mutant was reverted with
`git diff` showing zero deletions**, and `git status --short src/` confirmed empty after each.

### `test_the_shell_declares_exactly_one_skip_link_mechanism`

| Mutant | Result |
|---|---|
| a second standalone `.skip-link { … }` rule | FAILED |
| `.skip-link, .shell-skip-alt { … }` — grouped selector | FAILED |
| `:is(.skip-link, .alt-skip) { … }` — functional pseudo-class | FAILED |
| `.skip-nav { … }` — a differently-named skip affordance | FAILED |
| `content: "/*"` … `.skip-link { … }` … `content: "*/"` — string-literal comment escape | FAILED |
| baseline (`.skip-link` + `.skip-link:focus`) | passed |

**Four of those five escaped the first version of this guard.** It compared each captured selector
string to exactly `".skip-link"`, so anything that was not a bare single-selector rule was
invisible. It now counts *selector parts* with `:is()`/`:where()` unwrapped, and refuses a comment
delimiter inside a string literal outright — `re.sub(r"/\*.*?\*/", …, DOTALL)` eats everything
between two such literals, blinding every scan over the result.

**One false failure had to be fixed on the way.** Splitting a part on `::?` makes `.skip-link` the
base of both `.skip-link` and `.skip-link:focus`, so the legitimate shipped pair counted as two
mechanisms. A *mechanism* is a distinct base selector, not a distinct rule, so the assertion counts
distinct skip-like bases and expects exactly `{".skip-link"}`.

### `test_the_shell_component_layer_declares_no_raw_type_size`

| Mutant | Result |
|---|---|
| baseline **before** the CSS fix | **FAILED** — `['font-size: 0.875rem', 'font-size: 0.875rem']` |
| baseline **after** the CSS fix | passed |
| `font-size:12px` — no space after the colon | FAILED |
| `FONT-SIZE: 0.9REM` — uppercase property and unit | FAILED |
| `font-family: "Font 12"` — a numeral in a family name | passed (correct: not a size) |

This is the one guard that was **genuinely RED on arrival**. The uppercase case escaped the first
version: CSS property names and unit identifiers are case-insensitive, so a scan that is not has a
hole the width of a shift key. Both the property match and the unit match now carry
`re.IGNORECASE`.

### `test_the_shell_and_journey_type_scales_stay_separate` (`FR-201`)

| Mutant | Result |
|---|---|
| `--journey-text-sm` **referenced** in `shell-components.css` | FAILED |
| `--text-sm` **declared** in `journey.css` | FAILED |
| `var(--text-sm)` **referenced** in `journey.css` | FAILED |
| baseline | passed |

The third escaped the first version, and it is the asymmetry that mattered: the shell side forbade
any *mention* of `--journey-`, while the journey side forbade only a *declaration* of `--text-*`.
`FR-201` forbids naming another surface's value at all, so both sides now forbid the mention.

Fixing that surfaced a second-order problem worth recording: a raw substring check fires on
`journey.css:37`'s own header comment, which **names** the shell's `--text-*` tokens to explain the
separation ("distinct from the shell's own `--text-*`/`--leading-*` tokens"). A guard that reads
the warning as the violation is a guard the next slice narrows, so all three sheets are
comment-stripped before the check.

### `test_the_shell_component_layer_draws_no_artwork` (`FR-206`)

| Mutant | Result |
|---|---|
| `background-image: url(https://example.invalid/a.png)` | FAILED |
| `@import url("other.css")` | FAILED |
| `content: "→"` — a non-ASCII glyph as an icon | FAILED |
| baseline | passed |

**This guard is knowingly narrower than `FR-206`.** See "Deferred, with its successor named" below.

### `test_the_shell_skip_link_is_visible_only_when_focused` (`en`, `ar`)

The slice's only **behavioural** assertion — measured in the browser, not read off the stylesheet.

| Mutant | Result |
|---|---|
| delete the `inset-inline-start` from `.skip-link:focus` | **FAILED in both `en` and `ar`** |
| baseline | passed (both languages) |

Parametrized over both languages because the off-screen idiom is `inset-inline-start`, which
resolves to opposite sides under `rtl`. Asserts the bounding box is outside the viewport when
unfocused, inside it when focused, and at least 44px high. `pytest.skip` on `Error` from
`chromium.launch()`, matching the module's existing pattern.

### `test_the_team_surface_type_sizes_resolve_from_the_token_scale`

| Mutant | Result |
|---|---|
| `var(--text-smm)` — a typo'd token name | FAILED |
| baseline | passed |

This is the failure a stylesheet scan structurally cannot see: an unresolvable `var()` makes the
element silently inherit, and the declaration still *reads* correct. Asserts `--text-sm` computes
to `0.82rem` and the two Team classes compute to `13.12px`, which is the 0.88px delta observed
rather than asserted.

## Commands, with their output

```text
$ ./.venv/Scripts/python.exe -m pytest tests/test_r807_shell_quality.py \
    -k "skip_link_mechanism or raw_type_size or scales_stay_separate or draws_no_artwork" -q
# before the CSS fix — Task 3's RED
1 failed, 3 passed, 53 deselected in 2.49s
AssertionError: raw type sizes must use the token scale: ['font-size: 0.875rem', 'font-size: 0.875rem']

$ ./.venv/Scripts/python.exe -m pytest tests/test_r807_shell_quality.py tests/test_r801_shell_tokens.py -q
# after the CSS fix, before the browser tests
83 passed in 44.72s

$ ./.venv/Scripts/python.exe -m pytest tests/test_r807_shell_quality.py -k "skip_link_mechanism" -q
# the false failure the base-selector bug caused, recorded because it happened
1 failed in 1.45s
AssertionError: expected one .skip-link mechanism, found 2: ['.skip-link', '.skip-link:focus']

$ ./.venv/Scripts/python.exe -m pytest tests/test_r807_shell_quality.py -k "skip_link_mechanism" -q
# after counting distinct bases rather than parts
1 passed, 59 deselected in 1.45s

$ ./.venv/Scripts/python.exe -m pytest tests/test_r807_shell_quality.py tests/test_r801_shell_tokens.py -q
86 passed in 48.44s

$ ./.venv/Scripts/python.exe -m pytest -q
5585 passed, 77 skipped, 1 xfailed, 65 warnings in 515.36s (0:08:35)

$ uv run khepri-gov validate
Governance validation passed.                        (exit 0)

$ uv run ruff check .
All checks passed!                                   (exit 0)

$ git diff --check
                                                     (exit 0, clean)

$ CodeScene analyze_change_set  (base origin/main @ c296704, fetched first)
quality_gates: passed
status: no-issues-found
checked-file-count: 1, code-health-eligible-file-count: 1
```

**The full suite was run, not only the targeted modules.** 5,585 against 5,582 on `main`: the three
new browser cases (two languages of the focus test, plus the type test).

## One integrity lapse, recorded rather than omitted

During this slice a leftover `FR-201` mutant — `.zz { font-size: var(--text-sm); }` — was briefly
live at the end of `journey.css`, a file **outside this slice's authority** (`RRA-010`'s). It was
reverted and nothing shipped: `git diff origin/main -- journey.css` is empty and the file matches
`main`. But the claim "each mutant reverted with `git diff` showing zero deletions" was not
*continuously* true of the shared working tree, and a concurrent reader observed a test failing on
it.

**The rule this establishes for later slices:** when a mutant must be placed in a file outside the
slice's scope, place it in a `git worktree`, never the shared tree.

## Deferred, with its successor named

**`FR-206`'s asset scan is narrower than the allocation plan assigns slice 2b**, and the gap is
recorded rather than papered over. The plan specifies "a scan over the shell sheets **and
templates**"; the delivered guard reads `shell-components.css` only, and within that file these
shapes currently pass:

- a `::after` border triangle (`content: ""` plus a `transparent` border) — the plan's Task 3c
  names "pseudo-element used as artwork" explicitly
- `background: linear-gradient(...)` used as div-art
- a glyph icon parked in a custom property (`--icon: "•"`, U+2022, outside the scanned ranges)
- a raw type size inside a custom property (`--shell-badge-size: 0.9rem`), which the `font`-anchored
  raw-size scan also does not see

**Successor: slice 4's execution plan**, whose first task widens this scan to `shell.css` and
`workspace.css` (both verified free of non-ASCII characters after comment-stripping, so covering
them costs nothing), adds the gradient/mask/clip-path and border-triangle shapes, replaces the
enumerated glyph ranges with "any non-ASCII outside an allowlist", and extends the raw-size scan to
custom properties consumed by a `font-size`. Templates need per-file carve-outs for the `·`/`§`
they legitimately carry, which is why they are not folded in here.

This is a **deferral with a named owner**, not a silent narrowing — the distinction the repository's
own lessons turn on.

## Corrections to earlier claims in this slice

| Claim | Correction |
|---|---|
| "Discharges master specification §19 slice 2b, the last non-owner item in §18.3" | **Wrong twice.** §18.3's skip-link row is already struck through and marked "**Discharged**" — by `RCA-010`'s own merge at `e915af8` (`#477`), before this slice existed. And §18.3 still carries an open non-owner row: `DIRECTION_PROPOSAL` absorption (`cdfa024`, `#369`), which §19 slice 1 classes as **Docs**. Correct statement: this slice **implements** §19 slice 2b under the authority `RCA-010` established. |
| "the Team destination and the invitation-issued page" | **One surface.** All three classes are in `team.html.j2` only. |
| "three of four guards pass on arrival, each proved by mutation" | True as stated, but four of the five skip-link escape shapes were **not** caught by the first version of that guard, and the uppercase and journey-reference cases escaped two others. All are closed above. |

---

## Second review round — six CodeRabbit findings, eleven mutants

All six verified against the tree before acting; all held. Every revert left
`git status --short src/` empty.

| Finding | Mutant | Before | After |
|---|---|---|---|
| Raw-size scan allowlisted three units | `font-size: 12pt` | passed | **FAILS** |
| …and missed a unitless zero | `font-size: 0` | passed | **FAILS** |
| …must not flag a legitimate weight | `font: 700 var(--text-sm)/1 monospace` | — | passes (no false positive) |
| Artwork scan case-sensitive | `@IMPORT url("x.css")` | passed | **FAILS** |
| …URL scheme too | `background: URL(HTTPS://example.invalid/a.png)` | passed | **FAILS** |
| String-escape guard covered one of three paths | `content: "/*"` … `content: "*/"` in `journey.css` | passed | **FAILS** (refused) |
| Focus assertion checked only the leading edge | `inline-size: 3000px` on `.skip-link:focus` | passed | **FAILS** in `en` **and** `ar` |
| Type measurement skipped absent selectors | delete the `font-size` from `.member-role, .invitation-role` | passed | **FAILS** |

**The last one was the consequential gap.** The loop `continue`d over an absent selector, so it
measured `.member-role` alone — `.invitation-role` was absent because `_StubInvitations` returned an
empty tuple, and `.member-state` was never in the loop. **The test would have passed with two of
the three declarations deleted.** All three must now render and be measured, asserted with
`count() == 1` rather than skipped, and `_StubInvitations` yields one `_PendingInvitation` so
`.invitation-role` exists.

**The unit allowlist is the instructive one.** `rem|px|em` looked exhaustive and was not: `pt`,
`pc`, `ch`, `ex`, `vw`, `%` and a bare `0` all bypassed it. The scan now rejects any numeric
literal in a type declaration, with `_NON_SIZE_NUMERICS` first stripping the parts of a `font`
shorthand that are legitimately numeric — a weight and a line-height — so a fully tokenized
shorthand still passes.

**The string-escape guard protected one of three paths.** `_rules()` in the `FR-201` test read all
three stylesheets through its own stripper with no guard. Both paths now share
`_without_comments()`; a second stripper without the guard reopens the hole for whichever file it
reads.

```text
$ ./.venv/Scripts/python.exe -m pytest -q
5585 passed, 77 skipped, 1 xfailed, 65 warnings in 521.86s (0:08:41)

$ ./.venv/Scripts/python.exe -m pytest tests/test_r807_shell_quality.py tests/test_r801_shell_tokens.py -q
86 passed in 49.59s
```

The fixture change — one pending invitation, so `.invitation-role` renders — touches every test in
the module, which is why the full suite was re-run rather than the targeted one.

**Running total: 23 mutants across 6 guards, every one caught.**
