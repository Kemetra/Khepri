# OPS1-01 — DigitalOcean FRA1 environment descriptor proposal

**Status: planning-only draft. Nothing here is a governed artifact.** It approves nothing,
records no approval, creates no authority, allocates no identifier, and authorizes no
provisioning, deployment, spend, or external traffic. It does not resolve any stop-gate
`KHEPRI-DEC-027` reserves; it prepares the material an owner-approved artifact would need
and marks every unresolved choice **OWNER DECISION REQUIRED**.

This document deliberately allocates **no decision identifier**. The final
target-selection/environment descriptor requires one, and only the repository owner
allocates it. `AGENTS.md` fails closed on ambiguous identity, and the master roadmap warns
that renumbering silently retargets every citation, including the blocking clause of an
active decision.

## Base commit and citation check

Prepared against `1e774db` (`main`, `origin/main`), working tree clean.

Every governance artifact cited below was checked against `governance/registry.yaml` at
that commit:

| Artifact | Registry state | Used here as |
|---|---|---|
| `KHEPRI-DEC-006` | `active` | governing — benchmark workload |
| `KHEPRI-DEC-008` | `active` | governing — portable runtime capability contract |
| `KHEPRI-DEC-025` | `active` | governing — Clerk private-beta implementation |
| `KHEPRI-DEC-027` | `active` | governing — FRA1 target direction and stop-gates |
| `RRA-002` | `active` | governing — deletion semantics |
| `KHEPRI-DEC-007` | `retired`, `superseded_by: KHEPRI-DEC-008` | **historical only** |

`KHEPRI-DEC-007` is cited in this document only to explain the provenance of existing
sizing material. It is not treated as a live requirement anywhere.

## 1. What `KHEPRI-DEC-027` leaves open

`KHEPRI-DEC-027` is `active`. It selects **DigitalOcean, region FRA1 (Frankfurt)** as the
target direction and records that the current non-paying private-beta stage has no
Middle East residency requirement. Its own header and §4 state that it "does not authorize
provisioning, deployment, beta launch, or spend."

§3 reserves these as stop-gates before provisioning, and this proposal resolves none of
them:

1. concrete DigitalOcean product selections and exact versions where applicable;
2. acceptance and mitigation of provider-managed PostgreSQL minor upgrades;
3. the envelope-master-key secret source;
4. the egress/VPC posture and whether any dependency requires IP allowlisting;
5. owner-approved RTO and RPO targets;
6. worker/web/database sizing derived from the governed benchmark rules;
7. any remaining OPS1 operational defect that would make a provisioned environment unsafe
   or non-recoverable.

`KHEPRI-DEC-008` additionally fixes the required *content* of the target-selection
artifact: provider and region; the residency justification and whether any client
commitment constrains it; the concrete product satisfying each capability with exact
versions; confirmation that the object store's expiry, deletion, and multipart-abort
semantics satisfy `RRA-002`; the recorded RTO and RPO; and the sizing values its rules
require.

## 2. Architectural direction this proposal preserves

Unchanged from the merged shape, and no active governed artifact requires otherwise:

- one Khepri deployable image (`Dockerfile`);
- separate web and worker process roles;
- PostgreSQL as canonical durable operational state;
- object storage provider-portable and application-encrypted;
- no Kubernetes, no Kafka, no Redis, no RabbitMQ, no message broker, no new
  microservices, no separate frontend runtime.

`KHEPRI-DEC-008` replaced the broker with a PostgreSQL claim query
(`src/khepri/rra/claim_queue.py`) and moved encryption into the application, and bakes
Chromium into the image so its pin is transitive.

## 3. Proposed topology

```
                        Internet
                           │
                  DNS  +  TLS termination        ◀── OWNER DECISION REQUIRED (D4)
                           │
                    ┌──────┴──────┐
                    │ Khepri Web  │  uvicorn khepri.runtime.web:app
                    └──┬───────┬──┘  ⚠ no readiness probe today (§5, P1)
                       │       │
        ┌──────────────┘       └──────────────┐
        │                                     │
┌───────▼──────────┐               ┌──────────▼─────────┐
│ PostgreSQL 17    │               │ S3-compatible      │
│ sslmode=require  │               │ object storage     │
│ (forced, no      │               │ app-encrypted      │
│  override)       │               │ AES-GCM envelope   │
│ managed vs self  │               │ product = D2       │
│ = D1  (§6)       │               └──────────▲─────────┘
└───────▲──────────┘                          │
        │                                     │
        └──────────────┬──────────────────────┘
                       │
              ┌────────┴─────────┐
              │  Khepri Worker   │  python -m khepri.runtime.worker
              │  concurrency = 1 │  scale by replicas only
              └────────┬─────────┘
                       │
                 ┌─────┴──────┐
                 │ CAL1 engine│  separate lane, out of scope here
                 └────────────┘

Operational layer:  secrets (D6) · logs + OTLP (D8) · alerts · backups (D9)
                    restore drills · CI/CD + registry (D5) · runbooks
```

Migration execution is a one-shot role, not a service: `alembic upgrade head` must
complete before web or worker start. The merged local staging stack already expresses
exactly this ordering, with `web` and `worker` gated on the migration container's
successful completion.

## 4. Concrete DigitalOcean product candidates

Candidates only. Product selection is stop-gate 1 and is **not** settled here; no size,
tier, or instance count below is proposed as a value.

| Capability | Candidate | Alternative | Notes |
|---|---|---|---|
| Web compute | App Platform service | Droplet behind a Load Balancer | App Platform supplies TLS and rolling deploys but assumes an HTTP readiness probe (P1) |
| Worker compute | Droplet, or App Platform worker component | — | Memory-led: Chromium renders the report surfaces. No public ingress |
| Migration execution | pre-deploy job / one-shot container | manual gated step | Must block the release, not run beside it |
| PostgreSQL | DO Managed Database for PostgreSQL 17 | self-hosted PostgreSQL 17 on a Droplet | **The conflict in §6 decides this** |
| Object storage | DO Spaces (S3-compatible) | — | Must be verified against `RRA-002` before selection |
| Image registry | DO Container Registry (DOCR) | GHCR | CI is ECR-shaped today (§10) |
| Secret source | — | — | Stop-gate 3; no candidate proposed (§8) |

**OWNER DECISION REQUIRED (D3) — sizing.** No CPU, memory, storage, node count, or
database tier is proposed. The available sizing material is AWS-shaped and must be
reissued by `OPS1-09` (§11).

## 5. Web / worker / migration topology

**Separate web and worker compute from the start — recommendation, not a governed fact.**
The two scale on different axes: the worker's in-task concurrency is exactly 1
(`ClaimWorkerLoop` claims and settles one job at a time, so a second process in one
container is a second claimant racing the same rows) and is therefore scaled by replica
count, while the web role is not scaled that way. The worker is memory-led because
Chromium renders the report surfaces; the web role is not. Co-locating them couples two
unrelated scaling decisions.

The resource limits in the merged local staging compose file are explicitly local comfort
values, not sizing evidence, and are not carried into this proposal as numbers.

**Scaling trigger: none proposed.** A trigger requires the capacity and soak evidence
`OPS1-05` produces. Proposing a threshold now would invent the evidence.

### P1 — implementation prerequisite: no application readiness probe

The runtime exposes no health or readiness endpoint. The route surface in
`src/khepri/runtime/` is `/`, `/app`, `/api/v1/beta`, `/api/v1/commercial`,
`/{organization_id}/team`, the invitation-revoke path, and `/-/unavailable` — which is a
refusal surface, not a probe. `src/khepri/runtime/web.py` is an ASGI entry point that
delegates to `build_web_app`. In the merged local staging stack only PostgreSQL
(`pg_isready`) and MinIO (its own `/minio/health/live`) declare healthchecks; neither the
web nor the worker service does.

**This is recorded as an implementation prerequisite for hosted deployment, not as a
blocker to completing this architecture proposal.** It must exist before a load balancer,
App Platform health gate, rolling deploy, or post-deploy CI verification can be relied on.
Adding it is product-code work outside this docs-only slice, and it does not belong to
`OPS1-01`.

## 6. PostgreSQL — the governed conflict, not resolved here

**OWNER DECISION REQUIRED (D1).** This is the substantive decision in this proposal.

Two active artifacts pull in opposite directions:

- **`KHEPRI-DEC-008`** (`active`) states the relational-store capability as *PostgreSQL 17,
  TLS required, point-in-time recovery, **automatic minor upgrade disabled***, and requires
  the descriptor to record the product, the exact minor version, sizing, RTO and RPO. It
  warns that an engine change underneath an approved `environment_digest` "would silently
  invalidate every prior run's evidence while the digest still matched."
- **`KHEPRI-DEC-027` §3** (`active`) reserves *"acceptance and mitigation of
  provider-managed PostgreSQL minor upgrades"* as an unresolved stop-gate.

A provider-managed PostgreSQL product applies minor version upgrades on the provider's
maintenance schedule. That operational behaviour is in tension with a capability contract
requiring automatic minor upgrades to be disabled, and `KHEPRI-DEC-027` names the tension
rather than settling it. `src/khepri/infra/database.py` records the same discipline from
the other side: the minor version is a fact the environment descriptor records, not one
code invents.

**This proposal does not resolve the conflict.** The alternatives, with their trade-offs:

| Option | What it accepts | What it costs |
|---|---|---|
| **A. Managed PostgreSQL, upgrades accepted with a stated mitigation** | Provider performs minor upgrades in a maintenance window | Requires an explicit owner ruling on how DEC-008's "automatic minor upgrade disabled" is satisfied or amended, plus a defined re-evidencing path when the minor version moves under an approved `environment_digest` |
| **B. Self-hosted PostgreSQL 17 on a Droplet** | Full control of the minor version, satisfying DEC-008 literally | Khepri owns patching, TLS material, backup scheduling, PITR machinery, and restore verification — all currently unimplemented (§9) |
| **C. Managed, with a DEC-008 amendment sought first** | Keeps governance and operations aligned before provisioning | Adds a governance step ahead of `OPS1-02` |

Fixed regardless of the outcome: `khepri.runtime.config` builds every database URL with
`sslmode=require` and offers **no override**, so a non-TLS PostgreSQL is not connectable by
the runtime image at all. Credentials arrive as one Secrets-Manager-shaped JSON document
parsed by `_database_secret`; the runtime never joins the password into a URL string.

**Migration execution boundary.** Migrations run from the deployable image as a gated
pre-deploy step, never from a developer machine against the hosted database, and never
concurrently with a running web or worker role. `migrations/env.py` prefers
`KHEPRI_DATABASE_URL` over the URL pinned in `alembic.ini`, which points at the local
stack.

## 7. Object storage

DO Spaces is the leading candidate as the S3-compatible store. Selection is stop-gate 1
and additionally conditional on `RRA-002`.

Fixed by the application and not renegotiable per target:

- **No provider branch.** `src/khepri/rra/storage.py` contains no provider conditional and
  must never acquire one; a target differs only in endpoint and credentials.
- **Application-side envelope encryption.** `KHEPRI-DEC-008` moved encryption into the
  application (`khepri.rra.envelope`, AES-GCM), so bytes are ciphertext before they leave
  the process and no provider KMS is required.
- **Unversioned, and deletion must actually delete.** `RRA-002` (`active`) requires deletion
  to delete rather than leave a recoverable prior version; the store rejects any write
  response carrying a `VersionId`. **Object recovery is therefore restore-based, not
  version-rollback** — a real constraint on any recovery story (§9).

**Required before selection (per `KHEPRI-DEC-008`):** written confirmation that the chosen
store's **expiry, deletion, and multipart-abort** semantics satisfy `RRA-002`.

**OWNER DECISION REQUIRED (D2)** — product selection, once that confirmation exists.
**OWNER DECISION REQUIRED (D10)** — object lifecycle and retention beyond the seven-day
expiry the product already requires, and the credential scope for the bucket (a
per-environment key limited to one bucket is recommended; not yet authorized).

## 8. Secrets

**OWNER DECISION REQUIRED (D6) — the envelope-master-key secret source.** This is
stop-gate 3, named explicitly by `KHEPRI-DEC-027` §3. No candidate is proposed here.

Present state, for contrast: the merged local staging stack sets
`KHEPRI_STORAGE_MASTER_KEY` to 32 zero bytes, base64 — deliberately fixed, deliberately
not a secret, because a generated key would make objects written by one container
unreadable by the next. The compose file itself records that the real secret source is a
`KHEPRI-DEC-027` stop-gate.

Secrets a hosted environment must source, each needing an owner-approved home and a named
rotation owner: database credentials (as the JSON document `_database_secret` parses),
object-storage access key and secret, the envelope master key, Clerk credentials where
`KHEPRI-DEC-025` applies, and the CI deployment credential. `_clerk_settings` reads its
variables through `_optional`, so their absence is valid and a stack runs on invitation
sessions; supplying them **empty** fails `_required`.

## 9. Backup, PITR, recovery — capability absent today

No executable backup or restore capability exists in the repository. There is no
`pg_dump`/`pg_restore`/PITR procedure, no deploy or restore script, and no drill. The only
backup references are declarations inside the AWS CDK tree (`src/khepri/infra/`), which
describe a provider `KHEPRI-DEC-027` demoted to a fallback candidate.

**OWNER DECISION REQUIRED (D7) — RTO and RPO.** Stop-gate 5. No values are proposed:
proposing them would manufacture the approval the gate exists to require. Inputs the owner
would be deciding against — non-paying private-beta stage with no current client
commitment; FRA1 with no residency constraint at this stage; an unversioned object store,
so recovery is restore-based; and a report pipeline whose objective is already ten minutes
per `KHEPRI-DEC-006`.

**OWNER DECISION REQUIRED (D9) — backup retention and PITR window.** Contingent on D1: a
managed product supplies both as configuration, a self-hosted one requires Khepri to build
them.

Recovery exercises `OPS1-04` must perform before external traffic, all currently
unevidenced: database restore to a known point; object read-back through the encryption
boundary; **deletion-after-restore verification** — proving deleted content does not
reappear after a restore, which `RRA-002` makes mandatory; worker crash, retry, and
dead-letter recovery, where `max_attempts` bounds retries in the claim queue; and orphan
recovery.

## 10. Networking, ingress, egress, registry, telemetry

**TLS ingress — OWNER DECISION REQUIRED (D4).** Product and DNS unselected. Termination at
the edge; the application's own database TLS requirement is unaffected and non-optional.

**Egress identity / VPC posture — stop-gate 4, unresolved.** `KHEPRI-DEC-027` §3 reserves
both the egress posture and whether any dependency requires IP allowlisting. Clerk is the
concrete candidate under `KHEPRI-DEC-025`; the narrative model provider is a second.
A stable egress identity may be required for allowlisting, which constrains the compute
product chosen in §4 — so D4 and this posture are coupled and should be decided together.

Recommended, pending approval: database and object storage reachable only over the private
network with no public listener; default-deny inbound except the ingress port; no
application or domain code branching on provider or geography, which
`KHEPRI-DEC-008` requires to remain an infrastructure concern.

**Image registry — OWNER DECISION REQUIRED (D5).** DOCR is the candidate. Current CI
(`.github/workflows/image.yml`) builds without pushing and its publish job reports "NOT
PUBLISHED" and succeeds when no registry is configured; its publish path is written for AWS
ECR. Selecting a registry requires CI work in a later slice — **not** in `OPS1-01`, and not
in this docs-only change.

**OTLP and log destination — OWNER DECISION REQUIRED (D8).** `KHEPRI-DEC-008` requires
OpenTelemetry traces and metrics to an OTLP endpoint the descriptor records, and
content-free operational telemetry. **No OTLP or OpenTelemetry implementation exists in the
repository, and no structured-logging configuration exists in `src/khepri/runtime/`.** This
is a governed requirement with no implementation, not merely an unselected destination: the
descriptor must name the endpoint, and separate implementation work must emit to it.
Telemetry must remain content-free — identifiers, timestamps, digests, and outcomes, never
customer content.

## 11. Sizing evidence and gaps

`governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` is **historical, DEC-007-derived
sizing**. Its own header records that every value is fixed by
`KHEPRI-DEC-007-rra-infrastructure-sizing.md`, and the registry records that decision as
`retired`, `superseded_by: KHEPRI-DEC-008`. The file retains a real role: it is the current
sizing contract referenced by `src/khepri/infra/sizing_source.py` and the identity check in
`src/khepri/rra/performance.py`, and `OPS1-09` must **reissue it against the selected
DigitalOcean target** — not delete it, and not edit it in this slice.

| Field | Value | Disposition for `OPS1-09` |
|---|---|---|
| `web_cpu_units` | 1024 | AWS-shaped (Fargate CPU units) — remeasure |
| `web_memory_mib` | 4096 | remeasure against the selected product |
| `web_ephemeral_storage_gib` | 20 | AWS-shaped — remeasure |
| `worker_cpu_units` | 4096 | AWS-shaped — remeasure |
| `worker_memory_mib` | 16384 | remeasure (Chromium-led) |
| `worker_ephemeral_storage_gib` | 40 | AWS-shaped — remeasure |
| `database_instance_class` | `db.m7g.large` | AWS-shaped (RDS class) — replace with the selected product |
| `allocated_storage_gib` | 100 | portable shape; confirm against target |
| `backup_retention_days` | 7 | portable shape; **owner decision D9** |
| `visibility_timeout_seconds` | 300 | **retired broker key — leaves the file** |
| `message_retention_seconds` | 1209600 | **retired broker key — leaves the file** |
| `receive_wait_seconds` | 20 | **retired broker key — leaves the file** |
| `max_receive_count` | 3 | **retired broker key — leaves the file** |
| `max_attempts` | 3 | **KEEP** — consumed by live product code, `src/khepri/rra/claim_queue.py`, which bounds retries before dead-lettering |

The four broker keys are consumed only by the AWS SQS construct in
`src/khepri/infra/data_resources.py`; `max_attempts` is consumed by the PostgreSQL claim
queue that replaced the broker. That is why the roadmap names four departing keys, not
five.

**What `OPS1-09` must remeasure:** web and worker CPU and memory on the selected products;
database product, tier, and storage; and a re-derivation against `KHEPRI-DEC-006`'s
workload — 40 synthetic datasets, the integer-exact 95% threshold, and the ten-minute
objective, which `KHEPRI-DEC-008` confirms is provider-neutral and unaffected by the
provider change.

**No throughput or concurrency number is invented here.** None exists for a DigitalOcean
target.

Also noted, and deliberately not treated as decisive: `KHEPRI-BMK-001` has no entry in
`governance/registry.yaml`, whose 44 artifacts are `decision`, `family`, and
`specification` only. That is context for how its authority should be described — it does
not by itself mean the file has no role, and this proposal does not treat it that way.

## 12. Delivery flow, proposed

```
PR      ── governance validate · ruff · pytest · image build (no push)   exists today
main    ── build image ──▶ push to selected registry                     needs D5 + CI work
        ── record digest facts (scripts/build_image.py)                   exists today
        ── pre-deploy: alembic upgrade head (gated, must complete)        pattern exists
        ── deploy web + worker                                            no deploy path today
        ── health gate                                                    needs P1
        ── smoke test                                                      none for hosted
        ── rollback                                                        undefined
```

`scripts/build_image.py` already reads the descriptor facts out of the built image rather
than accepting them as arguments, and distinguishes the pushed repo digest from a local
image ID — the descriptor requires the **pushed** digest, so a registry must exist before
the descriptor can be completed with a real value.

**Production promotion is out of scope for this proposal and for `OPS1-02`.** External
traffic is gated by `OPS1-10`, and a go/no-go record is not sufficient: `KHEPRI-DEC-008`
requires an owner-merged beta-authorization artifact defining the client count and the
observation period.

## 13. Dependencies

```
OPS1-08  merged production-like local stack
   │
   ▼
OPS1-01  this proposal ──▶ owner-approved descriptor ──┐
   │                                                   │
   ▼                                                   ▼
OPS1-09  reissue BMK-001 against the selected target  (both required)
   │                                                   │
   └──────────────────────┬────────────────────────────┘
                          ▼
              OWNER APPROVAL — new decision ID, owner-allocated
                          ▼
OPS1-02  CI-only non-production provisioning   ◀── KHEPRI-DEC-027 blocks this by name
                          ▼
OPS1-03  managed PostgreSQL · private object storage · secrets · TLS ingress
         · image registry · operational telemetry
                          │
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                  ▼
   OPS1-04           OPS1-05            OPS1-06
   recovery          capacity + soak    alerts · dashboards
   evidence          (also needs CAL1)  · runbooks
        │
        ▼
   OPS1-07  release · rollback · migration · incident procedures
        │
        ▼
   OPS1-10  beta-authorization artifact + go/no-go record
```

`OPS1-02` depends on **both** `OPS1-01` and `OPS1-09`; the descriptor and the reissued
sizing contract are both preconditions for provisioning. `OPS1-04`, `OPS1-05`, and
`OPS1-06` fan out from `OPS1-03`; only `OPS1-07` waits on `OPS1-04`.

This document does not create, satisfy, or close `OPS1-09` or `OPS1-02`.

## 14. Owner decisions, consolidated

Every item is **OWNER DECISION REQUIRED**. None is decided in this document.

| ID | Decision | Recommendation | Classification |
|---|---|---|---|
| D1 | Managed vs self-hosted PostgreSQL, and how DEC-008's "automatic minor upgrade disabled" is satisfied | none — §6 presents three options | governed conflict; owner must rule |
| D2 | Object-storage product | Spaces, after `RRA-002` semantics are confirmed | recommendation requiring approval |
| D3 | Web / worker / database sizing | none | blocked on `OPS1-09` evidence |
| D4 | TLS ingress product and DNS | none | recommendation requiring approval; coupled to D11 |
| D5 | Image registry | DOCR | recommendation requiring approval; needs later CI work |
| D6 | Envelope-master-key secret source | none | stop-gate 3, explicitly reserved |
| D7 | RTO and RPO | none | stop-gate 5; owner-approved values required |
| D8 | OTLP endpoint and log destination | none | governed requirement, no implementation exists |
| D9 | Backup retention and PITR window | none | contingent on D1 |
| D10 | Object lifecycle, retention beyond the required expiry, and credential scope | per-environment key scoped to one bucket | recommendation requiring approval |
| D11 | Egress identity / VPC posture and IP allowlisting | none | stop-gate 4, explicitly reserved |
| D12 | Decision identifier for the descriptor artifact | none | owner allocates; not chosen here |

## 15. Risks

1. **The PostgreSQL conflict (D1) is structural, not administrative.** Selecting a managed
   product without an owner ruling would silently contradict an active capability contract.
2. **Telemetry is a governed requirement with zero implementation** (D8). `OPS1-03` and
   `OPS1-06` both depend on it, and it is product-code work no OPS1 docs slice supplies.
3. **No readiness probe (P1).** Blocks health-gated deploys and post-deploy verification.
4. **CI publishes nothing and is ECR-shaped.** A green pipeline is not evidence of a
   distributable image, and the descriptor needs a pushed digest.
5. **Recovery is entirely unexercised**, and the unversioned store means recovery cannot
   fall back on version rollback.
6. **Stale AWS surface invites wrong-target work.** `cdk.json` and `src/khepri/infra/`
   describe ECS/Fargate/RDS/SQS/ECR against a provider now a fallback candidate; several
   comments cite `KHEPRI-DEC-007`, and a few still call it "proposed." A reader may
   implement against the wrong target.

## 16. What this document is not

It is not the target-selection artifact. It selects no product, approves no sizing, records
no RTO or RPO, names no secret source, allocates no identifier, and clears no stop-gate. It
authorizes no provisioning, deployment, spend, or external traffic. It changes no product
code, no CI, no migration, and no governed artifact — including
`governance/registry.yaml` and `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml`.
