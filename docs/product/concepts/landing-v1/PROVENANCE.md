# Asset provenance — landing page concept

Three binaries ship beside `index.html`. None was produced, generated, subset, re-encoded, or
fetched from a network source. All three are **byte-for-byte copies** of the typefaces the product
already ships as package data.

## Source

`src/khepri/rra/rendering/typefaces/` — shipped as package data and verified at runtime against a
SHA-256 manifest by `src/khepri/rra/rendering/fonts.py`.

## Verified digests

Computed with `sha256sum` over both the source and the copy; every pair matches.

| File | SHA-256 | Matches source |
|---|---|---|
| `NotoSansArabic-Regular-arabic.woff2` | `4e2ca0745c908761dc5c5db951662873887c59366fa1a5693ad22c0864abf1bd` | yes |
| `NotoSansArabic-Regular-latin.woff2` | `290bdad021425e6ba6263c27d38652403f9b1a9ee74f5bbd2c62905b13f71b8c` | yes |
| `OFL.txt` | `01dfc2cdf10c808ca391fccf49d364e562408d77c4e0dc278ed4d384c817a032` | yes |

## Why the files are copied rather than referenced

The shipped `@font-face` rules in `journey.css` address these files at `/beta/assets/…`, an absolute
path served by the running application. A standalone concept file opened from disk resolves that
path to nothing, and the face falls back silently to Segoe UI or Tahoma — on the page whose thesis is
Arabic/English parity, which is the worst possible place for a silent substitution. The copies are
addressed relatively so the concept renders in the product's real typeface with no font host, no
`@import`, and no network fetch, preserving the posture the shipped `default-src 'none'` CSP
enforces even though the CSP does not bind a docs file.

## Licence

`OFL.txt` is the SIL Open Font License that governs Noto Sans Arabic, copied unchanged alongside the
faces it covers, as the licence requires.

## Known gap — inherited, not introduced

**Only the Regular (400) weight exists.** `landing.css` declares `font-weight: 400` on both
`@font-face` rules so this is explicit; the shipped `journey.css` omits that descriptor, which is
what makes the gap easy to miss there.

Every declaration in the concept at 600 or 650 therefore renders as browser-**synthesized** bold
rather than a drawn semibold, in both scripts. Faux bold is a poor result in Latin and a worse one in
Arabic, where the synthesis thickens the joins between letterforms.

This is not a defect of the concept. `journey.css` ships exactly these two Regular files and sets
`font-weight: 650` on its own `h1`, so the shipped product carries the identical gap; the concept
copied the world faithfully. Closing it is an **asset** change: a SemiBold face, or the variable face
at a `400 700` range, must first pass the licence-plus-audited-digest process recorded at
`docs/superpowers/specs/2026-08-13-client-journey-ui-design.md:214-217`. That process is exactly what
governs adding a face, and nothing in a design concept may substitute for it.

**On the replacement list.** Until it is done, the weights in the stylesheet are requests the family
cannot honour.
