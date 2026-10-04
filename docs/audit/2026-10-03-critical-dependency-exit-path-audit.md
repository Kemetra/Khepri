# Khepri critical dependency and exit-path audit — 2026-10-03

- **Execution scope:** Jira `SCRUM-39`. Refs #631 and `SCRUM-37`, and closes neither.
- **Audited commit:** `93f242a7` (`main`, 2026-10-03). Every version below was read from `uv.lock`,
  `Dockerfile`, the compose files, or the CI build log of that commit.
- **Date checked:** 2026-10-03, for every external fact (PyPI, OSV, endoflife.date, the Python
  devguide, SQLAlchemy, GitHub, MCR, and the cryptography changelog).
- **Status:** advisory research, not a governed artifact. It approves nothing, records no
  approval, and authorizes no implementation. No dependency, product code, migration, CI, Jira item,
  or Confluence page was changed. Follow-ups are recommendations only. Identity, state, and
  supersession are authoritative in `governance/registry.yaml`.
- **Storage boundary:** `SCRUM-37` owns the comparison of MinIO, SeaweedFS, and Garage. This audit
  records only the storage risk and hands that comparison back to it.

## Rubric

Risk is severity weighted by exposure on a path Khepri actually runs. The gate it blocks is
recorded in a separate column.

| Risk | Meaning |
|---|---|
| **Critical** | A credible path to an unsafe or non-repeatable **local pilot**, as defined by `KHEPRI-DEC-031` (an internal rehearsal on the local stack). |
| **High** | A known, unresolved security or continuity defect on a path an external pilot or production would use. It must be resolved before that gate. |
| **Medium** | Real exposure with limited exploitability, or a gate already recorded in governance. Needs a bounded evaluation or refresh. |
| **Low** | Healthy, or worth watching only. |

**Migration difficulty:**

- **Low:** a lock refresh or configuration change within the existing contract.
- **Medium:** code or contract adaptation, bounded to one adapter.
- **High:** cross-cutting re-evidencing, such as rendering parity or a data migration.

**Gates:**

- **Local pilot:** the `KHEPRI-DEC-031` local-only M2 rehearsal.
- **External pilot:** the external alpha. It requires `KHEPRI-DEC-030` §6.
- **Production:** commercial operation.

## Result

**23 dependencies audited: 0 Critical, 2 High, 6 Medium, 15 Low.** There is also one cross-cutting
High finding, X1. It is a missing control, not a dependency.

**Nothing blocks the local pilot.** `SCRUM-35` and `SCRUM-36` are unaffected by this audit.

## Primary table

Evidence IDs (`E*`) resolve in [Evidence](#evidence).

| # | Dependency | Khepri role | Current status | Risk | Exit path / alternative | Migration difficulty | Recommended action | Pilot/production impact | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **MinIO server and `mc`**, built from source | S3 store in the local and staging stacks; the only store verified against `khepri.rra.storage` | **Upstream archived**: no security updates. Built by an EOL Go 1.24 toolchain. | **High** | Any S3 store that meets `RRA-002` (`SCRUM-37`: SeaweedFS or Garage; Spaces under row 2). The contract has no provider branch. | Low for the code; Medium for re-evidencing | **Evaluate** through `SCRUM-37`; do not duplicate it | Local: none (loopback-bound). External: must not be the store. Production: excluded. | E1, E2, E3, E9 |
| 2 | **DigitalOcean Spaces** | The hosted object store `KHEPRI-DEC-028` names | Selected but **conditional**. No empirical confirmation of the contract exists. | Medium | Rows 1 and 2 share one contract. Any confirmed S3 store substitutes without code. | Low for code; Medium for evidence | **Evaluate**. This is `KHEPRI-DEC-028`'s own follow-on obligation. | External: blocked until confirmed (`KHEPRI-DEC-030` §6). | E4 |
| 3 | **boto3 and botocore** 1.43.59, with transitive **urllib3** 2.7.0 | The S3 client for every object read and write | Active; AWS-maintained. urllib3 2.7.0 carries **3 advisories** (2 HIGH, 1 MODERATE), fixed in 2.8.0. | Medium | Any S3 SDK; the store sits behind ports. A refresh is enough. | Low: botocore admits `urllib3<3` | **Evaluate**: a lock refresh, plus a store round trip on a non-AWS endpoint | External: refresh first. Local: not blocking (trusted loopback endpoint). | E5, E6, E7 |
| 4 | **PostgreSQL 17**, `postgres:17.11-alpine` | The relational store, job queue, and RLS boundary | 17.11 is the latest 17.x minor (2026-08-10). 17 is supported to 2029-11-08. | Low | Standard `pg_dump`; DO Managed PostgreSQL 17 | Low | **No action**. Keep the minor-version check `KHEPRI-DEC-029` owns. | None | E8, E4 |
| 5 | **psycopg** 3.3.4 (binary) | The PostgreSQL driver | Active. 3.3.6 is current. **LGPL-3.0-only**. | Low | psycopg2 or asyncpg, behind SQLAlchemy | Medium | **Watch**: refresh with row 3. LGPL matters only if the image is ever distributed. | None | E5 |
| 6 | **Python 3.13** (python-build-standalone via uv) | The interpreter for every role | **Security-only** since 2026-10, EOL 2029-10. The image runs **3.13.12**; 3.13.16 is current. | Medium | 3.14 (EOL 2030-10). Bumping the uv pin moves the patch level. | Low for a patch; Medium for a minor (`KHEPRI-DEC-028` names 3.13) | **Evaluate**: a patch refresh via the uv pin | External: refresh first. Local: none. | E9, E10, E11 |
| 7 | **FastAPI** 0.141.1, **Starlette** 1.3.1, **Uvicorn** 0.52.0 | HTTP and the application boundary | All active. FastAPI is pre-1.0, so a minor can break. | Low | Starlette alone, or Litestar | High (26 modules import FastAPI) | **Watch** FastAPI minor changes | None | E5 |
| 8 | **Pydantic** 2.13.4 | The boundary schemas (`KHEPRI-DEC-028`) | Active. 2.13.5 is current. | Low | msgspec or dataclasses | Medium | **No action** | None | E5 |
| 9 | **SQLAlchemy** 2.0.51 | ORM and Core persistence (45 modules) | **2.0 is now "Maintenance"**. 2.1 became current on 2026-09-24. The range `<3` admits 2.1 on any re-lock. | Low | 2.1, the vendor's path | Medium | **Watch**: review any re-lock that crosses into 2.1 | None now; plan before 2.0 reaches EOL | E5, E12 |
| 10 | **Alembic** 1.18.5 | Schema migrations | Active. 1.20.0 is current. | Low | None needed | — | **No action** | None | E5 |
| 11 | **Polars** 1.43.1, with **fastexcel** 0.20.2 (calamine) | CSV/XLSX materialization, profiling, KPI preparation | Both active. fastexcel is a smaller project (ToucanToco). | Low | Polars' openpyxl engine, as an XLSX fallback | Low for the engine; High for leaving Polars | **Watch** fastexcel | None | E5, E13 |
| 12 | **Jinja2** 3.1.6 | Server-side rendering of web, report, and evidence surfaces | Active (Pallets). Latest release 2025-03-05. | Low | None needed | — | **No action** | None | E5 |
| 13 | **XlsxWriter** 3.2.9 | The Excel report artifact | Active; one maintainer. Latest release 2025-09-16. | Low | openpyxl | Medium (artifact parity) | **Watch** | None | E5, E13 |
| 14 | **Playwright** 1.61.0, bundled **Chromium 149.0.7827.55**, base `playwright/python:v1.61.0-noble` | HTML-to-PDF rendering inside the pinned image | Active (Microsoft). Playwright 1.63.0 ships Chromium 153. The image's browser is **4 majors behind**. The base is pinned by tag, not digest. Ubuntu 24.04 is supported to 2029-05. | Medium | A newer Playwright; WeasyPrint as a last resort (no JS; a fidelity change) | **High**: bilingual RTL PDF parity and environment-digest re-evidencing | **Evaluate**: a refresh cadence, and digest-pinning the base | External: refresh first. Local: none (no egress; renders Khepri's own templates). | E9, E14, E15 |
| 15 | **uv** 0.10.11 (lock, sync, interpreter download; `ghcr.io/astral-sh/uv`) | Build and lock toolchain; it chooses the image's Python patch | Active. 0.12.23 is current. The pin is **6.5 months old** (2026-03-17) and by tag. Astral's acquisition by OpenAI was announced 2026-03-19 (news-reported). | Low | `uv export` to `requirements.txt` with pip; Apache-2.0 and forkable | Low | **Watch** | None (build-time only) | E9, E16, E17 |
| 16 | **Job processing**: PostgreSQL claim and redrive | Report-worker delivery | In-repo code (`SELECT … FOR UPDATE SKIP LOCKED`). No broker, no third-party queue. | Low | Not applicable: the risk reduces to row 4 | — | **No action** | None | E4, E18 |
| 17 | **Clerk** (SaaS) and **clerk-backend-api** 7.0.0 | External identity proof for the hosted private beta only. `khepri.local` has 0 Clerk references; the local pilot uses Khepri-native invitations. | The SDK is active (MIT). Clerk is **commercially unadmitted**: provisional, on educational access, behind a hard stop. | Medium | `KHEPRI-DEC-024` §13 exit paths. Khepri owns authority and the `(provider, subject)` link table. The `IdentityProvider` seam returns only `VerifiedIdentity`. | Medium (re-link every account to a new provider) | **Watch** the hard-stop triggers | External: allowed under `KHEPRI-DEC-025`. **Production: admission or replacement required.** | E19, E20 |
| 18 | **PyJWT** 2.13.0, transitive via clerk-backend-api | Verifies the RS256 signature of every Clerk session token | **13 advisories** published 2026-09-29/30: 1 CRITICAL, 5 HIGH, 7 MODERATE. Fixed in 2.14.0 and 2.15.0. | **High** | Refresh within clerk's `pyjwt<3,>=2.9` | Low | **Evaluate**: lock refresh to ≥ 2.15.0, then re-run the Clerk tests | **External: must refresh first.** Local: none (not on the local path). | E6, E19, E21 |
| 19 | **cryptography** 50.0.0 | AES-256-GCM envelope encryption (`khepri.rra.envelope`) | Active (PyCA). No OSV advisory on 50.0.0. 50.0.1 and 50.0.2 rebuild against newer OpenSSL 4.0.x patches. Capped `<51` here and by clerk. | Low | None needed. The primitive is standard AES-GCM. | Low | **Watch**: take 50.0.x with row 3 | None | E5, E6, E22 |
| 20 | **Envelope master key** (`KHEPRI_STORAGE_MASTER_KEY`) | Wraps every object's data key | A single 32-byte key. The envelope header carries **no key identifier**. The provisioning, rotation, and escrow path is undefined (already recorded by G2-01). | Medium | A key-ID-bearing envelope format (`v3`) or a full re-seal, under `KHEPRI-DEC-028`'s format rules | Medium | **Evaluate**: a rotation and escrow procedure | **Production**: required. External: recommended. | E23, E24, E25 |
| 21 | **DigitalOcean platform** (App Platform, Managed PostgreSQL, DOCR) | The selected hosted target, unprovisioned (`KHEPRI-DEC-031`) | Not exercised. The contract is portable: an OCI image, PostgreSQL 17, and S3. | Low | Any OCI runtime with PostgreSQL 17 and S3 (`KHEPRI-DEC-028` capability rows) | Medium | **Watch** | Governed by `KHEPRI-DEC-030` §6 | E4 |
| 22 | **OpenAI** narrative provider | Optional narrative adapter | **Withheld.** `DeterministicNarrator` is the live path, so it is not required by any journey. | Low | The deterministic, facts-only narrative is the default | — | **No action** | None | E26 |
| 23 | **Better Stack** OTLP | Hosted observability named by `KHEPRI-DEC-028` | **Unbuilt**: no OTLP code in `src/` or `pyproject.toml`. | Low | Any OTLP backend | Low | **No action** | Hosted only | E4 |

### Cross-cutting finding

| # | Control | Status | Risk | Recommended action | Impact | Evidence |
|---|---|---|---|---|---|---|
| X1 | **Advisory detection for dependencies and images** | No scan runs anywhere. The only image scan is ECR scan-on-push. On `main` that job prints `NOT PUBLISHED: missing KHEPRI_ECR_REPOSITORY …`, and the registry `KHEPRI-DEC-028` targets is DOCR, not ECR. Dependabot alerts are disabled. The 2026-08-17 `osv-scanner` recommendation was never actioned. | **High** | **Evaluate**: a pre-merge `osv-scanner` (or equivalent) on `uv.lock`, plus an image scan that does not depend on ECR | **External: resolve first.** This control is why the advisories in rows 3 and 18 were found only by this audit. | E27, E28, E29 |

## High findings

### H1: PyJWT 2.13.0 (row 18)

- **What is at risk:** Khepri's only external authentication path, the hosted private-beta Clerk
  sign-in.
- **Exact reason:** the locked PyJWT has 13 published advisories. An applicability read of the
  installed `clerk_backend_api/security/verifytoken.py` and of `runtime/clerk_identity.py` finds:
  - **Not applicable to this configuration:**
    - **The HMAC path:** the CRITICAL `GHSA-ffc3-869f-jxw9`, and `GHSA-p4g4-x82p-q773`,
      `GHSA-w2cx-738m-mc7w`, `GHSA-9j54-fg26-wv3r` and `GHSA-r6x4-923q-g947`. Each needs an HMAC
      algorithm in the allow-list or HMAC key preparation. Clerk passes `algorithms=['RS256']`,
      and Khepri refuses any header whose `alg` is not `RS256` or whose `kid` is not the pinned
      one.
    - **Options reuse:** `GHSA-gvp8-978c-rx2q` needs a reused options dict. Clerk passes a fresh
      literal on every call.
    - **The JWKS path:** `GHSA-9v7f-9g4p-ffgj`, `GHSA-2gx3-rcp4-g85q`, `GHSA-42vr-xj54-vc7v` and
      `GHSA-w6j9-cwv2-h6wq` concern PyJWKClient or JWK Sets. A `jwt_key` is configured, so an
      `InvalidSignatureError` re-raises and never reaches `_get_remote_jwt_key`.
    - **Attacker-supplied keys:** `GHSA-jwrc-g2q2-pq5p` needs an attacker-supplied PEM. The key
      is configuration.
    - **Raw-token revocation:** `GHSA-hxm8-2xgr-2p9m` affects revocation keyed by the raw token.
      Khepri mints its own server-side session and keeps no revocation list keyed by Clerk
      tokens. This was read from the code, not tested.
  - **Reachable in principle:** the DoS class, `GHSA-8wjv-2p76-3863` (RecursionError on a deeply
    nested header). Khepri's own pre-parse is reached first; see observation O2.
  - **Not tested:** this applicability is read from the code, not exercised. An authentication
    library pinned below 13 published fixes is not acceptable on an external path, whatever the
    read says.
- **Minimum corrective action:** a lock-only refresh to `pyjwt>=2.15.0`. clerk-backend-api 7.0.0
  admits `<3`. Then re-run the Clerk identity tests.
- **What becomes safe afterward:** the Clerk path carries no known PyJWT advisory. The
  `KHEPRI-DEC-025` preconditions for external admission are no longer undercut by a stale
  transitive dependency.

### H2: MinIO is archived; no maintained store is verified (row 1)

- **What is at risk:** continuity of object storage on every path beyond the local pilot.
- **Exact reason:**
  - The only S3 implementation verified against `khepri.rra.storage` is MinIO.
  - MinIO is archived upstream: both GitHub repositories are archived, and the binaries return
    410.
  - Khepri builds it from a pinned tag, with Go 1.24.13, which reached EOL on 2026-02-10. It
    receives no security fixes.
  - The hosted candidate, Spaces, is unconfirmed (row 2). The maintained alternatives are
    unevaluated (`SCRUM-37`).
  - The staging init also prints that this MinIO does not support incomplete-multipart cleanup.
- **Minimum corrective action:**
  - Complete `SCRUM-37`'s evaluation.
  - Complete `KHEPRI-DEC-028`'s Spaces verification against the same contract.
  - Neither belongs in this audit.
- **What becomes safe afterward:** a storage selection for the external pilot can rest on evidence.
  MinIO can stay a local-only substitute or be retired.
- **Why the local pilot is not blocked:**
  - #645 made clean-machine startup work.
  - Both stacks bind MinIO to `127.0.0.1`.
  - The local rehearsal is internal by definition (`KHEPRI-DEC-031` §2).

### X1: No advisory detection executes

- **What is at risk:** every dependency row. Advisories go unseen until someone audits by hand.
- **Exact reason:**
  - `image.yml`'s publish job gates on three ECR variables, all unset. Its scan therefore never
    runs; the `main` run 37147801127 logs `NOT PUBLISHED`.
  - The ECR path belongs to the retired AWS target, while `KHEPRI-DEC-028`'s registry is DOCR.
  - Dependabot alerts are disabled (the GitHub API returns `403`).
- **Minimum corrective action:** a CI check that queries OSV, or an equivalent advisory source,
  for `uv.lock` on pull requests and on a schedule. Add an image scan that does not require a
  registry push. This is a CI change, so it needs its own slice.
- **What becomes safe afterward:**
  - Rows 3, 18, and 19 are maintained by signal, not by audit.
  - The pre-external-pilot refreshes stay current after they land.

## Findings by category

### A. Healthy / no action

- PostgreSQL 17 (row 4).
- Pydantic (row 8).
- Alembic (row 10).
- Jinja2 (row 12).
- The PostgreSQL job queue (row 16).
- The OpenAI adapter (row 22): withheld by design.
- Better Stack (row 23): unbuilt.

### B. Watch list

- **psycopg (row 5):** patch lag; LGPL applies only if the image is distributed.
- **FastAPI (row 7):** pre-1.0 minor releases.
- **SQLAlchemy (row 9):** 2.0 is in maintenance, and `<3` silently admits 2.1.
- **fastexcel (row 11).**
- **XlsxWriter (row 13):** one maintainer.
- **uv (row 15):** a stale pin, and the change of ownership.
- **Clerk hard-stop triggers (row 17).**
- **cryptography (row 19):** OpenSSL rebuilds, and the `<51` cap.
- **DigitalOcean (row 21).**

### C. Needs bounded evaluation

| Row | Evaluation | Owner or vehicle |
|---|---|---|
| 1, 2 | A maintained S3 store, and Spaces confirmation, against the existing contract | `SCRUM-37`; `KHEPRI-DEC-028`'s follow-on obligation |
| 3, 5, 18, 19 | One lock refresh: pyjwt, urllib3, boto3/botocore, psycopg, and cryptography 50.0.x, holding SQLAlchemy at 2.0 | Follow-up F1 |
| 6, 14, 15 | An image refresh: the uv pin (and with it the Python patch), and Playwright with Chromium, with the base digest-pinned | Follow-up F3 |
| 20 | A master-key rotation and escrow procedure | Follow-up F4 |
| X1 | Advisory detection in CI | Follow-up F2 |

### D. Must be resolved before the external pilot or production

**Before the external pilot:**

- H1, the PyJWT refresh (F1).
- urllib3 2.8.0 (F1).
- X1, advisory detection (F2).
- Storage, H2 and row 2: these were already gated by `KHEPRI-DEC-030` §6 and `SCRUM-37`.
- **Recommended:** the Python and Chromium patch refreshes (F3). They are Medium, not High,
  because neither has a confirmed exploitable path in Khepri's use.

**Before production:**

- **Clerk** commercial admission, or a replacement (`KHEPRI-DEC-025` §5).
- A master-key rotation and escrow procedure (F4).
- A plan for SQLAlchemy 2.1 before 2.0 reaches EOL.

### E. Critical findings that block the local pilot

**None.** Every High item sits on the hosted path or concerns the storage choice beyond loopback:

- Clerk and PyJWT have no references in `khepri.local`.
- MinIO builds, passes the #645 contract checks, and is bound to loopback.

## Adjacent observations (recorded, not acted on)

- **O1. The runtime image installs the `infra` group.**
  - `default-groups = ["dev", "infra"]` holds, and `uv sync --frozen --no-dev` removes only `dev`.
  - A dry run of the Dockerfile's sync on `93f242a7` reports
    `+ aws-cdk-lib==2.262.2 … + jsii==1.139.0` among 59 packages.
  - This contradicts the `pyproject.toml` comment that infrastructure tooling "has no business
    inside" the image.
  - It is a dry run, not an inspection of a built image.
  - The minimal fix is `--no-default-groups` or `--only-group`. That is a Dockerfile change, so it
    needs its own slice.
- **O2. `clerk_identity._has_pinned_header` can raise an uncaught `RecursionError`.**
  - It calls `json.loads` on the attacker-supplied token header and catches only
    `UnicodeDecodeError` and `ValueError`.
  - On deeply nested JSON, CPython raises `RecursionError`, which subclasses neither. This was
    verified locally.
  - It was not exercised against the route, so whether it surfaces as a `500` is unverified.
  - It is the same input class as `GHSA-8wjv-2p76-3863`, and it is Khepri code, not a dependency.
- **O3. Stale wording in the `Dockerfile`.**
  - It calls the uv image tag "digest-bearing", but the tag is not a digest.
  - It cites the retired `KHEPRI-DEC-007` for the Chromium pin. `KHEPRI-DEC-029` now holds
    `environment_digest`.
- **O4. Dev-only advisories.**
  - `httpx2` and `httpcore2` 2.9.1, `pypdf` 6.14.2, and `pytest` 8.4.2 carry OSV advisories.
  - They are in the `dev` group, which the image's `--no-dev` sync excludes. They affect only
    developer and CI machines.

## Recommended bounded follow-ups (not created, not implemented)

| ID | Follow-up | Gate it serves | Size |
|---|---|---|---|
| F1 | A lock-only refresh: `pyjwt>=2.15.0`, `urllib3>=2.8.0`, current botocore/boto3, psycopg, and cryptography 50.0.x. Hold `sqlalchemy<2.1`. Then the full suite and a store round trip on the local stack. | External pilot | Small |
| F2 | Advisory detection in CI: OSV on `uv.lock` per PR and weekly, and an image scan that needs no ECR | External pilot | Small (a CI slice) |
| F3 | An image refresh: bump the uv pin (Python ≥ 3.13.16), Playwright and Chromium with its base, digest-pin the base, re-evidence the bilingual PDF | External pilot (recommended) | Medium |
| F4 | A master-key rotation and escrow procedure, and whether `v3` needs a key identifier | Production | Medium; owner decision |
| F5 | O1, O2, and O3 as one hygiene slice: Dockerfile sync groups, the header-parse guard, and the comments | Before the external pilot (O2) | Small |

Storage needs no new item: it is `SCRUM-37` together with `KHEPRI-DEC-028`'s Spaces obligation.

## Evidence

All checks were made on 2026-10-03.

| ID | Source | Finding |
|---|---|---|
| E1 | `gh api repos/minio/minio`, `repos/minio/mc` | `archived=true`, `license=AGPL-3.0` for both |
| E2 | #631 and its comment; `ops/minio/minio-from-source.Dockerfile` | Binaries return 410 Gone; source-only distribution; built from tag `RELEASE.2025-09-07T16-13-09Z` @ `07c3a42`; golang `1.24.13`, debian `12.15-slim`, both digest-pinned |
| E3 | `docker-compose.local.yml`, `docker-compose.staging.yml` | MinIO bound to `127.0.0.1`; staging init prints `incomplete-multipart cleanup: unsupported by this MinIO` |
| E4 | `KHEPRI-DEC-028` (§Target selection, §Follow-on obligations), `KHEPRI-DEC-030` §6, `KHEPRI-DEC-031` | Spaces "Conditional"; PG 17 minor-version check; DOCR registry; Better Stack OTLP; claim-and-redrive; no provisioning |
| E5 | `uv.lock`; PyPI JSON `pypi.org/pypi/<pkg>/json` | Locked versus latest versions, release dates, and licences as in the table |
| E6 | OSV `api.osv.dev/v1/querybatch` over all 72 locked packages | 6 packages with advisories: pyjwt (13), urllib3 (3), httpx2, httpcore2, pypdf, pytest. None on cryptography 50.0.0. |
| E7 | botocore 1.43.59 `requires_dist` | `urllib3!=2.2.0,<3,>=1.25.4` |
| E8 | `endoflife.date/api/postgresql.json` | 17: latest 17.11 (2026-08-10), EOL 2029-11-08 |
| E9 | CI run 37147801127 (`image`, `main`, `93f242a7`) build log | `python 3.13.12`, `chromium 149.0.7827.55`; publish job `NOT PUBLISHED: missing KHEPRI_ECR_REPOSITORY KHEPRI_AWS_REGION KHEPRI_PUBLISH_ROLE_ARN` |
| E10 | `devguide.python.org/versions` | "3.13 \| PEP 719 \| security \| 2024-10-07 \| 2029-10" |
| E11 | `endoflife.date/api/python.json` | 3.13 latest 3.13.16 (2026-09-30) |
| E12 | `sqlalchemy.org/download.html`; PyPI | 2.1 "Current Release" (2.1.0 on 2026-09-24); 2.0 "Maintenance" |
| E13 | `gh api repos/ToucanToco/fastexcel`, `repos/jmcnamara/XlsxWriter` | Not archived; last pushes 2026-09-21 and 2026-08-04 |
| E14 | `gh api repos/microsoft/playwright/releases/tags/v1.61.0`, `v1.63.0` | Chromium 149.0.7827.55 (2026-06-15); Chromium 153.0.8010.12 (2026-09-04) |
| E15 | `mcr.microsoft.com/v2/playwright/python/tags/list`; `endoflife.date/api/ubuntu/24.04.json` | `v1.62.0-noble` and `v1.63.0-noble` exist; Noble supported to 2029-05-31 |
| E16 | `gh api repos/astral-sh/uv/releases/tags/0.10.11`, `/releases/latest` | 0.10.11 released 2026-03-17; latest 0.12.23 |
| E17 | The New Stack, The Register (2026-03-19), JetBrains blog | OpenAI announced its acquisition of Astral; news-reported, not from a primary source |
| E18 | `src/khepri/runtime/worker.py` docstring; `KHEPRI-DEC-028` §Job delivery | PostgreSQL claim and redrive; no broker |
| E19 | `src/khepri/runtime/clerk_identity.py`; installed `clerk_backend_api/security/verifytoken.py` | `_ALGORITHM = "RS256"`; `algorithms=['RS256']`; with `jwt_key` set, `InvalidSignatureError` re-raises; `grep -rli clerk src/khepri/local` returns 0 |
| E20 | `KHEPRI-DEC-025` §§1, 2, 5 | Provisional admission; educational-access hard stop; no commercial admission |
| E21 | `api.osv.dev/v1/vulns/<id>` for the 13 PyJWT IDs; PyPI `clerk-backend-api` 7.0.0 | Severities and fixed versions as in H1; requires `pyjwt<3.0.0,>=2.9.0` and `cryptography<51.0.0,>=45.0.0` |
| E22 | `cryptography.io/en/latest/changelog/` | 50.0.1 (2026-08-25) and 50.0.2 (2026-09-30) are wheel rebuilds against newer OpenSSL 4.0.x |
| E23 | `src/khepri/rra/envelope.py` | `MASTER_KEY_BYTES = 32`; header = version, wrap nonce, content nonce, wrapped key; no key identifier |
| E24 | `docs/superpowers/specs/2026-09-03-g2-01-retained-data-inventory.md` | "The envelope master key's provisioning and rotation path" could not be determined |
| E25 | `KHEPRI-DEC-033` retention table; `KHEPRI-DEC-028` §Object storage control | Report artifacts kept with their run while the organization exists; key custody accepted as weaker than a KMS |
| E26 | `KHEPRI-DEC-026` §Context | `DeterministicNarrator` is what `wiring.py` selects; the provider is withheld |
| E27 | `.github/workflows/image.yml` | Scan only through `aws ecr describe-image-scan-findings`, after a push gated on ECR variables |
| E28 | `gh api repos/{owner}/{repo}/dependabot/alerts` | `403 Dependabot alerts are disabled for this repository` |
| E29 | `docs/khepri-dependency-scan.md` (2026-08-17) | Recommends `osv-scanner` because "`image.yml` scan skips pull requests" |

## Reproducing this audit

Run these from a checkout of `93f242a7`.

```bash
# Locked versions
python -c "import tomllib;l=tomllib.load(open('uv.lock','rb'));print({p['name']:p['version'] for p in l['package'] if 'version' in p})"
# Advisories for every locked package
python - <<'EOF'
import json, tomllib, urllib.request
l = tomllib.load(open('uv.lock', 'rb'))
qs = [{"package": {"name": p['name'], "ecosystem": "PyPI"}, "version": p['version']}
      for p in l['package'] if 'version' in p]
r = urllib.request.Request("https://api.osv.dev/v1/querybatch",
                           data=json.dumps({"queries": qs}).encode(),
                           headers={"Content-Type": "application/json"})
for q, res in zip(qs, json.load(urllib.request.urlopen(r))['results']):
    if res.get('vulns'):
        print(q['package']['name'], q['version'], [v['id'] for v in res['vulns']])
EOF
# Lifecycle
curl -s https://endoflife.date/api/python.json
curl -s https://endoflife.date/api/postgresql.json
# Upstream status
gh api repos/minio/minio --jq .archived
gh api repos/microsoft/playwright/releases/tags/v1.61.0 --jq .body | grep Chromium
# What the image's sync installs (O1)
UV_PROJECT_ENVIRONMENT=/tmp/khepri-audit-venv uv sync --frozen --no-dev --no-install-project --dry-run
# Image facts and the unpublished scan (E9)
gh run view 37147801127 --log | grep -E "python 3\.13|chromium [0-9]|NOT PUBLISHED: missing"
```
