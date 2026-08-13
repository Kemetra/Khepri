# R1-01 — Transaction boundary for the FR-013 final-owner guard

**Task:** `R1-01` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Closes the design question
behind issue `#155`.

**Status:** Design note. **No code, no migration, no test is authorized by this document.**
`R1-01`'s stated output is "Approved design note; no code", and this is that note.

**Baseline:** `main` @ `ebfbe77`, verified before writing. `uv run khepri-gov validate` passes;
`uv run pytest` reports 1794 passed, 10 skipped. Migration head is `20260813_0012` (single head).

**Author:** Claude Code, as planner under roadmap §2. Ahmed Shaaban is the approval authority; this
note is a proposal until merged.

---

## 1. The defect, stated exactly

`LifecycleService.disable_account` (`src/khepri/rca/lifecycle.py:91-106`) performs three
independent database round trips:

| Step | Call | Session |
|---|---|---|
| 1 | `self._accounts.get_account(account_id)` | its own |
| 2 | `self._organizations.memberships_for_account` + `count_owners` | its own (one per organization) |
| 3 | `self._accounts.save_account(disabled)` | its own |

Two concurrent disablements of a two-owner organization interleave as:

```
T1: read A            T2: read B
T1: count_owners(excluding=A) -> 1   (sees B, still enabled)
T2: count_owners(excluding=B) -> 1   (sees A, still enabled)
T1: write A disabled
T2: write B disabled
                      -> organization now has zero effective owners
```

Both guards passed truthfully. Neither read was stale at the moment it was taken. The organization
still ends in the state `FR-013` forbids. This is a lost-update race on a *derived aggregate*, and
no amount of care inside a single store method fixes it.

**The service is not at fault.** `src/khepri/rca/stores.py` defines both store protocols with no
session parameter on any method, and each `Sql*Store` method opens `with self._factory()`
internally. The seam was deliberately built to hide sessions from services. A service composed of
two such stores therefore *cannot* express one transaction spanning both. `#155` is a property of
the seam, not of `disable_account`.

The current docstring at `lifecycle.py:63-85` records this honestly and states the remaining risk:
"a single-process local stack with no concurrent callers cannot hit it. It must be closed before
any deployment serves concurrent requests." The roadmap turns that into a hard gate — OPS1's
deployment stop gate forbids serving concurrent external users before R1 merges.

## 2. What the guard must keep, and why it is easy to break

`FR-013` asks whether an organization retains an owner who can **act**. Three predicates exist on
`main` and they are deliberately not the same:

| Predicate | Definition | Location |
|---|---|---|
| `can_act` | enabled and not purged | `accounts.py` |
| `can_authenticate` | `can_act` **and** has a verifier | `accounts.py` |
| the `count_owners` SQL | `disabled_at IS NULL` **and** `email IS NOT NULL` **and** `credential_digest IS NOT NULL` | `persistence.py:392-412` |

The SQL predicate is `can_authenticate`, expressed in SQL. That is correct and load-bearing:
`KHEPRI-DEC-015` §5 leaves the verifier destroyed through re-enablement, so an enabled, unpurged
owner may still be unable to log in. `persistence.py:404-409` records the verified failure —
disable A, re-enable A, disable B left an organization whose only owner could not authenticate.

**R1 must not collapse these into one predicate.** The roadmap says so explicitly and this note
confirms it against the code: swapping the owner count onto `can_act` is a regression that
reintroduces a fixed defect. `can_act` stays the liveness predicate for `assert_account_active`
and scope resolution; `can_authenticate` stays the ownership predicate.

### The divergence R1-01 was asked to resolve

The effective-owner rule is expressed **twice**: once as Python properties in `accounts.py`, once
as a replicated SQL `WHERE` clause in `count_owners`. They agree today by review, not by
construction. Whichever mechanism R1 picks must state where this rule lives afterwards.

## 3. Three candidate mechanisms

### Option A — `SELECT … FOR UPDATE` on the owner rows, guard and write in one store method

Move the whole read-guard-write into a single `OrganizationStore` (or a new joint store) method
that opens one `factory.begin()`, locks the relevant membership rows with `with_for_update()`,
evaluates the count on the locked rows, and writes the account within the same transaction.

**There is already a working precedent for this exact shape in the repository.**
`SqlSessionStore.redeem_invitation` (`src/khepri/rra/persistence.py:361-375`) opens one
`factory.begin()`, selects the row via a module-level `invitation_for_update_statement`
(`:322-329`) that applies `.with_for_update()`, evaluates the redemption guard on the locked row,
and writes inside the same transaction. It solves the identical class of problem — guard and write
must not be separable — and it has been on `main` since the RRA sessions slice.

That precedent also shows how to get **test evidence without a live PostgreSQL**: because the
locking statement is a named module-level function, a test can compile it and assert the emitted
SQL contains `FOR UPDATE`, independently of the dialect the suite runs on.

| | |
|---|---|
| Guard and write atomic | Yes — one transaction |
| Serializes competitors | Yes — row locks on the owner memberships |
| Unrelated organizations independent | Yes — locks are per-row, scoped by `organization_id` |
| Predicate location afterwards | SQL, next to the lock. Resolves the divergence by making SQL authoritative |
| Fake parity | Hard. See §5 — this is the real cost |
| Seam change | Moderate: one new store method; `stores.py` protocols gain it |

**The gap this option must close, and it is not small.** `redeem_invitation` locks *one row by
primary key*. `FR-013` must lock *a set* — the owner rows of every organization the account owns —
and a `FOR UPDATE` over a set does not prevent another transaction **inserting** a new owner
membership into that set (no predicate locking under PostgreSQL's default `READ COMMITTED`). For
disablement that is benign: a concurrently inserted owner only makes the organization *safer*.
For R2's revoke and demote it is also benign for the same reason. **The dangerous direction is
removal, and removal is what the lock covers.** This asymmetry should be stated in the
implementation's docstring, because it is the kind of reasoning that silently stops holding when
someone later adds an operation that removes an owner by a path that does not take the lock.

### Option B — a shared session / unit-of-work threaded through the store protocols

Add an optional `session` parameter (or a `UnitOfWork` context object) to every store protocol
method, so a service can open one transaction and pass it down.

| | |
|---|---|
| Guard and write atomic | Yes |
| Serializes competitors | **No, not by itself** — still needs `FOR UPDATE` or `SERIALIZABLE` |
| Seam change | Large: every method of both protocols, both SQL stores, both fakes, every call site |
| Predicate location afterwards | Ambiguous — may drift back into Python, worsening §2's divergence |

**Rejected.** It is the largest change and it does not actually solve the race on its own — a
shared transaction under `READ COMMITTED` still lets both transactions read one, both write, and
both commit. It buys atomicity but not serialization, so it would need Option A's locking anyway.
It also violates the roadmap's own stop condition about broad changes across unrelated stores, and
it puts the effective-owner predicate back where it can drift.

### Option C — a database-enforced invariant (constraint or trigger)

Express "every organization has ≥1 effective owner" as a schema-level guarantee.

**Rejected, and worth recording why so it is not re-proposed.** The invariant is not expressible
as a `CHECK`: it spans `rca_memberships` **joined to** `rca_accounts`, and PostgreSQL `CHECK`
constraints cannot reference other tables. The remaining routes are a trigger or a materialized
owner-count column with a `CHECK (owner_count > 0)`. Both put governed `FR-013` logic in a place no
test in this repository currently reaches, split the rule across Python and DDL (worsening §2), and
neither survives the SQLite test fixture at all. A trigger also fires per-statement, so the refusal
would surface as an `IntegrityError` that the service must translate back into
`FinalOwnerProtected` — reconstructing the guard it was meant to replace.

## 4. Recommendation

**Option A**, with these boundaries:

1. **One new method on the organization store** that performs guard-and-write atomically — do not
   thread sessions through the whole seam. Provisional shape: a method that takes the account
   identifier and the mutation to apply, locks the owner rows for every organization the account
   owns, evaluates the remaining-owner count, and either writes or refuses.
2. **The locking select is a named module-level statement function**, following
   `invitation_for_update_statement`, so its SQL is assertable without PostgreSQL.
3. **The effective-owner predicate lives in SQL**, next to the lock. `accounts.py`'s
   `can_authenticate` remains the domain expression of the same rule; the implementation must add
   a test that fails if the two disagree, so the divergence in §2 is enforced rather than
   reviewed.
4. **Reuse for R2.** The same method must serve revoke and owner-to-member demotion, which is
   `R2-06`'s dependency on R1. Design it as "apply this owner-reducing change atomically", not as
   "disable an account".

`R1-05` (prove non-owner-reducing operations acquire no unnecessary locks) is satisfied naturally:
`enable_account`, `assert_account_active`, and the retention sweeper never enter this path.

## 5. The two risks this design must not hand-wave

### 5.1 SQLite cannot prove a PostgreSQL concurrency contract

The RCA suite runs on **in-memory SQLite with `StaticPool`** (`tests/rca_lifecycle_support.py:26-47`).
`StaticPool` means every session shares **one connection**, so two genuinely concurrent
transactions cannot exist in the fixture. SQLite also has no `SELECT … FOR UPDATE` — SQLAlchemy
silently omits it.

The roadmap names "a SQLite-only proof for a PostgreSQL concurrency contract" as a **stop
condition**. Therefore:

> **`R1-03` as currently written is not executable against the existing fixture.** A real
> concurrency test needs a PostgreSQL engine and two independent connections. This is a
> prerequisite the roadmap does not list, and it should be added to R1 as its own task before
> `R1-03`.

Three-part evidence strategy, in increasing strength:

| Level | Evidence | Runs where |
|---|---|---|
| 1 | Compiled-SQL assertion that the statement carries `FOR UPDATE` | existing suite, any dialect |
| 2 | Guard-and-write atomicity via an injected fault between guard and commit | existing suite |
| 3 | Two-connection concurrent disablement leaving ≥1 owner | PostgreSQL only, skipped otherwise |

Level 3 is the only one that actually proves the contract. It must exist and it must not be
silently skipped in CI — a skipped concurrency test reads as a passing one.

### 5.2 The memory fakes can model weaker semantics than SQL — and one already does

`MemoryOrganizationStore.__init__` (`tests/rca_fakes.py`) takes `accounts: MemoryAccountStore |
None = None`, and `_can_act` returns `True` unconditionally when it is unset. Constructed bare, the
fake reports **every membership holder as a live owner** — precisely the behavior the SQL join was
added to defeat. 14 call sites currently construct it bare.

Today those call sites are tests of accounts that own nothing, so the default is harmless and the
docstring says so. But the safety is held by **convention, not by the type**: an `R2` test that
revokes a membership and forgets to wire the account store would pass against the fake and fail
against SQL. The roadmap's design requirement — "preserve testability without allowing memory fakes
to model weaker semantics than SQL" — is not currently enforced by anything.

**Recommendation:** R1 should make the account store a required constructor argument of
`MemoryOrganizationStore` and update the bare call sites. That is a test-only change, it is
mechanical, and it converts a convention into a compile-time obligation. It is in scope for R1
because R1 is the slice that makes the fake's owner-counting semantics load-bearing under
concurrency.

## 6. Scope boundaries for the implementation slices

**In scope for R1-02 … R1-05:**

- one atomic guard-and-write path for account disablement;
- the named locking statement and its compiled-SQL test;
- a PostgreSQL-backed concurrency fixture and the two-connection test;
- making `MemoryOrganizationStore`'s account store required;
- a test asserting the SQL predicate and `can_authenticate` agree.

**Explicitly out of scope:**

- membership revocation and demotion behavior (that is `R2`; R1 only provides the seam they reuse);
- any change to `RRA` stores;
- any new migration — this design needs **no schema change**, and the migration head stays
  `20260813_0012`;
- collapsing `can_act` and `can_authenticate`;
- threading sessions through the full store protocols.

## 7. Stop conditions carried forward

Return to design if implementation requires broad changes across unrelated RRA stores; two
independent final-owner guards; a check committed separately from its write; a SQLite-only proof of
the concurrency contract; or weakening the exact two-role model.

## 8. The one decision this note cannot make

**CI has no PostgreSQL service, and this is verified rather than assumed.**
`.github/workflows/governance.yml` defines four jobs — `validate`, `ruff`, `pytest`, `benchmark`.
The `pytest` job runs `uv run pytest` on a bare `ubuntu-latest` runner with **no `services:` block
anywhere in the file**, and `image.yml` is the container build. Nothing in CI can reach a
PostgreSQL instance today.

Combined with §5.1, that yields a concrete consequence: **the only test that can actually prove
the `#155` fix cannot run in CI as CI is currently configured.** Levels 1 and 2 would run and pass;
level 3 would skip. A skipped concurrency test reports green.

This is an owner decision because both options cost something real:

| Option | What it costs | What it buys |
|---|---|---|
| **(a)** Add a `postgres` service to the `pytest` job | CI time on every PR; one workflow change, which is infrastructure, not product code | The contract is proven on every commit, automatically, forever |
| **(b)** Keep CI as-is; run level 3 locally against PostgreSQL and attach the output to the R1 PR | Nothing recurring | Proof exists once, for one commit, by hand. A later regression is invisible |

**Recommendation: (a).** The roadmap makes R1 the gate on OPS1's deployment stop — "do not serve
concurrent external users before R1 is merged and its concurrency tests pass". A gate whose test
skips in CI is not a gate. The cost is one `services:` block on one job, and PostgreSQL is already
the production target under `KHEPRI-DEC-008`'s capability contract, so the test would run against
the engine the product actually uses rather than a stand-in.

Note the scope boundary: adding the service is a **CI change, not product code**, and the roadmap's
Codex prompt lists "CI, or deployment changes" as forbidden scope unless explicitly listed. So if
(a) is chosen it must be named explicitly in the R1-02 task authorization, or split into its own
one-file infrastructure PR ahead of R1-03. The second is cleaner and is what this note recommends.

If (b) is chosen instead, record it as a deliberate acceptance with its expiry condition — that
level 3 must be wired into CI before OPS1-02 provisions any environment serving concurrent users —
rather than leaving it as an implementer's default.
