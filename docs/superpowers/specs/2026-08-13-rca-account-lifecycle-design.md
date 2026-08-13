# RCA account lifecycle: disablement, retention horizon, final-owner guard

Design for issue #149. Written 2026-08-13 under standing delegation; the owner was offline, so
every design question was answered here rather than asked, and each answer records its reasoning.

Depends on #151 (PR #153), which established the two-door construction rule this slice builds on.

## Problem

`disable_account` shipped briefly in PR #148 and was reverted in `9507580`. It sits at the
intersection of four requirements that slice never scoped, and three consecutive review rounds
each fixed one finding and surfaced another. The pattern was the signal: this needs its own
design, not a review loop.

## The four questions, answered

### Q1. Where does disablement live?

**A new `LifecycleService` in `khepri/rca/lifecycle.py`, holding both an `AccountStore` and an
`OrganizationStore`.**

FR-013 requires that disabling the final owner-role member of an organization fails closed, and
that the ownership check and the disablement are atomic. `AccountService` has no membership
visibility at all, so it cannot answer the question. Two alternatives were rejected:

- *Give `AccountService` an `OrganizationStore`.* It makes the account service depend on
  organizations for one operation, and leaves `disable_account` sitting beside `authenticate` in
  a class whose other methods need no such dependency.
- *Put it on `OrganizationService`.* Disablement is an account operation that happens to have an
  organization constraint, not the reverse.

A third service that owns exactly the cross-aggregate operations keeps both existing services
single-purpose. It will also be the natural home for #150's revocation, which has the same
shape.

### Q2. Is the tombstone the same row minimized, or a separate table?

**The same row, minimized in place.**

DEC-015 §2b says the post-horizon state is "minimized to an opaque tombstone" holding "an opaque
account identifier and the disablement timestamp — no email address, no credential verifier, no
profile data". Both readings are defensible on that text, but the same-row reading wins on two
concrete grounds:

1. **Referential integrity.** §2b states the tombstone's purpose is "to keep `FR-014` audit
   events referentially meaningful for the remainder of their own twelve-month horizon".
   `rca_memberships` and (in #150) `rca_membership_events` carry foreign keys onto
   `rca_accounts.account_id`. Moving the row to another table breaks those keys at exactly the
   moment they must still resolve.
2. **It cannot drift.** A separate table requires a copy-then-delete that can fail halfway,
   producing either two records or none. Nulling columns in place is one UPDATE.

So the purge is `UPDATE rca_accounts SET email = NULL, credential_* = NULL WHERE ...`, and
`email` must therefore become nullable — which is also what makes the post-horizon state
representable at all, and releases the A-1 uniqueness reservation as §2b requires.

### Q3. What triggers the 24-month purge?

**A sweeper pass, following the `khepri.local.sweeper` precedent — not lazy evaluation on read.**

Lazy evaluation fails the requirement outright. DEC-015 §2b bounds *retention*, not *visibility*:
an account nobody reads is an account whose identity data is never purged, so under lazy
evaluation a horizon would elapse and the data would remain. That is indefinite retention with a
policy comment on top, which §2b exists to refuse.

`khepri.local.sweeper` is the established precedent for "the caller nothing currently calls", and
its docstring states the discipline this slice adopts verbatim: it runs one pass when called, and
**it is not a scheduler** — choosing a cadence is an operational decision, and inventing one here
would model a deployment nobody has authorized.

Concretely: `AccountRetentionSweeper.sweep(now)` purges every account whose `disabled_at` is more
than 24 months in the past and whose identity fields are not already purged, and returns counts
only, echoing no identifier. The `LocalSweeper` gains a call to it, so the local stack exercises
the path.

### Q4. Does the revocation ledger land here?

**No. It is deferred, and this is the one place this slice deliberately leaves a gap.**

DEC-015 §8 makes the ledger's bound derive from **OD-3**, the backup purge horizon — which is
explicitly *unsettled*, recorded as an open owner decision, and stated to be an input to
`KHEPRI-DEC-008` (still `proposed`). A ledger whose retention bound cannot be computed cannot be
built correctly, and inventing a bound would be precisely the unjustified-number move DEC-015
spends its opening section refusing.

What this slice does instead is satisfy §8 item 5's *live* half: a disabled account must not
authenticate, which is FR-008 and is enforced here. The backup-restore half needs a runtime that
does not exist. Recorded as a follow-up issue rather than silently skipped.

## Scope boundary: sessions

FR-008 has two clauses. A disabled account must (a) fail authentication, and (b) have every
pre-existing session cease to authorize, with no dependence on session expiry.

**Sessions do not exist in `khepri.rca` yet.** Clause (a) is fully implementable now and is
implemented. Clause (b) has nothing to attach to.

The critical design consequence: the session slice must derive authorization from **account
state at authorization time**, not from a flag copied into the session at login. A copied flag
is what makes revocation depend on expiry, which FR-008 forbids by name. To make that
unavoidable rather than merely recommended, this slice ships the check the session layer must
call — `LifecycleService.assert_account_active(account_id)` — so the session slice inherits a
chokepoint instead of inventing one.

## The carried risk this slice must fix

`khepri-rca-slice1-carried-risks` records that `resolve_scope` does not refuse a disabled
account. That is inert today because disablement does not exist. **It becomes live the moment
this slice merges**, so it is fixed here, not deferred.

`IsolationService` gains an `AccountStore` and refuses a disabled account before returning a
scope. This is a constructor signature change, and every caller is updated.

## Schema changes

One Alembic revision, following `20260812_0010_rca_identity_spine`:

| Change | Why |
|---|---|
| `rca_accounts.disabled_at` — nullable timestamp | The 24-month horizon must be computed from something; the schema has no such column. NULL means enabled — the state is derived from the column, never duplicated into a boolean that could disagree with it. |
| `rca_accounts.email` — becomes nullable | Otherwise the post-horizon purge state is unrepresentable and the A-1 uniqueness reservation is held forever, contradicting §2b. |

The verifier columns are already nullable, so destruction needs no migration — which is why
slice 1 declared them that way.

**A partial unique index is required on `email`.** Once `email` is nullable, the existing
`UniqueConstraint` no longer expresses A-1 correctly: multiple purged accounts all hold NULL, and
while SQL treats NULLs as distinct (so this happens to work), the intent must be explicit.
A-1 is uniqueness across *live* identities, which is exactly what §2b says.

## Error handling

**FR-013 is a deliberate exception to the content-free refusal rule, and this is the trap.**

FR-004 and FR-034 require refusals to disclose nothing, and every existing error in `errors.py`
is content-free. But FR-013 states the operation "MUST fail closed and MUST state that the final
owner cannot be removed."

That is coherent, not a contradiction: the caller is an authenticated member of that
organization, so they already know it exists and who is in it. There is nothing to leak. Writing
this guard with a content-free refusal would match the surrounding style while violating the
requirement — so `FinalOwnerProtected` carries a specific message, and a test asserts the message
is specific rather than merely that the call fails.

New errors:

- `FinalOwnerProtected(PermissionError)` — message states the final owner cannot be removed.
- `AccountDisabled` is **not** added. A disabled account failing authentication must be
  indistinguishable from any other failure (FR-004), so it raises the existing
  `AuthenticationFailed` with the existing uniform message.

## Testing

Every guard is mutation-tested, and the slice is adversarially reviewed before the PR opens.
Both are required: on #151 mutation testing found an untested guard and review found a *missing*
one, and neither technique could have found the other's.

Specific properties, each with the failure it defends against:

1. **Disabling the final owner fails closed**, and the organization still has its owner
   afterwards. Test both, because a guard that raises *after* writing satisfies the first alone.
2. **The refusal names the cause** (FR-013), not a uniform message.
3. **Disablement destroys the verifier** in the same transaction. Assert the columns are NULL in
   the database, not merely that the returned object says so.
4. **A disabled account fails authentication uniformly** — same exception, same message, and the
   same single scrypt call as every other rejection path. This extends the existing FR-004
   uniform-cost harness rather than adding a second one.
5. **`resolve_scope` refuses a disabled account**, with the existing uniform scope refusal.
6. **The sweeper purges at 24 months and not before.** Parametrize the boundary: one day before
   the horizon must not purge, one day after must.
7. **Purging preserves the tombstone**: `account_id` and `disabled_at` survive; `email` and every
   verifier column are NULL.
8. **A purged account's email can be registered again** (§2b's A-1 release), and a *live*
   account's email still cannot.
9. **Disablement is not reversible by copying**: `dataclasses.replace(account, disabled_at=None)`
   is refused by the #151 door rule. This is the regression test that the two slices compose.

## Judgment calls made without the owner

- **`LifecycleService` as a third service** rather than extending either existing one (Q1).
- **Same-row tombstone** (Q2), on referential-integrity grounds that the alternative reading
  cannot satisfy.
- **Sweeper over lazy evaluation** (Q3), because lazy evaluation does not bound retention.
- **Revocation ledger deferred** (Q4) because OD-3 is unsettled. This is a known, recorded gap.
- **Re-enablement is supported.** DEC-015 §2b justifies the 24-month horizon partly so an account
  "can be re-enabled after a dispute, an erroneous disablement, or a lapsed commercial
  relationship". A horizon justified by re-enablement while offering no way to re-enable would be
  incoherent, so `enable_account` exists. It cannot restore a destroyed verifier — that is gone
  by §5 — so re-enablement requires setting a new credential, and a re-enabled account with no
  verifier fails authentication uniformly until one is set.
- **No `is_disabled` boolean.** State is derived from `disabled_at IS NULL`. Two representations
  of one fact can disagree.
- **`assert_account_active` ships unused by sessions**, so the session slice inherits the
  chokepoint FR-008 requires rather than inventing one.

## Verification

`uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`, the Alembic round-trip test,
mutation testing of every new guard, and an independent adversarial review before the PR opens.
