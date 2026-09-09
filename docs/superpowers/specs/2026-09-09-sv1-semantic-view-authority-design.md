# SV1-01 Semantic-View and Governed-Query Authority Design

**Status:** Proposed design; grants no authority

**Roadmap:** `SV1-01`

**Baseline:** `main` at `ac999e8` (`#415`)

**Consumed by:** one owner-authored authority proposal containing `RRA-014` and `RCA-006`

---

## 1. Purpose

`C1` now publishes governed single- and two-population facts, and `T1` exposes their metric,
population, reason, caveat, and evidence definitions. Khepri still has no contract for selecting
those facts into reusable read models. The roadmap calls that missing layer a semantic view.

`SV1-01` supplies authority for that layer and nothing above it. It does not build a dashboard,
route, report surface, API, cache, pre-aggregation, connector, or AI feature. It creates no product
code in the authority proposal itself.

The design preserves the roadmap's ownership split:

- `RRA` owns what a semantic view means, which governed facts it may select, which parameters it
  admits, and what evidence or refusal accompanies its result.
- `RCA` owns who may request a view, which organization-scoped sources may be read, and how the
  request reaches the RRA contract without widening authorization or retention.

## 2. Decision

Create two new active specifications in one atomic proposal:

1. **`RRA-014: Semantic View Definitions and No-Calculation Projection`**
2. **`RCA-006: Organization-Scoped Semantic Query Orchestration`**

The branch and pull request are proposals. The specifications become active only if the sole owner
merges them to `main`, as Constitution II requires.

Two artifacts are necessary because a specification must depend on exactly one family. A single
cross-family specification would fail the registry rule; assigning both halves to either family
would erase the roadmap's RRA-definition/RCA-orchestration boundary.

Both specifications enter `governance/registry.yaml` in the same proposal. `RCA-006` depends on
`RRA-014`, so a partial merge cannot authorize orchestration against a contract that does not exist.

## 3. Alternatives considered

### Amend `RRA-011` and `RCA-005`

This changes fewer files but is rejected. `RRA-011` is a catalog over existing calculation and
explicitly does not govern consuming surfaces. `RCA-005` governs retained workspace objects and the
pairwise comparison action, not a reusable governed-query subsystem. Appending SV1 would turn both
documents into catch-all authorities and make their existing exclusions misleading.

### Activate only the RRA half first

This is mechanically safe but leaves the roadmap item incomplete: `SV1-01` names both semantic-view
and governed-query authority. It also invites the RRA contract to be shaped without the isolation
and lifecycle obligations its only production caller must satisfy.

### One decision plus later specifications

This is rejected because no unresolved policy choice requires a decision. Existing authority already
settles the relevant boundaries: canonical organization isolation, least data, no speculative
retention, and no product telemetry. Specifications can apply those decisions directly.

## 4. `RRA-014` boundary

### 4.1 Scope

`RRA-014` governs a new, isolated package under `src/khepri/rra/semantic_views/` and its tests. It
may define:

- immutable, versioned `SemanticViewDefinition` records;
- the closed registry of published view definitions;
- validation of requested dimensions and filters against a definition;
- projection of already-governed facts, refusals, caveats, populations, and evidence into a
  language-neutral semantic-view result;
- stable refusal identities and their bilingual wording for view-level contract failures;
- version compatibility and rollback rules; and
- query-shape and latency measurement that changes no result.

It does not govern runtime routes, templates, shell assets, workspace persistence, raw-source access,
or any file currently owned by another active specification.

The registry row should depend on exactly one family, `RRA`, plus the active specifications it reads
directly: `RRA-004`, `RRA-006`, `RRA-008`, `RRA-009`, `RRA-011`, and `RRA-013`. It does not depend on
`RRA-012`, because SV1 produces no presentation component.

### 4.2 Definition contract

Each definition has a stable `view_id` and `view_version` and declares, rather than infers:

- the source shape it accepts: a governed single-population bundle, a governed two-population
  bundle, or either where the projection is identical;
- admitted metric codes, derived from `RRA-011`'s catalog rather than retyped;
- admitted dimension codes, derived from the `RRA-004` declarations that produce them;
- admitted request filters and any fixed filter the view applies;
- required evidence fields and how missing evidence is represented;
- deterministic output-field order; and
- whether an empty admitted result is valid or is a stated refusal.

The first registry may publish only the eight views the roadmap names:

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

`SV1-02` decides their exact field allowlists. `SV1-01` authorizes no ninth view by implication: a
new view requires a new published definition version under the same closed registry rules.

### 4.3 No-calculation projection

A semantic view may select, rename by governed vocabulary, order, and present fields that an input
bundle or catalog projection already carries. It may not:

- add, subtract, multiply, divide, round, normalize, rank, score, aggregate, group into a new fact,
  or derive a ratio or delta;
- query raw source rows or reconstruct a fact from retained bases;
- parse customer SQL, expressions, formulas, calculated fields, or arbitrary column names;
- substitute a nearby metric, version, dimension, filter, period, or population; or
- suppress a refusal, caveat, evidence absence, or population qualifier to make a view appear
  complete.

Deterministic ordering is allowed only over fields the definition names. Ordering does not create a
rank value. A top-N or threshold operation changes the admitted population and is excluded until a
governed fact or later authority defines it.

### 4.4 Visible filters and exact requests

Every result carries the exact view identity and version, source identities, effective dimensions,
and effective filters used to produce it. A fixed filter is legal only when the definition declares
it and the result repeats it. There is no hidden request state.

An unknown view, version, metric, dimension, or filter refuses before source projection. An omitted
required parameter refuses rather than selecting a default. An explicit definition default is part
of the versioned contract and is repeated in the effective request.

### 4.5 Propagation and emptiness

The result preserves the source's governed values and metadata byte-for-byte at their typed value
boundary. It carries the source formula, package, mapping, family, bundle, and view versions that are
relevant to each projected claim.

Refused facts remain refused; caveated facts retain every caveat; missing evidence remains an
explicit governed absence. A view cannot convert any of those states into an ordinary value.

An admitted query with no matching governed facts returns the definition's explicit empty outcome.
It never falls back to all data, another dimension, a previous version, or a partial result.

### 4.6 Versioning

A published definition is immutable. Any change to its admitted source shape, fields, metric set,
dimension set, filter set, fixed filters, evidence requirements, empty-result rule, or output order
creates a new `view_version`.

Requests name an exact version. The first release provides no floating `latest` alias. A deployment
may keep more than one reader for rollback, but a reader either supports the named version exactly or
refuses it. Response identity includes the view version and the underlying governed versions so a
consumer cannot mistake a changed view for the same answer.

## 5. `RCA-006` boundary

### 5.1 Scope

`RCA-006` governs a new, isolated package under `src/khepri/rca/semantic_queries/` and its tests. It
may define the request and outcome contracts, the organization-scoped query service, and read-only
ports into the workspace and `RRA-014` projector.

Its registry row depends on exactly one family, `RCA`, plus `RCA-001`, `RCA-005`, and `RRA-014`.

It does not govern a route, template, navigation entry, dashboard, public API, migration, cache,
background job, or renderer. Those belong to later D1 or distribution authority.

### 5.2 Request flow

The service accepts an authenticated actor, an organization, an exact view identity and version,
the source identifiers required by that definition, and the explicit dimension/filter parameters.

The flow is fixed:

1. Resolve the actor through canonical `RCA-001` authorization.
2. Read every named source through the requesting organization's opaque scope.
3. Return the existing uniform unavailable outcome when any source is absent, deleted, or outside
   the scope; disclose nothing about which condition held.
4. Pass only successfully scoped governed bundles and the explicit request to `RRA-014`.
5. Return the RRA result without recalculation, relabelling, or state suppression.

RCA never imports a concrete RRA implementation. It calls an injected protocol, following the
existing comparison-orchestration seam.

### 5.3 Retention, privacy, and telemetry

A semantic query is derived at read time and creates no retained content class. It writes no table,
artifact, cache, preference, history row, counter, access record, or query log. It introduces no
migration and no deletion cascade.

No new audit or product-telemetry event is authorized. A future surface may have a separately
authorized security-audit obligation, but `SV1-01` does not invent one. Request parameters and result
content do not enter existing logs.

Deleting or losing any source makes a later query unavailable. No stale result survives its source.

## 6. Failure ownership

The two specifications keep failures on the side that can know them:

| Failure | Owner | Result |
|---|---|---|
| Actor cannot act in the organization | `RCA-006` / `RCA-001` | Existing uniform denial |
| Source is absent, deleted, or cross-scope | `RCA-006` / `RCA-005` | Uniform unavailable outcome |
| View or version is unknown | `RRA-014` | Stable view-contract refusal |
| Dimension/filter is unsupported or incomplete | `RRA-014` | Refusal before projection |
| Source bundle shape is incompatible | `RRA-014` | Refusal with no partial result |
| Governed fact is refused or caveated | Source RRA authority | Propagated unchanged |
| Required evidence is absent | `RRA-014` | Explicit absence or definition-stated refusal |
| Admitted result is empty | `RRA-014` | Definition-stated empty outcome; no fallback |

## 7. Slice map after activation

The authority proposal contains no product code. If merged, it admits the roadmap's later slices as
separate, independently verifiable changes:

| Slice | Authorized result |
|---|---|
| `SV1-02` | Closed, versioned definition registry; no query execution |
| `SV1-03` | Dimension/filter/source compatibility validation; no workspace access |
| `SV1-04` | Organization-scoped read service through the RRA protocol; no surface |
| `SV1-05` | Exact metadata, evidence, caveat, refusal, and empty-state propagation |
| `SV1-06` | Published versions and exact-version rollback compatibility |
| `SV1-07` | Cross-scope, hidden-filter, arithmetic, unsupported-shape, version, and emptiness evidence |
| `SV1-08` | Latency and query-shape baseline; no cache or pre-aggregation |

No slice may widen another's scope merely because all are named by the same two specifications.

## 8. Verification design

The authority proposal must pass the repository's governance validator and prove that both new
specifications depend on exactly one family, use unique identifiers, cite only known active
dependencies, and point to existing documents.

The specifications must require later implementation evidence for at least these properties:

- the definition registry equals the closed published set and every metric/dimension is derived
  from its governing declaration;
- an unsupported view, version, source shape, dimension, filter, or required parameter refuses
  before projection;
- the effective request in the result exposes every fixed and requested filter;
- projected values and governed metadata equal their source records, and no semantic-view module
  contains arithmetic or aggregate behavior;
- every refusal, caveat, population qualifier, evidence value, and evidence absence survives the
  projection;
- cross-organization, missing, and deleted sources produce the same content-free unavailable
  outcome;
- the query path writes no database row, object, audit event, telemetry event, cache entry, or log
  content;
- an exact version either resolves to its immutable definition or refuses, with no `latest`
  fallback;
- empty results cannot widen into unfiltered results; and
- every new file scores 10.00 in the required server-side CodeScene gate.

Every later slice also runs `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest`.

## 9. Explicit exclusions

This design and the resulting authority proposal authorize none of the following:

- new metrics, formulas, facts, populations, comparison semantics, reason or caveat changes;
- raw-row access, arbitrary SQL, customer formulas, calculated fields, top-N, ranking, scoring, or
  statistical inference;
- a dashboard, report redesign, journey step, shell destination, API, embed, AI prompt, or customer
  wording outside the view-level refusal vocabulary;
- retained semantic-query results, caching, pre-aggregation, materialized views, background refresh,
  schedules, alerts, or telemetry;
- cross-organization joins, sharing, export, or per-object permissions;
- changes to any active specification's governed source path; or
- product code in the `SV1-01` proposal.

## 10. Acceptance

The `SV1-01` authority activation is complete only when one owner-merged pull request adds
`RRA-014`, `RCA-006`, and their two registry rows; the documents agree on their shared
request/result seam; and governance validation, Ruff, pytest, and CodeScene pass.

The proposal MUST NOT claim its own future `main` SHA. After merge, a documentation-only follow-up
records `SV1-01` as merged at the actual `main` SHA and names `SV1-02` as the next slice.

Until that merge, this document is design input only and grants no implementation authority.
