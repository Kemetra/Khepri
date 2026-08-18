# R4-01 — invitation state, expiry, revocation, intended role, and authenticated redemption

**Task:** `R4-01` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Output is a design, not code.

**Baseline:** `main` @ `9adeb0a`, 2026-08-18 (`R7-02`, `R7-04` and `R1-05` merged, so `R1` is now
closed; §6.2's cross-branch coordination note is settled accordingly). `uv run khepri-gov validate` passes; `uv run pytest` reports 2197 passed, 47
skipped — measured at this commit rather than carried over from a branch. Migration head
`20260817_0017`, single head.

**Depends on:** `R2`'s role model and event table (merged), and `R3`'s actor resolution (merged
through `R3-10`). Both met. `R6-01`'s matrix is merged, which matters because §6 below owes it two
rows.

**What this note settles:** the invitation record's shape, its state model, what "fail closed" means
concretely, who may issue and revoke, and what redemption does. **What it does not settle** is in
§8.

---

## 1. What exists today, stated first

**Nothing.** `FR-016` … `FR-020` are the largest untouched block in `RCA-001`:
`test_rca001_migration.py` enumerates exactly five `rca_` tables — accounts, organizations,
memberships, isolation_scopes, membership_events — and there is no `Invitation` type, no
`rca_invitations` table, and no store method. `STATUS.md` records all five requirements as `Not
implemented`.

**One thing that does exist, and must not be reused.** `khepri.rra.sessions.Invitation` is a *beta*
invitation: it carries `invitation_id`, `secret_salt`, `secret_digest`, `expires_at`, `redeemed_at`
and names no organization and no role, because a beta participant redeems into a throwaway scope
rather than into a tenant. `KHEPRI-DEC-019` §2 (re-enacted by `KHEPRI-DEC-020` §1) forbids changing
`redeem`, its signature, or the invitation lifecycle, and `FR-039` forbids `RCA` depending on an
`rra_` table. So `RCA` gets its own record.

The *shape* of RRA's record is nonetheless the right precedent for the secret half, and §3 follows
it deliberately rather than inventing a second hashing scheme.

## 2. The five requirements, and what each one constrains

Quoted so this note can be checked against them without opening the specification.
`governance/specifications/RCA-001.md` remains the only authoritative source.

| FR | What it requires | Where it lands |
|---|---|---|
| `FR-016` | Exactly one organization, one intended role, a high-entropy secret stored **only** as a strong salted hash, an explicit expiry | §3 record, §4 issuance |
| `FR-017` | Redeemable **at most once**; replayed, expired, revoked, or malformed all fail closed **without revealing which check failed** | §5 |
| `FR-018` | Accepting a valid invitation creates **exactly one** membership in the named organization at the named role | §6 |
| `FR-019` | Issuable to a person with **no account yet**; accepting **requires an authenticated account** at the moment of acceptance | §6 |
| `FR-020` | Revoking a membership invalidates that member's **unredeemed** invitations to that organization | §7 |

`KHEPRI-DEC-015` also binds, and §3's correction block records that the first version of this note
failed to read it. Its §2 matrix is authoritative for the invitation record's retention.

Scenarios 6, 7, 8, 9 and 11 in `RCA-001`'s Verification section are the tests these owe.

## 3. The record

> **Correction, 2026-08-17 (`R4-01`).** The first version of this section decided *against* storing
> the invitee's identity, on the grounds that "an email address is personal data with its own
> retention obligation, and the invitation table has no sweeper", and §8 then listed invitation
> retention as an open owner decision. Both are wrong, and wrong in the same way: an **active**
> governing record had already settled them. `KHEPRI-DEC-015` — `active` in
> `governance/registry.yaml` — carries an **Invitation** row in its authoritative §2 matrix whose
> post-trigger state is "Verifier **destroyed**; status and target identity retained only while
> needed to refuse replay and to attribute the resulting membership" and whose deletion rule is
> "Verifier destroyed at the trigger; record purged when replay refusal no longer needs it". That
> row *requires* a target identity, *requires* the verifier be destructible, and *decides* the
> retention this note called undecided. The error's cause: §3 was written from `FR-016`'s field list
> and `FR-040`'s content-free discipline without opening the retention decision that governs the
> same table. §2's matrix says "Where prose below and this matrix could both be read as settling a
> lifecycle rule, the matrix governs" — and a design note is not even prose in that decision. It
> cannot re-open a settled row. The corrected record is below, and it is a *larger* schema than the
> first version, not a smaller one.

```
Invitation
  invitation_id     str            opaque, prefixed `inv_`
  organization_id   str            exactly one, FK to rca_organizations
  intended_role     str            exactly one of ROLES, CHECK-constrained
  target_identity   str            whom the invitation is for; see the naming note below
  verifier          Verifier|None  salt + digest + kdf as one optional whole in the domain;
                                   destroyed at the trigger, so NULL is the terminal shape,
                                   not a defect. At rest this is five nullable columns —
                                   secret_salt, secret_digest, kdf_n, kdf_r, kdf_p — which are
                                   NULL together or not at all; see the CHECK below
  expires_at        datetime       explicit, no default lifetime baked into the record
  issued_by         str            the actor account, for FR-014-style attribution
  issued_at         datetime
  redeemed_at       datetime | None
  revoked_at        datetime | None
```

**Sealed, following `Membership` and `MembershipEvent`.** `records.py`'s door pattern applies: a
state change is a new instance, never a mutation, so `redeemed_at` is set by constructing rather
than by assignment. Destroying the verifier is the same move: a new instance carrying `None`.

**Why `target_identity` and not `email`.** The column is required by `KHEPRI-DEC-015` §2's
Invitation row ("target identity retained only while needed to refuse replay and to attribute the
resulting membership"). It is deliberately *not* named `email`, because that name would collapse two
separately governed data classes:

1. `KHEPRI-DEC-015` §2 line 74 governs **"Login identity (email)"** as its own class, with a
   purpose list ("Authentication, account recovery, and addressing an invitation to a person") and a
   **fixed horizon** — "While enabled; **24 months** after disablement", then "**Purged.** Nothing
   remains". The Invitation row's target identity has no fixed horizon at all: it is
   lifecycle-derived, purged "when replay refusal no longer needs it". Two classes, two retention
   rules. One name for both would make the shorter rule invisible, which is exactly the "no single
   retention horizon is quietly longer than another" discipline `KHEPRI-DEC-015` adopts from
   `KHEPRI-DEC-007`.
2. The addressable form is not fixed by this note's authority. `KHEPRI-DEC-018` admits **no**
   provider today — "No external identity provider is admitted by this decision" (§5) — but its
   admission gates include "Stable subject semantics", requiring a provider's identifier behavior be
   recorded "across email change, identity merge, and identity replacement" (§5 gate 7). A column
   named for one encoding of the identity would have to be renamed by whichever decision admits a
   provider. `KHEPRI-DEC-018` §8 keeps "Khepri's copy … authoritative for Khepri purposes —
   invitation delivery and the account identity record — under the retention and purpose limits
   `KHEPRI-DEC-015` §3 already sets", so the value is ours to hold; only the name is a design
   choice.

An email address is what `R4` will in fact store, since `FR-019` issues to a person before an
account exists and no other addressing exists. The name records that the *governed class* is the
invitation's target, not the account's login identity.

**Purpose limitation carries with it.** `KHEPRI-DEC-015` §3 makes each matrix purpose "exhaustive
for that data class" and names the login identity as "the sharpest case: an email address retained
to make recovery and invitation work is **not** thereby available for any message that is not part
of those flows". `target_identity` is readable to refuse replay and to attribute a membership. It is
not a mailing list, and `FR-040`'s content-free logging still forbids logging it.

**The verifier is an optional whole, not two nullable columns.** `credentials.py:77-80` states the
reasoning for exactly this shape and it transfers verbatim: `KHEPRI-DEC-015` "requires the verifier
to be destroyed immediately and non-recoverably on disablement or replacement, which is why an
account holds this as an optional whole rather than three independently-nullable columns:
destruction replaces the whole verifier with `None` and cannot be done by halves." Held as three
independently-nullable columns, a half-destroyed verifier — salt gone, digest kept — is expressible,
and nothing in the schema refuses it. `Verifier` is already sealed, so `R4-02` reuses the type
rather than declaring a second one; at rest that is still three nullable columns plus the KDF
parameters, which is why the invariant belongs in the domain type and not in the column definitions.

The shape has a precedent inside the same matrix: `KHEPRI-DEC-015` §2 line 77's **Recovery request**
row is identical in form — "Verifier **destroyed**; a content-free event record may remain as
security evidence", "Verifier destroyed immediately at the trigger". Invitations are the second
instance of one pattern, not a new one.

**Destruction triggers, from the matrix's own end-trigger list:** "Acceptance; expiry; revocation;
revocation of the inviting membership (`FR-020`)". Acceptance and revocation are writes and destroy
the verifier in the same transaction that sets the timestamp. **Expiry is not a write** — it is
`expires_at <= now` per §5's boundary, a derived state with no column and no event — so expiry
alone changes no bytes, and the sweeper below is what eventually clears them.

**What "destroyed at the trigger" requires at the expiry trigger, stated because the answer is not
"as soon as possible".** Read as *the bytes are gone at the instant*, the rule is unsatisfiable for
a derived state: no code runs at `expires_at`, so any mechanism — a sweep, a scheduled job, a
destroy-on-next-touch — leaves a window, and the only difference between them is its length.
`KHEPRI-DEC-015` does not read that way. Its §5 states the governing invariant under the heading
**"Retention must never delay revocation"**, and its own table pairs the effects for exactly this
row: "Invitation redeemed, expired, or revoked → **Unusable (`FR-017`)** | Verifier destroyed". The
sentence that closes it is the test — "**A retained record is never a live grant.** Nothing in this
decision permits an implementation to keep authority alive because a record still exists." The
guarantee is over *authority*, not over bytes.

**So the trigger obligation is discharged in §5, not by the sweeper.** An expired invitation is
unusable at the instant `expires_at <= now`, because §5's refusal is decided from the state
predicates and the surviving verifier authorizes nothing: a caller presenting the correct secret
against an expired row receives the same uniform refusal as a caller presenting a malformed token,
and pays the same KDF cost doing it. The verifier's bytes outlive its authority by exactly the
sweep interval, and outlive its *usefulness to an attacker* not at all — a salted scrypt digest at
`n=2**14` is not a secret whose disclosure grants anything, which is why `FR-016` permits storing it
at all while the invitation is live. What the sweeper reclaims is storage and the personal data in
`target_identity`, on the horizon below; what it is *not* doing is ending a grant, because §5 ended
that at the instant.

**Recorded because the weaker reading is the tempting one.** "The verifier survives until a sweep"
is true and sounds like a concession; it is only a defect if the surviving bytes authorize
something. `R4-05` and `R4-07` owe the evidence that they do not: a test that presents the **correct
secret** for an expired invitation whose verifier is still intact, and asserts the uniform refusal.
That case fails on an implementation that verifies the digest and returns success before checking
`expires_at` — which is the only way the delay could ever become a live grant, and §5's
ordering rule already forbids it.

**So invitations need a sweeper, and `R4-03` owes it.** This is a schema consequence, which is why
it lands with the table rather than later: the matrix's deletion rule ("record purged when replay
refusal no longer needs it") is not satisfiable by any code path that only runs when a user acts.
Two established shapes to follow, and they differ in a way that matters here:

- `_purge_expired_events` (`persistence.py:677`) is one `DELETE` with no prior select, because
  "Events are append-only and `occurred_at` never changes, so there is no window in which a selected
  row stops qualifying". Invitations are **not** append-only — an open invitation can be redeemed
  between a select and a write — so this shape is only safe for the purge if the predicate is
  evaluated in the deleting statement.
- `purge_if_still_eligible` (`persistence.py:338`) re-reads and re-checks inside the writing
  transaction, because the sweeper "select[ed], then wr[o]te, and those were separate transactions
  with no predicate between them", which erased a re-enabled account's email. Verbatim the hazard an
  invitation sweeper has.

`R4-03` should take the second shape, or the first with the full predicate inline.
`MembershipEventSweeper` owns the horizon arithmetic for events and the same split applies: the
sweeper owns "when", the store owns the transaction.

**What "when replay refusal no longer needs it" resolves to — a predicate, not an owner input.**
The first version of this paragraph called the remaining horizon "an operational choice about table
size, not a privacy horizon" and left it to `R4-03`. That is wrong for one reason: `target_identity`
is **personal data**, so a horizon that is merely operational lets it outlive its authorized
purposes, and `KHEPRI-DEC-015` §3 makes each matrix purpose "exhaustive for that data class". A
table-size argument cannot govern a privacy horizon. The corrected reading is that the matrix
already fixes the rule and the rule is *derivable* — this note is not choosing a number, it is
reading a lifecycle predicate `KHEPRI-DEC-015` §2 already settled.

**The derivation.** The Invitation row authorizes retaining status and target identity for exactly
two purposes: "to refuse replay and to attribute the resulting membership". Take them one at a time.

- **Attribution** applies only where a membership was created — a **redeemed** invitation. For an
  expired or revoked row no membership exists to attribute, so this purpose never attaches.
- **Replay refusal** needs the *row*, and needs nothing in it but the identifier. §5 already
  requires an unknown `invitation_id` to receive the identical refusal and the identical dummy KDF
  work as every other cause. So a deleted row and a retained-but-closed row are, by construction,
  **externally indistinguishable** — which means deleting the row does not weaken replay refusal at
  all. Retention adds nothing this purpose can use.

Both purposes therefore lapse for a non-redeemed invitation the moment it is closed, and neither
authorizes holding `target_identity` past that point.

**The purge predicate `R4-03` implements.** Two lifecycle rules, not one number:

| Row | Purge when | Why |
|---|---|---|
| Expired or revoked, never redeemed | The verifier is destroyed — the same sweep pass | Neither authorized purpose attaches; §5 makes deletion indistinguishable from retention |
| Redeemed | The `FR-014` `MembershipEvent` it produced is purged | Attribution is the surviving purpose, and the event is where `KHEPRI-DEC-015` §2a puts attribution's horizon |

The redeemed row's horizon is **derived, not imported**. §2a's twelve months is an audit-class
number and this note does not adopt it — what it adopts is the *anchor*: attribution outlives the
invitation only as long as the audit record it attributes, so when that event goes the invitation's
last authorized purpose has ended with it. If the event's horizon changes, this follows without
edit. That is the "lifecycle-derived, no fixed duration" shape the matrix requires, and it is why
`R4-03` must not write twelve months into the invitation sweeper as a literal.

**One consequence to state rather than discover.** Under the first rule the sweep that destroys an
expired verifier also deletes the row, so those are one pass, not two — there is no interval in
which an expired invitation exists with its verifier gone and its `target_identity` retained.
`R4-03`'s sweeper predicate is therefore evaluated in the deleting statement per the shape above,
and `R4-07` owes a test that an expired invitation's row is gone after a sweep, not merely
verifier-cleared.

**Constraints on the table:**

- `CHECK intended_role IN ('owner','member')` — the same shape as `ck_rca_membership_role`
  (`20260814_0015`), for the same reason: the domain refusing a third role is not sufficient when a
  store caller can reach the row directly.
- `CHECK (redeemed_at IS NULL OR revoked_at IS NULL)` — an invitation cannot be both. See §5's
  state model.
- `CHECK expires_at > issued_at` — following `ck_session_expiry_after_creation`.
- No `UNIQUE (organization_id, ...)` of any kind. One organization may hold many open invitations,
  and encoding a cardinality nobody requires is exactly the defect `R7-02` spent a slice unwinding
  (`KHEPRI-DEC-020`). In particular **no `UNIQUE (organization_id, target_identity)`**: the same
  person may hold two outstanding invitations, which is precisely the scenario §7's counter-example
  turns on, and forbidding it in the schema would hide the case rather than handle it.
- **The verifier's five columns are nullable together or not at all.** `AccountRow` already stores a
  `Verifier` this way — `credential_salt`, `credential_digest`, `kdf_n`, `kdf_r`, `kdf_p`, every one
  `nullable=True` (`persistence.py:77-81`) — and destroys it by setting all five to `None`
  (`:357-361`). `R4` follows the shape with `secret_`-prefixed names, and adds the constraint that
  table does not have: `CHECK ((secret_salt IS NULL) = (secret_digest IS NULL) AND (secret_salt IS
  NULL) = (kdf_n IS NULL) AND (kdf_n IS NULL) = (kdf_r IS NULL) AND (kdf_r IS NULL) = (kdf_p IS
  NULL))`. This is the "cannot be destroyed by halves" invariant expressed at the row, for the same
  reason `ck_rca_membership_role` exists: the domain refusing a half-destroyed verifier is not
  sufficient when a store caller can reach the row directly. `_verifier_from_row`
  (`persistence.py:259`) reads all five as a tuple and returns `None` unless every one is present,
  so the domain already treats them as one whole — the constraint makes the storage layer agree.
- **No `CHECK` can say "the verifier is NULL only in a terminal state", and that is worth
  stating.** Redeemed and revoked are columns, so `redeemed_at IS NOT NULL OR revoked_at IS NOT
  NULL` covers two of the four triggers — but **expiry is time-derived**, so a legitimately-swept
  expired invitation has a NULL verifier and both timestamps NULL, which is indistinguishable at the
  row level from an open invitation whose verifier was wrongly destroyed. A `CHECK` including
  `expires_at <= now()` is not writable: `now()` is not immutable and PostgreSQL refuses it in a
  `CHECK`. So this invariant is the domain's, enforced by the sweeper being the only path that
  destroys without a timestamp. Recorded rather than papered over with a constraint that would be
  wrong.

## 4. Issuance and revocation

`InvitationService.issue(organization_id, intended_role, target_identity, *, actor_account_id,
expires_at, now)` returns a **single-use token** the caller must transmit and cannot recover
afterwards. `target_identity` is required rather than optional: `KHEPRI-DEC-015` §2's Invitation row
retains it "to attribute the resulting membership", and §7's cascade cannot match a row that has
none, so an invitation without one would be a row `FR-020` cannot reach.

- **Token format `kci1.<invitation_id>.<secret>`**, mirroring RRA's `kiv1.` with a distinct prefix
  so a beta token and a commercial token can never be confused at a boundary that accepts both.
  `R3-01` §2.1 established that reasoning for session keys.
- **`scrypt` at RRA's parameters** (`n=2**14, r=8, p=1, dklen=32`, 16-byte salt). Matching rather
  than choosing new parameters: two hashing schemes in one codebase means one of them is unreviewed.
- **The secret is returned once and never stored.** Only the `Verifier`'s salt and digest persist,
  which is `FR-016`'s "persisted only as a strong salted hash", and they are destroyed together at
  the trigger per §3.
- **`expires_at` is a parameter, not a constant.** `FR-016` requires an explicit expiry; it does
  not fix a lifetime, and baking one in would put a product decision in the domain.

**Authorization lives outside this service.** Per `R6-01` §5's critical rule and `R6-04`'s placement
of the check in the gate rather than in the verbs, `issue` takes `actor_account_id` for
*attribution* and performs no role check of its own. §6.3 below adds the matrix rows that make the
gate the authorized route. Note the asymmetry with §6's corrected redemption signature: `issue` is
reached **through** the gate, which has already resolved the actor, so `actor_account_id` here is a
value the gate supplies rather than a caller's claim. `redeem` has no gate — a redeemer holds no
membership — so it must carry the `ResolvedActor` itself.

**The organization `issue` writes must be the organization the gate resolved.** `issue` creates a
row rather than looking one up, so it carries no identifier-grants-authority hazard of its own — but
nothing above yet forbids a service that takes a resolved scope *and* a separate `organization_id`
parameter, which would let an owner of `A` issue an invitation into `B`. So: the
`organization_id` `issue` writes is the value `resolve_scope` returned for this actor, and there is
no second path by which a caller names a different one. `FR-024` requires a request whose actor and
whose named scope disagree to fail closed, and two independently-supplied organization values are
exactly that disagreement made expressible.

### 4.1 Revocation is scoped by `(organization_id, invitation_id)`, never by identifier alone

`InvitationService.revoke(organization_id, invitation_id, *, actor_account_id, now)` — and **the
lookup is composite**: `WHERE organization_id = :organization_id AND invitation_id =
:invitation_id`, where `organization_id` is the scope the gate already resolved for this actor, not
a value the caller supplies alongside the invitation.

**Why the signature is stated here rather than left to `R4-04`.** §6.3 gives "Revoke an invitation"
as owner-only, and a reader could take the matrix row as the whole of the requirement. It is not. A
matrix row says *which role* may revoke; it says nothing about *which rows* that role may reach. If
`R4-04` fetches by `invitation_id` alone — the obvious shape, since the identifier is already unique
— then an owner of organization `A`, holding or guessing an `inv_` identifier belonging to
organization `B`, revokes `B`'s invitation. Worse before that: a revoke that returns "not found" for
a bad identifier and "revoked" for a real one turns the endpoint into an existence oracle for other
organizations' invitations, which discloses that `B` has an outstanding invitation at all.

`FR-023` is the requirement violated — "Possession of an object identifier MUST confer no
authority. Authorization MUST be decided from the actor's membership in the scope that owns the
object, never from the caller's ability to name the object" — and `R6-01` §5 states it as the
critical rule with its own worked example. **This is the same defect class as the caller-supplied
`account_id` §6's correction removed from `redeem`**, in a different verb: there the caller named
the account, here the caller names the object. One correction does not fix the other, which is why
both are written down.

**The refusal is uniform, and that is `FR-025` rather than a courtesy.** A mismatch between the
authorized organization and the invitation's — and an `invitation_id` that exists nowhere — produce
**one** failure, indistinguishable from each other and from "no such invitation". `FR-025`: "A
denial for an object the actor may not reach MUST be indistinguishable from a denial for an object
that does not exist. Denials MUST NOT disclose existence, ownership, or the identity of another
organization." So `revoke` never reports which of the two happened, and never names the owning
organization.

`resolve_scope` (`isolation.py:30-40`) is the in-repo shape and `R4-04` should read like it: the
membership lookup is composite — `get_membership(organization_id, account_id)` (`:34`) — and its
three distinct failure causes (no account or a disabled one `:33`, no membership `:36`, no scope
`:39`) all raise the identical `ScopeAccessDenied(SCOPE_FAILURE)`. Three causes, one message, no
branch a caller can distinguish. `R4-04` owes the same for revocation.

**No dummy-KDF padding is needed here, unlike §5's redemption path.** Revocation compares no secret,
and the composite `SELECT` is the same single statement whether it misses because the invitation
does not exist or because it belongs to another organization. The two causes are timing-equivalent
by construction rather than by padding, so §5's dummy-work discipline does not transfer to this
verb. Stated because "every uniform refusal needs a dummy hash" would be the wrong generalization.

**`R4-07` owes a cross-organization revocation case**, not merely a non-owner one: an owner of `A`
presenting `B`'s `invitation_id` must be refused, and `B`'s invitation must still be open
afterwards. A test that only checks a `member` cannot revoke would pass on the defective lookup.

## 5. State, and what "fail closed" means concretely

Four states, discriminated by nullability rather than a status column — following
`MembershipEvent`'s reasoning verbatim, because a `status` field could disagree with the timestamps
and then two fields would describe one fact:

| State | `redeemed_at` | `revoked_at` | `expires_at` vs now |
|---|---|---|---|
| open | NULL | NULL | `expires_at > now` |
| expired | NULL | NULL | `expires_at <= now` |
| redeemed | set | NULL | any |
| revoked | NULL | set | any |

> **Correction, 2026-08-17 (`R4-01`).** The first version of this table said "future" and "past",
> which classifies `now == expires_at` as **neither** state. That is not a wording infelicity: two
> implementations reading the same table could pick `<` and `<=` and disagree about one instant,
> and the one that picks `<` treats an invitation at its own expiry as still open — failing *open*
> at the boundary, in a state model whose whole point is failing closed. So the boundary is fixed
> explicitly: **open is `expires_at > now`; expired is `expires_at <= now`.** The expiry instant
> itself counts as expired. This is the repo's existing convention rather than a new choice —
> `Session.is_expired_at` is `return self.expires_at <= moment` (`rca/sessions.py:111`), whose
> docstring gives this exact reason ("a horizon that excluded its own boundary would leave a
> one-instant window where a session is neither live nor expired"), and RRA's `redeem` already
> refuses on `invitation.expires_at <= now` (`rra/sessions.py:120`). `R4-02` owes an
> `is_expired_at`-shaped predicate on the record rather than an inline comparison at each call
> site, so the boundary is stated once.

**`FR-017`'s hard part is the non-disclosure, not the at-most-once.** Six distinct causes —
malformed token, unknown `invitation_id`, wrong secret, expired, revoked, already redeemed — must
produce **one** externally identical failure, and they must be indistinguishable by **timing** as
well as by message. That means:

- One exception type carrying one message constant, following `SCOPE_FAILURE` and
  `_INVITATION_FAILURE`.
- **The digest comparison runs even when the invitation was not found**, against a module-level
  dummy salt, exactly as `credentials.py:31`'s `DUMMY_SALT` does for `FR-004` — its own comment says
  it exists "to pay the same scrypt cost for a missing account as for a wrong-credential rejection,
  so account existence is not revealed through timing". Without it, "unknown invitation" returns
  fast and "wrong secret" pays for a scrypt, and the timing difference is the disclosure the
  requirement forbids. This is the one place a `R4` implementation is most likely to be accidentally
  non-compliant, because the fast path looks like an optimization.
- **The dummy work must also run on the malformed-token path, which is earlier than the lookup.**
  The first version of this section paid the dummy scrypt only when the *lookup* missed, and that
  leaves the fastest path of all uncovered: a token that fails `kci1.<invitation_id>.<secret>`
  parsing never reaches a lookup, so it returns in microseconds while every other cause pays ~100ms.
  `FR-017` names malformed explicitly — "A replayed, expired, revoked, or **malformed** invitation
  MUST fail closed without revealing which check failed" — so malformed is one of the causes that
  must be indistinguishable, not a precondition outside the guarantee. Concretely: `redeem` catches
  its own parse failure, pays the dummy work described below, discards the result, and raises the
  same uniform refusal. Ordering matters — the dummy work is paid *before* the raise, in the same
  call — because a caller measures the call, not the branch.
- **The dummy work must run at `R4`'s own KDF parameters, and `credentials.py`'s constants are the
  wrong ones.** `credentials.py:24` sets `KDF_N = 2**15` and `DEFAULT_KDF` uses it, but §4 fixes
  invitations at RRA's `n=2**14` (`khepri/rra/sessions.py:108`). Calling
  `hash_credential(token, DUMMY_SALT)` with the default factor would pay **double** the work a real
  invitation verify pays, making the dummy path measurably *slower* than the genuine one — a
  different timing oracle, not the absence of one. So `R4` declares its **own** module-level dummy
  salt and pays `hash_credential(<the raw token>, INVITATION_DUMMY_SALT, INVITATION_KDF)` at
  `n=2**14`. Reusing `credentials.DUMMY_SALT` is fine as a *value* — it is 16 zero bytes and carries
  no secret — but the parameters must be the invitation module's. Stated because "reuse the existing
  dummy constant" is the obvious move and it silently reintroduces the defect this bullet fixes.
- **A verifier destroyed at rest is a third route to the dummy, not a seventh cause.** After the
  sweeper, a revocation, or a redemption runs, `verifier IS NULL`, so there is no digest to compare
  against — this is the at-rest *shape* of the expired, revoked, and already-redeemed causes rather
  than a new one. That path must pay the dummy work too rather than short-circuit on the NULL, or a
  swept invitation becomes distinguishable from a wrong secret by exactly the timing this
  requirement forbids. Three routes therefore reach the dummy: a malformed token, an unknown
  `invitation_id`, and a found row whose verifier is already destroyed.
- **The state checks must not short-circuit the digest comparison, and RRA's `redeem` is the
  ordering *not* to copy.** The bullet above covers the row whose verifier is already gone; it does
  **not** cover the row that is expired, revoked, or already redeemed while its verifier is still
  intact — which is every such row until the sweeper reaches it, so it is the common case rather
  than a window. `rra/sessions.py:117-123` refuses on
  `invitation is None or invitation.redeemed_at is not None or invitation.expires_at <= now or not
  self.verify_secret(...)`, and Python's `or` short-circuits: a redeemed or expired invitation
  returns **before** `verify_secret` runs and pays no scrypt at all, while a wrong secret against an
  open invitation pays the full cost. That is the timing disclosure `FR-017` forbids, present in the
  precedent this note otherwise follows for the secret half. So `R4`'s `redeem` computes the digest
  comparison **before** or regardless of the state predicates, and decides the refusal from all of
  them together. Concretely: the state of the row may determine *whether the refusal is raised*, but
  never *whether the KDF ran*.
- **The invariant, stated once so `R4-07` can assert it directly.** Every one of the six causes pays
  **equivalent KDF cost** — one `scrypt` at `n=2**14` — before any refusal is raised: a malformed
  token that never parses, an `invitation_id` that matches no row, a row whose verifier is
  destroyed, a row that is expired, revoked, or already redeemed with its verifier intact, and a
  genuine wrong secret. Six causes, one message, one KDF invocation each. Anything that skips the
  work on some branch is the defect, however reasonable it looks as an early return.
- `hmac.compare_digest` for the comparison itself, as RRA already does.

**A test asserting one message across six causes is not sufficient** — it passes on an
implementation that returns early. Scenario 8 and 9's tests must also assert the dummy-hash path is
taken, the way `test_rca001_accounts.py` does for authentication, and `R4-07` owes one case per
cause — malformed and verifier-destroyed included, since those are the two the first version of this
note would have shipped uncovered.

## 6. Redemption

> **Correction, 2026-08-17 (`R4-01`).** The first version of this section gave the signature as
> `redeem(token, *, account_id, now)` and called "the `account_id` parameter … the whole of
> `FR-019`'s second clause". That is wrong, and it is the same class of error as trusting a route
> parameter. A caller-supplied `account_id` lets any caller name **any** account: hold a stolen or
> guessed token, pass someone else's account identifier, and the membership is created for them — or
> for an account the caller has no session for at all. `FR-019` requires an *authenticated* account,
> and a parameter is not authentication. The corrected signature is below.

`redeem(token, actor, *, now)` where `actor: ResolvedActor` — **the account is derived from a
presented session, never named by the caller.**

**Why a parameter cannot satisfy `FR-019`.** `R6-01` §5 states the rule this violates, quoting the
roadmap: *"Object identifiers never grant authority. Every object lookup must be scoped from the
authorization result, not trusted from a route parameter."* Its own worked example is the same shape
— "An implementation that reads `organization_id` from a request and passes it to `resolve_scope`
has authorized nothing — it has let the caller name their own scope." Substitute `account_id` and
`redeem` and the sentence is unchanged. The in-repo precedent is exact: `actor_resolution.py:76`'s
`resolve_actor(self, token: str, *, now: datetime) -> ResolvedActor` takes **only a token and a
clock**, and derives the account by looking up the session and then reading `session.account_id`
(`:85-87`). There is no parameter by which a caller states who they are.

### 6.1 The steps

1. **The actor arrives already resolved.** `ActorResolver.resolve_actor` has run at the boundary,
   so the session was checked live and `assert_account_active` has already been consulted
   (`actor_resolution.py:87`). `redeem` does **not** re-check: `ResolvedActor`'s existence is the
   evidence, and a second check would be a second authority over one fact. `FR-019` says acceptance
   "MUST require that an authenticated account exists at the moment of acceptance" — *at the
   moment*, so a token issued before the account existed is fine, and a disabled account is refused
   by `resolve_actor` before `redeem` is entered.
2. **Parse and verify the invitation secret per §5.** Any failure → the single uniform refusal.
   This is second rather than first because an unauthenticated caller has no business consuming a
   token: `resolve_actor` failing means `redeem` never runs, following the order `ActorResolver`
   records as "load-bearing rather than incidental" — a dead session costs no further work.
3. **Check the actor is the addressee** — `canonical(actor.account.email) ==
   canonical(target_identity)`, or the same uniform refusal. See §6.1.1: this is a verification
   step, not a courtesy, and it is the reason §3 stores the field for anything beyond §7's cascade.
4. **Create exactly one membership** at `intended_role` in `organization_id` for
   `actor.account_id`, and mark the invitation redeemed, **in one transaction under a lock or a
   conditional update** — see §6.2, because "one transaction" alone is not sufficient.
5. **Emit `MembershipEvent.created`** with `actor_account_id` = `actor.account_id`. Attribution
   travels with the write for the reason `create_organization` records: an event committed
   separately can describe a change that rolled back.

**`organization_id` comes from the invitation row, not from the request, and that is not an
exception to §5's rule.** The invitation is authenticated by its secret before its `organization_id`
is read, so the identifier is derived from a verified record rather than trusted from a caller. This
is the one place in `RCA` where a scope is not derived from the actor's session membership — by
necessity, since `FR-019`'s redeemer holds no membership yet — and it is safe for the narrower
reason that the *secret* is the authorization. Stated because it looks like the violation corrected
above and is not.

### 6.1.1 The actor must be the addressee, and that is a product constraint worth naming

**The hole §3's correction opened.** Adding `target_identity` gave every invitation a recorded
addressee, and the steps above originally created the membership for whichever authenticated actor
presented a valid token. So account `B`, holding a token forwarded or stolen from account `A`,
redeems an invitation explicitly addressed to `A` and becomes a member. Two things break at once:
`FR-018`'s membership is created for the wrong person, and §3's claim that the retained target
identity is what lets the matrix "attribute the resulting membership" becomes false — the row says
`A` and the membership says `B`. A field retained *for* attribution that does not constrain the
thing it attributes is not attribution; it is a stale note.

**The check.** `canonical(actor.account.email) == canonical(target_identity)`, evaluated on the
uniform verification path per §5 — one more cause of the same refusal, not a distinguishable one.
Canonical on both sides, via `canonical_email` as `_canonical_or_none` (`persistence.py:254`) uses
it, for the reason §7 gives for the cascade: a case or normalization difference between the address
typed at issuance and the address registered at signup would silently spare the invitation there
and silently refuse it here.

**Why not simply "the emails must match", which is what the plain reading suggests.** Two states
this codebase actually produces would make that rule refuse a flow `FR-019` requires:

1. **The invitee registers at a different address.** `FR-019`'s whole case is an invitation to a
   person with **no account yet**; they create one on the way in, and nothing today forces the
   address they register to be the address they were invited at. A bare equality check makes that
   ordinary path fail — with the uniform refusal, so they cannot even be told why.
2. **The account is a purged tombstone.** After `KHEPRI-DEC-015` §2b's twenty-four months,
   `row.email = None` (`persistence.py:356`) and `actor.account.email is None`, so no comparison is
   constructible at all.

So the rule is stated with its boundaries rather than as a bare equality:

- **A match is required, and it is canonical.** The addressee is who may redeem.
- **`actor.account.email is None` → the uniform refusal.** A tombstone cannot be shown to be the
  addressee, so it fails **closed**, following the same discipline `resolve_scope` applies to a
  disabled account. Nothing here reconstructs an identity from a purged row.
- **The product consequence, stated because it is a behavioral constraint and not a footnote:**
  *an invitee must accept with the address they were invited at.* If they register a different one,
  redemption refuses and the owner must re-issue to the new address. `R8-05`'s screens will need to
  say so, and this note does not decide the copy — only that the constraint exists and is
  deliberate.

**Why that constraint is acceptable rather than a defect.** The alternative — letting any
authenticated account redeem any token addressed to anyone — makes the invitation a **bearer**
credential whose addressee is decorative. `FR-016` calls the secret high-entropy precisely so that
possession is hard to obtain; it does not say possession is *sufficient*, and `KHEPRI-DEC-015`
retains a target identity, which is only meaningful if the target constrains something. Requiring
the addressee to be the redeemer is what makes a forwarded token useless, and a forwarded token is
the realistic threat: invitations travel by email, and email is forwarded.

**`R4-05` and `R4-07` owe two cases here**, and neither is the happy path: account `B` presenting a
**valid** token addressed to `A` must be refused and no membership created, and an actor whose
account email is `None` must be refused. Both must produce the §5 refusal, indistinguishable from a
wrong secret — a test asserting only "redemption fails" passes on an implementation that discloses
which check failed.

### 6.2 At-most-once needs a lock or a conditional update, not just a transaction

**The race one transaction does not close.** Two concurrent requests present the same token with
*different* resolved actors — A and B. Both transactions read the invitation with `redeemed_at IS
NULL`. Both pass. Each inserts a membership row: `(O, A)` and `(O, B)`. Those are **distinct**
primary keys, so the composite key refuses neither. Both mark `redeemed_at` — a last-writer-wins
update on one column, which neither transaction sees as a conflict. Both commit. `FR-017`'s
"redeemable at most once" is violated and `FR-018`'s "exactly one membership" is violated twice
over, with two rows where the requirement permits one.

The read-check-write shape is the defect `#155` already cost `R1` a slice, and
`apply_owner_reducing_change` (`persistence.py:766`) records it in the same words: "the guard and
the write were three round trips on three sessions, so two concurrent disablements of a two-owner
organization could both count a live co-owner, both pass, and both commit, leaving zero." Redemption
is that shape with a different invariant.

**Two acceptable routes. `R4-05` must pick one and record which.**

- **Route A — `SELECT ... FOR UPDATE` on the invitation row**, following
  `_apply_membership_change` (`persistence.py:899`), whose docstring states why the count must run
  "inside this transaction on locked rows": the lock "blocks a competing owner-reducing operation on
  this organization at its own `SELECT` until this commits, so it observes this write rather than
  the state that preceded it." Substituting "a competing redemption of this invitation" leaves the
  sentence true. If this route is taken, the locking statement must be a **module-level named
  statement** like `owner_memberships_for_update` (`persistence.py:511`) and
  `organization_owners_for_update` (`:488`), for the reason `:516` gives: "SQLite emits no `FOR
  UPDATE` and SQLAlchemy silently omits it for that dialect, so if the lock were inline and someone
  later dropped it, the whole RCA suite would stay green" — the sibling at `:496` states the same
  thing in shorter form. Because the statement is named, "a test compiles it against the PostgreSQL
  dialect and asserts `FOR UPDATE` is present without needing a database" (`:518-519`). An inline
  `.with_for_update()` would produce a lock no test can demonstrate exists.
- **Route B — a conditional `UPDATE rca_invitations SET redeemed_at = :now WHERE invitation_id =
  :id AND redeemed_at IS NULL AND revoked_at IS NULL`**, which **must affect exactly one row**; zero
  rows means another transaction won and the loser raises the uniform refusal. The database's own
  row-level write lock does the serialization, so the claim rests on `rowcount` rather than on an
  explicit `FOR UPDATE`. `purge_if_still_eligible` (`persistence.py:338`) is the in-repo precedent
  for restating the selection predicate inside the writing transaction, and it exists because the
  sweeper "select[ed], then wr[o]te, and those were separate transactions with no predicate between
  them".

**Route B is the recommendation, for a reason about evidence rather than about performance.**
`tests/test_rca001_lock_scope.py` — merged with `R1-05` (#208) and now on `main` — allowlists which
methods may reach a lock. `_MAY_LOCK` names **six**: four store-level
(`apply_owner_reducing_change`, `_apply_membership_change`, `revoke_membership`,
`demote_membership`) and two service-level verbs that reach them (`disable_account`,
`demote_to_member`). Its docstring says "A seventh appearing fails the test rather than passing
unnoticed", and the scan follows delegation — so it is not enough for `R4-05` to add the locking
store method; **every service verb that reaches it must be listed too**, which for Route A means
`redeem` as well. **Route A therefore requires at least two new `_MAY_LOCK` entries**, plus a
predicate-by-predicate compilation test alongside the existing ones, because that file asserts each
locking statement's predicates "clause by clause -- not merely that a predicate appears somewhere in
the SQL". Route B adds nothing to `_MAY_LOCK` at all, since it takes no `FOR UPDATE`.

> **Correction, 2026-08-18 (`R4-01`).** The previous revision said the allowlist named "exactly
> four" and lived on an unmerged branch, and flagged cross-branch coordination as the main cost of
> Route A. `R1-05` has since merged, which settles that coordination question — the allowlist is on
> `main`, so `R4-05` is unambiguously the slice that owes any edit — and reading the merged file
> corrects the count: six entries, in two tiers, because the scan follows delegation from the
> service verb down. The tiering makes Route A's cost *higher* than the previous revision stated,
> not lower, so the recommendation is unchanged and better supported. Recorded rather than silently
> renumbered, because "exactly four" was checkable and wrong.

**Whichever route, the membership insert and the redemption mark commit together.** `FR-018`'s
"exactly one" is a cardinality claim, and a membership committed without the redemption mark is a
token that redeems twice.

**Already a member?** Refuse with the same uniform failure, and do not create a second membership —
the composite primary key `(organization_id, account_id)` makes a duplicate unexpressible, so this
is enforced structurally and the refusal is about not consuming the token silently. **The key
protects only against the same account twice**, which is why §6.2 exists: two *different* accounts
redeeming one token produce two distinct keys and the constraint refuses neither.

**`MembershipEvent` needs no new kind, and that is worth stating.** Its docstring says the kind is
carried by nullability — creation has no prior role, revocation no next role — and warns that "if a
future kind cannot be distinguished this way, that is when to add the column". An
invitation-redemption *is* a membership creation: `prior_role IS NULL`, `next_role = intended_role`.
It is distinguishable from organization-creation only by the actor differing from the subject, which
the existing columns already carry. **So `R4` adds no column**, and the nullability design holds
against its first real test.

### 6.3 The two matrix rows `R4` owes `R6-01` §3.1

`R6-05`'s `test_every_protected_action_in_the_design_has_a_matrix_class` parses `R6-01` §3.1's table
and **fails when an action there has no test class** — verified by adding an invitation row and
watching it fail. So these rows and their `ACTION_COVERAGE` entries land in the same slice as the
operations, never later:

| Action | owner | member | non-member | unauthenticated |
|---|---|---|---|---|
| Issue an invitation | **PERMIT** | DENY | DENY | DENY |
| Revoke an invitation | **PERMIT** | DENY | DENY | DENY |

`FR-015` names *invite* as an owner capability, which settles the owner and member columns.

**Redemption is deliberately not a row.** Every §3.1 action is authorized by the actor's membership
in the named organization; a redeemer holds none by definition. Redemption is authorized by the
*secret*, not by a role, so it belongs to §3.2's self-versus-another shape or to neither. Putting it
in §3.1 would mean a non-member `DENY` cell that contradicts `FR-019`. Recorded because "add all
three verbs to the matrix" is the obvious wrong move.

## 7. `FR-020` — revocation cascades to unredeemed invitations

Revoking a membership must invalidate that member's unredeemed invitations **to that organization**.

> **Correction, 2026-08-17 (`R4-01`).** The first version of this section chose the narrow reading —
> revocation invalidates invitations the revoked member **issued** (`issued_by`) — because §3 stored
> no invitee identity and the recipient reading was therefore unimplementable. The premise was the
> §3 error corrected above; with `target_identity` stored, the recipient reading is implementable,
> and a counter-example shows the narrow reading does not satisfy `FR-020` at all. Both readings
> turn out to be required, for different reasons, and the corrected text is below.

**The counter-example that kills the narrow reading.** A person holds **two** outstanding
invitations to organization `O`. They redeem the first and become a member. That membership is then
revoked — for cause, say. They redeem the second invitation and rejoin `O` immediately, at whatever
`intended_role` it names. Under the narrow reading nothing invalidated the second invitation,
because its `issued_by` is the *owner who sent it*, not the revoked member. Revocation therefore
stopped nothing: `FR-030`'s "stops at the next authorization decision" held for a few milliseconds,
and the member walked back in through a token they already held. That is not a corner case — it is
the ordinary consequence of any organization that sends more than one invitation to the same person,
and §3's decision not to add `UNIQUE (organization_id, target_identity)` makes it expressible by
design.

**So `FR-020` takes the recipient reading.** "That member's unredeemed invitations" means the
invitations **addressed to** the revoked member — `WHERE organization_id = O AND target_identity =
<the revoked member's identity> AND redeemed_at IS NULL AND revoked_at IS NULL`. Three things make
this the right reading rather than merely the convenient one:

1. **It is what the words say.** An invitation "belongs to" the person it invites in ordinary
   usage; the issuer's invitations are the ones they *sent*. `FR-020` says "that member's unredeemed
   invitations to that organization", and an issuer's invitations are not *to* an organization they
   already belong to — the recipient's are.
2. **It is the only reading under which revocation actually revokes.** `FR-030` requires a
   membership change to take effect for decisions made after it. A reading that leaves a held token
   able to recreate the revoked membership defeats the requirement it sits next to.
3. **The identity to match against is available — with one exception, handled below.** The revoked
   member has an account, so their `target_identity` is resolvable at revocation time. `R4-06` must
   match it **canonically**, the same way `_canonical_or_none` (`persistence.py:254`) normalizes an
   account's email, or a case difference between issuance and account creation silently spares the
   invitation.

### 7.1 The tombstone case, where the recipient anchor does not exist

**The state.** `KHEPRI-DEC-015` §2b purges a disabled account after twenty-four months:
`row.email = None` (`persistence.py:356`), leaving an opaque tombstone. A membership revoked *after*
that purge has no resolvable identity, so the recipient predicate above — `target_identity = <the
revoked member's identity>` — cannot be constructed at all. Meanwhile §4 makes `expires_at` a free
parameter, so a still-unexpired invitation may retain the old address. The cascade silently matches
nothing, and the invitation stays open.

**Why that is worse than it first looks.** The address is released when the account is purged, so it
can be registered by a **different** person. That new account is then, by §6.1.1's own rule, the
legitimate addressee of an invitation issued to someone else entirely — and it redeems into `O`.
The failure is not "revocation missed a row"; it is that a purge plus a stale invitation transfers
an offer of membership from one person to another.

**The fix is a cascade at the purge, not a bound on `expires_at`.** The other available route — cap
invitation lifetimes so this state is unreachable — is refused: §4 fixes that `expires_at` is a
parameter because "baking one in would put a product decision in the domain", and a ceiling is that
same product decision written as a maximum. Nothing about identity purging tells us how long an
invitation should live. What it does tell us is that the invitation's addressee has ceased to exist,
which is a **lifecycle** fact this note may act on.

So the destruction-trigger list gains a fifth entry, derived rather than invented: an invitation
whose addressee is purged has lost the identity the matrix retains it to attribute, so both of
`KHEPRI-DEC-015` §2's authorized purposes have lapsed exactly as §3's purge derivation describes.

**`R4-06` invalidates on account purge.** In the same transaction as `purge_if_still_eligible`
(`persistence.py:338`), and for the reason that method exists rather than by analogy: it re-reads
and re-checks inside the writing transaction because a select-then-write across two transactions
"erased a re-enabled account's email". An invitation cascade run *after* the purge returns has that
same gap, plus the one §7's atomicity note names — a failure between the two leaves the address
released and the invitation open, which is the whole defect. Predicate: `target_identity =
canonical(<the address being purged>) AND redeemed_at IS NULL AND revoked_at IS NULL`, across
**every** organization rather than one, since the purge is not scoped to a membership. The address
must be read before it is nulled, which fixes the ordering inside that transaction.

**Note this is the one cascade with no organization in its predicate**, and that is correct: the
trigger is the identity ending, not a membership ending, so every outstanding offer to that person
lapses at once. §7's two triggers stay organization-scoped; this third one cannot be.

**What `R4-06` owes as evidence.** Purge an account holding an unexpired, unredeemed invitation;
assert the invitation is closed and its verifier destroyed. Then the case that motivates it: after
the purge, register a **new** account at the same address and assert it cannot redeem that
invitation — which fails on an implementation that only closes invitations at membership
revocation.

**The issuer trigger is retained as well, because an active record requires it.** `KHEPRI-DEC-015`
§2's Invitation row names four end triggers verbatim: "Acceptance; expiry; revocation; **revocation
of the inviting membership** (`FR-020`)". That fourth trigger *is* the narrow reading, and it is
governed rather than optional — dropping it while correcting §3 would repeat this note's original
mistake in the opposite direction. It also closes a genuine hole the recipient reading does not
touch: a demoted or removed owner should not have outstanding invitations that still work, since the
authority under which they were issued is gone.

**Two triggers, two anchors, one cascade.** `R4-06` invalidates, in the same transaction as the
revocation — see the atomicity note below, which fixes *which* transaction that is:

| Trigger | Predicate | Anchor |
|---|---|---|
| Recipient | `organization_id = O AND target_identity = <revoked member>` | `FR-020` |
| Issuer | `organization_id = O AND issued_by = <revoked member>` | `KHEPRI-DEC-015` §2 |

Both restricted to unredeemed and unrevoked rows, and both destroying the verifier as they mark
`revoked_at`, per §3's destruction rule. The two predicates overlap only when someone invited
themselves, so this is a union rather than a choice.

**The cascade is atomic with the membership deletion, and "the same transaction" means
`_apply_membership_change`'s.** This is the §6.2 argument in a second verb, so it is stated with the
same force. If the invalidation runs *after* `OrganizationStore.revoke_membership` returns, then a
crash, a lost connection, or an unhandled exception between the two leaves the membership revoked
while its invitation is **still open and still redeemable** — and the revoked member walks back in
through the held token, which is precisely the counter-example above, re-created by a partial
failure rather than by the narrow reading. Authority regained is the same outcome whichever way the
gap opens.

**Where the code must go, because the transaction is not the service's to open.**
`revoke_membership` (`persistence.py:817`) does not manage its own transaction — it delegates to
`_apply_membership_change` (`persistence.py:899`), which opens `with self._factory.begin()` at
`persistence.py:934`, does the lock, the final-owner guard, the `write` callback, and
`database.add(_event_row(event))`, and commits by leaving that block at `persistence.py:955`. So
there is no seam after `revoke_membership` in which a second store call could still be inside the
transaction. The cascade therefore runs **inside** that block.

**It goes in `revoke_membership`'s `write` callback, and the helper body is not an equivalent
placement.** `_apply_membership_change` is shared: `revoke_membership` delegates to it at
`persistence.py:862` and **`demote_membership` delegates to the same helper** at
`persistence.py:897`. A cascade placed in the helper's own body therefore runs on **both** verbs, so
demotion would invalidate the demoted member's invitations — which contradicts §7's closing note,
where this slice implements revocation only and demotion is left as an owner question. The two
placements are not two spellings of one design; one of them silently decides an open question.

The `write(database, row)` callback is the correct seam because it is **per-verb**: `revoke`
(`persistence.py:862`) and `demote` (`:897`) pass different callbacks to the same helper, both
already inside the transaction and already receiving the session. Putting the cascade there scopes
it to revocation by construction rather than by a guard someone can drop. If a later slice does
decide demotion invalidates too, that is a second callback edit and a visible one — not a behavior
that arrived because two verbs shared a helper.

**`R4-06` owes the negative case**, and it is the one a happy-path suite omits: **demote** an owner
holding outstanding invitations and assert those invitations are **still open**. That test fails on
the helper-body placement, which is why it is named here rather than left to review.

Three things commit or roll back **together**: the membership row's deletion, its `FR-014`
`MembershipEvent.revoked` event, and every invitation matched by either predicate above.
`revoke_membership`'s own docstring already makes this argument for two of the three
(`persistence.py:840-844`): "**The deletion and the event commit together.** … An event written
outside this transaction could describe a revocation that rolled back, and a deletion without its
event is an unattributed membership change." The cascade is the third member of that set for the
same reason — an invitation left open outside the transaction describes a membership that still
exists.

**What `R4-06` owes as evidence.** A test that revokes and then observes the invitations closed
passes on the non-atomic implementation too, since nothing crashed. The failure has to be induced:
force the invalidation to raise *after* the deletion is staged and assert the membership is **still
present** and the invitation **still open** — both halves, since a rollback that dropped only one
would be its own defect. `test_rca001_concurrent_final_owner.py` is the precedent for proving a
transactional claim rather than asserting the happy path.

**What remains uncertain, stated narrowly.** Not the reading — the counter-example settles it. What
is uncertain is whether `R4-06` should invalidate on **demotion** as well as removal.
`KHEPRI-DEC-015` says "revocation of the inviting membership"; a demoted owner's membership is not
revoked, but their authority to invite is gone under `FR-015`. `FR-020` says only "revoking a
membership". This note reads both as covering revocation and neither as requiring demotion, so
`R4-06` implements revocation only and records the gap. Flagged as an owner question that does not
block `R4-03`, since it changes no schema.

## 8. What this note does not settle

- **Delivery.** `target_identity` records *whom* an invitation is for; nothing here sends anything
  to them. No transport, no template, no send path. `R5-01` owes a delivery abstraction for
  recovery, and invitations should reuse whatever that decides rather than inventing a parallel one.
- **HTTP surface.** `R8-05`'s team-management screens and any endpoint are out of scope, exactly
  as `R6-01` left `R7-05`'s endpoint alone.
- **Whether an invitation can be re-sent.** Re-issuing is just `issue` again, which is why no
  `resend` appears above — but whether the old token should then be revoked is a product decision.
- **Whether demotion invalidates invitations**, per §7's closing note. Revocation is settled; the
  demotion case changes no schema, so it does not block `R4-03`.

**Removed from this list, and why.** Earlier versions listed **invitation retention**, **`FR-020`'s
reading**, and **the purge horizon** here. None is open.

- **Retention** is settled by `KHEPRI-DEC-015` §2's Invitation row — verifier destroyed at the
  trigger, status and target identity retained only while replay refusal needs them, record purged
  after — and §3 now records it along with the sweeper `R4-03` owes.
- **`FR-020`'s reading** is settled by §7's counter-example.
- **The purge horizon** was listed as an owner input for one version, on the grounds that the
  remaining lifetime was "an operational choice about table size". §3 corrects that: the horizon
  governs personal data, so it cannot be operational, and the matrix's two authorized purposes
  yield a lifecycle predicate directly. This note derives it rather than asking for a number.

Listing a settled question as open is a failure mode this note fell into twice — once for
retention, once for the horizon — and in both cases the cause was the same: reading `FR-016`'s
field list without opening the governing retention decision. Recorded so a reader of the list knows
the omissions are deliberate, and so the pattern is visible rather than repeated a third time.

**What genuinely remains open is one product question, not a design one:** whether demotion
invalidates invitations (§7's closing note). It changes no schema, so it does not block `R4-03`, and
§7's placement decision makes implementing it later a visible edit rather than an accident.

## 9. Slice sequence, unchanged from the roadmap

`R4-02` domain and hashed secret → `R4-03` persistence and migration (single head; `20260817_0017`
is current) → `R4-04` issuance and revocation → `R4-05` redemption → `R4-06` `FR-020` cascade →
`R4-07` the uniform-failure matrix. `R4-04`'s roadmap row already depends on "`R6-01` authorization
matrix draft", which §6.3 now supplies concretely.

**What each slice owes beyond its roadmap row**, collected because several arrive from corrections
above rather than from the roadmap:

| Slice | Additional obligation | From |
|---|---|---|
| `R4-03` | The sweeper, with the purge predicate evaluated in the deleting statement | §3 |
| `R4-05` | The concurrency control (Route A or B, recorded) | §6.2 |
| `R4-05` | The addressee check on the uniform verification path | §6.1.1 |
| `R4-06` | Cascade in `revoke_membership`'s `write` callback, **not** the shared helper | §7 |
| `R4-06` | Cascade at account purge, unscoped by organization | §7.1 |
| `R4-07` | Correct-secret-against-expired refusal; addressee-mismatch and `email is None` refusals; demotion leaves invitations open | §3, §6.1.1, §7 |
