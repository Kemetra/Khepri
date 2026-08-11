# KHEPRI-DEC-001: Khepri authority and predecessor reference policy

## Context

Khepri needs a clean authority boundary. Reusing predecessor governance would import
decisions, assumptions, and approvals that were not made for this repository.

## Decision

Khepri is the sole authoritative platform repository. Seshat-Platform remains separate and
unchanged. The only predecessor reference admitted during initialization is:

`Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876`

That pin is read-only reference material. It grants no authority or approval. Khepri does not
copy Seshat's catalogs, 42 specifications, proposals, ledger, governance records, or product
application implementation.

Khepri begins with repository governance, validation tooling, and the Platform Foundation
family only. Product families and runtime technology remain deferred.

## Consequences

- Every carried-forward idea requires a new Khepri artifact merged by the owner.
- Conflicts resolve in favor of Khepri's constitution and registry.
- Updating the reference pin requires a new active Khepri decision.
- No change to Seshat-Platform is authorized by this decision.

Identity, state, document, dependencies, and supersession are authoritative in
`governance/registry.yaml`.
