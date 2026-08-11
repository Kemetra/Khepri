# KHEPRI-DEC-017: Minimal Single-Owner Governance

## Context

Khepri has one repository owner, but its first governance kernel modeled multiple human
authorities, delegated agents, digest-locked approval packages, renewable evidence, and several
overlapping lifecycle controls. That machinery made routine documentation changes expensive and
created an approval system more complex than the organization operating it.

Git already records the merged content, author, committer, and time. For a repository controlled
by one owner, a second approval ledger duplicates that evidence without creating an independent
control.

## Decision

Khepri uses a minimal single-owner model:

- the owner merging a change to `main` is approval;
- one registry records artifact identity and state;
- artifacts are either active or retired;
- proposals remain on branches and pull requests;
- one fail-closed command validates registry shape and dependency integrity.

The current tree removes approval packages, delegations, authority records, renewable digests,
lifecycle prose scanning, and the fixed predecessor-assessment ledger. Git history preserves every
removed record and its original context.

## Migration

- Accepted decisions become active.
- Superseded, rejected, and unaccepted proposed decisions become retired.
- Active families remain active.
- Approved, implemented, and verified specifications become active.
- Each specification names its family through `depends_on`.
- `KHEPRI-DEC-003` retains its successor link to `KHEPRI-DEC-014`.

## Retained guarantees

- Product code remains specification-linked and slice-bounded.
- Registry identity, paths, dependencies, cycles, family links, and supersession fail closed.
- Privacy, runtime, and data boundaries remain unchanged by this governance-only migration.
- Governance validation, Ruff, pytest, and the server-side CodeScene gate remain required.

## Consequences

Governance no longer attempts to simulate organizational separation that does not exist. Changes
become easier to understand and review, while repository history remains the durable audit trail.
If Khepri later gains another decision authority, the owner can introduce a proportionate review
model through a new merged decision; the former machinery does not remain active in anticipation.

## Verification

The repository must pass:

```text
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```
