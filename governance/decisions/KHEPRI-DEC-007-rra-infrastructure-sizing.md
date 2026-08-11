# KHEPRI-DEC-007: RRA private-beta and benchmark infrastructure sizing

> Retired and superseded by `KHEPRI-DEC-008`.

## Context

`KHEPRI-DEC-005` selects services. It does not size them. `KHEPRI-DEC-006` records that gap as
five open questions and states plainly that approving it "does not by itself enable a governed
benchmark run: no run can produce approved performance evidence until the parameters above are
settled by an artifact carrying infrastructure authority, and recorded in the environment
descriptor."

This is that artifact. It settles `KHEPRI-DEC-006` open questions 2 through 6, which are the
questions that block the environment descriptor, and through it the AWS CDK v2 definition that
`KHEPRI-DEC-005` authorizes but which does not yet exist in this repository.

Nothing here is derived from a measurement, because no governed measurement exists yet — that is
the circularity this decision breaks. Each value below is derived from a stated property of the
workload `KHEPRI-DEC-006` fixes, or from a hard constraint of the service `KHEPRI-DEC-005`
selects. Where the honest answer is a rule rather than a number, this decision states the rule
and requires the descriptor to record the number, and says so explicitly rather than inventing a
value that would read as authority.

## Decision

### What this decision carries, and what it does not

It settles sizing for two environments: the private-beta environment `KHEPRI-DEC-005` selects,
and the dedicated benchmark environment settled below. It authorizes the CDK definition of both
to be written and the benchmark environment to be provisioned.

It does not authorize beta deployment. `KHEPRI-DEC-005` requires an explicit
protected-environment authorization for that, and this decision is not it. It does not set the
beta service desired count, autoscaling policy, or any capacity that follows from the client
count, all of which `KHEPRI-DEC-003` and the `RRA-007` operational gate reserve to the separate
beta-authorization artifact.

### Fargate task sizing — open question 2

Two task definitions, sized separately because their work is not alike.

| Parameter          | Web service      | Worker service     |
| ------------------ | ---------------- | ------------------ |
| Task CPU           | 1024 (1 vCPU)    | 4096 (4 vCPU)      |
| Task memory        | 4096 MiB         | 16384 MiB          |
| Ephemeral storage  | 20 GiB (default) | 40 GiB             |

Both pairs are valid Fargate combinations; 4 vCPU admits 8192 to 30720 MiB in 1024 MiB steps,
and 1 vCPU admits 2048 to 8192 MiB.

The worker is sized by the largest band. It holds a Polars frame derived from an input of up to
52,428,800 bytes, whose in-memory width exceeds its stored width because the extended profile
parses twelve columns into typed arrays, and it holds a pinned Chromium rendering six surfaces
including a tagged, paginated PDF. Chromium alone is the largest single consumer and does not
shrink with dataset size. 16384 MiB leaves room for the frame, its aggregation intermediates,
and the browser without swapping into a duration nobody can reproduce. 4 vCPU is chosen because
Polars parallelizes grouping and aggregation across cores, and because the `RRA-006` surfaces are
produced from one fact package where per-surface work can overlap; below 4 vCPU the ten-minute
objective would be decided by core count rather than by the pipeline.

40 GiB of ephemeral storage covers the baked browser, the downloaded input, six rendered
surfaces, and the XlsxWriter and PDF temporaries at the largest band, with margin. 20 GiB is the
Fargate default and 21 GiB the smallest configurable value, so the worker's figure is a real
configuration and the web service's is the default recorded explicitly so the digest covers it.

The web service renders Jinja2 templates, streams uploads to S3, and enqueues jobs. It performs
no rendering and holds no fact package. 1 vCPU is sufficient; 4096 MiB rather than the 2048 MiB
floor because several concurrent uploads bounded at 52,428,800 bytes each hold buffers even when
streamed, and the floor would make a burst of uploads an out-of-memory event rather than a slow
one.

**Chromium and `/dev/shm`.** Fargate fixes `/dev/shm` at 64 MiB and does not support
`linuxParameters.sharedMemorySize`, which is an EC2-launch-type parameter. Chromium's default
shared-memory use exceeds 64 MiB while rendering a paginated document and fails in a way that
presents as a renderer crash rather than as a memory limit. The worker must therefore launch
Chromium with `--disable-dev-shm-usage`, which moves those allocations to the task's ephemeral
storage that the paragraph above sizes. This is a correctness requirement, not a tuning flag: it
is why the ephemeral storage figure and the browser configuration are one decision.

### Worker concurrency and queue bounds — open question 3

- Report jobs processed concurrently per worker task: **1**.
- SQS messages in flight per worker task: **1**, with `MaxNumberOfMessages=1`.
- SQS receive wait time: **20 seconds** (long polling).
- SQS visibility timeout: **300 seconds**, extended by heartbeat.
- Heartbeat interval: **60 seconds**.
- PostgreSQL lease duration (`lease_for`): **300 seconds**.
- Retry delay (`retry_delay`): **60 seconds**.
- SQS `maxReceiveCount` before the dead-letter queue: **3**.
- PostgreSQL `max_attempts`: **3**.
- SQS message retention: **14 days**.

One job per task, rather than a higher in-task bound, because the sizing above is the sizing of
exactly one pipeline. A second concurrent job in the same task would contend for the same four
cores during Chromium rendering and could exceed 16384 MiB whenever two large-band datasets met,
which makes `duration_ms` a function of what else happened to be running. The `KHEPRI-DEC-006`
measured interval includes queue time precisely so that waiting is counted honestly instead of
hidden by in-task overlap, so throughput is bought by task count and never by in-task
concurrency. It also makes the sequential submission `KHEPRI-DEC-006` requires a property of the
deployment rather than of the harness.

The visibility timeout and the PostgreSQL lease are deliberately the same 300 seconds so that
SQS invisibility and the database lease expire together. Different values would produce a window
in which one of the two believes the job is owned and the other does not, and `KHEPRI-DEC-005`
makes PostgreSQL the owner of idempotency and leases specifically so that no such window is
load-bearing. Both are shorter than the 600,000 ms deadline because heartbeats extend them; a
lease longer than the deadline would delay recovery of a task that died, which `RRA-007` requires
be detected.

`maxReceiveCount` and `max_attempts` are both 3 because they must be equal. If SQS exhausted
first, the message would reach the dead-letter queue while PostgreSQL still considered attempts
available, and the governed dead-letter reason would be absent or wrong; the merged
`job_persistence` records `DEAD_LETTER_RETRIES_EXHAUSTED` as a distinct reason from
`DEAD_LETTER_CONTENT_DELETED`, and that distinction only survives if the two bounds agree.

Service desired count is **exactly 1 task** in the benchmark environment, which is what makes
`KHEPRI-DEC-006` sequential submission true by construction. The beta desired count and
autoscaling are not set here; see "What this decision carries".

### PostgreSQL instance and storage — open question 4

| Parameter                   | Value                                |
| --------------------------- | ------------------------------------ |
| Instance class              | `db.m7g.large` (2 vCPU, 8 GiB)       |
| Deployment                  | Multi-AZ                             |
| Storage type                | `gp3`                                |
| Allocated storage           | 100 GiB                              |
| Provisioned IOPS            | None beyond the 3000 IOPS baseline   |
| Storage throughput          | 125 MiB/s baseline                   |
| Backup retention            | 7 days                               |
| Auto minor version upgrade  | Disabled                             |
| PostgreSQL minor version    | Recorded by the descriptor; see below |

`gp3` rather than `gp2` for a reproducibility reason, not a cost one. `gp2` performance depends
on an accumulated burst-credit balance, so the same benchmark run executed twice can produce two
different storage latencies depending on what the volume did beforehand. A benchmark whose
`workload_digest` and `environment_digest` are identical must not produce materially different
durations because of invisible credit state. `gp3` delivers its baseline continuously and removes
that variable.

At allocations below 400 GiB, RDS `gp3` provides 3000 IOPS and 125 MiB/s and does not admit
provisioning above that baseline; exceeding it requires allocating at least 400 GiB. The workload
does not need it. What PostgreSQL stores is metadata, fact packages, aggregates, telemetry, and
deletion evidence — never dataset content, which lives in S3 under the seven-day expiration rule
— so 100 GiB is generous for the beta and the baseline is not the constraint on the ten-minute
objective. `db.m7g.large` follows: 2 vCPU and 8 GiB is sized for bulk insertion of aggregates and
provenance rather than for high-transaction-rate serving, and Multi-AZ is required by
`KHEPRI-DEC-005` rather than chosen here.

Backup retention of 7 days matches the S3 seven-day expiration rule so that no single retention
horizon is quietly longer than another. `KHEPRI-DEC-005` already states that backups protect
operational state while content-retention and deletion rules continue to apply; this decision
adds no content to a backup and relaxes no deletion rule.

**The minor version is a recorded fact, not a number this decision invents.** Automatic minor
version upgrade is disabled, because an upgrade that changed the engine underneath an approved
`environment_digest` would silently invalidate every prior run's evidence while the digest still
matched. The descriptor records the exact minor version provisioned. A minor upgrade is therefore
a deliberate change that produces a new digest and requires the compatibility and recovery
verification `KHEPRI-DEC-005` already demands.

### The pinned Chromium build — open question 5

Chromium is pinned by being **baked into the OCI image**, and the descriptor records the image
digest. That is the whole mechanism, and it is chosen because it makes the pin transitive: the
`environment_digest` already covers the image digest, the image digest covers the browser bytes,
and no run can silently acquire a different browser.

Concretely: the image build installs the browser at a fixed `PLAYWRIGHT_BROWSERS_PATH`, and both
services run with `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` so that no task ever fetches a browser at
runtime. A task that cannot find the baked browser must fail rather than download one, because a
runtime download is exactly the unrecorded substitution this pin exists to prevent.

The descriptor records the resolved Playwright package version, the Chromium revision that
version installs, and the SHA-256 of the downloaded browser archive. Those three are facts about
the pinned build, produced at image-build time. This decision does not name a revision:
`uv.lock` pins the Playwright package, the package determines the revision, and writing a
revision here that disagreed with the lock file would create a second, competing pin.

### The benchmark environment — open question 6

The benchmark executes in a **separate dedicated benchmark environment**, not in the beta
environment.

`KHEPRI-DEC-006` excludes "any benchmark run in an environment holding customer content", and the
beta environment holds exactly that. Running there would also make every benchmark run depend on
the protected-environment authorization that governs beta deployment, which would either couple
routine measurement to a launch control or erode that control by routine use. A separate stack
also bounds blast radius: the benchmark writes forty synthetic datasets and their bundles, and
nothing it does can touch a client's bucket, key, database, or queue.

Requirements on that environment:

- It is a second instantiation of the same CDK application in the same region, `me-central-1`,
  with an environment identifier as the only naming input. It is not a hand-built environment,
  and it is not a second definition to keep in sync.
- Every sizing value in this decision is **identical** between the two environments — task CPU,
  memory, ephemeral storage, concurrency and queue bounds, instance class, storage type,
  allocation, IOPS, and image digest. This is what preserves inference: a duration measured on
  hardware sized unlike beta would not be evidence about beta, and the ten-minute objective would
  be met somewhere nobody ships. The environments may differ only in name, network isolation,
  service desired count, deletion protection, and the total absence of customer content.
- It holds no customer content and is never a target of any pipeline carrying customer content.
  It does not share the beta environment's KMS customer-managed key, bucket, database instance,
  or queues.
- Provisioning it is authorized by this decision on approval. It is not a beta environment, so
  the `KHEPRI-DEC-005` protected-environment authorization for beta deployment neither covers it
  nor is weakened by it.

### Effect on the environment descriptor

With this decision approved, every field
`governance/benchmarks/KHEPRI-BMK-001-environment.yaml` must carry has a source: the service
selections come from `KHEPRI-DEC-005`, the sizing values from this decision, and the four
recorded facts — OCI image digest, `uv.lock` digest, exact Python patch version, and the SHA-256
of the reviewed synthesized CDK template — from the build and synthesis that produce the
environment, together with the PostgreSQL minor version and the three Chromium facts above.

The descriptor still cannot be written before the CDK definition exists, because four of those
values are outputs of building and synthesizing it. That ordering is a consequence, not an
omission.

## Open questions

Fail-closed under Article V. This decision settles `KHEPRI-DEC-006` open questions 2 through 6
and settles nothing else. These remain open exactly as recorded there, and none of them is
answered by implication here:

1. Whether the approved 50 MB ceiling in `RRA-002` and `KHEPRI-DEC-003` means 50,000,000 or
   52,428,800 bytes. The sizing above is derived from the larger, conservative reading, so
   settling it downward would leave this sizing valid rather than invalidate it.
2. The concurrent arrival pattern representing real beta load, and the beta service desired count
   and autoscaling policy that follow from the client count, all reserved to the
   beta-authorization artifact.
3. Whether a narrative-enabled benchmark and an approved provider latency budget are required
   before beta exit.
4. The cadence of full benchmark execution.

New to this decision, and not settled by it: whether `db.m7g.large`, `gp3` at the stated
baseline, and the two Fargate combinations are available in `me-central-1` for the accounts
involved. `KHEPRI-DEC-005` already requires regional service availability and account
data-location settings to be verified before infrastructure provisioning. If any selection here
is unavailable in that region, the CDK definition must fail rather than substitute a neighbour,
and the substitute requires a superseding decision.

## Exclusions

This decision does not authorize:

- beta deployment, beta launch, client count, or observation period;
- any environment, region, or service `KHEPRI-DEC-005` did not select, or cross-region
  replication or multi-region copy of any kind;
- any customer content in the benchmark environment, or any benchmark input derived from customer
  data;
- load, capacity, soak, concurrency, or multi-tenant performance testing;
- narrative provider use, or any relaxation of the data-processing-agreement and Zero Data
  Retention gates in `KHEPRI-DEC-005`;
- weakening the 95% objective, the 600,000 ms deadline, the 52,428,800-byte ceiling, or any
  privacy, isolation, validation, reconciliation, provenance, language-parity, or deletion
  control in order to reach a sizing that measures faster;
- changing any `KHEPRI-DEC-006` workload parameter, measurement rule, or digest rule;
- treating a synthesized template, a passing CI run, or any automation output as human approval.

## Consequences

- `KHEPRI-DEC-006` open questions 2 through 6 are closed, which unblocks the environment
  descriptor and the AWS CDK v2 definition. Four remain open, and a governed benchmark run still
  requires the descriptors, the harness rework `KHEPRI-DEC-006` records, and this decision's
  approval.
- Every sizing value here is covered by `environment_digest` once the descriptor exists.
  Changing one changes that digest, changes the `BenchmarkIdentity`, and invalidates all prior
  evidence by the identity check in `src/khepri/rra/performance.py`. Resizing a task is therefore
  a governed change and never an operational adjustment.
- The benchmark environment and the beta environment are sized identically by construction, so a
  benchmark result is evidence about the environment beta will run in. Permitting them to drift
  would silently void that, which is why the identity requirement is stated as a requirement and
  not as a preference.
- The follow-on obligations created here are: write the AWS CDK v2 definition of both
  environments in specification-linked slices with the sizing values above as its only sizing
  inputs; verify regional availability of every selection before provisioning; and record the
  build and synthesis outputs in the environment descriptor.
- Nothing here produces or implies performance evidence. No benchmark has been run, no objective
  has been met, and a green CI run remains evidence of consistency only.

This decision is historical. Current state and supersession are recorded in
`governance/registry.yaml`.
