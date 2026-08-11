# Minimal Single-Owner Governance

## Context

Khepri has one repository owner, but its governance kernel models multiple human authorities,
delegated agents, digest-locked approval packages, renewable evidence, and several overlapping
lifecycle mechanisms. Those controls add substantial code and ceremony without adding assurance
for a repository where the owner controls merges to `main`.

The current system remains preserved in Git history. The working tree should describe the model
that is actually operated now.

## Goals

- Make governance understandable from the constitution, one registry, and one validator.
- Treat a sole-owner merge to `main` as approval, with Git providing identity and time evidence.
- Preserve specification-before-implementation, dependency integrity, and fail-closed validation.
- Remove approval, delegation, renewal, and prose-scanning machinery that does not serve the
  single-owner operating model.
- Keep the migration independently reviewable and fully covered by focused tests.

## Non-goals

- Changing product behavior, runtime architecture, privacy boundaries, or infrastructure.
- Rewriting Git history or erasing historical governance evidence from repository history.
- Introducing a replacement workflow engine, policy language, or external governance service.
- Claiming that automation independently approves changes.

## Governance Model

The constitution is reduced to a short operating contract:

1. Ahmed Shaaban is the sole repository owner and decision authority.
2. A change is approved when the owner merges it to `main`; the Git record is the evidence.
3. `governance/registry.yaml` is authoritative for governed artifact identity and state.
4. Product code must remain linked to an active specification and be delivered in verifiable
   slices.
5. Unknown or inconsistent registry data fails validation.

Branches and pull requests contain proposals. The authoritative registry on `main` therefore does
not need a proposed state.

## Unified Registry

`governance/registry.yaml` replaces the authorities, decisions, families, specifications, and
reference-assessment registries. Its schema is deliberately small:

```yaml
schema_version: 2
artifacts:
  - type: family
    id: RRA
    state: active
    document: governance/families/RRA.md
    depends_on: []
  - type: specification
    id: RRA-001
    state: active
    document: governance/specifications/RRA-001.md
    depends_on:
      - RRA
  - type: decision
    id: KHEPRI-DEC-003
    state: retired
    document: governance/decisions/KHEPRI-DEC-003-rra-private-beta.md
    depends_on: []
    superseded_by: KHEPRI-DEC-014
```

Allowed types are `decision`, `family`, and `specification`. Allowed states are `active` and
`retired`. `superseded_by` is optional and valid only on retired artifacts. A specification names
its family as a dependency instead of carrying a second relationship field.

Existing authoritative artifacts are migrated as follows:

- accepted decisions and active families become active;
- superseded, rejected, or still-proposed decisions become retired;
- approved, implemented, or verified specifications become active;
- retired specifications and families remain retired;
- current cross-artifact dependencies are retained, with each specification also depending on its
  family.

The registry no longer stores owners, approval fields, consequences, approval references, or
separate lifecycle vocabularies.

## Validator and CLI

The public CLI retains one command:

```text
uv run khepri-gov validate
```

Validation remains fail-closed and checks:

- the exact registry schema version and top-level shape;
- exact artifact fields and closed type/state vocabularies;
- unique, non-empty identifiers;
- repository-relative Markdown document paths that exist;
- unique document ownership;
- known, unique dependencies with no self-dependency or dependency cycle;
- specifications depending on exactly one family;
- active artifacts not depending on retired artifacts;
- `superseded_by` naming a different, active artifact of the same type;
- retired artifacts either naming a successor or remaining as explicit historical context.

Digest commands, delegation guards, lifecycle guards, renewal checks, reference-assessment
validation, and approval materialization are removed.

## Repository Migration

The current tree removes:

- `governance/approvals/`;
- `governance/delegations/`;
- `governance/authorities/`;
- `governance/reference-reviews/` and the predecessor assessment ledger;
- superseded registry files and approval/delegation templates;
- governance implementation modules and tests dedicated to removed behavior.

Decision, family, and specification Markdown files remain as design history. One migration decision
explains why the former machinery was removed and how Git preserves its history. General templates
are reduced to the three artifact types that remain useful.

Repository-facing documentation and CI commands are updated to describe the new model. No product
application code changes in this migration.

## Error Handling

The validator reports all discoverable registry errors in one run and exits non-zero. Malformed
YAML, unreadable files, unknown fields, unsupported values, and graph errors produce concise,
path-oriented messages without tracebacks. Missing or ambiguous data is never inferred.

## Testing

Focused tests cover one valid registry and each validation boundary: schema shape, fields,
vocabularies, identifiers, paths, dependencies, cycles, family linkage, active-to-retired
dependencies, and supersession. CLI tests cover success, aggregated errors, malformed input, and
path handling.

The complete repository gate remains:

```text
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

CodeScene remains authoritative for its server-side Code Health gate. New or rewritten files must
remain simple enough to score 10.00.

## Success Criteria

- A contributor can explain governance from the constitution and registry without reading Python.
- Governance has one source of artifact metadata and one executable command.
- No approval package, delegation, renewal, digest, or lifecycle prose-scanning path remains active.
- Every retained governed document appears exactly once in the unified registry.
- Product behavior and product tests are unchanged.
- All required local checks pass from a clean worktree.

