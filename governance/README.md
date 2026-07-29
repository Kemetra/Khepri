# Governance artifacts

The registries in `registries/` are the machine-readable source of truth:

- `authorities.yaml` names people who may own or approve artifacts.
- `decisions.yaml` records decision identity, state, ownership, and approval.
- `families.yaml` records product-family identity, state, ownership, dependencies, and
  approval.
- `specifications.yaml` records specification identity, state, family, ownership,
  dependencies, and approval.

Documents under `authorities/`, `decisions/`, `families/`, and `specifications/` explain
intent and boundaries. Templates under `templates/` define the minimum review shape.

The registry schema version is closed. Change it only through an accepted decision and a
validator update that can reject unsupported input.
