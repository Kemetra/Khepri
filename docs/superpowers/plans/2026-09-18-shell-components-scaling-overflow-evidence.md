# `shell-components.css` — 200% text overflow: the fix and its evidence

**Authority:** active `RCA-010` `FR-200` — "text scaling to 200% without loss of content or
function" (`RCA-010:223`). `src/khepri/rra/journey/assets/shell-components.css` is named in
`RCA-010` §Scope (`:120`) as "the shell's component rules".

**Why this is its own slice.** `#486` (slice 9b) found the defect and, per its allocation block,
**did not fix it**: "A floor failure discovered here opens a follow-on slice under `RCA-010` —
named for the file that fails — and does not widen this slice past `tests/`. An evidence slice
that edits a stylesheet or a template to make its own assertion pass has left its scope, and the
failure it hid is still in the product." This is that follow-on slice, named for
`shell-components.css`.

**Base:** `addf010` (`#486`).

---

## The defect

At the 390px viewport with 200% text, three shell surfaces overflowed horizontally, **in English
only**:

| Surface | `scrollWidth` | Over by | `h1` |
|---|---|---|---|
| `switcher` | 418 | 28px | "Choose an organization" |
| `no_membership` | 418 | 28px | "You are not in an organization yet" |
| `compare` | 411 | 21px | "Comparison" |

## The mechanism, measured rather than inferred

`.shell-main` (`:36`) and `.document-card` (`:68`) both pad with `var(--space-4, 1rem)`. `rem` is
relative to the root font size, so doubling the text doubles the padding too and the content box
**narrows** exactly when its contents grow:

```
100%:  main padding 16px  ->  card clientWidth 340  ->  h1 box 308px, h1 content 308px   (fits)
200%:  main padding 32px  ->  card clientWidth 308  ->  h1 box 244px, h1 content 345px   (overflows)
```

The heading should still wrap — `white-space` is `normal` the whole way up and no ancestor is a
non-shrinking flex item. Measuring each word at the scaled size shows why it cannot:

```
font-size 64px, h1 box 244px
  "Choose"        199px
  "an"             68px
  "organization"  345px   <- one word, wider than the box
```

**A single word is wider than its container**, and `overflow-wrap: normal` will not break inside a
word. So the word pushed the page wider instead. `"Comparison"` is one 10-character token, which
is why the shortest of the three headings still overflowed.

**Arabic passed at the same width throughout.** This reads like a right-to-left defect and is not
one: Arabic headings simply have shorter words. The variable is English string length against that
box.

## The fix

One declaration on `.document-card`:

```css
overflow-wrap: break-word;
```

**Why there.** `overflow-wrap` inherits, so setting it on the card reaches the headings and prose
inside rather than being repeated per element.

**Why `break-word` and not `anywhere`.** Both clear all three surfaces — measured, not assumed:

| Candidate | `switcher` | `compare` | `no_membership` |
|---|---|---|---|
| baseline | 418 (over 28) | 411 (over 21) | 418 (over 28) |
| `break-word` | **390 fits** | **390 fits** | **390 fits** |
| `anywhere` | 390 fits | 390 fits | 390 fits |

`break-word` is the weaker of the two: it does not affect min-content intrinsic sizing, so it
cannot change how the card negotiates width with its siblings. Preferred for that reason.

**Why not the alternatives.** Reducing the padding at narrow widths does nothing here — the test
scales the root font size and the **viewport width never changes**, so a `px`-based media query
never matches, and neither does real browser text-zoom, which is what `FR-200` is about. Clamping
the heading's font size is barred outright by slice 2b's
`test_the_shell_component_layer_declares_no_raw_type_size`, which scans this same sheet.

## Verification

### Red, then green — on the assertion `#486` already built

`#486` pinned the three cases two-sided in `_SCALING_OVERFLOW`. Removing the pin restores the
plain assertion and produces the RED state at `dfc16ad`:

```
3 failed, 37 passed   <- exactly compare/en/390, no_membership/en/390, switcher/en/390
```

Then the declaration at `2fc8af5`:

```
40 passed             <- every surface, both languages, both viewports
```

The constant and its `if/else` were **deleted rather than emptied**. An empty frozenset leaves a
branch that can never fire, beside a comment describing a finding that is closed — the stale-guard
shape this repository keeps finding.

### Nothing changed at 100%

`break-word` should act only on a word that would otherwise overflow. Checked rather than asserted,
across all ten surfaces in both languages at 390px, comparing `scrollWidth`, body height and
`innerText` length with and without the declaration:

```
surfaces whose 100% rendering changed: 0
```

### The guards this fix could have tripped

| Guard | Source | Result |
|---|---|---|
| No raw type size in this sheet | slice 2b | pass |
| No physical directional property | slice 8 (`_PHYSICAL`) | pass — `overflow-wrap` is logical |
| `shell.css` stays tokens-only | §Scope, `R801` | pass — untouched |

`tests/test_r807_shell_quality.py`, `test_r810_shell_responsive_rtl.py`, `test_r801_shell_tokens.py`
— **148 passed**.

### Full reach

`overflow-wrap` inherits, so it reaches every descendant on every shell surface **and every legal
page**, which link the same sheet. The whole accessibility module was run, not only the three
surfaces fixed: **256 passed, 20 skipped** (the skips are `FR-200`'s announcement clause, which has
no reachable subject — `#486` Finding 2, unchanged by this slice).

## Gate results

| Gate | Result |
|---|---|
| `pytest` (whole suite) | see PR — run with an isolated `--basetemp` |
| `tests/test_r811_shell_accessibility.py` | 256 passed, 20 skipped |
| guard suites (2b, 8, R801) | 148 passed |
| `ruff check .` | passed |
| `khepri-gov validate` | passed |
| CodeScene | `shell-components.css` unchanged in health |

## What this slice did not do

- **It did not touch `.shell-main`'s or `.document-card`'s padding.** The `rem` padding is correct
  — it is what makes the layout scale — and narrowing it would trade one floor against another.
- **It did not address `#486`'s Findings 1 or 2.** The computed-contrast floor still does not run
  in CI (`.github/` is outside §Scope, and an owner amendment is needed), and `FR-200`'s
  announcement clause still has no reachable subject.
- **It did not open slice 10b**, the visual-regression slice that follows 9b in the shell chain.
  Landing this first matters for it: baselines captured over a known layout defect would bake the
  defect into the reference images.
