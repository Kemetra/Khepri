# `RCA-011` — the shell serves its own typeface: the slice and its evidence

**Authority:** active `RCA-011` (`governance/registry.yaml`, merged at `#490` / `056ffc8`),
`FR-207`–`FR-211`. Its implementation precondition 1 — "this document is `active` in
`governance/registry.yaml`" — is met; this record is precondition 2.

**Base:** `056ffc8` (`#490`).

---

## What was open, and why this closes it

`#489`'s evidence record (`2026-09-18-shell-base-typeface-evidence.md`) applied `--font-body` to
`body` and recorded an honest limit rather than working around it:

> **Noto Sans Arabic does not actually load on the shell** […] Wiring the face is out of scope and
> stays open. It needs either font files in `shell_api.py`'s allowlist — and §Scope says "Not in
> scope: `src/khepri/runtime/shell_api.py`" — or an `@font-face` here pointing at a journey-served
> asset, which `FR-201` forbids in terms.

`RCA-011` is the authority that resolves exactly that fork, and it picks the first branch: the
*asset* moves into the shell's ownership. `FR-201` is unrelaxed — no shell stylesheet reaches for a
journey address — because the address the stylesheet now names is the shell's own.

The second branch stays refused, and the third (mounting `add_journey_routes`) is untouched.

## The change

Three files.

**`src/khepri/runtime/shell_api.py`** — the allowlist only.

`_ASSETS` entries grew a third element, the media type, because a `.woff2` served as `text/css` is
not served. The route reads it from the entry instead of the `_STYLESHEET` constant. The two faces
are read from `khepri.rra.rendering`'s `typefaces/` rather than copied into the runtime package,
for the reason the existing docstring already gives for the stylesheets: a second copy is a second
thing to keep in step, and here it would additionally be a face `rendering/fonts.py`'s SHA-256
manifest does not verify.

No route added, no handler, no destination, no capability, no authorization path, no read.

**`src/khepri/rra/journey/assets/shell-components.css`** — presentation only, as `RCA-010` §Scope
already admits for this file. Two `@font-face` rules naming `/app/assets/…`, with the
`unicode-range` values `fonts.py` declares for these exact subsets. The now-false comment block
explaining that the face is unavailable was replaced rather than left to mislead.

**`tests/test_rca011_shell_typeface.py`** — new, 30 cases.

`shell.css` is deliberately untouched: `test_r801_shell_tokens.py` asserts it declares no rules,
and an `@font-face` is a rule. `FR-210` wants `--font-body` unchanged in any case.

## Requirements

| | Evidence |
|---|---|
| `FR-207` | The two faces serve 200 from `/app/assets/` with `font/woff2`, and the **bytes match the audited digests** — a status check alone would pass a route reading the wrong directory. `OFL.txt`, which sits beside them, is refused: served by being named, not by arriving. |
| `FR-208` | A comment-stripped scan of all three shell stylesheets finds no `/beta/` address, with an emptiness assertion and a positive control (`journey.css`, which genuinely carries them). The `@font-face` URL is derived from `SHELL_ASSETS`, so moving `SHELL_PREFIX` fails here rather than leaving the stylesheet pointing at nothing. |
| `FR-209` | No `@import`, no `http(s)://`, no protocol-relative `url()`. The `url()` check is an **extent** assertion — exactly two, both the shell's own — not a subset one. Each declared `unicode-range` is compared against `fonts.py`'s constant, and the two digests are asserted unchanged. |
| `FR-210` | `--font-body` keeps its full four-family declaration; `body` still consumes the *token* rather than naming the family directly (which would load the same face and silently discard three fallbacks); `font-display: swap` on both rules keeps the fallback load-bearing at first paint. |
| `FR-211` | The face serves with no session, sets no cookie, and answers byte-identically to a caller carrying a forged session cookie. The stub resolver records **zero calls**. The shipped CSP still reads `default-src 'none'` with `font-src 'self'` — unweakened, and already permitting exactly this same-origin load. |

## Two things this evidence deliberately does *not* claim

**The `set_content` browser matrix is regression evidence, not font-load evidence.**
`test_r810`/`r811`/`r812` build pages with `page.set_content` + `page.add_style_tag` — there is no
HTTP origin in those tests, so a relative `url()` in an `@font-face` resolves against nothing and
the face is never fetched. Those suites measure the *fallback's* metrics however often they are
re-run. They were re-run in full and are unchanged at **354 passed / 20 skipped / 1 xfailed**,
identical to the `056ffc8` baseline: that proves this slice regressed nothing, which is a different
claim from "the shipped browser loads the face".

`r812`'s typeface case docstring asserted two things that this slice makes false — that the face
loads from `/beta/assets/` and that the shell does not serve it — and has been corrected in place
rather than left to mislead. Its assertion is unchanged: it reads the **declared** chain, which is
`#489`'s finding and is stable across hosts.

**That gap is now closed by `tests/test_rca011_shell_font_load.py`**, which runs the real
application under `uvicorn` on a loopback port and points the pinned Chromium at it. See the next
section.

**A legal-only deployment serves no `/app/assets/`.** `add_shell_routes` returns early when
`services is None`, so an image mounting the legal surface without the shell has no asset route and
its pages fall through to `--font-body`'s remaining families. That is `FR-210` working as written
rather than a defect, and it is recorded here so it is not discovered later as a surprise.

**The wheel assertion is an inclusion-rule assertion.** `W1-07a`'s defect — a route absent from the
image passing every hand-wired fixture — is answered as far as CI allows: Docker is unavailable
(`test_build_image.py` builds nothing and says so), and `hatchling` is not a dev dependency, so the
test reads `pyproject.toml` and proves the faces sit under a packaged root (`src/khepri`) and
outside the single declared exclusion (`src/khepri/local`). It is derived from the build config
rather than restating it, so a build that stopped packaging `src/khepri` fails here.

## The real-origin font-load proof

`tests/test_rca011_shell_font_load.py`, 22 cases: 18 in a real browser, 4 without one. The application is the
shipped one — real `add_shell_routes`, real templates, real allowlist, real security headers — with
stubs only for the resolver and the organization reader, so the route under test is the route that
ships. A hand-wired fixture serving the fonts itself would have proven nothing (`W1-07a`).

**The wire is the primary proof, not `document.fonts.check()`.** That call answers "does this
family resolve at all", which a **system-installed** Noto Sans Arabic satisfies on any host that
happens to have one — a false positive that would survive deleting this entire slice. What no
system font can fake is Chromium issuing `GET /app/assets/<face>.woff2` against *this* origin and
receiving a 200. Every response is recorded with `page.on("response")` and asserted against.

| Proved | How |
|---|---|
| **A** — the face is reachable through the real route | `GET {origin}/app/assets/NotoSansArabic-Regular-{arabic,latin}.woff2` → **200**, `content-type: font/woff2`, `x-content-type-options: nosniff`. Bytes are digest-checked in the companion module. |
| **B** — a real surface links the stylesheet | `/app/{en,ar}/org-acme/overview` renders **200** carrying `href="/app/assets/shell-components.css"`. Asserted *before* the browser runs, so no font assertion can pass vacuously on a page that linked nothing. |
| **C** — the browser resolves it, and reaches no journey address | Both subsets requested and **200** on the wire; **zero** requests matching `/beta/`; **no** font request with status ≥ 400. |
| **D** — the face is loaded, not merely declared | Two `FontFace` entries for the family (so the rules parsed), and after `document.fonts.load(...)` for text in *both* scripts every entry reports `status === "loaded"` with none `"error"`. A declared-but-unfetched face reports `unloaded`; a failed one reports `error`. Both would pass a `getComputedStyle` check. |

**A refusal is refused as a subject.** The unavailable surface links the same three stylesheets, so
the page is asserted to have landed **200** before anything is measured — otherwise the whole module
could pass while measuring a refusal.

**Real metrics were then measured, because a typeface moves them.** With the face confirmed
`loaded`, horizontal overflow is **0px** on both languages at 1180×900, at 390×844, and at 200%
`body.style.zoom` — six configurations, the same mechanism `#487`'s overflow fix was measured
against. No RTL, mobile, or zoom regression from the real face.

**What this does not claim.** Not pixel identity, not glyph rasterization, and not that the face is
the one Chromium finally painted with — `getComputedStyle(...).fontFamily` names the chain either
way, which is exactly why it is not the proof here. What is proven is that the file is requested
from the shell's own address, arrives with the right media type, parses into two `FontFace` entries,
reports `loaded`, and costs no layout.

## Validation

`uv run ruff check .`, `uv run ruff format --check`, `uv run khepri-gov validate`, and the shell
surface suites `r801`, `r802`, `r807`, `r808`, `r809`, `r810`, `r811`, `r812` plus the new module.

**Full suite**: `5993 passed, 97 skipped, 2 xfailed, 0 failed` before this module was added —
the 10 `test_m2_persistent_frame.py` failures the allowlist change caused, and nothing else, having
been converted by the guard fix below.

**The re-run including the real-origin module was IN FLIGHT when this PR opened.** An earlier
attempt reached 35%% with 0 failures and was killed by the host for memory pressure — an environment
event, not a test failure. The re-run was at 40%% with 0 failures at the moment of commit. The
whole-suite counts line is therefore the one gate not recorded here; every focused gate, the browser
matrix, CodeScene, ruff and governance all passed. A reviewer should confirm CI green before merge.

**CodeScene**: the new files score **10.00** with no
findings, as §Verification requires. `analyze_change_set` against `origin/main` initially returned
`quality_gates: failed` on `shell_api.py` — not for complexity, which is unchanged at 10, but
because `add_shell_routes` was *already* above the threshold and grew from 87 to 91 lines, and a
docstring inside a function body counts. The rationale moved to a module-level comment beside
`_ASSETS`, where it belongs; the function no longer grows and the gate **passes**. Restructuring
the route instead would have exceeded §Scope, which authorizes the allowlist only.

**Seven mutants, all killed** — a guard is only evidence once it has been seen to fail:

| Mutant | Dies |
|---|---|
| Font served as `text/css` | 2 |
| Latin face dropped from the allowlist | 5 |
| Stylesheet points back at `/beta/assets/` | 3 |
| `unicode-range` widened to `U+0000-FFFF` | 1 |
| `font-display: swap` removed | 1 |
| `--font-body` collapsed to the face alone | 1 |
| Allowlist replaced by a directory listing | 1 |

**Four more against the real-origin proof**, because a browser test that cannot fail is worth less
than no test at all:

| Mutant | Dies |
|---|---|
| Arabic face dropped from the allowlist (404 on the wire) | 8 |
| Stylesheet repointed at `/beta/assets/` | 6 |
| Font served as `text/css` (refused by `nosniff`) | 2 |
| A 4000px element planted in the component layer | 6 |

The second is the one `document.fonts.check()` alone could never catch, and the fourth proves the
overflow measurement is not vacuous. **15 mutants planted, 15 killed.**

## One existing guard was adjusted, and why that is maintenance rather than a change

`tests/test_m2_persistent_frame.py::test_no_shell_owned_asset_reaches_the_journey` (`RRA-010`
Verification) failed on ten cases the moment the faces entered `_ASSETS`. **It was not a defect in
the guard and not a boundary breach.** The guard deliberately derives "shell-owned asset" from
`shell_api._ASSETS` rather than a hardcoded list — its docstring says a future entry is "covered the
moment it is served, with no edit here" — and matches by **bare filename**. The journey has always
served files of the *same name* from its own `/beta/assets/`, so the shared name read as a leak.

Both surfaces now serving the same bytes from their own addresses is the intended end state of
`FR-207`/`FR-208`, not a defect in either.

**The fix keeps every existing assertion and narrows nothing that was covered.** The bare-name rule
is what closed the guard's original hole — a journey template linking `/beta/assets/shell.css`, the
journey's own address for a file that is the shell's — so switching the whole loop to address
matching would have re-opened it in the same edit. Instead the match rule is chosen **per entry, by
the entry's own media type**: stylesheets keep bare-name matching unchanged; a typeface is matched
by the shell's address. Splitting on `media_type` rather than on a list of filenames keeps the guard
from naming its own scope.

**Four mutants prove it was narrowed and not disarmed**, all planted in `journey.css` and all
failing the guard: `shell.css` (10 cases), `workspace.css` (10), `shell-components.css` (10), and —
the one that proves the font half can still fire — the shell's own
`/app/assets/NotoSansArabic-Regular-arabic.woff2` address (10). `journey.css` itself is untouched;
`RCA-011` §Scope excludes it by name.

## Out of scope, and left open

- **`workspace.css`'s undeclared `--font-sans`/`--font-mono`** — seven `var()` calls whose fallback
  always wins, recorded in `#489`. `RCA-011` names it a token-declaration question, not an asset
  one, and does not decide it.
- **The `RRA-010` journey-adoption reading** — the owner's, filed and untaken. Two font files
  moving into the shell's ownership is not a precedent for the journey's components or surfaces.
- **Mounting `add_journey_routes`** — it is not mounted, and this slice does not change that.
