# `U1` slice 11 — Final polish against the reference pack, and the hero's first placement

**Authority:** `RCA-010` §Scope (shell presentation files, `shell_copy.py`, `tests/`), `RCA-012`
`FR-212`–`FR-218`, master specification §7 (asset policy), §16 (pack contract), §17 (visual
acceptance), §19 slice 11.

**Family:** `RCA`. **Branch off `main`.** One PR carrying the plan+RED commit and then the
implementation commit.

**Verified tree state:** `main` at `d534bea`, 2026-09-22. No open PRs.

---

## Why this slice exists now

Two independent things became true, and each was the other's blocker.

| Fact | Verified at `d534bea` |
|---|---|
| The hero derivatives resolve at the shell's own address | `#514`; `khepri-hero.jpg` / `.webp` served by exact name from `_ASSETS`, digests audited at import |
| Anything places them | **No.** `grep khepri-hero src/ --include=*.j2 --include=*.css` returns nothing, and `test_the_artwork_reaches_no_template` asserts it |
| `RCA-012` `FR-218`'s bilingual alt text | **Unshipped.** No `shell_copy.py` entry, because there was no `<img>` to attach one to |
| The §19 gate on this slice | **Open.** Row 11 reads "After §16 is approved", and §16 is merged and governing |
| The shell slice queue ahead of this one | **Exhausted.** 2b (`#480`), 4 (`#483`/`#510`), 5 (`#484`), 8 (`#485`), 9b (`#486`), 10b (`#488`) all merged |

So the hero is built, audited, packaged, served — and reaches no reader. `RCA-012` is **not fully
verified** by `#514`, and this is the slice that finishes it.

### The gate, read from §19 rather than from a paraphrase

The two allocation plans record slice 11 as "gated on §16; six references absent. An asset
dependency." That was a **tree-state finding dated 2026-09-17**. Master specification §19 row 11
states the gate itself as *"After §16 is approved"*, and §16.1 records the owner's decision as
governing on merge. §16 is merged.

The reference count moved too: §16.4 now records the owner's 2026-09-20 expansion plus the `#512`
handoff, leaving **#11 narrow and mobile** unreferenced and **#7** partial (composition only; the
four trust states undemonstrated) — two gaps, not six.

**Consequence.** Pack coverage does not gate whether this slice starts; it bounds **which surfaces
it may polish**. See §Scope ceiling.

---

## Scope ceiling — the exact authorized paths

Everything outside this list is out of scope, including every path `RCA-010` §Scope already
refuses.

| Path | Why it is admitted |
|---|---|
| `src/khepri/runtime/shell_templates/overview.html.j2` | `RCA-010` §Scope, presentation markup and ARIA state only |
| `src/khepri/rra/journey/assets/shell-components.css` | `RCA-010` §Scope, the shell's component rules |
| `src/khepri/rra/journey/assets/shell.css` | `RCA-010` §Scope, tokens only — **stays tokens-only**; the test asserting it declares no rules stays passing. Adds `--hero-ground` (see the palette note below) |
| `src/khepri/runtime/shell_copy.py` | `RCA-010` §Scope, chrome labels only — carries `FR-218`'s alt text |
| `tests/` | evidence, extending the existing modules |

**Not in scope, restated because this slice is adjacent to all of them:** `shell_api.py` and every
other `src/khepri/runtime/*.py` module (`RCA-010` §Scope and `RCA-012` §Exclusions both refuse it —
`#514` spent the one allowlist carve-out and it is not reopened); `src/khepri/rra/journey/hero.py`
and the derivative bytes (audited and merged; this slice reads them, never regenerates them); any
route, address, capability or authorization path (`FR-193`); `journey.css` and the `/beta`
surfaces; the report and chart surfaces; `landing.css`; migrations; the composition root.

**No new asset of any kind.** `FR-206` and §7.2 are unrelaxed: no CSS-drawn illustration, no
pseudo-element artwork, no inline SVG authored here, no second derivative, no external host. The
one artwork is the one `#514` audited.

---

## What this slice delivers

### A. The hero is placed on Overview, once

Handoff §6 and the `03-workspace-overview.png` reference both put a hero band on the workspace
overview. This slice places it on **`overview.html.j2` only** — one surface, the one with an
independent approved reference.

Binding placement values, taken from the handoff's §09 table and §6 (composition evidence, not
product fact — §16.3, `FR-205`):

- 238px band, ground `--hero-ground` `#F6EDDF` **behind** the image, as the loading fallback: the
  band shows a solid ground, never whatever sits beneath it, before the image decodes or if it
  fails (§7 and the handoff both require the solid ground);
- `object-fit: cover`, `object-position: 62% 46%`; RTL mirrors to `38% 46%` so the monument stays
  on the copy-free side — **the artwork itself is never mirrored**, only the focal point moves;
- **no scrim.** The heading and lede stay in the document card below the band, not over the
  artwork, so there is no copy on the image for a scrim to make legible. The handoff's ivory wash
  belongs to the composition that puts the headline on the band, and ships with the slice that
  makes that change;
- `loading="eager"` and `fetchpriority="high"`, as it is above the fold;
- `<picture>` with the WebP source and the JPEG fallback, both from `/app/assets/`.

**Crop only.** §7.2 and the handoff both forbid recreating, filtering, recolouring or rotating the
artwork. If a placement cannot be achieved by `object-position` alone, it is not achieved.

#### The palette premise, checked rather than assumed

`--hero-ground` **does not exist** in `shell.css` at `d534bea`; this slice adds it. That is
authorized, but only because a clause was spent recently, so the reasoning is recorded here rather
than left for a reviewer to reconstruct.

`shell.css`'s own module docstring still argues the **superseded** position: it says the pack's
"navy, gold and ivory values ... are deliberately absent" because a dark palette is "an unmade
product decision", citing §16.1. That was accurate when written. It is **no longer the operative
restriction**:

- `#511` (`9c6a74f`, 2026-09-22) **struck** §16.1's "a dark palette (an unmade product decision)"
  clause, recording that it "was never a prohibition on the palette itself";
- §16.5 records the owner's supplied handoff token set as **the approved palette, binding for color
  values**, taken as custom properties on `:root` in `shell.css` **under `RCA-010` §Scope** — which
  names this exact file and this exact mechanism;
- `hero-ground #F6EDDF` is in §16.5's "Ivory and sand — surfaces" row.

So the token is authorized by §16.5 by name. **Two obligations follow**, and a slice that skips
them ships a file arguing against its own contents:

1. **Correct `shell.css`'s docstring in the same change**, in place and not deleted, the way §A.4's
   reconciliation rule and `#511` itself both handle a spent clause — retaining the old verdict as
   the historical record and naming §16.5 as its successor. This is the recorded
   *merged-specs-keep-a-stale-header* trap: read the registry and the correcting commit, never the
   prose header.
2. **`test_r801_shell_tokens.py::test_shell_introduces_no_colour_outside_the_shipped_palette` will
   fail on `#F6EDDF`, and that is the guard working.** Verified at `d534bea` by reading the test:
   it computes `declared - shipped - _DERIVED` over `shell.css`'s hexes and asserts the remainder
   is empty, so **every colour in `shell.css` must already appear in `journey.css` or be recorded
   as derived**. `#F6EDDF` is in neither: it is a *supplied* palette value from §16.5, not a
   derivation of a shipped ink.

   Its own failure message names the two admitted escapes — "reuse a shipped value or record the
   derivation in `_DERIVED` and in the note" — and **neither fits**. Reusing a shipped value would
   discard the owner's approved `hero-ground`; `_DERIVED` is for values *derived from* a shipped
   hue and this one is not derived from anything.

   So this slice adds a **third, explicitly named** category for owner-supplied §16.5 values,
   carrying the same discipline `_DERIVED` carries: an exact frozenset, each entry traceable to the
   §16.5 row that supplies it, so a fourth colour still fails. **Do not widen the subtraction to a
   blanket allowance** — `declared - shipped - _DERIVED - _EVERYTHING_ELSE` would disarm the guard
   this slice is trying to honour, which is the recorded *guard-that-disarms-itself* defect. If the
   category cannot be written so that an unlisted colour still fails, **stop and report** rather
   than relaxing the test.

Adding **only** `--hero-ground` is deliberate. §16.5's full navy/gold/ivory set is a larger change
than this slice needs, and `FR-201`'s cross-family prohibition plus the dark-rail composition
question make a wholesale palette import its own slice. **This slice takes the one token its own
markup consumes**, and names the rest as untaken.

### B. `FR-218`'s bilingual alternative text, attached

Added to `shell_copy.py` beside the existing chrome labels, carrying the same import-time parity
discipline. English is the handoff's supplied string, "Khepri monument at sunrise."; the Arabic is
its translation.

**This cannot ship without A, and A cannot ship without this.** Alt text with no `<img>` is the
recorded *defined-but-never-attached* defect — governed prose in both languages reaching no code
path, with nothing failing. An `<img>` with no governed alt text fails `FR-218`. They are one
slice.

The artwork is decorative and carries no governed meaning (`FR-218`): it states no figure, no
population, no refusal, no caveat, no state. A reader with the image absent still gets a correct,
legible, complete surface — which is the `FR-218` clause the RED tests must actually exercise.

### C. Bounded polish against the pack, on referenced surfaces only

§17's acceptance rule — hierarchy, density, spacing rhythm, typography, visual states, RTL,
responsive behaviour, asset fidelity — applied to shell surfaces that **have an independent
reference**. Corrections are targeted; a divergence from the pack that an active specification
requires is resolved for the specification (`FR-205`, §A.3), and recorded rather than silently
reconciled.

---

## What this slice deliberately does not do, and why

- **Narrow and mobile polish (#11).** §16.4: not yet independently referenced; the family board
  "does not count as a screen reference". §16.3 forbids substituting a coding agent's own visual
  interpretation. Slice 8 (`#485`) already hardened responsive posture as *behaviour*; this slice
  adds no narrow **visual** judgement. **Open question for the owner below.**
- **The four trust states on #7 executive decision.** §16.4 records #7 as composition-only. The
  states themselves are governed by `RCA-008` and shipped under slice 5 (`#484`); they are not
  re-judged visually here.
- **The `RRA` report and evidence surfaces.** `RRA-015`'s, not this document's.
- **Any shared token layer across families** (`FR-201`) — still "needs its own artifact naming both
  families' paths".
- **The hero on the second `/app` surface — deferred, and NOT because it belongs to another
  family.** `RCA-012`'s own opening says the handoff "places supplied hero artwork on the **two
  `/app` workspace surfaces** the next slice builds — its screens **01 Home and 05 Insights**".
  `SHELL_PREFIX` is `/app`, so **both are shell surfaces under this same `RCA-010`/`RCA-012`
  authority**, and §16.4 lists #5 analysis detail as independently covered, so pack coverage does
  not exclude it either.

  It is held out **to bound this slice**, not because it is someone else's. Verified mapping at
  `d534bea`: `_WORKSPACE_SURFACES` and the render calls give **`overview.html.j2` = 01 Home** and
  **`analysis.html.j2` = 05 Insights** (`shell_api.py:533` and `:660`; `analyses.html.j2:575` is
  the list, not the detail). ~~The follow-on slice takes `analysis.html.j2` with the handoff's own
  row for it — 210px band, `object-position: 64% 46%`, ivory wash to transparent at 76%, actions
  top-trailing.~~ **Superseded by the record below**, which is what shipped; struck rather than
  deleted so a reader arriving from an older note sees what changed. **See the second open
  question.**

  **Discharged by the follow-on slice** (`feat/u1-analysis-hero-placement`). It took the 210px band
  and the `64% 46%` focal point, and mirrored that focal point to `36% 46%` by the handoff's rule,
  since the handoff states a mirrored value for Home only. It kept this slice's composition: the
  heading, lede and decision link stay in the document card, so no scrim ships and the actions are
  not moved top-trailing into the band.

- **The hero on the journey and report surfaces.** Upload, Review, Processing and the report cover
  *are* `RRA-010`'s and `RRA-015`'s. `FR-217` moves the *asset* into the shell's ownership without
  letting the shell reach into the journey's, so a journey hero needs its own RRA-family artifact.
- **Regenerate or add a derivative.** `#514`'s bytes are audited and merged; no 2x exists because
  no 2x master was supplied.

---

## RED tests first

Written to fail against `d534bea`, and each one must be shown failing before implementation.

1. **`overview.html.j2` places the artwork** — the rendered surface carries a `<picture>` naming
   both `/app/assets/khepri-hero.webp` and `/app/assets/khepri-hero.jpg`, derived from
   `SHELL_ASSETS` and the `hero.py` constants rather than typed as literals, so moving either fails
   here instead of in a browser.
2. **The alt text is governed and bilingual** — present in `SHELL_COPY["en"]` and `SHELL_COPY["ar"]`,
   reaching the rendered surface in both languages, and **not** hardcoded in the template. Assert
   the template contains no literal alt string.
3. **The surface is complete with the artwork absent** (`FR-218`) — render with the image
   unreachable and assert the headline, the navigation and the region's accessible name all survive.
4. **The ground colour sits behind the image, and no scrim ships** — the band carries
   `--hero-ground` as the pre-decode and failed-load fallback, and no `hero-band__scrim` rule
   exists while no copy sits over the artwork; assert the declarations, not the screenshot.
5. **RTL mirrors the `object-position`, never the artwork** — `38% 46%` under
   `[dir="rtl"]`, and no `transform: scaleX(-1)` or equivalent anywhere on the hero.
6. **Logical properties only** (`FR-199`) — the hero rules introduce no physical directional
   property.
7. **No new asset and no external host** (`FR-206`) — the hero rules' only `url()`s are the two
   shell addresses; no CSS-drawn shape stands in for artwork; CSP unweakened.
8. **`--hero-ground` is `#F6EDDF`, and an unlisted colour still fails** — assert the token's value
   against §16.5's row, and assert the widened palette guard still rejects a colour that is neither
   shipped, derived, nor §16.5-supplied. The second half is the positive control: without it the
   category could be a blanket allowance and nothing would notice.
9. **A real browser, from a real origin, loads the placed hero** — extend
   `test_rca012_shell_hero_load.py`: navigate to the Overview surface and assert the browser issued
   `GET /app/assets/khepri-hero.{webp,jpg}` and received 200, with the image decoding at 1400x900.
   This is the assertion the in-process tests structurally cannot make, and CI now runs it —
   `FND-005` is implemented, so a `browser`-marked test that skips **fails the job**.

10. **The heading and landmark structure is unchanged** (`FR-200`) — `overview.html.j2` today has
    exactly one `h1` (`id="page-title"`, inside `<section aria-labelledby="page-title">`). A hero
    band placed above it must not add a second `h1`, skip a level, or leave the section's
    accessible name dangling. Slice 9b (`#486`) already asserts these floors; **run that module and
    keep it green** rather than writing a parallel assertion.

### The tripwire that must be updated, not deleted

`tests/test_rca012_shell_hero_artwork.py::test_the_artwork_reaches_no_template` **will fail the
moment A lands. That is by design.**

It must become an **extent assertion** — "the artwork is placed on exactly these surfaces" —
enumerated and compared for equality, so a later slice placing the hero on a second surface fails
here rather than passing unnoticed. **Deleting it, or relaxing it to a subset check, discards the
guard**; `#514` widened the `_ASSETS` key set to an exact seven rather than relaxing it to `>=`,
and this is the same discipline. Record the change in the PR body as a deliberately updated test.

---

## Execution discipline

- Tests run with `./.venv/Scripts/python.exe`. Do not run `ruff format`; `ruff check .` is the gate.
- **Run the full suite before believing a targeted one.**
- CodeScene pre-flight with `git fetch` first — a stale `origin/main` makes the change-set analysis
  return an empty, meaningless pass. It scores test modules too, and gates on cyclomatic >9, module
  mean >4, arguments >4, and cohesion. Every new file must score 10.00.
- On any test or CI failure, invoke `superpowers:systematic-debugging` **before** proposing a fix.
- Assert against the deployed template and route table, never a hand-wired fixture (`W1-07a`).
- Never `git add -A`; stage only the named files.
- §F contracts: slice 7 is an obligation inside whichever slice touches a surface, not a deferral.
  **This slice changes Overview, so it asserts Overview's §F contract as part of its own evidence**,
  or records that the contract is already met.

---

## Open question for the owner — answer before implementation

**May slice 11 proceed with #11 (narrow and mobile) unreferenced?**

§16.4 records it as not independently referenced, and §16.3 forbids substituting a coding agent's
own visual interpretation. Three readings, and this plan takes none of them:

- **(a) Proceed, bounded.** Polish only referenced surfaces; narrow/mobile visual judgement is held
  out and named in the PR. Slice 11 then closes for the referenced set and #11 stays open.
  *This is what the plan above is written for.*
- **(b) Hold slice 11** until a #11 reference is supplied, and land only A+B (hero placement and
  alt text) as a `RCA-012`-completing slice, deferring all §17 polish.
- **(c) Supply the #11 reference** first, then run slice 11 whole.

**Automation does not choose this**, because each reading changes what ships. Under (a) and (b) the
hero lands; under (c) nothing lands until an asset arrives.

**Second question: one `/app` hero surface, or two?**

`RCA-012` names **both** 01 Home (`overview.html.j2`) and 05 Insights (`analysis.html.j2`), and both
sit under this slice's authority with pack coverage for each. The plan above takes **one**
(Overview) to keep the change bounded and to let the first placement prove the pattern — the
RTL mirror, the pre-decode ground and the governed alt text — before it is repeated.

- **(i) One surface now** *(what this plan is written for)*, Insights as an immediate follow-on
  slice reusing the proven pattern.
- **(ii) Both in this slice** — one `<picture>` pattern, two placements, two sets of handoff values.
  Larger diff, one round of review, and `RCA-012`'s "two `/app` surfaces" sentence is fully
  discharged in one go.

**Recommendation: (i).** The two surfaces carry different band heights and crops, so
"repeat the pattern" is not a copy — and a placement defect found on the second surface after the
first is merged is cheaper than one found across both. But this is a scoping call that changes what
ships, so the owner takes it.

**Resolved as (i).** Overview shipped at `#515`, and analysis detail followed as its own slice.

## Acceptance

- `RCA-012` `FR-218` fully verified, closing the split `#514` opened.
- The approved hero reaches a customer surface at the shell's own audited address.
- No route, capability, asset, dependency, or governed word added.
- `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest` green; CodeScene no decline.
