# OPS1-01 — Private-beta environment owner rulings

**Status: planning-only proposal record.** This file records the owner's selected implementation direction for the remaining OPS1-01 environment choices. It does **not** amend `governance/registry.yaml`, supersede an active decision, authorize provisioning or spend, or open external traffic. Any ruling that conflicts with an active governed artifact must be activated through the repository's normal governance transition before implementation relies on it.

Prepared against `main` at `ceace057ce1e180fa6fddc851208aa0fd9d1808d`.

## 1. Selected private-beta target

The private-beta environment is to be designed around the following concrete target:

| Capability | Selected direction | Notes |
|---|---|---|
| Provider | DigitalOcean | Carries forward active `KHEPRI-DEC-027`. |
| Region | FRA1 (Frankfurt) | Carries forward active `KHEPRI-DEC-027`. |
| Web compute | DigitalOcean App Platform web service | No Droplet in the initial private-beta target. |
| Worker compute | DigitalOcean App Platform worker | Separate role from web; same pinned Khepri image. |
| Migration execution | App Platform pre-deploy / one-shot job | Must complete before web and worker start. |
| Relational store | DigitalOcean Managed PostgreSQL 17 | TLS required; PITR required; exact live minor version must be evidence-bound. |
| Object storage | DigitalOcean Spaces, private, FRA1 | S3-compatible; application-side envelope encryption remains authoritative. |
| Image registry | DigitalOcean Container Registry | Deploy immutable image digests; never deploy a floating `latest` tag. |
| Runtime secrets | App Platform encrypted runtime secrets | Includes the envelope master key, database/object-store credentials, and Clerk secrets where applicable. |
| Deployment credential | GitHub Actions secret | Deployment credential does not enter the application container. |
| Network | DigitalOcean VPC with private managed-database connectivity | No dedicated static egress IP in the initial private beta unless a dependency proves it necessary. |
| CI/CD | GitHub Actions is the normal deployment path | Console/manual deployment is not the normal release mechanism. |
| Infrastructure definition | Terraform for long-lived infrastructure plus an App Platform specification for app roles | Exact file layout is implementation work; this ruling selects the split of responsibility. |
| Observability | DigitalOcean native service health/metrics plus Better Stack for centralized logs and OTLP-compatible telemetry | Customer content must not be emitted into telemetry. |
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

No initial Droplet is selected. This deliberately avoids adding host patching, SSH administration, Docker-daemon administration, and self-managed load balancing to the beta's operational surface.

## 3. Managed PostgreSQL and minor-version changes

**Selected:** DigitalOcean Managed PostgreSQL 17.

Self-hosted PostgreSQL on a Droplet is rejected for the initial private beta because it would move patching, TLS, backup scheduling, PITR machinery, restore verification, and host hardening into Khepri's own operational burden before those capabilities have independent evidence.

The selected provider may apply PostgreSQL minor upgrades. The owner accepts that operational fact subject to the following control:

1. the environment descriptor records the exact live PostgreSQL minor version;
2. that minor version contributes to `environment_digest`;
3. the runtime/benchmark certification path must compare the live server minor version with the recorded value;
4. a mismatch refuses certification rather than silently accepting the old digest;
5. a minor-version change requires descriptor/digest re-issuance and the re-evidence required by the governing benchmark decision.

This is a **governance-impacting ruling** because active `KHEPRI-DEC-008` still says automatic minor upgrades are disabled. Implementation must not treat this paragraph as authority until the DEC-008 supersession/restatement is activated in `governance/registry.yaml`.

## 4. Object storage

**Selected direction:** DigitalOcean Spaces in FRA1, private and non-versioned.

The application remains responsible for encrypting customer objects before bytes leave the process. Provider-side encryption, when present, is additional and not evidence that replaces Khepri's envelope encryption.

The beta storage policy is:

- private bucket;
- object versioning disabled;
- immediate application deletion when the governed lifecycle requires deletion;
- seven-day automatic expiry as the backstop required by `RRA-002`;
- incomplete multipart uploads cleaned up within one day where the selected service can enforce that rule;
- per-environment credentials scoped as narrowly as the provider allows.

**Verification gate:** the selection is not operationally complete until the exact Spaces API behavior used by `khepri.rra.storage` is exercised against a real FRA1 bucket, including conditional write behavior, read-after-write, deletion, list/abort multipart behavior, and lifecycle semantics. Any incompatibility fails closed and reopens the storage implementation choice; it does not justify a provider-specific branch inside application code.

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

## 6. Networking

The initial target uses a DigitalOcean VPC and private connectivity to Managed PostgreSQL. Public database connectivity is not the normal application path.

A dedicated static egress IP is **not selected** for the initial private beta. It becomes a new decision only if an actual external dependency requires source-IP allowlisting. The environment should not buy or architect around an allowlisting requirement that does not yet exist.

Public ingress terminates TLS outside the Khepri application process. The worker has no public ingress.

## 7. CI/CD and infrastructure definition

GitHub Actions is the normal authority-bearing execution path for build and deployment operations.

Target release flow:

```text
pull request
  -> required CI
  -> merge to main
  -> build pinned image
  -> test / security checks
  -> push immutable image to DOCR
  -> validate infrastructure/app specification
  -> run gated migration job
  -> deploy web + worker
  -> readiness check
  -> content-free smoke verification
```

Automatic deployment merely because `main` changed is not selected. Deployment remains an explicit CI action with the exact image digest recorded.

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

## 10. Initial sizing baseline

The following is an **initial hosted-staging baseline only**, chosen to give `OPS1-09` and `OPS1-05` something concrete to measure. These are not final beta capacity claims:

| Role | Initial baseline |
|---|---|
| Web | 1 shared vCPU, 1 GiB RAM |
| Worker | 1 shared vCPU, 2 GiB RAM |
| PostgreSQL | smallest managed PostgreSQL 17 shape that satisfies the provider's selected PITR/private-network requirements and the governed benchmark run |
| Worker replicas | 1 |

The worker starts with more memory than the web role because report rendering launches pinned Chromium. `OPS1-09` must reissue the governed sizing record against the selected FRA1 target, and `OPS1-05` must run capacity/soak evidence before external private-beta traffic. Any measured failure overrides this baseline.

High availability for PostgreSQL is an explicit **beta-authorization checkpoint**, not assumed by this staging baseline: the owner should enable the provider's HA/standby shape before external private-beta traffic unless recovery evidence demonstrates a simpler topology still meets the approved RTO/RPO and governing durability requirements.

## 11. Observability

The selected direction is:

- DigitalOcean native health/service metrics for provider/runtime state;
- Better Stack for centralized application logs and OTLP-compatible traces/metrics;
- alerts and dashboards built only from content-free operational signals.

No raw uploaded rows, customer report prose, decrypted object payloads, secret values, or unapproved customer-derived labels may enter telemetry.

A different observability vendor may later replace Better Stack without changing the application/domain architecture provided the content-free telemetry contract and OTLP boundary remain intact.

## 12. What is now closed for planning

For OPS1 planning, the following choices are no longer open alternatives:

- DigitalOcean / FRA1;
- App Platform for both web and worker;
- App Platform one-shot/pre-deploy migrations;
- Managed PostgreSQL 17 rather than self-hosted PostgreSQL;
- Spaces rather than an AWS S3/KMS-specific storage path;
- DOCR rather than a floating external image source for the target deployment;
- App Platform runtime secrets for the initial beta;
- VPC/private database networking;
- GitHub Actions deployment path;
- Terraform + App Platform spec split;
- no Kubernetes/broker/cache tier;
- initial RTO 2 hours and RPO 15 minutes;
- initial web/worker sizing baseline above;
- DigitalOcean native monitoring plus Better Stack telemetry direction.

## 13. What remains a stop-gate

These are verification/activation tasks, not architecture-choice questions:

1. activate the required DEC-008 supersession/restatement so managed PostgreSQL minor upgrades are governed rather than merely proposed;
2. activate the DEC-006 benchmark-environment restatement required by the FRA1 target;
3. empirically verify DigitalOcean Spaces against the exact Khepri storage/deletion/multipart contract;
4. add the runtime live PostgreSQL minor-version certification check;
5. add admitted liveness/readiness probes;
6. run `OPS1-09` and reissue sizing against FRA1;
7. provision non-production only after the governing descriptor is active;
8. run backup/restore, deletion-after-restore, encryption read-back, worker crash/retry/redrive, and recovery drills;
9. demonstrate the selected RTO/RPO and capacity requirements;
10. create alerts, dashboards, runbooks, release/rollback procedures, and the eventual private-beta authorization artifact.

## 14. Merge interpretation

Merging this planning file records that these are the owner's selected OPS1 implementation directions and prevents later planning work from re-opening the same alternatives without new evidence.

It does **not** make a contradictory runtime rule governing by prose. `governance/registry.yaml` remains authoritative. The next governance PR must translate the applicable rulings into the DEC-008/DEC-006 successor decisions and final environment descriptor atomically enough that the validator sees one unambiguous active authority.
