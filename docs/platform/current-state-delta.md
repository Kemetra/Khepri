# Current-state delta: master roadmap versus both repositories

**Planning-only. Approves nothing.** Base commits: Khepri `c7d78b2`, Seshat-BI `157ef43`.

This reconciles `kemetra-analytics-platform-master-roadmap.md` against what the two
repositories actually contain. Roadmap §19.10 requires contradictions to be reported rather
than silently resolved; §G below is that report.

**Owner decisions taken 2026-08-05, after reading this report**, recorded here so §G is read
with its resolutions attached. Full table in [`README.md`](README.md).

| Contradiction | Resolution adopted |
|---|---|
| §G.1 Seshat owns no retail method | Deterministic retail stays **Khepri-authoritative**; transfer condition recorded, none proposed |
| §G.2 Duplicate renderers | **Option A** — two renderers, two products, closed; neither may acquire arithmetic |
| §G.3 DEC-012 misread | **Amend while `proposed`**, then accept; the amendment moves ahead of the boundary decisions |
| §G.4 Constitution III / `AGENTS.md` | **Qualify `AGENTS.md` to Seshat-Platform** in the DEC-013 package |
| §G.5 Forecasting | Boundary **does not carry forecast evidence**; a family amendment would come first |
| §G.6 Two disagreeing roadmaps | Deployment gate becomes **Phase 0 item 0**; integration deferred, so the two sequences no longer conflict |
| §G.7 `RRA.md` prose vs registry | Fixed in the charter package — **which is a renewal**, see §E.5 |

Whole-program consequence: **the Seshat integration is deferred past Milestones A and B.** The
boundary is settled now; nothing is built against it. §E.2, §E.3, and §C row 1 describe work
that is reserved rather than scheduled.

---

## A. Summary — the six findings that change the plan

| # | Finding | Consequence for the roadmap |
|---|---|---|
| 1 | Seshat-BI owns **no deterministic retail method**. Its closed catalog is eight *statistical* methods. | Phase 4's migration order starts with construction, not migration. The whole Phase 4 estimate is wrong in kind. |
| 2 | Seshat-BI **already ported Khepri's report renderers** into `src/seshat/report/`, owner-approved 2026-08-03. | §5.2 ("Seshat does not own the customer report's visual composition") is contradicted by shipped, approved code. |
| 3 | Phase 1's deliverables **already exist as a drafted design package** in `docs/reporting/`, awaiting owner approval. | Phase 1 is a single approval away from being an implementation phase, not a design phase. |
| 4 | Khepri has **no approvable deployment path**. `KHEPRI-DEC-005` is accepted and unfundable; `KHEPRI-DEC-008`, its replacement, is `proposed`. | Milestone A cannot be demonstrated regardless of everything else. The master roadmap has no phase for this. |
| 5 | `KHEPRI-DEC-012` is **`proposed`, not accepted**, and does not say what §10 Phase 0 item 3 says it says. | Amending it is free now and requires a supersession later. This reorders Phase 0. |
| 6 | Seshat-BI permits **at most one spec in implementation at a time** (spec 138 FR-026); 138 is ratified and active. | No Seshat headless-engine spec can enter implementation until 138 closes. Hard external sequencing constraint. |

---

## B. Already built

### B.1 Khepri

Registry state: families `FND` and `RRA` both `active`; specifications `FND-001` `verified`,
`FND-002`/`FND-003` `implemented`, `RRA-001` through `RRA-008` all `approved`.

| Roadmap expectation | Where it exists |
|---|---|
| §4.1 CSV/XLSX intake and validation | `src/khepri/rra/intake.py`, `admissibility.py` (RRA-002, RRA-003) |
| §4.1 Profiling and retail semantic mapping | `profiling.py`, `mapping.py` (RRA-003) |
| §4.1 Deterministic fact packages | `facts.py`, `aggregates.py`, `packages.py` (RRA-004) — twelve governed metrics, `Decimal` arithmetic, `PACKAGE_VERSION` and `FORMULA_VERSION` as hash inputs |
| §4.1 Comparative retail analyses | `analysis/comparison.py`, `concentration.py`, `growth.py`, `basket.py`, `windows.py` (RRA-008) |
| §4.1 Grounded Arabic/English narrative | `narrative.py`, `deterministic_narrative.py` (RRA-005) |
| §4.1 Unified web/PDF/Excel | `rendering/{html,pdf,excel,charts,chromium,fonts,wording}.py` (RRA-006) |
| §4.1 Refusal, reconciliation, provenance, job reliability | `bundle.py`, `jobs.py`, `job_persistence.py`, `worker.py`, `stage_telemetry.py` (RRA-007) |
| **§7.1 Decimal-string financial truth** | Built and stricter than the roadmap asks. `KHEPRI-DEC-008` forbids binary floating point as an authoritative fact; `excel.py` writes every cell through `write_string` so money never round-trips through IEEE 754. |
| **§7.1 Every result carries an evidence reference** | `Fact.citation_id`, `fact_id`, `FactPackage` digest; `bundle.reconcile` compares claimed and actual figure sets for equality. |
| **§9.3 Provider-neutral analyst interface** | `narrative.py:66` defines a `Protocol`; `NarrativeRequest` is the minimized context and carries no raw rows; `ProviderRefused`/`NarrativeUnavailable` are raised only by adapters. |
| **§9.1/§6 AI never authors numbers** | `narrative.py:47-51` fixes percent rendering in `Decimal` upstream so "the provider never" sees a number it could restate. Unsupported numerical prose is refused, not corrected. |
| **§6 Deterministic fallback on provider outage** | `deterministic_narrative.py`; `KHEPRI-DEC-005:187` — "report availability never depends on" the provider. |
| **§15.5 Content-free operational evidence** | `OperationalEvent` carries only opaque identifiers, content addresses, stage names, durations, and size bands (RRA-007). |

Phase 6's acceptance criteria are, with one exception, already met by shipped Khepri code.
The exception is Arabic/English contradiction detection across the same evidence.

### B.2 Seshat-BI

| Roadmap expectation | Where it exists |
|---|---|
| §4.2 Governed statistical evidence engine, closed method families | `src/seshat/statistical/` — `contracts.py`, `policy.py`, `evidence.py`, `registry.py`, `runtime.py`, `render.py`, `schema.py`, `query.py`, `methods/`, `providers/` |
| §4.2 `computed` / `withheld` / `refused` / `unavailable` / `failed` | `Outcome`; categorical exit codes 0–4 |
| §3 Phase 3 "no arbitrary executable method registration" | Eight methods, all version `1.0`, closed by schema. "No method accepts arbitrary Python, formulas, SQL, model names, or dynamically loaded callables." |
| §3 Phase 3 "minimum-data checks produce `withheld`" | `minimum_data.observations` / `groups` / `seasonal_cycles` declared per specification; method-specific floors enforced |
| §3 Phase 3 "evidence contains no raw customer row payload" | Local CSV provider "records a content digest instead of a local path or row payload"; Gold provider "never exposes connection details or raw rows in evidence" |
| §9.2 No association-to-causation promotion | Correlation and regression "always retain the association-not-causation boundary" |
| §9 Prior-only time methods | Anomaly baselines exclude the observation; rolling-origin never trains on future values; partial final periods must be declared |
| §4.2 Business meaning registries, metric contracts | specs `008-business-meaning-registry`, `010-metric-contract-store`, `src/seshat/kpi_contracts.py`, `metric_contract_inventory.py` |
| §4.2 Source profiling and mapping workflows | `file_profile.py`, `profile.py`, `semantic.py`, spec `009-grain-confidence-reviewer` |
| §4.2 dbt / Dagster / Power BI capability, separate from Khepri | `src/seshat/dbt`, `src/seshat/dagster_adapter`, `pbir_*`, specs 023, 024, 133, 134, 135 |
| §4.2 Dependency isolation of the numerical stack | `statistical/__init__.py` — "Importing this package keeps every optional numerical dependency unloaded" |

Seshat's authority model is stronger than the roadmap describes. ADR-0008 defines a closed
five-category taxonomy in which **only Core Authority creates truth or grants approval**, and
the statistical core is declared a Product Module whose evidence records
`authority: derived-evidence-only`, `review_state: pending`,
`readiness_effect: none; named-human approval required`. Roadmap §19.9 requires that this not
be weakened; nothing in the target architecture proposed here touches it.

### B.3 Phase 1, already drafted

`docs/reporting/` (Khepri, merged 2026-08-04 as PR #96) contains equivalents of six of
Phase 1's eight deliverables and is explicitly "draft, awaiting owner approval of the golden
sample."

| Phase 1 deliverable | Status |
|---|---|
| 1. Presentation visibility matrix | `docs/reporting/presentation-visibility-matrix.md` |
| 2. Business report information architecture | `docs/reporting/business-report-information-architecture.md` |
| 3. Refusal and limitation presentation contract | `docs/reporting/refusal-presentation.md` — five-part contract, 11 distinct codes in 13 contexts |
| 4. Fictional retail dataset | "Al Rahma Trading Co.", January–July 2026 |
| 5/6/7. Golden HTML / PDF / Excel | `docs/reporting/golden-sample/*.html`, `*.pdf`, `*.xlsx` — 9 business sections + Technical Evidence; 8-page PDF with appendix; 12-sheet workbook ending in Audit Trail and Provenance |
| 8. Arabic and English copy review | **Not done.** A bilingual sample exists; no human Arabic review is recorded. |

The separation rule is mechanically verified, not asserted:
`docs/reporting/golden-sample/verify_separation.py` reports 0 identifiers in the nine
business worksheets, 0 in the HTML business region, 47/46 in the audit regions, 0
Eastern-Arabic numerals, 0 hidden worksheets, and 6/6 PDF publication guards.

Two of the master roadmap's Phase 1 acceptance criteria are therefore already evidenced.
Two are not: the Arabic review, and owner approval itself.

---

## C. Partially built

| Capability | Built | Missing |
|---|---|---|
| **Seshat headless Python API** (Phase 3) | `statistical/__init__.py` exports a dependency-free contract surface (`AnalysisSpec`, `AnalysisEvidence`, `Outcome`, `Estimate`, `Interval`, `Blocker`, `Diagnostic`) with `ENGINE_VERSION = "1.0"`. Only two internal importers — `cli/commands/analyze.py` and `statistical/registry.py` — so the coupling is narrow and factorable. | `run_analysis(repo_root: Path, spec, provider)` takes a repository root. `evaluate_policy(repo_root, spec)` reads `readiness-status`, metric contracts, and PII evidence off the working set. Phase 3's constraints "No repository-root lock requirement" and "No readiness approval side effects" are **not met**. This is the single largest Seshat work item. |
| **Khepri commercial family** (Phase 0, Phase 7) | Named and shaped in `docs/khepri-commercial-roadmap.md` as **RCA — Retail Commercial Analysis** (a proposed code, not an allocated one), `depends_on: [FND, RRA]`, with the required simultaneous re-scope of `RRA.md`'s Excludes. | Not drafted, not registered, not approved. |
| **Deployment path** | `KHEPRI-DEC-008` fully drafted: provider-neutral capability contract, sizing rules, ~178 USD/mo AWS or 174–235 USD/mo DigitalOcean. | `proposed`. Blocks everything downstream (§E.1). |
| **AI provider roster** (§9.3) | The abstraction exists (§B.1). | Only OpenAI is named, by `KHEPRI-DEC-005:97-119`. `DeepSeekAnalyst`, `QwenAnalyst`, `LocalAnalyst` each require a DEC-005 supersession — that decision states that changing providers requires one. |
| **Cross-language narrative parity** (§6) | RRA-005 produces both languages from one grounded evidence set. | No test asserts that the same evidence cannot be narrated with contradictory directions. |
| **Seshat retail pack** (§5.2) | `packs/` and `src/seshat/packs/` exist with catalog, loader, validator, registry. | The packs hold Power BI and readiness reference content. There is **no retail analytical method pack**. |

---

## D. Duplicated

Roadmap §5.3 prohibits "copying the same authoritative calculation into both repositories,"
and §17 names divergent metrics as the first risk. Six duplications exist today. Only the
first is a governed, deliberate decision — which makes it the hardest to unwind.

| # | Duplication | Khepri | Seshat-BI | Severity |
|---|---|---|---|---|
| 1 | **Report renderers** | `src/khepri/rra/rendering/{html,pdf,excel,charts,chromium,fonts}.py` (RRA-006, approved) | `src/seshat/report/{html,pdf,excel,charts,chromium,layout,model}.py` — headers read "PORTED from `Khepri/src/khepri/rra/rendering/…` at commit `7a1e3fd`" | **Critical.** Owner-approved on the Seshat side 2026-08-03, with "shared package across both repos" explicitly rejected as the alternative. |
| 2 | **Cited-figure / bundle model** | `rra/bundle.py` — `CitedFigure`, figure/caveat/section sets | `report/model.py` — "Ported from `Khepri/src/khepri/rra/bundle.py`" | **Critical.** This is the evidence vocabulary §7 wants to make one shared contract. It now has two independent copies. |
| 3 | **Source profiling** | `rra/profiling.py` (RRA-003) | `file_profile.py`, `profile.py`, spec `009` | High. §5.2 assigns profiling contracts to Seshat; the working implementation is Khepri's. |
| 4 | **Semantic mapping** | `rra/mapping.py` (RRA-003) | source-map workflow, specs `008`, `010` | High. Same conflict, plus different confirmation UX assumptions. |
| 5 | **Refusal vocabularies** | 11 distinct customer-facing codes in 13 contexts, plus 20 bundle-integrity `GOVERNED_REASONS` | `STAT_*` diagnostic codes plus the five-value `Outcome` | Medium. No mapping exists in either direction; §8.3's customer contract has no Seshat-side source. |
| 6 | **Chromium PDF rendering** | `rendering/chromium.py` | `report/chromium.py` — "Ported in spirit" | Medium. Two browser-driving surfaces, two sets of publication guards. |

**Duplication 1 and 2 are the reconciliation this planning pass exists to force.** They were
created two days before the master roadmap was written, by an approved Seshat design decision
that had no visibility into it. Neither repository is at fault; the two governance systems have
never had a shared boundary artifact. That artifact is `[DEC-BOUNDARY]` (§F).

---

## E. Missing in both repositories

### E.1 The deployment gate — missing from the roadmap itself

`KHEPRI-DEC-005` is `accepted` and names AWS `me-central-1`, which `KHEPRI-DEC-008` prices at
~675 USD/month and records the owner cannot fund. `KHEPRI-DEC-008` replaces it with a
provider-neutral capability contract and is `proposed`. The fail-closed chain is: no accepted
DEC-008 → no approved target-selection artifact → no deployment definition → no environment →
no `KHEPRI-DEC-006` benchmark evidence → no beta authorization.

**Milestone A ("a realistic uploaded retail file is analyzed … Khepri generates an approved
business-first report") cannot be demonstrated to any customer until this clears**, and the
master roadmap contains no phase for it. It must become Phase 0's first item.

`KHEPRI-DEC-005` also carries a stale closing sentence — "This decision remains proposed until
its registry entry contains explicit approval evidence" — against a registry recording
`state: accepted`. It cannot be fixed as housekeeping: `APP-013.yaml` binds the document by
`document_sha256`, and `khepri-gov validate` fails closed on any edit. Correcting it requires a
renewal approval package.

### E.2 Every shared contract in §7

None of the thirteen named contract families exists as a cross-repository artifact.
Seshat's `AnalysisSpec` and `AnalysisEvidence` are the nearest equivalents and are
Seshat-internal, repo-root bound, and statistically shaped. Specifically absent:

`DatasetProfile` · `DataSnapshot` · `SemanticRole` · `SemanticMapping` ·
`MetricContractReference` · `AnalysisRequest` · `AnalysisResult` · `AnalysisLimitation` ·
`EvidenceReference` · `EvidenceBundle` · `AuditManifest` · `EngineCompatibilityManifest`

Also absent: shared fixtures, producer contract tests, consumer contract tests, a version
negotiation rule, and a fail-closed path for an unknown contract version.

### E.3 Distribution — the precondition §14 rule 5 assumes

Rule 5 says "Khepri pins an approved Seshat release/version." **There is nothing to pin.**
Seshat-BI is not published to any package index (`KHEPRI-DEC-012:74`). Until a distribution
channel exists — index, private index, git tag, or vendored contract package — the dependency
direction in §5.3 is undeliverable in any form Khepri's `pyproject.toml` can express.

Secondary: Seshat declares `requires-python >=3.13`, Khepri `>=3.13,<3.14`. Compatible today,
unpinned, and one Seshat release away from not being.

> **Resolved 2026-08-05: no package.** Contracts are exchanged as **committed schema and
> fixture files**, cross-validated in each repository's own CI. That is what §14 rule 4 asks
> for — "shared by committed schema/example artifacts, not copied prose" — and it meets §2's
> acceptance criterion without publishing anything or pinning anything. Since the integration
> is also deferred, no dependency is declared and the `requires-python` overlap stops mattering
> until it is revived.

### E.5 The `RRA.md` renewal — found after this report was first written

`governance/families/RRA.md` is pinned by `APP-002.yaml` as
`sha256:8a1235a0d6b9e36a6446a1e1cfd3f7ef5db52ca7d9e0ed23bcffb18eded095d2`, and the file hashes
to exactly that today.

Every edit to it — the commercial re-scope (§F), the prose/registry correction (§G.7), and the
two lapsed-clause notes — therefore requires a **renewal approval package**
(`src/khepri_gov/approval_renewals.py`), not an ordinary edit. Attempting it as an edit fails
`khepri-gov validate` closed, exactly as the `KHEPRI-DEC-005` attempt did.

`APP-002` also pins `KHEPRI-DEC-002`, `-003`, `-004`, and `RRA-001` through `RRA-007`. So
`[DEC-COMMERCIAL]`'s supersession of DEC-003 must be recorded **in the registry**, never by adding
a `superseded_by` note to the pinned document body.

This raises the cost of the commercial charter and is the second reason the report layer should
sit under `RRA` as `[SPEC-REPORT]` rather than behind that charter.

### E.4 Product capability gaps

| Missing | Note |
|---|---|
| Comparable-store / like-for-like sales | Recorded in `docs/khepri-commercial-roadmap.md` Phase 3 as the metric mid-market retail buyers read *first*. **Absent from the master roadmap entirely.** Needs branch-level revenue across two comparable periods and a new governed refusal (`comparable_set_insufficient`). |
| Arabic business copy review | Phase 1 deliverable 8. |
| Cross-dataset digesting | §8's "cross-dataset evidence digests all contributing inputs." No durable store exists to digest across. |
| Generated fact/formula/citation catalog | `KHEPRI-DEC-012:202-205` names it as the one dbt discipline Khepri lacks, achievable without dbt, and plausibly customer-facing. |

---

## F. Blocked by governance

| Roadmap phase | Blocked by |
|---|---|
| 7 (identity, orgs, workspaces), 10 (billing, quotas, signup), 11 (agency, white labeling) | `governance/families/RRA.md` **Excludes** names every one: commercial authentication, user profiles, persistent customer workspaces, organizations, membership roles, billing, subscriptions, scheduling, public signup, agency portfolios, client switching, delegated access, work queues, white labeling. No family owns them. `AGENTS.md` forbids implementing ahead of an approved specification. |
| 8 (multi-dataset accumulation) | `RRA.md` excludes persistent customer workspaces; `KHEPRI-DEC-005:36` excludes a data warehouse. |
| 9 (database adapters) | `KHEPRI-DEC-005:36` stack clause; RRA-002's intake boundary; no credential-handling decision exists. |
| 12 (scheduled refresh) | `RRA.md` excludes `scheduling`. |
| **All of the above** | Blocked *behind* §E.1. |
| Any new Seshat implementation | `Seshat-BI/CLAUDE.md`: spec 138 is RATIFIED and in implementation, spec 137 awaits ratification, and **"At most ONE of the two may be in implementation at a time (spec 138 FR-026)"**. A Seshat headless-engine specification can be written and ratified but cannot enter implementation until 138 closes. |

`RRA.md`'s exclusions are written as flat prohibitions. Once a commercial family owns billing,
"billing is excluded" becomes ambiguous between excluded-from-RRA and excluded-from-Khepri,
which Constitution I forbids. `FND.md` already solves this correctly by excluding
"responsibilities of future product families." `RRA.md` must adopt that phrasing **in the same
approval package** that charters the commercial family, so no moment exists where both
documents claim the same capability.

---

## G. Contradicted by an existing decision

Reported per §19.10 rather than resolved. Each row states the recommended resolution; none is
adopted here.

### G.1 Seshat does not own deterministic retail methods

§4.2 and §5.2 assign "deterministic and statistical calculations" and "reusable retail
analytical packs" to Seshat. Seshat's closed catalog is eight statistical methods. There is no
retail metric, no revenue, no margin, no growth decomposition, no concentration curve, no
basket analysis. Those are Khepri's, in `facts.py` and `analysis/`, under **approved** spec
RRA-004 and RRA-008.

**Consequence:** Phase 4's recommended migration order — "1. Existing deterministic retail
metrics that have clear parity fixtures" — describes moving approved, tested Khepri code into a
repository that has never held it. That is not a migration with a parity oracle on both sides;
it is construction in Seshat plus deprecation in Khepri, and the parity fixture is Khepri's
current output.

**Recommended resolution:** state explicitly in `[DEC-BOUNDARY]` that deterministic retail
methods remain Khepri-authoritative for the first commercial release, and that Seshat's
analytical ownership begins with *statistical* methods Khepri does not have. Revisit only when
a parity fixture exists on both sides. This inverts §5.1's "Khepri must not independently
recalculate figures already owned by the Seshat analytical engine" from a rule into a
condition: Khepri may not recalculate what Seshat owns, and Seshat does not yet own these.

### G.2 Seshat already owns a report renderer

§5.2: "Seshat does not own … the customer report's visual composition."
Seshat-BI `docs/superpowers/specs/2026-08-03-report-surfaces-design.md`, **status "approved by
owner"**, decision 2: "**Port** Khepri's `rra/rendering` into Seshat with provenance headers,"
rejecting "Shared package across both repos; or reimplement." Shipped as
`src/seshat/report/`.

**This is the sharpest contradiction in the package**, because both sides are correct in their
own frame: Seshat's clients need a board document without a Power BI licence, and its design
correctly refused to let each format query gold independently. The roadmap and that decision
were written two days apart with no shared boundary artifact.

**Recommended resolution — three options, one recommended:**

| Option | Shape | Cost |
|---|---|---|
| **A (recommended)** | Declare the two renderers **serving different products** and record it. Seshat's renders governed BI evidence for Power-BI-adjacent clients; Khepri's renders the commercial customer report. Neither imports the other. Both repositories record the divergence as intentional and forbid cross-porting *back*. | Cheapest. Honest. Accepts permanent parallel maintenance of ~7 modules. |
| B | Extract the renderer to a shared package. | Forbidden by §19.4 until contract ownership and release strategy are approved, and Seshat's own design already rejected it. Requires the distribution channel §E.3 says does not exist. |
| C | Remove one. | Removing Seshat's discards an owner-approved capability shipped two days ago. Removing Khepri's discards RRA-006, an approved specification with ~170 test references. |

Option A is recommended because the duplication's real cost is *divergent numbers*, and neither
renderer computes anything — Khepri's `pdf.py` states "It presents figures; it never produces
one," and Seshat's decision 1 is "Numbers come from one upstream bundle; renderers only
transcribe." Two transcribers of two different bundles are not a correctness risk. Two
*calculators* would be, and that is what §D.2 (the ported `CitedFigure` model) risks becoming
if either side ever adds arithmetic. The decision must say so.

### G.3 `KHEPRI-DEC-012` does not say what §10 Phase 0 item 3 says

Item 3 asks for "amendment or supersession of any proposed Khepri decision that currently
rejects all cross-repository dependencies without distinguishing headless analytical contracts
from dbt/Dagster/Power BI dependencies."

`KHEPRI-DEC-012` rejects **dbt and Dagster adoption into Khepri**, on named evidence: no
warehouse to compile against, `KHEPRI-DEC-005:36` excluding a data warehouse and a microservice
boundary, and Khepri's job layer already providing every Dagster capability it needs. Its
statement "No cross-repository dependency is created in either direction" appears in
*Consequences*, as an observation about what that refusal does — not as a general prohibition.
It never considered a headless analytical contract, because none was proposed.

It also records the co-installation evidence that still binds: Seshat-BI is not on a package
index, pins `dbt-core==1.12.0` against Khepri's `jinja2>=3.1,<4`, declares `requires-python
>=3.13` against Khepri's `>=3.13,<3.14`, and Khepri's `pyproject.toml` excludes
`src/khepri/local` from the wheel with a written rationale about what belongs in the image that
runs web and worker.

**Two corrections follow.**

1. **It is `proposed`, not accepted.** Its own closing line: "While it remains `proposed` it is
   reasoning on the record, not authority." Amending it today is an edit to an unaccepted
   draft. After acceptance it needs a supersession. **Amend before accepting.** This reorders
   Phase 0: the DEC-012 amendment must land *before* the DEC-012 acceptance, not after.
2. **The amendment is narrow.** The needed carve-out is one clause distinguishing (a) a
   tooling *runtime* dependency — a dbt binary, a Dagster interpreter, a Seshat workspace
   checkout — which stays refused on the evidence above, from (b) a *contract* dependency on a
   versioned, published, headless analytical package, which is a separate question DEC-012 did
   not decide. Draft in `proposed-governance/`.

### G.4 Constitution III names a different repository

§5.3's `Khepri -> Seshat` dependency runs against Constitution III at first reading. It does
not, on inspection: Article III names
`Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` — a **distinct repository**
from `Kemetra/Seshat-BI`, verified by remote (`Seshat-Platform` is the predecessor; its local
clone's only remote is `Kemetra/Khepri`).

But `AGENTS.md` writes the rule unqualified — "Do not copy Seshat catalogs, specifications,
proposals, ledgers, governance records, or **application code**" — immediately after a line
that scopes the preceding rule to Seshat-Platform. Read across both repositories, that
sentence already prohibits the port described in §G.2, in the reverse direction.

**Recommended resolution:** `[DEC-BOUNDARY]` must state the distinction explicitly, and the
`AGENTS.md` line must be qualified in the same package. Leaving it ambiguous means either the
Seshat port is a standing violation or the rule means nothing — and both readings are available
today.

### G.5 Forecasting

Seshat ships a governed `forecast` method with rolling-origin evaluation, MASE/sMAPE, and
partial-period policy. `RRA.md` **Excludes** forecasting from Khepri, and
`docs/khepri-commercial-roadmap.md` recommends it stay excluded in the commercial charter —
"where a defensibility product goes to die."

Consuming Seshat forecast evidence through the analytical boundary would import an excluded
capability without amending the family that excludes it. `[DEC-BOUNDARY]` must state whether
the boundary passes forecast evidence through, and the default answer should be no.

### G.6 The master roadmap and Khepri's own roadmap disagree on sequence

`docs/khepri-commercial-roadmap.md` (2026-08-04, advisory) sequences 0A-gov → 0A-spend → 0B →
0C → 1 … 7 and contains **no Seshat dependency at any phase**. The master roadmap sequences
0 → 1 … 12 with Seshat integration at Phases 2–4 and no deployment phase at all.

They agree on: business-first reporting first, then identity, then multi-dataset, then
commercial, then agency, then recurring delivery. They disagree on two things that matter:

- the master roadmap omits the deployment gate (§E.1) and the prospect-validation phase 0C;
- the Khepri roadmap omits Seshat entirely.

**Recommended resolution:** treat the master roadmap as the cross-repository layer and
`khepri-commercial-roadmap.md` as the Khepri-internal layer, and reconcile them in one pass
after `[DEC-BOUNDARY]` is decided. Do not leave two advisory roadmaps disagreeing on sequence.

### G.7 Registry/prose mismatch in `RRA.md`

`governance/registries/families.yaml` records `RRA` as `state: active`, approved 2026-07-29
under `APP-002`. `governance/families/RRA.md` closes with "The family is proposed."

Constitution I settles it — the registry wins — but the prose is wrong and a reader may act on
it. Fix it in whichever approval package next touches `RRA.md`, which is the commercial-family
charter (§F). Note the digest hazard: check whether an approval package binds `RRA.md` by
`document_sha256` before editing, as `APP-013` does for `KHEPRI-DEC-005`.

---

## H. What is already true that the roadmap can simply adopt

Not every delta is a gap. These are stronger than the roadmap requires and should be cited
rather than re-specified:

- **Khepri's numerical contract exceeds §15.1.** `facts.py` versions the *number*, not just the
  method: `FORMULA_VERSION` is both a field and a hash input.
- **Khepri's reconciliation is deliberately redundant.** `aggregates.reconciles`,
  `bundle.reconcile`, and `pipeline._require_one_bundle_behind_every_surface`, plus database
  `CheckConstraint`s.
- **Khepri's pipeline linearity is a safety property, not debt.** `KHEPRI-DEC-012:28-34`
  derives it: a per-stage *retry* would re-enter a stage under a lease whose loss could not
  have been observed. §6's architecture must not be read as licence to make it a graph.
- **Seshat's evidence carries an authority disclaimer by construction** —
  `authority: derived-evidence-only`, `review_state: pending`,
  `readiness_effect: none; named-human approval required`. §19.9 requires this survive; the
  proposed boundary preserves it verbatim.
- **Both repositories already refuse arbitrary execution.** Khepri has no user-authored formula
  path; Seshat's catalog is closed by schema. §16's non-goal is met today, not aspirationally.
