# `U1` RRA slice 10a — Evidence

Companion to `2026-09-19-u1-rra-slice-10a-execution-plan.md`. Records what was measured, what
each guard proves, and the two defects this slice's own mutation testing found in its tests.

**Authority:** active `RRA-015` `FR-190`–`FR-191`. **Files changed:** `tests/` only — no source
file, as the allocation plan requires of an evidence slice.

---

## What shipped

`tests/test_rra015_report_visual_regression.py`, 13 tests: 6 static, 7 marked `browser`.

| Guard | `FR` | Proves |
|---|---|---|
| no test reads a value out of a reference image | `FR-191` | no module opens, reads, decodes or digests a pack file |
| the scan is anchored to the module, not the CWD | `FR-191` | the scan's file set is identical from two working directories |
| the reference pack is present | `FR-191` | the scan is not guarding an empty directory |
| no baseline image or visual-testing platform | `FR-190` | no stored baseline, no hosted store, no snapshot platform |
| every named reference resolves to a rendered subject | `FR-190` | no reference is measured over nothing |
| the refusal reference is measured, not exempted | `FR-190` | §16.4 #9 has a real subject here, two-fixture split holds |
| dimensions are deterministic across two runs | `FR-190` §Verification | the measurement is usable as evidence at all |
| spacing rhythm comes from the report token scale | `FR-190` | `body`/`section` sit on `--report-space`'s 16px rhythm |
| RTL mirrors rather than reflows | `FR-190` | hierarchy and density are language-invariant |
| refusal composition is language-invariant | `FR-190`, §16.4 #9 | the refusal surface mirrors rather than reflows |

---

## Measured tree state — 2026-09-19 at `692134e`

### The report inlines its stylesheet

`documents/en` carries **one `<style>` element, zero `<link rel=stylesheet>`**. `set_content`
alone therefore produces a fully styled page and this module injects nothing.

This is the finding that would have voided the slice silently. The shell twin
(`test_r812_shell_visual_regression.py`) calls `add_style_tag(_shell_css())` because the shell
serves its CSS separately; copying that call here would have injected the **shell's** stylesheet
into a report page — the cross-family token import `FR-201` forbids, and the boundary slice 3
was scoped around.

### Surface composition, both fixtures, both languages

| Fixture | Surface | Measured |
|---|---|---|
| `published=True` | `documents` | 3 `<svg>`, 3 `role="img"`, 8 tables, 1 `h1`, 7 `h2`, 1 `nav`, 1 `main` |
| `published=True` | `evidence` | 2 tables, 1 `h1`, 5 `h2`, 0 `nav`, 1 `main`, 92KB |
| `published=False` | `documents` | **12 refusal panels**, 3 tables, **0 `<svg>`** |
| `published=False` | `evidence` | 2 tables, no refusal |

Arabic matches English on every structural count; only byte length differs (~600B of
translated text).

### Spacing rhythm, measured in the browser

`body_padding_block: 32px`, `body_padding_inline: 16px`, `section_margin_block_end: 32px` on both
surfaces — exactly `--report-space: 1rem` at 2×, 1×, 2× (`report.css:51-52`, `:166`).

---

## Two defects found by mutation testing, both in this slice's own tests

Neither would have been caught by a green run. Recorded because each is a reusable trap.

### 1. The platform scan matched itself

The first draft compiled `re.compile(r"percy|applitools|…")`. The module scanning for those names
**contained** them, so it reported itself as an offender.

The tempting repair — excluding this module from its own scan — would have blinded the guard on
the one file most likely to introduce a snapshot platform. Instead the pattern is assembled from
fragments at runtime, so the source text never holds a whole name while the scan still matches
real usage anywhere, including here.

**Mutant M1:** appending a line containing a real platform call. The guard fires. Killed.

### 2. The spacing-rhythm guard was vacuous — `0 % n == 0`

The first probe read `main`'s padding. `main` carries none, so both values measured `0px`, and
**`0 % 8 == 0` and `0 % 7 == 0`** — the assertion passed against every possible rhythm.

**Mutant M2 survived the first time**, with `_RHYTHM_PX = 7`: 2 passed. That survival is what
exposed the defect; the module was green and proving nothing on that dimension.

Repaired by probing the elements `report.css` actually puts `--report-space` on (`body`,
`section`) **and** by refusing zero explicitly, so this dimension can never again pass on a
null measurement. Re-run of M2 then failed on both surfaces. Killed.

### Mutation ledger

| # | Mutant | Result |
|---|---|---|
| M1 | a real visual-testing platform name appears in a test module | **killed** |
| M2 | `_RHYTHM_PX = 7` | **survived → defect fixed → killed** |
| M3 | `_DIRECTION["en"] = "rtl"` | **killed**, both surfaces |
| M4 | `#6` mapped to `<canvas>`, which nothing renders | **killed** |
| M5 | `_test_sources()` made CWD-relative (`Path("tests")`) | **killed** |

Each mutant was restored by targeted diff and the module re-run green, per
`khepri-restore-a-mutant-by-diff-not-by-replace`. The restored file was diffed against a
pristine backup to confirm no mutation residue remained.

---

## Reference mapping — stated rather than silently repeated

Slice 10b claimed §16.4 #6 and #8 for **shell** surfaces (`compare`, `decision`). This slice
claims them for **RRA** surfaces. Not a collision: a §16.2 reference is a design requirement and
two families may each realize it on their own surface.

| §16.4 reference | RRA subject | Basis |
|---|---|---|
| #6 period comparison | `documents`, published | 3 charts render |
| #8 evidence drawer | `evidence`, published | the drawer surface itself |
| #9 refusal | `documents`, unpublished | 12 refusal panels render |
| #10 Arabic RTL | `documents`, `ar` only | `dir="rtl"`; language-specific by definition |

**#10 is scoped to Arabic deliberately.** The first draft checked every marker against both
languages, and the mapping guard correctly reported `#10 → documents/en` as missing its subject:
`dir="rtl"` must **not** render on the English document. The language tuple is now explicit per
reference.

**No reference is exempted here.** Slice 10b had to record #9 as unreachable because no shell
surface renders a refusal. All four covered references have real subjects on these surfaces, so
this slice owes and provides a measurement for each.

---

## Coverage — no divergence to report

Master specification §16.4 and the pack's own `docs/product/ui-visual-references/README.md`
agree exactly: **4 of 12 independently covered** (#6, #8, #9, #10), **2 partial** (#4 RTL-only,
#7 composition-only), **6 not independently referenced** (#1, #2, #3, #5, #11, #12). Checked
because a digest-pinned count divergence has bitten this repository before (`RRA-009`); there is
none here.

The six uncovered references are an **asset-production dependency**, not a code blocker and not
this slice's work (§16.4: the pack "is acceptance evidence for the surfaces it covers and is
silent on the rest").

---

## Skips: none, and why that matters now

All 7 `browser` tests **executed** locally — verified with `-m browser -rs`: `7 passed, 6
deselected`, no skips.

Since `FND-005` (`#493`) CI installs the pinned Chromium and
`.github/scripts/require_browser_tests.py` fails the job if any `browser`-marked test skips, or
if the marker matches nothing at all. A skip is now fatal rather than silently green. This module
therefore records no absence as a skip; `_launch_chromium`'s `pytest.skip` branch exists only for
a developer machine without the browser installed.

No `xfail` was needed: every dimension this slice measures passes against the tree as it stands.

## Verification run

- `pytest tests/test_rra015_report_visual_regression.py -q` → **13 passed**
- `pytest tests/test_rra015_report_visual_regression.py -m browser -q -rs` → **7 passed, 0 skipped**
- `uv run ruff check .` → **All checks passed**
- `uv run khepri-gov validate` → **Governance validation passed**
- Full suite → see the PR body.

## Handoff

With 10a merged, **both `U1` allocation plans are exhausted.** Slice 1 (`#369` absorption) is
blocked on the owner (§18.3, §A.5 item 1); slice 11 (final polish) is gated on §16 by §19 and is
an asset dependency. The next track is therefore a **scheduling decision**, not a queue read —
`OPS1-02` (hosted provisioning) is the only executable candidate. The merge to `main` is the
owner's.
