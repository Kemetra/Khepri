# Khepri Agent Instructions

Khepri uses minimal single-owner governance. Read `governance/CONSTITUTION.md` and
`governance/registry.yaml` before changing governed artifacts.

- Treat `governance/registry.yaml` as authoritative for artifact type, identity, state, document,
  dependencies, and supersession.
- Treat a branch or pull request as a proposal. A change becomes approved and governing only when
  Ahmed Shaaban, the sole repository owner, merges it to `main`.
- Keep Markdown rationale aligned with the registry; prose cannot override it.
- Treat `Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` only as
  non-authoritative reference material. Do not copy its catalogs, specifications, proposals,
  ledgers, governance records, or application code.
- Add product code only in active-specification-linked, independently verifiable slices. Never
  widen a slice beyond its specification.
- Fail closed on ambiguous identity, state, dependency, scope, privacy, runtime, or data boundaries.
- Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` before handoff.
- CodeScene Code Health Review is a required server-side PR gate. Every new file must score 10.00
  and no tracked hotspot may decline; local tooling does not reproduce its thresholds.
- If parallel slices add sibling Alembic migrations, the second to merge re-points its
  `down_revision`. If squash-merging detaches a stacked branch, replay it with
  `git rebase --onto origin/main <old-base>` instead of merging.

Repository-local instructions override broader defaults when they are more restrictive.
