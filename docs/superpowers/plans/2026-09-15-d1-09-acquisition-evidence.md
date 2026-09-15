# `D1-09` — Acquisition and read-count evidence: the ledger

**Slice:** `D1-09`, the last implementation slice of `D1` before `D1-10`'s cross-cutting evidence.
**Authority:** active `RCA-008` (`FR-159`–`FR-171`), merged 2026-09-10 at `2734886` (`#444`).
**Plan:** `docs/superpowers/plans/2026-09-15-d1-09-execution-plan.md`.
**Precedent for this ledger's shape:** `docs/superpowers/plans/2026-09-09-sv1-08-baseline-evidence.md`.

Measured on one machine, 2026-09-15, Python 3.13, Windows. Same caveat `SV1-08` carries and it is
not a formality: one machine, one run, no approved workload. **A figure to know the shape of the
cost by, not a tolerance.**

---

## 1. Verdict, stated first

| Finding | State | Where |
|---|---|---|
| Read counts per path | **MEASURED** | §2 |
| Surface acquisition latency | **MEASURED** | §3 |
| Every bound able to fail | **MEASURED** — four mutants, each observed failing | §4 |
| The `FR-168` prohibitions | **HELD** — no production module changed | §5 |
| Coalescing | **VERIFIED, not built** — `D1-03`/`D1-05` already performed it | §6 |
| `PeriodComparisonView` unreachable | **HELD** — untouched; stays `D1-10`'s to assert | §6 |

**This slice ships no surface and changes no production code.** Every file it adds is in `tests/`.
That is not a shortfall against its roadmap row: the allocation plan's §6 sequencing table records
`D1-09` as "Ships a surface? No", because `FR-168` removes every instrument a performance slice
would normally reach for and what remains is evidence.

---

## 2. Read counts per path — MEASURED

Produced by `tests/test_d109_read_counts.py`, which drives the real
`khepri.runtime.shell_decisions.read_surface` with a counting wrapper on
`SemanticQueryActions.request` (`tests/d109_support.py::CountingActions`).

| Path | Reads | Views, in order |
|---|---:|---|
| Admitted | **7** | Overview, Availability, Evidence, Branch, Product, Basket, Concentration |
| Overview refused | **5** | Overview, Branch, Product, Basket, Concentration |
| All views unavailable | **5** | Overview, Branch, Product, Basket, Concentration |
| Unroutable parameter asked | **8** | the admitted seven, then Branch again |
| Real filter (`store`) applied | **7** | same as admitted |

**The count is path-dependent, and that is the finding.** `read_cards` returns at
`src/khepri/rca/workspace/decision/card.py:276` when the overview projection is `None`, before it
reads `MetricAvailabilityView` or `ReportEvidenceView`. A suite asserting `== 7` over the admitted
fixture alone would pass while leaving the refusal path entirely unmeasured — and §4's third mutant
is caught by **only** the two refusal-path cases, so without them it would have shipped silently.

**The eighth read is conditional and correct.** `_unsupported_read` issues one extra read only when
the reader asked for a parameter no view admits, so the refusal is earned by a real read rather
than invented (`FR-137`). Asserting it keeps it conditional: §4's second mutant makes it
unconditional and the real-filter case fails at eight.

**Seven and not eight views.** `DECISION_VIEWS` carries eight identities; `PERIOD_COMPARISON` is
published and unreachable (`FR-170`). The expected tuple is written out rather than derived from
`len(DECISION_VIEWS)`, which is off by one by design.

---

## 3. Surface acquisition latency — MEASURED

Produced by `tests/test_d109_acquisition_baseline.py::_surface_samples` — 200 samples, the script,
selection and request built once outside the loop, nothing warmed, memoized or reordered.

| Path | min | p50 | p90 | max |
| --- | ---: | ---: | ---: | ---: |
| Admitted page, seven reads, scripted port | 77 µs | **80 µs** | 97 µs | 308 µs |

Every sample issued exactly seven reads (`reads=[7]`).

**What this measures, and what it does not.** The port is scripted, so this is the read fan-out and
the orchestration around it — **not** the composed end-to-end path. It is therefore **not
comparable to `SV1-08` §3a's 4003 µs p50**, which drove a real projection over a real store. A
reader must not take 80 µs for an end-to-end figure; the composed cost is recorded in §3a and this
slice does not restate it.

**Why measuring the fan-out is nonetheless the right subject.** `FR-168` governs the number of reads,
not the cost of one, and §3a already established where the cost lives: projection is 11.6 µs against
a 4003 µs composed request, about one part in 345. A surface that issues seven reads instead of
forty is the whole lever this slice has, and the count — not the microseconds — is what §2 bounds.

**No wall-clock threshold is asserted anywhere.** `SV1-08`'s `_assert_measured` states the rule: "a
wall-clock threshold in CI is a flake, and the ledger is where a baseline belongs." What the test
asserts is `FR-144`'s own condition — that measuring changed nothing, so no iteration warmed,
cached or reordered a later one. Its instrument is the read count: a run served from anything
retained would drop below seven, and `set(counts) == {7}` would fail.

---

## 4. How each bound was made able to fail — MEASURED

A bound that cannot fail is decorative. Each mutant was applied alone, observed, and restored;
`git diff -- src/` was empty after every restore, so no mutant left a deletion behind.

| # | Mutant | Observed |
|---|---|---|
| 1 | A real second `read_products(actions, routed(PRODUCT_CATEGORY))` statement in `read_surface` | **6 of 6 failed** in `test_d109_read_counts.py` |
| 2 | `if not asked:` → `if False:` in `_unsupported_read` | **5 failed**, including `test_a_real_filter_adds_no_read` |
| 3 | The `qualifiers = ...` read moved above the `if projection is None` guard in `read_cards` | **exactly the 2 refusal-path cases failed** |
| 4 | A retained-result cache on `CountingActions.request` | **3 of 3 failed** in `test_d109_acquisition_baseline.py` |

**Mutant 3 is the one that justifies the per-path table.** It is invisible to every admitted-path
assertion — the admitted count stays seven — and is caught only by
`test_a_refused_overview_reads_five_because_cards_returns_early` and
`test_every_view_unavailable_reads_the_same_five`. Had the slice asserted a single count, moving a
read above a guard would have been a silent widening of the refusal path.

**Mutant 4 is the shape `FR-168` names.** It retains a result across requests, which is a cache
whatever it is called, and it fails the distribution test as well as the two non-retention tests —
because retention shows up as a read count below seven.

**One malformed mutant, recorded because it proves nothing.** The first attempt at mutant 1
duplicated the `products=` keyword argument, which is a `SyntaxError`: pytest never collected, and a
collection error is not a caught defect. The well-formed mutant is a separate statement issuing a
real second read. A red result that is only a parse failure must not be counted as evidence.

---

## 5. The prohibitions — HELD

`FR-168`: no cache, pre-aggregation, materialized view, sampling, or persisted projection was added.
`FR-169` and §Retention: nothing retained.

- **No production module was changed.** The slice adds `tests/d109_support.py`,
  `tests/test_d109_read_counts.py` and `tests/test_d109_acquisition_baseline.py`, and this ledger.
  `git diff -- src/` against `main` is empty.
- **The counter is test-only, deliberately.** A read-count accumulator living in
  `src/khepri/rca/workspace/` would be state surviving a request — exactly what `FR-169` and
  §Retention forbid. Shipping retention to assert non-retention would have been self-defeating, so
  the instrument is per-call and lives in `tests/`.
- **It counts at `SemanticQueryActions.request`, not at the port.** §3a puts the uniform-miss path
  at 1331 µs, "authorization plus the scoped run read alone", so a read that misses still costs
  acquisition; counting `project` calls would have measured the 11.6 µs half and under-counted every
  miss. The precedent is `_CountingIsolation`/`_LoggingReader` in `test_sv108_query_baseline.py`.
- **`KHEPRI-DEC-015` §3 stands unamended.** No product-analytics or repeat-use telemetry was added,
  and `D1-11` remains unauthorized.

---

## 6. What this slice did not do, and whose it is

**Coalescing was already performed, and is verified here rather than rebuilt.** The allocation plan
named "coalescing reads within one request" as the remaining legitimate lever. Measuring
`read_surface` shows `D1-03` and `D1-05` already took it: no view is read twice on any ordinary
path, `read_cards` reads S-9 once for the whole surface rather than once per card, and `read_surface`
declines to re-read `MetricAvailabilityView` for a consolidated limits section. `D1-01` §5's
forty-read projection was averted before this slice existed. Restructuring reads here would have
been invented scope; `test_no_view_is_read_twice_on_any_ordinary_path` holds the property instead.

**`read_limits` and `read_overview` have no production caller.** Both are exported —
`src/khepri/rca/workspace/decision/limits.py:151` and `overview.py:147` — and `read_surface`
reaches neither, composing the page from `read_cards` and the four breakdown readers. They are
alternate entry points, so the read-count guard anchors to the route. **Recording, not deciding:**
whether they should be removed is not this slice's call, and nothing here depends on the answer.

**`PeriodComparisonView` stays unreachable.** `FR-170` requires the gap be held open visibly and
asserted rather than rendered as an empty tab, and `D1-10`'s acceptance requires that assertion
still standing. This slice does not read the view, does not include it in the expected tuple, and
does not touch the assertion.

**Three owner items are untouched.** The successor composition artifact for Period Comparison
(without which `D1-03` keeps its asserted absence and D1 does not satisfy M4's "compare governed
periods"); the export reading in `D1-08` §Exclusions; and `D1-11`, which `RCA-008` §Retention leaves
unauthorized rather than merely unscheduled.

**What remains for `D1-10`.** Parity over figures, caveats, refusals and availability states in both
languages; cross-organization isolation on every surface; every refusal state reachable and
correctly worded; and the `FR-170` unreachability assertion still standing. `D1-10` does **not**
close its roadmap row: the accessibility-evidence and visual-regression programme remains `U1-03`,
`U1-05`, `U1-06` and `U1-07`'s and needs its own authority.

---

## 7. Regenerating every figure in this ledger

No figure here is unreproducible from committed code.

| Figure | Producer |
|---|---|
| §2's five-row count table | `tests/test_d109_read_counts.py`, all six tests |
| §3's min/p50/p90/max and `reads=[7]` | `tests/test_d109_acquisition_baseline.py::_surface_samples` |
| §4's four mutant outcomes | the mutations described in §4, applied to the named lines |

```bash
PYTHONPATH="src;." ./.venv/Scripts/python.exe -m pytest \
  tests/test_d109_read_counts.py tests/test_d109_acquisition_baseline.py -v

PYTHONPATH="src;." ./.venv/Scripts/python.exe -c "
import statistics
from tests.test_d109_acquisition_baseline import _surface_samples
t, c = _surface_samples()
q = statistics.quantiles(t, n=10)
print(f'min={min(t)//1000}us p50={int(statistics.median(t))//1000}us '
      f'p90={int(q[8])//1000}us max={max(t)//1000}us reads={sorted(set(c))}')
"
```

The latency figures will differ per machine and run; the read counts will not. That asymmetry is the
point — §2 is a bound and §3 is a shape.
