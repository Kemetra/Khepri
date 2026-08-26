# DRAFT — KHEPRI-DEC-NNN-BENCHMARK: RRA beta benchmark workload and environment

> **PROMOTED — superseded by an activated decision.** This draft was adopted as
> **`KHEPRI-DEC-029`** (`governance/decisions/KHEPRI-DEC-029-rra-benchmark-workload-and-environment.md`),
> active in `governance/registry.yaml` with `depends_on: [KHEPRI-DEC-028]`, retiring
> `KHEPRI-DEC-006`. The placeholder `KHEPRI-DEC-NNN-TARGET` was allocated as `KHEPRI-DEC-028`.
> Read the activated decision, not this draft. Retained as the reasoning record.

**Status: planning-only draft. Not a governed artifact — including after this commit is merged.**

Merging this commit does **not** make this document governing. `governance/registry.yaml` is
unchanged by it, contains no entry for this document, and is authoritative for artifact identity,
state, and document under Constitution III; the validator therefore ignores this file, which lives
under `docs/platform/proposed-governance/`. It remains planning-only until it is finalized under an
owner-allocated identifier, moved into `governance/decisions/`, and added through the registry
transition described below.

**Two identifiers are referenced in this branch and neither is allocated.** `AGENTS.md` fails closed
on ambiguous identity, so they are kept visibly distinct:

- **`KHEPRI-DEC-NNN-TARGET`** — the runtime-target decision drafted in
  `ops1-01-superseding-decision-draft.md`, proposed to supersede `KHEPRI-DEC-008`.
- **`KHEPRI-DEC-NNN-BENCHMARK`** — *this* document, proposed to supersede `KHEPRI-DEC-006`.

Only the owner allocates either. Nothing here authorizes provisioning, deployment, spend, external
traffic, or a benchmark run.

> Proposed to supersede `KHEPRI-DEC-006`. Restates it with the environment sections re-pointed from
> the retired `KHEPRI-DEC-005` to `KHEPRI-DEC-NNN-TARGET`. **The workload, the measurement rules,
> the digest discipline, the completion objective, and the exclusions are carried forward
> unchanged.**

## Context

`KHEPRI-DEC-006` (`active`) fixes the benchmark workload, the measured interval, the digest rule,
and the completion objective. Those are provider-neutral and are not in question here.

Its environment sections are not. They are inherited by reference from `KHEPRI-DEC-005` under a
heading that reads "Environment: pinned by `KHEPRI-DEC-005`", and `KHEPRI-DEC-005` is `retired`
(`superseded_by: KHEPRI-DEC-008`). An `active` decision therefore draws a live requirement from a
retired one.

### Why the validator does not catch this

`governance/registry.yaml` records `KHEPRI-DEC-006` with `depends_on: []`. The
active-depends-on-retired rule in `src/khepri_gov/validator.py` fires on registry dependencies, not
on prose citations, so it never fires here. `khepri-gov validate` passes and says nothing about the
staleness. This draft records the dependency in the registry so the same defect is caught next time.

### What actually breaks

`KHEPRI-DEC-006` requires the run to use AWS `me-central-1`, ECS on Fargate, ECR, an Application
Load Balancer, RDS PostgreSQL 17 Multi-AZ, S3 with SSE-KMS, SQS Standard with a dead-letter queue,
Secrets Manager, CloudTrail, KMS, and AWS CDK v2 — and requires `environment_digest` to cover "the
SHA-256 digest of the reviewed synthesized CDK template."

Against the target `KHEPRI-DEC-027` selected, three of those are not merely different but absent:
SQS was removed by `KHEPRI-DEC-008` in favour of a PostgreSQL claim queue; no CDK template exists
for a DigitalOcean target; and no KMS customer-managed key exists, because `KHEPRI-DEC-008` moved
encryption into the application. A FRA1 run could not satisfy this decision, and
`environment_digest` could not be computed as specified.

`KHEPRI-DEC-008` recorded that `KHEPRI-DEC-006`'s workload "is provider-neutral and is unaffected"
by the change of host. That is accurate about the **workload** and was never a statement about the
**environment**, whose sections this draft is confined to.

### Why this is a small change

`KHEPRI-DEC-006` already delegates the concrete environment downstream. It states that approving it
"fixes the workload, the measurement rules, the identity, and the digest discipline. It does not by
itself enable a governed benchmark run: no run can produce approved performance evidence until the
parameters above are settled by an artifact carrying infrastructure authority, and recorded in the
environment descriptor," and records that "No such definition exists in this repository yet."

The AWS service list is therefore an inherited snapshot, not the operative evidence rule. Replacing
the inheritance leaves the evidence contract intact. Neither
`governance/benchmarks/KHEPRI-BMK-001-workload.yaml` nor
`governance/benchmarks/KHEPRI-BMK-001-environment.yaml` has ever been created, so this changes a
requirement rather than a shipped artifact.

## Decision

This decision supersedes `KHEPRI-DEC-006` and restates it in full.

*(Drafting note: on adoption, the carried-forward text of `KHEPRI-DEC-006` — benchmark identity,
governed descriptor artifacts, the four workload sections, the measured interval and completion
definition, digest computation, the harness gap, the restated completion objective, and the
exclusions — is reproduced verbatim so this document stands alone. It is omitted from this draft
only to keep the diff reviewable; it is not being dropped, and the same block-by-block byte-identity
check applied to the target draft applies here.)*

### Environment: pinned by `KHEPRI-DEC-NNN-TARGET`

Replaces "Environment: pinned by `KHEPRI-DEC-005`".

The benchmark environment is the architecture `KHEPRI-DEC-NNN-TARGET` selects, and this decision
adds no infrastructure. The environment descriptor must record and the run must use the products
that decision records for each capability: the container runtime hosting the web and worker roles,
the relational store, the object store, the TLS ingress, the image registry, the secret source, and
the egress identity, each with the exact version, size, and region that decision requires.

The application stack is unchanged and remains as `KHEPRI-DEC-006` recorded it: Python 3.13,
FastAPI with Uvicorn, Jinja2 templates, SQLAlchemy 2 with Psycopg 3 and Alembic, Polars lazy
execution with the fastexcel/calamine XLSX reader, Playwright with pinned Chromium for both HTML and
tagged PDF, and XlsxWriter for Excel.

The descriptor must additionally record, so that the software under measurement is identified
exactly:

- the OCI image digest **published to the registry `KHEPRI-DEC-NNN-TARGET` records** — the pushed
  registry digest, not a local image ID;
- the SHA-256 digest of `uv.lock`;
- the exact Python patch version;
- **the exact PostgreSQL minor version in use at the time of the run** (see below); and
- the SHA-256 digest of **the reviewed infrastructure definition `OPS1-02` establishes**.

**The form of that infrastructure definition is deliberately not named here.** `KHEPRI-DEC-006`
named a synthesized AWS CDK v2 template because `KHEPRI-DEC-005` had authorized one. No equivalent
exists for the selected target, and no active artifact establishes its form: `OPS1-02` is scoped to
provisioning through continuous integration and does not name an infrastructure-as-code tool.
Naming one here would invent infrastructure authority this decision does not carry. The requirement
is therefore stated as a class — the reviewed definition that slice establishes, whose form that
slice records — and the concrete artifact is a recorded open question below.

### The PostgreSQL minor version is part of the measured environment

New, and the reason it is new is specific to the selected target.

`KHEPRI-DEC-006` inherited a relational store whose automatic minor upgrades were disabled, so the
minor version could not move underneath a run. `KHEPRI-DEC-NNN-TARGET` selects a managed product
whose provider does not permit disabling updates, and governs the resulting risk by recording the
exact minor version and treating a change to it as an `environment_digest`-affecting event.

That obligation lands here, because this decision owns `environment_digest`. Two requirements
follow:

- the environment descriptor records the exact PostgreSQL minor version; and
- a run is certified only when the **live server version matches the recorded one**. This is the
  runtime check `KHEPRI-DEC-NNN-TARGET` lists as an implementation prerequisite; without it the
  recording is a declaration only, because `resolve_approved_benchmark` reads
  `KHEPRI_BENCHMARK_ENVIRONMENT_DIGEST` as a static value
  (`src/khepri/rra/benchmark_authorization.py`) and nothing queries the live engine.

Until that check exists, no run against the selected target is governed evidence.

### Environment: parameters `KHEPRI-DEC-NNN-TARGET` does not settle

Replaces "Environment: parameters `KHEPRI-DEC-005` does not settle".

`KHEPRI-DEC-NNN-TARGET` selects products and records **provisional** starting sizes; it explicitly
defers measured sizing to `OPS1-09`. This decision does not invent any of the following:

- web and worker compute sizing on the selected products;
- the worker concurrency bound. *(The SQS maximum in-flight message count leaves this list. It
  describes a message broker `KHEPRI-DEC-008` removed, in the same way that
  `visibility_timeout_seconds`, `message_retention_seconds`, `receive_wait_seconds`, and
  `max_receive_count` leave `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml`. The bound is now the
  claim queue's, and `max_attempts` remains live because
  `src/khepri/rra/claim_queue.py` consumes it.)*
- the database tier, storage, and the PostgreSQL 17 **minor** version. Only the major version is
  pinned;
- the exact pinned Chromium build identifier. The `uv.lock` digest pins the Playwright package but
  not the browser build. *(Unchanged in substance: the target decision bakes Chromium into the image
  via the Playwright base image, so the build is transitively pinned by the image digest — but the
  identifier is still recorded, because the image digest alone does not name it.)*
- whether the benchmark executes in the authorized beta environment or a separate dedicated
  benchmark environment, and which authorization covers that environment.

The environment descriptor must record an exact value for each, because `environment_digest` covers
them and a benchmark whose sizing is unrecorded is not reproducible. Those values must be exactly
those of the reviewed infrastructure definition `OPS1-02` establishes.

Consequently, approving this decision fixes the workload, the measurement rules, the identity, and
the digest discipline. It does not by itself enable a governed benchmark run: no run can produce
approved performance evidence until the parameters above are settled by `OPS1-09` and recorded in
the environment descriptor, and until the minor-version check exists.

### Registry transition

`KHEPRI-DEC-006` has no dependents: nothing in `governance/registry.yaml` names it in a
`superseded_by` field or a `depends_on` list. Retiring it therefore does **not** produce the
predecessor breakage that retiring `KHEPRI-DEC-008` does. Verified by simulation.

1. add `KHEPRI-DEC-NNN-BENCHMARK`, `state: active`, **`depends_on: [KHEPRI-DEC-NNN-TARGET]`**;
2. `KHEPRI-DEC-006` → `state: retired`, `superseded_by: KHEPRI-DEC-NNN-BENCHMARK`.

**The `depends_on` edge is the fix for the defect this decision corrects.** Recording the dependency
in the registry rather than in prose means that if the target decision is ever retired, the
active-depends-on-retired rule fires instead of the staleness going unnoticed for a second time.

**Merge ordering is constrained, and it is not a matter of preference.** The validator rejects an
unknown dependency identifier. Verified against the real validator:

```
ERROR registry: KHEPRI-DEC-0B0: unknown dependency 'KHEPRI-DEC-0T0'
```

`KHEPRI-DEC-NNN-TARGET` must therefore be present in the registry **before, or in the same commit
as**, this decision. The full transition — the target decision's four edits plus this decision's
two — validates cleanly when applied together; verified by simulation against
`_validate_successor` and the dependency rule.

**A single combined artifact is also available.** `KHEPRI-DEC-008` superseded two decisions in one
document, so the mechanism is proven if the owner prefers one artifact over two. This draft keeps
them separate because `KHEPRI-DEC-006` is 432 lines of workload and evidence rules largely unrelated
to runtime-target selection, and a combined document would make both harder to review. The choice is
the owner's.

## Open questions

Fail-closed under Constitution V. Restated from `KHEPRI-DEC-006` with the AWS-shaped items
re-pointed, one item settled, and one item's broker half removed.

1. **Settled by implementation, recorded here rather than re-asked.** Whether the approved 50 MB
   ceiling means 50,000,000 or 52,428,800 bytes. `src/khepri/rra/persistence.py` enforces
   `size_bytes > 0 AND size_bytes <= 52428800` as a database CHECK constraint — durable schema, not
   configuration, and changing it would require a migration. The larger reading is therefore already
   binding on every stored input, and the benchmark's provisional use of it matches the shipped
   system. *(The underlying wording in `RRA-002` and `KHEPRI-DEC-003` still says "50 MB" without
   disambiguation. Aligning that text is a specification matter, not a benchmark one, and is not
   resolved here.)*
2. Web and worker compute sizing on the selected products — `OPS1-09`.
3. The worker concurrency bound — `OPS1-09`. *(SQS in-flight count removed; see above.)*
4. The database tier, storage, and PostgreSQL 17 minor version — `OPS1-09` and the environment
   descriptor.
5. The exact pinned Chromium build identifier.
6. Whether the benchmark runs in the authorized beta environment or a separate dedicated benchmark
   environment, and which authorization covers that environment.
7. The concurrent arrival pattern representing real beta load, which depends on the client count
   deferred to the beta-authorization artifact.
8. Whether a narrative-enabled benchmark and an approved provider latency budget are required
   before beta exit.
9. The cadence of full benchmark execution.
10. **New.** The form of the reviewed infrastructure definition whose digest `environment_digest`
    covers, which `OPS1-02` establishes and which no active artifact currently names.

## Exclusions

Carried forward from `KHEPRI-DEC-006` with one citation corrected. This decision does not authorize:

- provisioning, sizing, or changing any infrastructure, or any environment
  **`KHEPRI-DEC-NNN-TARGET`** did not select. *(`KHEPRI-DEC-006` cited `KHEPRI-DEC-005` here, which
  is retired.)*
- any benchmark input derived from customer data, or any benchmark run in an environment holding
  customer content;
- load, capacity, soak, concurrency, or multi-tenant performance testing;
- narrative provider use, or any relaxation of the data-processing-agreement and Zero Data
  Retention gates carried forward by `KHEPRI-DEC-NNN-TARGET`;
- weakening the 95% objective, the ten-minute deadline, the 50 MB ceiling, or any privacy,
  isolation, validation, reconciliation, provenance, language-parity, or deletion control in order
  to improve a measured time;
- beta launch, client count, or observation period;
- treating a benchmark result, a passing CI run, or any automation output as human approval.

## Consequences

- `KHEPRI-DEC-006` moves to `retired`, retaining its approval evidence unchanged.
- The benchmark environment is defined by capabilities and products the target decision selects,
  rather than inherited from a retired decision.
- The registry records the dependency, so a future retirement of the target decision is caught by
  the validator instead of passing silently.
- The PostgreSQL minor version becomes part of the measured environment, and a run is certified
  only when the live version matches the recorded one.
- `OPS1-09` and `OPS1-05` can produce evidence that satisfies an active decision. Under
  `KHEPRI-DEC-006` they could not, because no FRA1 run could satisfy its environment section.
- No benchmark evidence exists until the two descriptors are created and approved, `OPS1-09`
  settles the sizing, and the minor-version check exists. A green `benchmark` CI job remains
  `NOT CERTIFIED` and is not evidence.

*(`KHEPRI-DEC-006`'s closing sentence — "This decision remains proposed until its registry entry
contains explicit approval evidence" — is not carried forward. It describes an approval ledger
Constitution II abolished: merge is approval, and the Git record supplies the approval identity,
content, and time.)*
