# `SV1-08` — Latency and query-shape baseline: the evidence ledger

**Measured:** 2026-09-09. **Authority:** active `RRA-014` `FR-144`.
**Slice:** `SV1-08`, the last of `SV1-02`–`SV1-08`.
**Evidence:** `tests/test_sv108_query_baseline.py` (19 tests).

> **This ledger certifies nothing.** `FR-144` authorizes measurement — "latency and
> query-shape evidence **may measure execution**" — and that is all this is. It is **not** an
> `RRA-007` performance certification: no approved benchmark workload exists, and
> `.github/workflows/governance.yml`'s benchmark gate says why a figure without one must never be
> read as evidence that an objective held. The figures below are a dated observation on one
> machine, recorded so a later reader knows where the cost is not. They are not a tolerance, not a
> target, and not an approval.

---

## 1. Verdict, stated first

| Half of `FR-144` | Status | Why |
| --- | --- | --- |
| Query shape | **MEASURED** | The orchestration's shape is shipped behaviour and does not depend on any fake. |
| Projection-half latency | **MEASURED** | The real `project` over real bundles, both admitted source shapes. |
| End-to-end latency | **NOT EXERCISED** | The two shipped halves do not compose. §3. |
| The four prohibitions | **HELD** | Scanned over both packages; this slice adds no source module. §5. |

The allocation plan made this slice conditional: "if the runtime adapter deferred, there is no
shipped composition to measure and this whole slice is recorded NOT EXERCISED rather than passed."
The condition holds and the end-to-end baseline is recorded NOT EXERCISED. The rest is not, because
it does not depend on the composition — and §3 shows the reason for the deferral is sharper than
the plan assumed, which is itself the most useful thing this slice found.

---

## 2. Query shape — MEASURED

`SemanticQueryActions.request` issues, per request, in this order:

1. exactly one `IsolationService.resolve_scope`, before any source read;
2. exactly one `ScopedSourceReader.get_analysis_run` per named source, in the caller's order;
3. exactly one `SemanticViewPort.project`.

Nothing is read twice. A missing source stops the reads where it is found and reaches no
projection. Measured over the real isolation door and the real workspace store, with a reader that
counts calls without influencing them.

| Named sources | `resolve_scope` | Scoped reads | `project` |
| --- | ---: | ---: | ---: |
| 0 | 1 | 0 | 1 |
| 1 | 1 | 1 | 1 |
| 2 | 1 | 2 | 1 |
| 1, missing | 1 | 1 | 0 |
| 3, second missing | 1 | 2 | 0 |

Every row is a recorded call sequence, not a count assembled afterwards: one shared log receives
the scope resolution, each read and the projection in the order they happen, so the table states
ordering as well as arity.

**The shape is identical for all eight published views.** The plan asks for "the query shape each
view issues"; the measured answer is that no view issues one. The orchestration never reads the
view identifier to decide what to load, and the RRA half is handed its source and has no way to
fetch another — `test_the_projection_half_issues_no_read_at_all` scans the package for any import
that could reach a store, a socket or a file. So the composed shape equals the orchestration's
shape, and the table above is the whole of it.

---

## 3. End-to-end latency — NOT EXERCISED, and the reason is not the one anticipated

`SV1-04` resolved the runtime adapter's scope question against building one: `RCA-006` §Scope
governs no runtime wiring, so nothing in the image binds the RRA half to the RCA half. The plan
expected the cost of that deferral to be that a figure taken over a test-local fake port would
measure the fake.

**The actual position is stronger: the two shipped halves cannot compose at all.**
`test_the_shipped_halves_do_not_compose_so_there_is_no_end_to_end_path` composes them by hand with
no fake anywhere — the real isolation door, the real workspace store, the real
`SemanticQueryActions`, the real `project` — and every request for a published view returns:

```
ViewOutcome(kind='refused', refusal=ViewRefusal(cause='incompatible source shape'))
```

`SemanticQueryActions._scoped_sources` loads `AnalysisRun` rows. `project` admits a
`RenderableBundle`. An `AnalysisRun` carries none of `identity`, `figures`, `caveats`, `evidence`
or `bundle_version`, so `_shape_of` answers `unrecognized_source` and the request fails closed.

Three consequences worth recording:

- **The deferred adapter is not a wiring line.** It must *construct* a `RenderableBundle` from an
  `AnalysisRun`. That construction is unbuilt and named by no active artifact.
- **The unbuilt step is where the cost lives.** Both the end-to-end latency and the real
  source-acquisition query shape belong to bundle construction, not to anything measured here.
  Publishing a figure that excluded it would name the cheap half as the baseline.
- **The refusal is the only thing between the halves and a crash.** Mutating
  `_incompatible_source_shape` to admit the pair does not produce a wrong answer; it produces an
  `AttributeError` in the projection. Fail-closed is load-bearing here, not decorative.

That test fails the day an adapter makes the halves meet — which is the day the end-to-end baseline
becomes measurable and must be taken. It is written to fail then, deliberately.

---

## 4. Projection-half latency — MEASURED

The real `projection.project` over a real bundle of the shape each view admits. 200 samples per
view, request and bundle built once outside the loop, nothing warmed or reordered.

**Environment:** CPython 3.13.12, x86_64 Linux, one shared CI-class container, 2026-09-09.
Single machine, single run. An order of magnitude, not a tolerance.

| View | Source shape | Rows | min | p50 | p90 | max |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `BasketView` | single population | 1 | 11.0 µs | 11.5 µs | 13.4 µs | 212.7 µs |
| `BranchPerformanceView` | single population | 1 | 10.9 µs | 11.4 µs | 14.2 µs | 54.3 µs |
| `ConcentrationView` | single population | 1 | 11.1 µs | 11.6 µs | 13.7 µs | 49.8 µs |
| `ExecutiveOverviewView` | single population | 1 | 11.1 µs | 11.6 µs | 13.2 µs | 38.8 µs |
| `MetricAvailabilityView` | either bundle | 1 | 11.8 µs | 12.4 µs | 14.9 µs | 51.8 µs |
| `PeriodComparisonView` | **two population** | **20** | 36.6 µs | 39.3 µs | 45.6 µs | 169.1 µs |
| `ProductCategoryView` | single population | 1 | 10.9 µs | 11.3 µs | 13.0 µs | 48.5 µs |
| `ReportEvidenceView` | either bundle | 1 | 10.9 µs | 11.4 µs | 14.3 µs | 43.0 µs |

The maxima are scheduler noise on a shared runner, which is why the distribution is reported rather
than one sample and why no threshold is asserted in CI. A wall-clock assertion there would be a
flake, not a baseline; what the test asserts is that a distribution was collected and that every
sample in it returned an equal result.

**What this says, and the only thing it says:** projection costs tens of microseconds and scales
with projected rows, not with the number of published views. It is not a cost centre. Whatever the
absent adapter does to turn an `AnalysisRun` into a `RenderableBundle` will dominate this by orders
of magnitude. A reader optimizing `D1-09` should start there and not here.

### The null-case question, asked per view

The plan's second risk: "a run that can only produce the null case is NOT EXERCISED, not PASS."
All eight views answer **non-empty** above, so no figure here is a measurement of the empty path.
Reaching that took correcting a first pass in this slice, which recorded `PeriodComparisonView` as
unreachable — it is bound by `FR-136` to a two-population bundle, and the fixture in hand was
single-population. That would have published a gap belonging to the fixture and not to the product.
It is driven here by `C1-05`'s real `CrossVersionBundle`.

---

## 5. The prohibitions — HELD

`FR-144` bars the measurement from adding "caching, pre-aggregation, materialized views, sampling,
or result changes". The five are transcribed into `PROHIBITIONS` in the test module with one test
each, and `test_every_prohibition_has_a_test` fails if a sixth is transcribed and left untested —
a scan cannot find a rule nobody wrote down.

- **Zero additions to any read path.** This slice ships one test file and this ledger and **no
  source module at all**: `src/khepri/rra/semantic_views/` and `src/khepri/rca/semantic_queries/`
  are byte-identical before and after it. `test_the_read_path_gained_no_measurement_module` holds
  both module sets closed so a timing helper cannot be added later unremarked.
- **No caching.** `contracts._PUBLISHED_SEMANTICS` is the only module-level mutable state on the
  path and is not a cache: `_claim_identity` stores a definition's semantics with `setdefault` and
  *compares* on every later call, so `define_view` builds a fresh definition every time and no call
  is served from a store. It exists for `FR-134`'s immutability and makes the second call
  marginally slower, not faster.
- **No pre-aggregation, materialized views or sampling.** Scanned across both packages over the
  code with docstrings stripped — every one of these words appears in the packages' prose saying
  they are not done, and a scan its own prose fails is a scan nobody keeps.
- **No result changes.** No module on the read path imports a timing surface, and the same request
  answers equally on every repetition.

---

## 6. How each finding was made able to fail

Nineteen tests, nineteen mutants, each asserted to have applied before its result was believed;
every source file restored byte-identically afterwards.

| Mutant | Kills |
| --- | --- |
| A second `get_analysis_run` per source (N+1) | the shape and eight-view tests |
| A miss `continue`s instead of stopping | the short-circuit test |
| A store read before `resolve_scope` | the authorization-first test |
| A miss yields `()` instead of `None` | the no-projection-on-miss test |
| `_unknown_view` fires first, so a different cause refuses | the composition test |
| `import time` / `import sqlalchemy` on the read path | the timing and no-read scans |
| `lru_cache` / `groupby` / `materialize` / `sample` added | the four prohibition scans |
| A warm-cache result change across calls | both latency tests and `test_no_result_changes` |
| An empty metric allowlist | the eight-view reachability test |
| A prohibition's test renamed away | `test_every_prohibition_has_a_test` |
| A new module added to either package | the closed-module-set test |

**One negative control**, because a scan that matches text rather than code proves nothing: adding
`Sampling, lru_cache, groupby and materialize` to a module **docstring** must leave all four
prohibition scans green. It does.

Two defective mutants were caught and replaced rather than counted. A warm-cache mutant that
referenced an undefined `_SEEN` raised `NameError`, so its kill measured a crash and not a result
change; it was rewritten with the state defined. A mutant harness that took two edits to one file
recorded the once-mutated content as the original and left three lines behind on restore; the tree
was checked, the leak found, and every mutant that ran after it re-run on a clean tree.

---

## 7. What remains, and whose decision it is

One thing, and it is not this slice's to take:

**`SV1-08`'s end-to-end baseline and `SV1-07`'s composition property both stay NOT EXERCISED until
an owner-merged `RCA-006` amendment names a runtime adapter path.** `RCA-006` §Scope governs no
runtime wiring; `RCA-005` §Scope names only `shell_api.py` and `shell_templates/`, so
`runtime/comparison_assembly.py` is an unnamed-path precedent rather than an authorization; and
`R7-01` is a design note that is not in the registry. Article IV forbids widening the runtime
boundary without an owner-merged artifact, so the amendment is the gate.

What that amendment would need to say is now more specific than "wire the port": it must name a
path that **constructs a `RenderableBundle` from an `AnalysisRun`**, because §3 shows that is the
real gap. Until it exists, `SV1-01`–`SV1-08` deliver a complete, tested, governed semantic-view
capability that nothing in the running image can call.
