# `U1` — The bounded allocation plan for the `RRA` report and journey surfaces

> **For agentic workers:** this is an **allocation** plan, the `G3-04`/`SV1`/`D1-02`–`D1-10` tier.
> It allocates two specifications' requirements to five slices and **writes no code**. Each slice
> below opens its own **execution** plan at build time — the `W1-09` tier, with `- [ ]` RED/GREEN/
> commit steps and literal test code — created with `superpowers:writing-plans` when that slice
> starts. REQUIRED SUB-SKILL at execution: `superpowers:test-driven-development`, then
> `superpowers:executing-plans`.
>
> **Companion plan:** the shell half is
> `docs/superpowers/plans/2026-09-17-u1-shell-allocation-plan.md`. The two are separate documents
> because `governance/templates/specification.md` admits exactly one family per specification and
> `khepri_gov`'s `_validate_family_links` enforces it; `RRA-012` §Outcome reads that rule as
> forbidding one artifact across two families' surfaces. **Neither plan may cite the other's
> authority for a file.**

**Goal:** Give the `RRA` report and evidence surfaces the approved chart grammar, one skip-link
mechanism on the journey, a type scale with no raw literals, and accessibility and visual evidence
that measures those surfaces as tests rather than as aspirations.

**Architecture:** Presentation only, over surfaces and figures that already exist. `charts.py`
returns geometry and never markup; `_chart.svg.j2` renders that geometry; `report.css` and
`report.print.css` carry the chart's screen and print rules beside the component layer's;
`html.py` binds the chart view and registers chart chrome; `wording.py` adds chart chrome codes
beside the existing tables. No calculation, no route, no capability, no persistence.

**Tech Stack:** Python 3.13, frozen dataclasses, `Decimal` throughout `charts.py`, Jinja2, pytest,
and the Playwright/Chromium the repository already ships (`pyproject.toml:31`, `playwright>=1.61,<2`).
No new dependency, no visual-testing platform, no hosted baseline store.

**Authority:**
- active `RRA-015` (`FR-181`–`FR-192`), merged 2026-09-17 at `e915af8` (`#477`) — slices 6, 9a, 10a.
- active `RRA-010` (§73, "one skip-link mechanism") — slices 2 and 3.

**Design source:** `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md` §8 (chart grammar), §11
(accessibility), §17 (visual acceptance), §G.1 (type scale), §G.2 (components), §19 (slicing).
Roadmap: `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` §PROGRAM U1, row `READY_FOR_PLAN`.

---

## Global Constraints

Every slice's requirements implicitly include this section. Values are copied verbatim from the
governing artifacts; where this plan and a specification disagree, **the specification wins** and
this plan is corrected in place.

- **A chart computes no figure** (`FR-182`). It "resolves the values it is given into geometry and
  applies no sum, average, difference, rank, score, normalization, threshold, percentage,
  interpolation, re-rounding, or reformatting. A chart-derived fact is a defect against this
  requirement whatever its size, and the table beside the chart remains the authoritative
  presentation."
- **Only the shipped kinds** (`FR-181`): `CHART_BAR`, `CHART_GROUPED_BAR`, `CHART_LINE`. Confirmed
  present at `src/khepri/rra/rendering/charts.py:63-65` and dispatched at `:399-401`. "No slice
  under this specification admits a new chart kind."
- **Every customer-visible word is a governed code** (`FR-184`), resolved in `wording.py` in both
  languages under the same import-time completeness assertion the surrounding tables use. "A chart
  composes no sentence."
- **Images are evidence, not truth** (`FR-191`). "No baseline, screenshot, or reference image is
  read as a source of a figure, a route, a capability, a refusal reason, or a governed word, and no
  slice copies a value out of one. Where an image and an active specification disagree, the
  specification wins."
- **The §7 asset policy is binding and unrelaxed** (`FR-192`). No CSS-drawn illustration, div-art,
  CSS pyramid, CSS scarab, pseudo-element used as artwork, emoji icon, Unicode glyph standing in
  for an icon, or one-off inline SVG illustration. No external font, image, style, script, or CDN
  dependency — the shipped `default-src 'none'` CSP forbids it in any case. **Data-driven charts
  are the one expected programmatic drawing**, and that exception reaches charts and nothing else.
- **No shared token layer across families** (`RCA-010` `FR-201`, binding on this plan as a
  boundary). The journey's scale and the shell's scale stay separate — see the tree-state finding
  below. Answering the shared-token question "needs its own artifact naming both families' paths",
  and neither this plan nor its companion is that artifact.
- **Logical CSS properties only** (`FR-188`). "A physical directional property introduced on a
  chart rule is outside this specification."
- **No `|safe`, no `Markup`** in `_chart.svg.j2`, per `RRA-015` §Scope.

### Scope ceiling — the exact authorized paths

`RRA-015` §Scope admits these and no others:

| Path | Reach |
|---|---|
| `src/khepri/rra/rendering/charts.py` | chart geometry and presentation grammar; whole module |
| `src/khepri/rra/rendering/templates/_chart.svg.j2` | the chart macro's markup; whole file |
| `src/khepri/rra/rendering/templates/report.css` | **chart presentation rules only** |
| `src/khepri/rra/rendering/templates/report.print.css` | **the chart's print behaviour only** |
| `src/khepri/rra/rendering/html.py` | **the chart view's construction, its context binding, and the chart chrome table's registration point — nothing else** |
| `src/khepri/rra/rendering/wording.py` | **chart chrome codes only** |
| `tests/` | focused chart-grammar, chart-accessibility and report-surface visual evidence |

**Explicitly outside:** the fact families (`RRA-004`, `RRA-008`), the bundle and its render targets
(`RRA-006`), the narrative and refusal vocabulary (`RRA-009`), the catalog (`RRA-011`), the
data-display component layer (`RRA-012`), the Excel renderer, the PDF renderer beyond the chart
rules, the commercial shell and its stylesheets/templates/routes/assets, and every route,
orchestration, persistence and composition path in the repository.

`html.py`'s other behaviours stay with their owners: report copy is `RRA-009`'s, colophon wording
`RRA-010`'s, `FR-095a` component chrome `RRA-012`'s, and figure construction, cell building and
audit projection are unchanged.

### Tree-state findings — verified 2026-09-17 at `e915af8`

Recorded because a later slice must not re-derive them, and because one corrects a count.

1. **The journey and the shell carry separate type scales.** `journey.css:59-62` declares
   `--journey-text-xs/-sm/-display/-lede`; `shell.css:109-128` declares `--text-xs` … `--text-display`.
   These are different token sets on different surfaces. `FR-201` keeps them separate, so **slice 3
   and the companion plan's slice 2b resolve to different scales and must not be merged.**
2. **`.skip-link` is genuinely duplicated**, and the duplication is cross-family:
   `journey.css:75-76` and `shell-components.css:45,56`. Slice 2 takes the journey half under
   `RRA-010` §73. **Unifying *across* the two surfaces stays out of scope** — `FR-201` keeps each
   surface's values its own, and `RRA-010:30` puts `shell-components.css` outside `RRA-010`.
3. **§19 slice 3's count of four raw journey font sizes is correct.** Verified at
   `journey.css:82` (`.75rem`), `:115` (`.86rem`), `:165` (`.78rem`), `:171` (`.76rem`). Lines
   96, 98, 106, 182, 189 and 198 already use `var(--journey-text-*)` and are **not** in scope;
   `:191`'s `clamp(1.75rem, 8vw, 2.15rem)` is a responsive expression, not a raw literal, and a
   slice that flattens it would change behaviour rather than tokenize it. An execution plan must
   re-verify these four line numbers against the tree on the day it runs.
4. **`charts.py` already ships the disciplines `RRA-015` §Scope says are preserved, not reopened.**
   `build_chart` at `:197`; `mirrored` plot flag at `:190`, `:213`, `:264`, `:287`, `:367`; the
   kind dispatch table at `:399-401`; `Decimal` canvas constants at `:78-79`. The `mirrored` flag
   is the existing seam `FR-188` names for Arabic, so slice 6 extends it rather than inventing one.

---

## Slice sequence

Evidence runs **after** the build slices in this family, so accessibility and visual assertions
measure finished surfaces rather than moving ones.

```
6 (charts, U1-03)  →  2 (journey skip-link)  →  3 (journey type scale)  →  9a (a11y)  →  10a (visual)
```

Slices 2 and 3 are independent of slice 6 and of each other; they are sequenced after it because
slice 6 is the roadmap-designated next actionable task for `U1`, not because they depend on it. An
execution plan may take 2 or 3 first if the owner prefers a smaller opening slice.

---

### Slice 6 — Chart grammar (`U1-03`)

**Authority:** `RRA-015` `FR-181`–`FR-188`, plus `FR-189`'s chart clause for `role`/`<title>`/`<desc>`.
**Design:** master specification §8 (§8.1 form selection, §8.2 semantics, §8.3 chrome, §8.4 numbers
and Arabic layout, §8.5 the hard rule).
**Depends on:** nothing. This is the entry point.

**Files:** all seven §Scope paths. `charts.py` and `_chart.svg.j2` in full; `report.css` and
`report.print.css` at the chart rules only; `html.py` at the chart view's construction, its context
binding, and `_CHROME` registration only; `wording.py` at chart chrome codes only; `tests/`.

**Tests:** extend `tests/test_rra006_charts.py`; add focused modules beside it.

**RED shapes — each must fail before its implementation exists:**

- A chart kind outside `{CHART_BAR, CHART_GROUPED_BAR, CHART_LINE}` is refused rather than rendered
  (`FR-181`). Name a sentinel kind the dispatch table cannot serve, not the next plausible real one.
- A static check over the authorized paths asserts no sum, difference, ratio, ranking or percentage
  is derived in `charts.py` or `_chart.svg.j2` (`FR-182`, §Verification). **Anchor the scan to
  `__file__`, not to a CWD-relative `Path("src")`**, and assert the scan is non-empty so it cannot
  pass vacuously.
- A figure whose precision differs from any default survives unchanged through `build_chart`
  (`FR-182`, §Verification) — the value-preservation test, distinct from the static scan.
- An axis carries its unit and its period; a legend renders only with two or more series; a
  negative value hangs below a visible zero baseline; **a truncated axis on a comparison is
  refused** (`FR-183`).
- No tooltip or hover state is the sole carrier of a value (`FR-183`).
- Every chart word resolves from a governed code present in both languages, under the import-time
  completeness assertion; **an unknown code fails closed** rather than rendering the code string,
  an empty element, or a blank (`FR-184`, §Verification).
- A chart chrome label never describes a metric, refusal, caveat, population or version — where it
  would, the word is `RRA-009`'s or `RRA-011`'s and `RRA-012` `FR-095` governs it (`FR-184`).
- Missing data renders a visible gap carrying its stated reason: never interpolated, never drawn as
  zero, never silently dropped (`FR-185`). Incomplete data renders with its caveat adjacent.
- A refused figure renders the governed refusal presentation, not an empty chart; a zero
  denominator is that refusal rather than `0%` or `NaN` (`FR-186`).
- A refusal and an error never share an element or a class, and a refusal never carries error paint
  (`FR-186`). Assert the **effect** on the code path, not merely that an exception type is raised.
- Every chart carries an evidence entry point reached from the chart itself, not from a global
  destination (`FR-187`).
- In Arabic the category axis runs right to left through the existing `mirrored` flag; numbers use
  Arabic-Indic digits, Arabic month names and the Arabic percent mark; every label, axis, legend,
  caveat and refusal present in one language is present in the other (`FR-188`).
- A chart rule introduces no physical directional property (`FR-188`) — a scan over the chart rules
  in `report.css`/`report.print.css`, with an emptiness assertion.
- `_chart.svg.j2` adds no `|safe` and no `Markup` (§Scope).
- A chart exposes `role="img"` with `<title>` and `<desc>` from governed codes (`FR-189`).

**Extent assertion required, and its source must be independent.** A per-kind or per-field test
leaves the next one open, so the admitted chart-kind set and the chart chrome code set each need an
extent assertion: **equality plus non-empty**, never `>=`. A membership table without one cannot
see a row added.

**But deriving both sides from one source is a tautology** — it passes every mutant, because adding
an entry updates the expectation and the subject together. Each extent assertion names a source
the slice under this plan **cannot edit**:

| Extent assertion | Subject (under test, editable here) | Independent expectation (not editable here) |
|---|---|---|
| Chart kinds | the dispatch table in `charts.py:399-401` | **`GOVERNED_CHART_KINDS`**, a `frozenset` at `src/khepri/rra/bundle.py:383`. `bundle.py` is `RRA-006`'s and is **outside `RRA-015` §Scope**, so no slice here can widen it to match a mistake. `FR-181` names the three kinds in governance prose as a third, human-reviewed check |
| Chart chrome codes | the new chart entries in `wording.py` | the `_CHROME` registration in `html.py` **plus** the import-time completeness assertion across both languages — a code present in one and absent from the other fails, so the two tables check each other |
| Report surface list (slice 9a) | the surfaces the tests drive | the section-to-chart mapping already in `bundle.py:400-404` and the bundle's own render targets, both `RRA-006`'s |

Where no independent source exists for a set a slice introduces, the execution plan **says so** and
the reviewer supplies the expectation by hand rather than a test deriving it from the code it
measures. A hand-reviewed literal is weaker evidence than an independent registry and stronger
evidence than a tautology.

---

### Slice 2 — One skip-link mechanism on the journey

**Authority:** `RRA-010` §73 — "one skip-link mechanism, correct tab order, and visible focus".
**Design:** master specification §G.2.
**Depends on:** nothing.

**Files:** `src/khepri/rra/journey/assets/journey.css` (the `.skip-link` rules at `:75-76`).

**Scope boundary, stated because it is easy to cross:** this slice unifies the **journey** half
only. `shell-components.css:45,56` is outside `RRA-010` by `RRA-010:30` and belongs to the
companion plan's slice 2b. **Unifying across both surfaces is authorized by neither plan**
(`FR-201`).

**RED shapes:**
- The journey's skip link is first in the document and reachable by keyboard before any other tab
  stop.
- It is visible on focus and not merely present in the DOM.
- Exactly one skip-link mechanism exists on a journey page — assert the count, so a second
  definition added later fails.
- `journey.css` still declares no physical directional property after the change.

---

### Slice 3 — Collapse the four raw journey font sizes onto the type scale

**Authority:** `RRA-010`.
**Design:** master specification §G.1.
**Depends on:** nothing.

**Files:** `src/khepri/rra/journey/assets/journey.css` at `:82`, `:115`, `:165`, `:171`.

**Targets, verified above:** `.75rem` → the nearest journey token; `.86rem`, `.78rem`, `.76rem` →
`--journey-text-sm` (`0.82rem`) or `--journey-text-xs` (`0.7rem`) per §G.1's scale. The execution
plan states the chosen mapping per line and its computed pixel delta at a 16px root, following the
precedent already set in `journey.css:102`'s own comment and `shell.css:107-108`.

**Out of scope:** `:191`'s `clamp(1.75rem, 8vw, 2.15rem)` — a responsive expression, not a raw
literal. `:96`, `:98`, `:106`, `:182`, `:189`, `:198` already use tokens. The two raw sizes in
`shell-components.css:135,141` are the companion plan's.

**RED shapes:**
- No `font-size` declaration in `journey.css` carries a raw numeric literal — a scan with an
  emptiness assertion, so it cannot pass by scanning nothing.
- Computed type size is unchanged beyond the stated per-line delta, asserted in a real browser at
  the supported viewports rather than by reading the stylesheet.
- §G.1's computed contrast is re-measured, per master specification §22 — "the 0.22 margin has no
  room."

---

### Slice 9a — Accessibility evidence, `RRA` report and evidence surfaces (`U1-06`, this family's half)

**Authority:** `RRA-015` `FR-189`.
**Design:** master specification §11.
**Depends on:** slices 6, 2, 3 — this measures those surfaces once they are finished.

**Files:** `tests/` only. **This slice changes no source file**; where a floor fails, the fix lands
in the slice that owns that file, not here.

**Where a floor fails after its build slice has merged.** Slices 6, 2 and 3 close before this one
runs, so there may be no open slice to take the fix. **A floor failure discovered here opens a
follow-on slice under `RRA-015`** — or under `RRA-010` where the failing file is the journey's —
named for the file that fails, and does **not** widen this slice past `tests/`. An evidence slice
that edits a stylesheet or a template to make its own assertion pass has left its scope, and the
failure it hid is still in the product.

**RED shapes — asserted per surface, in both languages** (`FR-189`):
- A visible focus on every tab stop.
- Focus order follows document order, with **no positive `tabindex`**.
- Exactly one `h1`, with no skipped heading level.
- Labels associated with controls.
- `role="status"` for refusals and progress.
- Non-colour differentiation for every trust state.
- Targets of at least 44px **on the element a pointer lands on** — not on an ancestor.
- Text scales to 200% without loss of content or function.
- `lang` and `dir` are **server-computed**, never inferred in a template.
- A chart exposes `role="img"` with `<title>` and `<desc>` from governed codes.

**Extent assertion required, from an independent source.** Assert **equality plus non-empty** over
the report and evidence surfaces, so one added later cannot ship unmeasured — a subset assertion
hides a forgotten entry. **Do not derive the expectation from the list the tests themselves drive**;
that is the tautology slice 6's extent table rules out. Take the expectation from the bundle's own
render targets and the section-to-chart mapping in `src/khepri/rra/bundle.py:400-404` — `RRA-006`'s
file, outside `RRA-015` §Scope and so not editable by any slice here.

---

### Slice 10a — Visual regression, `RRA` report and evidence surfaces (`U1-07`, this family's half)

**Authority:** `RRA-015` `FR-190`–`FR-191`.
**Design:** master specification §17, §16.3, §16.4.
**Depends on:** slices 6, 2, 3, and 9a.

**Files:** `tests/` only.

**Bounded extent, and why this is a bound rather than a blocker.** `FR-190` compares "**a rendered
report surface**" against approved design evidence — a per-surface acceptance rule, not a
whole-pack requirement. Master specification §16.4 records the pack as independently covering
**four** of the twelve §16.2 references — **#6 period comparison, #8 evidence drawer, #9 refusal,
#10 Arabic RTL** — with **#4** (workspace overview, density floor in Arabic/RTL only) and **#7**
(executive decision, composition only) partial, and **#1, #2, #3, #5, #11, #12 not independently
referenced**. The pack "is acceptance evidence for the surfaces it covers and is **silent** on the
rest."

So: this slice asserts against the covered surfaces. The remaining eight are an
**asset-production dependency**, not a code blocker, and not this slice's work. The repository pack
lives at `docs/product/ui-visual-references/` and currently holds two screen references plus the
family board.

**Comparison dimensions** (`FR-190`): hierarchy, density, spacing rhythm, typography, visual states,
RTL, responsive behaviour, asset fidelity. **Pixel-identical equality is not required** where
responsive layout legitimately adapts; visual-language drift is a defect even where every other
test passes.

**RED shapes:**
- Evidence is deterministic and reproducible from the repository — the same two runs agree
  (`FR-190`, §Verification).
- It uses the shipped Playwright/Chromium, and introduces **no** visual-testing platform, service,
  or hosted baseline store (`FR-190`).
- No test reads a figure, route, capability, refusal reason or governed word out of a baseline or
  reference image (`FR-191`) — a scan, with an emptiness assertion.
- A surface whose visual language drifts fails, even with every other test green.

**A run that can only produce the null case is not a pass.** If a covered surface cannot be brought
to the state the reference shows, the execution plan records it as NOT EXERCISED rather than
reporting green.

---

## What this plan does not authorize

- Slice 1 (absorbing `#369` into `KHEPRI_DESIGN_LANGUAGE.md`) — master specification §18.3 files it
  under **Blocked on the owner**, and §A.5 item 1 records it as a live contradiction. Not
  schedulable here.
- Slice 11 (final polish against the pack) — §19 gates it on §16, and §16.4 records six references
  as absent. An asset dependency.
- Slice 7 (§F contracts) — per surface, conditional on that surface's own authority. It rides
  whichever slice touches the surface; it is not a slice of its own in this family.
- Any new chart kind, forecast, trend line, or refusal cause (`FR-181`, `RRA-015` §Exclusions).
- Any telemetry event of any kind. `KHEPRI-DEC-015` §3 stands unamended.
- The `/beta` journey-adoption reading, which remains **OWNER DECISION, not yet taken**
  (`docs/superpowers/plans/2026-09-03-rra010-journey-adoption-reading.md`). It bears on the `/beta`
  surface alone and blocks no slice in this plan. **No slice may act as though option A were
  chosen.**
- Any shared token layer across the journey, report and shell surfaces (`FR-201`).

## Execution discipline

- **One PR per slice**, carrying the plan+RED commit and then the implementation commit — the
  owner asked for fewer PRs. Branch every slice off `main`; never stack a PR on another branch.
- **Tests run with `./.venv/Scripts/python.exe`.** Do not run `ruff format` — there is no CI format
  gate. `ruff check .` is the gate that exists.
- **CodeScene pre-flight before opening a PR**, with `git fetch` first — a stale `origin/main`
  makes `analyze_change_set` return empty results and a meaningless pass. CodeScene gates on
  cyclomatic >9, module mean >4, arguments >4, and cohesion, and it scores test modules too.
- **On any test or CI failure, invoke `superpowers:systematic-debugging` before proposing a fix.**
- **Run the full suite before believing a targeted one** — changing a field's meaning breaks suites
  never opened.
- `uv run khepri-gov validate` and `uv run ruff check .` before every commit.
- The merge to `main` is the owner's. Technical checks report consistency; they do not grant
  approval.
