# KHEPRI-DEC-005: RRA private-beta runtime and provider architecture

> Retired and superseded by `KHEPRI-DEC-008`.

## Context

The approved RRA specifications require final technology and provider selections before product
implementation begins. The architecture must support deterministic retail calculations,
Arabic/English parity, immediate and seven-day deletion, content-free observability, recoverable
background processing, and the initial performance objective without introducing deferred
commercial capabilities.

## Decision

Implement RRA as a greenfield Python 3.13 modular monolith. One versioned codebase and container
image expose two independently scaled process roles:

- a synchronous web/API service; and
- a bounded background report worker.

The roles share domain contracts and persistence but communicate through identifiers and
durable job state. They are not separate product services.

### Application stack

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

- `FactPackage` is immutable, versioned, content-addressed, and the sole source for narrative,
  charts, web, PDF, and Excel output.
- `NarrativeAdapter` accepts only approved aggregate facts, safe labels, caveats, language
  instructions, and citation identifiers. It returns cited prose or a refusal.
- `ReportBundle` binds Arabic and English web, PDF, and Excel surfaces to one fact-package
  version and provenance record.
- PostgreSQL owns canonical job state, idempotency keys, leases, retries, reconciliation state,
  and deletion evidence.
- Queue messages contain only opaque job identifiers and routing metadata.

### Report generation

- Jinja2 supplies the canonical bilingual HTML report template.
- Playwright with pinned Chromium renders both browser-visible HTML and tagged PDF from that
  template using print CSS, embedded fonts, and RTL-aware layouts.
- XlsxWriter produces Excel workbooks directly from the immutable fact package.
- Excel generation writes governed literal values and safe labels only. Formula and automatic
  URL interpretation are disabled for customer-derived strings.
- Charts consume fact-package series and never independently calculate business figures.
- Every surface must reconcile to the same fact and citation identifiers before delivery.
- A workbook may carry numeric cells solely as chart series addresses, on a dedicated worksheet
  that holds no authoritative figure and no citation identifier. Such cells are excluded from the
  surface content a bundle reconciles, and the authoritative figure remains the decimal string on
  the section worksheet. This narrows the binary floating-point prohibition above; it does not
  relax it.

### Cloud provider and deployment

Use Amazon Web Services in the Middle East (UAE) region, `me-central-1`, for the private beta:

- Amazon ECS on AWS Fargate runs separate web and bounded-worker services from one image stored
  in Amazon ECR.
- An Application Load Balancer terminates public HTTPS for the web service.
- Application tasks, PostgreSQL, and internal endpoints run in private subnets with least-
  privilege security groups and IAM task roles.
- Amazon RDS for PostgreSQL 17 is the authoritative metadata and fact store. It uses Multi-AZ
  deployment, encrypted storage and backups, TLS connections, and an AWS KMS customer-managed
  key. Supported minor upgrades require compatibility and recovery verification.
- Amazon S3 stores uploads and generated artifacts in a private, non-versioned ephemeral-content
  bucket using SSE-KMS with a customer-managed key, blocked public access, opaque keys, checksum
  verification, and a seven-day expiration rule.
- Immediate deletion permanently deletes every indexed object and aborts incomplete multipart
  uploads. Lifecycle expiration is a backstop, not proof of timely application deletion.
- Amazon SQS Standard provides at-least-once job delivery with visibility-timeout heartbeats,
  bounded retries, and a dead-letter queue. PostgreSQL idempotency and leases make duplicate
  delivery safe.
- AWS Secrets Manager stores runtime secrets.
- AWS CloudTrail and KMS audit infrastructure access without recording customer content.
- AWS CDK v2 in Python defines reproducible infrastructure.
- GitHub Actions validates, builds, scans, and publishes the pinned OCI image. Deployment to a
  beta environment requires an explicit protected-environment authorization.

Required regional service availability and account data-location settings must be verified
before infrastructure provisioning. No cross-region replication or multi-region customer-data
copy is authorized.

### Narrative provider

The initial optional narrative adapter targets the OpenAI Responses API, subject to all of the
following gates:

- an executed data-processing agreement;
- explicit organization and project approval for Zero Data Retention;
- technical verification of the approved Zero Data Retention configuration;
- `store=false` on every request;
- synchronous requests only;
- no background mode, conversations, assistants, threads, files, vector stores, hosted tools,
  extended prompt caching, or provider-side state;
- no raw rows, source column values, owner/session identifiers, storage locations, secrets, or
  unapproved personal data;
- a governed model allowlist and pinned adapter/request-schema version; and
- response validation rejecting unsupported numbers, citations, claims, or unsafe labels.

Training opt-out without verified Zero Data Retention is insufficient. If any gate is absent,
revoked, or unverifiable, the OpenAI adapter remains disabled and RRA delivers the deterministic
cited facts-only report authorized by RRA-005 and RRA-006.

The exact model snapshot is an operational configuration selected through bilingual grounding,
latency, refusal, and privacy-gate evidence. Changing providers or materially changing provider
data handling requires a new or superseding architecture decision.

### Observability and recovery

- OpenTelemetry emits stable traces and metrics to Amazon CloudWatch.
- Python structured logs go directly to CloudWatch and remain content-free.
- Telemetry records opaque correlation IDs, stage names, state transitions, durations, queue
  time, retries, provider latency, dataset-size bands, and output sizes.
- Telemetry excludes filenames, labels, source values, narrative, facts, invitations, tokens,
  and object locations.
- ECS worker concurrency and SQS consumption are bounded by configured CPU, memory, database,
  provider, and latency budgets.
- Every stage is independently timed and retry-safe.
- Database backups and restore exercises protect operational state while content-retention and
  deletion rules continue to apply.
- Content-free deletion evidence retains identifiers, timestamps, digests, attempted locations,
  outcomes, and retry history only.

### Delivery controls

Implementation is authorized only in specification-linked, independently verifiable slices.
Before beta launch, the implementation must demonstrate:

- cross-session isolation and consent enforcement;
- deterministic reconciliation and reruns;
- raw-row exclusion from narrative requests;
- Arabic/English fact and caveat parity;
- accessible RTL web and PDF output;
- safe Excel output;
- immediate deletion and seven-day expiry;
- restart, retry, dead-letter, and orphan recovery;
- content-free telemetry; and
- at least 95% complete report bundles within ten minutes for the approved benchmark workload.

The later beta-authorization artifact must still define the client count and observation period.
This architecture decision does not authorize public signup, production launch, commercial
authentication, persistent workspaces, organizations, billing, scheduling, agency features,
forecasting, or customer-defined formulas.

## Alternatives not selected

- Django was not selected because its authentication and administration surface exceeds the
  private-beta boundary.
- A React or Next.js SPA was not selected because it would add a second runtime and duplicate
  bilingual rendering responsibilities.
- Celery with Redis or RabbitMQ was not selected because SQS and PostgreSQL provide the required
  bounded delivery and canonical state with fewer operated components.
- PostgreSQL-only queueing was not selected because it would require custom visibility,
  redrive, and dead-letter behavior.
- Lambda and Step Functions were not selected because containerized Polars and Chromium report
  jobs need predictable resources and bounded long-running execution.
- Kubernetes was not selected because its operational surface is unnecessary for the beta.
- WeasyPrint was not selected because Chromium allows the web and PDF surfaces to share one
  rendering engine.
- Pandas and openpyxl were not selected as the primary processing/export stack because Polars
  offers bounded lazy processing and XlsxWriter offers controlled streaming workbook output.
- S3 versioning and Object Lock were not selected for ephemeral customer content because they
  conflict with straightforward permanent deletion.

## Consequences

- The beta has one deployable product codebase with independently bounded web and worker roles.
- Managed AWS services reduce broker and host administration while preserving explicit
  application idempotency and deletion responsibility.
- Non-versioned ephemeral object storage makes permanent deletion simpler but removes recovery
  from accidental object deletion; deterministic regeneration is the recovery mechanism.
- Chromium increases image size and must be pinned, scanned, preloaded, and benchmarked.
- The narrative provider is optional and fails closed; report availability never depends on
  weakening retention requirements.
- PostgreSQL 17, browser, provider, and dependency upgrades require compatibility, numerical
  integrity, bilingual parity, deletion, recovery, and performance evidence.

This decision is historical. Current state and supersession are recorded in
`governance/registry.yaml`.
