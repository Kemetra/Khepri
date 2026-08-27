# OPS1-01 — Private-beta environment owner rulings

> **ACTIVATED.** The governance transition this record's §13 step 1 requires is merged: the two
> governance-impacting rulings (PostgreSQL minor upgrades in §3, egress in §6) are now carried by
> **`KHEPRI-DEC-028`**, the benchmark restatement by **`KHEPRI-DEC-029`**, and the provisional
> bootstrap authority by **`KHEPRI-DEC-030`**, which together retire `KHEPRI-DEC-008`,
> `KHEPRI-DEC-006`, and `KHEPRI-DEC-027`. Those decisions govern; this record remains the
> reasoning behind them. §13 steps 2–9 remain outstanding.

**Status: planning-only proposal record.** This file records the owner's selected implementation direction for the remaining OPS1-01 environment choices. It does **not** amend `governance/registry.yaml`, supersede an active decision, authorize provisioning or spend, or open external traffic. Any ruling that conflicts with an active governed artifact must be activated through the repository's normal governance transition before implementation relies on it.

Prepared against `main` at `ceace057ce1e180fa6fddc851208aa0fd9d1808d`.

## 0. Planning precedence and reconciliation

This record is the latest owner ruling for the OPS1-01 environment direction and **supersedes conflicting planning choices** in these earlier non-governing drafts:

- `docs/platform/proposed-governance/ops1-01-fra1-environment-descriptor-proposal.md`;
- `docs/platform/proposed-governance/ops1-01-superseding-decision-draft.md`;
- PR #286's selected-target table and associated Droplet/Grafana/RTO/sizing choices.

Those artifacts remain useful evidence for the portability analysis, governance mechanics, and defects they discovered, but they are **not activation-ready target definitions** after this ruling. A future governance activation must reconcile from this record rather than activating the stale target choices verbatim.

Where this record conflicts with active governance, active governance still wins until an owner-merged registry transition supersedes it. This record therefore closes planning alternatives without pretending that prose in `docs/` has governing force.

## 1. Selected private-beta target

The private-beta environment is to be designed around the following concrete target:

| Capability | Selected direction | Notes |
|---|---|---|
| Provider | DigitalOcean | Carries forward active `KHEPRI-DEC-027`. |
| Region | FRA1 (Frankfurt) | Carries forward active `KHEPRI-DEC-027`. |
| Web compute | DigitalOcean App Platform web service | No Droplet in the initial private-beta target. |
| Worker compute | DigitalOcean App Platform worker | Separate role from web; same pinned Khepri image. |
| Migration execution | App Platform pre-deploy / one-shot job | Alembic migrations follow expand → deploy → contract; pre-deploy expansion remains compatible with running old roles. |
| Relational store | DigitalOcean Managed PostgreSQL 17 | TLS required; PITR required; exact live minor version must be evidence-bound. |
| Object storage | DigitalOcean Spaces, private, FRA1 — **conditional pending compatibility proof** | S3-compatible; application-side envelope encryption remains authoritative. |
| Image registry | DigitalOcean Container Registry | Deploy immutable image digests; never deploy a floating `latest` tag. |
| Runtime secrets | App Platform encrypted runtime secrets | Includes the envelope master key, database/object-store credentials, and Clerk secrets where applicable. |
| Deployment credential | GitHub Actions secret | Deployment credential does not enter the application container. |
| Network | DigitalOcean VPC with private managed-database connectivity | No dedicated static egress IP unless an approved dependency proves source-IP allowlisting is required. |
| CI/CD | GitHub Actions is the normal deployment execution path | Approval authority remains the owner merge/governance process; CI executes, it does not approve. |
| Infrastructure definition | Terraform for long-lived infrastructure plus an App Platform specification for app roles | Exact file layout is implementation work; this ruling selects the split of responsibility. |
| Observability | DigitalOcean native service health/metrics plus Better Stack for centralized logs and OTLP-compatible telemetry | Customer content must not be emitted into telemetry; the runtime OTLP path is still an implementation prerequisite. |
| Orchestration not selected | No Kubernetes, Kafka, Redis, RabbitMQ, or additional microservice boundary | Carries forward the portable-runtime direction. |

## 2. Web, worker, and migration topology

The initial hosted target uses one pinned Khepri OCI image in three execution roles:

```text
pinned Khepri image
    ├── web service
    ├── worker
    └── pre-deploy migration job
```

Web and worker remain independently scalable roles. The worker remains single-job-at-a-time inside one process and scales by replica count rather than by adding an internal broker or concurrent worker pool. The migration role is one-shot and release-gating; it never runs beside a migration of the same release on another path.

Database changes use **expand → deploy → contract**:

1. an App Platform pre-deploy job runs the Alembic **expand** migration before the new roles deploy;
2. expansion remains compatible with the currently running old web and worker roles;
3. the new web and worker roles deploy and replace the old roles;
4. destructive **contract** cleanup runs in a later release only after the old roles are gone.

No pre-deploy migration may drop or rename a still-used object, or add an incompatible constraint, while old roles may still run. If a change cannot be made compatible, the release must explicitly quiesce the affected roles before applying it rather than assuming pre-deploy ordering makes the change safe.

No initial Droplet is selected. This deliberately avoids adding host patching, SSH administration, Docker-daemon administration, and self-managed load balancing to the beta's operational surface.

## 3. Managed PostgreSQL and minor-version changes

**Selected:** DigitalOcean Managed PostgreSQL 17.

Self-hosted PostgreSQL on a Droplet is rejected for the initial private beta because it would move patching, TLS, backup scheduling, PITR machinery, restore verification, and host hardening into Khepri's own operational burden before those capabilities have independent evidence.

The selected provider may apply PostgreSQL minor upgrades. The owner accepts that operational fact subject to the following control:

1. after the managed database is created, the exact live PostgreSQL minor version is captured from that database;
2. the captured value is recorded before certification and contributes to `environment_digest`;
3. the runtime/benchmark certification path compares the live server minor version with the recorded value;
4. a mismatch refuses certification rather than silently accepting the old digest;
5. a minor-version change requires descriptor/digest re-issuance and the re-evidence required by the governing benchmark decision.

This is a **governance-impacting ruling** because active `KHEPRI-DEC-008` still says automatic minor upgrades are disabled. Implementation must not treat this paragraph as authority until the DEC-008 supersession/restatement is activated in `governance/registry.yaml`.

## 4. Object storage

**Conditionally selected direction:** DigitalOcean Spaces in FRA1, private and non-versioned, subject to the mandatory compatibility proof below.

The application remains responsible for encrypting customer objects before bytes leave the process. Provider-side encryption, when present, is additional and not evidence that replaces Khepri's envelope encryption.

The beta storage policy is:

- private bucket;
- object versioning disabled;
- immediate application deletion when the governed lifecycle requires deletion;
- seven-day automatic expiry as the backstop required by `RRA-002`;
- incomplete multipart uploads cleaned up within the governed horizon where the selected service can enforce that rule;
- per-environment credentials scoped as narrowly as the provider allows.

**Mandatory verification gate:** Spaces is not a final operational product selection until the exact API behavior used by `khepri.rra.storage` is exercised against a real FRA1 bucket, including conditional write behavior, read-after-write, deletion, list/abort multipart behavior, and lifecycle semantics. Any incompatibility fails closed and reopens the storage product choice; it does not justify a provider-specific branch inside application code.

Until that proof is recorded, later planning may prepare around Spaces as the leading target but may not claim `KHEPRI-DEC-008`'s object-storage confirmation requirement is satisfied.

## 5. Secrets and interactive access

For the initial private beta, application runtime secrets are stored as App Platform encrypted secret values rather than introducing an additional secret-management product.

This includes at least:

- `KHEPRI_STORAGE_MASTER_KEY`;
- database credentials/configuration;
- object-storage access credentials;
- Clerk credentials where `KHEPRI-DEC-025` applies;
- other application runtime secrets introduced by an active specification.

The CI deployment credential remains in GitHub Actions secrets and is not injected into the Khepri runtime.

Interactive runtime access remains disabled by default. Any provider permission that allows console/shell access is withheld from the ordinary deploy/operator role. Break-glass access, if later enabled, must be time-bounded, logged, and handled as an operational event under the content-free telemetry rules.

## 6. Networking and egress

The initial target uses a DigitalOcean VPC and private connectivity to Managed PostgreSQL. Public database connectivity is not the normal application path.

A dedicated static egress IP is **not selected** for the initial private beta. The owner chooses private VPC connectivity and managed application runtime over adding Droplets solely to manufacture a fixed outbound address when no approved dependency currently requires source-IP allowlisting.

This creates a **second governance-impacting ruling** for the planned `KHEPRI-DEC-008` successor. Active `KHEPRI-DEC-008` currently requires:

> Egress identity: stable and restricted; descriptor records an address or range.

The successor must not carry that row forward unchanged. The intended replacement property is:

> Outbound access is restricted to approved dependencies. A stable egress identity is required only when an approved dependency requires source-IP allowlisting. The environment descriptor records whether a stable egress identity exists, which dependency requires it when present, and the outbound-access control used when it is absent.

This is not an implementation workaround around active governance. Until the successor is activated, App Platform + VPC does **not** satisfy the current unconditional egress row and therefore cannot be treated as an approved deployment target.

Public ingress terminates TLS outside the Khepri application process. The worker has no public ingress.

## 7. CI/CD and infrastructure definition

GitHub Actions is the normal deployment **execution** path for build and deployment operations. It is not an approval authority. Under the Constitution, owner merge and the active governance registry remain the approval boundary.

Target release flow:

```text
pull request
  -> required CI
  -> owner-approved merge to main
  -> build pinned image
  -> test / security checks
  -> push immutable image to DOCR
  -> validate infrastructure/app specification
  -> run compatible Alembic expand migration job
  -> deploy web + worker and retire old roles
  -> readiness check
  -> content-free smoke verification
  -> in a later release, run eligible contract cleanup
```

Automatic deployment merely because `main` changed is not selected. Deployment remains an explicit CI action with the exact image digest recorded and may execute only after the applicable governance and deployment authority are active.

The pre-deploy job is not permission to make destructive schema changes before old roles stop. Expand migrations must remain compatible with those roles. Contract migrations wait for a later release after replacement is complete; when compatibility is impossible, the deployment procedure explicitly quiesces the affected roles before migration.

Long-lived infrastructure is defined with Terraform; App Platform role/process configuration is defined through an App Platform specification. Manual console edits are break-glass, not the desired steady-state source of truth.

## 8. Health/readiness prerequisite

Hosted deployment requires explicit content-free health endpoints before traffic shifting can be trusted:

- `/health/live`: process liveness only;
- `/health/ready`: verifies that the process is ready to serve the selected environment, including database reachability and migration compatibility, without exposing customer data or secrets.

The exact implementation belongs to a separately admitted product-code slice. This ruling does not authorize code outside an active specification.

## 9. Recovery objectives

The owner selects these **initial private-beta operational objectives**:

- **RTO: 2 hours** — target time to restore service after a qualifying environment failure.
- **RPO: 15 minutes** — target maximum loss of durable operational state after a qualifying disaster.

These are targets, not claims of achieved capability and not provider guarantees. `OPS1-04` must prove the environment can satisfy them through timed restore and recovery exercises. If the selected DigitalOcean products cannot demonstrate these objectives, the environment descriptor or the targets must be revisited before beta authorization.

The seven-day content/backup horizon imposed by existing beta governance remains binding; an RPO target does not widen retention.

## 10. Provisional non-production bootstrap shape, not final sizing

No final web, worker, or database sizing is selected by this planning record. Final sizing belongs to `OPS1-09` and the governed benchmark evidence.

After the required governance activation permits a non-production environment, bootstrap the first hosted measurement with this **provisional shape**:

| Role | Provisional measurement shape |
|---|---|
| Web | 1 shared vCPU, 1 GiB RAM |
| Worker | 2 vCPU, 4 GiB RAM |
| PostgreSQL | a suitable Managed PostgreSQL 17 tier with PITR and private networking enabled |
| Worker replicas | 1 |

The worker starts materially above the web role because report rendering launches pinned Chromium alongside the analytical workload. These values exist only to bootstrap hosted measurement; they are neither final capacity values nor a beta commitment. After creation, capture the live PostgreSQL minor version and complete the mandatory Spaces compatibility verification. `OPS1-09` then runs on the hosted target and may move the provisional values up or down from evidence. Its final environment evidence must record the resulting sizes and captured PostgreSQL minor, and certification must refuse whenever the live minor differs from the recorded value. `OPS1-05` must later run capacity/soak evidence before external private-beta traffic.

High availability for PostgreSQL is a **beta-authorization checkpoint**, not assumed by the first staging measurement. The final beta topology must either enable the provider's HA/standby capability or carry recovery evidence proving that a simpler topology still satisfies the approved RTO/RPO and governing durability requirements.

## 11. Observability

The selected direction is:

- DigitalOcean native health/service metrics for provider/runtime state;
- Better Stack for centralized application logs and OTLP-compatible traces/metrics;
- alerts and dashboards built only from content-free operational signals.

No raw uploaded rows, customer report prose, decrypted object payloads, secret values, or unapproved customer-derived labels may enter telemetry.

**Implementation gap:** selecting an OTLP-compatible destination does not create telemetry. The current runtime does not yet provide the governed OpenTelemetry emission/export path required by `KHEPRI-DEC-008`. That path must be implemented and verified before the observability capability can be claimed complete.

A different observability vendor may later replace Better Stack without changing the application/domain architecture provided the content-free telemetry contract and OTLP boundary remain intact.

## 12. What is now closed for planning

For OPS1 planning, the following choices are no longer open alternatives unless new evidence invalidates them:

- DigitalOcean / FRA1;
- App Platform for both web and worker;
- App Platform one-shot/pre-deploy migrations using expand → deploy → contract compatibility sequencing;
- Managed PostgreSQL 17 rather than self-hosted PostgreSQL;
- DOCR for the target deployment;
- App Platform runtime secrets for the initial beta;
- VPC/private database networking;
- no unconditional static-egress requirement in the intended DEC-008 successor;
- GitHub Actions as the normal deployment execution path;
- Terraform + App Platform spec split;
- no Kubernetes/broker/cache tier;
- initial RTO 2 hours and RPO 15 minutes as objectives to prove;
- DigitalOcean native monitoring plus Better Stack telemetry direction.

The following are **not** closed by this section:

- Spaces final product selection, which remains conditional on the mandatory FRA1 compatibility proof;
- final web/worker/database sizing, which remains benchmark-driven;
- PostgreSQL HA topology for external beta, which remains evidence-driven within the RTO/RPO target.

## 12A. Gate 0 safety re-check — discharged for provisional OPS1-02 only

**Baseline reviewed: `main` @ `892f5c9`.** Re-checked 2026-08-27 against current code and tests, not
against the status text of the originating analysis. `KHEPRI-DEC-030` §6 step 0 carries forward
`KHEPRI-DEC-027` §3 undischarged and requires confirming that no operational defect identified by
the OPS1 analysis would make a provisioned environment **unsafe or non-recoverable**. That is the
standard applied here; completeness is not.

**BLOCKING: none.**

Every defect in `ops1-provider-portability-and-target-selection.md` §22.1 and §2.3 was re-verified
at its current call sites. Old line numbers and old status text were not trusted.

### Resolved on current `main`

| Defect (as originally recorded) | Current evidence |
|---|---|
| DEC-008 obligation 3 — five provider-header proofs, no envelope encryption | `src/khepri/rra/envelope.py` exists; `rra/storage.py` sends no `ServerSideEncryption`, `SSEKMSKeyId`, `BucketKeyEnabled`, or `ExpectedBucketOwner`. Read-back proof is a ciphertext digest |
| DEC-008 obligation 4 — `config.py` pinned to `me-central-1`, account id, KMS ARN | `runtime/config.py:27-28`: "no region allowlist and no account identifier". `endpoint_url` seam at `runtime/wiring.py:131` |
| Schema violation — `CHECK (encryption_algorithm = 'aws:kms')` | `migrations/versions/20260822_0020_portable_object_encryption.py` rewrites both constraints to `AES-256-GCM`. Remaining `aws:kms` strings are the historical `0002`/`0012` revisions and the downgrade path |
| §22.1-1 — boot requires two unread SQS queue URLs | Not required at boot: neither name reaches `RuntimeSettings` or any `_required` call. Retained only for the frozen `infra/` AWS reference |
| §22.1-4 — recovery sweep has no production caller | `runtime/worker.py:100` calls `self._queue.recover(now=now)` before every claim, deliberately not gated on an idle queue. `tests/test_ops1_worker_lease_recovery.py` — 7 tests pass, including one asserting the suite drives the deployed loop rather than calling recovery directly |

### Open but non-blocking for the provisional bootstrap

Each is sequenced *after* provisioning by §13 of this record or by `KHEPRI-DEC-030` §6, and none
makes the authorized environment unsafe or non-recoverable.

| Item | Current state | Why it does not block |
|---|---|---|
| Seven-day content deletion has no scheduled executor | `DeletionService.delete_session_content` is wired at `runtime/wiring.py:184` and callable on demand at `rra/api.py:418`; the only scheduled caller is `local/sweeper.py:201`, and `pyproject.toml:77` excludes `src/khepri/local` from the wheel. The AWS S3 lifecycle backstop is frozen CDK and is not provisioned by an App Platform deploy | The deletion path exists, works, and is reachable; what is missing is a scheduler. §22.1 assigns this "before beta traffic", and §13.6 sequences deletion-after-restore to step 6. Conditioned below |
| RRA-007 orphan detection has no deployed caller | `recover_orphans` is called only from `local/sweeper.py:172`; the worker inlined lease recovery only | Same reasoning: capability present, scheduler absent, no traffic authorized |
| Claim query is not work-conserving | `rra/job_persistence.py:190` uses plain `with_for_update()`; `skip_locked=True` appears only in the two recovery sweeps (`:211`, `:229`) | The analysis records the claim as *safe*, not incorrect. Throughput, not safety |
| Heartbeat is stage-driven, not a 60-second interval | `rra/pipeline.py:318,320,322` heartbeat between stages | Now degrades to reclaim-and-retry rather than a stuck job, because recovery runs on the deployed path. Defect 4's fix demotes this one |
| No OTLP emission path | Zero hits for `otel`/`otlp`/`opentelemetry` in `src/`, `pyproject.toml`, `Dockerfile` | §13.8 and `KHEPRI-DEC-030` §6.7 sequence observability to step 8 |
| No `/health/live` or `/health/ready` endpoints | None present in `src/khepri` | §8 requires them before *traffic shifting*; no traffic is authorized here |
| DigitalOcean Spaces compatibility unproven | Storage contract keeps `IfNoneMatch`, unversioned delete, list-after-delete confirmation, multipart abort; all fail closed via `StoragePolicyViolation` | `KHEPRI-DEC-030` §6.2 assigns empirical Spaces verification to *after* provisioning and keeps Spaces conditional |
| Secrets and TLS | `KHEPRI_STORAGE_MASTER_KEY` (32-byte base64) via env; `sslmode=require` at `runtime/config.py:240` | Matches §5 and D5's "App Platform encrypted env vars are the minimum acceptable" |

### Conditions attached to this discharge

Gate 0 is discharged **only** for the provisional non-production bootstrap at §10 / `KHEPRI-DEC-030`
§4 shape, and only while both hold:

1. **No external, customer, or production content enters the provisional environment.** The
   reasoning above rests on `KHEPRI-DEC-030`'s Consequences — "No external traffic is authorized by
   this decision, and none may be opened on the strength of it." Content subject to a seven-day
   clock does not enter an environment authorized to carry no traffic. If content ever does, the
   missing deletion scheduler becomes blocking immediately.
2. **A scheduled executor for content expiry and orphan recovery exists before beta
   authorization**, per §13.6 and §13.9. This discharge does not satisfy that obligation and must
   not be read as retiring it.

No final capacity, no benchmark certification, no beta authorization, and no external traffic is
implied or granted by this record.

## 13. What remains a stop-gate

These are verification/activation tasks, not reasons to reopen the whole architecture. Their dependency order is:

1. activate the required DEC-008 and DEC-006 restatements **and supersede `KHEPRI-DEC-027`**, in one governance transition, so that a provisional non-production bootstrap is authorized by exactly one unambiguous active authority.

   `KHEPRI-DEC-027` is `state: active`, its §4 withholds authority to provision or commit spend, and its consequences say in terms that "`OPS1-02` remains blocked until the final target-selection/environment descriptor is complete and approved". This sequence deliberately defers that final descriptor to steps 4–5. Restating DEC-008 and DEC-006 alone therefore leaves DEC-027's block standing: either the provisioning is still prohibited, or two active decisions disagree about whether it is. The successor must carry DEC-027's provisioning bar forward for *final* capacity while admitting the provisional bootstrap explicitly, and name the measurement shape in section 10 as what the bootstrap may claim.

2. provision only that provisional non-production environment, using the measurement shape in section 10 rather than claiming final capacity;
3. capture and record the live PostgreSQL minor version, empirically verify DigitalOcean Spaces against the exact Khepri storage/deletion/multipart contract, and refuse later certification if the live minor differs from the recorded value;
4. run the `OPS1-09` benchmark on the provisional hosted target **as an exploratory measurement, not as governed certification**;
5. approve the final environment descriptor and sizing from that measurement, then **re-run the governed `OPS1-09` benchmark against the final descriptor and issue the certification from that run**.

   The provisional run cannot certify the final target. `KHEPRI-DEC-006`'s digest discipline — and this document's own minor-version rule in section 3 — invalidate earlier evidence once the environment descriptor changes. A benchmark measured against the provisional shape is therefore not valid evidence for the descriptor that supersedes it, so certifying from it would leave every downstream exercise resting on evidence its own governance had already invalidated;
6. run `OPS1-04` recovery exercises, including backup/restore, deletion-after-restore, encryption read-back, worker crash/retry/redrive, and proof of the selected RTO/RPO;
7. run `OPS1-05` capacity and soak evidence;
8. complete `OPS1-06` content-free observability, alerts, dashboards, and runbooks, including the admitted liveness/readiness probes and governed OpenTelemetry/OTLP emission path;
9. complete release, rollback, database-migration, and incident procedures, then pursue the separate later private-beta authorization artifact.

## 14. Merge interpretation

Merging this planning file records that these are the owner's selected OPS1 implementation directions and gives later OPS1 planning a single precedence point instead of three contradictory target drafts.

It does **not** make a contradictory runtime rule governing by prose. `governance/registry.yaml` remains authoritative, and nothing here authorizes provisioning: `KHEPRI-DEC-027` still blocks `OPS1-02`, and a planning file cannot lift a bar an active decision holds.

The next governance PR must translate the applicable rulings into the DEC-008/DEC-006 successor decisions, **a `KHEPRI-DEC-027` successor**, and the final environment descriptor, atomically enough that the validator sees one unambiguous active authority. Splitting DEC-027's supersession into a later PR would leave a window in which the restatements read as permission the still-active DEC-027 withholds.
