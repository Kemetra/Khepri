# Atomic Approval Packages for Khepri

Date: 2026-07-29

Status: Approved design; not governance approval

## Problem

Khepri now removes ambiguity about authority, provenance, lifecycle state, and product scope,
but approval throughput remains serial. One named authority would otherwise need to repeat the
same approval decision across related decisions, a family, and each dependent specification.
That creates administrative delay without adding review quality.

The current Constitution already permits one approval record to name multiple artifacts.
The missing capability is a reusable, machine-validated way to bind one human approval action
to an exact, dependency-closed set of artifacts and apply every lifecycle transition atomically.

## Goals

- Preserve named-human approval and fail-closed behavior.
- Let one explicit human action approve a coherent package of exact artifacts.
- Prevent partial application, scope drift, stale documents, and ambiguous evidence.
- Let implementation proceed under approved specifications without repeated product approval.
- Require renewed approval when a governed artifact changes.
- Keep authoritative lifecycle state in the existing artifact registries.

## Non-goals

- Automation does not approve artifacts.
- Approval packages do not select architecture or providers.
- Packages do not authorize work outside their listed scope.
- This design does not introduce delegated authorities, risk tiers, or product application code.
- Implementation and verification lifecycle transitions are not human-approval package
  transitions.

## Considered approaches

### 1. Digest-locked atomic approval packages

One package identifies exact artifacts, current and target states, document digests, scope, and
exclusions. A human approves its stable manifest digest once. A deterministic follow-up change
records the evidence and applies every target state together.

This is the selected approach because it improves throughput without broad or implicit authority.

### 2. Broad authorization followed by independent transitions

A human could approve a general outcome and allow later pull requests to decide which artifacts
fit it. This is operationally fast but makes scope drift and partial application difficult to
detect. Khepri's fail-closed principle rules it out.

### 3. Delegated authorities and risk tiers

Additional human authorities could approve different domains or change classes. This may become
useful when the organization grows, but it adds identity, delegation, revocation, and conflict
rules that are unnecessary for the private-beta decision.

## Governance artifacts

### KHEPRI-DEC-004

Add a proposed decision named `KHEPRI-DEC-004: Atomic approval packages and bounded
implementation authority`. Once accepted, it establishes this mechanism for future approvals.

The first package may include `KHEPRI-DEC-004` itself. This is not circular: the existing
Constitution and approval template already allow one approval record to name multiple artifacts.
`KHEPRI-DEC-004` standardizes and automates that existing authority for subsequent packages.

### Approval package evidence

Store reusable package evidence as `governance/approvals/APP-NNN.yaml`. Artifact registries remain
authoritative for lifecycle state. The YAML package is structured approval evidence referenced by
each transitioned registry entry.

Version 1 has this shape:

```yaml
schema_version: 1
id: APP-002
title: RRA private beta governance approval
state: proposed
owner: AHMED-SHAABAN
scope: Exact bounded authorization statement
exclusions:
  - Explicit excluded authority
manifest_digest: sha256:HEX_DIGEST
artifacts:
  - id: KHEPRI-DEC-002
    document: governance/decisions/KHEPRI-DEC-002-selective-transfer-protocol.md
    document_sha256: sha256:HEX_DIGEST
    from_state: proposed
    to_state: accepted
```

An entry that renews approval for an already approved artifact also includes the current
repository-relative `supersedes_approval_ref`. Initial approval entries omit that field.

An approved package adds:

```yaml
state: approved
approval:
  approved_by: AHMED-SHAABAN
  approved_at: 2026-07-29
  approved_manifest_digest: sha256:HEX_DIGEST
  evidence_ref: https://github.com/Kemetra/Khepri/...
```

The approval block is forbidden while the package is proposed.

## Stable manifest digest

`manifest_digest` is the SHA-256 digest of a canonical JSON representation containing:

- `schema_version`
- `id`
- `title`
- `owner`
- `scope`
- ordered `exclusions`
- ordered artifact entries and every field in each entry

The canonical representation uses UTF-8, sorted mapping keys, compact separators, and no
insignificant whitespace. It excludes `state`, `manifest_digest`, and the `approval` block.
Consequently, recording approval evidence does not change the content that the human approved.

Artifact order is dependency order and is significant. Reordering or changing any transition,
document path, digest, scope, or exclusion changes the manifest digest and invalidates prior
approval.

Version 1 hashes each complete governed Markdown document. Any change to an approved governed
document therefore requires a proposed superseding package and renewed approval. This
conservative boundary avoids an ambiguous automated distinction between editorial and material
changes. Ordinary implementation code and non-governed documentation do not affect the digest.

## Supported transitions

Version 1 approval packages support only:

- Decision: `proposed` to `accepted`
- Family: `proposed` to `active`
- Specification: `draft` to `approved`
- Approval renewal after a governed document change: a decision remains `accepted`; a family
  remains `active` or `retired`; or a specification remains at its current approved-or-later
  state (`approved`, `implemented`, `verified`, or `retired`). Every renewal entry has
  `supersedes_approval_ref` equal to the artifact's current package reference.

Packages do not mark specifications `implemented` or `verified`. Those transitions record
implementation and verification evidence while preserving the original human approval fields.
Adding other package transitions requires a later accepted decision and validator change.

## Approval workflow

1. Create a proposed package whose artifacts remain at their `from_state`.
2. Calculate and validate its manifest and document digests.
3. Publish the proposed package for review.
4. The named active authority supplies durable evidence that explicitly identifies the package
   ID and exact `manifest_digest`, and authorizes only:
   - the listed state transitions;
   - insertion of that approval evidence; and
   - no change to the approved manifest payload.
5. A mechanical commit changes the package to `approved`, adds the approval block, and updates
   all listed registries atomically.
6. CI proves that the manifest digest is unchanged, documents still match, dependencies close,
   all registry transitions are complete, and approval fields agree.
7. Merge through the normal protected pull-request workflow.

The mechanical application does not require a second product decision because the authority's
evidence explicitly authorizes it only when the approved digest remains identical. Any payload
change invalidates the evidence and returns the package to human review.

## Registry materialization

For every artifact in an approved package:

- the registry state equals `to_state`;
- `approved_by` equals the package approver;
- `approved_at` equals the package approval date; and
- `approval_ref` equals the repository-relative package path.

For every artifact in a proposed package:

- the registry state equals `from_state`; and
- the package does not add or replace approval fields; and
- an approval-renewal entry points to the artifact's current package reference.

An approved package is valid only when every listed artifact is materialized. One missing,
extra, or partially transitioned artifact invalidates the whole repository.

Historical approved packages remain immutable evidence. The current governed document must match
the package named by its registry `approval_ref`, unless exactly one proposed package explicitly
supersedes that reference and matches the changed document. Once the new package is approved, the
registry points to it and the prior package remains the traceable predecessor.

## Dependency closure

The validator evaluates the repository as it would exist after the complete package:

- An activated family may depend only on families already active or activated earlier in the
  same package.
- An approved specification's family must already be active or activated earlier in the same
  package.
- Every specification dependency must already be approved-or-later or approved earlier in the
  same package.
- An artifact may appear only once in a package and in at most one proposed package.
- Approved packages may form a linear renewal chain only through an exact
  `supersedes_approval_ref`; ambiguous or branching approval histories are invalid.

This permits the RRA specifications to be ordered `RRA-001` through `RRA-007` in one package
while preserving their dependency graph.

## Evidence rules

- `owner` and `approved_by` must identify known active human authorities.
- `approved_by` must equal the package owner in version 1.
- `evidence_ref` must be a durable Khepri GitHub pull-request review or comment URL.
- The evidence text must name the authority ID, package ID, and exact manifest digest.
- A passing check, pull-request merge, automation comment, silence, or package prose is never
  approval.

Local validation checks the closed data shape, Khepri URL boundary, and registry consistency.
Human reviewers remain responsible for confirming that the linked GitHub evidence was authored
by the named authority. Automating GitHub identity verification is deliberately deferred until
authority-to-account mappings are governed.

## Bounded implementation authority

Once a specification is approved:

- implementation pull requests may build only its stated requirements;
- they must link the specification and relevant reference assessments;
- they require the normal technical, privacy, security, and reconciliation evidence;
- they do not require a new product approval when no governed artifact changes; and
- any governed document change requires a proposed superseding package before the repository can
  validate and requires renewed human approval before that package can be applied.

This turns approval into a scope boundary rather than a repeated per-implementation ceremony.

## Initial RRA package

The first package, `APP-002`, is proposed to contain these eleven artifacts in dependency order:

1. `KHEPRI-DEC-002`
2. `KHEPRI-DEC-003`
3. `KHEPRI-DEC-004`
4. `RRA`
5. `RRA-001`
6. `RRA-002`
7. `RRA-003`
8. `RRA-004`
9. `RRA-005`
10. `RRA-006`
11. `RRA-007`

It excludes runtime/provider selection, product application code, beta launch authorization,
commercialization, and any claim that technical review is human approval.

The RRA architecture decision remains separate because final providers and operational
selections have not been reviewed.

## Validation and tests

Extend `khepri-gov validate` with tests for:

- valid proposed and approved packages;
- unsupported schemas, states, transitions, and evidence forms;
- malformed and incorrectly calculated manifest or document digests;
- duplicate and unknown artifact IDs;
- document path mismatch and changed documents;
- unknown, inactive, or mismatched owners and approvers;
- approval blocks on proposed packages and missing blocks on approved packages;
- approval evidence outside the Khepri repository;
- partial or extra registry materialization;
- inconsistent approval fields;
- invalid artifact order and incomplete dependency closure;
- overlapping proposed packages and branching or malformed supersession chains; and
- preservation of the legacy `APP-001-bootstrap.md` evidence without allowing new unstructured
  multi-artifact packages.

Required handoff evidence remains:

```text
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

## Delivery slices

Implementation should remain independently verifiable:

1. Add `KHEPRI-DEC-004`, the package schema/template, digest functions, and package validation
   tests.
2. Add `APP-002` as a proposed package with calculated artifact digests.
3. Obtain one explicit human approval for the exact `APP-002` manifest digest.
4. Apply the authorized package atomically and verify every registry transition.
5. Create and approve the separate RRA architecture decision before product code.

No slice may claim human approval before step 3 supplies traceable evidence.
