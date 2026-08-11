## Scope

Describe the smallest independently verifiable change and its exclusions.

## Governed artifacts

List registry and rationale changes. State `None` if no governed artifact changes.

## Evidence

```text
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

## Owner decision

- [ ] Merge this pull request to approve the changes on `main`.
- [ ] Close it without merging to reject the proposal.

Until the owner merges it, this pull request is a proposal. Technical checks report consistency;
they do not grant approval.

## Parallel-slice collision notes

- Alembic sibling migration status:
- Stacked-branch rebase status:
