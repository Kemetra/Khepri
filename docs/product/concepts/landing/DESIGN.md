---
name: Khepri — The Register Wall
description: The public marketing surface's own visual world — warm stone registers cut into one wall, where gold means proven and a refusal is set into the band where the answer would have been.
colors:
  stone-900: "#12100e"
  stone-800: "#1a1714"
  stone-700: "#241f1a"
  stone-600: "#352e26"
  withheld: "#9a8d7e"
  papyrus: "#ede4d3"
  papyrus-dim: "#a89e8c"
  gold: "#d4a83a"
  egyptian-blue: "#4a9fc4"
  egyptian-blue-dim: "#2c6a87"
  ochre: "#c97b5a"
typography:
  monument:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "clamp(2.6rem, 7.2vw, 6.5rem)"
    fontWeight: 400
    lineHeight: 0.95
    letterSpacing: "-0.032em"
  register:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "clamp(1.9rem, 3.6vw, 3.2rem)"
    fontWeight: 400
    lineHeight: 1.12
    letterSpacing: "-0.026em"
  statement:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "3rem"
    fontWeight: 400
    lineHeight: 1.12
    letterSpacing: "-0.014em"
  quote:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "2.2rem"
    fontWeight: 400
    lineHeight: 1.12
    letterSpacing: "-0.016em"
  lede:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "clamp(1.0625rem, 1.5vw, 1.3rem)"
    fontWeight: 400
    lineHeight: 1.6
  title:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 400
    lineHeight: 1.12
  body:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.6
  detail:
    fontFamily: "Noto Sans Arabic, Segoe UI, Tahoma, sans-serif"
    fontSize: "0.82rem"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "ui-monospace, Cascadia Mono, Segoe UI Mono, Consolas, monospace"
    fontSize: "0.7rem"
    fontWeight: 400
    letterSpacing: "0.28em"
rounded:
  none: "0"
  disc: "50%"
spacing:
  s2: "0.5rem"
  s3: "0.75rem"
  s4: "1rem"
  s5: "1.5rem"
  s6: "2rem"
  s7: "3rem"
  s8: "4rem"
  s9: "6rem"
  s10: "9rem"
components:
  button-primary:
    backgroundColor: "transparent"
    textColor: "{colors.gold}"
    rounded: "{rounded.none}"
    padding: "0 2rem"
    height: "52px"
  button-primary-hover:
    backgroundColor: "{colors.gold}"
    textColor: "{colors.stone-900}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.papyrus-dim}"
    rounded: "{rounded.none}"
    padding: "0"
    height: "44px"
  button-ghost-hover:
    textColor: "{colors.papyrus}"
  state-mark-admitted:
    backgroundColor: "transparent"
    textColor: "{colors.egyptian-blue}"
    rounded: "{rounded.none}"
    padding: "3px 0.75rem"
    typography: "{typography.label}"
  course-value-proven:
    backgroundColor: "transparent"
    textColor: "{colors.gold}"
    typography: "{typography.detail}"
  course-withheld:
    backgroundColor: "transparent"
    textColor: "{colors.papyrus-dim}"
    rounded: "{rounded.none}"
    padding: "0 0 0 1.5rem"
  verdict-proven:
    backgroundColor: "transparent"
    textColor: "{colors.papyrus}"
    rounded: "{rounded.none}"
    padding: "0 0 0 1.5rem"
  verdict-caveated:
    backgroundColor: "transparent"
    textColor: "{colors.papyrus}"
    rounded: "{rounded.none}"
    padding: "0 0 0 1.5rem"
  verdict-withheld:
    backgroundColor: "transparent"
    textColor: "{colors.papyrus-dim}"
    rounded: "{rounded.none}"
    padding: "0 0 0 1.5rem"
  method-index:
    backgroundColor: "{colors.stone-900}"
    textColor: "{colors.egyptian-blue}"
    rounded: "{rounded.disc}"
    size: "3.1rem"
    typography: "{typography.label}"
  nav-link:
    backgroundColor: "transparent"
    textColor: "{colors.papyrus-dim}"
    height: "44px"
  nav-link-hover:
    textColor: "{colors.papyrus}"
---

# Design System: Khepri — The Register Wall

> **Scope, and its limit.** This file records the visual world of the **public marketing surface
> only**, as built at `docs/product/concepts/landing/`. It has no authority over `src/khepri/`, over
> `/app`, or over `/beta`. The Khepri application is governed by
> `docs/product/KHEPRI_DESIGN_LANGUAGE.md`, whose Law 1 — containment from rules and type, never
> elevation; no shadows, no gradients — is untouched by this work and remains in force for the app.
> The owner decided explicitly that the marketing surface gets its own identity. Two registers, one
> product thesis. Nothing here proposes a change to the shipped world, and no token here is imported
> by it.
>
> This surface has **no route, no template, and no navigation entry**, and must not gain one outside
> a slice with an active specification.

## Overview

**Creative North Star: "The Register Wall"**

Egyptian register composition was a data-graphics system before it was art. Content is organised into
horizontal bands with strict shared baselines, read in a fixed order, and figures are scaled by
significance rather than by perspective distance. That is structurally what a governed report is:
banded facts, ordered, each on its baseline, sized by importance. The page is therefore built as
eight registers cut into one stone wall — a claim register, six numbered courses (II through VII),
and a closing register — sharing one measure and one gutter so they read as courses of a single wall
rather than as stacked boxes.

The reference is taken as **composition, never as ornament**. There is not one hieroglyph, papyrus
texture, or pyramid silhouette in the build. The sole iconographic element on the page is an 11px
gold disc — the sun mark on the wordmark — drawn as pure geometry. The palette is likewise derived
from material rather than picked: granite and limestone for the ground, gold leaf for a proven
figure, Egyptian blue (the first synthetic pigment, made in Egypt c. 2500 BCE) for structure and
admission, red ochre for a caveat because red marked headings and corrections in the scribe's
palette. The stone ramp is deliberately **warm** — a measurable amber cast at 30° hue — because a
cool near-black would read as generic dark-mode SaaS, which is the rut this direction refuses.

The system's single most transferable idea was donated by a declined phosphor-terminal challenger:
**state prints itself into the register as content, never as chrome.** A refusal or a caveat is set
into the band where the figure would have been, on the same baseline as the proven figures, with a
4px inline-start rule and italic carrying it. It is never a floating badge, toast, pill, or overlay.
This agrees exactly with the product's own §4.6, which requires a refusal to stay where the answer
would have been: the marketing world changed, the product's law about refusal did not.

**Key Characteristics:**

- Eight horizontal registers on one shared measure (`1240px` max), cut apart by incised rules
- A warm four-step stone ramp on a dark ground, `#12100e` through `#352e26`
- Gold reserved semantically for proven value; blue for structure and admission; ochre for a caveat
- One typeface, Regular 400 only; monumental weight from scale and tracking, never from a weight axis
- Every state encoded three ways at once — the word, the rule colour, and roman-versus-italic
- Zero physical directional properties; `lang`/`dir` as real subtrees, mirrored natively
- One authored motion grammar ("the sun's passage") in nine keyframes, all double-gated
- Zero radius on every surface except the sun mark and the method spine's indices
- Contrast computed against each element's own ground, never asserted against the page ground

## Colors

A warm quarried ground carrying three semantic pigments and one derived state ink; the ramp is
material rather than a hue picked for effect.

### Primary

- **Gold Leaf** (`--gold`): the proven mark. It takes a figure that reconciled with its evidence
  (`.course-value--proven`, `.script-figure`), the wordmark's sun disc, the primary action's border
  and hover fill, and the headline word the page stakes its claim on. It also carries **interactive
  confirmation** — the focus ring, the skip link, and link hover — which is the one non-semantic job
  it holds. It never reaches prose and never carries a structural rule.

### Secondary

- **Egyptian Blue** (`--egyptian-blue`): structure and admission. Carries the ADMITTED state mark's
  border and word, the passage's state lines, the method indices, and evidence links. Its resting
  step, **Egyptian Blue Dim** (`--egyptian-blue-dim`), draws the register-mark rule and the passage
  indices — a rule at rest, never a state border. The full pigment is required wherever the border
  encodes state: the dim step measures 2.87:1 on the specimen ground and fails 1.4.11 there, while
  the full pigment measures 5.02:1.

### Tertiary

- **Red Ochre** (`--ochre`): a caveated figure — present, qualified, conditioned. It is drawn from
  the scribe's two-colour system where red marked headings and corrections against black body text.
  It is **explicitly not an error colour**; nothing broke.

### Neutral

- **Deepest Cut** (`--stone-900`): the page ground, and the fill inside the method spine's indices.
- **Lifted Band** (`--stone-800`): a register lifted out of the ground (`.register--deep`),
  alternating down the wall so no two adjacent registers share a ground.
- **Register Field** (`--stone-700`): the field inside a register — course dividers, cell rules, the
  method spine. This is the **lightest ground a state border is ever drawn on**, which is what sets
  `--withheld`'s lightness.
- **Incised Rule** (`--stone-600`): the top edge of every register and the decorative structural
  rules. Decorative weight by declaration — it never encodes state.
- **Weathered Stone** (`--withheld`): the state-border ink for a withheld or unresolved figure.
  Derived, not picked: the same hue and saturation as the stone ramp (30°, 12%) lifted to **L58**,
  the lightness at which it clears 3:1 against the *lightest* ground it is ever drawn on. Measured
  5.31:1 on `--stone-900`, 4.62:1 on `--stone-800`, 3.94:1 on `--stone-700` — one token correct
  everywhere, with no per-ground variant to drift. It reads as weathered stone rather than as a
  colour, which is what a withheld state should look like here: present, cut, deliberately unfilled.
- **Papyrus** (`--papyrus`): body and headline ink, 13.71:1 on the page ground.
- **Papyrus Dim** (`--papyrus-dim`): secondary prose, lede, details, and every withheld or
  questioning voice, 6.42:1 on the page ground.

### Named Rules

**The Scarcity Rule.** Gold means *proven*, and interactive confirmation. It marks a figure that
reconciled with its evidence, the sun mark, the primary action, and the focus/skip/hover
affordances — nothing else. It never colours prose and never carries a structural rule. When gold
leaked into a prose emphasis it both broke scarcity and *inverted* the meaning, marking a refused act
as proven; the italic carried that turn on its own instead.

**The Derived Border Rule.** A border that encodes state must clear **3:1 against the ground it
actually sits on**, not against the page ground. Derive the token by lifting the ramp's own hue and
saturation until it clears against the *lightest* ground it can ever appear on; then one token is
correct everywhere. The first draft's border was tuned against the page ground alone and measured as
low as 1.72:1 where it was actually used.

**The Not-Red Rule.** A refusal never borrows the error palette. Withheld is weathered stone; a
caveat is red ochre, and even ochre is not an error colour. Nothing broke — Khepri declined to
answer, which is a governed result.

**The Three-Carrier Rule.** Every state is encoded three ways at once — the **word**, the **rule
colour**, and the **roman-versus-italic face**. Any one alone identifies the state, so it survives
greyscale, a colour-blind reader, and print. Colour never carries a distinction alone.

## Typography

**Display Font:** Noto Sans Arabic, Regular 400 (with Segoe UI, Tahoma, sans-serif)
**Body Font:** Noto Sans Arabic, Regular 400 — the same face
**Label/Mono Font:** `ui-monospace`, Cascadia Mono, Segoe UI Mono, Consolas, monospace

**Character:** One face, both scripts, one weight — set from a whisper at 0.7rem to 6.5rem, so the
page reads as a single voice cut at different sizes, which is exactly how monumental Egyptian
lettering worked. Machine-adjacent values take the monospace stack and heavy tracking, so a figure
looks measured rather than written.

**No second typeface, by decision.** An imported Latin display face would apply to English and not to
Arabic, making one script the designed one and the other a fallback — on a page whose thesis is
parity, that is the one thing that must not happen. Display weight therefore comes from **scale and
tracking**, not from an imported face.

**Only Regular (400) ships**, and both `@font-face` rules declare `font-weight: 400` so the gap is
explicit rather than silent. This is an accepted state decided by the owner, not an open defect:
adding a face requires the licence-plus-audited-digest process, and `PROVENANCE.md` holds the digests
and the detail. The design compensates by **not leaning on weight at all** — hierarchy is carried by
scale, colour role, tracking, and register position. Every heading in the build declares
`font-weight: 400` explicitly, because a UA default `bold` on a family with no bold axis renders
browser-synthesised and degrades Arabic joins harder than Latin.

### Hierarchy

- **Monument** (400, `clamp(2.6rem, 7.2vw, 6.5rem)`, 0.95, `-.032em`): the page's voice. The claim
  headline only, held to a 15ch measure and balanced.
- **Register** (400, `clamp(1.9rem, 3.6vw, 3.2rem)`, 1.12, `-.026em`): the passage figure and the
  closing headline — the page's thesis cut at register scale.
- **Statement** (400, `3rem`, 1.12, `-.014em`): the script panels' headline figures, tabular.
- **Quote** (400, `2.2rem`, 1.12, `-.016em`): the two contrast quotes in Register III.
- **Lede** (400, `clamp(1.0625rem, 1.5vw, 1.3rem)`, 1.6): the claim's supporting paragraph, 46ch.
- **Title** (400, `1.25rem`, 1.12): passage terms, verdict claims, pillar and method headings.
- **Body** (400, `1.0625rem`, 1.6): the base, and the withheld course's term.
- **Detail** (400, `0.82rem`, 1.6): secondary prose, course terms and values, notes; 40–52ch.
- **Label** (mono, 400, `0.7rem`, `.28em`, uppercase): register marks, state marks, verdict names,
  passage and script labels, withheld reasons, the colophon mark.

### Named Rules

**The Machine-Adjacent Rule.** Monospace marks machine-adjacent **values** only — data,
measurements, state tokens, file names, register numbers. It never sets prose and never sets a
control label. "View evidence" is prose naming an action, so it is set in the body face; a control
label in mono is a costume.

**The Tracking Parity Rule.** Negative tracking is a Latin display convention that damages Arabic
joins, and it matters far more at monumental scale than at app scale. Every negatively-tracked
element resets to `letter-spacing: 0` under `[dir="rtl"]`, and heavily-tracked mono labels drop from
`.28`–`.34em` to `.1em`.

**The Weight-Free Rule.** Declare `font-weight: 400` on every heading. The family ships one weight;
an undeclared heading inherits the UA's `bold` and renders synthesised. Hierarchy is carried by
scale, colour role, tracking, and register position instead.

## Layout

The page is **one wall**. Every register shares a single measure — `min(100% - 2.5rem, 1240px)`,
centred — with the gutter inside the `min()` so no media query is needed to keep content off the
edge. That shared margin is what makes the bands read as courses of one wall.

**The register.** Each is a full-bleed horizontal band with `padding-block:
clamp(4rem, 8vw, 9rem)`, cut from the wall by an incised rule at its top edge. Grounds alternate:
plain registers sit on the page ground, `.register--deep` registers sit on `--stone-800`, so no two
adjacent registers share a ground.

**Spacing rhythm.** A 4px-based ramp extended for monumental scale: `0.5 / 0.75 / 1 / 1.5 / 2 / 3 /
4 / 6 / 9rem`. Register padding, section gaps, and grid gutters all `clamp()` between two adjacent
steps, so the page compresses smoothly rather than at a breakpoint.

**Grids are intrinsic, not queried.** Every multi-column region uses
`repeat(auto-fit, minmax(min(<floor>, 100%), 1fr))` — passage 210px, verdicts 260px, contrast 300px,
pillars 250px, uses 220px, scripts 320px. The `min()` wrapper is what guarantees the page can never
overflow at 320px; the body carries `min-width: 320px`.

**Measures.** Monument 15ch, lede 46ch, note 40ch, quote 22ch, close headline 18ch, method detail
52ch, use question 30ch. Prose is never allowed to run the full 1240px.

**Registers pace by treatment, not only by height.** Registers II, III, IV and VII are plain grid
registers; **Register V is the page's one procedural treatment** — a numbered descent read down a
continuous vertical spine with circular indices — and **Register VI carries questions** in the
reader's own voice. When those three shared one primitive across roughly a quarter of the page, the
first-time read dropped from distinctive to merely competent.

**One breakpoint, at 660px**, doing narrow-width adjustment only: it introduces no component,
changes no colour, and alters no topology. It makes actions full-width, converts vertical column
dividers to horizontal ones (so an inline-start border can never be mistaken for the withheld state
shape), collapses the method spine to two columns, and drops the four section links from the sticky
header — which had wrapped to three rows and held 212px of an 844px phone viewport. The language
control stays: parity is not an optional affordance.

**Interactive targets** are never below **44px** (`--touch-min`); the primary action is 52px. Zero
targets measure under 44px at 320px.

### Named Rules

**The Logical-Properties Rule.** Zero physical directional properties. Every inset, margin, padding,
border and size is logical (`inset-block-start`, `padding-inline`, `inline-size`,
`border-inline-start`), and `lang`/`dir` are real subtrees so the browser mirrors natively and
renders Arabic-Indic digits from the markup. The only surviving `width` is the wall's own `min()`
measure, which is direction-neutral.

**The Intrinsic Reflow Rule.** A grid earns its columns from `auto-fit` and a `min()`-wrapped floor.
Reach for a media query only for a genuine narrow-width adjustment, never to build a layout.

## Elevation & Depth

This world is **incised, not elevated**. Depth comes from cutting into stone, not from lifting
surfaces off it: there is no card shadow, no drop shadow under a container, and no elevation ramp.
Every surface sits flush in the wall and is defined by the rule cut around it.

The one material claim the world spends an effect on is the **incised rule** at each register's top
edge, and it must actually be perceptible. A real cut has three parts and all three are drawn: a dark
shadow line at the top of the cut, a bright lit lip just below it where light catches the lower edge,
and a soft falloff beneath that returns to the stone. A first draft used a single
`rgba(237,228,211,.045)` lip that measured an **8/255 lift** against the band below — below
perceptual threshold, so every boundary read as a flat hairline and the promise was structurally
real but visually absent. The lip is now roughly four times that value.

Ambient light comes from two radial sun fields — one low behind the claim, one risen at the foot of
the wall — at 13% and 11.5% gold opacity. They are light sources, not decorative blobs: each sits at
one edge, warm, so everything above is darker than everything below, which is what gives the stone
its rake. Both are suppressed in print.

### Shadow Vocabulary

- **Incised rule** (`border-block-start: 1px solid var(--stone-600)` + `box-shadow: inset 0 1px 0
  rgba(237,228,211,0.17), inset 0 6px 12px -6px rgba(0,0,0,0.55)`): the cut between two registers.
  The only structural depth on the page.
- **Sun mark glow** (`box-shadow: 0 0 14px rgba(212,168,58,0.55)`): the single outer glow in the
  system, belonging to the 11px wordmark disc alone.
- **Header veil** (`background: rgba(18,16,14,0.86)` + `backdrop-filter: blur(14px)`): the sticky
  header reads as a translucent stone face rather than as a floating bar.

### Named Rules

**The Incision Rule.** Depth is cut, not stacked. A boundary is a three-part cut — shadow line, lit
lip, falloff — and a surface is never raised off the wall by an outer shadow. If a lip is not
perceptible against the band below it, it is not a cut; measure it.

**The One Glow Rule.** The only outer glow on the page belongs to the sun mark. Actions fill on hover
rather than glowing: this world is cut stone and leaf, not neon.

## Shapes

**Zero radius, everywhere, with two exceptions.** Buttons, cards, specimens, state marks and every
container are square-cornered (`border-radius: 0` declared on the button so no UA default leaks in),
because a cut in stone has no fillet. The two exceptions are both discs: the 11px sun mark on the
wordmark, and the method spine's 3.1rem circular indices — a disc reads as a stamped seal against a
wall of rectangles, which is why it is reserved for the mark and the count.

The recurring form language is the **rule**: a 1px line that separates, and a **4px inline-start
rule** that means. The two thicknesses are never interchangeable. Every register, cell, course and
column divider is 1px in a decorative stone step; every state tab is 4px in a semantic ink. At narrow
width the vertical 1px column dividers become horizontal ones precisely so a 1px inline-start rule
can never be confused for the 4px state shape.

Borders on state marks are hairline boxes with no fill and no pill — a rule and a word, never a
filled chip.

### Named Rules

**The Square Cut Rule.** Radius is zero on every surface. Only the sun mark and the method indices
are discs, and their circularity is the signal.

**The Two Rules Rule.** 1px in a stone step separates; 4px in a semantic ink means. Never draw a
state at 1px and never draw a divider at 4px.

## Components

### Buttons

- **Shape:** square (`border-radius: 0`), never filled at rest.
- **Primary:** a gold hairline box on transparent, gold uppercase label at `0.82rem` with `.14em`
  tracking, `2rem` inline padding, `52px` minimum block size. The primary action is gold because
  requesting access is the page's one proven-value action.
- **Hover / Focus:** fills solid gold with the page ground as the label colour, transitioning
  `background-color` and `color` over 620ms on the sun ease. It fills; it does not glow. Focus is the
  global 2px gold outline at 4px offset.
- **Ghost:** no border, no padding, dim papyrus, underlined, `44px` minimum block size; hover lifts
  to full papyrus.
- **Narrow width:** both actions go full-width below 660px.

### Cards / Containers

There are no cards. Containers are **registers and cells**: full-bleed bands and grid cells separated
by 1px rules, with no radius, no shadow, and no background of their own beyond the alternating
register ground. The one exception is the **specimen**, which takes a 1px `--stone-600` box and a
subtle vertical gradient between two translucent stone steps to read as a document laid on the wall.

- **Internal padding:** `clamp(1rem, 3vw, 2rem)` inline on the specimen and its courses;
  `clamp(2rem, 4vw, 3rem)` block on grid cells.

### Navigation

- **Style:** a sticky translucent stone header, 72px minimum, with a `backdrop-filter` blur and a 1px
  bottom rule. Links are dim papyrus at `0.82rem`, no underline, `44px` minimum target, transitioning
  to full papyrus on hover over 620ms.
- **Wordmark:** the 11px gold sun disc plus real text in the mono face at `.34em` tracking — real
  text so speech input can operate the control.
- **Mobile:** below 660px the four section links are dropped rather than hidden behind a disclosure
  the concept does not implement; the wordmark, the primary action and the language control remain.
- **Skip link:** off-canvas until focused, then a gold hairline box on the page ground at 44px.

### The State Mark

A hairline box and a word — no fill, no pill. Mono, `0.7rem`, `.18em` tracking, uppercase, 3px by
0.75rem padding. The ADMITTED variant takes the **full** Egyptian blue on both border and word, not
the dim step, because the border encodes state and both carriers must clear their thresholds.

### The Withheld Course (signature)

The system's signature component, and the one thing on this page a competitor cannot copy.

A refused figure is set **into** the register where the figure would have been — its own course, on
the same baseline as the proven ones. The treatment is a **4px inline-start rule in weathered
stone**, `1.5rem` of inline-start padding, dim papyrus, and **italic**; beneath it a
`withheld-reason` line returns to roman mono at `0.7rem` with `.12em` tracking, because the reason is
a machine-adjacent state token. Rule, word and italic each carry the state independently.

The same shape recurs, deliberately and identically, in five places: the specimen's withheld course,
the passage's refusing step, the withheld verdict, the script panel's withheld line, and the verdict
column's default. That repetition is the point — one shape, one meaning, everywhere a refusal
appears. In the passage it must be written as a compound selector
(`.passage-step.passage-step--withheld`) so it outscores the sibling divider; declared plainly it
lost specificity outright and the disclosure shape was absent at desktop width, where most visitors
meet it.

### The Verdict Trio

Three columns sharing one 4px inline-start rule, differing only in ink and face: **proven** takes
gold with a roman name, **caveated** takes ochre with a roman name, **withheld** takes weathered
stone with an italic body. Names are mono, `0.7rem`, `.28em`, uppercase. The evidence link is body
face — not mono — dim Egyptian blue, underlined, 44px, warming to gold on hover.

### The Method Spine (signature)

Register V's procedural treatment: a continuous 1px vertical rule running through 3.1rem circular
indices, so four steps read as one descent rather than four independent rows. The spine stops
halfway through the last step, because a sequence ends. Indices are mono, Egyptian blue, filled with
the register's own ground so the spine appears to pass behind them.

### Motion — the sun's passage

**One authored grammar in nine keyframes**, not scattered effects. Two eases and two durations govern
everything: `cubic-bezier(0.16, 0.84, 0.28, 1)` at 1100ms and 620ms. Nothing overshoots — the sun's
passage is slow and inevitable.

**The admission sequence (on load).** The specimen performs the product. `value-arrives` brings each
course value in; `figure-resolves` brings a proven figure in dim and then takes gold as it
reconciles, over 1500ms; the four courses stagger at 420 / 700 / 980 / 1260ms so the reader watches
admission proceed course by course. `mark-stamps` stamps the ADMITTED mark onto the file at 260ms.
The refusal arrives **last and slowest** — `withheld-settles` at 1700ms, and `withheld-rule-cuts`
drawing its rule *downward* into the register at 1900ms, because a withheld figure is the considered
outcome, not the quick one.

**Ambient and accent.** `sun-breathes` is one 24s opacity loop behind the claim, because a stone wall
lit by a moving sun is never quite still. `claim-underlines` draws the gold rule under "prove" — the
page marking its own claim the way it marks a proven figure.

**Scroll-driven.** `rise-into-light` brings each register's contents up as the light reaches them and
`rule-open` draws the incised rule across the wall, both on `animation-timeline: view()` over an
`entry 4% cover 26%` range.

### Named Rules

**The Frame-Zero Rule.** Content is visible and correct at frame zero. Every animation runs from a
visible state to a visible state, and the un-animated default *is* the finished page. A client with
no view-timeline support, no JS, reduced motion, or a print stylesheet sees the resolved figures
immediately. Nothing is ever hidden waiting for an event that may never fire.

**The Double-Gate Rule.** Scroll-driven motion sits behind both `@supports (animation-timeline:
view())` and `prefers-reduced-motion: no-preference`. Under reduced motion, durations collapse to
`.001ms` rather than to `none` — an animation cancelled outright can strand an element at its `from`
state, while one that completes instantly cannot.

**The Cheap-Property Rule.** Animate `transform`, `opacity` and `color` only. No layout property is
ever animated, so nothing on this page reflows. Where an animation replaces a static border, the
border becomes `transparent` rather than being removed, so the space it occupies never changes.

## Do's and Don'ts

### Do:

- **Do** reserve gold (`#d4a83a`) for a proven figure, the sun mark, the primary action, and
  interactive confirmation. Its scarcity is the mechanism that makes it mean anything.
- **Do** set a refusal or caveat **into** the band where the answer would have been, with a 4px
  inline-start rule and italic, on the same baseline as the resolved figures.
- **Do** encode every state three ways at once — the word, the rule colour, and roman-versus-italic.
- **Do** measure a state border against the ground it actually sits on, and derive the token by
  lifting the ramp's own hue and saturation until it clears 3:1 on the lightest such ground.
- **Do** declare `font-weight: 400` on every heading; the family ships one weight.
- **Do** build multi-column regions from `auto-fit` with a `min()`-wrapped floor, so they reflow
  without a media query and cannot overflow at 320px.
- **Do** use logical properties exclusively and give each script a real `lang`/`dir` subtree.
- **Do** reset negative tracking to `0` under `[dir="rtl"]`, and drop mono label tracking to `.1em`.
- **Do** keep every interactive target at 44px or above.
- **Do** animate `transform`, `opacity` and `color` only, from a visible state to a visible state.
- **Do** pace registers by treatment — a grid, a procedural spine, a question register — not only by
  height.
- **Do** label demonstration data as illustrative wherever it appears.

### Don't:

- **Don't** let gold reach prose or a structural rule. Marking a refused act in gold both breaks
  scarcity and inverts the meaning.
- **Don't** render a refusal as a badge, toast, pill, or any floating chrome.
- **Don't** give a refusal the error palette. Withheld is weathered stone; a caveat is ochre; and
  ochre is not an error colour either.
- **Don't** set prose or a control label in the monospace face — it is scoped to machine-adjacent
  values.
- **Don't** use a decorative stone step (`--stone-600`, `--stone-500`) for a border that encodes
  state, or a dim pigment step where the full pigment is needed to clear 3:1.
- **Don't** draw a state at 1px or a divider at 4px; the two thicknesses are not interchangeable.
- **Don't** add radius to any surface. Only the sun mark and the method indices are discs.
- **Don't** raise a surface off the wall with an outer shadow, or add a glow to anything but the sun
  mark. Actions fill on hover; they do not glow.
- **Don't** import a second typeface. A Latin display face would apply to English and not to Arabic,
  making one script designed and the other a fallback on a page whose thesis is parity.
- **Don't** introduce a hieroglyph, papyrus texture, pyramid silhouette, or any pictorial Egyptian
  ornament. The composition *is* the reference; ornament would make it pastiche.
- **Don't** add a physical directional property.
- **Don't** hide content at a `from` state waiting for a scroll event, or cancel an animation with
  `animation: none` under reduced motion.
- **Don't** reach for a media query to build a layout; the single 660px breakpoint does narrow-width
  adjustment only.
- **Don't** import any token here into `/app` or `/beta`, or read this file as authority over
  `src/khepri/`. The application's design language is a separate, governed document.

---

## Recorded states

Accurate as built; these are decisions, not open defects.

- **Regular (400) is the only weight that ships.** Both `@font-face` rules declare it so the gap is
  explicit. The owner decided to leave the concept at Regular rather than acquire a face, because
  adding one requires the licence-plus-audited-digest process; `PROVENANCE.md` holds the digests and
  detail. The design compensates by carrying hierarchy on scale, colour role, tracking and register
  position instead.
- **Five `side-tab` detector findings stand deliberately** — all the identical
  `border-inline-start: 4px solid var(--withheld)` declaration. They were ruled earned on the merits:
  the committed visual world overrides the craft floor, the shape is mandated by the product's own
  §4.6, and italic carries the state independently. Left visible rather than suppressed by a
  file-level ignore.
- **The trust vocabulary is provisional.** PROVEN / CAVEATED / WITHHELD is design vocabulary gated on
  programme `T1`, which has no `governance/registry.yaml` entry. **The shape is durable; the words
  are not.**
- **Measured:** all 19 text samples pass against their own grounds (headline 15.04:1, lede 7.17:1,
  passage term 14.14:1, course term 13.56:1, proven figure 7.71:1, withheld term 6.46:1, verdict
  claim 15.04:1, button 8.55:1, script figure 8.55:1, remainder above 5.99:1). All six state borders
  clear WCAG 1.4.11's 3:1 (withheld course 5.28:1, proven verdict 8.55:1, caveated verdict 5.84:1,
  withheld verdict 5.86:1, passage withheld 5.51:1, admitted mark 5.74:1). Zero interactive targets
  under 44px at 320px. Zero physical directional properties. Desktop document 6319px at 1440 width;
  mobile 7742px at 390 width.
