# KHEPRI-DEC-028: RRA private-beta portable runtime and DigitalOcean FRA1 target

> Active when merged to `main`. Supersedes `KHEPRI-DEC-008`.

## Context

`KHEPRI-DEC-008` defined the private-beta runtime as a capability contract rather than a product
list, and deliberately deferred provider, region, residency, and sizing to a separate
target-selection artifact. `KHEPRI-DEC-027` then selected DigitalOcean and FRA1 as the direction
but was explicitly narrower than that artifact, so it authorized no provisioning.

The owner rulings merged in `#289` and refined in `#296` settle the remaining environment
questions for the initial private beta. Two of those rulings contradict rows in active
`KHEPRI-DEC-008` and are recorded there as governance-impacting for exactly that reason: the
managed PostgreSQL minor-upgrade row, and the unconditional stable-egress row. Neither can be
implemented while the predecessor's text stands, and `AGENTS.md` fails closed on a prose ruling
that contradicts an active governed artifact.

This decision restates `KHEPRI-DEC-008` in full with those two rows replaced, and supplies the
target-selection content its predecessor required of a separate artifact.

### Why supersession rather than an amendment

Amending only the two rows would leave an accepted governed document asserting a
minor-upgrade control the selected provider does not offer and an egress requirement the
selected architecture does not meet. Constitution I gives each governed fact one authoritative
representation. Two live decisions with contradictory capability tables is the drift it forbids.
`KHEPRI-DEC-008` retains its evidence unchanged as a retired artifact.

### What this decision does not reopen

The architecture settled in `#289` and `#296` is carried forward, not re-litigated: DigitalOcean,
FRA1, App Platform web and worker, App Platform pre-deploy jobs, Managed PostgreSQL 17, VPC with
private database connectivity, DigitalOcean Container Registry, App Platform runtime secrets,
GitHub Actions as deployment execution rather than approval authority, Terraform plus an App
Platform specification, the DigitalOcean-native plus Better Stack observability direction, RTO of
two hours and RPO of fifteen minutes as objectives to prove, no initial Droplets, no Kubernetes,
Kafka, Redis, or RabbitMQ tier, and expand → deploy → contract migrations.

The `#286` selected-target table, which chose Droplets and a different telemetry vendor, is
superseded by those rulings and is not carried forward. Its Droplet selection followed from the
unconditional egress row this decision replaces; with that row relaxed, the constraint that
excluded App Platform no longer applies.

## Decision

This decision supersedes `KHEPRI-DEC-008` and restates it in full. Every section below that is
not marked as changed is carried forward from that decision unchanged.

### What this decision carries, and what it does not

It settles the runtime, the application contracts, the controls that replace provider-specific
ones, the rules that size the target, and — new to this decision — the concrete provider, region,
residency, and products.

It does **not** authorize provisioning, deployment, spend, or beta launch. The authority to
bootstrap a provisional non-production environment is `KHEPRI-DEC-030`'s, and beta authorization
remains a separate later artifact. It sets no final capacity.

### Application stack

Carried forward unchanged.

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

Carried forward unchanged.

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

Carried forward unchanged.

- Jinja2 supplies the canonical bilingual HTML report template.
- Playwright with pinned Chromium renders both browser-visible HTML and tagged PDF from that
  template using print CSS, embedded fonts, and RTL-aware layouts.
- XlsxWriter produces Excel workbooks directly from the immutable fact package.
- Excel generation writes governed literal values and safe labels only. Formula and automatic URL
  interpretation are disabled for customer-derived strings.
- Charts consume fact-package series and never independently calculate business figures.
- Every surface must reconcile to the same fact and citation identifiers before delivery.

Chromium is launched with `--disable-dev-shm-usage`. Docker's default `/dev/shm` is 64 MiB and
Chromium's shared-memory use exceeds that while rendering a paginated document, failing as a
renderer crash rather than as a memory limit. This is a correctness requirement, not a tuning flag,
and it survives the change of host for the same reason it survived the previous one.

### Target capability contract

The target is defined by what it must provide. Where the honest answer is a rule rather than a
value, this decision states the rule and requires the environment descriptor to record the value.

| Capability | Requirement | Recorded by the descriptor |
|---|---|---|
| Container runtime | Runs the pinned OCI image as two distinct process roles, without interactive access | Host product, vCPU, memory, disk |
| Relational store | PostgreSQL 17, TLS required, point-in-time recovery, exact live minor version captured and recorded | Product, exact minor version, sizing, RTO and RPO |
| Object storage | S3-compatible API, private, non-versioned, seven-day expiry, multipart-abort on deletion | Endpoint product, region |
| Secret store | Outside the repository and outside the image | Product |
| TLS ingress | Terminated by a component that is not the application | Product |
| Outbound access | Restricted to approved dependencies; stable egress identity only where an approved dependency requires source-IP allowlisting | Whether a stable identity exists, which dependency requires it, and the control applied when absent |

Two rows differ from `KHEPRI-DEC-008`. Both are recorded below with the property each protects,
because a relaxation whose protected property is not restated is an unbounded relaxation.

#### Changed row 1 — PostgreSQL minor upgrades

`KHEPRI-DEC-008` required "automatic minor upgrade disabled". It stated the reason: an upgrade
that changed the engine underneath an approved `environment_digest` "would silently invalidate
every prior run's evidence while the digest still matched".

The selected managed product does not permit disabling minor upgrades, so the control is restated
as the property it protects rather than as the mechanism that happened to protect it:

- the exact live PostgreSQL minor version is captured from the database after creation;
- it is recorded in the environment descriptor and its evidence;
- it contributes to `environment_digest`;
- certification compares the live server minor version against the recorded value;
- a mismatch **refuses certification** rather than accepting the stale digest;
- a provider minor-version change requires descriptor and digest re-issuance, and re-evidencing of
  every affected run.

**A declaration alone does not achieve this, and this decision does not pretend otherwise.**
`resolve_approved_benchmark` reads `KHEPRI_BENCHMARK_ENVIRONMENT_DIGEST` as a static value
(`src/khepri/rra/benchmark_authorization.py`), and nothing in the runtime queries the live engine.
Without the comparison above implemented, a run would proceed against a new engine while the old
digest still matched — the same silent invalidation, merely relocated from the upgrade to the
digest. The row is satisfied only in combination with that runtime check, which
`KHEPRI-DEC-029` owns as the decision holding `environment_digest`. Until it exists, no run against
this target is governed evidence.

The cost is stated rather than hidden. Under the predecessor a minor-version change could not
occur; under this decision it can, and each occurrence obliges digest re-issuance and re-evidencing.
That is operational work this decision creates, accepted because the alternative — self-hosting
PostgreSQL and self-producing all durability, backup, and recovery evidence — was rejected on
stronger grounds.

#### Changed row 2 — egress identity

`KHEPRI-DEC-008` required a stable and restricted egress identity unconditionally, with the
descriptor recording an address or range. The protected property is that outbound access is
bounded and attributable, not that a fixed address exists.

The replacement, per the owner ruling:

- outbound access is restricted to approved dependencies;
- a stable egress identity is required **only** where an approved dependency requires source-IP
  allowlisting;
- the environment descriptor records whether a stable egress identity exists, which dependency
  requires it when present, and the outbound-access control used when it is absent.

This is what admits the settled architecture. The provider documents that dedicated egress IPs are
"only supported for apps not connected to a VPC", so an unconditional fixed-address requirement and
private VPC database connectivity are mutually exclusive on App Platform. The predecessor's row
forced Droplets purely to manufacture an address no approved dependency currently requires. No
approved dependency requires source-IP allowlisting today; if one is later approved, this row
requires the stable identity rather than permitting its absence.

That provider constraint is recorded in the OPS1 portability analysis
(`docs/platform/proposed-governance/ops1-provider-portability-and-target-selection.md`, finding
D6), which cites DigitalOcean's own documentation at
<https://docs.digitalocean.com/products/app-platform/how-to/add-ip-address/>. The citation is given
here because a governed decision should not rest on an external factual claim a reader cannot trace
from the decision itself. A provider change to this behaviour would reopen the row.

#### The S3-compatible requirement is a portability boundary, not neutrality

Carried forward unchanged.

Requiring an S3-compatible API fixes one wire protocol so that DigitalOcean Spaces, MinIO, Garage,
Ceph RGW, and Amazon S3 are substitutable without a code change, and excludes everything else:
block storage, POSIX filesystems, and non-S3 object APIs are out of contract. It is the narrowest
interface that keeps the existing `EncryptedObjectStore`, `DeletionObjectStore`, and
`ProfileObjectReader` ports intact while admitting inexpensive hosts.

The cost is stated rather than hidden. An S3-compatible implementation is only as good as its
consistency, durability, and expiry semantics, and those differ between implementations.
Substitutability at the API is not equivalence in behaviour, which is why the object-store
confirmation below remains a gate rather than a claim.

#### Object storage control: application-side envelope encryption

Carried forward unchanged.

Stored objects are encrypted by the application: a per-object AES-256-GCM data key, wrapped by a
master key drawn from the secret store, with the ciphertext digest verified on read-back. The
application knows the bytes are encrypted because it encrypted them, and the remaining proof
obligation is that the exact ciphertext written is the ciphertext read, which a digest settles
without trusting any provider header.

One property is lost and is recorded as accepted rather than argued away. A customer-managed key
service keeps key custody outside the application's blast radius; a master key drawn into the
application process does not. The compensating controls are the absence of interactive host access,
the transient presence of customer content, and the seven-day expiry.

Provider-side encryption at rest, where the target offers it, remains required and is additional to
this control, never a substitute for it.

#### Job delivery: PostgreSQL claim and redrive

Carried forward unchanged. Job delivery uses PostgreSQL with `SELECT ... FOR UPDATE SKIP LOCKED`,
a claim query, and a redrive sweep. No message broker is introduced. Messages remain opaque job
identifiers. At-least-once delivery, bounded retries, and dead-lettering remain required.

#### Infrastructure access

Carried forward unchanged, and the settled rulings restate it. Deployment happens only through
continuous integration. Interactive runtime access is disabled by default: any provider permission
allowing console or shell access is withheld from the ordinary deploy and operator role.
Break-glass access, if later enabled, is time-boxed, logged, and recorded as an operational event
under the content-free telemetry rules.

The requirement is runtime access to the host, not an infrastructure change trail — infrastructure
defined as code in a reviewed repository already produces the latter. Its cost is stated: diagnosis
by logging into the host is unavailable, and diagnostic needs must be met by telemetry.

#### Secrets, ingress, and image distribution

Runtime secrets come from a store that is neither the repository nor the image, and supply the
envelope master key. TLS is terminated by a component that is not the application. The pinned OCI
image is published to a registry recorded by the descriptor; continuous integration validates,
builds, scans, and publishes it, and publishing an image is not deploying one.

Per the settled rulings, the initial private beta uses App Platform encrypted runtime secrets
rather than introducing a separate secret-management product. These carry at least
`KHEPRI_STORAGE_MASTER_KEY`, database credentials and configuration, object-storage credentials,
Clerk credentials where `KHEPRI-DEC-025` applies, and any other runtime secret an active
specification introduces. The CI deployment credential remains a GitHub Actions secret and is
never injected into the Khepri runtime.

### Narrative provider

Carried forward unchanged.

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

Carried forward, with the destinations re-pointed to the settled direction.

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

The settled direction is DigitalOcean-native service health and metrics for provider and runtime
state, plus Better Stack for centralized application logs and OTLP-compatible telemetry. A
different vendor may later replace Better Stack without an architecture change, provided the
content-free telemetry contract and the OTLP boundary remain intact.

**Recovery objectives.** RTO is two hours and RPO is fifteen minutes, as objectives to prove rather
than as achieved properties. The seven-day content and backup horizon imposed by existing beta
governance remains binding; an RPO target does not widen retention. PostgreSQL high-availability
topology is a beta-authorization checkpoint, not assumed by the first measurement: the final
topology must either enable the provider's standby capability or carry recovery evidence proving a
simpler topology satisfies these objectives.

### Sizing

Carried forward as rules in provider-neutral units. No final capacity value is fixed here.

- One report job per worker process. Throughput is bought by process count, never by in-process
  concurrency: a second concurrent job in the same process would contend for the same cores during
  rendering and could exhaust memory whenever two large-band datasets met, making duration a
  function of what else happened to be running.
- Worker memory holds a pinned Chromium rendering six surfaces, including a tagged paginated PDF,
  together with a Polars frame derived from an input bounded at 52,428,800 bytes whose in-memory
  width exceeds its stored width, plus that frame's aggregation intermediates. Chromium is the
  largest single consumer and does not shrink with dataset size.
- Worker cores are sized so that the completion objective is decided by the pipeline rather than by
  core count.
- Worker disk holds the baked browser, the downloaded input, six rendered surfaces, the workbook
  and PDF temporaries, and the shared-memory allocations `--disable-dev-shm-usage` redirects.
- The web role renders templates, streams uploads, and enqueues jobs. It performs no rendering and
  holds no fact package. Its memory is sized so that several concurrent uploads bounded at
  52,428,800 bytes each are a slow event rather than an out-of-memory event.
- Lease duration is 300 seconds, extended by a heartbeat every 60 seconds. Retry delay is 60
  seconds. Attempts before dead-lettering are 3.
- Storage delivers its baseline performance continuously rather than through an accumulated credit
  balance, so that two runs with identical digests cannot differ because of invisible state.
- Backup retention matches the seven-day object expiry so that no retention horizon is quietly
  longer than another.

`governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` is re-issued against the selected target. The
keys `visibility_timeout_seconds`, `message_retention_seconds`, `receive_wait_seconds`, and
`max_receive_count` describe a message broker this architecture does not include and leave the file.

**Final sizing remains evidence-driven.** It is `OPS1-09`'s to produce from measurement against
the final descriptor, not this decision's to assert.

### Target selection

`KHEPRI-DEC-008` required this content in a separate artifact. This decision supplies it, which is
why it supersedes rather than accompanies its predecessor.

**Provider and region.** DigitalOcean, FRA1 (Frankfurt).

**Residency justification.** The current non-paying private-beta stage has no Middle East
data-residency requirement and no client commitment overriding FRA1. Every service-level storage
location recorded below is FRA1. A future contract, legal determination, or product commitment
requiring another jurisdiction is a trigger to revisit this before serving that customer.

**Concrete products satisfying each capability.**

| Capability | Product | Notes |
|---|---|---|
| Container runtime — web | DigitalOcean App Platform web service | Same pinned image as the worker |
| Container runtime — worker | DigitalOcean App Platform worker | Independently scaled; no public ingress |
| Migration execution | App Platform pre-deploy / one-shot job | Release-gating; expand → deploy → contract |
| Relational store | DigitalOcean Managed PostgreSQL 17 | TLS required; PITR required; exact live minor captured at provisioning |
| Object storage | DigitalOcean Spaces, private, non-versioned | **Conditional** — see the confirmation gate below |
| Secret store | App Platform encrypted runtime secrets | CI deployment credential excluded from the runtime |
| TLS ingress | App Platform managed TLS termination | Terminated outside the application process |
| Network | DigitalOcean VPC with private managed-database connectivity | Public database connectivity is not the normal path |
| Outbound access | Restricted to approved dependencies; no dedicated static egress IP | No approved dependency currently requires source-IP allowlisting |
| Image registry | DigitalOcean Container Registry | Immutable digests; never a floating `latest` tag |
| Infrastructure definition | Terraform for long-lived infrastructure, App Platform specification for app roles | File layout is implementation work |
| Deployment execution | GitHub Actions | Executes; does not approve |
| Observability | DigitalOcean native health/metrics plus Better Stack OTLP | Content-free telemetry contract binding |

No Droplet, Kubernetes, Kafka, Redis, or RabbitMQ tier is part of this target.

**Object-store semantics confirmation is a pre-certification gate, not a satisfied claim.**
`KHEPRI-DEC-008` requires written confirmation that the chosen store's expiry, deletion, and
multipart-abort semantics satisfy `RRA-002`. That confirmation does not exist. Spaces is therefore
recorded as the leading candidate and remains **conditional**: the exact API behaviour used by
`khepri.rra.storage` must be exercised against a real FRA1 bucket — conditional write behaviour,
read-after-write, deletion, list and abort multipart behaviour, and lifecycle semantics — before
any certification may rely on it. An incompatibility fails closed and reopens the storage product
choice; it never justifies a provider-specific branch inside application code.

**Recorded RTO and RPO.** Two hours and fifteen minutes respectively, as objectives to prove.

**Sizing values.** Not fixed here. The provisional measurement shape a bootstrap may claim is
`KHEPRI-DEC-030`'s; final sizing is `OPS1-09`'s from measurement.

### Delivery controls

Carried forward unchanged.

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

- Amending only the two changed rows of `KHEPRI-DEC-008` was not selected because it would leave an
  accepted governed document asserting a minor-upgrade control the provider does not offer and an
  egress requirement the settled architecture does not meet.
- Carrying the unconditional stable-egress row forward was not selected because it is mutually
  exclusive with private VPC database connectivity on the selected runtime, and it would force
  Droplets solely to manufacture an address no approved dependency requires.
- Self-hosted PostgreSQL on a Droplet, which would permit disabling minor upgrades, was not
  selected because it moves patching, TLS, backup scheduling, PITR machinery, restore verification,
  and host hardening into Khepri's operational burden before those capabilities have independent
  evidence.
- Recording Spaces as confirmed rather than conditional was not selected because no empirical
  verification against a real FRA1 bucket exists, and recording an unverified confirmation would
  convert a gate into a claim.
- Deferring the two changed rows to a later decision was not selected because the settled rulings
  cannot be implemented while the predecessor's text stands, which is the block this transition
  exists to clear.

## Consequences

- The runtime remains defined by capabilities; the concrete products are now recorded here rather
  than deferred to an artifact that does not exist.
- A provider minor-version change is now possible and becomes an explicit, visible
  digest-invalidating event rather than an impossibility.
- Outbound access is bounded by approved dependencies rather than by a fixed address, and the
  descriptor must record which control applies.
- `src/khepri/infra/` remains frozen reference: kept green by continuous integration, not the
  deployment path, and closed to new slices.
- Key custody remains weaker than a customer-managed key service provides, mitigated as described
  and recorded as accepted.
- Diagnosis by interactive host access remains unavailable by design, which raises the cost of a
  telemetry gap.
- `KHEPRI-DEC-008` moves to `retired`, retaining its evidence unchanged.
- **`KHEPRI-DEC-005` and `KHEPRI-DEC-007` are re-pointed to name this decision as their successor.**
  Both are retired and named `KHEPRI-DEC-008`, which this transition retires; the validator requires
  a named successor to be active (`_validate_successor` in `src/khepri_gov/validator.py`), so
  leaving them would fail with `successor 'KHEPRI-DEC-008' must be active`. Re-pointing follows the
  authority rather than rewriting history: this decision now carries the runtime-target authority
  those two originally held, by way of the predecessor it supersedes. Their own documents and
  evidence are untouched.
- No environment exists until `KHEPRI-DEC-030` authorizes a provisional bootstrap, and no beta
  authorization exists until the separate later artifact issues it.

### Follow-on obligations

- Implement the runtime PostgreSQL minor-version check that compares the live server version
  against the recorded value and refuses certification on a mismatch. Until it exists, no run
  against this target is governed evidence. **`KHEPRI-DEC-029` is the owning decision**, because
  the check gates certification and that decision holds `environment_digest`; it is listed here
  because this decision's capability row is unsatisfied without it, not to claim ownership.
- Empirically verify Spaces against the `khepri.rra.storage` contract and record the result.
- Re-issue `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` against the selected target.
- Unlock `src/khepri/runtime/config.py` from any remaining AWS-shaped pinning.

Identity, lifecycle state, dependencies, and supersession are authoritative in
`governance/registry.yaml`. Git history retains the transition evidence.
