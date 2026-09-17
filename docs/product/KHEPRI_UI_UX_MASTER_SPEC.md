# Khepri UI/UX Master Specification

**Baseline:** `6cea330` (`origin/main`), 2026-09-17. Clean tree, `main`, up to date.
**Command:** `/speckit-specify` + `/impeccable shape` — **design and specification only.** No CSS,
template, route, test, package, backend, API, governance, or database change is made by this
document.
**Standing:** This document **grants no implementation authority.** Per
`governance/CONSTITUTION.md` Article II it becomes governing direction only when the owner merges it
to `main`, and even then it confers no authority to change product code — that requires an active
specification naming the files (Article IV).

---

## A. Purpose and authority

### A.1 Why this document exists

Khepri's UI direction is currently spread across three documents and the shipped stylesheets. A
future UI slice must not have to reconstruct the design from four sources and a merge history. This
specification states, in one place, what a Khepri surface must look like, how it must behave, what
states it must carry, and how its implementation is accepted.

### A.2 What it governs

Every customer-reachable Khepri surface:

| Mode | Prefix | Surfaces |
|---|---|---|
| Landing | `/` | landing, legal |
| Focused journey | `/beta` | upload, review, processing, report, evidence, expired, unavailable |
| Commercial shell | `/app` | overview, data, analyses, analysis, compare, decision, decision-print, team, switcher, invitation-issued, no-membership, unavailable |
| Deliverable | — | report HTML, report PDF, Excel artifact |

### A.3 What it does not govern

It does not govern governed calculation, semantic admission, privacy boundaries, evidence
derivation, provenance, retention, or organization isolation. **Where this document and an active
specification disagree, the specification wins.** A design rule may constrain how a governed fact is
*presented*; it may never change which facts exist, what they mean, or who may see them.

Four layers, kept distinct throughout:

| Layer | Owner | Example |
|---|---|---|
| Governance authority | `governance/registry.yaml` | `RRA-012` authorizes the component layer |
| Product semantics | `PRODUCT.md`, blueprint | A refusal is a governed result, not a failure |
| Business logic | `src/khepri/` | `SECTION_STATE_REFUSED` is computed, never styled into existence |
| Design specification | this document | A refusal never uses error paint |

### A.4 Relationship to existing documents

```
governance/registry.yaml   (active specifications & decisions)   ← authority
        ↓
KHEPRI_MASTER_PRODUCT_ROADMAP.md                                 ← outranks the blueprint
        ↓
KHEPRI_PRODUCT_UX_BLUEPRINT.md                                   ← product UX reference
        ↓
KHEPRI_DESIGN_LANGUAGE.md                                        ← visual and component direction
        ↓
this document                                                     ← UI/UX implementation specification
        ↓
Implementation slices
```

**This document is deliberately standalone and restates rules that also appear in its predecessors.**
That duplication was chosen by the owner with the drift risk stated. The four overlapping areas, so a
future reader knows what to reconcile:

| This document | Also stated in |
|---|---|
| §D Information architecture | blueprint §5, §5.1, §8 |
| §G.1 Foundations / tokens | design language §2 |
| §G.2 Components | design language §4 |
| §9 RTL and bilingual, §10 Responsive | design language §5, §6; blueprint §14, §15 |

**Reconciliation rule.** When a rule in this document and its predecessor disagree, **this document
wins for implementation** and the predecessor is corrected in place in the same slice that discovers
the divergence. Corrected in place, never deleted: a reader arriving from an older note needs to see
what changed.

### A.5 Two recorded defects in the current document set

1. **`KHEPRI_DESIGN_DIRECTION_PROPOSAL.md` is merged but unabsorbed.** It merged at `cdfa024`
   (`#369`) as a proposal to revise `KHEPRI_DESIGN_LANGUAGE.md` and relax nine self-imposed visual
   rules. `KHEPRI_DESIGN_LANGUAGE.md` contains **zero references to it**, and its most recent
   reconciliation (`f15c835`, 2026-09-03) predates the proposal's own baseline (`d52f11f`,
   2026-09-04). A merged proposal its target never absorbed is a live contradiction. This document
   does not resolve it — absorbing it is a design-language edit, not a UI specification — but a slice
   touching either file must close it.

2. **This document's §16 overrides a settled clause — and corrects it here, not later.** §16.1
   supersedes `KHEPRI_DESIGN_LANGUAGE.md` §0's visual-authority restriction, and **the correction to
   §0 ships in this same change** rather than being deferred to an implementation slice. A document
   that created a contradiction and scheduled its own repair would violate §A.4's reconciliation
   rule on its first application. See §16.1 and §19 slice 1.

---

## B. Experience principles

Enforceable, each with a test shape. A principle that cannot fail a review is not in this list.

| # | Principle | What it forbids | How it is checked |
|---|---|---|---|
| B1 | **Evidence before decoration** | Decorative artwork inside an analytical region | No `<img>` or decorative SVG within a figure, table, or card region |
| B2 | **Explain before export** | An export control above the explanation of what is exported | Export affordance never precedes the claim in document order |
| B3 | **Refusal is a first-class product state** | A refusal rendered with error paint, or absent where the answer would have been | A refusal class and an error class never co-occur on one element |
| B4 | **Density without noise** | Whitespace that reduces information per screen without aiding scanning | Analytical pages meet the density floor in §E.4 |
| B5 | **Hierarchy before cards** | A card used to create hierarchy a heading should create | No card nested inside a card, ever (§15) |
| B6 | **Bilingual parity** | A caveat, refusal, evidence link, or action present in one language only | Copy key sets asserted equal at import; parity fails the build |
| B7 | **Progressive disclosure** | Full evidence inline where a link into evidence would do | Evidence reached from the claim, never a global destination |
| B8 | **Deterministic interaction** | A control whose result depends on unstated client state | Same address + same language produces the same rendering |
| B9 | **No hidden analytical assumption** | A figure whose scope, period, or filter is not visible on the same screen | Every figure region carries its scope line |
| B10 | **Desktop-first, responsive degradation** | Pretending a dense analytical workflow is identical on a phone | §10's per-surface narrow strategy |
| B11 | **Accessibility as system behavior** | Accessibility deferred to a final polish slice | Floors in §11 asserted per surface, not per release |
| B12 | **The interface never invents capability** | A "Coming soon" destination; a result count the governed set does not fix | A destination enters navigation in the slice that implements it |

---

## C. User journey map

Verified against `src/khepri/` at `6cea330`. Surfaces absent from the repository are marked
**FUTURE** and carry no contract.

### C.1 Landing — `/`

| Field | Value |
|---|---|
| Goal | Understand what Khepri does and start |
| Primary information | Positioning: admission before claim; refusal is visible |
| Primary action | Enter the journey |
| Secondary | Legal pages |
| Exit | `/beta` upload, or a legal page |
| Failure state | None — static |
| Evidence | Proven / Caveated / Withheld blocks are **labelled specimens** (`RCA-004` FR-084), never a second customer vocabulary |
| AR/EN | Full parity; language is a property of the address |

### C.2 Journey upload — `/beta/{lang}/upload`

| Field | Value |
|---|---|
| Goal | Submit a sales file |
| Primary information | Accepted file types; what happens next |
| Primary action | Choose or drop a file |
| Secondary | Language switch; step navigation |
| Exit | Advance to review on success |
| Failure | Rejected file names its reason; never a generic failure |
| Evidence | None at this step |
| AR/EN | `dir="auto"` on the file name — a customer-controlled mixed-script value |

### C.3 Journey review — `/beta/{lang}/review`

| Field | Value |
|---|---|
| Goal | Confirm what was detected before committing to an analysis |
| Primary information | Detected profile and findings |
| Primary action | Continue to processing |
| Secondary | Replace the file |
| Failure | Profile findings render as `.refusal-summary`, `role="status"` — **not** error paint (`#294`) |
| Evidence | Findings reference the submitted file, not a bundle |

### C.4 Journey processing — `/beta/{lang}/processing`

| Field | Value |
|---|---|
| Goal | Know the analysis is progressing and how much remains |
| Primary information | Progress against named stages |
| Primary action | None — waiting is the state |
| Failure | Processing failure names its governed cause where one exists |
| Motion | The only animation in the product; `prefers-reduced-motion` **fills** the track rather than freezing it |

### C.5 Journey report — `/beta/{lang}/report`

| Field | Value |
|---|---|
| Goal | Read what the data said |
| Primary information | Quality summary, then sections by state |
| Primary action | Read; reach evidence from a claim |
| Secondary | Download artifacts; evidence surface linked beside the report (`#363`) |
| Failure | A refused section keeps its position and states its reason |
| Evidence | `evidence_link(citation_id)` per claim |

### C.6 Evidence surface and drawer

| Field | Value |
|---|---|
| Goal | See what supports one specific claim |
| Primary information | Given facts, coverage, version |
| Primary action | Return to the claim |
| Density | Highest in the product — a proof surface, not a summary |
| Component | `evidence_drawer(given, chrome, coverage, open=false)` |

### C.7–C.10 Workspace overview, data, analyses, analysis — `/app/{lang}`

Shipped via `_WORKSPACE_SURFACES` (`overview`, `data`) plus a separate `analyses` dispatch that needs
more than a reader (`offers_analyses`). Per `FR-049`, **a surface enters the navigation only when the
shell holds a reader for it.**

| Surface | Goal | Primary action |
|---|---|---|
| Overview | Know the organization's current position | Enter an analysis |
| Data | Know what was submitted and whether it is retained | Pin a version (`PIN_KIND_VERSION`) |
| Analyses | Find one analysis among many | Open one (`PIN_KIND_RUN`) |
| Analysis | Read one completed analysis | Reach its report or evidence |

### C.11 Compare — `/app/{lang}/compare`

Period comparison, reachable through the composition root since `44d54a7` (`#470`). `RCA-009` active.

### C.12 Decision — `/app/{lang}/decision`

| Field | Value |
|---|---|
| Goal | Decide, with the trust state of each figure visible |
| Trust states | verified · caveated · refused · unavailable (`RCA-008` FR-162) — **four, not three** |
| Unavailable | Content-free by `FR-165`: it says *that*, and no *why* |
| Filters | Seven views, not eight — `SURFACE_VIEWS` excludes `PeriodComparisonView` by design |
| Print | `decision_print.html.j2` |

### C.13–C.15 Team, switcher, invitation issued

Owner-only capabilities: invitation issue and revoke. **`invitation_issued` renders no language
switch** — it is a POST result with no address of its own, and every destination the control could
name destroys the only plaintext copy of the token.

### C.16 Refusal-of-entry surfaces

`unavailable` and `no_membership` are handed **nothing but a language**. They take no cause, so they
can disclose none — `FR-050` holding by construction. Their frame carries brand and language only.

### C.17 FUTURE surfaces

Repeat-use history beyond M3, branded report, secure share, ready notification, guided exploration,
Ask Khepri, Try Sample Analysis. **No contract in this document.**

---

## D. Information architecture

### D.1 Two modes, not one

`/app` (commercial context) and `/beta` (task mode) are **two product modes by design and not a
defect to be merged.** The crossing is a 303 that sets its cookie only on success and deliberately
omits it on the refusal path.

### D.2 Global frame

Brand → organization → surfaces → language. The frame **degrades by surface** rather than rendering
one fixed row: brand and language need only a language and appear everywhere; organization and Team
appear only where a resolved organization was passed.

### D.3 Navigation rules

1. One navigation per surface. Duplication is a defect (§15).
2. A destination enters navigation in the slice that implements it (`FR-049`).
3. `aria-current="page"` on exactly one nav item; `aria-current="step"` on exactly one journey step.
4. **No literal directional glyph as a navigation affordance** — an arrow does not mirror.
5. The language switch preserves position: same surface, other language segment (`FR-047`).

### D.4 Tabs vs pages vs drawers

| Use | When |
|---|---|
| Page | A distinct address a reader may link to or return to |
| Drawer | Evidence for one claim — dismissible, never the only path to a fact |
| Dialog | Only to confirm a destructive or irreversible act |
| Tab | Not used for analytical content; it hides state from deep links |

### D.5 Deep links and back-navigation

Every analytical view is addressable. Pinning is explicit (`shell_pins.py`). Back returns to the
prior surface with its scope intact. **No surface may trap a reader:** every page, including every
refusal surface, carries at least one exit.

---

## E. Page anatomy

### E.1 Canonical order

```
1  Global frame        brand · organization · surfaces · language
2  Page identity       what this page is
3  Context             dataset · period · filters in force
4  Primary information the decision-relevant answer
5  Supporting analysis breakdowns, comparisons
6  Evidence & caveats  reachable from the claim
7  Contextual controls filters, pinning
8  Handoff             export, print, download
```

### E.2 Rules

- **At most one primary action per page.** A second competing primary is a defect.
- Content width `--shell-width` (1068px). Prose `--measure-prose` (62ch). Headings
  `--measure-heading` (24ch).
- **Cards do not nest.** A card inside a card is forbidden (§15).
- Sticky only for the global frame and, on a long analytical page, the scope line — never a
  decorative header.
- A page is not required to be a stack of cards. Prefer headings and rules over boxes.

### E.3 Section rhythm

Section spacing `--space-6`; within-section `--space-4`; label-to-value `--space-2`. Three tiers, not
seven.

### E.4 Density floor

An analytical surface at 1440×900 shows **at least 12 distinct governed figures or rows** above the
fold on Overview and Decision. Failing that, the layout is too loose: a page that reads as empty
needs its wasted width filled, not more sections.

---

## F. Screen contracts

Every contract below is for a **verified** shipped surface. Each carries: purpose · question
answered · required content · primary · secondary · navigation · evidence · density · empty ·
loading · error · refusal · partial · desktop · narrow · RTL · accessibility · prohibited.

### F.1 Landing — `/`

- **Question:** "What is this, and should I use it?"
- **Required:** positioning; the specimen blocks; entry.
- **Primary:** enter the journey. **Secondary:** legal.
- **Empty / loading / partial:** not applicable — static.
- **Error:** none reachable.
- **Narrow:** single column, full-width entry control.
- **RTL:** full mirroring; logical properties only.
- **Prohibited:** customers, testimonials, benchmarks, pricing, licensing, deployment claims —
  **none are established** and none may be fabricated.

### F.2 Upload — `/beta/{lang}/upload`

- **Question:** "How do I give Khepri my data?"
- **Required:** accepted types; the drop zone; what happens next.
- **Primary:** choose or drop a file.
- **Empty:** the default state — the drop zone *is* the empty state and must read as ready, not as
  missing.
- **Loading:** upload progress on the control, not a page overlay.
- **Error:** rejection names the governed reason. Never "Something went wrong."
- **Partial:** not applicable.
- **Narrow:** the drop zone becomes a full-width button; the drag affordance is never the only path.
- **RTL:** file name `dir="auto"`.
- **Accessibility:** the drop zone is a real control, keyboard reachable, ≥44px.
- **Prohibited:** a drag-only path; a file-type list that disagrees with the validator.

### F.3 Review — `/beta/{lang}/review`

- **Question:** "Did Khepri read my file correctly?"
- **Required:** detected profile; findings.
- **Primary:** continue. **Secondary:** replace the file.
- **Refusal:** `.refusal-summary` with `role="status"`. **Asserted never to share a class with the
  transport-error paint** (`test_refusal_and_transport_error_no_longer_share_paint`, both languages).
- **Partial:** a partially readable file shows what was read and what was not, by name.
- **Prohibited:** advancing while a blocking finding stands; error paint on a governed finding.

### F.4 Processing — `/beta/{lang}/processing`

- **Question:** "Is it working, and how long?"
- **Required:** named stages; current stage.
- **Primary:** none. **Secondary:** leave and return — the address survives.
- **Loading:** this surface *is* the loading state; it must never show a spinner with no stage name.
- **Error:** failure names its governed cause where one exists; otherwise the neutral default.
- **Motion:** the single animation; reduced motion **fills** the track.
- **Prohibited:** a fabricated percentage; an ETA the system cannot compute.

### F.5 Report — `/beta/{lang}/report`

- **Question:** "What did my data say?"
- **Required:** quality summary (answered / caveated / refused counts); sections in governed order;
  an evidence link per claim.
- **Primary:** read. **Secondary:** artifacts; evidence surface.
- **Refusal:** a refused section **keeps its position** and states its reason. It is not moved, not
  collapsed by default, and not greyed to illegibility.
- **Partial:** caveated sections carry their caveat adjacent to the figure, never in a footnote.
- **Density:** highest tolerated; this is a reading surface.
- **Narrow:** tables scroll horizontally within a focusable region with visible focus.
- **Prohibited:** a fixed result count; a section state invented by the template.

### F.6 Evidence drawer and surface

- **Question:** "What supports *this* figure?"
- **Required:** given facts; coverage; version label.
- **Primary:** return to the claim.
- **Empty:** `coverage_indicator` states absence in operator language, never a blank panel.
- **Narrow:** the drawer becomes a full-screen sheet with an explicit close, focus trapped while
  open, focus restored to the originating link on close.
- **Prohibited:** evidence as a top-level destination (**B7**) — it is contextual by principle.

### F.7 Overview — `/app/{lang}`

- **Question:** "Where does my organization stand?"
- **Required:** current position; entry to an analysis.
- **Density:** ≥12 governed figures or rows above the fold at 1440×900.
- **Empty:** no analyses yet — one instruction and one action, not an illustration.
- **Prohibited:** a KPI whose scope line is absent (**B9**).

### F.8 Data — `/app/{lang}/data`

- **Question:** "What did I submit, and is it still there?"
- **Required:** versions; retention state.
- **Primary:** pin a version.
- **Refusal and tombstone:** retention states render from `tombstones.py` codes, translated —
  machine vocabulary never reaches a customer.
- **Prohibited:** presenting an unretained version as retained.

### F.9–F.10 Analyses and Analysis

- **Questions:** "Which analysis?" then "What did this one say?"
- **Empty:** no runs — the instruction is to start one.
- **Primary:** open one; reach its report.

### F.11 Compare — `/app/{lang}/compare`

- **Question:** "How did this period differ from that one?"
- **Required:** both operands named with their periods; per-figure comparison state.
- **Refusal and unavailable:** `KIND_REFUSED` and `KIND_UNAVAILABLE` are distinct and render
  distinctly.
- **Prohibited:** a delta computed in the template. Comparison operands come from the shared runtime
  seam (`FR-180`).

### F.12 Decision — `/app/{lang}/decision`

- **Question:** "What should I do, and how far can I trust it?"
- **Required:** four trust states; scope line; filters in force.
- **Unavailable:** content-free (`FR-165`) — states *that*, never *why*.
- **Filters:** exactly the seven `SURFACE_VIEWS`. A filter for a view this surface does not read
  would offer to narrow a figure the page never shows.
- **Print:** `decision_print.html.j2`.
- **Prohibited:** fusing operational state with trust state into one compound badge.

### F.13–F.14 Team and invitation issued

- **Owner-only:** issue, revoke.
- **Invitation issued:** **renders no language switch**, by contract. The token is shown once.
- **Prohibited:** any navigation away that is not an explicit, warned choice.

### F.15 Unavailable and no membership

- **Required:** one sentence; one exit.
- **Cause:** none — the surface receives none.
- **Prohibited:** a cause, a retry that cannot succeed, or a dead end with no exit.

---

## G. Design system architecture

### G.1 Foundations — already shipping

**These are not proposals.** Every value below is in
`src/khepri/rra/journey/assets/shell.css`, a tokens-only sheet (a test asserts it declares no rules).

**Color, by role:**

| Role | Token | Value |
|---|---|---|
| Page | `--paper` / `--surface` | `#fbfcfd` |
| Raised | `--surface-raised` | `#fafbfd` |
| Text | `--ink` | `#202326` |
| Secondary text | `--muted` | `#55606d` |
| Rule | `--line` / `--line-subtle` | `#cfd6de` / `#e4e8ed` |
| Accent | `--accent` / `--accent-dark` / `--accent-surface` | `#1e5b96` / `#174a7c` / `#f0f5fa` |
| Danger | `--danger` plus `-border`, `-surface`, `-ink` | `#9a2d26` … |
| Ready | `--ready` plus `-border`, `-surface` | `#1d6b45` … |
| Track | `--track` | `#e3ded1` |
| Focus | `--focus` | `#1f5fa8` |

**Contrast, computed and not asserted:** `--ink` on `--paper` 15.37:1 · `--muted` 6.23:1 (AA) ·
`--accent` 6.83:1. The thinnest text in the product (step-nav `#667381` at 12px) passes AA **by 0.22
— no margin.** Any type or color change must recompute this.

**Spacing:** `--space-1` … `--space-8`, a 4px ramp (0.25rem → 4rem).

**Type:** `--text-xs` 0.7 · `-sm` 0.82 · `-base` 1 · `-md` 1.15 · `-lg` 1.4 · `-xl` 1.75 · `-2xl`
2.15 rem; `--text-display` and `--text-lede` fluid via `clamp()`. Leading 1.15 and 1.5.

**Radius:** `--radius-sm` 3px · `-md` 6px · `-pill` 999px. **Elevation:** `--shadow: none`.

**Layout:** `--shell-width` 1068px · `--measure-heading` 24ch · `--measure-prose` 62ch ·
`--touch-min` 44px.

**Typeface:** `--font-body: "Noto Sans Arabic", "Segoe UI", Tahoma, sans-serif` — shipped as package
data, SHA-256 verified. **No `@import`, no font host.**

**Four recorded deliberate absences — not gaps:** no dark palette · no second typeface · no icon set ·
no elevation ramp. Each may be added only through §16's approved reference, and any new face or icon
family must first pass the licence-plus-audited-digest process.

### G.2 Components — existing inventory first

Eight governed Jinja macros in `rendering/templates/_components.html.j2`, authority `RRA-012`:

`figure` · `status_badge` · `quality_summary` · `refusal_panel` · `evidence_link` · `version_label` ·
`coverage_indicator` · `evidence_drawer`

Plus `_chart.svg.j2` (`chart`), `_evidence.html.j2`, `_decision_cards.html.j2`, and
`_decision_sections.html.j2`.

**Canonical behavior for every component family** — purpose, variants, states, responsive,
accessibility, misuse:

| Family | Variants | States | Accessibility floor | Misuse |
|---|---|---|---|---|
| Button | primary, secondary, quiet, destructive | rest, hover, active, focus, disabled, busy | ≥44px on the element a finger lands on; visible focus | More than one primary per page |
| Text link | inline, standalone | rest, hover, focus, visited | Underline or other non-color differentiation | A link that acts like a button |
| Icon button | — | as button | Accessible name required; an icon is never the name | An icon with no text alternative |
| Input | text, number, file | rest, focus, invalid, disabled | Label associated; never placeholder-as-label | Placeholder carrying the only label |
| Select | single | as input | Native semantics preferred | A div pretending to be a select |
| Upload | drop zone, button | idle, drag-active, uploading, rejected | Keyboard path mandatory | Drag as the only path |
| Filter | applied, available | applied filters always visible | Applied set announced | A hidden filter changing a figure |
| Tabs | — | — | Not used for analytical content | Hiding state from a deep link |
| Table | dense, comparison | loading, empty, partial, scrolling | Scroll region focusable with visible focus | `em` padding on cells |
| KPI figure | `figure` macro | answered, caveated, refused, unavailable | Scope line adjacent | A figure with no scope |
| Metric card | only where a figure needs adjacent evidence | as KPI | — | Cards inside cards |
| Comparison | `KIND_REFUSED`, `KIND_UNAVAILABLE`, valued | — | Both operands named | A template-computed delta |
| Chart | bar, grouped bar, line | data, missing, refused | `role="img"` plus `<title>` and `<desc>` | A chart type the data does not support |
| Evidence link | `evidence_link` | — | Reached from the claim | A global evidence destination |
| Caveat | adjacent | — | Adjacent to its figure | A footnote |
| Refusal | `refusal_panel` | — | `role="status"`; never error paint | Sharing the error class |
| Alert | info, warning, danger | — | Not used for refusals | Styling a governed refusal |
| Drawer | `evidence_drawer` | open, closed | Focus trapped; restored on close | Being the only path to a fact |
| Dialog | confirm | — | Destructive confirmation only | Routine use |
| Tooltip | — | — | Never the sole carrier of meaning | Essential content |
| Status badge | `status_badge` | answered, caveated, refused, not stated | Non-color differentiation | Fusing operational and trust state |
| Breadcrumb | — | — | No directional glyph | An arrow that does not mirror |
| Page header | — | — | Exactly one `h1` | Two competing identities |
| Navigation | global, step | current marked | Exactly one `aria-current` | Duplicated navigation |
| Pagination | — | — | ≥44px targets | A fixed total the set does not fix |
| Skeleton | — | — | Announced as busy | Masking a refusal |
| Progress | `processing` | determinate | Reduced motion fills | A fabricated percentage |
| Export | download, print | idle, preparing, failed | Named format and scope | Export above the explanation (**B2**) |

**Known live defect, and its authority splits across two surfaces:** `.skip-link` is **two
mechanisms** — `journey.css:75` (`fixed`, `translateY(-180%)`) versus `shell-components.css:45`
(`absolute`, `-9999px`), with inverted colors.

`RRA-010` §73 authorizes "one skip-link mechanism" **for the journey**, and `RRA-010` is explicit
that adopting the shell's is excluded. But `RRA-010:30` states that
`src/khepri/rra/journey/assets/shell.css` and `shell-components.css` are "**outside this scope**" —
they sit in the journey's asset directory and are the shell's, because `shell.html.j2` is their sole
linking template and ownership follows the linking template rather than the folder.

**So `RRA-010` authorizes only the journey half.** Changing the shell's mechanism, or unifying the
two, needs authority that names the shell stylesheet. See §19 slices 2 and 2b.

---

## 7. SVG, imagery, and asset policy

**Binding. This section exists because a coding agent will otherwise invent artwork.**

### 7.1 Icons

- One consistent icon family, shipped as SVG assets committed to the repository.
- **No emoji as interface icons. No Unicode glyph pretending to be an icon. No CSS-drawn icon
  approximation. No one-off inline SVG drawn by a coding agent.**
- **No icon family is currently approved.** Adding one requires §16's reference plus the
  licence-plus-audited-digest process. Until then surfaces ship without icons rather than with
  invented ones.
- No literal directional glyph as a navigation affordance — an arrow does not mirror.

### 7.2 Brand and decorative illustration

- Must exist as **reviewed assets committed to the repository**. SVG for vector artwork; optimized
  raster where appropriate.
- **A coding agent must not recreate supplied artwork using CSS boxes, divs, borders, gradients, or
  programmatic shapes.** A visual reference is a reference, not permission to approximate it badly
  in code.
- If the asset is absent, the surface ships without it. **An absent asset is never replaced by a CSS
  approximation.**

### 7.3 Where illustration helps, and where it does not

| Region | Illustration |
|---|---|
| Landing | Permitted; reviewed assets only |
| Journey upload and empty states | One reviewed asset maximum |
| Analytical regions (figures, tables, charts, evidence) | **Forbidden** — it competes with data (**B1**) |
| Report deliverable | Forbidden except the wordmark |

### 7.4 Named anti-reference

**`docs/ui/design_handoff_khepri/` is NOT a source and must not be mined for values.** Its palette is
dark against a shipped light one, and its asset plan names Google Fonts and a unpkg CDN — **both
forbidden by the roadmap and unreachable under the shipped `default-src 'none'` CSP.** It is marked
non-authoritative in its own design spec. Its twelve screenshots are **not** the Visual Reference
Pack of §16.

### 7.5 Data visualization is the exception

Charts are generated programmatically because they are data-driven. They follow §8.

---

## 8. Data visualization grammar

**Authority note: `U1-03` is not authorized.** `RRA-012` excludes "a chart grammar, a chart type, or
any charting behavior — `U1-03` names that work and it needs its own authority" (`RRA-012:229`), and
`RRA-012:267` names `U1-03`, `U1-05`, `U1-06`, and `U1-07` **not authorized here.** This section is
written as specification and **may not be implemented** until successor authority exists (§18).

### 8.1 Form selection

| Question | Form |
|---|---|
| One value now | KPI figure |
| Exact values, many rows | Table |
| Change over ordered periods | Line |
| Comparison across a few categories | Bar |
| Two series across categories | Grouped bar |
| Share of a whole | **Table with percentages, not a pie** |
| Concentration | Ranked bar with an explicit cumulative column |

Shipped kinds: `CHART_BAR`, `CHART_GROUPED_BAR`, `CHART_LINE`. **No kind outside this set** without
successor authority.

### 8.2 Semantics

- **Color carries meaning or it is not used.** A single series takes one accent; categorical color is
  permitted only where the categories are governed and stable.
- Comparison: baseline and comparand distinguishable **without relying on hue alone**.
- Negative values render below a visible zero baseline. **A truncated axis is forbidden** on any
  comparison.
- Missing data: a visible gap with a stated reason. **Never interpolated, never zero.**
- Incomplete data: rendered with its caveat adjacent.
- Refused: **the chart region is replaced by `refusal_panel`.** A refused figure is never drawn as
  empty.
- Zero denominator: a refusal, not `0%` and not `NaN`.

### 8.3 Chrome

Axes labelled with unit and period. A legend only with two or more series. Tooltips are **never the
sole carrier** of a value. Annotations come only from governed facts. Every chart carries an evidence
entry point.

### 8.4 Numbers and Arabic layout

Locale-formatted. **Arabic yields Arabic-Indic digits, Arabic month names, and Arabic decimal,
grouping, and percent marks (U+066A).** In RTL the category axis runs right to left; `charts.py`
already carries a `mirrored` plot flag and `_mirror()`.

### 8.5 The hard rule

**Visualizations display truth; they do not create truth.** A chart may not introduce arithmetic
absent from governed facts and views. No decorative chart choice unsupported by data semantics.

---

## 9. RTL and bilingual system

Arabic and English are **equal populations**, not a primary language plus a translation.

| Concern | Rule |
|---|---|
| Direction | `lang` and `dir` are **server-computed**, never inferred in a template |
| Properties | **Logical CSS properties only.** All five stylesheets currently contain **zero** physical directional properties — a verified property to preserve |
| Mixed script | `dir="auto"` for customer-controlled values (organization names, file names); `dir="ltr"` islands only for guaranteed-Latin values such as emails and tokens |
| Icons | No literal directional glyph as a navigation affordance |
| Tables | Column order mirrors; numeric columns keep their alignment relative to the reading direction |
| Charts | The category axis mirrors (§8.4) |
| Numbers and dates | Locale-formatted; Arabic-Indic digits, Arabic month names, U+066A percent |
| Truncation | **In character units, with the full value retained in the DOM** so the accessible name is complete |
| Parity | Copy key sets asserted **equal at import** — a missing key fails the build, not the visitor |
| Equivalence | Caveats, refusals, evidence, and analytical meaning equally visible in both languages |
| Switch | Preserves surface and position; `lang` is set so the target language is pronounced in itself |

**Arabic is never translated English pasted into a mirrored page.** Copy lives in the copy modules,
never authored in JavaScript.

---

## 10. Responsive behavior

| Class | Width | Posture |
|---|---|---|
| Wide desktop | ≥1440px | Full density; `--shell-width` caps the measure |
| Desktop and laptop | 1024–1439px | Full density |
| Narrow and tablet | 768–1023px | Supporting analysis stacks below primary |
| Mobile | <768px | Summary first; full productivity may require desktop |

**Khepri is an analytical product. A dense desktop workflow is not pretended identical on a phone.**

| Element | Narrow strategy |
|---|---|
| Table | Horizontal scroll in a **focusable** region with visible focus — not a card list that loses column relationships |
| Chart | Full width with reduced label density; **never** dropped |
| Evidence drawer | Full-screen sheet; focus trapped; focus restored on close |
| Filters | Collapse into a disclosure; **applied filters stay visible** |
| Global navigation | Collapses; the language control remains reachable |
| Decision surface | Trust state stays adjacent to its figure at every width |

**No horizontal page overflow at any width.** A scrolling region is explicit and bounded.

---

## 11. Accessibility

**Floors, not aspirations. `U1-06` accessibility evidence is not authorized (§18); these are stated
as requirements now and asserted when authority exists.**

- **44px minimum target**, applied to the element a finger lands on rather than a padded wrapper, in
  both languages at every supported viewport.
- Visible focus on **every** tab stop, including scrollable regions.
- Focus order follows document order; no positive `tabindex`.
- Semantic landmarks. A named region needs a meaningful, **unique** accessible name — but not every
  scrollable table becomes a landmark merely to be focusable.
- Exactly one `h1`; no skipped heading levels.
- Labels associated with controls; a placeholder is never the label.
- **ARIA only where native semantics are insufficient.**
- Status updates announced: `role="status"` for refusals and progress.
- **Chart alternative:** `role="img"` with `<title>` and `<desc>`, both from governed chrome codes.
- Contrast **computed, not asserted** (§G.1).
- **Non-color state differentiation** for all four trust states.
- `prefers-reduced-motion` **fills** the progress track rather than freezing it.
- Text scaling to 200% without loss of content or function.
- Errors announced, not only colored.
- `lang` and `dir` server-computed.

---

## 12. Interaction and motion

**Motion explains change; it does not advertise the interface.**

| Transition | Behavior |
|---|---|
| State change | Immediate; no animated number counting |
| Drawer and dialog | Short positional transition, ≤200ms |
| Loading | Progress fills against named stages |
| Comparison | No animated morph between periods |
| Drill-down | Navigation, not an animated zoom |
| Reduced motion | Fills rather than freezes; no transition is load-bearing |

**Forbidden:** bounce, elastic easing, decorative floating elements, parallax, constant motion,
flashy gradients, and glow. The progress track is currently **the only animation in the product**; a
new one needs a stated reason.

---

## 13. Loading, empty, error, and refusal states

**First-class screen states.** `--shadow: none` and a light palette mean these are distinguished by
structure and wording, not by decoration.

| State | Title principle | Recovery | Expose cause? | Severity | Retry |
|---|---|---|---|---|---|
| Loading | Name the stage | — | — | Neutral | — |
| No uploaded data | Name what is absent | Upload | — | Neutral | — |
| No runs | Name what is absent | Start an analysis | — | Neutral | — |
| No filter matches | Name the filter | Clear filters | Yes — the filter set | Neutral | — |
| Unsupported operation | Name the operation | Nearest supported path | Yes | Neutral | No |
| Insufficient data | Name what was needed | Submit more | **Yes, by name** | Neutral | No |
| Incomplete data | Name what is partial | Proceed with caveat | Yes | Caution | — |
| **Analytical refusal** | Name the question refused | Reach evidence | **Yes, and never error paint** | **Governed, not error** | No |
| Permission failure | State the capability required | Ask an owner | Role only, never data | Caution | No |
| Organization isolation | Content-free | Exit | **No — discloses nothing** | Neutral | No |
| Processing failure | Governed cause where proven | Retry or resubmit | Where proven | Danger | Yes |
| Export failure | Name format and scope | Retry | Yes | Danger | Yes |
| Stale or unavailable | "Content is no longer available." | Exit | **No cause** | Neutral | No |

**"Something went wrong" is forbidden wherever Khepri knows the reason.** Neutral defaults ("We
couldn't complete this analysis.", "Content is no longer available.") are specialized **only** where
a governed reason proves the cause. Deadlines are stated in absolute time with a timezone, never as
"7 days".

---

## 14. UX writing

Precise · calm · concise · specific · evidence-oriented. **Reason-driven: copy must not assert a
cause the governed state does not prove.**

- Buttons describe their action ("Start analysis", not "Continue" where a more specific verb exists).
- Errors state what happened and what can happen next.
- **Refusals must not read as crashes.** A refusal is a result.
- **Machine vocabulary never reaches a customer** — internal state and reason identifiers are
  translated into operator language.
- No marketing language inside analytical workflows.
- The customer-visible scope noun is **Organization**. "Workspace" is an internal domain and contract
  term and is not a customer noun.
- Customer vocabulary is *Answered / Answered with caveats / Refused / Not stated*, governed by
  `RRA-012`. **Nothing finer has authority.**

---

## 15. Visual anti-patterns — forbidden

1. Generic SaaS dashboard appearance
2. Endless cards; **cards inside cards**
3. A rounded-square icon tile above every title
4. Purple or blue gradient defaults
5. Glassmorphism
6. Glow effects
7. Over-rounded everything — the radius ramp stops at 6px plus pill
8. Weak hierarchy
9. Gray-on-gray low contrast
10. Tiny muted text below the computed AA floor
11. Random spacing outside the 4px ramp
12. Colors outside the token set
13. Oversized hero whitespace on analytical screens
14. Stock illustration
15. **AI-generated CSS artwork** (§7.2)
16. Decorative charts (§8.5)
17. Unexplained animation
18. Duplicated navigation
19. Desktop-only layout
20. Hidden evidence or caveats
21. **Visually de-emphasized refusal states**
22. Emoji or Unicode glyphs as icons (§7.1)
23. Physical directional CSS properties
24. `em` padding on table cells

---

## 16. Visual Reference Pack contract

### 16.0 Character brief — what every reference must carry

**Egyptian-inspired, not Egyptian-themed.** Khepri should read as contemporary, analytical,
trustworthy, precise, editorial, and enterprise-ready — distinctive without becoming decorative,
comfortable with high information density, calm rather than flashy.

Egyptian influence enters through **geometry, rhythm, proportion, material inspiration, and
composition** — never through applied ornament. Concretely, as direction and constraint rather than
final values:

| Role | Direction | Current shipped instance |
|---|---|---|
| Surface | Warm neutral — limestone, papyrus | `--paper` `#fbfcfd` |
| Text | Dense, near-black ink — basalt | `--ink` `#202326` |
| Accent | One restrained cool family — lapis, faience | `--accent` `#1e5b96` |
| Type | Editorial, strong hierarchy, generous measure | `--text-*` scale, Noto Sans Arabic |
| Layout | Precise grid, architectural spacing | 4px ramp, `--shell-width` |
| Motif | Geometry and proportion only; restrained, never wallpaper | none shipped |

The shipped values are named as the **current instance** of each role, so the pack begins from a
real starting point rather than a blank canvas. They are not a ceiling under §16.1.

**Avoid, explicitly:** stereotypical pharaonic decoration · hieroglyphic wallpaper or borders ·
excessive gold · black-and-gold cliché styling · novelty Egyptian display fonts · any motif that
reduces readability or competes with data.

This brief feeds §16.2: every reference must carry this character, not merely resolve its listed
question.

### 16.1 Scope, and the override it carries

**Scope: the entire visual language** — composition, hierarchy, typography, density, spacing, asset
treatment, and interaction cues, across all twelve references below.

**This overrides `KHEPRI_DESIGN_LANGUAGE.md` §0**, which states "The shipped light token set is the
visual authority" and "No visual-world replacement is warranted," citing three agreeing sources. That
clause and this section cannot both govern.

**Recorded plainly rather than left implicit:** this is an owner decision taken on 2026-09-17, and
per Constitution Article II it becomes governing **only when this document is merged to `main`.**

**`DESIGN_LANGUAGE` §0 is corrected in the same change that creates this override**, not in a later
slice — §A.4's reconciliation rule applies to this document's own divergences first. The correction
sits under §0's "The visual authority is code that already ships" heading: it retains the three
sources' verdict as the historical record at `b19f365`/`65579bc`, marks it no longer the operative
restriction, and names this section as its successor. Corrected in place, never deleted, so a reader
arriving from an older note sees what changed.

**What the override does not reach:** it does not authorize a new typeface or icon family to bypass
the licence-plus-audited-digest process, an external font host or CDN (CSP-blocked), a dark palette
(an unmade product decision), or any change to governed facts, privacy, evidence, or isolation.

### 16.2 The twelve references

Each must communicate composition · hierarchy · typography · density · spacing · asset treatment ·
interaction cues.

| # | Reference | Must resolve |
|---|---|---|
| 1 | Welcome and journey entry | Entry hierarchy; how the specimen blocks read without becoming a second vocabulary |
| 2 | Upload | The drop zone as a ready state, not an empty one |
| 3 | Processing | Stage naming; the single permitted animation |
| 4 | Workspace overview | **The density floor (§E.4) made visible** |
| 5 | Analysis detail | Figure, scope, and evidence adjacency |
| 6 | Period comparison | Baseline versus comparand without hue-only encoding |
| 7 | Executive decision page | Four trust states, non-color differentiated |
| 8 | Evidence drawer | The product's densest surface |
| 9 | Refusal and insufficient data | **A refusal that reads as a result, not a crash** |
| 10 | Arabic RTL | A real Arabic surface — not a mirrored English screenshot |
| 11 | Narrow and mobile | What degrades and what does not |
| 12 | Dense analytical workspace | The density ceiling |

### 16.3 Binding status

**Future implementation must treat approved visual references as acceptance evidence, not as loose
inspiration.** A coding agent may adapt layout responsively but **may not replace the approved visual
language with its own interpretation.** Visual-language drift is a defect even where every test
passes.

---

## 17. Visual acceptance methodology

```
approved specification
  → approved visual reference
    → implementation
      → rendered screenshot
        → /impeccable critique
          → targeted corrections
            → /impeccable audit
              → /impeccable harden
                → /impeccable polish
                  → final visual acceptance
```

**An unchanged phase is not repeated without new implementation evidence.** Review compares
hierarchy · density · rhythm · typography · component behavior · responsive behavior · RTL · states ·
asset fidelity.

Pixel-perfect reproduction is not required where responsiveness demands adaptation. **Visual-language
drift is not acceptable.**

The mechanical detector runs **once**, after the change is finished, over the changed targets.

**The visual-regression half of this methodology is `U1-07` and is not authorized** (§18).

---

## 18. Implementation authority required

Determined from `governance/registry.yaml` and the roadmap at `6cea330`.

### 18.1 Authorized and implemented

| Item | Authority | Evidence |
|---|---|---|
| Primitive tokens and shell component layer (`U1-01`) | `RRA-012` active | `shell.css`; design language §4.11 |
| Data-display primitives (`U1-02`) | `RRA-012` active | `#350`; eight macros |
| Evidence drawer and metric detail (`U1-04`) | `RRA-012`, `RRA-013` active | `#352`, `#356`, `#358` |
| Decision workspace surfaces | `RCA-008` active | `D1-02` … `D1-10`, `D1-12` |
| Period comparison reachability | `RCA-009` active | `44d54a7` (`#470`) |

### 18.2 Specification-ready but implementation-blocked

| Item | Specified here | Blocker |
|---|---|---|
| Chart grammar (`U1-03`) | §8 | `RRA-012:229` excludes charting; `RRA-012:267` names `U1-03` **not** authorized; `RCA-008:161` says it needs its own authority |
| Global navigation and filter patterns (`U1-05`) | §D | `RRA-012:267` |
| Accessibility evidence (`U1-06`) | §11 | `RRA-012:267`; `RCA-008:161` |
| Visual regression (`U1-07`) | §17 | `RRA-012:267`; `RCA-008:161` |

### 18.3 Blocked on the owner

| Item | Nature |
|---|---|
| `RRA-010` journey-adoption reading | **OWNER DECISION, not yet taken.** Filed at `docs/superpowers/plans/2026-09-03-rra010-journey-adoption-reading.md`. It recommends no amendment; **the filing decides nothing, and no slice may act as though option A were chosen.** This document does not recommend an answer |
| §16's override of design language §0 | Governing on merge of this document (§16.1). **Not a follow-up task** — §0 is corrected in the same change |
| `DIRECTION_PROPOSAL` absorption | Merged `cdfa024` (`#369`), unabsorbed (§A.5 item 1) |
| Cross-surface `.skip-link` unification | **No active authority names the shell stylesheet.** `RRA-010:30` excludes `shell.css` and `shell-components.css` by name; §19 slice 2b is blocked until owner-authored authority covers them |

### 18.4 Minimum authority to enable the design-system work

**One successor specification** naming `src/khepri/rra/rendering/charts.py`,
`rendering/templates/_chart.svg.j2`, the shell stylesheets, and the affected test paths, and
authorizing `U1-03`, `U1-05`, `U1-06`, and `U1-07` — the four programs this document specifies and
cannot license.

**No new governance programme is proposed and no governance structure is redesigned.** `U1` already
exists in the roadmap; what it lacks is a registry entry. Standing constraint to respect: `W1`, `T1`,
`G2`, `G3`, and `U1` have **zero registry entries** — they are roadmap programs, not registered
authority.

---

## 19. Implementation slicing

Sequence adjusted to repository truth: foundations, typography, and the component layer **already
ship** and are not reopened.

| # | Slice | Authority | Note |
|---|---|---|---|
| 1 | Absorb `#369` into the design language | Docs | **§0's visual-authority correction is already discharged by this document's own change (§16.1); what remains of slice 1 is absorbing the merged proposal, which is a separate defect (§A.5 item 1)** |
| 2 | Unify the `.skip-link` mechanism on the **journey** side | `RRA-010` active — §73 authorizes "one skip-link mechanism" | Journey half only (§G.2) |
| 2b | Unify the **shell** side, or unify across both surfaces | **BLOCKED — no active authority** | `RRA-010:30`: `shell.css` and `shell-components.css` are "**outside this scope**". Needs authority naming the shell stylesheet |
| 3 | Collapse remaining raw font sizes onto the type scale — **journey only** (4 in `journey.css`) | `RRA-010` active | The 2 in `shell-components.css` are outside it (`RRA-010:30`) and ride slice 2b's authority |
| 4 | Navigation and filter patterns | **`U1-05` — blocked** | §18.2 |
| 5 | State grammar: the §13 matrix as components | `RCA-008` where in scope | Otherwise blocked |
| 6 | Chart grammar | **`U1-03` — blocked** | §8 |
| 7 | Apply §F contracts to shipped surfaces | Per surface | Incremental |
| 8 | RTL and responsive hardening | `RRA-010` partial | §9, §10 |
| 9 | Accessibility evidence | **`U1-06` — blocked** | §11 |
| 10 | Visual regression | **`U1-07` — blocked** | §17 |
| 11 | Final polish against the reference pack | After §16 is approved | §17 |

**Slices 4, 6, 9, and 10 cannot start until §18.4's authority exists.** No slice is implemented by
this document.

---

## 20. Quality bar — self-assessment

Could a competent frontend engineer implement Khepri from this specification without inventing:

| Question | Answer | Where |
|---|---|---|
| Hierarchy? | No invention needed | §E.1–E.4 |
| Navigation? | No | §D |
| Responsive behavior? | No | §10 |
| Component behavior? | No | §G.2 |
| Error and refusal behavior? | No | §13, §F |
| SVG and image rules? | No | §7 |
| Chart behavior? | No — blocked, not unspecified | §8 |
| RTL behavior? | No | §9 |
| Accessibility behavior? | No | §11 |
| Visual acceptance rules? | **Partly — pending the §16 pack** | §16.0, §16.3, §17 |

The one deliberate gap is §16's pack, which is a reviewed-asset dependency by design.

---

## 21. Validation

Run against this document at `6cea330`, 2026-09-17:

| Command | Result |
|---|---|
| `uv run khepri-gov validate` | `Governance validation passed.` (exit 0) |
| `uv run ruff check .` | `All checks passed!` (exit 0) |
| `git diff --check` | clean (exit 0) |
| `uv run pytest tests/test_governance_validator.py tests/test_rca001_status_consistency.py -q` | **40 passed** |

**Full product suite not run** — this change is docs-only and touches no executable code.

---

## 22. Maintaining this document

- **A new surface enters §C and §F in the slice that implements it**, never before (`FR-049`).
- **A contradiction with a predecessor is corrected in place in both documents**, never deleted
  (§A.4).
- **A blocked item leaves §18.2 only when a registry entry exists** — not when a plan is filed.
- Re-measure §G.1's computed contrast whenever type or color changes. The 0.22 margin has no room.
