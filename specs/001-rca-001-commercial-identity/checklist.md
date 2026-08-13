# RCA-001 — Specification quality checklist

> **SUPERSEDED — historical artifact, written 2026-08-08. Do not follow these instructions.**
> This document predates the current governance model and three merged RCA-001 slices. It reasons
> from a Constitution and an approval framework that no longer exist, and its status claims are
> false: `RCA-001` is `active` and implementation is under way. Read
> [`SUPERSEDED.md`](SUPERSEDED.md) for the delta and [`STATUS.md`](STATUS.md) for what is actually
> implemented. `governance/specifications/RCA-001.md` and `governance/registry.yaml` are
> authoritative; this file is not.

Adversarial review of `governance/specifications/RCA-001.md`. Every item was checked against the
document and, where the claim was about existing behaviour, against code or governance. Defects
found during review are listed at the end with their resolution.

## Testability

| # | Check | Result | Evidence |
|---|---|---|---|
| Q-1 | Every MUST is testable | **PASS** | All 40 FRs state an observable outcome. Spot-check of the weakest: `FR-026` ("one canonical checkpoint") is testable by asserting every protected action routes through it — see `T-014` |
| Q-2 | Success paths exist | **PASS** | Scenarios 1, 2, 4, 5, 6, 7, 10, 11, 12, 13 |
| Q-3 | Refusal paths exist | **PASS** | Scenarios 3, 8, 9, 14, 15, 16, 17, 18, 19, 20 — exactly half the scenarios are refusals |
| Q-4 | Success criteria are observable | **PASS** | Verification section names test classes, not intentions |
| Q-5 | No unresolved clarification marker | **PASS** | `grep -c "NEEDS CLARIFICATION" → 0` |

## Boundaries

| # | Check | Result | Evidence |
|---|---|---|---|
| Q-6 | Security boundaries explicit | **PASS** | `FR-021`..`FR-026` are a dedicated authorization section; deny-by-default is `FR-022` |
| Q-7 | Organization isolation explicit | **PASS** | `FR-024`, `FR-025`, `FR-035`; Scenarios 14, 15 |
| Q-8 | No technology choice leaked | **PASS** | Scanned for `Auth0, Clerk, Cognito, Keycloak, Supabase, JWT, OAuth, ORM, schema, cloud, mail provider`. Zero occurrences outside the Exclusions list. `FR-002` says "strong salted hash" — a property, not an algorithm |
| Q-9 | No later RCA scope leaked in | **PASS** | Workspaces, billing, agency, scheduling, signup all named in Exclusions |
| Q-10 | No RRA responsibility moved to RCA | **PASS** | `FR-036` forbids RCA performing retail calculation; `FR-037`..`FR-039` preserve RRA controls |
| Q-11 | No Seshat responsibility appeared | **PASS** | Named in Exclusions; no integration requirement anywhere |
| Q-12 | Deny-by-default stated, not implied | **PASS** | `FR-022` |
| Q-13 | Object identifiers grant no authority | **PASS** | `FR-023`, reinforced by `FR-025` (denial indistinguishable from nonexistence) |

## Invariant coverage

All twelve hard invariants from the task brief map to at least one requirement.

| Invariant | Requirement(s) | Scenario(s) |
|---|---|---|
| 1. One authenticated actor per protected action | `FR-003`, `FR-021` | 2, 19 |
| 2. Explicit organization scope | `FR-021`, `FR-027` | 13, 18 |
| 3. Identifiers grant no authority | `FR-023`, `FR-025` | 14, 15 |
| 4. Cross-org access fails closed | `FR-024`, `FR-034` | 14, 15 |
| 5. Multi-org without merged scopes | `FR-011`, `FR-035` | 12 |
| 6. Removing one membership is isolated | `FR-012` | 11 |
| 7. No accidental loss of final owner | `FR-013` | 17 |
| 8. Role/membership changes attributable | `FR-014` | 10 |
| 9. Revocation/disablement explicit | `FR-008`, `FR-030` | 16, 20 |
| 10. RCA performs no retail calculation | `FR-036` | — (negative; covered by `T-018`) |
| 11. RCA does not weaken RRA guarantees | `FR-037`, `FR-038` | — (covered by `T-019`) |
| 12. RRA independently testable | `FR-039` | — (covered by `T-019`) |

Scenario coverage: all 20 required scenarios are present and numbered stably.

Forbidden-identifier coverage: `FR-032` names all five identifiers from the brief verbatim —
`email address`, `organization name`, `organization slug`, `customer-visible account identifier`,
`human-readable resource identifier`.

## Defects found and resolved during review

**D-1 — Final-owner protection was under-specified.** The first draft covered only *removal* of the
final owner. Downgrading the final owner to `member`, and disabling the account holding the final
ownership, reach the same ownerless end state and were unguarded. `FR-013` was widened to name all
three operations. *Without this the invariant would have had two bypass routes and the test suite
would still have passed.*

**D-2 — Session-authorization timing was ambiguous.** The draft did not say whether a revocation
took effect immediately or at session expiry. Scenario 20 is untestable under the second reading.
Resolved in `clarify.md` C-6 and stated as `FR-030`, which forbids designs that capture roles into
a bearer credential treated as authoritative until expiry.

**D-3 — The bridge named the wrong entity.** The draft mapped an *account* to the opaque owner ID.
Reading `src/khepri/rra/deletion.py:149` (`owners/{owner_id}/sessions/{session_id}/`) showed this
would place colleagues in different storage prefixes and make `assert_same_scope` reject legitimate
shared access. Corrected to map the **organization**. See `clarify.md` C-11. *This was the single
defect most likely to invalidate the whole specification.*

**D-4 — Denial disclosure was unstated.** The draft required cross-org access to be denied but did
not require the denial to be uninformative, permitting a "belongs to another organization" message
that leaks existence. Added `FR-025`, matching the existing uniform
`CrossSessionAccessDenied("Resource is unavailable.")`.

**D-5 — Email uniqueness was an unmarked assumption.** Promoted to `A-1` and argued as a product
rule in `clarify.md` C-2, because `FR-005` and `FR-019` are undefined without it.

## Outcome

No open defect. The specification is internally coherent and ready for planning under Khepri's
rules, which permit planning while a specification is `draft`. It is **not** approved and **not**
implementation-authorized.
