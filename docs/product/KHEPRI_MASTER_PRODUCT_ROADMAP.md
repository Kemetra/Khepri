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
- `#152` and `#211` are the open issues, both carried in section 0.2; `#231` is **closed** — the `R7-03` mutation evidence it asked for is recorded in `tests/test_r703_live_authorization_on_resume.py`;
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
| `#231` | `R7-03` ships live-authorization evidence with no mutation proof that its guards can fail | `R7` | **CLOSED**, and kept here rather than deleted because this section is where the gap was recorded and a reader arriving from it needs the answer. Each of the three named mutants was applied and kills **exactly one** test inside `TestBothLayersRefuseIndependently` — the layer it belongs to — so the two gates are independently evidenced rather than redundant. Measured repo-wide the same mutants kill 12, 5 and 14 tests across 6, 4 and 7 modules, because each guard sits on a chokepoint with several callers; those kills land in other modules, never in the other layer's test, which is why the isolation claim is unaffected. Recorded in the module's §Mutation evidence and in each test's docstring, in `R7-07`'s style. **Two findings beyond the issue**: the membership and scope refusals in `resolve_scope` mask each other on the revocation journey (either alone kills at most one test, both together fail four), because `AuthorizationResolver.resolve` yields `organization_id=None` for a revoked member rather than refusing (`FR-028`); and the fixture helpers were mutated too, each no-op failing five tests, so the suite is not measuring a condition it never creates |
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
| **M3** | Durable trust workspace beta | Active retention/workspace authority; multiple dataset versions and analyses retained; history, report reopen, deletion, evidence, and metric catalog work. **`M3` is MEASURED and reachable in the same local-only form `M2` holds, with one clause open for an owner reading**, on `main` at `c98e946` against the deployed image: six of seven measured clauses pass, in both languages, deterministically across two runs in four separate organizations. Evidence: `docs/superpowers/plans/2026-09-06-m3-acceptance-evidence.md`. **The open clause is `W1-08`'s Methodology Change Notice**: the diff surface is wired and correctly renders nothing when no governed version differs, which is all a single image pinning one version triple can produce — verified on both runs' live pages, not reasoned from source. Whether "history" requires a *demonstrated* methodology diff or is satisfied by the Passport plus a wired diff surface is the owner's reading; `W1-08`'s own tests (`267c50c`, `#377`) are where the changed-version case is proven. **Unlike `M2`, no governed decision decomposes this gate into numbered conditions** — `KHEPRI-DEC-031` §7 did that for `M2` and has no `M3` counterpart — so the ledger measures this sentence's own six clauses and says so. If the owner would rather `M3` rest on numbered conditions, they are the owner's to author; nothing measured would change. The run is local-stack and **authorizes no external participant**, which still needs the hosted environment deferred by `KHEPRI-DEC-031` §4. One finding outside this gate: the Team surface (`RCA-002`/`R8`, not an `M3` clause) raises `500` in the deployed image — `wiring.py:497` passes an `InvitationService` where `shell_api.py:152`'s Protocol requires the store's `invitations_for_organization` |
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

MERGED CRITICAL PATH THROUGH COMPARISON
CAL1 -> T1 minimum -> M2 local-only -> G2/G3 -> W1 -> M3 measured -> G4 -> C1
                                                                  [#412 / #413]

OPEN PARALLEL BRANCHES
R8-08 Activation telemetry  [AUTHORITY-BLOCKED: conflicts with active
                              KHEPRI-DEC-015; needs an owner-authored
                              amendment, not a slice. KHEPRI-DEC-031 §5]
OPS1 hosted non-production  [DEFERRED past M2 by KHEPRI-DEC-031 §4;
                              authority active and unexercised]
Browser/assisted identity handoff remains conditional on external use.

MERGED CRITICAL PATH THROUGH SEMANTIC VIEWS
SV1-01 authority -> SV1-02..SV1-08 -> RCA-007 authority -> composition
[9ec3896 / #418]   [65521a6..9633c6c]  [32a1112 / #427]   [2337cd4 / #437]

CURRENT CRITICAL-PATH FRONTIER
D1-01 Information architecture, narrative order, and fact/view source map
  [ACTIONABLE NOW: its C1/SV1 dependency is merged. Scope definition, not
   code -- the G4-01 precedent. D1-02 onward is AUTHORITY-BLOCKED: no
   active specification governs the D1 product-code files]
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
| G4-02 | Activate RRA comparison-fact authority | G4-01 | RRA specification — **MERGED**: `RRA-008` §Two-population comparison is `active` in `registry.yaml`, and `RRA-006` §Two-population bundle (`#407`) allocates the sibling bundle beside it. The "governing only if the owner merges it" clause is spent: the owner merged both, and `C1-01`–`C1-08` shipped against them |
| G4-03 | Activate RCA comparison orchestration authority | G4-01 | RCA specification — **MERGED**: `RCA-005` §Comparison orchestration (`FR-130`–`FR-133`) is `active` in `registry.yaml`, and its derived-at-read-time decision is what `C1-06` implements and `C1-07` reaches |
| G4-04 | Freeze versioned input/output, compatibility, filter, and evidence contracts | G4-02/03 | Contract baseline — **MERGED**: both §Frozen contracts sections are active, and the freeze has since been *exercised* rather than merely declared — `#408` corrected a slice that had invented a `filter mismatch` cause the frozen set does not contain, and `C1-08` asserts the frozen `incomparable basis` for both filter halves. The filter half is frozen at **identity** rather than an enumeration |

## Implementation tasks

| ID | Task | Depends on | Parallel | Output |
|---|---|---|---|---|
| C1-01 | Add governed dataset-period semantics | G4-04, W1 | RRA fixtures | Period model — **MERGED** `7a1f17f` (`#401`): `analysis/dataset_period.py`, the ordered `VersionPair` plus §Period rule and `D-6` |
| C1-02 | Detect incompatible semantics, currency, population, coverage, mapping drift, and versions | C1-01 | no | Fail-closed compatibility contract — **MERGED** `3890d8b` (`#402`): `analysis/compatibility.py`, `D-1`–`D-5` as one ordered table returning the first cause. **Corrected in `#408`**: it had emitted `filter mismatch`, a cause `RRA-008` §Refusals and caveats does not list; §Frozen contracts assigns differing admitted filters to `incomparable basis`, the currency cause, so the two names are now one cause with one bilingual wording |
| C1-03 | Build immutable RRA comparison fact package | C1-02 | RCA API after freeze | Comparison facts — **MERGED** `f7b9824` (`#404`): `analysis/comparison_package.py`. The carrier question this row opened was answered by precedent rather than invention: `FactComparison` is already a *sibling* of `Fact` rather than a modification of it, so `CrossVersionFact` follows that shape with `PairProvenance` as the composed value — no `Fact` field added, `Fact.inputs` keeping its meaning. Operand order enters identity through `fact_identity(scope=(subject, baseline))`, which hashes `scope` as an ordered list. Review added the invariant that makes it hold: frozen prevents mutation and nothing else, so `__post_init__` recomputes both identifiers and raises `IdentityMismatch`, because `dataclasses.replace` could otherwise carry a stale `fact_id` onto a changed metric or pair |
| C1-04 | Build deterministic bilingual comparison narrative with evidence/refusals | C1-03 | renderer | Narrative — **MERGED** `7bbfed7` (`#405`): `analysis/comparison_narrative.py`, eleven causes × two languages plus the admitted-pair caveat. Causes are **imported** from `compatibility` and `dataset_period` rather than retyped, so coverage is asserted against the set the family actually raises — two language tables compared only to each other both pass when a cause is missing from both. Every string is static: `FR-131` forbids a partial or indicative figure and `FR-133` any figure, delta or version name, so a format placeholder is where a value would eventually be passed |
| C1-05 | Add comparison HTML/PDF/Excel surfaces and reconciliation | C1-03 | C1-04 | Deliverables — **MERGED** (`#408`) under `RRA-006` §Two-population bundle (`#407`): `crossversion_bundle.py` (the sibling bundle and its ordered-pair identity, versioned `rra006.crossversion.bundle.v1`), `crossversion_assembly.py` (admission through `C1-01`/`C1-02`, facts through `C1-03`, wording through `C1-04`, cells through `bundle._renderings`), `crossversion_rules.py` (one predicate per invariant: a delta never without both operands, one chart-less section, derived-record evidence with composite provenance), and `renderable.py` (`RenderableBundle`, the read-only Protocol both bundles satisfy, so `html.py`/`pdf.py`/`excel.py` and `reconcile()` accept either without duplicating a renderer). `ReportBundle` is unchanged in behaviour: `ORDERED_SECTIONS` is byte-identical, the sibling's `crossversion` section is admitted only through `PRESENTATION_SECTIONS`, and the retained union was **not** widened — the `record is None` evidence branch already carried a derived, unretained fact. `CitedEvidence` gained one defaulted `provenance` field emitted only when present, so every report-bundle evidence document is byte-identical. Nothing in `src/` calls it yet; `C1-06` is the production caller. Two things carried forward: the `Fact`-shape vs sibling-type reading of `RRA-008` §Two-population comparison is still the owner's, and `_assert_derived_metric_wording_complete` (cc 16) is the one pre-existing smell left in `wording.py`; and two admitted packages that state **no metric in common** (each gapped in the other's columns) refuse under `incomplete coverage`, whose wording speaks of period coverage — `RRA-008` §Refusals and caveats freezes the cause set and gives each cause one wording, so the closer statement (a cause for *no comparable measure*, or wording that also covers measure coverage) is an owner amendment to that section, recorded here rather than improvised in the slice |
| C1-06 | Add authorized comparison orchestration API | C1-01, stable C1-03 | C1-04/05 | API — **MERGED** (`#409`) under `RCA-005` §Comparison orchestration (`FR-130`–`FR-133`) and §Comparison retention; the first production caller of the C1 chain. `rca/workspace/comparisons.py` (`ComparisonActions.request`: scope resolved from the session through `IsolationService.resolve_scope`, never from the address; three or more ids or a self-pair refuse **before any store read**; either version absent, deleted or out of scope yields the one uniform unavailable outcome, and an out-of-scope baseline never reaches the package loader; exactly one content-free audit event per request on the **existing** `run_completed`/`run_failed` actions with subject `None`, because a comparison has no stored object and `FR-133` grants no new vocabulary). `runtime/comparison_assembly.py` (the RRA half as an injected port, so `khepri.rca` never imports `khepri.rra`: binds each version to its latest completed run's digest-verified package, reads the retained coverage manifest for granularity, completeness and aggregate scope, renders through `C1-05`, and unlinks the workbook file as soon as its bytes are in hand — `RRA-006` §Not stored). `runtime/shell_comparison.py` and `compare.html.j2` (`POST …/analyses/compare` and `GET …/compare/{subject}/{baseline}`: a bilingual page naming both versions and linking both Analysis Passports per `FR-132`, offering the HTML, PDF and workbook surfaces as downloads from the same render, since a comparison has no stored artifact for the redirect handoff to point at; a refusal shows `C1-04` wording and no figure; an isolation miss shows the uniform surface per `FR-050`). Nothing is stored: a request writes no row to any table except its audit event. Retail-day boundary: the retained `RRA-003` manifest attests calendar dates in one timezone, and that timezone is the boundary every attested day is stated in; the frozen period type carries an hour, not a zone, so hour zero is stated on both sides and — review of `#409` having shown that alone left `RRA-008`'s retail-day-boundary refusal unreachable when two manifests attest different zones — the assembly refuses a zone mismatch under that frozen cause once every frozen predicate has admitted the pair (owner's reading, 2026-09-08: the comparison lives in the composition layer for now). Carried forward for the owner: the proper home is the family's period predicate itself, carrying the zone rather than an hour, which is an `RRA-008` amendment; and the shipped wording for that cause, "close their retail day at different hours", is a near fit for a zone mismatch worth rewording in the same amendment. Also: scope denial (`ScopeAccessDenied`) propagates before an owner scope exists to attribute an event to, as in every other workspace action, so it is not audited. Content horizon: the package and profile are read through the upload session, whose content horizon is seven days, so a comparison is the uniform unavailable surface once either operand's session has passed it — the same horizon at which its report stops reopening — stated and tested rather than emergent; the `KHEPRI-DEC-033` §2 matrix keeps the package with the run and the manifest with the version, so a retained read path that outlives the session is an owner amendment, recorded here. Review of `#409` found the result page framed the HTML surface through `iframe srcdoc`, which the shell's `default-src 'none'` policy (no frame directive) blocks outright and whose inline stylesheet `style-src 'self'` would block besides; the frame was dropped and the HTML surface is offered as a handoff beside the PDF and workbook, as every Analyses artifact is (`#410`, closed). The same round found each surface rendered twice — once inside the assembler, which governs a renderer fault, and once outside it, where a fault escaped the request before its audit event — so the three renderers now run once, inside the assembler, with each document kept, and a fault is the uniform unavailable outcome with exactly one audit event |
| C1-07 | Build Compare flow and results UI | C1-06, U1 | accessibility | Customer flow — **MERGED** (`#411`) under `RCA-005` `FR-132` ("a completed comparison is reachable from the Analyses surface"). The Analyses page offers Compare below the spine when comparisons are wired and two live completed data entries exist: one form posting `subject` and `baseline` to `C1-06`'s existing `POST …/analyses/compare`, two labelled selects naming each entry the way the Data surface names it (submission instant visible, opaque identifier only in `<option value>`), defaults of newest against second-newest. Fewer than two candidates, or a deployment without the action wired, renders nothing — no disabled control, per the design language's rule against disabled-control education. `compare_candidates` is a pure helper over the spine rows already built: live rows only, completed only, present and undeleted data only, de-duplicated by version, spine order kept. **The `U1` dependency in this row's Depends-on column was planning, not authority, and the owner's reading of 2026-09-08 settled it**: `RCA-005`'s Scope already governs `shell_api.py` and `shell_templates/`, `U1`'s own block is the `/beta` journey-adoption decision on a surface `RCA-005` excludes, and `U1-03`/`U1-05`–`U1-07` have no active specification at all. The accessibility bar met here is `RCA-005`'s own Invariants — bilingual parity, RTL, 44px targets, no colour alone, no inline script or style, CSP unweakened — enforced by the `R8-07` shell-quality gate, whose stub now carries two completed versions so the form is measured in a real browser. **One boundary held rather than crossed**: `RRA-012`'s data-display components govern `RRA` surfaces only (its own §Scope excludes the shell's `shell.css`/`shell-components.css` under the one-family rule), so this slice composes from the shell's existing classes and adds no stylesheet rule. Carried forward for the owner: `runtime/shell_assets/` is named by no active artifact — `RCA-005` covers the templates and routes but not the shell stylesheets, and `R8-07` is archived — so the first slice that needs a new shell CSS rule needs that scope named first |
| C1-08 | Add exactness, provenance, cross-org, mixed-version, unsupported-filter, deletion, and rerun tests | all above | no | Evidence — **MERGED** (`#412`): `tests/test_c108_comparison_evidence.py`, eighteen tests proving the seven properties this row names against the assembled bundle and, where the property is about a reader rather than a value, through the shipped surface. **Three of the seven had no coverage anywhere in the suite**: exactness (the published delta and four-place ratio are the arithmetic `RRA-008` §Comparative states, hand-computed from the fixture rather than recomputed from the operands), mixed-version (each of the three governed versions refuses under its **own** cause, asserted by comparing all three against each other so a collapsed cause cannot pass), and unsupported filters (an event-kind or status difference refuses as the frozen `incomparable basis`, with no figure beside the refusal). The other four are proven through the door a customer reaches: a foreign pair is byte-identical to a missing one, a deleted version is unavailable **and still audited exactly once** (the `C1-06` test proves the surface and asserts nothing about the trail), the same pair assembles the same `bundle_id` twice while the reversed pair does not, and every figure's evidence names both operands and their order. **Mutation-tested, and the mutants found three real weaknesses**: a ratio quantized to two places survived (every fixture quotient is exact at two places), a `ROUND_HALF_UP` swap survived (no fixture quotient reaches a tie), and one test asserted that three imported constants differ, which no production change could break. All three are closed and each mutant now fails. One mutant survives by design: removing the compatibility table's scope predicate changes nothing because `crossversion_assembly` guards scope directly first — removing **both** guards does fail the test, which is how the equivalence was proven rather than assumed. No production code changed; `governance/**` untouched |

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

**The composition slice this table never allocated.** `SV1-04`'s "read-model/query service" is an
injected Protocol by `RCA-006` §Request flow, and neither `RRA-014` nor `RCA-006` admits the
composition root that binds it — so the eight tasks above can all be complete while every view over
a real run still refuses. Closing that needed a new artifact rather than a ninth ID here: active
`RCA-007` (`FR-151`–`FR-158`), `32a1112` (`#427`), implemented at `2337cd4` (`#437`). Recorded so a
reader does not read `SV1-01`…`SV1-08` as the whole program, and so the next allocation plan asks
where its composition root is admitted before it counts its slices. `W1-09` is the precedent
(§17 item 17).

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
| S1-02 | Identify caller-controlled identifiers and security material at store seams. **Its `#231` clause is discharged**: that evidence was delivered directly rather than waiting on this triage, so rank only the store seams | S1-01 | Ranked list |
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

## 16. Recommended current status at `2337cd4`

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
| R7 Commercial RRA bridge | MERGED | Commercial analysis bridge, routes, and consent surface merged. **`#231` is closed**: `R7-03`'s live-authorization guards now carry mutation evidence, and each of the three mutants kills exactly one test in the isolation class, so the resolver's gate and the bridge's gate are proven independent rather than redundant. Carries part of `#211`. See section 0.2 |
| R8 Commercial shell | READY_FOR_PLAN | **`R8-08` is AUTHORITY-BLOCKED, not merely unscoped** — it conflicts with active `KHEPRI-DEC-015` and resumes only by amending it (`KHEPRI-DEC-031` §5), so it is not R8's next actionable task. **`R8-10`'s journey half is MERGED** (`#363`, `523991a`, 2026-09-03) under existing `RRA-010`: the report step groups its seven links as *Report and evidence* then *PDF and Excel*, page-language web report first; the data side was already met by the web report's quality summary (`#350`) and the evidence surface's drawer (`#358`), which that step links. Its shell half stays `RCA-002`'s and is not started. **One finding for the owner came out of it**: every surface, the web report included, is served `Content-Disposition: attachment` (`report_api.py:562`), so no card opens a report in the browser — whether the two HTML surfaces should be served inline is an `RRA-006` reading, filed in the slice's plan. Browser handoff may require successor authority for external partner use; `R8-11` is deferred with the hosted environment |
| **CAL1 Calculation correction** | **MERGED** | **All seven successor versions published at `#308` (`7088749`)** — `mapping.py:22` pins `rra003.mapping.v3`, `facts.py:92-93` pin `rra004.package.v3` and `rra004.formula.v2`, and the four `rra008.*` families pin their `v2` constants. The strict `xfail` on `test_profile_accepts_a_complete_contract_and_stamps_mapping_v3` was removed there, as designed. Nine PRs merged after it correcting defects in the now-governing contracts, then `CAL1-11`'s catalogue-wide compatibility sweep at `9e7a886` (`#328`). **`MERGED` with a `main` SHA, per §15**: every CAL1 task has landed — `CAL1-12` through `CAL1-15` at `#330` (`f320c17`), after `CAL1-11` at `#328` (`9e7a886`). The closure evidence is the CAL1-15 ledger's own standing table, which records `CAL1-12` and `CAL1-15` complete and `CAL1-13`/`CAL1-14` passing; the owner merged that assessment, and `AGENTS.md` makes a merge the approval. **Two P2 findings are carried, not gates** — the same shape as `R7` carrying `#231` and `#211`: defects against landed work rather than unmet acceptance. `CAL1-12` killed five of six named mutants with existing tests and closed the sixth (publication-gating over `versions.py`'s `ADMITTED_PACKAGE_PAIRS`/`ADMITTED_FAMILY_PAIRS`, previously a P1 proof gap, now mutation-verified per table) with two new exact-extent tests, added a pharmacy golden fixture, and filed two P2 findings open: `CAVEAT_CURRENCY_NOT_DECLARED` is unreachable under `rra003.mapping.v3` (needs an `RRA-003` or `RRA-009` ruling), and the Excel container is not byte-identical across regenerations — one of 46 ZIP members, `docProps/core.xml`, carries a `dcterms:created`/`modified` wall-clock stamp (needs an `RRA-006` reading of whether deterministic regeneration governs container bytes or governed content). `CAL1-13`'s validation gate passes — governance and Ruff clean, 3,631 passed/72 skipped/1 xfailed whole-repo, the calculation-contract scope alone (`test_rra00*`, `test_rra_calculation_*`, `test_cal1_*`, `test_bmk001_*`) at 1,832 passed and zero skipped, deterministic across two runs. `CAL1-14`'s staging journey passed with zero failures end to end, bilingual, restart/recovery verified, `package_digest` byte-identical across four runs. `CAL1-15` is complete: its CodeScene clause could not be checked from the authoring session (CodeScene MCP `CONNECTION_CLOSED`, `github` MCP `401`) and was **settled by the required server-side gate on `#330`, which reported pass**. No unresolved P0/P1 finding remains open. Carries `#326` and `#311`; neither blocks. **Carries two P2 follow-ups; neither blocks** — (1) `CAVEAT_CURRENCY_NOT_DECLARED` is unreachable under `rra003.mapping.v3`, awaiting an `RRA-003` admission change or an `RRA-009` withdrawal; and (2) the Excel container is not byte-identical across regenerations, one of 46 ZIP members carrying a `dcterms` wall-clock stamp, awaiting an `RRA-006` reading of whether deterministic regeneration governs container bytes or governed content. Neither publishes a wrong figure. **Its critical-path successor, `T1`, is also merged.** |
| **T1 Trust/catalog** | MERGED | **The `M2` minimum has landed.** Active `RRA-011` allocates the metric, population, and reason catalog, its bilingual vocabulary, and its evidence surfaces, governing `T1-01` through `T1-05` and `T1-08` — and all six merged: `T1-01` through `T1-04` at `#334` (`a91fa63`), `#338` (`4e448ed`) and `#340` (`46b2d56`), then `T1-05` with the `T1-08` parity remainder at `#343` (`bc96a65`). §14's "M2 minimum" is `T1-01`…`T1-05` plus `T1-08`, so the program's next actionable task is outside the `M2` gate. `MERGED` with `main` SHAs per §15. **Carries `#345`'s Exclusion question, answered by `KHEPRI-DEC-032`** — the two package-scoped catalog routes construct a `ReportBundle`, which that decision reads as admissible; it publishes no figure, proven against live responses. `T1-06` lineage is excluded from `RRA-011`, needs its own authority, and may complete during early `M3`; `T1-07` trust telemetry is excluded and **blocked** on the same `KHEPRI-DEC-015` prohibition as `R8-08` (`KHEPRI-DEC-031` §5). Neither is an `M2` gate |
| **LAND1/legal Public surfaces** | MERGED | **Was absent from this table entirely** — three merged programs with no status row, which is the §15 drift this section warns about. The public legal and trust surfaces merged at `#331` (`9161b50`); `#339` (`3f998df`) activated the public-landing authority under `RCA-004`; `LAND1-01`'s public product landing surface merged at `#341` (`ee566b2`), after the `#335` (`80548a5`) design concept. No open task; recorded so a later reader does not re-derive the program from the commit log |
| **U1 Design system** | BLOCKED | **§15: a program's status is the status of its next actionable task.** Everything `RRA-012` and `RRA-013` authorize is **merged** (2026-09-03): `U1-02`'s component layer (`#350`), `U1-04`'s drawer structure (`#352`), active `RRA-013` (`#353`) with its plan and supply (`#354`, `#355`), the drawer placed beside every evidence figure row (`#356`, `#358`), the pagination-test correction that placement required (`#359`), and the `RRA-011` follow-on in which the citation route reads the bundle's evidence and its duplicate projection is deleted (`#360`, `37455a5`). **The "journey adoption" clause this row carried at `#361` was a phantom, and drafting its amendment is what found it.** No `/beta` page renders a governed figure, bundle section state, citation, formula version, or coverage identity — the seven things `RRA-012`'s components present — and every journey state is fetched by JavaScript after the page is served, so the Jinja macros could not render there even if the data existed. An `RRA-010` asset-wiring slice would ship a stylesheet to five pages on which none of its selectors ever matches. The one task that would put bundle state on a journey page is `R8-10`, and its data side is already met: the web report surface opens with the quality summary (`#350`) and the journey's report step links it before the downloads. Filed as `docs/superpowers/plans/2026-09-03-rra010-journey-adoption-reading.md`, **OWNER DECISION, not yet taken**: it recommends no amendment, and until the owner records an answer **the amendment stays on this program's path as pending** — the filing decides nothing, and no slice may act as though option A were chosen. That decision is the owner's and is not a task on this program's path; it is the named dependency that keeps the journey clause closed. What remains of `U1` beyond it is still **authority, not code**: `U1-03`, `U1-05`, `U1-06`, `U1-07` have no active specification governing their files. **`U1-01` is delivered**: `KHEPRI_DESIGN_LANGUAGE.md` is reconciled to `f15c835` — §4.11 documents the `RRA-012` component layer, its §0 verification table is re-measured, and §4.5/§8.2/§8.3/§8.5 record the authority that moved. After it, **no `U1` task can start**: `U1-03`, `U1-05`, `U1-06`, `U1-07` await a specification and the journey clause awaits the owner's answer to the filing, so per §15 the program reads `BLOCKED`, with those two owner-authored artifacts as the named dependencies |

| **OPS1 Hosted operations** | READY_FOR_PLAN | Local staging exists; environment descriptor, sizing, RTO/RPO, secrets, hosted provisioning, recovery and capacity evidence remain. **`OPS1-01` is done and `OPS1-02` is unblocked** by `KHEPRI-DEC-030` §3–4 for the provisional bootstrap shape — but `KHEPRI-DEC-031` §4 **defers `OPS1-02` through `OPS1-05` and `OPS1-09` past `M2`** by owner decision. Deferred, not blocked: the authority is active and unexercised, so this resumes by scheduling it |
| S1 RRA hardening | READY_FOR_PLAN | Triage only; avoid CAL1 hotspots. Owns `#152` through `S1-05`. **No longer ranks `#231`** — that evidence is delivered and the issue closed, so `S1-02` is store seams only |
| **G2/G3 Workspace authority** | MERGED | **Complete. Both artifacts are active.** `G2-01`'s inventory (`docs/superpowers/specs/2026-09-03-g2-01-retained-data-inventory.md`) measured 22 tables, two object namespaces, two cookies and one telemetry sink on `457f276`. `G2-02` was answered by the owner in session on 2026-09-03: all eight recommended values approved, recorded as the decided table in `KHEPRI-DEC-033` §4 — raw upload purged **7 days** after sealing, deletion evidence **12 months**, **no** inactivity expiry, disabled-organization content frozen then ended at **24 months**, backups **14 days**, owner-only deletion, no export beyond the governed bundle, organization-as-controller. `G2-03` merged that decision (`governance/decisions/KHEPRI-DEC-033-durable-retail-content-retention.md`), which also **closes `KHEPRI-DEC-015` §8's open backup horizon**. `G3-01`..`G3-03` merged as active `RCA-005` (`FR-109`..`FR-127`), and `G3-04`'s bounded plan is `docs/superpowers/plans/2026-09-03-g3-04-workspace-implementation-plan.md`, allocating ten PRs across `W1-01`..`W1-10`. **One obligation travels with this authority**: `KHEPRI-DEC-033` §5 records that no retention sweeper has a caller in the shipped image, so every horizon is intent until `W1-07` ships the sweep with a deployed caller. No surface may claim automatic expiry before then |
| **W1 Workspace/history** | MERGED | **Program complete: all eleven slices are on `main`.** `W1-01` `1397b69` (`#368`), `W1-02` `d66fe3d` (`#370`), `W1-03` `9e7989b` (`#371`), `W1-04` `882166d` (`#372`), `W1-04b` `b16165f` (`#375`), `W1-05` `99db705` (`#373`) with `fedb723` (`#374`), `W1-06` `e93356c` (`#376`) with `a894074` (`#378`) and `3867b8a` (`#381`), `W1-08` `267c50c` (`#377`), `W1-07a` `4d79692` (`#382`), `W1-07b` `89796bd` (`#384`), `W1-10` `916d679` (`#385`), and **`W1-09` `cf607fd` (`#390`)**, merged 2026-09-06 on the owner's explicit word once every check was green. `MERGED` with a `main` SHA per §15 — the previous row read `READY_FOR_IMPLEMENTATION` deliberately, because that SHA did not exist while `#390` was open. **`KHEPRI-DEC-033` §5 is discharged**: `W1-07b` shipped the retention sweep with a caller in the built wheel, so the horizons are enforced rather than intent, and a surface may now state them. **`W1-09` needed authority `G3-04` never allocated** — that plan carried ten slice IDs and no `W1-09` — which active `KHEPRI-DEC-034` (`1d8c5de`, `#386`) supplied as a new Constitution VII decision rather than an amendment to `KHEPRI-DEC-015` §3. **`W1-11` repeat-use telemetry therefore stays excluded**, needing the same amendment as `R8-08`; §2 of that decision states it is no precedent for either. **One follow-up carried, not a gate**: the Pinned region renders a kind and an instant but no link, so §1's "quick return" is served by orientation rather than navigation — a link is a surface decision `RRA-012`'s component layer owns |
| G4/C1 Comparison | MERGED | **Program complete: all eight `C1` slices are on `main`**, and all four `G4` tasks are complete: the governing comparison artifacts `RRA-006`, `RRA-008`, and `RCA-005` are `active` in `registry.yaml` — `C1-01` `7a1f17f`, `C1-02` `3890d8b`, `C1-03` `f7b9824`, `C1-04` `7bbfed7`, `C1-05` `aca025b` (`#408`), `C1-06` `3718930` (`#409`), `C1-07` `cd310e9` (`#411`), `C1-08` `02e50cd` (`#412`). §15 makes a program's status the status of its next actionable task, and `C1` has none. **Three owner readings are carried forward rather than decided**, each recorded in the slice row that raised it: the `RRA-008` amendment that would move the retail-day boundary into the family's period predicate (carrying a timezone rather than an hour) and reword its cause; the comparison's seven-day content horizon against `KHEPRI-DEC-033` §2, which keeps the package with the run; and the fact that no active artifact names `runtime/shell_assets/`, so the first slice needing a new shell stylesheet rule needs that scope named first. Historical note, kept because it records how the status moved: **moved from `BLOCKED` by §15's own rule**: a program's status is the status of its next actionable task, and `BLOCKED` is reserved for programs whose next task — design included — cannot start. `G4-01` is design and can start, so `BLOCKED` was the wrong status the moment item 18 measured `M3`; the blocking implementation dependency is named here instead of reverting the row. **The `W1`/`M3` half of this dependency is now met and the row's wording collapsed two different things.** `W1` is a merged program, verifiable from SHAs; `M3` is an exit gate, verifiable only from an acceptance record — and none existed until `M3` was measured on `c98e946` (§17 item 18, `docs/superpowers/plans/2026-09-06-m3-acceptance-evidence.md`). What remains is the **new split authority**, which is owner-authored: `G4-02` activates the RRA comparison-fact authority and `G4-03` the RCA orchestration authority. `G4-01` — comparison use cases and period/dataset semantics — is product scope and is **DONE** as a `docs/` scope note (`docs/superpowers/plans/2026-09-07-g4-01-comparison-scope.md`, §17 item 19), so the program's next actionable task is now owner-authored. **The earlier wording here — that `G4-01` "may be drafted `proposed`" — was wrong**: there is no `proposed` registry state (`ARTIFACT_STATES = {"active", "retired"}`), the Constitution's Lifecycle puts proposals "on branches and pull requests, not in the authoritative lifecycle", and a new `specification` row must depend on exactly one family, which would pre-empt the very `G4-02`/`G4-03` split; the note's §0 records all three grounds. At that historical point, `C1-01`..`C1-08` stayed blocked behind `G4-04`; those contracts are now active and all eight slices have merged |
| **SV1 Semantic views** | MERGED | **Program complete: all eight tasks are on `main`, plus the composition slice this table never allocated.** `SV1-01` activated both halves of the authority — `RRA-014` (`FR-134`–`FR-144`) and `RCA-006` (`FR-145`–`FR-150`) — at `9ec3896` (`#418`), 2026-09-09. Then `SV1-02` with its allocation plan at `65521a6` (`#420`), `SV1-03` `897f702` (`#421`), `SV1-04` `422106d` (`#422`), `SV1-05` `cd2eba3` (`#423`), `SV1-06` `172a94d` (`#424`), `SV1-07` `2ab898a` (`#425`), `SV1-08` `9633c6c` (`#426`). `MERGED` with `main` SHAs per §15. **The seven slices shipped a path that could not answer, and said so rather than hiding it.** `RCA-006` §Request flow made the RRA seam an injected Protocol and put the composition root outside both packages' Scope, so no SV1 slice could bind them: every semantic view over a real run answered `ViewRefusal('incompatible source shape')`. Three slices left **absence markers** — failing-by-design tests asserting the adapter did not exist — so the day it shipped they would fail and force the deferred property to be exercised. That is the `W1-09` shape repeating: a slice the allocation never carried an ID for, needing new owner-authored authority, supplied here as active `RCA-007` (`FR-151`–`FR-158`) at `32a1112` (`#427`) rather than as an amendment to either SV1 half. The composition merged at `2337cd4` (`#437`), 2026-09-10, and **all three markers fired exactly as written** and were replaced by the properties they held open — not deleted. **One reading the composition carries forward rather than decides**: `ReportBundle.of` runs `RRA-004`'s derivation on the read path, which `RCA-007` put to the owner with its counter-argument stated; merging it was the ruling that determinism is protected by the adapter's two fail-closed checks (the digest, `FR-153`, and the versions the run recorded at delivery, `FR-157`) rather than by avoidance |
| **D1 Decision workspace** | READY_FOR_PLAN | **Moved from `BLOCKED` by §15's own rule: a program's status is the status of its next actionable task, and `D1-01` is design that can start now.** Its stated dependency — "C1/SV1 stable" — is met on both halves: `C1-01`…`C1-08` merged, and `SV1` is complete through the `RCA-007` composition at `2337cd4` (`#437`), so a semantic view over an organization-scoped run returns a real projection rather than a refusal. **The blocking implementation dependency, named here rather than reverting the row: no active specification in `registry.yaml` governs the D1 product-code files**, so `D1-02` onward is authority-blocked and owner-authored, exactly as `G4-02`/`G4-03` were for `C1`. `D1-01` is information architecture, narrative order and an exact fact/view source map — product scope, which Article IV does not govern — so it lands as a `docs/` note under the `G4-01` precedent (`docs/superpowers/plans/2026-09-07-g4-01-comparison-scope.md`) and **may not be drafted `proposed`**: `ARTIFACT_STATES = {"active", "retired"}` and the Constitution puts proposals on branches, not in the lifecycle. **Two inputs `D1-01` already has, and should not re-derive.** The eight-view registry is closed and published (`FR-135`), so the source map is a selection from it rather than a design space. And `SV1-08`'s ledger §3a now measures the composed path — 4003 µs p50 end to end, of which projection is 11.6 µs, about one part in 345 — so **`D1-09` is pointed at source acquisition** (three scoped reads and one derivation per request), not at projection or the view registry, and `FR-144` still bars caching, pre-aggregation, materialized views and sampling from that path, making any change there a governed one. **`U1` is the `Parallel` column, not a dependency** — but it is `BLOCKED` on the owner's answer to the `RRA-010` journey-adoption filing, so `D1-01` may name the components it wants without assuming they can reach a page |
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
16. ~~**G2/G3:** activate retention and workspace authority.~~ **Done** — `KHEPRI-DEC-033` and `RCA-005` are active, and `G3-04`'s plan (`docs/superpowers/plans/2026-09-03-g3-04-workspace-implementation-plan.md`) allocates `W1-01`..`W1-09`. The owner approved all eight retention choices in session on 2026-09-03; `KHEPRI-DEC-033` §4 records each against the alternatives it beat. It also closes `KHEPRI-DEC-015` §8's backup horizon at fourteen days.
17. **`W1-01` onward — begin durable workspace/history implementation. This is now the first incomplete item on the critical path.** Order is fixed by `G3-04` §1-2: contracts (`W1-01`), persistence and the one-head migration (`W1-02`), the tombstone allowlist (`W1-03`), services (`W1-04`), then surfaces in `FR-049` link order (`W1-05`, split into Overview/Data then Analyses), Analysis detail and the Passport (`W1-06`), the Methodology Change Notice (`W1-08`), then deletion and the retention sweep (`W1-07`), then isolation hardening (`W1-10`). Build order is deliberately not numeric: `W1-07` introduces the first destructive path and lands after the read surfaces it can affect. **`W1-07` carries `KHEPRI-DEC-033` §5** and is the only slice that can discharge it: until its sweep ships with a caller in the built wheel, every retention horizon is unenforced and no surface may say content expires automatically.

    **Status at 2026-09-06.** That obligation is **discharged**: `W1-07b` (`89796bd`, `#384`) shipped the sweep with a caller in the built wheel. Ten slices are merged — `W1-01`…`W1-08`, `W1-04b`, `W1-10` — and the order above held, with deletion landing after the read surfaces it can affect. **`W1-09` is the remainder and was never in `G3-04`**, which allocated ten IDs without one for it: `RCA-005` named no requirement for pins or recent activity, and its Exclusions barred both halves. `#386` (`1d8c5de`) closed that by authoring `KHEPRI-DEC-034` as a **new** Constitution VII decision rather than an amendment to `KHEPRI-DEC-015` §3 — which is why `W1-11` and `R8-08` stay excluded and item 10 above is unchanged by it. `W1-09` builds last, after every surface a pin can point at. **Done** — `cf607fd` (`#390`), 2026-09-06. **This item is closed and the M3 workspace chain is complete.** The next critical-path work was `G4/C1` comparison; that program has since merged, as items 19–20 and §16 record.

18. ~~**`M3` acceptance — measure the §5 exit gate against the deployed image.**~~ **Done** — measured on `main` at `c98e946`, 2026-09-06. This item existed because `G4-01` depends on `M3` and **no acceptance record existed**: `M2` had a numbered queue item, four owner-authored conditions in `KHEPRI-DEC-031` §7, and two evidence ledgers, while `M3` had only §5's one-sentence gate and this queue ended at item 17. The gate's six clauses were driven through the real customer path — `POST /app/{lang}/{org}/analyses` into the beta journey, then the workspace surfaces — on a stack rebuilt first, because the running image was 23 hours old and predated `W1-09`. **Six of seven measured clauses pass**: two dataset versions and two analyses retained and listed; the Analysis Passport rendering period, coverage and the version triple; all four artifact kinds reopening with a scoped handoff; deletion removing the version from the surface that listed it and leaving one revocation, two tombstones and audit rows; and four catalog routes answering in both languages with no figure. Byte-identical package digests across two runs in four organizations. **The seventh — `W1-08`'s Methodology Change Notice — is recorded NOT EXERCISED rather than passing**: both analyses ran on the one version triple the image pins, so `methodology_change` returns `None` and the section correctly renders nothing, verified on both runs' live detail pages. A run that can only produce the null case does not prove the capability, and whether §5's "history" requires a demonstrated diff is an owner reading this ledger names rather than settles. `KHEPRI-DEC-033` §5 was separately re-confirmed discharged by finding `build_retention_sweeper`'s caller **in the image**, not merely in the repository. Evidence: `docs/superpowers/plans/2026-09-06-m3-acceptance-evidence.md`. **Two things this does not do.** It measures §5's sentence rather than a decomposed condition set, because no governed artifact decomposes `M3` and authoring one is the owner's, not this queue's; and it is a local-stack run that authorizes no external participant. **One finding came out of it, outside the gate**: the Team surface raises `500` in the deployed image — `wiring.py:497` passes `RcaInvitationService` where `shell_api.py:152`'s Protocol requires the store's `invitations_for_organization`, structural and so unchecked until driven. Introduced at `1e774db` (`#274`), not a `W1` regression, and `RCA-002`'s to fix.

19. ~~**`G4-01` — define comparison use cases and supported period/dataset semantics. This is now the first incomplete item on the critical path.**~~ **Done** — `docs/superpowers/plans/2026-09-07-g4-01-comparison-scope.md`, on `main` at `befd95a`, 2026-09-07. Its `M3` dependency is measured by item 18, which found six of seven clauses passing and one — `W1-08`'s Change Notice — not exercisable by a single-triple image. `G4-01` is scope definition rather than implementation, so it does not consume the open clause; the slices that would (`C1-01`..`C1-08`) sit behind `G4-04` and behind the owner's reading either way. `G4-01` is product scope rather than an activation, and is **now done** as a `docs/` scope note — `docs/superpowers/plans/2026-09-07-g4-01-comparison-scope.md`, which names four use cases (two admitted, one refused, one deferred), inherits `RRA-008`'s period semantics whole, and enumerates a six-predicate fail-closed compatibility gate. **It is not a governed artifact, and the earlier plan to draft it `proposed` was inadmissible**: there is no `proposed` state, `RCA-005` is the artifact that *deferred* comparison so it cannot host it, `RRA-008` is family-bound to one population, and a new specification row must depend on exactly one family — which would pre-empt the `G4-02`/`G4-03` split. Article IV governs product code, not scope definitions, and `G3-04` is the precedent for a `docs/` note carrying an Authority header. It passes the "what consumes it?" test because `C1-01`…`C1-08` is a real eight-task program, and `G4-02`/`G4-03` are where this scope acquires authority or is rejected. `G4-02` and `G4-03`, which activate the split RRA and RCA comparison authority, are owner-authored and are **not** this queue's to schedule.

20. ~~**Activate `G4-02`, `G4-03`, and `G4-04`, then implement `C1-01` through `C1-08`.**~~ **Done.** `RRA-008` carries the active two-population comparison authority, `RCA-005` carries active comparison orchestration, `RRA-006` carries the sibling bundle, and both governing specifications freeze the four contract halves by reference. All eight implementation slices are on `main`; §16 records their SHAs and the three owner readings they carry forward without deciding. At that point the first incomplete critical-path item was `SV1-01`; item 22 records it closed and item 23 names the successor.

21. ~~**Governance integrity — `Constitution VII` is cited 16 times in `governance/` and does not exist.**~~ **Done** — Article VII restored, Constitution `2.1.0`. Constitution v2.0.0 has Articles I–V; `#147` ("simplify single-owner governance") deleted **Article VII (Privacy and least data)** and **Article VIII (Delegation)** without rewriting their citations. `KHEPRI-DEC-034` §3 is the most load-bearing case — its choice of recency over frequency rests on "Constitution VII's least-data default" — and `KHEPRI-DEC-015` §3's "requires its own Constitution VII decision" is quoted by `RCA-005`'s telemetry exclusion. Article VIII mattered separately: it was the instrument by which a human authority could delegate approval to a non-human one, and under v2.0.0 Article I says automation "does not approve changes or act as a separate authority." **Resolved by restoring the article, not by rewriting citations.** `KHEPRI-DEC-017` — the **active** decision that authorized `#147` — states "Privacy, runtime, and data boundaries remain unchanged by this governance-only migration", so deleting Article VII contradicted the decision's own stated scope and restoring it repairs that rather than setting new policy. The same decision retires delegation deliberately ("approval packages, delegations, authority records" removed), and `#147`'s design names removing "approval, delegation, renewal" machinery as a goal while listing "claiming that automation independently approves changes" as a non-goal — so **Article VIII stays retired** and no authority, delegation, approval package or old lifecycle state returns. The restored text is the former article verbatim plus one clause fixing "approval" to Article II's owner merge, which the v1 wording left to a removed approval-package mechanism. **No citation was edited**: all 15 active citations (the 16th, `KHEPRI-DEC-008`, is retired) ask only for a least-data default and the new-data-use requirement, and `KHEPRI-DEC-015` — titled "Commercial identity retention under Constitution VII" — quotes the article verbatim, which is what proves the restored text carries the semantics they were written against. Found while authoring `G4-01`.

22. ~~**`SV1-01` — activate semantic-view and governed-query authority.**~~ **Done, and the whole program with it.** The owner merged both halves of the authority on 2026-09-09 — `RRA-014` and `RCA-006` at `9ec3896` (`#418`) — and all seven implementation slices followed within the day: `65521a6` (`#420`), `897f702`, `422106d`, `cd2eba3`, `172a94d`, `2ab898a`, `9633c6c` (`#421`–`#426`). §16's SV1 row carries the per-slice SHAs.

    **The instruction "do not schedule `SV1-02` through `SV1-08` until the owner merges that specification" held, and a second instance of the same rule appeared behind it.** `RCA-006` §Request flow required the RRA seam to be an injected Protocol and put the composition root in neither package's Scope, so the eight-view path shipped complete and unable to answer: every view over a real run returned `ViewRefusal('incompatible source shape')`. **No slice widened its scope to fix that** — `SV1-04`, `SV1-07` and `SV1-08` instead left failing-by-design absence markers asserting the adapter did not exist, and `SV1-08` recorded its end-to-end baseline `NOT EXERCISED` rather than inferring one. The gap was closed the owner's way: new authority, active `RCA-007` (`FR-151`–`FR-158`) at `32a1112` (`#427`), then the composition at `2337cd4` (`#437`) on 2026-09-10, where all three markers fired and were replaced by the properties they were holding open. **This is `W1-09` repeating** (item 17): an allocation plan that carried no ID for a slice the program turned out to need, resolved by authoring authority rather than by stretching an existing artifact.

23. **`D1-01` — define the information architecture, narrative order, and exact fact/view source map. This is now the first incomplete item on the critical path.** Its `C1`/`SV1` dependency is met on both halves, and as of `#437` a semantic view over an organization-scoped run returns a real projection, so the source map can be written against a path that answers rather than against one that refuses.

    **It is scope definition and writes no product code, because it cannot.** No active specification in `governance/registry.yaml` governs the D1 product-code files, so `D1-02` onward is authority-blocked in exactly the way `C1-01`…`C1-08` sat behind `G4-02`/`G4-03`. `D1-01` lands as a `docs/` note under the `G4-01` precedent, with an Authority header; **do not draft it `proposed`** — there is no such registry state, and a new specification row must depend on exactly one family, which would pre-empt whatever RRA/RCA split the owner chooses for D1. Scheduling `D1-02` before that specification is active is the mistake item 22 just recorded being avoided twice.

    **Two things it should consume rather than re-derive.** The view registry is closed to eight views by `FR-135` and is published, so the source map selects from it. And `SV1-08`'s ledger §3a measures the composed request at 4003 µs p50 with projection at 11.6 µs — one part in 345 — so `D1-09`'s target is source acquisition, and `FR-144` makes any caching, pre-aggregation, materialized view or sampling on that path a governed change rather than a local optimization.

    **The owner-authored artifacts this queue may not schedule** are the D1 product-code authority above and the `RRA-010` journey-adoption reading that keeps `U1` `BLOCKED` (`docs/superpowers/plans/2026-09-03-rra010-journey-adoption-reading.md`). `D1-01` may name the components it wants; it may not assume a stylesheet can reach a page.

### Parallel-safe work now

*This list was written during CAL1 and its first two entries have since been overtaken by events. Kept
and corrected in place rather than deleted, because a reader arriving from an older note needs to see
what changed.*

- ~~OPS1-01 environment decisions may proceed during CAL1.~~ **Done** — item 11.
- ~~T1/U1 design may proceed during late CAL1 review.~~ **T1 is merged** (item 9). **U1 was `BLOCKED` and is now `READY_FOR_PLAN`, and the phrase "U1 design may proceed" was wrong in between**: when this entry was corrected, no active specification governed the files `U1-02` through `U1-07` would touch. `RRA-011` disclaims the consuming surfaces, `RRA-010` puts `shell.css`/`shell-components.css` outside its scope, and `RCA-002` excludes changes to the journey's templates and assets. That gap is now closed for `U1-02` and for the presentation half of `U1-04`: **active `RRA-012` allocates the data-display component layer**, so U1 moves from `BLOCKED` to `READY_FOR_PLAN` — design and a bounded plan may proceed, and implementation begins when that plan's RED tests exist. Supplying the drawer's catalog data is deferred to its own artifact, because it is a materialization-path change rather than a component one. It excludes the chart grammar (`U1-03`), navigation (`U1-05`), accessibility evidence (`U1-06`), and visual-regression (`U1-07`) tasks, which keep the original gap and stay `BLOCKED`. **It also does not authorize component adoption on the journey surface** — the stylesheet cannot reach a journey page without an `RRA-010` asset-wiring slice. `U1-01` — documenting the primitives that already exist — is unaffected.
- G2 data-inventory research may start near CAL1 completion, but retention decisions should use M2 learnings. **`M2` is now reached in its local-only form (item 15), so those learnings exist.**
- S1 triage only may proceed if it does not overlap CAL1 files.

### Do not start now

- W1 persistence;
- C1 comparison;
- ~~D1 dashboard;~~ **corrected in place: `D1-01` is now item 23 and may start.** What stays barred is D1 *implementation* — `D1-02` through `D1-11` — until the owner merges an active specification governing the D1 product-code files. Writing a read model, a KPI module, or a filter surface before then is the prohibition this line still carries;
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
