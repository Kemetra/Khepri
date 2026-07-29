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
- Do not add product application code during the foundation phase.
- Work in small, independently verifiable slices and fail closed on ambiguity.
- Do not claim or record human approval unless the named authority supplied explicit,
  traceable evidence.
- Run `uv run khepri-gov validate`, `uv run ruff check .`, and `uv run pytest` before handoff.

Repository-local instructions override broader defaults when they are more restrictive.
