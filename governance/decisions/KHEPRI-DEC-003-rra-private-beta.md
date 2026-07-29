# KHEPRI-DEC-003: Retail Reporting Automation private beta boundary

## Context

Khepri needs a narrow first customer outcome that tests retail-report value while limiting
identity, retention, privacy, operational, and commercialization risk.

## Proposed decision

Create the proposed `RRA — Retail Reporting Automation` family. Its first outcome is an
invite-only private beta in which a client uploads one CSV or XLSX retail dataset and receives
grounded Arabic and English analysis through web, PDF, and Excel.

The beta boundary is:

- A single-use invitation creates a pseudonymous session and opaque owner ID.
- The system stores invitation secrets only as hashes and collects no password, profile,
  billing identity, or email owner key.
- Consent is required before upload. Session content expires seven days after creation and can
  be deleted immediately.
- One immutable retail fact package supplies narrative, charts, PDF, and Excel.
- Reports are automatically generated and clearly disclosed as such; no human approval is
  represented.
- At least 95% of valid datasets of 50 MB or less must produce a complete report bundle within
  ten minutes under an approved beta benchmark.
- Privacy, isolation, validation, reconciliation, provenance, language parity, and deletion
  controls cannot be weakened to improve latency.

Commercial authentication, persistent workspaces, organizations, billing, scheduling, agency
features, public signup, forecasting, customer-defined formulas, and generic non-retail analysis
are outside this beta.

Application implementation is not authorized by this proposed decision. It may begin only after:

1. this decision is accepted and `RRA` is active;
2. the relevant RRA specification is approved;
3. a separate architecture decision approves final runtime and provider selections; and
4. the implementation slice links its specification and relevant reference assessments.

The intended architecture for later selection is a greenfield Python 3.13 modular monolith,
PostgreSQL metadata and facts, encrypted S3-compatible object storage, a bounded background
worker, and replaceable narrative-provider adapter. This statement is a constraint for the
future architecture decision, not a provider selection.

## Consequences

- Opaque ownership remains independent of future commercial authentication.
- `FactPackage`, `NarrativeAdapter`, and `ReportBundle` are stable contract boundaries.
- No product application code is admitted while the family and specifications remain
  unapproved.
- Commercialization and progressively lower latency objectives require later decisions.
- Beta exit additionally requires an explicit authorization artifact from Ahmed Shaaban that
  defines the client count and observation period.

This decision remains proposed until its registry entry contains explicit approval evidence.
