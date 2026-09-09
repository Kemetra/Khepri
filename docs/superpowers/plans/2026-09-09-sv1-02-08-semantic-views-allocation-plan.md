# `SV1-02`–`SV1-08` — The bounded allocation plan for curated semantic views

> **For agentic workers:** this is an **allocation** plan, the `G3-04` tier. It allocates two
> specifications' seventeen requirements to seven slices and writes no code. Each slice below opens
> its own **execution** plan at build time — the `W1-09` tier, with `- [ ]` RED/GREEN/commit steps
> and literal test code — created with `superpowers:writing-plans` when that slice starts.
> REQUIRED SUB-SKILL at execution: `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`.

**Goal:** Provide reusable, versioned, no-calculation views over already-governed facts, and an
organization-scoped query path that retains nothing, so `D1` can build an executive workspace
without a second source of truth.

**Architecture:** Two packages either side of an injected protocol. `src/khepri/rra/semantic_views/`
holds the closed definition registry, compatibility validation, projection and refusals;
`src/khepri/rca/semantic_queries/` holds authorization, organization-scoped source loading and the
uniform unavailable outcome. `khepri.rca` never imports `khepri.rra` — it calls a Protocol, exactly
as `rca/workspace/comparisons.py`'s `ComparisonAssembly` does. A view is a projection boundary: it
selects, orders and propagates, and performs no arithmetic.

**Tech Stack:** Python 3.13, frozen dataclasses with `slots=True`, `typing.Protocol`, pytest. No new
dependency, no SQLAlchemy model, no Alembic revision, no route, no template.

**Authority:** active `RRA-014` (`FR-134`–`FR-144`) and active `RCA-006` (`FR-145`–`FR-150`), both
merged 2026-09-09 at `9ec3896` (`#418`).

**Spec:** `docs/superpowers/specs/2026-09-09-sv1-semantic-view-authority-design.md`, whose §7 slice
map this plan expands. Roadmap: `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` §PROGRAM SV1.

---

## Global Constraints

Every slice's requirements implicitly include this section. Values are copied verbatim from the
governing artifacts.

- **Scope is two package paths and `tests/`.** `RRA-014` §Scope admits
  `src/khepri/rra/semantic_views/`; `RCA-006` §Scope admits `src/khepri/rca/semantic_queries/`.
  "Runtime routes, templates, shell assets, workspace persistence, raw-source access, and every path
  governed by another active specification are outside scope" (`RRA-014`). `RCA-006` adds: "No
  route, runtime wiring, template, shell asset, public API, migration, cache, background job,
  renderer, or existing workspace file is governed."
- **No slice touches both packages.** Each specification's Exclusions bar edits to the other's
  source paths. A PR that needs both is mis-sliced.
- **`RRA-014` precondition 2:** an implementation slice "identifies itself as `SV1-02`, `SV1-03`,
  `SV1-05`, `SV1-06`, `SV1-07`, or `SV1-08`" and stays within that scope. `SV1-04` is the `RCA-006`
  half.
- **No arithmetic, ever** (`FR-138`): projection "may not perform arithmetic, aggregation, grouping
  into a new fact, ranking, scoring, normalization, top-N, thresholding, or raw-row access."
- **No second truth** (`FR-135`): metric and dimension members "derive from their governing
  declarations and are never retyped."
- **The registry is closed to exactly eight views** (`FR-135`), named in `RRA-014`:
  `ExecutiveOverviewView`, `PeriodComparisonView`, `BranchPerformanceView`, `ProductCategoryView`,
  `BasketView`, `ConcentrationView`, `ReportEvidenceView`, `MetricAvailabilityView`.
- **Immutability** (`FR-134`): changing any admitted source, field, metric, dimension, filter,
  evidence requirement, empty rule or output order **creates a new version**. It is never an edit.
- **No `latest` alias and no silent upgrade** (`FR-143`).
- **Nothing is retained** (`FR-148`): no database row, object, artifact, cache, preference, history
  entry, tombstone or deletion evidence. `FR-149`: no new audit or product-telemetry event, counter,
  access record or content-bearing log; "request parameters and result content do not enter existing
  logs."
- **One uniform unavailable outcome** (`FR-146`): absent, deleted, corrupt or cross-scope sources
  "return the same content-free unavailable outcome without identifying which condition held."
- **Fail closed** (`RRA-014` §Invariants): "no fallback, partial projection, or nearby substitution
  is admitted."
- **Bilingual refusal wording** (`FR-141`), en/ar, from governed vocabulary only.
- **Every new file must score 10.00** in the required server-side CodeScene Code Health Review
  (`RRA-014` §Verification). CodeScene gates cyclomatic >9, module mean >4, args >4, and cohesion —
  extracting helpers *raises* the mean, so prefer value-object grouping over flat parameter lists.
- **Run tests with `./.venv/Scripts/python.exe -m pytest`.** Do **not** run `ruff format` (no CI
  format gate); `ruff check .` only. Ruff counts characters, not bytes.
- **Every slice runs** `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`.
- **One PR per slice**, carrying a plan-and-RED commit then an implementation commit. Use
  `git commit -F <file>` (rebase ignores `-c commit.gpgsign`). Branch every slice off `main` —
  never stack a PR on another branch.
- **`governance/**` is untouched by every slice here.** The authority is already active.

---

## 1. The ordering constraint, stated once

`G3-04` fixed W1's order with one rule. SV1's rule is this:

> **A projection can only be validated against declarations that exist, and measured only once it
> executes.**

That single sentence fixes the whole order. `FR-137` refuses an unsupported dimension or filter
*before projection* — but "unsupported" is defined by the definition record's allowlists, so the
registry (`SV1-02`) precedes validation (`SV1-03`). `FR-147` has RCA pass "only successfully scoped
governed sources and the explicit request" to the RRA protocol, so both RRA halves precede the RCA
read service (`SV1-04`). `FR-139`/`FR-140` propagate what a projection returned, so propagation
follows the path that returns it (`SV1-05`). `FR-143`'s historical readers need something published
to be historical about (`SV1-06`). `FR-150`'s boundary evidence crosses both packages and asserts
against every earlier slice (`SV1-07`). `FR-144` "may measure execution" — there is nothing to
measure until it executes (`SV1-08`, last).

**Build order is numeric here**, unlike `G3-04`'s deliberate `W1-08`-before-`W1-07`. Nothing in SV1
is destructive: `FR-148` forbids writes outright, so there is no first-destructive-path slice to
hold back until the read surfaces exist. The one non-obvious placement is `SV1-07` at position six
rather than throughout — each earlier slice carries its own acceptance tests; `SV1-07` is the
*cross-cutting boundary* evidence `FR-150` enumerates, which cannot be written until both packages
exist to be crossed.

---

## 2. The seam, stated once

`RCA-006` §Request flow requires that "the future RCA implementation calls an injected protocol and
does not import a concrete RRA implementation, following `rca/workspace/comparisons.py`'s
`ComparisonAssembly` precedent." That protocol's shape constrains `SV1-02`'s `output_field_order`
and `request_filter_allowlist`, and `FR-134` makes a later reshape **a new view version, not an
edit**. So the seam is pinned here, before `SV1-02` publishes anything, rather than discovered by
`SV1-04`.

`W1-04b` is the precedent for the failure this avoids: review on `#373` found the services/surfaces
seam unnamed and a slice had to be added mid-programme.

**The seam is a Protocol declared in `khepri.rca.semantic_queries` and satisfied by an adapter in
`khepri.runtime`** — the direction `ComparisonAssembly` established, where the consumer owns the
Protocol and the composition root binds the RRA implementation to it. `SV1-02`'s record fields are
designed against this contract; `SV1-04` declares it.

```python
# src/khepri/rca/semantic_queries/ports.py  (SV1-04 creates; SV1-02 builds against it)

KIND_ADMITTED = "admitted"
KIND_REFUSED = "refused"
KIND_UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SemanticViewRequest:
    """The explicit request: exact identity, explicit dimensions, explicit filters.

    FR-143 -- the version is exact and there is no `latest`. FR-137 -- every
    requested filter is named here, so the result can state it back.
    """

    view_id: str
    view_version: str
    dimensions: tuple[str, ...]
    filters: tuple[tuple[str, str], ...]   # ordered pairs; never a dict, so order is identity


@dataclass(frozen=True, slots=True)
class EffectiveRequest:
    """FR-137 -- what actually applied, requested and definition-fixed alike."""

    dimensions: tuple[str, ...]
    requested_filters: tuple[tuple[str, str], ...]
    fixed_filters: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class ViewRefusal:
    """FR-141 -- a stable contract refusal with bilingual wording, no partial result."""

    cause: str
    wording: dict[str, str]        # {"en": ..., "ar": ...}


@dataclass(frozen=True, slots=True)
class ViewProjection:
    """FR-139/FR-140 -- projected values plus everything that must survive."""

    view_id: str
    view_version: str
    fields: tuple[str, ...]                    # output_field_order, as published
    rows: tuple[tuple[object, ...], ...]       # values equal to source records
    versions: dict[str, str]                   # mapping/package/formula/family/bundle/view
    caveats: tuple[object, ...]
    population_qualifiers: tuple[object, ...]
    evidence: tuple[object, ...]
    evidence_absences: tuple[str, ...]
    is_empty: bool


@dataclass(frozen=True, slots=True)
class ViewOutcome:
    """Admitted, refused, or the uniform isolation miss -- ComparisonOutcome's shape."""

    kind: str
    refusal: ViewRefusal | None = None
    projection: ViewProjection | None = None
    effective: EffectiveRequest | None = None


class SemanticViewPort(Protocol):
    """The RRA half, injected so `khepri.rca` never imports `khepri.rra`."""

    def project(
        self, request: SemanticViewRequest, sources: tuple[object, ...]
    ) -> ViewOutcome: ...
```

Three decisions this pins, each with its reason:

1. **`filters` is an ordered tuple of pairs, not a mapping.** `FR-137` requires every effective
   filter be *visible in both request and result*; a dict's iteration order is an implementation
   detail, and `FR-134` makes output order part of view identity.
2. **`sources` is `tuple[object, ...]`, deliberately untyped at the seam.** `RCA-006` §Exclusions
   bars `khepri.rca` from importing a concrete RRA implementation, and the admitted source shape is
   `RenderableBundle` — an `RRA-014`-side type. The RCA side passes what it scoped; the RRA side
   validates the shape (`FR-136`) and refuses an incompatible one. `ComparisonOutcome.bundle` uses
   the same `object` for the same reason.
3. **One `project` call, not a validate-then-project pair.** `FR-137` and `FR-141` require refusal
   *before* projection, which is a guarantee about the callee's internal order, not about the number
   of calls. Two calls would let a caller skip validation.

---

## 3. File Structure

| File | Responsibility |
|---|---|
| `src/khepri/rra/semantic_views/__init__.py` | **Create (`SV1-02`).** Package marker; re-export the public names. |
| `src/khepri/rra/semantic_views/contracts.py` | **Create (`SV1-02`).** `SemanticViewDefinition` — the ten `RRA-014` contract fields as one frozen record. No behaviour. |
| `src/khepri/rra/semantic_views/registry.py` | **Create (`SV1-02`).** The eight published definitions and the closed-extent lookup. Allowlist members derive from `definitions.METRIC_CODES` / `facts.SERIES_DIMENSIONS`. |
| `src/khepri/rra/semantic_views/compatibility.py` | **Create (`SV1-03`).** One ordered predicate table returning the first cause; `C1-02`'s `analysis/compatibility.py` is the shape precedent. |
| `src/khepri/rra/semantic_views/refusals.py` | **Create (`SV1-03`).** The closed cause set and its bilingual wording, both languages in one table. |
| `src/khepri/rra/semantic_views/projection.py` | **Create (`SV1-05`).** Select, order, propagate. The module `FR-138`'s arithmetic scan targets. |
| `src/khepri/rra/semantic_views/published.py` | **Create (`SV1-06`).** Published version history and the exact-version resolver. |
| `src/khepri/rca/semantic_queries/__init__.py` | **Create (`SV1-04`).** Package marker. |
| `src/khepri/rca/semantic_queries/ports.py` | **Create (`SV1-04`).** §2's seam verbatim: `SemanticViewPort` and its five value types. |
| `src/khepri/rca/semantic_queries/queries.py` | **Create (`SV1-04`).** `SemanticQueryActions.request` — authorize, scope-load, call the port, return. `comparisons.py` is the precedent. |
| `src/khepri/runtime/semantic_view_adapter.py` | **Create (`SV1-04`).** The composition-root adapter binding the RRA registry to `SemanticViewPort`. **Confirm scope before writing** — see `SV1-04`'s Risk. |
| `tests/test_sv102_view_registry.py` | **Create (`SV1-02`).** Extent, derivation, immutability. |
| `tests/test_sv103_compatibility.py` | **Create (`SV1-03`).** Early refusal, cause ordering, bilingual wording. |
| `tests/test_sv104_query_orchestration.py` | **Create (`SV1-04`).** Authorization, uniform unavailable, no-import. |
| `tests/test_sv105_propagation.py` | **Create (`SV1-05`).** Value equality, propagation completeness. |
| `tests/test_sv106_published_versions.py` | **Create (`SV1-06`).** Exact version, no `latest`, historical immutability. |
| `tests/test_sv107_boundary_evidence.py` | **Create (`SV1-07`).** `FR-150`'s six named properties + `RRA-014` §Verification's eight. |
| `tests/test_sv108_query_baseline.py` | **Create (`SV1-08`).** Latency and query-shape measurement. |
| `docs/superpowers/plans/<merge-date>-sv1-08-baseline-evidence.md` | **Create (`SV1-08`).** The measured baseline as an evidence ledger, dated the day it is measured. |

**No file is modified.** Every path above is new, which is why every one of them faces the 10.00
CodeScene gate. Nothing in `src/khepri/rra/` or `src/khepri/rca/` outside these two packages changes,
and `governance/**` is untouched throughout.

---

## 4. Slices

Seven PRs across seven roadmap tasks, numbered as the roadmap's `SV1` table numbers them. Each slice
names its requirements, what it delivers, its acceptance, and the one thing most likely to go wrong.

### `SV1-02` — The closed definition registry

- **Requirements:** `FR-134`, `FR-135`, `FR-136`.
- **Interfaces.** Consumes: `definitions.FAMILY_METRICS` and the governed family version constants
  it is keyed by, `facts.SERIES_MEASURES`, `facts.SERIES_DIMENSIONS`. `renderable.RenderableBundle`
  is the identical-projection contract `either_bundle` rests on, named rather than imported.
  Produces: `SemanticViewDefinition` (the ten contract fields), `ViewDefinitionRefused`,
  `view_ids()`, `define_view(view_id)`. `define_view` takes no version — `SV1-02` publishes one
  version per view, and `FR-143`'s exact-version resolution over published history is `SV1-06`'s.
- **Delivers:** `semantic_views/contracts.py` and `registry.py`. The ten `RRA-014` contract fields
  as one frozen record — `view_id`, `view_version`, `accepted_source_shape`, `metric_allowlist`,
  `dimension_allowlist`, `request_filter_allowlist`, `fixed_filters`, `required_evidence`,
  `output_field_order`, `empty_result_rule` — and exactly eight published definitions. Every
  allowlist member is **derived**: family metrics are read out of `definitions.FAMILY_METRICS` by
  the contract version that publishes them, series metrics are composed over `facts.SERIES_MEASURES`
  the way `definitions.SERIES_METRICS` composes them, and dimensions come from
  `facts.SERIES_DIMENSIONS` (itself `(PERIOD_DIMENSION, *COMPARISON_DIMENSIONS)`). The record's
  field types are designed against §2's seam.
- **Acceptance:** the registry's key set **equals** the eight named views — equality *and*
  non-empty, never `>=`; every metric in every `metric_allowlist` satisfies
  `definitions.admits_metric`, asserted by iterating the registry rather than a hand-list; every
  dimension is a member of `facts.SERIES_DIMENSIONS`; a ninth view cannot be registered; a value
  outside `FR-136`'s source shapes or `FR-142`'s empty rules refuses at construction rather than at
  query time; and the record is frozen and a `dataclasses.replace` that changes any of the eight
  version-moving fields produces a record whose `view_version` differs, or raises.
- **Risk:** **a subset assertion cannot see a ninth view added.** `RCA_TABLES` drifted three times
  this way, and a widening survived all 3,618 tests once. `FR-135` says "closed", which is an extent
  claim: assert set equality against the eight literal names *and* that the set is non-empty, so a
  registry that fails to load cannot pass by being empty. Second risk: retyping a metric code as a
  string literal in an allowlist. That is the "second truth" `FR-135` names — derive it, and let the
  test prove derivation by asserting against the governing constant, not against a copy.

### `SV1-03` — Compatibility validation and early refusal

- **Requirements:** `FR-137`, `FR-141`.
- **Interfaces.** Consumes: `SemanticViewDefinition`, `define_view`. Produces:
  `validate(request, definition) -> ViewRefusal | None`, `REFUSAL_CAUSES`, `refusal_wording(cause)`.
- **Delivers:** `semantic_views/compatibility.py` — one **ordered predicate table** returning the
  first cause, following `C1-02`'s `analysis/compatibility.py`, which `#408` corrected precisely for
  inventing a cause its specification did not list. And `refusals.py` — the closed cause set with
  both languages in one table. `FR-141` names the causes: unknown view, unknown version, unknown
  metric, unknown dimension, unknown filter, incompatible source shape, missing required evidence.
  An undeclared, hidden, missing-required or unsupported parameter refuses **before projection**.
- **Acceptance:** each cause is reachable and each is returned by an input that triggers only it;
  the table's order is asserted, so a reordering fails; every cause has non-empty en *and* ar
  wording, with the cause set derived from the table rather than retyped beside it; a refusal
  carries **no partial result and no figure**; a request naming a filter absent from
  `request_filter_allowlist` refuses rather than being silently dropped.
- **Risk:** **inventing a cause the specification does not list.** `#408` is the worked example —
  `C1-02` emitted `filter mismatch`, which `RRA-008` §Refusals does not contain, and the fix folded
  it into the frozen `incomparable basis`. `FR-141`'s enumeration is the closed set; a condition
  that seems to need an eighth cause is an `RRA-014` amendment, recorded and raised, never
  improvised in the slice. Second risk: a cause table where two causes can both match and the test
  fixtures only ever trigger one — assert first-match ordering explicitly.

### `SV1-04` — Organization-scoped query orchestration and the seam

- **Requirements:** `FR-145`, `FR-146`, `FR-147`, `FR-148`, `FR-149`.
- **Interfaces.** Consumes: `IsolationService.resolve_scope`, the workspace record store, §2's seam.
  Produces: `SemanticQueryActions.request(request) -> ViewOutcome`, and `ports.py`'s six public
  types for every later slice.
- **Delivers:** `semantic_queries/ports.py` (§2 verbatim) and `queries.py`. The flow is
  `comparisons.py`'s: resolve the actor and organization through canonical `RCA-001` authorization
  **before any source read** (`FR-145`); load every named source through the requesting
  organization's opaque scope (`FR-146`); pass only successfully scoped sources plus the explicit
  request to the injected port (`FR-147`); return its outcome unchanged. Plus
  `runtime/semantic_view_adapter.py`, the composition-root binding.
- **Acceptance:** an unauthenticated or cross-organization actor never reaches a store read, proven
  by driving the real entry point rather than calling the guard; absent, deleted, corrupt and
  cross-scope sources produce **byte-identical** outcomes, asserted by comparing all four against
  *each other*; zero rows written, evidenced at the session/connection level; zero audit and zero
  telemetry events; `khepri.rca.semantic_queries` imports nothing from `khepri.rra`, asserted by a
  module-level import scan.
- **Risk:** **`runtime/semantic_view_adapter.py` may be out of scope.** `RCA-006` §Scope names
  `src/khepri/rca/semantic_queries/` and says "no runtime wiring… is governed"; `C1-07` already
  carried forward that `runtime/shell_assets/` is named by no active artifact, and
  `runtime/comparison_assembly.py` exists as the `C1-06` precedent under `RCA-005`. **Resolve this
  before writing the adapter**: if `RCA-006`'s "no runtime wiring" bars it, the adapter needs scope
  named in an `RCA-006` amendment and this slice ships the Protocol and actions only, with the
  binding deferred. Raise it; do not decide it in the slice. **If the binding defers, say what that
  costs downstream rather than papering over it**: `SV1-07`'s no-concrete-RRA-import composition
  property and all of `SV1-08` can then only run over a test-local fake port, and both are recorded
  **NOT EXERCISED**, never passed. `W1-07a` is the precedent — a route absent from the image with
  seven tests green over a hand-built `ShellServices`. A fake port does not substitute for an absent
  adapter. Second risk: the zero-writes proof written as a before/after row count — that is the
  pre-read pattern that let two sweeps both attest one purge on `#384`. Assert no write occurred at
  the write path.

### `SV1-05` — Propagation and exact projected values

- **Requirements:** `FR-139`, `FR-140`, `FR-142`, and `FR-138`'s prohibition.
- **Interfaces.** Consumes: `SemanticViewDefinition`, `define_view` (`SV1-02`), `validate`
  (`SV1-03`), `RenderableBundle`, `ViewProjection`. Produces: `project(request:
  SemanticViewRequest, sources: tuple[object, ...]) -> ViewOutcome` — **the `SemanticViewPort`
  implementation itself**, matching §2's Protocol signature exactly. The definition is *not* a
  parameter: it is looked up inside this call via `define_view(request.view_id,
  request.view_version)`, because `RCA-006` §Exclusions bars the RCA side from knowing what a
  definition is. `SV1-06` later **replaces that one call** with its history-aware `resolve`, which
  is why `SV1-06` follows this slice rather than preceding it: the lookup seam exists here, and
  `SV1-06` widens what it can resolve without changing this signature.
- **Delivers:** `semantic_views/projection.py`. Select fields in `output_field_order`, carry every
  typed value and its mapping/package/formula/family/bundle/view versions **equal to the source
  records** — no re-rounding, no relabelling outside governed vocabulary, no substitution. Every
  source refusal, caveat, population qualifier, evidence value **and governed evidence absence**
  survives; none may be suppressed or converted into an ordinary value. `FR-142`'s empty outcome is
  produced here because emptiness is a *result* of projecting, not a validation failure: an admitted
  empty result follows the definition's own `empty_result_rule` and "never widens to unfiltered
  data, a nearby dimension, another version, or a partial result."
- **Acceptance:** a projected value is `==` to the source record's value and of the same type,
  including `Decimal` scale — a quantize anywhere fails; the propagated caveat set is compared
  against the set **imported** from `definitions.CAVEAT_CODES`/`REASON_CODES`, not against a second
  projection; an evidence *absence* appears in the result as an absence rather than a missing key;
  an admitted request matching no rows returns `is_empty=True` with the definition's stated empty
  rule, and the same request with its filters removed returns a *different, non-empty* result —
  which is what proves the empty case did not widen; a static scan of `semantic_views/` finds no
  arithmetic operator, `sum`, `round`, `sorted(key=)` ranking, or slicing that could implement
  top-N — **and asserts the scan saw a non-zero number of files**.
- **Risk:** **`FR-140` is the "defined but never attached" shape.** A caveat can have bilingual
  prose, a wording registration and two narrative branches and still reach no code path — nothing
  fails. Coverage asserted by comparing two projections against each other passes when a qualifier
  is missing from both; `C1-04`'s fix was importing causes from the source module rather than
  retyping them. Do the same here. Second risk: the arithmetic scan self-disarms — a scan scoped to
  a module list reproduces the drift it was written to catch, and a scan over an empty glob passes
  trivially.

### `SV1-06` — Published versions and exact-version rollback

- **Requirements:** `FR-143`, and `FR-134`'s immutability.
- **Interfaces.** Consumes: `view_ids`, `define_view`. Produces:
  `resolve(view_id, view_version) -> SemanticViewDefinition | ViewRefusal`, `PUBLISHED_HISTORY`.
- **Delivers:** `semantic_views/published.py`. Requests name an exact version; supported historical
  readers return that immutable definition, unsupported versions refuse. **No `latest` alias and no
  silent upgrade exists.**
- **Acceptance:** a request for a published historical version returns a definition byte-identical
  to what that version published; a request for an unpublished version refuses with `FR-141`
  wording; the string `latest` resolves nothing and is not a key anywhere; a version-less request
  refuses rather than defaulting; the published history of a view is append-only, asserted by extent.
- **Risk:** **a test that names the next real version becomes a no-op the day that version ships.**
  Use a `.v99` sentinel for the unsupported-version case. Second risk: `FR-134` says a field change
  *creates a new version* — a slice that "fixes" a published definition in place violates
  immutability while every test still passes, because the tests read the same object. Assert the
  historical record separately from the current one.

### `SV1-07` — Cross-cutting boundary evidence

- **Requirements:** `FR-150`, plus `RRA-014` §Verification's eight named properties.
- **Interfaces.** Consumes: every public name from `SV1-02` through `SV1-06`. Produces: no source
  module — tests only.
- **Delivers:** `tests/test_sv107_boundary_evidence.py`. `FR-150` names six:
  cross-organization, missing, deleted, exact-version, no-write, no-event, and no-concrete-RRA-import
  behaviour, "including byte-identical unavailable outcomes and zero writes". `RRA-014` adds: exact
  registry extent, derived allowlists, early refusal, visible effective filters, arithmetic absence,
  propagation completeness, exact versions, explicit emptiness. Where a property is about a *reader*
  rather than a value, drive the real entry point.
- **Acceptance:** every one of the fourteen properties has a test that fails when the guard is
  removed, proven by mutation rather than asserted; an empty admitted result cannot widen to
  unfiltered data, a nearby dimension, another version or a partial result; the four unavailable
  conditions are compared against **each other**, not each against a fixture. **Conditional on
  `SV1-04`:** if the runtime adapter deferred, the no-concrete-RRA-import property is asserted
  against a composition that does not ship, and is recorded NOT EXERCISED with the reason — the
  other thirteen properties are unaffected, because they hold over the two packages themselves.
- **Risk:** **a test that cannot fail.** Every finding in the `RCA` slice-1 verification round was
  one. Mutation-test each guard; a mutant that is malformed proves nothing, so verify the mutant
  actually introduces the defect before calling a test weak. And mutation testing cannot find a
  *missing* guard — walk `FR-150`'s enumeration and `RRA-014` §Verification's list item by item,
  because a property no test names is invisible to every mutant. Second risk: a redundant guard —
  one outcome test passes with either guard alone; isolate each.

### `SV1-08` — Latency and query-shape baseline

- **Requirements:** `FR-144`.
- **Interfaces.** Consumes: `SemanticQueryActions.request`. Produces: a measured baseline ledger;
  no source module other than the measurement test.
- **Delivers:** `tests/test_sv108_query_baseline.py` and an evidence ledger under
  `docs/superpowers/plans/`. `FR-144`: "Latency and query-shape evidence **may measure execution**
  but may not add caching, pre-aggregation, materialized views, sampling, or result changes."
  Measure per-view latency and the query shape each view issues; record both.
- **Authority note — this slice needs none beyond what is active.** `RRA-014` implementation
  precondition 2 names `SV1-08` as an admitted self-identifying slice, and `FR-144` authorizes the
  measurement explicitly. An earlier reading treated `SV1-08` as scope-ambiguous; the two citations
  settle it. The ledger half follows the `G4-01` precedent — Article IV governs product code, not
  measurement notes.
- **Acceptance:** the baseline is deterministic enough to be a baseline — report a distribution, not
  one sample; the measurement adds no cache, no pre-aggregation, no materialized view and no
  sampling, asserted by a diff showing zero additions to any read path; results with measurement
  enabled are byte-identical to results without it. **Conditional on `SV1-04`:** if the runtime
  adapter deferred, there is no shipped composition to measure and this whole slice is recorded NOT
  EXERCISED rather than passed. A latency figure taken over a test-local fake port measures the
  fake, and publishing it as the baseline `D1-09` will later optimize against is worse than having
  none.
- **Risk:** **a measurement that changes what it measures.** `FR-144`'s final clause bars "result
  changes"; a timing harness that warms a path, memoizes a definition lookup, or reorders work is a
  result change. Second risk: measuring the null case — a view that returns empty for the fixture
  measures nothing useful, and "a run that can only produce the null case is NOT EXERCISED, not
  PASS". Ask whether the non-empty case was reachable for each of the eight views, and record which
  were not.

---

## 5. What this plan does not do

- **It authorizes no surface.** Both specifications exclude routes, templates and shell assets, so
  nothing here is reachable by a customer. The consumer is `D1`.
- **`D1` needs authority this plan does not supply, and the gap is narrower than "no specification
  names those files".** `RCA-005` §Scope **does** govern `src/khepri/runtime/shell_api.py` and
  `shell_templates/` — that is how the owner settled `C1-07`'s `U1` dependency on 2026-09-08 — so
  D1's surface *paths* are governed and D1 is not path-blocked. What is absent is **requirement**
  authority: no active `FR` names an executive overview, decision modules, a report workspace or
  global filters, and `RCA-005`'s own Exclusions bar "any calculation, aggregation or re-rendering
  of figures on a workspace surface" and "any product-telemetry event" — which reaches `D1-03`,
  `D1-04` and `D1-11` directly. `RRA-014` and `RCA-006` add nothing here: both disclaim routes,
  templates and shell assets. So D1 needs an owner-authored requirement set, not a scope grant; it
  is not in roadmap §17; and it is the next thing between `SV1` and `M4`.
- **It decides nothing `RRA-014` or `RCA-006` left open**, with one exception, recorded rather than
  buried: §2 pins the seam's shape, which the specifications leave to implementation. It is written
  here so `SV1-02` can build against it, and it is reviewable before any code exists.
- **It does not update the roadmap.** §17 item 22 still names `SV1-01` as the first incomplete
  critical-path item and §16's header pins `b5fa6ce`; the `SV1-01` design note §10 separately asks
  for a documentation-only follow-up recording `SV1-01`'s merge SHA. That is one small docs PR, and
  it is not this plan's.

---

## 6. Sequencing summary

```text
SV1-02  registry            RRA   FR-134,135,136
   |
SV1-03  compatibility       RRA   FR-137,141
   |
SV1-04  query + THE SEAM    RCA   FR-145..149     <- scope question on the adapter
   |
SV1-05  propagation         RRA   FR-139,140,138
   |
SV1-06  published versions  RRA   FR-143,134
   |
SV1-07  boundary evidence   both  FR-150 + Verification
   |
SV1-08  baseline            RRA   FR-144
   |
   v
[D1 authority — owner-authored, does not exist]
   |
D1-01..11  ->  M4
```
