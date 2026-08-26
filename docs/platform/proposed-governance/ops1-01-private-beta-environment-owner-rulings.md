# OPS1-01 — Private-beta environment owner rulings

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
| Migration execution | App Platform pre-deploy / one-shot job | Must complete before web and worker start. |
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
  -> run gated migration job
  -> deploy web + worker
  -> readiness check
  -> content-free smoke verification
```

Automatic deployment merely because `main` changed is not selected. Deployment remains an explicit CI action with the exact image digest recorded and may execute only after the applicable governance and deployment authority are active.

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

## 10. Benchmark starting shape, not final sizing

No final web, worker, or database sizing is selected by this planning record. Final sizing belongs to `OPS1-09` and the governed benchmark evidence.

For the first hosted measurement only, use a **benchmark starting shape** that is at least as conservative as the production-like local stack already exercised:

| Role | First hosted measurement shape |
|---|---|
| Web | 1 shared vCPU, 1 GiB RAM |
| Worker | 2 vCPU, 4 GiB RAM |
| PostgreSQL | a Managed PostgreSQL 17 shape capable of running the governed workload with PITR/private networking enabled; exact tier selected by OPS1-09 setup |
| Worker replicas | 1 |

The worker starts materially above the web role because report rendering launches pinned Chromium alongside the analytical workload. These values exist only to start measurement; they are neither a capacity claim nor a beta commitment. `OPS1-09` may move them up or down from evidence, and `OPS1-05` must run capacity/soak evidence before external private-beta traffic.

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
- App Platform one-shot/pre-deploy migrations;
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

## 13. What remains a stop-gate

These are verification/activation tasks, not reasons to reopen the whole architecture:

1. activate the required DEC-008 supersession/restatement, revising **both** the managed-PostgreSQL minor-upgrade row and the unconditional stable-egress row;
2. activate the DEC-006 benchmark-environment restatement required by the FRA1 target;
3. empirically verify DigitalOcean Spaces against the exact Khepri storage/deletion/multipart contract before final product selection;
4. add the runtime live PostgreSQL minor-version certification check;
5. add admitted liveness/readiness probes;
6. implement and verify the governed content-free OpenTelemetry/OTLP emission path;
7. run `OPS1-09` and reissue sizing against FRA1;
8. provision non-production only after the governing descriptor is active;
9. run backup/restore, deletion-after-restore, encryption read-back, worker crash/retry/redrive, and recovery drills;
10. demonstrate the selected RTO/RPO and capacity requirements;
11. create alerts, dashboards, runbooks, release/rollback procedures, and the eventual private-beta authorization artifact.

## 14. Merge interpretation

Merging this planning file records that these are the owner's selected OPS1 implementation directions and gives later OPS1 planning a single precedence point instead of three contradictory target drafts.

It does **not** make a contradictory runtime rule governing by prose. `governance/registry.yaml` remains authoritative. The next governance PR must translate the applicable rulings into the DEC-008/DEC-006 successor decisions and final environment descriptor atomically enough that the validator sees one unambiguous active authority.
