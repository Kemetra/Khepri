# KHEPRI-DEC-012: Transformation and orchestration tooling boundary

## Context

The owner asked whether dbt and Dagster belong inside Khepri, inside the separately owned
`Kemetra/Seshat-BI` engine repository, split between them, or nowhere. The question follows an
observation worth recording accurately: that Khepri's report path "feels too traditional — a
linear pipe any n8n workflow could imitate."

This decision answers the tooling question. It does not answer the product question the
observation raises, which belongs to a roadmap and to whatever family charter follows it.

### What the pipeline is

`ReportPipeline.run` (`src/khepri/rra/pipeline.py:270-290`) is four calls in fixed order —
`load_package`, `compose_narrative`, `assemble`, `deliver` — with a lease heartbeat between
each. A search of `src/` finds no `ThreadPool`, `asyncio.gather`, `concurrent.futures`, or
`multiprocessing`; no `backfill`; no partition vocabulary; and no per-stage retry. The
observation about shape is correct: this expresses one path, not a graph.

The ordering is not an unfinished design. `pipeline.py:19-29` derives it: `NarrativeService.compose`
turns any provider exception into a refusal and `BundleAssembler.assemble` turns any renderer
exception into an incomplete bundle, both via broad `except Exception` handlers. A heartbeat
inside either would be swallowed, so a lost lease would surface as a bundle refusal instead of
as `LeaseLost` — and `LeaseLost` means another worker owns this job, which is the failure leases
exist to prevent.

State the resulting constraint precisely, because the loose version is refutable. A per-stage
error boundary already exists: `StageTelemetryPipeline._measure`
(`src/khepri/rra/stage_telemetry.py:325-338`) wraps every stage, re-raises `LeaseLost` untouched,
records `ReportPipelineFailed` as `TRANSITION_REFUSED`, and records any other exception as
`TRANSITION_FAILED`. A boundary that observes and re-raises is built and correct. A boundary that
**retries the stage** is what the design forbids, because retrying stage N re-enters it under a
lease whose loss could not have been observed while a stage was in flight.

### What the job layer already provides

`src/khepri/rra/jobs.py` defines a five-state machine (`queued`, `running`, `retryable`,
`succeeded`, `dead_lettered`), two governed dead-letter reasons (`retries_exhausted`,
`content_deleted`), and three attempt dispositions. `src/khepri/rra/job_persistence.py`
implements `enqueue` (idempotent), `lease`, `heartbeat`, `complete`, `fail`, `recover_expired`,
`recover_orphans`, and `list_attempts`, with database `CheckConstraint`s on `max_attempts > 0`,
`attempt_count <= max_attempts`, and lease-field coherence. `src/khepri/rra/worker.py` holds the
lease, heartbeat, and bounded-retry harness.

`KHEPRI-DEC-008` already reversed `KHEPRI-DEC-005`'s rejection of PostgreSQL-only queueing on
exactly this evidence — "the custom behaviour the rejection warned about is largely written and
tested" — and removes Amazon SQS in favour of `SELECT ... FOR UPDATE SKIP LOCKED` claim and
redrive. Khepri is mid-flight on reducing its orchestration substrates from two to one.

### What the data shape is

One CSV or XLSX upload per session, bounded at 52,428,800 bytes, expiring seven days after
session creation, producing one immutable content-addressed `FactPackage` and one report bundle.
No warehouse. Polars is imported in exactly two modules, `facts.py` and `profiling.py`.

### What Seshat-BI already owns

`Kemetra/Seshat-BI` at version 0.8.1 ships governed dbt and Dagster adapters: `dbt-core==1.12.0`
and `dbt-postgres==1.10.2` as an optional extra, `src/seshat/dbt`, `src/seshat/dagster_adapter`,
and specifications 023, 024, 133, 134, and 135 covering both adapters and their seam. Both are
gated: approved source maps, immutable plan digests, shadow-only targets, parity oracles, and
named-human approval before a build. Its Dagster adapter states its own boundary — "Dagster RUNS
already-approved steps; this adapter records, it does not decide."

Both adapters are command-line interfaces over a developer's repository checkout, scoped to a
governed table in a medallion warehouse, holding a repository-root filesystem lock. The Dagster
runner shells to a hardcoded module path (`tower_bi_orchestration.definitions`) using a
separately provisioned interpreter, and states that `seshat dagster run` never imports Dagster.
The dbt runner resolves a real `dbt` binary and requires `target == "shadow"`. Neither is a
library Khepri could import, and neither is a service Khepri could call.

Seshat-BI is not published to a package index. Its `requires-python` is `>=3.13`, against
Khepri's `>=3.13,<3.14`.

### What governance already says

The binding clause is in the accepted architecture decision, and it names both tools' runtime
shapes directly. `KHEPRI-DEC-005:36`, carried forward verbatim at `KHEPRI-DEC-008:77-78`:

> No separate SPA, Node.js runtime, Redis, **data warehouse**, notebook runtime, or
> **microservice boundary** is introduced for the private beta.

dbt without a warehouse has no relation to compile against, so adopting dbt means introducing the
data warehouse this clause excludes. A Dagster daemon with its own run storage is a separate
always-on process, which is the microservice boundary it excludes.

**State the consequence honestly, because the owner asked for these tools.** This is not a flat
prohibition. `KHEPRI-DEC-005` is `accepted`, so adopting either tool requires **superseding its
application-stack section** — the same mechanism `KHEPRI-DEC-008` used to replace its deployment
section. The question is therefore not "may we" but "is the supersession worth its cost." This
decision answers no, on the evidence below, and records what would change that answer.

One clause is deliberately *not* relied on. `governance/families/RRA.md` excludes "Runtime or
provider selection **before a separate architecture decision is accepted**." That exclusion is
conditional and its condition is satisfied: `KHEPRI-DEC-005` is accepted in
`governance/registries/decisions.yaml`. Reading it as a standing prohibition on runtime selection
drops the qualifier that carries its meaning, so it is recorded here as lapsed rather than cited
as authority.

`RRA.md` separately excludes `scheduling`, `persistent customer workspaces`, `agency portfolios`,
and `client switching` — the capabilities a scheduler would exist to serve.

`RRA.md:14` also excludes `work queues`, and that clause is **not** evidence for this decision.
It is grouped with agency portfolios, client switching, and white labeling, so it means
customer-facing queues; the internal report-job queue is owned by `RRA.md:8`, "Report-job
reliability," and is implemented in `jobs.py` and `job_persistence.py` under that authority.
Reading it platform-wide would make shipped, approved code unauthorized.

A case-insensitive search of `governance/` for `dbt`, `dagster`, and `orchestrat` returns zero
occurrences outside this decision: neither tool has ever been governed here.

## Decision

**Neither dbt nor Dagster is adopted into Khepri. Seshat-BI's existing governed dbt and Dagster
adapters stay where they are, and Khepri consumes neither.**

Khepri's transformation stack remains Polars in process, as `KHEPRI-DEC-008` restates it.
Khepri's job delivery remains PostgreSQL claim and redrive, as `KHEPRI-DEC-008` decides it.

This decision authorizes no code change in either repository. It records a boundary so that the
question is settled rather than re-opened per slice, and so that a later reversal is a decision
rather than a drift.

### The orchestration question, answered directly

Khepri has no orchestration problem that Dagster solves and its existing job layer does not.

| Dagster capability | Khepri's demand | Where already met, or why absent |
|---|---|---|
| Asset-graph fan-out | None. Four sequential stages. | `pipeline.py:284-290` |
| Partitions, backfills | None. One immutable package per session. | `facts.py` content addressing |
| Materialization caching | Present, by content address. | `pipeline.py:278-282`, `find_delivery` short-circuits before any stage |
| Schedules, sensors | **Excluded by `RRA.md`.** | `scheduling` is a listed exclusion |
| A warehouse to orchestrate over | **Excluded by `KHEPRI-DEC-005:36`.** | `data warehouse` named in the accepted stack clause |
| Bounded retry with delay | Present. | `worker.py`, `FailureRequest(retry_at=...)` |
| Lease and concurrency safety | Present. | `worker.py` lease and heartbeat; `LeaseLost` re-raised |
| Orphan and expired-lease recovery | Present. | `job_persistence.recover_orphans`, `recover_expired`, `jobs.orphanable` |
| Dead-lettering | Present, with a governed reason vocabulary. | `jobs.py:24-32` |
| Run observability | Present, and stricter. | `stage_telemetry.py`, content-free by construction |
| Per-stage **retry** | **Architecturally forbidden.** | `pipeline.py:19-29`; see Context |

Adopting Dagster would also degrade a governed property rather than add one. `OperationalEvent`
carries only opaque identifiers, content addresses, stage names, durations, and size bands, and
`RRA-007` requires that evidence be content-free. An orchestrator's run storage records what its
steps emit, which is why Seshat-BI needed a dedicated redaction layer for its adapter surfaces:
`src/seshat/dagster_adapter/redaction.py` states its own scope as "Redaction for every surfaced
Dagster-adapter string (spec 134, FR-008). Anything the adapter prints, records as evidence, or
raises passes through here first," with a counterpart at `src/seshat/dbt/redaction.py`. That is
in-repository evidence that the problem is real and had to be solved deliberately. Khepri needs no
such layer because nothing untrusted reaches its evidence today, and adding a component that
requires one converts a structural guarantee into a filtering obligation.

### The modelling-discipline question, answered directly

dbt's disciplines are worth having, and three of the four are already present under other names.

| dbt discipline | Khepri status |
|---|---|
| Versioned transformations | Present, and stricter. `facts.py` carries `PACKAGE_VERSION`, `FORMULA_VERSION`, and `Fact.formula_version` as both a field and a hash input. dbt versions the model; Khepri versions the number. |
| Tests as contracts | Present, enforced at delivery rather than at build. `aggregates.reconciles`, `bundle.reconcile`, and `pipeline._require_one_bundle_behind_every_surface` — deliberately redundant — plus database `CheckConstraint`s. |
| Lineage | Present as the citation graph. `Fact.citation_id`, `fact_id`, and `FactPackage` digest, correlated into telemetry. |
| Generated docs | **Genuinely absent** as a browsable artifact. The gap is a catalog, not the discipline. |

Adopting dbt would also cost a governed property. `facts.py` computes in `Decimal` under an
explicit arithmetic precision with bounded measure digits, because `KHEPRI-DEC-008` forbids
binary floating point as an authoritative financial fact. Pushing that arithmetic into warehouse
SQL substitutes an engine's numeric semantics for a governed decimal contract. For a product
whose value is defensibility, that is a downgrade.

### The condition under which this decision should be revisited

dbt becomes relevant when there is a relation to model and a schema to test — that is, when
Khepri accumulates datasets across sessions in a durable store. That capability is excluded
today by `RRA.md`'s exclusion of persistent customer workspaces, and the store it would require
is excluded by `KHEPRI-DEC-005:36`.

The trigger is therefore a **precondition, not a date**: revisit this decision when a family
owning cross-session accumulation is chartered and reaches `active`, and a specification under
it requires a persistent multi-dataset store. Until then dbt has nothing to compile against.

Dagster should be revisited only if a specification requires partitioned or backfilled compute,
or fan-out across datasets within one run. Retry semantics alone are not a trigger; they exist.

## Consequences

- Khepri's transformation and orchestration substrates are settled for the private beta:
  Polars in process, PostgreSQL claim and redrive. No new operated service, no second
  interpreter, no additional monthly cost, and no new CodeScene surface.
- The question is answered once. Once this decision is accepted, a future slice proposing dbt or
  Dagster must supersede it rather than argue the point again. While it remains `proposed` it is
  reasoning on the record, not authority.
- Seshat-BI is unaffected. Its adapters remain correctly placed over a medallion warehouse that
  actually exists. No cross-repository dependency is created in either direction.
- The coupling that option B would have created is refused explicitly. Seshat-BI is not on a
  package index, pins `dbt-core==1.12.0` against Khepri's `jinja2>=3.1,<4`, declares
  `requires-python >=3.13` against Khepri's `>=3.13,<3.14`, and makes dbt an extra with lazy
  imports while giving Dagster a separate interpreter — its own design resists co-installation.
  Khepri's `pyproject.toml` excludes `src/khepri/local` from the wheel with a written rationale
  about what belongs in the image that runs web and worker; a Seshat workspace plus a dbt binary
  plus an orchestration interpreter contradicts that rationale directly.
- One documentation gap is left open and named rather than fixed here: Khepri has no generated,
  browsable catalog of its governed facts, formulas, and citations. That is the one dbt
  discipline it lacks, it is achievable without dbt, and it is plausibly customer-facing for a
  buyer purchasing defensibility. It is outside this decision's boundary.
- This decision supersedes nothing. It does not amend `RRA.md`, alter any specification, or
  authorize any product capability. It records no approval and creates no authority.

### What this decision does not settle

It does not address the observation that prompted it. The limits that bind Khepri commercially
are that a session accepts one dataset ever, and that seven-day expiry deletes the baseline a
comparison would need. Both are retention and tenancy limits, not orchestration limits, and no
scheduler fixes either. They are the roadmap's subject, and they begin with a family charter.

It also does not settle where Khepri deploys. `KHEPRI-DEC-005` remains `accepted` and names an
environment `KHEPRI-DEC-008` prices at approximately 675 USD per month and states the owner
cannot fund; `KHEPRI-DEC-008`, which replaces it with a provider-neutral capability contract,
remains `proposed`. That is the first gate in front of everything else, including the beta.

This decision remains proposed until its registry entry contains explicit approval evidence.
