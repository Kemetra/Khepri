# R7-05: the commercial HTTP surface

**Baseline:** `main` @ `00a0918`, 2026-08-21 (`KHEPRI-DEC-022` merged and `active`; `R7-01`, `R7-02`,
`R7-03`, `R7-04`, `R7-07` merged).

**Authorized by:** `KHEPRI-DEC-022` §2, which lifted `KHEPRI-DEC-021` §5's first bullet ("No
endpoint"). That record fixes four things and this note may not depart from them: the endpoint calls
`for_request` and never `resolve`; the token comes from `CommercialSessionCookie` only; `R6-08`'s
tripwire is replaced rather than relaxed; `R6-01` §3.1 gains no row.

**What this note settles:** where the route group lives, its two routes, how a request becomes an
authorization decision, what every refusal returns, and what evidence the slice owes.

**What it does not settle** is in §8.

---

## 1. Why a new module, and why in `khepri.runtime`

The route group is `src/khepri/runtime/commercial_api.py`.

It cannot live in `khepri.rra`. `R7-07` asserts a **flat prohibition** in both directions —
`khepri.rca` imports no `khepri.rra` module and `khepri.rra` imports no `khepri.rca` module — and a
route module needs `AuthorizationResolver` (RCA) and `CommercialBridge` (which holds both). Putting
it in `rra/api.py` or `rra/commercial_api.py` would pull `khepri.rca` into the RRA package and fail
that test.

`khepri.runtime` is the composition root and already holds the bridge for the same reason
(`KHEPRI-DEC-021` §3: composition roots exist to know about both sides). It is also the layer the
built wheel ships — `pyproject.toml` excludes `src/khepri/local`, so a surface there would be
unreachable from the deployed web role.

A new file rather than an addition to `rra/api.py` (532 lines) also keeps CodeScene scoring a small
focused module instead of a growing one.

## 2. The seam

The repo's established pattern is `add_*_routes(app, *, services, clock)` with a null guard —
`add_report_routes` (`rra/report_api.py:126`) and `add_journey_routes`. This follows it:

```python
def add_commercial_routes(
    app: FastAPI,
    *,
    services: CommercialServices | None,
    clock: Callable[[], datetime],
) -> None:
    """Declare the commercial route group, or declare nothing at all."""
    if services is None:
        return
```

`CommercialServices` is a frozen dataclass holding `resolver: AuthorizationResolver` and
`bridge: CommercialBridge` — one collaborator from each side, paired only here.

**The null guard is load-bearing, not stylistic.** `KHEPRI-DEC-022` §3 forbids any beta-mode change.
When `services is None` the routes are never declared, so a beta-only deployment has no commercial
surface *at all* — the requirement is met structurally rather than by a test asserting behavior is
unchanged. `R7-04`'s regression suite must stay green unmodified, and it will, because there is
nothing new to reach.

## 3. Two routes

| Route | Bridge call | Success |
|---|---|---|
| `POST /api/v1/commercial/analyses` | `bridge.open` | `201` with `{"session_id": ...}` |
| `GET /api/v1/commercial/analyses/{session_id}` | `bridge.resume` | `200` with the analysis |

`/api/v1/commercial` sits beside the existing `/api/v1/beta` group rather than inside it: the two are
different authorization models, and nesting would suggest a shared one.

`{session_id}` in the path is an **object identifier and confers nothing** (`FR-023`). The bridge
already enforces this — `resume` re-resolves authorization *before* it reads, and its owner predicate
lives in the store's statement rather than in a comparison. The route adds no check of its own.

## 4. No organization is named in a request

`for_request` is called with `organization_id=None`, so the session's active organization is used.

`KHEPRI-DEC-022` §2 requires that *any* organization named in a request be passed to `for_request`
for comparison. This note satisfies that requirement by admitting no such parameter: neither route
accepts an organization in its path, query, or body, so there is nothing to compare and no path on
which a comparison could be skipped.

The alternative — `POST /api/v1/commercial/organizations/{organization_id}/analyses` — is compliant
too, since `for_request` refuses a mismatch. It was rejected because it puts a caller-supplied
identifier on the authorization path where only a comparison protects it, and `R6-01` §5's rule is
that identifiers never grant authority. An identifier that is never accepted cannot grant anything.

An actor changes which organization they act in through `R6-03`'s switch verb, which is the one place
that transition is authorized. Two ways to select an organization would be the accumulation `R6-03`
refused.

## 5. The authorization path

```
cookie (khepri_session, CommercialSessionCookie)
        |
resolver.for_request(token, organization_id=None, now=clock())   <- live (FR-030, FR-008)
        |
AuthorizationContext(account_id, organization_id)
        |
bridge.open(...) / bridge.resume(...)                            <- resolve_scope, live again
        |
owner_id                                                         <- the only thing crossing (FR-032, FR-033)
```

**Two live checks, and both are deliberate.** `for_request` refuses a disabled account at
authentication (`ActorResolver` step 3, `R3-05`); `resolve_scope` refuses a non-member and a disabled
account inside the bridge. `R7-03` proved these two layers refuse independently
(`TestBothLayersRefuseIndependently`), and this route composes exactly the pair it tested. The route
adds no third check: `KHEPRI-DEC-022` §3 forbids authorization inside RRA, and a check here would be
a second site for a rule that has one door.

**The token source is the cookie only.** `CommercialSessionCookie` (`rca/session_cookie.py:44`) is a
FastAPI `Cookie` annotation, so no body or query field can supply a token. A route accepting one
would create a second resolution path.

## 6. Every refusal is one `404`

| Cause | Raised by | Response |
|---|---|---|
| No cookie, expired, or revoked session | `AuthenticationFailed` | `404`, empty body |
| Non-member, disabled account, unknown organization | `ScopeAccessDenied` | `404`, empty body |
| No such analysis | `resume` returns `None` | `404`, empty body |
| Analysis belongs to another scope | `resume` returns `None` | `404`, empty body |

**All four are byte-identical.** This is `FR-025`'s indistinguishability requirement, and each
plausible alternative breaks it:

- A `401` for authentication and `404` for a missing analysis separates "not authorized" from "does
  not exist" — the enumeration oracle `R6-03` closed on the switch path and `FR-004`/`FR-022` forbid.
- A `403` confirms the analysis exists, which is the same leak in one step.
- Any distinguishing body reintroduces it below the status code.

Timing cannot leak either: authorization precedes every lookup, which the bridge enforces rather than
the route.

`404` is chosen over `403` because the honest statement to an unauthorized caller is that there is
nothing there for them.

## 7. Evidence this slice owes

Five groups. All live in `tests/test_r705_commercial_http_surface.py` except the tripwire replacement,
which edits `R6-08`'s file in place.

1. **The surface works.** A member opens an analysis, resumes it, and reads their own organization's
   scope. Includes a fixture-reaches-RRA assertion, so a later failure cannot be a fixture that
   never got there.
2. **Cross-organization refusal.** Actor A cannot resume actor B's analysis, and the response is
   byte-identical to a nonexistent `session_id` — asserted by comparing the two responses, not by
   checking each against a literal.
3. **Live authorization at the HTTP layer.** Revoked, disabled and demoted actors driven through the
   route rather than the bridge. `R7-03` proved the bridge re-resolves; this proves the route does
   not cache or bypass it. The demoted-owner case must still succeed, keeping the guard from being a
   blanket refusal.
4. **Uniform refusal matrix.** Every cause in §6 asserted to produce the same status and body, in one
   parametrized case so a new cause cannot be added without a row.
5. **`R6-08`'s tripwire replaced.** `test_the_resolver_has_no_production_consumer_yet` is deleted.
   Its replacement asserts `khepri/runtime/commercial_api.py` is the **only** production importer of
   `AuthorizationResolver` outside `authorization_resolution.py`, and carries an emptiness assertion
   so it cannot pass by finding nothing to scan. Relaxing the original — widening its allowlist and
   keeping its name — is forbidden by `KHEPRI-DEC-022` §2, because the name would then assert
   something false.

**Mutation evidence is required, not optional.** `#231` records the cost of shipping an evidence
suite with none. Three mutants, each with a named killer:

| Mutant | Expected killer |
|---|---|
| `for_request` → `resolve` | a test asserting a request cannot select a non-active organization |
| Return `403` instead of `404` for one refusal cause | the uniform-refusal matrix |
| Drop the `services is None` guard | an unwired-app test asserting the route is absent |

Verify each mutant actually introduces the defect before concluding a test is weak; a malformed
mutant proves nothing.

**Two tests change state when this lands, by design.** `R6-08`'s tripwire is replaced per §5 above,
and `R6-05`'s matrix tripwire fires because a production consumer now exists. Per `KHEPRI-DEC-022`
§2's fourth bullet it needs **no new matrix row** — only its consumer inventory updates. A green run
before this slice is not evidence either was covered.

## 8. What this note does not settle

- **The twelve `RCA-001` requirements' closure.** `FR-008`, `FR-009`, `FR-021`…`FR-026`, `FR-028`,
  `FR-031`, `FR-034`, `FR-038` move with this slice, but which are *closed* versus merely *reached*
  is the implementation's report, not this note's claim.
- **Response payload fields beyond `session_id`.** What a resumed analysis returns is RRA's existing
  shape; this note does not redefine it.
- **Pagination or a most-recent list.** `KHEPRI-DEC-021` §114 notes a surface may present one. Not
  in scope: `owner_id` is deliberately non-unique, so a list needs a selection rule no record makes.
- **`R7-06`.** The end-to-end cross-organization and nonexistence suite is the next slice and depends
  on this one. §7's group 2 is a unit-level claim, not a substitute for it.
- **Any UI.** `KHEPRI-DEC-022` §3 excludes it; `R8` owns templates.
