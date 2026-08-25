# DRAFT — KHEPRI-DEC-NNN: RRA private-beta runtime target and DigitalOcean FRA1 environment descriptor

**Status: planning-only draft. Not a governed artifact — including after this commit is merged.**

Merging this commit does **not** make this document governing. `governance/registry.yaml` is
unchanged by it, contains no `KHEPRI-DEC-NNN`, and is authoritative for artifact identity, state,
and document under Constitution III; the validator therefore ignores this file, which lives under
`docs/platform/proposed-governance/`. This file remains planning-only until it is finalized under an
owner-allocated identifier, moved into `governance/decisions/`, and added through the atomic
registry transition described below.

`NNN` is a placeholder; only the owner allocates the identifier. Nothing here authorizes
provisioning, deployment, spend, or external traffic, and merging this commit closes no `OPS1` gate
and resolves no `KHEPRI-DEC-027` stop-gate.

> Proposed to supersede `KHEPRI-DEC-008`, which superseded `KHEPRI-DEC-005` and `KHEPRI-DEC-007`.
> Restates `KHEPRI-DEC-008` in full, revising one capability row and supplying the target-selection
> content it deferred.

## Context

`KHEPRI-DEC-008` (`active`) defines the private-beta runtime as a provider-neutral capability
contract and requires a separate target-selection artifact before any deployment definition.
`KHEPRI-DEC-027` (`active`) selected DigitalOcean / FRA1 as the direction and reserved seven
stop-gates. This decision resolves those stop-gates and supplies the descriptor content
`KHEPRI-DEC-008` requires.

Its predecessor's context is unchanged and is not re-argued: the AWS `me-central-1` environment
`KHEPRI-DEC-005` and `KHEPRI-DEC-007` defined was sound about the workload and unaffordable, and the
runtime was therefore redefined in terms of capabilities rather than one provider's products.

### Why supersession rather than an amendment

`governance/registry.yaml` admits two states only — `active` and `retired`
(`src/khepri_gov/validator.py`, `ARTIFACT_STATES`). There is no amendment state, and Constitution I
gives each governed fact one authoritative representation. Revising one row of `KHEPRI-DEC-008`'s
capability table while leaving the original active would put two contradictory statements of the
same fact on `main`. `KHEPRI-DEC-008` chose restatement over amendment for this reason, and this
decision follows it.

### The conflict this decision resolves

`KHEPRI-DEC-008` requires the relational store to have "automatic minor upgrade disabled."
DigitalOcean Managed PostgreSQL cannot satisfy this. Its documentation states: "Updates are
necessary for security and stability, so you can't disable them, but you can customize the
maintenance window or manually initiate an available update."

`KHEPRI-DEC-027` §3 reserved "acceptance and mitigation of provider-managed PostgreSQL minor
upgrades" as an unresolved stop-gate rather than settling it.

The requirement's stated purpose is narrower than its wording. `KHEPRI-DEC-008` disabled automatic
minor upgrades because "an upgrade that changed the engine underneath an approved
`environment_digest` would silently invalidate every prior run's evidence while the digest still
matched." The protected property is **digest-bound evidence integrity**, not the absence of
upgrades. That property is preserved by recording the exact minor version and treating a change to
it as an event that re-issues the digest and re-evidences affected runs.

**The constraint is DigitalOcean's, not managed PostgreSQL's in general.** Some managed products do
expose the control: this repository's own frozen AWS reference sets
`auto_minor_version_upgrade=False` on the RDS instance (`src/khepri/infra/database.py:114`). The
original wording is therefore satisfiable — but only by a provider `KHEPRI-DEC-027` has already
demoted to a fallback candidate, or by self-hosting. Keeping the wording unchanged would not force
self-hosting outright; it would reopen the provider selection `KHEPRI-DEC-027` settled, which is a
larger change than this decision proposes and is not this decision's to make.

Self-hosting PostgreSQL on a Droplet would also satisfy the original wording literally, but
`KHEPRI-DEC-008` already rejected an equivalent trade in "Alternatives not selected": a self-hosted
store was declined because "the durability, backup, and recovery evidence `RRA-007` requires would
become entirely self-produced for a beta that does not need that trade." No backup, restore, or PITR
capability exists in the repository today, which makes that objection stronger now, not weaker.

## Decision

This decision supersedes `KHEPRI-DEC-008` and restates it in full. Every section is carried forward
unchanged except the relational-store row of the target capability contract, revised below, and the
target-selection content, supplied below rather than deferred.

### What this decision carries, and what it does not

It settles the runtime, the application contracts, the controls that replace provider-specific ones,
the rules that size the target, and — new to this decision — the concrete target.

It does not authorize provisioning, deployment, spend, or beta launch. It sets no service count or
autoscaling policy. It authorizes nothing commercial.

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

The target is defined by what it must provide, not by whose product provides it. Where the honest
answer is a rule rather than a value, this decision states the rule and requires the environment
descriptor to record the value, which is the discipline `KHEPRI-DEC-007` established.

| Capability | Requirement | Recorded by the descriptor |
|---|---|---|
| Container runtime | Runs the pinned OCI image as two distinct process roles, without interactive access | Host product, vCPU, memory, disk |
| Relational store | PostgreSQL 17, TLS required, point-in-time recovery, exact minor version recorded; a minor-version change is an `environment_digest`-affecting event requiring digest re-issuance and re-evidencing of affected runs; maintenance window pinned to a recorded low-traffic slot | Product, exact minor version, maintenance window, sizing, RTO and RPO |
| Object storage | S3-compatible API, private, non-versioned, seven-day expiry, multipart-abort on deletion | Endpoint product, region |
| Secret store | Outside the repository and outside the image | Product |
| TLS ingress | Terminated by a component that is not the application | Product |
| Egress identity | Stable and restricted | Address or range |

**The relational-store row is the one substantive change from `KHEPRI-DEC-008`.** Its predecessor
required "automatic minor upgrade disabled" to protect a specific property: an upgrade that changed
the engine underneath an approved `environment_digest` "would silently invalidate every prior run's
evidence while the digest still matched." The selected provider does not permit disabling updates,
so the control is restated as the property it protects. The minor version is recorded; a change to
it invalidates the digest explicitly and visibly, rather than silently.

**A declaration alone does not achieve this, and this decision does not pretend otherwise.**
`resolve_approved_benchmark` reads `KHEPRI_BENCHMARK_ENVIRONMENT_DIGEST` as a static value
(`src/khepri/rra/benchmark_authorization.py`), and nothing in the runtime queries the live
PostgreSQL minor version before accepting it. Without an automated check, a run would continue
against a new engine while the old digest still matched — the exact silent invalidation this row
exists to prevent, merely relocated from the upgrade to the digest.

The revised row is therefore satisfied only in combination with a **runtime minor-version check**,
listed as an implementation prerequisite below: the benchmark gate reads the live server version,
compares it against the minor version the descriptor records, and **refuses to certify a run** when
they differ, until the descriptor and digest are reissued. Until that check exists, no benchmark run
against this target may be treated as governed evidence.

The cost is stated rather than hidden. Under `KHEPRI-DEC-008` a minor-version change could not
occur; under this decision it can, and each occurrence obliges digest re-issuance and re-evidencing
of affected runs. That is operational work this decision creates. It is accepted because the
alternative — self-producing all durability, backup, and recovery evidence — was already rejected
on stronger grounds, and because a maintenance window pinned to a recorded slot makes the event
predictable rather than arbitrary.

The remaining rows are unchanged from `KHEPRI-DEC-008`.
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

### Target selection

`KHEPRI-DEC-008` required this content in a separate artifact and deliberately did not invent it.
This decision supplies it, which is why it supersedes rather than accompanies its predecessor.

**Provider and region.** DigitalOcean, FRA1 (Frankfurt), per `KHEPRI-DEC-027`.

**Residency justification.** Per `KHEPRI-DEC-027` §2, the current non-paying private-beta stage has
no Middle East data-residency requirement and no client commitment overriding FRA1. Every
service-level storage location recorded below is FRA1. A future contract, legal determination, or
product commitment requiring another jurisdiction is a trigger to revisit this before serving that
customer.

**Concrete products satisfying each capability.**

| Capability | Product | Version / size | Region |
|---|---|---|---|
| Container runtime — web | DigitalOcean Droplet, Basic | `s-1vcpu-2gb` (provisional) | FRA1 |
| Container runtime — worker | DigitalOcean Droplet, Basic | `s-4vcpu-8gb` (provisional) | FRA1 |
| Migration execution | one-shot container from the same image | gated pre-start | FRA1 |
| Relational store | DigitalOcean Managed PostgreSQL | 17, exact minor recorded at provisioning | FRA1 |
| Object storage | DigitalOcean Spaces | S3-compatible, versioning never enabled | FRA1 |
| Secret store | GitHub Actions Environment Secrets, delivered by CI to a root-owned mode-0600 systemd `EnvironmentFile` | — | — |
| TLS ingress | DigitalOcean Regional HTTP Load Balancer | 1 node | FRA1 |
| Egress identity | Two Reserved IPs (web, worker), recorded at provisioning | — | FRA1 |
| Image registry | DigitalOcean Container Registry, Basic | 5 GiB | — |
| Telemetry destination | Grafana Cloud, EU region, OTLP | free tier | EU |

**Why not App Platform.** The capability contract requires both private object-storage and database
reachability and a "stable and restricted" egress identity. DigitalOcean documents that dedicated
egress IPs are "only supported for apps not connected to a VPC," because "Apps connected to a VPC
route outbound traffic through the private network, so App Platform can't assign a fixed, public
egress IP." The two required capabilities are mutually exclusive on App Platform. Droplets in a VPC
satisfy both. This is a capability constraint, not a preference, and it is why the compute roles are
Droplets despite App Platform's lower operational burden.

**Why the image forces `linux/amd64`.** The deployable image is built `FROM
mcr.microsoft.com/playwright/python:v1.61.0-noble` with Chromium baked in, so ARM Droplet variants
are not candidates and the registry tier must hold a multi-gigabyte image.

**Object-store semantics confirmation (`RRA-002`).** `KHEPRI-DEC-008` requires written confirmation
that the chosen store's expiry, deletion, and multipart-abort semantics satisfy `RRA-002`.

Confirmed against DigitalOcean documentation: S3-compatible API; private access; time-based
lifecycle expiration; immediate deletion; and object versioning disabled by default, which the
non-versioned contract requires and which `src/khepri/rra/storage.py` independently enforces by
rejecting any response carrying a `VersionId` or `DeleteMarker`. **Versioning must never be enabled
on the selected bucket**, and that is a provisioning constraint, not a default to rely on.

**Multipart-abort listing is recorded as UNVERIFIED.** The Spaces API reference documents
`ListMultipartUploads`, while a DigitalOcean community report dated 2024-07-31 records
`501 NotImplemented` for that operation against SFO2. The two sources conflict and the question
cannot be settled from documentation. It is load-bearing: `src/khepri/rra/storage.py`
`abort_multipart_uploads` calls `list_multipart_uploads` with a `Prefix`, paginates on
`KeyMarker`/`UploadIdMarker`, and then makes a second confirmation call that raises
`StoragePolicyViolation` if uploads remain — so an unsupported operation surfaces as a policy
violation inside the deletion path `RRA-002` mandates rather than as a degraded capability. Spaces
auto-deletes incomplete multipart uploads after 30 days, which exceeds the governed seven-day
horizon and therefore does not satisfy the requirement on its own.

This decision records no confirmation it does not have. Because `KHEPRI-DEC-008` makes that
confirmation a **precondition of selecting the store** rather than a follow-up, the gap is not
merely deferred work: it leaves this decision's own prerequisite unsatisfied, and it is circular
under `KHEPRI-DEC-027`. Both are recorded under "Unresolved" below, with the two orderings the owner
may choose between. If the check fails, the remedies are a bounded `storage.py` change treating
`NotImplemented` as a distinct provider-capability error together with a lifecycle abort rule of
seven days or fewer, or a different S3-compatible store; either is a governed change, not a silent
workaround.

**Recorded RTO and RPO.** RPO 15 minutes; RTO 4 hours. DigitalOcean documents daily backups with
write-ahead logs backed up every five minutes and point-in-time recovery limited to the last seven
days, so five minutes is the provider floor and fifteen minutes is the approved target with
headroom. Four hours accommodates restore-to-new-cluster followed by redeployment without a paid
standby node. Both are targets to be proven by the `OPS1-04` recovery exercise; this decision does
not assert they have been demonstrated.

**Backup retention.** DigitalOcean Managed PostgreSQL retains backups and supports point-in-time
recovery for exactly seven days, fixed and not configurable. This matches the horizon
`KHEPRI-DEC-008` fixed — "Backup retention matches the seven-day object expiry so that no retention
horizon is quietly longer than another" — and cannot be widened, satisfying the rule by
construction.

**Telemetry retention is not a content-retention horizon.** Grafana Cloud's free tier retains
ingested telemetry for 14 days. Telemetry is content-free by the rules carried forward above —
opaque correlation IDs, stage names, state transitions, durations, and outcomes, never customer
content — so its retention is not a content horizon and does not widen `RRA-002`'s seven days.

**Sizing.** The Droplet and database sizes above are **provisional starting values, not benchmark
evidence.** They are chosen so the governed benchmark can execute and be measured down: the worker
is memory-led because Chromium renders six surfaces and does not shrink with dataset size, and an
under-provisioned worker yields a failed run rather than a measurement. `OPS1-09` reissues
`governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` against this target and may change any size,
including moving between tiers of a selected product. It may not substitute a different product or
provider; that requires a superseding decision.

### Registry transition

Adopting this decision is four registry edits in one commit, not one.
`src/khepri_gov/validator.py` requires a `superseded_by` target to be `active` and does not walk
supersession chains, so retiring `KHEPRI-DEC-008` while `KHEPRI-DEC-005` and `KHEPRI-DEC-007` still
name it produces two validation errors. Verified by simulation against the validator:

```
registry: KHEPRI-DEC-005: successor 'KHEPRI-DEC-008' must be active
registry: KHEPRI-DEC-007: successor 'KHEPRI-DEC-008' must be active
```

Re-pointing both at this decision in the same commit clears them.

1. add `KHEPRI-DEC-NNN`, `state: active`;
2. `KHEPRI-DEC-008` → `state: retired`, `superseded_by: KHEPRI-DEC-NNN`;
3. `KHEPRI-DEC-005` → `superseded_by: KHEPRI-DEC-NNN`;
4. `KHEPRI-DEC-007` → `superseded_by: KHEPRI-DEC-NNN`.

Constitution V fails closed, so splitting these across commits leaves `main` failing its own
validator.

### Unresolved: `KHEPRI-DEC-006` pins the benchmark environment to AWS

`KHEPRI-DEC-008` recorded that `KHEPRI-DEC-006`'s workload — 40 synthetic datasets, the
integer-exact 95% threshold, and the ten-minute objective — "is provider-neutral and is unaffected"
by the change of host. That is true of the **workload**. It is not true of the **environment**.

`KHEPRI-DEC-006` (`active`) additionally fixes the environment the run must use, under a heading
that reads "Environment: pinned by `KHEPRI-DEC-005`": AWS `me-central-1`; ECS on Fargate from an
image in ECR behind an Application Load Balancer; RDS for PostgreSQL 17, Multi-AZ; SQS Standard with
a dead-letter queue; Secrets Manager, CloudTrail, and KMS; and infrastructure defined by AWS CDK v2,
with `environment_digest` covering "the SHA-256 digest of the reviewed synthesized CDK template."

Two consequences follow, and neither is cosmetic:

1. A DigitalOcean/FRA1 benchmark run cannot satisfy `KHEPRI-DEC-006` as written, so `OPS1-09` and
   `OPS1-05` would produce evidence that fails an active decision. `environment_digest` cannot even
   be computed as specified, because no CDK template exists for this target and SQS is removed.
2. `KHEPRI-DEC-006`'s environment clause derives its authority from `KHEPRI-DEC-005`, which is
   `retired` and superseded by `KHEPRI-DEC-008`. An active decision is therefore pinned to a
   retired one in prose. `governance/registry.yaml` records `KHEPRI-DEC-006` with
   `depends_on: []`, so the validator's active-depends-on-retired rule never fires and the
   staleness is invisible to automation.

**This decision does not resolve it, and must not.** Restating the benchmark environment here would
widen this decision from a runtime-target selection into a rewrite of the benchmark contract, and
`KHEPRI-DEC-006` governs the evidence rule — the integer-exact threshold, the digest definitions,
and the approval identity — not merely a list of products. That is a separate artifact with its own
reasoning.

The owner therefore has a sequencing choice, and this decision records it rather than pre-empting
it: `KHEPRI-DEC-006` must be superseded or restated against the selected target **before** any
benchmark run is treated as governed evidence. Until then `OPS1-09` may reissue sizing values, but
no run against this target satisfies `KHEPRI-DEC-006`.

### Unresolved: the object-store confirmation is circular under `KHEPRI-DEC-027`

`KHEPRI-DEC-008` requires the target-selection artifact to confirm the object store's
multipart-abort semantics; this decision records that confirmation as UNVERIFIED. That is honest,
but it leaves this decision's own selection prerequisite unsatisfied, and the deferral is circular:
`KHEPRI-DEC-027` §4 blocks provisioning until the complete artifact is approved, while the
verification requires an FRA1 Space that provisioning would create.

The circularity is breakable, and the break is narrow: a single throwaway bucket used only to
observe `ListMultipartUploads` behaviour is not the non-production environment `OPS1-02` provisions,
carries no customer content, and costs cents. But it is still spend and still creation of a provider
resource, so it requires the owner's separate authorization rather than this decision's.

Two orderings are available, and the owner chooses:

- **Verify first.** Separately authorize the bounded check, record the result here, and finalize
  this decision with a confirmation rather than a gap. Preferred: it satisfies
  `KHEPRI-DEC-008`'s precondition literally.
- **Finalize with Spaces unselected.** Keep the object-storage stop-gate open, select every other
  product, and close storage in a follow-on once evidence exists.

Finalizing this decision with Spaces *selected* and the confirmation absent is not offered as an
option, because it would record a selection its own governing artifact forbids making without
evidence.

## Alternatives not selected

`KHEPRI-DEC-008`'s alternatives are carried forward unchanged. Added here:

- **Self-hosted PostgreSQL 17 on a Droplet** was not selected. It satisfies the original
  "automatic minor upgrade disabled" wording literally, but relocates durability, backup, PITR, and
  restore-verification evidence onto Khepri — the trade `KHEPRI-DEC-008` already rejected — and no
  such capability exists in the repository today.
- **DigitalOcean App Platform** was not selected because dedicated egress IPs and VPC connectivity
  are mutually exclusive on it, and the capability contract requires both.
- **Retaining "automatic minor upgrade disabled" and choosing a provider that permits it** was not
  selected because no managed PostgreSQL product permits disabling updates, so the requirement would
  force self-hosting by implication rather than by decision.
- **Recording the object-store multipart confirmation as satisfied** was not selected because the
  available sources conflict, and `KHEPRI-DEC-008` requires a confirmation rather than an
  assumption.

## Consequences

- `KHEPRI-DEC-008` moves to `retired`, retaining its approval evidence unchanged.
- `KHEPRI-DEC-005` and `KHEPRI-DEC-007` remain `retired` and now name this decision as successor.
- `KHEPRI-DEC-027`, `KHEPRI-DEC-025`, and `RRA-002` remain `active` and unchanged.
- **`KHEPRI-DEC-006` cannot remain unchanged, and this decision does not resolve it.** See the
  unresolved conflict recorded below.
- The stop-gates `KHEPRI-DEC-027` §3 reserved are resolved, except the object-store multipart-abort
  confirmation recorded as UNVERIFIED above.
- A managed minor-version change becomes a governed, visible event rather than a prohibited one,
  obliging digest re-issuance and re-evidencing of affected runs.
- Key custody remains as `KHEPRI-DEC-008` recorded it, mitigated and accepted.
- `OPS1-02` remains blocked until this decision and `OPS1-09` are both complete.
- No environment exists until this decision is merged, and therefore no benchmark evidence and no
  beta authorization exist until then.

### Implementation prerequisites — not authorized by this decision

- **runtime PostgreSQL minor-version check**, without which the revised relational-store row is a
  declaration only: the benchmark gate must read the live server version, compare it against the
  minor version the descriptor records, and refuse to certify a run when they differ. Until it
  exists, no run against this target is governed evidence;
- application readiness/health endpoint; none exists today, and a load balancer health gate,
  rolling deploy, and post-deploy verification all depend on it;
- OpenTelemetry OTLP emission and content-free structured logging; both are governed requirements
  with no implementation;
- DOCR publish path in continuous integration, replacing the ECR-shaped publish job;
- pull-based deploy unit on each Droplet, because the database is VPC-private and unreachable from
  continuous integration, so migrations run inside the VPC without inbound access;
- Reserved-IP outbound gateway configuration on each Droplet;
- empirical Spaces multipart-abort verification against FRA1.

Identity, lifecycle state, dependencies, and supersession are authoritative in
`governance/registry.yaml`. Git history retains the transition evidence.
