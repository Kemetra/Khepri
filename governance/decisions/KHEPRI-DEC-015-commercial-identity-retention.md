# KHEPRI-DEC-015: Commercial identity retention under Constitution VII

## Context

Constitution VII requires that "new data use requires an explicit purpose, owner, boundary,
retention decision, and approval." `RCA-001` proposes Khepri's first durable commercial identity:
accounts, credentials, authentication sessions, recovery, organizations, memberships, invitations,
and the authorization records over them. Storing an email address durably is new data use, so
Article VII binds.

`KHEPRI-DEC-014` §2 anticipated exactly this. It records that collecting "a profile, billing
identity, and email owner key becomes permitted — that is what commercialization means — and each
requires its own retention decision under Constitution VII," and §3 states that this decision
"permits that decision to be written; it does not pre-approve its content." `RCA-001`'s
implementation precondition 3 names the same obligation. This decision discharges the writing of
it; approval remains separate.

### Why existing retention authority does not settle this

A repository-wide search finds retention rules in `KHEPRI-DEC-005`, `KHEPRI-DEC-007`,
`KHEPRI-DEC-008`, `RRA-002`, and the superseded `KHEPRI-DEC-003`. **None of them covers commercial
identity**, and none is a qualifying authority here.

Every one of them governs *retail content* under the private beta's seven-day expiry.
`KHEPRI-DEC-007` sets a seven-day backup retention and justifies it explicitly: it "matches the S3
seven-day expiration rule so that no single retention horizon is quietly longer than another."
That anchor does not exist for commercial identity. `KHEPRI-DEC-014` §2 **replaced** the seven-day
expiry for durable identity, because an account whose purpose is to survive a session cannot be
scoped to a session's lifetime.

Two principles from that body of work do transfer, and this decision adopts them by name rather
than reinventing them:

- **`KHEPRI-DEC-005`**: "Database backups and restore exercises protect operational state while
  content-retention and deletion rules continue to apply."
- **`KHEPRI-DEC-007`**: no single retention horizon may be quietly longer than another.

What does not transfer is the **number**. Seven days was derived from an object-expiry rule that
no longer governs this data class, and reusing it because it exists would be exactly the
unjustified reuse this decision must avoid.

### The governing principle

> Retain the minimum data, for the minimum justified duration, for a named purpose.

Retention here is **lifecycle-derived wherever a lifecycle exists**. A fixed duration is used only
where lifecycle state alone cannot answer the question, and every such duration that is not
derivable from repository evidence is left as an explicit owner decision rather than invented.

## Decision

### 1. Scope

This decision governs the retention of **commercial identity and authorization data** required by
`RCA-001`, and nothing else. Every data class below is required by a named `RCA-001` requirement;
a class with no such anchor is out of scope by construction.

**Commercial identity retention is not customer retail-content retention.** These are separate
governed facts with separate authority. Approval of this decision grants no authority over retail
uploads, derived facts, narratives, or report bundles, whose retention remains governed by
`RRA-002` and is unchanged here.

### 2. Retention matrix

This matrix is **authoritative**. Where prose below and this matrix could both be read as settling
a lifecycle rule, the matrix governs; the prose covers only invariants a table cannot express.

"Active retention" is the period the record is usable for its purpose. "Post-trigger state"
describes what remains, if anything, after the end trigger fires.

| Data class | Purpose | Active retention | End trigger | Post-trigger state | Deletion rule | Backup rule | Anchor |
|---|---|---|---|---|---|---|---|
| **Account** | Establish one durable authenticated actor | While enabled; **24 months** after disablement | Elapse of 24 months from disablement (§2b) | Non-authenticating record until the horizon elapses, then minimized to an opaque tombstone | Identity fields purged at the horizon (§2b) | Bounded backups; restore must not re-enable a disabled account (§8) | `FR-001`, `FR-008` |
| **Login identity (email)** | Authentication, account recovery, and addressing an invitation to a person | While enabled; **24 months** after disablement | Elapse of 24 months from disablement (§2b) | **Purged.** Nothing remains | Purged at the horizon, not retained for duplicate prevention beyond it | Bounded backups | `FR-001`, `FR-005`, `FR-019`, `A-1` |
| **Credential verifier (hash)** | Verify an authentication attempt | While the account is enabled | Account disabled, or credential replaced | **Destroyed** on replacement; destroyed on disablement | Immediate, non-recoverable | Superseded verifiers must not survive in backups beyond the bounded backup horizon | `FR-002` |
| **Authentication session** | Carry one authenticated actor and at most one active organization | Until expiry or revocation | Expiry; revocation; recovery completion (`FR-007`); account disablement (`FR-008`) | Record may persist only until purged; it authorizes nothing from the trigger instant | Purge on or after the trigger; **retention never delays revocation** (§5) | Restore must not reactivate a revoked or expired session (§8) | `FR-003`, `FR-007`, `FR-008`, `FR-030` |
| **Recovery request** | Permit one account recovery | Until first use or expiry | Use; expiry; replacement by a newer request | Verifier **destroyed**; a content-free event record may remain as security evidence | Verifier destroyed immediately at the trigger | Used or expired verifiers must not be restorable as usable | `FR-005`, `FR-007` |
| **Invitation** | Offer one membership at one named role | Until accepted, expired, or revoked | Acceptance; expiry; revocation; revocation of the inviting membership (`FR-020`) | Verifier **destroyed**; status and target identity retained only while needed to refuse replay and to attribute the resulting membership | Verifier destroyed at the trigger; record purged when replay refusal no longer needs it | Restore must not make a redeemed or expired invitation usable | `FR-016`, `FR-017`, `FR-020` |
| **Organization** | Own retail content as a durable scope distinct from accounts | While the organization exists | Organization disabled (`FR-015`); deletion is not authorized here | Record persists, authorizing nothing | No deletion path authorized by this decision — see §6 | Bounded backups | `FR-009`, `FR-015` |
| **Membership** | Bind one account to one organization at one role | While the membership is active | Revocation; organization disablement | Record retained only as the subject of the `FR-014` audit event; it authorizes nothing from the revocation instant | Purge when no longer required by the audit event's own retention | Restore must not reinstate a revoked membership as active (§8) | `FR-011`, `FR-012`, `FR-030` |
| **Role** | Determine permitted actions within one organization | While the membership is active | As membership | As membership | As membership | As membership | `FR-015` |
| **Role/membership audit event** | Attribute who changed which membership, from which role to which, and when | **12 months** from the event | Elapse of 12 months | Content-free record: opaque actor ID, opaque membership ID, prior role, next role, timestamp | Purge on elapse | Bounded backups | `FR-014`, `FR-040` |
| **Security/authorization audit event** | Detect and investigate authentication and authorization abuse | **12 months** from the event | Elapse of 12 months | Content-free record; narrowest identifier sufficient for the security purpose | Purge on elapse | Bounded backups | `FR-040` |
| **Organization → opaque RRA scope mapping** | Resolve an authorized commercial context to the governed isolation boundary | While the organization exists | Organization ceases to exist | Mapping is stable for the organization's lifetime (`FR-035`) | Not deleted independently of the organization | Restore must not remap an organization to a different scope | `FR-031`, `FR-032`, `FR-035` |
| **Revocation ledger** (§8) | Prevent a backup restore from resurrecting revoked authority as active | Bounded (**OD-3**) | Elapse of the approved backup horizon plus a margin | Opaque IDs, revocation timestamps, and status only | Purge on elapse | Must itself be backed up, or it cannot serve its purpose | §8 |

### 2a. Audit retention is twelve months

Both audit classes retain for **twelve months from the event**, then purge.

**Why a fixed duration at all.** Audit evidence is the one class with no lifecycle anchor. Every
other row ends when something happens — a session expires, an invitation is redeemed, a membership
is revoked. Audit evidence is different: deleting it when the membership it describes ends would
destroy it at precisely the moment it becomes most useful, because an insider action is typically
investigated *after* the actor's access is removed. `FR-014` requires the evidence exist; it does
not say for how long, so this decision must.

**Why twelve months.** It is long enough that an intrusion or insider action discovered on a
delayed cycle can still be investigated and attributed, which is the purpose `FR-014` names. It is
short enough that the store of who-did-what-to-whom does not grow without bound, which
Constitution VII's least-data default requires.

**Why both classes carry the same horizon.** `KHEPRI-DEC-007` establishes the discipline that "no
single retention horizon is quietly longer than another." Giving security events a longer horizon
than role-change events would create exactly that asymmetry, and the two are investigated together
— a role change is often the very event a security investigation is trying to explain.

**What twelve months is not.** It is not derived from `KHEPRI-DEC-007`'s seven days, which was
anchored to the S3 object expiry for retail content and does not transfer. It is a horizon chosen
for this data class on its own terms, and a later decision may revise it on evidence.

### 2b. Disabled accounts are minimized after twenty-four months

A disabled account's record and login identity are retained for **twenty-four months from
disablement**, then the identity fields are purged and only an opaque tombstone remains.

**Why a horizon is required rather than deferred.** Disablement is terminal under `RCA-001`, which
excludes deletion. A terminal state with no horizon is not "retention pending a later decision" —
it is indefinite retention by omission. Former users' email addresses would be held forever while
this decision claimed to bound retention, which is precisely the reading §10 requires it to
refuse. A retention decision that leaves its one terminal state unbounded has not done its job.

**Why twenty-four months.** It is long enough that a disabled account can be re-enabled after a
dispute, an erroneous disablement, or a lapsed commercial relationship, and long enough to outlast
the twelve-month audit horizon so that audit evidence never outlives the subject it refers to. It
is short enough that Khepri is not a permanent archive of people who stopped using it.

**What remains after the horizon: an opaque tombstone.** It holds an opaque account identifier and
the disablement timestamp — **no email address, no credential verifier, no profile data**. Its
only purposes are to keep `FR-014` audit events referentially meaningful for the remainder of
their own twelve-month horizon, and to satisfy §8 item 5 so a restore cannot resurrect the account
as active. It is subject to §4's minimization rule like every other class.

**This does not create the deletion capability `RCA-001` excludes.** The exclusion concerns a
*customer-invoked* operation — "delete my account" as a product feature, with the blast radius
`RCA-001` §Exclusions and §6 both describe. This is a *policy-driven minimization* of data whose
purpose has expired, which is what Constitution VII requires of every retained class and is not a
feature any customer invokes. A later deletion specification remains necessary and remains
governed by §6.

**A-1 is preserved.** Email uniqueness holds across all *live* accounts. Once a disabled account's
email is purged, that address may be registered again — by the same person or another — because no
account claims it any longer. Uniqueness is a constraint over existing identities, not a permanent
reservation of every address Khepri has ever seen.

### 3. Purpose limitation

Each purpose named in the matrix is **exhaustive for that data class**. Retention authorized for
authentication, authorization, recovery, or security audit does not authorize, and must never be
read as authorizing, use of the same data for:

```text
marketing            profiling            AI training or inference
product analytics    billing              cross-product reuse
```

The login identity is the sharpest case: an email address retained to make recovery and invitation
work is **not** thereby available for any message that is not part of those flows. A new purpose is
new data use and requires its own Constitution VII decision.

### 4. Data minimization

No field may be retained because it may become useful later. A field is retained only while it
serves a purpose named in the matrix for its class. This decision authorizes **no** profile data:
no display name beyond an organization's own, no phone number, no address, no photograph, no
marketing preference, and no billing identity.

### 5. Secrets, and the primacy of revocation

**Raw secrets are never retained, in any form, at any point.** Credentials, recovery secrets, and
invitation secrets are persisted only as strong salted one-way verifiers, per `FR-002`, `FR-005`,
and `FR-016`. A verifier whose purpose has ended is destroyed rather than retained: a used or
expired verifier has no remaining purpose and every day it survives is unjustified risk.

Session identifiers are bearer material. They are stored in whatever form the approved
implementation requires to resolve a session, and they are subject to the same rule: no purpose,
no retention.

**Retention must never delay revocation.** This is the invariant that ordering alone could
obscure, so it is stated once and governs every row of the matrix:

| Event | Authorization effect | Retention effect |
|---|---|---|
| Membership revoked | Stops at the next authorization decision (`FR-030`) | Record may persist only as the `FR-014` audit subject |
| Role downgraded | Effective immediately (`FR-030`) | Prior role retained only in the audit event |
| Account disabled | All sessions cease to authorize, without waiting for expiry (`FR-008`) | Account record persists; credential verifier destroyed |
| Session revoked or expired | Authorizes nothing from that instant | Record may persist until purged |
| Recovery completed | All prior sessions invalidated (`FR-007`) | Verifier destroyed |
| Invitation redeemed, expired, or revoked | Unusable (`FR-017`) | Verifier destroyed |

A retained record is never a live grant. Nothing in this decision permits an implementation to
keep authority alive because a record still exists.

### 6. Deletion, and what this decision does not authorize

`RCA-001` **excludes** organization deletion and account deletion as customer-invoked operations,
and this decision does not add them. Disablement is the terminal state this decision governs, and
§2b bounds it: a disabled account is minimized to an opaque tombstone after twenty-four months.
That minimization is policy-driven expiry of data whose purpose has ended — required of every
class by Constitution VII — not the deletion feature `RCA-001` withholds.

A later deletion specification, if one is ever approved, must respect the following. These are
constraints on future work, not authorizations:

- Deletion must be immediate and idempotent on demand, preserving the control `RRA-002` fixes and
  `KHEPRI-DEC-014` §2 records as surviving unchanged.
- Deleting a commercial identity must not orphan retail content. The relationship between deleting
  an organization and deleting the content in its isolation scope must be settled explicitly.
- Deletion must reach backups through the bounded-horizon mechanism in §8, not by ignoring them.
- `FR-013`'s final-owner protection must not be circumvented by deleting the final owner's account.

### 7. Logging

Logs must not become a shadow identity database. Per `FR-040`, identity, membership, and
authorization records are logged content-free.

**Never logged:** credentials, credential verifiers, recovery secrets, invitation secrets, **the
session identifier or any other bearer material**, and retail content of any kind. This admits no
exception. A value that can be replayed to authenticate must never reach a log, and a
twelve-month log horizon would otherwise widen the exposure of that value by twelve months.

**Logged only where a security or audit purpose requires it, in the narrowest sufficient form:**
opaque account, organization, and membership identifiers; the **session correlation identifier**
defined below; event type; outcome; timestamp. An opaque identifier is preferred to an email
address in every case where it is sufficient, which is every case this decision contemplates.

**The session correlation identifier is not the session identifier.** A security investigation
needs to group events belonging to one session, so a per-session correlation value is authorized
for that purpose — but it is a **separate, non-bearer** value that confers no authority and cannot
be presented to authenticate. It must not be the session identifier, and it must not be derivable
from it. Where these two rules could be read as competing, the prohibition governs: if an
implementation cannot log a value without logging bearer material, it does not log it.

Log retention is bounded by the twelve-month security-audit horizon (§2a). Logs are not a
retention loophole: a field this decision forbids retaining in a record may not be retained by
writing it to a log instead.

### 8. Backup invariants

`KHEPRI-DEC-008` is `proposed`, so runtime and provider selection is unsettled. This decision
therefore states **technology-neutral guarantees** and names the provider-dependent value as an
owner decision rather than inventing it.

1. **Live deletion and revocation take effect immediately**, independent of any backup.
2. **Backups are not queryable customer records.** A backup is operational recovery material, not
   a second store to be read.
3. **Backup retention is bounded** by an approved horizon (**OD-3**), never indefinite.
4. **Expired backups are destroyed** through the selected runtime's lifecycle mechanism.
5. **A restore must not resurrect deleted, disabled, or revoked identity as active state.** A
   restored session must not authorize; a restored membership must not grant; a restored disabled
   account must not authenticate; a restored invitation or recovery verifier must not be usable.
6. **The revocation ledger that enforces #5 is itself minimal and purpose-bound.**

Item 6 resolves a real tension rather than leaving it implicit. Enforcing #5 requires knowing what
was revoked, which is itself retained data — so the mechanism could quietly become a second
identity store. It must not. The ledger holds **opaque identifiers, revocation timestamps, and
status only**: no email address, no credential verifier, no role history beyond what `FR-014`
already records, and no retail content. It is bounded by **OD-3** plus a margin, because a ledger
that outlives every backup it guards has outlived its purpose.

This adopts `KHEPRI-DEC-005`'s principle verbatim — backups protect operational state while
content-retention and deletion rules continue to apply — and `KHEPRI-DEC-007`'s discipline that no
retention horizon may be quietly longer than another.

### 9. Isolation

Commercial identifiers must never become analytical isolation keys. Per `FR-032`, the email
address, organization name, organization slug, customer-visible account identifier, and
human-readable resource identifier must not appear in, or be derivable from, any component of an
isolation key.

```text
Organization
     ↓  (opaque, non-derived, stable for the organization's lifetime)
governed RRA owner/isolation scope
```

The mapping is retained for the organization's lifetime because `FR-035` requires the scope be
stable across sessions, switches, and membership changes. Retaining it is what makes an
organization's content continuously reachable by its own members and no one else.

## Relationship to RRA

`RRA-002`'s intake and deletion lifecycle is **unchanged**. This decision adds no retail content to
any store, extends no retail-content horizon, and relaxes no deletion rule. `RRA-001`'s opaque
identifiers, cross-session isolation, and content-free logging are preserved exactly as
`KHEPRI-DEC-014` §2 records them as surviving.

The distinction is load-bearing and stated once more because §10's adversarial review turns on it:

```text
commercial identity retention  ≠  customer retail-content retention
```

Approval of one grants no authority for the other.

## Relationship to RCA-001

**Approval of this decision clears only `RCA-001`'s retention-policy precondition** — precondition
3 of four. It does **not**:

- approve `RCA-001`, which remains `draft`;
- authorize any `RCA-001` implementation;
- settle runtime or provider architecture;
- approve `KHEPRI-DEC-008`, which remains `proposed`;
- authorize persistent retail content, workspaces, multi-dataset storage, or report history;
- authorize billing, subscriptions, agency portfolios, recurring delivery, or Seshat-BI;
- authorize any AI use of any retained data.

No contradiction with `RCA-001` was found. Every matrix row is anchored to a named requirement,
and the two places where this decision could have contradicted the specification — account
deletion and organization deletion — are handled as forward-looking constraints in §6 precisely
because `RCA-001` excludes them.

## Consequences

- `RCA-001` gains one satisfied precondition **if and when this decision is accepted**. Three
  remain: `RCA-001`'s own approval, an approved architecture decision, and the slice's evidence
  linkage.
- The deployment gate is untouched and remains first.
- No decision is superseded. `KHEPRI-DEC-005` and `KHEPRI-DEC-007` are cited for principle and are
  neither amended nor weakened.
- Audit retention is fixed at twelve months (§2a). No class this decision authorizes is retained
  indefinitely, which is what makes it coherent to accept: a retention decision with unbounded
  audit retention would authorize the very indefinite retention it must refuse.
- Disabled-account retention is fixed at twenty-four months (§2b), so the one terminal state this
  decision governs is bounded rather than indefinite.
- One owner decision remains open and does not block acceptance. `OD-3` is an input to
  `KHEPRI-DEC-008` and cannot be settled before a runtime exists; every horizon this decision
  authorizes is bounded without it.

## Owner decisions required

Three values cannot be derived from repository evidence and are **not invented here**.

**OD-1 (audit retention) is settled at twelve months and is recorded in §2a, not here, because it
is no longer an open question.** Two decisions remain open, and neither blocks acceptance.

**OD-2 (disabled-account horizon) is settled at twenty-four months and is recorded in §2b.** It
was raised in review that deferring it would let this decision clear `RCA-001`'s retention
precondition while production retained former users' identity data indefinitely — governance
recording the opposite of the fact. That objection was correct, and the horizon is now fixed
rather than deferred. One decision remains open.

```text
OWNER DECISION REQUIRED  (OD-3)

Data class:        Backups; revocation ledger
Decision needed:   The bounded backup purge horizon
Why a fixed duration is necessary:
    §8 items 3 and 6 both depend on it, and the revocation ledger's own bound is derived
    from it. It cannot be lifecycle-derived because a backup's lifecycle is a property of
    the runtime, not of the data.
Existing repository precedent:
    KHEPRI-DEC-007 sets 7 days for the RRA private beta, explicitly to match the S3
    seven-day object expiry. That anchor does not exist here.
Recommended duration:
    Defer. §9 of the governing brief and KHEPRI-DEC-008's `proposed` state both point the
    same way: this needs provider knowledge that does not yet exist. Recorded as an
    explicit input to the architecture decision rather than guessed now.
Alternative:
    Adopt 7 days by analogy, which would silently import an anchor that no longer applies.
Risk if shorter:
    Reduced ability to recover from an incident discovered late.
Risk if longer:
    A revoked identity remains restorable for longer, and the revocation ledger must be
    retained for correspondingly longer to prevent it.
```

`OD-3` is settled by naming the successor obligation rather than a number, as its block records,
and does not block acceptance. Every retention horizon this decision actually authorizes is
bounded: audit at twelve months (§2a), disabled accounts at twenty-four months (§2b), every other
class by its lifecycle, and backups by the horizon `KHEPRI-DEC-008` must fix before any deployment
exists. No class is retained indefinitely.

## Explicit non-authorizations

This decision authorizes **none** of the following, and no reading of it may claim otherwise:

- Retention of retail uploads, derived facts, narratives, or report bundles beyond `RRA-002`.
- Persistent workspaces, report history, multi-dataset storage, or long-lived retail content.
- Billing, payment, subscription, quota, or invoicing records.
- Agency portfolios, client switching, delegated access, or recurring delivery.
- Marketing, product analytics, profiling, or any AI training or inference on retained data.
- Seshat-BI integration or database connector credentials.
- Deployment, provisioning, provider selection, or spend.
- `RCA-001` approval, or any `RCA-001` implementation.
- Any weakening of `RRA-001`, `RRA-002`, or `RRA-006` controls.

## Verification

- Every matrix row cites the `RCA-001` requirement that makes its data class necessary. A row
  without such an anchor is out of scope.
- No raw secret appears in any retained class; every secret class stores a one-way verifier and
  destroys it when its purpose ends (§5).
- No authorization outlives its revocation trigger in any row (§5 table).
- No commercial identifier named in `FR-032` appears in the isolation mapping (§9).
- Implementation evidence, when an approved specification and architecture decision permit it,
  must include tests that a restore does not reactivate a revoked session, membership, invitation,
  or disabled account (§8 item 5).
- `uv run khepri-gov validate` passes at this commit.

---

Identity, lifecycle state, ownership, and approval evidence are authoritative in
`governance/registries/decisions.yaml`.
