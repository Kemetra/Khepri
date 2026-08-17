# R4-01 — invitation state, expiry, revocation, intended role, and authenticated redemption

**Task:** `R4-01` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Output is a design, not code.

**Baseline:** `main` @ `086b960`, 2026-08-17 (`R7-02` and `R7-04` merged; `R1-05` in review, so `R1`
is not yet closed). `uv run khepri-gov validate` passes; `uv run pytest` reports 2197 passed, 47
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
`expires_at < now`, a derived state with no column and no event — so an expired invitation's
verifier survives until something sweeps it. That is the sweeper below, and it is why expiry cannot
be handled by "destroy it when the state changes".

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

**What "when replay refusal no longer needs it" resolves to is still an owner input, but bounded.**
The matrix fixes the *rule* (lifecycle-derived, no fixed duration) and `KHEPRI-DEC-015` §2a is
explicit that its twelve months is for audit classes only and that "what does not transfer is the
**number**". So `R4-03` must not import twelve months by analogy. Replay refusal needs the row for
as long as a leaked token could plausibly be presented, which is bounded below by `expires_at` — a
redeemed or revoked row is refusable from its own timestamps, and an expired row is refusable from
`expires_at` alone once the verifier is gone. A row past `expires_at` whose verifier is destroyed
can refuse replay without any secret material, so the purge horizon is an operational choice about
table size, not a privacy horizon. Recorded here so `R4-03` does not read the absence of a number as
an absence of a decision.

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
  `expires_at < now()` is not writable: `now()` is not immutable and PostgreSQL refuses it in a
  `CHECK`. So this invariant is the domain's, enforced by the sweeper being the only path that
  destroys without a timestamp. Recorded rather than papered over with a constraint that would be
  wrong.

## 4. Issuance

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

## 5. State, and what "fail closed" means concretely

Four states, discriminated by nullability rather than a status column — following
`MembershipEvent`'s reasoning verbatim, because a `status` field could disagree with the timestamps
and then two fields would describe one fact:

| State | `redeemed_at` | `revoked_at` | `expires_at` vs now |
|---|---|---|---|
| open | NULL | NULL | future |
| expired | NULL | NULL | past |
| redeemed | set | NULL | any |
| revoked | NULL | set | any |

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
3. **Create exactly one membership** at `intended_role` in `organization_id` for
   `actor.account_id`, and mark the invitation redeemed, **in one transaction under a lock or a
   conditional update** — see §6.2, because "one transaction" alone is not sufficient.
4. **Emit `MembershipEvent.created`** with `actor_account_id` = `actor.account_id`. Attribution
   travels with the write for the reason `create_organization` records: an event committed
   separately can describe a change that rolled back.

**`organization_id` comes from the invitation row, not from the request, and that is not an
exception to §5's rule.** The invitation is authenticated by its secret before its `organization_id`
is read, so the identifier is derived from a verified record rather than trusted from a caller. This
is the one place in `RCA` where a scope is not derived from the actor's session membership — by
necessity, since `FR-019`'s redeemer holds no membership yet — and it is safe for the narrower
reason that the *secret* is the authorization. Stated because it looks like the violation corrected
above and is not.

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
`tests/test_rca001_lock_scope.py` on branch `test/r1-05-lock-scope` allowlists which methods may
reach a lock — `_MAY_LOCK` names exactly four (`apply_owner_reducing_change`,
`_apply_membership_change`, `revoke_membership`, `demote_membership`) — and its own docstring says
"A fifth one appearing fails the test rather than passing unnoticed", with the scan following
delegation. **Route A therefore requires adding a fifth entry to `_MAY_LOCK`**, plus a
predicate-by-predicate compilation test alongside the existing ones, because that file asserts each
locking statement's predicates "clause by clause -- not merely that a predicate appears somewhere in
the SQL". Route B adds nothing to `_MAY_LOCK` at all, since it takes no `FOR UPDATE`.

**Cross-branch coordination, flagged because it will bite otherwise.** `R1-05` is in review (see the
baseline note at the top), so that allowlist is not on `main` yet. If `R4-05` takes Route A and
`R1-05` merges afterwards, the allowlist arrives already stale and `R1-05`'s own test fails on a
method it never heard of. Whichever slice lands second owes the edit. Route B avoids the coupling
entirely, which is most of why it is preferred.

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
3. **The identity to match against is available.** The revoked member has an account, so their
   `target_identity` is resolvable at revocation time. `R4-06` must match it **canonically**, the
   same way `_canonical_or_none` (`persistence.py:254`) normalizes an account's email, or a case
   difference between issuance and account creation silently spares the invitation.

**The issuer trigger is retained as well, because an active record requires it.** `KHEPRI-DEC-015`
§2's Invitation row names four end triggers verbatim: "Acceptance; expiry; revocation; **revocation
of the inviting membership** (`FR-020`)". That fourth trigger *is* the narrow reading, and it is
governed rather than optional — dropping it while correcting §3 would repeat this note's original
mistake in the opposite direction. It also closes a genuine hole the recipient reading does not
touch: a demoted or removed owner should not have outstanding invitations that still work, since the
authority under which they were issued is gone.

**Two triggers, two anchors, one cascade.** `R4-06` invalidates, in the same transaction as the
revocation:

| Trigger | Predicate | Anchor |
|---|---|---|
| Recipient | `organization_id = O AND target_identity = <revoked member>` | `FR-020` |
| Issuer | `organization_id = O AND issued_by = <revoked member>` | `KHEPRI-DEC-015` §2 |

Both restricted to unredeemed and unrevoked rows, and both destroying the verifier as they mark
`revoked_at`, per §3's destruction rule. The two predicates overlap only when someone invited
themselves, so this is a union rather than a choice.

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

**Removed from this list, and why.** The first version listed **invitation retention** and
**`FR-020`'s reading** here. Neither is open. Retention is settled by `KHEPRI-DEC-015` §2's
Invitation row — verifier destroyed at the trigger, status and target identity retained only while
replay refusal needs them, record purged after — and §3 now records it along with the sweeper
`R4-03` owes. `FR-020`'s reading is settled by §7's counter-example. Listing a settled question as
open is the failure mode this note fell into once; it is recorded here so a reader of the list knows
the omission is deliberate.

## 9. Slice sequence, unchanged from the roadmap

`R4-02` domain and hashed secret → `R4-03` persistence and migration (single head; `20260817_0017`
is current) → `R4-04` issuance and revocation → `R4-05` redemption → `R4-06` `FR-020` cascade →
`R4-07` the uniform-failure matrix. `R4-04`'s roadmap row already depends on "`R6-01` authorization
matrix draft", which §6.3 now supplies concretely. `R4-03` additionally owes the sweeper §3 records,
and `R4-05` owes the concurrency control §6.2 requires.
