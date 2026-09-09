# SV1-01 Authority Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate the paired RRA semantic-view and RCA governed-query authority that unblocks `SV1-02` without adding product code.

**Architecture:** One atomic pull request adds `RRA-014` for versioned, no-calculation semantic-view definitions and `RCA-006` for organization-scoped read orchestration. The two specifications use disjoint future source packages, meet through a narrow request/result seam, and enter the registry together with `RCA-006` depending on `RRA-014`.

**Tech Stack:** Markdown governance specifications, YAML registry, `uv`, `khepri-gov`, Ruff, pytest, GitHub pull requests

**Spec:** `docs/superpowers/specs/2026-09-09-sv1-semantic-view-authority-design.md`

## Global Constraints

- Read `governance/CONSTITUTION.md` and `governance/registry.yaml` before editing either governed artifact.
- `governance/registry.yaml` is authoritative for type, identity, state, document, dependencies, and supersession.
- A branch or pull request is a proposal; only the sole owner's merge to `main` activates `RRA-014` and `RCA-006`.
- The proposal contains no product code, migration, route, template, stylesheet, API, cache, persistence, telemetry, or new data use.
- `RRA-014` depends on exactly one family, `RRA`; `RCA-006` depends on exactly one family, `RCA`.
- Future RRA code is confined to `src/khepri/rra/semantic_views/`; future RCA code is confined to `src/khepri/rca/semantic_queries/`.
- Semantic views may select, visibly filter, deterministically order, and present governed facts; they may not calculate, aggregate, rank, score, normalize, or query raw rows.
- Every request names an exact view version. There is no floating `latest` alias.
- Every result exposes its effective dimensions and filters; no hidden filter or implicit fallback is permitted.
- Semantic-query results are derived at read time and retain no row, object, cache entry, audit event, telemetry event, access record, or content-bearing log.
- Do not mark `SV1-01` merged or cite a future merge SHA on the proposal branch. Reconcile the roadmap only after the owner merges the authority PR.
- Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` before handoff.
- CodeScene Code Health Review is a required server-side PR gate; every new file must score 10.00.
- Preserve unrelated working-tree changes. Stage only the files named by each task.

---

### Task 1: Activate the RRA semantic-view definition boundary

**Files:**
- Create: `governance/specifications/RRA-014.md`
- Modify: `governance/registry.yaml`

**Interfaces:**
- Consumes: `RRA-004` governed facts and dimensions; `RRA-006` single- and two-population bundle surfaces; `RRA-008` analysis and comparison facts; `RRA-009` bilingual wording rules; `RRA-011` definitions; `RRA-013` bundle evidence supply.
- Produces: registered active specification identity `RRA-014`, future scope `src/khepri/rra/semantic_views/`, and requirements `FR-134` through `FR-144` for `SV1-02`, `SV1-03`, `SV1-05`, `SV1-06`, `SV1-07`, and `SV1-08`.

- [ ] **Step 1: Re-read the governing inputs at the execution baseline**

Run:

```powershell
Get-Content -Raw governance/CONSTITUTION.md
Get-Content -Raw governance/registry.yaml
Get-Content -Raw governance/specifications/RRA-004.md
Get-Content -Raw governance/specifications/RRA-006.md
Get-Content -Raw governance/specifications/RRA-008.md
Get-Content -Raw governance/specifications/RRA-009.md
Get-Content -Raw governance/specifications/RRA-011.md
Get-Content -Raw governance/specifications/RRA-013.md
```

Expected: every dependency is `active`; `RRA-013` is the highest registered RRA specification; no existing specification governs `src/khepri/rra/semantic_views/`.

- [ ] **Step 2: Create `RRA-014.md` with the complete authority contract**

Write these sections in this order: `Outcome`, `Scope`, `Semantic view contract`, `Requirements`, `Exclusions`, `Invariants`, `Verification`, `Implementation preconditions`, and the standard registry-authority closing sentence.

The `Outcome` must state all of these claims directly:

```text
- A semantic view is an immutable, versioned selection and projection over already-governed facts.
- It defines no formula, fact, population, metric, or business calculation.
- It preserves refusals, caveats, populations, evidence, and governed versions.
- It exposes every effective dimension and filter.
- It fails closed on an unknown or incompatible request.
```

The `Scope` must name only the future package `src/khepri/rra/semantic_views/` and `tests/`. State explicitly that runtime routes, templates, shell assets, workspace persistence, raw-source access, and every path governed by another active specification are outside scope.

Define the semantic-view record with these contract fields, without choosing Python types that belong to `SV1-02`:

```text
view_id
view_version
accepted_source_shape
metric_allowlist
dimension_allowlist
request_filter_allowlist
fixed_filters
required_evidence
output_field_order
empty_result_rule
```

Name exactly the roadmap's initial view set:

```text
ExecutiveOverviewView
PeriodComparisonView
BranchPerformanceView
ProductCategoryView
BasketView
ConcentrationView
ReportEvidenceView
MetricAvailabilityView
```

Add the following requirements with these meanings:

| ID | Required contract |
|---|---|
| `FR-134` | Every definition has immutable `view_id` and `view_version`; changing any admitted source, field, metric, dimension, filter, evidence requirement, empty rule, or output order creates a new version. |
| `FR-135` | The published registry is closed to the eight named initial views; metric and dimension members derive from their governing declarations and are never retyped as a second truth. |
| `FR-136` | Each definition admits an exact source shape: governed single-population bundle, governed two-population bundle, or both only when their projection contract is identical. |
| `FR-137` | Every request and result states effective dimensions, requested filters, and definition-fixed filters; an undeclared, hidden, missing-required, or unsupported parameter refuses before projection. |
| `FR-138` | Projection may select, use governed wording, and deterministically order existing fields; it may not perform arithmetic, aggregation, grouping into a new fact, ranking, scoring, normalization, top-N, thresholding, or raw-row access. |
| `FR-139` | Projected typed values and their mapping, package, formula, family, bundle, and view versions equal the source records; no re-rounding, relabelling outside governed vocabulary, or substitution is allowed. |
| `FR-140` | Every source refusal, caveat, population qualifier, evidence value, and governed evidence absence survives projection; none may be suppressed or converted into an ordinary value. |
| `FR-141` | Unknown view/version/metric/dimension/filter, incompatible source shape, or missing required evidence returns a stable view-contract refusal with bilingual wording and no partial result. |
| `FR-142` | An admitted empty result follows the definition's explicit empty rule and never widens to unfiltered data, a nearby dimension, another version, or a partial result. |
| `FR-143` | Requests name an exact version; supported historical readers return that immutable definition and unsupported versions refuse. No `latest` alias or silent upgrade exists. |
| `FR-144` | Latency and query-shape evidence may measure execution but may not add caching, pre-aggregation, materialized views, sampling, or result changes. |

The exclusions must repeat the design's hard boundaries: no new calculations or governed fact vocabulary; no arbitrary SQL or customer expressions; no routes or presentation; no persistence, caching, scheduling, telemetry, cross-scope joins, exports, or AI; no edits to paths owned by another active specification.

The verification section must require independent tests for the exact registry extent, derived allowlists, early refusal, visible effective filters, arithmetic absence, propagation completeness, exact versions, explicit emptiness, and CodeScene 10.00 for each new file.

- [ ] **Step 3: Register `RRA-014` immediately after `RRA-013`**

Add exactly:

```yaml
  - type: specification
    id: RRA-014
    state: active
    document: governance/specifications/RRA-014.md
    depends_on:
      - RRA
      - RRA-004
      - RRA-006
      - RRA-008
      - RRA-009
      - RRA-011
      - RRA-013
```

Do not add `RCA`, `RCA-005`, `RRA-012`, or a supersession field.

- [ ] **Step 4: Validate the first half of the proposal**

Run:

```powershell
uv run khepri-gov validate
git diff --check
rg -n "RRA-014|FR-13[4-9]|FR-14[0-4]|semantic_views" governance/specifications/RRA-014.md governance/registry.yaml
```

Expected: governance passes; no whitespace error; one `RRA-014` registry row; requirements `FR-134` through `FR-144` appear once each; only the RRA family is a family dependency.

- [ ] **Step 5: Commit the RRA authority half**

```powershell
git add governance/specifications/RRA-014.md governance/registry.yaml
git commit -m "governance(sv1-01): define versioned no-calculation semantic views"
```

### Task 2: Activate the RCA governed-query orchestration boundary

**Files:**
- Create: `governance/specifications/RCA-006.md`
- Modify: `governance/registry.yaml`

**Interfaces:**
- Consumes: `RCA-001` canonical actor and opaque organization scope; `RCA-005` retained dataset-version/run lookup and deleted/unavailable behavior; `RRA-014` exact-version semantic-view request and result contract.
- Produces: registered active specification identity `RCA-006`, future scope `src/khepri/rca/semantic_queries/`, and requirements `FR-145` through `FR-150` for the RCA half of `SV1-04` and the isolation/no-write half of `SV1-07`.

- [ ] **Step 1: Re-read the RCA boundary and the newly drafted RRA seam**

Run:

```powershell
Get-Content -Raw governance/specifications/RCA-001.md
Get-Content -Raw governance/specifications/RCA-005.md
Get-Content -Raw governance/specifications/RRA-014.md
```

Expected: `RCA-001` owns canonical authorization; `RCA-005` owns organization-scoped versions and runs; `RRA-014` owns all semantic validation and projection.

- [ ] **Step 2: Create `RCA-006.md` with the complete orchestration contract**

Write these sections in this order: `Outcome`, `Scope`, `Request flow`, `Requirements`, `Retention, privacy, and telemetry`, `Exclusions`, `Invariants`, `Verification`, `Implementation preconditions`, and the standard registry-authority closing sentence.

The `Outcome` must state that an authenticated owner or member may request one exact semantic-view version over sources in one organization; RCA scopes and loads the sources, RRA validates and projects them, and no result is retained.

The `Scope` must name only the future package `src/khepri/rca/semantic_queries/` and `tests/`. State explicitly that no route, runtime wiring, template, shell asset, public API, migration, cache, background job, renderer, or existing workspace file is governed.

Freeze the conceptual seam in the document:

```text
Request: actor + organization + exact view identity/version + source identifiers + explicit dimensions/filters
RCA work: canonical authorization + organization-scoped source reads + uniform unavailable behavior
RRA work: definition lookup + validation + no-calculation projection + view refusal/empty/result
Result: exact view/source identities + effective request + governed projected state
```

State that the future RCA implementation calls an injected protocol and does not import a concrete RRA implementation, following `rca/workspace/comparisons.py`'s `ComparisonAssembly` precedent.

Add the following requirements with these meanings:

| ID | Required contract |
|---|---|
| `FR-145` | Every request resolves the actor and organization through canonical `RCA-001` authorization before reading a source or invoking RRA. |
| `FR-146` | Every named source is loaded through the requesting organization's opaque scope; absent, deleted, corrupt, or cross-scope sources return the same content-free unavailable outcome without identifying which condition held. |
| `FR-147` | RCA passes only successfully scoped governed sources and the explicit request to an injected `RRA-014` protocol, and returns its refusal, empty outcome, or result without calculation, relabelling, filtering, or state suppression. |
| `FR-148` | A semantic query is derived at read time and writes no database row, object, artifact, cache, preference, history entry, tombstone, or deletion evidence; losing a source makes a later query unavailable. |
| `FR-149` | The path emits no new audit or product-telemetry event, counter, access record, or content-bearing log; request parameters and result content do not enter existing logs. |
| `FR-150` | Cross-organization, missing, deleted, exact-version, no-write, no-event, and no-concrete-RRA-import behavior are independently tested, including byte-identical unavailable outcomes and zero writes. |

The exclusions must bar surfaces and routes, all calculation and projection semantics, persistence and retention changes, product telemetry, cross-organization joins, sharing/export, raw-row access, schedules, and edits to `RCA-001`, `RCA-005`, or `RRA-014` source paths.

The verification section must require a real two-organization request, a deleted-source request, a missing-source request, a write-count assertion spanning every injected store, an audit/telemetry absence assertion, and a static import-boundary assertion.

- [ ] **Step 3: Register `RCA-006` immediately after `RCA-005`**

Add exactly:

```yaml
  - type: specification
    id: RCA-006
    state: active
    document: governance/specifications/RCA-006.md
    depends_on:
      - RCA
      - RCA-001
      - RCA-005
      - RRA-014
```

Do not add `RRA` as a family dependency and do not add a supersession field.

- [ ] **Step 4: Validate the complete paired authority**

Run:

```powershell
uv run khepri-gov validate
git diff --check
rg -n "RCA-006|RRA-014|FR-14[5-9]|FR-150|semantic_queries" governance/specifications/RCA-006.md governance/registry.yaml
```

Expected: governance passes; `RCA-006` depends on the known active-in-proposal `RRA-014`; requirements `FR-145` through `FR-150` appear once each; only the RCA family is a family dependency.

- [ ] **Step 5: Commit the RCA authority half**

```powershell
git add governance/specifications/RCA-006.md governance/registry.yaml
git commit -m "governance(sv1-01): scope organization semantic queries"
```

### Task 3: Prove proposal consistency and open the authority PR

**Files:**
- Verify: `docs/superpowers/specs/2026-09-09-sv1-semantic-view-authority-design.md`
- Verify: `governance/specifications/RRA-014.md`
- Verify: `governance/specifications/RCA-006.md`
- Verify: `governance/registry.yaml`

**Interfaces:**
- Consumes: both registered specification identities and their shared request/result boundary.
- Produces: one reviewable GitHub proposal for `SV1-01`; no roadmap completion claim and no product code.

- [ ] **Step 1: Scan for placeholders and contract drift**

Run:

```powershell
rg -n "TBD|TODO|FIXME|PLACEHOLDER|latest alias|arbitrary SQL|hidden filter|product.telemetry|audit event" docs/superpowers/specs/2026-09-09-sv1-semantic-view-authority-design.md governance/specifications/RRA-014.md governance/specifications/RCA-006.md
```

Expected: no placeholder hits. Boundary terms appear only in explicit prohibitions or requirements. If `latest alias` appears, it says no such alias exists. If telemetry or audit appears, it says none is emitted.

- [ ] **Step 2: Check the exact changed-file scope**

Run:

```powershell
git diff --name-only origin/main...HEAD
git status --short
```

Expected committed PR scope:

```text
docs/superpowers/plans/2026-09-09-sv1-01-authority-activation.md
docs/superpowers/specs/2026-09-09-sv1-semantic-view-authority-design.md
governance/registry.yaml
governance/specifications/RCA-006.md
governance/specifications/RRA-014.md
```

Unrelated uncommitted files may appear in `git status`; do not stage or alter them.

- [ ] **Step 3: Run all required local gates**

Run:

```powershell
uv run khepri-gov validate
uv run ruff check .
uv run pytest
git diff --check origin/main...HEAD
```

Expected: governance validation passes; Ruff passes; pytest has no unexpected failure; diff check is clean.

- [ ] **Step 4: Commit any plan/design-only correction separately**

If this plan or its approved design changed after their checkpoint commit, stage only those two files and commit them before pushing:

```powershell
git add docs/superpowers/plans/2026-09-09-sv1-01-authority-activation.md docs/superpowers/specs/2026-09-09-sv1-semantic-view-authority-design.md
git commit -m "plan(sv1-01): activate the paired semantic-query authority"
```

Expected: the authority commits remain separately reviewable, while the design/plan correction contains no governed artifact.

- [ ] **Step 5: Push and open one proposal PR**

Push the branch, then open a PR titled:

```text
governance(sv1-01): activate semantic-view and governed-query authority
```

The PR body must state:

```text
Scope: RRA-014 + RCA-006 + their registry rows; no product code.
Governed artifacts: RRA-014 and RCA-006, both proposed active and governing only on owner merge.
Owner decision: merge approves; close rejects.
Retention: derived at read time; no new content class, cache, audit event, or telemetry event.
Parallel collision: no migration and no stacked dependency.
Evidence: exact outputs from khepri-gov, Ruff, pytest, and diff check.
Roadmap: do not mark SV1-01 merged until a follow-up can cite the actual main SHA.
```

- [ ] **Step 6: Verify server-side gates without merging**

Run:

```powershell
gh pr checks --repo Kemetra/Khepri
```

Expected before owner review: governance, Ruff, pytest, and CodeScene are present. CodeScene must pass and every new file must score 10.00. Do not merge; the PR is the owner's proposal gate.

---

## Post-merge follow-up

After the owner merges the authority PR, create a fresh documentation-only branch from the actual
`origin/main`. Update the roadmap's `SV1-01` task and status row to `MERGED` with the real merge SHA,
make `SV1-02` the first incomplete critical-path item, run the three repository gates, and open a
separate PR. Do not prepare that claim before the authority merge exists.
