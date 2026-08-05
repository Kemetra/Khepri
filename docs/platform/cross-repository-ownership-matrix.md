# Cross-repository ownership matrix

**Planning-only. Approves nothing.** Base commits: Khepri `c7d78b2`, Seshat-BI `157ef43`.

Roadmap §10 Phase 0 acceptance: "Every planned capability has one owning repository. No
calculation is authoritatively owned by both repositories."

## How to read this

- **Target owner** — the repository the roadmap and this analysis agree should own it.
- **Today** — where working code or an approved artifact actually is.
- **Δ** — `=` agreed, `!` disagreement requiring a decision, `+` nothing exists yet.

A capability with `!` cannot be implemented by either repository until `[DEC-BOUNDARY]` and its
Seshat counterpart resolve it. Roadmap §14 rule 1 — one feature, one primary owning repository.

---

## A. Commercial platform

| Capability | Target owner | Today | Δ |
|---|---|---|---|
| Authentication, account lifecycle | Khepri | Neither. Excluded by `RRA.md`. | + |
| Organizations, membership, RBAC | Khepri | Neither. Excluded by `RRA.md`. | + |
| Customer workspaces | Khepri | Neither. Excluded by `RRA.md`. Seshat has `workspace_init.py` / `workspace_root.py`, which are *developer* workspaces, not customer tenancy — do not confuse them. | + |
| Beta session isolation | Khepri | Khepri `sessions.py`, `session_cookie.py` (RRA-001) | = |
| File upload, storage, deletion | Khepri | Khepri `intake.py`, `storage.py`, `deletion.py` (RRA-002) | = |
| Dataset versioning, retention, history | Khepri | Neither. Seven-day expiry, one dataset per session. | + |
| Mapping confirmation UX | Khepri | Khepri `mapping.py` (RRA-003) | = |
| Analysis-run orchestration, job reliability | Khepri | Khepri `jobs.py`, `job_persistence.py`, `worker.py`, `pipeline.py` (RRA-007) | = |
| Billing, quotas, entitlements | Khepri | Neither. Excluded by `RRA.md`. | + |
| Sharing, downloads, agency workflows | Khepri | Neither. Excluded by `RRA.md`. | + |
| Deployment target and environment | Khepri | **Blocked.** `KHEPRI-DEC-005` accepted and unfundable; `KHEPRI-DEC-008` proposed. | ! |

## B. Data acquisition and semantics

| Capability | Target owner | Today | Δ |
|---|---|---|---|
| CSV/XLSX parsing and admissibility | Khepri | Khepri `intake.py`, `admissibility.py` (RRA-002/003) | = |
| Column profiling | **Seshat** (§5.2 "reusable profiling contracts") | **Both.** Khepri `profiling.py` (RRA-003, approved, in production). Seshat `file_profile.py`, `profile.py`, spec 009. | ! |
| Semantic-role contracts | **Seshat** | **Both.** Khepri `mapping.py` (RRA-003). Seshat specs 008, 010, `semantic.py`, `kpi_contracts.py`. | ! |
| Business-meaning registry | Seshat | Seshat spec `008-business-meaning-registry` | = |
| Metric contract store | Seshat | Seshat spec `010-metric-contract-store`, `metric_contract_inventory.py` | = |
| Database snapshot acquisition | Seshat policy + Khepri lifecycle | Seshat `statistical/providers/gold.py` (PostgreSQL-only, read-only, count-checked, row/byte ceilinged). Khepri: none, and blocked by `KHEPRI-DEC-005:36`. | + |
| Credential handling | Khepri | Neither. No decision exists. | + |

**On rows B.2 and B.3.** The target column follows the roadmap; the recommendation does not.
Khepri's profiling and mapping are approved, shipped, and tested against real retail uploads;
Seshat's serve a medallion warehouse and a Power BI readiness spine. These are not the same
problem wearing two hats — they profile different things for different consumers. The
recommendation in `[DEC-BOUNDARY]` is to **leave both in place and forbid cross-porting**,
exactly as for the renderers (delta §G.2 option A), and to revisit only if a shared
`DatasetProfile` contract proves they can be unified without loss.

## C. Analysis and evidence

| Capability | Target owner | Today | Δ |
|---|---|---|---|
| Deterministic retail metrics (revenue, units, cost, gross profit, gross margin, discount, returns, ASP, +4) | **Khepri** — *recommended*, against §5.2 | Khepri `facts.py` (RRA-004, approved). Seshat: **none**. | ! |
| Growth decomposition | **Khepri** — *recommended* | Khepri `analysis/growth.py` (RRA-008). Seshat: none. | ! |
| Period comparison (PoP, YoY) | **Khepri** — *recommended* | Khepri `analysis/comparison.py`, `windows.py` (RRA-008). Seshat: none. | ! |
| Concentration and ranking | **Khepri** — *recommended* | Khepri `analysis/concentration.py` (RRA-008). Seshat: none. | ! |
| Basket analysis | **Khepri** — *recommended* | Khepri `analysis/basket.py` (RRA-008). Seshat: none. | ! |
| Comparable-store / like-for-like | Khepri | **Neither.** Named in `khepri-commercial-roadmap.md` Phase 3; absent from the master roadmap. | + |
| Descriptive statistics, group comparison, proportions | **Seshat** | Seshat `statistical/methods/{descriptive,groups,proportions}.py` | = |
| Correlation, regression | **Seshat** | Seshat `methods/{correlation,regression,inference}.py` | = |
| Anomaly and change-point detection | **Seshat** | Seshat `methods/{anomaly,changepoint,time_index}.py` | = |
| Forecasting | **Seshat**, and **not consumed by Khepri** | Seshat `methods/forecast.py`. `RRA.md` excludes forecasting from Khepri. | ! |
| Minimum-data floors and withholding | Seshat, for Seshat methods | Seshat `policy.py`, `contracts.py`. Khepri has its own (`prior_window_absent`, etc.). | = (parallel, by design) |
| Refusal policy | Split — see below | Khepri: 11 customer codes + 20 integrity codes. Seshat: `STAT_*` + five outcomes. No mapping. | ! |
| Method and formula versioning | Both, independently | Khepri `FORMULA_VERSION`, `PACKAGE_VERSION`. Seshat all methods `1.0`, `ENGINE_VERSION = "1.0"`. | = |
| Evidence and provenance | Split — see below | Khepri `Fact.citation_id`/`fact_id`/`FactPackage` digest. Seshat `AnalysisEvidence`, `authority: derived-evidence-only`. | ! |

**The rule this table encodes.** No metric appears with a working implementation in both
columns. That property holds today and is the one thing the boundary decision must protect —
it is cheap to keep and expensive to recover.

## D. Reporting and presentation

| Capability | Target owner | Today | Δ |
|---|---|---|---|
| `BusinessFinding` / `ReportPlan` / `BusinessReportModel` | Khepri | Neither. Phase 5 work. Khepri's `bundle.py` is the nearest existing structure. | + |
| Business-first information architecture | Khepri | Khepri `docs/reporting/` — drafted, awaiting approval | = |
| Presentation visibility matrix | Khepri | Khepri `docs/reporting/presentation-visibility-matrix.md` | = |
| Customer refusal presentation | Khepri | Khepri `docs/reporting/refusal-presentation.md` | = |
| HTML / PDF / Excel renderers for the **customer report** | Khepri | Khepri `rra/rendering/` (RRA-006, approved) | = |
| HTML / PDF / Excel renderers for **governed BI evidence** | Seshat | Seshat `src/seshat/report/` — ported from Khepri `7a1e3fd`, owner-approved 2026-08-03 | ! |
| Arabic/English business copy | Khepri | Khepri `narrative.py`, `wording.py` (RRA-005). Arabic human review outstanding. | = |
| Technical evidence appendix / audit layer | Khepri | Khepri `docs/reporting/` — designed, not implemented | = |
| Deterministic technical evidence rendering | Seshat, for its own evidence | Seshat `statistical/render.py`, `seshat analyze render` | = |

**Row D.6 is delta §G.2.** The recommended resolution is *two products, one prohibition*: each
renderer serves its own consumer, and neither may acquire arithmetic. Both already state this
in their own words — Khepri's `pdf.py`: "It presents figures; it never produces one"; Seshat's
design decision 1: "renderers only transcribe."

## E. AI

| Capability | Target owner | Today | Δ |
|---|---|---|---|
| Provider-neutral analyst interface | Khepri | Khepri `narrative.py:66` `Protocol` | = |
| Minimized evidence context | Khepri | Khepri `NarrativeRequest` — "exactly what a provider is sent, and nothing the package also holds" | = |
| Narrative validation, uncited-number refusal | Khepri | Khepri `narrative.py` (RRA-005) | = |
| Deterministic fallback | Khepri | Khepri `deterministic_narrative.py`; `KHEPRI-DEC-005:187` | = |
| Provider roster beyond OpenAI | Khepri | Only OpenAI, by `KHEPRI-DEC-005:97-119`. Adding one requires a DEC-005 supersession. | + |
| Analysis-proposal policy (which methods AI may propose) | **Seshat** | Neither. Seshat's catalog is closed but exposes no proposal surface. | + |
| Arabic/English contradiction detection | Khepri | Neither. | + |

## F. Governance

| Capability | Owner | Note |
|---|---|---|
| Khepri families, decisions, specifications, approvals, delegations | Khepri | `governance/`, `khepri-gov validate`, Constitution 1.1.0 |
| Seshat constitution, ADRs, spec ratification | Seshat | `.specify/memory/constitution.md` 1.7.0, `docs/decisions/`, `specs/` |
| **The shared boundary** | **Neither, today** | This is the gap. `[DEC-BOUNDARY]` + the Seshat boundary decision create it. |
| Contract schema versioning | Seshat produces, Khepri pins | Nothing exists. Blocked by the distribution gap (delta §E.3). |
| Compatibility manifest | Seshat produces, Khepri validates | Nothing exists. |

Neither governance system can approve an artifact in the other repository. A cross-repository
boundary therefore needs **two mirrored artifacts**, each approved under its own repository's
rules, each citing the other by commit. That is what the PR sequence enforces.

---

## G. Capabilities with no owner

Every row here must acquire an owner in Phase 0, or be recorded as deferred. Silence is the
failure mode §10's acceptance criteria exist to prevent.

| Capability | Recommended owner | Why |
|---|---|---|
| `DataSnapshot` normalization (file *and* database produce the same shape) | Seshat | §9's acceptance criterion — "the report pipeline does not know whether its DataSnapshot came from a file or database" — is a contract property, and contracts are Seshat's per §5.2. |
| `EngineCompatibilityManifest` | Seshat produces, Khepri validates and fails closed | §14 rule 7. |
| Reason-code ↔ customer-language mapping | Khepri | §7.1 — "customer-facing wording is not part of the analytical evidence contract." |
| Cross-snapshot time alignment | Seshat | §8 assigns cross-snapshot analytical methods to Seshat. |
| Schema-drift detection | Khepri | §8 assigns it to Khepri; Seshat's `drift.py`/`drift_semantics.py` serve warehouse sources, a different problem. |
| Distribution channel for the contract package | **Owner decision** | Delta §E.3. Nothing can be pinned until this is answered, and it is a commercial/operational choice, not a technical one. |
| Cost-per-report measurement | Khepri | §12. |
