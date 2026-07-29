# Governance artifacts

The registries in `registries/` are the machine-readable source of truth:

- `authorities.yaml` names people who may own or approve artifacts.
- `decisions.yaml` records decision identity, state, ownership, and approval.
- `families.yaml` records product-family identity, state, ownership, dependencies, and
  approval.
- `specifications.yaml` records specification identity, state, family, ownership,
  dependencies, and approval.
- `reference-assessments.yaml` records the exact pinned predecessor provenance, technical
  disposition, newly written Khepri targets, and review evidence for all 42 capability
  references.

Documents under `authorities/`, `decisions/`, `families/`, and `specifications/` explain
intent and boundaries. Technical reference-review evidence is under `reference-reviews/`.
Templates under `templates/` define the minimum review shape.

The registry schema version is closed. Change it only through an accepted decision and a
validator update that can reject unsupported input.

## Atomic approval packages

YAML files under `approvals/` are digest-locked structured approval evidence. They do not
replace the lifecycle state or approval fields in the authoritative registries. A proposed
package locks its ordered manifest and governed documents but grants no authority. An approved
package must carry exact, traceable evidence from its named active owner and must be
materialized atomically into every listed registry entry.

Calculate exact digests with:

```text
uv run khepri-gov document-digest governance/path/to/document.md
uv run khepri-gov approval-digest governance/approvals/APP-NNN.yaml
```

One-action approval evidence must identify the authority, package ID, and complete manifest
digest. Automation and passing checks are never approval. `APP-001-bootstrap.md` is the only
legacy unstructured Markdown approval; all later repository-local approval packages use YAML.
`KHEPRI-DEC-004` proposes this mechanism and remains proposed until traceable human approval is
recorded.

## Current transfer boundary

`KHEPRI-DEC-002`, `KHEPRI-DEC-003`, `KHEPRI-DEC-004`, the `RRA` family, and `RRA-001` through
`RRA-007` are proposed or draft. Their presence documents reviewable Khepri intent; it is not
approval and does not authorize product application code. Ahmed Shaaban must supply explicit,
traceable evidence before those registry entries may advance.

The 42 technical assessments were performed by automation against the exact pinned blobs.
Their `reviewed` state means the references have a recorded disposition, not that any Khepri
target was approved.
