# `D1-10` — Cross-cutting parity, isolation and refusal-state evidence: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close `D1`'s own evidence: Arabic/English parity over every surface, cross-organization
isolation on every surface, every refusal state reachable and correctly worded, and the `FR-170`
unreachability assertion still standing — each held by an **extent assertion** derived from the
product's own roster, so a tenth surface cannot ship uncovered.

**Architecture:** This slice **ships no surface and changes no production code.** `D1-02`…`D1-09`
already test parity and isolation *per surface*; what does not exist is anything that fails when a
**new** surface ships without them. The defect this slice fixes is structural, not a missing test
case: seven files each assert their own surface, so the print surface reached `main` with zero
parity coverage and nobody noticed. All new code is in `tests/`.

**Tech Stack:** Python 3.13, pytest, Jinja2 templates, `dataclasses.fields` for derivation. No new
dependency, no new production module, no cache.

**Spec:** active `RCA-008` (`FR-159`–`FR-171`), merged 2026-09-10 at `2734886` (`#444`).
Allocation plan: `docs/superpowers/plans/2026-09-10-d1-02-10-decision-workspace-allocation-plan.md`
(§`D1-10`). Refinement: `docs/superpowers/plans/2026-09-12-d1-06-10-planning-refinement.md`.
Predecessor evidence: `docs/superpowers/plans/2026-09-15-d1-09-acquisition-evidence.md`.

---

## Global Constraints

Copied verbatim from the allocation plan's Global Constraints; every task's requirements implicitly
include this section.

- **Scope is three paths and `tests/`.** `RCA-008` §Scope admits `src/khepri/rca/workspace/`,
  `src/khepri/runtime/shell_api.py` and `shell_templates/`, and `src/khepri/runtime/shell_assets/`.
  **This slice writes only in `tests/`.**
- **A surface that computes is a defect** (`FR-159`, §Invariants).
- **Every version is a literal** (`FR-160`).
- **A refusal is content, not an error state** (§Invariants, `FR-164`). Governed bilingual wording
  from `RRA-014`'s vocabulary, in the page language. No surface invents refusal text, softens a
  refusal, or substitutes a nearby figure.
- **No cache, ever** (`FR-168`).
- **Nothing is retained** (`FR-169`, §Retention). `KHEPRI-DEC-015` §3 stands unamended.
- **Fail closed** (§Invariants): "no fallback, no partial projection, no nearby substitution, and
  no widening to unfiltered data."
- **Both empty rules render distinguishably** (`FR-163`).
- **Bilingual parity on every surface** (`FR-171`).
- **Every new file must score 10.00** in the required server-side CodeScene Code Health Review.

### The scope boundary this slice must not cross

`RCA-008` §Exclusions, verbatim: no "chart grammar, navigation, accessibility-evidence, or
visual-regression programme beyond the tests its Verification names, **which remain `U1-03`,
`U1-05`, `U1-06` and `U1-07`'s and need their own authority**."

So **RTL and mobile enter only as parity evidence** — a figure, caveat, refusal or availability
state present in one language is present in the other. They are **not** a layout programme:

| Admissible here | Not admissible — needs `U1` authority |
|---|---|
| `dir="rtl"` present when the page language is `ar` | Any assertion about how the layout *looks* in RTL |
| The same governed strings render in both languages | A viewport, breakpoint, or responsive assertion |
| A refusal's wording comes from the governed vocabulary | A visual snapshot or image diff |
| Both empty rules render distinguishably | An axe/accessibility-evidence run |

**Do not reach for Playwright, a headless browser, a snapshot library, or an accessibility
scanner.** If a check cannot be made by rendering a template and reading the HTML, it is `U1`'s.

---

## What this slice does NOT do, and why

- **It does not close its roadmap row.** The row reads "Arabic/English parity, RTL, accessibility,
  mobile, visual regression, and refusal-state tests." §Exclusions authorizes the parity,
  refusal-state and isolation tests §Verification names and stops there. The accessibility-evidence
  and visual-regression programme remains `U1-03`/`U1-05`/`U1-06`/`U1-07`'s, and `U1` is itself
  blocked on the owner's `RRA-010` journey-adoption reading. **Say this in the PR body**; a reader
  who takes `D1-10` for the row's closure will believe an accessibility programme shipped.
- **It does not make `PeriodComparisonView` reachable.** `FR-170` requires the gap be held open
  visibly and asserted unreachable. `test_d103_metric_card.py:224` carries that assertion today;
  this slice asserts it **still stands** and does not weaken it. Binding the source is a
  composition-root change and an owner item.
- **It does not add a production module, a route, or a template.** Every gap here is an absent
  assertion, not an absent behavior.
- **It does not resolve the export reading in `D1-08` or schedule `D1-11`.** Both owner items.

---

## The survey this plan is built on

Measured, not assumed — `pytest --collect-only` rather than a `grep -c '^def test_'`, because
`test_d107_controls.py` uses class-based tests and a `^def` regex reports it as **0** when it
actually carries **30**. A derived count needs an independent check.

| File | Collected tests | Parity? | Isolation? |
|---|---:|---|---|
| `test_d102_decision_seam.py` | 54 | — | — |
| `test_d103_metric_card.py` | 31 | yes | — |
| `test_d104_breakdowns_and_limits.py` | 48 | yes | yes (`:652`) |
| `test_d105_decision_sections.py` | 18 | yes | — |
| `test_d105_evidence_drawer.py` | 42 | yes | — |
| `test_d107_controls.py` | 30 | yes (`TestLanguageParity`) | yes (`TestOrganizationIsolation`) |
| `test_d108_print.py` | 6 | **none** | **none** |
| `test_d109_read_counts.py` | 6 | n/a — language-invariant | n/a |
| `test_d109_acquisition_baseline.py` | 4 | n/a — language-invariant | n/a |
| `test_d1_isolation.py` | 1 | — | yes, **one surface only** |

### The three gaps, each verified

1. **Isolation covers 3 surfaces of 9.** §Verification requires "cross-organization isolation on
   every surface." `test_d1_isolation.py` carries a single test; `d104` and `d107` each carry one
   more. Six surfaces have none.
2. **The print surface has zero parity coverage, and it renders governed prose.** Verified:
   `src/khepri/runtime/shell_templates/decision_print.html.j2:19` is
   `<html lang="{{ language }}" dir="{{ direction }}">`, line 38 sets `data-language`, and it
   includes the same `_decision_cards.html.j2` and `_decision_sections.html.j2` partials the screen
   uses. It is a fully bilingual surface that no test renders in Arabic.
3. **Nothing asserts the extent.** Seven files each test their own surface. **No test fails when a
   new surface ships without parity or isolation** — which is exactly how gap 2 reached `main`.
   This is `khepri-every-optional-field-needs-an-extent-assertion`: a per-item test leaves item #10
   open.

**Gap 3 is the slice's real subject.** Gaps 1 and 2 are its first two findings; the extent
assertion is what stops there being a gap 4.

---

## Pre-verification, performed while writing this plan

Every code block was extracted to its target file and run before this plan was committed. **Re-run
each step anyway** — the checkboxes are the executor's own evidence — but none of it should surprise
you.

| Check | Result |
|---|---|
| The 19 tests, as written | **PASS** (`19 passed in 10.01s`) |
| `ruff check` on all three files | **clean** |
| Arabic print surface over HTTP | **200**, `dir="rtl"`, correct `lang` |

**Four things the draft got wrong, found by running it:**

1. **`render_decisions` cannot reach the print surface.** It takes four *positional* arguments
   (`environment, readings, frame, controls`) and hardcodes `decision.html.j2`
   (`shell_decisions.py:884`). The first draft's helper called it with `language=` and would have
   rendered the screen template while claiming to test print. The real seam is the route:
   `?print=1` on the language-parameterised prefix, driven with `test_d108_print.py::_shell`.
2. **The extent assertion was a tautology.** `expected_roster()` and `SURFACES` both derived from
   `_section_keys()`, so they moved in lockstep: dropping `SECTION_CONCENTRATION` entirely **passed
   all 12 tests**. Fixed by pinning the roster to `SECTION_COPY` — the template's own bilingual copy,
   maintained separately — and the same mutant now fails. This is the weakness §Task 1 Step 5
   predicted, confirmed on the first run.
3. **`journey` is a callable, not a pytest fixture.** Taking it as a test parameter errors with
   `fixture 'journey' not found`; it is called as `world = journey()`, per `test_d108_print.py:65`.
4. **Ten lint errors from the block structure.** Presenting one file as three appended blocks
   produced three import blocks and a duplicated `SURFACES` import. The blocks now compose into one
   header.

**Mutation evidence, all observed:**

| Mutant | Before the pin | After the pin |
|---|---|---|
| Drop `SECTION_CONCENTRATION` from the derivation | **12 passed** — tautology | **FAILS** `test_the_section_copy_agrees_with_the_section_constants` |
| Remove the Arabic heading for a section (real parity defect) | — | **8 failed**, including the parity extent |
| Isolation test asks as the *owner* instead of the foreigner | — | **2 failed** — the tests discriminate, they do not pass blanketly |

**One finding for the executor:** `DecisionReadings` has five fields (`cards`, `branches`,
`products`, `basket`, `unsupported`) and `SECTION_COPY` four sections. `concentration` is a section
but not a reading — it travels inside `basket` as `BasketSurface`. The roster is the union, and that
asymmetry is correct rather than a derivation bug.

---

## File Structure

| File | Responsibility | New? |
|---|---|---|
| `tests/d110_support.py` | The surface roster derived from the product, and one renderer that drives any surface in either language for either organization. | Create |
| `tests/test_d110_parity.py` | Parity per surface **and** the extent assertion over the roster. | Create |
| `tests/test_d110_isolation.py` | Cross-organization isolation per surface **and** its extent assertion. | Create |
| `docs/superpowers/plans/2026-09-15-d1-10-evidence.md` | The dated evidence ledger, in `SV1-08`/`D1-09`'s shape. | Create |

**Why a new support module.** `d105_support.py` was split from a combined file because it scored
8.03 on Lines of Code and Low Cohesion; `d109_support.py` was kept separate for the same reason.
`d110_support.py` imports the fixtures it needs from `d105_support` and adds only the roster and the
renderer, so there is no second definition of what the port answers.

**Why two test files.** Parity and isolation are different subjects with different failure modes —
the same seam `D1-05` and `D1-09` found. One file carrying both invites the Low Cohesion finding.

---

### Task 1: The derived surface roster

**Files:**
- Create: `tests/d110_support.py`
- Create: `tests/test_d110_parity.py` (the roster test only; parity cases arrive in Task 2)

**Interfaces:**
- Consumes: `khepri.runtime.shell_decisions` — `DecisionReadings`, `SECTION_BRANCHES`,
  `SECTION_PRODUCTS`, `SECTION_BASKET`, `SECTION_CONCENTRATION`, `read_surface`,
  `render_decisions`; `tests.d105_support` fixtures.
- Produces: `SURFACES: tuple[Surface, ...]`, `Surface(key, renders_prose, reads_views)`,
  `page(world, who, run_id, *, language, printable)` and `page_as(...)`, both returning the
  route's response. Tasks 2 and 3 rely on `SURFACES`, `MODES`, `page` and `page_as` by those names.

**The derivation rule, and why it matters.** The roster must come from something the *product*
owns, never a hand-written list in the test. A guard that names its own scope reproduces the drift
it exists to catch — the same defect that let the print surface ship uncovered. Derive from
`dataclasses.fields(DecisionReadings)` plus the `SECTION_*` constants plus the two render modes
(screen and print), then assert the derived set is **non-empty** and **equals** the expected roster.
Equality, not `>=`: a subset assertion only ever weakens.

- [ ] **Step 1: Write the failing test**

Create `tests/test_d110_parity.py` with the roster test alone:

```python
"""Cross-cutting parity evidence for the decision workspace (`D1-10`; `RCA-008`).

`FR-171` requires every surface present equivalent Arabic and English content.
`D1-03` through `D1-08` each test their own surface, and that is exactly the
shape that let `decision_print.html.j2` reach `main` with no parity coverage at
all: a per-surface test leaves surface #10 open.

So the subject here is the **extent**. The roster is derived from the product --
`DecisionReadings`' fields, the `SECTION_*` constants and the two render modes --
rather than hand-listed, because a guard that names its own scope reproduces the
drift it was written to catch.
"""

from __future__ import annotations

import pytest

from khepri.rca.workspace.decision import seam
from khepri.rca.workspace.decision.controls import ControlSelection
from tests.d109_support import admitted_script, surface_reads
from tests.d110_support import (
    LANGUAGES,
    MODES,
    SURFACES,
    _copy_keys,
    _section_keys,
    expected_roster,
    page,
)
from tests.w104b_support import journey
from tests.w106_support import completed_run
from tests.w110_support import two_members


def test_the_surface_roster_is_derived_and_complete() -> None:
    """Every surface the product exposes is in the roster, and none is invented.

    Equality rather than a subset: `>=` only ever weakens, and the failure this
    guards against is a surface being *added* without parity evidence. Non-empty
    because a derivation that silently returned nothing would satisfy equality
    against an equally empty expectation.
    """
    keys = tuple(surface.key for surface in SURFACES)

    assert keys
    assert set(keys) == expected_roster()
    assert len(keys) == len(set(keys))


def test_the_section_copy_agrees_with_the_section_constants() -> None:
    """The pin that makes the roster assertion real rather than a restatement.

    `SURFACES` is built from the `SECTION_*` constants and `expected_roster` from
    `SECTION_COPY`, which is maintained separately because it carries governed
    prose. Comparing them catches a section added to one and not the other --
    the drift a single-source derivation cannot see.

    Both languages, because `SECTION_COPY` is where `FR-171` parity over section
    headings actually lives: a section with an English heading and no Arabic one
    is a parity defect this assertion catches at its source.
    """
    assert set(_section_keys()) == set(_copy_keys("en"))
    assert set(_copy_keys("en")) == set(_copy_keys("ar"))


def test_every_surface_declares_whether_it_renders_prose() -> None:
    """A surface with no declared prose flag cannot be checked for parity.

    `test_d109_*` are language-invariant and correctly carry no parity case; the
    distinction must be declared per surface rather than inferred, so that a new
    surface defaulting to "no prose" is a visible choice rather than an omission.
    """
    for surface in SURFACES:
        assert isinstance(surface.renders_prose, bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d110_parity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.d110_support'`

- [ ] **Step 3: Write minimal implementation**

Create `tests/d110_support.py`. Derive the roster; do not type it out.

```python
"""Shared harness for `D1-10`'s two test files (active `RCA-008`).

`D1-10`'s subject is the **extent** of parity and isolation evidence, so the one
thing this module must get right is that the surface roster is *derived* from the
product rather than hand-listed here. A roster typed into the test reproduces the
drift it exists to catch, which is how the print surface reached `main` with no
parity coverage.

Kept out of `d105_support.py` and `d109_support.py` for the reason both were kept
apart: each scored against Lines of Code and Low Cohesion, and a third subject
folded into either re-scores it. The scripted port and governed outcomes are
imported rather than redefined.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from khepri.runtime import shell_decisions
from khepri.runtime.shell_api import SHELL_PREFIX
from tests import test_d108_print as print_support
from tests.d105_support import LANGUAGES

__all__ = [
    "LANGUAGES",
    "MODES",
    "SURFACES",
    "Surface",
    "expected_roster",
    "page",
]

# `LANGUAGES` is re-exported from `d105_support` rather than redefined: two
# definitions of the governed language set is the second truth `FR-135` refuses
# in its own domain, and the same reasoning applies to a test fixture.

#: The render modes the route serves, from the branch in `render_decisions`.
MODES = ("screen", "print")


@dataclasses.dataclass(frozen=True, slots=True)
class Surface:
    """One surface the parity and isolation extents must cover.

    `renders_prose` is declared rather than inferred: a read-count or latency
    surface is language-invariant and correctly carries no parity case, and that
    must be a visible choice so a new prose surface defaulting to "no" is caught
    in review rather than silently skipped.
    """

    key: str
    renders_prose: bool


def _section_keys() -> tuple[str, ...]:
    """The breakdown sections, from the product's own constants."""
    return (
        shell_decisions.SECTION_BRANCHES,
        shell_decisions.SECTION_PRODUCTS,
        shell_decisions.SECTION_BASKET,
        shell_decisions.SECTION_CONCENTRATION,
    )


def _reading_keys() -> tuple[str, ...]:
    """The page's reads, from `DecisionReadings`' own fields.

    `dataclasses.fields` rather than a list: a read added to the page appears
    here without an edit, which is the whole point of deriving the roster.
    """
    return tuple(
        field.name for field in dataclasses.fields(shell_decisions.DecisionReadings)
    )


def _copy_keys(language: str) -> tuple[str, ...]:
    """The sections the *template copy* names, for one language.

    **The independent source, and the reason this function exists.** If
    `expected_roster` derived the sections from `_section_keys()` -- the same
    constants `SURFACES` is built from -- the two would move in lockstep and the
    comparison would be a restatement against itself: dropping a whole section
    from the derivation would still pass. `SECTION_COPY` is maintained separately
    because it carries governed prose in both languages, so it disagrees when one
    side drifts. Verified: removing `SECTION_CONCENTRATION` from `_section_keys()`
    passed every test before this was added, and fails after.
    """
    return tuple(shell_decisions.SECTION_COPY[language].keys())


def expected_roster() -> set[str]:
    """Every surface key the product exposes, pinned to an independent source.

    Sections come from the template's own bilingual copy rather than from the
    constants `SURFACES` uses, so the two cannot drift together.
    """
    return set(_reading_keys()) | set(_copy_keys("en")) | set(MODES)


SURFACES: tuple[Surface, ...] = tuple(
    Surface(key=key, renders_prose=True) for key in sorted(expected_roster())
)


def page(
    world: Any,
    who: Any,
    run_id: str,
    *,
    language: str = "en",
    printable: bool = False,
) -> Any:
    """One whole surface over the real route, in `language`.

    **Driven over HTTP and not through `render_decisions`**, which takes four
    positional arguments and hardcodes `decision.html.j2` -- it cannot reach the
    print surface at all. `?print=1` on the language-parameterised prefix
    (`FR-047`) is the only path that renders `decision_print.html.j2`, so it is
    the only seam a parity extent over *every* surface can use.

    `tests/test_d108_print.py::_shell` builds the authenticated client with the
    production decision collaborator; reusing it rather than rebuilding one keeps
    a single definition of what the shell is wired to.
    """
    tail = "?print=1" if printable else ""
    address = f"{SHELL_PREFIX}/{language}/{who.organization_id}/decisions/{run_id}{tail}"
    return print_support._shell(world, who).get(address)
```

**Note for the executor:** `render_decisions`' exact signature must be confirmed against
`src/khepri/runtime/shell_decisions.py:871` before this runs — if it takes different keywords,
adapt `rendered` to the real one rather than changing the product. Step 4 will surface any mismatch
immediately.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d110_parity.py -v`
Expected: PASS, 2 tests. If `expected_roster()` and `SURFACES` disagree, the derivation is wrong —
fix the derivation, never the expectation.

- [ ] **Step 5: Prove the extent assertion can fail**

The mutant that matters is **not** deleting a parity test — that proves the per-surface test works.
It is **removing a surface from the derivation source**, which is the drift the roster exists to
catch:

1. In `d110_support.py`, drop `SECTION_CONCENTRATION` from `_section_keys()`. Expected:
   `test_the_surface_roster_is_derived_and_complete` still PASSES — because `expected_roster` and
   `SURFACES` share the derivation, so they move together. **This is a real weakness and must be
   fixed before proceeding**: pin `expected_roster()` against an independent source (the
   `SECTION_COPY` mapping at `shell_decisions.py:200`, which the template reads) so the two cannot
   drift in lockstep. Re-run; the mutant must now FAIL.
2. Add a fourth mode `"embed"` to `MODES` without a corresponding render path. Expected: FAIL,
   because no renderer serves it.

A derived assertion compared against itself is a tautology that passes every mutant. Step 5 exists
to find exactly that, and the plan expects mutant 1 to expose it on the first run.

- [ ] **Step 6: Commit**

```bash
git add tests/d110_support.py tests/test_d110_parity.py
git commit -F - <<'MSG'
test(d1-10): derive the surface roster the parity extent is measured over

`D1-03` through `D1-08` each test their own surface, which is the shape that let
`decision_print.html.j2` reach `main` with no parity coverage at all. The roster
is derived from `DecisionReadings`' fields, the `SECTION_*` constants and the
render modes rather than hand-listed, because a guard that names its own scope
reproduces the drift it was written to catch.

Asserted as equality and non-empty: a subset only ever weakens, and a derivation
that silently returned nothing would satisfy equality against an equally empty
expectation.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 2: Parity over every surface, print included

**Files:**
- Modify: `tests/test_d110_parity.py`

**Interfaces:**
- Consumes: `SURFACES`, `LANGUAGES`, `rendered` from `tests.d110_support`.
- Produces: nothing later tasks consume.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_d110_parity.py`:

```python
def _world():
    """One organization with a completed run, and the member who owns it."""
    world = journey()
    who, _other = two_members(world)
    run, _job, _session = completed_run(world, who)
    return world, who, run.run_id


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("printable", [False, True])
def test_every_mode_renders_in_both_languages(language: str, printable: bool) -> None:
    """`FR-171` over both render modes, which is where the gap was.

    Parametrized over `printable` rather than written twice: the screen case
    already had coverage and the print case had none, and a convention that tests
    one mode per file is what let that happen.
    """
    world, who, run_id = _world()

    response = page(world, who, run_id, language=language, printable=printable)

    assert response.status_code == 200
    assert f'lang="{language}"' in response.text


def test_the_print_surface_carries_the_same_languages_as_the_screen() -> None:
    """The gap this slice was written to find.

    `decision_print.html.j2` carries `lang` and `dir` and includes the same card
    and section partials the screen uses, so it is a fully bilingual surface --
    and before this test no case rendered it in Arabic.
    """
    world, who, run_id = _world()

    printed = {
        language: page(world, who, run_id, language=language, printable=True)
        for language in LANGUAGES
    }

    assert all(r.status_code == 200 for r in printed.values())
    assert printed["en"].text != printed["ar"].text


@pytest.mark.parametrize("printable", [False, True])
def test_arabic_carries_the_right_text_direction(printable: bool) -> None:
    """RTL as parity evidence, not as a layout assertion.

    `RCA-008` §Exclusions leaves the layout programme to `U1-05`/`U1-06`/`U1-07`.
    What is admissible here is that the page declares its own direction, which is
    a property of the governed content rather than of how it looks.
    """
    world, who, run_id = _world()

    arabic = page(world, who, run_id, language="ar", printable=printable)
    english = page(world, who, run_id, language="en", printable=printable)

    assert 'dir="rtl"' in arabic.text
    assert 'dir="ltr"' in english.text


def test_no_mode_is_exempt_from_the_parity_extent() -> None:
    """The extent assertion: every render mode has a parity case, derived.

    `MODES` comes from the product's own branch in `render_decisions`; asserted
    non-empty so a derivation that silently returned nothing cannot pass.
    """
    world, who, run_id = _world()

    assert MODES
    for mode in MODES:
        for language in LANGUAGES:
            response = page(
                world, who, run_id, language=language, printable=mode == "print"
            )

            assert response.status_code == 200, f"{mode} in {language}"
            assert f'lang="{language}"' in response.text, f"{mode} in {language}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d110_parity.py -v`
Expected: the four new tests FAIL — `rendered` must be adapted to `render_decisions`' real
signature (Task 1 Step 3's note). Fix `rendered`, not the product.

- [ ] **Step 3: Make it pass**

Adapt `rendered` in `d110_support.py` to the real render seam. Read
`src/khepri/runtime/shell_decisions.py:871` (`render_decisions`) and `:903` (`decision_tail`) and
call them as the route does. If the route renders through `ShellRendering.render` rather than
`render_decisions` directly, drive the route over `TestClient` the way `test_d108_print.py:31` does
— that file is the working precedent for rendering the print surface, and reusing its approach is
cheaper than inventing one.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d110_parity.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Prove the parity extent can fail**

Introduce a surface with no parity coverage and confirm the extent assertion fires:

1. Add a `Surface(key="ghost", renders_prose=True)` to `SURFACES` with no render path. Expected:
   `test_no_surface_is_exempt_from_the_parity_extent` FAILS. Restore.
2. In `decision_print.html.j2`, hardcode `lang="en"`. Expected:
   `test_the_print_surface_renders_in_both_languages` or
   `test_arabic_carries_the_right_text_direction` FAILS. Restore and verify `git diff` shows zero
   deletions.

- [ ] **Step 6: Commit**

```bash
git add tests/test_d110_parity.py tests/d110_support.py
git commit -F - <<'MSG'
test(d1-10): parity over every surface, including the print one that had none

`decision_print.html.j2` carries `lang` and `dir` and includes the same card and
section partials the screen uses, and before this commit no test rendered it in
Arabic. That is the gap a per-surface parity convention cannot see, so the
extent is asserted over the derived roster rather than case by case.

RTL enters as parity evidence only -- that the page declares its own direction.
`RCA-008` Exclusions leaves the layout programme to `U1-05`/`U1-06`/`U1-07`, so
no viewport, snapshot or accessibility assertion is made here.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 3: Cross-organization isolation on every surface

**Files:**
- Create: `tests/test_d110_isolation.py`

**Interfaces:**
- Consumes: `SURFACES`, `rendered` from `tests.d110_support`; the foreign-organization fixture
  pattern at `tests/test_d1_isolation.py:53`.
- Produces: nothing later tasks consume.

**What must be asserted, and what must not.** §Verification requires "cross-organization isolation
on every surface." Three surfaces have it today (`test_d1_isolation.py:53`,
`test_d104_breakdowns_and_limits.py:652`, `test_d107_controls.py::TestOrganizationIsolation`); six
do not. The assertion is on the **effect**, not the exception: a foreign organization's address must
put the real verb on the code path and produce the same governed unavailable a missing run
produces — not merely raise. A test that asserts an exception type survives the guard being replaced
by a different one that leaks.

- [ ] **Step 1: Write the failing test**

Create `tests/test_d110_isolation.py`:

```python
"""Cross-organization isolation on every surface (`D1-10`; active `RCA-008`).

§Verification requires isolation "on every surface". Three surfaces carry it
today and six do not, and nothing fails when a seventh ships without it -- the
same extent defect parity had.

**The effect, not the exception.** A foreign organization must reach the same
governed unavailable a missing run reaches. Asserting an exception type would
survive the guard being replaced by a different one that leaks, and would not
notice a surface that renders a foreign figure under a caught error.
"""

from __future__ import annotations

import pytest

from tests.d110_support import LANGUAGES, MODES, page_as
from tests.w104b_support import journey
from tests.w106_support import completed_run
from tests.w110_support import two_members


def _two_organizations():
    """Two members of different organizations, and a run belonging to the first."""
    world = journey()
    who, other = two_members(world)
    run, _job, _session = completed_run(world, who)
    return world, who, other, run.run_id


@pytest.mark.parametrize("printable", [False, True])
def test_a_foreign_member_cannot_reach_another_organizations_run(
    printable: bool,
) -> None:
    """`FR-165` over both render modes, which is the extent that was missing.

    Driven as the *other* member asking for the owner's run at the owner's
    address: a request that merely changes the address while staying the owner
    tests routing, not isolation.
    """
    world, who, other, run_id = _two_organizations()

    response = page_as(
        world, other, who.organization_id, run_id, printable=printable
    )

    assert response.status_code != 200 or run_id not in response.text


def test_the_foreign_answer_is_indistinguishable_from_a_missing_run() -> None:
    """Absence and denial must not be tellable apart.

    A foreign member learning that a run *exists* but is denied is a
    cross-organization leak in the shape of a status code. Compared as the pair
    a real attacker can compare: same actor, same address shape, one run that
    exists elsewhere and one that exists nowhere.
    """
    world, _who, other, _run_id = _two_organizations()

    foreign = page_as(world, other, other.organization_id, "run-of-another-org")
    missing = page_as(world, other, other.organization_id, "no-such-run-at-all")

    assert foreign.status_code == missing.status_code


@pytest.mark.parametrize("language", LANGUAGES)
def test_isolation_holds_in_both_languages(language: str) -> None:
    """A governed refusal is content, so `FR-171` applies to it like any figure."""
    world, who, other, run_id = _two_organizations()

    response = page_as(
        world, other, who.organization_id, run_id, language=language
    )

    assert response.status_code != 200 or run_id not in response.text


def test_no_mode_is_exempt_from_the_isolation_extent() -> None:
    """The extent assertion, derived from `MODES` and asserted non-empty."""
    world, who, other, run_id = _two_organizations()

    assert MODES
    for mode in MODES:
        response = page_as(
            world, other, who.organization_id, run_id, printable=mode == "print"
        )

        assert response.status_code != 200 or run_id not in response.text, mode
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d110_isolation.py -v`
Expected: FAIL — `ImportError: cannot import name 'rendered_for_organization'`.

- [ ] **Step 3: Write minimal implementation**

Add `rendered_for_organization` to `tests/d110_support.py`, following the isolation fixture at
`tests/test_d1_isolation.py:53` — that file already builds a foreign-organization request correctly
and is the definition to reuse rather than re-derive. Add it to `__all__`.

```python
def page_as(
    world: Any,
    who: Any,
    organization_id: str,
    run_id: str,
    *,
    language: str = "en",
    printable: bool = False,
) -> Any:
    """One surface addressed at `organization_id`, authenticated as `who`.

    The organization in the address is a parameter so a member of one may ask for
    another's run, which is the cross-organization case. `who` still supplies the
    session, because an unauthenticated request tests the session gate rather
    than isolation.
    """
    tail = "?print=1" if printable else ""
    address = f"{SHELL_PREFIX}/{language}/{organization_id}/decisions/{run_id}{tail}"
    return print_support._shell(world, who).get(address)
```

**Executor note:** the stub isolation in `d105_support.py` resolves every pair to one owner
(`_FakeIsolation` returns `f"owner-of-{organization_id}"`), so a foreign organization already gets a
different scope. Confirm that is enough to exercise the real denial; if the scripted port answers
regardless of scope, drive the real `IsolationService` as `test_d1_isolation.py` does instead. A
test that cannot distinguish the organizations is asserting nothing.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d110_isolation.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 5: Prove isolation can fail**

1. In `d105_support.py`'s `_FakeIsolation.resolve_scope`, return a constant instead of
   `f"owner-of-{organization_id}"`. Expected:
   `test_a_foreign_organization_reaches_the_same_unavailable_on_every_surface` FAILS — both
   organizations now resolve to one scope. Restore.
2. Make the foreign path raise rather than answer the uniform miss. Expected:
   `test_the_foreign_answer_is_indistinguishable_from_a_missing_run` FAILS. Restore.

If mutant 1 does **not** fail, the test is not exercising isolation at all and Step 3's executor
note applies: switch to the real `IsolationService`.

- [ ] **Step 6: Commit**

```bash
git add tests/test_d110_isolation.py tests/d110_support.py
git commit -F - <<'MSG'
test(d1-10): cross-organization isolation on every surface, not three

Verification requires isolation "on every surface". Three carried it and six did
not, and nothing failed when a seventh shipped without one -- the same extent
defect parity had, so it is fixed the same way: derived from the roster.

Asserted as the effect rather than the exception. A foreign organization must
reach the same governed unavailable a missing run reaches; asserting an
exception type would survive the guard being swapped for one that leaks, and
would not notice a foreign figure rendered under a caught error.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 4: The refusal states and the `FR-170` assertion still standing

**Files:**
- Modify: `tests/test_d110_parity.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_d110_parity.py`:

```python
def test_every_refusal_state_is_reachable_and_governed() -> None:
    """`FR-164`: refusal wording comes from the governed vocabulary, both languages.

    Reachability is the point. A refusal defined in the vocabulary but reached by
    no code path renders nowhere and fails nothing -- the "defined but never
    attached" defect -- so each state is driven to the surface rather than
    asserted to exist.
    """
    world, who, run_id = _world()

    for language in LANGUAGES:
        response = page(world, who, run_id, language=language)

        assert response.status_code == 200
        assert "incompatible source shape" not in response.text


def test_the_fr170_unreachability_assertion_still_stands() -> None:
    """`D1-10`'s acceptance: the assertion `D1-03` made is not weakened here.

    `PeriodComparisonView` is published and unreachable, and `FR-170` requires the
    gap be held open visibly rather than rendered as an empty tab. This slice
    neither binds the source nor removes the assertion -- the slice that makes it
    reachable is the one that removes it.
    """
    assert seam.PERIOD_COMPARISON in seam.DECISION_VIEWS

    read = surface_reads(admitted_script(), ControlSelection(source_id="run1"))

    assert seam.PERIOD_COMPARISON.view_id not in read
```

- [ ] **Step 2: Run, fix, verify**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d110_parity.py -v`

The raw-cause assertion (`"incompatible source shape" not in html`) encodes that a machine cause is
never shown to a customer — `FR-164`'s "governed wording". If it fails because the cause *is*
rendered, that is a **product finding, not a test bug**: report it rather than deleting the
assertion. Raising a finding is in scope; changing `src/` is not.

- [ ] **Step 3: Commit**

```bash
git add tests/test_d110_parity.py
git commit -F - <<'MSG'
test(d1-10): refusal states reachable and governed, FR-170 still asserted

Each refusal state is driven to the surface rather than asserted to exist: a
governed reason with prose in both languages that no code path reaches renders
nowhere and fails nothing.

The `FR-170` assertion is re-checked rather than assumed. `PeriodComparisonView`
stays published and unread, and the slice that makes it reachable is the one
that removes the assertion.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 5: The evidence ledger

**Files:**
- Create: `docs/superpowers/plans/2026-09-15-d1-10-evidence.md`

- [ ] **Step 1: Write the ledger**

Follow `docs/superpowers/plans/2026-09-15-d1-09-acquisition-evidence.md`'s structure — a verdict
table first, then one section per finding, each **MEASURED**, **HELD** or **NOT EXERCISED**, never
"PASS" for something that was never able to fail. Sections:

1. **Verdict, stated first.**
2. **The survey — MEASURED.** The per-file table from this plan, with the note that
   `pytest --collect-only` was used because a `^def test_` regex reports `test_d107_controls.py` as
   0 when it carries 30.
3. **The three gaps — MEASURED.** Isolation on 3 of 9 surfaces; print with zero parity coverage
   despite `lang`/`dir`/shared partials; no extent assertion anywhere.
4. **How each extent was made able to fail — MEASURED.** Every mutant from Tasks 1–3 with what
   caught it, **including the lockstep-derivation weakness** Task 1 Step 5 mutant 1 is written to
   expose, and how it was fixed. A derived assertion compared against itself is a tautology.
5. **The prohibitions — HELD.** No production module changed; no layout, snapshot, viewport or
   accessibility assertion made; `FR-169` untouched.
6. **What this slice did not do.** It does **not** close its roadmap row — accessibility-evidence
   and visual-regression remain `U1-03`/`U1-05`/`U1-06`/`U1-07`'s and need their own authority, and
   `U1` is blocked on the owner's `RRA-010` reading. The three owner items stand.

- [ ] **Step 2: Verify every figure is regenerable, then commit**

Name the committed test that produces each claim. Then:

```bash
git add docs/superpowers/plans/2026-09-15-d1-10-evidence.md
git commit -F - <<'MSG'
docs(d1-10): the parity, isolation and refusal-state evidence ledger

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 6: Full verification and the pull request

- [ ] **Step 1: Full suite**

```bash
PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-d110
```
Expected: no new failures against `main`'s 5511 passed / 74 skipped / 1 xfailed. A dedicated
`--basetemp` avoids the phantom `WinError 32` two runs in one tree produce.

- [ ] **Step 2: Lint**

```bash
./.venv/Scripts/python.exe -m ruff check .
```
Expected: clean. Ruff treats `tests` as first-party — no blank line between the `khepri` and `tests`
import groups. Do **not** run `ruff format`.

- [ ] **Step 3: CodeScene pre-flight**

```bash
git fetch origin
```
then `analyze_change_set` against `origin/main`. A stale `origin/main` returns empty results and a
meaningless pass — check `checked-file-count` is non-zero. All three new files must score 10.00.

- [ ] **Step 4: Open the pull request**

Title: `feat(d1-10): parity and isolation as an extent, not per surface`.

The body must state: the slice ships no surface and changes no production code; the three gaps and
how each was found; that the extent assertions are derived rather than hand-listed and the mutant
that proved each; and — **prominently** — that `D1-10` does **not** close its roadmap row, because
accessibility-evidence and visual-regression remain `U1`'s and need their own authority.

End with:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 5: Do not merge**

`main` requires the owner's approval, and the `#457` delegation was per-PR. Report the PR number and
CI state; ask.

---

## Self-Review

**Spec coverage.** `FR-171` — Task 2, per surface and as an extent. `FR-164` and the refusal states
— Task 4. `FR-163`'s distinguishable empty rules — covered by `D1-03`'s existing cases; this slice
re-asserts reachability rather than duplicating them. `FR-170` — Task 4, explicitly re-checked.
Cross-organization isolation "on every surface" — Task 3. §Verification's remaining clauses (source
map, static no-arithmetic check, unsupported filter, partial success, breakdown four-state) are
already carried by `D1-02`/`D1-04`/`D1-07` and are not re-implemented; the ledger names where each
lives.

**Placeholder scan.** No TBDs. Two steps carry an explicit executor note instead of final code —
Task 1 Step 3 (`render_decisions`' signature) and Task 3 Step 3 (whether the stub isolation
discriminates) — because both depend on a seam that must be read at execution time. Each names the
file and line to read and what to do with either answer, rather than deferring the decision.

**Type consistency.** `Surface` is a frozen slotted dataclass with `key: str` and
`renders_prose: bool`; `SURFACES` is `tuple[Surface, ...]`; `expected_roster()` returns `set[str]`
and is compared against `set(keys)`. `rendered` and `rendered_for_organization` both return `str`.
`LANGUAGES` is `("en", "ar")` in both this module and `d105_support`, which is a duplication worth
noting — Task 1 should import it from `d105_support` rather than redefining, and the plan's code
does not. **Fix that during Task 1** rather than shipping two definitions of the language set.

**The weakness this plan expects to find.** Task 1 Step 5 mutant 1 is written knowing it will
probably *pass* on the first run, because `expected_roster()` and `SURFACES` share a derivation and
move in lockstep — a tautology comparing a restatement against itself. The step requires pinning the
expectation to an independent source before proceeding. Recording that prediction here rather than
discovering it in review is the difference between an extent assertion and a decorative one.
