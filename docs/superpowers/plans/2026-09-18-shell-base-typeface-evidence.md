# `shell-components.css` — the base typeface, and the token it exposed: the fix and its evidence

**Authority:** active `RCA-010` `FR-204` (typography is a named comparison dimension) and `FR-200`
(text scales to 200% without loss of function). `src/khepri/rra/journey/assets/shell-components.css`
is named in `RCA-010` §Scope (`:120`).

**Why its own slice.** `#488` (slice 10b) found the defect and, per the family's allocation rule,
**did not fix it**: an evidence slice that edits a stylesheet to make its own assertion pass "has
left its scope, and the failure it hid is still in the product". This is that follow-on slice,
named for the file that fails — the same shape as `#487`.

**Base:** `046883c` (`#488`).

---

## The defect

`shell.css:158` declares the shell's typeface token:

```css
--font-body: "Noto Sans Arabic", "Segoe UI", Tahoma, sans-serif;
```

**Nothing consumed it.** Measured on `overview`, `getComputedStyle(document.body).fontFamily`
returned `"Times New Roman"` — the browser's default serif. Every shell surface and every legal
page rendered in a face the design never chose.

## The fix, and the honest limit on it

```css
body { font-family: var(--font-body); }
```

**Noto Sans Arabic does not actually load on the shell**, and that is recorded rather than worked
around. Its `@font-face` rules live in `journey.css` and read from `/beta/assets/…woff2`; the shell
links three stylesheets and serves three (`shell_api.py`'s `_ASSETS` allowlist), none of them a
font file and none of them `journey.css`.

So the cascade **falls through to `"Segoe UI", Tahoma, sans-serif`** — the token's own fallback
chain, working as written. That is the difference between a font that is named-but-unavailable and
a declaration that is broken: CSS skips an unavailable family and uses the next one. The shell now
renders in its intended *class* of typeface, and the day the face reaches the shell this same rule
picks it up with no further change.

**Wiring the face is out of scope and stays open.** It needs either font files in
`shell_api.py`'s allowlist — and §Scope says "Not in scope: `src/khepri/runtime/shell_api.py` and
every other `src/khepri/runtime/*.py` module" — or an `@font-face` here pointing at a
journey-served asset, which `FR-201` forbids in terms. Plausibly the same asset-wiring question as
the owner's filed, untaken `RRA-010` journey-adoption reading.

---

## What the correct typeface then exposed

**A latent `FR-200` defect, invisible while the shell rendered in a serif.**

Real sans metrics are wider. The `h1` string "Choose an organization" measured 322px in Times New
Roman and **355px** with the token applied — about 10%. At 200% text on a 390px viewport that tipped
one surface over:

| | `team/en` | `team/ar` |
|---|---|---|
| before the typeface fix | fits | fits |
| after it | **over by 21px** | **over by 21px** |

The overflowing element is `span.member-identity` — a member's email address:

```
member-identity width: 304px (serif, fits a 308px box)  ->  338px (sans, overflows)
```

**`#487`'s `overflow-wrap: break-word` cannot help it.** `break-word` breaks *between* opportunities;
an email address is a single token with no space to break at. `anywhere` is required precisely
because there is no break opportunity to find. Measured:

| Candidate | result across all 20 surface/language pairs at 200%/390px |
|---|---|
| typeface fix alone | `team/en +21`, `team/ar +21` |
| **+ `overflow-wrap: anywhere` on `.member-identity`** | **ALL FIT** |

Scoped to that one element, so no prose elsewhere breaks mid-word. `.invitation-token code` already
uses `anywhere` in this sheet for the same reason — a hand-copied token that overflows cannot be
copied — so this is the established idiom here, not a new one.

**This is not a regression introduced by the typeface fix.** The defect was always in the markup;
the serif fallback was narrow enough to hide it. Shipping the typeface without this would have
moved a passing surface to failing.

---

## Verification

### The regression test, red then green

`test_the_body_typeface_is_the_shell_token_not_a_browser_default` asserts the **declared** family
list rather than the resolved face, so it is stable across platforms — the resolved face depends on
what is installed, the declaration does not.

| | Result |
|---|---|
| with `body { font-family }` removed | **3 failed** — all three representatives |
| with the rule present | **16 passed** |

### Every guard whose measurements this changes

Font metrics move every browser-measured assertion on every shell surface *and* every legal page.
All were re-run, not just the typography one:

| Suite | Result |
|---|---|
| `test_r811_shell_accessibility.py` + `test_r812_shell_visual_regression.py` | **269 passed, 20 skipped** |
| `test_r807` + `test_r810` + `test_r801` + `test_r808` | **156 passed, 1 xfailed** |

That covers `#487`'s 200% overflow guard, 9b's computed contrast and 44px pointer targets, slice
8's overflow and RTL assertions, 10b's measured dimensions, slice 2b's no-raw-type-size scan, and
`shell.css` remaining tokens-only.

### Gates

| Gate | Result |
|---|---|
| `ruff check .` · `khepri-gov validate` | passed |
| CodeScene vs `origin/main` | `quality_gates: passed` |
| `pytest` (whole suite) | see PR — run alone with an isolated `--basetemp` |

---

## What this slice did not do

- **It did not wire the Noto face to the shell.** That needs `shell_api.py` (outside §Scope) or an
  `@font-face` naming a journey-served asset (`FR-201`). Recorded as open.
- **It did not declare `--font-sans` or `--font-mono`.** `workspace.css` references both in seven
  places and **neither is declared anywhere the shell reaches** — only `landing.css` declares
  `--font-mono`, for itself. The fallback always wins, so those `var()` calls are decoration today.
  Recorded, not chased: `workspace.css` is a different file with its own history, and changing what
  a token resolves to is a larger question than this slice's subject.
- **It did not touch `#486`'s Findings 1 or 2** — the CI browser gap and the unreachable
  announcement clause, both still open and both the owner's.
