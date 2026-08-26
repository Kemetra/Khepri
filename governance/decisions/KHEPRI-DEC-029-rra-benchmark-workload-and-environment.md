# KHEPRI-DEC-029: RRA beta benchmark workload and environment

> Active when merged to `main`. Supersedes `KHEPRI-DEC-006`.

## Context

`KHEPRI-DEC-006` fixes the benchmark workload, the measured interval, the digest rule, and the
completion objective. Those are provider-neutral and are not in question here. They are carried
forward unchanged.

Its environment sections are not provider-neutral. They are inherited by reference under a heading
reading "Environment: pinned by `KHEPRI-DEC-005`", and `KHEPRI-DEC-005` is retired. An active
decision therefore drew a live requirement from a retired one.

The validator does not catch this. `governance/registry.yaml` records `KHEPRI-DEC-006` with
`depends_on: []`, and the active-depends-on-retired rule in `src/khepri_gov/validator.py` fires on
registry dependencies, not on prose citations. `khepri-gov validate` passes and says nothing about
the staleness. This decision records the dependency in the registry so the same defect is caught
next time.

### What actually breaks

`KHEPRI-DEC-006` requires the run to use AWS `me-central-1`, ECS on Fargate, ECR, an Application
Load Balancer, RDS PostgreSQL Multi-AZ, S3 with SSE-KMS, SQS Standard with a dead-letter queue,
Secrets Manager, CloudTrail, KMS, and AWS CDK v2 — and requires `environment_digest` to cover "the
SHA-256 digest of the reviewed synthesized CDK template".

Against the target `KHEPRI-DEC-028` selects, three of those are not merely different but absent:
SQS was removed in favour of a PostgreSQL claim queue; no CDK template exists for a DigitalOcean
target; and no customer-managed key exists, because encryption moved into the application. A FRA1
run could not satisfy this decision, and `environment_digest` could not be computed as specified.

`KHEPRI-DEC-008` recorded that `KHEPRI-DEC-006`'s workload "is provider-neutral and is unaffected"
by the change of host. That was accurate about the **workload** and was never a statement about the
**environment**, whose sections this decision replaces.

### Why this is a bounded change

`KHEPRI-DEC-006` already delegates the concrete environment downstream. It states that approving it
"fixes the workload, the measurement rules, the identity, and the digest discipline. It does not by
itself enable a governed benchmark run", and records that no infrastructure definition exists in the
repository. The AWS service list is an inherited snapshot, not the operative evidence rule.
Replacing the inheritance leaves the evidence contract intact. Neither
`governance/benchmarks/KHEPRI-BMK-001-workload.yaml` nor
`governance/benchmarks/KHEPRI-BMK-001-environment.yaml` has ever been created, so this changes a
requirement rather than a shipped artifact.

## Decision

This decision supersedes `KHEPRI-DEC-006` and restates it in full. Everything not marked as changed
is carried forward unchanged.

### Benchmark identity

- `benchmark_id` is the literal string `KHEPRI-BMK-001`.
- `workload_digest` and `environment_digest` are computed as defined under "Digest computation".
- `approval_ref` is the immutable Git commit identifier or URL for the owner-merged change that
  activates the benchmark identity and its descriptors.

No `BenchmarkIdentity` for a governed run may be constructed before that change is merged to `main`.
Placeholder identity values in tests are fixtures, not authority.

### Governed descriptor artifacts

The benchmark is defined by two governed YAML documents:

- `governance/benchmarks/KHEPRI-BMK-001-workload.yaml`
- `governance/benchmarks/KHEPRI-BMK-001-environment.yaml`

This decision fixes their required content and the digest rule over them. It does not add them.
They are added by a later specification-linked slice and become governing when the owner merges
that change to `main`.

Both descriptors are immutable under one approval. Any byte change produces a different digest,
which changes the `BenchmarkIdentity` and, by the identity check in
`src/khepri/rra/performance.py`, invalidates every earlier run's evidence.

### Workload: dataset population

Carried forward unchanged. The workload is exactly 40 synthetic datasets. No customer data, and no
dataset derived from customer data, is admitted.

The count is derived: the enforcement primitive compares `on_time_count * 100` against
`sample_count * minimum_on_time_percent` in integer arithmetic, so 95% is exactly representable
only when the sample count is a multiple of 20. At 20 the objective tolerates one miss, which makes
a single outlier decisive. Forty samples keep the threshold exact, tolerate two misses, and remain
small enough to regenerate and rerun.

| Band | Stored input size, bytes inclusive | Datasets |
| ---- | ---------------------------------- | -------- |
| `le_1_mib` | 1 to 1,048,576 | 4 |
| `le_10_mib` | 1,048,577 to 10,485,760 | 8 |
| `le_25_mib` | 10,485,761 to 26,214,400 | 12 |
| `le_50_mib` | 26,214,401 to 52,428,800 | 16 |

The distribution weights the two largest bands because that is where the ten-minute objective is at
risk, and retains the smallest band because fixed costs — Chromium start-up, template preload,
connection establishment, six-surface rendering — dominate small inputs and regress independently
of dataset size.

Within each band the datasets divide equally into four combinations of input format and column
profile — CSV/core, CSV/extended, XLSX/core, XLSX/extended — which is exact because every band
count is a multiple of four. Both formats are required because two distinct read paths exist:
Polars for CSV and fastexcel/calamine for XLSX. Band membership is decided by stored input byte
size, never by row count.

Each band must contain at least one CSV dataset whose stored size equals the band's upper edge
exactly. XLSX outputs are compressed containers whose exact byte size is not directly controllable,
so each band's XLSX datasets are generated from exact row counts recorded in the descriptor, and
the resulting byte size must fall within the band.

`sample_id` values are `KHEPRI-BMK-001-01` through `KHEPRI-BMK-001-40` in descriptor order. They
are opaque and content-free, and the enforcement primitive rejects duplicates.

### Workload: dataset shape

Carried forward unchanged. Every dataset must be a valid beta dataset under `RRA-003`: an
admissible time field, an answerable core retail measure, no unresolved ambiguous or conflicting
mapping.

Core profile, eight columns in this order: `transaction_id`, `transaction_date`, `product`,
`category`, `store`, `channel`, `units`, `net_sales`. Extended profile adds `cogs`,
`discount_value`, `refund_value`, and `customer_email`.

`customer_email` is present deliberately, so that the `RRA-003` personal-data detection and
exclusion path is inside the measured interval instead of being untimed. Its values are synthetic
addresses in the `example.invalid` reserved domain of RFC 2606 and are never routable, never
customer-derived, and never personal data. The benchmark run must assert that the column is
detected as personal-data risk and excluded from narrative and reporting inputs.

Further shape parameters, all fixed so the generator is deterministic: transaction dates span the
24 consecutive calendar months from `2024-07-01` to `2026-06-30` inclusive; dimension cardinalities
are 500 products, 12 categories, 25 stores, and 3 channels; one currency, `AED`, with monetary
columns written as exact decimal strings with exactly two fraction digits and no binary
floating-point value ever written; `units` is an integer from 1 to 20 inclusive;
`discount_value` is non-zero on 30% of rows and `refund_value` on 5%, by seeded draw; row counts
are derived from the target byte size or the recorded row count and are recorded per dataset.

If any of the 40 datasets is not admitted by `RRA-003`, the benchmark run is void and the
descriptor is defective. A rejected dataset is never recorded as a missed sample and never reduces
the population: the enforcement primitive requires exactly the expected sample count, so a short
run fails closed as tampered evidence rather than passing on 39 samples.

### Workload: determinism and regeneration

Carried forward unchanged.

- Generation uses a versioned deterministic generator in the product codebase, identified in the
  descriptor by module path and `generator_version`.
- The descriptor records one `master_seed`. Each dataset's seed is the first eight bytes,
  big-endian, of `SHA-256("<master_seed>:<sample_id>")`.
- The descriptor records the SHA-256 digest of every generated input file. Regeneration must
  reproduce every digest byte for byte; any mismatch voids the run.
- Generation is free of wall-clock, locale, environment, and iteration-order dependence: fixed
  `PYTHONHASHSEED=0`, UTC only, explicit column order, UTF-8 without BOM, `\n` line endings, and
  explicit quoting rules for CSV.

### Workload: narrative disposition

Carried forward unchanged. The benchmark runs with the narrative adapter disabled, and the measured
bundle is the deterministic facts-only bundle in Arabic and English across web, PDF, and Excel,
carrying the `RRA-006` disclosures that the analysis is automatically generated and that narrative
was omitted.

Two reasons, both fail-closed. The OpenAI adapter remains disabled until an executed
data-processing agreement and verified Zero Data Retention configuration exist, and this decision
does not verify those gates. Separately, provider latency is external, variable, and
version-dependent, so a workload including live provider calls could not hold a stable digest or be
reproduced.

### Measured interval and completion definition

Carried forward unchanged. `duration_ms` for a dataset is measured from the instant the validated
upload is durably stored and its report job is enqueued, to the instant the complete bundle is
delivered. Queue time is inside the interval.

A sample sets `complete_bundle` only when all six surfaces — Arabic and English web, PDF, and
Excel — are stored, bound to one fact-package version and provenance record, reconciled to the same
fact and citation identifiers, and carrying the required disclosures. Any partial export is an
incomplete bundle under `RRA-006` and is recorded as a miss, not as a shorter success.

Datasets are submitted sequentially, one in flight at a time, in descriptor order, with no other
workload in the environment. This isolates the bundle-production path. It is not a load, capacity,
soak, or concurrency test. Sequential submission is a provisional value chosen so that the
measurement is defined at all, and the arrival pattern remains an open question below.

Every sample record is content-free, carrying `sample_id`, `dataset_size_bytes`, `duration_ms`, and
`complete_bundle` only.

### Environment: pinned by `KHEPRI-DEC-028`

**Changed.** Replaces "Environment: pinned by `KHEPRI-DEC-005`".

The benchmark environment is the architecture `KHEPRI-DEC-028` selects, and this decision adds no
infrastructure. The environment descriptor must record and the run must use the products that
decision records for each capability: the container runtime hosting the web and worker roles, the
relational store, the object store, the TLS ingress, the image registry, the secret source, and the
outbound-access control, each with the exact version, size, and region that decision requires.

The application stack is unchanged: Python 3.13, FastAPI with Uvicorn, Jinja2 templates,
SQLAlchemy 2 with Psycopg 3 and Alembic, Polars lazy execution with the fastexcel/calamine XLSX
reader, Playwright with pinned Chromium for both HTML and tagged PDF, and XlsxWriter for Excel.

The descriptor must additionally record, so that the software under measurement is identified
exactly:

- the OCI image digest **published to the registry `KHEPRI-DEC-028` records** — the pushed registry
  digest, not a local image ID;
- the SHA-256 digest of `uv.lock`;
- the exact Python patch version;
- **the exact PostgreSQL minor version in use at the time of the run**; and
- the SHA-256 digest of **the reviewed infrastructure definition `OPS1-02` establishes**.

**The form of that infrastructure definition is deliberately not named here.** `KHEPRI-DEC-006`
named a synthesized AWS CDK v2 template because its predecessor had authorized one. `KHEPRI-DEC-028`
selects Terraform for long-lived infrastructure plus an App Platform specification for app roles,
but records that the exact file layout is implementation work. The requirement is therefore stated
as a class — the reviewed definition that slice establishes, whose form that slice records — and
the concrete artifact remains an open question below.

### The PostgreSQL minor version is part of the measured environment

**New**, and the reason is specific to the selected target.

`KHEPRI-DEC-006` inherited a relational store whose automatic minor upgrades were disabled, so the
minor version could not move underneath a run. `KHEPRI-DEC-028` selects a managed product whose
provider does not permit disabling updates, and governs the resulting risk by recording the exact
minor version and treating a change to it as an `environment_digest`-affecting event.

That obligation lands here, because this decision owns `environment_digest`. Three requirements
follow:

- the environment descriptor records the exact live PostgreSQL minor version, captured from the
  database after creation;
- a run is certified only when the **live server version matches the recorded one**;
- a mismatch **refuses certification**, and a provider minor change requires descriptor and digest
  re-issuance and re-evidencing of affected runs.

Without the comparison implemented, the recording is a declaration only: `resolve_approved_benchmark`
reads `KHEPRI_BENCHMARK_ENVIRONMENT_DIGEST` as a static value
(`src/khepri/rra/benchmark_authorization.py`) and nothing queries the live engine. Until that check
exists, no run against the selected target is governed evidence.

### The provisional run is exploratory; certification follows the final descriptor

**New.** `KHEPRI-DEC-030` authorizes a provisional non-production bootstrap at a measurement shape
that is explicitly not final capacity. A benchmark run against that shape is an **exploratory
measurement**, not governed certification.

The reason is this decision's own digest discipline. Approving a final environment descriptor and
sizing changes the descriptor's bytes, changes `environment_digest`, changes the
`BenchmarkIdentity`, and invalidates evidence produced under the provisional shape. Certifying from
the exploratory run would leave every downstream exercise resting on evidence its own governance
had already invalidated.

The sequence is therefore fixed:

1. run the benchmark on the provisional hosted target as an exploratory measurement;
2. approve the final environment descriptor and sizing from that measurement;
3. **re-run the governed benchmark against the final descriptor** and issue certification from that
   run.

No certification may cite the exploratory run.

### Environment: parameters `KHEPRI-DEC-028` does not settle

**Changed.** Replaces "Environment: parameters `KHEPRI-DEC-005` does not settle".

`KHEPRI-DEC-028` selects products and defers final sizing to `OPS1-09`. This decision does not
invent any of the following:

- web and worker compute sizing on the selected products;
- the worker concurrency bound. The SQS maximum in-flight message count leaves this list: it
  describes a message broker the architecture removed, in the same way that
  `visibility_timeout_seconds`, `message_retention_seconds`, `receive_wait_seconds`, and
  `max_receive_count` leave `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml`. The bound is now the
  claim queue's, and `max_attempts` remains live because `src/khepri/rra/claim_queue.py` consumes it;
- the database tier, storage, and the PostgreSQL 17 **minor** version. Only the major version is
  pinned;
- the exact pinned Chromium build identifier. The `uv.lock` digest pins the Playwright package but
  not the browser build;
- whether the benchmark executes in the authorized beta environment or a separate dedicated
  benchmark environment, and which authorization covers that environment.

The environment descriptor must record an exact value for each, because `environment_digest` covers
them and a benchmark whose sizing is unrecorded is not reproducible.

Consequently, approving this decision fixes the workload, the measurement rules, the identity, and
the digest discipline. It does not by itself enable a governed benchmark run: no run can produce
approved performance evidence until the parameters above are settled by `OPS1-09` and recorded in
the environment descriptor, and until the minor-version check exists.

### Digest computation

Carried forward unchanged. Each digest is `sha256:` followed by the lowercase hexadecimal SHA-256
of the descriptor's exact bytes. Neither value is transformed, re-serialized, truncated, or
normalized before it is placed in a `BenchmarkIdentity`.

Because the digest is over bytes, both descriptors are written under a fixed byte discipline: UTF-8
without BOM, `\n` line endings, no trailing whitespace, exactly one final newline, no tab
indentation, the YAML 1.2 safe subset only, and top-level keys in the order this decision lists
them. A formatting-only edit is a material change, because it produces a different digest and
invalidates prior evidence.

### The existing harness does not yet satisfy this decision

Carried forward unchanged. `src/khepri/rra/benchmark_workload.py`, `src/khepri/rra/benchmark.py`,
and the CI `benchmark` job are a correct enforcement path for the `RRA-007` requirement that CI
fail on an exceeded tolerance. They are not an implementation of `KHEPRI-BMK-001`, and a run of
them certifies nothing about this benchmark.

The two are incompatible at the digest. `certify_benchmark` compares `approved.workload.digest`
against `approved.identity.workload_digest`, and `BenchmarkWorkload.digest` returns
`WORKLOAD_VERSION` followed by a SHA-256 over the datasets it generated — the literal prefix
`rra007.workload.v1:`. This decision requires `workload_digest` to be the `sha256:`-prefixed
document digest. The two strings cannot be equal for any input, so populating the repository
variables from an approved record while that comparison stands makes every run raise
`BenchmarkTampered`. That is the fail-closed rule behaving correctly on a real inconsistency; it is
a defect to repair in the descriptor slice, not a steady state to leave in place.

The merged builder also diverges from the population fixed above — uniform row counts instead of
four byte-size bands, CSV only, six columns, no personal-data column, 28 days instead of 24 months,
and arithmetic seed derivation instead of the recorded per-file digests. Reworking those modules to
this population, and replacing the content-address comparison with one over the approved descriptor
bytes, is an obligation of the slice that adds the descriptors.

### Completion objective, restated and not weakened

Carried forward unchanged. At least 95% of the 40 benchmark datasets, none exceeding 52,428,800
bytes, must produce a complete bundle within 600,000 milliseconds. With 40 samples that is at least
38 on-time complete bundles. Neither number may be relaxed for any reason, including latency work,
provider behaviour, infrastructure cost, or CI duration.

`src/khepri/rra/performance.py` fixes `MINIMUM_ON_TIME_PERCENT` at 95, `MAX_DURATION_MS` at
600,000, and `MAX_DATASET_SIZE_BYTES` at 52,428,800, and actively refuses a weaker policy.
Weakening the objective is therefore not a configuration change; it requires changing governed
constants, which requires a superseding decision.

## Open questions

Fail-closed under Constitution V. Restated from `KHEPRI-DEC-006` with the AWS-shaped items
re-pointed, one item settled, and one item's broker half removed.

1. **Settled by implementation, recorded rather than re-asked.** Whether the approved 50 MB ceiling
   means 50,000,000 or 52,428,800 bytes. `src/khepri/rra/persistence.py` enforces
   `size_bytes > 0 AND size_bytes <= 52428800` as a database CHECK constraint — durable schema, not
   configuration. The larger reading is already binding on every stored input. The underlying
   wording in `RRA-002` and `KHEPRI-DEC-003` still says "50 MB" without disambiguation; aligning
   that text is a specification matter and is not resolved here.
2. Web and worker compute sizing on the selected products — `OPS1-09`.
3. The worker concurrency bound — `OPS1-09`.
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
10. The form of the reviewed infrastructure definition whose digest `environment_digest` covers,
    which `OPS1-02` establishes.

## Exclusions

Carried forward with the retired citation corrected. This decision does not authorize:

- provisioning, sizing, or changing any infrastructure, or any environment **`KHEPRI-DEC-028`** did
  not select;
- any benchmark input derived from customer data, or any benchmark run in an environment holding
  customer content;
- load, capacity, soak, concurrency, or multi-tenant performance testing;
- narrative provider use, or any relaxation of the data-processing-agreement and Zero Data
  Retention gates carried forward by `KHEPRI-DEC-028`;
- weakening the 95% objective, the ten-minute deadline, the 50 MB ceiling, or any privacy,
  isolation, validation, reconciliation, provenance, language-parity, or deletion control in order
  to improve a measured time;
- beta launch, client count, or observation period;
- treating a benchmark result, a passing CI run, or any automation output as human approval.

## Consequences

- `KHEPRI-DEC-006` moves to `retired`, retaining its evidence unchanged.
- The benchmark environment is defined by capabilities and products the target decision selects,
  rather than inherited from a retired decision.
- The registry records `depends_on: [KHEPRI-DEC-028]`, so a future retirement of the target
  decision is caught by the validator instead of passing silently — which is the defect this
  decision corrects.
- The PostgreSQL minor version becomes part of the measured environment, and a run is certified
  only when the live version matches the recorded one.
- A provisional-shape run is exploratory; certification requires a re-run against the approved final
  descriptor.
- `OPS1-09` and `OPS1-05` can produce evidence that satisfies an active decision. Under
  `KHEPRI-DEC-006` they could not, because no FRA1 run could satisfy its environment section.
- No benchmark evidence exists until the two descriptors are created and approved, `OPS1-09`
  settles the sizing, and the minor-version check exists. A green `benchmark` CI job remains
  `NOT CERTIFIED` and is not evidence.

Identity, lifecycle state, dependencies, and supersession are authoritative in
`governance/registry.yaml`. Git history retains the transition evidence.
