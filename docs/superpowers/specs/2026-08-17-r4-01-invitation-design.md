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
alone changes no bytes, and something else must. The correction below settles what.

> **Correction, 2026-08-18 (`R4-01`), retracting this note's own previous answer.** An earlier
> revision of this section argued that "destroyed at the trigger" governs **authority** rather than
> bytes, so §5's refusal discharged the obligation and the sweeper merely reclaimed storage. That
> is wrong, and it was wrong by the same method this note has already failed by twice: quoting part
> of a governing record instead of reading the section that governs the subject. The argument
> leaned on `KHEPRI-DEC-015` §5's closing line ("a retained record is never a live grant") and
> skipped the paragraph directly above it, which is about verifiers specifically and is not about
> authority at all: "**A verifier whose purpose has ended is destroyed rather than retained: a used
> or expired verifier has no remaining purpose and every day it survives is unjustified risk**"
> (§5, lines 172-173). That sentence names *expired* explicitly — the exact case the retracted
> argument carved out — and measures the harm in **days of survival**, which is a claim about
> duration and therefore about bytes. A reading under which an expired verifier may sit until the
> next sweep contradicts it directly. `KHEPRI-DEC-015` is `active`, and a design note cannot narrow
> an active decision by reinterpreting it.

**So expiry needs a destruction mechanism, and "no code runs at `expires_at`" is a constraint to
engineer around rather than an excuse.** The obligation is that an expired verifier's bytes do not
survive, and the honest difficulty is that a derived state fires no event. Two mechanisms together
satisfy it, and `R4-03` owes both:

1. **Destroy on first touch after expiry.** Any path that loads an invitation and finds
   `expires_at <= now` destroys the verifier in that transaction before refusing. This costs
   nothing on the read path that was already happening and closes the case that matters most — an
   expired invitation someone is actively presenting is exactly the one whose verifier should not
   still be there.
2. **A sweeper as the backstop, on a schedule stated as a requirement rather than left to
   operations.** Touch-based destruction cannot reach an invitation nobody presents, so the sweep
   is what bounds survival for the untouched rows. `R4-03` must state its interval, because "every
   day it survives is unjustified risk" makes the interval the compliance property — an unstated
   schedule is an unbounded one. `MembershipEventSweeper` owns the horizon arithmetic for events
   and the same split applies: the sweeper owns "when", the store owns the transaction.

**What this does not do, stated so the residual is visible rather than papered over.** Neither
mechanism destroys the verifier *at* the instant, because nothing runs at that instant. The
residual window for an untouched, unpresented invitation is the sweep interval, and this note
cannot make it zero. What it can do is refuse to call that window compliant by redefinition, and
bound it explicitly instead.

**The interval itself is operational, and §8.1 records why that is not an evasion.**
`MembershipEventSweeper` states the convention — "one pass when called. Choosing a cadence is an
operational decision" (`lifecycle.py:240-241`) — and the account and event sweepers both purge
classes with *fixed* horizons on it, a stronger obligation than this one. What §5 binds is that a
destroying mechanism exists and does not depend on someone happening to look; both above satisfy
that. So `R4-03` picks the cadence and states in the docstring why it is operational, rather than
escalating a question the repo has answered three times.

**Independently of destruction, the refusal must not depend on it.** An expired invitation whose
verifier is still intact — which is every such row before its first touch — is refused on the state
predicate. `R4-05` and `R4-07` owe that case with the **correct secret** presented, since it fails
on an implementation that verifies the digest and returns success before checking `expires_at`.
That test was previously offered as evidence the delay was harmless; it is retained because the
property is worth proving on its own, not because it discharges the destruction obligation.

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
  `CHECK`. So this invariant is the domain's, enforced by the **two** paths that may destroy without
  setting a timestamp being the only ones that do: destroy-on-touch and the sweeper, both of which
  evaluate `expires_at <= now` in the destroying transaction (§3's destruction mechanisms). Any
  third path that nulls a verifier without a timestamp is the defect this constraint cannot catch.
  Recorded rather than papered over with a constraint that would be wrong.

## 4. Issuance and revocation

`InvitationService.issue(organization_id, intended_role, target_identity, *, actor_account_id,
expires_at, now)` returns a **single-use token** the caller must transmit and cannot recover
afterwards. `target_identity` is required rather than optional: `KHEPRI-DEC-015` §2's Invitation row
retains it "to attribute the resulting membership", and §7's cascade cannot match a row that has
none, so an invitation without one would be a row `FR-020` cannot reach.

**`target_identity` is canonicalized at issuance — a storage rule, not a comparison rule.** `issue`
stores `canonical_email(target_identity)` and never the raw input. Canonicalizing only at comparison
time is not equivalent, and the gap is a real defect rather than a tidiness point: an address issued
mixed-case or whitespace-padded is stored as typed, so every predicate that compares it against a
canonicalized operand — §6.1.1's addressee check, §7's recipient cascade, §7.1's purge cascade —
misses the row. §7.1's miss is the worst of the three, because a skipped purge leaves a stale
invitation redeemable at a **released** address, which is precisely the identity transfer that
section exists to prevent.

Canonical at rest turns all three into plain equality and removes the possibility that one call site
forgets. `_canonical_or_none` (`persistence.py:254`) is the in-repo shape, and the accounts table
already stores canonically for the same reason (`:455`), so invitations matching it keeps one
convention in the codebase rather than two.

Two consequences. `R4-03`'s migration and `R4-04` must both apply it, since a value written by a
store caller that bypasses `issue` would reintroduce the gap — the same "the domain refusing it is
not sufficient" argument §3's `CHECK` constraints rest on. And `R4-07` owes one case per predicate:
issue to `Alice@Example.COM `, then assert the addressee check, the recipient cascade, and the purge
cascade all match an account at `alice@example.com`.

- **Token format `kci1.<invitation_id>.<secret>`**, mirroring RRA's `kiv1.` with a distinct prefix
  so a beta token and a commercial token can never be confused at a boundary that accepts both.
  `R3-01` §2.1 established that reasoning for session keys.
- **`scrypt` at RRA's parameters** (`n=2**14, r=8, p=1, dklen=32`, 16-byte salt). Matching rather
  than choosing new parameters: two hashing schemes in one codebase means one of them is unreviewed.
- **The secret and salt are CSPRNG-generated, at stated sizes.** `secret = secrets.token_urlsafe(32)`
  and `salt = secrets.token_bytes(16)`, with `invitation_id = f"inv_{secrets.token_urlsafe(18)}"` —
  the same constructions `rra/sessions.py:78-80` already uses, so there is one generation scheme in
  the codebase rather than two. **Stated because the rest of this section does not imply it.**
  Fixing the token encoding, the KDF parameters, and the salt *length* still leaves generation
  unspecified, and an implementation can satisfy every other bullet above while using a predictable
  secret or a fixed salt. `scrypt` does not rescue that: it protects the stored verifier against
  offline attack on a *high-entropy* input, and cannot add entropy a bearer token never had.
  `FR-016` requires the secret be high-entropy, which is a property of how it is generated and of
  nothing else here.
- **`R4-02` owes a test on the sizes rather than on the values.** A generated secret is not
  assertable against a known value, so the evidence is shape: decoded length, and that two
  successive issuances differ. `secrets` is the only admissible source — `random` is not a CSPRNG
  and the distinction is invisible at a call site, which is why the module is named here rather
  than left as "generate securely".
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

**Revocation is a conditional transition, not a write to a row it has already read.** The composite
lookup above scopes *which* row revocation may reach; it does not make the open-to-revoked
transition atomic, and those two concerns read as one. Run concurrently with a redemption: both read
the invitation as open, redemption's §6.2 conditional update wins and sets `redeemed_at`, and
revocation — holding a stale snapshot — writes `revoked_at` over a row that is already redeemed.
Both outcomes are wrong. Either the write lands and the row claims two terminal states, which `CHECK
(redeemed_at IS NULL OR revoked_at IS NULL)` refuses **after** the membership has committed — so the
failure surfaces as an integrity error on the revoking transaction rather than as a refusal — or
the constraint is satisfied by ordering and terminal state is silently overwritten.

So `revoke` takes the shape §6.2 requires of redemption, for the same reason: **`UPDATE
rca_invitations SET revoked_at = :now, <the five verifier columns> = NULL WHERE organization_id =
:org AND invitation_id = :id AND redeemed_at IS NULL AND revoked_at IS NULL AND expires_at > :now`,
affecting exactly one row.** Zero rows means the invitation was not open — already redeemed,
already revoked, **expired**, or not reachable in this scope — and all of those take the **same
uniform refusal** this section already requires, so the `rowcount` check adds no disclosure.

**Revocation deletes the row rather than marking it, because §3's derivation leaves nothing to
retain.** The statement above destroys the verifier and keeps the row, which contradicts the purge
predicate §3 derives: a **never-redeemed** invitation loses *both* authorized purposes at the moment
it closes — attribution never attached, and §5 makes a deleted row indistinguishable from a
retained closed one for replay refusal — so §3 requires it purged when the verifier is destroyed,
not at a later sweep. Retaining `target_identity` past that point is personal data outliving its
purpose, which is exactly what that derivation forbids.

So revocation is a **`DELETE`** under the same predicate — `DELETE FROM rca_invitations WHERE
organization_id = :org AND invitation_id = :id AND redeemed_at IS NULL AND revoked_at IS NULL AND
expires_at > :now`, affecting exactly one row — and `revoked_at` exists in the schema for the
**redeemed-then-revoked** case §3's second purge rule covers, not for a row this verb leaves behind.
§7's cascades take the same shape. The uniform refusal is unaffected: a deleted row is an
unknown-identifier attempt, which §5 already requires to be indistinguishable.

**`expires_at > :now` is load-bearing and easy to omit**, since the two timestamp predicates look
like the whole of "still open". They are not: §5's state model makes expiry a **derived** terminal
state with no column, so an expired row that the sweeper has not yet reached still has
`redeemed_at IS NULL AND revoked_at IS NULL` and would match. `revoke` would then transition it
from expired to revoked and report **success**, where §5 requires every non-open state to receive
the uniform refusal — a state change the caller should not be able to make, reported in a way that
distinguishes expired from the other non-open causes. The predicate must restate §5's boundary
(`expires_at > now` is open) rather than assume the nullability columns carry it. §7's cascades
inherit this clause with the rest. §7's cascade is the same statement with a
recipient or issuer predicate in place of the identifier, and inherits the requirement.

This is §6.2's argument in a third verb. Recorded here rather than left to `R4-04` because the
composite lookup is the eye-catching part of this section and "scoped the row" reads like the whole
requirement — exactly as "one transaction" did in §6 before §6.2 was written.

**`R4-07` owes two revocation cases.** First, cross-organization rather than merely non-owner: an
owner of `A` presenting `B`'s `invitation_id` must be refused, and `B`'s invitation must still be
open afterwards — a test that only checks a `member` cannot revoke would pass on the defective
lookup. Second, the race: revoke concurrently with a redemption of the same invitation, and assert
exactly one terminal state with no integrity error raised on either path.

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
- **The dummy work must also run on the malformed-token path, which is earlier than the lookup —
  and that means a dummy *lookup* as well as a dummy hash.** The first version of this section paid
  the dummy scrypt only when the *lookup* missed, and that leaves the fastest path of all uncovered:
  a token that fails `kci1.<invitation_id>.<secret>` parsing never reaches a lookup, so it returns
  in microseconds while every other cause pays ~100ms. `FR-017` names malformed explicitly — "A
  replayed, expired, revoked, or **malformed** invitation MUST fail closed without revealing which
  check failed" — so malformed is one of the causes that must be indistinguishable, not a
  precondition outside the guarantee. Concretely: `redeem` catches its own parse failure, pays the
  dummy work, discards the result, and raises the same uniform refusal. Ordering matters — the
  dummy work is paid *before* the raise, in the same call — because a caller measures the call, not
  the branch.

  **Equal scrypt is not equal work.** Paying only the hash still leaves the malformed path skipping
  a **database round trip** that every other cause performs: an unknown identifier, a wrong secret,
  and a closed record all `SELECT` before they hash. Against a local SQLite test database that
  difference is noise, which is exactly why it would ship — against a networked PostgreSQL it is a
  measurable constant, and it reconstructs the distinction the dummy hash was added to remove.
  Scenario 8's timing evidence must therefore be gathered against a real database rather than
  in-memory, or it certifies nothing. So the malformed path performs a lookup too: `redeem` parses,
  and on failure substitutes a **syntactically well-formed identifier that cannot exist** — a
  module-level constant with the `inv_` prefix, never issued because `issue` derives identifiers
  from `secrets.token_urlsafe(18)` — then runs the ordinary lookup, discards the miss, pays the
  dummy hash, and raises. One code path, one round trip, one KDF invocation, whatever the cause.
  Stated concretely because "make the timings equal" is not implementable and "do a dummy lookup" is.
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
- **Destroy-on-touch adds a write, and the write must not be what distinguishes the expired
  case.** §3 requires that a path finding `expires_at <= now` destroys the verifier before
  refusing. That is an `UPDATE` and a commit which a wrong-secret attempt against an open row does
  not perform, so the expired refusal becomes measurably slower than the cause it must be
  indistinguishable from — the timing oracle this section exists to close, reintroduced by the fix
  for a different requirement one section earlier. Two ways out, and `R4-05` must record which:
  **equalize the write** so every refusal path performs one, or **move destruction off the refusal
  path** so the response does not wait on it. The second is preferable if it can be made to satisfy
  §3 — the touch that observes expiry is what §3 needs, not the caller's latency — but "queue it and
  return" is a durability claim, and a destruction that is lost on restart does not satisfy
  `KHEPRI-DEC-015`. Stated as a constraint on `R4-05` rather than resolved here, because the answer
  depends on whether the codebase grows a durable post-commit hook, which nothing in `RCA` has
  today.
- **The invariant, stated once so `R4-07` can assert it directly.** Every one of the six causes pays
  **equivalent work** — one database lookup, one `scrypt` at `n=2**14`, and, per the bullet above,
  the same write cost — before any refusal is raised: a malformed token that never parses, an
  `invitation_id` that matches no row, a row whose verifier is destroyed, a row that is expired,
  revoked, or already redeemed with its verifier intact, and a genuine wrong secret. Six causes, one
  message, equivalent work each. Anything that skips the
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

1. **The actor arrives already resolved, and is revalidated at the write.**
   `ActorResolver.resolve_actor` has run at the boundary, so the session was checked live and
   `assert_account_active` has already been consulted (`actor_resolution.py:87`). `FR-019` says
   acceptance "MUST require that an authenticated account exists at the moment of acceptance" —
   *at the moment*, so a token issued before the account existed is fine.

   > **Correction, 2026-08-18 (`R4-01`).** The previous revision said `redeem` does **not** re-check,
   > on the grounds that "`ResolvedActor`'s existence is the evidence, and a second check would be a
   > second authority over one fact". That is wrong once §6.2 exists. `ResolvedActor` carries an
   > `Account` **snapshot** — `resolve_actor` returns `ResolvedActor(session=session,
   > account=account)` (`actor_resolution.py:90`) after reading it — and §6.2 then opens a
   > transaction that takes a lock and may wait on a competing writer. So there is a window between
   > resolution and commit, and it is not a narrow one by construction: it is however long the lock
   > contends. An account disabled inside that window yields a **durable membership created for an
   > account that is no longer an authenticated actor**, and `FR-019`'s "at the moment of acceptance"
   > is a claim about the commit, not about the boundary check that preceded it. The invitation is
   > consumed too, so the state is not even recoverable by retry.
   >
   > The "second authority over one fact" objection was the right instinct aimed at the wrong
   > target. Two *independent* checks would be two authorities; re-reading the same fact inside the
   > transaction that depends on it is what `purge_if_still_eligible` (`persistence.py:338`) already
   > does, and for the identical reason — it "select[ed], then wr[o]te, and those were separate
   > transactions with no predicate between them".

   **So the write is conditioned on the account still being live — under the lock disablement
   already takes, not merely re-read.** A plain re-read inside the transaction is **not
   sufficient**, and specifying one was the previous correction's own defect: `disable_account` can
   commit between that read and redemption's commit, and neither transaction sees a conflict, so
   both land and the membership survives its account. Re-reading narrows the window; it does not
   close it. Closing it requires the two operations to **contend on the same rows**.

   **The row to contend on is the account row, and reusing the disable path's lock does not
   work.** `apply_owner_reducing_change` (`persistence.py:766`) locks
   `owner_memberships_for_update(account_id)` (`:787`) rather than the account row, so reusing that
   statement is the obvious move and it is **wrong here**: that query selects owner rows in
   organizations the account already owns, and `FR-019`'s invitee owns none — frequently the
   account did not exist when the invitation was issued. `SELECT ... FOR UPDATE` over an **empty
   result set acquires no lock at all**, so a concurrent `disable_account` blocks on nothing and
   the window stays open exactly as it was.

   That failure mode is not hypothetical, and the same file records it: the docstring at `:521-528`
   describes the predicate's *previous* form locking "pairwise-disjoint single-row sets", so
   "`FOR UPDATE` had nothing to block on: all three read 'other effective owners exist', all three
   passed the guard, and all three committed, leaving zero" — measured at "4 failures in 12 against
   real PostgreSQL". An empty set is that defect at its limit. A lock is only a lock over rows that
   exist.

   **So `R4-05` locks the account row itself** — `SELECT ... FROM rca_accounts WHERE account_id =
   :id FOR UPDATE`, as a **module-level named statement** for the reason `:514-519` gives, since an
   inline `.with_for_update()` is silently dropped on SQLite and the suite would stay green without
   it — and evaluates `can_act` on the row it read under that lock. `accounts.py:68` names that
   "the single definition of 'live'", and its docstring records `FR-013` drifting exactly by growing
   a local judgment instead ("counted owner-role rows without consulting account state").

   The account row is the right anchor because it is the one row **both** operations certainly
   touch: disablement writes it, and redemption's liveness question is about it. Every other
   candidate is conditional on state the invitee may not have.

   **`disable_account` must take that lock too, or redemption contends with nothing.** A lock only
   serializes writers that acquire it, and `apply_owner_reducing_change` currently locks membership
   rows and then writes the account row without locking it. So this slice owes a change on the
   disable path as well: acquire the account-row lock before the guard, in addition to the existing
   membership lock, which is additive and leaves `#155`'s fix untouched. Once both paths take it, a
   concurrent `disable_account` either blocks until redemption commits — then observes the new
   membership — or wins, and redemption's `can_act` reads the disabled row. One of the two, never
   both.

   **This crosses `R4`'s boundary, and the note stops at the requirement rather than the
   sequencing.** `R4-05`'s roadmap dependencies are `R4-03`, `R2` merged, and `R3` actor resolution
   — **not** `R1`. Requiring it to modify `apply_owner_reducing_change` puts it in `R1`'s merged
   concurrency path, the method `#155` and `R1-05` both landed on, and adds `_MAY_LOCK` entries in
   `tests/test_rca001_lock_scope.py`. That is a dependency this note is not authorized to add to a
   roadmap row.

   So what this note settles is the **requirement**: redemption must serialize against the writes
   that end the actor's authority, and a lock taken by both paths is the mechanism that satisfies
   it. Who lands each counterpart is settled in §8.4: `R1-07` takes the account row's lock on the
   disable path, `R3-12` takes the session row's in the session-ending writes, and `R4-05` depends
   on both. Until they land, `R4-05` is specifiable but not startable — a redemption implemented
   without its counterparts contends with nothing, which is the defect two revisions of this
   section already shipped.

   **And the account is not the only stale half of `ResolvedActor`.** It carries a `session` as
   well (`actor_resolution.py:90`), and `SessionService.revoke` or `revoke_all` can end that session
   while redemption waits on its locks — so a membership can commit from a session that is no
   longer authenticated, which fails `FR-019` under this section's own commit-time reading of "the
   moment of acceptance". The account fix does not cover it: revoking a session does not touch
   `rca_accounts`, so `can_act` still passes. Session expiry has the same shape, since
   `expires_at <= now` may become true while the transaction waits.

   This is the **same escalation, one level out** rather than a second design problem: it needs the
   session row locked and re-read inside the redemption transaction, and the session-ending writes
   to take that lock too — which is again a change to a path `R4` does not own. §8.4 records both
   counterparts as `R1-07` and `R3-12`, because answering it for `disable_account` and not for
   `SessionService.revoke` would leave `R4-05` half-safe and looking finished.

   **Natural expiry is the part no lock reaches, and it needs a predicate rather than a
   counterpart.** `R3-12` locks the session row against `revoke` and `revoke_all`, which are
   *writes*. Expiry is neither: `Session.is_expired_at` is `self.expires_at <= moment`
   (`sessions.py:111`), derived from the clock, performing no write and touching no row. There is
   nothing for a lock to contend on, so redemption could lock the session an instant before
   `expires_at`, wait on the invitation or account lock, and commit a durable membership after it —
   with the lock held correctly throughout. A lock serializes writers; it does not serialize the
   passage of time.

   So the re-read evaluates **`Session.is_live_at(now)`** — "neither expired nor revoked"
   (`sessions.py:113`) — against a `now` re-read at that point, not `is_revoked`. The repo already
   holds both conditions in one predicate for this reason, and reaching past it to the revocation
   half alone is the drift `accounts.py:68` warns about for `can_act`. The lock covers the revoke
   race; the predicate covers expiry; neither substitutes for the other.

   `R4-05` owes the expiry case separately from the revocation one: hold the redemption transaction
   past the session's `expires_at`, release, and assert no membership was created. It fails on an
   implementation that checks only `revoked_at`, which is the shape a reader takes from "lock and
   re-read the session".

   A failure raises the §5 uniform refusal and the transaction rolls back, so **the invitation is
   not consumed**: the refusal is about the actor rather than the invitation, and a re-enabled
   account may still redeem.

   **This changes §6.2's recommendation, so it is flagged here rather than left to collide.** Route
   B was preferred because it "adds nothing to `_MAY_LOCK`". That advantage is gone — redemption
   now takes a lock for liveness whatever it does about at-most-once — so `R4-05` owes the
   `_MAY_LOCK` entries either way and the cost argument no longer separates the routes. See §6.2.

   **`R4-05`'s test must assert the outcome for whichever transaction wins, not one fixed
   outcome.** An earlier revision prescribed holding the redemption transaction open, committing a
   `disable_account`, and asserting no membership exists and the invitation is still open. That
   prescription is **not runnable under the lock it is meant to prove**: once redemption holds the
   account row, `disable_account` cannot commit until redemption releases it, so the stated
   ordering deadlocks or the disablement lands afterwards — and the assertion then rejects a
   **correct** serialization. Both orderings are valid; the test's job is to pin the outcome to the
   order rather than to demand one order.

   So two cases, each asserting the state its winner implies:

   | Winner | Required outcome |
   |---|---|
   | Redemption commits first | Membership **exists**, invitation **consumed**; the later disablement is valid and leaves a membership on a now-disabled account, which `can_act` refuses at the next authorization decision per `FR-030` |
   | Disablement commits first | **No** membership, invitation **still open**; redemption takes the §5 refusal |

   The second row is the one that fails on an unserialized implementation. The first is not a
   defect and must not be asserted away: a membership on a disabled account is `FR-030`'s ordinary
   post-revocation state, since disablement stops authority at the next decision rather than
   retroactively unwinding committed writes.

   Both run against **PostgreSQL** — SQLite emits no `FOR UPDATE`, so either case would pass on an
   unlocked implementation. `test_rca001_concurrent_final_owner.py` is the precedent for
   coordinating two real transactions rather than asserting a hoped-for interleaving. A test that disables *before* `redeem`
   is called passes on the unconditioned implementation, and one that disables after it returns
   passes on every implementation. `test_rca001_concurrent_final_owner.py` is the precedent for
   proving a contention claim against PostgreSQL rather than asserting it.
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
  :id AND redeemed_at IS NULL AND revoked_at IS NULL AND expires_at > :now`**, which **must affect
  exactly one row**; zero rows means the invitation was not open at the transition and the loser
  raises the uniform refusal.

  **`expires_at > :now` against a value read at transition time, for the reason §4.1 gives and one
  more.** §5 verifies before the lock is acquired, and the transaction may then wait — on the
  account row, the session row, or a competing redemption. An invitation open at verification can
  therefore be expired by the time this statement runs, and a predicate checking only the two
  timestamp columns would let it win: the row is still `NULL, NULL`, because expiry has no column.
  That would redeem an expired invitation, which `FR-017` refuses outright. The `:now` bound into
  this statement must be re-read at transition time rather than reused from the verification step,
  or the check is against a clock reading that predates the wait. **Route A needs the equivalent
  post-lock check** — the lock does not make the earlier `expires_at` comparison fresh, it only
  guarantees no competing writer, so `R4-05` re-evaluates expiry on the row it read under the lock
  before writing. The database's own
  row-level write lock does the serialization, so the claim rests on `rowcount` rather than on an
  explicit `FOR UPDATE`. `purge_if_still_eligible` (`persistence.py:338`) is the in-repo precedent
  for restating the selection predicate inside the writing transaction, and it exists because the
  sweeper "select[ed], then wr[o]te, and those were separate transactions with no predicate between
  them".

> **Correction, 2026-08-18 (`R4-01`).** The recommendation below was written when redemption's
> only reason to lock was at-most-once, so "Route B adds nothing to `_MAY_LOCK`" was a real
> saving. §6.1 step 1 has since established that redemption must lock the **account row**
> regardless, to serialize against `disable_account`. So `redeem` reaches a lock on either route,
> `_MAY_LOCK` gains its entries either way, and the evidence-cost argument no longer separates
> them. The recommendation stands on the reduced ground below — Route B still needs no
> predicate-by-predicate compilation test for a *second* locking statement, and still leaves the
> at-most-once claim resting on `rowcount` rather than on a lock whose absence a green SQLite suite
> would hide — but `R4-05` should treat the two as much closer than the text originally implied,
> and may reasonably prefer Route A now that one lock is unavoidable and a single serialization
> point is simpler to reason about than two mechanisms.

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

**An atomic purge-side cascade is not sufficient on its own: issuance must be serialized against
it.** The cascade above closes every invitation *visible* to the purge transaction. It does not
close one **inserted concurrently**: `issue` writes a new row for the address while
`purge_if_still_eligible` runs its `UPDATE`, the two lock no common row, both commit, and the
invitation is open after the address is released. That is the identity transfer this section
exists to prevent, arriving through a race rather than through a missing trigger — and unlike the
membership cascade there is no shared row to contend on, because the invitation being inserted did
not exist when the purge read the table.

> **Correction, 2026-08-18 (`R4-01`).** A previous revision proposed serializing the two paths on
> the **account row** — `issue` locking the addressee's account when one exists, and
> `purge_if_still_eligible` locking the row it already writes. That closes the issuance-first
> ordering and **not** the purge-first one, so it is not a fix. `purge_if_still_eligible` sets
> `row.email = None` (`persistence.py:356`) and the account row then survives only under its
> `account_id`. An `issue` that begins after the purge commits looks the addressee up **by
> canonical address**, finds nothing, and takes no lock — correctly, by that rule, since a
> post-purge miss is indistinguishable from `FR-019`'s ordinary no-account case. It then inserts an
> open invitation *after* the cascade has already run, and a replacement account at the released
> address redeems it. The identity transfer survives the fix.
>
> The general shape of the error: a **row** lock cannot serialize two operations when the
> discriminating fact is that the row stops being *discoverable* by the key one of them uses.
> Address-keyed discovery is exactly what the purge destroys.

**What this needs is an identity key that outlives the purge, and §8.2 records that no available
mechanism supplies one.** A transaction-scoped advisory lock closes the issuance-first ordering and
is what `R4-04` implements, but it carries no state across transactions, so the purge-first
ordering survives it: the purge releases the lock, `issue` acquires it, and a post-purge miss is
indistinguishable from `FR-019`'s ordinary no-account case. Detection — not serialization — is what
is missing, and every place an address-derived marker could live is closed by
`KHEPRI-DEC-015` §2b and §8 item 6. The candidates considered, and why each loses:

| Candidate | Objection it must answer |
|---|---|
| A retained one-way digest of the canonical address on the account row, surviving the purge as an opaque key both paths lock | `KHEPRI-DEC-015` §2b says a purged account is a tombstone and "nothing remains" — a retained digest is a linkable identifier, so this needs the decision's permission rather than a design note's |
| An identity-keyed advisory lock (e.g. `pg_advisory_xact_lock` over the canonical address) taken by both paths, storing nothing | Serializes without retaining anything, but it is PostgreSQL-specific and the repo's locking discipline is `_MAY_LOCK`-audited named statements; a lock that no compilation test can assert is the shape `persistence.py:516` warns about |
| Purge closes invitations *and* blocks issuance for a bounded window afterwards | Bounds rather than eliminates, and needs a number nobody has decided |

The digest candidate is barred by text rather than judgment — §2's Login-identity row reads
"**Purged.** Nothing remains" and §2b enumerates the tombstone as holding no email address — so
admitting it would need an amendment, which this note does not seek for a problem the advisory lock
solves without retaining anything. §8.2 carries the full argument and the evidence `R4-04` owes.

**What `R4-06` owes as evidence.** Purge an account holding an unexpired, unredeemed invitation;
assert the invitation is closed and its verifier destroyed. Then the case that motivates it: after
the purge, register a **new** account at the same address and assert it cannot redeem that
invitation — which fails on an implementation that only closes invitations at membership
revocation. Then the race, against PostgreSQL, **once §8's mechanism question is answered**: `issue` to a
disabled account's address concurrently with its purge — in **both** commit orders, since the
purge-first ordering is the one that defeated the retracted fix — and assert that no invitation to
that address is open afterwards.

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
demotion would invalidate the demoted member's invitations — which §8.3 settles it must **not** do.
The two placements are not two spellings of one design; one of them silently reverses a decided
question, and does so through a helper two verbs happen to share.

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

**Demotion does not invalidate, and that is now settled rather than flagged** — see §8.3 for the
argument. Both governing texts name revocation (`FR-020`: "revoking a membership";
`KHEPRI-DEC-015` §2's fourth trigger: "revocation of the inviting membership"), and the
counter-example above does not transfer to demotion: there the revoked member held a token
restoring **their own** membership, whereas a demoted owner's outstanding invitations are held by
third parties who did nothing and were issued under authority genuinely held at the time. So
`R4-06` implements the two triggers tabled above and no third, and `R4-07`'s demotion case proves
an intended behavior rather than guarding an open question.

## 8. What this note does not settle

- **Delivery.** `target_identity` records *whom* an invitation is for; nothing here sends anything
  to them. No transport, no template, no send path. `R5-01` owes a delivery abstraction for
  recovery, and invitations should reuse whatever that decides rather than inventing a parallel one.
- **HTTP surface.** `R8-05`'s team-management screens and any endpoint are out of scope, exactly
  as `R6-01` left `R7-05`'s endpoint alone.
- **Whether an invitation may be re-sent to a *different* address.** Re-issuing to the same one is
  just `issue` again. Whether the old token should then be revoked is a product decision, and §6.1.1
  gives it teeth: an invitee who registers at a different address than the one invited cannot
  redeem, so re-issuance is the recovery path and `R8-05` will need to offer it.

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

**What genuinely remains open: two items.**

- **Whether an invitation may be re-sent to a different address**, above — a product question for
  `R8-05`, blocking nothing in `R4`.
- **Issuance versus identity purge** (§8.2) — a `KHEPRI-DEC-015` question. Closed in an earlier
  revision and reopened, because the mechanism chosen does not close the purge-first ordering and
  no candidate that does is available without a decision change.

**Closed since the first review round, with the authority for each.** Four items sat here across
earlier revisions. Three are closed below on this note's own authority, and the fourth is resolved
as a sequencing decision. They are recorded rather than deleted, because each was escalated once
and a reader who saw the escalation is owed the resolution.

### 8.1 The sweep interval is an operational decision, not a governance one

**Closed.** An earlier revision escalated "does a sweep interval satisfy `KHEPRI-DEC-015` §5 for
expired verifiers" as a question this note could not answer. It over-escalated: the repo already
has the convention, stated three times.

`MembershipEventSweeper`'s docstring (`lifecycle.py:240-241`) is explicit — "**This is not a
scheduler**, following `AccountRetentionSweeper` and `khepri.local.sweeper`: one pass when called.
**Choosing a cadence is an operational decision.**" Three sweepers already exist on that split, and
none of them asked for a number.

What §5's "every day it survives is unjustified risk" binds is the **design**, not the deployment
cadence: there must be a mechanism that destroys, and it must not depend on someone happening to
look. §3 satisfies that with destroy-on-first-touch plus a sweeper backstop. A cadence chosen at
deploy time is the same shape `KHEPRI-DEC-015` already tolerates for the account and event
sweepers, both of which purge classes with fixed horizons — a stronger obligation than an
invitation verifier's, since those horizons are stated in the decision and this one is derived.

So `R4-03` builds `InvitationSweeper` on the `MembershipEventSweeper` shape: one pass when called,
the horizon arithmetic in the sweeper, the transaction in the store. **No owner input, and no
`KHEPRI-DEC-015` amendment.** What `R4-03` does owe is the docstring stating why the interval is
operational, so the next reader does not re-escalate it.

### 8.2 Issuance versus identity purge — open, and no candidate mechanism survives

**This item was closed in an earlier revision of this section and is reopened.** The closure picked
a transaction-scoped advisory lock over the canonical address. It does not work, and the reason
generalizes past this candidate.

**A mutex prevents overlap; it carries no state across transactions.** Take the purge-first
ordering: `purge_if_still_eligible` acquires the lock, closes the existing invitations, nulls the
address, and **releases**. The waiting `issue` then acquires the same lock, looks the addressee up,
and finds nothing — which is indistinguishable from `FR-019`'s ordinary invitee who never had an
account. It inserts an open invitation at an address that is now released, and a replacement
account redeems it. Serialization was never the missing ingredient. **Detection is**, and the lock
supplies none.

**That is the third mechanism this section has lost to one fact**, which is why the pattern is
recorded rather than a fourth attempted: the purge destroys the only evidence the address was ever
used. A row lock needs a discoverable row (retracted above); an advisory lock needs state to
outlive it (retracted here); a retained digest *is* the state, and is barred.

**Why "just make issuance fail closed" is not available to this note.** A fail-closed detector must
answer "was this address purged?" after the purge, which requires something address-derived to
survive it. `KHEPRI-DEC-015` closes both places it could live:

- The **tombstone** holds "an opaque account identifier and the disablement timestamp — **no email
  address**, no credential verifier, no profile data" (§2b).
- The **revocation ledger** holds "opaque identifiers, revocation timestamps, and status only: **no
  email address**" — and §8 item 6 states the reason directly, that the mechanism "could quietly
  become a second identity store. It must not."

An address-keyed purge marker is that second identity store under a different name, and it would
outlive the identity it describes — which is the retention inversion §2's matrix exists to prevent.

**So this is a `KHEPRI-DEC-015` question, not an `R4-04` one, and it is stated narrowly.** The
decision would have to admit *some* address-derived survivor with its own bounded horizon, or
accept the residual risk explicitly, or forbid issuance to a disabled account's address outright —
which is the one option needing no new retained data and is a product decision about behavior, not
a mechanism. `R4-04` must not choose among these: two of the three change what a purged account
leaves behind.

**What `R4-04` may implement today, and what it must not claim.** Take the advisory lock anyway —
it closes the *issuance-first* ordering, which is a real half of the hazard, and it stores nothing
so it prejudges no answer. But its docstring must record that the purge-first ordering remains
open, so a reader does not mistake a half-closed race for a closed one. `R4-07`'s two-order test
is written but the purge-first case is expected to fail until this is decided; mark it
`xfail(strict=True)` with this section as the reason, so the day it starts passing, something
changed and the suite says so.

**And `R4-05` waits on this, which an `xfail` does not accomplish by itself.** An `xfail` records
a known gap; it does not stop the code that makes the gap reachable. The hazard here is inert
until redemption exists — an invitation open at a released address grants nothing while nothing
can redeem it — so shipping `R4-05` is exactly the step that converts a documented hole into a
stranger holding a membership. Issuance and revocation (`R4-04`) are safe to land meanwhile,
because neither confers authority.

So `R4-05` depends on this item's resolution, and the roadmap carries it as a dependency rather
than as a comment. Recorded because "it's tracked in the spec and xfailed in the suite" reads like
a gate and is not one: both are records, and neither is a blocker.

<details>
<summary>The candidates considered when this was closed, retained for the record</summary>

**Closed on the second of §7.1's three candidates**, because the first is barred and the third is
not a mechanism.

**The retained-digest candidate is barred by the text, not merely disfavoured.**
`KHEPRI-DEC-015` §2's Login-identity row (line 74) gives the post-trigger state as "**Purged.**
Nothing remains", and §2b enumerates exactly what the tombstone holds: "an opaque account
identifier and the disablement timestamp — **no email address**, no credential verifier, no profile
data". A one-way digest of the canonical address is derived from the purged field and is linkable
by construction — present the address, compute the digest, match the tombstone. Retaining it would
be retaining the login identity in a weaker encoding, which is the "no single retention horizon is
quietly longer than another" discipline §3 already invokes. Admitting it needs an amendment, and
this note does not seek one for a serialization problem that has a mechanism requiring no
retention.

**The blocking-window candidate bounds rather than closes**, and needs a number nobody has decided.
A race narrowed is a race.

**So: `pg_advisory_xact_lock` over the canonical address**, taken by both `issue` and
`purge_if_still_eligible`. It stores nothing, so §2b is untouched; it is transaction-scoped, so it
releases on commit or rollback without a cleanup path; and it serializes on the *identity* rather
than on a row, which is what §7.1 established the problem requires — the purge destroys row
discoverability, and an advisory key does not depend on a row existing.

**The objection §7.1 raised against it is answerable, and the answer is the repo's own.** A lock no
test can assert is the shape `persistence.py:516` warns about. So the advisory call is a
**module-level named statement** alongside `owner_memberships_for_update` and its siblings, and
`R4-04` owes the same evidence they carry: a test compiling it against the PostgreSQL dialect and
asserting the advisory acquisition is present, "without needing a database" (`:518-519`). Same
discipline, different lock primitive.

Two consequences. The key must be derived from the **canonical** address per §4's storage rule, or
the two paths lock different keys and serialize nothing. And this is PostgreSQL-specific: SQLite
emits no advisory lock, so `R4-07`'s race case runs against PostgreSQL, exactly as §6.2's does.

</details>

### 8.3 Demotion does not invalidate invitations

**Settled, where §7's closing note left it open.** Both governing texts name revocation and neither
names demotion: `FR-020` says "revoking a membership", and `KHEPRI-DEC-015` §2's fourth end trigger
is "revocation of the inviting membership". Reading demotion in would extend two records past their
words.

**The argument for the other reading, and why it does not carry.** A demoted owner's authority to
invite is gone under `FR-015`, so their outstanding invitations look like authority surviving its
source. But §7's counter-example — the one that forced the recipient reading — does not transfer.
There, the revoked member held a token that would **restore their own** membership, so revocation
revoked nothing. Here the tokens are held by **third parties** who did nothing, and were issued
under authority the issuer genuinely held at the time. Invalidating them punishes the invitee for
the inviter's demotion, and `FR-015` governs who may *issue*, not how long an issued invitation
lives.

`FR-030`'s "stops at the next authorization decision" is satisfied either way: the demoted owner
cannot issue again, which is the authority that changed.

So `R4-06` implements the two triggers §7 tables and **no third**. `R4-07` owes the negative case
§7 already names — demote an owner holding outstanding invitations, assert they are still open —
which now proves an intended behavior rather than guarding an undecided one.

### 8.4 The counterpart locks land as `R1-07` and `R3-12`

**Resolved as a sequencing decision** (owner, 2026-08-18), where an earlier revision left it open.
§6.1 establishes that redemption must serialize against every write that ends the actor's authority
mid-transaction, and that a lock only serializes writers which acquire it. Both counterparts sit
outside `R4`, so each lands in the family that owns the path:

| Slice | What it does | Why there |
|---|---|---|
| `R1-07` | `apply_owner_reducing_change` (`persistence.py:766`) takes the account row's lock, in addition to the membership rows it already locks | Same concurrency defect class as `#155`, on the same method. `R1` is not closed — `R1-06` is the closeout row — so the family that owns this path is still open |
| `R3-12` | `SessionService.revoke`/`revoke_all` take the session row's lock | The session is `R3`'s object, and `ResolvedActor` carries it |

`R4-05` depends on both, and **`R1-06` now depends on `R1-07`** so `#155` closes over the final
state of the method rather than over a version `R4` would later change underneath it. Both
additions are on the roadmap.

**Why not `R4-05` doing both**, which is the faster route: a slice whose declared dependencies are
`R4-03`, `R2`, and `R3` would modify `R1`'s merged concurrency path and `R3`'s session service, add
`_MAY_LOCK` entries for both, and owe a re-run of `test_rca001_concurrent_final_owner.py` — and
`R1-06` would then close `#155` over a method `R4` had just changed. The locking discipline in this
repo is `_MAY_LOCK`-audited precisely so that no lock arrives without an owner; landing two through
a third family's slice is how that audit stops meaning anything.

Each of `R1-07` and `R3-12` owes what the existing locking statements owe: a module-level named
statement, and a dialect-compilation test asserting `FOR UPDATE` is present (`persistence.py:514-519`).

## 9. Slice sequence

`R4-02` domain and hashed secret → `R4-03` persistence and migration (single head; `20260817_0017`
is current) → `R4-04` issuance and revocation → `R4-05` redemption → `R4-06` `FR-020` cascade →
`R4-07` the uniform-failure matrix. `R4-04`'s roadmap row already depends on "`R6-01` authorization
matrix draft", which §6.3 now supplies concretely.

**`R4-05` depends on `R1-07` and `R3-12`**, per §8.4, and the roadmap now carries both. Redemption's
own locks do nothing until those counterparts acquire theirs, so starting `R4-05` first would
produce a slice that looks finished and serializes nothing. `R4-02`, `R4-03` and `R4-04` are
unaffected and can proceed in parallel with them.

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
