# The next three bounded slices

**Task:** `R0-05` in `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`. Scope is deliberately three
slices, not the whole roadmap.

**Baseline:** `main` @ `ebfbe77`, 2026-08-13.

**This maps existing issues to existing roadmap task IDs.** It creates no authority, approves
nothing, and adds no requirement. Implementation of any task below still needs the owner's explicit
approval of that task ID, per the roadmap's Definition of Ready.

**Where `R0-01` went.** Its stated output is a current-state matrix. Rather than a fourth document
restating what three others already carry, the snapshot is recorded as the shared baseline block at
the top of this file, `STATUS.md`, and `SUPERSEDED.md` — all three pinned to `ebfbe77` with the same
open issues, merged slices, and migration head. There is no separate `R0-01` artifact, and its
absence is not an incomplete Slice A.

---

## Slice 1 — `#155`, the FR-013 transaction boundary → `R1`

| | |
|---|---|
| Issue | `#155` — the FR-013 guard and its write are not in one transaction |
| Roadmap | `R1-01` … `R1-06` |
| Status | `R1-01` complete; design note at `docs/superpowers/specs/2026-08-13-r1-01-transaction-boundary-design.md` |
| Blocks | `R2` (revoke and demote inherit the same seam), and OPS1's deployment stop gate |
| Migration | none — the recommended design needs no schema change |

**Why first.** The roadmap's deployment stop gate: "Do not serve concurrent external users before
R1 is merged and its concurrency tests pass." `R2`'s revocation and demotion are the same
guard-then-write shape, so building membership first would duplicate a known defect across three
call sites instead of fixing it at one.

**Remaining tasks:** `R1-02` (transaction-scoped store contract and fake semantics), `R1-03` (RED
concurrency test), `R1-04` (one atomic guard-and-write boundary), `R1-05` (prove non-owner-reducing
operations take no unnecessary locks), `R1-06` (close `#155`).

**One decision is outstanding before `R1-03`.** The design note §8 records it: CI defines no
PostgreSQL service, and the RCA suite runs in-memory SQLite with `StaticPool`, so the only test that
proves the concurrency contract cannot run in CI as configured. Recommended resolution is a separate
one-file infrastructure PR adding the service. This is an owner decision, not an implementer's
default.

## Slice 2 — `#150`, membership lifecycle → `R2`

| | |
|---|---|
| Issue | `#150` — membership slice: roles, revocation, FR-013 guard, expiring audit events |
| Roadmap | `R2-01` … `R2-10` |
| Status | `R2-01` (design) may start now; implementation waits on `R1` |
| Depends on | `R1`'s merged transaction seam, for `R2-06` |
| Migration | yes — `R2-02` adds `rca_membership_events`. Head is `20260813_0012`; no other migration may merge alongside it |

**Requirements it closes**, per `STATUS.md`: FR-012 (revocation, currently absent as an operation),
FR-014's second gap (the current-state row cannot represent a transition), FR-015 (no `member`
constant, `role` unconstrained), FR-013's remove and downgrade clauses, and FR-020's revocation
half.

**The structural absence it removes:** no membership write operations. `stores.py`'s
`OrganizationStore` exposes exactly one write, `create_organization`.

**Ordering constraint worth stating early.** `R2-01` is design only. The first *implementation* PR
begins only after `R1`'s transaction boundary is merged, because `R2-06` applies that same invariant
to revoke and demote.

## Slice 3 — authentication sessions → `R3`

| | |
|---|---|
| Issue | none open yet — this slice needs one |
| Roadmap | `R3-01` … `R3-08` |
| Status | `R3-01` (design) may start now, in parallel with `R2-01` |
| Depends on | active `RCA-001` (met). Migration must coordinate with `R2-02` — see below |
| Migration | yes — `R3-03` adds a session table |

**Requirements it closes**, per `STATUS.md`: FR-003's second clause, FR-027, FR-029, FR-030, the
general half of FR-008's second clause, and the session halves of FR-022 and FR-035. It also gives
`assert_account_active` (`lifecycle.py:132`) its first production caller — that chokepoint already
ships and is deliberately unused.

**The structural absence it removes:** no session concept. Every `session` token in
`src/khepri/rca/` today is a docstring or SQLAlchemy's `sessionmaker`.

**Migrations are strictly serial.** `R2-02` and `R3-03` each add a migration and neither may merge
alongside the other. The second to merge re-points its `down_revision`. Design and domain work on
`R2` and `R3` may overlap; their schema merges may not.

---

## Recommended order

```
R1-01 (done) -> R1-02..R1-05 -> R1-06 close #155
                     |
                     +-> R2-01 design (may start now, in parallel)
                     +-> R3-01 design (may start now, in parallel)
                            |
                            R2 implementation -> R3 implementation
                            (serialize the two migrations)
```

Per the roadmap's concurrency limit for this repository and one owner: at most one high-risk
persistence branch, one independent domain or UI branch, and one docs branch at a time.

---

## Follow-up recorded here rather than lost

**`count_owners`' docstring is incomplete.** `src/khepri/rca/persistence.py:388-390` describes the
enabled and not-purged conditions but omits the `credential_digest IS NOT NULL` clause the query
actually applies at `:409` — which is the clause that matters most, because re-enablement leaves the
verifier destroyed under `KHEPRI-DEC-015` §5.

The code is correct; the prose is incomplete. The master roadmap's verification record already names
this and says: record as an issue, fix alongside `R1`. It is a one-paragraph docstring change and
belongs in an `R1` PR that is touching the file anyway, not in a separate drive-by commit.
