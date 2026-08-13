# R2-01 — Membership lifecycle, role transitions, and expiring audit events

**Task:** `R2-01` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Stated output: "Design and
plan". Addresses issue `#150`.

**Status:** Design note. **No code is authorized by this document.** `R2-02` onward each need the
owner's approval of that task ID.

**Baseline:** `main` @ `ab1f2e3`, 2026-08-14. `R1` is complete and `#155` is closed at `c8c6edb`.
Migration head is `20260813_0012`, single head. `uv run pytest`: 1799 passed, 15 skipped.

**Governed by:** `governance/specifications/RCA-001.md` FR-012, FR-013, FR-014, FR-015, FR-020,
FR-030, FR-040; `governance/decisions/KHEPRI-DEC-015-commercial-identity-retention.md` §2a, §4, §5.

---

## 1. What is missing, precisely

`STATUS.md` records the structural absence: `stores.py`'s `OrganizationStore` exposes exactly one
write, `create_organization`. There is no add-member, remove-member, or change-role operation
anywhere in `src/khepri/rca/`.

Five requirements turn on that, and one on the row's shape:

| FR | Gap |
|---|---|
| FR-012 | Revocation does not exist as an operation |
| FR-013 | Its *remove* and *downgrade* clauses have no operation to guard — only disable exists |
| FR-014 | `Membership` is a current-state row and cannot represent a transition, so "what the prior and resulting roles were" is unsatisfiable in this shape |
| FR-015 | No `member` constant; `role` is an unconstrained `String` with no CHECK, so a third role is writable |
| FR-020 | Doubly blocked — no revocation and no invitations |

FR-020's invitation half belongs to `R4`. Everything else is `R2`.

## 2. The event model

`organizations.py:44-49` already names the answer, and `KHEPRI-DEC-015` §82 fixes its content:

> Content-free record: **opaque actor ID, opaque membership ID, prior role, next role, timestamp**.
> Twelve months from the event.

So `rca_membership_events` carries exactly that and nothing else. Provisional columns:

| Column | Why |
|---|---|
| `event_id` | opaque primary key |
| `organization_id`, `account_id` | together the opaque membership identity — the membership has no surrogate key today, and inventing one is a larger change than this slice needs |
| `actor_account_id` | who made the change (FR-014) |
| `prior_role` | nullable: a *created* membership has no prior role |
| `next_role` | nullable: a *revoked* membership has no next role |
| `occurred_at` | the horizon is computed from this |

**Nullability carries the event kind.** Creation is `prior_role IS NULL`; revocation is
`next_role IS NULL`; a role change has both. Adding a separate `event_type` column would let the
two disagree — a row typed `revoked` with a non-null `next_role` is expressible, and then two
sources say different things about one event, which is the drift Constitution I forbids. If a
future event kind cannot be distinguished this way, that is the moment to add the column, not
before.

**No foreign key to `rca_accounts`.** DEC-015 §82 says content-free, and §on the tombstone says the
account row survives 24 months precisely "to keep `FR-014` audit events referentially meaningful
for the remainder of their own twelve-month horizon". A `RESTRICT` FK would additionally make the
account purge *fail* while any event referenced it, inverting the horizon relationship the decision
sets up. The identifiers are opaque strings; that is what content-free means here.

### 2.1 The ordering invariant between two sweepers

`KHEPRI-DEC-015` justifies the 24-month account horizon partly as being "long enough to outlast the
twelve-month audit horizon so that audit evidence never outlives the subject it refers to."

That is a relationship between two independently-scheduled sweepers, and nothing currently enforces
it. `R2-08` should add a test asserting `RETENTION_MONTHS > MEMBERSHIP_EVENT_RETENTION_MONTHS`, so
that shortening the account horizon below the audit horizon fails rather than silently producing
events pointing at rows that no longer exist.

### 2.2 Migrating the existing attribution

`rca_memberships` currently carries `changed_by` and `changed_at`. `R2-03` removes them, and the
question is what happens to the data.

**Backfill one creation event per existing membership row, then drop the columns.** The alternative
— dropping them outright — destroys the only attribution that exists for memberships created before
this slice. The backfill is exact: `changed_by` becomes `actor_account_id`, `changed_at` becomes
`occurred_at`, `prior_role` is NULL, `next_role` is the row's current `role`.

One caveat worth stating in the migration itself: a backfilled event is a *reconstruction*, not a
record of an observed event. It says "this membership existed at this role, attributed to this
account, at this time" — which is true — but it did not come from an operation that emitted it.

## 3. Role changes are operations, not field assignments

`records.py` already forbids the alternative: `dataclasses.replace` is refused, and the module
docstring says so directly — "A role change and a verifier destruction are **operations**, not
field assignments, and #150 and #149 respectively must write them as such."

So `Membership` gains door-built transitions in the shape `Account.disabled()` already
establishes — a method returning a *new* record — and the store writes the new row and the event in
one transaction.

**FR-015 needs a `MEMBER_ROLE` constant and a check.** Two roles, exactly. The `role` column should
gain a CHECK constraint restricting it to the two values: the domain can refuse a third role, but
the column currently admits one, and a store caller reaching the row directly is exactly the seam
`#151` was opened to close.

## 4. Reusing R1's transaction seam

`R2-06` applies the final-owner invariant to revoke and demote. It must route through
`apply_owner_reducing_change` rather than adding a second guard — the roadmap's stop condition names
"two independent final-owner guards" explicitly.

**But R1 implemented only the account case, deliberately.** Its method writes an `Account`. Revoke
and demote reduce owner count by changing *membership* rows, so the contract needs a sibling. From
`R1-02` §6, two things were kept reusable: the outcome vocabulary is about ownership rather than
accounts, and `owner_memberships_for_update` takes an account identifier and returns rows.

The sibling should be the same shape — lock, count on locked rows, write or refuse — differing only
in what it writes. The natural generalization is a method taking the membership transition and the
event to emit, both already built, and applying them together.

**The event and the state change must be in one transaction.** An event written outside it can
describe a change that rolled back; a change written without its event is an unattributed role
change, which is FR-014 unsatisfied. Neither is acceptable, and the transaction already exists.

## 5. What R1 proved that R2 must not relearn

**A two-thread concurrency test is not a reliable proof of this defect class.** R1's two-owner test
passed against the *broken* code; only three contenders exposed the race. `R2-06`'s concurrency
proof therefore needs at least three contenders — and it needs the mixed case R1 did not have:
**one caller revoking while another demotes**, since those are two different write paths reducing
the same count.

**The fake must keep matching.** `MemoryOrganizationStore` now requires its account store and the
shadowing duplicate is gone. Any new store method needs the fake to implement the same outcome
vocabulary, or every refusal test that uses it becomes meaningless.

## 6. Slice order and the migration constraint

| Task | Output | Note |
|---|---|---|
| `R2-02` | `rca_membership_events` schema, migration, backfill | **The only migration that may merge in this window.** Head is `20260813_0012`; `R3-03` must wait or re-point |
| `R2-03` | drop `changed_by`/`changed_at` from `rca_memberships` | after the backfill has merged, not with it |
| `R2-04` | `member` role constant, CHECK constraint, role-change operation | |
| `R2-05` | revocation, with non-interference tests (FR-012) | |
| `R2-06` | the shared final-owner invariant applied to revoke and demote | depends on the R1 sibling method |
| `R2-07` | emit events for create, role change, revoke | |
| `R2-08` | the 12-month sweeper, plus the ordering invariant test from §2.1 | follow `AccountRetentionSweeper`: one pass when called, no scheduler |
| `R2-09` | mutation and adversarial tests | |
| `R2-10` | close `#150` | |

**`R2-02` and `R2-03` should not be one PR.** A backfill and a column drop in one migration cannot
be verified independently: if the backfill is wrong, the source data is already gone. Landing them
separately means the drop runs against a backfill that has been reviewed on `main`.

## 7. Non-goals

- Invitations (`R4`), including FR-020's invitation half.
- Organization disablement — FR-015 names it as an owner capability, but no operation exists and
  `RCA-001` does not require one in this slice.
- Any change to the `R1` account path beyond adding the sibling method.
- A surrogate membership key. `(organization_id, account_id)` is the identity today; changing that
  is a larger migration than `#150` needs.

## 8. Open question for the owner

**Does organization creation emit a membership-created event?** The roadmap's `R2` design questions
list this explicitly and it is genuinely undecided.

For: FR-014 says "every change to a membership", and the initial owner membership is a change. An
audit trail with a gap at the first event is harder to reason about than one without.

Against: creation is already atomic with the organization (`R1`'s `create_organization` writes
three rows), and the event adds a fourth write to a path that currently cannot partially fail.

**Recommendation: yes, emit it.** The backfill in §2.2 has to synthesize exactly this event for
existing rows anyway, so *not* emitting it going forward would mean historical memberships have a
creation event and new ones do not — the inconsistency is worse than the extra write.
