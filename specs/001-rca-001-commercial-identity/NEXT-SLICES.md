# The next three bounded slices

**Task:** `R0-05` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Scope is deliberately three
slices, not the whole roadmap.

**Baseline:** `main` @ `dcb63da`, 2026-08-14 (was `ebfbe77` when written; updated by `R2-10`).

**This maps existing issues to existing roadmap task IDs.** It creates no authority, approves
nothing, and adds no requirement. Implementation of any task below still needs the owner's explicit
approval of that task ID, per the roadmap's Definition of Ready.

**Where `R0-01` went.** Its stated output is a current-state matrix. Rather than a fourth document
restating what three others already carry, the snapshot is recorded as the shared baseline block at
the top of this file, `STATUS.md`, and `SUPERSEDED.md` — originally all three pinned to `ebfbe77`
with the same open issues, merged slices, and migration head. There is no separate `R0-01` artifact,
and its absence is not an incomplete Slice A. `R2-10` re-pinned this file and `STATUS.md` to
`95760a4`; `SUPERSEDED.md` records what was superseded at a moment in time and stays at `ebfbe77`
deliberately.

---

## Slice 1 — `#155`, the FR-013 transaction boundary → `R1`

| | |
|---|---|
| Issue | `#155` — **closed** at `c8c6edb` |
| Roadmap | `R1-01` … `R1-06` — **complete** |
| Design | `2026-08-13-r1-01-transaction-boundary-design.md`, `2026-08-13-r1-02-store-contract-design.md` |
| Delivered | `apply_owner_reducing_change`, the named `owner_memberships_for_update` lock, a single SQL expression of the effective-owner rule, a PostgreSQL CI service, and three deterministic concurrency tests |
| Migration | none — no schema change was needed |

**Why it was first.** The roadmap's deployment stop gate: "Do not serve concurrent external users
before R1 is merged and its concurrency tests pass." `R2`'s revocation and demotion are the same
guard-then-write shape, so building membership first would have duplicated a known defect across
three call sites instead of fixing it at one.

**The gate was cleared on tests green against still-broken code, and is re-cleared by `ac7143b`
(`#175`), not by `R1`.** `R1`'s lock covered one owner row per organization, so three callers
disabling three *different* owners of one organization locked pairwise-disjoint single-row sets and
`FOR UPDATE` had nothing to block on: all three read "another owner exists", all three committed,
zero owners remained. It surfaced during `R2` as an intermittent CI failure that passed on rerun.
Recorded because "R1's tests passed" was true and insufficient.

**What `R2` inherits.** `R2-06` must route revoke and demote through
`apply_owner_reducing_change` rather than adding a second final-owner guard. Two findings from R1
apply directly to it:

- a two-thread concurrency test is **not** a reliable proof of this class of defect. The two-owner
  test passed against the broken code; only three contenders exposed it. `R2-06`'s proof needs at
  least three.
- `MemoryOrganizationStore` now requires its account store, and the shadowing duplicate in
  `test_rca001_organizations.py` is gone. There is one fake, and it must keep matching the SQL
  store's outcome vocabulary.

**The `count_owners` docstring follow-up is still open** — see the end of this file.

## Slice 2 — `#150`, membership lifecycle → `R2` — **DELIVERED**

| | |
|---|---|
| Issue | `#150` — **closed** at `95760a4` |
| Roadmap | `R2-01` … `R2-10` — **complete**, PRs `#165` … `#178` |
| Migration | `20260814_0013` (events + backfill), `_0014` (drop attribution), `_0015` (role CHECK). Head is `20260814_0015` |

**Requirements closed:** FR-012 (revocation), FR-013 (all three verbs — remove, downgrade, disable —
through one shared guard), FR-014 (append-only attribution on its own expiring table). FR-015's role
model is closed and CHECK-constrained; its owner-capability clause stays partial because invite is
`R4` and organization disablement has no operation. FR-020's revocation half is supplied, so it now
waits on invitations alone.

**The structural absence is removed.** `OrganizationStore` had exactly one write; it now has
promotion, demotion, revocation, and the retention purge.

**Two latent gaps recorded rather than closed**, both asserted in
`tests/test_rca001_guard_evidence.py` and neither currently reachable: `rca_membership_events` has no
role CHECK, and the domain records accept any string as a role. What prevents forgery today is that
no service takes a role as input. See `STATUS.md`.

**Three findings for whoever builds `R4` or `R6` on top of this:**

- **A green concurrency run proves nothing here.** `R1`'s residual defect (`#175`) passed CI about two
  runs in three and read as a flake; a parametrized probe measured it at 4 failures in 12. Every
  contention test now runs `ATTEMPTS = 10`. A `FOR UPDATE` lock serializes only where row sets
  *intersect* — the locked set must cover every row the guard's count reads, not just the row about
  to change.
- **Mutation-test the test, not only the code.** Four defects in this slice were found that way, two
  of them in tests that were green against broken code. Both failures were text matching standing in
  for structure; both were fixed by walking the AST.
- **The fake is a second implementation.** `MemoryOrganizationStore` mirrors ten protocol methods and
  has already diverged once in a way that made unit tests pass wrongly. Parity is now asserted by
  signature.

## Slice 3 — authentication sessions → `R3`

| | |
|---|---|
| Issue | none open yet — this slice needs one |
| Roadmap | `R3-01` … `R3-08` |
| Status | `R3-01` design merged; `R3-02` (domain types) may start now |
| Depends on | active `RCA-001` (met). **The migration slot is now free** — `R2` added its last migration at `20260814_0015`, so `R3-03` re-points `down_revision` there and needs no coordination |
| Migration | yes — `R3-03` adds a session table |

**Requirements it closes**, per `STATUS.md`: FR-003's second clause, FR-027, FR-029, FR-030, the
general half of FR-008's second clause, and the session halves of FR-022 and FR-035. It also gives
`assert_account_active` (`lifecycle.py:132`) its first production caller — that chokepoint already
ships and is deliberately unused.

**The structural absence it removes:** no session concept. Every `session` token in
`src/khepri/rca/` today is a docstring or SQLAlchemy's `sessionmaker`.

**Migrations are strictly serial**, and this constraint is now satisfied rather than pending: `R2`'s
three migrations are merged and `R3-03` is the only one in flight. It re-points `down_revision` to
`20260814_0015`. `R2` left no schema work outstanding — see the two recorded gaps in `STATUS.md`, one
of which is a future migration but belongs to no slice yet.

**Two owner decisions still gate `R3-03`**, per the `R3-01` design note §9: whether to hash the
session identifier at rest, and what the session horizon is (single absolute expiry versus sliding
renewal). Neither is settled, and `R3-03` writes schema that depends on both.

---

## Recommended order

```
R1 complete (#155 closed at c8c6edb; residual fixed by #175)
     |
     +-> R2 COMPLETE (#150 closed at 95760a4, R2-01...R2-10)
     |
     +-> R3-01 design merged
              |
              +-> R3-02 domain types      <-- may start now
              +-> R3-03 migration         <-- slot free; blocked on two owner decisions (S9)
```

Per the roadmap's concurrency limit for this repository and one owner: at most one high-risk
persistence branch, one independent domain or UI branch, and one docs branch at a time.

---

## Follow-up recorded here rather than lost

**`count_owners`' docstring — closed by `R1-04`, no issue needed.** It described the enabled and
not-purged conditions and omitted the `credential_digest IS NOT NULL` clause, which is the one that
matters most because re-enablement leaves the verifier destroyed under `KHEPRI-DEC-015` §5.

`R1-04` removed the drift at its source rather than patching the prose: the rule now has one
expression, `_effective_owner_conditions`, and the docstring names that function instead of
restating it. A test asserts it agrees with `Account.can_authenticate` across four account states.
The roadmap's instruction was "record as an issue, fix alongside R1" — R1 fixed it, so there is
nothing left to record.
