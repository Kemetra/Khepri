# `D1-09` — Acquisition baseline and read-count bounds: the execution plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the decision workspace's acquisition cost as measured evidence and bound the number of
semantic-view reads each surface path performs, so a later slice cannot quietly multiply them — and
assert that nothing survives between requests.

**Architecture:** This slice **ships no surface and changes no production read path.** The reads are
already coalesced: `read_surface` performs each view exactly once and `read_cards` reads S-9 once for
the whole surface. What is missing is that those facts live only in docstrings. This slice converts
them into a per-path read-count assertion driven over the real `read_surface`, adds an end-to-end
acquisition measurement in the `SV1-08` ledger's shape, and asserts non-retention rather than
reviewing it. All new code is in `tests/`.

**Tech Stack:** Python 3.13, pytest, frozen dataclasses with `slots=True`. No new dependency, no new
production module, no SQLAlchemy model, no Alembic revision, no cache.

**Spec:** active `RCA-008` (`FR-159`–`FR-171`), merged 2026-09-10 at `2734886` (`#444`).
Allocation plan: `docs/superpowers/plans/2026-09-10-d1-02-10-decision-workspace-allocation-plan.md`
(§`D1-09`). Refinement: `docs/superpowers/plans/2026-09-12-d1-06-10-planning-refinement.md`.
Baseline precedent: `docs/superpowers/plans/2026-09-09-sv1-08-baseline-evidence.md` §3a.

---

## Global Constraints

Copied verbatim from the allocation plan's Global Constraints; every task's requirements implicitly
include this section.

- **Scope is three paths and `tests/`.** `RCA-008` §Scope admits `src/khepri/rca/workspace/`,
  `src/khepri/runtime/shell_api.py` and `shell_templates/`, and `src/khepri/runtime/shell_assets/`.
  **This slice writes only in `tests/`.**
- **A surface that computes is a defect** (`FR-159`, §Invariants).
- **Every version is a literal** (`FR-160`).
- **A refusal is content, not an error state** (§Invariants, `FR-164`).
- **No cache, ever** (`FR-168`): no cache, pre-aggregation, materialized view, sampling, or
  persisted projection. "Performance work is a change to a governed artifact and not a surface
  decision."
- **Nothing is retained** (`FR-169`, §Retention): no product-analytics or repeat-use telemetry, no
  new audit event, counter, access record or content-bearing log, and no retained preference,
  layout, filter, sort or dismissal state. `KHEPRI-DEC-015` §3 stands unamended.
- **Fail closed** (§Invariants).
- **Both empty rules render distinguishably** (`FR-163`).
- **Bilingual parity on every surface** (`FR-171`).
- **Every new file must score 10.00** in the required server-side CodeScene Code Health Review.

### Three constraints specific to this slice

1. **The counter lives in `tests/` only.** A read-count accumulator in
   `src/khepri/rca/workspace/` is retained state across requests — `FR-169` and §Retention
   directly. The slice whose job is asserting non-retention may not ship retention to do it.
2. **Count at the `SemanticQueryActions.request` seam, not at the port.** Ledger §3a puts the
   1331 µs uniform-miss path at "authorization plus the scoped run read alone": a read that
   *misses* still costs acquisition. A counter on `project` would measure the 11.6 µs half and
   under-count every miss. Precedent: `_CountingIsolation` / `_LoggingReader` / `_LoggingPort` at
   `tests/test_sv108_query_baseline.py:221-264`, which wrap the door and the reader, not just
   the port.
3. **No wall-clock threshold is asserted in CI.** `SV1-08`'s `_assert_measured` states the rule:
   "a wall-clock threshold in CI is a flake, and the ledger is where a baseline belongs." The test
   asserts a distribution was collected and that measuring changed nothing; the figures go in the
   dated ledger.

---

## What this slice does NOT do, and why

- **It does not coalesce reads.** The allocation plan names coalescing as the remaining legitimate
  lever, and it was already taken by `D1-03` and `D1-05`. `read_cards` docstring: "**S-9 is read
  once for the whole surface, not once per card.** `FR-168` bars a cache and `FR-135` bars a second
  truth, and ten reads of one view over one run would be both." `read_surface` docstring: "Every
  read this page performs, **each view exactly once**", and on S-6: a consolidated limits section
  "would read `MetricAvailabilityView` a second time … which `FR-168` bars as a cache". `D1-01` §5's
  forty-read projection was averted before this slice. **Verified empirically, not read off the
  docstrings** — the counts in the table below were measured over the real `read_surface`. A
  restructuring task here would be invented scope, and §6 of the allocation plan says this slice
  ships no surface.
- **It does not touch `read_limits` or `read_overview`.** Both are exported from
  `decision/limits.py` and `decision/overview.py` and have **zero production callers**:
  `read_surface` composes the page from `read_cards` and the four breakdown readers. They are
  alternate entry points, so the read-count guard anchors to the route, not to them. Removing them
  is not this slice's call.
- **It does not make `PeriodComparisonView` reachable.** `DECISION_VIEWS` carries eight identities;
  seven are read. `PERIOD_COMPARISON` is published and unreachable by `FR-170`, and `D1-10`'s
  acceptance requires that unreachability assertion still standing. **Do not derive the expected
  count from `len(DECISION_VIEWS)`** — it is off by one by design.
- **It does not resolve the export reading in `D1-08`, schedule `D1-11`, or authorize `U1`'s
  programme.** All three are owner items.

---

## File Structure

| File | Responsibility | New? |
|---|---|---|
| `tests/d109_support.py` | The counting seam wrapper, the seven-view admitted script, and the per-path case builder. Shared by the two test subjects below. | Create |
| `tests/test_d109_read_counts.py` | The per-path read-count bounds and the identity of which views were read. | Create |
| `tests/test_d109_acquisition_baseline.py` | The acquisition measurement and the non-retention assertions. | Create |
| `docs/superpowers/plans/2026-09-15-d1-09-acquisition-evidence.md` | The dated evidence ledger, in `SV1-08`'s shape. | Create |

**Why a new support module rather than extending `tests/d105_support.py`.** That file was split from
a combined one *because* the combined file scored 8.03 on Lines of Code in a Single File and on Low
Cohesion (`d105_support.py` docstring). Adding this slice's counting harness re-scores it and risks
regressing a file that is currently clean. `d109_support.py` imports the fixtures it needs from
`d105_support` — `ScriptedPort`, `actions`, `overview`, `availability`, `evidence_outcome`,
`breakdown` and the field tuples — and adds only what counting needs, so there is no second
definition of what the port answers.

**Why two test files rather than one.** The same seam `D1-05` found: read counts and latency are
different subjects with different failure modes. One file carrying both invites the Low Cohesion
finding again.

---

## The measured per-path counts

These are **measured over the real `read_surface`**, not derived from reading the code. Every number
below was produced by driving `read_surface` with a counting wrapper on
`SemanticQueryActions.request`. This table is the deliverable; the number 7 alone is not.

| Path | Reads | Views, in order |
|---|---:|---|
| Admitted | **7** | Overview, Availability, Evidence, Branch, Product, Basket, Concentration |
| Overview refused | **5** | Overview, Branch, Product, Basket, Concentration |
| All views unavailable | **5** | Overview, Branch, Product, Basket, Concentration |
| Unroutable parameter asked | **8** | the admitted seven, then Branch again |
| Real filter (`store`) applied | **7** | same as admitted |

**Why the refusal path is 5 and not 7.** `read_cards` returns at `card.py:276` when the overview
projection is `None`, before it reads `MetricAvailabilityView` or `ReportEvidenceView`. A test that
asserted `== 7` over only the admitted fixture would pass while leaving the refusal path's count
entirely unasserted — the inverse of "a run that can only produce the null case is NOT EXERCISED,
not PASS". Each path gets its own case.

**Why the unroutable path is 8 and that is correct.** `_unsupported_read` issues one extra read, and
only when the reader asked for something no view admits, so the refusal is earned rather than
invented (`FR-137`). Its own docstring: "an ordinary request performs exactly the seven the page
always did — this adds no read to the path `FR-168` governs." The 8 is asserted so that it stays
conditional: if it ever fired on an ordinary request, the admitted case would fail at 8.

---

## Pre-verification, performed while writing this plan

Every code block below was extracted to its target file and run before this plan was committed, so
the executor inherits verified code rather than a draft. **Re-run each step anyway** — the point of
the checkboxes is the executor's own evidence — but none of it should surprise you.

| Check | Result |
|---|---|
| The 9 tests, as written | **PASS** (`9 passed in 1.30s`) |
| `ruff check` on all three files | **clean** |
| Full suite with the three files present | **5511 passed, 74 skipped, 1 xfailed** — no regressions |
| `git diff -- src/` after all mutants restored | **empty** — zero production deletions |

**All four mutants were applied and observed to fail**, which is the part that matters: a bound that
cannot fail is decorative.

| Mutant | Caught by |
|---|---|
| A real second `read_products` call in `read_surface` | all 6 read-count tests |
| `if not asked:` → `if False:` in `_unsupported_read` | 5 tests, including `test_a_real_filter_adds_no_read` |
| `qualifiers = ...` moved above the `projection is None` guard in `read_cards` | exactly the 2 refusal-path tests |
| A retained-result cache on `CountingActions.request` | all 3 baseline tests |

**One trap worth recording.** The first attempt at mutant 1 duplicated the `products=` keyword
argument, which is a `SyntaxError` and therefore proves nothing — a malformed mutant is not
evidence. The well-formed form is a separate statement issuing a real second read.

**A measured baseline was captured** on this machine, 2026-09-15:
`min=76µs p50=78µs p90=82µs max=288µs reads=[7]`. Re-measure at Task 2 Step 5 and record your own
figures; these are the shape of the cost, not a tolerance, and they are **not** comparable to
`SV1-08` §3a's 4003 µs — the port here is scripted, so this measures the read fan-out and the
orchestration, not the composed end-to-end path.

---

### Task 1: The counting seam and the per-path read-count bounds

**Files:**
- Create: `tests/d109_support.py`
- Create: `tests/test_d109_read_counts.py`

**Interfaces:**
- Consumes: `khepri.runtime.shell_decisions.read_surface(actions, request, *, selection)`;
  `khepri.rca.workspace.decision.card.CardsRequest(organization_id, account_id, source_id)`;
  `khepri.rca.workspace.decision.controls.ControlSelection(source_id, filters=())`;
  from `tests.d105_support`: `ScriptedPort`, `actions`, `overview`, `availability`,
  `evidence_outcome`, `breakdown`, `BRANCH_FIELDS`, `PRODUCT_FIELDS`, `BASKET_FIELDS`,
  `CONCENTRATION_FIELDS`.
- Produces: `CountingActions(inner)` with attribute `views: list[str]`; `admitted_script()`;
  `refused_overview_script()`; `request_for(source_id="run1")`;
  `surface_reads(script, selection) -> tuple[str, ...]`. Task 2 relies on `CountingActions`,
  `admitted_script`, `request_for`, `ScriptedPort` and `actions` by those exact names.

- [ ] **Step 1: Write the failing test**

Create `tests/test_d109_read_counts.py`:

```python
"""Per-path read-count bounds for the decision surface (`D1-09`; active `RCA-008`).

`FR-168` bars every usual performance instrument, so what is left is the number
of reads a surface performs. `read_surface` and `read_cards` both state in prose
that each view is read exactly once; this file makes that an assertion, per path,
so a later slice cannot quietly multiply them.

**Counted at `SemanticQueryActions.request`, not at the port.** `SV1-08` ledger
§3a puts the uniform-miss path at 1331 us -- "authorization plus the scoped run
read alone" -- so a read that misses still costs acquisition. A counter on
`project` would measure the 11.6 us half and under-count every miss.
"""

from __future__ import annotations

from khepri.rca.workspace.decision.controls import ControlSelection
from tests.d109_support import (
    admitted_script,
    refused_overview_script,
    surface_reads,
)

#: The admitted page, in the order `read_surface` issues it. Seven and not eight:
#: `PeriodComparisonView` is published and unreachable (`FR-170`), so this is not
#: derived from `DECISION_VIEWS`.
ADMITTED_VIEWS = (
    "ExecutiveOverviewView",
    "MetricAvailabilityView",
    "ReportEvidenceView",
    "BranchPerformanceView",
    "ProductCategoryView",
    "BasketView",
    "ConcentrationView",
)

#: `read_cards` returns before S-6 and S-9 when the overview refuses.
REFUSED_VIEWS = (
    "ExecutiveOverviewView",
    "BranchPerformanceView",
    "ProductCategoryView",
    "BasketView",
    "ConcentrationView",
)


def _plain() -> ControlSelection:
    """A request asking for no filter at all."""
    return ControlSelection(source_id="run1")


def test_the_admitted_page_reads_seven_views_each_exactly_once() -> None:
    """`read_surface`'s "each view exactly once", asserted rather than documented."""
    read = surface_reads(admitted_script(), _plain())

    assert read == ADMITTED_VIEWS
    assert len(read) == len(set(read))


def test_a_refused_overview_reads_five_because_cards_returns_early() -> None:
    """The count is path-dependent, and the short path is asserted too.

    `read_cards` returns at `card.py:276` before S-6 and S-9 when the overview
    projection is `None`. A suite asserting only the admitted seven would leave
    this path unmeasured.
    """
    read = surface_reads(refused_overview_script(), _plain())

    assert read == REFUSED_VIEWS
    assert len(read) == len(set(read))


def test_every_view_unavailable_reads_the_same_five() -> None:
    """A uniform miss costs acquisition on the same path as a refusal."""
    read = surface_reads({}, _plain())

    assert read == REFUSED_VIEWS


def test_an_unroutable_parameter_adds_exactly_one_read_and_only_then() -> None:
    """`_unsupported_read`'s extra read is earned, conditional, and bounded at one.

    `FR-137` refuses a parameter no view admits before projection, and the
    refusal must be earned by a real read rather than invented. What is asserted
    is that it fires only for the unroutable ask and adds exactly one.
    """
    asked = ControlSelection(source_id="run1", filters=(("nosuchdim", "x"),))

    read = surface_reads(admitted_script(), asked)

    assert read == (*ADMITTED_VIEWS, "BranchPerformanceView")


def test_a_real_filter_adds_no_read() -> None:
    """`store` is routed to the views admitting it, and routing is not a read."""
    asked = ControlSelection(source_id="run1", filters=(("store", "s1"),))

    read = surface_reads(admitted_script(), asked)

    assert read == ADMITTED_VIEWS


def test_no_view_is_read_twice_on_any_ordinary_path() -> None:
    """The coalescing `D1-03` and `D1-05` performed, held as a standing bound.

    Derived from the recorded reads rather than hand-listed, and asserted
    non-empty: a scan that silently recorded nothing would otherwise pass.
    """
    for script in (admitted_script(), refused_overview_script(), {}):
        read = surface_reads(script, _plain())

        assert read
        assert len(read) == len(set(read))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d109_read_counts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.d109_support'`

- [ ] **Step 3: Write minimal implementation**

Create `tests/d109_support.py`:

```python
"""Shared harness for `D1-09`'s two test files (active `RCA-008`).

`D1-09` has two subjects -- how many reads a surface performs, and what
acquisition costs -- and they need one set of fixtures. Kept out of
`tests/d105_support.py` deliberately: that file was split from a combined one
because the combined file scored 8.03 on Lines of Code in a Single File and on
Low Cohesion, and adding a counting harness to it re-scores it. The scripted
port, the governed outcomes and the field tuples are imported from there rather
than redefined, so there is no second definition of what the port answers.

**The counter is here and not in `src/`.** A read-count accumulator living in
`khepri.rca.workspace` would be state surviving a request, which is exactly what
`FR-169` and `RCA-008` §Retention forbid -- and shipping retention is a strange
way to assert non-retention. The instrument is test-only and per-call.

**It wraps `SemanticQueryActions.request`, not the port.** `SV1-08` ledger §3a
measures the uniform-miss path at 1331 us, "authorization plus the scoped run
read alone", so a read that misses still costs acquisition. Counting `project`
calls would measure the 11.6 us half and under-count every miss. The precedent
is `_CountingIsolation`/`_LoggingReader` in `test_sv108_query_baseline.py`, which
wrap the door and the reader for the same reason.
"""

from __future__ import annotations

from typing import Any

from khepri.rca.semantic_queries import ports
from khepri.rca.workspace.decision import seam
from khepri.rca.workspace.decision.card import CardsRequest
from khepri.rca.workspace.decision.controls import ControlSelection
from khepri.runtime.shell_decisions import read_surface
from tests.d105_support import (
    BASKET_FIELDS,
    BRANCH_FIELDS,
    CONCENTRATION_FIELDS,
    PRODUCT_FIELDS,
    ScriptedPort,
    actions,
    availability,
    breakdown,
    evidence_outcome,
    overview,
)

__all__ = [
    "CountingActions",
    "ScriptedPort",
    "actions",
    "admitted_script",
    "refused_overview_script",
    "request_for",
    "surface_reads",
]

ORGANIZATION = "org1"
ACCOUNT = "acc1"
SOURCE = "run1"


class CountingActions:
    """Records the `view_id` of every read, then serves it from the real seam.

    A list rather than a counter: which views were read, and in what order, is
    what a later slice would quietly change. A bare total would not see a
    substitution.
    """

    def __init__(self, inner: Any) -> None:
        """Wrap `inner`; every request appends its view id to `views`."""
        self._inner = inner
        self.views: list[str] = []

    def request(self, query: Any) -> Any:
        """Record the view read, then answer from the real orchestration."""
        self.views.append(query.view.view_id)
        return self._inner.request(query)


def admitted_script() -> dict[str, ports.ViewOutcome]:
    """The seven reachable views, each admitting.

    `PeriodComparisonView` is absent and that is `FR-170`, not an omission: the
    adapter builds only single-population bundles, so it is published and
    unreachable, and `D1-10` asserts it stays so.
    """
    return {
        seam.EXECUTIVE_OVERVIEW.view_id: overview(),
        seam.METRIC_AVAILABILITY.view_id: availability(
            (("revenue", "available", None, ()),)
        ),
        seam.REPORT_EVIDENCE.view_id: evidence_outcome(),
        seam.BRANCH_PERFORMANCE.view_id: breakdown(
            seam.BRANCH_PERFORMANCE, BRANCH_FIELDS, (("s1", "revenue", "1", "complete"),)
        ),
        seam.PRODUCT_CATEGORY.view_id: breakdown(
            seam.PRODUCT_CATEGORY,
            PRODUCT_FIELDS,
            (("category", "c", "revenue", "1", "complete"),),
        ),
        seam.BASKET.view_id: breakdown(
            seam.BASKET, BASKET_FIELDS, (("revenue", "1", "complete", ()),)
        ),
        seam.CONCENTRATION.view_id: breakdown(
            seam.CONCENTRATION,
            CONCENTRATION_FIELDS,
            (("product", "revenue", "1", "complete"),),
        ),
    }


def refused_overview_script() -> dict[str, ports.ViewOutcome]:
    """The admitted seven, with S-1 refusing so `read_cards` returns early."""
    script = admitted_script()
    script[seam.EXECUTIVE_OVERVIEW.view_id] = ports.ViewOutcome(
        kind=ports.KIND_REFUSED,
        refusal=ports.ViewRefusal(cause="incompatible source shape"),
    )
    return script


def request_for(source_id: str = SOURCE) -> CardsRequest:
    """One organization member's request for one run."""
    return CardsRequest(
        organization_id=ORGANIZATION, account_id=ACCOUNT, source_id=source_id
    )


def surface_reads(
    script: dict[str, ports.ViewOutcome], selection: ControlSelection
) -> tuple[str, ...]:
    """Drive the real `read_surface` once and return the views it read, in order."""
    counting = CountingActions(actions(ScriptedPort(script)))
    read_surface(counting, request_for(), selection=selection)
    return tuple(counting.views)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d109_read_counts.py -v`
Expected: PASS, 6 tests.

- [ ] **Step 5: Prove each bound can fail**

A read-count bound that cannot fail is the defect this repository keeps finding. Verify by mutation,
one at a time, restoring after each — and confirm with `git diff` that the restore shows **zero
deletions** before moving on:

1. In `shell_decisions.py` `read_surface`, add a second `read_products(actions, routed(PRODUCT_CATEGORY))`
   call. Expected: `test_the_admitted_page_reads_seven_views_each_exactly_once` and
   `test_no_view_is_read_twice_on_any_ordinary_path` both FAIL.
2. In `_unsupported_read`, change `if not asked:` to `if False:`. Expected:
   `test_a_real_filter_adds_no_read` FAILS — an ordinary request now reads eight.
3. In `card.py` `read_cards`, move the `qualifiers = ...` line above the `if projection is None`
   guard. Expected: `test_a_refused_overview_reads_five_because_cards_returns_early` FAILS.

Record each mutant and its observed failure for the ledger (Task 3). A mutant that does not fail
means the bound is decorative and the test must be strengthened before proceeding.

- [ ] **Step 6: Commit**

```bash
git add tests/d109_support.py tests/test_d109_read_counts.py
git commit -F - <<'MSG'
test(d1-09): bound the reads each decision path performs

`read_surface` and `read_cards` both state "each view exactly once" in prose.
This makes it an assertion, per path: seven admitted, five when the overview
refuses and `read_cards` returns early, eight only when an unroutable parameter
earns its refusal. Counted at `SemanticQueryActions.request` rather than at the
port, because `SV1-08` 3a puts the miss path at 1331 us -- a read that misses
still costs acquisition.

The counter is test-only: an accumulator in `khepri.rca.workspace` would be
state surviving a request, which `FR-169` forbids.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 2: The acquisition baseline and the non-retention assertions

**Files:**
- Create: `tests/test_d109_acquisition_baseline.py`

**Interfaces:**
- Consumes: `CountingActions`, `ScriptedPort`, `actions`, `admitted_script`, `request_for` from
  `tests.d109_support`; `ControlSelection`; `read_surface`.
- Produces: `_surface_samples() -> tuple[list[int], list[int]]`, which Task 3 calls to generate the
  ledger's figures.

- [ ] **Step 1: Write the failing test**

Create `tests/test_d109_acquisition_baseline.py`:

```python
"""The decision surface's acquisition baseline (`D1-09`; active `RCA-008`).

`SV1-08` ledger §3a fixed this slice's target and it is not projection: the
composed request measures 4003 us p50 of which projection is 11.6 us, about one
part in 345. So what is measured here is the whole surface's acquisition -- the
seven reads a page issues -- and what is asserted is that measuring changed
nothing.

**No wall-clock threshold is asserted.** `SV1-08`'s `_assert_measured` states the
rule: "a wall-clock threshold in CI is a flake, and the ledger is where a
baseline belongs." The figures live in the dated ledger beside this file, and
this module is the committed function that produced every row of it -- evidence
a reader cannot regenerate from committed code is not evidence.

**What this measures, stated so the ledger cannot overclaim.** The port is
scripted, so this is the read fan-out and the orchestration around it, not the
composed end-to-end path `SV1-08` measured over a real projection and store.
That is the right subject here -- `FR-168` governs the number of reads, and the
composed cost is already recorded in §3a.
"""

from __future__ import annotations

import statistics
import time

from khepri.rca.workspace.decision.controls import ControlSelection
from khepri.runtime.shell_decisions import read_surface
from tests.d109_support import (
    CountingActions,
    ScriptedPort,
    actions,
    admitted_script,
    request_for,
)

#: Same sample count as `SV1-08`, so the two ledgers are comparable.
_SAMPLES = 200


def _surface_samples() -> tuple[list[int], list[int]]:
    """`_SAMPLES` timings of one whole admitted page, and the reads each issued.

    The script, the selection and the request are built once, outside the loop:
    building them inside would measure the fixture. Nothing is warmed, memoized
    or reordered -- the loop drives the same `read_surface` the route drives.
    """
    script = admitted_script()
    selection = ControlSelection(source_id="run1")
    request = request_for()
    timings: list[int] = []
    counts: list[int] = []
    for _ in range(_SAMPLES):
        counting = CountingActions(actions(ScriptedPort(script)))
        started = time.perf_counter_ns()
        read_surface(counting, request, selection=selection)
        timings.append(time.perf_counter_ns() - started)
        counts.append(len(counting.views))
    return timings, counts


def test_the_surface_acquisition_is_a_measured_distribution() -> None:
    """`FR-144` "may measure execution" -- so the whole surface is measured.

    What is asserted is the condition `FR-144` itself imposes: that measuring
    changed nothing, so no iteration warmed, cached or reordered a later one. If
    any run had been served from something retained, its read count would drop
    below the seven every other run issued.
    """
    timings, counts = _surface_samples()

    assert len(timings) == _SAMPLES
    assert statistics.median(timings) > 0
    assert set(counts) == {7}


def test_no_result_survives_between_requests() -> None:
    """`FR-168`'s line, asserted rather than reviewed.

    Coalescing within one request is legitimate; keeping a result *between*
    requests is a cache whatever it is called. Two identical consecutive requests
    must each perform the full seven reads -- a second request served from
    anything retained would read fewer.
    """
    script = admitted_script()
    selection = ControlSelection(source_id="run1")
    request = request_for()

    first = CountingActions(actions(ScriptedPort(script)))
    read_surface(first, request, selection=selection)
    second = CountingActions(actions(ScriptedPort(script)))
    read_surface(second, request, selection=selection)

    assert len(first.views) == 7
    assert first.views == second.views


def test_the_same_port_across_two_requests_still_reads_twice() -> None:
    """The stronger form: one shared port, so nothing can hide in a fresh fake.

    The test above builds a new `ScriptedPort` per request, which would mask a
    cache held on the port itself. Here both requests share one port and the
    projection count must double -- if the surface retained anything keyed by
    run, the second request would not reach the port at all.
    """
    port = ScriptedPort(admitted_script())
    selection = ControlSelection(source_id="run1")
    request = request_for()

    read_surface(CountingActions(actions(port)), request, selection=selection)
    after_first = len(port.requests)
    read_surface(CountingActions(actions(port)), request, selection=selection)

    assert after_first == 7
    assert len(port.requests) == 14
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d109_acquisition_baseline.py -v`
Expected: PASS if Task 1 Step 3 already exported `ScriptedPort` and `actions`. If it did not, FAIL
with `ImportError: cannot import name 'ScriptedPort' from 'tests.d109_support'` — add both to that
module's `__all__` (they are already imported there for `surface_reads`, so no new import is
needed) and re-run.

This task's RED is the mutation in Step 4, not an import error: the non-retention properties are
the subject, and the way to see them fail is to introduce retention.

- [ ] **Step 3: Run test to verify it passes**

Run: `PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest tests/test_d109_acquisition_baseline.py -v`
Expected: PASS, 3 tests.

- [ ] **Step 4: Prove the non-retention assertions can fail**

Introduce a cache deliberately and confirm the tests catch it, then restore and verify with
`git diff` that zero lines were deleted:

In `tests/d109_support.py`, give `CountingActions` a module-level dict keyed by `view_id` that
returns a stored outcome on a second request instead of delegating. Expected:
`test_the_same_port_across_two_requests_still_reads_twice` FAILS with 7 rather than 14, and
`test_the_surface_acquisition_is_a_measured_distribution` FAILS because `set(counts)` is no longer
`{7}`.

This is the mutant that matters for this task: it is the exact shape `FR-168` forbids, and if both
tests pass with it in place they are asserting nothing.

- [ ] **Step 5: Capture the measured figures**

Run the baseline once and record min / p50 / p90 / max for the ledger:

```bash
PYTHONPATH="src;." ./.venv/Scripts/python.exe -c "
import statistics
from tests.test_d109_acquisition_baseline import _surface_samples
t, c = _surface_samples()
q = statistics.quantiles(t, n=10)
print(f'min={min(t)//1000}us p50={int(statistics.median(t))//1000}us '
      f'p90={int(q[8])//1000}us max={max(t)//1000}us reads={sorted(set(c))}')
"
```

Record the exact output, with the machine and date. It is a figure to know the shape of the cost
by — not a tolerance.

- [ ] **Step 6: Commit**

```bash
git add tests/test_d109_acquisition_baseline.py tests/d109_support.py
git commit -F - <<'MSG'
test(d1-09): measure surface acquisition and assert nothing is retained

The target is acquisition, not projection: `SV1-08` 3a measures the composed
request at 4003 us p50 with projection at 11.6 us. So the whole admitted page is
sampled 200 times in that ledger's shape, and no wall-clock threshold is
asserted -- a threshold in CI is a flake and the ledger is where a baseline
belongs.

Non-retention is asserted rather than reviewed, in two forms: two requests over
fresh ports read the same seven, and two requests over one shared port reach the
port fourteen times. A surface retaining anything keyed by run fails the second.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 3: The evidence ledger

**Files:**
- Create: `docs/superpowers/plans/2026-09-15-d1-09-acquisition-evidence.md`

**Interfaces:**
- Consumes: the measured output of Task 2 Step 5 and the mutation results of Task 1 Step 5 and
  Task 2 Step 4.
- Produces: the dated record `RCA-008` §Verification's measurement discipline requires.

- [ ] **Step 1: Write the ledger**

Follow `docs/superpowers/plans/2026-09-09-sv1-08-baseline-evidence.md`'s structure: a verdict table
stated first, then one section per finding, each marked **MEASURED**, **HELD**, or **NOT
EXERCISED** — never "PASS" for something that was never able to fail. Sections:

1. **Verdict, stated first** — a table of each finding and its state.
2. **Read counts per path — MEASURED.** The five-row table from this plan, naming
   `tests/test_d109_read_counts.py` as the committed test that produced it.
3. **Surface acquisition latency — MEASURED.** Min/p50/p90/max from Task 2 Step 5, the sample
   count, machine and date, and the caveat `SV1-08` carries: one machine, one run, no approved
   workload; a figure to know the shape by, not a tolerance. **State plainly that the port is
   scripted**, so this is the read fan-out and orchestration rather than the composed end-to-end
   path §3a measured — a reader must not take it for an end-to-end figure.
4. **How each bound was made able to fail — MEASURED.** The three mutants from Task 1 Step 5 and
   the cache mutant from Task 2 Step 4, each with the test that caught it. A bound with no recorded
   mutant is decorative.
5. **The prohibitions — HELD.** No cache, pre-aggregation, materialized view, sampling or persisted
   projection added; no production module changed; the counter is test-only, so `FR-169` and
   §Retention are untouched.
6. **What this slice did not do, and whose it is.** Coalescing was already performed by `D1-03` and
   `D1-05` and is recorded here as verified rather than rebuilt; `read_limits` and `read_overview`
   have no production caller and removing them is not this slice's call; `PeriodComparisonView`
   stays unreachable by `FR-170` and is `D1-10`'s to keep asserted.

- [ ] **Step 2: Verify every figure is regenerable**

For each number in the ledger, name the committed function that produces it. `SV1-08`'s rule:
"evidence a reader cannot regenerate from committed code is not evidence." A figure with no named
producer must be removed, or its producer committed.

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-09-15-d1-09-acquisition-evidence.md
git commit -F - <<'MSG'
docs(d1-09): the acquisition and read-count evidence ledger

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
```

---

### Task 4: Full verification and the pull request

**Files:** none changed.

- [ ] **Step 1: Run the full suite, not the targeted one**

Changing a shared test-support module can break suites never opened. Run everything:

```bash
PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-d109
```

Expected: no new failures against `main`'s count. Use a dedicated `--basetemp`: two pytest runs in
one tree collide and produce phantom `WinError 32` teardown errors. Note `pytest -m unit` deselects
everything here — the marker is unused.

- [ ] **Step 2: Lint**

```bash
./.venv/Scripts/python.exe -m ruff check .
```

Expected: clean. Do **not** run `ruff format` — there is no CI format gate and it reformats
unrelated files. Ruff counts characters, not bytes, so a `§` in a docstring is one column.

- [ ] **Step 3: CodeScene pre-flight**

Fetch first — a stale `origin/main` makes `analyze_change_set` return empty results and a
meaningless pass:

```bash
git fetch origin
```

Then run `analyze_change_set` against `origin/main`. All three new files must score 10.00. If
`d109_support.py` trips Low Cohesion, fold the offending fixture into the existing builder rather
than adding a helper — extracting helpers raises the module mean.

- [ ] **Step 4: Open the pull request**

One PR carrying every commit — plan and RED first, then implementation, then the ledger. Title:
`feat(d1-09): bound the reads each surface performs, and measure what they cost`.

The body states: the slice ships no surface and changes no production code; the five measured
per-path counts; that coalescing was already performed by `D1-03`/`D1-05` and is verified rather
than rebuilt; the four mutants and what caught them; and the two things left for `D1-10` — the
`FR-170` unreachability assertion and the parity/isolation evidence.

End the body with:

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 5: Do not merge**

`main` requires the owner's approval. Report the PR number and CI state; do not merge without an
explicit in-session delegation from the owner.

---

## Self-Review

**Spec coverage.** `FR-168` — Task 1 bounds the read counts and Task 2 asserts nothing survives
between requests, in two forms. `RCA-008` §Verification's measurement discipline — Task 2 measures
and Task 3 records in `SV1-08`'s shape. `FR-169`/§Retention — held by construction: the counter is
test-only, and Task 3 §5 records it. `FR-170` — this slice does not make `PeriodComparisonView`
reachable, stated in "What this slice does NOT do" and re-asserted in the ledger. The allocation
plan's three acceptance clauses map to Task 2 Step 5 (a measured baseline in the ledger's shape),
Task 1 (read counts asserted per surface), and Task 2's two non-retention tests (asserted rather
than reviewed).

**Placeholder scan.** No TBDs. Every code step carries literal code. The ledger task carries a
section-by-section specification rather than finished prose, because its content is measured output
that cannot exist before Tasks 1–2 run; each section names what must appear in it.

**Type consistency.** `CountingActions.views` is `list[str]` throughout; `surface_reads` returns
`tuple[str, ...]` and every assertion compares against a tuple. `admitted_script()` and
`refused_overview_script()` both return `dict[str, ports.ViewOutcome]`, which is what
`ScriptedPort.__init__` accepts. `request_for()` returns `CardsRequest`, matching `read_surface`'s
second parameter. `ControlSelection` is constructed with `source_id` in every case — it has no
default — and `read_surface` takes `selection` keyword-only with no default, both deliberately.
`_surface_samples` returns `tuple[list[int], list[int]]` and Task 2 Step 5 and Task 3 both unpack it
as `t, c`.

**One gap, named rather than hidden.** Task 2 measures the surface over a *scripted port*, not over
the real projection and store — so it measures the read fan-out and the orchestration, not the
4003 µs composed path `SV1-08` measured end to end. That is the right subject for this slice
(`FR-168` governs the number of reads, and the composed cost is already in `SV1-08` §3a), but the
ledger must say so plainly, and Task 3 §3 requires it.
