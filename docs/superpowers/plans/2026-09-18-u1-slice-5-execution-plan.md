# `U1` slice 5 — The state grammar: the §13 matrix as components, the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:test-driven-development`, then
> `superpowers:executing-plans`. Steps use checkbox (`- [ ]`) syntax. **Do not skip a RED step, and
> prove by mutation any test that passes on arrival.** Six of this slice's eight guards pass on
> arrival; each is named below and each needs a mutation proof rather than a bare run.

**Goal:** Make `RCA-010` `FR-202`'s four-state grammar and `RCA-008` `FR-163`'s two empty rules
**provable** on the commercial shell, and make `FR-203`'s motion prohibition an instrument rather
than prose. The slice **adds no state, no cause, and no governed word** — it presents states that
already exist. Its one behavioural change is the ARIA live-region role on the shell's refusal
element, which today is `role="alert"`: assertive, error-adjacent semantics for something master
specification §13 classes as "**Governed, not error**".

**Architecture:** Presentation only. The state classes already exist and already differ; what does
not exist is anything that **fails** when a refusal is given error paint, when a state class is
merged with an error class, when a motion declaration lands in a shell sheet, or when the two
governed empty rules collapse into one sentence. This slice writes in `shell_templates/`,
`workspace.css` (one stale comment), and a **new** test module. `shell-components.css` gains
nothing. **No Python source file is changed** — and the reason is finding 3 below, which is a real
defect this slice is forbidden to fix.

**Tech Stack:** Python 3.13, pytest, Jinja2 with `StrictUndefined` and unconditional autoescaping,
`importlib.resources` for every asset read, Playwright/Chromium as already pinned
(`pyproject.toml:31`). No new dependency, no new production module.

**Spec:** active `RCA-010` (`FR-193`–`FR-206`), merged 2026-09-17 at `e915af8` (`#477`), for the
shell's presentation of those states; `RCA-008` `FR-163`/`FR-164` for the model presented.
Allocation plan: `docs/superpowers/plans/2026-09-17-u1-shell-allocation-plan.md` (§Slice 5).
Design: master specification §13 (the state matrix), §F (screen contracts F.7–F.15).

**Start authorization, recorded because §19's list omits this slice.** Master specification §19 says
"§18.4's authority exists, so slices **2b, 4, 6, 9, and 10** may start" — **slice 5 is not in that
list**, and `FR-202` is a *requirement*, not a start authorization. The enabling clause is
`RCA-010` §"What is now authorized, stated plainly": "**The shell presentation files named in
§Scope may be changed to realize the approved design language.**" This slice changes only those
files and only their presentation. Read the enabling clause; never infer permission from a
requirement.

**Baseline:** `main` at `b26de23`. **Re-verify every line number below against the tree before
editing** — they are hints, and the selectors and symbol names are the real anchors.

**Slice 4 is in flight concurrently — re-verify before starting.** At the time this plan was
written a branch `claude/u1-05-navigation-and-filters` carried two unmerged commits (`5fd626a`
plan, `59c1a9c` navigation guards) plus uncommitted work in
`src/khepri/runtime/shell_templates/shell.html.j2` and a new
`tests/test_u1_05_navigation_and_filters.py`. **Note the branch name follows the `U1-05` roadmap ID
and is slice 4, not slice 5** — do not mistake it for this slice's work. Every file **this** plan
cites was verified unchanged from `b26de23` by
`git diff --stat b26de23 -- <the cited paths>` (empty), so all line references hold. But the
allocation plan makes **slice 5 depend on slice 4**, so: **re-run that diff before Task 1**, and if
slice 4 has landed, re-verify `_decision_cards.html.j2`, `_decision_sections.html.j2`,
`workspace.css` and `SHELL_SURFACES` before trusting a line number. A docs or plan PR is falsified
by a concurrent code merge; re-verify tree-state claims after each rebase.

**Environment warning, verified at `b26de23`.** `./.venv/Scripts/python.exe -c "import khepri;
print(khepri.__file__)"` resolves to
`C:\Users\user\AppData\Local\Temp\Khepri-fnd004-20260917-01\src\khepri\__init__.py` — a **stray
worktree**, not this repo. `git worktree list` shows two temporary worktrees at `d2a01fc`. **Every
test run in this slice must set `PYTHONPATH=<repo>/src`**, or the suite measures the wrong tree and
a template edit "passes" untested. Confirm the import path prints a path under
`C:\Users\user\Documents\GitHub\Khepri\src` **before** believing any result.

---

## Global Constraints

Copied **verbatim** from the allocation plan's Global Constraints and §Scope ceiling; every task's
requirements implicitly include this section. Where this plan and a specification disagree, **the
specification wins** and this plan is corrected in place.

- **Scope is `RCA-010` §Scope only**: `shell.css` (tokens-only, **must stay so**),
  `shell-components.css`, `workspace.css`, `shell_templates/`, `legal_templates/`, `shell_copy.py`
  (**chrome labels only**), and `tests/`. **NOT `shell_api.py`, NOT any other
  `src/khepri/runtime/*.py`, NOT `src/khepri/rca/`.** `shell_controls.py`'s `SURFACE_VIEWS`
  (`:73`) may be **read** by a test and edited by no slice in this plan.
- **`FR-199`: logical CSS properties only** — **BUT** `workspace.css:310` and `:372` carry
  deliberate `direction: ltr` declarations, **pre-approved per review on `#377`**, and
  **`min-height` is NOT a directional property**. Any scan must **carve those out by name**:
  `.change-transition`, `.decision-formula`, `.decision-citation`, and the six `min-height: 44px`
  declarations in `shell-components.css` (`:50`, `:97`, `:111`, `:117`, `:183`, `:223`). A scan
  written from `FR-199`'s sentence fires on lines a review deliberately landed; the implementer
  then either "fixes" working code or quietly narrows the scan until it proves nothing — the
  guard-that-disarms-itself failure.
- **The `FR-201` cross-family token boundary and the `FR-206` asset policy already have instruments
  from slice 2b** in `tests/test_r807_shell_quality.py`
  (`test_the_shell_and_journey_type_scales_stay_separate` at `:617`,
  `test_the_shell_component_layer_draws_no_artwork` at `:651`). **Extend, do not duplicate.** A
  second scanner over the same files is a second definition, and two definitions drift.
- **Adds no state, no cause, no governed word, no route, no capability, no retained state, no
  telemetry event.** `KHEPRI-DEC-015` §3 stands unamended.
- **The interface never invents capability** (`FR-193`). No route, address, capability,
  authorization path or product destination; no "coming soon" entry; no disabled control standing
  in for a future surface.
- **A shell presentation value is the shell's** (`FR-201`). No custom property, class or asset whose
  authority sits with the journey or the report surfaces, and **no shared token layer across the
  two** — "the question `RRA-012` left open stays open, and answering it needs its own artifact
  naming both families' paths." **Neither this plan nor its allocation plan is that artifact.**
- **`shell.css` stays tokens-only** (§Scope, §Verification). "The test asserting it declares no
  rules stays passing."
- **No inline script or style, and the CSP is never weakened** — the standing shell constraint the
  `R8-07` quality gate enforces.
- **`FR-206`: the §7 asset policy is binding and unrelaxed.** No CSS-drawn illustration, div-art,
  CSS pyramid, CSS scarab, pseudo-element used as artwork, emoji icon, Unicode glyph standing in
  for an icon, or one-off inline SVG illustration. No external font, image, style, script or CDN
  dependency. **The shell has no admitted programmatic-drawing exception** — charts are `RRA-015`'s.
- **Images are evidence, not truth** (`FR-205`). No baseline, screenshot or reference image is read
  as a source of a figure, route, capability, refusal reason or governed word.
- **A chrome label names a region of the interface.** "The moment a word would describe a metric,
  refusal, caveat, population, version, or governed state, it is `RRA-009`'s, `RRA-011`'s,
  `RRA-014`'s or `RCA-008`'s and belongs there" (§Scope). **This slice adds no `shell_copy.py`
  entry at all** — see finding 3.
- **A refusal is a governed result the reader is entitled to, never an error to be hidden or styled
  into something else** (§Higher-order invariants). **No surface traps a reader**: every page,
  refusal surfaces included, carries at least one exit.
- **No test under another specification's Verification is weakened or deleted** (§Scope).
  `tests/test_d105_decision_sections.py` and `tests/test_d105_evidence_drawer.py` are `RCA-008`'s;
  this slice **cites** them and never edits, moves or relaxes them.

---

## Findings that set this slice's scope

Established against the tree at `b26de23` **before** this plan was written, because four of them
change what the slice can ask for and one of them falsifies a claim the allocation plan carries.
Each is a fact about the repository, not a reading of a specification.

### 1. What states exist today, and where — and the four-state count is two-and-a-half, not four

| `FR-202` state | Authored on the shell? | Where |
|---|---|---|
| **Refusal** | **Yes**, **four** elements | `.decision-refusal` at `_decision_cards.html.j2:13` and `_decision_sections.html.j2:11`, both `role="alert"`; `.decision-unsupported` at `decision.html.j2:30`, `role="alert"` — a governed refusal (`FR-137`/`FR-164`: "a parameter no published view admits is refused, not dropped"); `.compare-refusal` at `compare.html.j2:34`, **no role at all** |
| **Empty** | **Yes**, two idioms | `.decision-empty` at `_decision_cards.html.j2:26` and `_decision_sections.html.j2:25`; `.empty-state` at `overview.html.j2:27,54,95,109`, `data.html.j2:41,47`, `analyses.html.j2:85`, `analysis.html.j2:149,177` |
| **Unavailable** (`FR-165`, content-free) | **Yes** | `.decision-unavailable` at `_decision_cards.html.j2:18` and `_decision_sections.html.j2:16`, both `role="note"`; `.decision-evidence-unavailable` at `:106` / `:74` |
| **Loading** | **NO — STRUCTURALLY UNREACHABLE** | See below |
| **Error** | **NO — no error class exists anywhere on the shell** | See below |

**Governed codes.** The two empty rules are `EMPTY_STATED_NO_ROWS = "stated_no_rows"` and
`EMPTY_STATED_ABSENCE = "stated_absence"` (`src/khepri/rca/workspace/decision/seam.py:67,71`),
mirrored in `src/khepri/rra/semantic_views/contracts.py:79,85` with the closed set `EMPTY_RULES` at
`:88`. Their bilingual sentences are `EMPTY_WORDING` (`shell_decisions.py:206-215`).

**There is no loading state on the shell, and there cannot be one.** Verified exhaustively: a grep
for `<script`, `aria-busy`, `spinner`, `skeleton`, `htmx` and `onclick` across
`shell_templates/` **and** `legal_templates/` returns **zero matches**. The surfaces are
server-rendered whole; the shipped `default-src 'none'` CSP forbids the script that a client-side
loading affordance would need, and `FR-206` forbids weakening it. **A state that cannot occur is
not a state to present**, and driving one would be a run that can only produce the null case — NOT
EXERCISED, not PASS. **Verdict: STRUCTURALLY UNREACHABLE. Assert the invariant instead** (Task 4),
so a later slice cannot ship a decorative spinner that names no stage — which master specification
§F.4 forbids even on the journey's own processing surface.

**There is no error state on the shell either.** A grep for `error` across the three shell sheets
and both template directories returns **only prose comments** (`workspace.css:387`, `shell.css:65-66`,
`shell_copy.py:8`) and the journey's own `.error-summary` (`journey.css:148`, **out of scope**,
`RRA-010`'s). `.decision-unavailable` is **not** an error: it is `FR-165`'s content-free
unavailable, which §13 lists in the *Neutral* "Stale or unavailable" row, not the *Danger*
"Processing failure" row. §13's Danger rows — processing failure and export failure — have **no
shell surface**. **Verdict: the error half of `FR-202` is an ABSENCE to be pinned, not a state to
present** (Task 3).

**`FR-202` names four states and the shell authors two-and-a-half.** State the count before
asserting distinguishability, or a test "proving four states differ" is proving something about two.

### 2. `FR-202` is ALREADY SATISFIED — structurally, and by *absence of paint*. The work is pinning it.

This is slice 6's `FR-186` shape exactly: the requirement is met and the slice's value is the
instrument, not the change.

- **"never shares an element or a class with an error"** — trivially true: **no error class
  exists**. Distinct elements, distinct classes: `.decision-refusal` / `.decision-empty` /
  `.decision-unavailable` are three classes on three `<p>` elements in three independent `{% if %}`
  branches (`_decision_cards.html.j2:12-27`, `_decision_sections.html.j2:9-26`).
- **"never carries error paint"** — trivially true, and *fragile*: **`.decision-refusal`,
  `.decision-empty`, `.decision-unavailable` and `.compare-refusal` have NO CSS rule in any shell
  sheet.** Verified by grep across `workspace.css`, `shell-components.css` and `shell.css`: the
  only state rule that exists is `.empty-state { color: var(--muted) }`
  (`shell-components.css:144`) and the muted absence block at `workspace.css:391`. A refusal is
  unpainted body text.
- **"keeps the position the answer would have occupied"** — true by construction: the three
  branches sit in document order *before* the figures they qualify, inside the same
  `.document-card`, and a refused section's `<h2>` and `data-section` attribute are emitted
  unconditionally (`_decision_sections.html.j2:5-7`). The section is not moved, not collapsed, not
  greyed to illegibility — master specification §F.5's rule, holding on the shell too.
- **"distinguished by structure and wording rather than by decoration"** — true, and *necessarily*
  so, because there is no decoration to distinguish them by.

**`workspace.css:385-387` carries stale prose that describes an unattached treatment.** Its comment
says an absence carries "the muted treatment the other stated findings carry, **never the
refusal's**" — asserting a *refusal treatment* that **does not exist**. That is a defined-but-never-
attached shape in a comment: a later reader takes it for shipped behaviour. **In scope to correct**
(Task 7), and correcting the comment is the whole of this slice's `workspace.css` change.

**Verdict: ALREADY SATISFIED (pin it).** No new CSS. The guards are forward-looking: they fail when
a later slice paints a refusal, merges a state class with an error class, or moves a refusal out of
position.

**`--danger` needs a named carve-out.** It **is** used on the shell: `shell-components.css:159`,
`.invitation-warning { color: var(--danger) }`. That is a warning on a **destructive action**, not a
screen state. A scan asserting "no state class carries `--danger`" must **carve
`.invitation-warning` out by name** — the same shape as the `direction: ltr` carve-out — or it
reports a defect that is not one and the implementer narrows it until it proves nothing.

### 3. The two empty rules render distinguishably on the **sections** path and are COLLAPSED on the **cards** path — and this slice is forbidden to fix it

This is the slice's most consequential finding, and it is a **deferral, not a build**.

- **Sections path: correct.** `_SectionView.empty` is the *governed sentence*, resolved
  `EMPTY_WORDING[language].get(reading.empty_rule or "")` (`shell_decisions.py:645`), and the
  template renders `{{ section.empty }}` (`_decision_sections.html.j2:25`). Two rules, two
  sentences. Pinned by `RCA-008`'s own
  `test_the_two_governed_empty_rules_render_distinguishably_on_one_page`
  (`tests/test_d105_decision_sections.py:142`) and
  `test_the_empty_wording_covers_exactly_the_two_governed_rules` (`:272`).
- **Cards path: collapsed.** `_DecisionView.empty` is a **`bool`** —
  `empty=reading.empty_rule is not None` (`shell_decisions.py:494`) — and
  `_decision_cards.html.j2:26` renders the **fixed** `decision.no_rows`, i.e. "This analysis
  published no figures." The governed rule is **discarded at the view-model boundary**.
- **And the fixed sentence is the wrong rule's.** `ExecutiveOverviewView.empty_rule` is pinned to
  `EMPTY_STATED_ABSENCE` (`seam.py:86`; applied at `card.py:255` and `overview.py:120`), whose
  governed sentence is "The source published no value for this." The cards path states the
  `stated_no_rows` sentence for a `stated_absence` finding. `FR-163` is exactly the requirement
  this violates: "a surface that renders both as an empty table misstates the customer's data."

**Every available fix is out of reach, and that is why this is deferred.** `shell_decisions.py` is
`src/khepri/runtime/*.py` — "**Not in scope**" in `RCA-010` §Scope and "**Explicitly outside**" in
the allocation plan's scope ceiling. Minting a second sentence in `shell_copy.py` is barred
**twice**: chrome labels only, and this slice "adds no governed word". **Do not edit that module.**

**Verdict: DEFERRED, owner named — an `RCA-008` slice**, because `RCA-008` owns both `FR-163` and
the `src/khepri/runtime/` module that carries the bug. **Asserted negatively** (Task 2) so a later
slice cannot quietly paper it: the cards path's empty sentence is pinned to what it renders **today**
with the defect named in the test's docstring, and the sections path's two-sentence behaviour is
pinned so a "simplification" cannot collapse it too. A deferral that is only prose is an invitation.

### 4. `FR-203` is testable — and the allocation plan's premise for it is FALSE

**The allocation plan records that `workspace.css` "contains three `transition`/`animation`
declarations". It contains ZERO.** Verified two ways at `b26de23`:

- `grep -nE "^\s*(transition|animation|transform|will-change|scroll-behavior)[-a-z]*\s*:"` over
  all three shell sheets → **exit 1, no matches.**
- The three matches for the *word* are: the class name `.change-transition` (`workspace.css:306`)
  and two prose comments (`:301`, `:369`). **The plan counted the word, not declarations.**
- Also false at `e915af8`, the commit the plan says it verified against:
  `git show e915af8:src/.../workspace.css | grep -cE "^\s*(transition|animation)"` → **0**.

**So the slice's answer to the question the allocation plan poses is: the three declarations do not
exist, and a `prefers-reduced-motion` block must NOT be added.** A reduced-motion block over zero
motion declarations is **dead CSS** — it would gate nothing, and it is precisely the
defined-but-never-attached defect the repository's own lessons name. `journey.css:206` and
`landing.css:232` have such blocks because those sheets **have** motion; the shell does not.

**Verdict: ALREADY SATISFIED (pin it), and the invariant is stronger than `FR-203` asks.** Rather
than scanning for the specific prohibitions (`bounce`, elastic `cubic-bezier`, `parallax`, infinite
`animation-iteration-count`, counting numbers), assert the **superset**: *the shell sheets declare
no motion at all*. That subsumes every named prohibition and cannot be satisfied by a sheet that
adds a "tasteful" transition the enumerated list happens to miss.

**The scan has three specific requirements or it is useless** (Task 5):

1. **Strip comments first**, or `workspace.css:301` and `:369` are false positives.
2. **Do not anchor to line start.** `journey.css:153` proves the packed single-line-rule idiom
   exists in this repository; a start-anchored pattern lets `.x { transition: all 1s }` through.
3. **Match a property-then-colon inside a declaration block**, not the bare word, or
   `.change-transition {` at `:306` fires on its own selector.

Plus an **emptiness assertion** on every file read, so a rename cannot satisfy it vacuously.

`FR-203`'s "a positional transition on a drawer or dialog is short" is **vacuously satisfied**: the
drawer is a `<details>` that opens in place with no transition (`workspace.css:346-352`), and the
allocation plan already allocates the drawer's full-screen-sheet measurement to **slice 8**. This
slice asserts no transition exists; slice 8 measures one if it ever ships.

### 5. Guards that already exist — extend, never found

| Instrument | Where | This slice |
|---|---|---|
| `test_every_shell_template_is_measured` | `test_r807_shell_quality.py:388`, scanning `files("khepri.runtime").joinpath("shell_templates")` at `:396` | **Scans only `shell_templates/`. `legal_templates/` is in `RCA-010` §Scope and reached by no extent assertion** — slice 2b's recorded lesson. This slice records the legal pages' state reachability explicitly (Task 6) rather than inheriting the blind spot |
| `SHELL_SURFACES` (11 surfaces) | `test_r807_shell_quality.py:64-77`, with `_LAYOUT_TEMPLATES`, `_POST_ONLY_TEMPLATES` and `_PRINT_TEMPLATES` exclusion sets at `:81-100` | **Parametrize from this mapping, never a hand list.** A hand-listed scope reproduces the drift the guard exists to catch |
| The three-sheet browser harness | `test_r807_shell_quality.py:404-430` joins `shell.css`, `shell-components.css`, `workspace.css` **in link order** | Follow exactly, or a measurement runs against an unstyled document |
| `test_the_shell_and_journey_type_scales_stay_separate` (`FR-201`) | `:617` | **Cite. Do not duplicate.** Slice 2b's instrument |
| `test_the_shell_component_layer_draws_no_artwork` (`FR-206`) | `:651` | **Cite. Do not duplicate.** Slice 2b's instrument |
| `shell.css` tokens-only | `test_r801_shell_tokens.py` | Must still pass; this slice adds no rule there |
| `FR-163` on the sections path | `test_d105_decision_sections.py:142` | **`RCA-008`'s. Cite, extend beside, never move or weaken** |
| `EMPTY_WORDING` extent | `test_d105_decision_sections.py:272` — derives from `seam.EMPTY_STATED_*`, i.e. **not** a tautology | **Already correct.** Do not re-add |
| Shell CSP | `test_r802_shell_unavailable_surface.py:290` asserts `'unsafe-inline'` absent; `:281` asserts the shell policy **is** the journey policy, imported rather than restated | **An instrument exists.** Task 4 asserts the *template* side (no script element, no `aria-busy`) and **cites** `r802` for the header rather than founding a second policy assertion |
| `role="alert"` on the shell's refusals | **PINNED BY NO TEST.** Only `test_rra_journey_accessibility.py:46,64,67` pins roles, and those are the **journey's**. `test_d107_controls.py:261,269` pins `.decision-no-sources`'s **class**, not its role | **This is slice 5's one genuine BUILD** — see below |

**The complete role inventory, enumerated rather than assumed.** A keyword grep for state words
misses a role on a line that carries none, so this is the output of
`grep -rn 'role=' src/khepri/runtime/shell_templates/ src/khepri/runtime/legal_templates/` —
**thirteen attributes, three of them `role="alert"`**:

| `role="alert"` (assertive) | `role="note"` |
|---|---|
| `_decision_cards.html.j2:13` `.decision-refusal` | `_decision_cards.html.j2:18,26,106,138` |
| `_decision_sections.html.j2:11` `.decision-refusal` | `_decision_sections.html.j2:16,25,74,89` |
| **`decision.html.j2:30` `.decision-unsupported`** | `decision.html.j2:50` `.decision-no-sources`; `analysis.html.j2:50` `.change-notice` |

`legal_templates/` carries **no** `role` attribute — consistent with finding 6's NOT APPLICABLE.
**The third `role="alert"` is the one a keyword grep misses**, and Task 8 must change it too or
Task 3's cross-template scan fails after the build.

**The one BUILD: the refusals' live-region role.** All **three** `role="alert"` attributes above sit
on **governed refusals** — an **assertive** live region, which is error-adjacent semantics for
something §13 classes as "**Governed, not error**" with "**never error paint**". The journey
deliberately uses `role="status"` for its refusal and reserves `role="alert"` for the **transport
error** (`test_rra_journey_accessibility.py:64,67`; master specification §F.3 records the assertion
by name). ARIA state is **explicitly in `RCA-010` §Scope** ("presentation markup and ARIA state
only"), and **no test pins any of the three**, so changing them weakens nothing. `role="status"`
(polite) is the correct grammar and aligns the two families' semantics without sharing a class, a
token or a sheet — so `FR-201` is untouched. `.compare-refusal` carries **no** role and gains the
same one, so the four refusal idioms carry one grammar.

---

## CodeScene: two new test modules are required

**`tests/test_r807_shell_quality.py` is 788 lines at `b26de23` — already past the 600-line gate.**
Slice 5's tests **cannot** land there; adding to it makes an existing overage worse and slice 6
already had to split a module for this reason. The gate is **600 lines and 4 responsibilities per
module**, plus cyclomatic > 9, module mean > 4 and arguments > 4, and **it scores test modules too**.

**The split is decided here, not at PR time.** Slice 6 discovered its split when CodeScene flagged
it, which cost a cycle. Tasks 1–6 are eleven tests over five topics, and the gate is 600 lines
**and 4 responsibilities** — at `r807`'s observed ~31 lines/test, length is comfortable but
**cohesion is the risk**. So **two modules, named now**:

- **`tests/test_r808_shell_state_grammar.py`** — Tasks 1–5. One responsibility, *the shell's
  screen-state grammar*: state-class exclusivity, the two empty rules' presentation, the absence of
  a loading state and of an error state, and the motion invariant. ~250 lines.
- **`tests/test_r809_shell_state_contracts.py`** — Task 6. One responsibility, *the §F per-surface
  state contracts*: the reachability table, the empty-state contract, and the exit invariant. It
  owns the `SHELL_SURFACES` parametrization and the reachability mapping. ~150 lines.

Every new file must score **10.00** in the required server-side Code Health Review, and no tracked
hotspot may decline.
**`test_r807_shell_quality.py` must not absorb any of this.** It is 788 lines at `b26de23` —
already past the gate.

- **Do not move anything out of `test_r807_shell_quality.py`** to make room. Its tests are under
  `RCA-010` §Verification and slice 2b's; moving one is a diff a reviewer must re-verify for no
  gain, and `r807` stays over the gate either way — reducing it is a separate, owner-visible
  decision.
- **Do not add to `tests/test_d105_*.py`.** Those are `RCA-008`'s Verification; §Scope forbids
  weakening them and adding `RCA-010` tests to them confuses which specification governs a failure.
- **Prefer parametrization over new helpers.** Extracting a helper **raises** the module mean;
  fold a parameter into an existing builder instead of minting a sibling.
- **Pre-flight with `analyze_change_set` against `origin/main`, after `git fetch origin --prune`** —
  a stale `origin/main` returns empty results and a meaningless pass.

---

## Independent sources for every extent assertion

Slice 6's lesson: **deriving the expectation from the same constant the subject uses is a tautology
that passes every mutant.** Each extent assertion below names a file **this slice cannot edit**.

| Assertion | Independent source | Why it is independent |
|---|---|---|
| The two governed empty rules, and **exactly** two | `src/khepri/rra/semantic_views/contracts.py:88` — `EMPTY_RULES: frozenset = {EMPTY_STATED_NO_ROWS, EMPTY_STATED_ABSENCE}` | `src/khepri/rra/` is `SV1`/`RRA`'s and **outside `RCA-010` §Scope**. A third rule invented there fails here; a rule renamed there is an **import error** |
| Which view carries which rule | `src/khepri/rca/workspace/decision/seam.py:67,71,86-134` | `src/khepri/rca/` is **outside `RCA-010` §Scope** |
| The set of shell surfaces a state test covers | `SHELL_SURFACES` (`test_r807_shell_quality.py:64`) cross-checked against `files("khepri.runtime").joinpath("shell_templates").iterdir()` | The directory listing is the tree itself; a template added without a case fails |
| The shell's stylesheet set | `importlib.resources` over the three sheets, **each with a non-emptiness guard** | A renamed file cannot satisfy the scan vacuously |
| **`FR-202`'s four-state set** | **NONE EXISTS.** `FR-202` names refusal/empty/loading/error in **prose**; there is no constant, enum or table anywhere in the repository that enumerates them | **Stated rather than faked: use a reviewed literal** — the four-tuple `("refusal", "empty", "loading", "error")` written out in the test module with a comment citing `RCA-010` `FR-202` and master specification §13, and with **two of the four asserted as absences** per findings 1 and 3. A derived-looking expectation here would be a fabrication, which is worse than a literal a reviewer can check against the specification text |

---

## Tasks

### Task 0 — Branch, and prove the environment

- [ ] `git branch --show-current`. **If it is not `main`, stop and read the note above** — slice 4
      was in flight on `claude/u1-05-navigation-and-filters` (which is slice **4**, despite the
      name) with uncommitted work. Do not branch from it and do not discard its changes.
- [ ] `git switch main && git pull --ff-only origin main`, then `git log --oneline -1`. **Record the
      SHA**; if it is past `b26de23`, re-verify every citation with
      `git diff --stat b26de23 -- <cited paths>` before trusting a line number.
- [ ] Branch off `main`: `git switch -c claude/u1-slice-5-state-grammar`. **Never stack on another
      branch** — a PR based on another branch is auto-CLOSED when that base is deleted and cannot be
      reopened or retargeted. In particular, **do not branch off slice 4's branch** even though the
      allocation plan makes slice 5 depend on it; wait for slice 4 to merge to `main`.
- [ ] `PYTHONPATH=$PWD/src ./.venv/Scripts/python.exe -c "import khepri; print(khepri.__file__)"`
      → must print a path under `C:\Users\user\Documents\GitHub\Khepri\src`. **Record the output.**
      Without `PYTHONPATH`, the stray worktree at
      `C:\Users\user\AppData\Local\Temp\Khepri-fnd004-20260917-01` is imported and every result is
      about the wrong tree. **Use this prefix on every command below.**
- [ ] Commit this plan: `docs(u1-05): the slice 5 execution plan`

### Task 1 — RED: the four state kinds share no element and no class (`FR-202`)

**PASSES ON ARRIVAL.** Per finding 2, refusal/empty/unavailable already occupy three classes on
three elements and no error class exists. This is a **forward-looking** guard, so a bare run proves
nothing — it must be made RED by mutation.

- [ ] Create `tests/test_r808_shell_state_grammar.py` with a module docstring recording finding 1's
      count: **`FR-202` names four states; the shell authors refusal, empty and `FR-165`'s
      content-free unavailable, and neither loading nor error is reachable** — with Tasks 3 and 4
      naming the invariants asserted in their place.
- [ ] Add `test_the_shell_state_classes_are_mutually_exclusive`, driving the **decision surface**
      through the real render path (the only surface that can carry refusal, empty and unavailable
      together — see Task 6's reachability table), in **both languages**:
      - each of `decision-refusal`, `decision-empty`, `decision-unavailable` appears on its own
        `<p>` element, and **no element carries two of them**;
      - the refusal element's class attribute contains **no** token matching `error|danger|alert|fail`;
      - a non-emptiness guard: `assert body.strip()` and `assert "decision-refusal" in body`, so a
        template rename cannot satisfy it vacuously.
- [ ] **Mutate three ways, separately** — a single mutant leaves the others unproven:
      1. merge the classes: `class="decision-refusal decision-empty"` in
         `_decision_sections.html.j2` → must fail;
      2. rename the refusal class to `decision-error` → must fail on the token scan;
      3. put refusal and empty in **one** `<p>` → must fail.
- [ ] Revert each mutant with `git diff` showing **ZERO deletions**; `git status --short src/` empty
      after each. **Never restore by `str.replace`** — it restored 8 deleted security filters from 5
      untouched reads on a prior slice.
- [ ] Commit: `test(u1-05): hold the shell's state classes mutually exclusive`

### Task 2 — RED: the two governed empty rules, both paths (`FR-163`)

**Half passes on arrival** (the sections path), **half pins a known defect** (the cards path). Both
need mutation.

- [ ] Add `test_the_two_governed_empty_rules_reach_the_shell_from_an_independent_source`:
      `set(shell_decisions.EMPTY_WORDING["en"]) == set(contracts.EMPTY_RULES)` and the same for
      `"ar"`, plus `assert contracts.EMPTY_RULES`, asserting **equality and non-empty**. A subset
      assertion "only ever weakens" and cannot see a rule **added**.
- [ ] **Independent source:** `contracts.EMPTY_RULES` (`semantic_views/contracts.py:88`), outside
      `RCA-010` §Scope. **Distinct from `test_d105_decision_sections.py:272`**, which derives from
      `seam.py` — this asserts the `RRA` registry and that module agree, which nothing checks today.
- [ ] Add `test_the_two_empty_rules_render_as_two_sentences_on_the_breakdown_sections`, extending
      (**not** duplicating) `test_d105_decision_sections.py:142` by asserting **in Arabic as well**
      and that neither sentence appears where the other's rule applies.
- [ ] Add `test_the_cards_path_states_its_governed_empty_rule` as a **strict xfail** — **not** a pin
      on today's behaviour. **A test pinned to the pre-fix behaviour dies as scaffolding**, and the
      successor slice reads its failure as a regression rather than as the signal it is. So assert
      the **correct** behaviour and mark it:

      @pytest.mark.xfail(strict=True, reason=...)   # the finding-3 text, in full

      The assertion: an empty `ExecutiveOverviewView` reading renders
      `EMPTY_WORDING[language][EMPTY_STATED_ABSENCE]` in the cards region, in **both** languages.
- [ ] The `reason` names the whole defect and its owner: `_DecisionView.empty` is a `bool`
      (`shell_decisions.py:494`), `_decision_cards.html.j2:26` renders the fixed `decision.no_rows`,
      and `ExecutiveOverviewView.empty_rule` is `EMPTY_STATED_ABSENCE` (`seam.py:86`, applied at
      `card.py:255`), so the cards path states the `stated_no_rows` sentence for a `stated_absence`
      finding. **`FR-163` is violated there, and the fix needs `src/khepri/runtime/*.py`, outside
      `RCA-010` §Scope — owner: an `RCA-008` slice.**
- [ ] **`strict=True` is the load-bearing part.** Today the test fails → reported `xfailed`. When the
      `RCA-008` slice lands the fix it passes → `strict=True` turns the XPASS into a **failure**,
      which tells the successor to delete the marker rather than leaving a dead test behind. That
      **hooks the surviving seam instead of the defect.** The idiom already ships in this repository:
      the baseline full-suite run at `b26de23` reports `1 xfailed`, so CI tolerates it.
- [ ] **Do not** also assert the wrong sentence is present. An assertion that today's defective
      output *is* what renders is the scaffolding this rewrite exists to avoid.
- [ ] **Mutate:** delete the `{% if section.empty %}` branch from `_decision_sections.html.j2` → must
      fail; add a third key to `EMPTY_WORDING` **without touching `contracts.py`** → the extent
      assertion must fail. Revert each by `git diff`, zero deletions.
- [ ] Commit: `test(u1-05): hold the two governed empty rules, and pin the cards-path gap`

### Task 3 — RED: no shell state class is an error class (`FR-202`, the error half)

**PASSES ON ARRIVAL by absence.** Per finding 1 there is no error class; this guard is what stops one
appearing under a state's name. It is **the guard that makes the `--danger` carve-out load-bearing.**

- [ ] Add `test_no_shell_state_rule_carries_error_paint`. Read all three shell sheets via
      `importlib.resources`, **strip comments with the shared `_without_comments()` helper**
      (`test_r807_shell_quality.py`; slice 2b's evidence records that a second stripper without the
      string-escape guard reopens a hole), and assert:
      - no rule whose selector names a state class — `decision-refusal`, `decision-empty`,
        `decision-unavailable`, `decision-absence`, `decision-evidence-absent`,
        `decision-evidence-unavailable`, `compare-refusal`, `empty-state` — references
        `--danger`, `--danger-border`, `--danger-surface` or `--danger-ink`;
      - **no selector in any shell sheet matches `error`**, so an `.error-*` rule cannot arrive
        unnoticed;
      - non-emptiness on each file read **and** on the set of rules parsed.
- [ ] **Carve out `.invitation-warning` by name** (`shell-components.css:159`,
      `color: var(--danger)`), with the reason in a comment: a **warning on a destructive action**,
      not a screen state. Without the carve-out the scan reports a non-defect and gets narrowed
      until it proves nothing.
- [ ] Add `test_no_shell_template_gives_a_governed_state_an_error_role`: across **every** template
      in `shell_templates/` and `legal_templates/`, no element carrying a state class also carries
      `role="alert"`. **This is the assertion Task 8's BUILD makes pass** — so it is **genuinely RED
      on arrival**: `role="alert"` ships today at `_decision_cards.html.j2:13` and
      `_decision_sections.html.j2:11`. **Record the failure output.**
- [ ] **Mutate the paint scan:** add `.decision-refusal { color: var(--danger) }` to
      `workspace.css` → must fail. Add `.error-summary { … }` → must fail. Add
      `/* .decision-refusal { color: var(--danger) } */` as a **comment** → must **pass** (the
      comment-stripping proof). Revert each by `git diff`, zero deletions.
- [ ] Commit: `test(u1-05): forbid error paint and an error role on a governed state`

### Task 4 — RED: no loading state can occur — assert the invariant (`FR-202`, the loading half)

**PASSES ON ARRIVAL by absence, and is STRUCTURALLY UNREACHABLE** per finding 1. Driving a loading
state would be a run that can only produce the null case.

- [ ] Add `test_no_shell_surface_carries_a_loading_affordance`, over **every** template in
      `shell_templates/` **and `legal_templates/`** (derived from
      `files("khepri.runtime").joinpath(...).iterdir()`, **not** a hand list), asserting **absence**
      of: a `<script` element, `aria-busy`, `onclick`/`on[a-z]+=` handler attributes, and any class
      matching `spinner|skeleton|loading|progress`. Non-emptiness guard: assert the template set is
      non-empty **and** that each file read is non-empty.
- [ ] **Docstring states the structural reason, not just the fact:** the surfaces are
      server-rendered whole, the shipped `default-src 'none'` CSP forbids the script a client-side
      loading affordance needs, and `FR-206` forbids weakening it. **`FR-202`'s loading state is
      therefore not presented — it cannot occur.** A later slice that ships a spinner naming no
      stage fails here.
- [ ] **Cite `test_r802_shell_unavailable_surface.py:290` for the CSP header** rather than founding
      a second policy assertion — `:281` already asserts the shell policy **is** the journey policy,
      imported rather than restated, and a second copy is a second definition that drifts.
- [ ] **Mutate:** add `<script>/* */</script>` to `overview.html.j2` → must fail. Add
      `aria-busy="true"` to `analyses.html.j2` → must fail. Add a `class="loading-spinner"` element
      to `legal_page.html.j2` → **must fail, and this is the mutant that proves the scan reaches
      `legal_templates/`** — the directory `test_every_shell_template_is_measured` (`:396`) misses.
      Revert each by `git diff`, zero deletions.
- [ ] Commit: `test(u1-05): assert no loading affordance can reach a shell surface`

### Task 5 — RED: the shell sheets declare no motion (`FR-203`)

**PASSES ON ARRIVAL**, and the allocation plan's premise for this task is **FALSE** — see finding 4.
**No `prefers-reduced-motion` block is added**: over zero motion declarations it would be dead CSS
gating nothing.

- [ ] Add `test_the_shell_stylesheets_declare_no_motion`. Read all three sheets via
      `importlib.resources`, **strip comments with the shared `_without_comments()`**, and assert
      **zero** declarations of: `transition`, `transition-*`, `animation`, `animation-*`,
      `@keyframes`, `transform`, `will-change`, `scroll-behavior`.
- [ ] **The pattern must satisfy all three requirements of finding 4:**
      1. comments stripped first, or `workspace.css:301` and `:369` are false positives;
      2. **not** anchored to line start — `journey.css:153` proves the packed single-line idiom
         exists here, and `.x { transition: all 1s }` must be caught;
      3. **property-then-colon inside a declaration block**, not the bare word, or
         `.change-transition {` (`:306`) fires on its own selector.

      **Requirements 2 and 3 are in tension as worded, so the pattern is given concretely.** Anchor
      on the **declaration boundary** rather than the line start:

      (?:[{;]\s*)(transition|animation|transform|will-change|scroll-behavior)[-a-z]*\s*:

      A declaration follows either `{` or `;`, which occurs mid-line in a packed one-liner — so this
      matches `.x { transition: all 1s }` (requirement 2) and cannot match `.change-transition {`,
      where the word is followed by `{` rather than preceded by one (requirement 3).
- [ ] **`@keyframes` needs a SECOND pattern — the declaration pattern cannot see it.** An at-rule
      carries no property-colon, so `@keyframes pulse { … }` escapes the pattern above entirely.
      Add `re.compile(r"@keyframes\b")` as a separate check, or Task 5's mutant 3 passes and the
      scan proves less than it claims.

      **The scan logic is pre-validated** — run against the tree at `b26de23` before this plan was
      committed, so execution does not discover a broken approach at RED:

      | Case | Result |
      |---|---|
      | `workspace.css`, `shell-components.css`, `shell.css`, comments stripped | **CLEAN** (zero matches — finding 4 confirmed) |
      | `transition: opacity .2s` on its own line | caught |
      | packed `.decision-drawer { transition: all 1s }` | caught (requirement 2 holds) |
      | `animation: pulse 1s infinite` | caught |
      | `.change-transition { display: inline-flex }` — selector only | **no match** (requirement 3 holds) |
      | `/* transition: opacity 0.2s */` | **no match** (requirement 1 holds) |
      | `transform: translateX(2px)` | caught |
      | **bare `@keyframes pulse { … }`** | **NO MATCH — this is why the second pattern is required** |

      The last row is the load-bearing one: it is a real gap in the obvious pattern, found by running
      it rather than by reading it.
- [ ] Non-emptiness assertions: each file read is non-empty **and** the set of declarations parsed
      is non-empty, so a broken parser cannot pass by finding nothing anywhere.
- [ ] Docstring records: **this invariant is a superset of `FR-203`'s enumerated prohibitions**
      (bounce, elastic `cubic-bezier` outside `[0,1]`, parallax, infinite
      `animation-iteration-count`, counting numbers). A sheet with no motion satisfies every one,
      and the superset cannot be slipped past by a "tasteful" transition the enumeration misses.
      It also records that **no `prefers-reduced-motion` block exists or is needed on the shell**,
      unlike `journey.css:206` and `landing.css:232`, whose sheets **have** motion — and that
      `FR-203`'s short positional drawer transition is vacuous here (`<details>`, no transition) and
      is slice 8's to measure if one ever ships.
- [ ] **Mutate four ways, separately:**
      1. `transition: opacity 0.2s` on its own line → must fail;
      2. **packed single-line** `.decision-drawer { transition: all 1s }` → must fail (proves
         requirement 2);
      3. `@keyframes pulse { … }` → must fail;
      4. `/* transition: opacity 0.2s */` as a **comment** → must **pass** (proves requirement 1).
      Revert each by `git diff`, zero deletions.
- [ ] Commit: `test(u1-05): assert the shell sheets declare no motion`

### Task 6 — RED: the §F state contracts, per surface, with reachability recorded

**The allocation plan dissolves slice 7 into slices 4, 5 and 8 and states that "it rides whichever
slice touches the surface" is NOT a discharge.** So slice 5 asserts the §F state rows for the
surfaces it touches, and records "already met" where it is.

- [ ] Create **`tests/test_r809_shell_state_contracts.py`** — a second module, per the CodeScene
      note above; Task 6's tests do **not** go in `r808`.
- [ ] Build the **reachability table** in that module as a parametrized mapping, and record it in
      the evidence. Established at `b26de23`:

      | Surface | Refusal | Empty | Unavailable | Notes |
      |---|---|---|---|---|
      | `decision` | `.decision-refusal` | `.decision-empty` (both paths) | `.decision-unavailable` | **The only surface reaching all three** — the four-state test's subject |
      | `compare` | `.compare-refusal` (`compare.html.j2:34`) | — | — | §F.11: `KIND_REFUSED` / `KIND_UNAVAILABLE` distinct (`comparison_assembly.py:120,187`) |
      | `overview` | — | `.empty-state` ×4 (`:27,54,95,109`) | — | §F.7: "one instruction and one action, **not an illustration**" |
      | `data` | — | `.empty-state` ×2 (`:41,47`) | — | §F.8 |
      | `analyses` | — | `.empty-state` (`:85`) | — | §F.9 |
      | `analysis` | — | `.empty-state` ×2 (`:149,177`) | — | §F.10 |
      | `unavailable`, `no_membership` | — | — | the surface **is** the state | §F.15: one sentence, one exit |
      | `team`, `switcher`, `invitation_issued` | — | — | — | No state region |
      | `legal.html.j2`, `legal_page.html.j2` | — | — | — | **NOT APPLICABLE**: static legal text, no read, no state region. **Recorded, not omitted** — §Scope admits the directory, and an omission reads as a blind spot |

- [ ] **A surface that cannot reach a state is NOT EXERCISED, not PASS.** Parametrize from
      `SHELL_SURFACES` (`test_r807_shell_quality.py:64`) and assert, per surface, **only the states
      the table says are reachable** — plus that a surface reaching **none** carries none of the
      state classes, which is what stops a later slice dropping an `.empty-state` onto a surface
      whose read cannot be empty.
- [ ] Add `test_every_shell_empty_state_offers_one_action_and_no_illustration` (§F.7): an
      `.empty-state` region carries governed prose and **no** `<img>`, `<svg>` or artwork-drawing
      rule — which **`FR-206`'s slice-2b instrument already covers for the stylesheet**
      (`test_r807_shell_quality.py:651`), so **cite it** and assert only the **template** half here.
- [ ] Add `test_every_state_bearing_surface_carries_an_exit` (§Higher-order invariants: "No surface
      traps a reader: every page, refusal surfaces included, carries at least one exit"). **This is
      genuinely new** — `FR-050`'s exit on `unavailable.html.j2:24` is pinned, but nothing asserts
      the property across surfaces.
- [ ] **Scope it to where it is non-trivial, or it passes on chrome.** Every surface extending
      `shell.html.j2` carries navigation anchors, so "renders at least one `<a href>`" would be
      satisfied by the frame and would prove nothing about the state. Assert it **only** on the
      three surfaces whose frame drops or narrows the navigation: **`unavailable`**,
      **`no_membership`**, and a **refused `decision`** — and on those, assert an anchor **in the
      state region's own document-card**, not anywhere on the page.
- [ ] **Mutate once per surface, three mutants** — a single mutant leaves the other two unproven:
      delete the exit anchor from `unavailable.html.j2:24` → must fail; delete it from
      `no_membership.html.j2` → must fail; remove the refused decision surface's exit → must fail.
- [ ] **Mutate the reachability assertion:** add `<p class="empty-state">` to `team.html.j2` → must
      fail (a state class on a surface whose read cannot be empty). Revert by `git diff`, zero
      deletions.
- [ ] Commit: `test(u1-05): assert the §F state contracts per shell surface`

### Task 7 — GREEN (a): correct the stale prose in `workspace.css`

- [ ] `workspace.css:385-387`'s comment asserts a **refusal treatment that does not exist** — "the
      muted treatment the other stated findings carry, **never the refusal's**". Per finding 2, no
      shell sheet paints a refusal at all.
- [ ] Rewrite the comment to state what ships: an absence is muted; **a refusal carries no paint in
      any shell sheet**, which is how `FR-202`'s "never carries error paint" holds — by absence, and
      guarded forward by `test_no_shell_state_rule_carries_error_paint`. Cite that test by name, so
      a reader who wonders whether the absence is deliberate finds the instrument.
- [ ] **Comment only.** No rule added, changed or removed; `git diff --stat` shows `workspace.css`
      with **no declaration change**. `shell.css` untouched — its tokens-only test must still pass.
- [ ] Run Tasks 1, 3 and 5: all must still pass.
- [ ] Commit: `docs(u1-05): correct the refusal-treatment comment to what ships`

### Task 8 — GREEN (b): the refusal is a polite live region, not an alert

The slice's **one behavioural change**, authorized by finding 5: ARIA state is explicitly in
`RCA-010` §Scope, and **no test pins the shell's current `role="alert"`**.

- [ ] Change `role="alert"` → `role="status"` on **all three** refusal elements the inventory in
      finding 5 enumerates — `_decision_cards.html.j2:13`, `_decision_sections.html.j2:11`
      (`.decision-refusal`) **and `decision.html.j2:30` (`.decision-unsupported`)**. The third is
      the one a keyword grep misses, and **Task 3's cross-template scan fails if it is left behind.**
- [ ] Put the reason in the adjacent Jinja comment on each: **§13 classes an analytical refusal as
      "Governed, not error"**; `role="alert"` is an assertive live region and is the journey's
      **transport-error** role (`test_rra_journey_accessibility.py:64`), while the journey's refusal
      is `role="status"` (`:67`, and master specification §F.3 records the assertion by name).
      `.decision-unsupported` is a refusal by its own comment's words — `FR-137`/`FR-164`, "a
      parameter no published view admits is **refused**, not dropped".
- [ ] **Do not touch any `role="note"`** — `FR-165`'s content-free unavailable, the two empty
      regions, the evidence lines, `.decision-no-sources` and `.change-notice` are correctly notes,
      and changing one is a change this slice's authority does not cover.
- [ ] **`compare.html.j2:34`'s `.compare-refusal` carries no role at all.** Add `role="status"` for
      the same reason, so the four refusal idioms carry one grammar. **No new class, no new word** —
      every element and its governed text are unchanged.
- [ ] Re-run `grep -rn 'role=' src/khepri/runtime/shell_templates/ src/khepri/runtime/legal_templates/`
      after the edit and confirm **zero** `role="alert"` remain.
- [ ] Task 3's `test_no_shell_template_gives_a_governed_state_an_error_role` must now **pass**; it
      was the one genuinely-RED-on-arrival assertion.
- [ ] **This adds no state, no cause and no governed word** — it changes one ARIA attribute on three
      existing elements. Confirm `shell_copy.py` is **unchanged** (`git diff --stat`).
- [ ] Run every earlier task's tests. **Run `test_d105_decision_sections.py` and
      `test_d105_evidence_drawer.py` unchanged** — an `RCA-008` test must not break, and if one does,
      invoke `superpowers:systematic-debugging` before proposing a fix.
- [ ] Commit: `feat(u1-05): make a governed refusal a polite live region`

### Task 9 — Verify the whole suite, then mutate

**Order is load-bearing: RED → commit → GREEN → COMMIT → mutate → revert.** On slice 6 a
`git checkout --` during mutation testing, taken across **uncommitted** implementation, destroyed
three files' work while `git status` showed clean. **Never mutate across uncommitted implementation.**

- [ ] `PYTHONPATH=$PWD/src ./.venv/Scripts/python.exe -m pytest tests/test_r808_shell_state_grammar.py tests/test_r809_shell_state_contracts.py tests/test_r807_shell_quality.py tests/test_r801_shell_tokens.py -q`
      — expect **one `xfailed`** from Task 2's strict-xfail cards-path test, not a pass.
- [ ] `PYTHONPATH=$PWD/src ./.venv/Scripts/python.exe -m pytest tests/test_d105_decision_sections.py tests/test_d105_evidence_drawer.py tests/test_d103_metric_card.py tests/test_d104_breakdowns_and_limits.py tests/test_d108_print.py -q`
      — the `RCA-008` suites the ARIA change touches, **including print**: the partials are shared
      by `decision_print.html.j2` (`FR-159`), so a role change reaches paper too.
- [ ] `PYTHONPATH=$PWD/src ./.venv/Scripts/python.exe -m pytest -q` — **the full suite.** Changing a
      shared partial breaks suites nobody opened; a targeted run cannot see it. Expect ~5596 passed
      as the `b26de23` baseline, plus this slice's tests. **If a count drops, check the branch
      before re-creating anything.**
- [ ] **Isolate `--basetemp`** if another pytest run may be live in this tree — two concurrent runs
      give phantom `WinError 32` teardown ERRORs.
- [ ] **Only now** run every mutation from Tasks 1–6. Revert each by `git diff` showing **ZERO
      deletions**; `git status --short src/` empty after each. Where a mutant must live outside this
      slice's scope, use a `git worktree` **with `PYTHONPATH` set to that worktree's `src`**.
- [ ] `uv run khepri-gov validate`; `uv run ruff check .` — **never `ruff format`**, there is no CI
      format gate; `git diff --check`.
- [ ] Note: **ruff counts characters, not bytes** — `awk`/`wc` over-report E501 on lines containing
      `§`. Reproduce any E501 with `ruff check .`, never with a shell line-length proxy.
- [ ] Write `docs/superpowers/plans/2026-09-18-u1-slice-5-evidence.md`: per-mutant results, **full
      stdout including failures** (not a summary), the reachability table as run, the falsified
      allocation-plan motion claim, and the deferrals with their owners.

### Task 10 — Pre-flight and one PR

- [ ] `git fetch origin --prune` **first**, then CodeScene `analyze_change_set` against
      `origin/main`. A stale `origin/main` returns empty results and a meaningless pass.
- [ ] The new test module must score **10.00**. Read any finding via
      `gh api .../check-runs` — it names the file, rule, score and method. **Guessing cost a cycle
      and made the code worse** on a prior slice.
- [ ] **Self-mutate every guard before requesting review.** Gaps found locally cost minutes; gaps
      that reach CI cost a full cycle each.
- [ ] **One PR**: the plan+RED commits then the implementation commits. Branch off `main`,
      **never stacked**.
- [ ] **Batch every review fix into one push per round.** Five mid-flight pushes on slice 2b reset a
      ten-minute pipeline five times. Same-PR fix rounds are for **critical gaps only**; batch the
      rest into a deferred issue.
- [ ] State in the PR body: that **`FR-202` was found already satisfied and the work was pinning
      it**; that the allocation plan's "three `transition`/`animation` declarations in
      `workspace.css`" is **false** (zero, at `b26de23` **and** at `e915af8`) and **no
      reduced-motion block was added because it would gate nothing**; that the **cards-path
      `FR-163` defect is real and outside `RCA-010` §Scope**, pinned negatively and deferred to an
      `RCA-008` slice; that the one behavioural change is `role="alert"` → `role="status"` on three
      refusal elements; and that **no Python source file and no `shell_copy.py` entry changed**.
- [ ] **Do not merge.** The merge to `main` is the owner's. Technical checks report consistency; they
      do not grant approval, and automation never authors the owner's approval.
- [ ] Append the non-trivial lessons to `~/.claude/global-lessons.md` — in particular the
      stray-worktree `PYTHONPATH` requirement re-confirmed at `b26de23`.

---

## Deferred, each with its owner named

| Item | Why | Owner |
|---|---|---|
| **The cards-path `FR-163` collapse** — `_DecisionView.empty` is a `bool` (`shell_decisions.py:494`) and `_decision_cards.html.j2:26` renders the fixed `decision.no_rows`, while `ExecutiveOverviewView.empty_rule` is `EMPTY_STATED_ABSENCE` (`seam.py:86`), so the surface states the **wrong rule's sentence** | The fix needs `shell_decisions.py`, a `src/khepri/runtime/*.py` module **explicitly outside `RCA-010` §Scope**; a second sentence in `shell_copy.py` is barred twice (chrome labels only; adds no governed word) | **An `RCA-008` slice** — `RCA-008` owns `FR-163` **and** the module carrying the defect. Asserted negatively in Task 2 with the successor named in the docstring |
| **A `prefers-reduced-motion` block on the shell sheets** | **Not deferred — REFUSED as unnecessary.** Zero motion declarations exist (finding 4), so the block would be dead CSS gating nothing, and the allocation plan's premise for requiring it is false | Nobody. If a later slice adds motion, it adds the block **with** it, and Task 5's invariant fails until it does |
| **A `loading` state presentation** | **STRUCTURALLY UNREACHABLE.** No script, no `aria-busy`, no client-side affordance; `default-src 'none'` forbids one and `FR-206` forbids weakening the CSP. The invariant is asserted instead (Task 4) | Nobody at the shell. A future surface needing one needs a CSP decision first, which is `RCA-002`/`RCA-010` §Assets territory and an owner decision |
| **An `error` state presentation** | **No error surface exists on the shell.** §13's Danger rows — processing failure, export failure — have no shell destination, and inventing one would add a state and a cause, which this slice's boundary forbids | A slice implementing a shell export or processing surface, which needs a route and is barred by `FR-193` |
| **`FR-199` should perhaps be corrected in place** (its "no physical directional property" premise is false of `workspace.css`) | Recorded by the allocation plan; **not a task in any slice** | **The owner's call** |
| **Reducing `test_r807_shell_quality.py` below the 600-line gate** (788 at `b26de23`) | Moving tests out is a diff a reviewer must re-verify for no functional gain, and the module stays over the gate either way | A dedicated test-module split, owner-visible. **Slice 5 adds a new module rather than making the overage worse** |

**Each is a deferral with a named owner, not a silent narrowing** — and the two presentable ones are
**asserted negatively** (no loading affordance, no error role, no error paint), so a later slice
cannot quietly ship what this one declined to invent.

## What this slice does not do

- **Adds no state, no cause, no governed word, no route, no address, no capability, no
  authorization path, no product destination** (`FR-193`, §19's boundary for this slice).
- **Adds no filter**, sends no parameter a view's allowlist does not name, and retains **no** filter,
  layout, sort, dismissal or preference state (`FR-197`).
- **Adds no telemetry event, audit record, counter, access record, content-bearing log, or retained
  presentation state.** `KHEPRI-DEC-015` §3 stands unamended; `D1-11` stays unauthorized.
- **Changes no Python source file.** Not `shell_api.py`, not `shell_decisions.py`, not
  `shell_controls.py`, not `shell_copy.py`, not anything under `src/khepri/rca/` or
  `src/khepri/rra/`. `SURFACE_VIEWS` and `EMPTY_RULES` are **read** by tests only.
- **Adds no CSS rule.** `workspace.css` changes one comment; `shell-components.css` and `shell.css`
  are untouched, and `shell.css` stays tokens-only.
- **Adds no `prefers-reduced-motion` block**, for the reason in finding 4.
- **Does not touch `journey.css`, `landing.css`, the `/beta` surfaces, the report stylesheets, or
  any chart** — `RRA-010`'s, `LAND1`'s and `RRA-015`'s respectively.
- **Introduces no shared token layer across families** (`FR-201`) — the `RRA-012` question "needs
  its own artifact naming both families' paths", and neither this plan nor its allocation plan is
  that artifact.
- **Does not weaken, move or delete any test under another specification's Verification** — the
  `test_d105_*` modules are `RCA-008`'s and are cited, never edited.
- **Does not act as though the `/beta` journey-adoption reading were decided** — it remains an
  **OWNER DECISION, not yet taken**, and bears on the `/beta` surface alone.
- **Does not measure the drawer's full-screen-sheet behaviour, RTL mirroring, or responsive
  overflow** — those are **slice 8**'s, and slice 5 asserting them would duplicate its instruments.
- **Does not add accessibility or visual-regression evidence** — **slices 9b and 10b**'s, and
  `FR-204`'s reference pack is gated on §16 assets that are absent.

## Execution discipline

- **One PR for this slice**: plan+RED commits, then the implementation commits. **Branch off `main`,
  never stacked** — a PR based on another branch is auto-CLOSED when that base is deleted.
- **Every test command carries `PYTHONPATH=$PWD/src`** and runs `./.venv/Scripts/python.exe`. A
  stray worktree shadows this repo's `khepri` package; verify the import path before believing a
  result.
- **Do not run `ruff format`** — there is no CI format gate. `ruff check .` is the gate that exists.
- **Commit GREEN before mutating.** A `git checkout --` of a dirty file destroys uncommitted work,
  and `git status` shows clean afterwards.
- **Restore every mutant by `git diff`, never by `str.replace`** — require the diff to show **ZERO**
  deletions, and `git status --short src/` empty after each.
- **On any test or CI failure, invoke `superpowers:systematic-debugging` before proposing a fix.**
- **Run the full suite before believing a targeted one.** A shared partial changes surfaces no
  targeted run opens.
- **Check the branch before blaming the code.** Status disagreeing with grep has two causes needing
  opposite responses — a destructive revert and a branch switch — and both present identically.
  `git branch --show-current` settles it in one command.
- **Outdated review threads block merge.** `main` requires conversation resolution; a stale
  CodeScene thread keeps a PR BLOCKED with every check green, and never self-resolves.
- **The merge to `main` is the owner's.** Never author the owner's approval.
