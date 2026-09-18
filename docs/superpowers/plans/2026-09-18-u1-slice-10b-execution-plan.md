# `U1` slice 10b / `U1-07` — Visual regression, commercial shell surfaces: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`. Checkboxes in this repository are **never ticked after the fact** —
> read the newest dated status block, not the boxes.

**Goal:** Make `RCA-010` `FR-204`'s eight comparison dimensions measurable on named representative
shell surfaces, deterministically and from the repository alone — and make `FR-205`'s prohibition
on reading product truth out of an image enforceable by a scan.

**Architecture:** One new test module, `tests/test_r812_shell_visual_regression.py`. Visual evidence
is captured as **computed measurements** (box geometry, computed styles, element counts) rather than
stored images. No production file changes.

**Tech Stack:** pytest, Playwright (Chromium), FastAPI `TestClient`.

**Spec:** `governance/specifications/RCA-010.md` — `FR-204`, `FR-205`, §Scope, §Verification.
**Allocation:** `docs/superpowers/plans/2026-09-17-u1-shell-allocation-plan.md` §Slice 10b.
**Design:** `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md` §17, §16.3, §16.4.
**Base:** `0322f7c`.

---

## Global Constraints

- **Authority is `RCA-010` `FR-204`–`FR-205`**, `active` in `governance/registry.yaml`.
- **`tests/` only.** No production file changes. A drift this slice finds opens a follow-on slice
  named for the failing file — the rule slice 9b followed into `#487`.
- **`.github/` is not in §Scope.** `#486` Finding 1 stays open; this slice does not touch CI.
- **No new visual-testing platform, service, or hosted baseline store** (`FR-204`, verbatim).
- **No baseline, screenshot, or reference image may be read as a source of a figure, route,
  capability, refusal reason, or governed word** (`FR-205`). "Where an image and an active
  specification disagree, the specification wins."
- **Pixel-identical equality is NOT required** where responsive layout legitimately adapts
  (`FR-204`). Visual-language drift is a defect even where every other test passes.
- **Run tests with `./.venv/Scripts/python.exe -m pytest`**; do not run `ruff format`.
- **Run the full suite alone, with an isolated `--basetemp`.** Two concurrent runs in one tree
  produced 72 phantom errors this session, and pytest exited 0 anyway — read the counts line.

---

## Decisions, taken from primary sources during planning

### Decision 1 — Computed measurements, not stored images

Both were tested before choosing.

Screenshots **are** byte-stable here — the same surface captured twice gave identical SHA-256
digests (`decision`, `overview`). So determinism alone does not decide it. Three things do:

1. **A stored PNG baseline is the "hosted baseline store" `FR-204` excludes**, and committing
   reference images would make the repository the store.
2. **A digest cannot name the dimension that drifted.** `FR-204` requires comparison on eight
   *named* dimensions; a changed hash says only "something moved". Measured: a 1px padding change
   and a font-family swap both changed the digest, and the digest distinguished neither.
3. **A digest cannot express "pixel-identical equality is not required".** Any legitimate
   responsive adaptation changes it, so the guard would have to be disabled exactly where
   `FR-204` says adaptation is allowed.

Computed measurements were tested against the same two mutations and **named the dimension each
time**: `spacing.cardPad 16px → 17px`, `typography.family → Georgia`. They are deterministic across
two runs. So: box geometry, computed styles and element counts, asserted against **token-derived
expectations**, never against a committed image.

### Decision 2 — The representative set is named honestly, and it is short

The allocation block says to name representatives from `§16.4`'s covered set: **#6 period
comparison, #8 evidence drawer, #9 refusal, #10 Arabic RTL**. Checked against what the shell
actually renders:

| Reference | Shell surface | Usable? |
|---|---|---|
| #10 Arabic RTL | every surface in `ar` | **yes** |
| #8 evidence drawer | `decision` — renders a drawer | **yes** |
| #6 period comparison | `compare` — renders chrome and downloads, **no comparison figures** | **composition only** |
| #9 refusal | **no shell surface renders any refusal class** | **NO — unreachable** |

**#9 is excluded.** Slice 9b established that no surface in `SHELL_SURFACES` renders
`.decision-refusal`, `.decision-unsupported` or `.compare-refusal`. Naming it a representative
would build a run that can only produce the null case — `#486` Finding 2, repeated one slice later.
Recorded in the evidence as unreachable, not as covered.

**#6 is included for composition only**, which is what the reference covers and what the fixture
renders.

A short true list beats a longer one carrying unreachable subjects.

### Decision 3 — Two obligations, two scopes

The allocation block says representatives come from "the full in-scope set, which includes
`legal_templates/`" **and** from "the covered set". No legal page appears in §16.2's twelve
references, so one list cannot satisfy both. The reading that makes both true:

- **Comparison against the approved pack** (`FR-204`'s eight dimensions) applies to the **covered
  references** — Decision 2's set.
- **Visual-regression evidence as such** — determinism, the `FR-205` scan, the extent assertion —
  applies to the **full in-scope set, including `legal_templates/`**.

Two obligations, two scopes. Stated here so a reviewer does not have to reconstruct it.

### Decision 4 — What runs in CI, and what does not

Split by whether a dimension needs a browser:

- **Static, runs in CI:** the `FR-205` scan, the representative-set extent assertion, and
  typography/spacing *token* conformance read from the stylesheets.
- **Browser-gated, skips in CI:** hierarchy, density, visual states, RTL and responsive behaviour,
  which need a rendered box tree.

This is `#486` Finding 1 again and it is **not** closable here: `.github/` is outside §Scope. The
evidence records which dimensions CI actually covers rather than reporting a green run.

### Decision 5 — A finding this slice records but does not fix

**The shell declares no base `font-family`.** Body text resolves to the browser default — measured
as `"Times New Roman"` on `overview`. `workspace.css` uses `var(--font-mono, monospace)` and
`var(--font-sans, inherit)` in seven places, but no sheet sets a family on `body` or `:root`.

That is a `FR-204` typography-dimension question. **It is not fixed here** — this slice changes no
production file, and the fix belongs to the slice owning the sheet. The typography assertion is
therefore written against **what the shell declares** (the `--text-*` scale) rather than against a
resolved family, and the absence is recorded as an open finding.

---

## Facts verified at `0322f7c`

| Fact | Value |
|---|---|
| Screenshot determinism | byte-identical across two runs (`decision`, `overview`) |
| Measurement determinism | identical across two runs |
| Shell surfaces rendering a drawer | `decision` only |
| Shell surfaces rendering a refusal class | **none** |
| `compare` rendered content | chrome + three download actions; no figures |
| Type scale tokens | `--text-xs/sm/base/md/lg` in `shell.css:109+` |
| Base `font-family` on `body`/`:root` | **none declared** (Decision 5) |
| Reference pack | 2 screen references + 1 family board, `docs/product/ui-visual-references/` |

---

## Task 1: The `FR-205` scan — no product truth read from an image

**Files:** Create `tests/test_r812_shell_visual_regression.py`

- [ ] **Step 1: Write the failing test**

```python
"""`RCA-010` `FR-204`-`FR-205`: visual-regression evidence for the commercial shell surfaces.

`tests/` only, and no stored image. Visual evidence here is **computed measurement** -- box
geometry, computed styles and element counts -- because a pixel digest cannot name which of
`FR-204`'s eight dimensions drifted, and a committed baseline image would be the hosted baseline
store `FR-204` excludes. Both were measured before choosing; see the execution plan's Decision 1.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

#: The reference pack. Its own README states the rule this module enforces: "Visual composition is
#: evidence. Generated product facts are not."
_PACK = Path(__file__).resolve().parents[1] / "docs" / "product" / "ui-visual-references"

#: Anything that would make an image a source of product truth (`FR-205`).
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".svg")


def _test_sources() -> list[Path]:
    """Every test module, anchored to this file rather than the CWD.

    A `Path("tests")` would resolve against the working directory and scan nothing when pytest
    runs from elsewhere -- passing vacuously.
    """
    return sorted((Path(__file__).resolve().parent).glob("test_*.py"))


def test_no_test_reads_a_value_out_of_a_reference_image() -> None:
    """`FR-205`: an image is evidence, not truth.

    No module may open, read, decode or digest a file from the reference pack. A test that did
    would be taking a figure, route, capability, refusal reason or governed word from a picture --
    and where an image and an active specification disagree, the specification wins.
    """
    sources = _test_sources()
    assert sources, "no test modules found, so this scan proves nothing"

    offenders = []
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), 1):
            if "ui-visual-references" not in line and not any(
                suffix in line for suffix in _IMAGE_SUFFIXES
            ):
                continue
            if re.search(r"(read_bytes|read_text|open\(|imread|Image\.|sha256|digest)", line):
                offenders.append(f"{source.name}:{line_number}: {line.strip()[:80]}")

    assert offenders == [], "a test reads product truth out of an image: " + "; ".join(offenders)


def test_the_reference_pack_is_present_and_this_scan_is_not_vacuous() -> None:
    """The scan above proves nothing if the pack it guards has moved or emptied."""
    assert _PACK.is_dir(), f"the reference pack is missing at {_PACK}"
    images = [entry for entry in _PACK.iterdir() if entry.suffix in _IMAGE_SUFFIXES]
    assert images, "the reference pack holds no images, so `FR-205` guards nothing here"
```

- [ ] **Step 2: Run**

`./.venv/Scripts/python.exe -m pytest tests/test_r812_shell_visual_regression.py -q`
Expected: PASS.

- [ ] **Step 3: Prove the scan fires**

Append a line to a scratch test module that reads a pack file, run the scan (expect FAIL), delete
it, and confirm `git status --porcelain` is clean. **A scan that cannot fire proves nothing** — if
the mutant passes, the pattern is wrong, not the product.

Also prove it is not CWD-relative: run the module from `tests/` as the working directory and
confirm the same result.

- [ ] **Step 4: Commit**

```bash
git add tests/test_r812_shell_visual_regression.py
git commit -F - <<'MSG'
test(u1-10b): forbid reading product truth out of a reference image

`FR-205`: visual evidence is evidence, not truth. The scan is anchored to
`__file__` rather than the CWD, and carries an emptiness assertion on both sides --
the modules it scans and the pack it guards -- so it cannot pass vacuously.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

## Task 2: The named representative set, asserted for extent

**Files:** Modify `tests/test_r812_shell_visual_regression.py`

- [ ] **Step 1: Write the failing test**

```python
from tests.test_r807_shell_quality import SHELL_SURFACES

#: The representatives, named as a reviewed literal and cross-checked against master specification
#: §16.4's covered references -- not derived from the surfaces these tests happen to drive, which
#: would be a tautology.
#:
#: §16.4 covers #6 period comparison, #8 evidence drawer, #9 refusal, #10 Arabic RTL.
#: **#9 is absent deliberately**: no shell surface renders `.decision-refusal`,
#: `.decision-unsupported` or `.compare-refusal` (slice 9b), so naming it would build a run that
#: can only produce the null case. #6 is composition only -- `compare` renders chrome and three
#: download actions, no figures -- which is what the reference covers.
_REPRESENTATIVES = {
    "decision": "§16.4 #8 evidence drawer, and #7 executive composition",
    "compare": "§16.4 #6 period comparison, composition only",
    "overview": "§16.4 #4 workspace overview density floor",
}

#: `FR-204`'s eight comparison dimensions, so a dimension dropped later fails here.
_DIMENSIONS = (
    "hierarchy",
    "density",
    "spacing_rhythm",
    "typography",
    "visual_states",
    "rtl",
    "responsive",
    "asset_fidelity",
)


def test_every_representative_is_a_surface_the_shell_serves() -> None:
    """A representative naming a surface that does not exist measures nothing."""
    assert _REPRESENTATIVES, "no representatives named, so this slice measures nothing"
    unknown = sorted(set(_REPRESENTATIVES) - set(SHELL_SURFACES))
    assert unknown == [], f"representatives name surfaces the shell does not serve: {unknown}"


def test_the_refusal_reference_is_recorded_as_unreachable_not_covered() -> None:
    """`§16.4` covers #9 refusal; the shell renders none, and that is recorded rather than claimed.

    Fails the day a shell surface renders a refusal -- which is when #9 becomes a usable
    representative and belongs in `_REPRESENTATIVES`.
    """
    from tests.test_r807_shell_quality import _html

    classes = ("decision-refusal", "decision-unsupported", "compare-refusal")
    rendering = sorted(
        surface
        for surface in SHELL_SURFACES
        for name in classes
        if f'class="{name}' in _html(surface, "en")
    )
    assert rendering == [], (
        f"{rendering} now render a refusal: add §16.4 #9 to _REPRESENTATIVES and delete this test"
    )
```

- [ ] **Step 2: Run** — expected PASS.

- [ ] **Step 3: Mutate** — add `"nonexistent"` to `_REPRESENTATIVES` (expect FAIL), restore by
  `git checkout --` and confirm `git diff` is empty.

- [ ] **Step 4: Commit** with a message stating why #9 is excluded.

---

## Task 3: The measured dimensions

**Files:** Modify `tests/test_r812_shell_visual_regression.py`

The probe returns one dict per surface; each assertion names its dimension so a failure says
*which* of the eight drifted.

- [ ] **Step 1: Write the failing tests**

```python
#: Read in the page, so every value is what the browser resolved rather than what a sheet says.
_PROBE = """
(() => {
  const card = document.querySelector('.document-card');
  const style = (el) => el ? getComputedStyle(el) : null;
  const card_style = style(card);
  return {
    hierarchy: {
      h1: document.querySelectorAll('h1').length,
      h2: document.querySelectorAll('h2').length,
      landmarks: document.querySelectorAll('nav, main, header').length,
    },
    density: {
      cards: document.querySelectorAll('.document-card').length,
      actions: document.querySelectorAll('a, button').length,
    },
    spacing_rhythm: card_style ? {
      padding: card_style.paddingTop,
      gap: card_style.marginBlockEnd,
    } : null,
    rtl: {
      dir: document.documentElement.getAttribute('dir'),
      cardStart: card ? Math.round(card.getBoundingClientRect().left) : null,
    },
  };
})()
"""


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(_REPRESENTATIVES))
def test_the_measured_dimensions_are_deterministic_across_two_runs(surface: str) -> None:
    """`FR-204` §Verification: the evidence is reproducible and deterministic across two runs."""
    first = _measure(surface, "en")
    second = _measure(surface, "en")
    assert first == second, f"{surface}: the measurement is not deterministic"


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(_REPRESENTATIVES))
def test_the_spacing_rhythm_comes_from_the_token_scale(surface: str) -> None:
    """`FR-204` spacing rhythm: padding and gap are token multiples, not arbitrary values.

    Asserted against the token the sheet declares, not against a value copied from an image --
    which `FR-205` forbids and which would make the picture the source of truth.
    """
    measured = _measure(surface, "en")["spacing_rhythm"]
    assert measured is not None, f"{surface}: no card measured, so this proves nothing"
    for name, value in measured.items():
        pixels = float(value.removesuffix("px"))
        assert pixels % 4 == 0, f"{surface}: {name} is {value}, off the 4px rhythm"


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(_REPRESENTATIVES))
def test_the_right_to_left_rendering_mirrors(surface: str) -> None:
    """`FR-204` RTL: the same surface in Arabic is a mirror, not a reflow."""
    english, arabic = _measure(surface, "en"), _measure(surface, "ar")
    assert english["rtl"]["dir"] == "ltr"
    assert arabic["rtl"]["dir"] == "rtl"
    # Hierarchy and density are language-invariant: the same page, mirrored.
    assert english["hierarchy"] == arabic["hierarchy"], f"{surface}: hierarchy differs by language"
    assert english["density"] == arabic["density"], f"{surface}: density differs by language"
```

- [ ] **Step 2: Run with the browser present.** A failure here is a **real `FR-204` finding** —
  record it and open a follow-on slice named for the failing file. Do not change a stylesheet.

- [ ] **Step 3: Mutate each dimension.** Inject a CSS override at measurement time only
  (`padding: 17px` → spacing fails; a hidden `<h2>` → hierarchy fails) and confirm each assertion
  names its own dimension. No source file is touched.

- [ ] **Step 4: Commit.**

---

## Task 4: The evidence document

**Files:** Create `docs/superpowers/plans/2026-09-18-u1-slice-10b-evidence.md`

Must record: the representative set and **why #9 is excluded**; which dimensions run in CI and
which skip (Decision 4); the determinism result for both candidate architectures and why
measurements won (Decision 1); the two-scope reading (Decision 3); the missing base `font-family`
as an open finding (Decision 5); and the mutation result per dimension with `git diff` clean after
each restore.

Then: `ruff check .`, `khepri-gov validate`, the full suite alone with an isolated `--basetemp`,
CodeScene `analyze_change_set` after `git fetch origin main`.

---

## Self-review against `FR-204`

| Dimension | Where | Runs in CI |
|---|---|---|
| hierarchy | `test_the_right_to_left_rendering_mirrors` (invariance) | no |
| density | same | no |
| spacing rhythm | `test_the_spacing_rhythm_comes_from_the_token_scale` | no |
| typography | token-scale conformance — **Decision 5 finding** | partly |
| visual states | slice 5's state grammar already binds these | yes |
| RTL | `test_the_right_to_left_rendering_mirrors` | no |
| responsive | slice 8's viewport guards + 9b's matrix | no |
| asset fidelity | slice 2b's `FR-206` asset scan — extended, not duplicated | yes |

**Known gap:** most dimensions are browser-gated and skip in CI (`#486` Finding 1, still open and
still the owner's). The evidence states this rather than reporting a green run.
