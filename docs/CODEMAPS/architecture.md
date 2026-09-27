<!-- Generated: 2026-09-27 | Files scanned: 310 | Token estimate: ~800 -->
# Architecture

Python 3.13 monolith, one OCI image, two roles (web, worker). Bilingual (ar/en) governed retail analytics.
Authority lives in `governance/registry.yaml` (decisions, families, specs) — not in code comments.

## Packages (src/)
```
khepri/rra/      Retail analysis: intake → profiling → facts → narrative → render   (~40k LOC)
khepri/rca/      Identity: accounts, orgs, memberships, sessions, invitations, workspace (~13k)
khepri/runtime/  Deployed composition: wiring, web/worker entry, /app shell, landing, legal (~10k)
khepri/infra/    AWS CDK v2 stacks (dev group "infra", not in image)                   (~1.4k)
khepri/local/    Local dev wiring + CLI (EXCLUDED from wheel/image)                    (~0.9k)
khepri_gov/      `khepri-gov` registry/governance validator                            (~0.4k)
```

## Roles & entry points
```
web     uvicorn khepri.runtime.web:app       → wiring.build_web_app(build_stack(RuntimeSettings))
worker  python -m khepri.runtime.worker      → ClaimWorkerLoop → rra.ReportWorker → ReportPipeline
migrate alembic upgrade head                 (migrations/versions, 34 revisions)
cli     khepri-gov | khepri-clerk-hard-stop | khepri-retention-sweep
local   uvicorn khepri.local.app:app / khepri.local.cli (editable install only)
```
Dockerfile sets no CMD on purpose — compose/ECS choose the role.

## Data flow
```
CSV/XLSX ─► POST /beta/uploads ─► rra.intake (S3 envelope-encrypted object)
         ─► rra.admission/mapping ─► rra.profiling ─► rra.facts ─► immutable FactPackage
POST /beta/reports ─► rra_report_jobs ─► worker claims (lease) ─► ReportPipeline
     DeterministicNarrator ─► renderers {HTML, PDF (Chromium), Excel} ─► delivery + artifacts (S3)
/app shell ─► runtime.shell_* ─► rca.workspace (runs, versions, pins, provenance, decisions)
```
Invariant: facts computed once; renderers select, never recalculate. Narrative sees aggregates only.

## Boundaries
- FND = governance (`governance/`, `khepri_gov`) · RRA = `khepri/rra` · RCA = `khepri/rca`
- `runtime/` is the only layer that imports both RRA and RCA (composition root = `runtime/wiring.py`).
- Isolation: every read keyed by `owner_id` via `rca_isolation_scopes`; org switching via session.

## Environments
local: docker-compose.local.yml (postgres 17, minio) · staging: docker-compose.staging.yml
(postgres TLS, minio, migrate, web, worker) · AWS: infra/app.py → RraEnvironmentStack ×2 (beta, benchmark)
