# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Retail operators in an organization — not analysts. They arrive having sent Khepri a sales file and
wanting to know what it said. They think in **submissions and answers**, not in dashboards, models,
or metrics:

> "I sent you last quarter's sales file. You told me what it said. Where is that, and is it still
> there?"

Roles are owner and member; owner-only capabilities exist (invitation issue and revoke today,
deletion later). Arabic-reading and English-reading operators are equal populations, not a primary
language plus a translation.

The customer-visible scope is the **Organization**. "Workspace" is an internal domain and contract
term and is not a customer noun.

## Product Purpose

Khepri answers questions about a retailer's own submitted data, and refuses — visibly and by name —
the questions its governed facts cannot support. Success is an operator who knows which of their
answers were supported, which were not, where the evidence for each one is, and whether the content
is still retained.

## Positioning

**Semantic admission happens before any claim is made, and unsupported conclusions are refused
rather than approximated.** A neighboring BI product presents whatever the query returns; Khepri
declines to answer where its facts do not support an answer, keeps that refusal visible in the place
the answer would have appeared, and makes the reason and evidence reachable from the claim.

Facts are deterministic and versioned. Templates, controllers, dashboards, APIs, semantic views, and
AI may select and present facts; **they may not recalculate them**.

## Operating Context

Two product modes exist by design and are not a defect to be merged:

- **Commercial shell** (`/app`) — organization and commercial context: organization chooser, team,
  invitations, and the entry point that starts an analysis.
- **Focused journey** (`/beta`) — task mode for completing one analysis: upload → review →
  processing → report, with evidence and artifacts reached from the report.

The crossing between them is a 303 redirect that sets its cookie only on success and deliberately
omits it on the refusal path.

Deliverables the same governed facts feed: the web UI (interactive), the final report (premium
executive deliverable, read on screen and on paper), the evidence layer (proof), and an Excel
artifact (structured downstream).

Milestones: **M2** is the current design-partner analysis experience. **M3** adds durable history —
what data was submitted, what analyses exist, which report belongs to which analysis, and whether
content is still retained. **M3 is not an executive dashboard.** **M4** is a decision workspace and
is direction only, with no page-level UX specified.

## Capabilities and Constraints

Binding technical and governance constraints:

- Server-rendered FastAPI/Jinja2 with bundled CSS and minimal bundled JavaScript, until an active
  architecture decision changes it.
- **No external fonts, CDNs, analytics scripts, or runtime assets.** Enforced at runtime by a
  `default-src 'none'` CSP.
- The typeface is Noto Sans Arabic, shipped as package data and verified against a SHA-256 manifest.
  A new face or icon set must first pass a licence-plus-audited-digest process.
- Product code is admitted only in small, independently verifiable slices linked to an **active**
  specification. A slice does not widen its specification, privacy boundary, runtime boundary, or
  data use.
- Ambiguity in identity, scope, semantics, population, privacy, retention, or runtime **fails
  closed**.
- Arabic and English state, action, fact, caveat, refusal, and evidence coverage must remain equal.
  Copy parity is asserted at import, so a missing key fails the build rather than the visitor.
- Customer-facing strings live in the copy modules, never authored in JavaScript.
- Telemetry is content-free. No customer raw rows, source column values, filenames, secrets, opaque
  owner/session identifiers, or storage paths reach an AI provider.
- Ahmed Shaaban is the only merge authority. A branch or PR is a proposal until merged.

**Registered authority is narrower than the roadmap's program list.** `governance/registry.yaml`
contains `FND`, `RRA`, and `RCA` only. The programs `W1`, `T1`, `G2`, `G3`, and `U1` have **zero
registry entries** — they are roadmap programs, not registered authority, so no M3 slice is
admissible on them and any design work against them is direction only.

Explicitly undecided product facts: retention clock cardinality; tombstone fields; whether deletion
is owner-only in the shipped sense; the customer-facing trust-state vocabulary and its counting
grammar; and the primary navigation label set (see the conflict below).

## Brand Commitments

- Product name and wordmark: **KHEPRI**, set in the type face already shipped, letterspaced. A
  picture of a name is not a name — the wordmark carries real text so a speech-input reader can
  operate the control.
- Voice: plain, specific, and non-overclaiming. Copy is **reason-driven** and must not assert a
  cause the governed state does not prove. Neutral defaults ("We couldn't complete this analysis.",
  "Content is no longer available.") are specialized only where a governed reason proves the cause.
- Deadlines are stated in absolute time with a timezone, never as "7 days".
- **The interface never invents capability the system does not possess.** No dead "Coming Soon"
  navigation; a destination enters the navigation in the slice that implements it.

## Evidence on Hand

Real, in-repository:

- `docs/product/KHEPRI_PRODUCT_UX_BLUEPRINT.md` — the single current product UX reference. Grants no
  implementation authority; carries a per-decision status vocabulary (LOCKED / PROVISIONAL /
  CONFLICT-BLOCKED / AUTHORITY-BLOCKED / IMPLEMENTATION-BLOCKED / SHIPPED).
- `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` — outranks the blueprint.
- `docs/superpowers/specs/2026-08-25-m2-ux-design-critique.md` — M2 critique at baseline `b19f365`,
  with computed (not asserted) contrast figures and a *Refuted claims* section. Several of its P0
  findings have since shipped; it must be re-verified against current files, not cited as current.
- The shipped stylesheets are the visual authority: `src/khepri/rra/journey/assets/shell.css`
  (tokens, no rules), `shell-components.css` (the component layer), `journey.css` (the journey), and
  `src/khepri/rra/rendering/templates/report.css` + `report.print.css` (the deliverable).

**Anti-reference, named so it is not rediscovered and used:** `docs/ui/design_handoff_khepri/`. Its
palette is dark against a shipped light one, and its asset plan names Google Fonts and a unpkg CDN —
both forbidden by the roadmap and unreachable under the shipped CSP. It is marked non-authoritative
in the design spec.

Absences future work must not fabricate: no customers, testimonials, benchmarks, pricing, licensing,
or deployment claims are established. No dark palette for the app. No icon set. No second typeface.
No elevation ramp. Each of those four is a **recorded deliberate absence**, not a gap.

## Product Principles

1. **Admission before claim.** Nothing is asserted about data that was not semantically admitted.
2. **A refusal is a governed result, not a failure.** It stays visible where the answer would have
   appeared, never defaults to error styling, and its reason and evidence are reachable.
3. **Evidence is contextual.** It is reached from the claim it supports; there is no generic primary
   "Evidence" destination.
4. **Operational state and trust state are two dimensions and are never fused** into one compound
   badge. What is happening to this analysis is a different question from what Khepri could safely
   support.
5. **Machine vocabulary never reaches a customer.** Internal state and reason identifiers are
   translated into operator language.
6. **The interface never invents capability the system does not possess** — including navigation to
   surfaces that do not exist and result counts the governed set does not fix.

## Accessibility & Inclusion

Established and verified in the shipped surfaces; these are floors, not aspirations:

- **44px minimum interactive target**, applied to the element a finger lands on rather than to a
  padded wrapper, in both languages at every supported viewport.
- **Logical CSS properties only.** All five stylesheets currently contain **zero** physical
  directional properties; that is a verified property to preserve, not a style preference.
- `lang` and `dir` are **server-computed**, never inferred in a template. `dir="auto"` for
  customer-controlled or mixed-script values (organization names, file names); `dir="ltr"` islands
  only for values guaranteed Latin, such as email addresses and tokens.
- No literal directional glyph as a navigation affordance — an arrow does not mirror.
- Truncate in character units, keeping the full value in the DOM so the accessible name is complete.
- Dates and numbers are locale-formatted; Arabic yields Arabic-Indic digits, Arabic month names, and
  Arabic decimal, grouping, and percent marks.
- Visible focus on every tab stop, including scrollable regions; a horizontally scrolling table
  stays keyboard reachable. A named region is a landmark and needs a meaningful, unique accessible
  name — but not every scrollable table must become a landmark merely to be focusable.
- `prefers-reduced-motion` guards the only animation, and fills the progress track rather than
  freezing it.
- Contrast is **computed, not asserted**. Current: `--ink` on `--paper` 15.37:1; `--muted` 6.23:1
  (AA, fails AAA only); `--accent` 6.83:1. The thinnest text in the product, step-nav `#667381` at
  12px, passes AA by 0.22 — no margin.
