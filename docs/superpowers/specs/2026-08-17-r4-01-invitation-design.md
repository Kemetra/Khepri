# R4-01 — invitation state, expiry, revocation, intended role, and authenticated redemption

**Task:** `R4-01` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Output is a design, not code.

**Baseline:** `main` @ `086b960`, 2026-08-17 (`R7-02` and `R7-04` merged; `R1-05` in review, so `R1`
is not yet closed). `uv run khepri-gov validate` passes; `uv run pytest` reports 2197 passed, 47
skipped — measured at this commit rather than carried over from a branch. Migration head
`20260817_0017`, single head.

**Depends on:** `R2`'s role model and event table (merged), and `R3`'s actor resolution (merged
through `R3-10`). Both met. `R6-01`'s matrix is merged, which matters because §6 below owes it two
rows.

**What this note settles:** the invitation record's shape, its state model, what "fail closed"
means concretely, who may issue and revoke, and what redemption does. **What it does not settle** is
in §8.

---

## 1. What exists today, stated first

**Nothing.** `FR-016` … `FR-020` are the largest untouched block in `RCA-001`:
`test_rca001_migration.py` enumerates exactly five `rca_` tables — accounts, organizations,
memberships, isolation_scopes, membership_events — and there is no `Invitation` type, no
`rca_invitations` table, and no store method. `STATUS.md` records all five requirements as
`Not implemented`.

**One thing that does exist, and must not be reused.** `khepri.rra.sessions.Invitation` is a
*beta* invitation: it carries `invitation_id`, `secret_salt`, `secret_digest`, `expires_at`,
`redeemed_at` and names no organization and no role, because a beta participant redeems into a
throwaway scope rather than into a tenant. `KHEPRI-DEC-019` §2 (re-enacted by `KHEPRI-DEC-020` §1)
forbids changing `redeem`, its signature, or the invitation lifecycle, and `FR-039` forbids `RCA`
depending on an `rra_` table. So `RCA` gets its own record.

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

Scenarios 6, 7, 8, 9 and 11 in `RCA-001`'s Verification section are the tests these owe.

## 3. The record

```
Invitation
  invitation_id     str        opaque, prefixed `inv_`
  organization_id   str        exactly one, FK to rca_organizations
  intended_role     str        exactly one of ROLES, CHECK-constrained
  secret_salt       bytes      per-invitation
  secret_digest     bytes      scrypt, never the secret itself
  expires_at        datetime   explicit, no default lifetime baked into the record
  issued_by         str        the actor account, for FR-014-style attribution
  issued_at         datetime
  redeemed_at       datetime | None
  revoked_at        datetime | None
```

**Sealed, following `Membership` and `MembershipEvent`.** `records.py`'s door pattern applies: a
state change is a new instance, never a mutation, so `redeemed_at` is set by constructing rather than
by assignment.

**No email column, deliberately, and this is the note's least obvious decision.** `FR-019` requires
an invitation be issuable to someone with no account, which invites storing the invitee's address so
the system knows whom it is for. Three reasons not to:

1. `FR-040` and `KHEPRI-DEC-015` §82 make invitation *records* content-free like every other
   `rca_` row. An email address is personal data with its own retention obligation, and the
   invitation table has no sweeper.
2. The secret **is** the addressing. Whoever holds it redeems it; that is what "issuable to a person
   with no account" means operationally. An email column would be a second, weaker authority
   describing the same fact — the drift the constitution forbids.
3. Delivery is out of scope for `R4` and unresolved for `R5` (`R5-01` owes a delivery abstraction).
   Storing an address for a delivery mechanism that does not exist is speculative schema.

**Consequence, recorded rather than hidden:** the system cannot answer "which invitations did I send
to alice@example.com?" A product that needs that needs a decision about storing invitee identity,
which is the owner's, not this note's. Flagged for `R8-05`'s team-management surface, which is the
first place a human will want it.

**Constraints on the table:**

- `CHECK intended_role IN ('owner','member')` — the same shape as `ck_rca_membership_role`
  (`20260814_0015`), for the same reason: the domain refusing a third role is not sufficient when a
  store caller can reach the row directly.
- `CHECK (redeemed_at IS NULL OR revoked_at IS NULL)` — an invitation cannot be both. See §5's state
  model.
- `CHECK expires_at > issued_at` — following `ck_session_expiry_after_creation`.
- No `UNIQUE (organization_id, ...)` of any kind. One organization may hold many open invitations,
  and encoding a cardinality nobody requires is exactly the defect `R7-02` spent a slice unwinding
  (`KHEPRI-DEC-020`).

## 4. Issuance

`InvitationService.issue(organization_id, intended_role, *, actor_account_id, expires_at, now)`
returns a **single-use token** the caller must transmit and cannot recover afterwards.

- **Token format `kci1.<invitation_id>.<secret>`**, mirroring RRA's `kiv1.` with a distinct prefix
  so a beta token and a commercial token can never be confused at a boundary that accepts both.
  `R3-01` §2.1 established that reasoning for session keys.
- **`scrypt` at RRA's parameters** (`n=2**14, r=8, p=1, dklen=32`, 16-byte salt). Matching rather
  than choosing new parameters: two hashing schemes in one codebase means one of them is unreviewed.
- **The secret is returned once and never stored.** Only `secret_digest` persists, which is
  `FR-016`'s "persisted only as a strong salted hash".
- **`expires_at` is a parameter, not a constant.** `FR-016` requires an explicit expiry; it does not
  fix a lifetime, and baking one in would put a product decision in the domain.

**Authorization lives outside this service.** Per `R6-01` §5's critical rule and `R6-04`'s placement
of the check in the gate rather than in the verbs, `issue` takes `actor_account_id` for
*attribution* and performs no role check of its own. §6 below adds the matrix rows that make the
gate the authorized route.

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

**`FR-017`'s hard part is the non-disclosure, not the at-most-once.** Five distinct causes —
malformed token, unknown `invitation_id`, wrong secret, expired, revoked, already redeemed — must
produce **one** externally identical failure. That means:

- One exception type carrying one message constant, following `SCOPE_FAILURE` and
  `_INVITATION_FAILURE`.
- **The digest comparison runs even when the invitation was not found**, against a module-level
  dummy salt, exactly as `credentials.py:31`'s `DUMMY_SALT` does for `FR-004` — its own comment says
  it exists "to pay the same scrypt cost for a missing account as for a wrong-credential
  rejection, so account existence is not revealed through timing". Without it, "unknown
  invitation" returns fast and "wrong secret" pays for a scrypt, and the timing difference is the
  disclosure the requirement forbids. This is the one place a `R4` implementation is most likely to
  be accidentally non-compliant, because the fast path looks like an optimization.
- `hmac.compare_digest` for the comparison itself, as RRA already does.

**A test asserting one message across five causes is not sufficient** — it passes on an
implementation that returns early. Scenario 8 and 9's tests must also assert the dummy-hash path is
taken, the way `test_rca001_accounts.py` does for authentication.

## 6. Redemption

`redeem(token, *, account_id, now)` — and the `account_id` parameter is the whole of `FR-019`'s
second clause.

1. Parse and verify per §5. Any failure → the single uniform refusal.
2. **The account must exist and be able to act.** `assert_account_active`, the same chokepoint
   `actor_resolution.py` uses at step 3. `FR-019` says acceptance "MUST require that an
   authenticated account exists at the moment of acceptance" — *at the moment*, so a token issued
   before the account existed is fine and a disabled account at redemption time is not.
3. **Create exactly one membership** at `intended_role` in `organization_id`, and mark the
   invitation redeemed, **in one transaction**. `FR-018`'s "exactly one" is a cardinality claim, and
   a membership committed without the redemption mark is a token that redeems twice.
4. **Emit `MembershipEvent.created`** with `actor_account_id` = the redeeming account. Attribution
   travels with the write for the reason `create_organization` records: an event committed
   separately can describe a change that rolled back.

**Already a member?** Refuse with the same uniform failure, and do not create a second membership —
the composite primary key `(organization_id, account_id)` makes a duplicate unexpressible, so this
is enforced structurally and the refusal is about not consuming the token silently.

**`MembershipEvent` needs no new kind, and that is worth stating.** Its docstring says the kind is
carried by nullability — creation has no prior role, revocation no next role — and warns that "if a
future kind cannot be distinguished this way, that is when to add the column". An
invitation-redemption *is* a membership creation: `prior_role IS NULL`, `next_role = intended_role`.
It is distinguishable from organization-creation only by the actor differing from the subject, which
the existing columns already carry. **So `R4` adds no column**, and the nullability design holds
against its first real test.

### 6.1 The two matrix rows `R4` owes `R6-01` §3.1

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

**The reading that makes this implementable.** §3 stores no invitee identity, so "that member's
invitations" cannot be resolved by email. It is resolvable by `account_id` only for invitations
already tied to an account — and an unredeemed invitation is tied to none. Two candidate readings:

1. **Narrow:** revocation invalidates unredeemed invitations whose `issued_by` is the revoked
   member. Implementable today, and it closes the real hole — an owner who is demoted or removed
   should not have outstanding invitations that still work.
2. **Broad:** revocation invalidates every unredeemed invitation naming the revoked person.
   Requires storing invitee identity, which §3 declines.

**This note takes reading 1** and records why: `FR-020` sits in the invitations block immediately
after `FR-019`'s "issuable to a person who has no account yet", so the requirement's own context is
an invitation not yet attached to an account. Under reading 2 the requirement would be unsatisfiable
without an email column that `FR-040` argues against — and a requirement is not usually written to
demand a field the same specification's privacy clauses resist.

**Flagged as the one place `R4` may be reading `FR-020` more narrowly than intended.** It is a
requirement-interpretation question, so if the owner reads it the other way, §3's no-email decision
is what changes, and that is a schema decision worth making before `R4-03` rather than after.
`R4-06` is the slice that implements whichever reading stands.

## 8. What this note does not settle

- **Delivery.** No email, no transport. `R5-01` owes a delivery abstraction for recovery, and
  invitations should reuse whatever that decides rather than inventing a parallel one.
- **HTTP surface.** `R8-05`'s team-management screens and any endpoint are out of scope, exactly as
  `R6-01` left `R7-05`'s endpoint alone.
- **Invitation retention.** Every other `rca_` table has a horizon under `KHEPRI-DEC-015`;
  invitations have none, because none is decided. A redeemed invitation's row is audit-adjacent and
  arguably belongs on `MembershipEvent`'s twelve-month horizon. **This needs an owner decision or an
  explicit "no horizon" before `R4-03` writes the table**, since adding a sweeper later means a
  second migration.
- **Whether an invitation can be re-sent.** Re-issuing is just `issue` again, which is why no
  `resend` appears above — but whether the old token should then be revoked is a product decision.
- **`FR-020`'s reading**, per §7.

## 9. Slice sequence, unchanged from the roadmap

`R4-02` domain and hashed secret → `R4-03` persistence and migration (single head; `20260817_0017`
is current) → `R4-04` issuance and revocation → `R4-05` redemption → `R4-06` `FR-020` cascade →
`R4-07` the uniform-failure matrix. `R4-04`'s roadmap row already depends on "`R6-01` authorization
matrix draft", which §6.1 now supplies concretely.
