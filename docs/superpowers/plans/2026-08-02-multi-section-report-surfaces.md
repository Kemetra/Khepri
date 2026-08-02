# Multi-Section Report Surfaces and Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present the report bundle as an ordered set of governed sections — each with an accessible table and a chart — across web, PDF and Excel, with the four `RRA-008` analysis families supplying four of those sections.

**Architecture:** A section is a grouping of `CitedFigure`s by the analysis family that produced them, carried in the bundle rather than invented by a renderer. `reconcile()` gains placement checks so a surface cannot silently move a figure or a caveat between sections. Chart geometry is computed in `Decimal` from `Bucket.value` and becomes a coordinate only at write time. The web and PDF surfaces render inline SVG through the existing single template; the workbook renders native XlsxWriter charts addressing a dedicated non-authoritative numeric worksheet.

**Tech Stack:** Python 3.13, uv, Jinja2 (autoescaped), Playwright + pinned Chromium, XlsxWriter, pytest, ruff.

## Global Constraints

- Python 3.13 and `uv`. Run everything through `uv run`.
- **Every new file must score 10.00 on CodeScene Code Health.** No tracked hotspot may decline; `src/khepri/rra/api.py` is a tracked hotspot. CI is the only authority — iterate locally with per-file `code_health_review` until findings are empty.
- Keep constructors to 2–3 parameters. Never sit exactly at a threshold.
- *Complex Conditional* counts logical operators, threshold 2: `if a and (b or c)` fails. Push multi-operator conditions into a helper's `return`.
- *Overall Code Complexity* is the **mean** CC per function, threshold 4, aim ≤ 3.5.
- Binary floating point is never an authoritative financial fact. Use `Decimal`.
- Every workbook cell is written through `write_string`. The only exception this plan introduces is the `chartdata` worksheet, and only after Task 1 records approval.
- No Jinja2 autoescape exemptions. No `|safe`. No client-side JavaScript.
- Arabic is RTL; Arabic and English carry equal facts, caveats and citations.
- Commit signing is broken locally; unsigned commits are sanctioned until the key is restored. Use `git commit --no-gpg-sign`. **The harness classifier blocks the agent from committing an approval attributed to itself — Ahmed runs those commits with a `!` line.**
- Branch protection forces serial merges. `main` is protected; work on a branch.

---

### Task 1: Delegation record and the DEC-005 amendment

**This task is the only approval gate in the plan.** Tasks 2–11 do not depend on it. Only Task 12's chart path does.

**Files:**
- Create: `governance/delegations/DEL-002.yaml`
- Modify: `governance/decisions/KHEPRI-DEC-005-rra-runtime-architecture.md`
- Modify: `governance/registries/decisions.yaml`
- Create: `governance/approvals/APP-013.yaml`

**Interfaces:**
- Consumes: nothing.
- Produces: authority for a numeric cell on a `chartdata` worksheet, cited by Task 12.

**Scope this conservatively.** The instruction is session-scoped and expires the day it was given. If Task 1 is not completed that same day, **stop and ask Ahmed for a fresh instruction** — do not extend, renew, or reinterpret `DEL-002`. A delegate reading its own instruction generously is exactly what Article VIII exists to prevent.

**Implementation was deferred on 2026-08-02, so the record below is already stale.** The instruction
it quotes was given in session `05cd944b-db94-4195-928a-a724c8b7d6ca` and expired that day. Treat the
YAML as a *shape to follow*, not a record to copy: when this task is picked up, the `instruction`,
`granted_at`, `session`, and `expires_at` fields must all be re-captured verbatim from a fresh
instruction given at that time, and the identifier will not be `DEL-002` if another delegation has
been recorded meanwhile. Copying the fields below forward would fabricate a delegation record, which
is the one failure `FND-003` cannot detect.

- [ ] **Step 1: Write the delegation record with the instruction verbatim**

Store the typo as typed. Session id is this session's.

```yaml
schema_version: 1
id: DEL-002
delegate: KHEPRI-AGENT
granted_by: AHMED-SHAABAN
instruction: >-
  i authroize you]
granted_at: 2026-08-02
session: 05cd944b-db94-4195-928a-a724c8b7d6ca
scope:
  kind: session
  artifacts:
    - KHEPRI-DEC-005
expires_at: 2026-08-02
revoked: false
```

- [ ] **Step 2: Add the bounded clause to KHEPRI-DEC-005**

Add beneath the existing rendering bullets, adjacent to the prohibition it narrows:

```markdown
- A workbook may carry numeric cells solely as chart series addresses, on a dedicated worksheet
  that holds no authoritative figure and no citation identifier. Such cells are excluded from the
  surface content a bundle reconciles, and the authoritative figure remains the decimal string on
  the section worksheet. This narrows the binary floating-point prohibition above; it does not
  relax it.
```

- [ ] **Step 3: Run the governance validator and confirm it still passes**

Run: `uv run khepri-gov validate`
Expected: PASS. A failure here means the registry and the documents disagree — fix before continuing.

- [ ] **Step 4: Compute the document digest for the amended decision**

Run: `uv run khepri-gov document-digest governance/decisions/KHEPRI-DEC-005-rra-runtime-architecture.md`
Record the value; it goes into `APP-013.yaml` as `document_sha256`.

- [ ] **Step 5: Write the approval package with delegate attribution**

`approved_by` is `KHEPRI-AGENT` with a `delegation_ref`. **Never** `evidence_ref`, never a human identifier — that would claim Ahmed approved it.

```yaml
schema_version: 1
id: APP-013
title: Bounded numeric chart cells in the governed workbook
state: approved
owner: AHMED-SHAABAN
scope: >-
  Amend KHEPRI-DEC-005 to permit numeric cells solely as chart series addresses, on a
  dedicated worksheet holding no authoritative figure and no citation.
exclusions:
  - Any change to governance/CONSTITUTION.md or the authorities registry
  - Any delegation record, including DEL-002 which this package cites
  - Any widening of DEL-002, whose scope and expiry this package cannot alter
  - Any relaxation of the binary floating-point prohibition beyond chart series addressing
  - Any claim that a human authority approved this package
  - Any transition or approval of KHEPRI-DEC-008
approval:
  approved_by: KHEPRI-AGENT
  approved_at: 2026-08-02
  delegation_ref: governance/delegations/DEL-002.yaml
  session: 05cd944b-db94-4195-928a-a724c8b7d6ca
```

Fill `manifest_digest`, `approved_manifest_digest`, and the `artifacts` block following `APP-012.yaml` exactly, using `uv run khepri-gov approval-digest governance/approvals/APP-013.yaml`.

- [ ] **Step 6: Run both guards**

Run: `uv run khepri-gov validate && uv run khepri-gov delegation-guard`
Expected: both PASS. The package validator sees artifact transitions; the delegation guard sees the diff. Both are required because neither sees what the other does.

- [ ] **Step 7: Hand the commit to Ahmed**

The classifier refuses to let the agent commit an approval attributed to itself, and will not be moved by a spoken approval or a settings rule. Do not hunt for a phrasing that slips past it. Write the message to a file and hand over one line:

```
! git -C C:/Users/user/Documents/GitHub/Khepri commit --no-gpg-sign -F <msgfile>
```

---

### Task 2: Section and ChartSpec types

**Files:**
- Modify: `src/khepri/rra/bundle.py`
- Test: `tests/rra/test_bundle_sections.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SECTION_OVERVIEW`, `SECTION_COMPARISON`, `SECTION_CONCENTRATION`, `SECTION_GROWTH`, `SECTION_BASKET`, `ORDERED_SECTIONS: tuple[str, ...]`, `SECTION_PRESENT`, `SECTION_REFUSED`, `CHART_BAR`, `CHART_GROUPED_BAR`, `CHART_LINE`, `Section`, `ChartSpec`, and `ReportBundle.sections: tuple[Section, ...]` — the ordered sections the bundle declares, which Task 3 reconciles chart coverage against.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from khepri.rra.bundle import (
    CHART_BAR,
    ORDERED_SECTIONS,
    SECTION_COMPARISON,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    SECTION_REFUSED,
    ChartSpec,
    Section,
)


def test_ordered_sections_starts_with_overview() -> None:
    assert ORDERED_SECTIONS[0] == SECTION_OVERVIEW
    assert SECTION_COMPARISON in ORDERED_SECTIONS


def test_present_section_carries_no_reason() -> None:
    section = Section(
        section_id=SECTION_OVERVIEW,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=("F-1",),
        chart=None,
    )
    assert section.reason is None


def test_refused_section_requires_a_reason() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_REFUSED,
            reason=None,
            figure_ids=(),
            chart=None,
        )


def test_chart_must_plot_at_least_one_figure() -> None:
    with pytest.raises(ValueError):
        ChartSpec(kind=CHART_BAR, figure_ids=())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/test_bundle_sections.py -v`
Expected: FAIL with `ImportError: cannot import name 'ORDERED_SECTIONS'`

- [ ] **Step 3: Write minimal implementation**

Add to `bundle.py` beside the existing `SURFACE_*` constants:

```python
SECTION_OVERVIEW = "overview"
SECTION_COMPARISON = "comparison"
SECTION_CONCENTRATION = "concentration"
SECTION_GROWTH = "growth"
SECTION_BASKET = "basket"
ORDERED_SECTIONS = (
    SECTION_OVERVIEW,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_GROWTH,
    SECTION_BASKET,
)

SECTION_PRESENT = "present"
SECTION_REFUSED = "refused"

CHART_BAR = "bar"
CHART_GROUPED_BAR = "grouped_bar"
CHART_LINE = "line"
GOVERNED_CHART_KINDS = frozenset({CHART_BAR, CHART_GROUPED_BAR, CHART_LINE})


@dataclass(frozen=True, slots=True)
class ChartSpec:
    kind: str
    figure_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in GOVERNED_CHART_KINDS:
            raise ValueError("unknown chart kind")
        if not self.figure_ids:
            raise ValueError("chart plots no figure")


@dataclass(frozen=True, slots=True)
class Section:
    section_id: str
    state: str
    reason: str | None
    figure_ids: tuple[str, ...]
    chart: ChartSpec | None

    def __post_init__(self) -> None:
        _require_section(self.section_id)
        _require_section_state(self.state, self.reason)
        _require_chart_within(self.chart, self.figure_ids)
```

Three small module-level helpers keep `__post_init__` at CC 1 and each check's operators separated — required by the *Complex Conditional* threshold:

```python
def _require_section(section_id: str) -> None:
    if section_id not in ORDERED_SECTIONS:
        raise ValueError("unknown section")


def _require_section_state(state: str, reason: str | None) -> None:
    if state == SECTION_REFUSED and reason is None:
        raise ValueError("refused section states no reason")
    if state == SECTION_PRESENT and reason is not None:
        raise ValueError("present section states a reason")


def _require_chart_within(chart: ChartSpec | None, figure_ids: tuple[str, ...]) -> None:
    if chart is None:
        return
    if not frozenset(chart.figure_ids) <= frozenset(figure_ids):
        raise ValueError("chart plots a figure outside its section")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/test_bundle_sections.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Check Code Health before committing**

Run `code_health_review` on `src/khepri/rra/bundle.py`. It is an existing file, so the bar is "no decline" rather than 10.00 — capture its score **before** this task and compare. If it dropped, extract rather than inline.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/bundle.py tests/rra/test_bundle_sections.py
git commit --no-gpg-sign -m "feat: add governed section and chart types to the report bundle"
```

---

### Task 3: Bind figures to sections and reconcile placement

**Files:**
- Modify: `src/khepri/rra/bundle.py` (`CitedFigure`, `StatedFigure`, `reconcile`, `GOVERNED_REASONS`)
- Test: `tests/rra/test_bundle_section_reconcile.py`

**Interfaces:**
- Consumes: `Section`, `ORDERED_SECTIONS` from Task 2.
- Produces: `CitedFigure.section: str`, `StatedFigure.section: str`, and reasons `REASON_UNKNOWN_SECTION = "unknown_section"`, `REASON_FIGURE_MISPLACED = "figure_misplaced"`, `REASON_SECTION_COVERAGE_DIFFERS = "section_coverage_differs_by_language"`, `REASON_SECTION_ORDER_DIFFERS = "section_order_differs_by_language"`, `REASON_CHART_FIGURE_NOT_STATED = "chart_figure_not_stated"`.

**This task changes a shared DTO.** `CitedFigure` gains a required field, so every branch constructing one will fail to build once this merges. Write that into the pull request body before it happens — it is the same collision class as the alembic `down_revision` siblings the repository's change discipline already names.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from khepri.rra.bundle import (
    REASON_FIGURE_MISPLACED,
    REASON_SECTION_COVERAGE_DIFFERS,
    SECTION_COMPARISON,
    SECTION_OVERVIEW,
    BundleRefused,
    reconcile,
)
from tests.rra.factories import bundle_with_sections, surface_content


def test_figure_stated_in_the_wrong_section_refuses() -> None:
    bundle = bundle_with_sections()
    content = surface_content(bundle, moved={"F-1": SECTION_COMPARISON})
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_FIGURE_MISPLACED


def test_section_dropped_from_one_language_only_refuses() -> None:
    bundle = bundle_with_sections()
    content = surface_content(bundle, drop_section_from_arabic=SECTION_COMPARISON)
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_SECTION_COVERAGE_DIFFERS


def test_correct_placement_reconciles() -> None:
    bundle = bundle_with_sections()
    reconcile(surface_content(bundle), bundle=bundle)


def test_chart_plotting_a_figure_the_surface_did_not_state_refuses() -> None:
    bundle = bundle_with_sections()
    content = surface_content(bundle, unstate={"F-2"})
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_CHART_FIGURE_NOT_STATED
```

`unstate` drops a figure from `stated` while leaving it in the section's `ChartSpec`. This is the
one gap the structural subset rule in Task 2 does not close: a chart may only reference figures its
section declared, but the *surface* could still omit one from what it says it presented, leaving a
plotted bar with no reconciled text behind it.

Add the two factories to `tests/rra/factories.py`, following the construction the existing bundle tests already use. `surface_content` builds both languages from the bundle and applies the named mutation to Arabic only.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/test_bundle_section_reconcile.py -v`
Expected: FAIL — `StatedFigure` has no `section`.

- [ ] **Step 3: Write minimal implementation**

Add `section: str` to `CitedFigure` and to `StatedFigure`, add the four reasons to `GOVERNED_REASONS`, and extend `_reconcile_language` with one placement check:

```python
    for stated in entry.stated:
        figure = bundle.figure(stated.figure_id)
        if figure is None:
            raise BundleRefused(REASON_UNKNOWN_FIGURE)
        if stated.section != figure.section:
            # Placement is a claim like any other. A figure shown under the
            # wrong heading is cited correctly and read wrongly.
            raise BundleRefused(REASON_FIGURE_MISPLACED)
        if stated.text != figure.renderings.get(entry.language):
            raise BundleRefused(REASON_FIGURE_NOT_RECONCILED)
```

Add the chart-coverage check. `_reconcile_language` receives a `SurfaceLanguage`, which knows what
was shown but not what the bundle's sections declared, so this is called from `reconcile` — which
holds both — rather than from inside it:

```python
def _reconcile_chart(section: Section, shown: frozenset[str]) -> None:
    if section.chart is None:
        return
    if not frozenset(section.chart.figure_ids) <= shown:
        raise BundleRefused(REASON_CHART_FIGURE_NOT_STATED)


def _reconcile_charts(entry: SurfaceLanguage, bundle: ReportBundle) -> None:
    for section in bundle.sections:
        _reconcile_chart(section, entry.shown)
```

Wire it into the existing per-language loop in `reconcile`:

```python
    for entry in seen.values():
        _reconcile_language(entry, bundle)
        _reconcile_charts(entry, bundle)
```

Then, in `reconcile`, alongside the existing cross-language coverage comparison, add ordered-section comparison. Keep it a separate helper so `reconcile`'s own complexity does not rise:

```python
def _reconcile_sections(coverage: list[SurfaceLanguage]) -> None:
    first = _sections_of(coverage[0])
    for other in coverage[1:]:
        current = _sections_of(other)
        if frozenset(current) != frozenset(first):
            raise BundleRefused(REASON_SECTION_COVERAGE_DIFFERS)
        if current != first:
            raise BundleRefused(REASON_SECTION_ORDER_DIFFERS)


def _sections_of(entry: SurfaceLanguage) -> tuple[str, ...]:
    seen: list[str] = []
    for stated in entry.stated:
        if stated.section not in seen:
            seen.append(stated.section)
    return tuple(seen)
```

Order is compared as a tuple and membership as a set, so a reordering and an omission produce different reasons rather than one ambiguous refusal.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/test_bundle_section_reconcile.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Fix every construction site of CitedFigure**

Run: `uv run pytest -m 'not local_stack and not browser' -x -q`
Expected: PASS. Failures here are the required-field collision, not new bugs — fix each construction site to pass a section.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/bundle.py tests/rra/
git commit --no-gpg-sign -m "feat: reconcile figure placement and section parity across languages"
```

---

### Task 4: Bind caveats to sections

**Files:**
- Modify: `src/khepri/rra/bundle.py` (`SurfaceLanguage.caveats`, `_reconcile_language`)
- Test: `tests/rra/test_bundle_section_caveats.py`

**Interfaces:**
- Consumes: `ORDERED_SECTIONS` from Task 2.
- Produces: `StatedCaveat(code: str, section: str | None)`. `SurfaceLanguage.caveats` becomes `tuple[StatedCaveat, ...]`; `ReportBundle.caveats` likewise.

`section=None` means a report-level caveat that belongs to no single analysis. No new refusal reason is needed: the existing comparison against `bundle.caveats` now compares pairs, so a misplaced caveat fails it exactly as a missing one does.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from khepri.rra.bundle import (
    REASON_CAVEAT_COVERAGE_DIFFERS,
    SECTION_BASKET,
    SECTION_COMPARISON,
    BundleRefused,
    StatedCaveat,
    reconcile,
)
from tests.rra.factories import bundle_with_sections, surface_content


def test_caveat_under_the_wrong_section_refuses() -> None:
    bundle = bundle_with_sections()
    content = surface_content(
        bundle,
        recaveat=(
            StatedCaveat(code="window_truncated", section=SECTION_BASKET),
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_CAVEAT_COVERAGE_DIFFERS


def test_report_level_caveat_carries_no_section() -> None:
    caveat = StatedCaveat(code="rows_redacted", section=None)
    assert caveat.section is None


def test_section_scoped_caveat_must_name_a_governed_section() -> None:
    with pytest.raises(ValueError):
        StatedCaveat(code="window_truncated", section="invented")
```

The bundle factory must place `window_truncated` under `SECTION_COMPARISON`, so the first test moves a caveat that genuinely belongs elsewhere.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/test_bundle_section_caveats.py -v`
Expected: FAIL with `ImportError: cannot import name 'StatedCaveat'`

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True, slots=True)
class StatedCaveat:
    code: str
    section: str | None

    def __post_init__(self) -> None:
        if self.section is None:
            return
        _require_section(self.section)
```

`_reconcile_language`'s caveat comparison is unchanged in shape — it already compares `frozenset(entry.caveats)` against `frozenset(bundle.caveats)`, and now compares pairs because the element type changed. Keep the existing `REASON_CAVEAT_COVERAGE_DIFFERS`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/test_bundle_section_caveats.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Fix every construction site and run the suite**

Run: `uv run pytest -m 'not local_stack and not browser' -x -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/bundle.py tests/rra/
git commit --no-gpg-sign -m "feat: bind caveats to the section they qualify"
```

---

### Tasks 5–8: The four analysis families

Each family is one task with the identical five-step shape: write the golden-dataset test, watch it fail, implement, watch it pass, commit. They share no code beyond the `RRA-004` types they read, which is why they are four files rather than one — a single `analysis.py` would fail *Number of Functions in a Single Module* and mean-CC immediately.

**Shared interfaces for all four** — each module exposes exactly one entry point returning either derived facts or a refusal, so the pipeline treats them uniformly:

```python
def derive(package: FactPackage) -> tuple[Fact, ...] | RefusedResult: ...
```

`RefusedResult(metric, reason)` and `Fact` already exist in `facts.py`; no new refusal channel is needed. A `RefusedResult` becomes a `Section` with `state=SECTION_REFUSED` in Task 10's assembly.

---

### Task 5: Period comparison

**Files:**
- Create: `src/khepri/rra/analysis/__init__.py`
- Create: `src/khepri/rra/analysis/comparison.py`
- Test: `tests/rra/analysis/test_comparison.py`

**Interfaces:**
- Consumes: `FactPackage`, `FactSeries`, `Bucket`, `Fact`, `RefusedResult`.
- Produces: `comparison.derive(package) -> tuple[Fact, ...] | RefusedResult`.

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal

from khepri.rra.analysis import comparison
from khepri.rra.facts import RefusedResult
from tests.rra.analysis.factories import package_with_trend


def test_incomplete_window_truncates_both_sides_and_caveats() -> None:
    package = package_with_trend(current_days=15, prior_days=30)
    facts = comparison.derive(package)
    assert not isinstance(facts, RefusedResult)
    delta = next(f for f in facts if f.metric == "revenue_delta_absolute")
    assert "window_truncated" in delta.caveats


def test_absent_prior_coverage_refuses_the_comparison_only() -> None:
    package = package_with_trend(current_days=30, prior_days=0)
    result = comparison.derive(package)
    assert isinstance(result, RefusedResult)
    assert result.reason == "prior_window_absent"


def test_zero_base_refuses_the_percentage_but_keeps_the_absolute() -> None:
    package = package_with_trend(current_days=30, prior_days=30, prior_total=Decimal(0))
    facts = comparison.derive(package)
    assert not isinstance(facts, RefusedResult)
    metrics = {f.metric for f in facts}
    assert "revenue_delta_absolute" in metrics
    assert "revenue_delta_percent" not in metrics


def test_negative_base_refuses_the_percentage() -> None:
    package = package_with_trend(current_days=30, prior_days=30, prior_total=Decimal(-50))
    facts = comparison.derive(package)
    metrics = {f.metric for f in facts}
    assert "revenue_delta_percent" not in metrics
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/analysis/test_comparison.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.rra.analysis'`

- [ ] **Step 3: Write minimal implementation**

Read `package.trend()` for the revenue series, split its buckets into current and prior windows of equal length, truncating both to the shorter day count and appending `window_truncated` to the caveats of every fact derived from a truncated window. Return `RefusedResult("revenue_comparison", "prior_window_absent")` when the prior window has no buckets. Emit the absolute delta always; emit the percentage only when the base is strictly positive.

Keep the base test in its own helper so the *Complex Conditional* threshold is not reached:

```python
def _percentage_is_defined(base: Decimal | None) -> bool:
    if base is None:
        return False
    return base > 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/analysis/test_comparison.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Check Code Health, then commit**

`comparison.py` is a new file and must score **10.00**. Run `code_health_review` and iterate until findings are empty — "improved" is still a failure.

```bash
git add src/khepri/rra/analysis/ tests/rra/analysis/
git commit --no-gpg-sign -m "feat: derive period comparison facts with like-for-like truncation"
```

---

### Task 6: Concentration

**Files:**
- Create: `src/khepri/rra/analysis/concentration.py`
- Test: `tests/rra/analysis/test_concentration.py`

**Interfaces:**
- Consumes: `FactPackage.comparison(dimension)`, `Comparison.distinct_values`, `Comparison.truncated_values`, `Bucket`.
- Produces: `concentration.derive(package) -> tuple[Fact, ...] | RefusedResult`.

`Comparison` already records `distinct_values` and `truncated_values`, which is exactly the full-distinct-set rule `RRA-008` requires. Use them; do not recount from the buckets.

- [ ] **Step 1: Write the failing test**

```python
from khepri.rra.analysis import concentration
from khepri.rra.facts import RefusedResult
from tests.rra.analysis.factories import package_with_products


def test_curve_is_computed_over_the_full_distinct_set_not_the_display() -> None:
    package = package_with_products(distinct=57, displayed=20)
    facts = concentration.derive(package)
    ranked = next(f for f in facts if f.metric == "concentration_ranked_values")
    distinct = next(f for f in facts if f.metric == "concentration_distinct_values")
    assert distinct.value == "57"
    assert ranked.value == "57"


def test_top_decile_and_quartile_shares_are_emitted() -> None:
    package = package_with_products(distinct=40, displayed=20)
    metrics = {f.metric for f in concentration.derive(package)}
    assert "concentration_top_decile_share" in metrics
    assert "concentration_top_quartile_share" in metrics


def test_no_fixed_classification_bands_are_emitted() -> None:
    package = package_with_products(distinct=40, displayed=20)
    metrics = {f.metric for f in concentration.derive(package)}
    assert not any(metric.startswith("concentration_class_") for metric in metrics)


def test_uncomputable_distinct_set_refuses() -> None:
    package = package_with_products(distinct=0, displayed=0)
    result = concentration.derive(package)
    assert isinstance(result, RefusedResult)
    assert result.reason == "distinct_set_uncomputable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/analysis/test_concentration.py -v`
Expected: FAIL with `ImportError: cannot import name 'concentration'`

- [ ] **Step 3: Write minimal implementation**

Rank buckets by value descending, accumulate the cumulative share in `Decimal`, and emit the ranked count, the distinct count taken from `Comparison.distinct_values`, and the measured share held by the top decile and top quartile of ranked values. Emit no classification bands. Refuse with `distinct_set_uncomputable` when `distinct_values` is zero.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/analysis/test_concentration.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Check Code Health, then commit**

```bash
git add src/khepri/rra/analysis/concentration.py tests/rra/analysis/test_concentration.py
git commit --no-gpg-sign -m "feat: derive concentration facts over the full distinct value set"
```

---

### Task 7: Growth decomposition

**Files:**
- Create: `src/khepri/rra/analysis/growth.py`
- Test: `tests/rra/analysis/test_growth.py`

**Interfaces:**
- Consumes: `FactPackage`, revenue and units series.
- Produces: `growth.derive(package) -> tuple[Fact, ...] | RefusedResult`.

Formula, fixed by `RRA-008`:
`(average_selling_price_prior * units_change) + (units_current * average_selling_price_change)`
The interaction term is assigned to price, and that assignment is recorded as a fact.

- [ ] **Step 1: Write the failing test**

Additivity is asserted as **exact equality, not a tolerance** — this is the point of the whole family.

```python
from decimal import Decimal

from khepri.rra.analysis import growth
from khepri.rra.facts import RefusedResult
from tests.rra.analysis.factories import package_with_price_and_units


def test_parts_sum_exactly_to_the_revenue_change() -> None:
    package = package_with_price_and_units()
    facts = growth.derive(package)
    price = Decimal(next(f for f in facts if f.metric == "growth_price_effect").value)
    volume = Decimal(next(f for f in facts if f.metric == "growth_volume_effect").value)
    total = Decimal(next(f for f in facts if f.metric == "growth_revenue_change").value)
    assert price + volume == total


def test_interaction_assignment_is_recorded() -> None:
    facts = growth.derive(package_with_price_and_units())
    assignment = next(f for f in facts if f.metric == "growth_interaction_assigned_to")
    assert assignment.value == "price"


def test_zero_units_in_either_period_refuses() -> None:
    package = package_with_price_and_units(units_current=0)
    result = growth.derive(package)
    assert isinstance(result, RefusedResult)
    assert result.reason == "units_absent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/analysis/test_growth.py -v`
Expected: FAIL with `ImportError: cannot import name 'growth'`

- [ ] **Step 3: Write minimal implementation**

Compute in `Decimal` throughout. After computing both parts, assert their sum equals the revenue change and return `RefusedResult("growth_decomposition", "decomposition_not_additive")` if it does not — an inequality is a reconciliation failure, not a rounding artifact. Refuse with `units_absent` when units are zero in either period.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/analysis/test_growth.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Check Code Health, then commit**

```bash
git add src/khepri/rra/analysis/growth.py tests/rra/analysis/test_growth.py
git commit --no-gpg-sign -m "feat: derive price and volume growth decomposition with exact additivity"
```

---

### Task 8: Basket structure

**Files:**
- Create: `src/khepri/rra/analysis/basket.py`
- Test: `tests/rra/analysis/test_basket.py`

**Interfaces:**
- Consumes: `FactPackage`, mapped `transaction_id`, an admissible product or category dimension.
- Produces: `basket.derive(package) -> tuple[Fact, ...] | RefusedResult`.

- [ ] **Step 1: Write the failing test**

The third test is the one that matters most: row count is not transaction count, and mistaking them silently inflates every basket metric.

```python
from khepri.rra.analysis import basket
from khepri.rra.facts import RefusedResult
from tests.rra.analysis.factories import package_with_baskets


def test_items_per_transaction_and_attach_rate_are_emitted() -> None:
    metrics = {f.metric for f in basket.derive(package_with_baskets())}
    assert "basket_items_per_transaction" in metrics
    assert "basket_attach_rate" in metrics


def test_missing_transaction_identifier_refuses_with_a_stated_reason() -> None:
    result = basket.derive(package_with_baskets(transaction_id=False))
    assert isinstance(result, RefusedResult)
    assert result.reason == "transaction_identifier_absent"


def test_line_item_grain_is_not_mistaken_for_transaction_grain() -> None:
    package = package_with_baskets(rows=100, transactions=25)
    facts = basket.derive(package)
    items = next(f for f in facts if f.metric == "basket_items_per_transaction")
    assert items.value == "4.00"


def test_attach_rate_requires_an_admissible_dimension() -> None:
    result = basket.derive(package_with_baskets(dimension=None))
    assert isinstance(result, RefusedResult)
    assert result.reason == "dimension_absent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/analysis/test_basket.py -v`
Expected: FAIL with `ImportError: cannot import name 'basket'`

- [ ] **Step 3: Write minimal implementation**

Items per transaction divides row count by **transaction count**, never by row count. Attach rate is the share of transactions containing a given admissible dimension value. Refuse with `transaction_identifier_absent` or `dimension_absent` rather than substituting anything.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/analysis/test_basket.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Check Code Health, then commit**

```bash
git add src/khepri/rra/analysis/basket.py tests/rra/analysis/test_basket.py
git commit --no-gpg-sign -m "feat: derive basket structure facts from transaction grain"
```

---

### Task 9: The chart module

**Files:**
- Create: `src/khepri/rra/rendering/charts.py`
- Test: `tests/rra/rendering/test_charts.py`

**Interfaces:**
- Consumes: `ChartSpec`, `CitedFigure`, `DIRECTION_RTL` from `bundle.py`.
- Produces: `render_chart(spec: ChartSpec, figures: tuple[CitedFigure, ...], *, direction: str, language: str) -> str | None` returning an SVG fragment, or `None` when the series cannot be drawn.

Geometry is computed in `Decimal` and converted to a coordinate only at write time. `render_chart` returns `None` rather than raising: the table is the authoritative presentation and a chart must never suppress governed analysis.

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal

from khepri.rra.bundle import CHART_BAR, DIRECTION_LTR, DIRECTION_RTL, ChartSpec
from khepri.rra.rendering.charts import render_chart
from tests.rra.rendering.factories import figures_for_chart


def test_bar_chart_is_an_accessible_svg() -> None:
    svg = render_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        figures_for_chart(),
        direction=DIRECTION_LTR,
        language="en",
    )
    assert 'role="img"' in svg
    assert "aria-labelledby=" in svg


def test_arabic_chart_mirrors_the_category_order() -> None:
    figures = figures_for_chart()
    spec = ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2"))
    ltr = render_chart(spec, figures, direction=DIRECTION_LTR, language="en")
    rtl = render_chart(spec, figures, direction=DIRECTION_RTL, language="ar")
    assert _first_bar_x(ltr) != _first_bar_x(rtl)


def test_single_point_series_is_not_drawn() -> None:
    svg = render_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1",)),
        figures_for_chart(),
        direction=DIRECTION_LTR,
        language="en",
    )
    assert svg is None


def test_all_zero_series_is_not_drawn() -> None:
    svg = render_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        figures_for_chart(values=(Decimal(0), Decimal(0))),
        direction=DIRECTION_LTR,
        language="en",
    )
    assert svg is None


def test_figure_without_a_value_is_not_drawn() -> None:
    svg = render_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        figures_for_chart(values=(Decimal(10), None)),
        direction=DIRECTION_LTR,
        language="en",
    )
    assert svg is None
```

`_first_bar_x` is a two-line helper in the test file that reads the first `x=` attribute.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/rendering/test_charts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.rra.rendering.charts'`

- [ ] **Step 3: Write minimal implementation**

Three kinds only. Dispatch through a dict lookup rather than an if-chain — a dict lowers the complexity numerator where an if-chain raises it, which is the arithmetic that decides whether this new file reaches 10.00:

```python
_GEOMETRY = {CHART_BAR: _bars, CHART_GROUPED_BAR: _grouped_bars, CHART_LINE: _line}
```

Mirror for RTL by transforming the x coordinate as `width - x - bar_width` when `direction == DIRECTION_RTL`, in one helper used by all three kinds. Escape every label through the same autoescaping the templates use — this fragment is inserted into an autoescaped template, so it must be built as markup the template treats as text it produced, not as an exemption.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/rendering/test_charts.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Check Code Health, then commit**

New file, must score **10.00**. Watch mean CC: five small functions each at CC 1–2 keep the mean well under 3.5, whereas one `render_chart` holding all three kinds will not.

```bash
git add src/khepri/rra/rendering/charts.py tests/rra/rendering/test_charts.py
git commit --no-gpg-sign -m "feat: render governed fact series as accessible inline SVG"
```

---

### Task 10: Web surface — sections and charts

**Files:**
- Modify: `src/khepri/rra/rendering/templates/report.html.j2`
- Modify: `src/khepri/rra/rendering/html.py`
- Test: `tests/rra/rendering/test_html_sections.py`

**Interfaces:**
- Consumes: `Section`, `ChartSpec` (Task 2), `render_chart` (Task 9).
- Produces: an HTML surface whose `SurfaceContent` states a section per figure and a section per caveat.

This task also assembles `Section`s from the package: a family returning `RefusedResult` becomes `state=SECTION_REFUSED` carrying `result.reason`.

- [ ] **Step 1: Write the failing test**

```python
from khepri.rra.bundle import SECTION_COMPARISON, SECTION_CONCENTRATION
from tests.rra.rendering.factories import render_web


def test_each_section_has_its_own_heading_and_nav_entry() -> None:
    page = render_web(language="en")
    assert f'<section id="{SECTION_CONCENTRATION}"' in page
    assert f'href="#{SECTION_CONCENTRATION}"' in page


def test_a_refused_section_renders_its_governed_reason() -> None:
    page = render_web(language="en", refuse={SECTION_COMPARISON: "prior_window_absent"})
    assert f'<section id="{SECTION_COMPARISON}"' in page
    assert "prior_window_absent" in page


def test_the_table_is_present_even_when_the_chart_is_not() -> None:
    page = render_web(language="en", undrawable={SECTION_CONCENTRATION})
    assert "<svg" not in page
    assert "<table" in page


def test_existing_sections_keep_their_place() -> None:
    page = render_web(language="en")
    for anchor in ("caveats", "commentary", "citations", "provenance"):
        assert f'href="#{anchor}"' in page


def test_an_undrawable_chart_emits_a_governed_caveat() -> None:
    content = render_web_content(language="en", undrawable={SECTION_CONCENTRATION})
    codes = {
        caveat.code
        for caveat in content.caveats
        if caveat.section == SECTION_CONCENTRATION
    }
    assert "chart_not_drawn" in codes
```

The last test is the one that keeps a chart failure honest. `render_chart` returning `None` is not
by itself a disclosure — a section would simply look sparse, and a reader could not tell "there was
nothing to show" from "we could not show it". The caveat is what carries that distinction, so the
assembly emits `chart_not_drawn` scoped to the section whenever `render_chart` returns `None`.
`render_web_content` returns the `SurfaceContent` rather than the page string.

The fourth test guards the regression this design is most likely to cause: `ORDERED_SECTIONS` covers figure-bearing analysis sections only, and the four existing sections must not fall out of the navigation.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/rendering/test_html_sections.py -v`
Expected: FAIL — the template renders one figures table, not a section per family.

- [ ] **Step 3: Write minimal implementation**

Replace the single `#figures` section with a loop over `sections`, each rendering heading, chart, then table. The refused branch renders the reason and no table. Nothing is marked safe; the SVG fragment is passed as template-produced markup, not as an exempted variable.

```jinja
{% for section in sections %}
<section id="{{ section.section_id }}" aria-labelledby="{{ section.section_id }}-heading">
<h2 id="{{ section.section_id }}-heading">{{ chrome.sections[section.section_id] }}</h2>
{% if section.state == refused_state %}
<p class="refused" data-reason="{{ section.reason }}">{{ chrome.refused[section.reason] }}</p>
{% else %}
{% if section.chart_svg %}{{ section.chart_svg }}{% endif %}
{{ section_table(section) }}
{% endif %}
</section>
{% endfor %}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/rendering/test_html_sections.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/ tests/rra/rendering/
git commit --no-gpg-sign -m "feat: render report sections and charts on the web surface"
```

---

### Task 11: PDF pagination

**Files:**
- Modify: `src/khepri/rra/rendering/templates/report.print.css`
- Test: `tests/rra/rendering/test_pdf_sections.py` (marked `browser`)

**Interfaces:**
- Consumes: the template from Task 10. `report.pdf.html.j2` is **not modified** — it extends the parent and fills two blocks, and that inheritance is what keeps Arabic/English parity in one place.

The spec requires a refused section to render its reason on all three surfaces. There is no separate
PDF test for it because there is no separate PDF markup: every heading, section and refusal on the
printed page comes from the parent template, so Task 10's refusal test covers this surface too. Only
pagination is genuinely new here, and that is what these two tests exercise.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from tests.rra.rendering.factories import render_pdf_pages


@pytest.mark.browser
def test_each_section_starts_on_its_own_page() -> None:
    pages = render_pdf_pages(language="en")
    assert pages["concentration"] != pages["comparison"]


@pytest.mark.browser
def test_arabic_paginates_identically() -> None:
    assert render_pdf_pages(language="ar").keys() == render_pdf_pages(language="en").keys()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/rendering/test_pdf_sections.py -v -m browser`
Expected: FAIL — sections currently flow continuously.

- [ ] **Step 3: Write minimal implementation**

Add to the print stylesheet, beside the existing `break-inside`/`break-after` rules:

```css
  main > section + section {
    break-before: page;
  }
```

`section + section` rather than `section` so the first section does not force a leading blank page.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/rendering/test_pdf_sections.py -v -m browser`
Expected: PASS (2 tests). These skip without the pinned Chromium.

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/templates/report.print.css tests/rra/rendering/test_pdf_sections.py
git commit --no-gpg-sign -m "feat: start each report section on its own printed page"
```

---

### Task 12: Workbook — a sheet per section and native charts

**Blocked by Task 1.** Do not write a numeric cell before `APP-013` records approval.

**Files:**
- Modify: `src/khepri/rra/rendering/excel.py`
- Test: `tests/rra/rendering/test_excel_sections.py`

**Interfaces:**
- Consumes: `Section` (Task 2), `StatedCaveat` (Task 4).
- Produces: fifteen worksheets — seven per language plus a shared `provenance`.

The module docstring currently argues charts out. **Rewrite that paragraph** — leaving it would leave the file asserting the opposite of what it does, which is worse than either position.

- [ ] **Step 1: Write the failing test**

```python
from tests.rra.rendering.factories import workbook_sheets, workbook_values


def test_one_worksheet_per_section_per_language() -> None:
    names = workbook_sheets()
    for section in ("overview", "comparison", "concentration", "growth", "basket"):
        assert f"ar_{section}" in names
        assert f"en_{section}" in names
    assert "provenance" in names


def test_chartdata_carries_no_citation_and_no_authoritative_figure() -> None:
    cells = workbook_values("en_chartdata")
    assert not any(value.startswith("C-") for value in cells.text_values)


def test_every_numeric_chart_cell_matches_its_authoritative_string() -> None:
    numeric = workbook_values("en_chartdata").numeric_cells
    authoritative = workbook_values("en_concentration").text_values
    for value in numeric:
        assert format(value, "f") in authoritative


def test_stated_never_contains_a_chartdata_cell() -> None:
    stated = {entry.figure_id for entry in workbook_values("en_chartdata").stated}
    assert stated == set()


def test_a_refused_section_still_gets_its_worksheet() -> None:
    names = workbook_sheets(refuse={"comparison": "prior_window_absent"})
    assert "en_comparison" in names
    assert "ar_comparison" in names


def test_the_arabic_chart_axis_is_reversed() -> None:
    assert workbook_values("ar_concentration").chart_axis_reversed is True
    assert workbook_values("en_concentration").chart_axis_reversed is False
```

The mirroring test matters for the same reason it did for SVG in Task 9, and `reconcile` cannot
catch it: a spreadsheet category axis defaults left-to-right regardless of the declared direction,
so an Arabic chart would plot its first category on the wrong side while every text cell reconciles
perfectly.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/rendering/test_excel_sections.py -v`
Expected: FAIL — the workbook writes one report sheet per language.

- [ ] **Step 3: Write minimal implementation**

Split `_write_report` into a per-section writer. Add `_write_chartdata`, the only place in the module permitted to call a numeric write, and add the native chart via `workbook.add_chart` addressing that worksheet. Every other cell still goes through `write_string`. Reverse the category axis for Arabic.

Keep the numeric write isolated in one small function with a comment naming its authority:

```python
def _write_chart_value(
    sheet: Worksheet, row: int, column: int, figure: CitedFigure
) -> None:
    # The single numeric write in this module. APP-013 permits it solely as a
    # chart series address, on a worksheet holding no authoritative figure and
    # no citation. The authoritative figure is the string on the section sheet.
    #
    # Quantized to the figure's own recorded precision before narrowing, so the
    # double is the nearest representation of the governed string rather than
    # of some longer Decimal the string never claimed. APP-013 narrows the
    # binary floating-point prohibition; it does not relax it, and an
    # unquantized float(value) would be the relaxation it refuses.
    quantized = figure.value.quantize(Decimal(1).scaleb(-figure.precision))
    sheet.write_number(row, column, float(quantized))
```

The round trip is what makes the "faithful copy at write time" claim true rather than asserted:
`format(...)` on the value read back must equal the authoritative string, which is exactly what the
third test in Step 1 checks. If that test fails after this change, the precision is wrong — fix the
quantization, not the test.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/rendering/test_excel_sections.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the whole gate**

```bash
uv run khepri-gov validate
uv run ruff check .
uv run pytest -m 'not local_stack and not browser'
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/rendering/excel.py tests/rra/rendering/test_excel_sections.py
git commit --no-gpg-sign -m "feat: write one worksheet per section with a native governed chart"
```

---

## Pull request notes

Write these into the PR body **before** opening it, because both are predictable:

1. **Shared DTO collision.** `CitedFigure` gains a required `section` field (Task 3) and the caveat type changes shape (Task 4). Any branch constructing either fails to build once this merges; the second to merge fixes the fixtures.
2. **Serial merges.** Branch protection requires branches be up to date, so merging any PR invalidates every other PR's checks. Budget `gh pr update-branch` → poll until `CLEAN` → `gh pr merge --squash`, about two minutes apiece.
