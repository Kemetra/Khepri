# Khepri Design Language

**Baseline:** `65579bc` (`origin/main`), 2026-08-26. Read in worktree `uxQ`.
**Command:** `/impeccable shape` — design only. No CSS, template, route, test, package, backend, API,
governance, or database change.
**Reconciled:** `ed57967` (`origin/main`), 2026-08-27 — §3.5, §7, and §8.2 updated to reflect the
`W1-05` navigation conflict now RESOLVED (roadmap and blueprint reconciliation); no visual, CSS, or
token change. Sections not touched were not re-verified against `ed57967`.

## 0. Authority and standing

This document is **design direction**. It grants no implementation authority.

```
Active governance / specifications / decisions   ← governance/registry.yaml
        ↓
Master Product Roadmap
        ↓
KHEPRI_PRODUCT_UX_BLUEPRINT.md          product UX reference
        ↓
KHEPRI_DESIGN_LANGUAGE.md   ← this document — visual and component direction
        ↓
Implementation slices
```

If this document conflicts with active authority, **authority wins** and this document is reconciled
before implementation.

### The visual authority is code that already ships

Blueprint §17 states it: *"The shipped light token set is the visual authority."* Roadmap `U1-01`
states it as a task: *"**Preserve and document** the merged primitive tokens and shell component
layer — current visual foundation remains the source of truth."* The M2 critique states it as a
verdict: *"not a weak design that needs redesigning — it is a strong design with unfinished seams…
**No visual-world replacement is warranted.**"*

Three independent sources agree. **This document therefore preserves and extends; it does not
replace.** Every token below is either already shipping, or derived from one that is with its
derivation stated.

The authority files, in precedence order within the visual layer:

| File | Role |
|---|---|
| `src/khepri/rra/journey/assets/shell.css` | **The palette and scale. Tokens only — a test asserts it declares no rules.** |
| `src/khepri/rra/journey/assets/shell-components.css` | The component layer. Consumes tokens, introduces no colour of its own. |
| `src/khepri/rra/journey/assets/journey.css` | The journey. Predates the token layer; consumes none of it. |
| `src/khepri/rra/rendering/templates/report.css` + `report.print.css` | The deliverable. A **separate, deliberate** namespace — see §2.6. |

**Named anti-reference:** `docs/ui/design_handoff_khepri/`. Dark palette against a shipped light one;
asset plan names Google Fonts and a unpkg CDN, both forbidden by roadmap:156 and unreachable under
the shipped `default-src 'none'` CSP. Marked non-authoritative in its own design spec. Do not mine it
for values.

### Verified at this baseline, not inherited from the critique

The M2 critique reads at `b19f365`. Several of its findings have since shipped. Re-verified here:

| Critique finding | Status at `65579bc` |
|---|---|
| P0 `.refused` has no CSS rule | **RESOLVED** — `report.css:133`, side-rule + italic, `--report-muted` |
| P2 `.caveats--section` unstyled | **RESOLVED** — `report.css:150`, `report.print.css:150` |
| P2 report `.scroller` not keyboard-scrollable | **RESOLVED** — `report.css:179` `:focus-visible` |
| P0 `.document-card` means two things | **RESOLVED** — journey renders `.journey-document` |
| P1 shell has no nav or language switcher | **RESOLVED** — `shell.html.j2` frame carries both |
| P1 #7 `unavailable` has no exit | **RESOLVED** — `unavailable.html.j2` carries a cause-free exit link |
| P1 #12 four user strings inlined in JS | **RESOLVED** — all five JS files read copy from `data-*`; 0 hardcoded strings |
| P2 `--text-*` defined and unused | **LIVE — 0 `var(--text-*)` in all of `src/`** |
| P1 `.skip-link` is two mechanisms | **LIVE** — `journey.css:39` `fixed`/`translateY(-180%)` vs `shell-components.css:45` `absolute`/`-9999px`, inverted colours |
| G font-size drift | **LIVE — 12 distinct raw sizes across 17 declarations**, counted over all four rule-bearing sheets (`shell.css` declares tokens only). `.82` `.83` `.84` `.86rem` coexist — four values inside 0.04rem |
| P1 #16 `aria-current` absent | **LIVE — 0 occurrences in all of `src/`** |
| P1 #10 refusal shares error paint | **LIVE** — `review.html.j2:7` `#profile-findings` uses `.error-summary`. Its `role="status"` is already correct; the *paint* is the defect |
| P1 #8 "available on request" for a published URL | **LIVE** — `rendering/html.py:145` |
| P1 #7 `expired` has no exit | **LIVE** — `expired.html.j2` is prose-only in both branches |
| F RTL: zero physical directional properties | **LIVE AND INTACT — preserve** |

Every claim of a present-tense defect in this document appears in this table. A claim in body prose
without a row here is inherited from the critique and has not been re-verified.

---

## 1. Visual direction

### The sentence

**A governed document, not a dashboard.** Khepri looks like an instrument that reports what it can
support and names what it cannot — calm, dense with fact, drawn with rules rather than shadows, and
equally at home in Arabic and English.

### The five laws

**1. Containment comes from rules and type, never from elevation.**
`--paper` and `--surface` are the same value (`#fbfcfd`). `--shadow: none` ships. `border-radius: 0`
is applied to the primary button. This is not an unfinished figure/ground — it is the thesis. A
hairline rule and a type-size change separate regions. **A shadow ramp, a raised card, or a
gradient would each break the law**, and the absence of an elevation ramp is a *recorded deliberate
absence*, not a gap awaiting a fix.

**2. Colour is semantic or it is absent.**
The palette has one accent and three state families. Colour never carries a distinction alone: every
state reads as text or shape first, with colour reinforcing. This is what makes the product legible
in print, in dark-preference contexts, and to a colour-blind reader without a second design.

**3. Refusal is a result, and looks like one.**
The most important sentence in the product is *"we did not answer this."* It gets the **disclosure
shape** — an inline-start rule plus italic — and the **withheld palette** (`--report-muted`), never
the error palette. Painting it red would say something went wrong. The shipped `.refused` rule is the
canonical precedent; §4.6 generalizes it.

**4. Type does the work of hierarchy.**
One typeface, both scripts, one weight axis used sparingly (400 / 600 / 650). Hierarchy comes from
size, measure, and colour role — not from rules, boxes, or decoration. Monospace is reserved and
meaningful: it marks machine-adjacent values (the wordmark, tokens, meta, step numbers), never body
prose.

**5. The interface renders only capability that exists.**
No destination appears before the slice that implements it. No result count is fixed. No control is
shown disabled to teach a customer about a permission they do not have. A "Coming Soon" item is a
lie told in navigation.

### What this direction rejects, and why each is a live risk here

| Rejected | Why it would be wrong for Khepri |
|---|---|
| Generic SaaS dashboard | The product answers submissions, not "metrics at a glance". M3 is explicitly *not* the executive dashboard. |
| Giant sidebar | Four to six destinations do not need a persistent 240px column. The shipped frame is one wrapping row and is correct. |
| KPI card walls | `M3-U5` forbids "KPI cards; charts; business metrics" on Overview by name. A card wall also implies a fixed count, violating the LOCKED no-fixed-count invariant. |
| Nested cards | Blueprint §2 names it. With one surface colour, a card inside a card is two hairlines and no information. |
| Gradients | Nothing in the palette is a gradient stop. A gradient cannot be printed reliably or stated as a contrast ratio. |
| Badge soup | Operational state and trust state are two axes (§4.5). Badges invite fusing them into one compound lie. |
| Fake capability | Roadmap `FR-049` forbids it; §1 law 5. |
| Coming Soon nav | Same. |
| A second typeface or an icon set | Each requires a licence-plus-audited-digest process. Neither exists. Both are recorded deliberate absences. |

---

## 2. Design tokens

### 2.1 Standing

`shell.css` is the palette and scale, and **a test asserts it declares no rules**. That separation is
load-bearing: tokens are declared in exactly one place, so the component layer can introduce no
colour of its own.

Everything in §2.2–§2.5 **already ships**. This section documents and names the system, adds the two
role gaps §4 needs, and states the consumption rule that closes the largest live seam.

### 2.2 Colour — ink, surface, and rule

| Token | Value | Role | Measured |
|---|---|---|---|
| `--paper` | `#fbfcfd` | Page ground | — |
| `--surface` | `#fbfcfd` | Component ground — **intentionally identical to `--paper`** (law 1) | — |
| `--surface-raised` | `#fafbfd` | The one genuinely raised ground: the drop zone | — |
| `--ink` | `#202326` | Primary text | **15.37:1** on paper — AAA |
| `--muted` | `#55606d` | Secondary text, labels, **and any border that encodes state** | **6.23:1** — AA (fails AAA only) |
| `--line` | `#cfd6de` | Decorative hairline between regions | **1.43:1 — decorative only** |
| `--line-subtle` | `#e4e8ed` | Lighter rule, inside lists | — |

**The `--line` / `--muted` rule is the single most transferable lesson in this palette.** A border
that separates paragraphs may be `--line` at 1.43:1. A border that *tells you what state something
is in* must clear WCAG 1.4.11's 3:1, and `--line` does not — so it takes `--muted` at 6.23:1. The
shipped precedents: form control edges (`shell-components.css`, "a control's edge is what tells a
sighted reader where the field is") and `.refused` (`report.css:127-131`, where `--report-rule`
reached only 1.32:1 against the tint and would have left the italic carrying the signal alone).

**The palette gains steps, never colours.** There is deliberately no value between `--line` and
`--muted`.

### 2.3 Colour — accent and state

| Token | Value | Role | Measured |
|---|---|---|---|
| `--accent` | `#1e5b96` | Links, primary action edge | **6.83:1** — AA |
| `--accent-dark` | `#174a7c` | Hover fill, action text on tint, progress fill | — |
| `--accent-surface` | `#f0f5fa` | The one accent-tinted ground | — |
| `--focus` | `#1f5fa8` | Focus ring — 3px, `outline-offset: 3px`, **identical in shell and journey** | — |
| `--danger` / `-border` / `-surface` / `-ink` | `#9a2d26` `#d9a49f` `#faece9` `#6d201b` | **Transport and system error only** | — |
| `--ready` / `-border` / `-surface` | `#1d6b45` `#a0d9be` `#eafaf3` | Success | — |
| `--track` | `#e3ded1` | Progress track — warm, genuinely its own value | — |

**`--danger` is for errors, not refusals.** A governed refusal that borrows this family tells the
customer something broke. §4.6 gives refusal its own treatment.

**The `--ready-*` derivation is the standard every future value must meet.** Those two are the only
values in the file not already in `journey.css`, and they were *derived*: `--ready`'s hue (151) held
constant at the saturation and lightness steps the danger family already used (`-border` S43/L74,
`-surface` S62/L95). A first draft eyeballed `#a9cbb8`/`#eef5f1`, drifted the hue to 146, and matched
neither step — "close enough to look intentional and not derived from anything." A test caught it.

> **Rule for any new colour: state the hue-constant derivation and the measured ratio, or it is an
> eyeballed value wearing a token's name.**

### 2.4 Spacing — a 4px ramp

`--space-1` … `--space-8` = 4 · 8 · 12 · 16 · 24 · 32 · 48 · 64px.

Live drift: 25 distinct spacing values in use, **17 off-scale**. The ramp names what the shipped
values were already clustering around; it is not a new geometry.

### 2.5 Type

One face, both scripts, no fallback to a font host:

```
--font-body: "Noto Sans Arabic", "Segoe UI", Tahoma, sans-serif;
```

Shipped as package data under `rendering/typefaces/`, verified against a SHA-256 manifest, split into
Arabic and Latin `unicode-range` subsets. **No `@import`, no font host** — forbidden by roadmap:156
and unreachable under the CSP.

| Token | Value | Role |
|---|---|---|
| `--text-xs` | `0.7rem` | Meta labels, uppercase monospace `dt` |
| `--text-sm` | `0.82rem` | Secondary and table text — **collapses the live `.82/.83/.84/.86rem` run** |
| `--text-base` | `1rem` | Body |
| `--text-md` | `1.15rem` | Sub-heading — **new value, not promoted** |
| `--text-lg` | `1.4rem` | Section heading — **new value, not promoted** |
| `--text-xl` `--text-2xl` | `1.75rem` `2.15rem` | Headings |
| `--text-display` | `clamp(1.9rem, 3vw, 2.25rem)` | `h1` — fluid, as shipped |
| `--text-lede` | `clamp(1rem, 2vw, 1.16rem)` | Lede — fluid, as shipped |
| `--leading-tight` / `-normal` | `1.15` / `1.5` | Headings / prose |

`--text-md` and `--text-lg` are marked **new** deliberately: in `journey.css` those numbers occur
only as a margin and a padding, so calling them "promoted" would tell a builder a shipped rule
already sets type at that size, and none does.

**Monospace is a semantic, not a style.** `ui-monospace, monospace` marks the wordmark, meta lines,
step numbers, `dt` labels, and the invitation token — machine-adjacent values. It never sets prose.

Measure: `--measure-heading: 24ch`, `--measure-prose: 62ch`. Character units, so the cap follows the
text rather than the viewport — which matters when the text is Arabic.

### 2.6 The report is a second namespace, deliberately

`report.css` declares `--report-ink` `#16191d`, `--report-paper` `#ffffff`, `--report-muted`
`#55606d`, `--report-rule` `#d5dae1`, `--report-accent` `#0f4c81` — **different values from the app
palette**, plus a `prefers-color-scheme: dark` block the app does not have.

**This is documented, not unified.** Blueprint §16: *"The final report is not redesigned in this
blueprint version."* The report is a print-first executive deliverable; the app is a screen surface.
White paper and a denser ink are correct for a document that gets printed.

**The relationship rule:** the two namespaces are siblings that must stay *semantically* aligned even
where their values differ. `--report-muted` and `--muted` are the same value (`#55606d`) and both
carry the same role — secondary text *and* any border that encodes state. When a role is added to one
namespace, the other gets the same role or an explicit note saying why not.

**Unresolved:** the dark block means a dark-preference OS yields a dark report inside a light app.
See §8.1.

### 2.7 Layout and target tokens

| Token | Value | Note |
|---|---|---|
| `--shell-width` | `1068px` | One shell width. A sibling rule uses `1050px`; that is drift. |
| `--touch-min` | `44px` | **A verified floor, not a preference** — see §5.3 |
| `--radius-sm` / `-md` / `-pill` | `3px` / `6px` / `999px` | `--radius` is retained as an alias to `--radius-sm` so no existing rule changes meaning |
| `--shadow` | `none` | Law 1 |

### 2.8 The consumption rule — the largest live seam

**`var(--text-*)` appears 0 times in all of `src/`.** The type scale is **nine `--text-*` tokens plus
two `--leading-*`** — eleven in all. The M2 critique and `shell.css`'s own note both say "ten"; the
declared count at `shell.css:109-129` is nine, and `tests/test_r801_shell_tokens.py:316` asserts
`("--text-", 9)`. The test was reading the artifact while the prose repeated itself.
`var(--space-*)` has exactly one consumer file. `journey.css` re-inlines the three danger hexes that
`shell.css` already names.

> **A token with no consumer is a design decision that did not ship.** The direction is not complete
> when the tokens exist; it is complete when the surfaces read them.

Consolidation runs **journey → shell**, never the reverse: the shell is the newer, more disciplined
layer (logical properties, tokens, documented derivations). It is where the font-size drift and the
17 off-scale spacing values resolve.

### 2.8.1 Why this seam cannot be closed by a design slice

Investigated on `#287` and recorded so the next attempt does not rediscover it.

**Consumption requires declaration in the same cascade.** `base.html.j2` links `journey.css` alone;
`shell.html.j2` links `shell.css` and `shell-components.css`. Two allowlists, two routes, and **the
sheets never co-load** — so a bare `var(--text-sm)` in `journey.css` resolves to nothing, and an
invalid `font-size` is *dropped*, not ignored. The element falls back to its inherited size. **A
find-and-replace here is a silent visual regression, not a no-op.**

The workable shape is to mirror the consumed tiers into `journey.css`'s own `:root` at identical
values, then consume them — symmetric with the palette, where `shell.css`'s note records sixteen
colours coming from `journey.css:15-30` unchanged. But that **mirrors** the seam rather than closing
it: one value, two files, with no test able to see them diverge. Closing it needs a shared token
sheet linked by both templates — a routes and allowlist change — or a build step.

**Nor is the substitution appearance-neutral throughout.** Four declarations map exactly
(`--text-display`, `--text-lede`, `--leading-tight`, and `.82rem` → `--text-sm`); three sit inside the
collapse `shell.css:107` documents and move 0.16–0.64px at a 16px root, measured. Because
`line-height: 1.6` is unitless, a changed type size carries the leading with it.

**⚠ And the change is not admissible on this document's authority.** `RCA-002:132-135` excludes *"Any
change to the `RRA` beta journey, its routes, its templates, or its **assets**"*, `journey.css` is
such an asset, and **no active specification in `governance/specifications/` mentions it**. The
precedent is `df9f1d1`, which changed `report.css` and cited active `RRA-006`/`RRA-009` — a named spec
whose surface scope covered the file. `U1-01` is a roadmap task with **no registry entry**, and this
document grants no implementation authority. **The work is designed and verified; it requires an
active RRA specification naming the journey assets before it can ship.**

---

## 3. Shell composition

### 3.1 Two modes, one frame

The shell (`/app`) and the journey (`/beta`) are **separate product modes by design** — blueprint §4
calls the separation intentional and "not an architectural defect to be corrected." The shell carries
organization and commercial context; the journey is focused task mode.

**What must be shared is the frame, not the mode.** The critique's finding stands: the visitor
crosses a 303 redirect and the header model, button treatment, and skip-link mechanism all change.
The transition itself is correct and must be kept — the redirect sets its cookie only on success and
deliberately omits it on the refusal path.

### 3.2 The frame

```
┌────────────────────────────────────────────────────────────────────────┐
│  KHEPRI     {Organization}     {destinations}              {اللغة}     │  identity row
├────────────────────────────────────────────────────────────────────────┤
│  {step progress — journey mode only}                                   │  context row
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│   h1                                                                   │
│   lede                                                                 │
│                                                                        │
│   … one document, one primary decision …                               │
│                                                                        │
├────────────────────────────────────────────────────────────────────────┤
│  retention promise · absolute time with timezone                       │  footer
└────────────────────────────────────────────────────────────────────────┘
```

**One wrapping row, not a sidebar.** `flex-wrap` rather than a media query — the shipped reasoning is
exact: *"the row has at most four items and wrapping at 320px is the correct behaviour for all of
them — a breakpoint would encode a guess about which one should go first."* At six destinations that
reasoning still holds; a sidebar would not be earned until the count is far higher.

`.frame-language { margin-inline-start: auto }` pushes the language control to the inline end
whatever precedes it, so the row reads identically at two items or four **and mirrors in RTL without
a second rule**. That is the pattern for every future frame element.

**The frame degrades by surface, not by rendering a fixed row.** `unavailable` and `no_membership`
receive nothing but a language — "takes no cause, so it can disclose none" — so brand and language
appear everywhere, and organization and destinations appear only where a resolved organization was
passed. Privacy holds by construction rather than by care.

### 3.3 Identity

The wordmark is a link, not a `<span>`, and carries **real text plus a visually-hidden purpose**,
named in source order by `aria-labelledby`. An `aria-label` here once *replaced* the visible text, so
the Arabic shell's accessible name held no "KHEPRI" at all and a speech-input reader could not
operate it. **A picture of a name is not a name.**

The organization name: `max-inline-size` in `ch`, `dir="auto"`, truncation **visual only** — the full
name stays in the DOM so the accessible name is complete.

### 3.4 The document

`.journey-document` — `max-width: 860px`, `border: 0`, `padding: 0`. One document per page, hierarchy
from type alone, nothing drawn around it. `.document-card` — bordered, padded, `60rem`, stacked
several to a page — is the shell's genuine card.

**Two names because they are two things.** They once shared one class, so the same semantic element
was a card on one side of the crossing and the absence of one three URLs away; the sheets never
co-load, so no test could see it. The naming is the fix and must not be re-merged.

### 3.5 Navigation — mechanism, and now a settled label set

**The label set is settled; registered authority to implement it is not.** Blueprint §8 marks
Overview · Data · Analyses · Team **LOCKED**, and `W1-05` is now amended to the same four-item scope
(§8.2) — the conflict this section previously flagged is resolved. **Verified at this baseline:
`governance/registry.yaml` contains `FND`, `RRA`, `RCA` and nothing else — `W1`, `T1`, `G2`, `G3`,
`U1` have zero entries.** So a settled label set is still not implementation-ready; see §8.2.

The **mechanism** is designable now — it is `M3-U1`'s own scope ("the frame, route continuity, the
nav mechanism"):

- Destinations are **text links that wrap**, not a menu and not a collapsing drawer.
- The active destination carries **`aria-current="page"`** plus a 2px inline-end-agnostic bottom rule
  in `--accent`, `--ink` colour, and 600 weight. **Three signals, so colour is never alone.**
  Verified: `aria-current` has **0 occurrences in all of `src/`**, so the shipped active step is rule
  + colour + weight only — a visual-only state that does not reach a screen reader.
- Each link is **44px minimum on the element itself**, not on a padded wrapper.
- **No directional glyph.** An arrow does not mirror and points away from the reading direction in
  RTL.
- **A destination enters the navigation in the slice that implements its surface** — `FR-049`.
  Landing four links in `M3-U1` would render navigation with nothing behind it.
- The navigation needs its **own parity-paired label key**. It currently borrows the Team title,
  which is imprecise for one item and wrong for four.

### 3.6 Shell, journey, and report — the three-way relationship

Four surfaces consume **the same governed facts**. None recalculates them — templates, controllers,
dashboards, APIs, semantic views, and AI may select and present facts, and may not compute them.
That single rule is what lets the four look different without disagreeing.

| Surface | Role | Design consequence |
|---|---|---|
| **Shell** (`/app`) | Commercial and organization context | A frame. Carries identity, scope, destinations, language. Owns no analysis content. |
| **Journey** (`/beta`) | Focused task mode for one analysis | A document per page, one primary decision per page. Owns no commercial context. |
| **Report** | Premium executive deliverable | Print-first. Own token namespace (§2.6). Denser ink, white paper, repeated `thead`, `break-inside` control. |
| **Evidence** | Proof layer | **Contextual only** — reached from the claim it supports. Never a primary destination (§4.7). |
| **Excel** | Structured downstream artifact | Reached from the analysis that produced it, alongside the report. |

**What each surface owes the others:**

- **Shell → journey:** scope, and a 303 that sets its cookie only on success. The shell must make the
  organization legible *before* the crossing, because the journey currently cannot name it — that is
  an AUTHORITY-BLOCKED gap, not a design choice.
- **Journey → report:** the report is the journey's terminal artifact, not a separate destination
  reached from navigation. Analyses is the history spine; **artifacts are reached from the analysis
  that produced them.** This is why "Reports" is argued against as a primary destination.
- **Report → evidence:** a claim links to its own proof. The report is where §4.7's live defect
  bites — evidence is published at a URL while the prose says "available on request."
- **Report → shell:** nothing. The report is a document; it does not carry app chrome. This is the
  one boundary where divergence is correct, and §2.6 states the sibling rule that keeps the two
  namespaces semantically aligned anyway.
- **All → all:** state vocabulary, refusal treatment, caveat scoping, and the 44px floor are
  product-wide. A refusal must read as a refusal in the app, in the report, in print, and in dark.

**The seam that has no owner:** the shell and journey are correctly separate *modes* but should share
one *frame*. Today they diverge in skip-link mechanism (§4.10), primary button (§8.4), and exit
affordance (§4.9). Those are three symptoms of one missing slice (§8.7).

---

## 4. Component system

### 4.1 Buttons and controls

| | Treatment |
|---|---|
| **Primary** | `min-block-size: 46px`; 1px `--accent` border; **transparent** fill; `--accent` text; `border-radius: 0`. Hover: `--accent-dark` fill, `--surface` text. |
| **Secondary** | Same geometry, `--muted` text, no fill change. |
| **Text** | No border, no fill, `--muted`, underlined with `text-underline-offset: .2em`, 44px. |
| **Disabled** | `--line` border, `#7b817e` text (3.87:1 — **below AA but WCAG-exempt for disabled controls**), `cursor: not-allowed`. |

**Live divergence to resolve journey → shell:** journey primary is 46px/transparent/`--accent`;
shell primary is 44px/`--accent-surface` fill/`--accent-dark`. One product, one primary button. The
journey's transparent treatment is the more restrained and reads better against a single surface
colour; the shell's 44px matches the token.

**Never show a destructive control to a role that cannot use it.** Disabled-button education is
named as forbidden scope in `M3-U7`. A member does not see a greyed Delete.

**Typed controls take `font: inherit`.** Two reasons, both load-bearing: it takes the 16px body size
so **iOS Safari has nothing to zoom to** on focus, and it stops controls rendering in the platform UI
face beside prose set in the product's own. Their border is `--muted`, not `--line` (§2.2). Labels sit
**above** their control, never beside — Arabic and English name fields at different lengths, and a
side-by-side pair sizes the column from the longer language.

### 4.2 Tables

The shipped grammar, to be preserved:

- `.table-region` with `overflow-x: auto` and `border-block: 1px solid --line`. **The region scrolls,
  never the page** (§5.1).
- `min-width: 720px` on the table, `border-collapse: collapse`, `text-align: start`.
- `caption` — present, `text-align: start`, 600 weight.
- `th`/`td`: `padding: .75rem 0`; `th + th, td + td { padding-inline-start: 1rem }` — so the first
  column has no phantom inset and gutters exist only *between* columns. Mirrors in RTL free.
- `th` in `--muted` at `--text-sm`, `vertical-align: top`.
- `scope="col"` / `scope="row"`; per-section `aria-labelledby`.
- **`tabindex="0"` on the scroll container**, with a visible `:focus-visible` ring — a scrollable
  region that cannot be reached by keyboard is a trap that looks like nothing happened.
- **Column widths must fit Arabic-Indic digits.** Arabic yields different digit glyphs, grouping and
  decimal marks; a column sized for Latin digits will not fit them.
- Print: repeated `thead`, `break-inside` control, `overflow: visible` so no column clips.

**No zebra striping, no row hover fill, no sortable-column chrome** until a contract supplies
sorting. Rules and alignment carry the grid.

### 4.3 Lists as rows

Organizations, members, invitations share one rule — they differ in content, not in shape:
`display: flex`, `flex-wrap`, `gap: --space-3`, `min-height: 44px`, `border-block-end: --line-subtle`.

**A one-line row containing a link is designed at 44px from the start**, not discovered during
implementation.

### 4.4 The disclosure — the shape state borrows

```
│▌ A governed disclosure.        border-inline-start: 4px solid --report-accent
│▌                              background: #f2f6fa
```

4px, not a hairline: `report.print.css` **drops the tint** because a printer may not honour
background graphics, so **the border is what carries the emphasis onto paper**. A 1px rule would leave
a mandatory disclosure with no signal in the medium the report is most often read in.

**This is the canonical "this passage has a state" shape.** Severity is never colour-only.

### 4.5 Operational state and trust state — two axes, never fused

**LOCKED.** Operational state answers *what is happening to this analysis*. Trust state answers *what
could Khepri safely support*. Both are real and their combination is real — an analysis can finish
successfully while some results could not be supported.

A single compound badge — "Completed with caveats and partial refusal" — **misstates that**. The
shape is a state plus a governed summary:

```
Completed
Quality: [governed summary]
```

Visual treatment: **a neutral state chip — hairline border, `--muted` ink, no fill** — with the state
reading as text, not as colour alone. `.member-state` is the shipped precedent
(`padding-inline: --space-2`, `1px solid --line`, `--muted`).

**Three constraints on anyone implementing this:**

1. **The customer-facing trust vocabulary is PROVISIONAL and gated on `T1`, which has no registry
   entry.** *verified / caveated / refused / unavailable* are conceptual design vocabulary in the
   blueprint and are explicitly **not** the shipped words. Design the shape; do not mint the labels.
2. **No fixed result count is a LOCKED UX invariant.** The summary derives totals from the current
   governed result set. Today's report structure is an implementation fact, not a durable principle —
   so no layout may assume a section or metric count.
3. **Machine vocabulary never reaches a customer.** `mapped` / `ambiguous` / `transaction_date` /
   `net_revenue` are internal. The critique found 11 snake_case values rendering under a localized
   heading — in Arabic, an RTL table with two Latin snake_case columns, on the page where the
   customer confirms Khepri understood their data.

### 4.6 Trust, caveat, and refusal states

| State | Treatment | Never |
|---|---|---|
| **Refusal** — a governed result | Disclosure shape: `border-inline-start: 4px` in `--muted` (6.02:1 on the tint, 7.61:1 on paper) **plus italic**. Rule and italic each carry the meaning independently. Stays **where the answer would have appeared**. | `--danger`. `role="alert"`. Omission. Colour alone. |
| **Caveat, global** | The shipped caveats list. | — |
| **Caveat, section-scoped** | Visually distinct from the global list — a section caveat that reads like a global one misattributes its scope. | Sharing the global treatment. |
| **Error, transport or system** | `--danger-*` family: `--danger-border`, `--danger-surface`, `--danger-ink`. | Being reused for a refusal. |
| **Success** | `--ready-*`. | — |

**Refusal and error must not share paint.** Verified live: `review.html.j2:7` `#profile-findings`
carries `.error-summary`, so a governed refusal is painted exactly like a transport failure. Its
`role="status"` is already right — the semantics were fixed and the paint was not, which is why the
defect survives. Under §1 law 3 this is a product-meaning defect, not a styling one.

**`role="alert"` is wrong for a stable refusal.** An alert announces a problem; a refusal is an
outcome.

**Dark and print degradation, both already solved and worth copying:** in print the refusal tint is
dropped and the rule alone carries it. In dark the tint is dropped too — *"at these luminances a tint
one step off the page reaches about 1.06:1 against it, which is a surface nobody can see."* Dropping
it is honest; picking a dark grey would be invention.

### 4.7 Evidence

**Evidence is contextual — reached from the claim, result, or report it supports. There is no generic
primary "Evidence" destination** (blueprint §10, LOCKED).

The link from a metric to its evidence is the cheap and correct half: `_evidence.html.j2` already
mints `citation-*` anchors, and the report's only pointer is prose. Verified live at
`rendering/html.py:145`: *"Full calculation evidence and data lineage are available on request."* —
**for a document already published at a URL.** That phrasing actively reduces trust: it reads as
withholding something that is in fact one link away, on the surface whose entire claim is that
evidence is reachable from the claim it supports.

Evidence detail may carry definition, population, source semantics, coverage, comparison window,
reconciliation, caveats, refusal information, citation identifiers, and governed versions. **Low-level
formula and version strings must not dominate primary customer pages.**

### 4.8 Progress and processing

Determinate upload: `.progress-track` with a live `aria-valuenow`. Indeterminate processing:
`.indeterminate` **correctly omits** `aria-valuenow` — a bar that reports a position it does not know
is a lie with an ARIA attribute on it.

`prefers-reduced-motion` **fills the track** rather than freezing it — a frozen indeterminate bar at
35% reads as stalled. The RTL keyframe is mirrored (`journey-progress-rtl`), because a translate
animation does not mirror itself.

### 4.9 Empty and loading states

**LOCKED grammar — every empty state says three things:** what this area is, why it is empty, and the
next valid action where one exists. **No decorative empty-state illustrations by default.**

**Loading: placeholder rows at the final row height**, so nothing shifts when content arrives. Not a
spinner, not a shimmer — the row height is known, so the layout should not move.

Terminal states carry a route out. **`unavailable` now does this correctly and is the pattern**: an
exit that is identical in wording, target, and presence on every cause — because `FR-050` collapses
five causes into one surface and an exit that *varied* would reintroduce the disclosure the surface
exists to prevent. It names no cause, and it targets `/app/{language}` rather than an
organization-scoped address because scope is re-resolved from the session.

**`expired` is still prose-only** in both its branches, and the journey brand link bounces back to
where the visitor already is. **A failure state carries a next action where one validly exists** —
and `expired`'s valid next action is a new analysis.

### 4.10 The skip link — one mechanism

Currently two: `journey.css:39` is `fixed` + `translateY(-180%)` with `--ink` ground and `--surface`
text; `shell-components.css:45` is `absolute` + `inset-inline-start: -9999px` with `--surface` ground,
`--accent` text, and `min-height: 44px`.

**One mechanism.** The shell's — logical, offset rather than transformed, and sized to the same 44px
minimum as every other target, because *"a skip link too small to hit is one that only exists for the
test."* It must be the first focusable element in the body.

---

## 5. Responsive rules

### 5.1 The invariant

**LOCKED — no page-level horizontal overflow.** Wide content scrolls **inside its own container**.
`body { min-width: 320px }`.

### 5.2 Wrap before you break

**Prefer wrapping to a breakpoint.** `shell-components.css` has **zero media queries** and this is
deliberate: *"a breakpoint would encode a guess about which one should go first."*

Where a breakpoint is genuinely needed, there is **one** — 640px, in `journey.css:97-110`, carrying
~19 declarations across 11 selectors. It performs **narrow-width adjustment only**: no selector in it
introduces a component, changes a colour, or alters a layout topology. The representative moves are
raising `h1`'s clamp floor, collapsing `.intake-facts` from three columns to two with the third
spanning, tightening the step-nav gap, reducing the drop zone, and making the primary button full
width.

At narrow widths:

- Destinations remain **text links that wrap**, not a collapsed menu.
- Rows become **stacked blocks**.
- The **primary action is full width and first**.
- **Artifact actions stack** rather than compressing into a row of equal buttons.
- Tables scroll in their region; the page does not move.

### 5.3 44px is a requirement

`RCA-002` `FR-056` requires every interactive target to meet it, **in both languages at every
supported viewport**, and browser tests measure every button, language link, and nav item.

**Applied to the element itself, never to a wrapper** — *"a padded parent around a 17px anchor still
leaves a 17px anchor."* `R8-07` found every shell target at 17px precisely because the tokens shipped
without a component layer to apply them.

### 5.4 Fluid where the shipped surface is fluid

`--text-display` and `--text-lede` are `clamp()`. Fixed sizes stay fixed. Horizontal page padding is
`clamp(1rem, 4.8vw, 3.6rem)`. Shell width is `min(100% - 2rem, --shell-width)` — the gutter is in the
`min()`, so no media query is needed to keep it off the edge.

---

## 6. RTL rules

**LOCKED — Arabic RTL and English LTR are first-class equal product surfaces.** Not a primary
language plus a translation.

### 6.1 Verified and to be preserved

**All five stylesheets contain zero physical directional properties** — verified at this baseline. A
test asserts it for `report.css`, so the rule cannot be relaxed one declaration at a time.

> An RTL layout that mirrors correctly **cannot be built** from `left` / `right` / `margin-left`. This
> is not a preference; it is the reason there is no mirrored second stylesheet to drift.

`text-align` uses only `center` and `start` — both direction-agnostic.

### 6.2 The rules

| Rule | Detail |
|---|---|
| **`lang` and `dir` are server-computed** | Never inferred in a template. |
| **`dir="auto"` for customer values** | Organization names, file names. A fixed `ltr` reorders an Arabic name around its own punctuation and digits and puts a Latin extension at the visual left. `auto` derives direction from the first strong character — correct for both. |
| **`dir="ltr"` islands only where Latin is guaranteed** | Email addresses, tokens, counts, `50 MB`. |
| **No literal directional glyph** | An arrow does not mirror and points away from the reading direction in RTL. |
| **Truncate in `ch`, not `px`** | The cap follows the text, not the viewport. Keep the full value in the DOM. |
| **Locale-formatted dates and numbers** | Arabic-Indic digits, Arabic month names, Arabic decimal / grouping / percent marks. **Size columns for them** (§4.2). |
| **Mirror animations explicitly** | A `translateX` keyframe needs its RTL twin. |
| **Copy parity enforced at import** | A missing key fails the build, not the visitor. **Customer strings never live in JavaScript.** Verified: all five JS files now read copy from `data-*` attributes, 0 hardcoded strings — this is the shipped pattern to preserve, not a gap. |
| **Labels above controls** | Never beside: a side-by-side pair sizes the column from the longer language. |
| **RTL type correction** | `[dir="rtl"] h1 { letter-spacing: 0 }` — negative tracking is a Latin display convention and damages Arabic joins. |
| **Set `lang` on the language control** | So a screen reader pronounces the target language *in* that language. |

---

## 7. Example Overview composition

**⚠ CONTRACT-BLOCKED — structure only.** Overview requires `W1-04` and `G2`/`G3`, none registered
(§8.2). `M3-U5` forbids **"KPI cards; charts; business metrics."** No data below is real; no count is
fixed.

**The frame's destination slot below now names the reconciled label set (§8.2): Overview, Data,
Analyses, Team.** Each still enters navigation only in the slice that implements its own surface —
`FR-049` — so naming them here is not a claim that all four ship together.

Overview answers **"what happened, and what do I do now?"** — it is *operational orientation*, not
analytics. M3 is explicitly not the executive dashboard.

```text
┌──────────────────────────────────────────────────────────────────────────┐
│  KHEPRI    Acme Trading    {Overview · Data · Analyses · Team}  العربية   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   Overview                                              --text-display   │
│   Everything for Acme Trading.                          --text-lede      │
│                                                                          │
│   ──────────────────────────────────────────────────────  --line         │
│   LATEST WORK                              --text-xs mono uppercase muted│
│                                                                          │
│   Q3 sales analysis                                     --text-md        │
│   Completed · 12 March 2026, 14:20 GMT+3                --text-sm muted  │
│   Quality: [governed summary]              ← T1. Not a badge. Not a count│
│   ┌──────────────┐                                                       │
│   │ Open report  │  ← one primary action, 46px, transparent, radius 0    │
│   └──────────────┘                                                       │
│                                                                          │
│   ──────────────────────────────────────────────────────                 │
│   DATA                                                                   │
│                                                                          │
│   q3-sales.csv                    Admitted      14 Feb 2026, 09:12 GMT+3 │
│   q2-sales.csv                    Admitted      02 Nov 2025, 11:40 GMT+3 │
│   returns.csv          ▌Not admitted — coverage  08 Feb 2026, 16:05 GMT+3│
│                        └ neutral chip, hairline + --muted. Not red.      │
│                                                                          │
│   ──────────────────────────────────────────────────────                 │
│   NEEDS ATTENTION                        ← omitted entirely when empty    │
│                                                                          │
│   ▌ Content for "Q1 comparison" is no longer available.                  │
│     ← 4px --muted rule + italic. Neutral wording: the state does not     │
│       prove the actor or the cause.                                      │
│                                                                          │
│   ┌────────────────────┐                                                 │
│   │ New analysis       │                                                 │
│   └────────────────────┘                                                 │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│  Content is retained until 12 September 2026, 23:59 GMT+3.               │
└──────────────────────────────────────────────────────────────────────────┘
```

**What this composition asserts, and what it refuses to:**

| Does | Does not |
|---|---|
| Three named regions separated by hairline rules and monospace `--text-xs` labels | Four KPI cards |
| Latest work as **one** row with one primary action | A chart |
| `Completed` and `Quality:` as **two separate lines** (§4.5) | A compound badge |
| Absolute time with timezone, everywhere | "2 days ago" |
| Non-admission as a **neutral chip** with the coverage reason | Red for a governed outcome |
| Attention region **omitted when empty**, never rendered empty | A zero-state card |
| One obvious next action | A row of equal-weight buttons |
| Any region absorbing 0 or 50 rows | Any fixed count |

**Empty Overview** (§4.9 grammar — what this is, why it is empty, the next action):

```
   Overview
   Everything for Acme Trading.
   ──────────────────────────────────────────
   No data has been submitted yet. Analyses and reports appear here once
   a file has been admitted.
   ┌────────────────────┐
   │ New analysis       │
   └────────────────────┘
```

**Loading:** placeholder rows at the final row height. Nothing shifts.

**Narrow (below 640px):** the frame wraps; each region's rows become stacked blocks; `New analysis`
goes full width and first; time strings drop to their own line rather than truncating.

---

## 8. Unresolved design decisions

None of these may be resolved by a builder. Each needs an owner decision or registered authority.

### 8.1 The report's dark palette and its second namespace — OWNER DECISION

`report.css` ships `prefers-color-scheme: dark`; `shell.css` hardcodes `color-scheme: light` and
records "no dark palette" as a **deliberate absence**. **A dark-preference OS today yields a dark
report inside a light app.** Blueprint §16 says the report is not redesigned in this version, so this
document documents the split rather than resolving it (§2.6).

The option space, stated without a recommendation:

1. Scope the dark block out — all three surfaces agree at light, and dark becomes one future product
   decision rather than one surface's local choice.
2. Keep it and document it as intentional — the report is a document, and a document may follow the
   reader's preference where an app chrome does not.
3. Bring dark into the system as a product decision — a full second palette for every surface.

Option 3 is the largest and would reverse a recorded deliberate absence.

### 8.2 The navigation label set — RESOLVED, still no registered authority

Blueprint §8 previously marked Overview · Data · Analyses · Team **LOCKED**, then marked four rows
**CONFLICT-BLOCKED** against `W1-05`, which required *Workspace Overview, Datasets, Analyses,
Reports, Metrics, Activity* (roadmap `W1-05`).

**The owner has approved the four-item direction, and `W1-05` is amended to match it**: Overview,
Data, Analyses, Team are the primary customer surfaces; Reports fold into Analysis detail; Metrics
and Activity are contextual; "Workspace" is retained only as the internal domain term. The label set
that was unsettled at the previous baseline is therefore settled: **Overview · Data · Analyses ·
Team**, Arabic **الرئيسية · البيانات · التحليلات · الفريق**.

**This does not register any authority.** `governance/registry.yaml` still contains only `FND`, `RRA`,
`RCA` — `W1`, `T1`, `G2`, `G3`, `U1` have zero entries, unchanged by this resolution. No M3 navigation
slice is implementation-ready; resolving the label conflict removed a contradiction between two
unregistered documents, nothing more. §3.5's mechanism design (destinations as wrapping text links,
`aria-current`, 44px targets, no directional glyph, its own parity label key) is unaffected — it was
always independent of which four words fill the slots, and now those words are also settled.

### 8.3 The trust vocabulary — CONTRACT-BLOCKED on unregistered `T1`

*verified / caveated / refused / unavailable* are conceptual design vocabulary, explicitly **not** the
shipped words. The aggregate states a customer sees depend on the `T1` analysis-quality-summary
contract — and `T1` has no registry entry. §4.5 designs the shape; the labels stay open.

### 8.4 One primary button — DESIGN DECISION, ready

Journey 46px / transparent / `--accent` versus shell 44px / `--accent-surface` / `--accent-dark`. One
product needs one primary button. Recommended: the journey's transparent treatment (more restrained
against a single surface colour) at the shell's tokenized 44px. Low-risk and inside `U1-01`.

### 8.5 Token consumption — AUTHORITY-BLOCKED, and the largest live gap

`var(--text-*)` has **0 consumers in `src/`**; 12 distinct raw font sizes across 17 declarations ship
with `.82/.83/.84/.86rem` coexisting; 17 spacing values are off-scale; `journey.css` re-inlines three
danger hexes `shell.css` already names.

An earlier revision of this section claimed **"`U1-01` owns this and it needs no new authority — the
values do not change, only where they are read from."** Both halves are wrong, and `#287` is where
that was established:

- **The values do change.** Three of seven substitutions move 0.16–0.64px, and the cascade makes a
  naive substitution a silent regression rather than a no-op (§2.8.1).
- **It does need authority.** `RCA-002:132-135` excludes any change to the RRA beta journey's assets,
  no active specification names `journey.css`, and `U1-01` is a roadmap task with no registry entry.

The work itself is designed, measured, and verified — it is blocked on an **active RRA specification
naming the journey assets**, not on design. Sequenced journey → shell when that exists.

### 8.6 Report ↔ app relationship — needs a stated rule

`--report-muted` and `--muted` are the same value with the same role; `--report-ink`/`--ink` and
`--report-paper`/`--paper` differ. §2.6 proposes: siblings, semantically aligned, and a role added to
one namespace is added to the other or explicitly declined. **Not yet ratified anywhere.**

### 8.7 Frame continuity across the crossing — needs a slice owner

The 303 redirect is correct and must be kept. The visitor still crosses from `/app` to `/beta` with
no shared frame and no route back. `.skip-link`'s two mechanisms (§4.10) and the primary-button
divergence (§8.4) are the concrete symptoms, and `expired`'s missing exit (§4.9) is the same seam at
the other end of the journey — `unavailable`, on the shell side, already solved it. **No task ID owns
"one frame across both modes."**
Related recorded scope hole: roadmap §8 lists **"New Analysis"** as an M2 UI surface and *no task ID
anywhere owns it*.

---

## 9. What this document does not do

- **No implementation authority.** Design direction only.
- **No visual-world replacement.** Three independent sources say the shipped world is the authority.
- **No new colour, no new typeface, no icon set, no elevation ramp, no dark palette.**
- **No customer-facing trust labels** — `T1` is unregistered.
- **Navigation label set is settled (Overview · Data · Analyses · Team) but not registered authority** — see §8.2.
- **No report redesign** — blueprint §16.
- **No fixed result counts** anywhere in any composition.
