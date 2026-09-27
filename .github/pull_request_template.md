## Scope

Describe the smallest independently verifiable change and its exclusions.

## Governed artifacts

List registry and rationale changes. State `None` if no governed artifact changes.

## Claims

One row per claim this PR makes. The reviewer checks this table and the diff; it does not
re-derive them. A claim with no failing mutant is not evidence (`FR`/issue references required).

| Claim | Governing FR / issue | Test that proves it | Mutant that turns it red |
|---|---|---|---|
|  |  |  |  |

Owner items raised (not decided here):

- None

## Evidence

```text
uv run khepri-gov validate
uv run ruff check .
uv run pytest
coderabbit review --agent   # local, before the first push
```

## Owner decision

- [ ] Merge this pull request to approve the changes on `main`.
- [ ] Close it without merging to reject the proposal.

Until the owner merges it, this pull request is a proposal. Technical checks report consistency;
they do not grant approval.

## Parallel-slice collision notes

- Alembic sibling migration status:
- Stacked-branch rebase status:
