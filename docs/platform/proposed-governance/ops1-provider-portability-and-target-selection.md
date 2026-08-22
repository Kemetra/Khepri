# OPS1 PROVIDER PORTABILITY AND TARGET SELECTION

**Status: DRAFT — NOT A GOVERNED ARTIFACT.** No file under `governance/` was created or modified
by this analysis. No registry entry exists. No identifier is allocated. No approval state changed.
Nothing here is owner approval, and nothing here authorizes provisioning, deployment, or spend.

Per `governance/CONSTITUTION.md` II and the Lifecycle section, a change becomes governing only when
the sole owner merges it to `main`; drafts and proposals live on branches and pull requests, not in
the authoritative lifecycle. This document is uncommitted working material.

- Prepared: 2026-08-22
- Analysed against: `main` @ `1e3b63c` (verified equal to freshly-fetched `origin/main`)
- Governing authority: `KHEPRI-DEC-008` (`state: active`, superseded by nothing)
- Satisfies: roadmap task `OPS1-01`
- All provider pricing and product facts date-stamped **2026-08-22**

---

## 1. Executive Summary

1. `KHEPRI-DEC-008` is active, unsuperseded, and *requires* this artifact before any deployment
   definition may be written. This draft supplies it and supersedes nothing.
2. The domain layer is genuinely provider-agnostic: `src/khepri/rca/` has zero provider references,
   and analysis, evidence, report, and authorization code name no cloud product.
3. **But Khepri cannot deploy to DigitalOcean or Hetzner today** — not for provider reasons, but
   because four of DEC-008's five open follow-on obligations were never implemented. `main` still
   hard-pins AWS `me-central-1` in application code and in a database CHECK constraint.
4. The `'aws:kms'` CHECK constraint is a genuine architecture violation: a cloud product name is
   durable in the schema. Changing provider therefore requires a *migration*, not configuration.
5. Price does not decide this. Verified against official sources, private beta costs ~$78/mo on
   DigitalOcean against ~$86 on AWS — an ~$8 gap. The real divergence is the metered surface
   (AWS egress is 9× DigitalOcean's) and Hetzner's ~⅓ cost bought with operational burden.
6. **Recommended primary provider: DigitalOcean. Recommended primary region: FRA1 (Frankfurt).**
7. Decisive reason: it is the only candidate offering managed PostgreSQL 17 with PITR *and*
   S3-compatible storage *and* a container runtime, at the lowest operational burden, without
   reproducing the AWS cost structure the owner already declined.
8. Hetzner is **not suitable now** — it offers no managed PostgreSQL and no container registry, so
   it relocates durability and recovery evidence onto the operator. It is a credible later cost
   optimization once that evidence is established elsewhere.
9. No approved artifact commits Khepri to any customer geography. Choosing DigitalOcean or Hetzner
   means EU residency by construction, since neither has a Middle East region.
10. The recommended next slice is **not** provisioning: it is implementing DEC-008's follow-on
    obligations, without which no provider choice can be executed.

---

## 2. Current Governance Authority

### 2.1 What is settled

| Fact | Source | State |
|---|---|---|
| Runtime is defined by capabilities, not products | `KHEPRI-DEC-008` | `active` |
| A separate target-selection artifact must precede any deployment definition | `KHEPRI-DEC-008` §"Target selection is a separate, pre-deployment artifact" | `active` |
| Job delivery is PostgreSQL claim/redrive; SQS removed | `KHEPRI-DEC-008` §"Job delivery" | `active` |
| Object storage contract is S3-compatible, private, non-versioned, 7-day expiry, multipart-abort | `KHEPRI-DEC-008` capability table | `active` |
| Application-side envelope encryption replaces provider-header proofs | `KHEPRI-DEC-008` §"Object storage control" | `active` (design), **unimplemented** |
| Interactive host access disabled by default; deploy only via CI | `KHEPRI-DEC-008` §"Infrastructure access" | `active` |
| No message broker (SQS/Redis/Kafka/RabbitMQ) | `KHEPRI-DEC-008` §"Alternatives not selected" | `active` |
| `src/khepri/infra/` is frozen reference, not the deployment path | `KHEPRI-DEC-008` §"Consequences" | `active` |
| AWS `me-central-1` (DEC-005) and its sizing (DEC-007) | registry `:47`, `:58` | **`retired`**, `superseded_by: KHEPRI-DEC-008` |

**Supersession check performed.** `governance/registry.yaml` shows `KHEPRI-DEC-008` at
`state: active` with no `superseded_by` field. A scan of `KHEPRI-DEC-009` … `-025` found no
decision that materially changes DEC-008's runtime-target authority. `KHEPRI-DEC-018` and
`KHEPRI-DEC-024`/`-025` mention data residency, but only as a *conditional recording obligation on
the identity provider* ("Where residency obligations apply, processing and storage regions are
recorded and verified"), which confirms rather than contradicts DEC-008's deliberate silence.

**A correction to a common misreading.** DEC-008 did not decline AWS. It declined a *specific
oversized AWS architecture* — Multi-AZ `db.m7g.large`, a continuously-held 4 vCPU / 16384 MiB
worker, NAT Gateway — priced at ~675 USD/mo on 2026-08-02. It states plainly: *"Cost alone does not
settle where the beta runs. A cost-shaped AWS environment was also priced at roughly 178 USD per
month and a DigitalOcean equivalent at 174 to 235, so the provider question is not decided by the
monthly figure."* A cost-shaped AWS proposal is therefore admissible.

### 2.2 What remains owner-selectable

DEC-008 explicitly does **not** settle: the provider, the region, the residency commitment, the
service count, autoscaling policy, or capacity. It authorizes no provisioning, deployment, or beta
launch. Those are this artifact's subject, and they require an owner merge to become governing.

### 2.3 The finding that reframes everything below

DEC-008 lists six follow-on obligations. **Only one has been substantively discharged.** Verified
directly against `main` @ `1e3b63c`:

| # | Obligation | Status | Verified evidence |
|---|---|---|---|
| 1 | Write the target-selection artifact | **Open** | No such decision file; no registry entry |
| 2 | Replace SQS adapter with PostgreSQL claim/redrive | **Mostly done** | `rra/sqs_queue.py` deleted in `f36f55f`; `claim_queue.py` exists. Two divergences below |
| 3 | Replace five provider-header proofs with envelope encryption | **Not done** | `rra/storage.py:96-101` still sends all five |
| 4 | Unlock `runtime/config.py` from region / account id / KMS ARN | **Not done** | `config.py:20,37,38-41,125-129` all intact |
| 5 | Re-issue `KHEPRI-BMK-001-sizing.yaml` against the selected target | **Open** | Broker keys still at `:17-20` |
| 6 | `superseded_by` registry field | **Done** | `registry.yaml:50,61` |

This is not a criticism of the decision; it is the normal state of an approved design whose slices
were never scheduled. But it is decisive for provider selection, because **the blocker to running
Khepri on DigitalOcean or Hetzner is Khepri's own code, not any provider's capability.**

---

## 3. Architecture Invariant

**Khepri application and domain code remains provider- and region-agnostic.** Provider and
geography are deployment concerns and must never become domain concepts. No provider name, cloud
region, country, continent, or cloud product name may influence analytical calculations, evidence,
facts, refusals, reports, accounts, memberships, authorization, organization behaviour, UI, or job
semantics. No `if provider == …` or `if region == …` branching, and no continent abstraction.

### 3.1 Compliance measured against the code, in three layers

A whole-tree case-insensitive scan of all 124 `src/**/*.py` files for provider, region, and cloud
product names yields a precise three-layer verdict.

**Layer 1 — Domain: COMPLIANT.**
`src/khepri/rca/` (identity, accounts, memberships, authorization — 24 modules) returns **zero
hits**. `rra/jobs.py`, `job_persistence.py`, `claim_queue.py`, `worker.py`, `pipeline.py`, all of
`rra/analysis/`, `rra/benchmark*`, and `khepri_gov/` are likewise clean. The four storage Protocols
(`EncryptedObjectStore`, `DeletionObjectStore`, `ProfileObjectReader`, `ArtifactObjectStore`) traffic
only in `bytes`, `str`, and plain dataclasses, leaking no boto3 types. **The portability seam is
real and well-drawn.**

**Layer 2 — Adapter: UNIMPLEMENTED, not un-portable.**
`src/khepri/rra/storage.py` is an AWS-specific adapter carrying a hard region pin:

```python
_KMS_KEY_ARN = re.compile(r"^arn:aws:kms:me-central-1:\d{12}:key/[0-9a-fA-F-]{36}$")  # :14-17
...
raise ValueError("KMS key must be a key ARN in me-central-1.")                        # :64
```

The constructor raises before a single S3 call is made. `runtime/config.py:125-129` independently
rejects any `KHEPRI_AWS_REGION` other than `me-central-1`. This is exactly the work DEC-008's
obligations 3 and 4 already authorize — bounded and specified, not a rewrite.

**Layer 3 — Schema: ONE GENUINE VIOLATION.**
The provider name is durable in the database:

```python
sa.CheckConstraint("encryption_algorithm = 'aws:kms'", name="ck_upload_kms_encryption")
# migrations/versions/20260729_0002_rra_uploads.py:37-40
```

Repeated at `migrations/versions/20260813_0012_rra_report_artifacts.py:165`, and mirrored in
`rra/persistence.py:108`, `rra/artifact_persistence.py:76,371`, `rra/intake.py:288`,
`rra/artifact_publication.py:337`. **A deployed PostgreSQL database physically rejects any row whose
encryption algorithm is not the literal string `aws:kms`.** This is a cloud product name in the
schema and is the single clearest breach of the invariant this section states. Correcting it needs
a schema migration, not a configuration change.

---

## 4. Portable Runtime Contract

Derived from DEC-008's capability table and narrowed to what the code actually exercises. Rows
marked ⚠ are requirements the code does **not** currently meet.

| # | Capability | Requirement (DEC-008) | What the code actually needs |
|---|---|---|---|
| C1 | Container runtime | Pinned OCI image, two process roles, no interactive access | `Dockerfile` builds one image; `khepri.runtime.web:app` under Uvicorn and `python -m khepri.runtime.worker`. No CMD by design |
| C2 | Relational store | PostgreSQL 17, TLS, PITR, auto minor upgrade disabled | **Code needs only PostgreSQL 9.5+** (`FOR UPDATE SKIP LOCKED`, `pg_advisory_xact_lock`). No PG16/17-only feature is used. "17" is a governance/ops pin for `environment_digest` stability, not a feature dependency. TLS is enforced app-side via `sslmode=require` (`config.py:235`) |
| C3 | Object storage | S3-compatible, private, non-versioned, 7-day expiry, multipart-abort | Six calls only: `put_object`, `get_object`, `delete_object`, `list_objects_v2`, `list_multipart_uploads`, `abort_multipart_upload`. Details in §4.1 |
| C4 | Secret store | Outside repo and image | One JSON blob in `KHEPRI_DATABASE_SECRET` + individual env vars. No secrets-manager client in the runtime |
| C5 | TLS ingress | Terminated by a non-application component | No app-side ingress TLS config exists; must be provided by the platform |
| C6 | Egress identity | Stable and restricted | Not referenced in application code; purely infrastructural |
| C7 | Image distribution | Registry recorded by descriptor; CI builds/scans/publishes | Any OCI registry |
| C8 | Telemetry | OTLP endpoint + content-free logs shipped off-host | ⚠ **No OTLP code exists.** Zero hits for `otel`/`otlp`/`opentelemetry` in `src/`, `pyproject.toml`, `Dockerfile`. `rra/telemetry*.py` is an internal DB-backed event model, not an exporter |
| C9 | Backup / PITR + restore exercise | Required before beta authorization | Provider capability; no application surface |
| C10 | Envelope encryption | App-side AES-256-GCM data key wrapped by a master key | ⚠ **Does not exist.** No `AESGCM`/`HKDF` anywhere in `src/khepri`. Still SSE-KMS with five provider proofs |

### 4.1 The real object-storage contract

The binding constraints are **not** the six API calls — those are ordinary and widely supported.
They are the behaviours layered on top:

| Behaviour | Where | Portability consequence |
|---|---|---|
| Five policy proofs on `put` (checksum, `aws:kms`, exact key ARN, `BucketKeyEnabled`, no `VersionId`) | `storage.py:96-101,248-259` | **No non-AWS store can satisfy these.** DEC-008 §"Object storage control" already records that Spaces has no CMK and never returns `BucketKeyEnabled`, and MinIO rewrites the key id. Removing them is obligation 3 |
| `ExpectedBucketOwner` on *every* call | `storage.py:100,154,178,204,220,241` | AWS-only parameter with no S3-compatible equivalent |
| `IfNoneMatch="*"` conditional create | `storage.py:101`, `412` handler `:125-148` | Requires conditional-write support |
| Versioning must be **absent**; `VersionId` in a response is rejected | `storage.py:166,243-246,258` | Needs a bucket that can be non-versioned |
| List-after-delete confirmation pass | `storage.py:196-198,233-235` | **Strictest consistency requirement in the codebase.** Raises `StoragePolicyViolation` if a listing still shows deleted keys — spurious failures on an eventually-consistent listing endpoint |
| Multipart: **abort only, never initiated** | `storage.py:200-235`, called `deletion.py:222` | Needs `ListMultipartUploads` + `AbortMultipartUpload` for deletion completeness |

**Seven-day expiry is application-side deletion, not a lifecycle rule.** `local/sweeper.py` sweeps
sessions past `content_expires_at` through the same `DeletionService` path an on-demand request
uses. The S3 lifecycle rule is an explicitly-labelled backstop
(`infra/data_resources.py:21-25`: *"the rule here exists to bound worst-case residency, never to
satisfy the `RRA-002` deletion obligation"*). ⚠ **However the sweeper has no production caller** —
`ClaimingReportQueue.recover` has zero callers and `ClaimWorkerLoop.run_once` never invokes it, so
on the deployment path the seven-day bound currently rests on the lifecycle backstop alone.

---

## 5. DigitalOcean Architecture (minimal valid)

```
DigitalOcean — one project, one region (FRA1)
├── App Platform
│   ├── Web service    (Khepri web role, Uvicorn)          — scales independently
│   └── Worker         (Khepri worker role, bounded)        — scales independently
├── Managed PostgreSQL 17          — PITR (7-day WAL), daily backup, VPC-attached, TLS
├── Spaces (FRA1)                  — private bucket, S3-compatible, lifecycle expiry
├── Container Registry             — pinned OCI image, published by CI
├── VPC                            — private DB + app networking
└── Monitoring / log forwarding    — content-free logs off-host
```

TLS ingress is terminated by App Platform (not the application), satisfying C5.

**Egress identity (C6) carries a real constraint, verified 2026-08-22.** App Platform *does* offer
dedicated egress IPs — two static addresses provisioned exclusively per app, persisting across
redeployments, intended precisely for allowlisting outbound traffic. But they are **only supported
for apps not connected to a VPC**: an app attached to a VPC routes outbound traffic through the
private network, so no fixed public egress IP can be assigned. The recommended architecture above
attaches the database over a VPC, so **VPC-private database access and a stable public egress
identity are mutually exclusive on App Platform**. Whether that matters depends on whether any
dependency requires IP allowlisting — recorded as D6 in §22.

**Verified availability (2026-08-22).** Spaces is available in FRA1 (also AMS3, LON1). Managed
PostgreSQL offers version 17. App Platform, Container Registry, VPC, and Load Balancers are all
available in the Frankfurt region.

**Verified gap.** DigitalOcean applies OS and database engine updates during a weekly maintenance
window and states these **cannot be disabled** — only the window can be scheduled, or an update
manually initiated early. This conflicts with DEC-008's "automatic minor upgrade disabled". See
§9.1 for why this is mitigable rather than disqualifying.

---

## 6. AWS Architecture (minimal valid)

Built to the smallest shape satisfying the contract — deliberately **not** a reproduction of the
DEC-005/DEC-007 architecture the owner declined.

```
AWS — one account, one region (eu-central-1)
├── ECS Fargate (small, ARM/Graviton)
│   ├── Web service    — bounded task count
│   └── Worker         — bounded, no NAT dependency
├── RDS PostgreSQL 17, Single-AZ, db.t4g.small, gp3
│                                  — PITR, AutoMinorVersionUpgrade=false
├── S3 + Gateway VPC endpoint       — private, non-versioned, lifecycle backstop
├── ECR                             — pinned image
├── Secrets Manager                 — DB credential + master key
├── KMS CMK                         — (retained only while the SSE-KMS proofs remain)
└── CloudWatch                      — content-free logs
```

**App Runner is not available and must not be proposed.** Verified 2026-08-22 on AWS's own product
page: *"AWS App Runner will no longer accept new customers starting on April 30, 2026."* AWS directs
new workloads to **Amazon ECS Express Mode**. Khepri has no existing App Runner footprint, so it is
closed to this project. This removes the simplest managed-container option and pushes the AWS path
toward Fargate — which is why §6 is Fargate-shaped and why TLS now needs an explicit answer (Express
Mode, or an ALB at ~$19.71/mo standing before LCUs).

Deliberately excluded, each with the reason: **NAT Gateway** — a **Gateway VPC endpoint for S3 is
free**, against $37.96/mo (derived) for an idle NAT Gateway plus $0.052/GB processing;
**Multi-AZ** — a private beta with a 7-day PITR window does not need a synchronous standby, and it
exactly doubles the database line; **SQS** — DEC-008 removed it.

**Prefer ARM/Graviton on Fargate.** At the same shape it is 20% cheaper than x86
($16.58 vs $20.72/mo for 0.5 vCPU / 1 GB, derived), and the image already builds for the platform
CI targets.

**Unique AWS advantage.** `AutoMinorVersionUpgrade=false` is a real, settable RDS parameter —
the only candidate where DEC-008's requirement is directly expressible. The caveat is that AWS
documents it will still apply a minor upgrade for critical security issues or at end-of-support,
so the guarantee is strong-but-not-absolute even here.

**Unique AWS advantage, second.** It is the only candidate with a Middle East region
(`me-central-1`, Bahrain), and the only one where the *current unmodified code* runs — because that
region is what the code is pinned to.

---

## 7. Hetzner Architecture (minimal valid)

```
Hetzner Cloud — one project, one location (FSN1 / NBG1 / HEL1)
├── Cloud server (CPX/CAX)
│   ├── Khepri Web container      (docker compose or systemd units)
│   ├── Khepri Worker container
│   └── Reverse proxy / TLS termination     ← self-operated (Caddy/nginx + ACME)
├── PostgreSQL 17                  ← SELF-MANAGED on a Volume
│   ├── WAL archiving              ← self-configured (pgBackRest / WAL-G)
│   ├── PITR                       ← self-configured and self-verified
│   └── Patching                   ← self-operated
├── Object Storage (FSN1/NBG1/HEL1) — S3-compatible, lifecycle + AbortIncompleteMultipartUpload
├── Load Balancer                  — optional
└── Container registry             ← EXTERNAL (GHCR or similar); Hetzner offers none
```

**Verified against Hetzner's own documentation (2026-08-22):**

- **No managed PostgreSQL.** The Hetzner Cloud product page lists Object Storage, Storage Box,
  Storage Share, Load Balancer, Firewalls, Networks, DNS, and SSL — and **no managed relational
  database of any kind**. Third-party offerings (e.g. Ubicloud) run *on* Hetzner but are a
  different vendor relationship, a different processor, and a different DPA.
- **No managed container registry.**
- **No managed secrets service.**
- **Object Storage is genuinely adequate for the storage contract**: locations Falkenstein
  (`fsn1`), Nuremberg (`nbg1`), Helsinki (`hel1`); lifecycle policies supported for automatic
  object expiry; `AbortIncompleteMultipartUpload` with `DaysAfterInitiation` supported; private
  bucket visibility; multipart up to 10,000 parts.
- **Object Storage encryption caveat**: only **SSE-C** is supported; SSE-KMS and SSE-S3 are not
  offered. Under DEC-008's envelope-encryption design this is acceptable, because the application
  encrypts before writing. But DEC-008 also requires provider-side encryption at rest *in addition*
  where available, and that additive layer is weaker here.
- Documented limits: 5 GB per single object operation, 5 TB per object, 100 TB and 50 M objects per
  bucket — all far above Khepri's 52,428,800-byte input bound.
- `CopyObject` is only partially supported and "may fail even if the buckets are in the same
  location". **Khepri never calls `copy_object`**, so this does not bind.

---

## 8. Technical Comparison

| Capability | DigitalOcean | AWS | Hetzner |
|---|---|---|---|
| Managed PostgreSQL 17 | ✅ Yes | ✅ Yes (RDS) | ❌ **None — self-managed** |
| PITR | ✅ 7-day WAL window | ✅ Configurable | ⚠ Self-configured (pgBackRest/WAL-G) |
| Auto minor upgrade **disable** | ❌ **Cannot be disabled** (window schedulable only) | ✅ `AutoMinorVersionUpgrade=false` (with security/EOL exception) | ✅ Full control (and full responsibility) |
| S3-compatible object storage | ✅ Spaces | ✅ S3 (native) | ✅ Object Storage |
| Lifecycle expiry | ✅ | ✅ | ✅ |
| Abort incomplete multipart | ✅ | ✅ | ✅ `AbortIncompleteMultipartUpload` |
| Private buckets + TLS | ✅ | ✅ | ✅ |
| Provider-side encryption at rest | ✅ | ✅ SSE-S3/SSE-KMS | ⚠ **SSE-C only** |
| Five current SSE-KMS proofs | ❌ Impossible | ✅ Only place they pass | ❌ Impossible |
| Managed container runtime | ✅ App Platform | ⚠ Fargate / ECS Express Mode — **App Runner closed to new customers 2026-04-30** | ❌ Self-operated on a VM |
| Container registry | ✅ | ✅ ECR | ❌ **None — external** |
| Managed secret store | ⚠ Env-var encryption only | ✅ Secrets Manager | ❌ None |
| TLS ingress (non-app) | ✅ App Platform | ✅ App Runner / ALB | ⚠ Self-operated proxy |
| Stable egress identity | ⚠ Dedicated egress IPs exist, but **not with VPC attachment** | ✅ NAT/EIP (at cost) | ✅ Server IP is inherently stable |
| Middle East region | ❌ None | ✅ `me-central-1` | ❌ None |
| Runs today's *unmodified* code | ❌ No | ✅ Yes (`me-central-1` only) | ❌ No |

---

## 9. Operational Responsibility Comparison

Burden classified LOW / MEDIUM / HIGH. No dollar value is assigned to engineering time, because no
evidence in the repository supports a rate.

| Responsibility | DigitalOcean | AWS | Hetzner |
|---|---|---|---|
| Host maintenance | **LOW** — App Platform manages hosts | **LOW** — App Runner/Fargate manages hosts | **HIGH** — operator owns the VM entirely |
| PostgreSQL maintenance | **LOW** — fully managed | **LOW** — fully managed | **HIGH** — install, tune, patch, monitor, upgrade |
| DB backups | **LOW** — daily automatic + WAL | **LOW** — automated | **HIGH** — configure pgBackRest/WAL-G, verify, monitor, store offsite |
| Restore | **MEDIUM** — provider restore, but the *exercise* is still ours (DEC-008 requires one) | **MEDIUM** — same | **HIGH** — entire restore path self-built and self-proven |
| OS patching | **LOW** — managed | **LOW** — managed | **HIGH** — operator, including reboots and kernel |
| TLS | **LOW** — automatic certs | **LOW** — ACM / App Runner | **MEDIUM** — self-operated ACME renewal |
| Monitoring | **MEDIUM** — built-in metrics; content-free log shipping still ours | **MEDIUM** — CloudWatch; same caveat | **HIGH** — stack self-assembled |
| Incident recovery | **MEDIUM** — provider handles infra; app is ours | **MEDIUM** — same | **HIGH** — every layer is ours, and DEC-008 forbids interactive host access, so recovery must be driven by telemetry that does not yet exist |
| Scaling | **LOW** — instance count | **LOW** — task/instance count | **HIGH** — manual resize, manual redeploy |
| Security patching | **LOW** | **LOW** | **HIGH** |
| **Human operational burden** | **LOW** | **LOW–MEDIUM** (service sprawl, IAM) | **HIGH** |

**Why Hetzner's HIGH ratings are structural, not pessimistic.** DEC-008 already rejected a
self-hosted database once, for a reason unrelated to price: *"the durability, backup, and recovery
evidence `RRA-007` requires would become entirely self-produced for a beta that does not need that
trade."* The same reasoning applies unchanged. This compounds with DEC-008's prohibition on
interactive host access: on a self-managed host, the operator carries full responsibility for
PostgreSQL recovery while being denied the usual means of diagnosing it.

### 9.1 Scoping the DigitalOcean auto-upgrade gap

DEC-008 requires auto minor upgrade disabled because *"an upgrade that changed the engine underneath
an approved `environment_digest` would silently invalidate every prior run's evidence while the
digest still matched."* The binding is therefore on **benchmark-evidence validity (OPS1-05)**, not
on the ability to deploy or serve.

Two facts narrow it further. First, **no environment descriptor exists yet** — every reference in
the repo is future-tense (`infra/sizing_source.py:5`, `KHEPRI-BMK-001-sizing.yaml:5`: "once the
descriptor exists"), and `environment_digest` is currently only a required non-empty string
(`rra/performance.py:21-31`), not a computed hash. Second, the requirement is **not fully
satisfiable anywhere**: AWS also reserves the right to force minor upgrades for security or EOL.

**Proposed mitigation** (owner decision, §22): record the exact engine minor version in the
descriptor, schedule the maintenance window, and treat a version change as an event that
invalidates and re-runs the governed benchmark. This converts a silent invalidation into an
observed one — which is the property DEC-008 actually wants.

---

## 10. Region / Location Comparison

Deployment implications only. No region or continent enters application code.

| Provider | Candidate | Managed PG | Object storage | Container runtime | Registry |
|---|---|---|---|---|---|
| DigitalOcean | **FRA1** (Frankfurt) | ✅ | ✅ Spaces | ✅ App Platform | ✅ |
| DigitalOcean | AMS3 (Amsterdam) | ✅ | ✅ Spaces | ✅ | ✅ |
| DigitalOcean | LON1 (London) | ✅ | ✅ Spaces | ✅ | ✅ |
| AWS | `me-central-1` (Bahrain) | ✅ RDS | ✅ S3 | ✅ | ✅ ECR |
| AWS | `eu-central-1` (Frankfurt) | ✅ RDS | ✅ S3 | ✅ | ✅ ECR |
| Hetzner | FSN1 (Falkenstein) | ❌ | ✅ | VM only | ❌ |
| Hetzner | NBG1 (Nuremberg) | ❌ | ✅ | VM only | ❌ |
| Hetzner | HEL1 (Helsinki) | ❌ | ✅ | VM only | ❌ |

**Per-service verification was performed rather than inferred**, per the §8 warning. Notably,
DigitalOcean Spaces is *not* available in every DigitalOcean region — NYC1, NYC2, and MEM1 lack it.
FRA1 was confirmed to carry Spaces, Managed PostgreSQL, App Platform, and Container Registry
together.

**Latency is not quantified here.** No approved artifact records a target customer geography, and
no latency measurement exists in the repository. Asserting a millisecond figure would be false
precision. If the owner names a customer geography, latency becomes measurable and may change the
region choice.

**FRA1 over AMS3/LON1**: Frankfurt is the largest European interconnection point and is closest of
the three to the Middle East, should the customer base prove to be there; LON1 additionally sits
outside the EU for data-protection purposes post-Brexit, which needlessly complicates §19.

---

## 11. Cost by Khepri Stage

**All figures 2026-08-22. Read the verification status before using any number here.**

Figures marked ✅ are quoted from an official provider source. Figures marked ⚠ are unverified and
must not be relied on for a spend commitment. Monthly figures derived from hourly rates use
**730 h/month** and are marked *(derived)*.

**Sources.** DigitalOcean and Hetzner from their published pricing pages; Hetzner cross-checked
against its own live price feed. **AWS from the official Price List Bulk API**
(`pricing.us-east-1.amazonaws.com/offers/v1.0/aws/…`) — the machine-readable source behind the
JavaScript-rendered pages, so AWS figures here are genuine quotes, not estimates.

**Two freshness caveats, stated rather than buried.** AWS offer files re-stamp only when a price
changes, so "retrieved 2026-08-22" is not "priced 2026-08-22": RDS/EC2/S3 are days old, but Secrets
Manager and KMS are stamped 2025-08-28 and ECR 2025-11-21. And **Hetzner raised prices on
15 June 2026** and renamed plan generations (CX22→CX23), so any earlier Hetzner figure is stale.

**Currency and tax.** DigitalOcean and AWS in USD. **Hetzner in EUR, net of VAT** — its German
locale displays gross including 19%, so a EUR figure seen in a browser may be ~19% higher than the
one recorded here. Do not compare the two directly without adjusting.

This section is therefore **not decision-grade for spend approval**. It is sufficient for the only
conclusion it is used to support — that the three providers sit within the same order of magnitude
at every stage, which `KHEPRI-DEC-008` independently established on 2026-08-02 with the ~178 USD/mo
and 174–235 USD/mo figures. Before any spend commitment, the ⚠ rows must be replaced with quotes
from official pricing pages or the provider's calculator.

Costs are separated into **FIXED** (standing monthly), **VARIABLE** (usage-driven), and
**OPTIONAL**.

### Stage: LOCAL (Phase 0)

| Item | DigitalOcean | AWS | Hetzner |
|---|---|---|---|
| All (WSL/Docker: `postgres:17.6-alpine` + `localstack`) | **$0** | **$0** | **$0** |

Cloud infrastructure cost is $0 for all three. `docker-compose.local.yml` already provides
PostgreSQL 17.6 and an S3-compatible endpoint.

### Stage: REMOTE STAGING (Phase 1)

One provider, one region, no customers, lowest managed complexity.

| Line item | DigitalOcean (USD) | AWS eu-central-1 (USD) | Hetzner (EUR, ex-VAT) |
|---|---|---|---|
| Web compute | ✅ App Platform `1vcpu-0.5gb` **5.00** | ✅ Fargate ARM 0.5 vCPU/1 GB **16.58** *(derived)* | — |
| Worker compute | ✅ App Platform `1vcpu-1gb` **12.00** | ✅ Fargate ARM 1 vCPU/2 GB **33.16** *(derived)* | — |
| VM (both roles) | — | — | ✅ CX23 (2 vCPU/4 GB, 20 TB) **5.49** |
| PostgreSQL | ✅ Managed 1 vCPU/1 GiB **15.15** | ✅ RDS db.t4g.micro Single-AZ **13.87** *(derived)* | self-managed: **€0 licence**, HIGH labour |
| DB storage | included in tier (10–30 GiB) | ✅ gp3 **0.137**/GB-mo | ⚠ Volume €/GB-mo **unpublished** |
| Object storage | ✅ Spaces base **5.00** (250 GiB + 1 TiB out) | ✅ S3 **0.0245**/GB-mo — cents at this scale | ✅ Object Storage **6.49** (1 TB + 1 TB) |
| Registry | ✅ Starter **0** (1 repo, 500 MiB) | ✅ ECR **0.10**/GB-mo | ⚠ none offered — GHCR free tier |
| TLS ingress | ✅ included in App Platform | ⚠ ECS Express Mode, or ALB ✅ **19.71** *(derived)* + LCUs | self-operated (€0 + labour) |
| IPv4 | — | — | ✅ **0.50** |
| **FIXED subtotal** | ✅ **~$37** | ✅ **~$64** (Express Mode) / **~$84** (ALB) | ✅ **~€12.50 + HIGH labour** |

### Stage: PRIVATE BETA (Phase 2)

Small number of design partners, real backups, restore exercise, monitoring.

| Line item | DigitalOcean (USD) | AWS eu-central-1 (USD) | Hetzner (EUR, ex-VAT) |
|---|---|---|---|
| Web compute | ✅ App Platform `1vcpu-1gb` **12.00** | ✅ Fargate ARM 0.5 vCPU/1 GB **16.58** *(derived)* | — |
| Worker compute (Chromium + Polars headroom) | ✅ App Platform `1vcpu-2gb` **25.00** | ✅ Fargate ARM 1 vCPU/2 GB **33.16** *(derived)* | — |
| VM sized for Chromium (16 GB) | — | — | ✅ CX43 (8 vCPU/16 GB) **15.99** |
| PostgreSQL | ✅ Managed 1 vCPU/2 GiB **30.45** | ✅ RDS db.t4g.small Single-AZ **27.01** *(derived)* | self-managed, **€0 + HIGH labour** |
| DB storage (~50 GB) | ✅ $0.215/GiB-mo over tier | ✅ gp3 **0.137**/GB-mo ≈ **6.85** | ⚠ Volume €/GB-mo **unpublished** |
| Backups | ✅ included (7-day PITR) | ✅ **0.103**/GB-mo beyond free allocation ⚠(allocation size unverified) | snapshots ✅ **0.0143**/GB-mo + offsite |
| Object storage | ✅ Spaces **5.00** base | ✅ S3 **0.0245**/GB-mo + ✅ $0.0054/1k PUT, $0.0043/10k GET | ✅ **6.49** base |
| Registry | ✅ Basic **5.00** (5 GiB) | ✅ ECR **0.10**/GB-mo | ⚠ external |
| Secrets | env-var encryption **0** | ✅ Secrets Manager **0.40**/secret-mo + $0.05/10k | none — self-operated |
| KMS | n/a | ✅ **1.00**/key-mo + $0.03/10k | n/a |
| Monitoring / logs | ✅ included, "no additional cost" | ✅ CloudWatch **0.63**/GB ingest + $0.0324/GB-mo | self-operated |
| TLS ingress | ✅ included | ⚠ Express Mode, or ALB ✅ **19.71** *(derived)* + LCUs | self-operated, or LB11 ✅ **7.49** |
| Bandwidth | ✅ pooled; overage **$0.01/GiB** | ✅ egress **0.09**/GB (100 GB/mo free) | ✅ 20 TB incl.; overage **1.00**/TB |
| IPv4 | Reserved IP free when assigned ✅ ($5 idle) | — | ✅ **0.50** |
| **FIXED subtotal** | ✅ **~$78** | ✅ **~$86** (Express Mode) / **~$106** (ALB) | ✅ **~€23 + HIGH labour** |

**Read the egress line before concluding the totals are close.** DigitalOcean's overage is
**$0.01/GiB** against AWS's **$0.09/GB** — nine times higher, on top of a far smaller free
allowance, and Hetzner includes 20 TB before charging €1.00/TB. Khepri serves rendered PDFs and
workbooks, so egress is a real line, not a rounding error. This is the metered surface §15 reason 3
refers to, and it is the largest cost divergence between the three at any realistic volume.

**One unpublished Hetzner rate matters here.** There is no published Volumes €/GB-month figure —
the block-storage page carries none, and the widely-cited €0.04 traces to a 2018 announcement, so
it is not adopted. That is precisely the input a self-managed PostgreSQL data disk needs, which
means **Hetzner's cheapest-looking column has an unpriced line exactly where its extra
responsibility sits.**

DEC-008's own dated comparison (2026-08-02) put cost-shaped AWS at **~178 USD/mo** and DigitalOcean
at **174–235 USD/mo** for a beta-grade environment. Those figures are an approved internal source
and are consistent with the ranges above once monitoring and egress are included.

### Stage: FIRST COMMERCIAL PRODUCTION (Phase 3)

Production separated from staging; increased DB reliability; rollback and incident procedures.

| Line item | DigitalOcean | AWS | Hetzner |
|---|---|---|---|
| Two environments (prod + staging) | ~2× beta | ~2× beta | ~2× beta |
| PostgreSQL HA / standby | ✅ a standby is a **matching node at the same rate** (≈ ×2) | ✅ Multi-AZ db.t4g.small **54.02** *(derived, exactly 2×)* | second VM + replication, **self-built** |
| **FIXED subtotal** | ✅ **~$190** | ✅ **~$200** (Express Mode) / **~$240** (ALB) | ✅ **~€46 + HIGH labour** |

DigitalOcean documents HA as *"at least one $30.00 per month matching standby node"* — note its own
docs say **$30.00** where the pricing page says **$30.45** for the same node. Two official pages
disagree; the cent-level value is ⚠ unverified, the ×2 structure is not.

### Stage: EARLY COMMERCIAL SCALE (Phase 4)

Scale on measurement, not assumption. Worker count is the scaling unit — DEC-008 fixes one report
job per worker process and forbids in-process concurrency, so throughput is bought by process
count. Each additional worker adds roughly one worker-compute line item. **No capacity figure is
proposed here**, because none is measured: the governed benchmark (`KHEPRI-DEC-006`: 40 synthetic
datasets, 95% threshold, ten-minute objective) has never been run on any target.

### Cost conclusion

**The verified figures confirm DEC-008's conclusion and narrow the gap further.** At private beta,
DigitalOcean ~$78/mo against AWS ~$86 (Express Mode) — closer than DEC-008's own August comparison
of 174–235 vs ~178, and closer than the placeholder estimates this section previously carried. **A
provider decision cannot rest on ~$8/month.**

Three things the numbers *do* decide:

1. **The metered surface, not the base rate, is where the money is.** Egress is $0.09/GB on AWS
   against $0.01/GiB on DigitalOcean, and CloudWatch ingest ($0.63/GB), Secrets Manager calls, KMS,
   and per-request S3 charges each accrue separately. The base rates are near-identical; the
   variance is not.
2. **Hetzner's advantage is real and large** — roughly a third of the others at every stage — and is
   bought entirely with operational responsibility, plus one unpriced line (Volumes).
3. **Multi-AZ and HA standby exactly double the database line on both managed providers.** Deferring
   HA until Phase 3, as this analysis does, is the single largest cost lever available.

---

## 12. Portability Matrix

"If Khepri moves from this provider to another, what changes?"

| Capability | Khepri contract | DigitalOcean | AWS | Hetzner | Migration impact |
|---|---|---|---|---|---|
| Web container | OCI image, web role | App Platform service | App Runner / Fargate | container on VM | **LOW** — same image everywhere |
| Worker container | OCI image, bounded worker | App Platform worker | App Runner / Fargate | container on VM | **LOW** |
| PostgreSQL | PG 17, TLS, PITR | Managed | RDS | self-managed | **LOW** for the app (`sslmode=require` + a URL); **HIGH** operationally toward Hetzner |
| Object storage | S3-compatible, 6 calls | Spaces | S3 | Object Storage | **HIGH today, LOW after obligation 3.** Blocked by the five proofs, `ExpectedBucketOwner`, and the missing `endpoint_url` in `wiring.py:122` |
| Encryption / master key | App-side envelope (per DEC-008) | app-side + Spaces at rest | app-side + SSE | app-side (SSE-C only) | **HIGH** — the design exists, the code does not |
| Secrets | Outside repo and image | App Platform env encryption | Secrets Manager | self-operated | **MEDIUM** — Hetzner has no service |
| Registry | Any OCI registry | DO Registry | ECR | external (GHCR) | **LOW** — a pull credential |
| Ingress / TLS | Terminated off-application | App Platform | App Runner / ALB | self-operated proxy | **LOW–MEDIUM** |
| DNS | Not in application code | DO DNS | Route 53 | Hetzner DNS | **LOW** |
| Telemetry | OTLP + content-free logs | any OTLP endpoint | any OTLP endpoint | any OTLP endpoint | **MEDIUM** — no OTLP code exists yet, so this is greenfield on every provider |
| Networking | Private DB path | VPC | VPC | Networks | **LOW** |
| Egress identity | Stable, restricted | ⚠ Dedicated egress IP, but not alongside VPC | NAT/EIP | server IP | **MEDIUM** on DigitalOcean App Platform |
| Backup / restore | PITR + proven restore exercise | managed | managed | self-built | **LOW** managed→managed; **HIGH** toward Hetzner |
| **Database schema** | — | — | — | — | **HIGH** — `ck_upload_kms_encryption` forces a migration off `'aws:kms'` for *any* non-AWS move |

### The three HIGH cases explained

1. **Object storage adapter (HIGH → LOW).** `S3EncryptedObjectStore` refuses to construct outside
   `me-central-1` and demands five AWS-only response proofs. Additionally
   `runtime/wiring.py:120-122` builds the boto3 client with **no `endpoint_url` and no
   addressing-style override**, so it cannot be pointed at a non-AWS endpoint at all — ironically
   the *local* path (`local/config.py`, `KHEPRI_LOCAL_S3_ENDPOINT`) is the only one with that seam.
   DEC-008 obligation 3 already authorizes the fix.
2. **Encryption/master key (HIGH).** Envelope encryption is designed but unwritten. Until it
   exists, "provider-agnostic storage" is a governance statement, not a code property. Note
   DEC-008 records the security trade explicitly: a master key in the application process has
   weaker custody than a KMS CMK, accepted against the compensating controls of no interactive host
   access, transient content, and seven-day expiry.
3. **Database schema (HIGH).** `encryption_algorithm = 'aws:kms'` is a CHECK constraint in two
   migrations. Any non-AWS backend needs a schema migration plus a data migration for existing
   rows. This is the one place where a cloud product name is *durable* rather than configurable.

---

## 13. Recommended Primary Provider

# DigitalOcean

One provider. No hedging.

---

## 14. Recommended Primary Region

# FRA1 — Frankfurt, Germany

One region. Single-region only, per §9 of the task and DEC-008's private-beta scope. No
active-active, no multi-cloud, no simultaneous deployment.

---

## 15. Why This Choice

1. **It is the lowest-operational-burden option that satisfies the whole contract.** It is the only
   candidate other than AWS providing managed PostgreSQL 17 with PITR, S3-compatible storage, a
   managed container runtime, a registry, and TLS ingress as products rather than as work.
2. **It avoids re-litigating the cost decision the owner already made.** DEC-008 declined a
   ~675 USD/mo AWS architecture. A cost-shaped AWS build is admissible but arrives with the service
   sprawl, IAM surface, and egress pricing that produced that outcome; DigitalOcean's pricing is
   flat and legible, which matters more to a self-funded private beta than a marginal dollar gap.
3. **Its cost is legible and has no usage cliffs.** The private beta's spend risk is not the base
   rate but the metered surface: on AWS, egress per GB, NAT data processing, CloudWatch ingestion,
   Secrets Manager API calls, and per-request S3 charges each accrue independently and are hard to
   forecast before the workload is measured — and the benchmark has never been run. DigitalOcean
   prices compute and databases as flat monthly tiers with pooled bandwidth, so the bill is close to
   the standing figure. For a self-funded beta, predictability is worth more than a marginal rate.
4. **Its managed database matches the governed retention rule by construction.** DEC-008 requires
   backup retention to match the seven-day object expiry "so that no retention horizon is quietly
   longer than another." DigitalOcean's PITR window is exactly seven days.
5. **It keeps the exit cheap.** After the obligations land, the storage contract is six ordinary S3
   calls behind four clean Protocols, and PostgreSQL is a connection URL. The residual switching
   cost to AWS or Hetzner is infrastructure and configuration, which is precisely DEC-008's stated
   intent.

---

## 16. Second Choice

**AWS, in `eu-central-1` (Frankfurt) — not `me-central-1`.**

It satisfies every capability, is the only place `AutoMinorVersionUpgrade=false` is directly
expressible, and is the only provider where today's unmodified code runs. It is second because it
reintroduces the cost structure and service sprawl DEC-008 reacted against, and because deploying
to `me-central-1` specifically would reward the existing hard pin instead of removing it.

`eu-central-1` rather than `me-central-1` is deliberate: it keeps the region a *deployment*
variable rather than the value the code already assumes, so the pin must still be removed.

*(Practical note: `me-central-1` is an opt-in AWS region. Its enablement status on the intended
account should be confirmed before it is selected — an unopted region fails authentication in a way
that reads as a credentials problem. Not verified as part of this analysis.)*

---

## 17. Hetzner Position

**Suitable as a later cost optimization. Not suitable now. Not currently suitable as a DR target.**

- **Not suitable now**, decisively, because it offers **no managed PostgreSQL**. This is not a
  price question. It relocates PITR configuration, backup verification, restore exercises, failover,
  and patching onto the operator — and DEC-008 must have a *proven* restore exercise before beta
  authorization. It already rejected this exact trade: *"the durability, backup, and recovery
  evidence `RRA-007` requires would become entirely self-produced for a beta that does not need
  that trade."* The absence of a managed registry and secret store compounds it, and the
  prohibition on interactive host access makes self-managed recovery harder still, since diagnosis
  must run through telemetry that does not yet exist.
- **Suitable as a later cost optimization**, genuinely. Its Object Storage satisfies the real
  storage contract — lifecycle expiry, `AbortIncompleteMultipartUpload`, private buckets, and
  limits far above Khepri's bounds. Its compute is materially cheaper. Once DEC-008's obligations
  are implemented and operational maturity exists (proven restore procedure, working telemetry,
  measured capacity), moving the *compute and object storage* to Hetzner while keeping a managed
  database elsewhere is a rational later step.
- **Not currently a DR target**, because a disaster-recovery target must be *more* trustworthy than
  the primary at the moment it is needed, not less. A self-managed standby that has never
  demonstrated a restore is not recovery capability.
- **Do not recommend it on VM price.** The dollar gap is real (~€25–40/mo vs ~$80–120/mo at beta)
  but it is bought entirely with operational responsibility, and this analysis declines to assign
  that a fake dollar value.

---

## 18. Exit Strategy

Moving from DigitalOcean to AWS or Hetzner without touching product or domain architecture:

| Step | What changes | What does not |
|---|---|---|
| 1. Build image | Nothing — same pinned OCI image | Everything in the image |
| 2. Object storage | `endpoint_url`, credentials, bucket name — **configuration**, once obligation 3 lands | The six S3 calls; the four Protocols; all five consumer services |
| 3. PostgreSQL | Connection URL in `KHEPRI_DATABASE_SECRET`; `pg_dump`/restore or logical replication | Schema, migrations, all queries; PG 9.5+ is the real floor |
| 4. Job delivery | Nothing | PostgreSQL owns canonical job state — no broker to migrate on any provider |
| 5. Secrets | Injection mechanism | What the application reads (plain env vars) |
| 6. Registry | Pull credential | Image contents and digest |
| 7. Ingress / TLS | Platform-specific | The application terminates no TLS |
| 8. Telemetry | OTLP endpoint URL | Content-free telemetry semantics |
| 9. Descriptor | New provider/region/product values; new `environment_digest` | The descriptor *format* |
| 10. Benchmark | Re-run on the new target | The workload (`KHEPRI-DEC-006` is provider-neutral) |

**The single genuine exception**, stated rather than hidden: step 2 additionally requires an Alembic
migration to drop `ck_upload_kms_encryption` and relax `kms_key_id`. Until that lands, no exit from
AWS is a configuration change. **This is why §23 recommends implementing the obligations before
provisioning anything.**

---

## 19. Data Residency Position

**Where data would physically run.** Under this recommendation: all customer content, derived
artifacts, and database state reside in **Frankfurt, Germany (DigitalOcean FRA1)** — App Platform
compute, Managed PostgreSQL, and Spaces in one region. Backups and WAL remain within DigitalOcean's
FRA1 infrastructure. This excludes the identity provider (Clerk, per `KHEPRI-DEC-025`), whose own
residency is governed separately, and the optional OpenAI narrative adapter, which is gated
separately by DEC-008 and disabled absent verified Zero Data Retention.

**What Khepri can truthfully promise once this is approved and provisioned.** That the primary
processing and storage region is Germany, and that the region is recorded in the environment
descriptor as a governed value. Nothing more, and only after provisioning — a promise cannot precede
the environment.

**What is NOT currently promised, and must not be implied.**

- **No residency commitment exists today.** DEC-008 deliberately records none, and its refusal is
  principled: *"a refusal to record a commitment no approved artifact supports."*
- **No customer geography is approved.** A repository-wide search found no artifact naming a target
  country, market, or customer region. Bilingual Arabic/English output is a product requirement, not
  a residency commitment. **This analysis therefore recommends a region without an approved
  geographic requirement to satisfy — that is an owner input, not a derivable fact.**
- **No data-residency guarantee to any customer**, no contractual SLA, no regulatory-compliance
  claim (GDPR adequacy, sovereignty, sector-specific), and no commitment about subprocessor
  locations.
- **Choosing DigitalOcean or Hetzner means EU residency by construction**, since neither operates a
  Middle East region. If the owner requires Middle East residency, **AWS `me-central-1` is the only
  candidate of the three that can provide it**, and that requirement would override the §13
  recommendation. This is the one input that reverses the result.

---

## 20. Future Multi-Region / Multi-Cloud Triggers

Not designed and not implemented. Triggers only. **No numeric thresholds are invented**, because no
approved product or governance artifact supplies them; each trigger names the evidence that would
have to exist first.

| # | Trigger | Evidence that would establish it |
|---|---|---|
| T1 | A customer contract requires data residency in a named jurisdiction the primary region is not in | An executed agreement with a residency clause |
| T2 | A regulatory obligation attaches to a customer segment | Legal determination naming the regime |
| T3 | A contractual availability SLA exceeds what a single-region managed database delivers | A signed SLA plus the provider's published availability |
| T4 | Measured user-facing latency breaches a product-approved objective | An approved latency objective (none exists) plus measurement |
| T5 | Provider concentration risk becomes material to revenue | Revenue concentration data (no paying customers exist) |
| T6 | An RTO/RPO target is approved that single-region PITR cannot meet | A governed RTO/RPO in the descriptor plus a measured restore time |
| T7 | Provider outage history breaches an approved availability objective | Incident record against an approved objective |

Until at least one trigger is evidenced, single-provider single-region remains correct. Portability
is the ability to **move**, never the obligation to **run everywhere**.

---

## 21. Environment Descriptor Proposal

**Reusing the existing convention, not inventing one.** The repository already has exactly one
descriptor-shaped artifact: `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` — flat YAML, a
`schema_version` key, **all values quoted strings**, read by `src/khepri/infra/sizing_source.py`
which supplies no fallbacks and fails closed. This proposal keeps that shape exactly.

**Not created by this analysis.** The file below is a proposal for owner review. `OPS1-01`'s output
is an *approved* descriptor; this is the draft of one. Values marked `TBD-…` require provisioning
or an owner decision and must not be invented here.

```yaml
# Proposed: governance/environments/KHEPRI-ENV-001-private-beta.yaml
# Shape follows governance/benchmarks/KHEPRI-BMK-001-sizing.yaml: flat, quoted strings,
# schema_version, no defaults. Editing any value changes this file's digest, which changes
# the environment_digest, which invalidates prior benchmark evidence.
schema_version: "1"

environment_name: "private-beta"

# Deployment metadata. Recorded here, never read by application/domain code.
deployment_provider: "digitalocean"
deployment_region: "fra1"
residency_jurisdiction: "de"

# C1 container runtime
container_web_product: "app-platform-service"
container_worker_product: "app-platform-worker"
container_web_instance: "TBD-owner-sizing"
container_worker_instance: "TBD-owner-sizing"
interactive_host_access: "disabled"

# C2 relational store
database_product: "digitalocean-managed-postgresql"
database_version_major: "17"
database_version_exact: "TBD-at-provisioning"
database_tls: "required"
database_pitr_window_days: "7"
database_auto_minor_upgrade: "provider-enforced-cannot-disable"
database_recorded_rto: "TBD-owner-decision"
database_recorded_rpo: "TBD-owner-decision"

# C3 object storage
object_storage_product: "digitalocean-spaces"
object_storage_endpoint: "TBD-at-provisioning"
object_storage_bucket: "TBD-at-provisioning"
object_storage_versioning: "disabled"
object_storage_expiry_days: "7"
object_storage_abort_incomplete_multipart_days: "1"

# C4 secrets
secret_source: "TBD-owner-decision"

# C5 ingress
tls_ingress_product: "app-platform-managed"

# C6 egress identity
egress_identity: "TBD-owner-decision"

# C7 image distribution
image_registry: "digitalocean-container-registry"
image_digest: "TBD-per-release"

# C8 telemetry
otlp_endpoint: "TBD-owner-decision"
log_destination: "TBD-owner-decision"

# Backup retention matches object expiry, per KHEPRI-DEC-008.
backup_retention_days: "7"
```

### 21.1 Sizing values, in provider-neutral units

DEC-008 requires the descriptor to record sizing derived from its rules rather than DEC-007's
Fargate-shaped values. **This analysis proposes rules-consistent placeholders and explicitly does
not re-issue `KHEPRI-BMK-001-sizing.yaml`** — that is a separate OPS1 task, and §20 of this task
limits changes to documentation.

| Rule (DEC-008 §Sizing) | Provider-neutral requirement |
|---|---|
| One report job per worker process | Worker concurrency `1`; throughput by process count only |
| Worker memory holds Chromium (6 surfaces incl. tagged PDF) + Polars frame from ≤52,428,800-byte input + intermediates | Sized so two large-band datasets cannot coincide in one process |
| Worker cores sized so completion is pipeline-bound, not core-bound | Multi-core; Polars parallelizes grouping/aggregation |
| Worker disk holds baked browser, input, 6 surfaces, temporaries, `/dev/shm` redirect | Local disk, not credit-based |
| Web role renders/streams/enqueues only | Sized so several concurrent ≤52,428,800-byte uploads are slow, not OOM |
| Lease 300 s, heartbeat 60 s, retry 60 s, attempts 3 | ⚠ Hardcoded module constants (`runtime/worker.py:31-32`, `report_services.py:41`), not configurable; heartbeat is stage-driven rather than on a 60 s interval (§22.1) |
| Storage delivers baseline performance continuously | No burst-credit storage |
| Backup retention = 7-day object expiry | `backup_retention_days: "7"` |

### 21.2 The four SQS keys

`KHEPRI-BMK-001-sizing.yaml:17-20` still carries `visibility_timeout_seconds`,
`message_retention_seconds`, `receive_wait_seconds`, and `max_receive_count`. DEC-008 ordered their
removal, but there is a coupling to respect: `src/khepri/infra/sizing.py:77` declares
`RETRY_KEYS = ("max_receive_count", "max_attempts")`, so deleting the key breaks a currently-green
test. **Removing them is a code slice, not a YAML edit** — noted for the re-issue task, not done
here.

---

## 22. Open Owner Decisions

**What approving D1 actually requires.** Merging *this file* would not create authority — it is a
`docs/` draft, and `governance/registry.yaml` is authoritative for artifact identity and state
(Constitution III). Promoting the recommendation to governing authority requires a decision-shaped
artifact under `governance/decisions/` plus its registry entry at `state: active`, merged by the
owner. This analysis deliberately authors neither: **automation never writes the owner's approval.**

Only genuine decisions requiring the owner.

| # | Decision | Why it is the owner's | Recommendation |
|---|---|---|---|
| **D1** | Approve DigitalOcean + FRA1, or select an alternative | DEC-008 reserves provider, region, and residency to a separate approved artifact | DigitalOcean / FRA1 |
| **D2** | **Is Middle East data residency required?** | No approved artifact names a customer geography. This is the one input that reverses D1 — only AWS `me-central-1` can satisfy it | Answer before D1 is merged |
| **D3** | Accept DigitalOcean's non-disableable minor upgrades, with the mitigation in §9.1 | DEC-008 states the requirement; only the owner may vary it | Accept with mitigation; it binds benchmark validity, not deployment, and is not fully satisfiable anywhere |
| **D4** | Order of work: implement DEC-008's obligations **before** provisioning | Affects cost and sequencing | Obligations first (see §23) |
| **D5** | Secret source for the envelope master key | DEC-008 requires "outside repo and image" but names no product; DigitalOcean has no managed secret store | Owner selects; App Platform encrypted env vars are the minimum acceptable |
| **D6** | Stable egress identity requirement | On App Platform, dedicated egress IPs and VPC attachment are **mutually exclusive** (§5). Choosing one gives up the other | Confirm whether any dependency requires IP allowlisting; if none does, prefer VPC-private database access |
| **D7** | Recorded RTO and RPO | DEC-008 requires both in the descriptor; neither exists anywhere | Owner sets targets; 7-day PITR bounds what is achievable |

### 22.1 Defects found during this analysis (not owner decisions — recorded for the ledger)

Found while verifying the runtime contract. None is in this task's scope to fix; all are reportable
per §21 of the task.

1. **The runtime cannot boot without two SQS queue URLs that nothing reads.**
   `runtime/config.py:148-155` requires `KHEPRI_QUEUE_URL` and `KHEPRI_DLQ_URL` and rejects them if
   equal; a grep of `wiring.py` finds **no consumer** of either. Any new environment must set two
   meaningless variables.
2. **The claim query does not use `SKIP LOCKED`.** DEC-008 specifies
   `SELECT … FOR UPDATE SKIP LOCKED`; `job_persistence.py:190` uses plain `with_for_update()`.
   `SKIP LOCKED` appears only in the two recovery sweeps (`:211`, `:229`). The claim is *safe* but
   not work-conserving: a blocked worker re-evaluates the predicate, finds `state='running'`, and
   idles even when other jobs are claimable.
3. **The heartbeat is stage-driven, not the 60-second interval DEC-008 specifies.** `heartbeat()`
   *is* invoked — `rra/pipeline.py:318,320,322` calls it between stages, deliberately placed
   outside them so a lost lease surfaces rather than being swallowed by a stage's exception
   handler. But DEC-008 specifies a heartbeat "every 60 seconds", and nothing enforces an
   interval: the gap between heartbeats is however long a stage takes. A single stage exceeding
   the 300-second lease loses it. This is a divergence to reconcile — either the code gains a
   timer, or the decision's interval becomes a between-stages rule — not a missing feature.
4. **The recovery sweep has no production caller.** `ClaimingReportQueue.recover` has zero callers;
   `ClaimWorkerLoop.run_once` never invokes it. `local/sweeper.py:1-8` documents this. **Expired
   leases are never reclaimed on the deployment path**, and the seven-day expiry currently rests on
   the S3 lifecycle backstop rather than on application deletion.
5. **No OTLP implementation exists.** DEC-008's observability section requires an OTLP endpoint
   recorded by the descriptor; there is nothing to record into.

**Item 4 is the most operationally serious.** A worker that dies mid-job leaves a job whose lease
expires and is then never reclaimed, because nothing on the deployment path runs the recovery
sweep. Item 3 compounds it: a long stage can lose the lease while the job is still healthy. Both
should be resolved before beta traffic, and both are independent of provider choice.

### 22.2 Pricing inputs that remain unverified

Listed so a later reader knows these were *sought and not found*, rather than overlooked.

| Item | Status |
|---|---|
| **Hetzner Volumes €/GB-month** | Genuinely unpublished — no rate on the block-storage page. The €0.04 in circulation traces to a 2018 post and is not adopted. Needed to price self-managed PostgreSQL storage |
| DigitalOcean Managed PG HA node: **$30.00 vs $30.45** | Two official DigitalOcean pages disagree. The ×2 structure is confirmed; the cent value is not |
| DigitalOcean App Platform **worker** rate | Docs price "services and jobs" and describe workers as services that are not routable. Equal pricing is implied, never stated |
| AWS RDS backup **free allocation size** | The rate beyond it ($0.103/GB-mo) is verified; the allowance itself is not quantified in the API or docs |
| AWS `me-central-1` egress exact rate | AWS's own data self-contradicts: `pricePerUnit` 0.11 against description text "USD0.1170" |
| DigitalOcean Premium Intel/AMD Droplet delta | JavaScript-gated; only a blog carries a figure |

---

## 23. Recommended Next OPS Slice

Exactly one bounded task, after owner approval of D1–D4.

> **Implement `KHEPRI-DEC-008` follow-on obligations 3 and 4: replace the five provider-header
> proofs with application-side envelope encryption and read-back digest verification, and unlock
> `src/khepri/runtime/config.py` and `src/khepri/rra/storage.py` from `me-central-1`, the
> twelve-digit account identifier, and the KMS key ARN — including the Alembic migration that
> relaxes `ck_upload_kms_encryption`, and an `endpoint_url` seam in `runtime/wiring.py`.**

**Why this and not provisioning.** Provisioning first would create a DigitalOcean environment the
application cannot use: `S3EncryptedObjectStore` raises `ValueError` at construction outside
`me-central-1`, the boto3 client has no `endpoint_url`, and the database rejects any row not marked
`'aws:kms'`. The environment would sit idle and paid-for while this slice is written anyway.

**Why it is bounded and verifiable.** Both obligations are already authorized by an active
decision, so no new authority is needed. The blast radius is three modules plus one migration, all
consumers already depend on Protocols, and success is directly testable: the existing suites
(`tests/test_rra002_s3_storage.py`, `tests/test_rra003_s3_read.py`, `tests/test_runtime_config.py`)
must pass against a non-AWS S3-compatible endpoint, which `docker-compose.local.yml` already
provides.

**Explicitly out of scope for that slice:** provisioning, deployment, the descriptor's TBD values,
the `KHEPRI-BMK-001-sizing.yaml` re-issue, and defects 1–5 in §22.1 (each its own slice).

---

## Appendix A — DEC-008 required-content checklist

DEC-008 fixes the required content of the target-selection artifact. Mapped here so the artifact is
checkable against its governing decision.

| DEC-008 requirement | Where addressed | Complete? |
|---|---|---|
| The provider and region | §13, §14 | ✅ Recommended (owner approval pending) |
| Residency justification, and whether any client commitment constrains it | §19 | ✅ Including the finding that **no** approved artifact commits a geography |
| The concrete product satisfying each capability, with exact versions | §5, §21 | ⚠ Partial — exact versions are `TBD-at-provisioning` by necessity |
| Confirmation the object store's expiry, deletion, and multipart-abort semantics satisfy `RRA-002` | §4.1, §7, §8 | ✅ Verified per provider from official docs |
| The recorded RTO and RPO | §21, §22 D7 | ❌ **Owner input required** — no value exists anywhere in the repository |
| The sizing values the rules require | §21.1 | ⚠ Rules restated in provider-neutral units; values require owner sizing + measurement |

Three items cannot be completed by analysis alone. Stating that is the point: DEC-008 fails closed,
and inventing an RTO or a machine size to make the table look finished would be exactly the false
precision it forbids.

---

## Appendix B — Sources

All fetched 2026-08-22. Official provider documentation only.

**DigitalOcean** — [Spaces availability](https://docs.digitalocean.com/products/spaces/details/availability/) ·
[Managed PostgreSQL features](https://docs.digitalocean.com/products/databases/postgresql/details/features/) ·
[PostgreSQL 17 availability](https://www.digitalocean.com/blog/postgresql-17) ·
[Scheduling automatic updates](https://docs.digitalocean.com/products/databases/postgresql/how-to/schedule-updates/) ·
[Managed database pricing](https://www.digitalocean.com/pricing/managed-databases) ·
[Static / dedicated egress IPs on App Platform](https://docs.digitalocean.com/products/app-platform/how-to/add-ip-address/)

**AWS** — [RDS engine version upgrades / `AutoMinorVersionUpgrade`](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_UpgradeDBInstance.Upgrading.html) ·
[App Runner product page](https://aws.amazon.com/apprunner/) (closure to new customers) ·
all rates from the **AWS Price List Bulk API**,
`https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/{service}/{version}/{region}/index.json`
— the official machine-readable source behind the JavaScript-rendered pricing pages. Offer-file
versions recorded at retrieval: RDS `20260820203529`, EC2 `20260821020257`, S3 `20260818181113`,
Fargate `20260707160651`, ECR `20251121153639`, Secrets Manager `20250828153804`, KMS
`20250828153913`. The human-facing
[RDS pricing page](https://aws.amazon.com/rds/postgresql/pricing/) returned no numbers when
fetched, which is why the Bulk API was used instead.

**Hetzner** — [Hetzner Cloud products](https://www.hetzner.com/cloud/) ·
[Object Storage overview](https://docs.hetzner.com/storage/object-storage/overview) ·
[Supported S3 actions](https://docs.hetzner.com/storage/object-storage/supported-actions/) ·
[Lifecycle policies](https://docs.hetzner.com/storage/object-storage/howto-protect-objects/manage-lifecycle/) ·
pricing from Hetzner's own live price feed at
`hetzner.com/_resources/app/data/app/live_data_prices.json` (the source its JavaScript-rendered
marketing pages read), cross-checked against the published June price-adjustment table to confirm
the plan→ID mapping and that the feed carries **net, ex-VAT** figures

**Internal (authoritative)** — `governance/decisions/KHEPRI-DEC-008-rra-portable-runtime-target.md` ·
`governance/registry.yaml` · `governance/CONSTITUTION.md` ·
`docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` §OPS1

---

OWNER DECISION REQUIRED

A. Approve the recommended primary provider and region.
B. Select one of the documented alternatives.
C. Request additional evidence before selection.

No provisioning or implementation is authorized by this analysis.
