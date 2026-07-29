# Khepri

Khepri is Kemetra's authoritative platform repository. Its first phase is deliberately
governance-only: it defines how authority, decisions, product families, specifications,
validation, evidence, and change control work before product code is admitted.

Ahmed Shaaban is the initial product owner and named human authority. Machine-readable
registries under `governance/registries/` are authoritative for artifact identity, state,
ownership, dependencies, and approval evidence. Markdown documents explain rationale and
boundaries but do not override those registries.

`Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` is pinned reference
material only. It grants no approval, carries no authority into Khepri, and must not be
copied as a catalog, specification set, governance ledger, or application implementation.

## Local checks

Install [uv](https://docs.astral.sh/uv/), then run:

```text
uv sync --frozen
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

Python 3.13 is required. Validation fails closed: malformed, incomplete, or inconsistent
governance data returns a nonzero exit code with artifact-specific errors.

## Change workflow

1. Start with a small independently verifiable governance slice.
2. Update the relevant Markdown rationale and authoritative YAML registry together.
3. Record approval evidence when an artifact enters an accepted state.
4. Run all local checks.
5. Submit a pull request to `main`; resolve every conversation and squash merge only after
   required checks pass.

The [constitution](governance/CONSTITUTION.md) governs this repository. No product family or
runtime technology is implied beyond the approved Platform Foundation boundary.
