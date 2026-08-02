# KHEPRI-DEC-008: RRA private-beta portable runtime and target selection

## Context

`KHEPRI-DEC-005` selected Amazon Web Services in `me-central-1` as the private-beta runtime, and
`KHEPRI-DEC-007` sized it. Both were reasoned from the workload rather than from habit, and
neither is wrong about the workload. They are unaffordable.

Priced against the published `me-central-1` rates on 2026-08-02, the environment those decisions
define costs approximately 675 USD per month standing: 299 for a Multi-AZ `db.m7g.large`, 221 for
a worker task holding 4 vCPU and 16384 MiB continuously, 55 for the web task, and the remainder in
load balancing, address translation, storage, and keys. Two line items are 77% of it. The owner
cannot fund that through a private beta into a commercial phase, and a decision the owner cannot
execute is not authority; it is an aspiration that blocks every artifact downstream of it.

Cost alone does not settle where the beta runs. A cost-shaped AWS environment was also priced at
roughly 178 USD per month and a DigitalOcean equivalent at 174 to 235, so the provider question is
not decided by the monthly figure. It is decided by the owner's judgment about the commercial
phase, and that judgment is not this decision's to make. What this decision settles is that the
runtime stops being defined in terms of one provider's products.

Three measurements bound the work. The approved specifications name no AWS service: a
case-insensitive search of `governance/specifications/` for `aws`, `amazon`, `sqs`, `s3`,
`fargate`, `cloudwatch`, `kms`, `ecs`, and `rds` returns nothing across `RRA-001` through
`RRA-007`, and `RRA-002` states its storage obligation as a property, "encrypt stored input and
derived content in transit and at rest in isolated object namespaces", rather than as a product.
`boto3` is imported in two modules, `src/khepri/runtime/wiring.py` and
`src/khepri/local/storage.py`, because every consumer already depends on a `Protocol`. And
`src/khepri/infra/` is 1,351 lines with 1,575 lines of tests, against 18,827 lines of source and
20,689 lines of tests overall.

No specification changes. No specification approval is re-issued. The product is untouched by a
change of host.

## Decision

This decision supersedes `KHEPRI-DEC-005` and `KHEPRI-DEC-007` and restates the architecture in
full, with the provider and deployment sections replaced by a target capability contract.

Restatement rather than amendment is deliberate. Amending only the deployment section of
`KHEPRI-DEC-005` would leave an accepted governed document asserting that AWS is the deployment
path. Constitution I gives each governed fact one authoritative representation, and two live
architecture decisions with contradictory deployment sections is the drift it forbids. The
superseded decisions retain their approval evidence unchanged, as Constitution VI requires.

### What this decision carries, and what it does not

It settles the runtime, the application contracts, the controls that replace provider-specific
ones, and the rules that size the target. It authorizes the portability slices listed under
"Follow-on obligations" to be written.

It does not select a provider, a region, or a residency commitment. It does not authorize
provisioning, deployment, or beta launch. It sets no service count, autoscaling policy, or
capacity. It authorizes nothing commercial.

### Application stack

Carried forward from `KHEPRI-DEC-005` unchanged.

Implement RRA as a greenfield Python 3.13 modular monolith. One versioned codebase and container
image expose two independently scaled process roles: a synchronous web/API service, and a bounded
background report worker. The roles share domain contracts and persistence but communicate through
identifiers and durable job state. They are not separate product services.

- FastAPI with Uvicorn provides HTTP and application boundaries.
- Jinja2 renders server-side web reports using bundled CSS and minimal bundled JavaScript.
- CSS logical properties, explicit language direction, Arabic-capable embedded fonts, and
  bilingual snapshot tests govern RTL and language parity.
- SQLAlchemy 2, Psycopg 3, and Alembic provide synchronous PostgreSQL persistence and migrations.
- Polars lazy execution performs CSV/XLSX materialization, profiling, mapping, grouping, and KPI
  preparation. The fastexcel/calamine engine reads XLSX inputs.
- Governed monetary calculations use validated integer minor units or exact decimal values.
  Binary floating-point values are never authoritative financial facts.
- Pydantic models define application-boundary schemas.
- Python dependencies are locked and updated only through reviewed changes.

No separate SPA, Node.js runtime, Redis, data warehouse, notebook runtime, or microservice
boundary is introduced for the private beta.

### Stable application contracts

Carried forward from `KHEPRI-DEC-005` unchanged.

- `FactPackage` is immutable, versioned, content-addressed, and the sole source for narrative,
  charts, web, PDF, and Excel output.
- `NarrativeAdapter` accepts only approved aggregate facts, safe labels, caveats, language
  instructions, and citation identifiers. It returns cited prose or a refusal.
- `ReportBundle` binds Arabic and English web, PDF, and Excel surfaces to one fact-package version
  and provenance record.
- PostgreSQL owns canonical job state, idempotency keys, leases, retries, reconciliation state,
  and deletion evidence.
- Queue messages contain only opaque job identifiers and routing metadata.

### Report generation

Carried forward from `KHEPRI-DEC-005` unchanged.

- Jinja2 supplies the canonical bilingual HTML report template.
- Playwright with pinned Chromium renders both browser-visible HTML and tagged PDF from that
  template using print CSS, embedded fonts, and RTL-aware layouts.
- XlsxWriter produces Excel workbooks directly from the immutable fact package.
- Excel generation writes governed literal values and safe labels only. Formula and automatic URL
  interpretation are disabled for customer-derived strings.
- Charts consume fact-package series and never independently calculate business figures.
- Every surface must reconcile to the same fact and citation identifiers before delivery.

Chromium is launched with `--disable-dev-shm-usage`. `KHEPRI-DEC-007` required this because AWS
Fargate fixes `/dev/shm` at 64 MiB and Chromium's shared-memory use exceeds that while rendering a
paginated document, failing as a renderer crash rather than as a memory limit. Docker's default
`/dev/shm` is also 64 MiB, so the requirement survives the change of host for the same reason and
remains a correctness requirement rather than a tuning flag.

### Target capability contract

This section replaces the "Cloud provider and deployment" section of `KHEPRI-DEC-005`.

The target is defined by what it must provide, not by whose product provides it. Where the honest
answer is a rule rather than a value, this decision states the rule and requires the environment
descriptor to record the value, which is the discipline `KHEPRI-DEC-007` established.

| Capability | Requirement | Recorded by the descriptor |
|---|---|---|
| Container runtime | Runs the pinned OCI image as two distinct process roles, without interactive access | Host product, vCPU, memory, disk |
| Relational store | PostgreSQL 17, TLS required, point-in-time recovery, automatic minor upgrade disabled | Product, exact minor version, sizing, RTO and RPO |
| Object storage | S3-compatible API, private, non-versioned, seven-day expiry, multipart-abort on deletion | Endpoint product, region |
| Secret store | Outside the repository and outside the image | Product |
| TLS ingress | Terminated by a component that is not the application | Product |
| Egress identity | Stable and restricted | Address or range |

Automatic minor upgrade is disabled for the same reason `KHEPRI-DEC-007` disabled it: an upgrade
that changed the engine underneath an approved `environment_digest` would silently invalidate
every prior run's evidence while the digest still matched.

#### The S3-compatible requirement is a portability boundary, not neutrality

Requiring an S3-compatible API is a deliberate, bounded portability decision. It is not a claim
that the object store is interchangeable with any storage technology.

It fixes one wire protocol so that DigitalOcean Spaces, MinIO, Garage, Ceph RGW, and Amazon S3 are
substitutable for each other without a code change, and it excludes everything else: block
storage, POSIX filesystems, and non-S3 object APIs are out of contract. The boundary is chosen
because it is the narrowest interface that keeps the existing `EncryptedObjectStore`,
`DeletionObjectStore`, and `ProfileObjectReader` ports intact while admitting inexpensive hosts.

The cost of the boundary is stated rather than hidden. An S3-compatible implementation is only as
good as its consistency, durability, and expiry semantics, and those differ between
implementations. The target-selection artifact must record which implementation was chosen and
confirm that its expiry rule, deletion semantics, and multipart-abort behaviour satisfy `RRA-002`.
Substitutability at the API is not equivalence in behaviour.

#### Object storage control: application-side envelope encryption

`S3EncryptedObjectStore` currently trusts nothing and verifies that the `PutObject` response
*proves* the storage policy: matching checksum, `aws:kms` encryption, the exact configured customer
managed key ARN, `BucketKeyEnabled`, and the absence of a `VersionId`. No S3-compatible store
outside AWS can satisfy those five proofs. DigitalOcean Spaces has no customer managed key and
never returns `BucketKeyEnabled`. MinIO rewrites the key identifier to `arn:aws:kms:<keyname>`,
which carries neither region nor account.

Stored objects are therefore encrypted by the application: a per-object AES-256-GCM data key,
wrapped by a master key drawn from the secret store, with the ciphertext digest verified on
read-back.

This changes the character of the proof and improves it. Today the application asks the provider
to attest that it encrypted the bytes and validates the attestation. Under envelope encryption the
application knows the bytes are encrypted because it encrypted them, and the remaining proof
obligation is that the exact ciphertext written is the ciphertext read, which a digest settles
without trusting any provider header.

One property is lost and is recorded as accepted rather than argued away. A KMS customer managed
key keeps key custody outside the application's blast radius; a master key drawn into the
application process does not. The compensating controls are the absence of interactive host access
below, the transient presence of customer content on the host, and the seven-day expiry.

Provider-side encryption at rest, where the target offers it, remains required and is additional
to this control, never a substitute for it.

#### Job delivery: PostgreSQL claim and redrive

`KHEPRI-DEC-005` rejected PostgreSQL-only queueing because it "would require custom visibility,
redrive, and dead-letter behavior". That premise has been overtaken by what `RRA-007` built.
`job_persistence` already owns leases, `max_attempts`, retries, and the distinct dead-letter
reasons `DEAD_LETTER_RETRIES_EXHAUSTED` and `DEAD_LETTER_CONTENT_DELETED`, and a recovery and
expiry pass already exists. The custom behaviour the rejection warned about is largely written and
tested. This decision reverses the rejection on that ground, not on cost.

Job delivery uses PostgreSQL with `SELECT ... FOR UPDATE SKIP LOCKED`. What is added is a claim
query and a redrive sweep. Amazon SQS, its adapter, and its one-message driver are removed.

Two hazards collapse rather than move. `KHEPRI-DEC-007` had to force the SQS visibility timeout and
the PostgreSQL lease to the same 300 seconds, because different values produce a window in which
one mechanism believes a job is owned and the other does not. It also had to force
`maxReceiveCount` and `max_attempts` to the same 3, because if SQS exhausted first a message would
reach the dead-letter queue while PostgreSQL still considered attempts available, and the governed
dead-letter reason would be absent or wrong. With one mechanism, both properties hold by
construction rather than by matched configuration, and two ways to misconfigure the system stop
existing.

Messages remain opaque job identifiers. At-least-once delivery, bounded retries, and dead-lettering
remain required; only their mechanism changes.

#### Infrastructure access

A host the operator can log into introduces a risk a managed task runtime did not have: a human
can reach the process that is handling customer content, with the envelope master key in its
memory. Replacing an infrastructure audit trail is not the requirement — infrastructure defined as
code in a reviewed repository already produces a change trail. The requirement is runtime access to
the host.

Deployment happens only through continuous integration. Interactive host access is disabled by
default, and is re-enabled only as a logged, time-boxed break-glass action recorded as an
operational event under the content-free telemetry rules below. This preserves a property the
managed runtime supplied without being asked. Its cost is stated: diagnosis by logging into the
host is not available, and diagnostic needs must be met by telemetry.

#### Secrets, ingress, and image distribution

Runtime secrets come from a secret store that is neither the repository nor the image, and supply
the envelope master key. TLS is terminated by a component that is not the application. The pinned
OCI image is published to a registry recorded by the descriptor; continuous integration validates,
builds, scans, and publishes it, and publishing an image is not deploying one.

### Narrative provider

Carried forward from `KHEPRI-DEC-005` unchanged.

The initial optional narrative adapter targets the OpenAI Responses API, subject to all of the
following gates: an executed data-processing agreement; explicit organization and project approval
for Zero Data Retention; technical verification of the approved Zero Data Retention configuration;
`store=false` on every request; synchronous requests only; no background mode, conversations,
assistants, threads, files, vector stores, hosted tools, extended prompt caching, or provider-side
state; no raw rows, source column values, owner/session identifiers, storage locations, secrets, or
unapproved personal data; a governed model allowlist and pinned adapter/request-schema version; and
response validation rejecting unsupported numbers, citations, claims, or unsafe labels.

Training opt-out without verified Zero Data Retention is insufficient. If any gate is absent,
revoked, or unverifiable, the OpenAI adapter remains disabled and RRA delivers the deterministic
cited facts-only report authorized by `RRA-005` and `RRA-006`.

The exact model snapshot is an operational configuration selected through bilingual grounding,
latency, refusal, and privacy-gate evidence. Changing providers or materially changing provider
data handling requires a new or superseding architecture decision.

### Observability and recovery

Carried forward from `KHEPRI-DEC-005`, with the provider-specific destinations replaced.

- OpenTelemetry emits stable traces and metrics to an OTLP endpoint recorded by the descriptor.
- Python structured logs are content-free and are shipped off-host to a destination recorded by
  the descriptor.
- Telemetry records opaque correlation IDs, stage names, state transitions, durations, queue time,
  retries, provider latency, dataset-size bands, and output sizes.
- Telemetry excludes filenames, labels, source values, narrative, facts, invitations, tokens, and
  object locations.
- Worker concurrency and queue consumption are bounded by configured CPU, memory, database,
  provider, and latency budgets.
- Every stage is independently timed and retry-safe.
- Database backups and restore exercises protect operational state while content-retention and
  deletion rules continue to apply. A restore exercise against the target is required before beta
  authorization.
- Content-free deletion evidence retains identifiers, timestamps, digests, attempted locations,
  outcomes, and retry history only.

### Sizing

`KHEPRI-DEC-007`'s values are derived from valid Fargate CPU and memory combinations, Fargate
ephemeral-storage bands, RDS instance classes, and gp3 burst-credit behaviour. None of those
constrain the new target, so the values do not carry forward. Its reasoning largely does, and is
restated here as rules in provider-neutral units.

- One report job per worker process. The sizing below is the sizing of exactly one pipeline. A
  second concurrent job in the same process would contend for the same cores during rendering and
  could exhaust memory whenever two large-band datasets met, which makes duration a function of
  what else happened to be running. Throughput is bought by process count, never by in-process
  concurrency.
- Worker memory holds a pinned Chromium rendering six surfaces, including a tagged paginated PDF,
  together with a Polars frame derived from an input bounded at 52,428,800 bytes whose in-memory
  width exceeds its stored width, plus that frame's aggregation intermediates. Chromium is the
  largest single consumer and does not shrink with dataset size.
- Worker cores are sized so that the completion objective is decided by the pipeline rather than by
  core count; Polars parallelizes grouping and aggregation, and the `RRA-006` surfaces derive from
  one fact package so per-surface work can overlap.
- Worker disk holds the baked browser, the downloaded input, six rendered surfaces, the workbook
  and PDF temporaries, and the shared-memory allocations `--disable-dev-shm-usage` redirects.
- The web role renders templates, streams uploads, and enqueues jobs. It performs no rendering and
  holds no fact package. Its memory is sized so that several concurrent uploads bounded at
  52,428,800 bytes each are a slow event rather than an out-of-memory event.
- Lease duration is 300 seconds, extended by a heartbeat every 60 seconds. Retry delay is 60
  seconds. Attempts before dead-lettering are 3. Both bounds are shorter than the completion
  deadline because heartbeats extend them, and a lease longer than the deadline would delay
  recovery of a process that died.
- Storage delivers its baseline performance continuously rather than through an accumulated credit
  balance, so that two runs with identical digests cannot differ because of invisible state.
- Backup retention matches the seven-day object expiry so that no retention horizon is quietly
  longer than another.

`governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` is re-issued against the selected target. The
keys `visibility_timeout_seconds`, `message_retention_seconds`, `receive_wait_seconds`, and
`max_receive_count` describe a message broker this decision removes and leave the file.
`KHEPRI-DEC-006`'s workload — 40 synthetic datasets, the integer-exact 95% threshold, and the
ten-minute objective — is provider-neutral and is unaffected.

### Target selection is a separate, pre-deployment artifact

The concrete provider, region, and residency commitment are not settled here, and are not delegated
to beta authorization. Delegating them there would be circular: the deployment definition needs a
provider and region; the environment descriptor and sizing depend on the deployment target; the
governed benchmark must run on the final target environment; and beta authorization should follow
that evidence rather than produce it.

A separate target-selection artifact carrying infrastructure authority resolves them, and must be
approved before any deployment definition is written. Its required content is fixed here:

- the provider and region;
- the residency justification, and whether any client commitment constrains it;
- the concrete product satisfying each capability above, with exact versions;
- confirmation that the chosen object store's expiry, deletion, and multipart-abort semantics
  satisfy `RRA-002`;
- the recorded RTO and RPO; and
- the sizing values the rules above require.

Leaving residency open is not an evasion of Constitution VII. It is a refusal to record a
commitment no approved artifact supports, and the fail-closed consequence is explicit: absent that
artifact, no deployment definition exists, so no environment exists, so no benchmark evidence
exists, so beta cannot be authorized.

### Delivery controls

Carried forward from `KHEPRI-DEC-005` unchanged.

Implementation is authorized only in specification-linked, independently verifiable slices. Before
beta launch, the implementation must demonstrate cross-session isolation and consent enforcement;
deterministic reconciliation and reruns; raw-row exclusion from narrative requests; Arabic/English
fact and caveat parity; accessible RTL web and PDF output; safe Excel output; immediate deletion
and seven-day expiry; restart, retry, dead-letter, and orphan recovery; content-free telemetry; and
at least 95% complete report bundles within ten minutes for the approved benchmark workload.

The later beta-authorization artifact must still define the client count and observation period.
This decision does not authorize public signup, production launch, commercial authentication,
persistent workspaces, organizations, billing, scheduling, agency features, forecasting, or
customer-defined formulas.

## Alternatives not selected

- Amending only the deployment section of `KHEPRI-DEC-005` was not selected because it would leave
  an accepted governed document asserting a deployment path that is no longer authorized.
- Naming DigitalOcean concretely was not selected because residency is unresolved, and naming a
  provider would settle residency by implication rather than by decision.
- A single self-hosted host running the database and object store alongside the application was not
  selected because the durability, backup, and recovery evidence `RRA-007` requires would become
  entirely self-produced for a beta that does not need that trade.
- Provider server-side encryption with checksum verification alone was not selected because it
  degrades a governed control from proven to assumed.
- A self-operated key service was not selected because it restores custody separation at the cost
  of an operated, backed-up, highly available component the private beta does not otherwise need.
- A self-hosted or managed third-party message broker was not selected because PostgreSQL already
  owns the canonical state, and a broker would reintroduce the two-clock hazards described above.
- Retaining interactive host access with session auditing was not selected because the audit would
  be only as trustworthy as a further component to operate, where prohibiting the access removes
  the risk instead of recording it.
- Assigning target selection to the beta-authorization artifact was not selected because it is
  circular, as set out above.

## Consequences

- The runtime is defined by capabilities, so a change of host is a descriptor change and a
  deployment-definition change rather than an architecture decision.
- `src/khepri/infra/` becomes frozen reference. It is kept green by continuous integration, is not
  the deployment path, and is closed to new slices. It is not deleted: it passes its tests and is
  the only worked example of the sizing reasoning the new target must reproduce.
- Key custody is weaker than a customer managed key provides, mitigated as described and recorded
  as accepted.
- Diagnosis by interactive host access is unavailable by design, which raises the cost of a
  telemetry gap.
- No environment exists until the target-selection artifact is approved, and therefore no benchmark
  evidence and no beta authorization exist until then.
- `KHEPRI-DEC-005` and `KHEPRI-DEC-007` move to `superseded` when this decision is approved,
  retaining their approval evidence unchanged.

### Follow-on obligations

- Write the target-selection artifact before any deployment definition.
- Replace the Amazon SQS adapter and driver with the PostgreSQL claim-and-redrive implementation.
- Replace the five provider-header proofs with envelope encryption and read-back digest
  verification.
- Unlock `src/khepri/runtime/config.py` from `me-central-1`, the twelve-digit account identifier,
  and the KMS key ARN.
- Re-issue `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` against the selected target.
- Add a `superseded_by` field to the decisions registry and validator support for supersession
  linkage. The schema records no such field today, so this decision's supersession relationship is
  stated in prose only. That gap is recorded here so it is not mistaken for an oversight, and is
  outside this decision's slice.

This decision remains proposed until its registry entry contains explicit approval evidence.
