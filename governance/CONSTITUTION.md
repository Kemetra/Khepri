# Khepri Constitution

Version: 1.2.0

Ratified: 2026-07-29

Amended: 2026-08-10 (KHEPRI-DEC-016)

Authority: Ahmed Shaaban, Product Owner

## I. One source of truth

Khepri is the only authoritative platform repository. Each governed fact has one
authoritative representation. YAML registries govern identity, lifecycle state, ownership,
dependencies, and approval evidence; explanatory documents cannot override them.

## II. Named human authority

Every governed artifact has a known human owner. Only a named, active authority can approve an
artifact, and only a named, active human authority can approve a change within the reserved set
defined in Article VIII. Automation validates and reports; it grants approval only as a named
delegate, only within a recorded delegation, and never under a human authority's identifier.

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

## VIII. Delegation

A named, active human authority may delegate approval to a named, active non-human authority. A
delegation is created by an explicit instruction from the human authority and recorded by the
delegate as a delegation record stating the instruction verbatim, the date it was given, the
session in which it was given, the scope granted, and an expiry date. A delegation record is the
delegate's attestation of an instruction; it is not proof of one, and the authority's approval of
this article is its acceptance of that attestation as sufficient.

An approval performed under a delegation records the delegate's identifier as its approver, in the
approval package and in every registry entry it materialises. It never records a human authority's
identifier. Human and delegated approvals remain distinguishable by inspection.

The reserved set is this constitution; the authorities registry, including a delegate's own record,
role, and active flag; every delegation record, including its creation, extension, and renewal; the
acceptance of any decision that alters the reserved set; and any artifact whose recorded consequence
is deployment, spending, provider or runtime selection, or a change to a privacy, retention, or data
boundary. An artifact's consequence is recorded in its authoritative registry entry and is not
inferred from its prose. An artifact that records no consequence is reserved. No delegation reaches
the reserved set, and an authority that could widen its own authority is unbounded however narrowly
it begins.

A delegation granted without an explicit duration covers only the session in which it was given. A
standing delegation expires no later than ninety days after it is recorded and does not renew
itself. The human authority may revoke any delegation at any time by any means, with immediate
effect, and a delegate may not resist, defer, or condition a revocation. Revocation does not
invalidate transitions already recorded; it stops further ones.

Validation fails closed on every condition in this article.

## Lifecycle vocabularies

- Decisions: `proposed`, `accepted`, `rejected`, `superseded`
- Families: `proposed`, `active`, `retired`
- Specifications: `draft`, `approved`, `implemented`, `verified`, `retired`

An accepted decision, active or retired family, and approved-or-later specification records
`approved_by`, `approved_at`, and `approval_ref` in its authoritative registry entry.
