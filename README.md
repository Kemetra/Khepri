<div align="center">
  <img
    src="docs/assets/khepri-logo.png"
    alt="Khepri — golden scarab and Egyptian governance mark"
    width="520"
  />

  <h1>Khepri</h1>

  <p><strong>Governed retail intelligence, built on evidence.</strong></p>

  <p>
    Kemetra's authoritative platform repository for turning retail data into grounded,
    bilingual decisions—without sacrificing numerical integrity, privacy, or traceability.
  </p>

  <p>
    <a href="governance/CONSTITUTION.md">
      <img
        alt="Governance: fail-closed"
        src="https://img.shields.io/badge/governance-fail--closed-B45309?style=flat-square&amp;labelColor=0F172A"
      />
    </a>
    <a href="governance/registries/">
      <img
        alt="Beta launch: not authorized"
        src="https://img.shields.io/badge/beta_launch-not_authorized-64748B?style=flat-square&amp;labelColor=0F172A"
      />
    </a>
    <a href="pyproject.toml">
      <img
        alt="Python 3.13"
        src="https://img.shields.io/badge/python-3.13-3776AB?style=flat-square&amp;labelColor=0F172A&amp;logo=python&amp;logoColor=white"
      />
    </a>
    <a href="uv.lock">
      <img
        alt="Dependencies: uv, locked"
        src="https://img.shields.io/badge/uv-locked-DE5FE9?style=flat-square&amp;labelColor=0F172A&amp;logo=uv&amp;logoColor=white"
      />
    </a>
    <a href="LICENSE">
      <img
        alt="Apache 2.0 license"
        src="https://img.shields.io/badge/license-Apache_2.0-475569?style=flat-square&amp;labelColor=0F172A"
      />
    </a>
  </p>
</div>

---

## What Khepri is

Khepri is a governance-first platform. Before application code is admitted, the repository
defines who has authority, what is approved, which evidence supports it, how dependencies are
ordered, and which controls may never be bypassed.

Its first active product family is
[RRA — Retail Reporting Automation](governance/families/RRA.md): an invite-only private beta
designed to transform a client's CSV or XLSX retail data into one reconciled Arabic/English
analysis bundle across web, PDF, and Excel.

```text
Invitation → governed upload → validated retail facts → grounded bilingual narrative
           → one reconciled web / PDF / Excel report bundle
```

That flow is the approved product contract—not a claim that the application is already
launched.

## The trust model

Khepri is designed around five non-negotiable properties:

- **One source of numbers.** An immutable `FactPackage` supplies every narrative, chart, PDF,
  and workbook figure.
- **Grounded language.** Narrative providers receive approved aggregates, safe labels, caveats,
  and citation identifiers—never raw customer rows.
- **Arabic/English parity.** Both languages carry equal facts, caveats, citations, and
  automatic-report disclosure.
- **Fail-closed governance.** Unknown states, stale digests, missing dependencies, partial
  materialization, and ambiguous approval evidence block progress.
- **Measured operations.** Validation, profiling, KPI calculation, narrative, rendering,
  storage, and delivery are timed independently without logging customer content.

Badges here are deliberately static. A status badge this repository cannot authenticate would
render as a broken or misleading claim, and a claim nothing verifies is exactly what the
governance model exists to reject.

## Current governed status

| Area | State | Meaning |
|---|---|---|
| Governance kernel | **Verified** | [FND-001](governance/specifications/FND-001.md) authority, registries, validation, and evidence controls are active |
| Selective predecessor transfer | **Accepted** | All 42 pinned references have Khepri-owned technical dispositions |
| Atomic approval packages | **Accepted** | Digest-locked, dependency-closed approval can be materialized mechanically |
| RRA product family | **Active** | The private-beta family boundary is authorized |
| RRA-001 through RRA-007 | **Approved** | Invitations, intake, profiling, facts, narrative, reports, and operations are specified |
| Product application | **In bounded slices** | Every approved specification has implementation slices, wired into the two governed runtime roles and exercised end to end on the local stack |
| Infrastructure definition | **Defined, not deployed** | [`src/khepri/infra/`](src/khepri/infra/) defines the beta and benchmark environments as one CDK application under [KHEPRI-DEC-007](governance/decisions/KHEPRI-DEC-007-rra-infrastructure-sizing.md); nothing is provisioned, and [KHEPRI-DEC-008](governance/decisions/KHEPRI-DEC-008-rra-portable-runtime-target.md) proposes freezing this path |
| Pinned OCI image | **Built, not published** | Every relevant change builds the image and verifies it as the non-root user that runs it; publishing reports `NOT PUBLISHED` until a registry is configured |
| Benchmark evidence | **Not certified** | [KHEPRI-DEC-006](governance/decisions/KHEPRI-DEC-006-rra-benchmark-workload.md) is accepted, but no approved workload has been executed and the CI gate certifies nothing |
| Beta launch | **Not authorized** | Client count and observation period require separate human authorization |

The authoritative state is always in
[`governance/registries/`](governance/registries/), not in this table.

## Approved specification chain

| Specification | Contract |
|---|---|
| [FND-001](governance/specifications/FND-001.md) | Governance kernel, registry schema, and repository controls |
| [RRA-001](governance/specifications/RRA-001.md) | Single-use invitations, consent, opaque ownership, and isolated sessions |
| [RRA-002](governance/specifications/RRA-002.md) | CSV/XLSX intake, validation, 50 MB limit, retention, and deletion |
| [RRA-003](governance/specifications/RRA-003.md) | Profiling, quality findings, semantic mapping, and fail-closed admissibility |
| [RRA-004](governance/specifications/RRA-004.md) | Deterministic retail KPIs, comparisons, reconciliation, and provenance |
| [RRA-005](governance/specifications/RRA-005.md) | Grounded Arabic/English narrative with minimized provider inputs |
| [RRA-006](governance/specifications/RRA-006.md) | One fact package rendered consistently to web, PDF, and Excel |
| [RRA-007](governance/specifications/RRA-007.md) | Idempotent jobs, recovery, deletion evidence, telemetry, and beta controls |

## Accepted decisions

| Decision | Boundary it fixes |
|---|---|
| [KHEPRI-DEC-001](governance/decisions/KHEPRI-DEC-001-successor-reference-policy.md) | Khepri authority and the predecessor reference policy |
| [KHEPRI-DEC-002](governance/decisions/KHEPRI-DEC-002-selective-transfer-protocol.md) | Selective predecessor assessment and re-specification |
| [KHEPRI-DEC-003](governance/decisions/KHEPRI-DEC-003-rra-private-beta.md) | The RRA private-beta boundary |
| [KHEPRI-DEC-004](governance/decisions/KHEPRI-DEC-004-atomic-approval-packages.md) | Atomic approval packages and bounded implementation authority |
| [KHEPRI-DEC-005](governance/decisions/KHEPRI-DEC-005-rra-runtime-architecture.md) | Runtime, provider, and deployment boundary |
| [KHEPRI-DEC-006](governance/decisions/KHEPRI-DEC-006-rra-benchmark-workload.md) | The beta benchmark workload and its environment |
| [KHEPRI-DEC-007](governance/decisions/KHEPRI-DEC-007-rra-infrastructure-sizing.md) | Private-beta and benchmark infrastructure sizing |

[KHEPRI-DEC-008](governance/decisions/KHEPRI-DEC-008-rra-portable-runtime-target.md) is
**proposed**, not accepted, and is listed separately for that reason. It would supersede
KHEPRI-DEC-005 and KHEPRI-DEC-007, replacing the provider-specific deployment path with a target
capability contract and freezing [`src/khepri/infra/`](src/khepri/infra/) as reference. Its
registry entry carries no approval evidence, so it grants no authority and nothing in the table
above changes until it does.

## Repository map

| Path | Purpose |
|---|---|
| [`governance/CONSTITUTION.md`](governance/CONSTITUTION.md) | Repository authority and non-negotiable operating rules |
| [`governance/registries/`](governance/registries/) | Machine-readable source of truth for identity, state, dependencies, and approval |
| [`governance/authorities/`](governance/authorities/) | People who may own or approve an artifact |
| [`governance/families/`](governance/families/) | Product-family boundaries |
| [`governance/decisions/`](governance/decisions/) | Decision context, boundaries, and consequences |
| [`governance/specifications/`](governance/specifications/) | Approved product contracts and acceptance boundaries |
| [`governance/approvals/`](governance/approvals/) | Durable bootstrap and digest-locked package evidence |
| [`governance/benchmarks/`](governance/benchmarks/) | Approved benchmark declarations and their environments |
| [`governance/reference-reviews/`](governance/reference-reviews/) | Bounded review evidence for the pinned predecessor |
| [`governance/templates/`](governance/templates/) | The minimum review shape every governed document must satisfy |
| [`src/khepri_gov/`](src/khepri_gov/) | Fail-closed governance validator and digest tooling |
| [`src/khepri/rra/`](src/khepri/rra/) | Specification-linked RRA implementation slices |
| [`src/khepri/runtime/`](src/khepri/runtime/) | The two governed runtime roles the pinned image serves: web and worker |
| [`src/khepri/infra/`](src/khepri/infra/) | The beta and benchmark environments as one AWS CDK application |
| [`src/khepri/local/`](src/khepri/local/) | Local development wiring and operator commands; excluded from the built wheel |
| [`migrations/`](migrations/) | Alembic migrations for the authoritative PostgreSQL schema |
| [`tests/`](tests/) | Governance, provenance, lifecycle, dependency, and evidence regression tests |
| [`Dockerfile`](Dockerfile) | The pinned OCI image, including its pinned Chromium; carries no default `CMD` |
| [`docker-compose.local.yml`](docker-compose.local.yml) | PostgreSQL and an S3-compatible endpoint for local development only |
| [`scripts/build_image.py`](scripts/build_image.py) | Reproducible image build helper |
| [`docs/superpowers/`](docs/superpowers/) | Slice design notes and execution plans; explanatory, never authoritative |

## Quality gate

Khepri requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --frozen
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

Those run as three separate jobs in the
[`governance` workflow](.github/workflows/governance.yml) for every pull request and every push
to `main`. Two more required checks exist beyond them:

- A **benchmark gate** in the same workflow. It reads its declaration from repository
  configuration and reports `NOT CERTIFIED` while none is set. A green run is not evidence that
  any performance objective holds.
- A **CodeScene Code Health Review**, configured on the repository and appearing in no workflow
  file. Every new file must score 10.00 and no tracked hotspot may decline. Local tooling does
  not reproduce the server thresholds, so treat CI as the only authority.

The separate [`image` workflow](.github/workflows/image.yml) builds the pinned OCI image and
verifies it as the non-root user that runs it, on every change that can affect it. It publishes
only when a registry has been provisioned and configured, and it never writes a digest into a
governed document.

## Run the journey locally

The local stack is development wiring, not a deployment, and nothing it produces is benchmark
or approval evidence. Defaults are built in, so no configuration is required.

```powershell
docker compose -f docker-compose.local.yml up -d
uv run alembic upgrade head
uv run python -m khepri.local.cli invite          # prints a token once; only its hash is stored
uv run uvicorn khepri.local.app:app --reload      # redeem the token, upload, request a report
uv run python -m khepri.local.cli work            # process due report jobs
uv run python -m khepri.local.cli sweep           # one recovery and expiry pass
```

Nine tests are marked `local_stack` and skip when the stack is not running; two more are marked
`browser` and skip without the pinned Chromium. Deselect them explicitly with
`-m 'not local_stack and not browser'`. Read the header of
[`docker-compose.local.yml`](docker-compose.local.yml) before changing the pins—the LocalStack
version, and the choice of LocalStack over MinIO, are both load-bearing.

## Digest-locked approval

Approval packages bind the exact ordered manifest and full governed-document bytes:

```powershell
uv run khepri-gov document-digest governance/path/to/document.md
uv run khepri-gov approval-digest governance/approvals/APP-NNN.yaml
```

Registries remain authoritative. A package does not grant authority by existing, passing CI,
or being merged. It becomes approved only through durable evidence from its named active human
owner, after which automation may materialize only the listed transitions.

## Predecessor boundary

`Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` is immutable,
non-authoritative reference material. Khepri imports no predecessor Git history, approval
authority, governance ledger, catalog, specification set, or application tree.

The 42 assessed capabilities retain exact source paths and blob identifiers in
[`reference-assessments.yaml`](governance/registries/reference-assessments.yaml). Every adapted
idea is a newly written and newly approved Khepri artifact.

## Change discipline

1. Start with a small, independently verifiable slice.
2. Update explanatory documents and authoritative registries together.
3. Record approval only when a named human supplies durable evidence.
4. Run the complete quality gate.
5. Resolve every review conversation.
6. Squash-merge only after required checks pass.

Two collisions are predictable when slices are prepared in parallel, and belong in the pull
request before they happen: two slices that each add an Alembic migration become siblings off
one parent, so the second to merge re-points its `down_revision`; and squash-merging a base
branch detaches anything stacked on it, so replay with
`git rebase --onto origin/main <old-base>` rather than merging.

---

<div align="center">
  <strong>Khepri creates trustworthy movement: from governed evidence to retail action.</strong>
  <br />
  <sub>Apache-2.0 · Kemetra · Governance before implementation</sub>
</div>
