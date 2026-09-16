# RCA-009 Period Comparison Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `PeriodComparisonView` reachable through the shipped semantic-query composition root by relocating the existing comparison operand derivation into one shared runtime seam, and remove every `FR-170` asserted-absence claim in the same slice.

**Architecture:** `SemanticQueryActions` already resolves scope and loads `AnalysisRun` rows, and `RRA-014`'s `project` already admits *one* bundle whose `bundle_version` declares two populations. The missing join is a branch in `semantic_view_adapter.py` that, for `PeriodComparisonView` only, derives one operand per run through a shared seam extracted from `comparison_assembly.py`, asks that seam to admit the ordered pair, and hands projection the resulting `CrossVersionBundle` as a one-element tuple. Every other view continues through the existing single-population flow untouched.

**Tech Stack:** Python 3.13, pytest, SQLAlchemy, Jinja2. Run tests with `./.venv/Scripts/python.exe -m pytest`.

**Spec:** `governance/specifications/RCA-009.md` (active; `FR-172`–`FR-180`). Read it before Task 1 — this plan argues from it throughout.

**Roadmap item:** §17 item 26 of `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.

## Global Constraints

- **One slice, one PR.** `RCA-009` §Implementation preconditions 2 and 3: source reachability and `FR-170` absence removal ship together; neither is a preparatory slice for the other. Plan+RED commit, then implementation commit, in one PR.
- **No second operand derivation** (`FR-180`). If the shared seam cannot serve a caller, that is a defect in the seam, not grounds for a parallel path.
- **Completeness is never inferred from period bounds** (`FR-180`). It stays the `RRA-003` coverage manifest's answer via `admits_completeness`.
- **No new refusal cause, route, view, view version, read model, calculation, persistence, schema, migration, cache, materialization, sampling, telemetry, audit record, or retention rule** (`RCA-009` §Exclusions, `FR-178`).
- **No wall clock inside the seam or the composition branch** (`FR-180`). The time source is supplied from the composition root.
- **Do NOT run `ruff format`** — there is no CI format gate; run `ruff check .` only.
- **Run the full suite**, not a targeted one. Removing a read-model field breaks suites this plan does not name.
- **CodeScene:** every new file must score 10.00 in the server-side Code Health Review, and no tracked hotspot may decline. Frozen dataclass arguments, ≤4 parameters per function.
- Commit message trailer: `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.

---

## §0. Design calls and findings — read before Task 1

These are decisions this plan makes, with the grounds that determine them, plus one finding it deliberately does **not** build. Recorded here rather than resolved silently, per the repo's governance convention.

### 0.1 A refused pair returns `None`, not a `ViewRefusal` — determined, not preferred

The comparison path's causes and `RRA-014`'s causes are **disjoint vocabularies**:

- `RRA-014`'s closed set (`src/khepri/rra/semantic_views/refusals.py:43-68`) is seven view-contract causes: `unknown view`, `unknown version`, `unknown metric`, `unknown dimension`, `unknown filter`, `incompatible source shape`, `missing required evidence`.
- The comparison path's causes live in `RRA-008`'s `src/khepri/rra/analysis/dataset_period.py:56-57`: `CAUSE_RETAIL_DAY = "retail day boundary mismatch"` and `CAUSE_INCOMPLETE = "incomplete coverage"`.

The branch therefore maps an inadmissible pair to `None`. Four grounds, in order of force:

1. **`FR-175` states the disjunction itself**: "A mismatch returns the existing governed refusal **or unavailable outcome**." The spec anticipated this.
2. **A foreign cause carries no bilingual wording.** `REFUSAL_CAUSES` is *derived* from `VIEW_REFUSALS`, so a `ViewRefusal(CAUSE_INCOMPLETE)` has no Arabic or English text — it fails `FR-177` before it even reaches the closed-set question.
3. **`refusals.py`'s own docstring** bars widening: "A condition that seems to need an eighth cause is an `RRA-014` amendment," citing `#408` where exactly this was folded rather than widened. `FR-174` bars new refusal derivation and §Exclusions bars a new refusal cause.
4. **`None` is the declared contract, not an escape from it.** `src/khepri/rca/semantic_queries/ports.py:161-164`: "`None` is part of the contract… The RCA half maps it to the one uniform unavailable outcome, so that outcome is built in exactly one place and cannot drift." That satisfies `FR-173`'s content-free outcome "without identifying which source failed" and `RCA-006` `FR-146`.

### 0.2 Pair admission belongs in the seam, not only per-source derivation

`CrossVersionAssembly._assemble` (`comparison_assembly.py:163-184`) applies a refusal **after** `assemble_crossversion` returns a bundle:

```python
if subject.timezone != baseline.timezone:
    return _refused_outcome(CAUSE_RETAIL_DAY)
```

A seam covering only per-source derivation would let the semantic-view branch **admit a pair the comparison surface refuses** — an incompatibility degrading into another result, which §Invariants bars, and a divergence from `FR-180`'s "every refusal cause stays the one the existing path already produces". No existing test would catch it.

So the seam exposes **two** entry points: `derive_operand(...)` and `admit_pair(...)`, the latter wrapping `assemble_crossversion` **and** the timezone comparison, returning admitted-bundle-or-cause. `CrossVersionAssembly._assemble` calls `admit_pair` instead of duplicating it.

*The narrower alternative, stated for the owner:* the branch could call only a shared per-source helper and leave the pair check in `comparison_assembly.py`. This plan rejects it on the grounds above, but the choice is visible rather than buried.

**The same divergence exists a second time, at pair shape.** `OrderedVersionIds` is documented as "the two identifiers **after** the pairwise shape has already been accepted" (`comparisons.py:76-77`), and that acceptance happens in `ComparisonActions.request` — `_shape_refused` (`comparisons.py:174-177`) refuses a self-pair or an over-long request *before* assembly, answering `unordered_refusal()`. The semantic-query path never enters that layer, so `request.source_ids` arrives validated for neither.

`_admission_cause` does **not** close the gap. It checks organization scope (`CAUSE_SCOPE`, `crossversion_assembly.py:186-187`) and package compatibility, but nothing there refuses a pair whose two sides are the same run. So a request naming one run twice would be assembled and projected as a comparison of a period against itself — admitted by the view, refused by the surface.

Therefore `admit_pair` carries the self-pair check too, for the same reason it carries the timezone check: a caller that skipped it admits what the other refuses. `ComparisonActions` keeps its own `_shape_refused` gate, which becomes redundant rather than moved — it fires earlier and carries the audit event that `FR-178` bars this path from writing. Redundant guards need separate evidence, so Task 3 tests the seam's check directly rather than relying on the surface's.

Arity (`_has_extra_versions`) is handled in the branch by the `len(sources) != 2` guard, since `sources` is already a tuple by the time the adapter sees it.

### 0.3 `wiring.py` is not enumerated in §Scope — flagged, not self-authorized

§Scope names the adapter, the `FR-170` sites, the shared seam with its consumption edits, and `tests/`. It does not name `src/khepri/runtime/wiring.py`, which this slice must edit at line 630 to supply the adapter its new collaborators.

The ground for proceeding is `FR-180`'s own sentence: the seam's collaborators "are constructed at the composition root that already builds both consumers" — and that root is `wiring.py` (line 355 builds `CrossVersionAssembly`, line 630 builds `SemanticViewAdapter`). An authority that requires construction at a root it does not name is read as authorizing the edit its own requirement forces.

**This is recorded as an enumeration gap for the owner.** If the reading is rejected, the fix is a one-line §Scope amendment, not a redesign. Do not expand the `wiring.py` edit beyond supplying existing collaborators.

### 0.4 The time source is injected at construction, not threaded through the protocol

`SemanticViewPort.project(request, sources)` (`ports.py:152`) carries no `now`, and widening it would edit the seam `RCA-007` excludes touching. `FR-180` requires the time source be "supplied to the seam, never read inside it or inside the composition branch," because "a derivation that read the wall clock itself would make one request's outcome depend on when it ran, which §Outcome forbids."

So `SemanticViewAdapter.__init__` takes a `now` callable alongside its ports, supplied at `wiring.py:630`. The protocol is unchanged.

### 0.5 The branch predicate reads the published definition, not a string

`FR-172` is a conjunction: the exact published `PeriodComparisonView` version **and** a definition admitting the two-population shape. The branch resolves the definition and reads `accepted_source_shape`, never `request.view_id == "PeriodComparisonView"`. A string compare would silently keep routing the view if its published shape ever changed.

The predicate admits **both** `SHAPE_TWO_POPULATION` and `SHAPE_EITHER_BUNDLE` (`contracts.py:40-58`). `FR-172` says "admits the governed two-population source shape", and a view declaring `either_bundle` admits it — testing equality against `SHAPE_TWO_POPULATION` alone would mis-route such a view into the single-population path. No published view declares `either_bundle` today; the registry-derived test asserts that rather than assuming it, so a view added later is caught rather than silently routed.

`define_view` **raises** `UnknownView` rather than returning `None` (`registry.py:211-222`), so the resolution helper catches it. A raise escaping the branch would reach the caller as a broken read instead of `FR-146`'s content-free miss.

### 0.6 Verified: `CrossVersionBundle` already classifies as two-population

No change is needed. `_shape_of` (`projection.py:157-172`) requires all of `_REQUIRED_MEMBERS = ("identity", "figures", "caveats", "evidence", "bundle_version")` and then looks for the literal `"crossversion"`. `CrossVersionBundle` (`crossversion_bundle.py:290-308`) declares `identity`, `figures`, `caveats`, `evidence` and a `bundle_version` property returning `CROSSVERSION_BUNDLE_VERSION = "rra006.crossversion.bundle.v1"`, which contains the marker.

Note `_candidate` admits **exactly one** source (`projection.py:358-360`): the branch passes a **1-tuple** containing the assembled `CrossVersionBundle`, never a 2-tuple of runs.

### 0.7 Finding filed, not built: the card's now-unexplained `comparison` field

`FR-170` removal is "removal only. No surface redesign is authorized." After this slice, `MetricCard.comparison` stays `None` and `SURFACE_VIEWS` stays seven — adding the view there would change `offered_filters` output, which is the surface redesign §Scope bars and the read model §Exclusions bar.

That leaves the card carrying a named `comparison` field that is empty **with no stated reason**, against `card.py:13-16`'s own "named rather than omitted" principle. Whether the D1 decision surface should now consume the reachable view is `RCA-008`'s call, not this slice's.

**This is a finding for the owner. Do not build it.** The view becomes reachable through the semantic-query composition root (§Outcome), which is a different consumer from the decision surface.

---

## File Structure

**Created:**
- `src/khepri/runtime/comparison_operands.py` — the `FR-180` shared seam. Owns per-source operand derivation and pair admission. Both `comparison_assembly.py` and `semantic_view_adapter.py` call it. This is `RCA-009`'s artifact and does not enter `RCA-007` §Scope.
- `tests/test_rca009_period_comparison_composition.py` — reachability, order, isolation, fail-closed, provenance, parity, no-write, no-event evidence.
- `tests/test_rca009_operand_seam_parity.py` — proof the `FR-180` relocation changed no behaviour.

**Modified:**
- `src/khepri/runtime/comparison_assembly.py` — consumption edits only: import from the seam, delete the relocated privates, call `admit_pair` in `_assemble`. Run *selection* (`_latest_completed`) stays here per `FR-180`.
- `src/khepri/runtime/semantic_view_adapter.py` — the one new composition branch plus the injected clock.
- `src/khepri/runtime/wiring.py:630` — supply the adapter its collaborators (§0.3).
- `src/khepri/rca/workspace/decision/card.py` — remove `comparison_unreachable` field and its `FR-170` prose.
- `src/khepri/runtime/shell_decisions.py` — remove `COMPARISON_UNREACHABLE`, its export, its read-model field and its assignment.
- `src/khepri/runtime/shell_templates/_decision_cards.html.j2` — remove lines 12 and 16-17.
- `src/khepri/runtime/shell_controls.py:66-70` — correct the "Seven and not eight" comment prose only; `SURFACE_VIEWS` itself is unchanged (§0.7).
- `tests/test_d103_metric_card.py`, `tests/test_d104_breakdowns_and_limits.py`, `tests/test_d105_evidence_drawer.py` — remove the absence assertions.

---

## Task 1: Extract the shared operand seam (`FR-180`)

Mechanical relocation. No behaviour changes. Run selection stays in `comparison_assembly.py`.

**Files:**
- Create: `src/khepri/runtime/comparison_operands.py`
- Modify: `src/khepri/runtime/comparison_assembly.py`
- Test: `tests/test_rca009_operand_seam_parity.py`

**Interfaces:**
- Consumes: `ComparisonAssemblyPorts`, `AnalysisRun`, `CrossVersionRequest`, `assemble_crossversion`, `CAUSE_RETAIL_DAY`, `CAUSE_INCOMPLETE`.

> **Import trap — two functions share this name.** `refusal_wording` exists in **both** `khepri.rra.analysis.comparison_narrative` (line 188) and `khepri.rra.semantic_views.refusals` (line 163), with identical signatures. The seam must import the **comparison_narrative** one, which is what `comparison_assembly.py:33` already imports. The `refusals` one governs the seven view causes and would return no wording for `CAUSE_RETAIL_DAY` — a refusal published with empty text in both languages, failing `FR-177` silently.
- Produces:
  - `ComparisonOperand` (frozen): `package: FactPackage`, `period: DatasetPeriod`, `aggregate_scope: str | None`, `run_id: str`, `timezone: str`
  - `OperandLoad` (frozen): `operand: ComparisonOperand | None`, `incomplete: bool`
  - `OperandRequest` (frozen, **public entry type**): `ports: ComparisonAssemblyPorts`, `owner_id: str`, `run: AnalysisRun`, `now: datetime`
  - `_OperandAsk` (frozen, **private**): the original `comparison_assembly` type with `run: AnalysisRun` replacing `version_id`, plus `bound: _RunPackage`. Kept private so the public entry type carries only what a caller supplies.
  - `PairAdmission` (frozen): `bundle: object | None`, `cause: str | None`, `wording: dict[str, str]`
  - `derive_operand(request: OperandRequest) -> OperandLoad`
  - `admit_pair(owner_id: str, subject: ComparisonOperand, baseline: ComparisonOperand) -> PairAdmission`
- Also consumes `CAUSE_UNORDERED_PAIR = "unordered pair"` from `khepri.rra.analysis.dataset_period` (line 51) — the same module that defines `CAUSE_RETAIL_DAY` and `CAUSE_INCOMPLETE`. Import it; do not re-declare the constant.

- [ ] **Step 1: Write the failing parity test**

```python
"""`RCA-009` `FR-180`: one derivation states a comparison operand.

Authority: active `RCA-009` `FR-180`. The relocation redefines no calculation,
completeness, timezone, compatibility, provenance, ordering, refusal, or
isolation semantics.
"""

from __future__ import annotations

import inspect

from khepri.runtime import comparison_assembly, comparison_operands


def test_the_seam_publishes_both_entry_points() -> None:
    """`FR-180` -- one seam derives operands and admits the pair."""
    assert hasattr(comparison_operands, "derive_operand")
    assert hasattr(comparison_operands, "admit_pair")


def test_the_assembly_holds_no_second_operand_derivation() -> None:
    """`FR-180` -- a second implementation is not authorized anywhere.

    The relocated privates are gone from the assembly module rather than left
    beside the seam as an agreeing copy: two agreeing copies are what this
    requirement exists to prevent.
    """
    relocated = (
        "_operand_from",
        "_manifest_of",
        "_dataset_period",
        "_granularity",
        "_complete",
        "_scope_complete",
        "_session_of",
        "_package_record",
        "_profile_record",
        "_verified_package",
    )
    for name in relocated:
        assert not hasattr(comparison_assembly, name), name


def test_run_selection_stays_with_the_assembly() -> None:
    """`FR-180` -- run *selection* from a version identifier is not relocated."""
    assert hasattr(comparison_assembly, "_latest_completed")
    assert not hasattr(comparison_operands, "_latest_completed")


def test_the_seam_reads_no_clock() -> None:
    """`FR-180` -- the time source is supplied, never read inside the seam."""
    source = inspect.getsource(comparison_operands)
    assert "datetime.now" not in source
    assert "utcnow" not in source
```

- [ ] **Step 2: Run it to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca009_operand_seam_parity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'khepri.runtime.comparison_operands'`

- [ ] **Step 3: Create the seam by moving code verbatim**

Create `src/khepri/runtime/comparison_operands.py`. Move these from `comparison_assembly.py` **unchanged in body**, renaming only `_Operand` → `ComparisonOperand`, `_Load` → `OperandLoad`, `_OperandAsk` → `OperandRequest`, `_operand_from` → the private half of `derive_operand`:

`_Operand`, `_Load`, `_RunPackage`, `_OperandAsk`, `_operand_from`, `_manifest_of`, `_session_of`, `_package_record`, `_profile_record`, `_verified_package`, `_dataset_period`, `_granularity`, `_complete`, `_scope_complete`, `_cross_request`, `_CALENDAR_DAY_HOUR`, `_PACKAGE_FAULTS`.

`derive_operand` is `_load_operand`'s body **minus** its first three lines (the `_latest_completed` call and the `run is None or run.package_digest is None` guard), because the run arrives in `OperandRequest`:

```python
def derive_operand(request: OperandRequest) -> OperandLoad:
    """One run's governed operand, or why the pair cannot use it.

    `FR-180`: this is the one derivation that states a comparison operand.
    Completeness stays the `RRA-003` coverage manifest's answer -- `_complete`
    asks `admits_completeness` -- and is never inferred from period bounds.

    Run *selection* is not here. `comparison_assembly` selects the latest
    completed run for a version identifier; `SemanticQueryActions` supplies a
    run it already read under the caller's scope. Both arrive holding a run.
    """
    run = request.run
    if run.package_digest is None:
        return OperandLoad(None, False)
    session = _session_of(request.ports, run.run_id, request.owner_id)
    if session is None:
        return OperandLoad(None, False)
    record = _package_record(request.ports.packages, session.session_id, request.now)
    if record is None:
        return OperandLoad(None, False)
    try:
        package = _verified_package(record)
    except PackageDoesNotVerify:
        return OperandLoad(None, False)
    if package is None:
        return OperandLoad(None, False)
    if run.package_digest != package.digest:
        return OperandLoad(None, False)
    bound = _RunPackage(run=run, session=session, package=package)
    return _operand_from(
        _OperandAsk(
            ports=request.ports,
            owner_id=request.owner_id,
            run=run,
            now=request.now,
            bound=bound,
        )
    )
```

`_operand_from` keeps its body verbatim, with one substitution: it read `ask.version_id`, and now reads `ask.bound.run.version_id`. That is the run's **own** recorded version, not a caller-supplied one — the period's `dataset_version_id` must stay the identity the run recorded, or the same package would yield a period with a different identity depending on who asked.

`admit_pair` carries the pair step (§0.2):

```python
def admit_pair(
    owner_id: str, subject: ComparisonOperand, baseline: ComparisonOperand
) -> PairAdmission:
    """The admitted two-population bundle, or the one cause that refused it.

    `FR-180`: every refusal cause stays the one the existing path already
    produces. The retail-day comparison is here rather than in either caller
    because a caller that skipped it would admit a pair the other refuses --
    an incompatibility degrading into another result, which §Invariants bars.
    """
    if subject.run_id == baseline.run_id:
        # `ComparisonActions._shape_refused` refuses a self-pair before assembly and
        # `_admission_cause` does not -- it checks scope and package compatibility,
        # neither of which sees one run named twice. A caller that reached assembly
        # without passing that earlier gate would compare a period against itself and
        # be admitted. The cause is the one the comparison path already produces.
        return PairAdmission(None, CAUSE_UNORDERED_PAIR, dict(refusal_wording(CAUSE_UNORDERED_PAIR)))
    built = assemble_crossversion(_cross_request(owner_id, subject, baseline))
    if isinstance(built, CrossVersionRefusal):
        return PairAdmission(None, built.cause, dict(built.wording))
    if subject.timezone != baseline.timezone:
        # `RRA-008` §Period rule refuses a pair whose periods differ in retail-day
        # boundary, and the coverage manifest's timezone is that boundary. The frozen
        # period type carries an hour, not a zone, so the family's predicate cannot
        # see this; the comparison is made once every frozen predicate has admitted
        # the pair, under the cause the family already froze. Its proper home is the
        # predicate itself, an owner amendment recorded in the roadmap row.
        return PairAdmission(None, CAUSE_RETAIL_DAY, dict(refusal_wording(CAUSE_RETAIL_DAY)))
    return PairAdmission(built, None, {})
```

- [ ] **Step 4: Rewire `comparison_assembly.py` to consume the seam**

Delete the relocated definitions. `_load_operand` keeps run selection and delegates:

```python
def _load_operand(
    ports: ComparisonAssemblyPorts, owner_id: str, version_id: str, now: datetime
) -> OperandLoad:
    run = _latest_completed(ports.workspace, owner_id, version_id)
    if run is None:
        return OperandLoad(None, False)
    return derive_operand(OperandRequest(ports=ports, owner_id=owner_id, run=run, now=now))
```

`_assemble` calls `admit_pair`:

```python
def _assemble(
    self, owner_id: str, subject: ComparisonOperand, baseline: ComparisonOperand
) -> ComparisonOutcome | None:
    admission = admit_pair(owner_id, subject, baseline)
    if admission.bundle is None:
        return ComparisonOutcome(
            kind=KIND_REFUSED,
            refusal=ComparisonRefusal(admission.cause, admission.wording),
        )
    surfaces = self._render(admission.bundle, subject.run_id, baseline.run_id)
    if surfaces is None:
        return None
    return ComparisonOutcome(kind=KIND_ADMITTED, surfaces=surfaces, bundle=admission.bundle)
```

- [ ] **Step 5: Run the parity test and the whole comparison suite**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca009_operand_seam_parity.py tests/ -k "comparison or crossversion" -v`
Expected: PASS. Every pre-existing comparison test must pass **unchanged** — that is the `FR-180` "changed no behaviour" proof.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/runtime/comparison_operands.py src/khepri/runtime/comparison_assembly.py tests/test_rca009_operand_seam_parity.py
git commit -F- <<'EOF'
refactor(rca-009): relocate the comparison operand derivation to one shared seam

`FR-180`: one runtime seam derives the governed package, `DatasetPeriod`,
aggregate scope, timezone and run identity, and admits the ordered pair.
Run selection stays with the comparison assembly. No calculation,
completeness, timezone, compatibility, provenance, ordering, refusal or
isolation semantics change.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 2: The composition branch (`FR-172`–`FR-176`)

**Files:**
- Modify: `src/khepri/runtime/semantic_view_adapter.py`, `src/khepri/runtime/wiring.py:630`
- Test: `tests/test_rca009_period_comparison_composition.py`

**Interfaces:**
- Consumes: `derive_operand`, `admit_pair`, `OperandRequest` (Task 1); `projection.project`; `define_view`, `view_ids`, `UnknownView` (from `khepri.rra.semantic_views.registry`); `SHAPE_TWO_POPULATION`, `SHAPE_EITHER_BUNDLE` (from `khepri.rra.semantic_views.contracts`).
- Produces: `SemanticViewAdapter(packages, *, operands=None, now=None)` — `operands: ComparisonAssemblyPorts | None`, `now: Callable[[], datetime] | None`. Both default `None`, and the branch refuses to `None` when either is absent, so an unwired deployment fails closed rather than crashing.

- [ ] **Step 1: Write the failing reachability test**

The fixture must be **substantive** — two packages sharing metrics. A pair sharing none yields `CAUSE_INCOMPLETE` from `_crossversion_facts`, which is the null case dressed as a pass.

```python
"""`RCA-009`: the Period Comparison composition branch.

Authority: active `RCA-009` `FR-172`--`FR-180`.
"""

from __future__ import annotations

from khepri.rra.semantic_views import projection
from khepri.rra.semantic_views.contracts import SHAPE_EITHER_BUNDLE, SHAPE_TWO_POPULATION


def test_an_authorized_ordered_pair_reaches_a_real_projection() -> None:
    """`FR-179` -- an admitted projection with compared figures, not an empty one.

    The distinction this asserts is `FR-179`'s own: an admitted empty projection
    is not proof of reachability, and neither is the absence of a refusal.
    """
    outcome = _composed(subject=_SUBJECT_RUN, baseline=_BASELINE_RUN)
    assert outcome is not None
    assert outcome.kind == projection.KIND_ADMITTED
    assert outcome.projection.rows, "an empty projection does not prove reachability"
    assert outcome.refusal is None


def test_the_view_no_longer_refuses_for_an_incompatible_shape() -> None:
    """`FR-179` -- the refusal this slice exists to remove."""
    outcome = _composed(subject=_SUBJECT_RUN, baseline=_BASELINE_RUN)
    assert outcome.refusal is None


def test_the_caller_supplied_order_survives_composition() -> None:
    """`FR-174`, `FR-176` -- subject and baseline are the caller's, in their order."""
    forward = _composed(subject=_SUBJECT_RUN, baseline=_BASELINE_RUN)
    swapped = _composed(subject=_BASELINE_RUN, baseline=_SUBJECT_RUN)
    assert _subject_values(forward) == _baseline_values(swapped)
    assert _baseline_values(forward) == _subject_values(swapped)


def test_every_other_view_still_routes_single_population() -> None:
    """`FR-172` -- derived from the registry, asserting equality and non-emptiness.

    A subset assertion here would not see a view added to the branch.

    `SHAPE_EITHER_BUNDLE` is included in the predicate, not just
    `SHAPE_TWO_POPULATION`: `FR-172` fires for a definition that *admits* the
    two-population shape, and a view declaring `either_bundle` admits it too.
    No published view declares it today, and this asserts that rather than
    assuming it -- otherwise one added later would route through the branch
    while this test still passed.
    """
    from khepri.rra.semantic_views.registry import define_view, view_ids

    admits_two = {
        view_id
        for view_id in view_ids()
        if define_view(view_id).accepted_source_shape
        in {SHAPE_TWO_POPULATION, SHAPE_EITHER_BUNDLE}
    }
    assert admits_two == {"PeriodComparisonView"}
    assert admits_two
```

- [ ] **Step 2: Run it to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca009_period_comparison_composition.py -v`
Expected: FAIL — the composed outcome is `ViewRefusal('incompatible source shape')`, which is the measured pre-state `SV1-08` recorded.

- [ ] **Step 3: Add the branch to the adapter**

```python
def project(
    self, request: object, sources: tuple[object, ...]
) -> projection.ViewOutcome | None:
    """The view this request names over these runs, or the uniform miss."""
    if self._is_two_population(request):
        return self._compare(sources)
    bundles = self._bundles(sources)
    if bundles is None:
        return None
    return projection.project(request, bundles)  # type: ignore[arg-type]

def _is_two_population(self, request: object) -> bool:
    """`FR-172` -- the published definition's shape, never the view's name.

    A string compare against the view id would keep routing this view here if
    its published shape ever changed, which is the opposite of what `FR-172`
    asks. `SHAPE_EITHER_BUNDLE` is admitted for the same reason: `FR-172` fires
    for a definition that *admits* the two-population shape, and that one does.

    An unpublished view resolves to `None` and falls through to the existing
    single-population path, where `validate` refuses it under the cause it
    already owns -- this branch invents no refusal (`FR-174`).
    """
    definition = _definition_of(request)
    return definition is not None and definition.accepted_source_shape in {
        SHAPE_TWO_POPULATION,
        SHAPE_EITHER_BUNDLE,
    }


def _definition_of(request: object) -> SemanticViewDefinition | None:
    """The published definition this request names, or `None`.

    `define_view` raises `UnknownView` rather than returning `None`, and a raise
    escaping here would reach the caller as a broken read instead of `FR-146`'s
    content-free miss -- a fail-open dressed as an error.
    """
    view_id = getattr(request, "view_id", None)
    if not isinstance(view_id, str):
        return None
    try:
        return define_view(view_id)
    except UnknownView:
        return None

def _compare(self, sources: tuple[object, ...]) -> projection.ViewOutcome | None:
    """`FR-173`--`FR-176` -- the ordered pair, assembled by the governed path.

    Every miss is the same miss. An unwired deployment, a run whose operand
    cannot be derived, and a pair the governed path refuses all return `None`,
    which `SemanticQueryActions` maps to the one content-free unavailable
    outcome (`ports.py`: "`None` is part of the contract, not an escape from
    it"). Nothing here reports which condition held.

    A refused pair cannot come back as a `ViewRefusal`: the comparison causes
    are `RRA-008`'s and carry no `RRA-014` wording, so naming one would publish
    a refusal with no governed text in either language (`FR-177`). `FR-175`
    admits exactly this -- "the existing governed refusal *or unavailable
    outcome*".
    """
    if self._operands is None or self._now is None:
        return None
    if len(sources) != 2:
        return None
    pair = self._operands_for(sources)
    if pair is None:
        return None
    subject, baseline = pair
    admission = admit_pair(subject.owner_id, subject.operand, baseline.operand)
    if admission.bundle is None:
        return None
    return projection.project(request, (admission.bundle,))
```

`_operands_for` derives one operand per run through the seam, returning `None` if either misses or the two runs disagree about scope:

```python
def _operands_for(self, sources: tuple[object, ...]) -> tuple[_Scoped, _Scoped] | None:
    """One operand per run, or `None` if either cannot be derived.

    All-or-nothing, matching `_bundles` and `SemanticQueryActions._scoped_sources`:
    a partial pair would let a two-population view project over one population.

    The scope equality check is not redundant. `_cross_request` maps one
    `owner_id` onto both sides, so two runs read under different scopes would be
    assembled as though they shared one -- `FR-173` requires each source be
    loaded through the same requesting organization's opaque scope.
    """
    derived: list[_Scoped] = []
    for source in sources:
        owner_id = getattr(source, "owner_id", None)
        if not isinstance(owner_id, str) or not owner_id:
            return None
        load = derive_operand(
            OperandRequest(ports=self._operands, owner_id=owner_id, run=source, now=self._now())
        )
        if load.operand is None:
            return None
        derived.append(_Scoped(owner_id=owner_id, operand=load.operand))
    subject, baseline = derived
    if subject.owner_id != baseline.owner_id:
        return None
    return subject, baseline
```

- [ ] **Step 4: Supply the collaborators at the composition root**

`wiring.py:630` (§0.3 — the enumeration gap is flagged, the edit stays minimal):

```python
port=SemanticViewAdapter(
    SqlFactPackageRepository(stack.factory),
    operands=ComparisonAssemblyPorts(
        packages=stack.services.packages,
        profiling=stack.services.profiling,
        jobs=SqlJobSessions(factory),
        reports=SqlRunReportStore(factory),
        provenance=SqlRunProvenanceStore(factory),
        workspace=SqlWorkspaceRecordStore(factory),
    ),
    now=lambda: datetime.now(UTC),
),
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca009_period_comparison_composition.py -v`
Expected: PASS, including a non-empty `projection.rows`.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/runtime/semantic_view_adapter.py src/khepri/runtime/wiring.py tests/test_rca009_period_comparison_composition.py
git commit -F- <<'EOF'
feat(rca-009): bind the governed two-population source to PeriodComparisonView

`FR-172`--`FR-176`: one composition branch, selected from the published
definition's accepted source shape, derives an operand per scoped run through
the `FR-180` seam, delegates assembly to the governed path, and hands the
admitted bundle to the existing projection. A refused pair returns the uniform
content-free unavailable outcome, per `FR-175`.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 3: Fail-closed, isolation and no-write evidence (`FR-173`, `FR-175`, `FR-177`, `FR-178`)

**Files:**
- Test: `tests/test_rca009_period_comparison_composition.py` (extend)

- [ ] **Step 1: Write the fail-closed and isolation tests**

```python
import pytest


@pytest.mark.parametrize(
    "case",
    [
        "missing_run",
        "corrupt_package",
        "cross_scope",
        "incomplete_coverage",
        "retail_day_mismatch",
        "self_pair",
    ],
)
def test_every_failure_yields_one_content_identical_unavailable_outcome(case: str) -> None:
    """`FR-173`, `FR-175` -- byte-identical, content-free, naming no source.

    Five distinct conditions, one answer. A test asserting only "not admitted"
    would pass while the outcomes differed and leaked which source failed.
    """
    outcomes = {_composed_for(case) for case in _ALL_FAILURE_CASES}
    assert len(outcomes) == 1
    assert _composed_for(case) == _unavailable_outcome()


def test_a_refused_pair_never_degrades_to_one_population() -> None:
    """`FR-175` -- no fallback, partial projection or single-population substitution."""
    outcome = _composed_for("retail_day_mismatch")
    assert outcome is None or outcome.projection is None


@pytest.mark.parametrize("arity", [1, 3])
def test_the_branch_fails_closed_on_the_wrong_number_of_sources(arity: int) -> None:
    """`FR-175` -- the branch owns arity once it intercepts `_candidate`."""
    assert _composed_with_arity(arity) is None


def test_the_two_runs_must_share_one_scope() -> None:
    """`FR-173` -- `_cross_request` maps one scope onto both sides.

    Redundant with `_admission_cause`'s `CAUSE_SCOPE` check by design, and
    tested separately for that reason: one outcome test passes with either
    guard alone, so neither would be proven. This drives the branch's guard by
    supplying two runs whose scopes differ before assembly is reached.
    """
    assert _composed(subject=_SUBJECT_RUN, baseline=_OTHER_ORG_RUN) is None


def test_one_run_named_twice_is_refused() -> None:
    """`FR-175` -- a self-pair is what the comparison surface refuses first.

    `_admission_cause` does not see this: it checks scope and package
    compatibility, and one run named twice passes both. Without the seam's
    check the view would admit a period compared against itself while
    `ComparisonActions._shape_refused` refuses the same request.
    """
    assert _composed(subject=_SUBJECT_RUN, baseline=_SUBJECT_RUN) is None


def test_the_seam_refuses_a_self_pair_under_the_existing_cause() -> None:
    """`FR-180` -- the cause is the one the existing path already produces.

    Asserted at the seam rather than through the branch, because the branch
    maps every cause to `None` (§0.1) and so cannot show *which* cause fired.
    """
    admission = admit_pair(_OWNER, _SUBJECT_OPERAND, _SUBJECT_OPERAND)
    assert admission.bundle is None
    assert admission.cause == CAUSE_UNORDERED_PAIR
    assert set(admission.wording) == {"ar", "en"}


def test_the_composition_writes_nothing(write_spy) -> None:
    """`FR-178` -- no row, artifact, event, counter or content-bearing log."""
    _composed(subject=_SUBJECT_RUN, baseline=_BASELINE_RUN)
    assert write_spy.writes == []
    assert write_spy.audit_events == []


def test_the_write_spy_can_fire(write_spy) -> None:
    """The zero-write assertion above is only evidence if the spy can record.

    A spy that never fires makes every no-write test pass by construction.
    """
    write_spy.record("probe")
    assert write_spy.writes == ["probe"]
```

- [ ] **Step 2: Write the bilingual parity test**

```python
def test_both_languages_carry_equal_content() -> None:
    """`FR-177` -- neither language drops a figure, caveat, refusal or evidence path."""
    arabic = _composed(language="ar")
    english = _composed(language="en")
    assert _figure_codes(arabic) == _figure_codes(english)
    assert _caveat_codes(arabic) == _caveat_codes(english)
    assert _evidence_codes(arabic) == _evidence_codes(english)
```

- [ ] **Step 3: Write the provenance test**

```python
def test_projected_values_and_provenance_equal_the_governed_source() -> None:
    """`FR-176` -- the adapter adds, suppresses and relabels nothing.

    Derived from the assembled bundle rather than restated here: comparing a
    restatement against itself is a tautology that passes every mutant.
    """
    bundle = _governed_bundle(_SUBJECT_RUN, _BASELINE_RUN)
    outcome = _composed(subject=_SUBJECT_RUN, baseline=_BASELINE_RUN)
    assert _figure_values(outcome) == _figure_values_of(bundle)
    assert _versions(outcome) == _versions_of(bundle)
    assert _evidence_codes(outcome) == _evidence_codes_of(bundle)
```

- [ ] **Step 4: Run them**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca009_period_comparison_composition.py -v`
Expected: PASS

- [ ] **Step 5: Mutation-check the three load-bearing guards**

Each guard needs its own evidence — one outcome test passes with either guard alone.

| Mutant | Must fail |
|---|---|
| `if subject.owner_id != baseline.owner_id` → `if False` | `test_the_two_runs_must_share_one_scope` |
| `if len(sources) != 2` → `if False` | the arity tests |
| `if admission.bundle is None` → `if False` | the fail-closed tests |
| `subject.timezone != baseline.timezone` → `if False` (in the seam) | `retail_day_mismatch` case |
| `subject.run_id == baseline.run_id` → `if False` (in the seam) | the two self-pair tests |

Apply each with `git diff` showing **zero deletions** other than the one line, run the named test, confirm it fails, then `git checkout --` the file.

- [ ] **Step 6: Commit**

```bash
git add tests/test_rca009_period_comparison_composition.py
git commit -F- <<'EOF'
test(rca-009): fail-closed, isolation, parity and no-write evidence

`FR-173`, `FR-175`, `FR-177`, `FR-178`: five failure conditions yield one
content-identical unavailable outcome; arity and cross-scope pairs fail closed;
both languages carry equal content; the composition writes nothing, proven with
a spy that can fire.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 4: Remove the `FR-170` asserted absence (`FR-179`)

Removal only. No surface redesign. This **must** ship in the same PR as Tasks 2–3.

**Files:**
- Modify: `src/khepri/rca/workspace/decision/card.py`, `src/khepri/runtime/shell_decisions.py`, `src/khepri/runtime/shell_templates/_decision_cards.html.j2`, `src/khepri/runtime/shell_controls.py`
- Modify: `tests/test_d103_metric_card.py`, `tests/test_d104_breakdowns_and_limits.py`, `tests/test_d105_evidence_drawer.py`
- Test: `tests/test_rca009_period_comparison_composition.py` (extend)

- [ ] **Step 1: Write the extent test**

A per-file removal leaves the tenth file. Derive the assertion from a sweep, not a list.

```python
def test_no_asserted_absence_survives_anywhere() -> None:
    """`FR-179` -- every `FR-170` assertion and explanatory claim is removed.

    An extent assertion, not a per-file one: nine files carried this marker and
    a file-by-file removal cannot see the tenth. `governance/` is excluded --
    `RCA-008` keeps `FR-170` as history, and this slice succeeds its reading
    rather than editing the artifact.

    **This file excludes itself, and that is not a loophole.** The sweep's own
    docstring and predicate contain both literals, so a sweep including itself
    could never pass. The exclusion is sound because this file *asserts the
    absence* rather than claiming Period Comparison is unreachable -- which is
    the thing `FR-179` removes. Exactly one path is exempt and it is named by
    `__file__`, so the exemption cannot silently widen to a second file.
    """
    here = Path(__file__).resolve()
    roots = (Path("src"), Path("tests"))
    offenders = [
        str(path)
        for root in roots
        for path in root.rglob("*")
        if path.suffix in {".py", ".j2"}
        and "__pycache__" not in path.parts
        and path.resolve() != here
        and any(
            marker in path.read_text(encoding="utf-8")
            for marker in ("FR-170", "comparison_unreachable")
        )
    ]
    assert offenders == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca009_period_comparison_composition.py::test_no_asserted_absence_survives_anywhere -v`
Expected: FAIL, listing the nine files.

- [ ] **Step 3: Remove the assertions**

1. `card.py` — delete `comparison_unreachable: bool = True` (line 140) and the `CardsReading` docstring paragraph at lines 124-126. In the `MetricCard` docstring (lines 94-97), replace the `FR-170` sentence with the plain statement that the field is `None` until a surface consumes the view (§0.7 — do **not** wire the card to the view).
2. `shell_decisions.py` — delete `COMPARISON_UNREACHABLE` (line 156), its `__all__` entry (line 119), the `comparison_unreachable: str | None = None` field (line 384), the assignment (lines 511-512), and the `FR-170` paragraph at lines 23 and 152.
3. `_decision_cards.html.j2` — delete the comment at line 12 and the `{% if %}` block at lines 16-17.
4. `shell_controls.py:66-70` — rewrite the comment so it no longer claims the view is unreachable. `SURFACE_VIEWS` stays seven; state that the decision surface does not read it, without the `FR-170` claim.
5. `tests/test_d103_metric_card.py` — delete the `FR-170` group at lines 216-234 and the assertion at line 449; remove `FR-170` from the module docstring authority line at line 3.
6. `tests/test_d104_breakdowns_and_limits.py:649` and `tests/test_d105_evidence_drawer.py:445` — delete the assertions.

- [ ] **Step 4: Run the extent test and the three D1 suites**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca009_period_comparison_composition.py tests/test_d103_metric_card.py tests/test_d104_breakdowns_and_limits.py tests/test_d105_evidence_drawer.py -v`
Expected: PASS

- [ ] **Step 5: Confirm the sweep independently**

Run: `grep -rn "FR-170\|comparison_unreachable" src/ tests/ --include=*.py --include=*.j2 | grep -v __pycache__`
Expected: no output. (`governance/` still carries it as history — that is correct.)

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rca/workspace/decision/card.py src/khepri/runtime/shell_decisions.py src/khepri/runtime/shell_templates/_decision_cards.html.j2 src/khepri/runtime/shell_controls.py tests/
git commit -F- <<'EOF'
feat(rca-009): remove the FR-170 asserted absence, now that the source is reachable

`FR-179`: the slice that makes the governed two-population source reachable
removes every assertion and explanatory claim that Period Comparison is
unreachable, in the same slice. Removal only -- `MetricCard.comparison` stays
`None` and `SURFACE_VIEWS` stays seven, because wiring the decision surface to
the view is the read model `RCA-008` §Exclusions bars.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 5: Whole-repo verification and the PR

- [ ] **Step 1: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: no failures. Removing a read-model field changes shapes in suites this plan does not name — that is why this is not a targeted run.

**Compare the counts against `main`, do not just record them.** Run the same command on a clean `main` checkout and diff the pass/skip/xfail totals. The expected delta is the tests this slice adds, minus the four `FR-170` assertions it removes. A total that moved by any other amount means a test was silently dropped or skipped — which a green run will not tell you.

- [ ] **Step 2: Lint and governance**

```bash
./.venv/Scripts/python.exe -m ruff check .
./.venv/Scripts/python.exe -m pytest tests/ -k "governance or registry" -q
```
Expected: clean; governance/registry tests pass. Do **not** run `ruff format`.

- [ ] **Step 3: Static scope evidence**

Run: `git diff --stat origin/main...HEAD`
Confirm the changed files are exactly those in File Structure — no unrelated view, route, or runtime binding changed (§Verification).

- [ ] **Step 4: CodeScene pre-flight**

```bash
git fetch origin
```
Then `analyze_change_set` against `origin/main`. A stale `origin/main` returns empty results and a meaningless "passed". `comparison_operands.py` must score 10.00. If the MCP is unreachable this session, the server-side gate on the PR is the authority — say so in the PR body rather than claiming a local pass.

- [ ] **Step 5: Open the PR**

Title: `feat(rca-009): make Period Comparison reachable through the composition root`

Body must state:

1. The slice identifies itself as the `RCA-009` Period Comparison composition slice (precondition 2).
2. Reachability and `FR-170` removal shipped together (precondition 3).
3. **For the owner —** the §0.3 `wiring.py` enumeration gap: §Scope does not name the file `FR-180` requires the construction to happen in.
4. **For the owner —** the §0.7 finding: after removal the card carries a named `comparison` field that is empty with no stated reason. Whether the D1 surface should consume the now-reachable view is `RCA-008`'s call.
5. **For the reviewer —** the §0.1 refusal mapping: a refused pair returns `None`, not a `ViewRefusal`, because the two cause vocabularies are disjoint and a foreign cause would carry no bilingual wording. This is the question a reviewer is most likely to raise.
6. **For the reviewer —** the `refusal_wording` name collision (Task 1): two functions share the name, and `admit_pair` imports the `comparison_narrative` one.

```
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 6: Do not merge**

Per `AGENTS.md` and this repo's memory, the owner's merge is the approval. Report status and stop.

---

## Self-Review

**Spec coverage:**

| Requirement | Task |
|---|---|
| `FR-172` branch selection from published definition | Task 2 §0.5, `test_every_other_view_still_routes_single_population` |
| `FR-173` authorization, scope, uniform unavailable | Task 3 fail-closed + scope tests |
| `FR-174` order preserved, no arithmetic | Task 2 order test, Task 3 provenance test |
| `FR-175` fail closed, no fallback | Task 3 arity, self-pair + no-degradation tests |
| `FR-176` identities/versions/evidence survive | Task 3 provenance test |
| `FR-177` bilingual parity | Task 3 parity test |
| `FR-178` no write, no event | Task 3 write-spy tests |
| `FR-179` reachability + absence removal together | Tasks 2 and 4, same PR |
| `FR-180` relocation, not reimplementation | Task 1 parity suite |
| §Verification static scope evidence | Task 5 Step 3 |
| §Verification CodeScene 10.00 | Task 5 Step 4 |

**Placeholder scan:** no TBDs; every code step carries real code; the two owner findings are explicitly marked "do not build".

**Type consistency:** `ComparisonOperand`/`OperandLoad`/`OperandRequest`/`PairAdmission` are defined in Task 1 and used under those names in Task 2. `derive_operand` takes `OperandRequest` (public, four fields) and constructs the private `_OperandAsk` (five fields, carrying `bound`) internally — the public type never carries `bound` or `version_id`. `admit_pair` takes `(owner_id, subject, baseline)` and returns `PairAdmission`. `projection.project` receives a 1-tuple in Task 2, matching `_candidate`'s `len(sources) != 1` rule.

**Verified against the tree** (not assumed): `ViewProjection.rows` exists (`projection.py:114`); `ViewOutcome` has `kind`/`refusal`/`projection`/`effective` (`projection.py:130-136`); `registry.py` exports `view_ids` + `define_view`, **not** `published_views`; `SHAPE_TWO_POPULATION` lives in `contracts.py:44`, not `definitions`; `define_view` **raises** `UnknownView`; `CAUSE_UNORDERED_PAIR`/`CAUSE_RETAIL_DAY`/`CAUSE_INCOMPLETE` all live in `dataset_period.py:51-57`; `CROSSVERSION_BUNDLE_VERSION = "rra006.crossversion.bundle.v1"` contains the `"crossversion"` marker. Every line number cited in Task 4 was confirmed to resolve to the stated content.

**Declared inline:**
- `_Scoped` — Task 2 Step 3, a frozen dataclass of `owner_id: str`, `operand: ComparisonOperand`, declared in `semantic_view_adapter.py` beside the branch.
- `_definition_of` — Task 2 Step 3, the `UnknownView`-catching resolver.
- `_OperandAsk`, `_RunPackage` — Task 1, private to the seam.

**Test fixtures the executor must build** (named here so they are not discovered mid-task): `_SUBJECT_RUN`, `_BASELINE_RUN`, `_OTHER_ORG_RUN`, `_SUBJECT_OPERAND`, `_OWNER`, `_composed()`, `_composed_for()`, `_composed_with_arity()`, `_unavailable_outcome()`, `_governed_bundle()`, `_subject_values()`, `_baseline_values()`, `_figure_values()`, `_figure_codes()`, `_caveat_codes()`, `_evidence_codes()`, `_versions()`, and the `write_spy` fixture. `_SUBJECT_RUN` and `_BASELINE_RUN` must share metrics — a pair sharing none yields `CAUSE_INCOMPLETE` from `_crossversion_facts` (`crossversion_assembly.py:154-165`), which is the null case dressed as a pass.
