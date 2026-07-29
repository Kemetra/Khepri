# Khepri Constitution

Version: 1.0.0

Ratified: 2026-07-29

Authority: Ahmed Shaaban, Product Owner

## I. One source of truth

Khepri is the only authoritative platform repository. Each governed fact has one
authoritative representation. YAML registries govern identity, lifecycle state, ownership,
dependencies, and approval evidence; explanatory documents cannot override them.

## II. Named human authority

Every governed artifact has a known human owner. Only a named, active authority can approve
an artifact. Automation validates and reports; it never grants approval.

## III. Reference is not authority

External and predecessor material may inform work but never approves it. In particular,
`Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` is immutable reference
material. No Seshat artifact or approval carries forward without a new Khepri artifact and
explicit Khepri approval.

## IV. Small verifiable slices

Changes are independently reviewable, testable, and reversible. A pull request must state
its boundary and evidence. Product scope is not smuggled into governance or tooling work.

## V. Fail closed

Unknown states, owners, dependencies, schemas, missing evidence, malformed data, and
ambiguous authority block progress. Silence or a passing technical check is not approval.

## VI. Evidence and versioning

Governed artifacts use stable identifiers, explicit schema versions, traceable dependencies,
and durable approval references. Material changes create reviewable version history;
supersession is explicit and never rewrites prior authority.

## VII. Privacy and least data

Khepri defaults to collecting, retaining, exposing, and processing the least data necessary.
New data use requires an explicit purpose, owner, boundary, retention decision, and approval.

## Lifecycle vocabularies

- Decisions: `proposed`, `accepted`, `rejected`, `superseded`
- Families: `proposed`, `active`, `retired`
- Specifications: `draft`, `approved`, `implemented`, `verified`, `retired`

An accepted decision, active or retired family, and approved-or-later specification records
`approved_by`, `approved_at`, and `approval_ref` in its authoritative registry entry.
