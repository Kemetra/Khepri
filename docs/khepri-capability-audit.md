# Khepri capability and framework audit

- Audited at: 2026-08-04
- Audited commit: `0b1ae35` on `main`, clean working tree
- Method: read-only inspection of `src/`, `tests/`, `governance/`, `pyproject.toml`
- Status: **advisory analysis, not a governed artifact.** It approves nothing, records no
  approval, and creates no authority. Where it states a governance fact, the registry named
  beside it is authoritative.

This audit answers one question the owner asked directly: is Khepri "too traditional — a
linear pipe any n8n workflow could imitate"? Section 3 answers it with code evidence, and the
answer is *partly yes and the interesting part is no*. Sections 1, 2, 4, 5, and 6 supply the
inventory that answer rests on.

---

## 1. Capability inventory

Package sizes are source lines, excluding tests.

| Package | Files | Purpose | Specs referenced in code |
|---|---|---|---|
| `khepri.rra` (top) | 41 | The whole beta product: intake, profiling, mapping, facts, narrative, bundle, jobs, telemetry | RRA-001, 002, 003, 004, 006, 007, 008 |
| `khepri.rra.analysis` | 6 | The four RRA-008 analysis families, one module each | RRA-004, RRA-008 |
| `khepri.rra.rendering` | 8 | Concrete surfaces: HTML, PDF, Excel, charts, fonts, wording | RRA-006, 007, 008 |
| `khepri.runtime` | 5 | Production composition roots for web and worker roles | **none** |
| `khepri.infra` | 10 | AWS CDK infrastructure definition | RRA-002, RRA-007 |
| `khepri.local` | 9 | Local development wiring; excluded from the built wheel | RRA-001, 002, 006, 007 |
| `khepri_gov` | 9 | Governance validation tooling; the `khepri-gov` CLI | **none** |

Total: ~24,525 source lines against 27,324 test lines across 81 `test_*.py` files plus 5 support
modules, holding 1,273 test functions. The test-to-source ratio is above 1:1.

### 1.1 What each package can and cannot do

**`khepri.rra` — the product.** Owns every governed capability the beta has. Intake
(`intake.py`) validates one upload against a 50 MiB bound, determines type from content rather
than filename, and rejects zip bombs and unsafe archive entries. Profiling (`profiling.py`,
718 lines) infers types and detects likely personal data across email, IBAN, card, phone,
address, and IPv4 shapes. Mapping (`mapping.py`) infers column semantics with confidence and
evidence. Facts (`facts.py`) builds the immutable content-addressed `FactPackage`. Narrative
(`narrative.py`, 66 KB) grounds bilingual prose in that package and validates the response.
Bundle (`bundle.py`, 80 KB) reconciles every surface against one package version.

It cannot: accept more than one input per session, analyze anything but retail, forecast, or
accept a customer-authored formula. Those are excluded by `governance/families/RRA.md`, not
merely unimplemented.

**`khepri.rra.analysis` — RRA-008.** Four families, split into four modules explicitly to stay
under complexity thresholds (`analysis/__init__.py`). `basket.py` computes items per
transaction and attach rate and refuses to substitute a row count for a transaction count.
`comparison.py` runs period-over-period and year-over-year as independently refusable modes.
`concentration.py` computes concentration over the full distinct-value set rather than over
truncated display buckets. `growth.py` decomposes revenue change into price and volume and
asserts the sum as exact equality. None of them computes an aggregate — they read the package.

**`khepri.rra.rendering` — the surfaces.** `charts.py` returns geometry as an exact view model,
never markup. `excel.py` only transcribes a bundle, which is what prevents formula injection
and editable-cell drift. `html.py` emits two documents rather than one bilingual page.
`pdf.py` extends the web template rather than forking it. `fonts.py` ships typefaces as
package data inlined as `data:` URIs so Arabic renders in a minimal container. `chromium.py`
uses `set_content` rather than a URL, and is deliberately not exported from the package.

**`khepri.runtime` — production wiring.** Five files, no spec references. `config.py` parses a
database credential from one Secrets Manager JSON so the password never enters a plain string
or `repr`. `worker.py` holds the only unbounded loop in the codebase
(`while True: self.run_once()`, `runtime/worker.py:73`).

**`khepri.infra` — frozen reference.** 10 files of AWS CDK. `sizing.py` has no defaults at all:
an absent field is a refusal, which is the discipline `KHEPRI-DEC-007` established.
`network.py` builds a VPC with no NAT gateway. `KHEPRI-DEC-008` declares this package frozen
reference — kept green by CI, not the deployment path, closed to new slices.

**`khepri.local` — development only.** Excluded from the wheel (`pyproject.toml:56`) because it
carries local credentials and would hand the image the two entry points the Dockerfile
deliberately withholds. `local/worker.py` drives the worker from PostgreSQL with no queue in
front — which matters for section 3.

**`khepri_gov` — the governance kernel.** 9 files, 2,479 lines, zero spec references because it
validates registries generically. `validator.py` (562 lines) checks registry shape, authority,
ISO dates, global ID uniqueness, family relationships, dependency cycles, and reference
assessments. `delegation.py` (458 lines) enforces the Constitution VIII reserved set.
`approval_transition_validation.py` classifies supersession and renewal. This package is the
subject of section 6's central claim.

### 1.2 Two inventory gaps worth recording

**`RRA-005` is referenced in zero source modules.** Every other approved RRA specification is
cited somewhere in `src/`. `narrative.py` — the apparent RRA-005 implementation — cites RRA-006
only. `tests/test_rra005_narrative.py` exists with 106 test functions, the largest single test
file in the repo. The capability is implemented and tested; the traceability comment is
missing. This is a documentation gap, not a capability gap, and it is worth closing because
RRA-005 is load-bearing for the differentiation argument in section 6.

**`FND-001`, `FND-002`, and `FND-003` are referenced in zero source modules.** Their only
non-test reference is `.github/workflows/governance.yml:60`. The FND specifications govern the
governance kernel, and `khepri_gov` implements them without naming them.

---

## 2. Framework map

Declared runtime dependencies and where they are actually used.

| Dependency | Import sites in `src/` | Verdict |
|---|---|---|
| `sqlalchemy` | 11 modules | Heaviest dependency. Used. |
| `fastapi` | 5 modules | Used. |
| `pyyaml` | 5 modules (4 in `khepri_gov`) | Used. |
| `polars` | `facts.py`, `profiling.py` | Used, and narrowly. See below. |
| `jinja2` | `rendering/html.py`, `rendering/pdf.py` | Used. |
| `boto3` | `local/storage.py`, `runtime/wiring.py` | Used. Two sites only. |
| `xlsxwriter` | `rendering/excel.py` | Used. |
| `playwright` | `rendering/chromium.py` | Used. Single site. |
| `alembic` | none in `src/` | Used outside `src/`: `migrations/env.py` and 9 version files. Runtime-declared for `alembic upgrade head`. Correct. |
| `psycopg` | none | Present only as a SQLAlchemy driver string. Loaded at connect time. Correct. |
| `uvicorn` | none | A container command string only. Invoked as a process. Correct. |
| `fastexcel` | **none by name anywhere** | Functionally required — it is the engine `polars.read_excel` uses at `profiling.py:294` — but never named in `src/`, `tests/`, or `scripts/`. |

**Two undeclared direct imports.** `pydantic` is imported at `rra/api.py:8` and
`rra/report_api.py:34` but is **not** a declared dependency in `pyproject.toml`; it resolves
transitively through FastAPI. `botocore` is imported at `runtime/wiring.py:12` and resolves
through boto3. Both are named in `KHEPRI-DEC-005`/`DEC-008` as part of the approved stack, so
the governance intent is clear and the declaration is missing. A transitive resolution that
works today is not a pin, and a FastAPI major bump could remove it.

**The polars footprint is smaller than the decision implies.** `KHEPRI-DEC-008` describes
Polars as performing "CSV/XLSX materialization, profiling, mapping, grouping, and KPI
preparation." It is imported in exactly two modules. `mapping.py` (568 lines) and
`aggregates.py` (299 lines) do not import it. This matters for section 3: the dataframe engine
is confined to the two edges where data enters and facts are computed, and everything between
is plain Python over frozen dataclasses.

**No hand-rolled capability duplicates a declared dependency.** The one adjacent case is
`khepri_gov`'s own validation logic, which could in principle be a schema library; it is
hand-written because it validates cross-file relationships (dependency cycles, supersession
linkage, delegation reserved sets) that a per-file schema validator cannot express.

---

## 3. Architecture shape — the crux

**Verdict: the pipeline is strictly sequential, and calling it "a pipe n8n could imitate" is
half right in a way that matters.**

### 3.1 It is sequential, and that is not in dispute

`ReportPipeline.run` (`src/khepri/rra/pipeline.py:270-290`) is four calls in fixed order:

```
load_package  →  heartbeat  →  compose_narrative  →  heartbeat
              →  assemble   →  heartbeat          →  deliver
```

There is no branching, no conditional stage, no dynamic graph, and no per-stage retry. The
module's own docstring says so: "It owns the *order* of the stages and nothing else." A stage
failure raises `ReportPipelineFailed` and the whole run delivers nothing.

Measured absences, confirmed by search across `src/`:

| Capability | Present? | Evidence |
|---|---|---|
| In-process fan-out | **No** | No `ThreadPool`, `asyncio.gather`, `concurrent.futures`, or `multiprocessing` anywhere in `src/` |
| Backfill | **No** | No occurrence of `backfill` in `src/` |
| Incremental state | **No** | Each run rebuilds from one immutable package |
| Partitions | **No** | No partitioning vocabulary; one dataset per session. The single `partition` occurrence is `str.partition("@")` at `profiling.py:559`, an email split |
| Per-node retry | **No** | Retry is per *job*, not per stage (`worker.py`, `job_persistence.fail`) |
| Lineage across runs | **No** | Provenance is within one package version, not across datasets |
| Multi-dataset joins | **No** | One upload per session (`RRA-002`) |

So: if the question is "does this express a DAG," the answer is no. It expresses one path.

### 3.2 Why the sequencing is an argument, not an accident

The `pipeline.py` docstring is ~50 lines of reasoning about *why* the stages are ordered this
way and why nothing wraps them. Three properties are load-bearing:

**Heartbeats sit strictly between stages, never inside one.** `NarrativeService.compose` turns
any provider exception into a refusal, and `BundleAssembler.assemble` turns any renderer
exception into an incomplete bundle. Both contain broad `except Exception` handlers. A
heartbeat *inside* either would be swallowed, so a lost lease would surface as a bundle
refusal rather than as a lost lease — and `LeaseLost` means another worker owns this job, which
is the exact failure leases exist to prevent. The module therefore catches nothing at all
(`pipeline.py:19-29`).

**A refused narrative stops the run, deliberately.** RRA-006 authorizes a facts-only report
whose disclosure says commentary was refused. This pipeline does not deliver one, because
"building a facts-only report is a *different* report from the one this job was queued for, and
choosing to publish it is an authorization this slice was not granted" (`pipeline.py:31-37`).

**Idempotency is asked of the store, not inferred.** `run` asks `find_delivery(job_id)` before
any stage runs. Rebuilding the bundle to compare would mean asking a provider for prose again,
and prose is the one non-deterministic input — the second run would produce a different
`bundle_id` and read as a different report (`pipeline.py:39-45`).

**This is the finding that answers the owner's complaint.** An orchestrator that models each
stage as an independently *retryable* node would break property one. State the constraint
precisely, because the imprecise version is refutable: a per-stage error boundary already
exists. `StageTelemetryPipeline._measure` (`stage_telemetry.py:325-338`) wraps every stage,
re-raising `LeaseLost` untouched, recording `ReportPipelineFailed` as `TRANSITION_REFUSED`, and
recording any other exception as `TRANSITION_FAILED`. A boundary that **observes and re-raises**
is fine and is built. A boundary that **retries the stage** is what the design forbids: retrying
stage N means re-entering it under a lease whose loss could not have been observed, because
heartbeats sit only between stages. The sequencing is not naivety awaiting an upgrade. It is a
safety property with a written derivation.

### 3.3 What the job layer already does that a "pipe" does not

`KHEPRI-DEC-008` reversed `KHEPRI-DEC-005`'s rejection of PostgreSQL-only queueing on the
grounds that the custom behaviour "is largely written and tested." The audit confirms this.

`jobs.py` defines a five-state machine (`queued`, `running`, `retryable`, `succeeded`,
`dead_lettered`), two distinct dead-letter reasons (`retries_exhausted`,
`content_deleted`), and three attempt dispositions (`retry_scheduled`, `lease_reclaimed`,
`retries_exhausted`). `JobAttempt.__post_init__` enforces that only a retried attempt may
schedule availability.

`job_persistence.py` implements `enqueue` (idempotent via `_insert_or_get`), `lease`,
`heartbeat`, `complete`, `fail`, `recover_expired`, `recover_orphans`, and `list_attempts`,
with database-level `CheckConstraint`s on `max_attempts > 0`, `attempt_count <= max_attempts`,
and lease-field coherence.

That is a work queue with leases, bounded retries, orphan recovery, dead-lettering with
governed reasons, and content-free attempt evidence. It is the substrate an orchestrator would
otherwise supply.

### 3.4 The honest concession

Three real limits follow from the shape, and they bind the product rather than the code:

1. **One dataset per session, ever.** Not one at a time — one, period. Trend analysis across
   months requires the customer to re-upload a wider file. `RRA-002` and the 7-day expiry make
   accumulation impossible by design.
2. **No cross-run history.** Each report is an island. A customer cannot ask "how did last
   month's report differ from this one" because last month's content was deleted.
3. **Throughput is bought by process count only.** `KHEPRI-DEC-008`'s sizing rules state one
   report job per worker process; a second concurrent job in-process would contend for cores
   during rendering. Confirmed: no in-process concurrency primitives exist.

Limits 1 and 2 are the ones that matter commercially, and neither is an orchestration problem.
They are a *retention and tenancy* problem — the customer has no durable workspace to
accumulate anything in. Dagster does not fix that. Persistent, isolated, multi-dataset
workspaces fix that, and RRA.md currently excludes them.

---

## 4. Governance position

### 4.1 Lifecycle state

Authoritative source: `governance/registries/`. Reproduced here for reading convenience only.

| Artifact | State | Approved by |
|---|---|---|
| FND-001 Governance Kernel | verified | AHMED-SHAABAN |
| FND-002 Governed Lifecycle Transitions | implemented | AHMED-SHAABAN |
| FND-003 Delegated Approval Records | implemented | KHEPRI-AGENT (delegated) |
| RRA-001 … RRA-003 | approved | AHMED-SHAABAN |
| RRA-004 Deterministic Retail Fact Package | approved | KHEPRI-AGENT (delegated) |
| RRA-005 … RRA-008 | approved | AHMED-SHAABAN (RRA-008 via APP-006) |
| DEC-001 … DEC-004 | accepted | AHMED-SHAABAN |
| DEC-005 Runtime architecture (AWS `me-central-1`) | **accepted** (see note) | KHEPRI-AGENT |
| DEC-006 Benchmark workload | accepted | AHMED-SHAABAN |
| DEC-007 Infrastructure sizing | accepted | AHMED-SHAABAN |
| **DEC-008 Portable runtime target** | **proposed** | — |
| DEC-009 Standing authorization | rejected | AHMED-SHAABAN |
| DEC-010, DEC-011 Delegation | accepted | AHMED-SHAABAN |

No RRA specification has reached `implemented` or `verified`. Both families are `active`.

**Note on DEC-005.** Its document still closes with "This decision remains proposed until its
registry entry contains explicit approval evidence," while `decisions.yaml` records
`state: accepted` with approval evidence at `APP-013.yaml`. The registry governs under
Constitution I, so `accepted` is the true state — and it matters, because DEC-005 being accepted is
what makes `RRA.md`'s conditional runtime-selection exclusion lapse.

It is **not** a housekeeping fix. `APP-013.yaml` binds
`document_sha256: sha256:2214cd1246eebfb61464369903a03b706bf1ed9e2194fde1dc74cd5197e37eeb` to the
document, and editing it makes `khepri-gov validate` fail with `approval-packages:APP-013: governed
document for KHEPRI-DEC-005 changed without renewal`. Verified empirically during this audit: the
edit was attempted, rejected, and reverted. Correcting the sentence needs a renewal approval
package and a named authority.

### 4.2 The blocking fact

**Khepri has no approvable deployment path today.** DEC-005 is `accepted` and names AWS
`me-central-1`. DEC-008 priced that environment at ~675 USD/month standing and states plainly
that the owner cannot fund it — "a decision the owner cannot execute is not authority; it is an
aspiration that blocks every artifact downstream of it." DEC-008 supersedes DEC-005 and
DEC-007, but it is `proposed`, so the unaffordable decision remains the authoritative one.

DEC-008's own fail-closed chain: absent an approved target-selection artifact, no deployment
definition exists, so no environment exists, so no benchmark evidence exists, so beta cannot be
authorized.

This is independent of anything commercial. It blocks the *beta*.

### 4.3 What RRA.md excludes

`governance/families/RRA.md` "Excludes" lists, verbatim:

- Commercial authentication, user profiles, persistent customer workspaces, organizations,
  membership roles, **billing, subscriptions, scheduling, and public signup**
- Agency portfolios, client switching, delegated access, work queues, and **white labeling**
- Forecasting, generic analysis, customer-authored formulas, and unsupported metrics
- **Runtime or provider selection before a separate architecture decision is accepted**
- Product implementation while this family remains proposed or its specifications remain draft

The fourth clause is easy to misread, and the misreading matters. It is **conditional** — "before a
separate architecture decision is accepted" — and its condition is satisfied, because
`KHEPRI-DEC-005` is `accepted` in the registry. It does not stand as a general prohibition on
runtime selection, and `KHEPRI-DEC-012` records it as lapsed rather than relying on it.

The clause that actually binds new runtime components is in the accepted architecture decision:
`KHEPRI-DEC-005:36`, carried forward verbatim at `KHEPRI-DEC-008:77-78` — "No separate SPA,
Node.js runtime, Redis, **data warehouse**, notebook runtime, or **microservice boundary** is
introduced for the private beta." A case-insensitive search of `governance/` for `dbt`, `dagster`,
and `orchestrat` returns **zero occurrences** outside DEC-012 itself.

One further reading trap, recorded because it cuts both ways. `RRA.md:14` excludes `work queues`,
but `RRA.md:8` **owns** "Report-job reliability," and `jobs.py` plus `job_persistence.py` implement
a leased work queue under that authority. The exclusion is grouped with agency portfolios, client
switching, and white labeling, so it means customer-facing queues. Read platform-wide, it would
make shipped approved code unauthorized.

The owner's stated buyers are **retail chains/mid-market and agencies/consultants**. Reading
that against the exclusion list: mid-market needs persistent workspaces, organizations, and
subscriptions. Agencies need portfolios, client switching, delegated access, and white
labeling. **Every capability both target buyers require is explicitly excluded.**

DEC-003 reinforces it, and DEC-005 and DEC-008 each close by disclaiming authorization of
public signup, commercial authentication, persistent workspaces, organizations, billing,
scheduling, and agency features.

Two reference reviews already surveyed this ground and deferred it: `BATCH-04` (commercial
identity, persistent workspaces, report history) and `BATCH-09` (agency portfolios, delegation,
work queues, white labeling). Both are technical review evidence carrying no approval — but
they mean the predecessor's shape of this problem has been read.

**Consequence for the roadmap:** commercialization is gated on a governance change, not on
code. No slice implementing billing, signup, or a persistent workspace can be authorized under
the current family document, and `AGENTS.md` forbids implementing ahead of an approved
specification.

---

## 5. Complexity hotspots

Under the CI rule that every new file must score CodeScene Code Health 10.00 and no tracked
hotspot may decline, file size is a governance risk and not only a style question.

| File | Size | Assessment |
|---|---|---|
| `rra/bundle.py` | 80.6 KB | **Largest. Mixed.** Holds reconciliation, the all-or-nothing surface rule, and bilingual assembly — "all arithmetic happens once here, in both languages." The single-place property is deliberate and valuable. But 80 KB is roughly four times the next-largest module, and reconciliation, assembly, and the surface contract are separable concerns. A candidate for extraction, done carefully. |
| `rra/narrative.py` | 66.3 KB | **Mostly irreducible.** Implements RRA-005: provider contract, request projection through `_REQUEST_SCHEMA` (a positive projection rather than a blocklist), response validation against supplied fact IDs, citation checking, bilingual parity enforcement, refusal handling. Each is a governed requirement. The 106-test file corroborates the surface breadth. |
| `rra/persistence.py` | 33.6 KB | **Irreducible for its kind.** 8 ORM row classes and 5 repositories. Large because it is a schema, and schemas are wide rather than deep. |
| `rra/facts.py` | 32.8 KB | **Irreducible.** The `FactPackage` and every governed KPI with documented zero/null/currency/sign/duplicate/return semantics. |
| `rendering/excel.py` | 33.7 KB | **Mostly irreducible.** Transcription plus formula-injection and URL-interpretation suppression. Governed output safety. |
| `rra/mapping.py` | 27.0 KB | Semantic inference with confidence and evidence. Rule-table shaped. |
| `rra/profiling.py` | 23.9 KB | Type inference plus PII detection across six shapes. |

`analysis/` is the counter-example that proves decomposition is achievable here: its
`__init__.py` states the four families were split into four modules specifically to stay under
complexity thresholds, and each lands at 5-20 KB.

**The pattern:** files carrying *governed semantics* (facts, narrative, excel) are large because
the semantics are large, and shrinking them would scatter rules that must be read together.
`bundle.py` is the one case where size looks like accumulated responsibility rather than
irreducible domain, and it is also the file most central to the differentiation claim — which
argues for touching it deliberately and with evidence, not opportunistically.

---

## 6. Reuse verdict

Against the owner's target: a commercial service for retail chains/mid-market **and**
agencies/consultants, whose differentiator is **auditable, defensible analysis**.

### 6.1 Reusable as-is — the majority, and the valuable part

| Asset | Why it survives commercialization |
|---|---|
| `khepri_gov` (2,479 lines) | Provider-agnostic, product-agnostic. Validates registries, lifecycle, delegation. Nothing about it is beta-shaped. |
| `facts.py` + `FactPackage` | Immutable, versioned, content-addressed, sole source for every surface. This is the audit trail. |
| `analysis/` (all four families) | RRA-008 analysis over a package. Buyer-agnostic. |
| `narrative.py` + adapter contract | Grounded bilingual prose with citation validation and refusal. Replaceable provider behind a Protocol. |
| `rendering/` (all 8 modules) | Surfaces from a bundle. Unaffected by who is paying. |
| `bundle.py` reconciliation | All-or-nothing multi-surface integrity. |
| `profiling.py`, `mapping.py`, `admissibility.py` | Intake intelligence and PII detection. |
| `jobs.py` + `job_persistence.py` | Leases, retries, orphan recovery, dead-lettering. Scales by process count. |
| `telemetry*.py` | Content-free operational evidence. |
| Test suite (27,324 lines) | The reason any of the above can be changed with confidence. |

### 6.2 Beta-only scaffolding — replace, and expect it to be load-bearing

| Asset | Why it does not survive |
|---|---|
| `sessions.py` invitation model | Single-use invitation secrets, opaque pseudonymous owner IDs, no email owner key. A commercial buyer needs a durable identity. |
| Seven-day expiry | Correct for a privacy-minimizing beta; fatal for mid-market recurring reporting, where the previous period *is* the comparison baseline. |
| One-upload-per-session | Both target buyers need multiple datasets over time. Agencies need many per client. |
| `session_cookie.py` | Beta session carriage. Becomes real auth. |
| `sqs_queue.py` | DEC-008 removes SQS in favour of PostgreSQL claim-and-redrive. Already scheduled for deletion. |
| `khepri.infra` (1,351 lines) | Declared frozen reference by DEC-008. Not deleted — it is the only worked example of the sizing reasoning a new target must reproduce. |
| `runtime/config.py` AWS coupling | Pinned to `me-central-1`, a 12-digit account ID, and a KMS key ARN. DEC-008 lists unlocking it as a follow-on obligation. |

### 6.3 The differentiation finding

The owner's instinct — auditable/defensible analysis — is the correct one, and the audit
supports it over the alternatives:

**It is already built, not aspirational.** The immutable content-addressed fact package, the
one-package-behind-every-surface rule, the deliberately redundant re-check in
`_require_one_bundle_behind_every_surface`, the refusal vocabulary, the content-free evidence
trail, and `khepri_gov` itself are all present and tested today.

**It is the property a generic pipeline structurally cannot claim.** An n8n workflow can call
an LLM and emit a PDF. What it cannot do is guarantee that every number on every surface came
from one immutable versioned package, that no uncited claim survived validation, that the same
input reproduces the same `bundle_id`, and that a partial render is recorded as a refusal
rather than delivered as a report. Those are enforced at type boundaries
(`DeliveryRecord.__post_init__` refuses a record naming fewer than every required surface) and
proven by 1,273 tests. Reproducing them is not a matter of adding nodes to a graph; it is the
work of building the invariants.

**The AR/EN parity requirement compounds it.** RRA-005 requires equal factual and caveat
coverage in both languages, validated rather than trusted. In a MENA retail market that is both
a feature and a barrier to imitation.

**Ranked honestly for the two named buyers:**

1. **Auditable/defensible analysis** — primary. Mid-market finance functions and agencies both
   need to defend a number to someone else. Agencies especially: their product *is* their
   credibility with their client.
2. **Bilingual parity** — strong secondary, and near-decisive in the target geography.
3. **Deterministic reproducibility** — an enabler of (1) rather than a sold feature. It is what
   makes a dispute resolvable.
4. **Admissibility gating** — genuine, but sells poorly and may read as rejection. Best framed
   as a quality guarantee rather than a gate.

### 6.4 The uncomfortable part

The moat is real, and it is in the layer the owner suspects of being boring. `khepri_gov` and
the fact-package discipline are not scaffolding around the product — for an auditability
buyer, they *are* the product, and the report is how the product is delivered. The strategic
error available here is dressing up the pipeline while leaving that layer where a buyer never
sees it.

The commercially binding limits are one-dataset-per-session and no cross-run history
(section 3.4). Both are retention and tenancy problems. Neither is solved by an orchestrator.

---

## The five facts a roadmap must respect

1. **Khepri has no approvable deployment path.** DEC-005 (AWS `me-central-1`, ~675 USD/month)
   is `accepted` and unaffordable; DEC-008, which fixes it, is `proposed`. This blocks the beta,
   before anything commercial. Approving DEC-008 and writing its target-selection artifact is
   the first gate.
2. **Every capability both target buyers need is explicitly excluded by `RRA.md`.** Persistent
   workspaces, organizations, billing, subscriptions, scheduling, public signup, agency
   portfolios, client switching, white labeling. Commercialization begins as a governance
   change; `AGENTS.md` forbids implementing ahead of an approved specification. Note that
   `RRA.md`'s exclusions are written as flat prohibitions, so a new family owning these
   capabilities requires re-scoping them into family boundaries in the same approval package —
   otherwise two documents claim the same capability, which Constitution I forbids.
3. **The pipeline is sequential by argument, not by accident.** Per-stage retry with per-stage
   error boundaries would break the lease-safety property `pipeline.py:19-29` derives. Any
   orchestration proposal must engage that argument.
4. **The moat is the governance layer, and it is already built and tested.** Immutable
   content-addressed fact packages, one package behind every surface, citation validation,
   refusal over fabrication, content-free evidence, 1,273 tests. Make it visible; do not
   rebuild it.
5. **The binding limits are retention and tenancy, not orchestration.** One dataset per
   session and no cross-run history are what stop a mid-market customer from getting value.
   The fix is a durable, isolated, multi-dataset workspace — which is item 2's governance work,
   not a scheduler.
