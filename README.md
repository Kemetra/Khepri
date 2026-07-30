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
    <a href="https://github.com/Kemetra/Khepri/actions/workflows/governance.yml">
      <img
        alt="Governance workflow"
        src="https://github.com/Kemetra/Khepri/actions/workflows/governance.yml/badge.svg?branch=main"
      />
    </a>
    <a href="https://github.com/Kemetra/Khepri/commits/main">
      <img
        alt="Last commit"
        src="https://img.shields.io/github/last-commit/Kemetra/Khepri?branch=main&amp;style=flat-square"
      />
    </a>
    <a href="https://github.com/Kemetra/Khepri/pulls">
      <img
        alt="Open pull requests"
        src="https://img.shields.io/github/issues-pr/Kemetra/Khepri?style=flat-square"
      />
    </a>
    <a href="LICENSE">
      <img
        alt="Apache 2.0 license"
        src="https://img.shields.io/github/license/Kemetra/Khepri?style=flat-square"
      />
    </a>
    <a href="pyproject.toml">
      <img
        alt="Python 3.13"
        src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&amp;logoColor=white&amp;style=flat-square"
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
implemented or launched.

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

## Current governed status

| Area | State | Meaning |
|---|---|---|
| Governance kernel | **Verified** | Authority, registries, validation, and evidence controls are active |
| Selective predecessor transfer | **Accepted** | All 42 pinned references have Khepri-owned technical dispositions |
| Atomic approval packages | **Accepted** | Digest-locked, dependency-closed approval can be materialized mechanically |
| RRA product family | **Active** | The private-beta family boundary is authorized |
| RRA-001 through RRA-007 | **Approved** | Invitations, intake, profiling, facts, narrative, reports, and operations are specified |
| Runtime/provider architecture | **Accepted** | [KHEPRI-DEC-005](governance/decisions/KHEPRI-DEC-005-rra-runtime-architecture.md) fixes the runtime, provider, and deployment boundary |
| Product application | **In bounded slices** | RRA-001 through RRA-006 have specification-linked implementations; RRA-007 recovery, bounded worker and opaque SQS delivery coordination, telemetry, and fail-closed benchmark-enforcement primitives are implemented, while approved workload execution remains |
| Beta launch | **Not authorized** | Client count and observation period require separate human authorization |

The authoritative state is always in
[`governance/registries/`](governance/registries/), not in this table.

## Approved RRA specification chain

| Specification | Contract |
|---|---|
| [RRA-001](governance/specifications/RRA-001.md) | Single-use invitations, consent, opaque ownership, and isolated sessions |
| [RRA-002](governance/specifications/RRA-002.md) | CSV/XLSX intake, validation, 50 MB limit, retention, and deletion |
| [RRA-003](governance/specifications/RRA-003.md) | Profiling, quality findings, semantic mapping, and fail-closed admissibility |
| [RRA-004](governance/specifications/RRA-004.md) | Deterministic retail KPIs, comparisons, reconciliation, and provenance |
| [RRA-005](governance/specifications/RRA-005.md) | Grounded Arabic/English narrative with minimized provider inputs |
| [RRA-006](governance/specifications/RRA-006.md) | One fact package rendered consistently to web, PDF, and Excel |
| [RRA-007](governance/specifications/RRA-007.md) | Idempotent jobs, recovery, deletion evidence, telemetry, and beta controls |

## Repository map

| Path | Purpose |
|---|---|
| [`governance/CONSTITUTION.md`](governance/CONSTITUTION.md) | Repository authority and non-negotiable operating rules |
| [`governance/registries/`](governance/registries/) | Machine-readable source of truth for identity, state, dependencies, and approval |
| [`governance/decisions/`](governance/decisions/) | Decision context, boundaries, and consequences |
| [`governance/specifications/`](governance/specifications/) | Approved product contracts and acceptance boundaries |
| [`governance/approvals/`](governance/approvals/) | Durable bootstrap and digest-locked package evidence |
| [`governance/reference-reviews/`](governance/reference-reviews/) | Bounded review evidence for the pinned predecessor |
| [`src/khepri_gov/`](src/khepri_gov/) | Fail-closed governance validator and digest tooling |
| [`src/khepri/rra/`](src/khepri/rra/) | Specification-linked RRA implementation slices |
| [`migrations/`](migrations/) | Alembic migrations for the authoritative PostgreSQL schema |
| [`tests/`](tests/) | Governance, provenance, lifecycle, dependency, and evidence regression tests |

## Quality gate

Khepri requires Python 3.13 and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync --frozen
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

The same commands run automatically in the
[`governance` GitHub Actions workflow](.github/workflows/governance.yml) for every pull request
and every push to `main`.

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

---

<div align="center">
  <strong>Khepri creates trustworthy movement: from governed evidence to retail action.</strong>
  <br />
  <sub>Apache-2.0 · Kemetra · Governance before implementation</sub>
</div>
