# R1-02 — The transaction-scoped store contract and its fake semantics

**Task:** `R1-02` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Stated output: "Interface and
invariants". Implements the recommendation settled in `R1-01`.

**Status:** Design note. **No code is authorized by this document.** It defines the interface
`R1-03`'s tests are written against and `R1-04` implements.

**Baseline:** `main` @ `074978a`, 2026-08-13. `R1-01`'s design note is merged at `38bab5a`; the
RCA-001 status matrix is merged at `074978a`.

**Depends on:** `docs/superpowers/specs/2026-08-13-r1-01-transaction-boundary-design.md` §4, which
selected `SELECT … FOR UPDATE` with the guard and write inside one store method.

---

## 1. Why the contract is not a unit of work

`R1-01` rejected threading a session through every store protocol method. This note records the
second, sharper reason that emerged from reading the domain: **the caller has no mutable handle to
pass into a transaction.**

`Account` is a frozen, sealed record (`src/khepri/rca/records.py`). A state change is a new
instance produced through a door — `Account.disabled()` returns a *new* account with the verifier
destroyed and the timestamp set, and `dataclasses.replace` is refused outright. So the shape

```text
with store.unit_of_work() as uow:      # rejected
    account = uow.get_account(id)
    guard(uow)
    account.disabled_at = now          # not expressible: frozen and sealed
```

is not merely undesirable, it is unwritable in this codebase. The transition must be computed by
the domain, then handed to the store as a value.

### The invariant this produces, which is load-bearing

`records.py` states that a door "authorizes the thread, not one call", and warns that "a door that
wraps a long computation, a callback, or anything that yields is a wider grant than it looks". A
database round trip under `FOR UPDATE` blocks, yields, and may wait on another transaction's lock —
precisely the widened grant that warning describes.

The codebase already applies the rule: `Account.create` derives its ~100 ms scrypt verifier
*before* opening its door.

> **Invariant D — no door is open while a lock is held.** The transition is constructed before the
> transaction begins. The store receives an already-built record and never calls `create`,
> `_from_storage`, or `through_door()` while holding a lock.

`_from_storage` inside the reading half of the transaction is the one permitted exception, because
reconstruction is how rows become records at all; it is a single constructor call on values already
fetched, which is the window the module sanctions.

## 2. The contract

One new method on `OrganizationStore`. Provisional name and shape:

```text
apply_owner_reducing_change(
    account_id: str,
    updated: Account,
) -> OwnerReducingOutcome
```

**Why it lives on `OrganizationStore` rather than `AccountStore`.** The lock is taken on membership
rows and the guard is an organization-level question. The account write is the *consequence*. Put
the method where the invariant lives; `SqlOrganizationStore` already holds the `count_owners` query
and the join it depends on.

**Why it takes the already-built `Account` rather than a mutation callback.** §1. A callback
executing inside the transaction would run caller code while a lock is held, which is Invariant D
inverted.

**Why it returns an outcome rather than raising.** The store reports what the database decided;
translating that into `FinalOwnerProtected` or `AccountOperationFailed` stays in `LifecycleService`,
where the existing refusal vocabulary and its FR-013 message already live (`errors.py:8-18`). A
store that raised domain errors would put half the refusal contract in persistence.

Provisional outcome vocabulary — three cases, exhaustive and fail-closed:

| Outcome | Meaning | Service translates to |
|---|---|---|
| `APPLIED` | guard passed on locked rows; the write committed | return the updated account |
| `FINAL_OWNER` | the account is the last effective owner of at least one organization it owns | `FinalOwnerProtected` |
| `NOT_APPLICABLE` | the account row vanished or no longer matches the precondition | `AccountOperationFailed` |

### What the method does, in order

1. `begin()` one transaction.
2. Lock the owner-role membership rows of every organization this account holds an owner membership
   in, via the named statement in §3.
3. Evaluate the effective-owner count **on the locked rows**, per the predicate in §4.
4. If any organization would reach zero, roll back and report `FINAL_OWNER` — nothing is written.
5. Otherwise write `updated` and commit, reporting `APPLIED`.

## 3. The locking statement is a named module-level function

Following `invitation_for_update_statement` (`src/khepri/rra/persistence.py:322-329`), the
`FOR UPDATE` select is a module-level function returning a `Select`, not an inline expression.

> **Invariant A — the lock is assertable without a database.** Because the statement is a named
> function, a test can compile it against the PostgreSQL dialect and assert the emitted SQL contains
> `FOR UPDATE`. This is `R1-01` §5.1's level-1 evidence, and it is the only concurrency evidence
> that runs in CI as CI is currently configured.

This matters more here than it did for RRA: an inline `.with_for_update()` that someone later drops
would silently reintroduce `#155`, and under SQLite no test would notice, because SQLAlchemy emits
no `FOR UPDATE` for that dialect either way.

## 4. Where the effective-owner predicate lives

`R1-01` §2 recorded that the rule is expressed twice on `main` — as `Account.can_authenticate` in
`accounts.py`, and as a replicated `WHERE` clause in `count_owners` (`persistence.py:398-410`). They
agree today by review, not by construction.

**Decision: SQL stays authoritative for the count, and the divergence becomes enforced rather than
reviewed.**

The count must be evaluated on locked rows inside the transaction, which requires SQL. Reading rows
into Python to apply `can_authenticate` would mean reconstructing records under a held lock
(violating Invariant D) and would be slower for no benefit.

> **Invariant B — the two expressions of the effective-owner rule must agree.** A test enumerates
> the account states that matter — enabled with verifier, enabled without verifier, disabled,
> purged tombstone — and asserts for each that `Account.can_authenticate` and the SQL predicate
> return the same answer. If a future change moves one, the test fails rather than the two silently
> drifting.

The four states are not arbitrary: the verifier-less-but-enabled case is the one that already
caused a real defect (`persistence.py:404-409`), and the purged tombstone is the one that survives
because `fk_rca_membership_account` is `RESTRICT`.

> **Invariant C — `can_act` and `can_authenticate` stay distinct.** `can_act` remains the liveness
> predicate for `assert_account_active` and scope resolution; `can_authenticate` remains the
> ownership predicate. Collapsing them reintroduces a fixed defect (`accounts.py:82-96`).

## 5. Fake semantics

`R1-01` §5.2 found that `MemoryOrganizationStore` can model weaker semantics than SQL and currently
does: its `accounts` argument defaults to `None`, and owner counting then treats every membership
holder as live — the exact behavior the SQL join exists to defeat. 14 call sites construct it bare.

> **Invariant E — the fake cannot be constructed in a state that models weaker semantics than
> SQL.** `MemoryOrganizationStore.__init__` takes the account store as a **required** argument. The
> `None` default and the permissive branch in `_can_act` are removed.

This is a test-only change, mechanical, and in scope for R1 because R1 is the slice that makes the
fake's owner-counting semantics load-bearing under concurrency. The roadmap's design requirement —
"preserve testability without allowing memory fakes to model weaker semantics than SQL" — is
otherwise held by convention alone.

Verified at this baseline: 14 call sites construct the shared fake bare, and 3 pass the account
store.

### A second fake shadows the shared one, and it is the sharper instance of the same problem

`tests/test_rca001_organizations.py:21` defines its **own class also named
`MemoryOrganizationStore`** — not a subclass, a shadowing duplicate with a different constructor
(`fail_on_create`) and, critically, **no `count_owners` method at all**. It is not a variant of the
shared fake; it is a second implementation of the same protocol that satisfies a narrower subset.

This is the failure mode `rca_fakes.py`'s own module docstring records having already happened once:
the fakes were extracted precisely because "each of `test_rca001_accounts`, `test_rca001_isolation`,
and `test_rca001_organizations` had grown its own partial copy, and a protocol method added in one
place had to be remembered in three." One copy survived the extraction.

It is harmless today because that module tests only organization creation. It stops being harmless
the moment `apply_owner_reducing_change` joins the protocol: a partial fake either silently lacks
the method, or someone adds a second implementation of the invariant to it. `R1-04` should fold this
class into the shared fake — a small change, and the alternative is maintaining two answers to
"what does an organization store do when ownership would reach zero".

### What the fake models, and what it must not pretend to model

The fake implements `apply_owner_reducing_change` by performing guard-and-write with no interleaving
— which is what a single-threaded in-memory dictionary does anyway.

> **Invariant F — the fake proves the sequential contract only.** No test may claim concurrency
> evidence from the memory fake. `R1-01` §5.1 records why: the RCA suite runs in-memory SQLite with
> `StaticPool`, one shared connection, and SQLite has no `FOR UPDATE`. Concurrency evidence requires
> two real PostgreSQL connections.

The fake and the SQL store must agree on **outcomes** for every sequential case, which is testable
today and is the parity `rca_fakes.py`'s own docstring already asks for: "a test that passes against
a fake and fails against `SqlAccountStore` is telling you about the SQL, not about the fake."

## 6. Reuse by R2, which is the point

`R2-06` applies the same invariant to membership revocation and owner-to-member demotion. The method
is therefore named for the *class* of operation, not for disablement.

Both R2 operations reduce owner count by changing membership rows rather than account rows, so the
contract will need a sibling that writes a membership transition instead of an account one. **That
sibling is R2's to define, not R1's** — R1 must only avoid foreclosing it. Two things keep the door
open: the outcome vocabulary is about ownership, not about accounts; and the locking statement in §3
takes an account identifier and returns rows, so it is reusable unchanged.

`R1-04` should implement exactly the account case. Speculatively generalizing to a membership case
with no test exercising it would be scope creep in the slice whose stop condition names it.

## 7. Scope

**In scope for R1-04:**

- the one store method, on `SqlOrganizationStore` and the protocol in `stores.py`;
- the named `FOR UPDATE` statement function;
- `MemoryOrganizationStore` conforming, with the account store required;
- `LifecycleService.disable_account` rewritten to call it and translate the outcome;
- updating the 14 bare fake call sites.

**Out of scope:**

- membership revocation and demotion behavior (R2);
- any schema change — this contract needs none; migration head stays `20260813_0012`;
- any change to `AccountStore`'s protocol beyond what the service needs to stop doing;
- `RRA` stores.

## 8. Invariant summary

| | Invariant |
|---|---|
| A | The lock is assertable without a database, via a named module-level statement |
| B | `Account.can_authenticate` and the SQL predicate agree, enforced by test |
| C | `can_act` and `can_authenticate` stay distinct |
| D | No door is open while a lock is held |
| E | The fake cannot be constructed in a state modelling weaker semantics than SQL |
| F | The fake proves the sequential contract only; concurrency needs PostgreSQL |

## 9. Carried forward from R1-01 §8, still unresolved

CI defines no PostgreSQL service, so Invariant F's concurrency evidence cannot run there. The
recommendation stands: add a `postgres` service to the `pytest` job as its own one-file
infrastructure PR, before `R1-03`. Until that is decided, `R1-03` can deliver levels 1 and 2 only,
and the slice must not report the contract as proven.
