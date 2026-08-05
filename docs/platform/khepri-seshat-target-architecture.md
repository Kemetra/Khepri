# Khepri / Seshat-BI target architecture

**Planning-only. Approves nothing.** Base commits: Khepri `c7d78b2`, Seshat-BI `157ef43`.

This is the architecture the boundary decision would authorize, stated so that both
repositories can test their half independently. It is deliberately narrower than roadmap §6,
for reasons the delta report records.

---

## 1. The one-sentence boundary

> Khepri owns the customer, the deterministic retail numbers, and the report.
> Seshat owns statistical inference Khepri does not have, and emits evidence about it.
> Neither imports the other's runtime.

Roadmap §20 states it as "Seshat determines what the evidence supports; Khepri turns that
evidence into a product." That is the *end state*. It is not the first state, because Seshat
holds no retail method today (delta §G.1), and stating it as the first state would authorize
moving approved, tested Khepri code into a repository with no parity oracle.

## 2. What changes, and what does not

```text
                        TODAY                          TARGET (first release)
   +----------------------------+          +----------------------------+
   | KHEPRI                     |          | KHEPRI                     |
   |  intake, profile, map      |          |  intake, profile, map      |
   |  deterministic retail      |          |  deterministic retail      |  <- unchanged,
   |  narrative, render         |          |  narrative, render         |     authoritative
   |  jobs, telemetry           |          |  jobs, telemetry           |
   +----------------------------+          +-------------+--------------+
                                                         |
                                                         | AnalysisRequest
   +----------------------------+                        v   (optional, versioned)
   | SESHAT-BI                  |          +----------------------------+
   |  statistical engine        |          | SESHAT-BI                  |
   |    (repo-root bound)       |          |  statistical engine        |
   |  readiness spine           |          |    headless facade         |  <- the only
   |  dbt / dagster / powerbi   |          |  readiness spine           |     new surface
   |  report renderers          |          |  dbt / dagster / powerbi   |
   +----------------------------+          |  report renderers          |
                                           +-------------+--------------+
                                                         |
                                                         | EvidenceBundle
                                                         v
                                           +----------------------------+
                                           | KHEPRI report layer        |
                                           |  BusinessFinding           |
                                           |  ReportPlan                |
                                           |  BusinessReportModel       |
                                           |  HTML | PDF | Excel        |
                                           |  + separate audit evidence |
                                           +----------------------------+
```

**Unchanged in Khepri:** every approved RRA specification, the `Decimal` fact contract,
`FORMULA_VERSION` hashing, the four-stage linear pipeline (`KHEPRI-DEC-012:28-34` derives its
linearity as a lease-safety property — the target architecture must not be read as licence to
make it a graph), content-free telemetry, and the reconcile triad.

**Unchanged in Seshat:** the five-category authority taxonomy (ADR-0008), the readiness spine,
`authority: derived-evidence-only`, named-human approval, the closed method catalog, and every
adapter. The headless facade is *additive*.

**Added:** one facade in Seshat, one adapter and one consumer in Khepri, and a shared contract
package. Nothing is moved, deleted, or reimplemented in this release.

## 3. The seven seams

Each is independently specifiable, testable, and reversible.

| # | Seam | Owner | Precondition |
|---|---|---|---|
| S1 | **Headless facade** — `run_analysis` without a repository root | Seshat | Seshat spec 138 closes |
| S2 | **Policy injection** — governance inputs passed in, not read off disk | Seshat | S1 |
| S3 | **Contract package** — the versioned schemas both sides validate | Seshat produces | Distribution answered |
| S4 | **Compatibility manifest** — engine ↔ contract version negotiation | Seshat produces, Khepri validates | S3 |
| S5 | **Request adapter** — Khepri `FactPackage` → `AnalysisRequest` | Khepri | S3 |
| S6 | **Evidence consumer** — `EvidenceBundle` → `BusinessFinding` | Khepri | S3, S4 |
| S7 | **Reason-code presentation map** — Seshat codes → Khepri customer language | Khepri | S3, and the approved `refusal-presentation.md` |

### S1 — the headless facade

The blocking fact, verified at `157ef43`:

```python
# src/seshat/statistical/runtime.py:399
def run_analysis(repo_root: Path, spec: AnalysisSpec, provider: DataProvider) -> ...
# src/seshat/statistical/policy.py:284
def evaluate_policy(repo_root: Path, spec: AnalysisSpec) -> PolicyDecision
```

`evaluate_policy` reads `readiness-status`, metric contracts, and PII evidence off the working
set (`policy.py:59-117`). Phase 3's constraints "No repository-root lock requirement" and "No
readiness approval side effects" are therefore unmet.

**Two facts make this tractable.** First, `statistical/__init__.py` already exposes a
dependency-free contract surface with `ENGINE_VERSION = "1.0"` and keeps every numerical
dependency unloaded on import. Second, only two modules import `statistical` — 
`cli/commands/analyze.py` and `statistical/registry.py` — so the CLI is the *only* consumer that
supplies a repo root.

**Shape:** invert the read. `evaluate_policy` takes an already-materialized
`GovernanceContext` (contracts, readiness states, PII evidence) instead of a `Path`. The CLI
gains a thin loader that builds that context from the repo, preserving today's behaviour
byte-for-byte. A headless caller constructs it from the request. No policy rule changes; only
where its inputs come from.

**What this must not do:** it must not let a caller *assert* readiness. The context carries
evidence to be evaluated, never a verdict. ADR-0008 gives grant-approval to Core Authority
alone, and roadmap §19.9 requires that survive.

### S2 — policy injection

Follows from S1. Called out separately because it is the row where a headless boundary could
quietly become an approval bypass, and it needs its own adversarial tests: a request that
claims readiness must be `refused`, not honoured.

### S3 — the contract package

The thirteen families in §7 do not exist (delta §E.2). Seshat's `AnalysisSpec` and
`AnalysisEvidence` are the seed; they are statistically shaped and would need generalizing.

**Rules, from §7.1, that must be tested rather than asserted:**

- money and exact financial quantities serialize as **decimal strings**;
- every published result carries at least one evidence reference;
- every method and formula carries a version;
- every bundle carries an input or snapshot digest;
- every limitation is structured and machine-readable;
- an unknown contract version **fails closed** on the consumer side;
- contract schema versions are independent of package release versions;
- no customer-facing prose is required for contract validity.

**Distribution — decided 2026-08-05: committed fixtures, no package.**

Roadmap §14 rule 5 says "Khepri pins an approved Seshat release," and Seshat is on no package
index, so there is nothing to pin. Rather than manufacture a release channel for a deferred
integration, contracts are exchanged as **committed schema and fixture files**, validated
independently by each repository's own CI.

That is exactly what §14 rule 4 asks for — "compatibility fixtures are shared by committed
schema/example artifacts, not copied prose" — and it satisfies roadmap §2's acceptance
criterion in full: both repositories validate the same fixtures, decimal precision round-trips
exactly, an unknown version fails closed.

If the integration is later revived, the option kept open is a **contracts-only package**
(schemas, fixtures, validators, no numerical code), which makes the graph
`Khepri → contracts ← Seshat` and trips none of the co-installation evidence
`KHEPRI-DEC-012:196-201` records. Publishing all of `seshat-bi` is not an option — it
re-imports the `dbt-core==1.12.0` / `jinja2` conflict and the `requires-python` mismatch.

### S4 — compatibility manifest

Khepri pins an engine version *and* a contract version. On mismatch it refuses the analysis and
delivers the deterministic report — the same fail-closed shape `KHEPRI-DEC-005:187` already
uses for the narrative provider, which is the precedent to follow rather than invent.

### S5 — request adapter

Khepri-side, pure. `FactPackage` + `SemanticMapping` → `AnalysisRequest`. No network, no
Seshat import beyond the contract package. Fully testable against committed fixtures.

### S6 — evidence consumer

`EvidenceBundle` → `BusinessFinding`. The one hard rule: **the consumer may not compute.** It
transcribes evidence into findings and attaches materiality; any arithmetic here recreates the
divergent-metric risk the whole boundary exists to prevent. Khepri already enforces the
equivalent for renderers; the same test shape applies.

### S7 — reason-code presentation map

Seshat outcomes (`withheld`, `refused`, `unavailable`, `failed`) and `STAT_*` diagnostics must
reach a customer through the five-part contract in
`docs/reporting/refusal-presentation.md` §D: what was not produced, why, whether the rest
remains valid, what is missing, how to unlock it. The raw code stays in the audit layer
(§8.3). This is a Khepri-owned table, complete at import — `wording.py:149-151` raises on a
missing code by design, and a `KeyError` in a renderer is caught as `REASON_SURFACE_FAILED`,
so an incomplete table means no report at all.

## 4. Prohibited, restated with today's evidence

```text
Seshat -> Khepri                                    (no import, no reference, no test dependency)
Khepri -> Seshat CLI                                (`seshat analyze` is not an API)
Khepri -> Seshat repo checkout / workspace root     (`workspace_root.py` is not a runtime input)
Khepri -> Seshat readiness state machine
Khepri -> Seshat dbt / Dagster / Power BI runtime   (KHEPRI-DEC-012, on its own evidence)
Khepri -> Seshat forecast evidence                  (RRA.md excludes forecasting)
Either -> a second copy of an authoritative calculation
Either -> porting the other's renderer again        (the existing port is grandfathered, not a precedent)
```

The last two lines are the ones current state violates or nearly violates. They are the
prohibitions worth writing down.

## 5. Staging

**Owner decision, 2026-08-05: stage 0 and stage 4 proceed; stages 1–3 are deferred past
Milestones A and B.** The boundary is settled now; the integration is not built now.

| Stage | Contains | Status | Gate |
|---|---|---|---|
| **0** | `KHEPRI-DEC-008` acceptance → `KHEPRI-DEC-012` amendment → `[DEC-BOUNDARY]` → the Seshat boundary decision → commercial family charter | **Proceeds** | Owner approval in each repository |
| **4** | Report engine on the approved golden sample (`[SPEC-REPORT]`) | **Proceeds** | Golden-sample approval; §5 acceptance — renderers only transcribe; output matches the sample within stated tolerances |
| **1** | S3 contract fixtures, both sides validating independently | **Deferred** | §2 acceptance: both repos validate the same fixtures; decimal round-trips exactly; unknown version fails closed |
| **2** | S1 + S2 headless facade | **Deferred** | §3 acceptance: synthetic dataset analyzed through the Python API; no repo root. Also blocked by Seshat spec 138 (delta §F). |
| **3** | S4 + S5 + S6 + S7, one low-risk statistical analysis end to end | **Deferred** | §4 acceptance: no customer-visible number changes; fail-closed preserved; rollback available |

**Stage 4 does not depend on stages 1–3.** The Khepri report engine consumes Khepri's own
`FactPackage` today and would gain a second evidence source later. Sequencing it behind the
integration would delay the only phase a buyer can see behind the phase with the most
unresolved preconditions.

**Stage 0 is worth doing while stages 1–3 are deferred.** The boundary costs one review cycle
and prevents the failure that already occurred once: the 2026-08-03 renderer port happened in
good faith because no artifact existed for either side to consult. Deferring the boundary is
how the next duplication gets built.

**S3 (committed fixtures) is the cheapest deferred item and the one worth pulling forward
first** if the integration is ever revived — it needs no package, no distribution decision, and
no Seshat implementation capacity.

## 6. Why this is narrower than roadmap §6

§6 shows Seshat owning "deterministic retail methods." Three reasons this architecture does not:

1. **Seshat has none** (delta §G.1). The transfer is construction, not migration.
2. **Khepri's are approved and shipped** under RRA-004 and RRA-008, with `Decimal` arithmetic
   and formula-version hashing. Moving them is a governed change to approved specifications
   with no parity oracle on the receiving side.
3. **Roadmap §17 names the risk** — "two repositories calculate the same metric differently" —
   and the response is "one authoritative owner." Today there is exactly one owner per metric.
   The migration would create a period where there are two.

The end state in §20 stays the target. This states the first release, and names the condition
for moving: a parity fixture that both engines pass, on a metric Khepri already computes,
before any customer output changes.
