# U1 slice 12 — the shell converges on the approved Product UI composition

**Authority:** `RCA-010` §Scope (shell presentation markup and ARIA state, the three shell
stylesheets, `tests/`). `RCA-012` §Exclusions assigns the hero's placement rules to "a presentation
slice governed by `RCA-010`". No route, handler, read, copy key, asset, dependency or CSP change.

**Vehicle:** PR `#561`, on top of its presentation reset. One PR: this plan and its RED tests, then
the implementation.

## Why

The master specification §17 loop was run on `#561`: renders from a real loopback origin at the
handoff's verification widths (1440, 1024, 390) in both languages, an Impeccable critique (design
review and deterministic detector, run in isolation), then targeted corrections. Five findings are
presentation-only and inside this scope:

1. **The hero is "picture above a card".** The handoff (§6, §10; references 01 and 05) puts the
   page head on the band over an ivory wash that fades to transparent at 74–76%. Slice 11 deferred
   exactly this and pinned the deferral in `test_no_scrim_ships_while_no_copy_sits_over_the_artwork`
   so the slice making the change would have to say so. This is that slice.
2. **At 390 the image must be a 140px band above the copy** (handoff §13), not behind it.
3. **At 1024 the analysis side rail keeps two columns in a third of the width** and splits words
   in both languages. The handoff (§13) drops the rail below at tablet widths.
4. **At 1024 the overview leaves `Pinned` alone beside an empty cell.**
5. **At 1440 the frame touches the viewport's inline edges** while keeping its block margin; the
   handoff (§10) sets it on the sand ground with padding all round.

## Constraints the implementation must meet

- **The band grows with its copy.** `block-size` becomes `min-block-size` (handoff §13 "Hero
  min-heights"), or 200% text and Arabic's 1.8 line-height would clip (`RCA-010 FR-200`, `#487`).
- **Legibility is geometric.** The text column stays inside the wash's solid stop at 1440 and 1024
  in both directions. A contrast probe reading the nearest `background-color` would pass with the
  text over the photograph, so it cannot be the evidence.
- **The wash is a legibility overlay, not artwork** (`RCA-010 FR-206`): a gradient from
  `--hero-ground` to `transparent`, no `url()`, no colour of its own, on an `aria-hidden` element.
  `test_r807`'s `background-image` ban narrows to that one rule, with a positive control proving
  any other `background-image` still fails.
- **The title stays inside its labelled region**, so the band moves inside
  `section.workspace-page`. `test_r812`'s probe, which measured the first `.document-card`, is
  retargeted deliberately to the first card-like surface rather than drifting to another card.
- **Nothing is added that the product does not back:** no eyebrow, breadcrumb, motto, quote card,
  second action, search, bell or user chip. The artwork is cropped only and never mirrored.

## Deferred, not in this slice

Recorded in an issue: `aria-current` on detail pages (reads against `RCA-010 FR-194`'s "exactly
one"), the decision page's controls rendering above its `h1`, the Arabic alignment of a `dir="auto"`
passport value, and raw tokens in the decision rows.

## RED tests

`tests/test_u1_slice12_hero_convergence.py` (new), plus two guards whose premise this slice
changes: the slice-11 no-scrim assertion becomes "the scrim ships because copy sits over the
artwork", and `test_rca012_shell_hero_load.py` reads the band's `min-height`.
