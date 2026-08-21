# R7-06: commercial end-to-end evidence and the consent route

**Baseline:** `main` @ `43fcd72`, 2026-08-21 (`KHEPRI-DEC-023` merged and `active`; `R7-01`…`R7-05`
and `R7-07` merged).

**Authorized by:** `KHEPRI-DEC-023` §2, which authorizes one commercial consent route and fixes four
things about it. `KHEPRI-DEC-022` §2's four bounds are carried forward by `-023` §1 and bind this
slice too: `for_request` and never `resolve`, the cookie as the only token source, the replaced
`R6-08` tripwire, and no new `R6-01` §3.1 row.

**What this note settles:** the consent route's shape, what evidence closes each of the twelve
`RCA-001` requirements `R7` moves, and which requirement is satisfied by absence rather than by test.

**What it does not settle** is in §7.

**This is the last task in `R7`.** Its definition of done includes flipping §16's `R7` row from
`READY_FOR_IMPLEMENTATION` to `MERGED`.

---

## 1. Why this slice carries product code

`R7-06` was scoped as test-only. `KHEPRI-DEC-023`'s Context records why it is not: `FR-038` requires
consent-before-upload to hold for a commercial actor exactly as for a beta participant, and it is
false today. Consent is enforced at the service layer (`IntakeService.begin` calls
`require_upload_consent`, `rra/intake.py:188`), so it already binds a commercial actor; but the only
route that records consent reads the beta cookie `khepri_beta_session` (`rra/api.py:184`), which a
commercial actor never holds. Every commercial upload therefore fails closed forever.

A test suite cannot close a requirement the product does not satisfy. The route comes first, and the
evidence follows it.

## 2. The consent route

`POST /api/v1/commercial/analyses/{session_id}/consent`, added to
`src/khepri/runtime/commercial_api.py` beside the two existing handlers.

```
cookie (khepri_session)
      |
for_request(organization_id=None)          <- live authorization, as the other two routes
      |
bridge.resume(session_id)                  <- THE SCOPE CHECK, before anything is written
      |
record_consent(session_id, version, now)   <- the existing service, unchanged
```

**The `resume` call is not a redundant read.** It is what establishes that the named analysis belongs
to the resolved scope. A route that called `record_consent` on a caller-supplied `session_id` without
it would let one organization write consent onto another organization's analysis — the `FR-023`
violation the resume path exists to prevent, and the reason `KHEPRI-DEC-023` §2 names it explicitly.

`204 No Content` on success, matching the beta route's status so the two do not diverge in shape.

Every refusal is the same empty-body `404` the other two routes return, through the existing
`_not_found()`: an absent analysis, another scope's analysis, an expired session, and a missing
cookie are indistinguishable. A `409` for "already consented" is specifically excluded by
`KHEPRI-DEC-023` §2 — distinguishing it from "not yours" is a disclosure oracle (`FR-025`,
`FR-034`).

**Recording consent twice is not an error.** `record_consent` overwrites the version and timestamp,
and the route does not read the prior state to refuse. Refusing a second consent would require
distinguishing it, which the paragraph above forbids.

## 3. Evidence, requirement by requirement

All in `tests/test_r706_commercial_e2e.py`, reusing `R7-03`'s `Journey` (two owners so `FR-013`'s
final-owner invariant cannot confound a demotion, separate RCA and RRA databases for `FR-039`).

### 3.1 Cross-organization read and mutation — scenarios 14 and 15

`FR-023`, `FR-034`. An actor in organization B, driven through the real HTTP surface:

- Resuming A's analysis returns exactly what a nonexistent identifier returns, compared
  **response-to-response** rather than each against a literal.
- Consenting to A's analysis is refused, and **A's consent state is unchanged afterwards** — the
  mutation case needs the state assertion, because a refused write and a successful one can both
  return `404` if the check is in the wrong place.
- A's analysis still exists after both attempts, so each refusal is authorization rather than
  deletion.

### 3.2 An account with no membership — scenario 18

`FR-028`. An account that authenticates but belongs to no organization: every commercial route
refuses it, and the refusal is identical to the cross-organization one. `FR-028` requires
authentication to *succeed* while every organization-scoped action is denied, so the test asserts the
session resolves before asserting the routes refuse — otherwise it would pass against a system that
simply rejected the login.

### 3.3 One canonical checkpoint

`FR-021`, `FR-026`. `FR-026` requires an action that does not pass the checkpoint be *unreachable
rather than permitted*, which is a structural claim about the module rather than a per-request one:

- Every route function in `commercial_api.py` calls `for_request`, asserted by parsing the module and
  inspecting each handler.
- The scan carries an **emptiness assertion**: a parse that finds no handlers satisfies every claim
  about the handlers it found. Without it the test would go green if the module were renamed.

This is deliberately not a duplicate of `R6-08`'s replaced tripwire, which asserts *who imports the
resolver*. This asserts *that every handler in the module uses it*.

### 3.4 Scope mapping and the durable organization

`FR-009`, `FR-031`. The commercial path reaches RRA only through the `owner_id` that `resolve_scope`
returns:

- Two analyses opened by the same organization share one `owner_id`, and it equals what
  `resolve_scope` returns for that organization — so the isolation scope is the organization's, not
  the session's or the actor's.
- The organization outlives its analyses: `FR-009`'s durable scope distinct from the accounts acting
  in it is shown by a second member of the same organization resuming an analysis the first opened.

### 3.5 FR-038, all four clauses

`KHEPRI-DEC-023`'s Consequences require evidence for all four, not only consent.

- **Consent before upload** — a commercial actor consents through §2's route, and an upload attempted
  *before* consenting is refused with `ConsentRequired` while the same upload after consenting is
  accepted. Both halves are needed: the refusal alone would pass against a route that never records
  consent at all.
- **Disclosure, reconciliation and provenance, and language parity** — these hold by shared
  implementation, and the evidence proves that rather than assuming it. The report pipeline keys on
  `SessionScope(owner_id, session_id)` (`report_services.py:188`) and has no actor-kind concept, so a
  structural test asserts **no module under `khepri/rra/` branches on actor kind** — no reference to a
  commercial or beta distinction in the pipeline path — carrying its own emptiness assertion. One
  journey then shows a commercial actor reaching the pipeline, so the structural claim is about a
  path that is actually reachable.

Duplicating beta's pipeline suite is explicitly not the plan: the same code, reached through the same
services, does not need its rendering re-asserted per actor kind. What needs proving is that the
actor kind never enters.

### 3.6 FR-024 is satisfied by absence, not by test

`FR-024` requires a request whose actor and named organization scope disagree to fail closed. **No
commercial route accepts an organization** — `for_request` is called with `organization_id=None` — so
that request cannot be constructed at this surface.

`KHEPRI-DEC-023`'s Consequences require this be stated rather than implied. A test named for `FR-024`
that passed because the parameter does not exist would be a test that cannot fail. Instead one test
asserts the *absence*: no route in the module accepts an organization parameter, with an emptiness
assertion over the handlers inspected. That is a real claim, and it is the claim that makes `FR-024`
unreachable.

## 4. Mutants

`#231` records the cost of shipping an evidence suite with none. Four, each with a named killer:

| Mutant | Expected killer |
|---|---|
| Drop the `bridge.resume` scope check from the consent route | the cross-organization consent-write test, asserting A's consent state unchanged |
| Return `409` instead of `404` for an already-consented analysis | the uniform-refusal comparison |
| Call `resolve` instead of `for_request` in the consent route | the checkpoint structural scan |
| Make the pipeline actor-kind scan return no modules | that scan's own emptiness assertion |

Verify each mutant introduces the defect before concluding a test is weak; a malformed mutant proves
nothing.

## 5. What changes state when this lands

- `R6-08`'s replaced tripwire keeps passing: the consent route lives in the module already named as
  the resolver's only consumer, so its expected set does not change.
- `R6-05`'s matrix tripwire needs no new row. `KHEPRI-DEC-022` §2's fourth bullet, carried forward by
  `-023` §1, settles that consent is not a new `R6-01` §3.1 verb — it writes to an analysis the actor
  already reaches through "Resolve an isolation scope".
- `R7-04`'s beta regressions must stay green **unmodified**, and the beta consent route keeps its
  path, cookie and status code.

## 6. Definition of done

- The consent route ships within `KHEPRI-DEC-023` §2's four bounds.
- All twelve requirements have named evidence or a recorded absence: `FR-008`, `FR-022`, `FR-023`,
  `FR-025` were closed by `R7-05`; this slice closes `FR-009`, `FR-021`, `FR-026`, `FR-028`,
  `FR-031`, `FR-034`, `FR-038`; `FR-024` is recorded satisfied by absence.
- §16's `R7` row flips to `MERGED` — the transition only a final slice performs — stating which
  requirements closed where rather than claiming the program proved all twelve at once.

## 7. What this note does not settle

- **Report content for a commercial actor.** §3.5 proves the path is reachable and actor-kind-free,
  not that any particular figure is correct; that is the pipeline's own suite.
- **`#231`'s R7-03 mutation gap.** Same program, separate issue, not closed here.
- **Any UI.** `KHEPRI-DEC-023` §3 excludes it; `R8` owns templates.
- **A most-recent analyses list.** `KHEPRI-DEC-021` §114 noted a surface may present one; no record
  authorizes the selection rule it would need.
