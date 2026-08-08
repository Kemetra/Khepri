# Feature Specification: RCA-001 — Commercial Identity, Organizations, and Authorization

**Feature Branch**: `001-rca-001-commercial-identity` (directory only; no git branch was created)

**Created**: 2026-08-08

**Status**: Draft — not approved, not implementation-authorized

**Input**: User description: "RCA-001 — Commercial Identity, Organizations, and Authorization"

## This file is deliberately not the specification

The authoritative specification is:

> **`governance/specifications/RCA-001.md`**

Khepri's `governance/registries/specifications.yaml` pins each specification through its
`document:` field, and every existing specification (`FND-001`..`FND-003`, `RRA-001`..`RRA-009`)
lives under `governance/specifications/`. Constitution I requires one authoritative representation
per governed fact.

Restating the requirements here would create a second representation with no registry entry — the
"duplicated sources of truth" defect this feature's own analysis is required to detect. So this
file carries no requirements, no scenarios, and no success criteria. Read the governed document.

## What lives in this directory

| File | Role | Governed counterpart |
|---|---|---|
| `spec.md` | This pointer | `governance/specifications/RCA-001.md` |
| `clarify.md` | Ambiguity pass and how each item was resolved | none |
| `plan.md` | Technical plan | none |
| `tasks.md` | Dependency-ordered task breakdown | none |
| `analyze.md` | Traceability matrix and consistency findings | none |
| `checklist.md` | Specification quality checklist | none |

Only `spec.md` has a governed counterpart, and it defers to it. The remaining artifacts are Spec
Kit working material that Khepri's governance model does not otherwise represent, so they live
here without conflict.

## Constitution note

`/speckit-constitution` was **not** run. It writes `.specify/memory/constitution.md`, and Khepri
already has a ratified constitution at `governance/CONSTITUTION.md` (v1.1.0, amended 2026-08-02 by
`KHEPRI-DEC-011`). Populating the Spec Kit copy would create a second constitution that a later
reader could mistake for authority. The scaffold placeholder is left untouched.
