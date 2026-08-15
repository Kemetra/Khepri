# R6-01 — the protected-action catalog and the authorization matrix

**Task:** `R6-01` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Output is a matrix and a
contract, not code.

**Baseline:** `main` @ `6c93dea`, 2026-08-15 (`R3-10` merged; `R3-11` blocked on provider
admission).

**Depends on:** `R2`'s role model (merged) and `R3`'s session design (merged through `R3-10`). Both
met.

**What this note settles:** which operations are protected, what "protected" means for each, and
what every combination of `{owner, member, non-member, unauthenticated}` must produce. **What it
does not settle** is in §7 — the context type is `R6-02` and the resolver is `R6-04`.

---

## 1. The state this note describes, stated first

> **Correction, 2026-08-15 (`R6-03`).** The first version of this section claimed these verbs "take
> no caller". That is wrong: `promote_to_owner`, `demote_to_member`, and `revoke_membership` each
> take a keyword-only `actor_account_id` (`organizations.py:348`, `:387`, `:416`). The error came
> from reading only the first four lines of each signature, which stop before the keyword-only
> section. The corrected claim is below, and it is narrower but still the gap `R6` closes.

**Every membership verb names an actor, and none of them checks it.** `actor_account_id` flows
into `MembershipEvent` for `FR-014`'s attribution (`organizations.py:194`, `:209`, `:224`) and is
never compared against a role, a membership, or anything else. A caller may pass any account
identifier, including one holding no membership in the organization it names.

So the gap is not a missing parameter — it is a recorded parameter that authorizes nothing. The
audit trail will faithfully attribute a promotion to whoever the caller *said* performed it.

That is deliberate rather than an oversight, and `R2` recorded the adjacent reasoning: the role
model is CHECK-constrained and the domain accepts any string as a role, but *"what prevents forgery
today is that no service takes a role as input"* (`NEXT-SLICES.md`, `R2` findings). The parallel
here is exact — an unchecked actor is forgeable in precisely the way an unchecked role would be.

This holds only while nothing outside the package can reach a store. `R3-04` and `R3-05` have now
built the first path from an HTTP-shaped credential to an identified actor, so the window in which
"no caller exists" is an adequate defence is closing. The matrix below is what must become true
before a route calls any of these verbs; it is not a description of current behavior.

## 2. Two kinds of protected action, and why the distinction is load-bearing

A matrix over `{owner, member, non-member, unauthenticated}` is only well-formed for actions that
happen *inside an organization*. Asking whether a "non-member" may disable their own account is a
category error: the question has no organization in it.

So the catalog is split, and each half gets a different matrix shape.

**Organization-scoped** — the actor's role *in the organization named by the request* decides:

| Action | Code | Scenario |
|---|---|---|
| Promote a member to owner | `organizations.py:343` | 10 |
| Demote an owner to member | `organizations.py:411` | 10 |
| Revoke a membership | `organizations.py:382` | 11 |
| Resolve an isolation scope | `isolation.py:30` | 12, 14, 15 |
| Switch the active organization | `R6-03`, unbuilt | 13 |

**Account-scoped** — the actor's relationship to the *account named by the request* decides, and
role is irrelevant:

| Action | Code | Scenario |
|---|---|---|
| Disable an account | `lifecycle.py:105` | 16 |
| Re-enable an account | `lifecycle.py:127` | — |
| Create a session | `session_service.py:64` | 2 |
| Revoke one session | `session_service.py:95` | — |
| Revoke every session for an account | `session_service.py:113` | 4 (`R5-05`) |
| Link or unlink an external identity | `session_service.py:125`, `:148` | — |

**Unprotected, deliberately:** `create_account` (scenario 1 — an account is what an actor *becomes*,
so requiring one first is circular) and `create_organization` (scenario 5 — any authenticated actor
may create one, and the creator becomes its owner atomically). Both still require the caller to be
authenticated where they are reached over HTTP; neither consults a role.

## 3. The matrix

`RCA-001`'s Verification section requires: *"An authorization matrix test asserts, for every
combination of `{owner, member, non-member, unauthenticated}` against every protected action, that
the outcome is the specified permit or the specified fail-closed denial."*

`PERMIT` means the operation proceeds. Every denial is `AUTHENTICATION_FAILURE` or the
action's existing content-free refusal — never a message naming the cause, per `FR-004` and
`FR-022`.

### 3.1 Organization-scoped actions

| Action | owner | member | non-member | unauthenticated |
|---|---|---|---|---|
| Promote to owner | **PERMIT** | DENY | DENY | DENY |
| Demote to member | **PERMIT** | DENY | DENY | DENY |
| Revoke a membership | **PERMIT** | DENY¹ | DENY | DENY |
| Resolve an isolation scope | **PERMIT** | **PERMIT** | DENY | DENY |
| Switch active organization | **PERMIT** | **PERMIT** | DENY | DENY |

¹ A member revoking *their own* membership (leaving an organization) is a plausible product
behavior and is **not** in this matrix, because no operation expresses it. If one is added, it is a
distinct action with its own row, not a widening of this cell — "revoke any membership" and "revoke
my own" differ by exactly the authority this matrix exists to hold.

### 3.2 Account-scoped actions

The relevant distinction is *self* versus *another account*, so the columns change. `FR-015`'s
owner-capability clause names no cross-account power, and nothing in `RCA-001` grants one account
authority over another.

| Action | self | another account | unauthenticated |
|---|---|---|---|
| Disable an account | **PERMIT** | DENY | DENY |
| Re-enable an account | DENY² | DENY² | DENY |
| Create a session | n/a³ | DENY | n/a³ |
| Revoke one session | **PERMIT**⁴ | DENY | DENY |
| Revoke every session for an account | **PERMIT** | DENY | DENY |
| Link / unlink an external identity | **PERMIT** | DENY | DENY |

² **Re-enablement has no authorized caller in this model, and that is a finding rather than an
omission.** A disabled account cannot authenticate (`can_act` is false, so `assert_account_active`
refuses), so it cannot re-enable itself; and no account holds authority over another. The capability
exists in code (`lifecycle.py:127`) and `KHEPRI-DEC-015` §2b's rationale depends on it — an account
must be restorable "after a dispute, an erroneous disablement, or a lapsed commercial
relationship". See §6.

³ Creating a session *is* authentication. It is protected by credentials, not by this matrix.

⁴ Revoking a session requires presenting its token, which is the authorization. A caller holding
the token is the session's holder by construction.

### 3.3 The two scenarios the matrix must reproduce

Scenario 18 (authenticated, no organization): every cell in §3.1 is `DENY`, because the actor is a
non-member of every organization. `FR-028` requires them to authenticate successfully anyway, which
§3.2 permits.

Scenario 19 (stale or invalid session): the `unauthenticated` column of both tables. The actor is
never established, so no row is reached.

## 4. What is *not* an authorization rule, and must not become one

**`FR-013`'s final-owner guard.** `apply_owner_reducing_change` refuses to remove or disable an
organization's last effective owner **regardless of who asks** — including an owner acting on
themselves, which is the common case. That is an *invariant*, not a permission: it constrains the
resulting state, not the caller.

Conflating them would put the guard in two places. `R2` built `apply_owner_reducing_change`
precisely so one expression of the rule sits inside the transaction that writes, and `R1`'s residual
defect (`#175`) showed what happens when a guard's read and its write can diverge. `R6-04` must call
these verbs and let them refuse; it must not re-check ownership before calling.

The observable consequence, and it is deliberate: an owner attempting to demote themselves as the
final owner is **PERMIT** in §3.1 and still fails, with `FINAL_OWNER_FAILURE`. Authorization
succeeded; the invariant refused. Scenario 17 requires exactly this, and `FR-013` requires the
refusal to name its cause — the one deliberate exception to the content-free rule, because the
caller is already a member and there is nothing left to disclose.

**Account status.** `assert_account_active` is `R3-05`'s chokepoint and runs *before* the matrix is
consulted. A disabled account is refused at step 3 of the `R3-01` §4 path and never reaches a role
lookup. Scenario 16 is satisfied there, not here.

## 5. The ordering contract

`KHEPRI-DEC-018` §4 fixes the request model, and `R3-01` §4 states the same order for internal
sessions. `R6-04` implements steps 4 onward:

```
verified identity (R3-10 seam, or FR-002 credentials)
        |
Khepri session lookup                    <- R3-04
        |
live account-status check                <- R3-05   [scenario 16]
        |
live membership lookup                   <- R6-04   [scenarios 18, 20]
        |
live role lookup                         <- R6-04   [scenario 10]
        |
resource-organization check              <- R6-04   [scenarios 14, 15]
        |
ALLOW / DENY
```

**No step may be skipped, cached, or reordered.** Every lookup is live: `FR-030` requires a
membership or role change to take effect for decisions made after it *without the session ending*,
and `FR-008` requires disablement to stop authorization without waiting for expiry. A value
memoized at any step is a value that is wrong exactly when it matters.

**The critical rule, restated because it is easy to violate accidentally.** The roadmap states:
*"Object identifiers never grant authority. Every object lookup must be scoped from the
authorization result, not trusted from a route parameter."* An implementation that reads
`organization_id` from a request and passes it to `resolve_scope` has authorized nothing — it has
let the caller name their own scope. The organization must come from the actor's *session* (its
active organization) and the membership lookup must confirm it, before any object is fetched.

## 6. Question for the owner

**Who may re-enable a disabled account?**

The matrix has no `PERMIT` cell for it (§3.2, note 2): a disabled account cannot authenticate to
re-enable itself, and no account holds authority over another. So `lifecycle.enable_account` is
today reachable only by code with a store in hand, and under this matrix it would become reachable
by nobody.

That cannot be the intent — `KHEPRI-DEC-015` §2b's twenty-four month horizon is justified partly by
restoration being possible. Three candidate answers, none of which this note takes:

- **An operator capability outside the commercial authorization model**, exercised through an
  administrative path `RCA-001` does not describe. Consistent with `FR-015` naming no cross-account
  power, and with §11 of `KHEPRI-DEC-018` not authorizing an admin role.
- **A support-initiated flow with its own governance**, which would need a decision record.
- **Recovery (`R5`) subsuming it**, so a disabled account's route back is the recovery secret rather
  than re-enablement. Note this conflicts with `KHEPRI-DEC-015` §5, which leaves the verifier
  destroyed — recovery would have to *set* a credential, not restore one.

Recommendation: **the first**, recorded as an exclusion in `RCA-001` rather than as a matrix cell,
since an operator capability is precisely what the commercial authorization model is not.

**A smaller one, resolved here rather than left open.** Is `resolve_scope` a protected action or a
primitive the resolver calls after authorizing? It is listed in §3.1 as protected, but
`isolation.py:30` already refuses a non-member uniformly, so it would be authorized twice. I keep it
in the matrix because `RCA-001`'s Verification section requires the matrix to cover *every*
protected action and scenario 12 names scope resolution directly — but `R6-04` should treat
`isolation.py`'s existing refusal as the enforcement and not add a second check. Recorded so the
duplication is a deliberate belt-and-braces rather than an accident.

## 7. What this note does not settle

- **The authorization context type.** `R6-02` — including what makes it unconstructible by
  handlers, which is that task's whole point.
- **Active-organization selection and switching.** `R6-03`. `Session.switched_to` exists and
  deliberately validates nothing; the service that authorizes a switch is `R6-03`'s.
- **The resolver itself.** `R6-04`. This note says what it must decide, never how.
- **Any change to the three membership verbs' signatures.** They already take `actor_account_id`
  for attribution, so `R6-04` may not need a signature change at all — it needs the actor to be
  *checked* rather than merely recorded, and where that check lives (the service, or the resolver
  that calls it) is `R6-04`'s decision. Note that the parameter's current meaning is "who to
  attribute this to", and authorization would give it a second meaning; whether those should stay
  one parameter is worth deciding rather than assuming.
- **Invitation and recovery actions.** `R4` and `R5` add rows to §3.1 and §3.2 respectively; the
  matrix is extended by those programs, not pre-populated here.
