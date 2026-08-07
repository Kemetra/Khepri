# RCA: Retail Commercial Analysis

## Owns

- Durable commercial identity: accounts, credentials, sessions, and recovery, mapped onto the
  opaque owner ID that `RRA-001` establishes as the isolation boundary key.
- Organizations, membership roles, and the authorization model over them.
- Persistent customer workspaces: durable storage of inputs and reports beyond the beta's
  seven-day expiry, under an explicit approved retention decision.
- Multi-dataset accumulation within a workspace, and comparison across datasets a single upload
  could not produce.
- Pricing, plans, entitlements, subscription lifecycle, quota enforcement, and invoicing.
- Public signup, abuse controls, self-serve onboarding, and the pre-purchase product surface.
- Agency tenancy: portfolios, client switching, delegated access, and bounded white labeling.
- Recurring scheduled delivery of reports a customer does not log in to collect.

## Excludes

- The invite-bound pseudonymous beta boundary, its governed intake and content lifecycle, its
  deterministic retail facts, its grounded bilingual narrative, and its report surfaces. Those are
  `RRA`'s, and `RCA` consumes them rather than reimplementing them.
- Repository governance, artifact identifiers, registries, and fail-closed validation. Those are
  `FND`'s.
- Forecasting, customer-authored formulas, and generic non-retail analysis. These are excluded from
  Khepri rather than reassigned between families, and admitting one requires a separately approved
  decision and family amendment.
- Any weakening of the privacy, isolation, validation, reconciliation, provenance, language parity,
  or deletion controls that `RRA-001`, `RRA-002`, and `RRA-006` fix. Commercialization does not
  relax them, and no `RCA` specification may propose that it does.
- Analytical capabilities owned by `Kemetra/Seshat-BI`, including statistical inference Khepri does
  not implement. That boundary is governed separately and is not settled by this charter.
- Product implementation while this family remains proposed or its specifications remain draft.
- Runtime, provider, or deployment selection, which `KHEPRI-DEC-008` governs and which remains a
  separate gate.

The family is proposed. Its authoritative lifecycle state and approval evidence are recorded in
`governance/registries/families.yaml`.
