# KHEPRI-DEC-022: Authorization to implement the commercial HTTP surface

> Active. **Supersedes `KHEPRI-DEC-021`**, which is retired by this record. Stands beside
> `KHEPRI-DEC-014` and `KHEPRI-DEC-018`.
>
> `active` is the only non-retired state the registry admits (`validator.py:15`), and a branch is a
> proposal until the owner merges it (`AGENTS.md`). This record is therefore written in its merged
> form and is **not governing until that merge** — the header states the state it will hold, not a
> claim that it already holds it. `R7-05` may not begin before the merge.

## Context

`KHEPRI-DEC-021` (`d93b844`) authorized the bridge and the RRA scoped-session entry point, and
`R7-07` delivered both. Its §5 then withheld the surface that would call them, in terms:

> **No endpoint.** `R7-05`'s HTTP surface is not settled, proposed, or implied. `R7-07` places the
> bridge in `khepri.runtime` so that surface *can* consume it later, and wires nothing to a route.

That bullet is the only thing blocking `R7-05`. `R7-01` §7 withheld the same thing from the design
side — "No endpoint shape is proposed here, deliberately" — so **no merged document proposes a
surface**, and the slice cannot proceed by reading one.

**Supersession is the only available instrument, and this is the fourth time it has been.**
`KHEPRI-DEC-017` makes supersession whole-document; editing `KHEPRI-DEC-021` to admit what it
forbids would rewrite history rather than correct it, and its own Consequences state that a
superseded document *"remains in place as history and must not be edited to match this one."* The
same applies to it now.

**Why this record does more than lift one bullet.** Probing the seam before authorizing it — the
method `KHEPRI-DEC-020`'s closing lesson asks for and `KHEPRI-DEC-021` followed — surfaced three
things the merged documents do not settle, each of which would otherwise be decided by whoever
implements `R7-05`:

1. **Three resolver methods exist and nothing says which one an endpoint calls.**
   `AuthorizationResolver` exposes `resolve`, `for_request`, and `require_owner`
   (`authorization_resolution.py:73`, `:89`, `:115`). They are not interchangeable at a route:
   `for_request` refuses an organization the caller *is* a member of when it is not the session's
   active one (`FR-027`), while `resolve` accepts whatever the session names and compares nothing.
   Choosing wrongly decides whether an organization named in a request is honored or compared —
   which is `R6-01` §5's "object identifiers never grant authority" rule at the only place it can
   actually be broken. §2 settles it.
2. **A required test replacement is described only in a docstring.** `R6-08`'s
   `test_the_resolver_has_no_production_consumer_yet`
   (`tests/test_rca001_resolver_chokepoint.py:465`) says it "currently guards an empty room" and
   that the inventory is "*preventative* rather than confirmatory". `R7-05` is the slice that fills
   the room, so the test must flip rather than merely go red. Nothing merged states what it becomes.
   §2 settles it.
3. **`R6-01` §3.1's open row was left to the implementer.** `R7-01` §7: "Whether `R6-01` §3.1 gains
   a row for 'open an analysis session'. It probably should, and that is `R7-05`'s call once the
   endpoint exists." `KHEPRI-DEC-021`'s Consequences add that adding the row changes what the matrix
   tripwire demands. A slice deciding its own matrix row decides its own authorization rule. §2
   settles it.

## Decision

### 1. Everything `KHEPRI-DEC-021` decided is carried forward unchanged

Its §1 (the shape `KHEPRI-DEC-019`/`-020` admitted), §2 (the bridge, the entry point, the resume
query, the store path), §3 (the bridge lives in `khepri.runtime`), and §4 (what was checked) stand
as written. `R7-07` is merged under them and nothing here reopens it.

### 2. What this record additionally authorizes

**`R7-05` may implement a commercial HTTP surface**, bounded to the four decisions below.

- **The endpoint calls `for_request`, never `resolve`.** Any organization named in a request is
  passed to `for_request` as `organization_id`, so a caller naming an organization that is not the
  session's active one is refused with the same content-free `ScopeAccessDenied` the switch path
  uses. A route calling `resolve` and then handing the request's organization to the bridge would
  make the session's active organization advisory and reopen the enumeration oracle `R6-03` closed.
  `require_owner` is not used: opening and resuming an analysis are not owner-only verbs, per the
  matrix row the fourth bullet below identifies.
- **The session token arrives from the cookie, never from the request body or path.**
  `CommercialSessionCookie` (`rca/session_cookie.py:44`) is the only admitted source. A `session_id`
  in a URL names an analysis and confers nothing (`FR-023`); the bridge already refuses on that
  basis, and the route must not create a second path where a body-supplied token could be resolved.
- **`R6-08`'s tripwire is replaced, not relaxed.**
  `test_the_resolver_has_no_production_consumer_yet` is deleted and replaced by a test asserting the
  inverse: the commercial route module is the *only* production importer of `AuthorizationResolver`
  outside `authorization_resolution.py`. It must carry an emptiness assertion so it cannot pass by
  finding nothing to check. Relaxing the original — widening its allowlist and keeping its name — is
  specifically not authorized: the name would then assert something false.
- **`R6-01` §3.1 gains no new row.** Opening or resuming an analysis session *is* `resolve_scope`
  followed by a mint that performs no authorization (`runtime/bridge.py`), and "Resolve an isolation
  scope" is already **PERMIT / PERMIT / DENY / DENY** at §3.1. A second row would state the same
  rule twice and let the two drift. The matrix tripwire therefore keeps its current row count, and
  `R7-01` §7's open question is answered **no**, with that reason.

### 3. What this record still does not authorize

Every exclusion in `KHEPRI-DEC-021` §5 other than its first bullet is carried forward intact:

- **No further schema change.** `rra_uploads.UNIQUE (session_id)` stands.
- **No `RRA-001`, `RRA-002`, or `RCA-001` amendment.**
- **No change to `redeem`**, its signature, its behavior, or the invitation lifecycle.
- **No authorization inside `RRA`.** The caller is authorized before RRA is reached; a second check
  would put one rule in two places.
- **No commercial identifier crossing the boundary.** `FR-032` and `FR-033` unaffected.
- **No UI.** `R8`'s templates are a separate program. This authorizes an HTTP surface, not a screen.
- **No beta-mode change.** `R7-04`'s regression tests must stay green unmodified; a participant with
  no account is unaffected.

## Consequences

- **`R7-05` is unblocked** and may proceed once this record is merged, within §2's four bounds. It
  remains a separately reviewed slice.
- **`R7-06` remains blocked on `R7-05`**, not on governance — it is the end-to-end cross-organization
  and nonexistence-indistinguishability suite, and needs the surface to drive.
- **Two tests are expected to change state when `R7-05` lands, by design, and a green run before
  them is not evidence of coverage.** `R6-08`'s tripwire is replaced per §2; `R6-05`'s matrix
  tripwire fires because a production consumer appears, and §2's fourth bullet means it needs no new
  row — only its consumer inventory updates.
- **Twelve `RCA-001` requirements move with `R7-05`**: `FR-008`, `FR-009`, `FR-021`…`FR-026`,
  `FR-028`, `FR-031`, `FR-034`, `FR-038`. They did not move with `R7-07`, which reached no handler.
- **`KHEPRI-DEC-021` remains in place as history and must not be edited to match this record.**
  `KHEPRI-DEC-017`'s rule applies to it exactly as `-021` applied it to `-020`.
- **This record settles a surface, not its shape in detail.** Route paths, payload fields, and status
  codes are `R7-05`'s design note to propose under §2's bounds. What §2 fixes is the authorization
  path, the token source, the tripwire replacement, and the matrix answer — the four things that
  would otherwise be decided silently by implementation.
