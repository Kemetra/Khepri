# RRA VPS target decision — design

Date: 2026-08-02

Authority: none. This document designs a decision that does not exist yet. `KHEPRI-DEC-005`
(runtime, providers, deployment boundary) and `KHEPRI-DEC-007` (sizing) remain `accepted` and
authoritative in `governance/registries/decisions.yaml` until a named authority approves their
supersession. Nothing here is approval, and nothing here changes a registry.

## Outcome

One new decision, provisionally `KHEPRI-DEC-008`, supersedes `KHEPRI-DEC-005` and
`KHEPRI-DEC-007`. It freezes the AWS deployment path, replaces the AWS service selections with a
provider-neutral target capability contract, and requires a separate target-selection decision to
settle the concrete provider and data-residency region **before** any deployment definition is
written.

## Why this is possible at all

The AWS coupling is narrower than the repository's history suggests, and three measurements
decide the shape of this work.

**The approved specifications name no AWS service.** A case-insensitive search of
`governance/specifications/` for `aws`, `amazon`, `sqs`, `s3`, `fargate`, `cloudwatch`, `kms`,
`ecs`, and `rds` returns nothing across `RRA-001` through `RRA-007`. `RRA-002` states the storage
obligation as "encrypt stored input and derived content in transit and at rest in isolated object
namespaces", which is a property, not a product. **No specification changes, and no specification
approval is re-issued.**

**`boto3` is imported in two modules.** `src/khepri/runtime/wiring.py` and
`src/khepri/local/storage.py`. Every consumer depends on a `Protocol` — `EncryptedObjectStore`,
`DeletionObjectStore`, `ProfileObjectReader`, `DeliveryStore`, `ReportPublisher`, `ReportJobStore`,
`S3Client`, `SqsClient`. The ports already exist; only adapters change.

**AWS-bound code is about 7% of the tree.** `src/khepri/infra/` is 1,351 lines with 1,575 lines of
tests, against 18,827 lines of source and 20,689 lines of tests overall.

The product — the pipeline, the fact package, the narrative, the three surfaces, bilingual parity,
deletion evidence, job state, telemetry semantics, and the migrations — is untouched by a change of
host.

## Sequence, and the circularity it avoids

The obvious shortcut is to let the beta-authorization artifact settle the provider and region.
That shortcut is circular: the deployment definition needs a concrete provider and region; the
environment descriptor and sizing depend on the deployment target; the governed benchmark must run
on the final target environment; and beta authorization should follow the benchmark evidence, not
precede it. Assigning target selection to beta authorization makes beta authorization both a
consumer and a producer of the same fact.

The governed order is therefore:

```
KHEPRI-DEC-008  (freeze AWS; target capability contract)
  → provider-neutral portability slices
  → target-provider and residency decision          <- separate, pre-deployment
  → target deployment definition
  → re-issued sizing and environment descriptor
  → governed benchmark on that environment
  → beta authorization
```

`KHEPRI-DEC-008` leaves the provider and residency region unresolved and **requires a separate
target-selection artifact to resolve them before a deployment definition may be written**. That
artifact's identifier is assigned when it is written; this design does not reserve one. Its
required content is fixed here: the provider, the region, the residency justification, the concrete
products satisfying each capability below, and the recorded exact versions.

Leaving the region open is not an evasion of Constitution VII. It is a refusal to record a
residency commitment that no approved artifact supports, and the fail-closed consequence is
explicit: absent that decision, no deployment definition exists, so no environment exists, so no
benchmark evidence exists, so beta cannot be authorized.

## Supersession rather than amendment

`KHEPRI-DEC-008` restates the architecture in full, with the deployment section replaced, and moves
both prior decisions to `superseded`. The alternative — amending only DEC-005's deployment section
and leaving it `accepted` — would leave an accepted governed document asserting that AWS is the
deployment path. Constitution I gives each governed fact one authoritative representation, and two
live architecture decisions with contradictory deployment sections is exactly the drift the
constitution forbids.

Three mechanics were verified against the validator before choosing this shape.

**Superseding DEC-005 cannot break the specification chain.** `_validate_dependencies` in
`src/khepri_gov/validator.py` runs per registry, and specification `depends_on` entries reference
specifications only. There is no dependency edge from a specification to a decision, so the
`RRA-001`–`RRA-007` entries are unaffected.

**A superseded decision keeps its approval evidence.** `validator.py` treats
`APPROVED_STATES["decisions"]` as `{"accepted"}` and skips the `APPROVAL_FIELDS` check for any
other state. `KHEPRI-DEC-005` and `KHEPRI-DEC-007` therefore retain `approved_by`, `approved_at`,
and `approval_ref` unchanged, which is what Constitution VI requires when it says supersession
"never rewrites prior authority".

**One approval package can supersede two.** `supersedes_approval_ref` is validated per artifact
entry, not per package, in `src/khepri_gov/approval_packages.py`. A future package can carry
`APP-003` on the DEC-005 entry and `APP-005` on the DEC-007 entry.

### Known gap

The registry schema has no `superseded_by` field and the validator enforces no supersession
linkage. The relationship will be stated in the decision prose. Adding registry and validator
support is a follow-on obligation, recorded here so it is not mistaken for an oversight, and
deliberately outside this slice.

## The target capability contract

`KHEPRI-DEC-008` fixes what the target must provide. The target-selection artifact and the
environment descriptor record which products provide it, at which versions, at which sizes. This
follows `KHEPRI-DEC-007`'s own discipline: where the honest answer is a rule rather than a number,
state the rule and require the descriptor to record the number.

| Capability | Requirement | Recorded by the descriptor |
|---|---|---|
| Container runtime | Runs the pinned OCI image as two distinct process roles, without interactive access | Host product, vCPU, RAM, disk |
| Relational store | PostgreSQL 17, TLS required, point-in-time recovery, disabled automatic minor upgrade | Product, exact minor version, sizing, RTO and RPO |
| Object storage | S3-compatible API, private, non-versioned, seven-day expiry | Endpoint product, region |
| Secret store | Outside the repository and outside the image | Product |
| TLS ingress | Terminated by a component that is not the application | Product |
| Egress identity | Stable and restricted | Address or range |

### The S3-compatible requirement is a portability boundary, not neutrality

Requiring an S3-compatible API is a deliberate, bounded portability decision, not a claim that the
object store is interchangeable with any storage technology. It fixes one wire protocol so that
DigitalOcean Spaces, MinIO, Garage, Ceph RGW, and Amazon S3 are substitutable for each other
without a code change, and it excludes everything else — block storage, POSIX filesystems, and
non-S3 object APIs are out of contract.

The boundary is chosen because it is the narrowest interface that keeps the existing
`EncryptedObjectStore`, `DeletionObjectStore`, and `ProfileObjectReader` ports intact while
admitting cheap hosts. The cost of the boundary is stated rather than hidden: an S3-compatible
implementation is only as good as its consistency, durability, and expiry semantics, and those
differ between implementations. The target-selection artifact must record which implementation was
chosen and confirm that its expiry rule, deletion semantics, and multipart-abort behaviour satisfy
`RRA-002`. Substitutability at the API is not equivalence in behaviour.

## Control changes

### Object storage: application-side envelope encryption

`S3EncryptedObjectStore` currently trusts nothing and verifies that the `PutObject` response
*proves* the storage policy: matching checksum, `aws:kms` encryption, the exact configured customer
managed key ARN, `BucketKeyEnabled`, and no `VersionId`. No S3-compatible store outside AWS can
satisfy those five. DigitalOcean Spaces has no customer managed key and never returns
`BucketKeyEnabled`; MinIO rewrites the key identifier to `arn:aws:kms:<keyname>`, carrying neither
region nor account.

The replacement is a per-object AES-256-GCM data key, wrapped by a master key drawn from the secret
store, with the ciphertext digest verified on read-back.

This changes the character of the proof, and improves it. Today the application asks the provider
to attest that it encrypted the bytes, and validates the attestation. Under envelope encryption the
application knows the bytes are encrypted because it encrypted them; the remaining proof obligation
is that the exact ciphertext written is the ciphertext read, which a digest settles without trusting
any provider header.

One property is genuinely lost and must be recorded as accepted rather than argued away. A KMS
customer managed key keeps key custody outside the application's blast radius. A master key drawn
into the application process does not. The compensating controls are the absence of interactive host
access described below, the transient presence of customer content on the host, and the seven-day
expiry.

A side effect worth having: `docker-compose.local.yml` currently pins LocalStack to 3.8.1 solely
because LocalStack's KMS issues genuine `me-central-1` ARNs and MinIO's does not. Once the store no
longer reads provider encryption headers, that constraint disappears and the local journey can run
against any S3-compatible endpoint.

### Job delivery: PostgreSQL `SKIP LOCKED`

`KHEPRI-DEC-005` rejected PostgreSQL-only queueing because it "would require custom visibility,
redrive, and dead-letter behavior". `RRA-007` then implemented most of that in PostgreSQL anyway:
`job_persistence` owns leases, `max_attempts`, retries, and the distinct dead-letter reasons
`DEAD_LETTER_RETRIES_EXHAUSTED` and `DEAD_LETTER_CONTENT_DELETED`, and `local/sweeper.py` already
runs a recovery and expiry pass. The rejection's premise has been overtaken by what was built, and
`KHEPRI-DEC-008` reverses it on that ground rather than on cost.

What remains to add is a claim query and a redrive sweep. `src/khepri/rra/sqs_queue.py` and the
one-message SQS driver in `src/khepri/runtime/worker.py` are removed.

Two hazards collapse rather than move. `KHEPRI-DEC-007` had to force the SQS visibility timeout and
the PostgreSQL lease to the same 300 seconds, because different values produce a window in which
one mechanism believes a job is owned and the other does not. It also had to force
`maxReceiveCount` and `max_attempts` to the same 3, because if SQS exhausted first a message would
reach the dead-letter queue while PostgreSQL still considered attempts available, and the governed
dead-letter reason would be absent or wrong. With one mechanism, both properties are true by
construction instead of by matched configuration, and two ways to misconfigure the system stop
existing.

### Infrastructure access: no interactive host access

A VPS introduces a risk Fargate did not have. A human can log into the host that is processing
customer data, with the envelope master key in that process's memory. `CloudTrail` is not the thing
to replace — infrastructure-as-code in a reviewed repository already produces a change trail. The
gap is runtime access to the host.

Deploys happen only through CI. Interactive access is disabled by default and re-enabled only as a
logged, time-boxed break-glass action recorded as an operational event under the existing
content-free telemetry rules. This preserves a property the managed runtime supplied for free, and
its cost is stated plainly: debugging by logging into the box is not available.

### Secrets, ingress, registry

Secrets come from a secret store that is neither the repository nor the image, and supply the
envelope master key. TLS is terminated by a component that is not the application. The image
publishes to GHCR; `.github/workflows/image.yml` already reports "NOT PUBLISHED" and succeeds when
no registry is configured, so retargeting it changes the publish job only.

## Carried forward unchanged

The modular monolith and its two process roles; FastAPI with Uvicorn; Jinja2 server-side rendering;
SQLAlchemy 2, Psycopg 3, and Alembic; Polars with the fastexcel/calamine reader; integer minor
units and exact decimals for monetary facts; XlsxWriter; Playwright with pinned Chromium; the
`FactPackage`, `NarrativeAdapter`, and `ReportBundle` contracts; opaque queue messages; the full
OpenAI Zero Data Retention gate set and its fail-closed deterministic fallback; the content-free
telemetry field list; every delivery control, including at least 95% complete report bundles within
ten minutes for the approved benchmark workload.

`--disable-dev-shm-usage` is retained. `KHEPRI-DEC-007` required it because Fargate fixes
`/dev/shm` at 64 MiB, and Chromium exceeds that while rendering a paginated document, failing as a
renderer crash rather than as a memory limit. Docker's default `/dev/shm` is also 64 MiB, so the
requirement survives the move for the same reason.

## Sizing

`KHEPRI-DEC-007`'s numbers are derived from valid Fargate CPU and memory combinations, Fargate
ephemeral-storage bands, RDS instance classes, and gp3 burst behaviour. None of those constrain the
new target, so the numbers go.

Its reasoning largely transfers, and `KHEPRI-DEC-008` restates it as rules in provider-neutral
units: one report job per worker process, because the sizing is the sizing of exactly one pipeline
and a second concurrent job makes duration a function of what else was running; worker memory sized
to hold a pinned Chromium rendering six surfaces plus a Polars frame derived from an input bounded
at 52,428,800 bytes, whose in-memory width exceeds its stored width; worker disk sized for the baked
browser, the downloaded input, six rendered surfaces, and the PDF and workbook temporaries; a
300-second lease with a 60-second heartbeat; three attempts; and storage that delivers its baseline
continuously rather than through an accumulated credit balance, so that two runs with identical
digests cannot differ because of invisible state.

`governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` is re-issued against the chosen target. The
SQS-shaped keys `visibility_timeout_seconds`, `message_retention_seconds`, `receive_wait_seconds`,
and `max_receive_count` leave the file. `KHEPRI-DEC-006`'s workload — 40 synthetic datasets, the
integer-exact 95% threshold, and the ten-minute objective — is provider-neutral and survives
unchanged.

## Repository consequences

`src/khepri/infra/` becomes frozen reference: kept green by CI, not the deployment path, and closed
to new slices. It is not deleted. It passes its 1,575 lines of tests, and it is the only worked
example of the sizing reasoning that the new target must reproduce.

Follow-on slices, each independently verifiable and each requiring its own approved authority:

1. PostgreSQL claim-and-redrive queue adapter; remove the SQS adapter and driver.
2. Portable object store with envelope encryption; remove the five provider-header proofs.
3. Unlock `src/khepri/runtime/config.py` from `me-central-1`, the 12-digit account, and the KMS ARN.
4. Target deployment definition, after the target-selection decision.
5. GHCR publish.

## What this design does not do

It creates no decision document, no approval package, and no registry entry. It changes no
lifecycle state and records no supersession link. `KHEPRI-DEC-005` and `KHEPRI-DEC-007` remain
`accepted`. It touches no application code and nothing under `src/khepri/infra/`.

Writing `KHEPRI-DEC-008`, issuing its approval package, moving the prior decisions to `superseded`,
and recording approval evidence are future actions, each requiring explicit, traceable evidence from
the named active authority. A design document is not authority, and neither is a merged pull
request.

## Scope boundary

`KHEPRI-DEC-008` settles the private-beta runtime target only. `KHEPRI-DEC-003` and
`KHEPRI-DEC-005` exclude public signup, commercial authentication, persistent workspaces,
organizations, billing, scheduling, agency features, forecasting, and customer-defined formulas
from the private beta, and no specification approves any of them. Affordability at commercial scale
motivated this work, and the decision records that motivation while authorizing none of it. The
commercial phase requires its own decision chain once multi-tenancy, authentication, and billing
have approved specifications.
