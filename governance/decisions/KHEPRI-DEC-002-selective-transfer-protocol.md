# KHEPRI-DEC-002: Selective predecessor assessment and re-specification protocol

## Context

The pinned Seshat repository contains useful problem statements, but it is not authoritative
for Khepri. Bulk copying would import assumptions, scope, approval language, and implementation
choices that have not been accepted under Khepri governance.

## Proposed decision

Assess each of the 42 predecessor capability specifications at
`Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` as an immutable reference.
The authoritative `reference-assessments.yaml` registry records only exact provenance,
technical disposition, concise Khepri rationale, and any newly written Khepri target IDs.

The allowed workflow is:

1. Verify the pinned repository, source path, and Git blob identifier.
2. Review a bounded predecessor family without treating its prose as authority.
3. Assign `adapted`, `deferred`, or `rejected`; use `candidate` only while review is pending.
4. For `adapted`, identify an independently written Khepri decision, family, or specification.
5. Record who performed the review, when it occurred, and durable review evidence.
6. Obtain normal Khepri approval for every target before its requirements authorize product
   work.

Review evidence is not approval evidence. Automation may perform and record a technical
assessment, but it cannot accept a decision, activate a family, approve a specification, or
claim human authority.

Code reuse is exceptional and is not authorized by a capability assessment. A separate
provenance assessment must identify the exact blob, confirm Apache compatibility, document
security and privacy review, enumerate dependencies and tests, and receive explicit Khepri
approval. Clean implementation is the default.

## Consequences

- Seshat Git history, governance artifacts, catalogs, specifications, ledgers, and application
  tree are not imported.
- Incorrect pins, missing entries, duplicate sources, malformed provenance, incomplete review
  evidence, unknown dispositions, and missing adapted targets fail validation.
- Ten bounded review batches provide evidence for the 42 technical dispositions.
- A disposition never carries predecessor approval or silently approves its Khepri target.
- No change to Seshat-Platform is authorized.

This decision remains proposed until its registry entry contains explicit approval evidence.
