<!-- Generated: 2026-09-27 | Files scanned: 310 | Token estimate: ~550 -->
# Dependencies

## External services
```
PostgreSQL 17        primary store (RDS in AWS; postgres:17.11-alpine local)
S3 / MinIO           uploads, fact packages, report artifacts (envelope-encrypted client-side)
SQS                  infra/data_resources.ReportQueues (queue + DLQ, CDK); runtime worker claims via DB leases (rra/claim_queue.py)
Clerk                external identity (runtime/clerk_identity.py, external_auth_api.py; hard stop CLI)
Chromium (baked)     PDF printing via Playwright, pinned in image (mcr.microsoft.com/playwright/python:v1.61.0-noble)
AWS (CDK v2)         infra/: network (no NAT/egress), database, compute (ECS x86_64), image digest pin
```
No LLM provider at runtime: narrative is `DeterministicNarrator` (rra/deterministic_narrative.py).

## Python runtime deps (pyproject.toml)
```
fastapi, uvicorn[standard], pydantic 2   web boundary (DEC-008: Pydantic at app boundary)
sqlalchemy 2, psycopg[binary] 3, alembic persistence + migrations
boto3/botocore                          S3 client
cryptography                            AES-GCM envelope encryption
polars, fastexcel                       tabular intake/profiling/facts
jinja2                                  HTML templates (shell, journey, reports)
playwright                              Chromium PDF render
xlsxwriter                              Excel surface
clerk-backend-api                       identity provider
pyyaml                                  governance registry
```
Dev: pytest, ruff, httpx2, pillow, pypdf · infra group: aws-cdk-lib. Locked with `uv.lock`; Python `>=3.13,<3.14`.

## Tooling / CI
```
uv (0.10.11 in image) · ruff (lint only in CI; don't mass-format) · pytest markers: browser, local_stack, concurrency
.github/workflows/governance.yml: khepri-gov validate · ruff check · pytest (+ require_concurrency/browser_tests guards) · benchmark_gate
.github/workflows/image.yml: OCI image build · CodeScene on PRs; local CodeRabbit step in PR template
```

## Internal shared modules
```
rra/semantic_views/*   published semantic view registry/contracts (consumed by runtime/semantic_view_adapter)
rca/semantic_queries/* query ports over workspace data
rra/renderable.py, rra/bundle.py   report bundle contract shared by all renderers
runtime/config.py      RuntimeSettings.from_environment()
```
