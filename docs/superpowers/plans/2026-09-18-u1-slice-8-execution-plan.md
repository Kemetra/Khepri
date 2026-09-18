# `U1` slice 8 — Bounded responsive and right-to-left hardening, the execution plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax. **Do not skip a RED step, and prove
> by mutation any test that passes on arrival.** Most of this slice's guards pass on arrival; each
> is named below and each needs a mutation proof rather than a bare run. **Mutants must be
> pattern-targeted, never line-targeted** — slice 5's evidence records a line-targeted mutant
> silently disarmed by a later task's edit, reporting PASS over a guard it never exercised.

**Goal:** Make `RCA-010` `FR-198`'s responsive posture and `FR-199`'s right-to-left rules
**provable** on the commercial shell. The slice **adds no state, no cause, no governed word, and no
CSS rule**. Three of `FR-198`'s five named degradations have no subject on this shell or no
authority here, and each is recorded below rather than faked.

**Architecture:** Presentation only, and mostly assertion. `FR-199` states its own premise — "the
shell's stylesheets **currently contain no physical directional property** and a slice under this
document does not introduce one" — so that half is a **preservation** requirement by the
specification's own words, and the work is the instrument.

**Tech Stack:** Python 3.13, pytest, Playwright/Chromium as already pinned, `importlib.resources`
for every asset read. No new dependency, no new production module.

**Spec:** active `RCA-010` `FR-198`, `FR-199`. Design: master specification §9, §10 — **not present
in this repository**; `RCA-010`'s requirement text is the binding authority a slice can read, and
this plan works from it rather than paraphrasing a document nobody here can open.

**Baseline:** `main` at `228200c` (slice 5 merged as `#484`). Slice 8 depends on slices 4 and 5;
both are on `main`.

---

## Global Constraints

Inherited verbatim from the allocation plan's §Scope ceiling, and unchanged by this slice.

- **Scope is `RCA-010` §Scope only**: `shell.css` (tokens-only, **must stay so**),
  `shell-components.css`, `workspace.css`, `shell_templates/`, `legal_templates/`, `shell_copy.py`
  (**chrome labels only**), and `tests/`. **NOT `shell_api.py`, NOT any other
  `src/khepri/runtime/*.py`, NOT `src/khepri/rca/`, and NOT any JavaScript asset** — see finding 3.
- **Adds no state, no cause, no governed word, no route, no capability, no retained state, no
  telemetry event.**
- **`FR-206`: the §7 asset policy is binding and unrelaxed.** No CSS-drawn illustration, no external
  font, image, style, script or CDN dependency.
- **No inline script or style, and the CSP is never weakened.**
- **No test under another specification's Verification is weakened or deleted.**
- **Extend, do not duplicate.** `test_r807_shell_quality.py` already carries the browser harness and
  a two-viewport operability case; slice 2b's `FR-201` and `FR-206` instruments stay cited.

---

## Findings that set this slice's scope

Established against `main` at `228200c` **before** this plan was written. Four of the five change
what the slice can ask for.

### 1. `FR-199` is ALREADY SATISFIED, and the specification says so itself

`FR-199`'s own sentence is "The shell's stylesheets **currently contain no physical directional
property** and a slice under this document does not introduce one." Verified across all three
sheets — `shell.css`, `shell-components.css`, `workspace.css` — for `left`, `right`, `margin-left`,
`margin-right`, `padding-left`, `padding-right`, `text-align: left|right`, `float`, `border-left`,
`border-right`:

| Sheet | Physical directional declarations |
|---|---|
| `shell.css` | **none** |
| `shell-components.css` | **none** |
| `workspace.css` | **two `direction: ltr`**, at `:310` and `:372` |

**The two are pre-approved and must be carved out by name.** They are `.change-transition`
(`:310`) and the `.decision-formula`/`.decision-citation` pair (`:372`) — reviewed and deliberately
landed on `#377`, and the allocation plan's Global Constraints already require any scan to exempt
them. `direction` is also not a *physical* property in the `left`/`right` sense: it sets the writing
direction, which is exactly what an LTR-only run of digits inside Arabic prose needs.

**Verdict: ALREADY SATISFIED (pin it), with the carve-out named.** A scan written from `FR-199`'s
sentence without the exemption fires on two lines a review deliberately landed; the implementer then
either "fixes" working code or narrows the scan until it proves nothing.

### 2. `lang`, `dir`, `dir="auto"` and truncation are all already correct

- `shell.html.j2:2` renders `<html lang="{{ language }}" dir="{{ direction }}">` — both
  **server-computed**, neither inferred in the template.
- `dir="auto"` isolates customer-controlled values: the organization name at `shell.html.j2:58`.
- Truncation is **visual only** and the full value stays in the DOM —
  `shell-components.css:229-236`, whose own comment records that the accessible name stays complete.

**Verdict: ALREADY SATISFIED (pin all three).**

### 3. The drawer's focus trap is OUT OF SCOPE — and the reason is not the one slice 5 gave

`FR-198` asks that "a drawer becomes a full-screen sheet with **focus trapped and restored on
close**". The shell's drawer is a native `<details>`/`<summary>` disclosure
(`_decision_cards.html.j2:76`, `_decision_sections.html.j2:69`). A focus trap requires JavaScript.

**Slice 5 asserted that the shell's CSP forbids script. That is false, and it is corrected here.**
The shipped policy is `default-src 'none'; script-src 'self'; style-src 'self'; …`
(`rra/journey/security.py:21-25`), which the shell imports rather than restates
(`test_r802_shell_unavailable_surface.py:281`). **`script-src 'self'` explicitly permits same-origin
script**, and the journey ships five `.js` files under that same policy, loaded with
`<script type="module">` from `journey/templates/base.html.j2:31`. `default-src 'none'` is the
fallback for directives not otherwise named; it does not override `script-src`.

So a focus trap is **implementable**, not structurally impossible. What bars it is **authority**:
`RCA-010` §Scope grants three named stylesheets, two template directories, `shell_copy.py` and
`tests/`. It grants **no JavaScript file and not the `shell_assets/` directory** — only
`workspace.css` within it. A slice here cannot add the asset a focus trap needs.

**Verdict: DEFERRED, owner named.** Asserted negatively (Task 1) so a later slice cannot ship a
half-trap: the drawer stays a native disclosure, which needs no trap because it is not a modal.
**And slice 5's false claim is corrected in place (Task 5)** — the shell ships no script **by
choice**, not by prohibition, and a guard resting on a false reason invites the next author to
"fix" the CSP.

### 4. Two of `FR-198`'s degradations have no subject on this shell

- **A table.** `grep` for `<table` across `shell_templates/` and `legal_templates/` returns
  **nothing**. The breakdowns render as `<ul>`/`<li>` rows, not tables. "A table scrolls
  horizontally inside a focusable region" has nothing to scroll.
- **A chart.** No chart markup on any shell surface; charts are `RRA-015`'s, and `FR-198` itself
  writes the conditional into the requirement — "a chart, **where one is present**".

**Verdict: NOT EXERCISED, not PASS.** Asserted as absences, so the day a table or chart arrives on
the shell it arrives against a guard that says the degradation is now owed.

### 5. The overflow assertion exists and is narrower than `FR-198`

`test_r807_shell_quality.py`'s `test_shell_surfaces_are_operable_at_every_viewport` already asserts
`document.documentElement.scrollWidth <= innerWidth` — but at **two** viewports, 1180×900 and
390×844. `FR-198` says "no page-level horizontal overflow at **any supported width**".

The shell's only breakpoint is `max-width: 40rem` (640px), used three times in `workspace.css`
(`:243`, `:327`, `:412`). Two viewports never measure **at** the breakpoint, where a layout switches
and overflow is most likely.

**Verdict: EXTEND, do not found.** The existing case stays exactly as it is; this slice adds the
widths that bracket the breakpoint. **Do not duplicate the target-size or `dir` assertions** — that
test owns them.

---

## CodeScene

`test_r807_shell_quality.py` is past the 600-line gate, so slice 8's tests go in a **new module**:
**`tests/test_r810_shell_responsive_rtl.py`** — one responsibility, *the shell's responsive and
right-to-left posture*. Slice 5's lesson applies directly: **per-function cyclomatic complexity
must stay under 9 and nested blocks under 2**, or the gate fails at 9.19 as `r808` did. Prefer
**parametrization** over loops, and lift any nested block into a named helper.

---

## Independent sources

| Assertion | Independent source |
|---|---|
| The set of shell surfaces measured | `SHELL_SURFACES` (`test_r807_shell_quality.py:64`), cross-checked against the template directory |
| The shell's stylesheet set | `importlib.resources` over the three sheets, each with a non-emptiness guard |
| The shell's CSP | `khepri.rra.journey.security.SECURITY_HEADERS` — `RRA`'s, outside `RCA-010` §Scope |
| The breakpoint the viewport matrix brackets | `workspace.css`'s own `@media (max-width: 40rem)` |

---

## Tasks

### Task 0 — Branch and prove the environment

- [ ] Branch off `main` at `228200c`: `claude/u1-slice-8-responsive-rtl`. Never stack.
- [ ] Confirm `khepri.__file__` resolves inside this repository before trusting any run.
- [ ] Commit this plan: `docs(u1-08): the slice 8 execution plan`

### Task 1 — RED: no page-level horizontal overflow at any supported width

- [ ] New module `tests/test_r810_shell_responsive_rtl.py`. Parametrize widths that **bracket the
      40rem breakpoint** — 360, 639, 640, 641, 1024, 1440 — over every `SHELL_SURFACES` entry and
      both languages, asserting `scrollWidth <= innerWidth`.
- [ ] **Mark it `@pytest.mark.browser`** and follow `r807:404-430`'s three-sheet injection **in link
      order**, or the measurement runs against an unstyled document.
- [ ] Assert the drawer stays a native `<details>` disclosure with **no scripted trap** (finding 3),
      and that no shell template carries a `<script>` — the absence, with the corrected reason.
- [ ] Assert the two absences of finding 4: no `<table>`, no chart markup, on any shell surface.
- [ ] **Mutate:** a `width: 200vw` element on `overview.html.j2` → must fail; a `<table>` on
      `data.html.j2` → must fail; a `<script>` on `decision.html.j2` → must fail.
- [ ] Commit: `test(u1-08): hold the shell free of horizontal overflow at every supported width`

### Task 2 — RED: `FR-199` logical properties only

- [ ] Scan the three sheets for physical directional declarations, comments stripped with the
      **shared** `_without_comments()`, with a non-emptiness guard per file.
- [ ] **Carve out `.change-transition` and `.decision-formula`/`.decision-citation` by name**, with
      the `#377` review as the stated reason.
- [ ] **Mutate:** `margin-left: 1rem` into `workspace.css` → must fail; `text-align: right` → must
      fail; the same inside a comment → must **pass**; a third `direction: ltr` on an uncarved
      selector → must fail.
- [ ] Commit: `test(u1-08): forbid a physical directional property in the shell sheets`

### Task 3 — RED: `lang`, `dir`, `dir="auto"` and truncation

- [ ] Assert `lang` and `dir` on `<html>` come from server-computed context, never a literal or a
      template-side inference, on every surface in both languages.
- [ ] Assert `dir="auto"` on the customer-controlled organization name.
- [ ] Assert truncation is visual only: the full value is in the DOM.
- [ ] **Mutate:** hard-code `dir="ltr"` → must fail; drop `dir="auto"` from the name → must fail.
- [ ] Commit: `test(u1-08): hold lang, dir and mixed-script isolation server-computed`

### Task 4 — RED: bilingual parity and trust-state adjacency

- [ ] Assert a caveat, refusal, evidence link, state or action present in one language is present in
      the other — counted by **class**, not by text, since the text is what differs.
- [ ] Assert the trust state (`.decision-availability`) stays inside the same card as the figure it
      qualifies **at both widths** that bracket the breakpoint.
- [ ] **Mutate:** render an evidence link in English only → must fail; move the availability outside
      the card → must fail.
- [ ] Commit: `test(u1-08): hold bilingual parity and trust-state adjacency`

### Task 5 — GREEN: correct slice 5's false CSP claim

- [ ] `tests/test_r808_shell_state_grammar.py`'s `test_no_shell_surface_carries_a_loading_affordance`
      docstring asserts the CSP "forbids the script a client-side loading affordance would need".
      **False** — `script-src 'self'` permits it and the journey uses it (finding 3).
- [ ] Rewrite to state the true reason: the shell ships **no script at all, by choice**, and this
      guard is what keeps that true. Cite `security.py`'s policy string and the journey's own
      `<script type="module">` so the next reader can check it.
- [ ] **The test itself does not change** — it was always correct; only its stated reason was wrong.
- [ ] Commit: `docs(u1-08): correct slice 5's false claim that the CSP forbids script`

### Task 6 — Verify, mutate, evidence, one PR

- [ ] Full suite; `khepri-gov validate`; `ruff check .`; `git diff --check`.
- [ ] Re-run every mutant **pattern-targeted**, after the implementation is committed.
- [ ] Write `docs/superpowers/plans/2026-09-18-u1-slice-8-evidence.md`.
- [ ] One PR, stating the three deferrals and the slice 5 correction. **Do not merge.**

---

## Deferred, each with its owner named

| Item | Why | Owner |
|---|---|---|
| **The drawer's full-screen sheet with a focus trap** | Needs a JavaScript asset. The CSP permits one (`script-src 'self'`), so this is an **authority** limit, not a structural one: `RCA-010` §Scope grants no JS file and not `shell_assets/` | **An owner decision plus a specification that grants a shell script asset.** Asserted negatively here so no half-trap ships |
| **A table scrolling in a focusable region** | No `<table>` exists on any shell surface; breakdowns are `<ul>`/`<li>` | The slice that first renders a table on the shell. Asserted as an absence |
| **A chart keeping full width** | No chart on the shell; `FR-198` writes the conditional itself — "where one is present" | `RRA-015` owns charts. Asserted as an absence |
| **A `prefers-reduced-motion` block** | Still unnecessary — slice 5 established zero motion, and `r808` fails if motion arrives without it | Nobody, unless motion ships |
