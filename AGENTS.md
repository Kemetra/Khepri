# Khepri Agent Instructions

Khepri is governance-first. Read `governance/CONSTITUTION.md` and the relevant registry
before making changes.

- Treat `governance/registries/*.yaml` as authoritative for identity, state, ownership,
  dependencies, and approval evidence.
- Keep Markdown rationale aligned with the registries, but never infer approval from prose.
- Treat `Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` only as
  non-authoritative reference material.
- Do not copy Seshat catalogs, specifications, proposals, ledgers, governance records, or
  application code.
- Add product application code only in specification-linked, independently verifiable slices, as
  authorized by `governance/decisions/KHEPRI-DEC-005-rra-runtime-architecture.md`. Never implement
  ahead of an approved specification, and never widen a slice beyond its stated boundary.
- Work in small, independently verifiable slices and fail closed on ambiguity.
- Do not claim or record human approval unless the named authority supplied explicit,
  traceable evidence.
- Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` before handoff.
- Expect a fourth required check that appears in no workflow file: a CodeScene Code Health Review
  gates every pull request. Every new file must score 10.00 and no tracked hotspot may decline.
  Local CodeScene tooling does not reproduce the server thresholds, so treat CI as the only
  authority and keep constructors to two or three arguments rather than sitting at a limit.
- Expect two collisions when slices are prepared in parallel. Two slices that each add an Alembic
  migration become siblings off one parent, so the second to merge re-points its `down_revision`.
  Squash-merging a base branch detaches anything stacked on it, so replay those commits with
  `git rebase --onto origin/main <old-base>` instead of merging. State both in the pull request
  before they happen.

Repository-local instructions override broader defaults when they are more restrictive.
