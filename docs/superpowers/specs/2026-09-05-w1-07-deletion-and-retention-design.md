# `W1-07` — Deletion, evidence, and the retention sweep

**Date:** 2026-09-05
**Requirements:** `RCA-005` `FR-123`, `FR-124`, `FR-126`; `KHEPRI-DEC-033` §5
**Status:** design, pending the owner's review
**Measured against:** `main` at `3867b8a`

## 1. Why this slice exists

`KHEPRI-DEC-033` §2 fixes a retention horizon for every class of retail content. §5 then says, in
the decision rather than only in its evidence, that **none of those horizons is enforced**: every
sweeper's only caller is `khepri.local.cli`, which the wheel excludes. The product states what must
happen and the deployed image does none of it.

Re-measured on `3867b8a` while writing this design, and still true:

- `pyproject.toml:78` — `exclude = ["src/khepri/local"]`
- Five retention sweepers exist under `khepri.rca` (`invitation_retention`, `lifecycle` ×2 —
  purge and event purge — `recovery_security`, `session_retention`). The sixth `sweep` method is
  `local/sweeper.py`'s, which is the *composition* of the others, not a sweeper of its own; it and
  `local/wiring.py` are both excluded from the wheel
- `rca/invitation_retention.py:40` — `INVITATION_HORIZON_IS_UNENFORCED = True`

`W1-07` is the only slice that can discharge §5.

Deletion on the workspace side is **built but unreachable**. Corrected here after reading
`store.py` while drafting the implementation plan — an earlier draft of this design claimed the
cascade was missing, and it is not. What `W1-02`/`W1-03` already deliver:

- `store.set_retention_state` locks the version row, writes its tombstone through
  `_tombstone_version`, and **cascades to every live run** via `_cascade_tombstone_to_runs`
- Its early return at `store.py:631` is already `FR-123`'s idempotent retry, and deliberately does
  not move `retention_changed_at` — `_tombstone_version`'s docstring names this as `FR-123`'s
  "no new deletion evidence"
- `tombstones_for_scope` reads both `VersionTombstone` and `RunTombstone` back

What is genuinely missing:

- `store.tombstone_dataset_version` has **no production caller** — only tests reach it
- No deletion **service or route**: a customer cannot delete anything
- No **evidence** write on the workspace side (`FR-124`)
- No **audit vocabulary** for deletion (§3.4)
- No **revocation ledger** anywhere (§3.5)

## 2. Two slices, and where the line falls

`DEC-033` §1 names three kinds of ending: owner-requested deletion, named cascade, and
retention-triggered purge. The split follows that distinction rather than inventing one.

### `W1-07a` — Deletion, evidence, and the restore guard
`FR-123`, `FR-124`, `FR-126`. Customer-triggered endings: owner-only cascading deletion, first-
deletion evidence, the `already_deleted` idempotent path, and a workspace-scoped revocation ledger.

### `W1-07b` — The retention sweep with a caller in the wheel
`KHEPRI-DEC-033` §5. Time-triggered endings: a `khepri.runtime` composition of the existing
sweepers plus a workspace sweeper, a console-script entry point, and evidence per §2 horizon.

**(a) precedes (b)** because the sweep's workspace half purges classes whose deletion verbs (a)
builds. Doing (b) first would sweep classes that have no deletion path.

**What the ordering costs, stated so it is not discovered later:** `DEC-033` §5's constraint — *no
surface may tell a customer that content expires automatically* — stays in force until (b) merges.

**(a) ships the capability, not a button.** Corrected during the plan's critical review: an earlier
draft said (a) ships deletion UI. It ships the owner-only route and its guarantees; the Data
surface's delete affordance, its confirmation and its bilingual copy belong to a later slice. This
keeps (a)'s review surface to the guarantees, and it means no customer-facing deletion copy ships
while §5's constraint is live. The copy check stays as a standing guard, proven able to fail.

## 3. `W1-07a` — design

### 3.1 The cascade is a table, not a sequence

`DEC-033` §2 assigns every class an ending. That mapping lives in `workspace/deletion_matrix.py` as data:
one row per class naming its post-trigger state (tombstone / purge / cascade-from-parent) and its
parent where it has one. The orchestration reads the table; it does not hand-write the order.

**Why data.** A hand-written cascade is a scope that disarms itself: add a class, and the sequence
that does not mention it deletes nothing while every test still passes. That failure has recurred
in this repo often enough to be recorded (*a guard that names its own scope disarms itself*; *a
membership table needs an extent assertion*). A table can carry an **extent assertion** — every
class in the §2 matrix has exactly one rule, and a workspace table with no rule fails a test.

**Scope, given the correction above.** The RCA-side cascade (version → runs) already exists. The
table's job is therefore to *assert* the matrix over the whole ending — including the RRA content
`SqlDeletionRepository` ends — not to re-implement the walk `store.py` performs.

### 3.2 What ends, and how

From `DEC-033` §2, unchanged and not re-derived here:

| Class | Ending under owner deletion |
|---|---|
| Dataset version | **Tombstone** (allowlist, §3) |
| Analysis run | **Tombstone**; cascades from its dataset version |
| Mapping / coverage manifest | Tombstoned with the version |
| Fact package | **Tombstone**; cascades from the run |
| Report bundle artifacts | **Purged**; the run's tombstone is the only trace |
| Narrative | **Purged** |
| Provenance record | Digests survive in the tombstone; nothing else |
| Raw upload / normalized events | **Purged** |
| Source profile | **Purged**; deleting a profile deletes no dataset version |

This cascade is already implemented by `_tombstone_version` and `_cascade_tombstone_to_runs`.
`W1-07a` gives `tombstone_dataset_version` its first production caller and asserts the cascade
against the matrix; it does not rebuild it.

### 3.3 Reuse, and the package boundary

RRA content already ends correctly: `SqlDeletionRepository.complete` deletes the profile, fact-
package, artifact and upload rows, which `G2-01` confirmed. `W1-07a` **calls** it and does not
reimplement it. `rra/deletion.py` also already carries `DeletionEvidence` with the content-free
shape and retry state `FR-124` requires.

`R7-01` §3 forbids `khepri.rca` and `khepri.rra` importing each other, so the composition happens in
`khepri.runtime` — the seam `W1-04b` established.

### 3.4 Evidence and idempotency (`FR-123`, `FR-124`)

- The **first** deletion writes one `DeletionEvidence` record per object per ending.
- A repeated request returns **the same response**, writes **no second evidence**, and emits **one**
  audit event with outcome `already_deleted`.
- Evidence is retained twelve months (`DEC-033` §2), which (b)'s sweep enforces.

**A migration is required and is not optional.** `AUDIT_ACTIONS` and `AUDIT_OUTCOMES` are
CHECK-constrained and today read:

```
ACTIONS : version_created, run_started, run_completed, run_failed, profile_remembered, profile_reused
OUTCOMES: completed, refused, already_recorded
OBJECTS : version, run, profile
```

Neither a delete action nor `already_deleted` is admitted. `FR-123` names `already_deleted`
literally, so `W1-07a` adds the `already_deleted` outcome and a delete action, with the CHECK
moved in the same migration. Note `already_recorded` already exists and is **not** the same thing
— reusing it would make the idempotency contract unreadable to the evidence consumer `FR-123`
names.

**One action ships, not three.** An earlier draft of this section promised `version_deleted` /
`run_deleted` / `profile_deleted`; `audit.py` defines `ACTION_VERSION_DELETED` alone, and that is
correct rather than incomplete. A dataset version is the only thing an owner deletes: runs end by
cascading from it (§3.2), and no route deletes a profile. An admitted action no code path can emit
is a *widening of the CHECK constraint with no caller* — the "defined but never attached" shape
this repo has met before — so the vocabulary stays as narrow as the endings that exist. `W1-07b`'s
sweep adds what its own horizons need. Corrected after review on `#382` compared this section
against `audit.py`.

### 3.5 The revocation ledger (`FR-126`)

**No revocation ledger exists anywhere in the tree.** `KHEPRI-DEC-015` §8 describes the pattern;
nothing implements it. `W1-07a` builds it **workspace-scoped**: deleted workspace object identifiers
only, holding opaque identifiers, revocation timestamps and status — nothing else, per §8's
"minimal and purpose-bound" rule.

It is deliberately not generalized to sessions, memberships and invitations. Those are named in §8
but have no requirement today, and their horizon is `OD-3`-bounded, which is a separate approval. A
later slice may generalize it; designing for four consumers with one requirement would be
authoring scope this slice does not hold.

Bounded by the fourteen-day backup horizon plus a margin. The ledger must itself be backed up, or
it cannot serve its purpose.

**The stated boundary of `FR-126`, and what is not closed here.** Review on `#382` observed that
`WorkspaceRevocationRow` lives in the *same schema as the rows it guards*, so a point-in-time
restore of that schema removes the ledger along with them and leaves nothing to consult. So:

- `FR-126` **holds** against in-database restoration — a row put back beneath the ORM, which is
  what defeats `_check_one_way_transitions` and is the shape a partial or scripted recovery takes.
- `FR-126` **does not hold** against restoring a whole-schema snapshot predating the deletion.

Closing the second requires the ledger to have a backup lifecycle of its own — a separate
database, a separate schedule, or an accepted limitation. That is a *backup topology* decision:
`KHEPRI-DEC-008` is `proposed`, AWS provisioning is frozen on cost, and `W1-07a` does not hold the
authority to author infrastructure policy. It is therefore recorded rather than implemented, and
`test_a_whole_schema_restore_predating_the_deletion_defeats_the_ledger` asserts the limitation as
it stands, so it cannot be mistaken for a guarantee and so the day the ledger moves, that test
fails and is rewritten. Filed for the owner.

### 3.6 Authorization

Owner-only (`FR-123`). A member cannot delete. The refusal is the uniform content-free denial, and
the test drives the **real route**, not the guard — a test that calls the check directly survives
deletion of its call site.

## 4. `W1-07b` — design

### 4.1 The caller

The composition moves from `local/sweeper.py` into `khepri.runtime`, exposed as a console script,
and gains a workspace sweeper for the classes `W1-07a` gives deletion verbs to.
This follows a precedent already recorded in `pyproject.toml:45`, for another command, in these
words: *"`khepri.runtime` rather than `khepri.local` deliberately: the wheel excludes
`src/khepri/local`, so a command there would be absent from the built artifact."*

Rejected: including `khepri/local` in the wheel — `pyproject.toml:70-76` records that it carries
local database credentials that "have no business in a published artifact". Rejected: a worker-loop
tick — `DEC-033` §5 says explicitly that the worker's per-claim sweep is *lease recovery, not
retention*, and coupling the two would blur exactly the distinction the decision draws.

### 4.2 The acceptance test that matters

§5's obligation is discharged by evidence **against the built wheel**, not the source tree. The test
builds the wheel and asserts the entry point resolves inside it — a source-tree assertion would pass
today and prove nothing, since the sweepers already exist in source.

`INVITATION_HORIZON_IS_UNENFORCED` is deleted in this slice, and its deletion is part of the
evidence.

## 5. Testing

**`W1-07a`**
- A cascade test per `DEC-033` §2 row that names one
- Extent: every workspace table has exactly one rule in the cascade table
- Repeated deletion — same response, no second evidence, one `already_deleted` audit event
- A member cannot delete, driven through the real route
- A restored deleted object is not readable (ledger)
- Copy check: no surface implies automatic expiry (see §2)
- Mutation: each guard fails under a mutant that removes it

**`W1-07b`**
- The entry point resolves **in the built wheel**
- One test per §2 horizon
- `INVITATION_HORIZON_IS_UNENFORCED` is gone

## 6. Non-goals

- **`G2-01` F-2 — plaintext documents.** `rra_dataset_profiles.document` and
  `rra_fact_packages.document` hold customer labels and values as unencrypted JSON. `DEC-033` §5
  says whether to envelope-encrypt them is an `RRA-002` reading and "is not decided here". Deletion
  removes these rows, so it is an at-rest concern, not a deletion gap. **Left to the owner.**
- **A general revocation ledger** for sessions, memberships and invitations (§3.5).
- **`W1-11` repeat-use telemetry** — excluded by `RCA-005` and `KHEPRI-DEC-015` §3.
- **Comparison** — `G4/C1`'s.
- **`W1-10`** isolation hardening, which follows this slice and exercises its routes.

## 7. Risks

1. **Shipping deletion without the sweep** leaves every horizon unenforced while the product looks
   finished. Mitigated by (b) following immediately, and by §2's copy check in (a).
2. **Testing the guard rather than the caller.** Every authorization and cascade test drives the
   real route.
3. **A cascade that silently misses a class.** Mitigated by the extent assertion (§3.1).
4. **Asserting the wheel from the source tree.** The §5 test builds the artifact (§4.2).
5. **A redundant guard with one shared test.** `FR-123`'s idempotency has three separate claims —
   same response, no second evidence, one audit event. Each needs its own evidence; one outcome test
   passes with any two of the three broken.
