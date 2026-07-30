# KHEPRI-DEC-006: RRA beta benchmark workload and environment

## Context

`RRA-007` requires demonstrating that at least 95% of valid beta datasets of 50 MB or less
produce the complete bundle within ten minutes "under an approved benchmark workload and
environment". `KHEPRI-DEC-003` states the same objective as a beta-boundary condition, and
`KHEPRI-DEC-005` lists it among the demonstrations required before beta launch.

The fail-closed enforcement primitive already exists. `src/khepri/rra/performance.py` refuses
to evaluate a run without a `BenchmarkIdentity` carrying `benchmark_id`, `workload_digest`,
`environment_digest`, and `approval_ref`, refuses a `BenchmarkPolicy` that weakens either
approved number, and refuses evidence whose identity, sample count, or sample identifiers do
not match the policy.

No governance artifact defines that identity. The workload is undefined, the measurement
environment is undefined, and no rule says how either digest is computed. The objective is
therefore unmeasurable, and any number produced today would be an unfalsifiable claim. This
decision closes that gap for the workload and for the digest discipline, and states explicitly
which environment parameters no approved artifact settles.

## Decision

Define one governed benchmark, `KHEPRI-BMK-001`, as the sole approved workload and environment
for the `RRA-007` completion objective during the private beta.

### Benchmark identity

- `benchmark_id` is the literal string `KHEPRI-BMK-001`.
- `workload_digest` and `environment_digest` are computed as defined under "Digest
  computation".
- `approval_ref` is the repository-relative path of the approved YAML approval package that
  accepts this decision and its two descriptors under `KHEPRI-DEC-004`.

No `BenchmarkIdentity` for a governed run may be constructed before that approval package
exists in an approved state. Placeholder identity values in tests are fixtures, not authority.

### Governed descriptor artifacts

The benchmark is defined by two governed YAML documents:

- `governance/benchmarks/KHEPRI-BMK-001-workload.yaml`
- `governance/benchmarks/KHEPRI-BMK-001-environment.yaml`

This decision fixes their required content and the digest rule over them. It does not add them:
this slice ships no code and no descriptor. They are added by a later specification-linked
slice and approved with this decision, or in a package that supersedes its approval.

`governance/benchmarks/` is a new directory that `governance/README.md` does not yet enumerate,
and the identifier is deliberately prefixed `KHEPRI-` rather than `RRA-` so that it cannot be
read as a specification in the `RRA` family, whose prefix the specification registry enforces.
Aligning `governance/README.md` with the new directory is a follow-on obligation of the change
that adds the descriptors, not of this decision, which modifies no existing governance
document.

Both descriptors are immutable under one approval. Any byte change produces a different digest,
which changes the `BenchmarkIdentity` and, by the identity check in
`src/khepri/rra/performance.py`, invalidates every earlier run's evidence.

### Workload: dataset population

The workload is exactly 40 synthetic datasets. No customer data, and no dataset derived from
customer data, is admitted into the benchmark.

The count is decided here. Its lower bound is derived: the enforcement primitive compares
`on_time_count * 100` against `sample_count * minimum_on_time_percent` in integer arithmetic,
so 95% is exactly representable only when the sample count is a multiple of 20. At 20 the
objective tolerates one miss, which makes a single outlier decisive. Forty samples keep the
threshold exact, tolerate two misses out of forty, and remain small enough to regenerate and
rerun.

Datasets are distributed across the governed size bands, using the byte-exact band edges
already governed by `MAX_DATASET_SIZE_BYTES` and the telemetry band vocabulary:

| Band         | Stored input size, bytes inclusive | Datasets |
| ------------ | ---------------------------------- | -------- |
| `le_1_mib`   | 1 to 1,048,576                     | 4        |
| `le_10_mib`  | 1,048,577 to 10,485,760            | 8        |
| `le_25_mib`  | 10,485,761 to 26,214,400           | 12       |
| `le_50_mib`  | 26,214,401 to 52,428,800           | 16       |

The distribution is decided here. It weights the two largest bands because that is where the
ten-minute objective is at risk, and retains the smallest band because fixed costs — Chromium
start-up, template preload, connection establishment, six-surface rendering — dominate small
inputs and regress independently of dataset size.

The ceiling is the binary reading, 52,428,800 bytes. The prose of `RRA-002` and
`KHEPRI-DEC-003` says fifty megabytes; the enforcement primitive implements `50 * 1024 * 1024`.
Benchmarking the larger reading is the fail-closed choice, because a population bounded at
52,428,800 bytes contains every dataset bounded at 50,000,000 bytes. Which reading the prose
intends is recorded below as an open question, so this ceiling is provisional even though the
benchmark encodes a value for it.

Within each band the datasets divide equally into four combinations of input format and column
profile — CSV/core, CSV/extended, XLSX/core, XLSX/extended — which is exact because every band
count is a multiple of four. Both formats are required because `KHEPRI-DEC-005` selects two
distinct read paths, Polars for CSV and fastexcel/calamine for XLSX. Band membership is decided
by stored input byte size, never by row count, because the same rows do not produce the same
bytes in both formats.

Each band must contain at least one CSV dataset whose stored size equals the band's upper edge
exactly. XLSX outputs are compressed containers whose exact byte size is not directly
controllable, so each band's XLSX datasets are generated from exact row counts recorded in the
descriptor, and the resulting byte size must fall within the band.

`sample_id` values are `KHEPRI-BMK-001-01` through `KHEPRI-BMK-001-40` in descriptor order.
They are opaque and content-free, and the enforcement primitive rejects duplicates.

### Workload: dataset shape

Every dataset must be a valid beta dataset under `RRA-003`: an admissible time field, an
answerable core retail measure, no unresolved ambiguous or conflicting mapping. Two column
profiles are fixed, both using unambiguous labels that map to one governed retail semantic
each.

Core profile, eight columns in this order:

| Column             | Governed semantic  | Type                               |
| ------------------ | ------------------ | ---------------------------------- |
| `transaction_id`   | `transaction_id`   | text                               |
| `transaction_date` | `transaction_date` | ISO 8601 calendar date             |
| `product`          | `product`          | text                               |
| `category`         | `category`         | text                               |
| `store`            | `store`            | text                               |
| `channel`          | `channel`          | text                               |
| `units`            | `units`            | positive integer                   |
| `net_sales`        | `revenue`          | decimal, exactly two fraction digits |

Extended profile, the core profile followed by four further columns:

| Column            | Governed semantic          | Type                                 |
| ----------------- | -------------------------- | ------------------------------------ |
| `cogs`            | `cost`                     | decimal, exactly two fraction digits |
| `discount_value`  | `discount`                 | decimal, exactly two fraction digits |
| `refund_value`    | `returns`                  | decimal, exactly two fraction digits |
| `customer_email`  | none — personal-data shape | text                                 |

The core profile answers the `RRA-004` core KPIs: revenue, units, transactions, average order
value, and average selling price, with product, category, store, and channel comparisons and
governed time trends. The extended profile additionally answers gross profit and margin,
discounts, and returns, so the conditional-metric and caveat paths are measured rather than
skipped.

`customer_email` is present deliberately, so that the `RRA-003` personal-data detection and
exclusion path is inside the measured interval instead of being untimed. Its values are
synthetic addresses in the `example.invalid` reserved domain of RFC 2606 and are never
routable, never customer-derived, and never personal data. The benchmark run must assert that
the column is detected as personal-data risk and excluded from narrative and reporting inputs.

Further shape parameters, all decided here so the generator is deterministic:

- Transaction dates span exactly the 24 consecutive calendar months from `2024-07-01` to
  `2026-06-30` inclusive, so that year-over-year trends and full date-coverage profiling are
  exercised in every band. No approved artifact settles this anchor; determinism requires a
  fixed one, and this is it.
- Dimension cardinalities are 500 products, 12 categories, 25 stores, and 3 channels: enough to
  exercise every governed dimension comparison without letting dimension cardinality dominate
  grouping cost.
- One currency, `AED`. No approved artifact settles the benchmark currency; a single currency is
  required because multi-currency input is excluded from the beta, and this code merely follows
  the region `KHEPRI-DEC-005` selects rather than being authorized by it. Monetary columns are
  written as exact decimal strings with exactly two fraction digits. No binary floating-point
  value is ever written, which the `KHEPRI-DEC-005` rule that binary floats are never
  authoritative financial facts does require.
- `units` is an integer from 1 to 20 inclusive.
- `discount_value` is non-zero on 30% of rows and `refund_value` on 5% of rows, by seeded draw.
- Row counts are derived from the target byte size or the recorded row count, never chosen
  independently, and are recorded per dataset in the descriptor.

If any of the 40 datasets is not admitted by `RRA-003`, the benchmark run is void and the
descriptor is defective. A rejected dataset is never recorded as a missed sample and never
reduces the population: the enforcement primitive requires exactly the expected sample count,
so a short run fails closed as tampered evidence rather than passing on 39 samples.

### Workload: determinism and regeneration

A workload that cannot be regenerated identically cannot have a stable `workload_digest`.

- Generation uses a versioned deterministic generator in the product codebase, identified in
  the descriptor by module path and `generator_version`.
- The descriptor records one `master_seed`. Each dataset's seed is the first eight bytes,
  big-endian, of `SHA-256("<master_seed>:<sample_id>")`.
- The descriptor records the SHA-256 digest of every generated input file. Regeneration must
  reproduce every digest byte for byte; any mismatch voids the run.
- Generation is free of wall-clock, locale, environment, and iteration-order dependence: fixed
  `PYTHONHASHSEED=0`, UTC only, explicit column order, UTF-8 without BOM, `\n` line endings,
  and explicit quoting rules for CSV.

### Workload: narrative disposition

The benchmark runs with the narrative adapter disabled, and the measured bundle is the
deterministic facts-only bundle in Arabic and English across web, PDF, and Excel, carrying the
`RRA-006` disclosures that the analysis is automatically generated and that narrative was
omitted.

Two reasons, both fail-closed. `KHEPRI-DEC-005` keeps the OpenAI adapter disabled until an
executed data-processing agreement and verified Zero Data Retention configuration exist, and
this decision does not verify those gates. Separately, provider latency is external, variable,
and version-dependent, so a workload including live provider calls could not hold a stable
digest or be reproduced.

Whether a narrative-enabled benchmark and a provider latency budget are additionally required
before beta exit is recorded below as an open question.

### Measured interval and completion definition

`duration_ms` for a dataset is measured from the instant the validated upload is durably stored
and its report job is enqueued, to the instant the complete bundle is delivered. Queue time is
inside the interval; excluding it would weaken the objective, and `RRA-007` requires queue time
to be recorded in any case.

A sample sets `complete_bundle` only when all six surfaces — Arabic and English web, PDF, and
Excel — are stored, bound to one fact-package version and provenance record, reconciled to the
same fact and citation identifiers, and carrying the required disclosures. Any partial export
is an incomplete bundle under `RRA-006` and is recorded as a miss, not as a shorter success.

Datasets are submitted sequentially, one in flight at a time, in descriptor order, with no
other workload in the environment. This isolates the bundle-production path. It is not a load,
capacity, soak, or concurrency test: the arrival pattern of real beta traffic depends on the
client count, which `KHEPRI-DEC-003` and the `RRA-007` operational gate explicitly defer to a
separate beta-authorization artifact. Sequential submission is therefore a provisional value
chosen so that the measurement is defined at all, not a settled representation of beta load, and
the arrival pattern is recorded below as an open question.

Every sample record is content-free. It carries `sample_id`, `dataset_size_bytes`,
`duration_ms`, and `complete_bundle` only, matching the enforcement primitive's evidence shape
and the `RRA-007` and `KHEPRI-DEC-005` content-free telemetry rules.

### Environment: pinned by KHEPRI-DEC-005

The benchmark environment is the architecture `KHEPRI-DEC-005` already selected, and this
decision adds no infrastructure. From its "Cloud provider and deployment" section, the
environment descriptor must record and the run must use:

- Amazon Web Services in region `me-central-1`, with no cross-region replication or
  multi-region copy of any kind.
- Amazon ECS on AWS Fargate running separate web and bounded-worker services from one image in
  Amazon ECR, behind an Application Load Balancer terminating public HTTPS, in private subnets
  with least-privilege security groups and IAM task roles.
- Amazon RDS for PostgreSQL 17, Multi-AZ, encrypted storage and backups, TLS connections, and
  an AWS KMS customer-managed key.
- Amazon S3, private, non-versioned, SSE-KMS with a customer-managed key, blocked public
  access, opaque keys, checksum verification, and the seven-day expiration rule.
- Amazon SQS Standard with visibility-timeout heartbeats, bounded retries, and a dead-letter
  queue, with PostgreSQL owning idempotency and leases.
- AWS Secrets Manager for runtime secrets; AWS CloudTrail and KMS auditing infrastructure
  access without customer content.
- Infrastructure defined by AWS CDK v2 in Python; the image built and published through GitHub
  Actions.

From its application stack: Python 3.13, FastAPI with Uvicorn, Jinja2 templates, SQLAlchemy 2
with Psycopg 3 and Alembic, Polars lazy execution with the fastexcel/calamine XLSX reader,
Playwright with pinned Chromium for both HTML and tagged PDF, and XlsxWriter for Excel.

The descriptor must additionally record, so that the software under measurement is identified
exactly: the OCI image digest published to ECR, the SHA-256 digest of `uv.lock`, the exact
Python patch version, and the SHA-256 digest of the reviewed synthesized CDK template.

### Environment: parameters KHEPRI-DEC-005 does not settle

`KHEPRI-DEC-005` selects services, not sizes. It does not fix any of the following, and this
decision does not invent them:

- Fargate task CPU and memory for the web service and for the worker service.
- The worker concurrency bound and the SQS maximum in-flight message count. `KHEPRI-DEC-005`
  requires them to be bounded by configured budgets; it names no value.
- The RDS instance class, storage type, and provisioned IOPS, and the PostgreSQL 17 minor
  version. Only the major version is pinned.
- The exact pinned Chromium build identifier. `KHEPRI-DEC-005` requires Chromium to be pinned,
  scanned, preloaded, and benchmarked, and names no build. The `uv.lock` digest pins the
  Playwright package but not the browser build that `playwright install` fetches.
- Whether the benchmark executes in the authorized beta environment or in a separate dedicated
  benchmark environment. `KHEPRI-DEC-005` requires an explicit protected-environment
  authorization for beta deployment and authorizes no second environment.

The environment descriptor must record an exact value for each of these fields, because the
`environment_digest` covers them and a benchmark whose sizing is unrecorded is not
reproducible. Those values must be exactly those of the reviewed AWS CDK v2 definition that
`KHEPRI-DEC-005` authorizes as the source of reproducible infrastructure. No such definition
exists in this repository yet.

Consequently, approving this decision fixes the workload, the measurement rules, the identity,
and the digest discipline. It does not by itself enable a governed benchmark run: no run can
produce approved performance evidence until the parameters above are settled by an artifact
carrying infrastructure authority, and recorded in the environment descriptor.

### Digest computation

Both digests reuse the existing digest discipline unchanged, so that two people computing them
independently get the same value.

```text
uv run khepri-gov document-digest governance/benchmarks/KHEPRI-BMK-001-workload.yaml
uv run khepri-gov document-digest governance/benchmarks/KHEPRI-BMK-001-environment.yaml
```

`workload_digest` is the verbatim first line of the first command's output and
`environment_digest` the verbatim first line of the second. Each is `sha256:` followed by the
lowercase hexadecimal SHA-256 of the file's exact bytes, as implemented by `document_digest` in
`src/khepri_gov/approval_packages.py`. Neither value is transformed, re-serialized, truncated,
or normalized before it is placed in a `BenchmarkIdentity`.

Because the digest is over bytes, both descriptors are written under a fixed byte discipline:
UTF-8 without BOM, `\n` line endings, no trailing whitespace, exactly one final newline, no tab
indentation, the YAML 1.2 safe subset only, and top-level keys in the order this decision lists
them. A formatting-only edit is a material change, because it produces a different digest and
invalidates prior evidence.

The same commands compute the document digests that the approval package for this decision and
its descriptors must carry, and `uv run khepri-gov approval-digest` computes that package's
manifest digest.

### The existing harness does not yet satisfy this decision

`src/khepri/rra/benchmark_workload.py`, `src/khepri/rra/benchmark.py`, and the CI `benchmark`
job merged before this decision was written. They are a correct enforcement path for the
`RRA-007` requirement that CI fail on an exceeded tolerance, and they remain so. They are not an
implementation of `KHEPRI-BMK-001`, and a run of them certifies nothing about this benchmark.
Recording that here, rather than adjusting this decision to match them, is deliberate: a
governed workload is defined by the approved artifact and implemented by code, never the
reverse.

The two are incompatible at the digest, not merely different in detail. `certify_benchmark`
compares `approved.workload.digest` against `approved.identity.workload_digest`, and
`BenchmarkWorkload.digest` returns `WORKLOAD_VERSION` followed by a SHA-256 over the datasets it
generated — the literal prefix `rra007.workload.v1:`. This decision requires `workload_digest`
to be the `sha256:`-prefixed document digest of `KHEPRI-BMK-001-workload.yaml`. The two strings
cannot be equal for any input, so populating the six repository variables from an approved
record while that comparison stands makes every run raise `BenchmarkTampered`. That is the
fail-closed rule behaving correctly on a real inconsistency; it is a defect to repair in the
descriptor slice, not a steady state to leave in place.

The workload the merged builder produces also diverges from the population fixed above, in ways
that each remove something this decision requires be measured:

| This decision | The merged builder |
| ------------- | ------------------ |
| 40 datasets across four byte-size bands, 4/8/12/16 | `sample_count` datasets of one uniform row count |
| CSV and XLSX, exercising both `KHEPRI-DEC-005` read paths | CSV only; the fastexcel/calamine path is never timed |
| Core profile of eight columns, extended profile of twelve | Six columns: `date,revenue,units,invoice_no,category,branch` |
| `customer_email`, so `RRA-003` personal-data detection is inside the measured interval | No personal-data column; that path is untimed |
| 24 consecutive months, `2024-07-01` to `2026-06-30` | 28 days of a single month |
| 500 products, 12 categories, 25 stores, 3 channels | 4 categories, 3 branches; no product, store, or channel |
| `sample_id` `KHEPRI-BMK-001-01` through `-40` | `sample_0000` upward |
| One `master_seed`, per-dataset seeds from `SHA-256("<master_seed>:<sample_id>")` | Arithmetic derivation from sample and row index |
| A recorded SHA-256 per generated input file, reproduced byte for byte | No recorded per-file digest to reproduce against |

Reworking those two modules to this population, and replacing the content-address comparison
with one over the approved descriptor bytes, is an obligation of the slice that adds the
descriptors. It is not authorized ahead of this decision's approval, and nothing above is
relaxed to shorten it. Until that slice lands, no `BenchmarkIdentity` for a governed run may be
constructed — which the absence of an approved record already enforces, because the gate reports
`NOT CERTIFIED` and measures nothing when the variables are unset.

### Completion objective, restated and not weakened

At least 95% of the 40 benchmark datasets, none exceeding 52,428,800 bytes, must produce a
complete bundle within 600,000 milliseconds. With 40 samples that is at least 38 on-time
complete bundles. Neither number may be relaxed for any reason, including latency work,
provider behaviour, infrastructure cost, or CI duration.

This is not merely asserted. `src/khepri/rra/performance.py` fixes `MINIMUM_ON_TIME_PERCENT` at
95, `MAX_DURATION_MS` at 600,000, and `MAX_DATASET_SIZE_BYTES` at 52,428,800, and actively
refuses a weaker policy: `_require_completion_objective` raises on any minimum below 95 and
`_require_completion_deadline` raises on any deadline above 600,000, both with the message that
the approved completion objective cannot be weakened. A dataset size above the ceiling is
refused outright. Weakening the objective is therefore not a configuration change; it requires
changing governed constants, which requires a superseding decision.

Per `RRA-007`, the recorded run is evaluated through `enforce_performance` in CI, and CI fails
on `PerformanceRegression` or `BenchmarkTampered`.

## Open questions

Fail-closed under Article V: no approved artifact settles the following, and this decision does
not settle them by assumption.

Items 1 and 7 carry a provisional value in the workload above, because a benchmark with no
ceiling and no arrival pattern is not a definition at all. In both cases the value is the
conservative or the isolating one, it is labelled provisional where it appears, and it remains
open here. Items 2 through 6 carry no value anywhere in this decision: the descriptor must record
them and this decision does not choose them.

1. Whether the approved 50 MB ceiling in `RRA-002` and `KHEPRI-DEC-003` means 50,000,000 bytes
   or 52,428,800 bytes. The benchmark provisionally uses the larger reading because it is the
   conservative one.
2. Fargate task CPU and memory for the web and worker services.
3. The worker concurrency bound and SQS maximum in-flight count.
4. The RDS instance class, storage type, provisioned IOPS, and PostgreSQL 17 minor version.
5. The exact pinned Chromium build identifier.
6. Whether the benchmark runs in the authorized beta environment or a separate dedicated
   benchmark environment, and which authorization covers that environment.
7. The concurrent arrival pattern representing real beta load, which depends on the client
   count that `KHEPRI-DEC-003` and the `RRA-007` operational gate defer to the
   beta-authorization artifact.
8. Whether a narrative-enabled benchmark and an approved provider latency budget are required
   before beta exit.
9. The cadence of full benchmark execution — every pull request, or release-gated — given that
   `RRA-007` requires CI to fail on an exceeded tolerance but does not state how often the full
   run executes.

## Exclusions

This decision does not authorize:

- provisioning, sizing, or changing any infrastructure, or any environment `KHEPRI-DEC-005` did
  not select;
- any benchmark input derived from customer data, or any benchmark run in an environment
  holding customer content;
- load, capacity, soak, concurrency, or multi-tenant performance testing;
- narrative provider use, or any relaxation of the data-processing-agreement and Zero Data
  Retention gates in `KHEPRI-DEC-005`;
- weakening the 95% objective, the ten-minute deadline, the 50 MB ceiling, or any privacy,
  isolation, validation, reconciliation, provenance, language-parity, or deletion control in
  order to improve a measured time;
- beta launch, client count, or observation period, all of which remain with the separate
  beta-authorization artifact;
- treating a benchmark result, a passing CI run, or any automation output as human approval.

## Consequences

- The `RRA-007` completion objective becomes measurable: a run can now be tied to a named
  workload, a named environment, and a named approval.
- Changing the workload or the environment changes a descriptor's bytes, changes its digest,
  changes the `BenchmarkIdentity`, and invalidates all prior evidence by the identity check in
  `src/khepri/rra/performance.py`. Such a change requires a new or superseding decision and a
  new approval package; it is never a configuration edit.
- Benchmark evidence remains content-free and cannot be correlated to any customer, because the
  entire population is synthetic and every sample record carries only opaque identifiers,
  sizes, durations, and a completion flag.
- The nine open questions above block a governed benchmark run. Until they are settled and the
  two descriptors exist and are approved, no performance evidence for beta exit can be
  produced, and none may be claimed.
- The CI gate is already wired to `enforce_performance`, and it reports `NOT CERTIFIED` on every
  run because no approved record supplies the identity. A green `benchmark` job is therefore not
  evidence about this or any benchmark, and must never be cited as any.
- The follow-on obligations created here are: add the two descriptors and the deterministic
  generator in specification-linked slices, rework `benchmark_workload.py` and the
  `certify_benchmark` digest comparison to this population and this digest rule as recorded
  above, and settle the environment sizing under infrastructure authority.

This decision remains proposed until its registry entry contains explicit approval evidence.
