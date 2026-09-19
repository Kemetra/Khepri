# `U1` RRA slice 10a — Visual regression, report and evidence surfaces (`U1-07`, RRA half)

> **Execution plan.** Opened from
> `docs/superpowers/plans/2026-09-17-u1-rra-surfaces-allocation-plan.md` §"Slice 10a", the last
> slice in that plan's `6 → 2 → 3 → 9a → 10a` sequence. Its four dependencies are merged:
> slice 6 at `#481`, slice 2 at `#495`, slice 3 at `#496`, slice 9a at `#497`/`#498`.
>
> Sub-skills, in order: `superpowers:test-driven-development`, then
> `superpowers:executing-plans`. On any failure, `superpowers:systematic-debugging` before
> proposing a fix.

**Authority:** active `RRA-015` `FR-190`–`FR-191`.
**Design:** `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md` §17, §16.3, §16.4.
**Files:** `tests/` only. This slice changes no source file.

---

## What this slice measures, and why that is the whole of it

`FR-190` compares "a rendered report surface" against approved design evidence. That is a
per-surface acceptance rule, so this slice asserts against the references the pack actually
covers and is silent on the rest. Master specification §16.4 and the pack's own
`README.md` agree exactly — verified 2026-09-19, both say **4 of 12 independently covered**
(#6, #8, #9, #10), 2 partial (#4 RTL-only, #7 composition-only), 6 not referenced. There is
no count divergence to record here.

The remaining eight references are an **asset-production dependency**, not a code blocker
and not this slice's work.

---

## Tree-state findings — verified 2026-09-19 at `692134e`

Recorded so the RED steps below rest on measurement rather than on the twin's assumptions.

### 1. The report inlines its stylesheet; the shell does not. **No `add_style_tag`.**

`documents/en` carries exactly **one `<style>` element and zero `<link rel=stylesheet>`** —
the bundled report stylesheet, inline. This is why slice 9a's browser tests do a bare
`set_content` with no injection, and why they measure real geometry rather than Chromium
defaults.

**This is the single thing that would have voided the slice silently.** The shell twin
(`test_r812_shell_visual_regression.py`) must call `add_style_tag(_shell_css())` because the
shell serves its CSS as a separate asset. Copying that call here would inject the **shell's**
stylesheet into a report page — a cross-family token import `FR-201` forbids, and the exact
boundary slice 3 was scoped around. This module injects nothing.

### 2. All four covered references are reachable here — there is no null-case exemption.

Measured across both fixtures and both languages:

| Fixture | Surface | Renders |
|---|---|---|
| `published=True` | `documents` | 3 `<svg>`, 3 `role="img"`, 8 tables, 1 `h1`, 7 `h2`, 1 `nav`, 1 `main` |
| `published=True` | `evidence` | 2 tables, 1 `h1`, 5 `h2`, 0 `nav`, 1 `main`, 92KB |
| `published=False` | `documents` | **12 refusal panels**, 3 tables, 0 `<svg>` |
| `published=False` | `evidence` | 2 tables, no refusal |

Arabic matches English on every structural count; only byte length differs (~600B, translated
text).

**This differs materially from slice 10b.** The shell renders no refusal at all, so 10b had to
record §16.4 #9 as *unreachable* and pin it two-sided. Here #9 is genuinely reachable, so 10a
owes it a real measurement instead of an exemption.

### 3. Two fixtures are required, and one would leave a covered reference unexercised.

A chart needs `published=True`; a refusal panel needs `published=False`. They are mutually
exclusive by construction — `V-concentration` closes the refusal window when the triple
publishes. Slice 9a found this first and built `_refusal_bearing_surfaces()` for it.

A 10a measuring only the published fixture would **never exercise #9** while reporting green:
"a run that can only produce the null case is not a pass."

### 4. The report's spacing rhythm is `--report-space`, not the shell's 4px scale.

`report.css:28` declares `--report-space: 1rem` and uses it 17 times as `1x`, `1.5x` and `2x`
(`:51`, `:157`, `:166`, …). That is a **16px rhythm with an 8px half-step**.

The shell twin asserts `pixels % 4 == 0` against `shell.css`'s token scale. **That assertion
must not be copied.** `FR-201` and the allocation plan's tree-state finding #1 keep the two
families' scales separate. This module derives its rhythm from `report.css`'s own token, which
is the independent source the report surface actually has.

### 5. `evidence` is the densest surface and discriminates on different elements.

`evidence` is 92KB against `documents`' 28KB, renders zero charts and zero `nav`. Its density
probe must therefore read the elements it actually has (tables, rows, links) rather than the
`.document-card`/`.chart` selectors that carry the report surface.

---

## Reference mapping — stated, not silently repeated

Slice 10b already claimed #6 and #8 for **shell** surfaces (`compare`, `decision`). This slice
claims them for **RRA** surfaces. That is not a collision: a §16.2 reference is a design
requirement, and two families may each realize it on their own surface. Recorded explicitly so
a later reader does not read the repeated numbers as a copy-paste error.

| §16.4 reference | RRA subject | Basis |
|---|---|---|
| #6 period comparison | `documents`, published | 3 charts render; the comparison figures are its subject |
| #8 evidence drawer | `evidence`, both fixtures | the drawer surface itself, the product's densest |
| #9 refusal | `documents`, unpublished | 12 refusal panels render |
| #10 Arabic RTL | both surfaces, `ar` | `dir="rtl"`, structurally identical to `en` |

---

## RED steps

Each step is RED before GREEN. Because this slice changes no source file, "GREEN" means the
assertion passes against the tree as it stands, or — where it does not — the failure is
**recorded as a strict xfail** naming the file that owes the fix.

**Recorded defects use `pytest.mark.xfail(strict=True)`, never `pytest.skip`.** Since `FND-005`
(`#493`) CI installs the pinned Chromium and `.github/scripts/require_browser_tests.py` fails
the job if **any** `browser`-marked test skips, or if the marker matches nothing. A skip is now
fatal. An xfail reports as `xfailed` and passes the guard; an unexpected pass under `strict`
reports as `failed`, which is what caught slice 9a's host-dependent false defect.
Per-`(surface, language)` via `request.node.add_marker`, never function-level: 9a recorded that
a function-level xfail stopped at the first surface and the module "claimed evidence it had not
produced."

- [ ] **R1 — `FR-191` emptiness scan.** No test module reads a figure, route, capability,
      refusal reason or governed word out of a reference image. Anchored to `__file__`, with a
      non-empty assertion on the scanned set so it cannot pass vacuously, and **proved to fire
      from two working directories**.
- [ ] **R2 — the pack is present.** The scan guards nothing if the pack has moved or emptied.
- [ ] **R3 — the reference mapping names only reachable subjects.** Every entry in the mapping
      table resolves to a surface that renders its subject on the stated fixture. An entry
      naming nothing is a null case and fails.
- [ ] **R4 — determinism.** The measured dimensions agree across two runs, per surface and
      fixture (`FR-190` §Verification). This is what makes measurement usable as evidence.
- [ ] **R5 — no visual-testing platform.** No hosted baseline store, no service, no stored
      baseline image; the shipped Playwright/Chromium only.
- [ ] **R6 — spacing rhythm from `--report-space`.** Measured boxes sit on the report's own
      16px rhythm with its 8px half-step, derived from `report.css`'s token.
- [ ] **R7 — RTL mirrors rather than reflows.** `dir` pairs with the language, and hierarchy
      and density are language-invariant — a divergence is real drift, not a translation
      artifact.
- [ ] **R8 — #9 refusal is measured, not exempted.** The unpublished fixture's refusal panels
      are present and composed on both surfaces' languages.

## Verification

- `./.venv/Scripts/python.exe -m pytest tests/test_rra015_report_visual_regression.py -q`
- The **full** suite before believing the targeted one — changing a field's meaning breaks
  suites never opened.
- `uv run khepri-gov validate` and `uv run ruff check .` before every commit. Do not run
  `ruff format`; there is no CI format gate.
- CodeScene pre-flight with `git fetch` first — a stale `origin/main` makes `analyze_change_set`
  return empty results and a meaningless pass. It scores test modules too.

## Out of scope

- Any source file. Where a floor or dimension fails, the fix belongs to the slice owning that
  file.
- The six uncovered §16.2 references — an asset dependency (§16.4).
- Slice 11 final polish, gated on §16 by §19.
- §F contracts: the allocation plan assigns slice 7's obligation to slices 6, 2 and 3, not here.
- Any shared token layer across journey, report and shell surfaces (`FR-201`).
- The PDF renderer, excluded from `RRA-015` §Scope at `RRA-015:140`.

## Handoff

After this slice **both `U1` allocation plans are exhausted.** Slice 1 (`#369` absorption) and
slice 11 (final polish) are owner- and asset-blocked respectively, so the next track is a
scheduling decision rather than a queue read. `OPS1-02` (hosted provisioning) is the only
executable candidate. The merge to `main` is the owner's.
