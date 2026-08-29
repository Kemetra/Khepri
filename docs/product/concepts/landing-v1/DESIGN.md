---
name: Khepri Landing Concept
description: One public Persuade surface extending the shipped Khepri design language — hairline containment, one accent, and a refusal that looks like a result.
colors:
  paper: "#fbfcfd"
  surface: "#fbfcfd"
  ink: "#202326"
  muted: "#55606d"
  line: "#cfd6de"
  line-subtle: "#e4e8ed"
  accent: "#1e5b96"
  accent-dark: "#174a7c"
  accent-surface: "#f0f5fa"
  focus: "#1f5fa8"
typography:
  landing:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "clamp(2.15rem, 4.4vw, 2.65rem)"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.018em"
  display:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "clamp(1.9rem, 3vw, 2.25rem)"
    fontWeight: 650
    lineHeight: 1.15
  statement:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "2.15rem"
    fontWeight: 650
    lineHeight: 1.15
    letterSpacing: "-0.014em"
  headline:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 650
    lineHeight: 1.15
  title:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "1.15rem"
    fontWeight: 600
    lineHeight: 1.15
  lede:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "clamp(1rem, 2vw, 1.16rem)"
    fontWeight: 400
    lineHeight: 1.6
  body:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  secondary:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "ui-monospace, Cascadia Mono, Segoe UI Mono, Consolas, monospace"
    fontSize: "0.7rem"
    fontWeight: 600
    letterSpacing: "0.18em"
  wordmark:
    fontFamily: "ui-monospace, Cascadia Mono, Segoe UI Mono, Consolas, monospace"
    fontSize: "0.82rem"
    fontWeight: 650
    letterSpacing: "0.28em"
rounded:
  none: "0"
spacing:
  1: "0.25rem"
  2: "0.5rem"
  3: "0.75rem"
  4: "1rem"
  5: "1.5rem"
  6: "2rem"
  7: "3rem"
  8: "4rem"
components:
  button-primary:
    backgroundColor: "transparent"
    textColor: "{colors.accent}"
    typography: "{typography.secondary}"
    rounded: "{rounded.none}"
    height: "46px"
    padding: "0 1.5rem"
  button-primary-hover:
    backgroundColor: "{colors.accent-dark}"
    textColor: "{colors.surface}"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.secondary}"
    rounded: "{rounded.none}"
    height: "44px"
    padding: "0"
  button-text-hover:
    textColor: "{colors.ink}"
  chip-state:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "2px 0.5rem"
  disclosure:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    typography: "{typography.secondary}"
    rounded: "{rounded.none}"
    padding: "0 0 0 1rem"
  trust-state:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0 0 0 1rem"
---

# Design System: Khepri Landing Concept

`docs/product/KHEPRI_DESIGN_LANGUAGE.md` is the authority. This file records **one surface's
extension of it** — the landing concept at `docs/product/concepts/landing/` — and nothing here
governs `src/`. Where this file and the design language disagree, the design language wins. Where
the design language and this build's stylesheet disagree on a value this surface introduced, the
stylesheet is recorded, because it is the shipped artifact.

The surface is a concept: **no route, no template, no navigation entry.** It must not gain one
outside a slice with an active specification. Law 5 forbids rendering capability that does not
exist, and that includes this page.

## Overview

**Creative North Star: "The Submission Trace"**

The world is unchanged — a governed document, not a dashboard. What this surface adds is proof that
the document can persuade. It takes the same instruments the app uses (a hairline, a type size, one
accent, an inline-start rule) and spends them on a public page that has to convince a stranger, and
it does so without reaching for a single device the world forbids: no shadow, no gradient, no card,
no icon, no second face, no dark panel, no hero screenshot, no logo wall.

Its composition is a trace rather than a feature grid. One synthetic export is named once and then
carried through five numbered stages — exports, semantic admission, deterministic facts, evidence
and refusals, decision — so the visitor watches a file become governed facts instead of reading five
descriptions of what would happen to a hypothetical one. The refusal appears in the first viewport,
in the product's own disclosure shape, with its reason reachable. The page performs admission rather
than describing it.

This surface is also the first Khepri file to actually **consume** the type scale. §2.8 records the
product's largest live seam: `var(--text-*)` appears zero times in all of `src/`, because §2.8.1's
cascade and authority problems block the shipped sheets from reading tokens they do not declare. A
standalone file has neither problem. It declares the scale in its own `:root` and reads it: 40+
`var(--text-*)` uses, 79+ `var(--space-*)` uses, and **zero raw px font-sizes**, against the shipped
product's twelve distinct raw sizes across seventeen declarations. The scale works when a surface
can read it.

**Key Characteristics:**

- Containment from hairline rules and type alone; `--shadow: none`, `--paper` and `--surface` the
  same value, radius 0 on the primary button.
- One accent (`#1e5b96`), used on the primary button, evidence links, focus, and selection — nowhere
  else.
- Monospace as a semantic, never a style: wordmark, region labels, state names, file names, step
  numbers, machine-adjacent values.
- Every state reads as text and shape before colour; the three trust states share one geometry and
  one colour, distinguished by the word and by roman-versus-italic.
- Zero physical directional properties; the Arabic column is a live RTL subtree, not a screenshot.
- One authored motion moment in the whole surface, double-gated, animating a rule and never content.

## Colors

The palette is the shipped one, promoted unchanged from `shell.css` — no new hue, no new step. Only
the tokens this surface actually paints are recorded; the promoted state families (`--ready*`,
`--danger*`, `--track`, `--surface-raised`) are declared in the file's `:root` for fidelity to the
world but are **never painted here**, so they are not part of this surface's system.

### Primary

- **Governed Blue** (`{colors.accent}`): the single accent. Primary button border and text, evidence
  links, and the selection colour. Its deep companion (`{colors.accent-dark}`) is the hover fill and
  the pressed link ink; the pale companion (`{colors.accent-surface}`) appears only as the
  `::selection` background.

### Neutral

- **Paper** (`{colors.paper}`): the page, and every surface on it. `--surface` is the same value by
  design — there is no figure/ground layering to find.
- **Document Ink** (`{colors.ink}`): body and headline text, 15.37:1 on paper.
- **Withheld Grey** (`{colors.muted}`): 6.23:1. Two jobs, and they are one idea — secondary text,
  **and every border that encodes state**. A refusal, a trust state, and the disclosure all take
  this value.
- **Decorative Hairline** (`{colors.line}`): 1.43:1. Section separators, grid rules, the header
  underline, the neutral chip. Never a state border.
- **Inner Hairline** (`{colors.line-subtle}`): the lighter rule used *inside* a region — between
  specimen rows, trace steps, and use cases — so a nested division reads as subordinate to the
  section rule that contains it.

### Named Rules

**The Line/Muted Split.** `--line` is decorative and `--muted` encodes state. A border that tells
the reader what state something is in must clear WCAG 1.4.11's 3:1; `--line` reaches 1.43:1 and
cannot. Audit test: point at any border and ask "does this carry meaning?" If yes and it is `--line`,
it is wrong.

**The Two-Axis Rule.** Operational state and trust state are never fused. `--ready` is the
*operational* Success value; a trust state that borrows it fuses the axes §4.5 keeps apart. Every
trust state on this surface is `--muted`, and the word carries the distinction.

**The Fail-Closed Default.** An unrecognized state inherits the withheld treatment, not a decorative
hairline. `.state`'s base border is `--muted` for exactly this reason: ambiguity resolves to "not
supported", never to "fine".

## Typography

**One face:** Noto Sans Arabic (with Segoe UI, Tahoma fallbacks), both scripts, shipped locally as
package data and addressed relatively — no `@import`, no font host.
**Label/Mono:** `ui-monospace, Cascadia Mono, Segoe UI Mono, Consolas, monospace`.

**Character:** A single humanist sans doing all the hierarchical work through size, measure, and
colour role, with a monospace that is never decorative — it appears only where a value is
machine-adjacent, and its appearance is therefore information.

**Only the Regular (400) weight ships.** Every 600 and 650 declaration on this surface renders as
browser-synthesised faux bold, in both scripts — poor in Latin, worse in Arabic, where the synthesis
thickens the joins. `landing.css` declares `font-weight: 400` on both `@font-face` rules so this is
explicit rather than silent; the shipped `journey.css` omits that descriptor, which is why the same
gap is easy to miss there. This is **an accepted state, not an open defect**: closing it is an asset
change requiring the licence-plus-audited-digest process at
`2026-08-13-client-journey-ui-design.md:214-217`, and the decision is to leave the concept at Regular
with the gap documented. `PROVENANCE.md` holds the detail. The weights recorded in the frontmatter
are what the stylesheet declares, not what the family can draw.

### Hierarchy

- **Landing** (`{typography.landing}`): the surface's one new tier. The `h1` and the close headline
  only — the page's opening and closing statements. Nothing else reads it.
- **Display** (`{typography.display}`): the shipped app `h1` tier, present in the scale and not spent
  on this surface's headline (see the Landing Tier Rule).
- **Statement** (`{typography.statement}`): the largest shipped tier, `--text-2xl`. The two contrast
  quotes — the page's central argument, set above the section headings and level with the close.
- **Headline** (`{typography.headline}`): `--text-xl`. The trace figure that concludes the trace, and
  the parity figures.
- **Title** (`{typography.title}`): `--text-md`. Trace terms, pillar and how-it-works headings,
  parity claims.
- **Lede** (`{typography.lede}`): the hero and section ledes, capped at `--measure-lede` (54ch).
- **Body** (`{typography.body}`): prose and trust-state claims.
- **Secondary** (`{typography.secondary}`): `--text-sm`. Detail text, nav, buttons, disclosure body.
- **Label** (`{typography.label}`): monospace, uppercase, `0.18em`. Region labels, state names,
  chips. Tracking drops to `0.06em` under `[dir="rtl"]`.
- **Wordmark** (`{typography.wordmark}`): monospace at `0.28em`. Real text, never a picture of a name.

### Named Rules

**The Landing Tier Rule.** `--text-display` clamps at 2.25rem — a ceiling chosen for an app `h1`
inside a 1068px shell. Spent unchanged on a 1440px public page it makes the product's opening
statement the same size as a workspace page title. `--text-landing` continues the shipped scale's
~1.23x upper-tier step (1.15 → 1.4 → 1.75 → 2.15, so 2.15 × 1.23 ≈ 2.65rem) and floors at
`--text-2xl`, so a narrow viewport falls back to the largest shipped tier and the token can never
render below the scale. This follows §2.5's precedent, by which `--text-md` and `--text-lg` were
minted and marked "new, not promoted". It is a Persuade-surface tier; an app surface uses
`--text-display`.

**The Monospace Semantic Rule.** Monospace marks machine-adjacent values — wordmark, region labels,
state names, file names, step numbers, evidence links, figures. It never sets prose. If a monospace
run would read as a sentence, it is the wrong face.

**The Latin Tracking Rule.** Negative tracking is a Latin display convention and damages Arabic
joins. Every negatively tracked element reverts to `letter-spacing: 0` under `[dir="rtl"]`; every
positively tracked uppercase label loosens to `0.06em`.

**The Three-Value Axis.** 400 / 600 / 650, and nothing else. 650 rather than 700 on the wordmark and
the state names: a weight the system declares nowhere is a fourth value on a three-value axis.

## Layout

A single centred shell of `min(100% - 2rem, 1068px)`, with an inner bleed padding of
`clamp(1rem, 4.8vw, 3.6rem)`; the gutter lives inside the `min()`, so no media query is needed to
keep content off the edge. Vertical rhythm runs on the shipped 4px ramp — nothing off-scale, nothing
minted.

The page has three chapters and they are given room: the trace (the demonstration), the states (the
argument) and the parity pair (the proof) take fluid `clamp()` intervals up to 6rem, while the
supporting matter — pillars, how-it-works, use cases — stays a step tighter at `{spacing.7}`. Equal
padding across all sections would give a governed document seven equal intervals and no chapters.

**Measures are named for roles, not scattered as literals.** The shipped pair is
`--measure-heading` (24ch) and `--measure-prose` (62ch); this surface adds three, all in character
units so the cap follows the text rather than the viewport — which matters most when the text is
Arabic:

- `--measure-lede: 54ch` — hero and section ledes. Wider than the journey's document because this
  surface is read once, at leisure, rather than worked in.
- `--measure-statement: 26ch` — a short declarative passage set large: the two contrast quotes, and
  only those. A tight measure is what keeps a big line from running the whole shell.
- `--measure-note: 42ch` — supporting prose beside or beneath a heading.

**Responsive behaviour is wrap-first.** Every grid uses `repeat(auto-fit, minmax(min(Npx, 100%), 1fr))`,
so the page reflows on its own with no encoded guess about which column goes first. Two floors do
real measured work: the trace's 186px floor prevents a 2-up grid at phone widths that stranded step
05 alone on a last row, and the parity pair's `min(300px, 100%)` lets a track collapse below its own
floor at 320px, where a bare 300px floor overflowed the content box by a measured 27px.

There is **one breakpoint**, at 640px, mirroring the journey's single rule. It does narrow-width
adjustment only — no component, no colour, no topology change: the primary action goes full width
and first, the hero becomes one reading order, and vertical rules between siblings become horizontal
ones. `.state` is deliberately absent from that list, because its inline-start rule is the state
itself and never divided a column.

Verified over the live DOM: zero horizontal overflow at 320 / 390 / 414 / 640 / 768 / 1024 / 1280 /
1440; zero interactive targets under 44px at 320px; zero physical directional properties in the
stylesheet.

### Named Rules

**The Wrap-Before-Break Rule.** Prefer an `auto-fit` floor to a media query. A breakpoint encodes a
guess about content order; a floor lets the content decide. Reach for the 640px block only when
reflow alone cannot hold the invariant.

**The 320px Invariant.** `body { min-width: 320px }` ships, so 320 must hold. Any fixed grid floor
must be wrapped in `min(floor, 100%)` or it will overflow there.

## Elevation & Depth

**There are no shadows.** `--shadow: none`, `--paper` and `--surface` are the same `#fbfcfd`, and the
stylesheet contains not one `box-shadow`, gradient, or raised card. This is the thesis, not an
unfinished figure/ground, and the absence of an elevation ramp is a recorded deliberate absence.

Depth is carried entirely by two instruments. **Hairlines** separate: `--line` between sections and
around regions, `--line-subtle` for divisions inside a region, so nesting reads through rule weight
rather than through stacking. **Type and space** do the rest: a size change, a measure change, and a
chapter-scale interval separate what a card would otherwise have boxed.

### Named Rules

**The No-Elevation Rule.** If a region needs to feel separate, give it a hairline, a type-size
change, or more space. Never a shadow, never a fill, never a card. A raised surface here is not a
style choice — it breaks Law 1.

## Shapes

`border-radius: 0` on the primary button and on everything else that could take one; `--radius-sm`
(3px) is promoted from the shipped palette and is **never used on this surface**. The form language
is orthogonal: rules, columns, and text blocks, with no rounding, no clipping, and no silhouette.

Borders are the only geometry. Three weights carry three meanings: a 1px `--line` rule separates
regions, a 1px `--line-subtle` rule separates rows inside one, and a **4px `--muted` inline-start
rule** marks a passage that has a state. That 4px rule is §4.6's mandated disclosure shape — 4px
rather than a hairline because `report.print.css` drops the refusal tint (a printer may not honour
background graphics), so the border alone must carry the state onto paper.

### Named Rules

**The Disclosure Shape.** A passage with a state takes a 4px `--muted` inline-start rule plus italic.
The rule and the italic each carry the meaning independently, so neither colour nor face is doing the
work alone. Never `--danger`: painting a governed refusal red says something went wrong, and nothing
did.

## Components

### Buttons

- **Shape:** square (`border-radius: 0`), 46px tall.
- **Primary:** transparent fill, 1px `--accent` border, `--accent` text, `{spacing.5}` inline
  padding. Never a filled block.
- **Hover / Focus:** hover inverts to an `--accent-dark` fill with paper text over a 150ms ease-out
  on colour only; focus is the one shared mechanism — `3px solid var(--focus)`, offset 3px. Under
  reduced motion the transition is removed.
- **Text (secondary):** no border, no padding, `--muted` underlined at `0.2em` offset, 44px minimum
  height, darkening to `--ink` on hover. One primary per view; the secondary action is always text.

### Chips

- **Style:** hairline border, no fill, `--muted` monospace uppercase at `0.08em`, 2px block padding.
  A chip is a bordered word, never a coloured pill.
- **State:** a chip that *encodes* state (`.chip--state`) takes a `--muted` border rather than
  `--line`, because that boundary carries meaning and must clear 3:1. A decorative chip keeps
  `--line`.

### Containers

There are no cards. A region is a `<section>` with a `--line` block-end rule and a chapter-scale
padding interval; a group inside it is a grid whose cells are divided by `--line-subtle` logical
borders. Internal padding comes from the 4px ramp only.

### Navigation

Sticky hairline header, 64px minimum, `--surface` background, `--line` block-end rule. Links are
`--text-sm` `--muted` at 44px minimum height, darkening to `--ink` on hover with no underline and no
active pill. The language control carries `lang` on itself so a screen reader pronounces the target
language in that language, and reveals a `--muted` block-end rule on hover. No directional glyph is
used as an affordance — an arrow does not mirror.

### The Disclosure

The canonical "this passage has a state" component, and the surface's most load-bearing shape. 4px
`--muted` inline-start rule, `{spacing.4}` inline-start padding, `--muted` italic body at
`--text-sm`, with the reason on its own line in upright monospace `--text-xs`. It appears in the
first viewport, inside the hero specimen, withholding one figure and naming why.

### The Trust State

Three blocks sharing **one geometry and one colour**: 4px `--muted` inline-start rule, monospace
`--text-xs` uppercase name at 650, a `--text-base` claim, `--muted` detail, and a monospace evidence
link in `--accent`. The refused variant is distinguished by italic and by dropping its claim to 400 —
two channels, neither of them colour. All three names read identically in colour, in greyscale, and
to a screen reader, which is what "colour never carries a distinction alone" actually requires.

### The Specimen

The hero's second column: one export mid-admission. A monospace file name (`dir="auto"`, because a
file name is customer-controlled) beside a neutral state chip, a `--line` block border, and four
governed rows — term in `--ink`, value in monospace `--text-xs` uppercase, tabular numerals, 44px
minimum row height, divided by `--line-subtle`. Below them, the disclosure. Not a chart, not a
screenshot: a governed document fragment showing the mechanism running on one file.

### The Trace (signature component)

The page's spine and the reason the composition is not a feature grid. Five numbered steps in one
`auto-fit` row above ~1000px, divided by logical `--line-subtle` borders that mirror in RTL without a
second declaration. Each step carries a monospace index, a `--text-md` term, a `--text-sm` detail,
and — the line that makes it a trace — a monospace state line showing what the *same* export looks
like at that stage. Step 04, where the refusal is minted, takes the disclosure shape on its
inline-start edge and sets its state line in the withheld treatment: the page states its thesis in
the product's own vocabulary rather than describing it.

**The one authored motion moment.** The world had none, so exactly one was authored, and it is the
page's subject given its motion: `@keyframes trace-rule-draw` scales each step's inline-start rule
from `scaleY(0)` to `scaleY(1)` on arrival via `animation-timeline: view()` over an
`entry 10% cover 22%` range, so admission is seen proceeding stage by stage. Four constraints make it
safe. It is **double-gated** behind `@supports (animation-timeline: view())` and
`prefers-reduced-motion: no-preference`. It animates **`transform` only**, so it never triggers
layout. It is drawn by a **pseudo-element**, not by animating the border, so the disclosure border's
state meaning is never mid-transition. And **the finished state is the un-animated default** — every
word is present, positioned and readable at frame zero, so a visitor who lands mid-animation, blocks
CSS animation, or screenshots the page loses nothing but the drawing.

### The Parity Pair

Two live specimens sharing one governed fact set, not a screenshot of a translation. The Arabic panel
is a real subtree with `lang="ar"` and `dir="rtl"`, so it mirrors natively, takes Arabic-Indic digits
from the markup, and drops the Latin negative tracking. The two panels are divided by a logical
`--line` border that becomes a horizontal one below 640px.

## Do's and Don'ts

### Do:

- **Do** promote values from `shell.css` unchanged. Every colour, space, and type tier on this
  surface came from the shipped file; the four additions (`--text-landing`, `--measure-lede`,
  `--measure-statement`, `--measure-note`) each carry their derivation and their role in the
  stylesheet, per §2.3.
- **Do** read the type scale through `var(--text-*)`. Zero raw px font-sizes is the property that
  makes this surface the scale's first consumer; a literal size reintroduces the seam §2.8 records.
- **Do** use `--muted` for any border that encodes state, and `--line` only for decoration.
- **Do** give a passage with a state the 4px `--muted` inline-start rule plus italic — the shape the
  product already uses. Three `side-tab` detector findings stand deliberately for this reason
  (`landing.css` L548, L659, L824); the shape stays flagged and the reason stays recorded rather than
  being silenced with a file-level ignore.
- **Do** name a measure for the role it serves when it is used more than once, and leave a genuine
  one-off as a literal — `.close-headline`'s `max-width: 20ch` is deliberately untokenized, because a
  token there would imply a shared role that does not exist.
- **Do** revert negative tracking and loosen uppercase tracking under `[dir="rtl"]`.
- **Do** keep every interactive target at 44px minimum on the element a finger lands on, in both
  languages at every viewport.

### Don't:

- **Don't** add a shadow, gradient, raised card, or fill to create separation. Use a hairline, a type
  size, or space.
- **Don't** paint a governed refusal with `--danger`. `--danger` is transport and system error only;
  a refusal is a result, not a failure.
- **Don't** tint a trust state with `--ready` or any operational colour. That fuses the two axes §4.5
  keeps apart — and three coloured 4px side rules in a row is the craft floor's refused side-tab
  pattern with the §4.4 citation quietly removed.
- **Don't** set prose in monospace, or use monospace anywhere a value is not machine-adjacent.
- **Don't** place a region label above the `h1`. `.region-label` is a structural landmark *inside* a
  governed document — it is not licence for an eyebrow over a headline.
- **Don't** introduce a fourth font weight, a second typeface, or an icon set. Each is a recorded
  deliberate absence, and a new face requires the licence-plus-audited-digest process.
- **Don't** treat `PROVEN / CAVEATED / REFUSED` as shipped labels. §4.5 constraint 1 gates the
  customer-facing trust vocabulary on programme `T1`, which has **no registry entry**. The shape is
  durable; the three words are PROVISIONAL and marked as such in the markup.
- **Don't** add a physical directional property. Zero is a verified property across all shipped
  stylesheets and this one; `left`, `right`, `margin-left`, `text-align: left` are all out.
- **Don't** fabricate a customer, testimonial, benchmark, price, licence, or deployment claim on this
  surface, and label synthetic demonstration material wherever a visitor could mistake it for a real
  claim.
- **Don't** give this concept a route, template, or navigation entry outside a slice with an active
  specification.
