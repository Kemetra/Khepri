<div align="center">
  <img src="docs/assets/khepri-logo.png" alt="Khepri" width="520" />
  <h1>Khepri</h1>
  <p><strong>Governed retail intelligence, built on evidence.</strong></p>
</div>

Khepri turns retail CSV/XLSX data into reconciled Arabic/English analysis across web, PDF, and
Excel. Its product code is organized as small slices tied to explicit specifications, with one
fact package feeding every surface.

## Governance in one screen

Khepri has one repository owner and one machine-readable governance source:
[`governance/registry.yaml`](governance/registry.yaml).

- Work on a branch or pull request is proposed.
- The owner merging it to `main` is approval; Git records the content, identity, and time.
- Artifacts are either `active` or `retired`.
- Active product work must link to an active specification.
- `uv run khepri-gov validate` rejects malformed metadata, missing documents, unknown or cyclic
  dependencies, invalid family links, and broken supersession.

There are no approval packages, delegation records, digest renewals, or parallel authority ledger.
Their complete history remains available in Git. The governing rules are in
[`governance/CONSTITUTION.md`](governance/CONSTITUTION.md).

## Product boundary

The active families are:

| Family | Responsibility |
|---|---|
| `FND` | Repository governance and fail-closed validation |
| `RRA` | Retail intake, profiling, facts, bilingual narrative, reports, and operations |
| `RCA` | Commercial identity, organizations, workspaces, authorization, and related boundaries |

The active RRA specification chain covers invitations and sessions, file intake and deletion,
profiling, deterministic facts, grounded narrative, reconciled report surfaces, reliable
operations, comparative analysis, and business-first presentation. `RCA-001` defines commercial
identity and organization boundaries. The registry—not this summary—is authoritative.

Core product guarantees remain unchanged:

- one immutable fact package supplies every reported number;
- narratives receive approved aggregates and citations, not raw customer rows;
- Arabic and English carry the same facts, caveats, and disclosures;
- privacy, deletion, and isolation failures close rather than default;
- operational telemetry remains content-free.

## Repository map

| Path | Purpose |
|---|---|
| `governance/registry.yaml` | Authoritative artifact metadata and dependency graph |
| `governance/decisions/` | Architecture and boundary rationale |
| `governance/families/` | Product-family ownership boundaries |
| `governance/specifications/` | Active and retired implementation contracts |
| `src/khepri_gov/` | Minimal governance validator and CLI |
| `src/khepri/rra/` | Retail reporting product slices |
| `src/khepri/runtime/` | Web and worker runtime roles |
| `src/khepri/infra/` | AWS CDK infrastructure definition |
| `src/khepri/local/` | Local-only development wiring |
| `migrations/` | PostgreSQL schema migrations |
| `tests/` | Governance and product regression tests |

Files under `docs/superpowers/` and `specs/` are historical design and planning records. They are
useful context but never authoritative.

## Required checks

Khepri requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --frozen
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

CI runs validation, Ruff, pytest, the benchmark gate, image checks, and the server-side CodeScene
Code Health Review. The benchmark job certifies nothing while no benchmark declaration is supplied.

## Run locally

The local stack is development wiring, not a deployment or approval record.

```powershell
docker compose -f docker-compose.local.yml up -d
uv run alembic upgrade head
uv run python -m khepri.local.cli invite
uv run uvicorn khepri.local.app:app --reload
uv run python -m khepri.local.cli work
uv run python -m khepri.local.cli sweep
```

Local-stack and browser tests skip when their external prerequisites are unavailable. Deselect them
explicitly with `-m 'not local_stack and not browser'` when needed.

## Predecessor boundary

`Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` is immutable,
non-authoritative reference material. Khepri imports no predecessor governance, approval,
specification, catalog, ledger, history, or application tree.
