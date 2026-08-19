# `R8-01` — commercial shell information architecture and design tokens

**Task:** `R8-01` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Output is *"UI design only"* —
information architecture and design tokens. No template, no route, no handler. `R8-02` builds the
shared layout, `R8-03`…`R8-06` the surfaces, `R8-07` the quality evidence.

**Baseline:** `main` @ `b9c8755`, 2026-08-19.

**Governing constraints, none of them this note's to choose:**

- `KHEPRI-DEC-008` fixes the runtime: FastAPI, Jinja2, bundled CSS, minimal bundled JavaScript. No
  SPA, no Node runtime. `2026-08-13-client-journey-ui-design.md` §Approaches records that HTMX and
  Alpine were considered and **rejected** — "both add a new client dependency and interaction
  vocabulary". This note does not relitigate any of it.
- The roadmap's UI guardrails: preserve server rendering, no empty widgets or fake history, reuse the
  four-step journey as a workflow rather than as the shell, equal Arabic and English coverage, and
  **no external fonts, analytics scripts, CDNs, or runtime assets**.

---

## 1. What already exists, stated first

One page-rendering module in the repository: `src/khepri/rra/journey/routes.py`. Everything else in
`rra/api.py` and `rra/report_api.py` returns JSON or bytes.

| Concern | Where | Shape |
|---|---|---|
| Templates | `src/khepri/rra/journey/templates/` | Jinja2 package data, one `base.html.j2` + five step templates, three blocks (`title`, `content`, `script`) |
| Environment | `routes.py:44-49` | `StrictUndefined` — every variable a template names must be supplied or rendering raises |
| Stylesheet | `assets/journey.css` | 114 lines, hand-written, no build step |
| Copy | `journey/copy.py` | closed dict, 71 keys per language, **parity enforced at import** (`:163-164`) |
| Direction | `routes.py:109-110` | derived from language, never stored |
| Assets | `routes.py:26-33` | hardcoded allowlist served through one route, **not** a `StaticFiles` mount |
| Fonts | `rendering/typefaces/` | local `woff2`, verified against a SHA-256 manifest by `rendering/fonts.py` |
| CSP | `journey/security.py:20-31` | `default-src 'none'` — no CDN is reachable even if a template named one |

**Nine of the ten commercial surfaces have no UI at all.** The identity backend behind them is
substantial — 21 modules under `src/khepri/rca/`, ~35 test files — so `R8` is genuinely UI work over
a built spine, not UI work waiting on a backend.

| Surface | Template | Backend that exists |
|---|---|---|
| Sign in | absent | `rca/sessions.py`, `session_service.py`, `session_cookie.py`, `credentials.py` |
| Recovery | absent | `rca/credentials.py`, `rca/session_retention.py` |
| Organization selection/switching | absent | `rca/switching.py`, `rca/authorization.py` |
| Team and invitation management | absent | `rca/invitations.py`, `rca/accounts.py`, `rca/lifecycle.py` |
| Account settings | absent | `rca/accounts.py` |
| Organization settings | absent | `rca/organizations.py`, `rca/isolation.py` |
| New analysis entry | absent | — the journey entry is an invitation bootstrap, not organization-scoped |
| The four-step journey | **exists** | fully wired |
| Expired / deleted / unavailable | **one template, two branches** (`expired.html.j2`) | `rra/session_cookie.py` |
| Unauthorized | absent | `rca/authorization.py` — 401/403 as JSON only |

### 1.1 `docs/ui/design_handoff_khepri/` is not authoritative, and following it would break a guardrail

The handoff README is 753 lines of high-fidelity direction — a full type scale, a dark and light
token set, shell anatomy, six operator screens, a responsive grid-reflow table. It is the best
available *layout and IA* reference and this note reuses it as such.

**Its asset plan is unusable.** `README.md:691-700` specifies IBM Plex Sans Arabic from **Google
Fonts** and Phosphor Icons from **`https://unpkg.com/@phosphor-icons/web@2.1.1/`**. The roadmap's UI
guardrails forbid both in terms: "No external fonts, analytics scripts, CDNs, or runtime assets."
The CSP would refuse them at runtime even if a template asked.

Its token *values* are equally superseded: it describes a dark palette (`--color-bg #161826`,
`--color-accent #9184d9`) against a shipped light one. The tie-breaker is explicit —
`2026-08-13-client-journey-ui-design.md:15-16`: *"The imported files under
`docs/ui/design_handoff_khepri/` remain non-authoritative visual reference. Production code recreates
the design; it does not port the prototype runtime."*

**So: reuse the handoff's IA and responsive reasoning; take tokens from the shipped stylesheet.**
Recorded because the handoff is detailed enough to look authoritative, and adopting its asset section
is a guardrail violation on the first commit.

---

## 2. The token gap, measured

`journey.css:15-30` declares **16 custom properties, and all but two are colors**. There is no
spacing scale, no type scale, and no radius scale. Two consequences, both counted rather than
asserted:

**Ten hex values bypass the token set entirely**, all in rules below `:root`:

| Value | Used for | Nearest token |
|---|---|---|
| `#e4e8ed` | step-nav bottom rule | `--line` `#cfd6de` |
| `#e3e7eb` | a second rule | `--line` |
| `#e3ded1` | a warm rule | none — genuinely different |
| `#667381` | secondary text | `--muted` `#55606d` |
| `#7b817e` | a third grey | `--muted` |
| `#fafbfd` | a raised surface | `--surface` `#fbfcfd` |
| `#f0f5fa` | a tinted surface | none |
| `#d9a49f` `#faece9` `#6d201b` | the error palette | `--danger` `#9a2d26` alone |

Three of those are one or two hex digits from an existing token, which is what an eyeballed value
looks like next to a chosen one. The error palette is a real gap: `--danger` is a single ink with no
surface or border companion, so the error box invented its own three.

**About fifty distinct hardcoded sizes**, including these near-duplicate runs:

- `.68rem` / `.7rem`
- `.82rem` / `.83rem` / `.84rem` / `.86rem`
- `1.15rem` / `1.16rem`
- `1050px` / `1068px`, and separately `820px` / `860px`

`.82`, `.83`, and `.84rem` are not three decisions. They are three rules that each got their own
value, and a type scale collapses them to one token. **This is `R8-01`'s core deliverable**: not
inventing a visual language, but promoting the one that shipped into scales, so `R8-02`…`R8-06` add
nine surfaces without adding ninety more literals.

---

## 3. The tokens

Proposed as real CSS in `src/khepri/rra/journey/assets/shell.css`, not as a table in prose, so
`R8-02` consumes them rather than reinterpreting them. **The file is referenced by no template in
this slice** — it is design output, and `R8-02` is what links it.

**Every color token traces to a value already shipping, and exactly two are derived rather than
copied.** No new *hue* is introduced, because a shell that looked different from the journey it wraps
would fail the guardrail asking the journey be reused as a workflow rather than replaced. The two
derived values are `--ready-border` and `--ready-surface`: `--ready`'s own hue at the saturation and
lightness steps the shipped danger family uses. A first draft eyeballed them instead, drifting the
hue from 151 to 146 — close enough to look intentional and derived from nothing. §7's first test is
what caught it, which is the argument for writing that test rather than asserting the claim.

### 3.1 What is added, and why each

- **A spacing scale** on a 4px base — `--space-1` … `--space-8`. The existing values cluster around
  `.35`/`.45`/`.65`/`1`/`1.5`/`2`/`2.8`/`4rem`, which is close to a 4px ramp already; the scale names
  what was nearly there.
- **A type scale** — `--text-xs` … `--text-2xl`, plus the two `clamp()` pairs that already exist for
  `h1` and `.lede` kept as `--text-display` and `--text-lede`. Fluid where the shipped stylesheet is
  fluid; fixed where it is fixed. The near-duplicate runs above collapse into `--text-sm` and
  `--text-base`.
- **A radius scale** — `--radius-sm` (the shipped `3px`), `--radius-md`, `--radius-pill`. The shipped
  `--radius: 3px` is retained as an alias so no existing rule changes meaning.
- **Companion surfaces and borders for every status ink.** `--danger` gains
  `--danger-surface`/`--danger-border` from the three hex values the error box already uses, and
  `--ready` gains the same pair so a success state does not have to invent them later. This is the
  one place the token set grows to cover a state the journey has and the shell will need more of.
- **`--line-subtle`** for `#e4e8ed`/`#e3e7eb`, which are a lighter rule than `--line` rather than a
  mistake.

### 3.2 What is deliberately not added

- **No dark palette.** `color-scheme: light` is shipped and a second palette is a product decision
  nobody has made. `--paper`/`--surface`/`--ink` are named by role rather than by value, so a later
  slice can add one without renaming anything.
- **No new typeface and no icon set.** Noto Sans Arabic ships with an audited digest and covers both
  scripts. Adding IBM Plex or Phosphor requires the process at
  `2026-08-13-client-journey-ui-design.md:214-217` — licence plus audited digest plus local hosting —
  and `R8-01` does not spend that budget speculatively. The journey's one icon is inline SVG
  (`upload.html.j2:16`); the shell follows.
- **No elevation scale.** `--shadow: none` is shipped, and the design direction is flat. A shadow
  ramp with no user would be the "empty widget" the guardrails forbid, one layer down.
- **No component tokens** (`--button-bg`, `--card-padding`). Nine surfaces do not exist yet, so
  component tokens now would encode guesses. Primitives first; `R8-02` promotes what repeats.

---

## 4. Information architecture

### 4.1 Route namespace — and why not under `/beta/`

Two facts make this a decision rather than a default:

- `routes.py:141-147` registers `/beta/{language}/{step}` as a **catch-all**. Any shell route under
  `/beta/` collides with it.
- `routes.py:126` registers `app.middleware("http")(endpoints.security)` — a **global** HTTP
  middleware, from inside the journey package. A second global middleware is not additive in an
  obvious way.

So the shell takes its own prefix, `/app/{language}/…`, and the journey keeps `/beta/`. Two
consequences worth stating:

- **The journey is reached from the shell rather than absorbed into it.** `R8-06` routes New Analysis
  into the existing flow; it does not re-implement four steps inside `/app/`. This is the guardrail's
  "reuse the current four-step journey as a workflow, not as the full product shell", expressed as a
  URL boundary.
- **`R8-02` owns whether the shell shares `endpoints.security` or declares its own.** This note
  raises it rather than settling it: the answer depends on whether the commercial session cookie
  wants the same CSP and cache headers as the beta one, which is `R3-06` territory and not visual
  design.

### 4.2 The surface map

```
/app/{language}
├── sign-in                      R8-03   unauthenticated
├── recovery                     R8-03   unauthenticated
├── (organization chooser)       R8-04   authenticated, no active organization
└── {organization}/
    ├── analyses                 R8-06   the landing surface: entry + nothing else yet
    ├── team                     R8-05   members, roles, invitations
    ├── settings                 R8-05   organization settings within RCA-001 scope
    └── account                  R8-05   account settings (not organization-scoped; see below)
```

**`account` sits under the organization path deliberately, and it is the one arguable placement.**
An account is not organization-scoped, so `/app/{language}/account` would be more truthful. It is
nested because every authenticated view needs the organization context in the header anyway, and a
route that drops it forces the shell to decide what to render in the switcher. `R8-02` may hoist it
if the layout turns out not to need the context; recorded so that is a change with a reason rather
than a correction.

**No dashboard, no history, no reports index.** The handoff's operator screens describe a product
with all three; the guardrails forbid building them empty. `analyses` is an entry point, not a list.

### 4.3 The four edge states

Today `expired.html.j2` serves expired, deletion-requested, and session-unavailable from **one
template with two branches**, and unauthorized does not exist as a page at all.

**This note keeps them collapsed, and separates exactly one.**

| State | Surface | Why |
|---|---|---|
| expired | shared `unavailable` | |
| deleted / deletion requested | shared `unavailable` | |
| session unavailable | shared `unavailable` | |
| **no membership** | **its own surface** | it is the only one with an action |

The three collapsed states share a surface because **distinguishing them is a disclosure**. The
design spec's failure table ends with the rule (`:266-267`): *"Unknown states and unknown reason
codes fail closed to a generic unavailable response and are not rendered verbatim"*, and `:254`
records that missing, expired, deleted, and foreign sessions are *deliberately indistinguishable*. A
shell that told a visitor "this analysis was deleted" rather than "unavailable" would answer a
question about someone else's data.

**"No membership" is different in kind, not degree.** An authenticated account with no organization
is not a refusal — it is a state with a next step, which `FR-028` requires be reachable ("an account
with no membership must authenticate"). It gets a surface because it needs a call to action, and
that is the only reason.

**Unauthorized — an authenticated actor asking for an organization they are not in — routes to the
shared `unavailable` surface, not to a distinct one.** `FR-023` requires a foreign organization be
indistinguishable from a nonexistent one, and `R6-06`'s scenario 14 already tests that at the
service layer. A dedicated "you do not have access to this organization" page would restate, in the
UI, the enumeration oracle the resolver refuses to be.

### 4.4 The shell chrome

Extending `base.html.j2`'s existing anatomy rather than replacing it — skip link, `.site-header`,
`.site-footer`, and `<main id="main-content" tabindex="-1">` all stay, and the tests at
`test_rra_journey_accessibility.py:11-21` already assert their shape.

What the authenticated header adds: the organization switcher, and the account menu. What it keeps:
the wordmark and the language link, whose `href` pattern (`/app/{alternate}/…`) preserves the current
surface exactly as the journey's does. **Language stays in the URL path**, per the design spec's
requirement that switching cannot mutate workflow state.

`.step-nav` is journey-only and does not appear in the shell. The shell's navigation is the
organization-scoped surface list, which is a different axis.

---

## 5. Bilingual and accessibility obligations, inherited not invented

Everything here already exists and applies unchanged; recorded so `R8-02` extends rather than
reinvents.

- **Copy lives in a closed dict with import-time parity.** `copy.py:163-164` raises if the two key
  sets differ. `R8`'s surfaces extend `_EN`/`_AR` — currently 71 keys each — and inherit that check.
  This is the mechanism behind the guardrail's "equal Arabic and English state/action coverage"; no
  gettext, no catalog format, no new dependency.
- **Logical CSS properties only.** `journey.css` already uses `inset-inline-start`,
  `padding-inline`, `border-block-end` throughout, with three justified `[dir="rtl"]` exceptions.
  `report.css` has a **test** enforcing this (`test_rra006_html_surface.py:406-424` asserts no
  physical property name appears in the file); `journey.css` does not. **`R8-07` owes that test for
  the shell stylesheet**, and it is cheap.
- **Latin and numeric runs carry explicit `dir="ltr"`.** See `upload.html.j2:9`, `report.html.j2:7`.
  Every count, timestamp, and identifier the shell renders needs the same treatment.
- **44px minimum touch targets and no horizontal overflow at 390px**, both machine-verified in both
  languages by `test_rra_journey_browser.py`. New surfaces are held to the same bar.
- **`StrictUndefined`.** Every template variable must be supplied. A copy key added to `_EN` and
  forgotten in a context dict is a render failure, not a blank.

---

## 6. What this note does not settle

- **Whether the shell shares the journey's security middleware** — §4.1, `R8-02`'s call, and it
  depends on `R3-06`'s cookie boundary rather than on visual design.
- **Visual regression baselines.** The design spec asked for screenshot comparison against the
  imported references; no baseline-image test exists — Playwright is used for geometry only. That is
  net-new `R8-07` work and this note does not scope it.
- **Whether `account` stays nested** — §4.2.
- **Any surface's content.** This is IA and tokens. What a team page *says* is `R8-05` with `R4`'s
  invitation vocabulary, and what a settings page offers is bounded by `RCA-001`'s scope rather than
  by layout.
- **A dark palette, an icon set, an elevation ramp, component tokens** — §3.2, each with its reason.

---

## 7. Verification

`R8-01` produces no behavior, so the checks are consistency rather than function:

1. **`shell.css` parses and introduces no color that is not already shipping.** A test can assert
   the second half directly: every hex in `shell.css` appears in `journey.css`.
2. **No external reference.** `assert "http://" not in text and "https://" not in text`, the gate
   `test_rra_journey_pages.py:18-19` already applies to rendered pages, applied to the stylesheet.
3. **No physical CSS property**, mirroring `test_rra006_html_surface.py:420` — the test `journey.css`
   lacks and `R8-07` owes for both.
4. **The orphan-value count does not grow.** The ten values in §2 are the baseline; a slice adding an
   eleventh is choosing a color outside the system.

Items 1–3 are cheap and belong with the stylesheet. Item 4 is the one that keeps this slice's work
from eroding, and it is the same shape as the `STATUS.md` rollup guard: count something derived, and
assert it against its source.

All four are implemented in `tests/test_r801_shell_tokens.py`, along with three more the writing
suggested: that the token file declares tokens and no rules, that every scale the note promises is
actually present, and a self-test of the comment stripper — `shell.css` documents the values it
rejected, so a scan that read comments would fail on prose describing what the file does *not* use.

**Seven defect shapes were planted and caught**, including the one that mattered: `#a9cbb8`, the
eyeballed green a first draft used, which drifted `--ready`'s hue from 151 to 146. It looked
intentional and was not derived from anything. The hue check refuses it.

### 7.1 What is deliberately not wired

`shell.css` is **not** added to `routes.py:26-33`'s asset allowlist. Serving a stylesheet no template
links would be `R8-02`'s work landing early, and the roadmap's guardrails forbid building surfaces
that do not exist yet. The file is design output; `R8-02` registers it in the same slice that links
it, which is also when the CSP and cache-header questions in §4.1 have to be answered anyway.
