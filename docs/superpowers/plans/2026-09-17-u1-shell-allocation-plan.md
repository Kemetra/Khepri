# `U1` — The bounded allocation plan for the commercial shell surfaces

> **For agentic workers:** this is an **allocation** plan, the `G3-04`/`SV1`/`D1-02`–`D1-10` tier.
> It allocates two specifications' requirements to six slices and **writes no code**. Each slice
> below opens its own **execution** plan at build time — the `W1-09` tier, with `- [ ]` RED/GREEN/
> commit steps and literal test code — created with `superpowers:writing-plans` when that slice
> starts. REQUIRED SUB-SKILL at execution: `superpowers:test-driven-development`, then
> `superpowers:executing-plans`.
>
> **Companion plan:** the `RRA` half is
> `docs/superpowers/plans/2026-09-17-u1-rra-surfaces-allocation-plan.md`. The two are separate
> documents because `governance/templates/specification.md` admits exactly one family per
> specification and `khepri_gov`'s `_validate_family_links` enforces it; `RRA-012` §Outcome reads
> that rule as forbidding one artifact across two families' surfaces. **Neither plan may cite the
> other's authority for a file.**

**Goal:** Give the commercial shell the approved navigation and filter presentation, one skip-link
mechanism, a state grammar in which refusal/empty/loading/error are four distinguishable screen
states, bounded responsive and right-to-left hardening, and accessibility and visual evidence that
measures those surfaces as tests rather than as aspirations.

**Architecture:** Presentation only, over destinations that already exist. `shell.css` stays
tokens-only; `shell-components.css` carries the component rules; `workspace.css` carries shell
presentation; `shell_templates/` and `legal_templates/` change as **presentation markup and ARIA
state only**; `shell_copy.py` gains **chrome labels only**. No route, no handler, no destination,
no read, no capability, no calculation, no persistence.

**Tech Stack:** Python 3.13, Jinja2, pytest, and the Playwright/Chromium the repository already
ships (`pyproject.toml:31`, `playwright>=1.61,<2`). No new dependency, no visual-testing platform,
no hosted baseline store.

**Authority:**
- active `RCA-010` (`FR-193`–`FR-206`), merged 2026-09-17 at `e915af8` (`#477`) — every slice here.
- active `RCA-008` `FR-163` (the two governed empty rules) and `FR-166` (what the global controls
  are) — binding on slices 4 and 5 as the model they present and never redefine.

**Design source:** `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md` §D (information architecture), §9
(RTL and bilingual), §10 (responsive), §11 (accessibility), §13 (loading, empty, error, refusal),
§17 (visual acceptance), §19 (slicing, incl. slice 2b).
Roadmap: `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` §PROGRAM U1, row `READY_FOR_PLAN`.

---

## Global Constraints

Every slice's requirements implicitly include this section. Values are copied verbatim from the
governing artifacts; where this plan and a specification disagree, **the specification wins** and
this plan is corrected in place.

- **The interface never invents capability** (`FR-193`). "A destination enters navigation only in
  the slice that implements it, as `RCA-002` `FR-049` already requires; no 'coming soon' entry, no
  disabled control standing in for a future surface, and no result count the governed set does not
  fix. No slice under this specification adds a route, an address, a capability, an authorization
  path, or a product destination."
- **A shell presentation value is the shell's** (`FR-201`). "A slice names no custom property,
  class, or asset whose authority sits with the journey or the report surfaces, and introduces no
  shared token layer across the two — the question `RRA-012` left open stays open, and answering it
  needs its own artifact naming both families' paths." **Neither this plan nor its companion is
  that artifact.**
- **Logical CSS properties only** (`FR-199`). "The shell's stylesheets currently contain no
  physical directional property and a slice under this document does not introduce one." `lang` and
  `dir` "remain server-computed and are never inferred in a template"; `dir="auto"` continues to
  isolate customer-controlled mixed-script values; truncation is in character units with the full
  value retained in the DOM so the accessible name stays complete.
- **`shell.css` stays tokens-only** (§Scope, §Verification). "The test asserting it declares no
  rules stays passing."
- **Filters stay what `RCA-008` `FR-166` already models them as** (`FR-197`): the period is a
  source selector, the workspace is the resolved organization scope, and only the view filters
  whose definitions admit them are filters. "No slice under this specification adds a filter, sends
  a parameter a view's allowlist does not name, or retains a filter, layout, sort, or dismissal
  state."
- **No retained state.** No layout, filter, sort, dismissal or preference state is persisted
  (`FR-197`).
- **Images are evidence, not truth** (`FR-205`). "No baseline, screenshot, or reference image is
  read as a source of a figure, a route, a capability, a refusal reason, or a governed word."
- **The §7 asset policy is binding and unrelaxed** (`FR-206`). No CSS-drawn illustration, div-art,
  CSS pyramid, CSS scarab, pseudo-element used as artwork, emoji icon, Unicode glyph standing in
  for an icon, or one-off inline SVG illustration. No external font, image, style, script or CDN
  dependency — the shipped `default-src 'none'` CSP forbids it in any case.
- **No inline script or style**, and the CSP is never weakened — the standing shell constraint the
  `R8-07` quality gate enforces.
- **A chrome label names a region of the interface.** "The moment a word would describe a metric,
  refusal, caveat, population, version, or governed state, it is `RRA-009`'s, `RRA-011`'s,
  `RRA-014`'s or `RCA-008`'s and belongs there" (§Scope).

### Scope ceiling — the exact authorized paths

`RCA-010` §Scope admits these and no others:

| Path | Reach |
|---|---|
| `src/khepri/rra/journey/assets/shell.css` | the shell's token sheet; **stays tokens-only** |
| `src/khepri/rra/journey/assets/shell-components.css` | the shell's component rules |
| `src/khepri/runtime/shell_assets/workspace.css` | shell presentation rules (404 lines at `e915af8`) |
| `src/khepri/runtime/shell_templates/` | **presentation markup and ARIA state only** — element, landmark and heading structure, accessible names, `aria-current`, focus targets, direction attributes, class names. **No route, handler, destination, read, or capability.** |
| `src/khepri/runtime/legal_templates/` | the same presentation-only reach |
| `src/khepri/runtime/shell_copy.py` | **the shell's own chrome labels only**, under the existing import-time parity discipline |
| `tests/` | focused navigation, filter, responsive, RTL, accessibility and visual evidence |

**Explicitly outside:** `src/khepri/runtime/shell_api.py` **and every other
`src/khepri/runtime/*.py` module**, the `src/khepri/rca/` packages, the `/beta` journey surfaces and
`journey.css`, the `RRA` rendering surfaces / charts / report stylesheets, the public landing
surface and `landing.css`, migrations, object storage, the composition root, and every route,
orchestration and persistence path in the repository.

**`shell_controls.py` is outside scope.** It is a `src/khepri/runtime/*.py` module; `SURFACE_VIEWS`
at `shell_controls.py:73` may be **read** by a test asserting navigation extent, and may not be
edited by any slice in this plan.

### Tree-state findings — verified 2026-09-17 at `e915af8`

Recorded because a later slice must not re-derive them.

1. **`aria-current="page"` already ships** at `shell_templates/shell.html.j2:75`, emitted
   conditionally on `tail == surface_path`. Slice 4 hardens and measures this; it does not
   introduce it.
2. **Fifteen shell templates exist**: `shell.html.j2`, `overview`, `data`, `analyses`, `analysis`,
   `compare`, `decision`, `decision_print`, `team`, `switcher`, `invitation_issued`,
   `no_membership`, `unavailable`, plus the partials `_decision_cards` and `_decision_sections`.
   Navigation and accessibility extent must be derived from the shell's own destinations, **not
   from a hand-written list** (§Verification).
7. **`legal_templates/` is in scope and is measured by nothing today.** It holds two templates —
   `legal.html.j2` and `legal_page.html.j2` — and `RCA-010` §Scope admits the directory with its
   reason stated: those pages "link the shell's stylesheets and would otherwise drift from them."
   But `test_every_shell_template_is_measured` scans **only** `shell_templates/`
   (`files("khepri.runtime").joinpath("shell_templates")` at `tests/test_r807_shell_quality.py:380`),
   so **no existing extent assertion reaches the legal pages at all**. A slice that extends that
   test without widening its scan inherits the blind spot — the exact "subset assertions hide a
   forgotten entry" defect. **Slices 9b and 10b must cover `legal_templates/` explicitly**, and an
   execution plan that cannot bring a legal page to a measurable state records it as NOT EXERCISED
   rather than omitting it. Slice 8 already lists the directory; the evidence slices must match
   that reach or slice 8 hardens surfaces nothing measures.
3. **`.skip-link` is duplicated across families**: `shell-components.css:45,56` and
   `journey.css:75-76`. Slice 2b takes the **shell** half. **Unifying across the two surfaces stays
   out** — `FR-201` keeps each surface's values its own, and `RRA-010:30` puts
   `shell-components.css` outside `RRA-010`.
4. **Two raw font sizes remain in `shell-components.css`** at `:135` and `:141`, both `0.875rem`.
   `shell.css:109-128` declares the `--text-xs` … `--text-display` scale, with `--text-sm: 0.82rem`
   the nearest token. These are the "2 in `shell-components.css`" master specification §19 slice 3
   assigns to 2b's authority.
5. **The journey and the shell carry separate type scales** — `--journey-text-*` in `journey.css:59-62`
   versus `--text-*` in `shell.css:109-128`. `FR-201` keeps them separate; **slice 2b and the
   companion plan's slice 3 must not be merged.**
6. **`test_r807_shell_quality.py` already ships five relevant tests**:
   `test_every_shell_template_is_measured`, `test_shell_surfaces_are_operable_at_every_viewport`,
   `test_every_surface_renders_in_both_languages`,
   `test_a_latin_run_inside_arabic_prose_carries_its_direction`, and
   `test_the_skip_link_is_first_in_the_document`. Slices 2b, 8 and 9b **extend** these; they do not
   found the harness. `test_r801_shell_tokens.py` holds the tokens-only assertion on `shell.css`.

---

## Slice sequence

Evidence runs **after** the build slices in this family, so accessibility and visual assertions
measure finished surfaces rather than moving ones.

```
2b (skip-link + 2 sizes)  →  4 (nav + filters, U1-05)  →  5 (state grammar)  →  8 (RTL + responsive)  →  9b (a11y)  →  10b (visual)
```

2b opens because it is the smallest slice with the clearest boundary and discharges master
specification §18.3's last non-owner item. 4 precedes 5 because the state grammar renders inside
the navigation and filter frame 4 fixes. 8 follows both because responsive posture is measured over
finished structure.

---

### Slice 2b — One skip-link mechanism on the shell, and two raw font sizes

**Authority:** `RCA-010` §Scope; master specification §19 slice 2b, §18.3.
**Design:** master specification §G.1, §G.2.
**Depends on:** nothing.

**Files:** `src/khepri/rra/journey/assets/shell-components.css` — the `.skip-link` rules at `:45`
and `:56`, and the two `0.875rem` declarations at `:135` and `:141`.

**Scope boundary:** the **shell** half only. `journey.css:75-76` is `RRA-010`'s and belongs to the
companion plan's slice 2. **Unifying across both surfaces is authorized by neither plan**
(`FR-201`).

**RED shapes:**
- The shell's skip link is first in the document and reachable by keyboard before any other tab
  stop — extend `test_the_skip_link_is_first_in_the_document`.
- It is visible on focus, not merely present in the DOM.
- Exactly one skip-link mechanism exists per shell surface — assert the **count**, so a second
  definition added later fails.
- No `font-size` declaration in `shell-components.css` carries a raw numeric literal — a scan
  anchored to `__file__` with an **emptiness assertion**, so it cannot pass by scanning nothing.
- Computed type size is unchanged beyond the stated per-line delta, measured in the real browser at
  the supported viewports rather than by reading the stylesheet.
- `shell.css` still declares no rules (`test_r801_shell_tokens.py` stays passing).
- No physical directional property is introduced (`FR-199`).

---

### Slice 4 — Navigation and filter presentation (`U1-05`)

**Authority:** `RCA-010` `FR-193`–`FR-197`; presenting `RCA-008` `FR-166` and `RCA-002` `FR-047`,
`FR-049`, `FR-055` without redefining any of them.
**Design:** master specification §D (§D.3 navigation rules, §D.4 tabs vs pages vs drawers, §D.5
deep links and back-navigation).
**Depends on:** slice 2b.

**Files:** `shell_templates/` (presentation markup and ARIA only), `shell_copy.py` (chrome labels
only), `workspace.css`, `shell-components.css`.

**RED shapes:**
- Exactly one navigation per surface, with exactly one `aria-current="page"`. Duplicated navigation
  on a surface is a defect (`FR-194`).
- **No navigation entry for a surface the shell does not serve** — asserted "against the shell's
  own destinations rather than against a list a test happens to remember" (§Verification). Read
  `shell_controls.SURFACE_VIEWS`; do not hand-list. **A guard that names its own scope disarms
  itself.**
- **Extent assertion:** derive the destination set from its own definition and assert **equality
  plus non-empty**, never `>=`. A membership table without an extent assertion cannot see a row
  added.
- No literal directional glyph serves as a navigation affordance, "because an arrow does not
  mirror" (`FR-194`).
- No "coming soon" entry, no disabled control standing in for a future surface, no result count the
  governed set does not fix (`FR-193`).
- **No route, handler, destination, or capability changed** — static scope evidence over the
  authorized paths (§Verification). Assert `shell_api.py` is untouched.
- The language stays a property of the address under the existing prefix, and the switch preserves
  the reader's surface **and position** (`FR-195`).
- Every effective filter is visible on the surface carrying the figures it qualifies, and the
  applied set is announced to assistive technology (`FR-196`).
- A narrow viewport may collapse the filter controls into a disclosure, **and the applied filters
  stay visible when it does** (`FR-196`).
- The period reads as a source selector and the workspace as the resolved organization scope; no
  slice adds a filter or sends a parameter a view's allowlist does not name (`FR-197`).
- No filter, layout, sort or dismissal state is retained (`FR-197`).

---

### Slice 5 — State grammar: the §13 matrix as components

**Authority:** `RCA-010` `FR-202` for the shell's presentation of those states; `RCA-008` where in
scope, and `RCA-008` `FR-163` as the model presented.
**Design:** master specification §13, §F.
**Depends on:** slice 4.

**Files:** `workspace.css`, `shell-components.css`, `shell_templates/`, `shell_copy.py` (chrome
labels only).

**Boundary, stated because §19 states it:** this slice "adds no state, no cause, and no governed
word." It presents states that already exist.

**RED shapes:**
- A refusal, an empty result, a loading state and an error are **four distinguishable** screen
  states, distinguished by **structure and wording rather than by decoration** (`FR-202`).
- A refusal **never shares an element or a class with an error**, never carries error paint, and
  **keeps the position the answer would have occupied** (`FR-202`). Assert the **effect** on the
  real code path, not merely that an exception type is raised.
- The two governed empty rules stay distinguishable, exactly as `RCA-008` `FR-163` requires —
  `stated_no_rows` versus the other admitted rule.
- No new state, cause, or governed word is introduced — derive the state set and the reason-code
  set from their own definitions and assert **equality**, so a widening fails.
- A governed caveat or reason that reaches no code path is a defect — sweep for **defined but never
  attached**, in both languages.
- Motion explains change and does not advertise: no bounce, elastic easing, parallax, decorative
  floating element, constant motion, or animated number counting; no transition is load-bearing
  under `prefers-reduced-motion` (`FR-203`).

---

### Slice 8 — Bounded responsive and right-to-left hardening

**Authority:** `RCA-010` `FR-198`–`FR-199`.
**Design:** master specification §9, §10.
**Depends on:** slices 4 and 5.

**Files:** `workspace.css`, `shell-components.css`, `shell_templates/`, `legal_templates/`.

**RED shapes:**
- **No page-level horizontal overflow at any supported width**, in **either language**
  (`FR-198`, §Verification). Every scrolling region is explicit and bounded.
- A wide table **scrolls horizontally inside a focusable region with visible focus**, rather than
  collapsing into a card list that loses its column relationships (`FR-198`).
- A chart, where one is present, keeps full width with reduced label density and **is never
  dropped** (`FR-198`).
- A drawer becomes a full-screen sheet with **focus trapped and restored on close** (`FR-198`).
- Trust state stays **adjacent to its figure at every width** (`FR-198`).
- Right-to-left presentation uses **logical CSS properties only**; no physical directional property
  is introduced — a scan with an **emptiness assertion** (`FR-199`).
- `lang` and `dir` remain **server-computed**, never inferred in a template (`FR-199`).
- `dir="auto"` continues to isolate customer-controlled mixed-script values (`FR-199`).
- Truncation is in **character units with the full value retained in the DOM**, so the accessible
  name stays complete (`FR-199`).
- A caveat, refusal, evidence link, state or action present in one language is present in the other
  (`FR-199`).

---

### Slice 9b — Accessibility evidence, commercial shell surfaces (`U1-06`, this family's half)

**Authority:** `RCA-010` `FR-200`.
**Design:** master specification §11.
**Depends on:** slices 2b, 4, 5, 8 — this measures those surfaces once they are finished.

**Files:** `tests/` only — extend `test_r807_shell_quality.py`. **This slice changes no source
file**; where a floor fails, the fix lands in the slice that owns that file, not here.

**Where a floor fails after its build slice has merged.** The build slices close before this one
runs, so there may be no open slice to take the fix. **A floor failure discovered here opens a
follow-on slice under `RCA-010`** — named for the file that fails — and does **not** widen this
slice past `tests/`. An evidence slice that edits a stylesheet or a template to make its own
assertion pass has left its scope, and the failure it hid is still in the product.

**Surface extent includes `legal_templates/`.** `test_every_shell_template_is_measured` scans only
`shell_templates/` (tree-state finding 7), so extending it as written would leave `legal.html.j2`
and `legal_page.html.j2` unmeasured while slice 8 hardens them. Widen the scan, or add a second
extent assertion over `legal_templates/` with its own emptiness check.

**RED shapes — per shell surface, in both languages, at the supported viewports** (`FR-200`):
- A visible focus on every tab stop, **including scrollable regions**.
- Focus order follows document order, with **no positive `tabindex`**.
- Semantic landmarks with **meaningful unique** accessible names.
- Exactly one `h1`, with no skipped heading level.
- Labels associated with controls, and **never a placeholder standing in for one**.
- ARIA **only where native semantics are insufficient**.
- `role="status"` for refusals and progress.
- Non-colour differentiation for every trust state.
- Targets of at least 44px **on the element a pointer lands on** — not on an ancestor.
- **Contrast computed rather than asserted** (§Verification) — measured in the real browser.
- `prefers-reduced-motion` **fills a progress track rather than freezing it**.
- Text scales to 200% without loss of content or function.
- Errors are **announced**, not only coloured.

**Extent assertion required.** Derive the surface list from the shell's own destinations and assert
**equality**, so a shell surface added later cannot ship unmeasured. Extend
`test_every_shell_template_is_measured` rather than adding a parallel list beside it.

---

### Slice 10b — Visual regression, commercial shell surfaces (`U1-07`, this family's half)

**Authority:** `RCA-010` `FR-204`–`FR-205`.
**Design:** master specification §17, §16.3, §16.4.
**Depends on:** slices 2b, 4, 5, 8, 9b.

**Files:** `tests/` only.

**Representatives are named from the full in-scope set**, which includes `legal_templates/`
(tree-state finding 7). A representative set drawn only from `shell_templates/` leaves a directory
`RCA-010` §Scope admits, and that slice 8 hardens, outside every visual assertion.

**Bounded extent, and why this is a bound rather than a blocker.** `FR-204` compares "**named
representative rendered shell surfaces**" — a per-surface acceptance rule naming representatives,
not a whole-pack requirement. Master specification §16.4 records the pack as independently covering
**four** of the twelve §16.2 references — **#6 period comparison, #8 evidence drawer, #9 refusal,
#10 Arabic RTL** — with **#4** (workspace overview, density floor in Arabic/RTL only) and **#7**
(executive decision, composition only) partial, and **#1, #2, #3, #5, #11, #12 not independently
referenced**. The pack "is acceptance evidence for the surfaces it covers and is **silent** on the
rest."

So: this slice names its representatives from the covered set. The remaining eight are an
**asset-production dependency**, not a code blocker, and not this slice's work. The repository pack
lives at `docs/product/ui-visual-references/` and currently holds two screen references plus the
family board.

**Comparison dimensions** (`FR-204`): hierarchy, density, spacing rhythm, typography, visual states,
RTL, responsive behaviour, asset fidelity. **Pixel-identical equality is not required** where
responsive layout legitimately adapts; visual-language drift is a defect even where every other
test passes.

**RED shapes:**
- Evidence is deterministic and reproducible from the repository — two runs agree (§Verification).
- It uses the shipped Playwright/Chromium and introduces **no** visual-testing platform, service,
  or hosted baseline store (`FR-204`).
- No test reads a figure, route, capability, refusal reason or governed word out of a baseline or
  reference image (`FR-205`) — a scan with an emptiness assertion.
- The **named representative set** is derived and asserted for extent, so a representative dropped
  later fails rather than silently shrinking the measured surface.
- A surface whose visual language drifts fails, even with every other test green.

**A run that can only produce the null case is not a pass.** If a named representative cannot be
brought to the state the reference shows, the execution plan records it as NOT EXERCISED rather
than reporting green.

---

## What this plan does not authorize

- **`shell_api.py` or any other `src/khepri/runtime/*.py` module** (§Scope). `shell_controls.py`
  may be read by a test and never edited here.
- Any route, address, capability, authorization path or product destination (`FR-193`).
- Any new filter, or any parameter a view's allowlist does not name (`FR-197`).
- Any retained filter, layout, sort, dismissal or preference state (`FR-197`).
- Any new state, cause, or governed word (slice 5's boundary; `RCA-008` owns the model).
- Any shared token layer across the shell, journey and report surfaces (`FR-201`) — that question
  "needs its own artifact naming both families' paths."
- Any telemetry event of any kind. `KHEPRI-DEC-015` §3 stands unamended; `D1-11` stays unauthorized
  under `RCA-008` §Retention.
- Slice 1 (`#369` absorption) — master specification §18.3 **Blocked on the owner**.
- Slice 11 (final polish against the pack) — gated on §16; six references absent. An asset
  dependency.
- Slice 7 (§F contracts) — per surface, conditional on that surface's own authority; it rides
  whichever slice touches the surface.
- The `/beta` journey-adoption reading, which remains **OWNER DECISION, not yet taken**. It bears on
  the `/beta` surface alone and blocks no slice here. **No slice may act as though option A were
  chosen.**
- Whether the decision surface should consume `PeriodComparisonView` — an open `RCA-008` reading,
  untouched by this plan.

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
- **A hand-wired fixture hides an unwired deployment.** `W1-07a` shipped a route absent from the
  image while seven tests passed over a hand-built `ShellServices`. Assert against the deployed
  template and route table, not a fixture.
- `uv run khepri-gov validate` and `uv run ruff check .` before every commit.
- The merge to `main` is the owner's. Technical checks report consistency; they do not grant
  approval.
