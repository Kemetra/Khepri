# Khepri Master Product Roadmap — Integrated Completion Plan v2

**Status:** Proposed planning artifact. This document grants no implementation authority and does not replace `governance/registry.yaml`, an active specification, or an active decision.

**Repository:** `Kemetra/Khepri`

**Verified baseline:** `origin/main` at `d355d12` on 2026-09-01. CAL1 state reconciled to `#308`
(`7088749`), which published all seven successor versions, the nine PRs merged after it — seven
corrections and two documentation slices — through `#325` (`aa19ff6`), `CAL1-11`'s compatibility
sweep at `#328` (`9e7a886`), and `CAL1-12` through `CAL1-15` at `#330` (`f320c17`). Since `f320c17`:
`T1-01` through `T1-05` and `T1-08` merged (`#334`, `#338`, `#340`, `#343`), the public landing and
legal surfaces merged (`#331`, `#339`, `#341`), and `#345` raised the `RRA-011` Exclusion reading
that `KHEPRI-DEC-032` answers.

**Audience:** Ahmed Shaaban (owner and merge authority), Claude Code (planning and adversarial review), Codex (bounded implementation), design reviewers, and future operators.

**Purpose:** Provide one complete, dependency-ordered roadmap from the current calculation-correction program through a calculation-validated design-partner alpha, durable workspaces, an evidence-backed decision workspace, self-serve monetization, platform distribution, governed intelligence, and enterprise GA.

## Historical replacement verification record

Checked against `main` at `f86507920155077fd3c87eb8878d29fb1624db69` before this document replaced its predecessor. Confirmed at that commit:

- the baseline SHA and date match `origin/main`, and `migrations/versions/` has exactly one head (`20260822_0020`);
- `RRA-003`, `RRA-004`, and `RRA-008` are `active` in `governance/registry.yaml` and carry the successor semantics merged by `#264`; `RCA-001`, `RCA-002`, and `RRA-009` are `active`;
- `rra003.mapping.v3` and `rra004.package.v3` are named in those specifications while
  `src/khepri/rra/mapping.py:21` still pinned `rra003.mapping.v2`, so CAL1 had not started at that
  historical baseline;
- `docs/superpowers/plans/` then contained no CAL1 plan and no execution ledger, which is why CAL1
  was historically `READY_FOR_PLAN` rather than `READY_FOR_IMPLEMENTATION`;
- `#152`, `#211`, and `#231` are the only open issues, and all three are carried in section 0.2;
- the merged local staging stack matches the `OPS1` baseline described below — one built image running web, worker, and migrations against TLS PostgreSQL and MinIO;
- `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` still carries `visibility_timeout_seconds` and `max_receive_count`, the retired broker keys `KHEPRI-DEC-008` says must leave the file, so `OPS1-09` is real outstanding work;
- `KHEPRI-DEC-027` is `active` and blocks `OPS1-02` by name; `KHEPRI-DEC-013` is retired with no successor, so `STAT1`'s reciprocal-authority precondition is stated correctly;
- the handoff gates and the CodeScene requirement match `AGENTS.md`.

Three corrections applied to the draft as a result of that review, marked in place. Successive rounds of adversarial review on `#266` found further defects of the same three kinds — an exception no artifact grants, a governed version published incomplete across slices, and a cross-reference into active governance broken by renumbering. Each was verified against the active artifact before it was applied, and each is recorded at the section it touches rather than listed here:

1. **`CAL1` claimed an exception to the small-slice rule that no artifact grants it.** `governance/CONSTITUTION.md` Article IV admits product code only in small, independently verifiable slices, and the merged design at `18019b5` states that `C0` must merge before `C1`-`C4` as separately versioned slices. The draft's justification — that the successor families share package and formula identities — does not hold, because the governed successor versions are per family. See the `CAL1` release strategy.
2. **Task identifiers were being renumbered across the replacement**, which would have retargeted `KHEPRI-DEC-027`'s blocking clause from CI-only provisioning to a sizing reissue, and left `RCA-002`'s `R8-01` and `R5-02`/`R5-04` citations, plus `KHEPRI-DEC-025`'s `R5-02`…`R5-06`, resolving to nothing at this path. See section 0.1, the `OPS1` table, and the `R5` program.
3. **The status vocabulary was used without being defined, and open issues had no home.** Section 15 restores the convention and the next-actionable-task rule, at the section number `KHEPRI-DEC-025` cites; section 0.2 carries `#152`, `#211`, and `#231` forward.

## Current CAL1 reconciliation

At `origin/main` `f320c17`, **all seven CAL1 successor versions have published.** `#308`
(`7088749`) carried the seven ordered publication commits — `rra003.mapping.v3`,
`rra004.package.v3`, `rra004.formula.v2`, then `rra008.comparison.v2`, `growth.v2`, `basket.v2`
and `concentration.v2` — each moving one constant and adding its own compatibility row. The
`xfail(strict=True)` on `test_profile_accepts_a_complete_contract_and_stamps_mapping_v3` was
removed in that PR, as the ledger required.

Prerequisites landed before it: `#292` (`1813682`) the independent oracle, owner residual ruling,
execution ledger, manifest/source-contract API ingestion, compatibility-gate wiring, admission
plumbing and the source-contract journey seam; `#300` (`8acef78`) the browser coverage-manifest
attestation surface; `#303` (`a2be74e`) the manifest exception fields, which §17 previously
carried as outstanding.

**Publication is not the end of the program.** Nine PRs merged after `#308`, each closing defects
in the now-governing contracts: `#310` (`9646223`) population corrections, `#314` (`1f535f2`)
validator guard tests, `#315` (`6288f77`) refusals where `RRA-003`/`RRA-004` require them instead
of a partial or doubled total, `#321` (`c5bfd44`) per-bucket completeness, `#323` (`604ff4b`) the
concentration curve refusing rather than narrowing, `#324` (`c24b857`) a missing key component
refusing four results rather than the package, and `#325` (`aa19ff6`) declared-event-key
collisions, plus the docs slices `#316` (`9bcbb2e`) and `#319` (`1428d74`).

That these were found *after* publication is the substantive fact for planning: the published
contracts governed real defects, and the review rounds on `#325` alone surfaced three
under-refusals — cases where an identity proof that could not be evaluated was reported as one
that passed. Four findings are deferred on `#326`.

`CAL1-11` merged at `9e7a886` (`#328`), and `CAL1-12` through `CAL1-15` — mutation and pharmacy
golden evidence, the validation gate, local staging, and external review — merged at `#330`
(`f320c17`). A pharmacy golden fixture (`tests/test_cal1_pharmacy_golden.py`) is on `main`, and
CodeScene passed on `#330`'s required server-side gate; it was not checkable from the authoring
session (MCP `CONNECTION_CLOSED`), so it is recorded from the check result rather than from a local
proxy. Two `P2` findings stay open by design: `CAVEAT_CURRENCY_NOT_DECLARED` is unreachable and needs an
`RRA-003` or `RRA-009` ruling, and the Excel container is not byte-identical across regenerations —
exactly one of 46 ZIP members differs, `docProps/core.xml`, in its `dcterms:created`/`modified`
wall-clock stamp — which needs an `RRA-006` reading of whether "deterministic regeneration" governs
container bytes or governed content.

**The delivery unit was never ruled on.** `#301` recorded the one-PR/seven-commit model as
explicitly proposed and awaiting an owner ruling; no `KHEPRI-DEC-*` row records one. In practice
the owner merged `#308` as that single seven-commit PR, and then merged nine further PRs
individually. This roadmap records what happened; it does not resolve the open question, and
§17's queue is annotated accordingly.

## UX reconciliation — merged via #306

`W1-05` previously required a six-surface customer scope (Workspace Overview, Datasets, Analyses,
Reports, Metrics, Activity) that conflicted with `KHEPRI_PRODUCT_UX_BLUEPRINT.md` §8's four-surface
navigation (Overview, Data, Analyses, Team). **That conflict is resolved.** `W1-05` and the M3/M4 UI
lists below carry the four-surface scope, with Reports/Metrics/Activity/Watchlists reached
contextually rather than as primary destinations. See `KHEPRI_PRODUCT_UX_BLUEPRINT.md` §5.1 for the
full integrated customer experience map and §8/§20 for the resolved navigation decision.

**Per `governance/CONSTITUTION.md` Article II, a branch or pull request is a proposal; it becomes
approved and governing only when the sole owner merges it to `main`.** #306 merged to `main` at
`1c51105`, so this section and every downstream `W1-05` reference in this document reflect the
governing resolution.

**Neither `W1` nor the blueprint is registered authority** — `governance/registry.yaml` still holds
only `FND`, `RRA`, `RCA` — so this reconciliation removes a documentary contradiction between two
roadmap-level artifacts; it does not make any M3 UX slice implementation-ready. `LOCKED product
direction` is not implementation authority: M3 UX still requires active `G2`/`G3` authority.

---

## 0. Merge strategy and source-of-truth rule

This document is the single current planning source at:

`docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`

Its predecessor is archived, unedited, at `docs/product/history/KHEPRI_MASTER_PRODUCT_ROADMAP_2026-08-24.md`.

Merge procedure, as executed:

1. The previous roadmap moved to `docs/product/history/KHEPRI_MASTER_PRODUCT_ROADMAP_2026-08-24.md` with its historical dispositions unedited.
2. This document was placed at `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`.
3. **Task identifiers and the two cited section numbers are stable across the replacement.** The repository cites this file mostly by task ID — four active governed artifacts do — and two of them additionally cite section numbers: `KHEPRI-DEC-025` cites `§15` and `KHEPRI-DEC-023` cites `§16`. Both keep their contents. Section 0.1 records what may not be renumbered, and says where each program's task table now lives.
4. Historical status prose is not copied forward; the archived roadmap and the merged pull requests preserve it. Tracked open defects are the deliberate exception and carry forward in section 0.2, because an issue with no planning home is an issue nobody sequences.
5. Update this roadmap only after a merge to `main`, except for clearly marked proposals.

The roadmap is not authority. If this roadmap conflicts with an active specification or decision, governance wins and the roadmap must be reconciled before implementation continues.

### 0.1 Identifier continuity

`R0`-`R8`, `OPS1`, and `S1` began in the archived roadmap. Their identifiers keep the meanings they held there. A program may gain a new identifier; renumbering an existing one silently retargets every citation below, including the blocking clause of an active decision.

Citations in **active** governed artifacts:

| Artifact | Cites | What the identifier must keep meaning |
|---|---|---|
| `governance/decisions/KHEPRI-DEC-031-local-only-design-partner-rehearsal.md` | `OPS1-02`…`OPS1-05`, `OPS1-09`, `R8-08`, `R8-11`, `T1-06`, `T1-07`, `T1-01`…`T1-05`, `T1-08` | The deferred-versus-blocked distinction, which the identifiers carry. `OPS1-02`…`OPS1-05`, `OPS1-09` and `R8-11` are **deferred**: authority active, unexercised. `R8-08` and `T1-07` are **blocked** by active `KHEPRI-DEC-015` and resume only by amending it. `T1-01`…`T1-05` and `T1-08` are the `M2` minimum `RRA-011` governs; `T1-06` is excluded to `M3`. A renumbering that moved any of these would silently retarget which of the two dispositions applies. |
| `governance/specifications/RRA-011.md` | `T1-01`…`T1-05`, `T1-08` | The metric, population, and reason catalog's `M2` minimum. `T1-06` lineage and `T1-07` telemetry are excluded by name. |
| `governance/decisions/KHEPRI-DEC-030-fra1-provisional-bootstrap-authority.md` | `OPS1-02` | Retires `KHEPRI-DEC-027`, whose blanket "`OPS1-02` remains blocked" clause is re-scoped: the provisional non-production bootstrap at the §4 measurement shape is authorized; final capacity, expansion, and external traffic remain blocked. `OPS1-02` is CI-only provisioning of the non-production environment, and nothing else. |
| `governance/specifications/RCA-002.md` | `R5-02`, `R5-04`, `R8-01` | `R8-01`'s surface map and its open browser-security-policy question; the two deferred `R5` credential tasks. |
| `governance/decisions/KHEPRI-DEC-025-clerk-private-beta-implementation-authorization.md` | `R3-11`, `R5-02`…`R5-06` | The Clerk credential-ownership dispositions. |
| `governance/decisions/KHEPRI-DEC-023-commercial-consent-route-authorization.md` | `R6-01`, `R6-08`, `R7-04`, `R7-05`, `R7-06` | The merged commercial-bridge slice boundaries. |

Citations by **section number**, which the replacement renumbers:

| Artifact | Cites | Resolves to |
|---|---|---|
| `governance/decisions/KHEPRI-DEC-025-...` (active) | "§15's rule that `MERGED` requires a `main` SHA" | **§15**, unchanged — the status convention keeps that number. |
| `governance/decisions/KHEPRI-DEC-023-...` (active) | `R7-06`'s definition of done includes "flipping §16's `R7` row" | **§16**, unchanged — the status table keeps that number. |

**`§15` and `§16` are therefore fixed points, and the rest of the document is numbered around them.** Both are honoured by keeping each section where its decision expects it, not by a redirect note: this roadmap does not govern, so it cannot retarget a decision's reference. An earlier revision of this replacement moved the convention to `§16.1` and added a note; that was wrong for exactly this reason. A future reorganization must either preserve both numbers or amend the citing decisions through the governed process first.

These two were found by searching every `active` artifact in `governance/registry.yaml` for a section citation next to roadmap vocabulary — a row, a status, the `MERGED` rule. A search for task identifiers alone misses them.

Merged design, plan, and reconciliation documents add citations to `R0-02`, `R0-03`, `R0-05`, `R1-01`, `R1-02`, `R3-09`, `R4-01`, `R5-01`, `R6-01`, `R7-01`, `R7-02`, `R7-05`, `R7-06`, `R8-01`, `R8-02`, `OPS1-01`, `OPS1-02`, and `OPS1-05` across `specs/001-rca-001-commercial-identity/`, `docs/superpowers/`, and `docs/platform/proposed-governance/`.

Where each task table now lives:

| Program | Task table |
|---|---|
| `R0`-`R4`, `R6`, `R7` | Archived roadmap only. These are `MERGED`; their tasks are closed and are not re-planned here. |
| `R5` | Identifiers and dispositions preserved below; the full `R5-01` design record stays in the archive. |
| `R8` | `R8-01`…`R8-07` in the archive, including the `R8-03` closure record. `R8-08`…`R8-11` below. |
| `OPS1`, `S1` | Below, with archived identifiers preserved and new work appended. |
| Everything else | Below. First defined in this document. |

### 0.2 Open tracked debt carried forward

| Issue | Subject | Owner | Disposition |
|---|---|---|---|
| `#152` | Apply the RCA construction-boundary stance to `khepri.rra` records | `S1` | `S1-05` closes it only after every classified high-risk record is addressed or explicitly accepted |
| `#231` | `R7-03` ships live-authorization evidence with no mutation proof that its guards can fail | `S1` triage, then one bounded slice | A green evidence suite is not proof a guard can fail. Rank it in `S1-02`, ahead of comparison work that inherits those guards |
| `#211` | Deferred minor review findings, batched | Whichever program next touches the named code | Includes consolidating the two boundary scanners `R7-07` left behind. Drain opportunistically; do not let it grow unread |
| `#326` | Three over-refusals from the `#323`/`#324`/`#325` review round, plus minting `repeated_event_key` as its own reason code | `CAL1` | All four withhold a provable figure rather than publishing a wrong one, so none blocks. The reason-code item needs seven files in lockstep: `wording.py` enforces bilingual completeness at import, so a half-landed code fails the whole suite |
| `#311` | `RRA-004`:141's partial-window selection has no producer, so its caveat is unreachable | `CAL1` or a later comparison slice | `RRA-004`:141 says the package **may** derive the prefix projection, so no published figure is wrong. Needs a new governed carrier, not a fix |

None of the five blocks `CAL1`.

---

## 1. Product north star

Khepri is a governed retail decision platform that converts imperfect operational exports into reproducible bilingual analysis, evidence-backed reports, and decision workflows, while clearly refusing any result whose business meaning, population, identity, coverage, or formula cannot be proven.

Khepri is not positioned as:

- another generic BI dashboard;
- a customer-authored formula engine;
- a general-purpose semantic-model editor;
- a chat-with-CSV product;
- a forecasting platform;
- a replacement for a customer data warehouse;
- a copy of AtScale, Cube, or ThoughtSpot.

Khepri combines four product strengths:

1. **Semantic admission:** prove what source data means before calculation.
2. **Deterministic retail truth:** publish only versioned facts over compatible populations.
3. **Evidence and refusal:** every material claim is traceable; unsupported claims are refused with a reason.
4. **Decision experience:** workspaces, comparison, dashboards, guided exploration, watchlists, APIs, and AI all consume the same governed facts.

The external product pattern is informed by three reference categories:

- AtScale-style semantic rigor, validation, lineage, and operations;
- Cube-style curated semantic views, catalog, APIs, and embedding;
- ThoughtSpot-style question-first UX, narrative dashboards, guided exploration, and watchlists.

Khepri's differentiator remains its upload-first admission, refusal system, retail specialization, bilingual parity, and evidence contract.

---

## 2. Non-negotiable operating rules

Before any agent changes code or governed artifacts, it must read:

1. `AGENTS.md`
2. `governance/CONSTITUTION.md`
3. `governance/registry.yaml`
4. the active specification and decisions for the requested slice;
5. this roadmap;
6. the relevant issue, design, plan, tests, and prior merged PRs.

Repository rules:

- Ahmed Shaaban is the only merge authority.
- A branch or PR is a proposal until merged to `main`.
- Product code requires active authority.
- **Product code is admitted only in small, independently verifiable slices linked to an active specification** (`governance/CONSTITUTION.md` Article IV, repeated in `AGENTS.md`). A slice does not widen its specification, privacy boundary, runtime boundary, or data use. **This roadmap grants no exception to that rule, to any program, including `CAL1`.**
- Ambiguity in identity, scope, semantics, population, privacy, retention, or runtime fails closed.
- Authoritative retail arithmetic stays in RRA facts and derived fact families.
- RCA owns commercial identity, organization/workspace workflow, authorization, and product orchestration.
- Templates, controllers, dashboards, APIs, semantic views, and AI may select and present facts; they may not recalculate them.
- PostgreSQL remains canonical durable operational state.
- Object storage remains provider-portable and application-encrypted.
- The current private-beta UI remains server-rendered FastAPI/Jinja2 with bundled CSS and minimal bundled JavaScript until an active architecture decision changes it.
- No external fonts, CDNs, analytics scripts, or runtime assets.
- Arabic and English state, action, fact, caveat, refusal, and evidence coverage must remain equal.
- Operational and product telemetry must remain content-free.
- No customer raw rows, source column values, unapproved personal data, filenames, secrets, **opaque owner or session identifiers**, or storage paths may be sent to an AI provider. The qualifier is load-bearing: `RRA-005` requires `NarrativeAdapter` to send approved aggregate facts, safe labels, caveats, language instructions, and **citation identifiers**, and to validate the response against those supplied fact IDs. A blanket ban on identifiers would make grounded, cited provider output impossible.
- One Alembic head must be preserved.
- Required handoff gates are `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`, relevant integration tests, and the required server-side CodeScene gate.

---

## 3. Canonical architecture

### 3.1 Runtime shape

The default architecture remains one deployable Khepri image with separate process roles:

```text
Browser / API consumer
        |
        v
Khepri Web role
        |
        +--------------------+
        |                    |
        v                    v
PostgreSQL             Encrypted object storage
        ^                    ^
        |                    |
Khepri Worker role ----------+
```

No Kubernetes, Kafka, Redis, RabbitMQ, or separate frontend runtime is introduced without a measured requirement and active authority.

### 3.2 Analytical layers

```text
Source upload / future connector
        |
        v
Semantic admission
- source contract
- event kind/status
- identity/grain
- currency/measure basis
- coverage manifest
        |
        v
Governed fact and evidence graph
- population-certified bases
- facts and series
- refusals and caveats
- versions and citations
- reconciliation
        |
        +-------------------------+
        |                         |
        v                         v
Curated semantic views       Trust/catalog surfaces
        |                         |
        +------------+------------+
                     v
Customer decision experience
- report
- workspace/history
- compare
- executive overview
- guided exploration
- watchlists
- Ask Khepri
                     |
                     v
Read APIs / embeds / optional statistical evidence
```

### 3.3 Canonical product object graph

```text
Organization
  |
  +-- Workspace
        |
        +-- DatasetVersion
        |     - input digest
        |     - source contract
        |     - mapping version
        |     - coverage manifest
        |
        +-- AnalysisRun
        |     - admitted semantic state
        |     - fact package
        |     - report bundle
        |     - evidence/refusals/caveats
        |
        +-- ComparisonRun
        +-- SavedView / SavedAnswer
        +-- Watchlist
        +-- Activity / deletion evidence

Global governed registries
  +-- MetricDefinition
  +-- PopulationDefinition
  +-- SemanticViewDefinition
  +-- Reason/Caveat vocabulary
  +-- Formula and contract versions
```

No duplicate writable representation of a metric, membership, authorization rule, or calculation is permitted.

---

## 4. Product surfaces and personas

Khepri evolves as one product with role-scoped surfaces, not three separate applications.

### 4.1 Customer Decision UI

Primary users: pharmacy owner, branch manager, commercial manager, finance manager.

**Primary navigation, reconciled with `KHEPRI_PRODUCT_UX_BLUEPRINT.md` §8:**

```text
Overview
Data
Analyses
Team
```

`Settings` enters primary navigation only in the slice that ships it; it is not owned by any current program. Everything else below is reached contextually rather than through its own primary destination, per blueprint §8 and §20 items 1/2/4/19/20:

```text
Compare              — an action from Analyses / Analysis detail (G4/C1), not a destination
Branches              \
Products & Categories  |  decision-workspace modules inside Analysis detail / D1, not primary nav
Basket & Concentration/
Reports               — discovered from Analysis detail; no separate Reports index (W1-05)
Metrics               — contextual quality/evidence surface (T1); a dedicated destination needs
                         a later contract and demonstrated need
Watchlists            — reached from an analysis/metric it monitors (G8/MON1/S2), post-M4
```

### 4.2 Analyst / Operator Studio

Primary users: Khepri operator, implementation analyst, support engineer.

```text
Semantic admission
Mapping review
Coverage and identity checks
Metric availability
Golden-fixture verification
Analysis and report verification
Dataset/analysis version diff
```

### 4.3 Governance / Operations Console

Primary users: maintainers and operational reviewers.

```text
Semantic catalog
Lineage
Validation findings
Jobs and retries
Runtime health
Metric/refusal usage
Model and formula versions
Artifact publication
Performance and cost
```

These are permissions and route groups inside the current architecture. A separate SPA or service is not implied.

---

## 5. Milestones and exit gates

| Milestone | Product state | Required exit gate |
|---|---|---|
| **M0** | Secure private-beta baseline | Existing analysis journey, governed RRA reports, and runtime baseline on `main` |
| **M1** | Commercial identity and authorization spine | Membership, sessions, invitations, canonical authorization, and commercial RRA bridge merged and concurrency-safe |
| **M2** | Calculation-validated design-partner alpha | CAL1 complete; shell and approved browser/assisted auth work; analysis quality and evidence are visible; activation telemetry exists; full journey passes in production-like local staging and an owner-approved non-production hosted environment before external use. **Two clauses are unmet by owner decision, and `KHEPRI-DEC-031` records both rather than waiving them silently.** *Activation telemetry* is not merely unbuilt: `R8-08` conflicts with active `KHEPRI-DEC-015`, which forbids product-analytics use of retained commercial identity data, and with `RRA-010`'s and `RCA-003`'s exclusions of new telemetry events — it needs an owner-authored amendment, not an implementation slice. *The hosted environment* is deferred: `KHEPRI-DEC-030`'s provisioning authority stays active and unexercised. The staging clause therefore **splits** — its local half is met by `CAL1-14`'s merged evidence (`#330`, `f320c17`), so `M2` is reachable in a **local-only form**: internal rehearsal, no external participant. "Before external use" is the operative bound; the hosted half governs again the moment anyone outside the project is involved. **`M2` is REACHED in that local-only form, with those two clauses unmet by owner decision rather than met.** All four `KHEPRI-DEC-031` §7 conditions hold: (1) `RRA-011`'s catalog and evidence surfaces merged through `#343` and pass `T1-08`'s parity — the Exclusion question `#345` raised is answered by `KHEPRI-DEC-032`; (2) `CAL1` complete, its two `P2`s still non-blocking; (3) no widening of `RRA-010` or `RCA-002`; (4) the full journey re-measured on `d355d12` after `#343` changed `report_api.py` and both wiring modules — two runs, zero failures, both languages, published figures equal to the independently derived oracle. Condition 4's evidence is `docs/superpowers/plans/2026-09-01-m2-condition-4-delivery-rerun-evidence.md`. **This records an internal rehearsal only. It authorizes no external participant**, which needs the hosted environment, and no activation telemetry, which needs an owner-authored amendment to `KHEPRI-DEC-015` |
| **M3** | Durable trust workspace beta | Active retention/workspace authority; multiple dataset versions and analyses retained; history, report reopen, deletion, evidence, and metric catalog work |
| **M4** | Sellable decision workspace | Governed multi-period comparison, curated semantic views, executive overview, branch/product/basket/concentration modules, evidence drawer, and deterministic guided drill-down work |
| **M5** | Paid self-serve candidate | Successor commercial identity authority replacing the provisional Clerk admission; public or assisted onboarding under active authority; plans, billing, entitlements, quotas, usage, invoices, and supportable operations work |
| **M6** | Multi-tenant and distribution growth | Agency portfolios, deterministic watchlists, recurring delivery, selected governed connectors, and optional read-only embedding/API distribution work |
| **M7** | Evidence-backed intelligence | Ask Khepri passes grounding, refusal, privacy, bilingual, and evidence evaluations; optional Seshat statistical evidence may ship only under its own successor authority |
| **M8** | Enterprise GA | Independent security review, restore/deletion exercises, capacity evidence, SSO/SCIM roadmap, release controls, incident/support procedures, semantic operations, and accurate customer documentation are complete |

M4 remains the first broadly sellable analytics milestone. M2 supports controlled design partners; M3 creates repeat use; M4 creates recurring decision value.

---

## 6. Master dependency graph

```text
MERGED COMMERCIAL SPINE
R0 -> R1 -> R2/R3 -> R6 -> R7 -> R8 shell base

CURRENT CRITICAL PROGRAM
CAL1 Deterministic calculation correction  [MERGED: #330 f320c17, #332 f7bf2d3]
  |
  +--> T1 Trust foundation and metric catalog minimum
  |      [authority active: RRA-011 -- the next actionable work]
  |
  +--> R8-08 Activation telemetry  [AUTHORITY-BLOCKED: conflicts with active
  |                                 KHEPRI-DEC-015; needs an owner-authored
  |                                 amendment, not a slice. KHEPRI-DEC-031 §5]
  |
  +--> approved browser/assisted identity handoff if required
  |
  +--> OPS1 hosted non-production readiness
  |      [DEFERRED past M2 by KHEPRI-DEC-031 §4 -- authority active, unexercised]
  |
  M2 CALCULATION-VALIDATED DESIGN-PARTNER ALPHA
     [reachable in a LOCAL-ONLY form: internal rehearsal, no external
      participant. The telemetry and hosted branches above stay unmet]

M2
  |
  +--> G2 Retention decision
  +--> G3 Workspace/history specification
           |
           v
          W1 Durable workspace and history
           |
           +--> T1 full catalog/lineage
           |
           M3 DURABLE TRUST WORKSPACE BETA
           |
           +--> G4 RCA/RRA comparison authority
                 |
                 v
                C1 Multi-dataset comparison
                 |
                 v
                SV1 Curated semantic views
                 |
                 v
                D1 Executive decision workspace
                 |
                 +--> X1 deterministic guided exploration MVP
                 |
                 M4 SELLABLE DECISION WORKSPACE

After M4, parallel growth tracks:

  G5/ON1 Public onboarding
  G6/B1 Billing/entitlements
  API1 Read APIs and embedding
  ING1 Governed ingestion connectors
  G8/MON1/S2 Watchlists, alerts, and recurring delivery
  G7/A1 Agency tenancy
  OPS2 Semantic operations and performance
  STAT1 Optional Seshat statistical evidence

G5/ON1 + G6/B1 -> M5 PAID SELF-SERVE
G7/A1 + MON1/S2 + selected API1/ING1 -> M6 DISTRIBUTION GROWTH
T1 + SV1 + D1 + G9 + AI1 -> M7 EVIDENCE-BACKED INTELLIGENCE
All product programs + OPS1/OPS2 + E1 -> M8 ENTERPRISE GA
```

---

## 7. Program inventory and ownership

| Program | Primary owner | Purpose |
|---|---|---|
| R0-R8 | Existing RCA/RRA/runtime authorities | Commercial identity, authorization, bridge, and shell |
| **CAL1** | RRA-003/004/008 | Correct deterministic semantics, populations, windows, and publication |
| **T1** | New/extended RRA + RCA presentation authority | Metric definitions, analysis quality, evidence, lineage, bilingual vocabulary |
| **U1** | RCA-002 and presentation authority | Cross-cutting design system and visual QA |
| **OPS1** | Runtime/deployment decisions | Non-production and production-readiness foundation |
| **G2/G3/W1** | New retention and RCA workspace authority | Durable datasets, analyses, reports, history, deletion |
| **G4/C1** | Split RCA/RRA authority | Governed multi-dataset comparison |
| **SV1** | RRA definition + RCA orchestration | Curated no-calculation semantic views |
| **D1** | RCA product surface over RRA facts | Executive dashboard and report workspace |
| **X1** | RCA orchestration over SV1 | Deterministic guided exploration and saved answers |
| **G5/ON1** | New onboarding authority | Public/assisted onboarding and abuse controls |
| **G6/B1** | Billing/entitlement authority | Plans, payments, quotas, usage, invoices |
| **API1** | New API/embed authority | Read-only semantic API and embedded components |
| **ING1** | New ingestion/runtime authority | Selected governed connectors beyond manual upload |
| **G7/A1** | Agency tenancy authority | Agency/client portfolios and delegated access |
| **G8/MON1/S2** | Scheduling/notification authority | Watchlists, deterministic alerts, recurring delivery |
| **STAT1** | Successor cross-repository authority | Optional Seshat-derived statistical evidence |
| **G9/AI1** | AI provider/privacy/product authority | Evidence-backed Ask Khepri |
| **OPS2** | Operations authority | Semantic/query observability, caching, cost and capacity |
| **S1** | RRA hardening | Selective construction-boundary hardening |
| **E1** | Enterprise decisions and operating model | Security, identity, resilience, support, release readiness |

---

# PROGRAM CAL1 — Deterministic calculation correction and validation

## Goal

Implement the active RRA-003/004/008 successor contracts so Khepri publishes a fact only when source semantics, event identity, transaction identity, currency, population, and calendar coverage are proven.

## Release strategy

**Historical as of `#308` (`7088749`) — this strategy was executed, and the publication it
describes is done.** It is kept because the version-per-family rule below still governs, and
because `CAL1-15`'s acceptance is verified against what this section specified.

CAL1 is **not** an exception to the small-slice rule. The publication was delivered as one pull
request containing seven ordered, independently verifiable publication commits. Each commit had
its own RED, GREEN, reconciliation, and compatibility evidence, published exactly one successor,
and added only the compatibility row owned by that successor. `V-mapping` added no row because no
successor package triple was expressible until `V-package`.

**The "only the complete final head may merge" rule applied to that PR and has not governed
since.** Nine PRs merged individually between `7088749` and `aa19ff6`, correcting defects in the
published contracts. Whether the one-PR model governs the remaining `CAL1-11`…`CAL1-15` work is
an open owner question — `#301` left it explicitly proposed and no `KHEPRI-DEC-*` row settles it.
See § Current CAL1 reconciliation.

**The governed successor versions are per family**, so each publication commit creates exactly
one successor and no transitional version:

| Commit | Publishes | Governed by | Tasks that must be inside it |
|---|---|---|---|
| `V-mapping` semantic admission | `rra003.mapping.v3` | `RRA-003` | CAL1-03, CAL1-05a, and CAL1-03g |
| `V-package` package, bases, and window alignment | `rra004.package.v3` | `RRA-004` | CAL1-04 and CAL1-06; no residual field |
| `V-formula` core formulas and refusal rules | `rra004.formula.v2` | `RRA-004` | CAL1-05b, CAL1-07a, CAL1-09a, CAL1-10a |
| `V-comparison` comparison facts | `rra008.comparison.v2` | `RRA-008` | CAL1-07b |
| `V-growth` growth decomposition | `rra008.growth.v2` | `RRA-008` | CAL1-08a and CAL1-08b, including all residual evidence. **Follows `V-comparison`**, not merely `V-formula` |
| `V-basket` basket | `rra008.basket.v2` | `RRA-008` | CAL1-09b |
| `V-concentration` concentration | `rra008.concentration.v2` | `RRA-008` | CAL1-10b, sampling included. **Last of the four families** |

**These labels are deliberately not the design's `C0`-`C4`.** `CAL1-01` must read both this table and the merged design, and reusing `C1`-`C4` for different scopes would make the same label mean two things. `C1` is also this roadmap's comparison program, whose tasks are `C1-01` through `C1-08` — a third meaning the `V-` prefix avoids. The design's phase list and this slice map reconcile as follows:

| Merged design | This roadmap |
|---|---|
| `C0` semantic admission | `V-mapping`, widened to every normalized measure `rra003.mapping.v3` governs |
| `C1` package coverage signatures and period alignment | inside `V-package` |
| `C2` retained reconciliation bases and growth residual assignment | package bases are inside `V-package`; all residual evidence is inside `V-growth` |
| `C3` sale-only complete-coverage basket inputs | `V-basket` |
| `C4` non-null full-set concentration eligibility | `V-concentration` |
| Phase 4 policy-dependent formula corrections | `V-formula`, which precedes the `RRA-008` families |

**Where they differ, the specification governs and this table records why.** The design split
`rra004.package.v3` package work across `C1` and `C2`; `V-package` combines the coverage and
retained-basis work so package v3 publishes complete. The owner ruling, now explicit in `RRA-004`,
places all growth rounding-residual evidence in `V-growth`, not in the persisted package.

The fixed dependency order is mapping -> package -> formula -> comparison -> growth -> basket ->
concentration. It was commit order inside the single publication PR `#308` (`7088749`), not a
sequence of owner merges.

**Four of these versions span more than one task, and the fourth column is the binding part of this table.** A slice is not a task; it is the smallest set of tasks that can publish one governed version complete.

**`V-mapping` covers admission, not only identity.** `RRA-003` states that the version governs "the semantic declarations, event and canonical transaction identities, **normalized measures**, currency, and coverage-manifest confirmation in this specification", and that specification's governed-measures sections define revenue and returns, discounts, cost and gross-profit inputs, and units. Those admission rules are `V-mapping`. What `CAL1-05` contributes beyond them is the `RRA-004` formula rows, which are `V-formula`. Splitting a measure's admission out of `V-mapping` would publish `mapping.v3` incomplete.

**`rra004.formula.v2` is one version over one table.** `RRA-004` §"Core formulas and refusal rules" defines Revenue through Returns, absolute and percentage delta, items per transaction, attach rate for value, the concentration curve point, and top decile and quartile share in a single governed table, and `rra004.formula.v2` "governs the formulas, compatible populations, signs, zero/null/negative behavior, precision, and refusal rules **in this specification**". Those rows are spread across `CAL1-05`, `CAL1-07`, `CAL1-09`, and `CAL1-10`. Publishing `formula.v2` with `CAL1-05` alone would leave it incomplete; deferring it past the `RRA-008` commits would make those families consume an unpublished version. **So `V-formula` contains every `RRA-004` formula change and precedes the four `RRA-008` family commits**, which publish only their own `rra008.*` versions.

**Ordering alone is not sufficient.** PR #292 at `1813682` wired the fail-closed compatibility
gate at both package and family scope before any successor constant moved. Every publication
commit must prove that gate and may add only its owned compatibility row.

Intermediate proposal commits deliberately expose fail-closed refusal states. After `V-mapping`,
the successor mapping has no admitted successor package triple; after `V-formula`, successor
families remain refused until their own commits follow. These review states never govern because
only the complete final PR head may merge.

The gate is an **explicit table of admitted version pairs**, not a comparison: a consumer
publishes only when the pairing it is handed appears in the table and refuses otherwise.

*A "newer than" predicate would be wrong, and stating why prevents it being reintroduced.* These identifiers are independent namespaces — `rra003.mapping.v3`, `rra004.formula.v2` and `rra008.basket.v2` share a numbering convention and nothing else — so their suffixes define no ordering to compare. A one-sided rule also guards one direction only: once a family reached `v2`, "refuse when the formula is newer" would happily stamp a successor family identity onto a package still carrying `rra004.formula.v1`. And it leaves an unrecognised version's handling undefined, where a table refuses it by construction. `RRA-008` frames the contract the same way — its `v2` families consume "the exact `rra003.mapping.v3`, `rra004.package.v3`, and `rra004.formula.v2` changes" — so every pairing outside the table refuses.

Each later commit adds only its owned admitted pair, with governed reason codes and complete
accepted Arabic and English wording. The refusing set is largest after `V-formula` and shrinks
through the family commits; `V-concentration` empties it. A reasoned refusal is required in every
intermediate proposal state. An implementer must not remove or widen the gate to make one commit
publish.

**`V-mapping` needed two surfaces that did not exist, or the slice could not be exercised.** Neither was a mapping rule, so a ledger listing only admission changes would have left them unbuilt. **Both were built and merged in `#292` (`1813682`):**

- **The coverage-manifest ingestion path exists.** The manifest is attested on `POST /api/v1/beta/profile` as an optional `coverage_manifest` field (`coverage_request.CoverageManifestBody`), baked into the content-addressed profile document, and read back at use time through `GET /api/v1/beta/coverage/completeness` (`src/khepri/rra/coverage_api.py`). It rides the profile request rather than its own POST because attaching a manifest to an existing profile would rewrite `profile_digest`, which every already-published package cites. Without this, `rra003.mapping.v3` would ship an identity that can confirm nothing, and every completeness-dependent comparison and growth result would refuse permanently for a reason about the software rather than about the data.
- **The upload journey collects the source contract.** `journey/assets/upload.js`'s `declaration()` builds the contract from fields tagged `data-contract-field`/`data-contract-required`, and `profileRequest()` sends it as `source_contract` (`upload.js:49`). Before this, the page posted `{requested_semantics: []}` alone, so making the contract required would have returned 422 on every web upload and stranded the customer on the upload page.

`CAL1-03` carried both, and its acceptance said so: a real upload can submit a manifest and a contract. **Both halves are now met.** The API accepts an optional `coverage_manifest` on `POST /api/v1/beta/profile` (`#292`, `1813682`), and `#300` (`8acef78`) added the browser surface: `upload.js` collects `[data-manifest-field]` controls and sends `coverage_manifest` only when the customer attests, with `upload.html.j2` carrying the controls and their bilingual wording. A real upload can now submit a manifest and a contract, so a completeness-dependent comparison or growth request from a browser upload no longer refuses merely for want of an attestation. **The exception fields are collected as of `#303` (`a2be74e`).** `upload.html.j2` now carries `closed_days`, `extraction_gap_days` and `partial_terminal_boundary` alongside timezone, covered window, covered days, aggregate scope, event kinds and statuses. The defect this paragraph previously recorded — an operator who knows of a closure, an extraction gap or a partial terminal boundary could not attest it from the journey, so a known gap was recorded as no gap — is closed. (`store_roster` is **not** a gap: `RRA-003` treats it and `aggregate_scope` as alternatives and `coverage.py` refuses a manifest carrying both, so the journey collecting the aggregate scope is the complete choice.) Completing those controls stays inside `V-mapping`, since `rra003.mapping.v3` governs manifest confirmation.

With that surface landed, the first ordered commit of `#308` carried the remaining admission
rules and moved `rra003.mapping.v3`.

**`rra008.concentration.v2` publishes with presentation sampling, which this ledger did not name at all.** `RRA-008` puts it inside the concentration contract — "The full curve remains authoritative. Presentation-only sampling keeps no more than 100 points, including the final 100% point, and carries a bilingual sampling caveat" — and names sampling in that specification's own Verification list, so it is `RRA-008`'s to verify rather than a free presentation choice. No `CAL1` task mentioned it, so following this ledger publishes the concentration identity incomplete and leaves the sampling to change governed behaviour afterwards, under a version already on `main`. That is the defect the `V-package` rule above refuses, and the same-slice rule for caveats settles where it goes: `CAL1-11` is "a final sweep, not the task where surfaces catch up". `CAL1-10b` carries it. The merged mission plan reached this first; the roadmap was the outlier.

**`V-concentration` is last of the four family commits.** `RRA-008` requires growth after
comparison, while the publication sequence additionally places basket before concentration so the
final commit closes every remaining compatibility refusal before the PR is eligible to merge.

**The growth rounding-residual placement is settled.** The owner-confirmed decision is now
formalized in `RRA-004`: growth residuals are wholly `rra008.growth.v2` audit evidence.
`rra004.package.v3` contains package population, basis, and coverage fields only and no residual
field. `V-growth` carries the computation, evidence, refusal, and bilingual wording together.

**`V-growth` follows `V-comparison`.** `RRA-008` states that growth "consumes the exact PoP window selected by period comparison and may not select another", over "the structural coverage compatibility already accepted by comparison" and "comparison's accepted aligned daily measure bases". A `V-growth` commit first would have to consume comparison `v1`'s window or reselect one itself, and the specification forbids both.

**`rra004.package.v3` publishes once, when `V-package` is complete.** It combines `CAL1-04`'s
population and retained-basis work with `CAL1-06`'s coverage signatures and aligned daily bases.
It contains no residual field; `CAL1-08` belongs wholly to the later `V-growth` commit.

The release rules are therefore:

- Governance has already merged separately, at `f865079`.
- **`V-mapping` is the first publication commit.** Each of the seven commits is independently
  verifiable and carries its own RED, GREEN, and reconciliation evidence.
- Each family publishes its single governed successor version once. **No intermediate or transitional package, mapping, or formula version is published on `main`**, and no extra version is invented to accommodate a partial implementation.
- A refusal reason or caveat, its governed code, accepted Arabic and English customer prose, audit representation, **bundle, narrative, chart, and HTML/PDF/Excel propagation**, parity checks, and reconciliation tests ship in **the same slice that introduces it**. `RRA-008` states it directly: "Every later code slice that adds a refusal or caveat must add its complete customer wording in both languages in the same slice under `RRA-009`." No slice reaches GREEN while a result it can publish or refuse lacks that wording or surface representation. **`CAL1-11` is therefore a final sweep, not the task where surfaces catch up** — a slice that leaves its refusal unsurfaced for `CAL1-11` has already broken this rule.
- **The propagation half of that rule governs *result* refusals, and stating the boundary is what keeps the rule enforceable.** A `RefusedResult` refuses one metric inside a produced package and therefore owes bundle, narrative, chart, HTML, PDF, and Excel propagation. A `PackageRefused` occurs before a package exists and instead owes a governed code, accepted Arabic and English response prose, audit representation, and rendering on the review page. PR #292 wired that package-level version-refusal path and the family-level fail-closed seam. Each later family commit still owes full result-refusal propagation so independently answerable facts remain standing.
- A slice does not reach GREEN by weakening a semantic guard to preserve an existing fixture. Fixture migration stages after the RED proofs.
- Current versions stay authoritative until the complete successor PR merges. Historical serialized
  packages remain valid under their recorded versions and are not rewritten in place.
- The validation gate in `CAL1-13` runs against the assembled successor contract, not against any
  single commit. No result is released to a design partner before that gate passes.
- **`CAL1-01` owns the exact slice boundaries.** The table above fixes which version each slice publishes and which tasks must be inside it; the ledger fixes the file-level split and proves that no task contributing to a governed version sits outside that version's slice. A boundary that would publish a version twice, publish it incomplete, or make a later family consume an unlanded version is a stop condition, not a judgement call.

## Tasks

| ID | Task | Depends on | Output / acceptance evidence |
|---|---|---|---|
| CAL1-01 | Create an execution ledger against current `main`; map every RRA-003/004/008 requirement to implementation and test work | active successor specifications | Reviewed ledger; exact allowed/forbidden files per slice; the C0-first slice sequence and its version-publication order |
| CAL1-02 | Add independent RED golden and adversarial fixtures before production changes | CAL1-01 | Expected values derived outside production helpers; tests fail against current defects for the intended reasons |
| CAL1-03 | Implement **every** `V-mapping` semantic admission change `rra003.mapping.v3` governs, taking `CAL1-05a` and `CAL1-03g` with it: normalized event kind/status, source-contract declarations, currency, event and canonical transaction identity, coverage-manifest confirmation, **and the normalized measures — revenue and returns, additive discounts, extended-cost inputs, and units**. **Also the two surfaces that make those admissible at all: the coverage-manifest ingestion path, and the client collection of the source contract** | CAL1-02 | `rra003.mapping.v3` behavior, complete in one slice; ambiguous source semantics refuse affected populations; a real upload can submit a manifest and a contract |
| CAL1-04 | Implement `FactPackage` successor population codes and retained reconciliation bases. **Ships in the `V-package` commit with `CAL1-06`; no residual field exists** | preceding `V-mapping` commit | Package successor carries readable population provenance, basis identities, currency, event/transaction counts, and compatible source bases |
| CAL1-05 | Correct core metrics under governed populations: revenue, units, transactions, AOV, ASP, cost, gross profit/margin, discount, returns. **Split across two slices — see the contribution table below** | per part | No cross-population headline or ratio; exact refusal and surviving-fact behavior |
| CAL1-06 | Implement coverage-aware daily bases and aligned PoP/YoY windows. **Same `V-package` commit as `CAL1-04`** — `RRA-004` puts coverage signatures and aligned daily bases inside `rra004.package.v3` | preceding `V-mapping` commit | No two-day versus twenty-eight-day comparison; missing coverage proof refuses completeness-dependent comparisons |
| CAL1-07 | Correct comparison facts and bilingual incomplete-window behavior. **Split across two slices — see the contribution table below** | per part | Absolute/percentage deltas use the same aligned population; zero/negative base rules preserved |
| CAL1-08 | Correct growth decomposition populations, return exclusion, rounding-residual computation, and audit evidence wholly in `V-growth`; no package residual field exists | preceding `V-comparison` commit | Disjoint revenue/units refuse; price + volume equals the governed revenue change exactly; refusal cause is accurate |
| CAL1-09 | Correct basket populations and dimension eligibility. **Split across two slices — see the contribution table below** | per part | Items/transaction and attach rate use complete sale populations and canonical transaction keys; repeated lines do not inflate attach |
| CAL1-10 | Correct concentration eligibility and full-set behavior. **Split across two slices — see the contribution table below** | per part | Null/unlabelled dimensions do not become products; full-set curve remains independent of display truncation; ceiling convention is pinned |
| CAL1-11 | **Final compatibility sweep only.** Prove no slice deferred a refusal reason, caveat, bilingual wording, or surface representation, and close version compatibility across the assembled contract | CAL1-05 through CAL1-10 | A catalogue-wide proof that every governed refusal and caveat already shipped with its wording and surfaces; no surface recalculates; the successor facts reconcile in both languages |
| CAL1-12 | Add mutation evidence and pharmacy-focused golden fixtures | CAL1-11 | Named mutants for row-vs-transaction, unequal windows, unmatched populations, full-set concentration, sign/currency rules, and publication gating are killed |
| CAL1-13 | Run the calculation validation gate | CAL1-12 | Governance, Ruff, full tests, independent fixtures, report reconciliation, deterministic reruns, version checks, and no skipped required behavior |
| CAL1-14 | Run PostgreSQL/MinIO production-like local staging end to end | CAL1-13 | Upload -> admission -> facts -> worker -> HTML/PDF/Excel -> evidence; restart/retry/recovery and bilingual artifacts verified |
| CAL1-15 | Complete external review of the assembled contract. **The seven-commit publication PR already merged at `#308` (`7088749`)**, so this task is now the review and the verification of its acceptance, not a merge | CAL1-14 | No unresolved P0/P1 finding; CodeScene passes; every family sits on its single governed successor version, and no transitional version was published on `main` — the last two are verified against the merged history rather than achieved here |

## Publication-commit contributions

Several task identifiers contribute formula rows to `V-formula` and family behavior to a later
family commit. The table keeps those contributions explicit without assigning any residual work
to `V-package`.

| Part | Work | Slice | Depends on |
|---|---|---|---|
| CAL1-05a | Normalized-measure admission for revenue, returns, discounts, extended cost, and units | `V-mapping` | CAL1-02 |
| CAL1-03g | Prove the already-wired fail-closed compatibility gate when mapping publishes; `V-mapping` adds no row because no successor package triple exists yet | `V-mapping` | CAL1-02 |
| CAL1-05b | The `RRA-004` core-metric formula and refusal rows | `V-formula` | preceding `V-package` commit |
| CAL1-07a | Absolute and percentage delta formula and refusal rows | `V-formula` | preceding `V-package` commit |
| CAL1-07b | Comparison facts and bilingual incomplete-window behavior | `V-comparison` | preceding `V-formula` commit |
| CAL1-08a | Growth rounding-residual computation and audit evidence; no package field | `V-growth` | preceding `V-comparison` commit |
| CAL1-08b | Growth decomposition populations, return exclusion, and the growth formula | `V-growth` | preceding `V-comparison` commit |
| CAL1-09a | Items-per-transaction and attach-rate formula and refusal rows | `V-formula` | preceding `V-package` commit |
| CAL1-09b | Basket populations and dimension eligibility | `V-basket` | preceding `V-growth` commit |
| CAL1-10a | Concentration curve-point and top decile/quartile formula and refusal rows | `V-formula` | preceding `V-package` commit |
| CAL1-10b | Concentration eligibility and full-set behavior, **including presentation-only curve sampling and its bilingual caveat** | `V-concentration` | preceding `V-basket` commit |

**`CAL1-08a` and `CAL1-08b` both sit in `V-growth`, and are retained as separate identifiers only because the execution ledger and this roadmap cite them by name.** The split once resolved an apparent cycle, in which the residual appeared to belong to `V-package` while its computation needed comparison's window. `RRA-004` no longer authorizes a package residual field, so the cycle is gone and both parts publish in one commit.

`CAL1-03` takes `CAL1-05a` **and `CAL1-03g`** with it. `CAL1-04` and `CAL1-06`
form `V-package`; both `CAL1-08` parts form `V-growth`. Every part is a prerequisite of its own
publication commit, never a consumer of it.

## Stop conditions

Stop and return to governance if implementation requires:

- a new business meaning not present in active RRA-003/004/008;
- a new intermediate package/formula version;
- a customer-defined formula;
- currency conversion;
- fractional quantity support;
- forecasting;
- a generic normalization engine;
- a direct Seshat dependency.

## Exit gate

CAL1 is complete only when ordinary imperfect pharmacy exports either produce correct population-certified facts or refuse the affected metric with a precise bilingual reason. A clean-data pass alone is insufficient.

---

# PROGRAM T1 — Trust foundation, semantic catalog, and evidence UX

## Goal

Expose the meaning, availability, population, version, provenance, caveats, and evidence of every customer-visible metric without creating a second calculation source.

## Governance prerequisite — **satisfied for the M2 minimum by `RRA-011`**

Before T1 product code, a bounded contract had to allocate `MetricDefinition` ownership, the
analysis-quality summary vocabulary, evidence and lineage surfaces, Arabic/English labels,
descriptions, synonyms and unsupported interpretations, content-free trust telemetry, and the rule
that definitions are generated from or validated against active governed contracts.

Active `RRA-011` allocates all of those **except two**, and the exceptions are deliberate:

- **Lineage surfaces** are excluded from `RRA-011` and belong to `T1-06`, which this section already
  permits to complete during early `M3`.
- **Content-free trust telemetry** is excluded and remains **blocked**, not merely unallocated.
  `T1-07` hits the same active `KHEPRI-DEC-015` prohibition as `R8-08` — see `KHEPRI-DEC-031` §5 —
  and needs an owner-authored amendment before any slice for it exists. `RRA-011` authorizes no
  exception to it.

`RRA-011` is therefore the governing authority for `T1-01` through `T1-05` and `T1-08`. Its central
requirement is the one this program exists to honour: the catalog is **derived** from the governed
constants that already declare each code, never retyped beside them, and a slice under it must
*reduce* the repository's count of hand-maintained code lists rather than add the fourth.

## Tasks

| ID | Task | Depends on | Parallel | Output |
|---|---|---|---|---|
| T1-01 | Define `MetricDefinition`, `PopulationDefinition`, and reason/caveat registry contracts | CAL1 contract stable | U1 design | Versioned read-only definitions; no formula implementation |
| T1-02 | Generate or validate the registry from governed RRA sources | T1-01, CAL1 merged | no | No hand-maintained parallel metric truth |
| T1-03 | Add bilingual vocabulary and safe synonyms | T1-01 | U1 | Arabic/English names, descriptions, supported and explicitly unsupported interpretations |
| T1-04 | Build `AnalysisQualitySummary`, **and the underlying pre-analysis capability-availability contract an Analysis Impact Preview would read from** — availability only, never a confidence score or invented certainty. **Journey placement of that preview as a new pre-analysis step is a separate, currently unauthorized concern** — see the Analysis Impact Preview note below | T1-02 | T1-03 | Counts and lists of verified, caveated, refused, unavailable, and unsupported results; pre-analysis capability-availability contract |
| T1-05 | Build metric detail and evidence routes. **Two of the outputs below are not derivable from what governed records carry, and `RRA-011` narrows them rather than inventing them** — see its Requirements | T1-02 | U1 evidence drawer | Definition, formula version, inputs, coverage, filters, citations, reconciliation, and caveats. **Population is package-level, not per figure**: a `Fact` carries no population or basis identifier while a package retains several bases, so the catalog reports what the package reconciled against and never selects one for a figure. **Refusal alternatives are prose, not fields**: a `RefusedResult` carries a metric and a reason only, and the remedy exists inside `RRA-009`'s accepted wording, which the catalog surfaces rather than parses. Recording either as data is an `RRA-004` change |
| T1-06 | Build source-to-surface lineage, **with its own parity and fail-closed tests in the same slice** | T1-02, CAL1 evidence bases | T1-05 | Source semantic -> basis -> fact -> claim/chart/report lineage |
| T1-07 | Add content-free trust telemetry, **with its own content-free and fail-closed tests in the same slice**. **AUTHORITY-BLOCKED on the same active `KHEPRI-DEC-015` prohibition as `R8-08`** — see `KHEPRI-DEC-031` §5. Excluded from `RRA-011`, which authorizes no exception to it | **an owner-authored amendment to `KHEPRI-DEC-015`**, T1-04/T1-05 | R8-08 | Evidence opens, refusal views, mapping review, quality-summary use; never customer content |
| T1-08 | Add parity, fail-closed, and no-duplicate-truth tests over the customer-visible metric, definition, quality, and evidence surfaces | T1-01 through T1-05 | no | Unknown metric/reason/version refuses; every displayed figure has one definition and evidence path |

## M2 minimum

M2 requires T1-01 through T1-05 and T1-08. Full lineage and trust telemetry may finish during early M3 if they do not weaken the design-partner evidence surface.

**That is why `T1-08` depends on `T1-01` through `T1-05`, not on "all above".** A gate that required every task in the program could not be reached while the same paragraph declares two of those tasks deferrable — M2 would either admit a design partner without its parity and fail-closed evidence, or stall on work it just called optional. `T1-08` therefore covers the surfaces M2 actually ships, and `T1-06` and `T1-07` carry their own tests in their own slices, per the same-slice rule `CAL1` follows.

**Analysis Impact Preview journey placement — AUTHORITY-BLOCKED, not `T1-04`'s to build.** `T1-04`
owns only the underlying pre-analysis capability-availability contract (what data the availability
vocabulary applies to). Rendering that contract as a new pre-analysis step inside the `/beta` journey
is a different concern with the same shape as Fix & Continue (§R8 COMPLETION above): active `RRA-010`
governs presentation-only changes to the existing journey and explicitly excludes "a new workflow
state, step, or journey phase." An Impact Preview step does not exist in the current journey, so
adding one is a new journey phase, not a presentation change to an existing one. This needs an active
RRA specification naming that phase before any implementation task exists for it; `T1-04`'s contract
can be built and consumed elsewhere (for example the review/pre-check step, if that step's existing
authority already covers it) while the dedicated preview step itself waits on that authority.

---

# CROSS-CUTTING TRACK U1 — Design system and bilingual data experience

## Goal

Build a coherent, accessible, server-rendered decision experience without introducing a second frontend architecture.

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| U1-01 | Preserve and document the merged primitive tokens and shell component layer | current R8 assets | Current visual foundation remains the source of truth |
| U1-02 | Add governed data-display primitives | T1 contracts | KPI card, status badge, quality summary, refusal panel, evidence link, version label, coverage indicator |
| U1-03 | Define a no-calculation chart grammar | CAL1/T1 | Approved chart types, axes, units, missing/refused states, print/export behavior |
| U1-04 | Build the evidence drawer and metric-detail layout | T1-05 | Reusable desktop/mobile component with RTL/LTR parity |
| U1-05 | Build global navigation and filter-bar patterns by milestone | stable route contracts | Organization, workspace, period, language, and visible applied filters |
| U1-06 | Add responsive, keyboard, focus, screen-reader, bidi, and minimum-target evidence | every new surface | Accessibility and RTL/LTR parity gates |
| U1-07 | Add visual-regression and surface-inventory guards | U1-02 through U1-06 | New surface cannot ship unmeasured or without refusal/loading/empty states |

## Design rules

- A page has one primary decision purpose.
- Executive pages target four to six headline KPIs and roughly five to eight meaningful visuals, not a dense wall of widgets.
- Every chart/KPI exposes evidence and applied filters.
- No fake dashboard, fake history, or inactive enterprise controls.
- Mobile prioritizes narrative, KPI status, and evidence over dense model-building controls.

---

# PROGRAM R5 — Account recovery, deferred under Clerk credential ownership

`R5` is the one pre-`CAL1` program that is neither merged nor closed, and its identifiers are cited by two active artifacts — `KHEPRI-DEC-025` (`R3-11`, `R5-02`…`R5-06`) and `RCA-002` (`R5-02`, `R5-04`). They are preserved here so those citations resolve at this path. The full `R5-01` design record stays in the archived roadmap.

| ID | Task | Disposition under Clerk credential ownership |
|---|---|---|
| R5-01 | Specify recovery lifecycle, delivery abstraction, expiry, and uniform initiation response | MERGED |
| R5-02 | Add recovery secret domain and persistence | DEFER — no Khepri recovery-secret domain, table, or migration while Clerk owns the credential |
| R5-03 | Implement uniform recovery initiation for existing and unknown accounts | DEFER — Clerk owns initiation, delivery, and anti-enumeration behavior |
| R5-04 | Implement one-use credential replacement | DEFER — Clerk owns one-use credential replacement |
| R5-05 | Revoke every existing session in the same successful recovery transaction | REFRAME, **MERGED and composed** — Khepri revalidates account state, revokes every Khepri session, and records content-free security evidence after provider recovery. Merged at `15a8175` (`#240`); the composition gap that audit found was closed at `1e3b63c` (`#242`) under `KHEPRI-DEC-025` §4 — `build_recovery_security_service` in `runtime/wiring.py` constructs the service over the real store, and the sweeper is the fifth `RetentionPasses` entry at the governed twelve-month horizon |
| R5-06 | Add replay, expiry, concurrent use, and logging tests | REFRAME, **MERGED** — proves those local consequences, idempotency, disabled/purged refusal, and identity-link integrity rather than reproducing Clerk recovery internals |

The Clerk credential change and the Khepri consequence cannot share the transaction `R5-01` designed for local credentials. `KHEPRI-DEC-025` §1 accepts that cross-system residual for non-paying private beta only and keeps it open for commercial admission — so **`R5` reopens at M5 with `G6-00`, not before**, and reopening requires a credential-ownership decision rather than an engineering one.

**Nothing in `R5` is outstanding implementation work, and none of it may be planned yet.** Every implementable task is merged or deferred, so the program reads `BLOCKED`: `R5-02`/`R5-03`/`R5-04` have no `main` SHA by design and cannot acquire one before `G6-00`'s credential-ownership decision at M5. It is not `MERGED`, because three tasks have no SHA; it is not `READY_FOR_PLAN`, because no design may start. Do not plan a composition slice for `R5-05` either; that work is merged.

---

# PROGRAM R8 COMPLETION — Commercial shell and alpha activation

The merged R8 shell remains the base. The remaining work is:

| ID | Task | Depends on | Output |
|---|---|---|---|
| R8-08 | Govern and implement content-free product activation telemetry. **AUTHORITY-BLOCKED — see `KHEPRI-DEC-031` §5.** Its "approved scope" dependency is not an unwritten specification but a *conflict with an active decision*: `KHEPRI-DEC-015` forbids product-analytics use of retained commercial identity data, and this task's event chain begins at invite and authentication. Active `RRA-010` and `RCA-003` each exclude new telemetry events, and the only active telemetry authority — `RRA-007` under `KHEPRI-DEC-028` — is an eleven-stage operational pipeline vocabulary that structurally cannot carry an activation event. **This resumes by amending `KHEPRI-DEC-015`, not by scheduling an implementation slice**; no specification may authorize an exception without that amendment | **an owner-authored amendment to `KHEPRI-DEC-015`** | Invite/auth -> org selected -> analysis started -> admission reviewed -> report ready -> evidence opened -> report downloaded |
| R8-09 | If a real design partner requires browser sign-in, approve and implement one browser-shaped invite-only provider handoff. **This is `R8-03` reopened**, not new work | amending or successor identity authority over `KHEPRI-DEC-025` §2 | No public signup; identity only; organization and authority remain Khepri-owned |
| R8-10 | Add analysis quality and evidence entry points to the journey and shell | T1 minimum | User understands what was computed, caveated, and refused before downloading |
| R8-11 | Run design-partner browser and mobile acceptance | CAL1, T1, OPS1 staging | Complete bilingual journey under live authorization |

**`R8-09` inherits `R8-03`'s closure, and the closure was an authority boundary rather than a difficulty.** The archived roadmap records `R8-03` CLOSED at 2026-08-22 with no code written, for three separate reasons: recovery is out of scope while Clerk owns credentials (`KHEPRI-DEC-025` §3, `RCA-002` A-5); the invalid-session surface already shipped inside `R8-02`'s shared `unavailable` surface; and the existing handoff takes a Bearer credential in an `Authorization` header plus a JSON body naming an organization, which an HTML form cannot send and which presumes an organization the user has not yet chosen.

So `R8-09` does not begin with engineering. `KHEPRI-DEC-025` §2 authorizes **"One external-authentication route"**, and its prohibitions include **"No public or post-authentication self-service bootstrap"**. A browser-shaped sign-in is a *second* external-authentication route, so it needs the owner to merge amending or successor authority first. Read the `R8-03` disposition in the archive before planning this task.

`R8-09` is conditional only in timing, not in the M2 outcome: an external design partner must have a supported authentication handoff. Manual developer session creation is not an external-user product flow.

**Fix & Continue — AUTHORITY-BLOCKED, not `R8-10`.** Returning to a mapping/attestation step to correct a customer-correctable pre-check or refusal cause, without losing session progress, is desired M2 product direction but is **not** authorized by any current specification and does not belong to `R8-10`. Active `RRA-010` governs presentation-only changes to the existing journey and explicitly excludes "a new workflow state, step, or journey phase" and any new capability the runtime does not already serve; today the review step only *displays* the confirmed mapping (read-only) and `Restart` deletes the session outright, so an editable return-and-resume path is a new workflow capability, not a presentation fix. This needs an active RRA specification naming that capability before any implementation task exists for it.

---

# CROSS-CUTTING TRACK OPS1 — Hosted target and operational readiness

## Current baseline

The production-like local staging stack is merged: one built Khepri image runs web, worker, and migrations against TLS-enabled PostgreSQL and MinIO. It is valuable evidence but is not cloud provisioning, managed backup, hosted ingress, or capacity evidence.

## Tasks

`OPS1-01` through `OPS1-07` keep the meanings they carry in the archived roadmap, because `KHEPRI-DEC-027` blocked on `OPS1-02` by name and its successor `KHEPRI-DEC-030` continues to gate on that identifier. New work is appended as `OPS1-08` through `OPS1-10`. The table is ordered by dependency, not by identifier.

| ID | Task | Depends on | Parallel | Output |
|---|---|---|---|---|
| OPS1-08 | Maintain the merged production-like local stack and its contract tests | merged | CAL1 | Local staging foundation |
| OPS1-01 | ~~Activate the DigitalOcean FRA1 governance needed for a provisional non-production bootstrap~~ **Done** — `KHEPRI-DEC-028` (runtime target and products), `KHEPRI-DEC-029` (benchmark), `KHEPRI-DEC-030` (provisional bootstrap authority) are active; `KHEPRI-DEC-008`, `KHEPRI-DEC-006`, `KHEPRI-DEC-027` retired | owner decisions | CAL1 | Concrete services, provisional measurement shape, RTO/RPO, secret source, network/egress, backup/PITR, registry, OTLP/log destinations; no final capacity claim |
| OPS1-02 | Provision the provisional non-production environment through CI only | OPS1-01 | late CAL1/T1 | Hosted staging at the provisional shape. **Unblocked for the provisional bootstrap only** by `KHEPRI-DEC-030` §3–4; anything beyond that shape still requires a further owner decision |
| OPS1-03 | Configure managed PostgreSQL, private object storage, secrets, TLS ingress, image registry, and operational telemetry; capture the live PostgreSQL minor and verify Spaces | OPS1-02 | T1/R8 | Provisional environment facts and storage compatibility evidence; certification refuses a live/recorded PostgreSQL minor mismatch |
| OPS1-09 | Run the governed hosted benchmark and reissue `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` against the measured target, without the retired broker fields | OPS1-03, CAL1 | no | Final web/worker/DB sizing and environment evidence; `visibility_timeout_seconds`, `message_retention_seconds`, `receive_wait_seconds`, and `max_receive_count` leave the file per `KHEPRI-DEC-028` |
| OPS1-04 | Run expand/deploy/contract migration exercises, backup/restore, deletion-after-restore, encryption read-back, worker crash/recovery, retry, and dead-letter exercises | OPS1-09 | no | Recovery evidence; expand remains compatible with old roles, contract waits for a later release, and incompatible changes explicitly quiesce affected roles |
| OPS1-05 | Run capacity and soak tests | OPS1-04 | no | Concurrency and sustained-load evidence against the final sizing |
| OPS1-06 | Add content-free alerts, dashboards, runbooks, and break-glass evidence | OPS1-05 | R8-08 | Operability |
| OPS1-07 | Define release, rollback, database migration, and incident procedures | OPS1-06 | no | Alpha/pilot runbook using expand → deploy → contract |
| OPS1-10 | Authorize external private-beta traffic only after M2 gates pass | all M2 dependencies; `KHEPRI-DEC-028` pre-beta demonstrations | no | **An owner-merged beta-authorization artifact defining the client count and the observation period**, which `KHEPRI-DEC-028` requires and which no other task produces, plus the explicit go/no-go record |

## M2 operational gate

No external design partner uses Khepri until hosted non-production, recovery evidence, calculation validation, authentication handoff, and the pilot runbook are complete.

**A go/no-go record is not sufficient to open external traffic.** `KHEPRI-DEC-028` is active and states that "the later beta-authorization artifact must still define the client count and observation period", and it lists what implementation must demonstrate before beta launch: cross-session isolation and consent enforcement; deterministic reconciliation and reruns; raw-row exclusion from narrative requests; Arabic/English fact and caveat parity; accessible RTL web and PDF output; safe Excel output; immediate deletion and seven-day expiry; restart, retry, dead-letter, and orphan recovery; content-free telemetry; and at least 95% complete report bundles within ten minutes for the approved benchmark workload. `OPS1-10` produces that artifact for the owner to merge; it does not substitute for it.

---

# PROGRAM G2/G3 — Durable workspace and retention authority

## Goal

Authorize repeat use without silently changing the retention of uploads, facts, reports, evidence, or backups.

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| G2-01 | Inventory retained data classes and purposes | M2 learnings | Upload, normalized events, mappings, manifests, facts, reports, evidence, telemetry, deletion evidence |
| G2-02 | Decide retention defaults, deletion, organization closure, backup behavior, export, and legal/operational ownership | G2-01 | Owner decisions |
| G2-03 | Activate the durable retail-content retention decision | G2-02 | Active authority |
| G3-01 | Draft the workspace/history specification | G2-01 | RCA proposal |
| G3-02 | Clarify workspace, dataset version, analysis run, comparison run, immutability, visibility, and deletion semantics | G3-01 | Clarification record |
| G3-03 | Define authorization, audit, and evidence rules for every workspace action | G3-02 | Security contract |
| G3-04 | Produce plan, tasks, checklist, migration strategy, and registry proposal | G2-03, G3-03 | Implementation-ready active spec |

---

# PROGRAM W1 — Durable workspace, datasets, analyses, and history

## Goal

Turn a one-time report into a repeat-use organization workspace while preserving isolation, versioning, provenance, and deletion evidence.

## UX reconciliation note

This program's task wording is reconciled with the Integrated Customer Experience Map in
`KHEPRI_PRODUCT_UX_BLUEPRINT.md` §5.1. No new task IDs are added for repeat-use UX: **Remember My
Data** (reusable source/mapping profile), **Draft Safety** (save setup / resume later), **Run
Again / Run New Period**, **Analysis Passport**, and **Methodology Change Notice** are wording
additions to `W1-01`, `W1-04`, and `W1-08` below, not separate programs. Each remains gated on
active `G3` authority exactly as the rest of `W1` is — adding wording does not change readiness.

## Tasks

| ID | Task | Depends on | Parallel | Output |
|---|---|---|---|---|
| W1-01 | Define workspace, dataset version, analysis run, comparison run, retained artifact, **and reusable source/mapping profile** domain contracts. A profile record is descriptive metadata only — reusing it must re-attest against the current source rather than silently skipping semantic admission when the source has materially changed (Article V, fail-closed) | active G3 | U1 IA | Domain model |
| W1-02 | Add persistence and one-head migrations | W1-01 | no migration branch | Schema |
| W1-03 | Extend encrypted object namespaces and metadata under G2 | W1-01, G2 | W1-02 tests | Storage lifecycle |
| W1-04 | Implement authorized create/read/list/delete/resume operations, **including saved-setup resume (Draft Safety) and re-running a dataset/analysis configuration for a new period or unchanged period (Run Again / Run New Period) where the prior configuration remains compatible** | W1-02, R6 | W1-05 skeleton | Service/API |
| W1-05 | Build the new M3 customer surfaces — Overview, Data, Analyses — and integrate them with the existing shipped Team destination into one four-item primary navigation (Overview, Data, Analyses, Team), reconciled with `KHEPRI_PRODUCT_UX_BLUEPRINT.md` §8/§20. **Team itself is already SHIPPED under active `RCA-002`** (blueprint §6) and is not rebuilt by this task. Reports are discovered from Analysis detail, not a separate index; Metrics and Activity are contextual (§7.5, §8), not primary destinations; "Workspace" stays an internal domain term, not a customer-facing surface label | stable W1 API, U1 | W1-04 | Customer Organization UI (Overview, Data, Analyses) + integrated navigation |
| W1-06 | Preserve immutable provenance and fact/report bindings, **exposed to the customer as a compact Analysis Passport (period, organization/data reference, scope coverage, run timestamp, methodology/version context) with digests and machine identifiers kept behind contextual audit detail** | W1-03/04 | no | Reproducibility evidence |
| W1-07 | Implement immediate deletion, retention sweep, backup-aware lifecycle, and deletion evidence | W1-03, G2 | no | Lifecycle enforcement |
| W1-08 | Add version and availability diff between analyses, **presented to the customer as a Methodology Change Notice when a prior and later analysis differ because governed mapping or formula/family versions changed, with the diff detail reachable rather than implying numeric comparability where it does not hold. Semantic-view version changes are out of scope here** — `SV1` view definitions do not exist until after `C1`, which itself starts only after M3/`W1`, so `W1-08` cannot exercise or test a view-version case; a view-level notice is a later `SV1`/`D1` extension of this same principle, not `W1-08`'s to build | W1-04, T1 | W1-05 | What changed in inputs, mappings, metrics, refusals, and versions |
| W1-09 | Add favorites/pins and recent activity without creating a new calculation | W1-05 | no | Navigation convenience |
| W1-10 | Add cross-org, expired, deleted, partial, corrupt, restore, and concurrent lifecycle tests | W1-04 through W1-09 | no | Security/recovery evidence |
| W1-11 | Add content-free repeat-use telemetry | W1-05, approved scope | no | Second analysis, report reopen, workspace return, deletion completion |

## M3 exit gate

An organization can retain multiple dataset versions and completed analyses, understand each analysis's metric availability and versions, reopen reports, and delete content with correct evidence.

---

# PROGRAM G4/C1 — Governed multi-dataset comparison

## Ownership split

- RCA owns workspace selection, period/dataset selection, authorization, and user flow.
- RRA owns compatibility, comparison facts, calculations, caveats, refusals, and report surfaces.
- UI, SQL read models, and JavaScript never compute comparison values.

## Governance tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| G4-01 | Define comparison use cases and supported period/dataset semantics | M3 | Product scope |
| G4-02 | Activate RRA comparison-fact authority | G4-01 | RRA specification |
| G4-03 | Activate RCA comparison orchestration authority | G4-01 | RCA specification |
| G4-04 | Freeze versioned input/output, compatibility, filter, and evidence contracts | G4-02/03 | Contract baseline |

## Implementation tasks

| ID | Task | Depends on | Parallel | Output |
|---|---|---|---|---|
| C1-01 | Add governed dataset-period semantics | G4-04, W1 | RRA fixtures | Period model |
| C1-02 | Detect incompatible semantics, currency, population, coverage, mapping drift, and versions | C1-01 | no | Fail-closed compatibility contract |
| C1-03 | Build immutable RRA comparison fact package | C1-02 | RCA API after freeze | Comparison facts |
| C1-04 | Build deterministic bilingual comparison narrative with evidence/refusals | C1-03 | renderer | Narrative |
| C1-05 | Add comparison HTML/PDF/Excel surfaces and reconciliation | C1-03 | C1-04 | Deliverables |
| C1-06 | Add authorized comparison orchestration API | C1-01, stable C1-03 | C1-04/05 | API |
| C1-07 | Build Compare flow and results UI | C1-06, U1 | accessibility | Customer flow |
| C1-08 | Add exactness, provenance, cross-org, mixed-version, unsupported-filter, deletion, and rerun tests | all above | no | Evidence |

---

# PROGRAM SV1 — Curated semantic views and governed read models

## Goal

Provide reusable, versioned, no-calculation views over governed facts for dashboards, guided exploration, APIs, and AI.

## Governance principles

- A semantic view selects existing metrics, dimensions, filters, and evidence requirements.
- It cannot define a new formula.
- It cannot accept arbitrary SQL, customer-calculated fields, or hidden filters.
- It propagates refusals and caveats rather than dropping unavailable metrics.
- Every request is organization-scoped through canonical authorization.

## Initial views

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

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| SV1-01 | Activate semantic-view and governed-query authority | C1 contract stable, T1 | Active contract |
| SV1-02 | Define versioned `SemanticViewDefinition` registry | SV1-01 | Metric/dimension/filter/evidence allowlists |
| SV1-03 | Implement filter and dimension compatibility validation | SV1-02 | Unsupported combinations refuse before query |
| SV1-04 | Build organization-scoped read-model/query service | SV1-02/03 | No-calculation read path |
| SV1-05 | Propagate evidence, caveats, refusals, and population metadata | SV1-04 | Trust-preserving response contract |
| SV1-06 | Add published view versions and rollback-safe compatibility | SV1-04 | Stable dashboard/API baseline |
| SV1-07 | Add cross-org, hidden-filter, arithmetic, unsupported-dimension, version, and emptiness tests | all above | Boundary evidence |
| SV1-08 | Establish latency and query-shape baseline | SV1-04 | Evidence before caching/pre-aggregation |

---

# PROGRAM D1 — Executive decision workspace and evidence-backed reports

## Goal

Expose recurring decision value without duplicating calculations outside RRA facts and SV1 views.

## Product surfaces

- Executive Overview
- Period Comparison
- Branch Performance
- Product/Category Performance
- Basket and Concentration
- Exceptions, Caveats, and Refusals
- Recent Analyses and Comparisons
- Navigable Report Workspace
- Metric Detail and Evidence Drawer

## Tasks

| ID | Task | Depends on | Parallel | Output |
|---|---|---|---|---|
| D1-01 | Define information architecture, narrative order, and exact fact/view source map | C1/SV1 stable | U1 | No-calculation UI contract |
| D1-02 | Build executive overview read model from SV1 only | D1-01 | evidence API | Read model |
| D1-03 | Build headline KPIs and change summary | D1-02 | D1-04 | Overview |
| D1-04 | Build branch, product/category, basket, concentration, and exception modules only where governed facts exist | D1-02 | D1-03 | Decision modules |
| D1-05 | Integrate T1 metric detail, evidence, quality, and refusal surfaces | T1, D1-03/04 | no | Evidence experience |
| D1-06 | Refactor the report page into a navigable report workspace | D1-05 | no | Interactive report UX |
| D1-07 | Add visible global period/workspace/dimension filters with no hidden state | SV1, U1 | D1 modules | Filter UX |
| D1-08 | Add print/export/snapshot behavior without recalculation | D1-03 through D1-07 | no | Stable presentation |
| D1-09 | Add performance behavior after SV1 baseline | SV1-08 | OPS2 planning | Targeted cache/read-model behavior only |
| D1-10 | Add Arabic/English parity, RTL, accessibility, mobile, visual regression, and refusal-state tests | all above | no | Quality evidence |
| D1-11 | Add content-free decision-use telemetry | approved scope | no | Evidence opens, compare use, module use, report navigation, return visits |

## M4 exit gate

A design partner can return to a workspace, compare governed periods, view an executive decision page, drill through supported breakdowns, inspect evidence and limitations for every material claim, and download reconciled bilingual reports.

**M4 is explicitly non-paying, and that is a governance boundary rather than a product preference.** `KHEPRI-DEC-025` §5 carries forward `KHEPRI-DEC-024` §9's hard stop unchanged: the provisional Clerk admission "becomes inoperative immediately before accepting consideration from any customer, opening a commercial production service, or losing the current educational access". Clerk is the only authorized identity path, and no successor commercial identity authority is scheduled before M4. So M4 proves the workspace is worth paying for; **taking the money is M5**, and it cannot happen until the successor authority named under `G6` is merged.

---

# PROGRAM X1 — Deterministic guided exploration and saved answers

## Goal

Deliver a question-first experience without arbitrary formulas, SQL, or AI-generated calculations.

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| X1-01 | Define a supported business-question catalog and metric/dimension combinations | M4 facts/views | Curated question contract |
| X1-02 | Add `Explore` actions to KPIs and charts | SV1/D1 | Metric, period, and filter context carried visibly |
| X1-03 | Implement deterministic branch/product/category/period breakdowns | X1-01/02 | Governed answers with evidence |
| X1-04 | Add suggested next questions based on supported contracts, not content inference | X1-01 | Safe guided flow |
| X1-05 | Add Saved Answers and versioned filters | W1, X1-03 | Reopenable decision artifacts |
| X1-06 | Allow approved Saved Answers to be pinned to a workspace overview | X1-05 | Curated personalization, no new formula |
| X1-07 | Add unsupported-combination, hidden-filter, stale-version, deletion, cross-org, and evidence tests | all above | Safety evidence |

X1-01 through X1-03 may be included in the M4 release. Saved Answers and pinning may follow immediately after M4.

---

# PROGRAM G5/ON1 — Public or assisted onboarding

## Goal

Move beyond operator-provisioned design partners only after M4 proves repeat decision value.

## Try Sample Analysis — AUTHORITY-BLOCKED

A pre-authentication "Try Sample Analysis" is desired product direction for first-visit activation,
owned by this program if and when it is authorized — **it is not `ON1-03`**, which is the
*post*-auth guided first analysis. **It does not fall under `KHEPRI-DEC-025` §5's "no public or
post-authentication self-service bootstrap" as written** — that prohibition is scoped to *accounts and
links*, and a sample that creates neither is a different concern; citing it as the blocker would
misidentify the authority this needs. The actual blockers are `RCA-002`'s Exclusions, which exclude
both "public self-serve signup" and "any change to the `RRA` beta journey, its routes, its templates,
or its assets," and active `RRA-010`, which authorizes only presentation changes to the existing
journey and excludes any new route or workflow phase — a public, unauthenticated route into the
analysis engine is neither. `G5-01` must decide whether and how a sample experience is authorized, and
the authorizing artifact must be a new or amended RCA/RRA specification naming that public route, not
merely a `G5` product decision on its own.

## Governance tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| G5-01 | Decide self-serve versus assisted onboarding, verification, organization bootstrap, support boundaries, **and whether a pre-authentication sample/demo experience is authorized under a new or amended RCA/RRA specification** (see the Try Sample Analysis note above — `RCA-002`'s public-self-serve and beta-journey Exclusions and active `RRA-010`'s presentation-only scope are the actual blockers, not `KHEPRI-DEC-025`) | M4 evidence | Product decisions |
| G5-02 | Define signup, verification, first organization, invitation acceptance, and failure behavior | G5-01 | Active specification |
| G5-03 | Decide email, rate limit, anti-abuse, domain, and provider boundaries | G5-01 | Operations decision |

## Implementation tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| ON1-01 | Build approved account verification and signup | active G5 | Auth flow |
| ON1-02 | Build first-organization bootstrap and first-owner guarantee | ON1-01 | Organization creation |
| ON1-03 | Build guided first-analysis onboarding with trust summary (post-authentication) | ON1-02, T1 | Activation flow |
| ON1-04 | Complete team, invitation, role, and membership administration UX | R2/R4/R6 | Admin UX |
| ON1-05 | Add account/organization audit views using approved content-free events | retention authority | Audit UX |
| ON1-06 | Add abuse, throttling, enumeration, replay, accessibility, and recovery-consequence tests | all above | Security evidence |

---

# PROGRAM G6/B1 — Billing, entitlements, quotas, and invoicing

## Goal

Monetize only after M4 demonstrates repeat value.

## Identity precondition

**Billing cannot ship over the provisional Clerk admission.** `KHEPRI-DEC-025` §5 makes that admission inoperative "immediately before accepting consideration from any customer", and it records that every `KHEPRI-DEC-024` §8 commercial gate remains unrecorded, with §7's accepted gaps — including provider-session revocation and the recovery window — accepted **only** for private-beta scope and lifetime. Elapsed time, a successful beta, and the absence of an incident satisfy none of them. `G6-00` is therefore the first task in this program, and `R5`'s deferred credential tasks reopen with it.

## Governance tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| G6-00 | Activate successor commercial identity authority: credential ownership, the `KHEPRI-DEC-024` §8 commercial gates, provider-session revocation, and the recovery window | M4 evidence | Authority to accept consideration; `R5-02`…`R5-06` re-dispositioned |
| G6-01 | Define plans, entitlement vocabulary, billable units, trial/free behavior, and overage policy | M4 evidence | Product catalog |
| G6-02 | Define cancellation, downgrade, payment failure, refunds, invoices, tax responsibility, and retention consequences | G6-01 | Lifecycle rules |
| G6-03 | Select a billing provider behind an adapter and approve data flow | G6-01/02 | Provider decision |
| G6-04 | Activate billing/entitlement specification | G6-00 through G6-03 | Authority |

## Implementation tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| B1-01 | Implement versioned plan and entitlement model | active G6 | Domain |
| B1-02 | Implement content-free idempotent usage metering | B1-01 | Usage ledger |
| B1-03 | Implement canonical entitlement checkpoint separate from authorization | B1-01 | Enforcement |
| B1-04 | Implement billing adapter and idempotent webhook ingestion | B1-01/02/03 | Billing integration |
| B1-05 | Enforce quotas at job, retained-resource, API, and delivery boundaries | B1-02/03 | Quotas |
| B1-06 | Build plan, usage, checkout, payment, invoice, and cancellation UX | B1-04/05 | Billing UI |
| B1-07 | Add replay, out-of-order, downgrade, payment-failure, quota-race, refund, and cross-org tests | all above | Reliability evidence |

---

# PROGRAM API1 — Read-only semantic API and embedded analytics

## Goal

Allow approved partners and products to consume Khepri decisions without bypassing authorization, evidence, or metric governance.

## Preconditions

- M4 and SV1 are stable.
- A new API/embed authority is active.
- Demand is demonstrated; this is not a prerequisite for first sellable value.

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| API1-01 | Define API versioning, tenancy, scopes, rate limits, embed identity, allowed views, and deprecation policy | M4/SV1 | Active contract |
| API1-02 | Add read-only metric, fact, evidence, report, and semantic-view endpoints | API1-01 | Versioned API |
| API1-03 | Add short-lived signed organization-scoped embed sessions | API1-01, R6 | Embed boundary |
| API1-04 | Add KPI, chart, report, evidence, and Ask Khepri embed components as separately authorized | API1-02/03 | Embedding |
| API1-05 | Add request idempotency where applicable, rate limits, content-free telemetry, and audit | API1-02 | Operations |
| API1-06 | Add cross-org, scope, replay, expiry, unsupported-view, version, and hidden-action tests | all above | Security evidence |

## Explicit non-goals for first API release

- no SQL endpoint;
- no DAX/XMLA endpoint;
- no customer formulas;
- no write API;
- no generic dashboard builder;
- no hidden provider-hosted state.

---

# PROGRAM ING1 — Governed ingestion connectors

## Goal

Add a small number of reliable ingestion paths after the upload-first product works, without turning Khepri into a general ETL platform.

## First candidate paths

1. authenticated object-storage drop;
2. SFTP pull with pinned host identity;
3. versioned upload API;
4. later, one demand-backed pharmacy/ERP connector.

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| ING1-01 | Define connector credentials, source identity, snapshot, freshness, replay, deletion, and incident boundaries | M4 demand | Active contract |
| ING1-02 | Build provider-neutral connector port and snapshot manifest | ING1-01 | Domain/adapter seam |
| ING1-03 | Implement one low-risk connector | ING1-02 | First connector |
| ING1-04 | Route every snapshot through the same RRA-003 admission path as manual upload | ING1-03 | No second semantics path |
| ING1-05 | Add scheduling or webhooks only under G8 authority | G8, ING1-03 | Automated ingestion |
| ING1-06 | Add replay, duplicate snapshot, partial transfer, rotation, revocation, cross-org, and deletion tests | all above | Reliability evidence |

---

# PROGRAM G7/A1 — Agency tenancy and delegated portfolios

## Goal

Let an agency serve multiple client organizations without creating a second path around organization isolation.

## Required decisions

- agency as organization, portfolio, or distinct tenant type;
- creation/attach/detach/delegation rights;
- client visibility and consent;
- billing allocation;
- branding limits that cannot remove provenance, evidence, or disclosures.

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| G7-01 | Activate agency/delegated-access specification | M5, owner decisions | Authority |
| A1-01 | Implement portfolio and client-association domain | active G7 | Domain |
| A1-02 | Extend canonical authorization with explicit delegated access | A1-01, R6 | Authorization |
| A1-03 | Build portfolio overview and client switcher | A1-02 | UI |
| A1-04 | Implement bounded branding, **the same bounded-branding authority a future Branded Report (organization identity/logo/reporting period on deliverables) would reuse; branding must never remove Khepri provenance, disclosure, evidence, caveats, refusals, or governance-required audit/version information** | G7 | Branding |
| A1-05 | Add exhaustive cross-client, detach, revocation, billing, and nonexistence tests | all above | Isolation evidence |

**Secure Share has no current owner.** Read-only, scoped, revocable, expiring, cross-organization-safe sharing of an analysis/report/result without exposing the source upload is desired direction with no registered authority and no task ID. `API1-03`'s short-lived signed embed sessions are the closest existing mechanism but solve a different problem (partner embedding, not point-to-point sharing). Do not claim current authority for it; a future sharing authority is a precondition for any implementation task.

---

# PROGRAM G8/MON1/S2 — Watchlists, deterministic alerts, and recurring delivery

## Goal

Monitor governed metrics and deliver approved reports without weakening metric versions, authorization, retention, or evidence.

## Governance tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| G8-01 | Define watchlist ownership, metric/version binding, thresholds, comparison windows, time zones, pause/cancel, recipients, and channels | M4/M5 | Product rules |
| G8-02 | Define deterministic alert classes and excluded statistical claims | G8-01 | Alert vocabulary |
| G8-03 | Activate scheduling/delivery/runtime authority | G8-01/02 | Authority |

## Implementation tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| MON1-01 | Add watchlist domain and persistence | active G8 | Watchlists |
| MON1-02 | Implement threshold, percentage-change, missing-data, refused-result, and failed-analysis alerts | MON1-01 | Deterministic monitoring |
| MON1-03 | Build watchlist and alert-history UI | MON1-02 | UX |
| S2-01 | Add schedule domain, persistence, and one-head migration | active G8 | Schedules |
| S2-02 | Add durable scheduler/claim worker with bounded retries | S2-01 | Runtime |
| S2-03 | Add secure delivery adapters and recipient reauthorization — **the outbound half of a Ready Notification** (email/push/scheduled delivery). The in-product ready state itself is the analysis's operational state, already owned by W1/blueprint §7.1/§7.3; this task owns only outbound delivery, and does not duplicate that state in a second notification subsystem | S2-01/02 | Delivery |
| S2-04 | Build schedule and delivery UI | S2-01/03 | UX |
| S2-05 | Add DST, duplicate trigger, stale metric version, revoked recipient, deletion, retry, and audit tests | all above | Reliability evidence |

Anomaly detection, predictive alerts, and causal diagnosis are not included. They require STAT1 or a separately governed RRA family.

---

# PROGRAM STAT1 — Optional Seshat statistical evidence integration

## Goal

Consume statistical evidence Khepri does not calculate, without moving deterministic retail authority or importing Seshat runtime/governance into Khepri.

## Preconditions

- M4 deterministic facts and evidence graph are stable.
- A successor to the retired Khepri/Seshat boundary is active in both repositories.
- Seshat has a reviewed headless facade that does not require a repository checkout/root.
- Contract schemas and fixtures have one canonical owner and version/digest controls.

## Tasks

| ID | Owner | Task | Output |
|---|---|---|---|
| STAT1-01 | both repos | Activate reciprocal boundary decisions with pinned SHAs and rollback | Authority |
| STAT1-02 | Seshat canonical | Publish/commit versioned request/evidence schemas and fixtures | Contract baseline |
| STAT1-03 | Seshat | Build headless facade with policy inputs as evidence, never caller-supplied approval | Engine API |
| STAT1-04 | Khepri | Build pure FactPackage/SemanticView -> AnalysisRequest adapter | Request adapter |
| STAT1-05 | Khepri | Build EvidenceBundle -> governed finding consumer with no arithmetic | Evidence consumer |
| STAT1-06 | both repos | Run one low-risk statistical method end to end | First capability |
| STAT1-07 | Khepri | Add version mismatch, unavailable provider, refusal, and deterministic-report fallback | Fail-closed behavior |
| STAT1-08 | both repos | Add parity fixtures, privacy review, rollback rehearsal, and independent review | Release evidence |

## Prohibitions

- no Khepri import of Seshat CLI, checkout, readiness state, dbt, Dagster, or Power BI runtime;
- no Seshat import of Khepri;
- no duplicate deterministic retail calculation;
- no forecasting consumption until the RRA family exclusion is amended first;
- no customer-visible claim without Khepri evidence/presentation mapping.

STAT1 is not on the critical path to M4 or M5.

---

# PROGRAM G9/AI1 — Ask Khepri, evidence-backed intelligence

## Goal

Allow business questions only through governed facts and semantic views, with evidence for every material claim and refusal for unsupported questions.

## Preconditions

- M4 is stable.
- T1 definitions and SV1 views are versioned.
- G9 provider/model/data-processing/ZDR/retention authority is active.
- No raw customer rows or hidden provider state are required.

## Governance tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| G9-01 | Define supported question classes, answer schema, citations, follow-ups, refusal, and coaching behavior | M4/T1/SV1 | Product spec |
| G9-02 | Select provider/model/data-processing/ZDR/retention and adapter constraints | G9-01 | Provider decision |
| G9-03 | Activate AI assistant specification | G9-01/02 | Authority |

## Implementation tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| AI1-01 | Build read-only question context from SV1 views, T1 definitions, facts, caveats, and citations | active G9 | Context contract |
| AI1-02 | Build provider-neutral adapter and pinned request/response schemas | AI1-01, G9-02 | Adapter |
| AI1-03 | Validate every numeric, categorical, temporal, comparison, and causal claim | AI1-01/02 | Claim validator |
| AI1-04 | Require evidence for every material claim and refuse unsupported questions | AI1-03 | Grounding |
| AI1-05 | Add English/Arabic parity, synonyms, follow-ups, and direction-safe rendering | AI1-04, T1 | Bilingual assistant |
| AI1-06 | Turn user corrections into review proposals, never automatic semantic changes | AI1-05 | Human-in-the-loop coaching |
| AI1-07 | Add adversarial evaluation for unsupported numbers, prompt injection, cross-org leakage, missing evidence, stale versions, causal overclaim, and refusal quality | all above | Evaluation gate |
| AI1-08 | Build Ask Khepri UI with evidence navigation and explicit limitations | AI1-04/05 | Product UX |

## Non-goals for first AI release

- no autonomous actions;
- no writes;
- no customer formulas;
- no forecasting;
- no raw-row retrieval;
- no provider-hosted files/vector stores/threads;
- no answer that cannot be reconstructed from cited governed facts.

---

# CROSS-CUTTING TRACK OPS2 — Semantic operations, performance, and cost

## Goal

Operate the decision platform using measured evidence rather than premature caching or pre-aggregation.

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| OPS2-01 | Define operational metrics for jobs, semantic views, dashboards, APIs, alerts, and AI | M4 | Content-free observability contract |
| OPS2-02 | Build operator pages for job/query status, retries, latency, refusal rates, artifact publication, and version usage | OPS2-01 | Operations console |
| OPS2-03 | Establish per-view/page/API performance budgets | SV1/D1/API1 as applicable | Budgets |
| OPS2-04 | Identify repeated query/read-model patterns from evidence | OPS2-02/03 | Optimization candidates |
| OPS2-05 | Add only targeted persisted read models or cache entries with organization/version keys | OPS2-04 | Measured optimization |
| OPS2-06 | Evaluate a pre-aggregation engine only if targeted approaches fail measured budgets | OPS2-05 | Explicit go/no-go decision |
| OPS2-07 | Add cost, capacity, cache-invalidation, and stale-version alerts and runbooks | OPS2-02 through OPS2-06 | Operability |

A general AtScale/Cube-style aggregate subsystem is not authorized merely because competitors have one.

---

# CROSS-CUTTING TRACK S1 — Selective RRA construction hardening

## Goal

Harden only records that carry a security or integrity invariant a direct store caller could violate.

| ID | Task | Depends on | Output |
|---|---|---|---|
| S1-01 | Inventory and classify RRA records | none | Risk inventory |
| S1-02 | Identify caller-controlled identifiers and security material at store seams; rank `#231`'s missing mutation evidence for the `R7-03` live-authorization guards alongside them | S1-01 | Ranked list |
| S1-03 | Select one bounded family | S1-02 | Approved slice |
| S1-04 | Implement one family with accidental-bypass tests | S1-03 | Bounded PRs |
| S1-05 | Close `#152` only after every classified high-risk record is addressed or explicitly accepted | S1-04 | Closeout |

S1 may run in parallel only when it does not touch active CAL1/C1 hotspots.

---

# PROGRAM E1 — Enterprise GA hardening

## Goal

Make Khepri supportable, recoverable, secure, auditable, and commercially reviewable.

## Tasks

| ID | Task | Depends on | Output |
|---|---|---|---|
| E1-01 | Decide enterprise identity roadmap: MFA baseline, SSO/SAML, SCIM, domain controls, and portability | M5 needs | Identity decision |
| E1-02 | Implement approved enterprise identity controls behind existing auth/authorization | E1-01 | Identity |
| E1-03 | Complete account/org/workspace export, closure, retention, legal hold if required, and deletion workflows | workspace/billing/agency authority | Lifecycle completeness |
| E1-04 | Run independent security/privacy review and close approved findings | feature complete | Security evidence |
| E1-05 | Run load, soak, concurrency, failover, backup/restore, deletion-after-restore, and provider-outage exercises | OPS1/OPS2 | Resilience evidence |
| E1-06 | Define SLA/SLO, on-call, severity, escalation, support, and customer communication | observability stable | Operating model |
| E1-07 | Finalize release channels, migration rehearsal, rollback, feature gates, emergency disablement, and dependency response | E1-05 | Release safety |
| E1-08 | Produce customer-facing security, privacy, architecture, data-flow, retention, subprocessors, and operational documentation | all above | Enterprise documentation |
| E1-09 | Rehearse one enterprise onboarding and one incident end to end | E1-02 through E1-08 | GA readiness |

---

## 8. UI evolution by milestone

### M2 UI

```text
Organization switcher
Team / invitations
New Analysis
Upload -> Review -> Processing -> Report
Analysis Quality Summary
Metric/evidence detail
Artifacts/downloads
Shared unavailable states
```

No dashboard or history is faked.

### M3 UI

Primary: **Overview, Data, Analyses, Team** (W1-05). Reports, Metrics, and Activity are reached
contextually rather than as primary destinations — see W1-05 and blueprint §8.

```text
Overview
  └─ contextual recent activity, where the capability exists (W1-09, §7.5)
Data
Analyses
  └─ Analysis detail: report / evidence / PDF / Excel (no separate Reports index)
       └─ version/availability diff, methodology change notice (W1-08)
Team
Deletion/retention state
```

### M4 UI

```text
Executive Overview
Compare
Branches
Products/Categories
Basket
Concentration
Exceptions/Limitations
Evidence drawer
Navigable report workspace
Deterministic Explore actions
```

### M5-M6 UI

```text
Onboarding
Plans/usage/billing
Watchlists/alerts
Schedules/delivery
Agency portfolio
Integrations
API/embed management
```

### M7 UI

```text
Ask Khepri
Answer evidence
Supported follow-ups
Refusal/limitations
Review-proposed vocabulary coaching
```

---

## 9. Metric card and evidence contract

Every customer-visible KPI card should expose, directly or through one action:

```text
Metric label
Value and unit/currency
Comparison only when compatible
Status: verified / caveated / refused / unavailable
Population
Formula/contract version
Visible filters and period
Evidence action
Caveat/refusal count
```

The evidence surface must expose:

- definition and bilingual labels;
- formula and formula version;
- population code and basis identity;
- event and transaction counts where applicable;
- source semantic roles and source-contract identity;
- currency, precision, and rounding;
- coverage manifest and comparison window;
- applied filters/dimensions;
- reconciliation result;
- caveats/refusals;
- citations and surfaces using the figure.

No UI component may recompute the value it explains.

---

## 10. Product measurement framework

All telemetry is content-free and requires approved scope.

**For `R8-08` and `T1-07`, "approved scope" is a prohibition rather than a gap.** Both are blocked by
**active** governance rather than merely unwritten: `KHEPRI-DEC-015` forbids product-analytics use of
retained commercial identity data and `R8-08`'s event chain begins at invite and authentication;
active `RRA-010` and `RCA-003` each exclude new telemetry events; and the only active telemetry
authority, `RRA-007` under `KHEPRI-DEC-028`, is an eleven-stage *operational pipeline* vocabulary
whose validator rejects any stage outside it, so it structurally cannot carry a product event.

Approving that scope means **amending an active decision**, which is the owner's to author. No
specification may authorize an exception without it, and no task may close a measurement clause by
building an event meanwhile. `KHEPRI-DEC-031` §5 records this.

**Whether the same prohibition reaches `W1-11` and `D1-11` is unresolved and unexamined.** Their
events — second analysis, report reopen, workspace return, compare use — have not been checked
against `KHEPRI-DEC-015`'s subject, which is retained *commercial identity* data specifically. The
question arises for them; this section does not answer it, and their programs must answer it before
scheduling either.

The measurements below are the design of what would be measured once scope exists — for `R8-08` and
`T1-07`, not a backlog awaiting scheduling.

### Activation

- identity handoff succeeded;
- organization selected;
- analysis started;
- upload accepted;
- semantic review completed;
- facts produced;
- report completed;
- evidence opened;
- report downloaded.

### Trust

- quality summary viewed;
- refused result inspected;
- evidence opened;
- mapping correction requested;
- report and displayed facts reconciled.

### Repeat use

- workspace returned to;
- second dataset version created;
- second analysis completed;
- old report reopened;
- comparison run;
- saved answer/watchlist used.

### Decision value

- executive module viewed;
- supported drill-down used;
- evidence followed from a claim;
- report shared/downloaded;
- scheduled digest opened, when governed.

### Operations

- job success/retry/dead-letter/recovery;
- stage and renderer latency;
- view/API latency;
- storage/DB errors;
- refusal categories by code, never by customer content;
- deployed formula/view versions.

Targets are owner/product decisions and should be recorded only after baseline evidence exists.

---

## 11. Parallel work and serialization policy

### Maximum active work

For one owner, keep at most:

- one high-risk calculation/persistence/authorization implementation branch;
- one independent UI/domain implementation branch;
- one docs/governance/planning branch.

### Work that may run in parallel

- late CAL1 implementation and T1/U1 design, but not T1 production code before CAL1 contracts merge;
- OPS1 environment decisions and CAL1 implementation;
- G2/G3 drafting during M2 stabilization;
- W1 UI design and W1 backend contract design;
- C1 RRA facts and RCA orchestration after a frozen contract;
- D1 modules after SV1 read contracts freeze;
- API1/ING1/MON1 design after M4 while billing/onboarding proceeds;
- AI evaluation design after M4 while G9 provider evaluation proceeds.

### Work that must be serialized

- CAL1 successor calculations and another RRA facts/comparison branch;
- two schema/migration branches without a reviewed re-point plan;
- two broad authorization changes;
- W1 retention implementation before G2 authority;
- C1 calculation before G4 contract freeze;
- D1 calculation-like read logic before SV1;
- API/AI implementation before stable T1/SV1 contracts;
- Seshat integration before reciprocal authority and a headless facade;
- billing enforcement before entitlement vocabulary;
- agency access alongside another broad authorization refactor.

---

## 12. Pull-request and release packaging

### Normal rule

One bounded customer or safety outcome per PR, with:

- active authority and exact requirement IDs;
- explicit non-goals;
- RED/negative evidence;
- mutation/adversarial evidence for load-bearing guards;
- migration-head state where relevant;
- focused and full validation;
- CodeScene;
- roadmap/status update only after merge.

### CAL1 has no exception

CAL1 followed the small-slice rule through seven family-shaped, independently verifiable commits
inside one pull request, `#308` (`7088749`). The commits were ordered mapping, package, formula,
comparison, growth, basket, concentration. Each published exactly one successor with its owned
compatibility row and its RED/GREEN/reconciliation evidence — except `V-mapping`, which added
**no** row, because the row admitting `rra003.mapping.v3` is a `(mapping, package, formula)`
triple naming a package version that did not exist until `V-package`.

**The delivery unit was proposed and never formally settled.** `#301` recorded the seven-commits-in-one-pull-request model as a proposal awaiting an owner ruling, in the same way the residual placement was a proposal until its dated decision record confirmed it. No `KHEPRI-DEC-*` row records that ruling. In practice the owner merged `#308` as exactly that PR, and then merged nine further PRs individually — so the model was followed for publication and not for the corrections that followed. Whether it governs the remaining `CAL1-11`…`CAL1-15` work is still the owner's to rule; this roadmap records the practice rather than resolving it.

**This is not the exception section 0.1 rejected.** That exception was a single undivided unit
justified by the claim that the successor families share package and formula identities — false,
because the governed successor versions are per family. Article IV requires small, independently
verifiable *slices*, and names no unit of pull request. Seven commits that each publish one
governed version, carry their own evidence, and can each be reviewed on their own terms are those
slices; keeping them in one pull request is what stops an intermediate successor contract from
reaching `main`, which is the same protection separate merges were reaching for.

### Prohibited combinations

Do not combine:

- governance authority and unrelated product implementation;
- a new frontend architecture with a product feature;
- arbitrary formulas/SQL with semantic views;
- Seshat integration with deterministic correction;
- billing with workspace calculation changes;
- AI integration with dashboard refactoring;
- broad RRA hardening with an active analytical family change.

---

## 13. Definitions of Ready and Done

### Ready for planning

- current `main` and relevant open work are verified;
- authority and missing owner decisions are identified;
- dependencies and collision risks are named.

### Ready for implementation

- active authority exists;
- owner decisions are settled;
- exact outcome, scope, files, RED tests, non-goals, validation, and stop point are approved;
- dependencies are merged or a reviewed stacking strategy exists;
- migration strategy is explicit where relevant.

### Done

- behavior and negative cases pass;
- no unrelated behavior is added;
- facts, populations, evidence, privacy, and bilingual parity are preserved;
- production and test fakes enforce equivalent invariants;
- integration behavior executes rather than skips;
- governance, Ruff, tests, migration gates, CodeScene, and required external review pass;
- owner merges to `main`;
- issue and roadmap status are reconciled to the merged SHA.

---

## 14. Explicit non-goals until separately governed

1. Customer-facing semantic-model editor.
2. Customer-authored formulas or calculated fields.
3. Arbitrary SQL or raw-row query workbench.
4. Drag-and-drop general dashboard builder.
5. Generic chat with uploaded data.
6. Forecasting or trend extrapolation.
7. Automated causal/root-cause claims.
8. Unsupervised anomaly alerts.
9. Universal Power BI/Tableau/DAX/XMLA endpoint.
10. General multi-warehouse modeling.
11. Dynamic per-customer code generation.
12. General pre-aggregation platform before measured need.
13. Separate SPA/Node frontend without an active architecture decision.
14. Kubernetes, Kafka, Redis, or a new broker without measured requirement.
15. Direct Khepri-to-Seshat runtime import or repository checkout dependency.

---

## 15. Roadmap status convention

*This section keeps the number it held in the archived roadmap, because active `KHEPRI-DEC-025` makes `R3-11` satisfiable "subject to §15's rule that `MERGED` requires a `main` SHA". Moving the rule elsewhere would leave that governed reference pointing at unrelated content, and a note in a non-governing roadmap cannot retarget a decision. The later sections are numbered around it.*

Use these statuses only. Inventing one is a review finding — it happened on `#214`, where `MERGED_EXCEPT_R3-11` and `PARTIAL` appeared because the next-actionable-task rule below had not been applied.

- `PROPOSED` — roadmap or specification work exists but is not approved or active.
- `READY_FOR_PLAN` — governing authority exists; design questions remain.
- `READY_FOR_IMPLEMENTATION` — an approved bounded plan and its RED tests exist.
- `IN_IMPLEMENTATION` — one approved branch is implementing the task. A program stays
  `IN_IMPLEMENTATION` while merged work exists on `main` and a governance question gates the next
  branch; the gating question is named in the program's row rather than reverting it to `BLOCKED`,
  which is reserved for programs with no merged implementation.
- `IN_REVIEW` — implementation is complete and under adversarial review.
- `MERGED` — the owner merged to `main`.
- `BLOCKED` — a named dependency or owner decision prevents progress.
- `SUPERSEDED` — a later roadmap or artifact replaces this task.

A program's status is the status of its **next actionable task**. Where design may proceed but implementation cannot, the program is `READY_FOR_PLAN` and the blocking implementation dependency is named in the reason. `BLOCKED` is reserved for programs whose next task — design included — cannot start.

Never mark a task complete because it exists on a branch. Use `MERGED` only with a `main` SHA. A green CI run and a merged pull-request title prove a slice landed, never that its requirements closed.

**The status table in §16 is the one document a merged slice never has to touch, so it is the one that drifts.** Four rows described a stale repository in the archived roadmap because a slice's Definition of Done requires its own artifacts and tests and nothing more. Verify a status claim against the merged commits and the files the slice was supposed to produce before building on it. Fixing a stale row means reading what governs the dependency, not only what the table says about it.

---

## 16. Recommended current status at `d355d12`

*This section keeps the number it held in the archived roadmap, because active `KHEPRI-DEC-023` makes `R7-06`'s definition of done include "flipping §16's `R7` row". Like `§15`, it may not be renumbered without amending the decision that cites it.*

### 16.1 Status table

| Program | Status | Reason / next action |
|---|---|---|
| R0 Roadmap/spec reconciliation | MERGED | Historical program complete |
| R1 Concurrent final-owner safety | MERGED | Concurrency gate cleared by merged fixes |
| R2 Membership lifecycle | MERGED | Program complete |
| R3 Authentication sessions/provider seam | MERGED | Invite-only Clerk path and local session composition merged |
| R4 Invitations | MERGED | Program complete |
| R5 Recovery | BLOCKED | **`BLOCKED`, not `READY_FOR_PLAN`, because §15 reserves `READY_FOR_PLAN` for programs whose design work may start now, and `R5`'s cannot.** `KHEPRI-DEC-025` defers `R5-02`/`R5-03`/`R5-04` while Clerk owns credentials, and the named dependency that reopens them is `G6-00`'s successor credential-ownership decision at M5. The local consequence is **merged and composed** at `1e3b63c` (`#242`) — do not plan another composition slice. `R5-02`…`R5-06` are preserved above because `KHEPRI-DEC-025` and `RCA-002` cite them |
| R6 Canonical authorization | MERGED | Canonical resolver and evidence merged |
| R7 Commercial RRA bridge | MERGED | Commercial analysis bridge, routes, and consent surface merged. **Carries `#231`** — `R7-03`'s live-authorization evidence records no mutation proof that its guards can fail — and part of `#211`. See section 0.2 |
| R8 Commercial shell | READY_FOR_PLAN | **`R8-08` is AUTHORITY-BLOCKED, not merely unscoped** — it conflicts with active `KHEPRI-DEC-015` and resumes only by amending it (`KHEPRI-DEC-031` §5), so it is not R8's next actionable task. `R8-10`'s entry points are actionable once `RRA-011`'s surfaces land, under existing `RRA-010` and `RCA-002` authority. Browser handoff may require successor authority for external partner use; `R8-11` is deferred with the hosted environment |
| **CAL1 Calculation correction** | **MERGED** | **All seven successor versions published at `#308` (`7088749`)** — `mapping.py:22` pins `rra003.mapping.v3`, `facts.py:92-93` pin `rra004.package.v3` and `rra004.formula.v2`, and the four `rra008.*` families pin their `v2` constants. The strict `xfail` on `test_profile_accepts_a_complete_contract_and_stamps_mapping_v3` was removed there, as designed. Nine PRs merged after it correcting defects in the now-governing contracts, then `CAL1-11`'s catalogue-wide compatibility sweep at `9e7a886` (`#328`). **`MERGED` with a `main` SHA, per §15**: every CAL1 task has landed — `CAL1-12` through `CAL1-15` at `#330` (`f320c17`), after `CAL1-11` at `#328` (`9e7a886`). The closure evidence is the CAL1-15 ledger's own standing table, which records `CAL1-12` and `CAL1-15` complete and `CAL1-13`/`CAL1-14` passing; the owner merged that assessment, and `AGENTS.md` makes a merge the approval. **Two P2 findings are carried, not gates** — the same shape as `R7` carrying `#231` and `#211`: defects against landed work rather than unmet acceptance. `CAL1-12` killed five of six named mutants with existing tests and closed the sixth (publication-gating over `versions.py`'s `ADMITTED_PACKAGE_PAIRS`/`ADMITTED_FAMILY_PAIRS`, previously a P1 proof gap, now mutation-verified per table) with two new exact-extent tests, added a pharmacy golden fixture, and filed two P2 findings open: `CAVEAT_CURRENCY_NOT_DECLARED` is unreachable under `rra003.mapping.v3` (needs an `RRA-003` or `RRA-009` ruling), and the Excel container is not byte-identical across regenerations — one of 46 ZIP members, `docProps/core.xml`, carries a `dcterms:created`/`modified` wall-clock stamp (needs an `RRA-006` reading of whether deterministic regeneration governs container bytes or governed content). `CAL1-13`'s validation gate passes — governance and Ruff clean, 3,631 passed/72 skipped/1 xfailed whole-repo, the calculation-contract scope alone (`test_rra00*`, `test_rra_calculation_*`, `test_cal1_*`, `test_bmk001_*`) at 1,832 passed and zero skipped, deterministic across two runs. `CAL1-14`'s staging journey passed with zero failures end to end, bilingual, restart/recovery verified, `package_digest` byte-identical across four runs. `CAL1-15` is complete: its CodeScene clause could not be checked from the authoring session (CodeScene MCP `CONNECTION_CLOSED`, `github` MCP `401`) and was **settled by the required server-side gate on `#330`, which reported pass**. No unresolved P0/P1 finding remains open. Carries `#326` and `#311`; neither blocks. **Carries two P2 follow-ups; neither blocks** — (1) `CAVEAT_CURRENCY_NOT_DECLARED` is unreachable under `rra003.mapping.v3`, awaiting an `RRA-003` admission change or an `RRA-009` withdrawal; and (2) the Excel container is not byte-identical across regenerations, one of 46 ZIP members carrying a `dcterms` wall-clock stamp, awaiting an `RRA-006` reading of whether deterministic regeneration governs container bytes or governed content. Neither publishes a wrong figure. **Next: `T1`** |
| **T1 Trust/catalog** | MERGED | **The `M2` minimum has landed.** Active `RRA-011` allocates the metric, population, and reason catalog, its bilingual vocabulary, and its evidence surfaces, governing `T1-01` through `T1-05` and `T1-08` — and all six merged: `T1-01` through `T1-04` at `#334` (`a91fa63`), `#338` (`4e448ed`) and `#340` (`46b2d56`), then `T1-05` with the `T1-08` parity remainder at `#343` (`bc96a65`). §14's "M2 minimum" is `T1-01`…`T1-05` plus `T1-08`, so the program's next actionable task is outside the `M2` gate. `MERGED` with `main` SHAs per §15. **Carries `#345`'s Exclusion question, answered by `KHEPRI-DEC-032`** — the two package-scoped catalog routes construct a `ReportBundle`, which that decision reads as admissible; it publishes no figure, proven against live responses. `T1-06` lineage is excluded from `RRA-011`, needs its own authority, and may complete during early `M3`; `T1-07` trust telemetry is excluded and **blocked** on the same `KHEPRI-DEC-015` prohibition as `R8-08` (`KHEPRI-DEC-031` §5). Neither is an `M2` gate |
| **LAND1/legal Public surfaces** | MERGED | **Was absent from this table entirely** — three merged programs with no status row, which is the §15 drift this section warns about. The public legal and trust surfaces merged at `#331` (`9161b50`); `#339` (`3f998df`) activated the public-landing authority under `RCA-004`; `LAND1-01`'s public product landing surface merged at `#341` (`ee566b2`), after the `#335` (`80548a5`) design concept. No open task; recorded so a later reader does not re-derive the program from the commit log |
| **U1 Design system** | READY_FOR_IMPLEMENTATION (`U1-02`, `U1-04`) · BLOCKED (rest) | **Active `RRA-012` allocates the governed data-display component layer**, in the same shape `RRA-011` received the catalog: the report and evidence templates, a new component stylesheet under `rra/rendering/`, and one bounded catalog projection into `build_context`. It authorizes **`U1-02` and `U1-04` only**, so those two are `READY_FOR_IMPLEMENTATION` and the rest of the program is not. It is `RRA`, not `RCA`, because the surfaces rendering evidence are `rra/rendering/templates/` — an `RCA` authority over them would contradict `RCA-002`:134 on the day it merged. **The gap it closes:** `RRA-011` merged six catalog routes and no template consumed any of them. **Two boundaries `RRA-012` draws that a slice must respect.** (1) **Journey adoption is not authorized** — `journey/templates/base.html.j2` loads only `/beta/assets/journey.css` and `RRA-010`:88 excludes a new asset filename or allowlist change, so a component stylesheet cannot reach a journey page; that wiring needs an `RRA-010` slice. (2) `rendering/html.py` is open for the FR-096a prepared input **and nothing else** — its wording and colophon stay `RRA-009`'s and `RRA-010`'s. `U1-03` (chart grammar), `U1-05` (navigation and filter bars), `U1-06` (accessibility evidence), and `U1-07` (visual regression) are excluded from `RRA-012` and remain `BLOCKED` for the same reason U1 was: no active specification governs their files. `U1-01` is documentation of what exists and is unaffected |
| **OPS1 Hosted operations** | READY_FOR_PLAN | Local staging exists; environment descriptor, sizing, RTO/RPO, secrets, hosted provisioning, recovery and capacity evidence remain. **`OPS1-01` is done and `OPS1-02` is unblocked** by `KHEPRI-DEC-030` §3–4 for the provisional bootstrap shape — but `KHEPRI-DEC-031` §4 **defers `OPS1-02` through `OPS1-05` and `OPS1-09` past `M2`** by owner decision. Deferred, not blocked: the authority is active and unexercised, so this resumes by scheduling it |
| S1 RRA hardening | READY_FOR_PLAN | Triage only; avoid CAL1 hotspots. Owns `#152` through `S1-05`, and ranks `#231` in `S1-02` |
| G2/G3 Workspace authority | PROPOSED | Needs M2 learnings and retention decisions |
| W1 Workspace/history | BLOCKED | No active G2/G3 authority |
| G4/C1 Comparison | BLOCKED | Depends on W1/M3 and new split authority |
| SV1 Semantic views | BLOCKED | Depends on T1 and stable C1 contracts |
| D1 Decision workspace | BLOCKED | Depends on SV1/C1 |
| X1 Guided exploration | BLOCKED | Depends on M4 semantic views and dashboard |
| G5/ON1 Onboarding | PROPOSED | Begins after M4 proves value |
| G6/B1 Billing | PROPOSED | Begins after M4 and owner pricing decisions |
| API1 Embedding/API | PROPOSED | Demand-backed post-M4 track |
| ING1 Connectors | PROPOSED | Demand-backed post-M4 track |
| G7/A1 Agency | PROPOSED | Depends on M5, billing, and stable authorization |
| G8/MON1/S2 Alerts/delivery | PROPOSED | Depends on history, stable metrics, and scheduling authority |
| STAT1 Seshat evidence | PROPOSED | Optional post-M4; needs reciprocal successor authority |
| G9/AI1 Ask Khepri | PROPOSED | Depends on M4, T1, SV1, and provider/privacy authority |
| OPS2 Semantic operations | PROPOSED | Begins after M4 query/view evidence exists |
| E1 Enterprise GA | PROPOSED | Final hardening over all preceding capabilities |

---

## 17. Immediate execution order from current `main`

This is the no-hesitation queue. Do not begin a later item merely because it is interesting.

### Critical path

1. ~~**CAL1-01/02:** create the execution ledger, fix the slice sequence, add independent RED fixtures.~~ **Done** — `docs/superpowers/plans/2026-08-26-cal1-01-v-mapping-execution-ledger.md`.
2. ~~**Obtain the owner ruling on the delivery unit, then open one CAL1 implementation PR carrying all seven publication commits.**~~ **Superseded by events.** `#308` (`7088749`) merged as exactly that PR — seven ordered publication commits, one constant each. The ruling itself was never recorded: `#301` left the one-PR model explicitly proposed, and no `KHEPRI-DEC-*` row settles it. **The "never merged separately" rule did not hold afterwards**: nine PRs merged individually between `7088749` and `aa19ff6`, correcting defects in the published contracts. Whether that model governs the remaining `CAL1-11`…`CAL1-15` work is an open owner question; this queue records the practice rather than resolving it.
3. ~~**Commits 1-7 — publish the seven successor versions in governed order.**~~ **Done at `#308` (`7088749`)**, in the order this queue specified: `V-mapping`, `V-package`, `V-formula`, `V-comparison`, `V-growth`, `V-basket`, `V-concentration`. Each moved one constant and carried its own compatibility row. The prerequisites this queue tracked as open are also closed — `#303` (`a2be74e`) collected the manifest exception fields, and the strict `xfail` on `test_profile_accepts_a_complete_contract_and_stamps_mapping_v3` was removed in `#308`.
4. ~~**The transaction-date refusal and manifest exception fields.**~~ **Done** — `#303` (`a2be74e`).
5. **Correction work found after publication is not queued here.** Nine PRs through `#325` (`aa19ff6`) closed defects in the now-governing contracts; `#326` and `#311` carry what is deferred. Neither blocks `CAL1-11` or the slices after it.
6. ~~**`CAL1-11` — the final compatibility sweep.**~~ **Done** — `9e7a886` (`#328`). Proved no slice deferred a refusal reason, caveat, bilingual wording, or surface representation, and closed version compatibility across the assembled contract, directly answering the gap the `#325` review round exposed.
7. ~~**`CAL1-12` — mutation and pharmacy golden evidence.**~~ **Done** — `#330` (`f320c17`). It applied all six named mutants to merged source: row-vs-transaction, unequal windows, unmatched populations, and full-set concentration and sign rules were each killed by an existing test; publication gating over `versions.py`'s `ADMITTED_PACKAGE_PAIRS`/`ADMITTED_FAMILY_PAIRS` survived as a real P1 proof gap and is now closed by two new exact-extent tests, mutation-verified per table. A pharmacy golden fixture (`tests/test_cal1_pharmacy_golden.py`, `PHARMACY_ROWS` in `tests/rra_calculation_oracle.py`) now exists, mutation-verified against `facts._sale_only`. **The sign/currency acceptance clause is met, and the distinction is worth stating because it decides whether this slice is complete.** The clause requires the named mutants to be *killed*. The sign mutant is killed. The currency mutant is not a surviving guard — it is an unreachable branch: `facts.py:1143` fires only when the package has no admitted currency *and* still publishes a monetary fact, and the only path to the first (`admission._currency` returning `(None, True)`) sets `monetary_refused`, which nulls every monetary measure before the caveat can attach. Verified empirically. No test can kill a mutant in code no input reaches, so the clause cannot be discharged by test work in this slice, and a test forcing the branch by internal construction would assert a state production cannot produce. Filed as P2 rather than deferred silently: `CAVEAT_CURRENCY_NOT_DECLARED` carries bilingual prose, a wording registration and two narrative branches, so it is a *defined but never attached* catalogue defect. Its fix is an `RRA-003` admission change or an `RRA-009` withdrawal — a family ruling, not evidence — and it publishes no wrong figure meanwhile, because where mixed currency occurs every monetary fact is already refused. **That reading was put to the owner and answered by the merge**: `#330` carried this conditional in its own body and was merged with the slice recorded complete, so the clause is met and the unreachable caveat is a carried P2 follow-up rather than an open gate. It blocks nothing below it. Ledger: `docs/superpowers/plans/2026-08-29-cal1-12-mutation-and-pharmacy-evidence-ledger.md`.
8. ~~**`CAL1-13/14/15` — the gate, staging, and external review.**~~ **Done** — `#330` (`f320c17`), which also carried `CAL1-12`. `CAL1-13`'s validation gate passes: governance and Ruff clean, 3,631 passed/72 skipped/1 xfailed whole-repo (the 72 skips are all outside the calculation contract — Postgres-only and WSL-loopback tests — and the calculation-contract scope alone runs 1,832 passed, zero skipped), deterministic across two full reruns. `CAL1-14`'s local staging journey (upload → admission → facts → worker → HTML/PDF/Excel/evidence) passed with zero failures, bilingual artifacts confirmed, containers restarted cleanly between journeys, a job queued with no worker alive was claimed and completed by the next worker (`attempt_count=1`), a first attempt failed against a stopped object store and was **retried after the governed 60s `RETRY_DELAY` to succeed on attempt 2** (`rra_report_job_attempts` records attempt 1 as `retry_scheduled`), and `package_digest` was byte-identical across all four runs. One property is filed rather than closed: the Excel *container* is not byte-identical across regenerations, because `docProps/core.xml` carries a wall-clock stamp — every worksheet and both digests are identical, and whether `RRA-006`'s one-line deterministic-regeneration clause governs container bytes is an owner reading. `CAL1-15`'s acceptance — "every family sits on its single governed successor version, and no transitional version was published on `main`" — is verified against the merged history: the seven versions published at `#308` and `versions.py`'s two tables (three package triples, eight family pairs, both now extent-tested) hold no fourth identity. No unresolved P0/P1 finding remains open. **CodeScene passed on `#330`'s required server-side gate**, which is the authority; it was not checkable from the authoring session (MCP `CONNECTION_CLOSED`, `github` MCP `401`), so it is recorded from the check result. Ledger: `docs/superpowers/plans/2026-08-29-cal1-13-14-15-gate-staging-and-review-evidence.md`.
9. ~~**T1 governance, then `T1-01`…`T1-05` and `T1-08`.**~~ **Done** — active `RRA-011` allocates the metric, population, and reason catalog, its bilingual vocabulary, and its evidence surfaces, and all six tasks merged: `#334` (`a91fa63`), `#338` (`4e448ed`), `#340` (`46b2d56`), and `T1-05` with the `T1-08` parity remainder at `#343` (`bc96a65`). The catalog is *derived* from the governed constants rather than retyped beside them, as `RRA-011` requires. `#345` then raised whether the two package-scoped routes' `ReportBundle` construction is a re-derivation; `KHEPRI-DEC-032` reads it as admissible. `T1-06` lineage needs its own authority and may complete during early `M3`; `T1-07` is blocked with item 10.
10. **`R8-08` — AUTHORITY-BLOCKED, and not this queue's to unblock.** It conflicts with active `KHEPRI-DEC-015`, which forbids product-analytics use of retained commercial identity data, and its event chain begins at invite and authentication. It resumes only by an owner-authored amendment to that decision — not by scheduling an implementation slice — and `T1-07` waits on the same amendment. See `KHEPRI-DEC-031` §5. `R8-09` remains conditional on a design partner requiring browser sign-in, which is external use and deferred with item 11.
11. ~~**OPS1-01**~~ **Done** — `KHEPRI-DEC-028`, `KHEPRI-DEC-029`, and `KHEPRI-DEC-030` are active and `KHEPRI-DEC-027` is retired. **Items 11 through 14 below are deferred past `M2` by `KHEPRI-DEC-031` §4**, which records the owner's decision to stay on the local stack for now. Deferred, not blocked: `OPS1-02` is unblocked for the provisional bootstrap shape and resumes by scheduling it.
12. **OPS1-02, then OPS1-03:** provision the provisional non-production environment through CI, then configure its managed services and capture the live PostgreSQL minor and Spaces compatibility evidence.
13. **OPS1-09:** run the governed hosted benchmark against that measured target and reissue the sizing authority. It cannot precede `OPS1-03`, which produces the target it measures.
14. **OPS1-04 through OPS1-07:** recovery and capacity evidence, observability, and the pilot runbook.
15. ~~**M2 acceptance, in its local-only form.**~~ **Done — `M2` is reached in its local-only form, with its two unmet clauses named.** All four `KHEPRI-DEC-031` §7 conditions hold. Condition 1 was the last open one: `#342` (`b8b3716`) correctly recorded it failing when the catalog had no consumer, `#343` (`bc96a65`) supplied one, and `#345` (`d355d12`) then asked whether those routes re-derive — answered by `KHEPRI-DEC-032`. Condition 4 was re-measured on `d355d12` rather than inherited from `#342`, because `#343` changed `report_api.py` and both wiring modules: two runs, zero failures, both languages, on `rra003.mapping.v3`/`rra004.package.v3`/`rra004.formula.v2`, with published figures equal to the independently derived oracle and every surface byte-identical across runs except the Excel container's known `dcterms` stamp. Evidence: `docs/superpowers/plans/2026-09-01-m2-condition-4-delivery-rerun-evidence.md`. **The rehearsal was internal and authorizes no external participant** — that needs the hosted environment (item 11) and, separately, the amendment item 10 names.
16. **G2/G3:** activate retention and workspace authority.
17. **W1-01 onward:** begin durable workspace/history implementation.

### Parallel-safe work now

*This list was written during CAL1 and its first two entries have since been overtaken by events. Kept
and corrected in place rather than deleted, because a reader arriving from an older note needs to see
what changed.*

- ~~OPS1-01 environment decisions may proceed during CAL1.~~ **Done** — item 11.
- ~~T1/U1 design may proceed during late CAL1 review.~~ **T1 is merged** (item 9). **U1 is `BLOCKED`, and the phrase "U1 design may proceed" is what needs correcting**: no active specification governs the files `U1-02` through `U1-07` would touch. `RRA-011` disclaims the consuming surfaces, `RRA-010` puts `shell.css`/`shell-components.css` outside its scope, and `RCA-002` excludes changes to the journey's templates and assets. That gap is now closed for two of the tasks: **active `RRA-012` allocates the data-display component layer**, making `U1-02` and `U1-04` `READY_FOR_IMPLEMENTATION`. It excludes the chart grammar (`U1-03`), navigation (`U1-05`), accessibility evidence (`U1-06`), and visual-regression (`U1-07`) tasks, which keep the original gap and stay `BLOCKED`. **It also does not authorize component adoption on the journey surface** — the stylesheet cannot reach a journey page without an `RRA-010` asset-wiring slice. `U1-01` — documenting the primitives that already exist — is unaffected.
- G2 data-inventory research may start near CAL1 completion, but retention decisions should use M2 learnings. **`M2` is now reached in its local-only form (item 15), so those learnings exist.**
- S1 triage only may proceed if it does not overlap CAL1 files.

### Do not start now

- W1 persistence;
- C1 comparison;
- D1 dashboard;
- billing;
- agency;
- connectors;
- embedding;
- watchlists;
- Seshat integration;
- Ask Khepri.

---

## 18. Decision rules that prevent hesitation

When choosing the next task, apply these rules in order:

1. **Governance first:** no product code without active authority.
2. **Correctness before convenience:** unresolved calculation or isolation risk beats new UI.
3. **One critical path:** execute the first incomplete item in section 17 unless a named blocker exists.
4. **Design may lead code, not outrun contracts:** UI/UX design can proceed against a frozen interface; implementation waits.
5. **No duplicate truth:** a new surface consumes existing definitions/facts/views or stops.
6. **No speculative platform work:** connectors, embedding, caching, pre-aggregation, AI, and Seshat require demand and prerequisites.
7. **Refuse rather than guess:** unsupported semantics, filters, dimensions, versions, and questions produce explicit refusal.
8. **Measure before optimize:** latency and usage evidence precede cache/pre-aggregation work.
9. **Merge evidence, not intention:** status changes only after owner merge to `main`.
10. **Keep only three active lanes:** one high-risk implementation, one independent UI/domain lane, one governance/docs lane.

If two tasks appear equally valid, choose the one that closes an exit gate for the nearest milestone without creating a second source of truth.

---

## 19. Final sequencing statement

Khepri's complete sequence is:

```text
Correct deterministic meaning and populations
-> expose trust and evidence
-> prove the full alpha journey in hosted non-production
-> retain workspaces and history
-> compare governed periods
-> serve curated semantic views
-> build the executive decision workspace
-> enable deterministic exploration
-> monetize repeat value
-> add selected distribution, connectors, alerts, and agency workflows
-> add grounded AI and optional statistical evidence
-> prove enterprise security, resilience, operations, and support
```

This order preserves Khepri's strongest product claim: every customer-visible result is reproducible, organization-scoped, population-correct, versioned, bilingual, cited, and safe under failure.
