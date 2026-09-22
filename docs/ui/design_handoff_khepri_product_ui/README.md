> ## Repository authority notice
>
> **This is supplied design and handoff material. It is not implementation authority.**
>
> It was imported verbatim as the owner supplied it, and its content below this notice is
> unmodified. It records an approved *visual direction*. It does not, and cannot, authorize any
> change to product code.
>
> **Any list of source files in this package — notably §5 "Files expected to change" and §6
> "Registration (mandatory)" — is blast-radius and design guidance only.** Where such a list names
> a repository path, it is describing where the design is expected to land, not granting permission
> to edit it. Phrases in this package such as "the only permitted edits", "mandatory", or "expected
> to change" carry no authority in this repository.
>
> **Active specifications and their `§Scope` always govern what product code may actually change**
> (Constitution Article IV; `governance/registry.yaml` is authoritative for artifact state). Where
> this package and an active specification disagree about whether a file may be touched, the
> specification governs and this package yields.
>
> Two concrete instances, true at import (2026-09-22), recorded so the conflict is not discovered
> mid-slice:
>
> - This package states that allow-list additions are "the only permitted edits" to
>   `src/khepri/rra/journey/routes.py` and `src/khepri/runtime/shell_api.py`. Active `RCA-010`
>   §Scope places `shell_api.py` **and every other `src/khepri/runtime/*.py` module** under
>   *Not in scope*. `RCA-010` governs; those edits are **not** authorized by this package.
> - §5 additionally names `journey.css`, the journey templates and `rendering/html.py`. Those are
>   `RRA-010`'s and `RRA-015`'s surfaces, not `RCA-010`'s. Each needs its own active specification
>   naming it before any slice touches it.
>
> Importing this package starts no implementation. Product code changes only under an
> active specification naming the files, in bounded, independently verifiable slices.
>
> The palette recorded here as §8 is transcribed into `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md`
> §16.5, which is the citable record for those token values.

# Khepri Product UI — implementation handoff (FINAL)

Approved design → `Kemetra/Khepri`. Six surfaces plus the shared visual system.
Place this folder in the repo at `docs/ui/design_handoff_khepri_product_ui/`.

**Method: CONTROLLED VISUAL REPLACEMENT.** Behavior, routes, contracts, read models and tests are
preserved. Only the visible presentation is replaced, one screen at a time. Old presentation for a
screen is removed only after its replacement passes validation. This is not a redesign of the
product — it is a restyle of what already ships.

Verified against `main` at tree `bb497d9a30fe`, 2026-09-21.

**Contents**
1. Package contents · 2. Authority order · 3. Governed vs. visual ·
4. Screen → route map · 5. Files expected to change · 6. Asset inventory & registration ·
7. Anti-references · 8. Design tokens · 9. Typography · 10. Shell · 11. Components ·
12. States · 13. Responsive · 14. RTL / Arabic · 15. Accessibility · 16. Gates ·
17. Execution order · 18. Forbidden scope · 19. Final report · 20. Completeness

---

## 1. Package contents

```
docs/ui/design_handoff_khepri_product_ui/
  README.md                       this file — the implementation contract
  IMPLEMENTATION_PROMPT.md        the executable brief (paste into Claude Code)
  design-files/
    Khepri Product UI.dc.html     VISUAL SOURCE OF TRUTH — six screens, LTR+RTL, real states
    Khepri Handoff.dc.html        rule set: tokens, components, states, responsive, RTL, inventory
    Khepri Design Language.dc.html  palette / type / motif rationale (read once, for intent)
    support.js                    runtime the .dc.html files need in a browser — NOT for the repo
    src/assets/khepri-hero.png    hero artwork at the path the prototypes reference
  references/
    01-home.png 02-upload.png 03-review.png
    04-processing.png 05-insights.png 06-report.png   approved screen renders
    icons.png                     approved icon set — stroke language reference
    motifs.png                    approved Egyptian motifs — permitted placements only
  assets/
    khepri-hero.png               1400×900 PNG — the production source artwork
```

Open any `.dc.html` from inside `design-files/` in a browser; the sibling `support.js` and
`src/assets/` are what it expects. **Do not port prototype markup into the repo** — the prototypes
are React-flavored HTML; Khepri's frontend is server-rendered Jinja2 with hand-authored CSS.

Fidelity is **high**: final colors, type, spacing, states, interaction. Match the values exactly.
Where a repository constraint makes an exact match unsafe, implement the nearest faithful result
and report the difference. Do not reinterpret.

---

## 2. Authority order

1. Existing Khepri product semantics, route contracts, read models and repository invariants
2. `design-files/Khepri Product UI.dc.html` — visual appearance
3. `design-files/Khepri Handoff.dc.html` — implementation rules
4. Existing frontend architecture, where it does not conflict with the approved visual design

Prototype content is illustrative. Figures, org names, filenames, vendor names, avatars and
percentages in the prototypes are **not** canonical business data and must not become fixtures,
seeds or defaults. Never add product functionality to make a placeholder real.

---

## 3. Governed product semantics vs. visual design instructions

The single most important distinction in this package.

**Governed — never changed by this work.** Route shapes and path parameters. Read models
(`ExecutiveOverviewView`, `OverviewReading`, decision cards, tombstones). Offers/entitlement gating
in `shell_frame.organization_frame()`. Refusal and unavailable-surface behavior
(`shell_api.py::_UNAVAILABLE_TAIL`, `test_r802`). Which nav destinations exist and when
(`FR-121`, `RCA-002 FR-049`: a link never ships ahead of a complete surface). Copy dictionaries in
`journey/copy.py` and `shell_copy.py`. Empty-rule semantics. State grammar and state contracts
(`test_r808`, `test_r809`). Language/direction derivation. Asset allow-lists as a mechanism.

**Visual — this work replaces it.** Color values, type scale and faces, spacing, radii, elevation,
borders, icon stroke language, component geometry, layout and grid, hero imagery and its cropping,
chart styling, motion, breakpoint layout behavior, and the visible presentation of every state.

Rule of thumb: if changing it would alter what the product *says, offers or permits*, it is
governed — stop and report. If it only changes how the same information *looks*, it is in scope.

Prototype labels do not override route contracts. Where the design says "Home" and the product says
"Overview", the product wins for naming, URLs and copy; the design wins for appearance.

---

## 4. Screen → route map (owner-approved, final)

| # | Prototype screen | Route | Handler / template | Stylesheet | Action |
|---|---|---|---|---|---|
| 01 | Home / Dashboard | `/app/{language}/{organization}/overview` | `runtime/shell_api.py` → `shell_templates/overview.html.j2` (extends `shell.html.j2`) | `shell_assets/workspace.css`, `journey/assets/shell.css`, `shell-components.css` | Restyle existing Overview surface |
| 02 | Upload / New Analysis | `/beta/{language}/upload` | `rra/journey/routes.py` → `journey/templates/upload.html.j2` | `journey/assets/journey.css` | Restyle |
| 03 | Review & Map | `/beta/{language}/review` | `routes.py` → `review.html.j2` | `journey.css` | Restyle |
| 04 | Analysis in Progress | `/beta/{language}/processing` | `routes.py` → `processing.html.j2` | `journey.css` | Restyle |
| 05 | Insights / Results | `/app/{language}/{organization}/analyses` and analysis detail (`surface_path` = `/{organization_id}/analyses/{run_id}`) | `shell_api.py` → `analyses.html.j2`, `analysis.html.j2`; supporting `shell_analysis.py`, `shell_decisions.py` (`decision.html.j2`) | `workspace.css`, `shell-components.css` | Restyle where semantically appropriate |
| 06 | Report / Report Viewer | `/beta/{language}/report` + generated report HTML | `routes.py` → `report.html.j2`; `rra/rendering/html.py` | `journey.css`, `rendering/templates/report.css`, `report.print.css` | Restyle |

Rules that follow from this map:

* **Do not create routes** to reproduce prototype naming. No `/home`, no `/insights`.
* `SHELL_PREFIX = "/app"` and the `/beta` journey prefix both stay exactly as they are.
* Screen 05 maps onto an experience that spans list + detail + decision surfaces. Apply the
  approved visual system to all three; do not merge them into one page to match the prototype's
  single-screen composition.
* Screen 01's prototype KPI strip must bind to whatever `read_overview` already returns. If the
  prototype shows a figure the read model does not carry, omit it and report — do not invent it.

### Shell strategy (owner-approved, final)

The `/beta` journey shell and the `/app` workspace shell are **not** unified in this work.
Restyle both inside their current architecture so they share one visual language. Architectural
unification is explicitly out of scope.

Practically: token definitions and shared component CSS live in `journey/assets/shell.css` +
`shell-components.css`, which `shell_api.py::_ASSETS` already serves to `/app/assets/` and
`legal_api.py::_ASSETS` already serves to the legal pages. That existing sharing mechanism is the
seam to use — extend it, do not replace it. `journey.css` may `@import`-free duplicate the token
block if cross-serving a file would require a new route; prefer reuse, and if you must duplicate,
duplicate values, never diverge them.

---

## 5. Files expected to change

Everything below already exists. This list is the expected blast radius; anything outside it needs
a justification in the final report.

**Shared visual system**
```
src/khepri/rra/journey/assets/shell.css              tokens, shell frame, sidenav, topbar
src/khepri/rra/journey/assets/shell-components.css   buttons, cards, badges, tabs, tables, fields,
                                                     steppers, banners, charts, @font-face
src/khepri/runtime/shell_assets/workspace.css        workspace surface styling
```

**Journey surfaces (02, 03, 04, 06)**
```
src/khepri/rra/journey/assets/journey.css
src/khepri/rra/journey/templates/base.html.j2        shell markup for /beta
src/khepri/rra/journey/templates/upload.html.j2
src/khepri/rra/journey/templates/review.html.j2
src/khepri/rra/journey/templates/processing.html.j2
src/khepri/rra/journey/templates/report.html.j2
src/khepri/rra/journey/templates/expired.html.j2     keep consistent with the restyled shell
src/khepri/rra/journey/routes.py                     _ASSETS registration ONLY (see §6)
```

**Workspace surfaces (01, 05)**
```
src/khepri/runtime/shell_templates/shell.html.j2     shell markup for /app
src/khepri/runtime/shell_templates/overview.html.j2
src/khepri/runtime/shell_templates/analyses.html.j2
src/khepri/runtime/shell_templates/analysis.html.j2
src/khepri/runtime/shell_templates/decision.html.j2
src/khepri/runtime/shell_templates/_decision_cards.html.j2
src/khepri/runtime/shell_templates/_decision_sections.html.j2
src/khepri/runtime/shell_api.py                      _ASSETS registration ONLY (see §6)
```

**Report rendering (06)**
```
src/khepri/rra/rendering/templates/report.css
src/khepri/rra/rendering/templates/report.print.css
src/khepri/rra/rendering/html.py                     class hooks only, if markup must change
```

**New files (only these)**
```
src/khepri/rra/journey/assets/khepri-hero.jpg        + .webp, + @2x variants
docs/ui/design_handoff_khepri_product_ui/**          this package
```

**Touch only if a gate forces it, and say so:** `tests/test_r801`, `test_r807`, `test_r808`,
`test_r809`, `test_r810`, `test_r811`, `test_r812`, `test_rca011_*`, `test_rra010_*`,
`test_rra015_*` — see §16.

**Do not touch:** `journey/copy.py`, `shell_copy.py`, `journey/state.py`, `journey/security.py`,
`shell_frame.py`, `shell_workspace.py`, `rca/workspace/**`, `rra/bundle.py`, any schema/migration,
`pyproject.toml`, lockfiles, `.github/**`, `runtime/landing_*`, `docs/product/**`.

Editing `decision_print.html.j2` and `report.print.css` is in scope only to keep print output
consistent with the restyle. Print is governed output (`FR-159` — print projects the same read
model); never change what it contains.

---

## 6. Asset inventory and registration

### Inventory

| Asset | Source in package | Destination | Notes |
|---|---|---|---|
| Hero artwork | `assets/khepri-hero.png` (1400×900 PNG, 2.3 MB) | `src/khepri/rra/journey/assets/` | Ship compressed derivatives, not the PNG: `khepri-hero.jpg` (~1400px, q80), `khepri-hero@2x.jpg`, `khepri-hero.webp` (+ `@2x`) |
| Noto Sans Arabic (arabic + latin woff2) | already vendored | `src/khepri/rra/rendering/typefaces/` | No change. Served to `/beta/assets/` via `routes.py::_TYPEFACE_ASSETS` (from `load_report_fonts()`) and to `/app/assets/` via `shell_api.py` |
| Icons | `references/icons.png` | inline SVG in templates | Reference only — author as inline SVG, do not ship the PNG |
| Motifs | `references/motifs.png` | inline SVG | Reference only; permitted placements in §11 |
| Avatars, vendor logos | not supplied | — | Prototype placeholders. Use existing repo assets or initials; **do not draw them** |

### Registration (mandatory)

Both shells serve assets from explicit allow-lists. A file not listed returns 404.

* **`src/khepri/rra/journey/routes.py::_ASSETS`** — currently `journey.css`, `common.js`,
  `upload.js`, `review.js`, `processing.js`, `report.js`. Add each new hero derivative with its
  media type, e.g. `"khepri-hero.jpg": "image/jpeg"`, `"khepri-hero.webp": "image/webp"`. Fonts go
  through `_TYPEFACE_ASSETS`, not `_ASSETS`.
* **`src/khepri/runtime/shell_api.py::_ASSETS`** — currently maps `shell.css` and
  `shell-components.css` to `khepri.rra.journey/assets`, and `workspace.css` to
  `khepri.runtime/shell_assets`. Add hero derivatives here too if `/app` surfaces reference them.
  Entries are `(package, directory, media_type)` tuples — follow the existing shape.
* `runtime/legal_api.py::_ASSETS` also serves `shell.css` / `shell-components.css`. Restyling those
  two files changes the legal pages. Check them; they must not break.

These allow-list additions are the **only** permitted edits to `routes.py` and `shell_api.py`.

### Artwork policy

The monument, sun disc, sky and reflecting pool are supplied artwork. Never redrawn — no CSS
drawing, no div compositions, no generated SVG, no gradient stand-ins. Do not filter, recolor,
rotate or mirror the image. Crop only, via `object-fit: cover` + `object-position`. Legibility
comes from a scrim over the image, never from dimming the artwork.

| Screen | Placement | `object-position` | Scrim |
|---|---|---|---|
| 01 Home | full-bleed hero band 238px, ground `#F6EDDF` | `62% 46%` | ivory 90° wash → transparent at 74% |
| 02 Upload | right rail promo card 270px, radius 14, ground `#0E1A24` | `50% 50%` | navy 180°, .72 → .25 → .88 |
| 03 Review | hero band 170px | `70% 40%` | ivory wash → transparent at 80% |
| 04 Processing | hero band 186px | `66% 44%` | ivory wash → transparent at 78% |
| 05 Insights | hero band 210px, actions top-trailing | `64% 46%` | ivory wash → transparent at 76% |
| 06 Report | cover panel right of a 250px masthead column | `50% 46%` | paper wash 90°, opaque only to 22% |

`loading="eager"` + `fetchpriority="high"` above the fold, `loading="lazy"` elsewhere. Alt text:
"Khepri monument at sunrise." (Arabic equivalent via the existing copy mechanism — add the key the
same way neighboring strings are added, or reuse an existing one; do not hardcode Arabic in a
template.) Keep the solid ground color behind the image so headlines are legible before it decodes.

Charts, tables, text and product UI are **never** rasterized.

---

## 7. Anti-references — explicitly NOT authoritative

Ignore these for this work. They are earlier or adjacent explorations and following them will
produce the wrong result:

* `Khepri Monumental Mockup.dc.html`, `Khepri Console.dc.html`,
  `Khepri Findings Patterns.dc.html` (design project) — superseded explorations.
* `docs/ui/design_handoff_khepri/` in the repo — the **previous** handoff round (journey screens
  only). Not superseded as a record, but not the target for this work. Where the two conflict, this
  package wins.
* `docs/product/concepts/landing/` and `runtime/landing_assets/landing.css` — the marketing landing
  wall. Different register (heavier Egyptian ornament). Do not import its motifs into product UI.
* The prototypes' demo nav strip under the topbar — scaffolding, omit it.
* Any prototype copy, number, filename, org name or logo — illustrative only.
* Generic SaaS conventions: purple/blue gradients, nested cards, rounded icon tiles everywhere,
  decorative motifs on ordinary controls, reduced data density, per-page visual reinterpretation.

---

## 8. Design tokens

CSS custom properties on `:root` in `shell.css`. No ad-hoc hex values in components.

**Navy — chrome & ink** `navy-900 #101C26` · `navy-950 #0B1017` · `ink #16212B` ·
`ink-muted #55616C` · `ink-secondary #6B7580` · `ink-tertiary #98A0A8` · `nav-label #A9B2B9` ·
`ink-disabled #B2B7BC`

**Gold — brand & primary** `gold-400 #D5AE63` · `gold-500 #C9A45C` · `gold-600 #B98C39` ·
`gold-link #8C6B22` · `gold-eyebrow #9A7B34` · `gold-ink #7A5A17` · `gold-tint #F6EBD6` ·
`gold-border #E3CE9F`

**Ivory / sand — surfaces** `surface-card #FFFFFF` · `surface-canvas #FBF9F6` ·
`surface-page #E9E3DA` · `surface-sand #F4EEE4` · `hero-ground #F6EDDF` · `border-card #EBE5DC` ·
`border-inner / track #EFE9E0` · `border-strong #DED7CC`

**Status triplets**

| Status | Ink | Fill | Border / bar |
|---|---|---|---|
| Success | `#27724F` · `#2E7D57` | `#E7F2EB` · `#E9F3EC` | `#D5E5DA` / bar `#46875F` |
| Warning | `#7A5A17` · `#9A7327` | `#FAEEDA` · `#FDF7EA` | `#F0E1C2` / dot `#D9922E` |
| Error | `#B0392F` | `#FBE9E7` · `#FEF7F6` | `#F2DAD6` / bar `#C0433A` |
| Info | `#3C6089` · `#4E5F70` | `#F3F7FB` | `#CFDCE8` |

Row tints: warning `#FDF9F0`, error `#FEF8F7`.

**Charts** in order `#33506D`, `#5E7E9E`, `#C9A45C`, `#8FB4D4`, `#E0D3BA`. Neutral bars `#CBD4DC`;
the current period is always gold. Gridlines 1px `#EFE9E0`.

**Spacing** 4 · 6 · 8 · 10 · 12 · 14 · 18 · 22 · 24 · 26 · 30 · 34 · 40. Card gutters 14, card
padding 16–18 / 18–20, screen padding 24, hero padding 18–28.

**Radii** frame 16 · card 12 · inner row 10 · control 8–9 · pill 999 · report sheet 0.

**Elevation** cards are flat, 1px border only. Three shadows exist in the entire system: app frame
`0 40px 80px -52px rgba(18,28,38,.55)`, report sheet `0 30px 60px -44px rgba(18,28,38,.6)`, primary
button `0 10px 22px -12px rgba(140,104,30,.9)`.

**Hit targets** buttons and nav items 46px, secondary controls 40–42px, table controls 38px, never
below 44px at touch breakpoints.

`test_r801_shell_tokens.py` asserts the token vocabulary. Read it before renaming anything.

---

## 9. Typography (owner-approved, final)

**Do not introduce Source Serif 4.** No new font dependency, no external font CDN, no
`pyproject.toml` change. Implement the display hierarchy with the **currently vendored/approved
stack** — Noto Sans Arabic (`src/khepri/rra/rendering/typefaces/`, already served to both
`/beta/assets/` and `/app/assets/`) plus the system stacks the repo already declares.
Source Serif 4 may only arrive later through the repository's font asset/approval path.

Consequence: the serif *scale, weight and rhythm* below are authoritative; the serif *face* is not
available. Render display roles in the approved local stack at the specified sizes, line-heights
and weights, and preserve the contrast between display and UI text through size, weight and
tracking. Note this substitution in the final report as a known visual difference from the
prototype. Do not approximate a serif with a web-font fallback chain that would hit a CDN.

Root 16px.

| Role | Size / line-height / weight |
|---|---|
| display-xl | 3rem / 1.05 / 600 — report cover |
| display-l | 2.5rem / 1.1 / 500 — Home hero |
| page-title | 2–2.1rem / 1.12 / 500 — screens 02–05 |
| metric-l | 1.5–1.62rem / 600 — KPI value |
| metric-s | 1.3rem / 600 — summary stat |
| card-title | 1rem / 600 |
| body | .92–.95rem / 1.6–1.7 |
| body-s | .84–.88rem — rows, tables |
| caption | .74–.8rem, `ink-tertiary` |
| eyebrow | .6–.68rem, .24–.34em tracking, uppercase, monospace stack |

One display-size heading per screen. Display roles never below 1.3rem (sole exception: the report
pull quote at 1.06rem italic). Body copy caps at 78ch, hero copy 46–62ch. `text-wrap: pretty` on
display headings. UI labels, table cells and buttons never use the display treatment.

`test_rra010_journey_type_scale.py`, `test_rca011_shell_font_load.py` and
`test_rca011_shell_typeface.py` all constrain this area. Read all three before changing a font
declaration.

---

## 10. App shell

Outer page `#E9E3DA`, 26px padding. Frame: max-width 1620px, radius 16, border `#DED7CC`, grid
`238px / 1fr`.

* **SideNav** — navy gradient `#101C26 → #0B1017`, logo lockup, nav items, quote card pinned bottom
  (`margin-top: auto`). Nav item 46px min-height, radius 10, 13px gap, 18px icon. Active = gold left
  bar `inset 3px 0 0 #C9A45C` + `linear-gradient(90deg, rgba(201,164,92,.26), rgba(201,164,92,.02))`
  with gold icon stroke. Inactive hover `rgba(255,255,255,.06)`, label `#DFE3E7`.
* **TopBar** — white, 1px bottom border, 12/24 padding: search pill, language switch, bell, user chip.
* **Content** — `#FBF9F6`, optional hero band, then a padded card grid.

Nav destinations come from `shell_frame.organization_frame()` and are Offers-gated. Render what the
frame yields — never hardcode the prototype's nav list, and never ship a link to a surface that is
not offered.

Active-state rules: Upload and Review both mark *New Analysis* active; Insights and Report both mark
*Insights* active. Breadcrumbs live in the hero band, not the topbar; Processing and Report use a
back link. One primary action per screen — top-trailing in the hero band (Insights) or in a bottom
action row (Upload, Review). Processing has no primary action; it is read-only until complete.

The `/beta` shell (`base.html.j2`) and `/app` shell (`shell.html.j2`) each implement this
independently. Same tokens, same component classes, same measurements — two files.

---

## 11. Components

Full specimens with production values: `design-files/Khepri Handoff.dc.html` §06.

**Shell (4)** AppFrame · SideNav (+NavItem) · TopBar (+SearchPill, LanguageSwitch, NotificationBell,
UserChip) · BrandQuoteCard
**Headers (4)** HeroBand `light`/`dark` · Breadcrumb · BackLink · Eyebrow
**Actions (5)** Button `primary`/`secondary`/`secondary-sm`/`toolbar-xs`/`tonal` · TextLink ·
ActionRow · QuickActionRow · ZoomControl
**Containers (6)** Card · KpiCard `gold`/`blue`/`report` · ListRow `default`/`active`/`error`/`muted` ·
SuggestionRow · ReportSheet · PageRail
**Navigation (4)** Tabs · SegmentedControl · Pagination · Stepper `inline-4`/`process-5`
**Data entry (7)** SearchPill · Select · Textarea + CharCount · TagInput · Checkbox · Dropzone ·
SourceTile
**Data display (9)** Table · ConfidenceMeter · Badge (7) · FileTypeChip (4) · MetaChip · DetailList ·
SummaryGrid · Timeline · ActivityList
**Charts (5)** LineAreaChart · BarChart · DonutChart + LegendList · DonutGauge · RankedBarList
**Feedback (8)** Banner `info`/`success` · Callout `help`/`warning` · EmptyState · SkeletonRow ·
Spinner · ProgressBar `determinate`/`indeterminate`/`error` · TaskItem · InsightStreamCard
**Brand (4)** Logo lockup · MottoColumn · Quote · TrustFooter

Key values:

* **Button primary** — gradient `#D5AE63 → #B98C39`, ink `#1B1405`, 46px, radius 10, hover
  `filter: brightness(1.05)`. Secondary hover raises border to `#C9A45C`. Disabled: surface
  `#FAF8F5`, border `#F0ECE5`, ink `#B2B7BC`, `cursor: not-allowed`, plus a `title` saying why.
* **Table** — header `#F7F3EC`, 600, ink `#55616C`, `text-align: start` (never `left`). Cells 10/12,
  divider `#F3EEE6`, no vertical rules. Confidence meter 74×6, radius 999, fill follows status.
  The 7-column mapping table sits in `overflow-x: auto` with `min-width: 900px`.
* **Tabs** — 2px `#B98C39` underline on active only, 22px gap, inactive `#6B7580`.
* **Segmented** — track `#F4EFE7`, selected chip `#E8D6B0` with ink `#4A3712`.
* **Fields** — surface `#FDFBF8`, border `#E6E0D6`, focus border `#C9A45C`, no glow. Warning border
  `#E3CE9F` on `#FFFCF5`; error `#EBC7C2` on `#FFFBFA`. Helper text .74rem under the control.
* **Stepper** — node 28px inline / 32px on Processing. Complete = solid gold-600 + ✓; current = gold
  ring `0 0 0 4–5px rgba(201,164,92,.18–.22)`; upcoming `#EFE9E0` with `#8A929B`. Connector turns
  gold only behind completed steps.
* **Icons** — one family: `viewBox 0 0 24 24`, `fill: none`, stroke 1.4–1.8 (1.6 default), round
  joins, no filled shapes except the logo sun disc and status dots. Sizes 14 / 16–17 / 18 / 19–21 /
  22 / 30–54. See `references/icons.png`.
* **Motifs** — sun disc, pyramid, horizon rings appear **only** in the logo lockup, the sidebar quote
  card and report chrome. Never on buttons, inputs, rows, badges or tables. See
  `references/motifs.png`.

Status is data-driven: one `status` enum (`success | warning | error | info | pending`) drives
badge, row tint, meter fill and icon together. Never hardcode a tint on a row. The enum must map to
the state grammar `test_r808` already enforces — read that test before naming classes.

---

## 12. States

| State | Treatment |
|---|---|
| Loading | Skeleton rows keep the real card's geometry at `opacity: .6`; bars `#EDE7DE` / `#F2EDE5` pulsing 1.5s. Inline work uses the 10–22px gold ring spinner. Never a full-page blocking spinner. |
| Processing | Stepper + task list + determinate or indeterminate bar; read-only until complete. |
| Empty | Dashed `#DED7CC` container, gold outline icon, title, one explanatory line, one action. No illustration. Empty **copy** comes from the governed empty-rule, not from the prototype. |
| Success | Three tiers — badge, inline line, banner. Never a toast overlay. |
| Warning | Always names a recovery action. Row-level warnings tint `#FDF9F0` + Needs Review badge. |
| Error | States cause, not blame; always paired with Retry plus a dismissal. Failed progress bars stay visible at their stop point in `#C0433A`. |
| Disabled | Keeps its shape; always says why in the secondary line or a `title`. Opacity is never used to disable — use the disabled tokens. |
| Pending | `#F1ECE4` fill, `#8A929B` ink badge; stepper node `#EFE9E0`. |

Connect real states where they exist; never fake a state the application cannot enter, and never
add a state path that violates `test_r809`'s contracts.

Animation is exactly three keyframes: `khSpin` 900ms linear, `khBar` 1.6s ease-in-out, `khPulse`
1.5s ease-in-out. Transitions 140ms, background and color only. `prefers-reduced-motion` freezes
all three.

---

## 13. Responsive

Desktop ≥1280 · tablet 768–1279 · mobile <768. Most grids use `auto-fit / minmax` and need no query.

| Element | Desktop | Tablet | Mobile |
|---|---|---|---|
| Shell | 238px rail + content, 26px page padding, radius 16 | rail → 72px icon-only, labels on hover | rail → drawer behind hamburger; frame edge-to-edge, radius 0, padding 0 |
| Topbar | search 520px + language + bell + user chip | search flexes; role line hidden | search → icon expanding full-width; chip → avatar |
| Hero band | copy + 210px motto column | motto hidden; min-height −20% | image becomes a 140px band above copy; scrim 180°; display steps down one level |
| KPI strip | 4 across | 2 × 2 | 1 per row, icon tile 38px |
| Home body | `1.45fr / 1fr / .95fr` | chart full width, then two columns | single column: chart → recent → quick actions → reports → team |
| Insights | `1fr` + 360px rail | rail drops below charts | tabs scroll horizontally; charts stack; donut legend under ring |
| Stepper | horizontal with connectors | horizontal, captions truncate | vertical list, or "Step 3 of 5" + current label |
| Mapping table | all 7 columns | horizontal scroll, source column sticky | one card per column mapping |
| Action row | inline, trailing-aligned | inline, wraps | sticky bottom bar, primary full-width, 48px targets |
| Report | 186px page rail + 940px sheet | rail → horizontal page strip; sheet fluid | sheet full width; toolbar keeps back, zoom, Export |

Hero min-heights: Home 238 · Insights 210 · Processing 186 · Review 170.

Verify at 1440, 1024 and 390. `test_r810_shell_responsive_rtl.py` covers this area.

---

## 14. RTL and Arabic

Direction is already derived per request — `journey/routes.py` sets `"rtl" if language == "ar" else
"ltr"` and passes it into every template, and the workspace shell carries its own language
handling. **Extend that. Do not build a second layout, and do not duplicate templates per
direction.**

* One `dir` switch on the app root: `dir="rtl"` + `lang="ar"`. Shell mirrors — rail to the right,
  chevrons and arrows flip, breadcrumbs and steppers reverse.
* Logical properties only: `margin-inline-*`, `padding-inline`, `border-inline-start`,
  `inset-inline-end`, `text-align: start/end`. Do not introduce `left`/`right`.
* Arabic UI in Noto Sans Arabic 400/500/600/700; body line-height rises to 1.8–1.85. Arabic uses no
  separate display face — Noto Sans Arabic 600 at the same display sizes.
* Numerals, currency, percentages, dates and file sizes stay Western/LTR: wrap each in a
  `dir="ltr"` span so `$482M` and `+18%` do not reorder. Mixed-direction labels (English filenames
  in an Arabic UI) get `unicode-bidi: plaintext`.
* Hero artwork is **not** mirrored. Only the scrim flips (`to inline-end`, or a `[dir="rtl"]`
  override) and `object-position` mirrors to `38% 46%`.
* Charts: bar and line axes mirror (time flows right → left); donut keeps its rotation, legend
  mirrors. Progress bars fill from the inline start.
* All Arabic strings come from the existing copy dictionaries (`journey/copy.py`, `shell_copy.py`).
  Never hardcode Arabic in a template or stylesheet.

Verify every surface in `dir="ltr" lang="en"` and `dir="rtl" lang="ar"`.

---

## 15. Accessibility

Preserve or improve — `test_r811_shell_accessibility.py`, `test_rra_journey_accessibility.py` and
`test_rra015_report_accessibility.py` already assert much of this:

* Language switch is a labelled control with `aria-pressed`.
* Every progress element: `role="progressbar"` with `aria-valuenow` / `aria-valuemin` /
  `aria-valuemax`; `aria-busy` when indeterminate.
* Processing announces task changes through an `aria-live="polite"` region.
* Focus ring: gold border plus 2px `rgba(201,164,92,.35)` outline, offset 2px. Always visible, never
  removed. `test_rra010_journey_focus.py` covers journey focus behavior.
* Semantic controls: real `button`, `a`, `label`; `table` headers with `scope`; heading order intact.
* Keyboard order matches visual order — including after RTL mirroring and after the mobile rail
  becomes a drawer (trap and restore focus in the drawer).
* Contrast ≥4.5:1 for body text, ≥3:1 for display-scale type. Check gold-on-ivory combinations
  specifically: use `gold-ink #7A5A17` or `gold-link #8C6B22` for text, never `gold-400`/`gold-500`.
* Touch targets ≥44px at touch breakpoints.
* `prefers-reduced-motion` honored by all three keyframes and all transitions.

---

## 16. Gates that must remain green

```
tests/test_r801_shell_tokens.py                 token vocabulary
tests/test_r802_shell_unavailable_surface.py    unavailable-surface behavior (governed)
tests/test_r806_journey_entry.py                journey entry
tests/test_r807_shell_quality.py                shell quality rules
tests/test_r808_shell_state_grammar.py          state grammar
tests/test_r809_shell_state_contracts.py        state contracts
tests/test_r810_shell_responsive_rtl.py         responsive + RTL
tests/test_r811_shell_accessibility.py          accessibility
tests/test_r812_shell_visual_regression.py      visual regression — baselines
tests/test_rca011_shell_font_load.py            font loading
tests/test_rca011_shell_typeface.py             typeface
tests/test_rra010_journey_type_scale.py         journey type scale
tests/test_rra010_journey_focus.py              focus behavior
tests/test_rra015_report_accessibility.py       report accessibility
tests/test_rra015_report_visual_regression.py   report visual regression — baselines
tests/test_rra_journey_pages.py                 page rendering
tests/test_rra_journey_browser.py               browser-level checks
tests/test_rra_journey_accessibility.py         journey accessibility
tests/test_rra_journey_upload.py / _review.py / _processing.py / _report.py
tests/test_local_journey.py                     local end-to-end
tests/test_rra003_journey_source_contract.py    source contract (governed)
```

Plus whatever lint/typecheck/build gates the repo already runs (`pyproject.toml` config, `Makefile`
or CI definition — read, do not modify).

Several of these assert literal token values and type-scale numbers. Updating an assertion because
a *visual value changed by approved design* is expected. Updating one because the implementation is
inconvenient is not. **Read each assertion's docstring first** — this repo encodes product rules in
test prose. Any test whose *intent* you would change: stop and report instead.

Visual regression: `test_r812` and `test_rra015` hold baselines. Regenerate them deliberately,
screen by screen, and state in the final report exactly which baselines moved and why. Never
regenerate the whole baseline set in one sweep.

---

## 17. Execution order — controlled visual replacement

Each numbered step is a checkpoint. **Do not start the next step until the current one renders
correctly, passes its gates in both directions and at all three breakpoints, and its superseded
presentation has been removed.** Leaving old and new presentation coexisting past a checkpoint is
the failure mode this method exists to prevent.

**Phase A — shared system (no screen changes visible yet)**
1. Tokens as CSS custom properties in `shell.css`. Gate: `test_r801`.
2. Typography scale + font loading with the vendored stack (§9). Gates: `test_rca011_*`,
   `test_rra010_journey_type_scale`.
3. Shell chrome: AppFrame, SideNav, TopBar — in `base.html.j2` and `shell.html.j2` independently.
   Gates: `test_r807`, `test_r810`, `test_r811`.
4. Primitives in `shell-components.css`: buttons, cards, badges, form controls, tabs, steppers,
   tables, banners, chart styling, the three keyframes. Gates: `test_r808`, `test_r809`.
   Check the legal pages still render — they consume these two stylesheets.

**Phase B — screens, in this order**
5. **02 Upload** — simplest full composition; proves the system. `upload.html.j2`, `journey.css`.
6. **03 Review & Map** — the dense table, confidence meters, mapping states. `review.html.j2`.
7. **04 Processing** — stepper, progress, live region, error stop state. `processing.html.j2`.
8. **06 Report** — sheet, page rail, zoom, print parity. `report.html.j2`, `report.css`,
   `report.print.css`. Gates: `test_rra015_*`.
9. **01 Home / Overview** — first `/app` surface; binds only to `read_overview` figures.
   `overview.html.j2`, `workspace.css`.
10. **05 Insights** — `analyses.html.j2`, `analysis.html.j2`, `decision.html.j2` and the shared
    decision partials. Largest surface area; do it last.

**Phase C — sweep**
11. Responsive pass at 1440 / 1024 / 390 across all six.
12. RTL pass: every surface in `ar`, including mixed-direction values and mirrored charts.
13. State pass: loading, processing, success, warning, error, empty, disabled, pending.
14. Side-by-side against `design-files/Khepri Product UI.dc.html` and `references/*.png`.
15. Full gate run; regenerate visual baselines deliberately; write the final report.

After each of steps 5–10: delete that screen's superseded CSS rules and markup. Do not leave dead
selectors behind "just in case" — the visual regression baselines are the safety net.

---

## 18. Forbidden scope

Do not change: backend behavior · database schema, models or migrations · the authentication or
membership model · API contracts or response shapes · read models and projections · route shapes,
prefixes or path parameters · Offers/entitlement gating · copy dictionaries (beyond adding a key
that a new visual element genuinely requires, flagged in the report) · CI workflows · the landing
wall · unrelated product features.

Do not add dependencies or modify `pyproject.toml` / lockfiles. Do not add an external font CDN.
Do not perform broad architectural refactors. Do not unify the two shells. Do not create routes.
Do not rename tests, files or CSS token names purely for tidiness.

**Git safety.** Stage only named files. Never `git add -A`. Never stage unrelated untracked files.
Do not commit, push, open a PR or merge. Stop before every publication action.

If unexpected modified files, unrelated failing tests, merge conflicts or scope creep appear: stop
and report the exact blocker rather than widening the task.

---

## 19. Final report format

1. Files changed (grouped: shared system / journey / workspace / report / assets / tests)
2. Components created vs. reused
3. Screens implemented, with the route each was verified at
4. Assets added, with their `_ASSETS` registrations
5. Gates run and results; any baseline regenerated, and why
6. Responsive validation (1440 / 1024 / 390) and RTL validation, per screen
7. Remaining visual differences that could not safely be reproduced — including the display-face
   substitution from §9
8. Genuine blockers

No new design proposal. Implement the approved design.

---

## 20. Completeness

Settled by the owner and requiring no further interpretation: route mapping (§4), shell strategy
(§4), typeface policy (§9), asset policy and registration (§6), scope boundaries (§18).

Known gaps, none blocking:

* **Avatar and vendor-logo assets are not supplied.** Prototype placeholders. Use existing repo
  assets or initials; do not draw them. If a surface genuinely requires real logos, report it.
* **The display face is a substitution, not a match** (§9). Expected and approved; report the
  resulting differences rather than compensating with a new dependency.
* **Compressed hero derivatives are not pre-generated.** The 1400×900 PNG source is supplied;
  producing the jpg/webp/@2x variants is an implementation step (§6).
* **Screen 05 spans three templates.** The prototype shows one composition; apply the system across
  `analyses`, `analysis` and `decision` without merging them.
