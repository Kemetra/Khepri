# M2 UX design critique — Commercial Shell and RRA Journey

**Date:** 2026-08-25
**Baseline:** `b19f365` (`origin/main`), read in worktree `design/m2-ux-critique`
**Command:** `/impeccable critique`, design review only — no code, template, CSS, route, test, or package change
**Method:** two isolated assessments — A (design review, 24 dimensions), B (mechanical detector plus computed metrics)

## Evidence quality — read this before trusting a number

The Impeccable mechanical detector ran **DEGRADED**. Plugin `4.1.1` ships no `package.json` and no
`node_modules`, so `detector/engines/static-html/detect-html.mjs:127-128` cannot resolve
`htmlparser2`, `css-select`, `css-tree`, or `domutils` as bare ESM specifiers. The fallback is regex
matching, and the warning is suppressed on `.j2` files.

Consequently the three checks most relevant to this audit — **custom properties, selector matching,
and computed contrast** — never executed. Its findings are an undercount, not a clean bill of health.
Its one finding is `side-tab` at `report.css:103` (`border-inline-start: 4px solid`), which is a
*logical* property and most likely a false positive.

Contrast and token drift in this document were therefore **computed directly** rather than detected.

Assessment B **refuted two** of Assessment A's claims; both refutations were independently
re-verified before publication and are recorded in *Refuted claims* below. Any figure in this
document traces to a `file:line` citation.

## A. Executive design verdict

Khepri M2 is **not a weak design that needs redesigning — it is a strong design with unfinished
seams.** The trust layer, RTL implementation, print engineering, and copy voice are better than most
bilingual enterprise products ship. Every serious problem is a *seam*: something built well on one
side of a boundary and not carried across.

Three seams produce nearly every P0:

1. **The token layer serves 6 of 17 templates.** `shell.css` is a genuinely excellent, reasoned token
   set. `journey.css` — the surface a customer completes a task in — and `report.css` — the
   deliverable — consume **zero** of it. `var(--text-*)` appears **0 times in `src/`** despite ten
   tokens being defined.
2. **The shell↔journey handoff has no shared frame.** `/app` and `/beta` differ in navigation, header
   model, button treatment, skip-link mechanism, and the meaning of `.document-card`. The redirect is
   structurally correct; the *experience* of crossing it is not.
3. **Refusal is emitted but not expressed.** `.refused` ships with zero CSS rules. The product's core
   claim is "we tell you what we could not answer" — and that sentence renders as ordinary body prose.

**Ship-blocking on five items, all narrow and fixable inside `U1-01`/`U1-07`.** No visual-world
replacement is warranted.

## B. Already strong — do not redesign

| # | Strength | Evidence |
|---|---|---|
| 1 | RTL implementation — 0 physical directional properties, 78 logical, across 5 stylesheets | `journey.css:78-79` mirrored keyframe; `:54` RTL letter-spacing correction |
| 2 | `dir` never inferred in-template — server-computed | `routes.py:109`; `shell_copy.py:87` `DIRECTIONS` |
| 3 | `dir="ltr"` islands on emails, tokens, counts, `50 MB` | 7 targeted overrides |
| 4 | Print engineering — repeated `thead`, `break-inside`, palette stated so a dark container cannot print white-on-black, `overflow: visible` so no column clips | `report.print.css:18-31,63-76,168-184` |
| 5 | Trust copy and governed deletion deadline with timezone, not "7 days" | `report.js:3-6,13-16`; `copy.py:15` |
| 6 | Figure-naming rule (name → label → either) preventing identical row names carrying different numbers | `report.html.j2:84-103` |
| 7 | Structural i18n guarantees — import-time parity asserts plus `StrictUndefined`: a missing key fails the build, not the visitor | `copy.py:163`; `shell_copy.py:81`; `routes.py:48` |
| 8 | Zero `innerHTML` across 257 lines of JS — all writes via `createElement` + `textContent` | all 5 JS files |
| 9 | Polling discipline — recursive `setTimeout`, 1s→10s backoff, suspends on `document.hidden` | `processing.js:3,13,34,37` |
| 10 | Progressbar semantics — determinate upload has live `aria-valuenow`; indeterminate processing correctly omits it | `upload.js:56`; `processing.html.j2:6` |
| 11 | Table semantics — captions, `scope="col"`/`scope="row"`, per-section `aria-labelledby`, no heading skips, exactly one `h1` per page | verified composed across all 4 roots |
| 12 | Refusal-surface security discipline — `unavailable.html.j2` takes no state so it can disclose none | intentional; findings below concern the missing *next step*, not the withholding |
| 13 | Consent gates the input, not just submit | `upload.js:26` |
| 14 | No generic-SaaS tells — no gradient hero, shadow ramp, emoji, toast layer, icon library, "Oops!" | `--shadow: none` |

## C. Top M2 UX problems

### P0 — blocks understandable or safe M2 use

**1. `.refused` has no CSS rule. ADD.**
`report.html.j2:65` emits `<p class="refused">`; grep returns **zero** rules in `report.css` and
`report.print.css`. A refused section is visually identical to body prose — same size, colour,
weight — in web, evidence *and* PDF. This is the most important "we did not answer this" signal in
the product, and it is invisible.

**2. Raw machine identifiers on the comprehension surface. ADD.**
`review.js:16` prints `mapping.semantic` — 11 snake_case values (`transaction_date`, `net_revenue`,
`units`, …) — under the localized heading "Retail meaning", and `mapping.state` (`mapped` /
`ambiguous`) under "Status". `copy.py:49-52` localizes the four *column headers* and supplies no
value vocabulary at all. In Arabic this is an RTL table whose two central columns are Latin
snake_case. This is the page where the customer confirms we understood their data.
Source of the values: `mapping.py:23-33,37-38`.

**3. The invitation form does not exist. ADD.**
`shell_invitations.py:127` declares `POST /app/{lang}/{org}/team/invitations`, reading `email` and
`role` from a form body. There are exactly two forms in the shell templates:
`switcher.html.j2:32` (new analysis) and `team.html.j2:50`, which is a **revoke** form. Owners can
revoke invitations but cannot create one. The route is unreachable from any shipped UI.

**4. `.document-card` means opposite things across the handoff. IMPROVE.**
`journey.css:51` → `max-width: 860px; border: 0; padding: 0`.
`shell-components.css:61` → `max-inline-size: 60rem` (960px); `border: 1px solid`;
`padding: var(--space-4)`.
The sheets never co-load, so no bug fires and no test catches it — but the same semantic element is
100px wider, bordered and padded on one side of the crossing and edge-to-edge on the other.

**5. "Start a new analysis" hardcodes `organizations[0]`. IMPROVE.**
`switcher.html.j2:32`. A multi-org member opens the analysis in whichever organization sorted first,
with nothing on screen naming it. The page's own comment is scrupulous about not disclosing an
organization count — then the form below silently picks one.

### P1 — materially hurts usability or trust

| # | Finding | Cite | Class |
|---|---|---|---|
| 6 | Shell has no navigation and no language switcher; brand is a bare `<span>`. Arabic visitors on `/app` cannot switch language. `prefix` and `language` are already in scope | `shell.html.j2:12-14`; cf. `base.html.j2:12-17`; `shell_api.py:201` | ADD |
| 7 | Terminal states offer no way out — `expired` and `unavailable` are prose-only; the journey brand link bounces back | `expired.html.j2:5-11`; `unavailable.html.j2:11-14`; `common.js:25` | ADD |
| 8 | No metric→evidence path. `_evidence.html.j2:91` mints `citation-*` anchors nothing targets; the only pointer is prose, "available on request", for a document already published at a URL | `report.html.j2:53-57`; `html.py:120-121` | ADD |
| 9 | Processing conveys no position. Four stages render as a static `<ol>` beside a bar that never advances, while `job_state` and `package_present` are already polled | `processing.html.j2:7`; `state.py:36-38` | IMPROVE |
| 10 | A governed refusal looks exactly like a transport error — `#profile-findings` reuses `.error-summary` | `review.html.j2:7` vs `upload.html.j2:12` | IMPROVE |
| 11 | Broken back-link. "Back to the team" omits the organization segment, so `segments[2]` is empty and it resolves to the switcher | `invitation_issued.html.j2:16`; `shell_api.py:330-347` | IMPROVE |
| 12 | Four user-facing strings inlined in JS, outside `copy.py`'s import-time parity guard | `upload.js:32,74`; `review.js:40,45` | IMPROVE |
| 13 | Seven undifferentiated artifact cards — no grouping, no format hint, no open-vs-download distinction | `report.js:18-27` | IMPROVE |
| 14 | `.skip-link` is two mechanisms — `fixed`/`translateY(-180%)` vs `absolute`/`-9999px`, with inverted colours | `journey.css:39` vs `shell-components.css:45` | IMPROVE |
| 15 | Dark palette on one of three surfaces, undocumented. A dark-preference OS yields a dark report and a light app | `report.css:262-274` | IMPROVE |
| 16 | `aria-current` absent — the active step is `border-block-end` plus colour and weight only. Verified 0 occurrences repo-wide | `journey.css:48`; `base.html.j2:21-24` | IMPROVE |

### P2 — polish

- `#processing-status` starts empty, so the `aria-live` region announces nothing until the first poll
  resolves (`processing.html.j2:8`).
- `#processing-recovery` ships without `hidden`, so the destructive "Delete session content" action is
  visible during normal processing and `processing.js:30`'s failure branch is a no-op.
- Report `.scroller` has no `tabindex`, so report tables are not keyboard-scrollable (`report.css:120`;
  contrast `review.html.j2:18`, which does this correctly).
- `.caveats--section` is unstyled (`report.html.j2:146`), so a section-scoped caveat is
  indistinguishable from the global list at `:157`.
- `report.js:25` sets `link.dir` from session language rather than artifact language, for all 7 links.
- `journey.css:108` sets `grid-template-columns` on `.report-meta`, which is `display: flex` — an
  inert declaration.
- `shell.css:4` docstring is stale: it still reads "Design output, not yet wired. No template links
  this file", but `R8-02` wired it. This is the token source of truth, and the staleness is what
  invites the orphaned-stylesheet misreading refuted below.

## D. Shell / Journey consistency findings

| Element | Journey | Shell | Class |
|---|---|---|---|
| `.document-card` | `border: 0; padding: 0`, 860px | `1px solid`, `space-4`, 960px | **P0** |
| Header | `.site-header`, `min-height: 64px`, border on all four sides | `.shell-identity`, `padding-block`, `border-block-end` only | P1 |
| Primary button | `min-block-size: 46px`, transparent, `--accent` text | `min-height: 44px`, `--accent-surface` fill, `--accent-dark` text | P1 |
| Skip link | `fixed` + `translateY`, `--ink` background | `absolute` + `-9999px`, `--surface` background, `min-height: 44px` | P1 |
| Navigation | 4-step nav, home link, language link | none | P1 |
| Idiom | `max-width`, `border: 0` (physical, older) | `max-inline-size`, logical tokens | — |

The shell is the newer, more disciplined layer. **Consolidation should run journey → shell**, not the
reverse.

The transition itself is correct and must be kept: `shell_journey_entry.py:93-105` performs a 303
redirect and sets the cookie only on success, deliberately omitting it on the refusal path
(`:73-76`). The defect is that the visitor crosses from `/app` to `/beta` with no shared frame and no
route back.

## E. Trust and evidence UX findings

The trust *content* is the product's best work. The trust *signalling* has three holes: `.refused`
unstyled (P0), `.caveats--section` unstyled (P2), and evidence published but unreachable from the
report (P1). "Available on request", for a live URL, actively reduces trust — it reads as
withholding.

`report.html.j2:41` `.disclosure` is the counter-example done right: `border-inline-start: 4px` plus a
tint, and `report.print.css:131-135` drops to the rule alone so nothing depends on the printer
honouring backgrounds. Severity is not colour-only. **This is the pattern `.refused` should follow.**

## F. Mobile, RTL, and accessibility findings

**RTL — excellent, do not touch.** Zero physical directional properties, 78 logical, across all five
stylesheets. `text-align` uses only `center` and `start`. The RTL defects are all *content*, not
layout: untranslated identifiers (#2), JS-inlined strings (#12), and `report.js:25`.

**Contrast — computed (WCAG 2.x relative luminance), not asserted:**

| Pair | Ratio | Verdict |
|---|---|---|
| `--ink` on `--paper` | 15.37 | AAA |
| `--muted` on `--paper` | **6.23** | **AA pass** (fails AAA 7:1 only) |
| `--accent` on `--paper` | 6.83 | AA |
| step-nav `#667381` at 12px (`journey.css:46`) | 4.72 | AA by 0.22 — no margin, thinnest text in the product |
| disabled `#7b817e` (`journey.css:68`) | 3.87 | Below AA but **WCAG-exempt** (disabled control) |
| `--report-ink` on white | 17.63 | AAA |
| report dark palette, all pairs | 7.99–15.87 | AAA |
| `--line` on `--paper` | 1.43 | decorative rule, not a state indicator |

**Accessibility — strong, with four real gaps.** Viewport meta on all four roots; skip links on both
interactive roots (absent on the two static report documents, which is acceptable);
`<main tabindex="-1">` on both; exactly one `h1` per page with no skipped levels;
`prefers-reduced-motion` guards the only animation and fills the track rather than freezing it.
Gaps: `aria-current` absent (#16), empty `aria-live` region, non-keyboard-scrollable report tables,
and the unhidden recovery control.

**Mobile.** One 640px breakpoint (`journey.css:97-110`); tables scroll; `body { min-width: 320px }`.
`shell-components.css` has no media query at all — `flex-wrap` saves it, so this is a DEFER/P2.

## G. Visual-system inconsistencies

| Class | Count | Evidence |
|---|---|---|
| Font-size declarations | **19 declarations, 16 distinct** | `.82`/`.83`/`.84rem` all confirmed: `journey.css:95,59,89,42`; `shell.css:110`. `.83`/`.84` hide inside `font:` shorthand |
| `--text-*` tokens defined | **10** | `var(--text-*)` used **0 times in `src/`** |
| Tokens in `shell.css` | **48** | **34 unused** by `shell-components.css`, its only co-loaded consumer |
| Radius tokens | 4 | **1** application total: `border-radius: 0` (`journey.css:65`) |
| Spacing values | 25 distinct | **17 off-scale** against the 8-step `--space-*` ramp |
| Distinct hex literals | 34 | 4 near-duplicate pairs (≤2 per channel); no `rgb()`, `hsl()`, or `oklch()` |
| Danger family | 3 tokens at `shell.css:69-71` | `journey.css:73` re-inlines the same three hexes |
| Figure/ground | `--paper` == `--surface` == `#fbfcfd` | plus `--shadow: none` and `border: 0` — nothing is visually contained |
| Class-name collisions | **2** | `.document-card`, `.skip-link` |
| Emitted classes with no rule | **2** | `.refused`, `.caveats--section` |

## Refuted claims

Recorded so they are not re-raised:

- **"The shell stylesheets are orphaned" — REFUTED.** `shell.css` and `shell-components.css` are
  linked at `shell.html.j2:7-8` and served from the allowlist at `shell_api.py:71-72`. The stale
  docstring at `shell.css:4` is what invites this misreading.
- **"`--muted` fails contrast" — REFUTED.** `--muted` on `--paper` computes to **6.23:1**, which
  passes AA for normal text. It fails only AAA. No colour change is needed. The only sub-4.5 value in
  the product is the disabled button label at 3.87:1, which WCAG 1.4.3 exempts.
- **"`journey.css` contains physical directional properties" — REFUTED.** Its `text-align` values are
  `center` and `start`, both direction-agnostic.

## H. Recommended M2 information hierarchy

```text
One persistent frame across /app and /beta
├─ Identity bar     KHEPRI → home (link, not span) · organization name · language toggle
├─ Context line     which organization · which analysis
└─ Progress         4-step nav, aria-current on the active step

Journey page
├─ h1 + lede                    ← already correct
├─ Primary action zone          ← one decision per page
├─ Governed findings            ← refusal must not share error paint
└─ Retention promise            ← already in every footer

Report
├─ h1 + generated / expires
├─ Section nav, including an evidence entry point
├─ Sections: figure → chart → table → caveat
│    refused sections visually distinct
└─ Artifacts: grouped Open | Download
```

## I. Recommended shell-to-analysis flow

```text
/app/{lang}/{org}          switcher — organization named explicitly, not organizations[0]
      │
      ├─ team ──► invite form (ADD) ──► invitation_issued ──► back to THIS org's team
      │
      └─ "New analysis" POST ──► 303 ──► /beta/{lang}/upload
                                            │  shared frame retained; route back to /app
                                            ▼
                     upload → review → processing → report
                                            │
                              ┌─────────────┴─────────────┐
                              ▼                           ▼
                        artifacts (grouped)          evidence (linked from metrics)
                              │
              expired ──► "Start a new analysis" ──► back to /app  (ADD)
```

## J. Prioritized design backlog

| Rank | Item | Class | Severity |
|---|---|---|---|
| 1 | Style `.refused` and `.caveats--section` across web, print, and PDF, not colour-only | ADD | P0 |
| 2 | Bilingual value vocabulary for `mapping.semantic` and `mapping.state` in `copy.py` | ADD | P0 |
| 3 | Invite form on `team.html.j2` for the route that already exists | ADD | P0 |
| 4 | Resolve `.document-card` to one meaning; consolidate journey onto shell | IMPROVE | P0 |
| 5 | Name the organization on "New analysis"; drop `organizations[0]` | IMPROVE | P0 |
| 6 | Shell navigation and language switcher | ADD | P1 |
| 7 | Exit links on `expired` and `unavailable` | ADD | P1 |
| 8 | Metric→evidence link; retire "available on request" | ADD | P1 |
| 9 | Stage position in processing, from already-polled state | IMPROVE | P1 |
| 10 | Separate refusal paint from error paint | IMPROVE | P1 |
| 11 | Fix the organization segment in the team back-link | IMPROVE | P1 |
| 12 | Move the four JS strings into `copy.py` | IMPROVE | P1 |
| 13 | Group artifacts; distinguish open from download | IMPROVE | P1 |
| 14 | One `.skip-link` mechanism | IMPROVE | P1 |
| 15 | Scope or document the report dark palette | IMPROVE | P1 |
| 16 | `aria-current` on the active step | IMPROVE | P1 |
| 17 | Consume `--text-*`, `--space-*`, and the danger tokens in `journey.css` | IMPROVE | P2 |
| 18 | Seed `#processing-status`; add `hidden` to `#processing-recovery` | IMPROVE | P2 |
| 19 | `tabindex="0"` on the report `.scroller` | IMPROVE | P2 |
| 20 | Fix the stale `shell.css:4` docstring | IMPROVE | P2 |

## K. M2 versus T1/U1 versus M3

Grounded in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.

**M2 now — `U1-01`** ("preserve and document the merged primitive tokens"): items 1, 4, 10, 11, 12,
13, 14, 16, 17, 20.

**M2 now — `U1-07` gate** ("New surface cannot ship unmeasured or without refusal/loading/empty
states"): items 1 and 10, plus tokenized empty and error states. This is a **gate**, not a
nice-to-have, and it names exactly these.

**M2 now — shell / `R8`:** items 3, 5, 6, 7. Note `ON1-04` owns *complete* invite, role, and
membership administration UX and sits outside M2's dependency graph — M2 needs only a minimum viable
invite form.

**DEFER — T1/U1, already owned.** These appear in the brief as "missing M2 surfaces" but are
scheduled work with owners, so they are DEFER rather than defects: Analysis Quality Summary is
**`T1-04`**; metric and evidence detail is **`T1-05`**; the evidence drawer is **`U1-04`**; journey
and shell evidence entry points are **`R8-10`**, which explicitly depends on "T1 minimum". Item 8 is
the cheap half — linking to evidence that already exists — and can precede `T1-05`.

**DEFER — M3:** loading skeletons; dashboard and history (the roadmap states "No dashboard or history
is faked").

**Not defects — recorded absences** (`shell.css:26-33`): dark palette, second typeface, icon set,
elevation ramp, component tokens. Also the chart label collision at 12-plus categories
(`report.css:241-260`), which is recorded and owned by the geometry module.

**Scope hole for an owner decision.** Roadmap §8 lists **"New Analysis"** as an M2 UI surface, and no
task ID anywhere owns it; every other M2 UI item maps to a task. Related: `M1`'s exit gate declares
invitations "merged" — the backend is — while the *UX* sits in `ON1-04`, outside M2. That is how
finding #3 shipped with no gate positioned to catch it.

## L. Recommended next command

`/impeccable harden src/khepri/rra/journey src/khepri/runtime/shell_templates`

`harden` owns errors, i18n, and edge cases, which is the shape of this backlog's top ten: unstyled
refusal, untranslated values, JS-inlined strings outside the parity guard, terminal states with no
exit, refusal-versus-error confusion. It maps directly onto the `U1-07` gate.

Then `/impeccable extract` for items 4, 14, and 17 — the token and component consolidation that pulls
`journey.css` onto the `shell.css` layer.

Not `polish` (the surface is not the problem), not `bolder` (this product should not be louder), not
`layout` (spacing is off-scale but not broken).
