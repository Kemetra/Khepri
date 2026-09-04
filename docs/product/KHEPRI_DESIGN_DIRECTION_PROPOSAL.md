# Khepri Design Direction Proposal — A Trustworthy Decision Workspace

**Baseline:** `d52f11f` (`origin/main`), 2026-09-04. Clean tree, `main`, up to date.
**Command:** `/impeccable shape` — **design direction only.** No CSS, template, route, test, package,
backend, API, governance, or database change is made or proposed as part of this document.
**Standing:** This document **grants no implementation authority.** It is a proposal to revise
`KHEPRI_DESIGN_LANGUAGE.md`. Per `governance/CONSTITUTION.md` Article II it becomes governing
direction only when the owner merges it to `main`, and even then it confers no authority to change
product code — that requires an active specification naming the files (Article IV).

**Precedence this document sits under:**

```
governance/registry.yaml  (active specifications & decisions)   ← authority
        ↓
KHEPRI_MASTER_PRODUCT_ROADMAP.md                                ← outranks the blueprint
        ↓
KHEPRI_PRODUCT_UX_BLUEPRINT.md                                  ← product UX reference
        ↓
KHEPRI_DESIGN_LANGUAGE.md   ← what this proposal revises
        ↓
this proposal
```

---

## 0. The finding that makes this proposal possible

The task asks whether visual rules are suppressing design quality, and instructs that a rule is not
preserved merely because it ships when the rule is itself under evaluation. Four verified facts
decide the question.

### 0.1 The strictest rules are self-imposed by the lowest-precedence document

| Document | Precedence | What it actually says about elevation, radius, gradient |
|---|---|---|
| `governance/registry.yaml` + active specs | **Authority** | **Nothing.** No active specification constrains elevation, radius, gradient, or motion. Verified by search across `governance/`. **Icons are the exception and are excluded by name** — `RCA-002`:140–141, `RRA-012`:221–222 (§5.6). |
| Master Product Roadmap | Outranks blueprint | **No prohibition.** Its only binding UI guardrails are roadmap:232–233 — server-rendered Jinja2 with **bundled** CSS/JS, and **no external fonts, CDNs, analytics scripts, or runtime assets.** |
| Product UX Blueprint §17 | Product UX reference | "Small radii. Borders and rules rather than **heavy** shadows." §2 avoids "**decorative** gradients", nested cards, badge soup. |
| **Design Language §1, §2.7** | **Lowest — grants no authority** | **`--shadow: none`. `border-radius: 0`. "A shadow ramp, a raised card, or a gradient would each break the law."** |

The blueprint's qualifiers are load-bearing and were dropped on the way down. "Rather than *heavy*
shadows" permits restrained elevation. "*Small* radii" **mandates radius and forbids only large
radius** — yet the design language ships `border-radius: 0` on the primary button and calls the
absence of an elevation ramp a thesis. **The design language is stricter than every document that
outranks it, and it is the only one with no authority to be strict.**

Consequence: most freedoms this proposal recommends are unlocked by an owner-merged edit to
`KHEPRI_DESIGN_LANGUAGE.md`. They do not need a governance amendment.

### 0.2 The absences were justified by contingent reasons, not by doctrine

`shell.css`'s own header states why each absence exists:

> "`--shadow: none` ships and **a shadow ramp with no user is an empty widget one layer down**; and
> **nine surfaces do not exist yet**, so component tokens now would encode guesses."

That is a YAGNI argument — *no consumer yet* — not a principle. Design language §1 law 1 then
re-states the same absence as thesis: "This is not an unfinished figure/ground — it is the thesis."
**Both cannot be true.** M3 supplies the missing consumers (Overview, Data, Analyses, Analysis
detail), which discharges the contingent reason without contradicting anything.

The two genuinely principled absences — no second typeface, no icon set — do **not** rest on taste.
Both are **excluded by name in active specifications** (`RCA-002`:140–141, `RRA-012`:221–222: "any
icon, typeface, or third-party asset"), *and* gated by the licence-plus-audited-digest process. They
are preserved here as blockers, not repealed (§5.6, §10.1 blocker 1).

### 0.3 The requested freedom set already ships on `main`, under active authority

`src/khepri/runtime/landing_assets/landing.css` (1331 lines — the largest stylesheet in the
repository) ships **today**, served at `/landing/assets/landing.css` under **active `RCA-004`**
(`LAND1-01`):

| Requested freedom | What `landing.css` actually contains |
|---|---|
| Secondary brand accents | `--gold #d4a83a`, `--ochre #c97b5a`, `--egyptian-blue #4a9fc4`, `--papyrus #ede4d3` |
| Multiple surface levels | `--stone-900/-800/-700/-600/-500` — an explicit five-step ground ramp |
| Limited gradients, brand/hero only | Three: two `radial-gradient`, one `linear-gradient` (`:438`, `:485`, `:906`) |
| Restrained glow | `box-shadow: 0 0 14px rgba(212,168,58,.55)` — **an isolated glow effect, not an elevation ramp.** No named `--shadow-*` steps exist here |
| Purposeful motion | `--ease-sun: cubic-bezier(.16,.84,.28,1)`, `--dur-slow: 1100ms`, `--dur-mid: 620ms` |
| Richer typography hierarchy | `--text-monument: clamp(2.6rem,7.2vw,6.5rem)`, `--text-register` |
| Intentional radius | `border-radius: 50%` on the sun disc |
| Egyptian geometry, abstract not literal | Tomb-wall **register** composition |
| ~~Curated SVG icon set~~ | **Not present.** Zero SVG files in `src/`; the one mark is CSS-drawn geometry, described in the file as "the one piece of iconography on the page" (§5.6) |

Its header records the owner decision and the rationale, and pre-empts the pastiche risk exactly as
this task's brief demands:

> "Egyptian register composition was a DATA-GRAPHICS system before it was art… banded facts,
> ordered, each on its baseline, sized by importance. Taking the composition rather than the ornament
> is what keeps this out of pastiche. **There is not one hieroglyph, papyrus texture, or pyramid
> silhouette in this file. The layout IS the reference.**"

**So this proposal is not inventing a direction. It extends an owner-approved, shipped, governed
precedent inward from the marketing surface to the product** — with the identity dialled down and the
ground kept light, because the app is a workspace and the landing is a wall.

**Stated precisely, because the file itself is careful about this.** `landing.css` scopes its own
claim and expressly declines to reach the app:

> "It styles the marketing surface ONLY. `KHEPRI_DESIGN_LANGUAGE.md` still governs `/app` and
> `/beta`, including its Law 1, and no token here is imported by either (`FR-091`)… **The app is
> untouched.** … nothing here proposes a change to the shipped world."

So design language §9's claims are **true as scoped to `/app` and `/beta`** — they are not false.
The defect is narrower and still real: **§9 never states its scope**, and `landing.css` appears in
the document only twice, as token-consumption counts, never as a visual world. A reader therefore
takes "no new colour, no icon set, no elevation ramp" as a product-wide doctrine when it is a
two-surface one. **The edit is to state §9's scope and cross-reference the landing world, not to call
§9 false** (§9.1).

**And the precedent is narrower than "all three".** Corrected during review: the landing ships new
colour, isolated effects (one glow, three gradients), motion tokens, and a display type scale. It
does **not** ship an icon set (§5.6) and does **not** ship an elevation *ramp* — it has a five-step
*ground* ramp and one glow, which is not the same thing as named elevation steps. The §9 edit at §9.1
must therefore be scoped to what the code contains, not to a blanket contradiction.

What the precedent does establish — and this is sufficient — is that **the owner has already approved
a richer governed visual world for this product, with a recorded rationale, under active
specification, without loss of accessibility or parity.** Whether the app should move toward it is
the open owner question at §10.3.

### 0.4 The roadmap's own north star already asks for the proposed thesis

Roadmap §1: Khepri is "a governed retail **decision platform** … while clearly refusing any result
whose business meaning, population, identity, coverage, or formula cannot be proven," and is "**not
positioned as** another generic BI dashboard."

The proposed thesis — *a trustworthy decision workspace, not a generic dashboard* — is **closer to
the roadmap's own words than the current "governed document" sentence is.** "Document" is a metaphor
the design language chose; "decision platform, not another generic BI dashboard" is what the highest
document actually says. The shift is a reconciliation, not a departure.

---

## 1. New visual thesis

> ### A trustworthy decision workspace, not a generic dashboard.
>
> Khepri is an instrument of record that an operator returns to. It states what it can support,
> names what it cannot, and keeps the proof one reachable step from the claim. It is built from
> **structure, weight, and material** — banded registers, deliberate ground levels, and type that
> ranks meaning — rather than from ornament or from chart furniture. Its confidence shows as
> **composure**: nothing floats without reason, nothing glows to seem important, and no surface
> implies a capability the system does not hold. It is equally at home in Arabic and English, on
> screen and on paper.

### What changed, and why each word is load-bearing

| From | To | Why |
|---|---|---|
| "a governed **document**" | "a trustworthy decision **workspace**" | M3 makes Khepri a place operators *return to* — with history, retention state, and provenance. A document is read once; a workspace is inhabited. `RCA-005`'s Outcome names it: "find their work." |
| "not a **dashboard**" | "not a **generic** dashboard" | The blanket rejection was over-broad. Blueprint §20.22 forbids analytics *content* on Overview; it never forbade analytical *treatment* where real capability exists. "Generic" is the actual objection, and it is the roadmap's own word. |
| "drawn with **rules rather than shadows**" | "built from **structure, weight, and material**" | Keeps the anti-ornament stance and the preference for structure, without freezing one implementation (hairlines) as the only permitted mechanism. |
| — | "**composure**" | The replacement quality bar. It licenses restraint as a *judgment* rather than as a numeric ban, and it is what rules out glow, glass, and float-by-default. |

### The five laws, restated

**Law 1 — Structure carries containment; elevation may only assist it.**
*(Replaces: "Containment comes from rules and type, never from elevation.")*
A region is defined by its band, its baseline, its measure, and its type rank. A ground step or a
restrained shadow may **reinforce** that structure where a real layering relationship exists — a
drawer over its row, a sticky header over scrolled content, a dialog over the page. **Elevation may
never be the only thing that separates two regions, and it may never encode state** (§6, §7.6).

**Law 2 — Colour is semantic, structural, or absent — and never all three at once.**
*(Extends the old law 2.)*
Semantic colour (state, accent, refusal) is unchanged and inviolable. A **secondary brand accent**
may carry identity in framing, rules, and brand moments where **no state reading is possible**. A
brand accent appearing anywhere a reader could mistake it for a state is a defect, not a flourish.
Colour still never carries a distinction alone.

**Law 3 — Refusal is a result, and looks like one.** *Unchanged. Non-negotiable.*
The disclosure shape (inline-start rule + italic) and the withheld palette, never the error palette,
never `role="alert"`, never colour alone, always where the answer would have appeared.

**Law 4 — Type ranks meaning, and may do so with more range than one face has been asked for.**
Hierarchy still comes from size, measure, weight, and colour role, on one licensed face — now with a
sanctioned display tier and editorial measure control (§7.3). Monospace stays semantic: it marks
machine-adjacent values and never sets prose.

**Law 5 — The interface renders only capability that exists.** *Unchanged. Non-negotiable.*
No destination before its slice. No fixed result count. No disabled control as permission education.
**And now explicitly: no analytical treatment — no chart, sparkline, trend, or delta — over a figure
the governed facts do not supply.** Richer treatment raises this law's stakes; it does not relax it.

---

## 2. Principles that remain non-negotiable

Every invariant named in the task is preserved. None is traded for visual freedom, and each has a
verified mechanism behind it rather than an intention.

| Invariant | Mechanism that holds it | Standing |
|---|---|---|
| No fake capability or fake data | `FR-049`; blueprint §20.21, §20.32; law 5 | LOCKED |
| No UI-side recalculation | `RRA-012` FR-093; `RCA-005` Exclusions; PRODUCT.md | Active authority |
| Refusal distinct from error | Design language §4.6; blueprint §20.9; `RRA-012` `refusal_panel`; `test_refusal_and_transport_error_no_longer_share_paint` | LOCKED + test |
| Evidence reachable from the claim | Blueprint §10, §20.6; `RRA-012` `evidence_link`, `evidence_drawer` | LOCKED |
| Governed facts authoritative | Constitution IV; `RRA-012` FR-093/FR-094 | Active authority |
| Arabic/English parity | Import-time copy parity; blueprint §20.24; strings never authored in JS | LOCKED + build gate |
| RTL/LTR quality | **Zero physical directional properties in all five stylesheets**; `lang`/`dir` server-computed; no directional glyph; mirrored keyframes | LOCKED + test |
| Accessibility | 44px on the element (`RCA-002` FR-056, browser-measured); visible focus on every tab stop; computed contrast | LOCKED + test |
| Loading / empty / unavailable / caveated / refused / error states | Blueprint §13; design language §4.6, §4.9 | LOCKED |
| Semantic state colour unambiguous | §2.2 `--line`/`--muted` rule; `RRA-012` FR-100 never-colour-alone | LOCKED + test |

**Four additional invariants this proposal treats as non-negotiable *because* it widens the palette:**

1. **Contrast is computed, never asserted.** Every new value states a hue-constant derivation and a
   measured ratio, or it is "an eyeballed value wearing a token's name." The `--ready-*` derivation
   is the standard; a first draft that drifted the hue to 146 was caught by a test.
2. **Every technique degrades to print and to high-contrast.** The refusal precedent is binding: in
   print the tint drops and the 4px rule carries the meaning alone. A technique with no fallback does
   not ship. `landing.css` already models this with a `prefers-contrast` block that flattens its
   five-step ground to two.
3. **Motion is guarded and reversible.** `prefers-reduced-motion` is respected, and the shipped
   pattern is exact: the reduced case **fills the progress track rather than freezing it**, because a
   frozen indeterminate bar at 35% reads as stalled.
4. **Elevation and brand accent never encode state.** State encoding requires WCAG 1.4.11's 3:1, and
   **a shadow has no statable contrast ratio** — which is precisely why it cannot carry meaning.

---

## 3. Existing visual rules to retain

Retained on merit, having been re-examined rather than inherited.

**Retain unchanged — these are verified properties, not preferences:**

- **Logical CSS properties only.** Zero physical directional properties across all five sheets, with
  a test on `report.css`. An RTL layout that mirrors correctly *cannot be built* from
  `left`/`right`/`margin-left`.
- **44px on the element itself, never on a wrapper.** "A padded parent around a 17px anchor still
  leaves a 17px anchor."
- **`--line` vs `--muted`.** A decorative rule may be 1.43:1; **a border that encodes state must
  clear 3:1 and therefore takes `--muted` at 6.23:1.** The single most transferable rule in the
  palette, and the one that keeps state colour unambiguous under a richer surface system.
- **One licensed face, digest-verified, no font host.** Enforced by CSP `font-src 'self'` and
  roadmap:233.
- **Monospace as semantic, not style.** Machine-adjacent values only; never prose.
- **The refusal treatment**, and its print and dark degradation.
- **`dir="auto"` for customer values; `dir="ltr"` islands only where Latin is guaranteed.**
- **Truncate in `ch`, full value in the DOM**, so the accessible name stays complete.
- **Labels above controls**, never beside — a side-by-side pair sizes the column from the longer
  language.
- **`font: inherit` on typed controls** — iOS Safari has nothing to zoom to, and controls do not
  render in the platform face beside product prose.
- **`[dir="rtl"] h1 { letter-spacing: 0 }`** — negative tracking is a Latin display convention and
  damages Arabic joins.
- **`aria-valuenow` omitted on indeterminate progress** — "a bar that reports a position it does not
  know is a lie with an ARIA attribute on it."
- **Wrap before you break.** Zero media queries in `shell-components.css`; one 640px breakpoint in
  the journey doing narrow-width adjustment only. A breakpoint encodes a guess about which item
  should go first.
- **The region scrolls, never the page**, with `tabindex="0"` and a visible focus ring on the
  scroller.
- **Columns sized for Arabic-Indic digits.**
- **Empty-state grammar:** what this area is, why it is empty, the next valid action.
- **Loading as placeholder rows at final row height** — not a spinner, not a shimmer.
- **Attention regions omitted entirely when empty**, never rendered as a zero-state card.
- **Absolute time with timezone**, never "2 days ago".
- **`.journey-document` and `.document-card` stay two names**, because they are two things. Must not
  be re-merged; the sheets never co-load, so no test could see it.
- **The report is a second namespace, deliberately** — print-first, white paper, denser ink.

**Retain, with the reasoning corrected:**

- **No sidebar.** Retained — but on the *stated* reason (four to six destinations do not earn a
  persistent 240px column), not as an aesthetic. If the count rises materially, revisit.
- **No zebra striping, row-hover fill, or sortable-column chrome** until a contract supplies sorting.
  Retained as *no chrome without capability* (law 5), not as anti-decoration.
- **No nested cards.** Retained and **strengthened**: with multiple surface levels now permitted,
  nested-card proliferation becomes the primary new risk. See §6.

---

## 4. Existing visual rules to relax or retire

Each row names the rule, where it lives, why it changes, and what replaces it. **All nine live in
`KHEPRI_DESIGN_LANGUAGE.md` — the document with no authority.**

| # | Rule today | Where | Disposition | Replacement |
|---|---|---|---|---|
| 1 | `--shadow: none`; "a shadow ramp would break the law"; elevation absence as **thesis** | DL §1 law 1, §2.7 | **Relax** | An elevation ramp of **at most three steps**, permitted only where a real layering relationship exists; never a region separator; never state-encoding (§5.1) |
| 2 | `--paper` and `--surface` **identical by design** | DL §1 law 1, §2.2 | **Relax** | Three to four intentional ground levels (§7.1). Blueprint §17 never required one ground; `landing.css` ships five |
| 3 | `border-radius: 0` on the primary button | DL §4.1 | **Retire** | Blueprint §17 says "**small radii**" — mandating radius, forbidding only large. `border-radius: 0` **contradicts the document that outranks it.** Adopt the shipped `--radius-sm: 3px` |
| 4 | "**Gradients** — nothing in the palette is a gradient stop" | DL §1 rejection table | **Relax, narrowly** | Permitted **only** on brand/hero surfaces that never render a governed figure (§5.4). Blueprint §2 forbids "**decorative** gradients"; a brand surface is not decoration |
| 5 | "No **elevation ramp**, no **secondary accent**" as *recorded deliberate absences* | DL §9; `shell.css` header | **Retire as doctrine; keep as history** | The recorded reason was "a shadow ramp **with no user**" — contingent. M3 supplies the users. Reclassify from doctrine to superseded rationale |
| 6 | "No **icon set**" | DL §9 | **NOT relaxed — corrected during review** | An earlier draft relaxed this to "a gate, not a ban" on CSP grounds. **Wrong: `RCA-002`:140–141 and `RRA-012`:221–222 each exclude "any icon, typeface, or third-party asset" by name, and `RRA-010` excludes new asset files.** CSP compatibility is not authority. Icons stay **blocked pending separate asset-admission authority** (§5.6, §10.1 blocker 1) |
| 7 | Composition assumed **symmetric, single-column**; "one document per page" | DL §3.4, §7 | **Relax** | Editorial/asymmetric register composition (§5.9, §8.1). Never at the cost of the 320px no-overflow invariant |
| 8 | "**KPI card walls**" rejected outright | DL §1 rejection table | **Relax, precisely** | Blueprint §20.22 forbids **analytics content on Overview** — revenue, sales, branch, category, basket, concentration. It does **not** forbid analytical *treatment* elsewhere where real capability exists (§5.8). Card *walls* and *fixed counts* stay forbidden |
| 9 | Motion limited to the single guarded progress animation | DL §4.8 | **Relax** | Purposeful micro-interaction with a stated UX job (§5.7), under the shipped reduced-motion discipline |

**Not relaxed, and why:**

- **A second typeface** stays absent. The gate is real (licence + audited digest) *and* `--font-body`
  already covers both scripts from one digest-verified face. A second face doubles the parity surface
  for no established need.
- **A dark app palette** stays absent. It is a genuine unmade product decision (§10 blocker 2), and
  DL §8.1's open question — a dark report inside a light app — must be resolved **before**, not by,
  any dark work.
- **Blueprint §20 LOCKED items** are untouched by this proposal.

---

## 5. Newly permitted visual techniques

**Read this section as a matrix, not a permission list.** Khepri has four surfaces under three
exclusion regimes, and a technique available on one is frequently blocked on another. The authority
column is what an implementer must cite.

| Surface | Files | Governing authority | Regime |
|---|---|---|---|
| Landing | `runtime/landing_assets/landing.css` | **active `RCA-004`** (`FR-083`, `FR-091`) | Widest. Already ships the full technique set |
| Shell (`/app`) | `shell.css`, `shell-components.css` | **active `RCA-002`**, **active `RCA-005`** | Workspace surfaces + four-item nav are **in `RCA-005`'s Scope** |
| Journey (`/beta`) | `journey.css` | **active `RRA-010`** | **Narrowest.** No new asset filename or allowlist change; may not name a shell-owned property, class, or file "**even when the resulting pixels would match**" |
| Report | `report.css`, `report.print.css` | **active `RRA-012`**, `RRA-009` | Print-first, own namespace. No report redesign (blueprint §16) |

### 5.1 Restrained elevation — three steps, assistive only

| Token | Purpose | Permitted where |
|---|---|---|
| `--shadow-none` | Default. Flat remains the default state, not the exception | Everywhere |
| `--shadow-raised` | A surface genuinely above its sibling | Evidence drawer over its row; menu over content |
| `--shadow-overlay` | A layer over the page | Dialog; sticky header over scrolled content |

Rules: elevation **assists** a structural boundary and never replaces one; it **never encodes
state**; it never appears on a static content region; and every elevated surface must still read
correctly with shadows suppressed (print, forced-colors).

### 5.2 Multiple surface levels — three to four, named by role

Ground levels are `--surface-sunken` / `--surface` / `--surface-raised` / `--surface-overlay`, named
by **role** so a future dark palette can be added without renaming — the discipline `shell.css`
already established. Each adjacent pair must be visually distinguishable **and** every token sitting
on a new ground must be **re-measured** (§7.6).

### 5.3 Intentional border radius

Three radius tokens are **declared** in `shell.css` — `--radius-sm: 3px`, `--radius-md: 6px`,
`--radius-pill: 999px`. **Measured consumption at `d52f11f`: `--radius-sm` 1 consumer,
`--radius-md` 0, `--radius-pill` 0.** By the design language's own rule — "a token with no consumer
is a design decision that did not ship" — only `--radius-sm` is shipped in any meaningful sense. This
proposal therefore adopts them as **declared** tokens to consume, not as established practice:

- **`--radius-sm` (3px)** — controls, inputs, buttons. This is the value that retires
  `border-radius: 0` and satisfies blueprint §17's "small radii".
- **`--radius-md` (6px)** — panels and drawers. Still within §17's "small".
- **`--radius-pill` (999px)** — **not adopted by this proposal.** It cannot be justified under the
  same §17 clause used to retire `border-radius: 0`: "small radii" is the authority for adding
  radius, and a maximal radius is the opposite reading of that clause. Using §17 in one direction and
  against itself in the other would be exactly the selective reading this proposal criticizes in
  §0.1. A state chip keeps its shipped treatment — hairline border, `--muted` ink, no fill (DL §4.5)
  — with `--radius-sm` if any. **Admitting `--radius-pill` is a separate owner decision.**

### 5.4 Limited gradients — brand and hero only

Permitted **only** on a surface rendering **no governed figure, state, or refusal**: the landing
(already shipping), a hero band, a report cover. Every gradient must have a **flat fallback that is
the actual paint in print and forced-colors.**

**Forbidden absolutely:** gradient behind any figure, table, state chip, refusal panel, or evidence
chrome; gradient *text*; the purple/blue SaaS default; and any gradient in `report.css`'s screen
namespace whose print counterpart differs — the report is read on paper.

### 5.5 Secondary brand accents

Anchor to the **shipped, owner-approved** landing palette rather than inventing values — `--gold`,
`--ochre`, `--egyptian-blue` — with `--track: #e3ded1` as the app's one existing warm value and a
plausible bridge.

**The derivation obligation is absolute.** Each accent admitted to an app surface must state its
hue-constant derivation and its **measured** ratio against every ground it touches, in the
`--ready-*` format. **Brand accent is permitted only where no state reading is possible** — framing,
section rules, wordmark lockup, hero. **Never** on a state chip, badge, refusal panel, figure, or
evidence chrome, where it would compete with semantic colour.

### 5.6 Locally bundled curated SVG icons — BLOCKED on every current surface

**Corrected during review of this proposal. An earlier draft called icons "technically admissible,
procedurally gated" on the strength of the CSP. That was wrong, and the error is instructive: CSP
compatibility is not authority.** Every active specification covering a surface that could host an
icon excludes one by name:

| Surface | Exclusion | Text |
|---|---|---|
| Shell (`/app`) | **`RCA-002`:140–141** | "**Any icon, typeface, or third-party asset.** Asset admission is governed separately and is not granted here." |
| Report / evidence | **`RRA-012`:221–222** | "**Any icon, typeface, or third-party asset.** Asset admission is governed separately, exactly as `RCA-002`:134 records, and is not granted here." |
| Journey (`/beta`) | **`RRA-010`:88** | A new asset filename or allowlist change is excluded |

`img-src 'self'` and `style-src 'self'` do mean a bundled SVG set would be **CSP-compatible**, and
inline SVG in a Jinja partial needs no asset route. **Neither fact overrides an exclusion.** Asset
admission is governed separately on all three surfaces, so an icon set is **blocked pending separate
asset-admission authority** — which is a governance artifact the owner merges, not a licence file an
implementer supplies. The licence-plus-audited-digest process is a *further* requirement after that
authority exists, not a substitute for it.

**Recorded so it is not rediscovered:** there are **zero SVG files in `src/`** at `d52f11f`.
`landing.css` draws its one mark — a gold sun disc in the wordmark — in pure CSS geometry, and its
own comment calls it "the one piece of iconography on the page." **The landing is not a precedent for
an icon set**, and this proposal does not claim it is.

**When authority exists, these design requirements apply:** icon **never alone** — always paired with
text, since `RRA-012` FR-100 forbids colour alone and an icon is a weaker signal than colour; **no
directional glyph** (an arrow does not mirror); `aria-hidden` when decorative; mirrored or
direction-neutral in RTL.

### 5.7 Purposeful micro-interactions and motion

Every motion needs a stated UX job. **Permitted:** state transition (drawer open/close, disclosure
expand); arrival of content into a known-height placeholder; focus and hover affordance confirmation;
progress.

**Forbidden:** entrance animation on page load; parallax; scroll-jacking; attention-seeking loops;
animated counting numbers (a counting figure *looks like* UI-side recalculation); and any motion on a
refusal or error — a governed refusal is stable, not an event.

Reuse the shipped landing tokens (`--ease-sun`, `--dur-mid`, `--dur-slow`) as the reference easing
rather than inventing a second motion language. `prefers-reduced-motion` reduces to **a completed end
state, never a frozen middle one.**

### 5.8 Stronger analytical/KPI treatment — only where real capability exists

**Permitted:** a figure at display weight with its label and its evidence link; a governed comparison
where `G4/C1` authority exists; a coverage or quality summary rendered as **counts derived from the
current governed result set**.

**Forbidden, each with a named authority:** any analytics content on Overview (**blueprint §20.22**,
LOCKED); a **fixed** section or metric count (**§20.8**, LOCKED); any chart, sparkline, trend, or
delta the governed facts do not supply (law 5); a card *wall* implying a fixed count; any client-side
computation (`RRA-012` FR-093, `RCA-005` Exclusions).

**Blueprint §20.23 bounds this section (LOCKED): "Audit and version identifiers sit behind
disclosure, never leading a primary customer row."** Richer figure treatment does not promote them.
A figure may take display weight; its governed formula version, package version, citation identifier,
and audit fields stay **behind the disclosure** — the `evidence_drawer`, not the row. Design language
§4.7 states the same rule: "low-level formula and version strings must not dominate primary customer
pages."

**The KPI treatment must render through `RRA-012`'s component layer** — `figure`, `status_badge`,
`quality_summary` — or it is outside that specification.

### 5.9 Richer typography hierarchy and editorial composition

Add a **display tier above `--text-2xl`** for hero and report-cover use, plus per-context measure
control (`--measure-heading: 24ch` and `--measure-prose: 62ch` already exist). `--text-monument` and
`--text-register` are the shipped landing precedents.

Asymmetric composition comes from **measure and weight**, not from a fixed multi-column grid, so it
collapses to stacked blocks with no page-level overflow. **Character units, never `px`**, so the cap
follows Arabic text rather than the viewport.

### 5.10 Visual storytelling and Egyptian-inspired geometry

**Take the composition, not the ornament.** The landing sheet already proves the method and states
the standard: Egyptian register composition was a data-graphics system — banded content on strict
shared baselines, read in fixed order, figures scaled by significance. **That is structurally what a
governed report is.**

Permitted carriers — named, so the identity budget is verifiable:

| Carrier | Treatment |
|---|---|
| Wordmark lockup | Letterspaced KHEPRI, real text. Already shipped |
| Landing / hero | Full register world. Already shipped under `RCA-004` |
| Section framing and rules | Banded registers on shared baselines; incised rule weights |
| Empty-state composition | Structural geometry only — never a decorative illustration (DL §4.9) |
| Report cover | Restrained framing; must survive print |

**Forbidden absolutely:** hieroglyphs, papyrus texture, pyramid or sphinx silhouettes, scarab
imagery, sandstone photo texture, gold-on-black "luxury" pastiche, and **any Egyptian motif on a
state chip, refusal panel, badge, figure, or evidence chrome.** The identity lives in composition,
framing, and material — never in iconography over governed content.

---

## 6. Anti-patterns and limits

**Named in the brief — all forbidden:** generic SaaS styling · purple/blue gradient defaults ·
excessive glassmorphism · nested-card proliferation · excessive glow · decorative motion with no UX
purpose · Egyptian theme-park styling · papyrus/hieroglyphics/pyramids as routine decoration · any
effect that weakens evidence, refusal, or state clarity.

**New risks this widening creates, each with a stated limit:**

| Risk | Limit |
|---|---|
| Elevation creep — everything becomes a floating card | **Three shadow steps, hard cap.** Flat is the default. Elevation requires a real layering relationship |
| **Nested cards** — the top risk once ground levels exist | **Two ground levels of nesting maximum.** A card inside a card inside a card is forbidden. "With one surface colour, a card inside a card is two hairlines and no information" — with four grounds it is worse, not better |
| Brand accent drifting into state meaning | Brand accent **only** where no state reading is possible. If a reader could mistake it for a state, it is a defect |
| Radius drift | **Two** adopted radius tokens (`--radius-sm`, `--radius-md`). No raw radius literals. `--radius-pill` is not adopted (§5.3) |
| Gradient spreading from hero to content | Gradient only on surfaces rendering **no** governed figure, state, or refusal |
| **Contrast regression from new grounds** | Every token on a new ground is **re-measured**. The canary is step-nav `#667381` at 12px, which **passes AA by 0.22** — no margin (§7.6) |
| Motion on governed content | No motion on a refusal, an error, or a figure |
| Icon substituting for a word | Icon never alone (`RRA-012` FR-100) |
| Identity budget creeping past 25% | Verified against the **carrier list** (§5.10), not against a percentage |
| Print / high-contrast divergence | Every technique states its flat fallback. The refusal precedent is binding |
| **Spec-widening dressed as design** | Every technique routes to a surface + active specification (§5). "A template that begins reading a value the view model did not previously supply is a domain change" |

**The identity budget, expressed verifiably.** The 75–80% / 20–25% target is not measurable as a
percentage, so it is expressed as: identity appears **only** on the §5.10 carriers, and **never** on
state chips, refusal panels, badges, figures, evidence chrome, or the disclosure shape. On any surface
rendering governed content, identity is confined to framing and rules — which is how the proportion
lands where the brief asks without anyone measuring pixels.

---

## 7. Proposed token-system evolution

**Additive and role-named.** No existing token changes value, so no shipped rule changes meaning.
Colour tokens stay named by **role** rather than by value — `shell.css`'s stated discipline — so a
dark palette remains addable later without renaming anything.

### 7.1 Surface ramp (new)

```
--surface-sunken     recessed wells, table header bands, inset regions
--surface            component ground              [= today's value, unchanged]
--surface-raised     genuinely raised              [ships today: #fafbfd, the drop zone]
--surface-overlay    dialog / menu ground
```

### 7.2 Elevation ramp (new — three steps, hard cap)

```
--shadow-none        [= today's --shadow: none, retained as an alias]
--shadow-raised      drawer over row; menu over content
--shadow-overlay     dialog; sticky header over scrolled content
```

`--shadow` is **retained as an alias to `--shadow-none`** so no existing rule changes meaning — the
same technique `--radius: var(--radius-sm)` already uses.

### 7.3 Type (extend)

```
--text-hero          display tier above --text-2xl, clamp()   [landing: --text-monument]
--measure-narrow     editorial column measure, in ch
```

### 7.4 Brand accents (new, gated on derivation)

```
--brand-gold         from landing --gold          #d4a83a
--brand-ochre        from landing --ochre         #c97b5a
--brand-blue-light   from landing --egyptian-blue #4a9fc4
```

**Each requires, before use on any app surface:** hue-constant derivation stated, measured ratio
against every ground it touches, and a declared **non-state** role. Unmeasured, they are "eyeballed
values wearing a token's name."

### 7.5 Motion (new)

```
--ease-standard      [landing: --ease-sun cubic-bezier(.16,.84,.28,1)]
--dur-fast / --dur-mid / --dur-slow   [landing: 620ms / 1100ms]
```

### 7.6 Two mandatory obligations on any token slice

1. **Re-measure every affected ratio.** Multiple grounds mean each foreground token sits on a new
   ground. Figures to preserve or beat: `--ink` on `--paper` **15.37:1**; `--muted` **6.23:1**;
   `--accent` **6.83:1**; and **step-nav `#667381` at 12px, which passes AA by 0.22.** That 0.22 is
   the canary: any ground change touching it must be re-measured before merge.
2. **A token with no consumer is a design decision that did not ship.** Add each token in the slice
   that consumes it, not ahead of it — otherwise this proposal recreates the exact seam DL §2.8
   documents (`var(--text-*)` at zero consumers for a whole milestone).

### 7.7 The seam this proposal must not widen

`journey.css` and `shell.css` **never co-load** — two templates, two allowlists. A bare
`var(--surface-raised)` in `journey.css` resolves to nothing, and **an invalid `background` or
`font-size` is dropped, not ignored**: the element silently falls back to its inherited value. **A
find-and-replace here is a silent visual regression, not a no-op.**

`RRA-010` authorizes a journey rule to consume a token **declared in the journey's own stylesheet**
and forbids resolving one whose sole declaration is shell-owned. So journey-side adoption must
**mirror** each token into `journey.css`'s own `:root` at identical values — the shape already taken
by `--journey-text-*`. **A shared token sheet is excluded by `RRA-010`:88** (new asset filename +
allowlist change) and remains an owner question, not a slice.

---

## 8. Composition guidance

### 8.1 M3 — Durable Workspace

**Authority: active `RCA-005` + `RCA-002`.** `RCA-005`'s Scope names `runtime/shell_api.py` and
`shell_templates/` for "the Overview, Data and Analyses surfaces and the four-item navigation."
**M3 surfaces now have registered authority** — a material change from the design language's
"CONTRACT-BLOCKED on unregistered `G2`/`G3`" reading, which `d52f11f` superseded via
`KHEPRI-DEC-033` and `RCA-005`.

**Thesis: the register spine.** Overview is *operational orientation* (blueprint §7.1, §20.22) — what
happened, what is processing, what data exists, what needs attention. Not analytics.

- **Banded registers, not a card grid.** Each region is a band on a shared baseline with a monospace
  `--text-xs` uppercase label — the shipped Overview grammar, with the band now an explicit
  compositional unit rather than an implicit gap.
- **Asymmetric spine.** A wide primary column (latest work, attention) beside a narrower secondary
  register (data, retention). Asymmetry from **measure and weight**, not a fixed two-column grid, so
  it collapses to stacked blocks below 640px with no page-level overflow.
- **`--surface-sunken` for the table header band**; `--surface` for content. This is where multiple
  grounds earn their place: a scrolling region reads as a region without another hairline.
- **`--shadow-raised` on the evidence drawer only** — a real layering relationship over its own row.
- **Elevation is never the region separator.** Bands and baselines are.
- **Operational state and trust state stay two lines** (`Completed` / `Quality: …`), never a compound
  badge. State chips keep their shipped treatment — hairline + `--muted` ink, no fill, no pill
  (§5.3).
- **Attention region omitted entirely when empty.** No zero-state card.
- **No region assumes a count.** Any band absorbs 0 or 50 rows.
- **Identity carriers here:** band framing and rule weights only. Nothing else.

### 8.2 M4 — Sellable Decision Workspace

**Direction only. No page-level UX is specified, and none is proposed here.** Blueprint **§21**
records "**M4 page structure — FUTURE SHAPING REQUIRED**" depending on `SV1`, `C1`, and M3 learnings;
PRODUCT.md confirms "direction only, with no page-level UX specified." Compare is `G4/C1`'s and is
**explicitly excluded from `RCA-005`**.

**M4's content is already enumerated by blueprint §22 and is not this proposal's to invent.** §22
names it: "Executive overview, period comparison, branches, products and categories, basket,
concentration, limitations and refusals, contextual evidence, governed exploration," depending on
`SV1`/`C1`. Two adjacent §22 tracks constrain the same surface — **Guided Exploration**
(`X1-01`…`X1-05`, questions "selected from supported governed question contracts — never LLM-inferred
speculative questions") and **Ask Khepri** (`G9/AI1`, which "does not calculate novel KPIs, does not
retrieve raw rows, and performs no writes").

This section therefore supplies **visual direction for that named content only** — it adds no M4
capability, page, or thesis beside §22's.

**Visual thesis: the decision record.** Where M3 answers *what happened*, M4 answers *what should we
do, and can we defend it later*. The visual consequence: a **decision** carries the same provenance
discipline a figure has — what it rested on, which governed versions, what was refused at the time,
and what has changed since. Note that §22's list is the first place in the product where
**analytical content is genuinely in scope** (branches, categories, basket, concentration) — which is
why §5.8's "only where real capability exists" clause matters more here than anywhere else, and why
§20.22's Overview prohibition must not be read as reaching M4.

- **The strongest identity moment belongs here** — the sellable artifact (report cover, decision
  record). Full type hierarchy, framing geometry, and a gradient permitted **on the cover only**,
  never behind a figure.
- **Comparison is the one place analytical treatment is genuinely earned** — and it needs `G4/C1`
  authority that does not exist. Until then: **no comparison UI, no delta, no trend.**
- **A methodology change is a first-class visual event** (blueprint: Methodology Change Notice,
  LOCKED, CONTRACT-BLOCKED) — the disclosure shape, not a badge.
- **Refusal becomes more prominent, not less**, as claims get more persuasive treatment. This is the
  central M4 risk: a premium deliverable that made refusals feel like blemishes would invert the
  product's thesis.
- **No dashboard.** M4 is a *workspace* — where decisions are made and defended, not a wall of
  charts.

**What M4 must not do on this proposal's authority:** specify pages, mint trust vocabulary beyond
`RRA-012`'s chrome, imply comparison capability, or assume a dark palette.

---

## 9. Exact documentation sections that would need editing

**No edits are made by this document.** This is the change list an owner-approved revision would
execute.

### 9.1 `docs/product/KHEPRI_DESIGN_LANGUAGE.md` — primary target

| Section | Edit |
|---|---|
| Header block | Add a reconciliation line: baseline `d52f11f`; `RCA-005` and `KHEPRI-DEC-033` are active |
| **§0 authority table** | **Add the fifth stylesheet.** `landing.css` (1331 lines, active `RCA-004`) is absent from a table that claims to list the visual authority files |
| §0 verification table | Re-measure every row at `d52f11f`; the last re-measure was `f15c835` |
| **§1 "The sentence"** | **Replace** with the new thesis (§1 above) |
| **§1 "The five laws"** | **Rewrite laws 1, 2, and 4.** Laws 3 and 5 unchanged |
| **§1 rejection table** | Rewrite the **Gradients** and **KPI card walls** rows; **keep the icon-set row and strengthen it** with its two governance citations (§5.6); keep and strengthen **Nested cards**; keep **Generic SaaS dashboard**, **Giant sidebar**, **Badge soup**, **Fake capability**, **Coming Soon nav** |
| §2.1 | Note the token layer now spans **two** visual worlds under two authorities |
| §2.2 | Add the surface ramp; **retain the `--line`/`--muted` rule verbatim** |
| §2.3 | Add brand accents **with derivations and measured ratios** |
| §2.5 | Add `--text-hero`, `--measure-narrow` |
| §2.7 | **Replace `--shadow: none`** with the three-step ramp plus alias; state radius adoption |
| **§2.7 (new subsection)** | **Motion tokens** — they currently have no home in the token system |
| §2.8 / §2.8.1 | Restate the co-load hazard for **every** new token class, not only type |
| §3.4 | Permit editorial/asymmetric composition; keep `.journey-document` / `.document-card` distinct |
| §4.1 | **Retire `border-radius: 0`**; adopt `--radius-sm`; resolve the primary button per §8.4 |
| §4.5 | Note that the state chip keeps its shipped treatment; `--radius-pill` is **not** adopted (§5.3) |
| §4.6 | Unchanged. Restate as inviolable under a richer palette |
| §4.9 | Permit **structural** empty-state geometry; keep the no-decorative-illustration rule |
| §4.11 | Note that richer figure treatment must render **through** the `RRA-012` component layer |
| §5.2 | Permit asymmetric composition **within** the no-overflow invariant |
| §6 | Unchanged. Add: icons mirrored or direction-neutral; no directional glyph |
| §7 | Recompose the Overview example on the register spine (§8.1) |
| §8.1 | **Re-open**: the dark report/app split must resolve **before** any dark work |
| §8.4 | Resolve to `--radius-sm` + 44px with the journey's transparent treatment |
| **§8 (new)** | **Record: is `landing.css` a sibling world or the direction of travel?** The most consequential open question, and an owner decision (§10.3) |
| **§9** | **State its scope and cross-reference the landing world**, narrowed to what the code contains. Its claims are **true as scoped to `/app` and `/beta`** and must say so. Against `landing.css` specifically: **new colour and a dark palette are contradicted** at product scope; **"no icon set" is not** (zero SVG files; one CSS-drawn mark); and **"no elevation ramp" is not** (a five-step *ground* ramp plus one glow is not an elevation ramp). **"No icon set" stays true for `/app` and `/beta` as governance, not just as taste** — `RCA-002`:140–141 and `RRA-012`:221–222 exclude it (§5.6) |

### 9.2 `docs/product/KHEPRI_PRODUCT_UX_BLUEPRINT.md` — two edits only

| Section | Edit |
|---|---|
| **§17 Visual direction** | Extend to name the two registers (the app world, and the landing world under `RCA-004`), and state that "small radii / not *heavy* shadows" permits restrained elevation and intentional radius. **§20.31's LOCKED status is unaffected** — the shipped light token set remains the app's visual authority |
| §18 authority matrix | Update the Overview / Data / Analyses / Analysis-detail rows: authority is now **active `RCA-005`** + `KHEPRI-DEC-033`, not unregistered `G2`/`G3` |

**§20 Locked decisions register: no edits.** Nothing in this proposal touches a LOCKED item. §20.31
is preserved — this proposal *extends* that token set additively and proposes no dark app palette.

### 9.3 `PRODUCT.md` — one correction

The "Registered authority is narrower than the roadmap's program list" paragraph is **stale at
`d52f11f`**. `G2`/`G3` still have zero registry rows, but their substance is now active as
**`KHEPRI-DEC-033`** and **`RCA-005`**, and M3 surfaces are consequently in scope. Also add
`landing.css` to *Evidence on Hand* — it is the largest stylesheet and is currently unlisted.

### 9.4 Not edited, and the citation check that confirms it

`governance/CONSTITUTION.md`, `governance/registry.yaml`, every specification and decision,
`AGENTS.md`, and all product code, templates, CSS, and tests.

**A blueprint section number can be a governed fixed point, so this was checked rather than
assumed.** The roadmap documents the trap: active `KHEPRI-DEC-023` and `KHEPRI-DEC-025` cite
*roadmap* section numbers, and those were "found by searching every `active` artifact for a section
citation." Running the equivalent search against **blueprint** section numbers across `governance/`
returns four citing artifacts:

| Active artifact | Cites blueprint |
|---|---|
| `RCA-005` FR-117 | §7.3 (Analyses as the single history spine) |
| `RCA-005` FR-118 | §7.4 (artifacts reached from Analysis detail) |
| `RCA-005`:118, :191 | §19 (slice ordering) |
| `RCA-005`:50 | §8 ("Workspace" stays internal) |
| `KHEPRI-DEC-033`:84, :122 | §7.3 |

**No active artifact cites blueprint §17 or §18** — the only two blueprint sections this proposal
edits. Both edits are therefore safe, and **this proposal requires no governance change** (§10).
A future revision that renumbers §7.3, §7.4, §8, or §19 would be a governed change and must amend
the citing artifacts first.

---

## 10. Governance conflicts that prevent a proposed visual freedom

Assessed against `governance/registry.yaml` at `d52f11f`, not against prose.

### 10.1 Blockers — freedoms that cannot proceed on a doc edit

| # | Freedom | Blocker | Nature | Resolution |
|---|---|---|---|---|
| **1** | **Any icon set, on every current surface** | **`RCA-002`:140–141** and **`RRA-012`:221–222** each exclude "**Any icon, typeface, or third-party asset.** Asset admission is governed separately and is not granted here." **`RRA-010`:88** excludes new asset filenames and allowlist changes | **HARD BLOCK, active authority on all three surfaces** | A **separate asset-admission artifact** the owner merges. CSP compatibility (`img-src 'self'`) is **not** authority, and the licence-plus-digest process is a further requirement after that authority exists, not a substitute (§5.6) |
| **1b** | **A shared token sheet, or any new asset file, in `/beta`** | **`RRA-010` Exclusions:88** — "a new route, address, or **asset filename**; a change to the asset allowlist"; and no dependency on a property, class, or file "whose authority sits with the shell, **even when the resulting pixels would match**" | **HARD BLOCK, active authority** | Mirror tokens into `journey.css`'s own `:root` (§7.7); or a new `RRA` specification naming journey assets. **Cross-surface visual consistency is explicitly not `RRA-010`'s to deliver** |
| **2** | **Dark app palette** | Blueprint **§20.31 LOCKED** (the shipped light token set is the visual authority) + `shell.css` `color-scheme: light` + DL §8.1's unresolved dark-report-in-light-app split | **OWNER DECISION** | Not proposed here. §8.1 must resolve first. This proposal keeps the app light |
| **3** | **Second typeface** | Licence-plus-audited-digest process + roadmap:233 (no external fonts) + CSP `font-src 'self'` | **PROCESS GATE** | Not proposed. One face already covers both scripts from one verified digest |
| **4** | **Analytical treatment on Overview** | Blueprint **§20.22 LOCKED** — no revenue, sales, branch, category, basket, or concentration content | **LOCKED** | Not proposed. §5.8 confines analytical treatment to surfaces with real capability |
| **5** | **Comparison / delta / trend UI** | `G4/C1` has **zero registry entries**; **explicitly excluded by `RCA-005`** | **NO AUTHORITY** | M4 direction only. No comparison UI |
| **6** | **Any external asset, CDN, or web font** | roadmap:233 + runtime CSP `default-src 'none'` | **HARD BLOCK, runtime-enforced** | Bundle locally. Non-negotiable and not contested |
| **7** | **Deletion UI, tombstone rendering, and workspace role cells** | Blueprint **§21**: deletion authority AUTHORITY-BLOCKED; tombstone fields CONTRACT-BLOCKED; "workspace role cells (list, read, reopen artifacts)" AUTHORITY-BLOCKED on `G3-03` | **AUTHORITY-BLOCKED** | Not designed here. §8.1 covers only the read surfaces `RCA-005` FR-117/FR-120/FR-121 authorize |
| **8** | **M4 page structure** | Blueprint **§21**: "M4 page structure — FUTURE SHAPING REQUIRED", depending on `SV1`, `C1`, and M3 learnings | **FUTURE SHAPING** | §8.2 supplies visual direction for blueprint §22's already-named content only, and specifies no page |

### 10.2 Not blockers — three findings that materially widen what is available

1. **No active specification constrains elevation, radius, gradient, or motion** (icons excepted — §5.6).
   Verified by search across `governance/`. The strictest visual rules are **self-imposed by
   `KHEPRI_DESIGN_LANGUAGE.md`, the lowest-precedence document, which grants no authority.** Most of
   §5 is therefore unlocked by an owner-merged doc edit — **no governance amendment required.**
2. **M3 surfaces are no longer authority-blocked.** `d52f11f` merged **`KHEPRI-DEC-033` (active)** and
   **`RCA-005` (active)**. Verified in `RCA-005`'s **Requirements**, not inferred from the commit
   message: **FR-117** (Analyses is the single history spine, newest first), **FR-118** (artifacts
   reached only from Analysis detail; no reports index), **FR-120** (Overview shows latest work, data
   state, and items needing attention), **FR-121** (navigation is Overview, Data, Analyses, Team, each
   link shipping only with its surface), **FR-122** (both languages, RTL parity, 44px). Its Scope
   names `runtime/shell_api.py` and `shell_templates/`.
   `G2`/`G3`/`W1` remain absent from the registry — **the program labels never registered; their
   substance did.** `PRODUCT.md` and blueprint §18 are both stale on this point.
   **Two M3 items stay blocked and are not unblocked by this finding:** deletion authority and
   tombstone fields remain AUTHORITY-BLOCKED per blueprint §21, and "workspace role cells (list, read,
   reopen artifacts)" is recorded there as AUTHORITY-BLOCKED on `G3-03`. §8.1's guidance is
   composition for the read surfaces FR-117/FR-120/FR-121 authorize, nothing more.
3. **The whole technique set already ships under active `RCA-004`.** `landing.css` is owner-approved,
   governed, accessible (`prefers-reduced-motion`, `prefers-contrast`), and bilingual. `FR-091` says
   the landing **MAY** remain distinct and that no app asset **need** change — **permissive, not
   prohibitive.** It does not forbid the app from evolving toward it. This precedent is the strongest
   argument in the proposal.

### 10.3 The one owner question this proposal cannot answer

**Is `landing.css` a permanently separate marketing world, or the direction of travel for the
product?**

Both readings are defensible on the record. `RCA-004` `FR-091` permits permanent separation, and the
landing header says "Two registers, one thesis… the app keeps `KHEPRI_DESIGN_LANGUAGE.md` Law 1
unchanged." But the same header records *why* the previous concept was replaced:

> "That palette was designed for a workspace — one accent, hairline rules, no elevation — and on a
> public page **it read as a plain document rather than as an enterprise product.**"

That is the same critique this task makes of the app. **Two clauses point opposite ways, which makes
it an owner question rather than a designer's pick.** The answer sets the ceiling on §5:

- **Sibling worlds** → §5 proceeds; identity stays at the low end of 20%; app and landing diverge
  permanently by design.
- **Direction of travel** → §5 proceeds toward the landing's register language; identity lands at the
  upper end of 25%; and DL §8.1's dark question must be scheduled rather than deferred.

**Everything else in this proposal is executable under either answer.** Only the identity ceiling and
the dark-palette schedule depend on it.

---

## 11. Recommended next implementation-ready design step

**One step, and it is a documentation slice, not a code slice.**

> **Revise `KHEPRI_DESIGN_LANGUAGE.md` per §9.1, in one PR, with no CSS, template, or token change.**

Why this and nothing else first:

- It is the **only** change that unblocks everything else, because every visual freedom in §5 is
  currently blocked by that document alone (§10.2 finding 1).
- It is **verifiable in isolation**: no CSS diff, so no contrast, RTL, 44px, or parity risk, and
  `khepri-gov validate` is unaffected.
- It **fixes an unscoped statement on `main`** — §9 reads as product-wide doctrine while a shipped
  `landing.css` under active `RCA-004` contradicts its colour and dark-palette claims at that scope
  (§0.3). The icon and elevation-ramp claims stay, with their real basis stated (§5.6).
- It requires **no governance amendment** and touches **no LOCKED blueprint item**.

**The first code slice after it** — and only after it merges — is the shell primary button (DL §8.4):
adopt `--radius-sm: 3px` at the tokenized 44px with the journey's transparent treatment, in
`shell-components.css` under active `RCA-002`/`RCA-005`. It is one rule, it retires the
`border-radius: 0` contradiction with blueprint §17, it consumes an already-shipping token, and it
proves the doctrine change end-to-end at the smallest possible blast radius.

**Do not start with:** the journey (`RRA-010` is the narrowest regime), the report (blueprint §16 — no
redesign), a dark palette (§10.1 blocker 2), or a token slice with no consumer (§7.6 obligation 2).
