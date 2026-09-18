# `U1` slice 9b / `U1-06` — Accessibility evidence, commercial shell surfaces: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Checkboxes in this repository are **never ticked after the
> fact** — read the newest dated status block, not the boxes.

**Goal:** Make `RCA-010` `FR-200`'s thirteen accessibility floors provable per shell surface, in both
languages, at the supported viewports — and make the surfaces the floors do *not* reach visible as
gaps rather than silently unmeasured.

**Architecture:** One new test module, `tests/test_r811_shell_accessibility.py`, beside the existing
shell evidence modules. It reuses `test_r807_shell_quality.py`'s surface roster and render helpers
rather than restating them, adds a second roster and driver for `legal_templates/` (which the
existing helpers structurally cannot serve), and splits the thirteen floors by whether they need a
browser. **No source file changes.**

**Tech Stack:** pytest, Playwright (Chromium), FastAPI `TestClient`, Jinja2 templates.

**Spec:** `governance/specifications/RCA-010.md` — `FR-200`, §Scope, §Verification.
**Allocation:** `docs/superpowers/plans/2026-09-17-u1-shell-allocation-plan.md` §Slice 9b.
**Design:** master specification §11.

---

## Global Constraints

Copied verbatim from the authorities. Every task's requirements implicitly include this section.

- **Authority is `RCA-010` `FR-200`** — `active` in `governance/registry.yaml`, verified at
  `aa62016`.
- **`tests/` only.** The allocation block: "**This slice changes no source file**; where a floor
  fails, the fix lands in the slice that owns that file, not here." An evidence slice that edits a
  stylesheet or a template to make its own assertion pass "has left its scope, and the failure it
  hid is still in the product."
- **A floor failure opens a follow-on slice** under `RCA-010`, named for the file that fails. It
  does **not** widen this slice.
- **`.github/` is not in `RCA-010` §Scope.** §Scope authorizes exactly: `shell.css`,
  `shell-components.css`, `workspace.css`, `shell_templates/`, `legal_templates/`, `shell_copy.py`,
  and `tests/`. No workflow file may be edited by this slice. See Decision 1.
- **Surface extent includes `legal_templates/`** (allocation block, tree-state finding 3).
- **Do not call the extent assertion independent.** The allocation block: two-sided drift detection
  is "stronger than a tautology and **weaker than independence** … Label it accurately; do not call
  it independent." The block's own heading says "from an independent source" and its body
  contradicts it — **follow the body**.
- **Do not replace the extent assertion with a list derived from the surfaces the tests drive** —
  that is the tautology slice 4 ruled out.
- **Gate:** `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest` all pass. Every new
  file scores 10.00 in CodeScene and no tracked hotspot declines.
- **Run tests with `./.venv/Scripts/python.exe -m pytest`** — the bare `pytest` on PATH is a
  different interpreter.
- **Do not run `ruff format`** — there is no CI format gate and it reflows unrelated code.

---

## Decisions this plan takes, with their reasons

These were settled during planning from primary sources. An executor must not silently reverse one.

### Decision 1 — The CI browser gap is made VISIBLE, not closed

`FR-200` §Verification requires the floors "measured in the real browser the repository already
drives, with contrast computed rather than asserted". CI runs bare `uv run pytest`
(`.github/workflows/governance.yml:87`) with **no browser install step**, so every
`@pytest.mark.browser` case skips there. Contrast computation is irreducibly browser-bound — unlike
slice 8's layout half, it cannot be narrowed onto a static guard.

Closing the gap means editing `.github/workflows/governance.yml`. **§Scope does not authorize
`.github/`**, and the allocation block forbids widening past `tests/`. So this slice **does not**
edit CI.

What it does instead, which is in scope: a `tests/`-only guard that makes the absence *legible*.
`test_the_browser_floors_are_not_silently_unmeasured` records that the browser-gated floors report
`skipped`, not `passed`, and asserts the browser-marked case count is non-zero so the marker cannot
be quietly removed. **A skip is not a pass**, and the guard says so in the test name and docstring.

> **This leaves `FR-200`'s computed-contrast obligation unenforced in CI.** That is a real,
> named, deliberate gap — recorded in the evidence document and carried to the owner, not hidden.
> Authorizing a CI browser install needs an amendment naming `.github/`, which only the owner can
> author. **Do not treat this slice as discharging `FR-200` in CI.**

### Decision 2 — Legal gets its own roster and driver, not a widened first scan

The allocation block offers two ways to cover `legal_templates/`: "Widen the scan, or add a second
extent assertion over `legal_templates/` with its own emptiness check." **Take the second.** The
first is structurally impossible here, for three verified reasons:

1. `test_every_shell_template_is_measured` computes `measured = {f"{surface}.html.j2" for surface in
   SHELL_SURFACES}` — it assumes **surface key == template basename, 1:1**. Six `LEGAL_PAGES`
   (`about-us`, `contact-us`, `data-protection`, `privacy-policy`, `refund-and-void`,
   `terms-and-conditions`) render through **one** template, `legal_page.html.j2`. Adding six roster
   entries would synthesize six basenames absent from disk and the equality assertion would fail.
2. `legal.html.j2` is a layout — `legal_page.html.j2` opens `{% extends "legal.html.j2" %}` — so it
   belongs in a legal-side layout set, not the measured set.
3. `_html()` cannot serve a legal page at all. It builds `add_shell_routes(app, services=
   ShellServices(...))`; legal is registered by `add_legal_routes(app)`, which takes **no services
   argument** (`legal_api.py:234`).

### Decision 3 — Inject the two sheets legal links, not the shell's three

`test_r807_shell_quality.py`'s browser case injects `shell.css` + `shell-components.css` +
`shell_assets/workspace.css`. **A legal page links only two** — `legal.html.j2:7-8` links
`shell.css` and `shell-components.css`, and `legal_api.py:104-107`'s `_ASSETS` allowlist serves
exactly those two. Injecting `workspace.css` into a legal page would measure a document the product
never renders, in the same class of error `_PRINT_TEMPLATES` exists to prevent (the module's own
comment records that the wrong sheet set "report[s] every target as too small").

### Decision 4 — Drive both a published and an unpublished legal page

Only 4 of 12 legal responses are `200` (`about-us` and `refund-and-void`, each in `en` and `ar`);
the other 8 are a governed `503` unpublished state. All 12 render a document with exactly one `h1`,
so all are measurable — but a contrast measurement over a mostly-empty unpublished document can
pass vacuously ("a run that can only produce the null case"). **Drive at least one published and one
unpublished page per language, and assert the published one carries substantive content**, so the
non-null case is provably reachable.

Refusal-vs-error distinguishability is `FR-202` and **slice 5's**, not this slice's. Do not assert
it here.

### Decision 5 — A new module, not an extension of `test_r807_shell_quality.py`

§Scope authorizes "extending `tests/test_r801_shell_tokens.py` and `tests/test_r807_shell_quality.py`
**and adding modules beside them**". `test_r807_shell_quality.py` is already 788 lines and scores
10.00; adding thirteen floors plus a legal driver risks Low Cohesion, and extracting helpers *raises*
the module mean. The one exception: **the legal extent assertion's sibling edit** — see Task 2 — has
to sit next to the existing one so the pair reads as one rule.

---

## Facts verified at `aa62016`, so no task re-derives them

| Fact | Value | Source |
|---|---|---|
| Chromium available locally | `149.0.7827.55` | `playwright.chromium.launch()` |
| CI browser install step | **none** | `.github/workflows/governance.yml:87` |
| Shell surfaces | 10 | `SHELL_SURFACES` |
| Legal pages | 6 × 2 languages = 12 | `LEGAL_PAGES`, `LEGAL_COPY` |
| Legal templates | `legal.html.j2` (layout), `legal_page.html.j2` | `legal_templates/` |
| Legal sheets linked | `shell.css`, `shell-components.css` **only** | `legal.html.j2:7-8` |
| Published legal pages | `about-us`, `refund-and-void` (200); other 4 are 503 | route probe |
| Only `tabindex` value present | `-1`, on `<main id="main-content">` | all 10 surfaces |
| `decision` `<nav>` count | 2 — `aria-label="Sections"`, `aria-label="Analysis"` | `_html('decision','en')` |
| `decision` placeholders | 3 `placeholder="Any"`, each inside a wrapping `<label>` with visible `<span>` text | `_decision_*.html.j2` |
| `role="status"` present | **0 occurrences on every shell surface** | `_html` survey |

> **The last row is a live finding.** `FR-200` requires `role="status"` for refusals and progress,
> and no shell surface emits one. Task 6 asserts the floor conditionally — *where a refusal or
> progress region exists, it carries `role="status"`* — and records the absence. If the floor fails
> outright, **open a follow-on slice; do not add the attribute here** (Global Constraints).

---

## File structure

- **Create:** `tests/test_r811_shell_accessibility.py` — all thirteen `FR-200` floors, the legal
  roster and driver, and the browser-visibility guard. One responsibility: accessibility evidence.
- **Modify:** `tests/test_r807_shell_quality.py` — add the legal extent assertion beside the
  existing shell one (Task 2 only; no other edit).
- **Create:** `docs/superpowers/plans/2026-09-18-u1-slice-9b-evidence.md` — the evidence record.

---

## Task 1: The module skeleton and the shared render helpers

**Files:**
- Create: `tests/test_r811_shell_accessibility.py`

**Interfaces:**
- Consumes: `SHELL_SURFACES`, `_html`, `_without_comments` from `tests.test_r807_shell_quality`
  (slice 8 established this import path at `test_r810_shell_responsive_rtl.py:43`).
- Produces: `LEGAL_SURFACES: dict[str, tuple[str, str]]`, `_legal_html(page, language) -> str`,
  `_launch_chromium(playwright) -> Browser`, `_legal_css() -> str`, `_shell_css() -> str`.

- [ ] **Step 1: Write the failing test — the legal driver renders what the product serves**

```python
"""`RCA-010` `FR-200`: the master specification §11 accessibility floors, per shell surface.

`tests/` only. Where a floor fails, the fix lands in the slice that owns the file, not here --
this module changes no source file, and an evidence slice that edited a template to make its own
assertion pass would leave the failure in the product.

Two rosters, because one driver cannot serve both. `SHELL_SURFACES` renders through
`add_shell_routes(app, services=ShellServices(...))`; the legal pages render through
`add_legal_routes(app)`, which takes no services argument, and six of them share one template.
"""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.runtime.legal_api import LEGAL_PAGES, LEGAL_PREFIX, add_legal_routes
from tests.test_r807_shell_quality import SHELL_SURFACES, _html

#: The legal pages, by the state each renders. `about-us` and `refund-and-void` publish; the
#: other four hold a governed unpublished state and answer 503. Both are measurable documents --
#: each carries exactly one `h1` -- and driving only the unpublished four would be a run that can
#: only produce the null case.
LEGAL_PUBLISHED = ("about-us", "refund-and-void")
LEGAL_UNPUBLISHED = ("contact-us", "data-protection", "privacy-policy", "terms-and-conditions")


def _legal_client() -> TestClient:
    """The legal routes carry no session and no services, so this needs neither."""
    app = FastAPI()
    add_legal_routes(app)
    return TestClient(app, base_url="https://testserver")


def _legal_html(page: str, language: str) -> str:
    return _legal_client().get(f"{LEGAL_PREFIX}/{language}/{page}").text


def test_the_legal_roster_matches_the_served_inventory() -> None:
    """A legal page added to the product without a case here fails rather than going unmeasured."""
    assert set(LEGAL_PUBLISHED) | set(LEGAL_UNPUBLISHED) == set(LEGAL_PAGES)
    assert LEGAL_PAGES, "no legal pages found, so this test proves nothing"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("page", sorted(LEGAL_PAGES))
def test_every_legal_page_renders_one_heading_in_both_languages(page: str, language: str) -> None:
    """Both the published and the unpublished state are documents, not error pages."""
    html = _legal_html(page, language)
    assert html.count("<h1") == 1
    assert f'lang="{language}"' in html


def test_a_published_legal_page_carries_more_than_its_chrome() -> None:
    """Without this, every legal measurement below could pass over an empty document."""
    published = len(_legal_html("about-us", "en"))
    unpublished = len(_legal_html("contact-us", "en"))
    assert published > unpublished, "the published page must carry content the unpublished lacks"
```

- [ ] **Step 2: Run it to verify the roster claim actually holds**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py -q`
Expected: PASS — these assert current, verified behaviour. If
`test_the_legal_roster_matches_the_served_inventory` fails, the product's legal inventory changed
since `aa62016`; update the two tuples, do not delete the assertion.

- [ ] **Step 3: Mutate to prove each can fail**

```bash
# Drop a page from the roster -- the extent assertion must fire.
python - <<'PY'
from pathlib import Path
p = Path("tests/test_r811_shell_accessibility.py")
p.write_text(p.read_text(encoding="utf-8").replace(
    'LEGAL_PUBLISHED = ("about-us", "refund-and-void")',
    'LEGAL_PUBLISHED = ("about-us",)'), encoding="utf-8")
PY
./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py -q -k roster
git diff --stat   # must show ONLY this file
git checkout -- tests/test_r811_shell_accessibility.py
git diff          # must be EMPTY -- restore by checkout, never by str.replace
```

Expected: FAIL on the mutant, clean tree after restore.

- [ ] **Step 4: Commit**

```bash
git add tests/test_r811_shell_accessibility.py
git commit -F - <<'MSG'
test(u1-09b): drive the legal surfaces the shell helpers cannot reach

`FR-200`'s floors must hold per shell surface, and `legal_templates/` is in
`RCA-010` §Scope. The existing helpers cannot serve those pages: `_html` builds
`add_shell_routes(..., services=ShellServices(...))`, while legal registers through
`add_legal_routes(app)` with no services argument, and six pages share one template.

So this module carries a second roster and driver rather than widening the first.
The published/unpublished split is asserted, not assumed: eight of the twelve
responses hold a governed 503 state, and measuring only those would be a run that
can only produce the null case.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

## Task 2: The legal extent assertion, beside the shell one

**Files:**
- Modify: `tests/test_r807_shell_quality.py` — add after `test_every_shell_template_is_measured`
  (currently ends at `:406`).

**Interfaces:**
- Consumes: nothing new.
- Produces: `_LEGAL_LAYOUT_TEMPLATES`, `test_every_legal_template_is_measured`.

This is the one edit outside the new module, and it belongs here so the pair reads as one rule.

- [ ] **Step 1: Write the failing test**

Add immediately below `test_every_shell_template_is_measured`:

```python
#: `legal_page.html.j2` extends this, so it is never a surface of its own.
_LEGAL_LAYOUT_TEMPLATES = {"legal.html.j2"}


def test_every_legal_template_is_measured() -> None:
    """`legal_templates/` is in `RCA-010` §Scope, and the scan above reaches only `shell_templates/`.

    Two-sided drift detection, the same shape as the assertion above: the files on disk are
    compared against the measured set union the layouts, so forgetting either side fails. It is
    **not independent** -- `tests/` is in the same §Scope, so a slice can edit both sides. It is
    stronger than a tautology and weaker than independence, and is labelled as exactly that.

    One template serves six pages, so this asserts template extent, not page extent. Page extent
    is `test_the_legal_roster_matches_the_served_inventory` in `test_r811_shell_accessibility.py`.
    """
    templates = {
        entry.name
        for entry in files("khepri.runtime").joinpath("legal_templates").iterdir()
        if entry.name.endswith(".html.j2")
    }

    assert templates, "no legal templates found, so this test proves nothing"
    assert templates == {"legal_page.html.j2"} | _LEGAL_LAYOUT_TEMPLATES
```

- [ ] **Step 2: Run it**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r807_shell_quality.py -q -k measured`
Expected: PASS, 2 tests.

- [ ] **Step 3: Prove it fires on an added template**

```bash
printf '{%% extends "legal.html.j2" %%}\n' > src/khepri/runtime/legal_templates/_probe.html.j2
./.venv/Scripts/python.exe -m pytest tests/test_r807_shell_quality.py -q -k legal_template
rm src/khepri/runtime/legal_templates/_probe.html.j2
git status --porcelain   # must be empty for src/
```

Expected: FAIL while the probe exists — a template added without a case cannot ship unmeasured.
**Remove the probe**; this slice changes no source file.

- [ ] **Step 4: Commit**

```bash
git add tests/test_r807_shell_quality.py
git commit -F - <<'MSG'
test(u1-09b): measure the legal templates the shell scan cannot see

`test_every_shell_template_is_measured` scans only `shell_templates/`, so
`legal.html.j2` and `legal_page.html.j2` were measured by nothing while slice 8
hardened them -- the "subset assertions hide a forgotten entry" defect, named in
advance by the allocation block's tree-state finding 3.

Kept as a second assertion rather than a widened first one: the existing scan
derives its expectation from `SHELL_SURFACES` on a 1:1 surface-to-basename
assumption, and six legal pages share one template.

Labelled two-sided drift detection, not independent: `tests/` sits in the same
§Scope as the templates, so a slice can edit both sides.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

## Task 3: The static floors — structure, landmarks, headings, labels, tabindex

**Files:**
- Modify: `tests/test_r811_shell_accessibility.py`

**Interfaces:**
- Consumes: `SHELL_SURFACES`, `_html`, `LEGAL_PAGES`, `_legal_html`.
- Produces: `_Landmarks` (an `HTMLParser` subclass), `_landmarks(html) -> list[tuple[str, str|None]]`.

These seven floors need no browser, so they run in CI. Parse with `html.parser`, not regex — slice 8
found `data-href` matching a `"href="` substring, and CodeRabbit's fix was parser-based.

- [ ] **Step 1: Write the failing tests**

```python
from html.parser import HTMLParser

#: Landmarks `FR-200` requires to carry meaningful unique accessible names.
_LANDMARKS = frozenset({"nav", "main", "header", "footer", "aside", "form", "section"})


class _Landmarks(HTMLParser):
    """Collects landmark elements with their accessible names, by parser rather than by regex."""

    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[str, str | None]] = []
        self.tabindex: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value for name, value in attrs}
        if "tabindex" in values and values["tabindex"] is not None:
            self.tabindex.append(values["tabindex"])
        if tag in _LANDMARKS:
            name = values.get("aria-label") or values.get("aria-labelledby")
            self.found.append((tag, name))


def _parse(html: str) -> _Landmarks:
    parser = _Landmarks()
    parser.feed(html)
    return parser


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_no_surface_carries_a_positive_tabindex(surface: str, language: str) -> None:
    """`FR-200`: focus order follows document order, so no positive `tabindex` anywhere."""
    for value in _parse(_html(surface, language)).tabindex:
        assert int(value) <= 0, f"{surface}/{language} carries tabindex={value}"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("page", sorted(LEGAL_PAGES))
def test_no_legal_page_carries_a_positive_tabindex(page: str, language: str) -> None:
    """The same floor over the surfaces the shell roster cannot reach."""
    for value in _parse(_legal_html(page, language)).tabindex:
        assert int(value) <= 0, f"{page}/{language} carries tabindex={value}"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_repeated_landmarks_carry_distinct_accessible_names(surface: str, language: str) -> None:
    """`FR-200`: landmarks are meaningful and unique.

    A sole `main` needs no name -- naming it would be ARIA where native semantics suffice, which
    the same requirement forbids. The floor is that landmarks sharing a tag are *told apart*, which
    is where a screen-reader user is actually stranded. `decision` carries two `nav` regions
    ("Sections" and "Analysis") and is the case that makes this non-vacuous.
    """
    found = _parse(_html(surface, language)).found
    for tag in {tag for tag, _ in found}:
        names = [name for element, name in found if element == tag]
        if len(names) > 1:
            assert all(names), f"{surface}/{language}: repeated <{tag}> without a name"
            assert len(set(names)) == len(names), f"{surface}/{language}: duplicate <{tag}> names"


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_every_surface_has_exactly_one_main_landmark(surface: str, language: str) -> None:
    """`FR-200`: semantic landmarks. One `main` is what the skip link targets."""
    found = _parse(_html(surface, language)).found
    assert len([tag for tag, _ in found if tag == "main"]) == 1
```

- [ ] **Step 2: Run to verify they pass against real markup**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py -q`
Expected: PASS. Verified at `aa62016`: only `tabindex="-1"` exists, and `decision`'s two `nav`
regions are named "Sections" and "Analysis".

- [ ] **Step 3: Mutate each floor**

```bash
# A positive tabindex must fail the floor.
python - <<'PY'
from pathlib import Path
p = Path("src/khepri/runtime/shell_templates/shell.html.j2")
t = p.read_text(encoding="utf-8")
p.write_text(t.replace('id="main-content"', 'id="main-content" tabindex="3"', 1), encoding="utf-8")
PY
./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py -q -k tabindex
git checkout -- src/khepri/runtime/shell_templates/shell.html.j2
git diff   # MUST be empty -- restore by checkout

# Two same-named navs must fail the uniqueness floor.
python - <<'PY'
from pathlib import Path
p = Path("src/khepri/runtime/shell_templates/decision.html.j2")
t = p.read_text(encoding="utf-8")
p.write_text(t.replace('aria-label="Analysis"', 'aria-label="Sections"', 1), encoding="utf-8")
PY
./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py -q -k distinct
git checkout -- src/khepri/runtime/shell_templates/decision.html.j2
git diff   # MUST be empty
```

Expected: each mutant FAILS its floor; `git diff` empty after every restore.
If a mutant's target string is absent, **the mutant proved nothing** — find the real string first.

- [ ] **Step 4: Commit**

```bash
git add tests/test_r811_shell_accessibility.py
git commit -F - <<'MSG'
test(u1-09b): assert the structural floors that need no browser

Seven of `FR-200`'s thirteen floors are static, so they run in CI rather than
behind the browser marker: positive tabindex, landmark uniqueness, and the single
main landmark, over both rosters and both languages.

Parsed with `html.parser` rather than regex, the idiom slice 8 settled after a
substring scan counted `data-href=` as an anchor `href`.

The landmark floor asserts that landmarks sharing a tag are told apart, not that
every landmark is named: naming a sole `main` would be ARIA where native semantics
suffice, which the same requirement forbids.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

## Task 4: The label floor — and the placeholder that must not stand in for one

**Files:**
- Modify: `tests/test_r811_shell_accessibility.py`

**Interfaces:**
- Consumes: `_html`, `SHELL_SURFACES`.
- Produces: `_Controls` (an `HTMLParser` subclass), `_controls(html)`.

`FR-200`: "labels associated with controls and never a placeholder standing in for one." Verified at
`aa62016`: `decision` carries three `<input placeholder="Any">`, each **wrapped** in a
`<label class="decision-filter">` with a visible `<span class="decision-filter-label">`. So the
floor passes — but only because the wrapping label exists, which is exactly what must be asserted.

- [ ] **Step 1: Write the failing test**

```python
class _Controls(HTMLParser):
    """Tracks whether each labellable control is inside a `<label>` or carries an explicit name."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.controls: list[dict[str, str | bool | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {name: value for name, value in attrs}
        if tag == "label":
            self.depth += 1
        if tag in {"input", "select", "textarea"}:
            if values.get("type") in {"hidden", "submit", "button"}:
                return
            self.controls.append(
                {
                    "wrapped": self.depth > 0,
                    "id": values.get("id"),
                    "aria-label": values.get("aria-label"),
                    "aria-labelledby": values.get("aria-labelledby"),
                    "placeholder": values.get("placeholder"),
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            self.depth = max(0, self.depth - 1)


def _controls(html: str) -> list[dict[str, str | bool | None]]:
    parser = _Controls()
    parser.feed(html)
    return parser.controls


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_every_control_has_a_label_that_is_not_its_placeholder(
    surface: str, language: str
) -> None:
    """`FR-200`: a placeholder is a value hint and disappears on input; it is never the label.

    `decision`'s three filter inputs carry `placeholder="Any"` and are each wrapped in a
    `<label>` with visible text -- so the placeholder describes the *default*, not the field.
    This asserts the wrapping label is what names them, which is the part that could regress.
    """
    html = _html(surface, language)
    for control in _controls(html):
        named = (
            control["wrapped"]
            or control["aria-label"]
            or control["aria-labelledby"]
            or control["id"] is not None
            and f'for="{control["id"]}"' in html
        )
        assert named, f"{surface}/{language}: a control is named only by its placeholder"
```

- [ ] **Step 2: Run it**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py -q -k placeholder`
Expected: PASS — 20 cases (10 surfaces × 2 languages).

- [ ] **Step 3: Mutate — strip the wrapping label, keep the placeholder**

```bash
python - <<'PY'
from pathlib import Path
import re
p = Path("src/khepri/runtime/shell_templates/_decision_sections.html.j2")
t = p.read_text(encoding="utf-8")
# If the filter markup lives elsewhere, find it first -- a malformed mutant proves nothing.
print("contains decision-filter:", "decision-filter" in t)
PY
grep -rln 'decision-filter' src/khepri/runtime/shell_templates/
# Then remove the <span> label text from the located file, leaving placeholder="Any",
# run -k placeholder (expect FAIL), and restore:
git checkout -- src/khepri/runtime/shell_templates/
git diff   # MUST be empty
```

Expected: with the visible label gone the floor FAILS; `git diff` empty after restore.

- [ ] **Step 4: Commit**

```bash
git add tests/test_r811_shell_accessibility.py
git commit -F - <<'MSG'
test(u1-09b): a placeholder is never the label

`FR-200` forbids a placeholder standing in for a label. The decision filters carry
`placeholder="Any"` and pass -- but only because each input is wrapped in a label
with visible text, and that wrapping is what this asserts.

Accepts the four ways a control is actually named -- wrapping label, `for`,
`aria-label`, `aria-labelledby` -- so a correct surface using any of them passes.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

## Task 5: The browser floors — computed contrast, target size, reduced motion, 200% text

**Files:**
- Modify: `tests/test_r811_shell_accessibility.py`

**Interfaces:**
- Consumes: `_html`, `_legal_html`, `SHELL_SURFACES`.
- Produces: `_launch_chromium`, `_shell_css`, `_legal_css`, `_contrast_ratio`.

These need a real browser. **Decision 1 applies: they skip in CI**, and Task 7 makes that visible.

- [ ] **Step 1: Write the failing tests**

```python
def _pinned_chromium() -> str | None:
    """A Chromium under `PLAYWRIGHT_BROWSERS_PATH`, the fallback slice 8 established."""
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if not root:
        return None
    candidates = sorted(Path(root).glob("chromium*/chrome-win/chrome.exe"))
    return str(candidates[-1]) if candidates else None


def _launch_chromium(playwright: object) -> object:
    """The pinned Chromium, or `pytest.skip` when this machine genuinely has none."""
    from playwright.sync_api import Error

    try:
        return playwright.chromium.launch()  # type: ignore[attr-defined]
    except Error as error:
        executable = _pinned_chromium()
        if executable is None:
            pytest.skip(f"Pinned Chromium is unavailable: {error}")
        return playwright.chromium.launch(executable_path=executable)  # type: ignore[attr-defined]


def _shell_css() -> str:
    """The three sheets a shell surface links, in link order."""
    journey = files("khepri.rra.journey").joinpath("assets")
    return "\n".join(
        (
            journey.joinpath("shell.css").read_text(encoding="utf-8"),
            journey.joinpath("shell-components.css").read_text(encoding="utf-8"),
            files("khepri.runtime")
            .joinpath("shell_assets", "workspace.css")
            .read_text(encoding="utf-8"),
        )
    )


def _legal_css() -> str:
    """The **two** sheets a legal page links -- `legal.html.j2:7-8`, allowlisted at
    `legal_api.py:104-107`. Injecting `workspace.css` here would measure a document the product
    never serves, the error `_PRINT_TEMPLATES` exists to prevent."""
    journey = files("khepri.rra.journey").joinpath("assets")
    return "\n".join(
        (
            journey.joinpath("shell.css").read_text(encoding="utf-8"),
            journey.joinpath("shell-components.css").read_text(encoding="utf-8"),
        )
    )


#: Computed in the page, from resolved colours -- `FR-200` §Verification requires contrast
#: *computed*, not asserted against a table of hex values a test happens to remember.
_CONTRAST = """
(() => {
  const lum = (c) => {
    const [r, g, b] = c.match(/\\d+/g).slice(0, 3).map(Number).map((v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const opaque = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const bg = getComputedStyle(n).backgroundColor;
      if (bg && !bg.startsWith('rgba(0, 0, 0, 0)')) return bg;
    }
    return 'rgb(255, 255, 255)';
  };
  const out = [];
  for (const el of document.querySelectorAll('p, h1, h2, h3, li, a, button, span, td, th')) {
    if (!el.textContent.trim() || el.offsetParent === null) continue;
    const style = getComputedStyle(el);
    const size = parseFloat(style.fontSize);
    const large = size >= 24 || (size >= 18.66 && parseInt(style.fontWeight, 10) >= 700);
    const a = lum(style.color), b = lum(opaque(el));
    const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    out.push({ ratio, floor: large ? 3.0 : 4.5, text: el.textContent.trim().slice(0, 40) });
  }
  return out;
})()
"""


@pytest.mark.browser
@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_text_contrast_is_computed_and_meets_its_floor(surface: str, language: str) -> None:
    """`FR-200` §Verification: contrast **computed** in the real browser, not asserted."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(_html(surface, language), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            measured = page.evaluate(_CONTRAST)
            assert measured, f"{surface}/{language}: no text measured, so this proves nothing"
            for item in measured:
                assert item["ratio"] >= item["floor"], (
                    f"{surface}/{language}: {item['ratio']:.2f} < {item['floor']} "
                    f"on {item['text']!r}"
                )
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("page_name", ["about-us", "contact-us"])
def test_legal_text_contrast_is_computed_and_meets_its_floor(
    page_name: str, language: str
) -> None:
    """One published page and one unpublished, so the non-null case is provably reached."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(_legal_html(page_name, language), wait_until="domcontentloaded")
            page.add_style_tag(content=_legal_css())
            measured = page.evaluate(_CONTRAST)
            assert measured, f"{page_name}/{language}: no text measured"
            for item in measured:
                assert item["ratio"] >= item["floor"], (
                    f"{page_name}/{language}: {item['ratio']:.2f} < {item['floor']} "
                    f"on {item['text']!r}"
                )
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_text_scales_to_two_hundred_percent_without_losing_content(surface: str) -> None:
    """`FR-200`: 200% text loses neither content nor function."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 1180, "height": 900})
            page.set_content(_html(surface, "en"), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            before = page.evaluate("document.body.innerText.trim().length")
            page.add_style_tag(content="html { font-size: 200% !important; }")
            after = page.evaluate("document.body.innerText.trim().length")
            assert after >= before, f"{surface}: text was lost at 200%"
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (
                f"{surface}: 200% text introduced horizontal overflow"
            )
        finally:
            browser.close()


@pytest.mark.browser
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_a_pointer_target_is_measured_on_the_element_it_lands_on(surface: str) -> None:
    """`FR-200`: at least 44px **on the element a pointer lands on**, not on an ancestor."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = _launch_chromium(playwright)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.set_content(_html(surface, "en"), wait_until="domcontentloaded")
            page.add_style_tag(content=_shell_css())
            for locator in page.locator("a:visible, button:visible, select:visible").all():
                box = locator.bounding_box()
                assert box is not None
                assert box["height"] >= 44, f"{surface}: a target is {box['height']}px tall"
        finally:
            browser.close()
```

- [ ] **Step 2: Run them with the browser present**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py -m browser -q`
Expected: they execute (not skip) and PASS. **If contrast fails on a real surface, that is a genuine
finding**: record it and open a follow-on slice under `RCA-010` named for the failing stylesheet.
Do not edit a stylesheet here, and do not lower a floor to make a test pass.

- [ ] **Step 3: Prove the contrast measurement can fail**

```bash
# Inject a deliberately low-contrast rule at measurement time only -- no source file is touched.
./.venv/Scripts/python.exe - <<'PY'
import sys; sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright
from tests.test_r811_shell_accessibility import _CONTRAST, _shell_css, _html
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.set_content(_html("overview", "en"), wait_until="domcontentloaded")
    pg.add_style_tag(content=_shell_css())
    pg.add_style_tag(content="* { color: #bbb !important; background: #ccc !important; }")
    bad = [m for m in pg.evaluate(_CONTRAST) if m["ratio"] < m["floor"]]
    print("violations under a low-contrast override:", len(bad))
    assert bad, "the contrast measurement cannot detect a violation -- it proves nothing"
    b.close()
PY
```

Expected: a non-zero violation count. A measurement that reports none under a forced
low-contrast override is measuring nothing.

- [ ] **Step 4: Commit**

```bash
git add tests/test_r811_shell_accessibility.py
git commit -F - <<'MSG'
test(u1-09b): compute contrast in the browser, and measure targets where a pointer lands

`FR-200` §Verification requires contrast computed rather than asserted, so the ratio
is derived in the page from resolved colours and the real background walked up the
ancestor chain -- not compared against a table of hex values a test remembers.

The legal cases inject the two sheets a legal page links, not the shell's three:
`workspace.css` is not among them, and injecting it would measure a document the
product never serves.

Each measurement asserts it measured something before asserting it passed; a run
over an empty node list would otherwise report as a pass.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

## Task 6: The conditional floors — `role="status"`, non-colour trust, reduced motion

**Files:**
- Modify: `tests/test_r811_shell_accessibility.py`

**Interfaces:** Consumes `_html`, `SHELL_SURFACES`, `_parse`.

**Verified at `aa62016`: no shell surface emits `role="status"`.** So an unconditional assertion
would fail, and the fix is not this slice's to make. Assert the floor **conditionally** and record
the absence, per Global Constraints.

- [ ] **Step 1: Write the failing test**

```python
#: Class fragments the shell uses for a refusal or a progress region. Kept explicit so that a
#: surface gaining one without `role="status"` fails here rather than passing by absence.
_ANNOUNCING = ("refusal", "progress", "unavailable", "empty")


@pytest.mark.parametrize("language", ["en", "ar"])
@pytest.mark.parametrize("surface", sorted(SHELL_SURFACES))
def test_a_refusal_or_progress_region_announces_itself(surface: str, language: str) -> None:
    """`FR-200`: `role="status"` for refusals and progress.

    Conditional by necessity, not by preference. At `aa62016` no shell surface emits a
    `role="status"`, and this slice changes no source file -- so an unconditional assertion here
    would be an evidence slice editing a template to make its own test pass. What it *can* prove
    is that a surface which grows an announcing region announces it, and that the absence is
    recorded rather than hidden. See the evidence document's open-finding section.
    """
    html = _html(surface, language)
    announcing = [fragment for fragment in _ANNOUNCING if f'class="{fragment}' in html]
    if not announcing:
        pytest.skip(f"{surface}/{language} renders no announcing region")
    assert 'role="status"' in html, (
        f"{surface}/{language} renders {announcing} without role=status"
    )


def test_the_role_status_absence_is_recorded_and_not_silent() -> None:
    """The finding above, pinned so it cannot be forgotten.

    If a shell surface gains `role="status"`, this fails -- and that is the signal to make
    `test_a_refusal_or_progress_region_announces_itself` unconditional and delete this case.
    """
    emitting = sorted(
        surface
        for surface in SHELL_SURFACES
        if 'role="status"' in _html(surface, "en")
    )
    assert emitting == [], (
        f"{emitting} now emit role=status: make the floor above unconditional and remove this test"
    )
```

- [ ] **Step 2: Run**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py -q -k status`
Expected: PASS, with skips on the conditional case.

- [ ] **Step 3: Commit**

```bash
git add tests/test_r811_shell_accessibility.py
git commit -F - <<'MSG'
test(u1-09b): hold the announcement floor open, and pin why it is conditional

`FR-200` requires `role="status"` for refusals and progress. No shell surface emits
one at `aa62016`, and this slice changes no source file -- so the floor is asserted
conditionally and the absence is pinned by a second test that fails the moment a
surface gains the attribute.

That pin is what stops a conditional guard from quietly becoming permanent: the day
the markup lands, the floor becomes unconditional and the pin is deleted.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

## Task 7: Make the CI browser gap visible

**Files:**
- Modify: `tests/test_r811_shell_accessibility.py`

**Interfaces:** Consumes nothing new.

Decision 1: the gap cannot be closed in scope, so it must be *legible*.

- [ ] **Step 1: Write the failing test**

```python
def test_the_browser_floors_are_not_silently_unmeasured() -> None:
    """The browser-gated floors skip in CI, and a skip is not a pass.

    CI runs a bare `uv run pytest` with no browser install step, so every `@pytest.mark.browser`
    case -- including this module's computed-contrast floor, which `FR-200` §Verification requires
    to run in a real browser -- reports `skipped` there. Closing that needs a workflow edit, and
    `.github/` is not in `RCA-010` §Scope, so this slice records the gap instead of hiding it.

    What this pins: the marker still gates a non-zero number of cases. Deleting the marker to make
    CI 'cover' them, or deleting the cases, fails here.
    """
    source = Path(__file__).read_text(encoding="utf-8")
    marked = source.count("@pytest.mark.browser")
    assert marked >= 4, (
        f"only {marked} browser-gated cases remain; the computed-contrast floor "
        "may have been removed or silently de-marked"
    )
```

- [ ] **Step 2: Run**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py -q -k unmeasured`
Expected: PASS.

- [ ] **Step 3: Full suite, both markers**

```bash
./.venv/Scripts/python.exe -m pytest tests/test_r811_shell_accessibility.py tests/test_r807_shell_quality.py -q
./.venv/Scripts/python.exe -m pytest -q          # the whole suite -- a field's meaning can break
                                                 # modules you never opened
./.venv/Scripts/python.exe -m ruff check .
uv run khepri-gov validate
```

Expected: all green. **Run the whole suite** — not just the touched modules.

- [ ] **Step 4: Commit**

```bash
git add tests/test_r811_shell_accessibility.py
git commit -F - <<'MSG'
test(u1-09b): record that the browser floors do not run in CI

A guard that cannot evaluate its input must refuse rather than report success.
CI installs no browser, so the computed-contrast floor `FR-200` §Verification
requires reports `skipped` there -- not `passed`.

`.github/` is not in `RCA-010` §Scope and the allocation block forbids widening
past `tests/`, so this slice makes the gap legible instead of closing it: the
marker is pinned against silent removal, and the evidence document carries the
gap to the owner as an open finding.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

## Task 8: The evidence document

**Files:**
- Create: `docs/superpowers/plans/2026-09-18-u1-slice-9b-evidence.md`

- [ ] **Step 1: Write it**

It must record, with commands and their real output:

1. **Which floors run in CI and which do not** — the static seven versus the browser-gated ones,
   with the skip count from a no-browser run.
2. **The `role="status"` absence** as an open finding, naming the follow-on slice it needs.
3. **The mutation results** — one per floor, each with the mutant, the failure it produced, and
   `git diff` proving zero deletions after restore.
4. **The two extent assertions** and why the legal one is a sibling rather than a widening.
5. **The unenforced-in-CI gap** (Decision 1), stated plainly as needing an owner amendment naming
   `.github/`.

- [ ] **Step 2: CodeScene pre-flight, against a fetched base**

```bash
git fetch origin main           # a stale base returns empty results and a meaningless pass
```

Then `mcp__plugin_codescene_codescene__analyze_change_set`. Expected: 10.00 on the new module, no
decline on `test_r807_shell_quality.py` (10.00 at `aa62016`).

- [ ] **Step 3: Commit and open the PR**

```bash
git add docs/superpowers/plans/2026-09-18-u1-slice-9b-evidence.md
git commit -F - <<'MSG'
docs(u1-09b): the slice's evidence, and the gap it could not close

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
git push -u origin claude/u1-slice-9b-accessibility-evidence
```

The PR body states the scope, the authority, the two open findings (`role="status"`, CI browser),
and ends with the attribution line.

---

## Self-review against `FR-200`

| `FR-200` floor | Task | Browser? |
|---|---|---|
| Visible focus on every tab stop, incl. scrollable regions | 5 (target/size cases share the harness) | yes |
| Focus order follows document order, no positive `tabindex` | 3 | no |
| Semantic landmarks with meaningful unique accessible names | 3 | no |
| Exactly one `h1`, no skipped heading level | 1 (legal), existing `r807` case (shell) | no |
| Labels associated with controls, never a placeholder | 4 | no |
| ARIA only where native semantics are insufficient | 3 (the sole-`main` reasoning) | no |
| `role="status"` for refusals and progress | 6 — **conditional, open finding** | no |
| Non-colour differentiation for every trust state | 6 | no |
| Targets ≥ 44px on the element a pointer lands on | 5 | yes |
| Contrast computed rather than asserted | 5 — **does not run in CI** | yes |
| `prefers-reduced-motion` fills a progress track | 5 harness (`emulate_media`) | yes |
| Text scales to 200% without loss | 5 | yes |
| Errors announced, not only coloured | 6 | no |

**Known gaps, both deliberate and both recorded:** the computed-contrast floor does not execute in
CI (Decision 1), and `role="status"` is asserted conditionally because no surface emits it
(Task 6). Neither is closable inside `tests/`.
