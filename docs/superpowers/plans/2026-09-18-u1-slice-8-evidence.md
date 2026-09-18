# `U1` slice 8 — Bounded responsive and right-to-left hardening: evidence

Execution record for `docs/superpowers/plans/2026-09-18-u1-slice-8-execution-plan.md`.
Branch `claude/u1-slice-8-responsive-rtl`, based on `main` at `228200c`.

**No execution plan existed for this slice.** Slice 5's plan existed only because slice 4 authored
it in parallel. This slice's plan was written first, findings-first, and committed as `8bcd654`
before any test was written.

---

## `FR-198` is asserted in CI by nothing, and that decided the module's shape

The repository marks browser cases `@pytest.mark.browser`, whose own description reads "skipped when
it is not installed". CI (`.github/workflows/governance.yml:87`) runs `uv run pytest` with **no
browser install step**:

```text
$ pytest tests/test_r807_shell_quality.py -m browser -rs
43 skipped
```

So the pre-existing overflow assertion — `document.documentElement.scrollWidth <= innerWidth`, which
is `FR-198`'s central claim — **has never executed in CI**. Adding more browser-only assertions would
have added more guards that never run.

**Consequence for this slice, and it is structural, not cosmetic.** As much of `FR-198`/`FR-199` as
possible is asserted **without a browser**: the three absences, the stylesheet scan, `lang`/`dir`,
`dir="auto"`, truncation and bilingual parity are all static and run everywhere, CI included. Only
two genuine layout questions sit behind the marker — page overflow, and trust-state adjacency.

**And those two now actually run.** `_launch_chromium` falls back to a Chromium discovered under
`PLAYWRIGHT_BROWSERS_PATH` when the default lookup misses one, because the installed Playwright and
the browser build on disk disagree in this container:

```text
$ pytest tests/test_r810_shell_responsive_rtl.py -m browser
22 passed in 18.66s          # not "22 skipped"
```

**Still owed, and named rather than assumed:** CI installs no browser, so those 22 skip there. The
workflow file is not in `RCA-010` §Scope. **Owner decision** — see the deferrals table.

---

## Findings

### 1. `FR-199` is ALREADY SATISFIED, and the requirement says so itself

`FR-199`'s own sentence: "The shell's stylesheets **currently contain no physical directional
property** and a slice under this document does not introduce one." Verified across all three sheets
for `left`, `right`, `margin-*`, `padding-*`, `border-left/right`, `float`, `clear` and
`text-align: left|right`:

| Sheet | Physical directional declarations |
|---|---|
| `shell.css` | none |
| `shell-components.css` | none |
| `workspace.css` | **two `direction: ltr`**, `:310` and `:372` |

`direction` is not scanned as physical — it sets the writing direction rather than a physical edge —
and the two shipped uses are `.change-transition` and the `.decision-formula`/`.decision-citation`
pair, reviewed and landed on `#377` to hold an LTR run of digits inside Arabic prose. They are
carved out **by name**, and a separate guard holds the carve-out to exactly those two so a third
cannot ride `#377`'s justification.

### 2. `lang`, `dir`, `dir="auto"` and truncation already ship correctly

`shell.html.j2:2` renders `<html lang="{{ language }}" dir="{{ direction }}">` — both server-computed.
`dir="auto"` isolates the customer-controlled organization name. Truncation is visual only
(`text-overflow: ellipsis`), leaving the text node whole. All three are pinned, including the
stronger claim that the **template** infers neither value: a `{% if language == 'ar' %}` writing
`dir="rtl"` would satisfy a rendered check while moving the decision into the presentation layer.

### 3. The drawer's focus trap is OUT OF SCOPE — and slice 5's reason for it was false

`FR-198` asks that "a drawer becomes a full-screen sheet with focus trapped and restored on close".
The drawer is a native `<details>`/`<summary>`, which needs no trap because it is not a modal.

**Slice 5 claimed the shell's CSP forbids script. It does not.**

```text
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; ...
```

`script-src 'self'` explicitly **permits** same-origin script; `default-src` is only the fallback for
directives not otherwise named. The journey ships five `.js` files under that identical policy,
loaded with `<script type="module">` from `journey/templates/base.html.j2:31`.

So a focus trap is **implementable**, not structurally impossible. What bars it is **authority**:
`RCA-010` §Scope grants three named stylesheets, two template directories, `shell_copy.py` and
`tests/` — **no JavaScript file, and not the `shell_assets/` directory**.

Had this slice inherited slice 5's premise it would have recorded the wrong deferral reason. The
claim is corrected at source (`95494b0`), the test body unchanged, and slice 8 asserts the policy
still permits script so the correction cannot silently rot back.

### 4. Two of `FR-198`'s degradations have no subject

- **No `<table>`** on any shell surface; breakdowns render as `<ul>`/`<li>`.
- **No chart**; `FR-198` writes the conditional itself — "a chart, **where one is present**".

Both asserted as absences, so the day either arrives it meets a guard saying the degradation is owed.

### 5. The overflow assertion existed and was narrower than the requirement

`test_shell_surfaces_are_operable_at_every_viewport` measures 1180 and 390. The shell's only
breakpoint is `max-width: 40rem`, used at `workspace.css:243`, `:327`, `:412`. Neither viewport
measures **at** the switch. This slice brackets it — 360 / 639 / 640 / 641 / 1024 / 1440 — and
extends that case rather than re-founding it, duplicating neither its target-size nor its `dir`
assertions.

---

## Mutation record

Every guard mutated after the implementation was committed, pattern-targeted throughout.

```text
== FR-198 absences ==
a <table> on data.html.j2                    expect=FAIL got=FAIL OK
an <svg> chart on analyses.html.j2           expect=FAIL got=FAIL OK
a <script> on decision.html.j2               expect=FAIL got=FAIL OK
drawer <details> becomes a <div>             expect=FAIL got=FAIL OK
== FR-199 physical properties ==
margin-left in workspace.css                 expect=FAIL got=FAIL OK
text-align: right                            expect=FAIL got=FAIL OK
float: left                                  expect=FAIL got=FAIL OK
the SAME rule inside a comment               expect=PASS got=PASS OK
a third, unreviewed direction: ltr           expect=FAIL got=FAIL OK
== FR-199 lang / dir / truncation ==
dir hard-coded in the frame                  expect=FAIL got=FAIL OK
lang hard-coded in the frame                 expect=FAIL got=FAIL OK
org name loses dir=auto                      expect=FAIL got=FAIL OK
a template truncates a value                 expect=FAIL got=FAIL OK
== FR-198 layout (browser, actually run) ==
a 200vw element on overview.html.j2          expect=FAIL got=FAIL OK
the figure's card renamed                    expect=FAIL got=FAIL OK
availability hoisted out of the card         expect=FAIL got=FAIL OK
== FR-199 parity ==
the evidence drawer in English only          expect=FAIL got=FAIL OK
a RENDERING .empty-state in English only     expect=FAIL got=FAIL OK
```

### Three of the first mutants were no-ops, and catching that is why they are run

| Mutant as first written | Why it proved nothing |
|---|---|
| `data-moved="1"` added to the trust state | An attribute does not move the element out of its card |
| `team.html.j2`'s empty state gated to English | That `{% else %}` branch is never taken — the fixture has members |
| `overview.html.j2:27`'s empty state gated to English | `:27` and `:54` do not render; only `:95` and `:109` do |

Each reported PASS and looked like a weak guard. Probed, each turned out to be a dead mutant. The
replacements — renaming the figure's card, gating the evidence drawer, gating `:95` — all fail
correctly.

**The lesson, sibling to slice 5's.** Slice 5 recorded that a mutant must be **pattern-targeted**,
not line-targeted, because a later task's edit shifts lines and silently disarms it. This slice adds:
a mutant must target markup **the fixture actually renders**, verified by probe. Present in the
template is not the same as reached by the case, and a mutant on an untaken branch proves nothing
while looking exactly like proof.

The probe that settles it is cheap — mark every candidate line with a distinct sentinel and see which
sentinels reach the render:

```text
$ # each `class="empty-state"` tagged data-probe="L<line>"
en ['L95', 'L109']
ar ['L95', 'L109']
```

---

## Verification

```text
$ pytest -q                                  # FULL suite, this branch
5637 passed, 130 skipped, 2 xfailed in 378.49s

$ pytest -q                                  # FULL suite, main at 228200c, same container
5576 passed, 130 skipped, 2 xfailed in 341.97s

delta: +61 passed, +0 skipped, +0 xfailed    # exactly test_r810's 61 collected tests
```

The baseline was **re-measured on `main` in this container** rather than carried over from slice 5's
run, which reported 5575. The one-test difference between those two runs is variance, not a change;
quoting it as the baseline would have made the delta read `+62` and implied a test appearing from
nowhere.

```text
$ pytest tests/test_r810_shell_responsive_rtl.py -q      61 passed in 19.78s
$ pytest tests/test_r810_shell_responsive_rtl.py -m browser   22 passed in 18.66s
$ pytest tests/test_r808_shell_state_grammar.py -q        8 passed, 1 xfailed

$ khepri-gov validate      Governance validation passed.   (exit 0)
$ ruff check .             All checks passed!              (exit 0)
$ git diff --check                                         (exit 0, clean)
```

**No production file changed at all.** The diff is one new test module, one corrected docstring in
slice 5's module, the plan and this evidence.

---

## Deferred, each with its owner

| Item | Why | Owner |
|---|---|---|
| **The drawer's full-screen sheet with a focus trap** | Needs a JavaScript asset. The CSP permits one (`script-src 'self'`), so this is an **authority** limit, not a structural one: `RCA-010` §Scope grants no JS file and not `shell_assets/` | **An owner decision plus a specification granting a shell script asset.** Held meanwhile at the native `<details>` shape that needs no trap |
| **Browser cases do not run in CI** | `.github/workflows/governance.yml` installs no browser, so all 65 browser cases skip there — including `FR-198`'s overflow assertion. The workflow file is **not in `RCA-010` §Scope** | **The owner.** A `playwright install --with-deps chromium` step would make `FR-198`'s layout half real in CI; until then it is proven locally and stated, not assumed |
| **A table scrolling in a focusable region** | No `<table>` on any shell surface | The slice that first renders one. Asserted as an absence |
| **A chart keeping full width** | No chart on the shell; the requirement writes the conditional itself | `RRA-015`. Asserted as an absence |
