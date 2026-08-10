# RRA: Retail Reporting Automation

## Owns

- Invite-bound, pseudonymous beta sessions and their isolated ownership boundary.
- Governed CSV/XLSX intake, profiling, retail admissibility, and content lifecycle.
- Deterministic retail facts, grounded bilingual narrative, and consistent report surfaces.
- Report-job reliability, content-free operational evidence, and beta performance measurement.

## Excludes

- Responsibilities of the `RCA — Retail Commercial Analysis` family: commercial authentication,
  user profiles, persistent customer workspaces, organizations, membership roles, billing,
  subscriptions, scheduling, public signup, agency portfolios, client switching, delegated access,
  customer-facing work queues, and white labeling. Those boundaries require separately approved
  specifications under that family.
- Forecasting, generic analysis, customer-authored formulas, and unsupported metrics. These are
  excluded from Khepri rather than allocated to another family.
- Runtime or provider selection before a separate architecture decision is accepted.
- Product implementation until the implementation preconditions of the governing `RRA`
  specification are met. This exclusion is stated against those gates rather than against a
  lifecycle state, because a charter condition of the form "while this family's specifications
  remain draft" stops excluding anything at the moment the first specification is approved, which
  is exactly when the exclusion is needed. Neither this family being `active` nor a specification
  being `approved` is authority to implement.

The family's authoritative lifecycle state and approval evidence are recorded in
`governance/registries/families.yaml`.
