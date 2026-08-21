# KHEPRI-DEC-023: Authorization for the commercial consent route

> Active. **Supersedes `KHEPRI-DEC-022`**, which is retired by this record. Stands beside
> `KHEPRI-DEC-014` and `KHEPRI-DEC-018`.
>
> `active` is the only non-retired state the registry admits (`validator.py:15`), and a branch is a
> proposal until the owner merges it (`AGENTS.md`). This record is therefore written in its merged
> form and is **not governing until that merge** — the header states the state it will hold, not a
> claim that it already holds it. `R7-06` may not implement the route before the merge.

## Context

`KHEPRI-DEC-022` (`00a0918`) authorized `R7-05`'s commercial HTTP surface, and `R7-05` delivered it
(`9802586`). `R7-06` is the last task in `R7` and owes end-to-end evidence closing the twelve
`RCA-001` requirements the program moves, eight of which `R7-05` reached without proving.

Designing that evidence surfaced a defect rather than a gap in testing. **`FR-038` is not satisfiable
at the current surface**, so no test suite can close it:

> **FR-038**: Consent before upload, the immutable automated-report disclosure, the reconciliation
> and provenance controls, and Arabic/English language parity MUST continue to hold for a commercial
> actor exactly as they hold for a beta participant.

Three facts, each verified against the code rather than inferred:

1. **Consent-before-upload is enforced at the service layer, and therefore already binds a
   commercial actor.** `IntakeService.begin` calls `require_upload_consent`
   (`rra/intake.py:188`), which raises `ConsentRequired` when `consent_version is None`
   (`rra/sessions.py:206`). This is not per-route, so it applies to a commercial session with no
   change.
2. **`open_commercial_session` creates every session with `consent_version=None` and
   `consented_at=None`** (`rra/sessions.py:104`). That is correct — consent has not been given —
   and it is also permanent, because of (3).
3. **The only way to record consent is `POST /api/v1/beta/consent`, which reads the beta cookie**
   `khepri_beta_session` (`rra/api.py:184`, `session_cookie.py:27`). A commercial actor holds
   `khepri_session` and never holds the beta cookie, and `open_commercial_session` deliberately
   bypasses `redeem`, which is what issues it.

Together: a commercial actor is permanently blocked from consenting, so every upload they attempt
fails closed forever. `FR-038`'s "exactly as they hold for a beta participant" is false today, and a
suite asserting it would either fail or be written to assert something weaker.

**A probe confirmed the shape of the fix before this record was written.** `record_consent` takes a
plain `session_id` (`rra/sessions.py:177`), and calling it directly against a commercial session
records consent successfully. The service layer is already surface-agnostic; only the HTTP handler is
beta-bound. So the fix is one thin route, not a second consent implementation.

**Why this needs a record at all.** `KHEPRI-DEC-022` §2 authorizes "a commercial HTTP surface" for
**`R7-05`**, bounded to four decisions, none of which contemplates a consent route. A third endpoint
in a different slice is outside that grant. `KHEPRI-DEC-017` makes supersession whole-document, so
this retires `-022` rather than editing it — the fifth use of the instrument, and `-022`'s own
Consequences forbid editing a superseded record to match its successor.

## Decision

### 1. Everything `KHEPRI-DEC-022` decided is carried forward unchanged

Its §1 (which carried forward `-021` §§1–4) and §2's four bounds stand as written. `R7-05` is merged
under them and nothing here reopens it. In particular `for_request`-not-`resolve`, the cookie as the
only token source, the replaced `R6-08` tripwire, and **no new `R6-01` §3.1 row** all continue to
hold, and the route authorized below is bound by them too.

### 2. What this record additionally authorizes

**`R7-06` may add one commercial consent route**, bounded to the four decisions below.

- **`POST /api/v1/commercial/analyses/{session_id}/consent`.** It sits under the analysis it
  consents for, because consent is a property of one analysis session rather than of the actor. The
  beta route is untouched and keeps its path, its cookie, and its behavior.
- **It reuses `InvitationService.record_consent` and adds no consent logic.** The service already
  accepts a plain `session_id` and is surface-agnostic; a second implementation is how two consent
  answers eventually differ. `require_upload_consent` stays the single enforcement point and is not
  called from the route.
- **Authorization is `for_request` then the bridge, exactly as the other two routes.** The handler
  resolves the cookie through `for_request(organization_id=None)`, then confirms the named analysis
  belongs to the resolved scope **through `CommercialBridge.resume`** before recording anything. A
  route that recorded consent against a `session_id` it had not scope-checked would let one
  organization write to another's analysis, which is the `FR-023` violation the resume path exists
  to prevent.
- **Every refusal is the same empty-body `404`** the other two routes return — including an absent
  analysis, another scope's analysis, and a session whose content has expired. `FR-025` and `FR-034`
  admit no second refusal shape, and a `409` or a `403` distinguishing "already consented" from "not
  yours" would be a disclosure oracle.

### 3. What this record still does not authorize

Every exclusion in `KHEPRI-DEC-022` §3 is carried forward intact:

- **No further schema change.** `rra_uploads.UNIQUE (session_id)` stands; `BetaSession` already
  carries `consent_version` and `consented_at`, so the route needs no column.
- **No `RRA-001`, `RRA-002`, or `RCA-001` amendment.** `FR-038` is satisfied by making the product
  match it, never by amending it.
- **No change to `redeem`**, its signature, its behavior, or the invitation lifecycle.
- **No change to the beta consent route.** `POST /api/v1/beta/consent` keeps its path, cookie, and
  status code, and `R7-04`'s regressions must stay green unmodified.
- **No authorization inside `RRA`.** The caller is authorized before RRA is reached.
- **No commercial identifier crossing the boundary.** `FR-032` and `FR-033` unaffected: the route
  passes a `session_id` and a consent version, and nothing else.
- **No UI.** `R8` owns templates. This authorizes an endpoint, not a screen.
- **No change to `require_upload_consent`.** It is already correct for both actor kinds; the defect
  was the missing way to satisfy it, not the enforcement.

## Consequences

- **`R7-06` is unblocked** and may proceed once this record is merged, within §2's four bounds. It
  remains a separately reviewed slice.
- **`R7-06` is the last task in `R7`.** Its definition of done includes flipping §16's `R7` row from
  `READY_FOR_IMPLEMENTATION` to `MERGED` — the one status transition only a final slice performs.
- **`FR-038` is closable only if the route lands.** Its other three clauses — the immutable report
  disclosure, the reconciliation and provenance controls, and Arabic/English parity — are properties
  of the report pipeline that a commercial actor reaches through the same services as a beta
  participant, so they hold by shared implementation. Consent was the one clause a commercial actor
  could not reach. A slice claiming `FR-038` closed must show evidence for all four clauses, not
  only the one this record unblocks.
- **The remaining seven requirements are unaffected by this record.** `FR-009`, `FR-021`, `FR-024`,
  `FR-026`, `FR-028`, `FR-031` and `FR-034` need evidence, not product changes. `FR-024` deserves a
  note: `R7-05` accepts no organization in any request, so "a request whose actor and whose named
  organization scope disagree" cannot be constructed at this surface. It is satisfied **by absence**,
  and a slice claiming it closed must say so rather than implying a comparison was tested.
- **`KHEPRI-DEC-022` remains in place as history and must not be edited to match this record.**
  `KHEPRI-DEC-017`'s rule applies to it exactly as `-022` applied it to `-021`.
- **This defect is the reason design preceded testing here.** `R7-06` was scoped as a test-only
  slice; probing the seam found product code that could not satisfy a requirement the slice was
  meant to close. A suite written without that probe would have asserted something weaker and
  reported it as coverage.
